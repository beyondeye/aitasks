"""ait syncer — TUI for tracking remote desync state.

Polls `lib/desync_state.snapshot()` for the project's `main` and
`aitask-data` refs and displays ahead/behind counts plus per-row detail
(commit subjects and changed paths). Action handlers (pull/push/sync)
land in sibling task t713_3 once the shared sync runner is extracted by
t713_8.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from desync_state import snapshot  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402

from textual import work  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Vertical, VerticalScroll  # noqa: E402
from textual.widgets import DataTable, Footer, Header, Static  # noqa: E402


REFRESH_TICK_DEFAULT = 30
DETAIL_MAX_COMMITS = 20
DETAIL_MAX_PATHS = 50


def _format_clock(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class SyncerApp(TuiSwitcherMixin, App):
    """Textual TUI for the syncer."""

    TITLE = "aitasks syncer"

    CSS = """
    Screen {
        layout: vertical;
    }
    #branches {
        height: auto;
        max-height: 12;
    }
    #detail_scroll {
        height: 1fr;
        border-top: solid $accent-darken-2;
    }
    #detail {
        padding: 0 1;
    }
    """

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        Binding("r", "refresh", "Refresh"),
        Binding("f", "toggle_fetch", "Fetch on/off"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, cli_args: argparse.Namespace) -> None:
        super().__init__()
        self.cli_args = cli_args
        self.current_tui_name = "syncer"
        self._interval = max(1, int(getattr(cli_args, "interval", None) or REFRESH_TICK_DEFAULT))
        self._fetch = not getattr(cli_args, "no_fetch", False)
        self._last_snapshot: dict[str, Any] = {"refs": []}
        self._row_keys: list[str] = ["main", "aitask-data"]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            table = DataTable(id="branches", cursor_type="row", zebra_stripes=True)
            table.add_column("Branch", key="branch")
            table.add_column("Status", key="status")
            table.add_column("Ahead", key="ahead")
            table.add_column("Behind", key="behind")
            table.add_column("Last refresh", key="last")
            yield table
            with VerticalScroll(id="detail_scroll"):
                yield Static("Loading…", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#branches", DataTable)
        for name in self._row_keys:
            table.add_row(name, "loading…", "", "", "", key=name)
        self.set_interval(self._interval, self.action_refresh)
        self.call_later(self.action_refresh)
        self._update_subtitle()

    def _update_subtitle(self) -> None:
        fetch_state = "on" if self._fetch else "off"
        self.sub_title = f"interval={self._interval}s  fetch={fetch_state}"

    def action_refresh(self) -> None:
        self._refresh_worker()

    def action_toggle_fetch(self) -> None:
        self._fetch = not self._fetch
        self._update_subtitle()
        self.notify(f"Fetch {'enabled' if self._fetch else 'disabled'}")
        self.call_later(self.action_refresh)

    @work(thread=True, exclusive=True, group="syncer-refresh")
    def _refresh_worker(self) -> None:
        try:
            data = snapshot(None, self._fetch)
        except Exception as exc:  # pragma: no cover — defensive
            self.call_from_thread(self._notify_refresh_error, str(exc))
            return
        ts = time.time()
        self.call_from_thread(self._apply_snapshot, data, ts)

    def _notify_refresh_error(self, message: str) -> None:
        self.notify(f"Refresh failed: {message}", severity="error")

    def _apply_snapshot(self, data: dict[str, Any], ts: float) -> None:
        self._last_snapshot = data
        clock = _format_clock(ts)
        table = self.query_one("#branches", DataTable)

        by_name = {ref["name"]: ref for ref in data.get("refs", [])}
        for name in self._row_keys:
            ref = by_name.get(name)
            if ref is None:
                table.update_cell(name, "status", "missing")
                table.update_cell(name, "ahead", "")
                table.update_cell(name, "behind", "")
                table.update_cell(name, "last", clock)
                continue
            status = ref["status"]
            if status == "ok":
                ahead = str(ref.get("ahead", 0))
                behind = str(ref.get("behind", 0))
            else:
                ahead = ""
                behind = ""
            table.update_cell(name, "status", status)
            table.update_cell(name, "ahead", ahead)
            table.update_cell(name, "behind", behind)
            table.update_cell(name, "last", clock)

        self._refresh_detail()

    def _selected_ref_name(self) -> str:
        table = self.query_one("#branches", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            return self._row_keys[0]
        try:
            row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
            if row_key.value:
                return str(row_key.value)
        except Exception:
            pass
        idx = max(0, min(table.cursor_row, len(self._row_keys) - 1))
        return self._row_keys[idx]

    def _find_ref(self, name: str) -> dict[str, Any] | None:
        for ref in self._last_snapshot.get("refs", []):
            if ref.get("name") == name:
                return ref
        return None

    def _refresh_detail(self) -> None:
        detail = self.query_one("#detail", Static)
        name = self._selected_ref_name()
        ref = self._find_ref(name)
        if ref is None:
            detail.update(f"[b]{name}[/b]\nNo data yet.")
            return

        lines: list[str] = [f"[b]{ref['name']}[/b]  [dim]({ref.get('worktree', '?')})[/dim]"]
        status = ref.get("status", "?")
        lines.append(f"Status: {status}")
        if status == "ok":
            lines.append(f"Ahead: {ref.get('ahead', 0)}    Behind: {ref.get('behind', 0)}")
        if ref.get("error"):
            lines.append(f"[red]Error:[/red] {ref['error']}")

        commits = ref.get("remote_commits") or []
        if commits:
            lines.append("")
            lines.append("[b]Remote commits not yet pulled:[/b]")
            for subject in commits[:DETAIL_MAX_COMMITS]:
                lines.append(f"  • {subject}")
            if len(commits) > DETAIL_MAX_COMMITS:
                lines.append(f"  [dim]… {len(commits) - DETAIL_MAX_COMMITS} more[/dim]")

        paths = ref.get("remote_changed_paths") or []
        if paths:
            lines.append("")
            lines.append("[b]Changed paths:[/b]")
            for path in paths[:DETAIL_MAX_PATHS]:
                lines.append(f"  • {path}")
            if len(paths) > DETAIL_MAX_PATHS:
                lines.append(f"  [dim]… {len(paths) - DETAIL_MAX_PATHS} more[/dim]")

        detail.update("\n".join(lines))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._refresh_detail()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ait syncer",
        description="TUI for tracking remote desync state of main and aitask-data refs.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=REFRESH_TICK_DEFAULT,
        help=f"Polling interval in seconds (default: {REFRESH_TICK_DEFAULT}).",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip 'git fetch' before computing state (offline mode).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    SyncerApp(args).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
