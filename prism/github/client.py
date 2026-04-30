import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

from .models import (
    CheckRun, PR, InboxItem, ContribWeek, RepoStats, DashboardData
)
from .queries import DASHBOARD_QUERY, TOGGLE_DRAFT_MUTATION, MARK_READY_MUTATION, PR_NODE_ID_QUERY

GRAPHQL_URL = "https://api.github.com/graphql"
log = logging.getLogger(__name__)


def _parse_dt(s: Optional[str]) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _ci_status_from_rollup(rollup: Optional[dict]) -> tuple[str, list[CheckRun]]:
    if not rollup:
        return "none", []
    state = (rollup.get("state") or "").upper()
    checks = []
    for node in (rollup.get("contexts") or {}).get("nodes") or []:
        if "name" in node:
            checks.append(CheckRun(
                name=node.get("name", ""),
                status=node.get("status", "COMPLETED"),
                conclusion=node.get("conclusion"),
            ))
        elif "context" in node:
            gh_state = (node.get("state") or "").upper()
            conclusion = None
            if gh_state == "SUCCESS":
                conclusion = "SUCCESS"
            elif gh_state in ("FAILURE", "ERROR"):
                conclusion = "FAILURE"
            checks.append(CheckRun(
                name=node.get("context", ""),
                status="COMPLETED" if gh_state in ("SUCCESS", "FAILURE", "ERROR") else "IN_PROGRESS",
                conclusion=conclusion,
            ))

    if state == "SUCCESS":
        ci = "passing"
    elif state in ("FAILURE", "ERROR"):
        ci = "failing"
    elif state in ("PENDING", "EXPECTED"):
        ci = "running"
    else:
        ci = "none" if not checks else "running"
    return ci, checks


def _parse_pr_node(node: dict) -> PR:
    repo = node.get("repository", {}).get("nameWithOwner", "")
    rollup = node.get("statusCheckRollup")
    ci_status, checks = _ci_status_from_rollup(rollup)
    return PR(
        number=node.get("number", 0),
        title=node.get("title", ""),
        url=node.get("url", ""),
        repo=repo,
        created_at=_parse_dt(node.get("createdAt")),
        updated_at=_parse_dt(node.get("updatedAt")),
        is_draft=node.get("isDraft", False),
        mergeable=node.get("mergeable", "UNKNOWN"),
        review_decision=node.get("reviewDecision"),
        review_count=(node.get("reviews") or {}).get("totalCount", 0),
        ci_status=ci_status,
        check_runs=checks,
    )


def _compute_streak(weeks: list[dict]) -> int:
    days: list[int] = []
    for week in weeks:
        for day in week.get("contributionDays") or []:
            days.append(day.get("contributionCount", 0))
    streak = 0
    for count in reversed(days):
        if count > 0:
            streak += 1
        else:
            break
    return streak


def _parse_contrib_weeks(raw_weeks: list[dict]) -> list[ContribWeek]:
    result = []
    for week in raw_weeks:
        days = week.get("contributionDays") or []
        result.append(ContribWeek(
            week_start=_parse_dt(week.get("firstDay")),
            commit_count=sum(d.get("contributionCount", 0) for d in days),
            pr_count=0,
            review_count=0,
            contribution_days=[d.get("contributionCount", 0) for d in days],
        ))
    return result


class GitHubClient:
    def __init__(self, token: str):
        self._token = token
        self._http = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
            },
            timeout=30.0,
        )

    async def close(self):
        await self._http.aclose()

    async def _graphql(self, query: str, variables: dict) -> dict:
        resp = await self._http.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
        )
        resp.raise_for_status()
        return resp.json()

    async def fetch_dashboard(self, max_prs: int = 20, max_inbox: int = 20) -> DashboardData:
        now = datetime.now(timezone.utc)
        contrib_from = (now - timedelta(weeks=12)).isoformat()
        review_search = "is:pr is:open review-requested:@me"

        data = DashboardData(fetched_at=now)
        partial = False

        try:
            result = await self._graphql(DASHBOARD_QUERY, {
                "contribFrom": contrib_from,
                "reviewSearch": review_search,
                "prFirst": max_prs,
                "inboxFirst": max_inbox,
            })
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise RuntimeError("GitHub token invalid (401). Check GITHUB_TOKEN.") from e
            data.fetch_error = f"HTTP {e.response.status_code}"
            return data
        except Exception as e:
            data.fetch_error = str(e)
            return data

        gql_errors = result.get("errors") or []
        if gql_errors:
            partial = True
            _log_errors(gql_errors)

        raw = result.get("data") or {}
        viewer = raw.get("viewer") or {}
        data.viewer_login = viewer.get("login", "")
        data.viewer_name = viewer.get("name", "") or data.viewer_login

        # My PRs
        pr_nodes = (viewer.get("pullRequests") or {}).get("nodes") or []
        my_prs = [_parse_pr_node(n) for n in pr_nodes]
        for pr in my_prs:
            pr.author_login = data.viewer_login
        # Sort: non-draft by updated_at desc, drafts last
        my_prs.sort(key=lambda p: (p.is_draft, -p.updated_at.timestamp()))
        data.my_prs = my_prs

        # Review-requested PRs (dedicated tile + inbox)
        review_nodes = (raw.get("reviewRequested") or {}).get("nodes") or []
        review_prs = [_parse_pr_node(n) for n in review_nodes if n]
        review_prs.sort(key=lambda p: -p.updated_at.timestamp())
        data.review_prs = review_prs

        inbox: list[InboxItem] = []
        for node in review_nodes:
            if not node:
                continue
            inbox.append(InboxItem(
                category="review_requested",
                title=node.get("title", ""),
                url=node.get("url", ""),
                repo=(node.get("repository") or {}).get("nameWithOwner", ""),
                pr_number=node.get("number", 0),
                event_at=_parse_dt(node.get("updatedAt")),
            ))

        # Inbox — merge conflicts from own PRs
        for pr in my_prs:
            if pr.mergeable == "CONFLICTING":
                inbox.append(InboxItem(
                    category="merge_conflict",
                    title=pr.title,
                    url=pr.url,
                    repo=pr.repo,
                    pr_number=pr.number,
                    event_at=pr.updated_at,
                ))

        data.inbox_items = inbox

        # CI status — all PRs (own + review-requested), deduplicated
        ci_map: dict[str, PR] = {}
        for pr in my_prs:
            ci_map[pr.url] = pr
        for node in review_nodes:
            if not node:
                continue
            pr = _parse_pr_node(node)
            if pr.url not in ci_map:
                ci_map[pr.url] = pr
        ci_prs = list(ci_map.values())
        # Sort: failing first, then running, then passing
        order = {"failing": 0, "running": 1, "passing": 2, "none": 3}
        ci_prs.sort(key=lambda p: (order.get(p.ci_status, 3), -p.updated_at.timestamp()))
        data.ci_prs = ci_prs

        # Contributions
        contrib_coll = viewer.get("contributionsCollection") or {}
        cal = contrib_coll.get("contributionCalendar") or {}
        raw_weeks = cal.get("weeks") or []
        data.contrib_weeks = _parse_contrib_weeks(raw_weeks)
        data.total_commits_4w = sum(
            w.commit_count for w in data.contrib_weeks[-4:]
        )
        data.total_reviews_4w = contrib_coll.get("totalPullRequestReviewContributions", 0)
        data.streak_days = _compute_streak(raw_weeks)

        # Per-repo stats
        repo_contribs = contrib_coll.get("commitContributionsByRepository") or []
        repo_stats = []
        for rc in repo_contribs:
            repo_name = (rc.get("repository") or {}).get("nameWithOwner", "")
            count = (rc.get("contributions") or {}).get("totalCount", 0)
            if count > 0:
                repo_stats.append(RepoStats(name=repo_name, commit_count=count))
        repo_stats.sort(key=lambda r: -r.commit_count)
        data.repo_stats = repo_stats[:5]

        # Rate limit
        rl = raw.get("rateLimit") or {}
        data.rate_limit_remaining = rl.get("remaining", 5000)
        reset_str = rl.get("resetAt")
        if reset_str:
            data.rate_limit_reset_at = _parse_dt(reset_str)

        data.partial_data = partial
        return data

    async def get_pr_node_id(self, owner: str, repo: str, number: int) -> Optional[str]:
        try:
            result = await self._graphql(PR_NODE_ID_QUERY, {
                "owner": owner, "repo": repo, "number": number,
            })
            return ((result.get("data") or {})
                    .get("repository", {})
                    .get("pullRequest", {})
                    .get("id"))
        except Exception:
            return None

    async def toggle_draft(self, pr: PR) -> bool:
        parts = pr.repo.split("/", 1)
        if len(parts) != 2:
            return False
        node_id = await self.get_pr_node_id(parts[0], parts[1], pr.number)
        if not node_id:
            return False
        mutation = TOGGLE_DRAFT_MUTATION if not pr.is_draft else MARK_READY_MUTATION
        try:
            await self._graphql(mutation, {"prId": node_id})
            return True
        except Exception:
            return False


def _log_errors(errors: list[dict]) -> None:
    log_path = Path.home() / ".prism" / "error.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(f"\n--- {datetime.now(timezone.utc).isoformat()} ---\n")
        for e in errors:
            f.write(str(e) + "\n")
