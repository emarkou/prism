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


def _check_summary(pr: PR) -> tuple[str, str]:
    checks = pr.check_runs
    if not checks:
        return "", "grey50"
    if pr.ci_status == "failing":
        failing = [c.name for c in checks if c.conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED")]
        if failing:
            return _trunc(failing[0], 20), "red"
    if pr.ci_status == "passing":
        total = len(checks)
        return f"{total}/{total} checks", "green"
    running = sum(1 for c in checks if c.status in ("QUEUED", "IN_PROGRESS"))
    return f"{running}/{len(checks)} running", "yellow"


class CIStatusWidget(Static):
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

        # " 🟢 " (4) + " age   " (8) = 12 reserved; rest for title
        max_title = max(10, w - 12)
        # "    " (4 indent) + " [summary ~16]" = 20 reserved; rest for repo
        max_repo = max(10, w - 22)

        text = Text()
        text.append(" CI STATUS\n", style="bold white")
        text.append("─" * (w - 1) + "\n", style="grey50")

        prs = self._prs()
        if not prs:
            text.append("\n  no recent ci runs\n", style="grey50 italic")
            return text

        for i, pr in enumerate(prs):
            selected = i == self.selected
            bg = "on grey19" if selected else ""

            dot = _ci_dot(pr.ci_status)
            age = _age(pr.updated_at)
            summary_text, summary_color = _check_summary(pr)

            title = _trunc(pr.title, max_title)
            repo_pr = _trunc(f"{pr.repo} #{pr.number}", max_repo)

            text.append(f" {dot} ", style=bg)
            text.append(f"{title:<{max_title}}", style=f"white {bg}")
            text.append(f" {age:<7}\n", style=f"grey58 {bg}")
            text.append(f"    {repo_pr:<{max_repo}}", style=f"grey50 {bg}")
            if summary_text:
                text.append(f" [{summary_text}]", style=f"{summary_color} {bg}")
            text.append("\n")

            if i < len(prs) - 1:
                text.append("  " + "·" * max(0, w - 3) + "\n", style="grey23")

        return text

    def _prs(self) -> list[PR]:
        if self.data is None:
            return []
        return self.data.ci_prs

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
