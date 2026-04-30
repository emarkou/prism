import webbrowser
from datetime import datetime, timezone
from typing import Optional

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from ..github.models import InboxItem, DashboardData


_CATEGORY_ICONS = {
    "review_requested": "◎",
    "unread_comment": "💬",
    "merge_conflict": "⚠",
}

_CATEGORY_COLORS = {
    "review_requested": "cyan",
    "unread_comment": "yellow",
    "merge_conflict": "orange1",
}


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


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


class InboxWidget(Static):
    can_focus = True

    BINDINGS = [
        Binding("up,k", "move_up", "Up", show=False),
        Binding("down,j", "move_down", "Down", show=False),
        Binding("enter,o", "open_item", "Open", show=False),
        Binding("x", "dismiss", "Dismiss", show=False),
    ]

    selected: reactive[int] = reactive(0)
    data: reactive[Optional[DashboardData]] = reactive(None)
    _dismissed: set[str] = set()

    def render(self) -> Text:
        w = self.content_size.width or 60

        # " ◎ " (3) + " age   " (8) = 11 reserved for row1; rest for title
        max_title = max(10, w - 11)
        # "    " (4 indent) for row2; rest for repo+pr
        max_repo = max(10, w - 5)

        text = Text()
        text.append(" INBOX\n", style="bold white")
        text.append("─" * (w - 1) + "\n", style="grey50")

        items = self._visible_items()
        if not items:
            text.append("\n  inbox zero\n", style="bold green italic")
            return text

        for i, item in enumerate(items):
            selected = i == self.selected
            bg = "on grey19" if selected else ""

            icon = _CATEGORY_ICONS.get(item.category, "·")
            icon_color = _CATEGORY_COLORS.get(item.category, "white")
            age = _age(item.event_at)

            title = _trunc(item.title, max_title)
            repo_pr = _trunc(f"{item.repo} #{item.pr_number}", max_repo)

            text.append(f" {icon} ", style=f"{icon_color} {bg}")
            text.append(f"{title:<{max_title}}", style=f"white {bg}")
            text.append(f" {age:<7}\n", style=f"grey58 {bg}")
            text.append(f"    {repo_pr}\n", style=f"grey50 {bg}")

            if i < len(items) - 1:
                text.append("  " + "·" * max(0, w - 3) + "\n", style="grey23")

        return text

    def _visible_items(self) -> list[InboxItem]:
        if self.data is None:
            return []
        return [
            item for item in self.data.inbox_items
            if not item.dismissed and item.url not in self._dismissed
        ]

    def action_move_up(self) -> None:
        items = self._visible_items()
        if items:
            self.selected = max(0, self.selected - 1)
            self.refresh()

    def action_move_down(self) -> None:
        items = self._visible_items()
        if items:
            self.selected = min(len(items) - 1, self.selected + 1)
            self.refresh()

    def action_open_item(self) -> None:
        items = self._visible_items()
        if items and 0 <= self.selected < len(items):
            webbrowser.open(items[self.selected].url)

    def action_dismiss(self) -> None:
        items = self._visible_items()
        if not items or not (0 <= self.selected < len(items)):
            return
        self._dismissed.add(items[self.selected].url)
        new_count = len(self._visible_items())
        if self.selected >= new_count:
            self.selected = max(0, new_count - 1)
        self.refresh()

    def update_data(self, data: DashboardData) -> None:
        self.data = data
        items = self._visible_items()
        if self.selected >= len(items):
            self.selected = max(0, len(items) - 1)
        self.refresh()
