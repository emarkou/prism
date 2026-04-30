import webbrowser
from datetime import datetime, timezone
from typing import Optional

from rich.text import Text
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Static

from ..github.models import PR, DashboardData


def _age(dt: datetime) -> str:
    delta = datetime.now(timezone.utc) - dt
    s = int(delta.total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{delta.days}d"


def _ci_dot(status: str) -> str:
    return {"passing": "🟢", "failing": "🔴", "running": "🟡", "none": "⚫"}.get(status, "⚫")


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def _decision_badge(pr: PR) -> tuple[str, str]:
    rd = pr.review_decision
    if rd == "APPROVED":
        return "✓ approved", "green"
    if rd == "CHANGES_REQUESTED":
        return "✗ changes", "red"
    if pr.is_draft:
        return "draft", "medium_purple1"
    return "needs review", "cyan"


class PendingReviewsWidget(Static):
    can_focus = True

    BINDINGS = [
        Binding("up,k", "move_up", "Up", show=False),
        Binding("down,j", "move_down", "Down", show=False),
        Binding("enter,o", "open_pr", "Open", show=False),
    ]

    selected: reactive[int] = reactive(0)
    data: reactive[Optional[DashboardData]] = reactive(None)

    def render(self) -> Text:
        w = self.content_size.width or 60
        fixed = 18
        max_title = max(10, w - fixed)
        max_repo = max(10, w - 24)

        text = Text()
        text.append(" PENDING REVIEWS\n", style="bold white")
        text.append("─" * (w - 1) + "\n", style="grey50")

        prs = self._prs()
        if not prs:
            text.append("\n  no reviews requested\n", style="grey50 italic")
            return text

        for i, pr in enumerate(prs):
            selected = i == self.selected
            bg = "on grey19" if selected else ""

            ci = _ci_dot(pr.ci_status)
            badge_text, badge_style = _decision_badge(pr)
            age = _age(pr.updated_at)
            num = f"#{pr.number:<5}"
            title = _trunc(pr.title, max_title)

            text.append(f" {num} ", style=f"grey58 {bg}")
            text.append(f"{title:<{max_title}}", style=f"white {bg}")
            text.append(f" {ci}", style=bg)
            text.append(f" {age:<6}\n", style=f"grey58 {bg}")

            repo = _trunc(pr.repo, max_repo)
            text.append(f"       {repo:<{max_repo}}", style=f"grey50 {bg}")
            text.append(f" [{badge_text}]\n", style=f"{badge_style} {bg}")

            if i < len(prs) - 1:
                text.append("  " + "·" * max(0, w - 3) + "\n", style="grey23")

        return text

    def _prs(self) -> list[PR]:
        if self.data is None:
            return []
        return self.data.review_prs

    def action_move_up(self) -> None:
        prs = self._prs()
        if prs:
            self.selected = max(0, self.selected - 1)
            self.refresh()

    def action_move_down(self) -> None:
        prs = self._prs()
        if prs:
            self.selected = min(len(prs) - 1, self.selected + 1)
            self.refresh()

    def action_open_pr(self) -> None:
        prs = self._prs()
        if prs and 0 <= self.selected < len(prs):
            webbrowser.open(prs[self.selected].url)

    def update_data(self, data: DashboardData) -> None:
        self.data = data
        if self.selected >= len(self._prs()):
            self.selected = max(0, len(self._prs()) - 1)
        self.refresh()
