from typing import Optional

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ..github.models import DashboardData

_BLOCKS = "▁▂▃▄▅▆▇█"


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


class ContributionsWidget(Static):
    can_focus = True

    data: reactive[Optional[DashboardData]] = reactive(None)

    def render(self) -> Text:
        w = self.content_size.width or 60

        text = Text()
        text.append(" CONTRIBUTIONS\n", style="bold white")
        text.append("─" * (w - 1) + "\n", style="grey50")

        if self.data is None:
            text.append("\n  loading…\n", style="grey50 italic")
            return text

        d = self.data

        # Stat boxes
        def box(value: str, label: str) -> None:
            text.append(f" {value:>6} ", style="bold cyan")
            text.append(f"{label}\n", style="grey62")

        box(str(d.total_commits_4w), "commits · 4w")
        box(str(len(d.my_prs)), "prs open")
        box(str(d.total_reviews_4w), "reviews given")
        box(str(d.streak_days), "day streak 🔥")

        text.append("\n")

        # Sparkline — use full available width minus 2 margin
        bar_count = min(len(d.contrib_weeks), max(4, w - 4))
        weeks = d.contrib_weeks[-bar_count:]
        commit_counts = [wk.commit_count for wk in weeks]

        text.append(" commits · last 12 weeks\n", style="grey62")
        if commit_counts:
            max_v = max(commit_counts) or 1
            text.append(" ")
            for i, v in enumerate(commit_counts):
                idx = int((v / max_v) * (len(_BLOCKS) - 1))
                bar = _BLOCKS[idx]
                style = "bold cyan" if i == len(commit_counts) - 1 else "grey50"
                text.append(bar, style=style)
            text.append("\n")
            text.append(f"  max:{max(commit_counts):>4}\n", style="grey35")

        text.append("\n")

        # Per-repo breakdown
        if d.repo_stats:
            text.append(" by repo\n", style="grey62")
            max_count = d.repo_stats[0].commit_count or 1
            # name col + bar col + count col
            # count = 5, space = 1, bar = dynamic, name = rest
            count_col = 5
            bar_col = max(8, w // 3)
            name_col = max(8, w - bar_col - count_col - 4)

            for rs in d.repo_stats:
                name = _trunc(rs.name, name_col)
                filled = int((rs.commit_count / max_count) * bar_col)
                bar = "█" * filled + "░" * (bar_col - filled)
                text.append(f" {name:<{name_col}} ", style="grey70")
                text.append(bar, style="cyan")
                text.append(f" {rs.commit_count:>{count_col}}\n", style="grey62")

        return text

    def update_data(self, data: DashboardData) -> None:
        self.data = data
        self.refresh()
