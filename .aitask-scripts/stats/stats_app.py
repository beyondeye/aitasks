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

from lib.tui_switcher import TuiSwitcherMixin  # noqa: E402  (also adds lib/ to sys.path)
from agent_launch_utils import AitasksSession, discover_aitasks_sessions  # noqa: E402
from stats import stats_config  # noqa: E402
from stats.modals.name_input import NameInputModal  # noqa: E402
from stats.modals.pane_selector import PaneSelectorModal  # noqa: E402
from stats.panes import PANE_DEFS  # noqa: E402
from stats.stats_data import (  # noqa: E402
    SessionTotals,
    StatsData,
    collect_stats,
    merge_stats_data,
)

ALL_SESSIONS_KEY = "__all__"


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


class _SessionItem(ListItem):
    """Session-selector row. Carries the session key (name or `__all__`)."""

    def __init__(self, session_key: str, label_text: str) -> None:
        super().__init__(Label(label_text))
        self.session_key = session_key


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

    #session_panel {
        height: auto;
        max-height: 30%;
        border-bottom: tall $accent;
        padding: 0;
    }

    #session_panel_title {
        padding: 0 1;
        text-style: bold;
        color: $accent;
    }

    #session_list { height: auto; max-height: 8; }

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
        Binding("s", "focus_sessions", "Sessions"),
        Binding("c", "focus_layouts", "Layouts"),
        Binding("n", "new_custom", "New custom"),
        Binding("d", "delete_custom", "Delete custom"),
        Binding("e", "edit_custom", "Edit custom"),
        Binding("left", "prev_verified_op", "← Cycle", show=True),
        Binding("right", "next_verified_op", "→ Cycle", show=True),
        Binding("[", "prev_window", "prev window", show=True),
        Binding("]", "next_window", "next window", show=True),
        Binding("q", "quit", "Quit"),
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_tui_name = "stats"
        self.stats_data: StatsData | None = None
        self.config: dict = stats_config.load()
        self.active_layout: list[str] = self._resolve_layout()
        self.sessions: list[AitasksSession] = discover_aitasks_sessions()
        self.multi_session: bool = len(self.sessions) >= 2
        self._session_cache: dict[str, StatsData] = {}
        self.selected_session: str = self._default_session_selection()

    # ─── Helpers ───────────────────────────────────────────────────────────

    def _resolve_layout(self) -> list[str]:
        return [
            pid
            for pid in stats_config.resolve_active_layout(self.config)
            if pid in PANE_DEFS
        ]

    def _default_session_selection(self) -> str:
        if not self.multi_session:
            return ""
        # Match the attached tmux session, if any, to one of the discovered
        # aitasks sessions. Falls back to the first session by sort order.
        attached = os.environ.get("TMUX", "")
        attached_name = ""
        if attached:
            try:
                import subprocess
                result = subprocess.run(
                    ["tmux", "display-message", "-p", "#{session_name}"],
                    capture_output=True, text=True, timeout=2,
                )
                if result.returncode == 0:
                    attached_name = result.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
        for sess in self.sessions:
            if sess.session == attached_name:
                return sess.session
        return self.sessions[0].session

    def _session_key_to_label(self, key: str) -> str:
        if key == ALL_SESSIONS_KEY:
            return "All sessions (aggregate)"
        for sess in self.sessions:
            if sess.session == key:
                return f"{sess.session} ({sess.project_name})"
        return key

    # ─── Compose ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            with Vertical(id="left_column"):
                if self.multi_session:
                    with Vertical(id="session_panel"):
                        yield Label(
                            "Session  [dim]← / → to cycle[/]",
                            id="session_panel_title",
                        )
                        yield ListView(
                            *self._build_session_items(),
                            id="session_list",
                        )
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
        if self.multi_session:
            session_list = self.query_one("#session_list", ListView)
            for idx, item in enumerate(session_list.children):
                if isinstance(item, _SessionItem) and item.session_key == self.selected_session:
                    session_list.index = idx
                    break
        if self.active_layout:
            self._show_pane(self.active_layout[0])
            sidebar = self.query_one("#sidebar", ListView)
            sidebar.index = 0
            sidebar.focus()
        self._update_title()
        self._apply_focus_hint()

    # ─── Data ──────────────────────────────────────────────────────────────

    def _load_data(self) -> None:
        if not self.multi_session:
            self.stats_data = collect_stats(date.today(), 1)
            return

        if self.selected_session == ALL_SESSIONS_KEY:
            parts = [self._stats_for(s) for s in self.sessions]
            data = merge_stats_data(parts)
        else:
            sess = next(
                (s for s in self.sessions if s.session == self.selected_session),
                self.sessions[0],
            )
            data = self._stats_for(sess)

        # Populate the per-session breakdown for the sessions.totals pane.
        # Always available in multi-session mode regardless of which session is
        # selected, so users can see the comparison without switching to the
        # aggregate view.
        today = date.today()
        breakdown: list[SessionTotals] = []
        for s in self.sessions:
            sd = self._stats_for(s)
            breakdown.append(SessionTotals(
                session=s.session,
                project_name=s.project_name,
                tasks_today=sd.daily_counts.get(today, 0),
                tasks_7d=sd.tasks_7d,
                tasks_30d=sd.tasks_30d,
            ))
        data.session_breakdown = breakdown
        self.stats_data = data

    def _stats_for(self, sess: AitasksSession) -> StatsData:
        cached = self._session_cache.get(sess.session)
        if cached is None:
            cached = collect_stats(date.today(), 1, project_root=sess.project_root)
            self._session_cache[sess.session] = cached
        return cached

    def _update_title(self) -> None:
        if self.multi_session:
            self.title = f"ait stats — {self._session_key_to_label(self.selected_session)}"
        else:
            self.title = "ait stats"

    def _refresh_current_pane(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        idx = sidebar.index if sidebar.index is not None else 0
        if 0 <= idx < len(self.active_layout):
            self._show_pane(self.active_layout[idx])

    # ─── Sidebar (pane list) ───────────────────────────────────────────────

    def _build_sidebar_items(self) -> list[ListItem]:
        return [_SidebarItem(pid, PANE_DEFS[pid].title) for pid in self.active_layout]

    def _build_session_items(self) -> list[ListItem]:
        items: list[ListItem] = []
        for sess in self.sessions:
            items.append(_SessionItem(
                sess.session,
                f"{sess.session} [dim]({sess.project_name})[/]",
            ))
        items.append(_SessionItem(ALL_SESSIONS_KEY, "All sessions [dim](aggregate)[/]"))
        return items

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
        elif isinstance(item, _SessionItem):
            if item.session_key != self.selected_session:
                self.selected_session = item.session_key
                self._load_data()
                self._update_title()
                self._refresh_current_pane()
                self.notify(
                    f"Session: {self._session_key_to_label(item.session_key)}",
                    timeout=1,
                )

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
        self._session_cache.clear()
        self._load_data()
        self._refresh_current_pane()
        self.notify("Refreshed", timeout=1)

    def _current_pane_id(self) -> str | None:
        sidebar = self.query_one("#sidebar", ListView)
        idx = sidebar.index
        if idx is None or idx < 0 or idx >= len(self.active_layout):
            return None
        return self.active_layout[idx]

    def action_prev_verified_op(self) -> None:
        pane_id = self._current_pane_id()
        if pane_id == "agents.verified":
            self._cycle_verified_op(-1)
        elif pane_id == "agents.usage":
            self._cycle_usage_op(-1)
        elif self.multi_session:
            self._cycle_session(-1)

    def action_next_verified_op(self) -> None:
        pane_id = self._current_pane_id()
        if pane_id == "agents.verified":
            self._cycle_verified_op(+1)
        elif pane_id == "agents.usage":
            self._cycle_usage_op(+1)
        elif self.multi_session:
            self._cycle_session(+1)

    def action_prev_window(self) -> None:
        self._cycle_window(-1)

    def action_next_window(self) -> None:
        self._cycle_window(+1)

    def _cycle_verified_op(self, delta: int) -> None:
        if self._current_pane_id() != "agents.verified":
            return
        from stats.panes.agents import VerifiedRankingsPane
        try:
            pane = self.query_one("#content VerifiedRankingsPane", VerifiedRankingsPane)
        except Exception:
            return
        pane.cycle_op(delta)

    def _cycle_usage_op(self, delta: int) -> None:
        if self._current_pane_id() != "agents.usage":
            return
        from stats.panes.agents import UsageRankingsPane
        try:
            pane = self.query_one("#content UsageRankingsPane", UsageRankingsPane)
        except Exception:
            return
        pane.cycle_op(delta)

    def _cycle_window(self, delta: int) -> None:
        pane_id = self._current_pane_id()
        if pane_id == "agents.verified":
            from stats.panes.agents import VerifiedRankingsPane
            try:
                pane = self.query_one("#content VerifiedRankingsPane", VerifiedRankingsPane)
            except Exception:
                return
            pane.cycle_window(delta)
        elif pane_id == "agents.usage":
            from stats.panes.agents import UsageRankingsPane
            try:
                pane = self.query_one("#content UsageRankingsPane", UsageRankingsPane)
            except Exception:
                return
            pane.cycle_window(delta)

    def _cycle_session(self, delta: int) -> None:
        # Order: detected sessions in display order, then "All sessions".
        keys = [s.session for s in self.sessions] + [ALL_SESSIONS_KEY]
        try:
            current = keys.index(self.selected_session)
        except ValueError:
            current = 0
        new_key = keys[(current + delta) % len(keys)]
        if new_key == self.selected_session:
            return
        self.selected_session = new_key
        # Mirror selection in the session_list widget.
        try:
            session_list = self.query_one("#session_list", ListView)
            for idx, item in enumerate(session_list.children):
                if isinstance(item, _SessionItem) and item.session_key == new_key:
                    session_list.index = idx
                    break
        except Exception:
            pass
        self._load_data()
        self._update_title()
        self._refresh_current_pane()
        self.notify(
            f"Session: {self._session_key_to_label(new_key)}",
            timeout=1,
        )

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
        cycle: list[ListView] = [sidebar, layouts]
        if self.multi_session:
            sessions = self.query_one("#session_list", ListView)
            # Order: session_list → sidebar → layouts → session_list.
            cycle = [sessions, sidebar, layouts]
        try:
            current = cycle.index(self.focused)  # type: ignore[arg-type]
        except ValueError:
            current = -1
        step = 1 if forward else -1
        target = cycle[(current + step) % len(cycle)]
        target.focus()
        self._apply_focus_hint()

    def action_focus_layouts(self) -> None:
        self.query_one("#layout_list", ListView).focus()
        self._apply_focus_hint()

    def action_focus_sessions(self) -> None:
        if not self.multi_session:
            return
        self.query_one("#session_list", ListView).focus()
        self._apply_focus_hint()

    def _apply_focus_hint(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        layouts = self.query_one("#layout_list", ListView)
        targets: list[tuple[ListView, bool]] = [
            (sidebar, self.focused is sidebar),
            (layouts, self.focused is layouts),
        ]
        if self.multi_session:
            sessions = self.query_one("#session_list", ListView)
            targets.append((sessions, self.focused is sessions))
        for w, is_focused in targets:
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
