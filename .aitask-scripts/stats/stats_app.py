#!/usr/bin/env python3
"""ait stats TUI — sidebar-driven viewer for archive statistics.

Layout:
  ┌──────────────┬──────────────────┐
  │  sidebar     │                  │
  │  (active     │   content        │
  │   layout     │   (chart)        │
  │   panes)     │                  │
  ├──────────────┤                  │
  │  layout      │                  │
  │  picker      │                  │
  └──────────────┴──────────────────┘

Highlighting a sidebar entry shows its pane immediately (no Enter needed).
Tab flips focus between the sidebar (top) and the layout picker (bottom).
Enter on a layout applies it and saves to `stats_config.local.json`.
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
from textual.containers import Container, Horizontal, Vertical  # noqa: E402
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static  # noqa: E402

from lib.tui_switcher import TuiSwitcherMixin  # noqa: E402
from stats import stats_config  # noqa: E402
from stats.modals.name_input import NameInputModal  # noqa: E402
from stats.modals.pane_selector import PaneSelectorModal  # noqa: E402
from stats.panes import PANE_DEFS  # noqa: E402
from stats.stats_data import StatsData, collect_stats  # noqa: E402


class _SidebarItem(ListItem):
    """Sidebar row carrying its pane id as an attribute (no widget id needed)."""

    def __init__(self, pane_id: str, title: str) -> None:
        super().__init__(Label(title))
        self.pane_id = pane_id


class _LayoutListItem(ListItem):
    """Layout-picker row. Carries the logical layout name and kind."""

    def __init__(self, kind: str, name: str, label_text: str) -> None:
        super().__init__(Label(label_text))
        self.kind = kind  # "preset" | "custom" | "new"
        self.layout_name = name


class StatsApp(TuiSwitcherMixin, App):
    """Top-level app: sidebar + layout picker on the left, content on the right."""

    TITLE = "ait stats"

    CSS = """
    Screen { layout: vertical; }

    #main_container { height: 1fr; }

    #left_column {
        width: 30;
        height: 100%;
        border-right: tall $accent;
    }

    #sidebar { height: 1fr; }

    #layout_panel {
        height: auto;
        max-height: 50%;
        border-top: tall $accent;
        padding: 0;
    }

    #layout_panel_title {
        padding: 0 1;
        text-style: bold;
        color: $accent;
    }

    #layout_list { height: auto; max-height: 14; }

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

    .focused_panel {
        border-left: tall $primary;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("tab", "focus_next_panel", "Focus"),
        Binding("shift+tab", "focus_prev_panel", "Focus"),
        Binding("c", "focus_layouts", "Layouts"),
        Binding("n", "new_custom", "New custom"),
        Binding("d", "delete_custom", "Delete custom"),
        Binding("e", "edit_custom", "Edit custom"),
        Binding("q", "quit", "Quit"),
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_tui_name = "stats"
        self.stats_data: StatsData | None = None
        self.config: dict = stats_config.load()
        self.active_layout: list[str] = self._resolve_layout()

    # ─── Helpers ───────────────────────────────────────────────────────────

    def _resolve_layout(self) -> list[str]:
        return [
            pid
            for pid in stats_config.resolve_active_layout(self.config)
            if pid in PANE_DEFS
        ]

    # ─── Compose ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            with Vertical(id="left_column"):
                yield ListView(
                    *self._build_sidebar_items(),
                    id="sidebar",
                )
                with Vertical(id="layout_panel"):
                    yield Label("Layouts", id="layout_panel_title")
                    yield ListView(
                        *self._build_layout_items(),
                        id="layout_list",
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
        self._apply_focus_hint()

    # ─── Data ──────────────────────────────────────────────────────────────

    def _load_data(self) -> None:
        self.stats_data = collect_stats(date.today(), 1)

    # ─── Sidebar (pane list) ───────────────────────────────────────────────

    def _build_sidebar_items(self) -> list[ListItem]:
        return [_SidebarItem(pid, PANE_DEFS[pid].title) for pid in self.active_layout]

    async def _rebuild_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        await sidebar.clear()
        items = self._build_sidebar_items()
        if items:
            await sidebar.extend(items)
            sidebar.index = 0
            self._show_pane(self.active_layout[0])
        else:
            content = self.query_one("#content", Container)
            content.remove_children()
            content.mount(Static("[dim]No panes in this layout[/dim]"))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, _SidebarItem):
            self._show_pane(item.pane_id)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, _LayoutListItem):
            await self._activate_layout_item(item)

    # ─── Pane rendering ────────────────────────────────────────────────────

    def _show_pane(self, pane_id: str) -> None:
        content = self.query_one("#content", Container)
        content.remove_children()
        pane = PANE_DEFS.get(pane_id)
        if pane is None or self.stats_data is None:
            content.mount(Static("[dim]Pane unavailable[/dim]"))
            return
        pane.render(self.stats_data, content)

    # ─── Layout panel ──────────────────────────────────────────────────────

    def _build_layout_items(self) -> list[ListItem]:
        items: list[ListItem] = []
        active = self.config.get("active", "overview")
        for name in self.config.get("presets", {}):
            marker = "● " if name == active else "  "
            items.append(_LayoutListItem("preset", name, f"{marker}{name}"))
        customs = self.config.get("custom", {})
        if customs:
            for name in customs:
                marker = "● " if name == active else "  "
                items.append(_LayoutListItem("custom", name, f"{marker}{name} [dim](custom)[/]"))
        items.append(_LayoutListItem("new", "", "  + New custom"))
        return items

    def _rebuild_layout_list(self, focus_name: str | None = None) -> None:
        layout_list = self.query_one("#layout_list", ListView)
        layout_list.clear()
        items = self._build_layout_items()
        for item in items:
            layout_list.append(item)
        if focus_name is not None:
            for idx, item in enumerate(items):
                if isinstance(item, _LayoutListItem) and item.layout_name == focus_name:
                    layout_list.index = idx
                    break

    async def _activate_layout_item(self, item: _LayoutListItem) -> None:
        if item.kind == "new":
            self._new_custom_flow()
            return
        # Apply preset or custom.
        self.config["active"] = item.layout_name
        stats_config.save(self.config)
        self.active_layout = self._resolve_layout()
        await self._rebuild_sidebar()
        self._rebuild_layout_list(focus_name=item.layout_name)
        self.notify(f"Layout: {item.layout_name}", timeout=1)

    # ─── Actions ───────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self._load_data()
        sidebar = self.query_one("#sidebar", ListView)
        idx = sidebar.index if sidebar.index is not None else 0
        if 0 <= idx < len(self.active_layout):
            self._show_pane(self.active_layout[idx])
        self.notify("Refreshed", timeout=1)

    def action_focus_next_panel(self) -> None:
        self._cycle_focus(forward=True)

    def action_focus_prev_panel(self) -> None:
        self._cycle_focus(forward=False)

    def _cycle_focus(self, forward: bool) -> None:
        if self.screen is not self:
            # A modal is on top — let its own bindings handle Tab.
            return
        sidebar = self.query_one("#sidebar", ListView)
        layouts = self.query_one("#layout_list", ListView)
        # Two-element cycle — direction is cosmetic.
        target = layouts if self.focused is sidebar else sidebar
        target.focus()
        self._apply_focus_hint()

    def action_focus_layouts(self) -> None:
        self.query_one("#layout_list", ListView).focus()
        self._apply_focus_hint()

    def _apply_focus_hint(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        layouts = self.query_one("#layout_list", ListView)
        for w, is_focused in ((sidebar, self.focused is sidebar),
                              (layouts, self.focused is layouts)):
            if is_focused:
                w.add_class("focused_panel")
            else:
                w.remove_class("focused_panel")

    def on_descendant_focus(self, event) -> None:
        self._apply_focus_hint()

    # ─── Custom-layout flows ───────────────────────────────────────────────

    def action_new_custom(self) -> None:
        if self.focused is not self.query_one("#layout_list", ListView):
            return
        self._new_custom_flow()

    def _new_custom_flow(self) -> None:
        def on_name(name: str | None) -> None:
            if not name:
                return
            if name in self.config.get("custom", {}) or name in self.config.get("presets", {}):
                self.notify(f"Name '{name}' is already taken", severity="warning")
                return
            self._open_pane_selector(name, initial=[], is_new=True)
        self.push_screen(NameInputModal("New custom layout name:"), on_name)

    def action_edit_custom(self) -> None:
        if self.focused is not self.query_one("#layout_list", ListView):
            return
        item = self._current_layout_item()
        if item is None or item.kind != "custom":
            return
        initial = list(self.config.get("custom", {}).get(item.layout_name, []))
        self._open_pane_selector(item.layout_name, initial=initial, is_new=False)

    async def action_delete_custom(self) -> None:
        if self.focused is not self.query_one("#layout_list", ListView):
            return
        item = self._current_layout_item()
        if item is None or item.kind != "custom":
            self.notify("Only custom layouts can be deleted", severity="warning")
            return
        name = item.layout_name
        customs = self.config.get("custom", {})
        if name not in customs:
            return
        del customs[name]
        if self.config.get("active") == name:
            self.config["active"] = "overview"
            self.active_layout = self._resolve_layout()
            await self._rebuild_sidebar()
        stats_config.save(self.config)
        self._rebuild_layout_list(focus_name=self.config.get("active"))
        self.notify(f"Deleted '{name}'")

    def _current_layout_item(self) -> _LayoutListItem | None:
        layout_list = self.query_one("#layout_list", ListView)
        item = layout_list.highlighted_child
        return item if isinstance(item, _LayoutListItem) else None

    def _open_pane_selector(
        self, name: str, initial: list[str], is_new: bool,
    ) -> None:
        async def on_done(pane_ids: list[str] | None) -> None:
            if pane_ids is None:
                if is_new:
                    self.notify(f"Discarded new layout '{name}'", timeout=1)
                return
            if not pane_ids:
                self.notify("Select at least one pane", severity="warning")
                return
            self.config.setdefault("custom", {})[name] = pane_ids
            self.config["active"] = name
            stats_config.save(self.config)
            self.active_layout = self._resolve_layout()
            await self._rebuild_sidebar()
            self._rebuild_layout_list(focus_name=name)
            self.notify(f"Saved '{name}'")
        self.push_screen(PaneSelectorModal(name, initial), on_done)


if __name__ == "__main__":
    StatsApp().run()
