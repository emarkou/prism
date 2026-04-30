from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static
from textual.worker import Worker, WorkerState

from textual.containers import Vertical

from .config import Config
from .github.client import GitHubClient
from .github.models import DashboardData
from .widgets.contributions import ContributionsWidget
from .widgets.ci_status import CIStatusWidget
from .widgets.inbox import InboxWidget
from .widgets.my_prs import MyPRsWidget, ToggleDraftRequest
from .widgets.pending_reviews import PendingReviewsWidget

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class StatusBar(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._syncing = False
        self._spinner_idx = 0
        self._last_sync: Optional[datetime] = None
        self._n_repos: int = 0
        self._n_prs: int = 0
        self._rate_remaining: int = 5000
        self._rate_low = False
        self._error: Optional[str] = None

    def render(self) -> Text:
        text = Text(overflow="ellipsis", no_wrap=True)
        keys = "[o] open  [r] refresh  [tab] next tile  [↑↓] navigate  [x] dismiss  [?] help  [q] quit"
        text.append(keys, style="bold")
        text.append("  ·  ", style="dim")

        if self._error:
            text.append(f"⚠ {self._error}", style="bold red")
        elif self._rate_remaining == 0:
            text.append("⚠ rate limit exhausted", style="bold red")
        elif self._rate_low:
            text.append(f"⚠ rate limit low: {self._rate_remaining} remaining", style="bold yellow")

        text.append("  ", style="")

        if self._syncing:
            spin = _SPINNER[self._spinner_idx % len(_SPINNER)]
            text.append(f"{spin} syncing...", style="bold")
        elif self._last_sync:
            delta = int((datetime.now(timezone.utc) - self._last_sync).total_seconds())
            text.append(f"last sync {delta}s ago", style="dim")
        else:
            text.append("not synced yet", style="dim")

        text.append(f"  ·  {self._n_repos} repos  ·  {self._n_prs} open prs", style="dim")
        return text

    def start_sync(self) -> None:
        self._syncing = True
        self._error = None
        self.refresh()

    def end_sync(self, data: DashboardData) -> None:
        self._syncing = False
        self._last_sync = data.fetched_at or datetime.now(timezone.utc)
        self._n_prs = len(data.my_prs)
        self._n_repos = len(data.repo_stats)
        self._rate_remaining = data.rate_limit_remaining
        self._rate_low = data.rate_limit_remaining < 100
        if data.fetch_error:
            self._error = f"fetch failed: {data.fetch_error}"
        elif data.partial_data:
            self._error = "partial data"
        else:
            self._error = None
        self.refresh()

    def tick_spinner(self, idx: int) -> None:
        self._spinner_idx = idx
        if self._syncing:
            self.refresh()


class HelpOverlay(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_overlay", "Close", show=False)]

    def compose(self) -> ComposeResult:
        lines = [
            " KEYBINDINGS",
            "─" * 30,
            " q          quit",
            " r          force refresh",
            " tab        next tile",
            " shift+tab  previous tile",
            " ↑ / k      move up",
            " ↓ / j      move down",
            " o / enter  open in browser",
            " x          dismiss inbox item",
            " m          toggle draft (tile 1)",
            " ?          close this help",
        ]
        yield Static("\n".join(lines))

    def action_dismiss_overlay(self) -> None:
        self.app.pop_screen()

    def on_key(self, event) -> None:
        if event.key == "question_mark":
            self.app.pop_screen()


class PrismApp(App):
    CSS_PATH = str(Path(__file__).parent / "styles" / "prism.tcss")

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "force_refresh", "Refresh"),
        Binding("tab", "focus_next", "Next tile", show=False),
        Binding("shift+tab", "focus_previous", "Prev tile", show=False),
        Binding("question_mark", "show_help", "Help", show=False),
    ]

    def __init__(self, config: Config, client: GitHubClient):
        super().__init__()
        self._config = config
        self._client = client
        self._data: Optional[DashboardData] = None
        self._spinner_counter = 0
        self._refresh_worker: Optional[Worker] = None

    def compose(self) -> ComposeResult:
        yield MyPRsWidget(id="my-prs")
        with Vertical(id="center-col"):
            yield InboxWidget(id="inbox")
            yield CIStatusWidget(id="ci-status")
        with Vertical(id="right-col"):
            yield PendingReviewsWidget(id="pending-reviews")
            yield ContributionsWidget(id="contributions")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.set_focus(self.query_one("#my-prs"))
        self.set_interval(0.1, self._spinner_tick)
        self.set_interval(self._config.refresh_seconds, self._auto_refresh)
        self._start_refresh()

    def _spinner_tick(self) -> None:
        self._spinner_counter += 1
        self.query_one(StatusBar).tick_spinner(self._spinner_counter)

    def _auto_refresh(self) -> None:
        if self._data and self._data.rate_limit_remaining == 0:
            return
        self._start_refresh()

    def _start_refresh(self) -> None:
        if self._refresh_worker and self._refresh_worker.state == WorkerState.RUNNING:
            return
        self.query_one(StatusBar).start_sync()
        self._refresh_worker = self.run_worker(self._fetch_data(), exclusive=True)

    async def _fetch_data(self) -> None:
        try:
            data = await self._client.fetch_dashboard(
                max_prs=self._config.max_prs,
                max_inbox=self._config.max_inbox,
            )
        except RuntimeError as e:
            self.exit(message=str(e))
            return
        except Exception as e:
            data = DashboardData(fetch_error=str(e))

        self._data = data
        self.query_one(MyPRsWidget).update_data(data)
        self.query_one(InboxWidget).update_data(data)
        self.query_one(CIStatusWidget).update_data(data)
        self.query_one(PendingReviewsWidget).update_data(data)
        self.query_one(ContributionsWidget).update_data(data)
        self.query_one(StatusBar).end_sync(data)

    def action_force_refresh(self) -> None:
        self._start_refresh()

    def action_show_help(self) -> None:
        self.push_screen(HelpOverlay())

    def on_toggle_draft_request(self, message: ToggleDraftRequest) -> None:
        self.run_worker(self._toggle_draft(message.pr))

    async def _toggle_draft(self, pr) -> None:
        ok = await self._client.toggle_draft(pr)
        if ok:
            self._start_refresh()

    async def on_unmount(self) -> None:
        await self._client.close()
