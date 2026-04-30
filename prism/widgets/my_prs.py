import webbrowser
from datetime import datetime, timezone
from typing import Optional

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
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


def _review_badge(pr: PR) -> tuple[str, str]:
    if pr.is_draft:
        return "draft", "medium_purple1"
    rd = pr.review_decision
    if rd == "APPROVED":
        return "✓ approved", "green"
    if rd == "CHANGES_REQUESTED":
        return "✗ changes", "red"
    if pr.review_count > 0:
        return f"● {pr.review_count} reviews", "grey62"
    return "awaiting review", "grey50"


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


class MyPRsWidget(Static):
    can_focus = True

    BINDINGS = [
        Binding("up,k", "move_up", "Up", show=False),
        Binding("down,j", "move_down", "Down", show=False),
        Binding("enter,o", "open_pr", "Open", show=False),
        Binding("m", "toggle_draft", "Toggle draft", show=False),
    ]

    selected: reactive[int] = reactive(0)
    data: reactive[Optional[DashboardData]] = reactive(None)

    def render(self) -> Text:
        # content_size.width = inner width after border+padding; fall back if not laid out yet
        w = self.content_size.width or 60

        # fixed cols: " #NNNNN " (8) + " 🟢" (3) + " age   " (7) = 18 reserved; rest for title
        fixed = 18
        max_title = max(10, w - fixed)
        # repo row: "       " (7 indent) + badge ~16 = 23 reserved
        max_repo = max(10, w - 24)

        text = Text()
        text.append(" MY OPEN PRS\n", style="bold white")
        text.append("─" * (w - 1) + "\n", style="grey50")

        prs = self._prs()
        if not prs:
            text.append("\n  no open pull requests\n", style="grey50 italic")
            return text

        for i, pr in enumerate(prs):
            selected = i == self.selected
            bg = "on grey19" if selected else ""

            ci = _ci_dot(pr.ci_status)
            badge_text, badge_style = _review_badge(pr)
            conflict = " ⚠ conflict" if pr.mergeable == "CONFLICTING" else ""
            age = _age(pr.updated_at)

            num = f"#{pr.number:<5}"
            title = _trunc(pr.title, max_title)

            text.append(f" {num} ", style=f"grey58 {bg}")
            text.append(f"{title:<{max_title}}", style=f"white {bg}")
            text.append(f" {ci}", style=bg)
            text.append(f" {age:<6}", style=f"grey58 {bg}")
            if conflict:
                text.append(conflict, style=f"yellow {bg}")
            text.append("\n")

            repo = _trunc(pr.repo, max_repo)
            text.append(f"       {repo:<{max_repo}}", style=f"grey50 {bg}")
            text.append(f" [{badge_text}]", style=f"{badge_style} {bg}")
            text.append("\n")

            if i < len(prs) - 1:
                text.append("  " + "·" * max(0, w - 3) + "\n", style=f"grey23")

        return text

    def _prs(self) -> list[PR]:
        if self.data is None:
            return []
        return self.data.my_prs

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

    def action_toggle_draft(self) -> None:
        prs = self._prs()
        if not prs or not (0 <= self.selected < len(prs)):
            return
        self.post_message(ToggleDraftRequest(pr=prs[self.selected]))

    def update_data(self, data: DashboardData) -> None:
        self.data = data
        if self.selected >= len(self._prs()):
            self.selected = max(0, len(self._prs()) - 1)
        self.refresh()


class ToggleDraftRequest(Message):
    def __init__(self, pr: PR):
        super().__init__()
        self.pr = pr
