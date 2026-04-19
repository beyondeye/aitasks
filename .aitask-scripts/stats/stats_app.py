#!/usr/bin/env python3
"""ait stats TUI — sidebar-driven viewer for archive statistics.

The sidebar is populated from `HARDCODED_LAYOUT`; t597_4 replaces this with
a config-driven layout resolved from persisted preferences.
"""
from __future__ import annotations

import os
import sys
from datetime import date

# Allow `from stats.stats_data import …` regardless of how this script is
# launched (via aitask_stats_tui.sh, directly, or under pytest).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, Horizontal  # noqa: E402
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static  # noqa: E402

from lib.tui_switcher import TuiSwitcherMixin  # noqa: E402
from stats.panes import PANE_DEFS  # noqa: E402
from stats.stats_data import StatsData, collect_stats  # noqa: E402

# Hardcoded layout — t597_4 replaces with config-driven resolution.
HARDCODED_LAYOUT: list[str] = [
    "overview.summary",
    "overview.daily",
    "overview.weekday",
]


def _pane_id_to_widget_id(pane_id: str) -> str:
    """Convert a dotted pane id to a Textual-safe widget id (no dots)."""
    return "pane_" + pane_id.replace(".", "_")


def _widget_id_to_pane_id(widget_id: str) -> str:
    return widget_id[len("pane_"):].replace("_", ".", 1)


class StatsApp(TuiSwitcherMixin, App):
    """Top-level app: sidebar on the left, content area on the right."""

    TITLE = "ait stats"

    CSS = """
    Screen {
        layout: vertical;
    }

    #main_container {
        height: 1fr;
    }

    #sidebar {
        width: 28;
        height: 100%;
        border-right: tall $accent;
    }

    #content {
        width: 1fr;
        height: 100%;
        padding: 1 2;
    }

    .summary_card {
        width: 1fr;
        content-align: center middle;
        padding: 1 2;
        border: tall $accent;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("c", "config", "Config"),
        Binding("q", "quit", "Quit"),
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_tui_name = "stats"
        self.stats_data: StatsData | None = None
        # t597_4 will replace with config.resolve_active_layout(config).
        self.active_layout: list[str] = [pid for pid in HARDCODED_LAYOUT if pid in PANE_DEFS]

    # ─── Layout ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            yield ListView(
                *[
                    ListItem(Label(PANE_DEFS[pid].title), id=_pane_id_to_widget_id(pid))
                    for pid in self.active_layout
                ],
                id="sidebar",
            )
            yield Container(id="content")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()
        if self.active_layout:
            self._show_pane(self.active_layout[0])
            sidebar = self.query_one("#sidebar", ListView)
            sidebar.index = 0
            sidebar.focus()

    # ─── Data ──────────────────────────────────────────────────────────────

    def _load_data(self) -> None:
        # week_start_dow=1 (Monday) matches the CLI default; t597_4 will read
        # this from the persisted config.
        self.stats_data = collect_stats(date.today(), 1)

    # ─── Pane rendering ────────────────────────────────────────────────────

    def _show_pane(self, pane_id: str) -> None:
        content = self.query_one("#content", Container)
        content.remove_children()
        pane = PANE_DEFS.get(pane_id)
        if pane is None or self.stats_data is None:
            content.mount(Static("[dim]Pane unavailable[/dim]"))
            return
        pane.render(self.stats_data, content)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is not None and event.item.id is not None:
            self._show_pane(_widget_id_to_pane_id(event.item.id))

    # ─── Actions ───────────────────────────────────────────────────────────
    #
    # Note (per memory feedback_textual_priority_bindings): when t597_4 adds a
    # ModalScreen for config, App-level priority bindings for `c`, `r`, `q`,
    # arrow keys can swallow keystrokes destined for the modal. If you observe
    # that, scope guards inside these actions to `self.screen.query_one(...)`
    # and raise `textual.actions.SkipAction` when the active screen is a
    # modal — see the memory entry for the full pattern.

    def action_refresh(self) -> None:
        self._load_data()
        sidebar = self.query_one("#sidebar", ListView)
        idx = sidebar.index if sidebar.index is not None else 0
        if 0 <= idx < len(self.active_layout):
            self._show_pane(self.active_layout[idx])
        self.notify("Refreshed", timeout=1)

    def action_config(self) -> None:
        self.notify("Config modal coming in t597_4", timeout=2)


if __name__ == "__main__":
    StatsApp().run()
