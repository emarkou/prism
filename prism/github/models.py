from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CheckRun:
    name: str
    status: str  # QUEUED, IN_PROGRESS, COMPLETED
    conclusion: Optional[str] = None  # SUCCESS, FAILURE, NEUTRAL, CANCELLED, SKIPPED, TIMED_OUT


@dataclass
class PR:
    number: int
    title: str
    url: str
    repo: str
    created_at: datetime
    updated_at: datetime
    is_draft: bool
    mergeable: str  # MERGEABLE, CONFLICTING, UNKNOWN
    review_decision: Optional[str]  # APPROVED, CHANGES_REQUESTED, REVIEW_REQUIRED, None
    review_count: int
    ci_status: str  # passing, failing, running, none
    check_runs: list[CheckRun] = field(default_factory=list)
    author_login: str = ""


@dataclass
class InboxItem:
    category: str  # review_requested, unread_comment, merge_conflict
    title: str
    url: str
    repo: str
    pr_number: int
    event_at: datetime
    dismissed: bool = False


@dataclass
class ContribWeek:
    week_start: datetime
    commit_count: int
    pr_count: int
    review_count: int
    contribution_days: list[int] = field(default_factory=list)  # count per day


@dataclass
class RepoStats:
    name: str
    commit_count: int


@dataclass
class DashboardData:
    viewer_login: str = ""
    viewer_name: str = ""
    my_prs: list[PR] = field(default_factory=list)
    review_prs: list[PR] = field(default_factory=list)
    inbox_items: list[InboxItem] = field(default_factory=list)
    ci_prs: list[PR] = field(default_factory=list)
    contrib_weeks: list[ContribWeek] = field(default_factory=list)
    total_commits_4w: int = 0
    total_reviews_4w: int = 0
    streak_days: int = 0
    repo_stats: list[RepoStats] = field(default_factory=list)
    rate_limit_remaining: int = 5000
    rate_limit_reset_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    fetch_error: Optional[str] = None
    partial_data: bool = False
