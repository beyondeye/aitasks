"""Render + surface tests for the prioritized-agent mark (t1326).

Covers what the user actually sees: the glyph in both TUIs' agent rows (asserted
at the mounted-widget level, not just on the builder's return string), the
binding surface, and the minimonitor's key-hint width budget.

The action contract (argv, strict root, outcome handling) lives in
`test_monitor_agent_marks_action.py`; real key routing lives in
`test_monitor_modal_space_dispatch.py`.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MonitorApp only renames its tmux window when constructed with
# rename_window=True, but scrub the ambient tmux env too (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.text import Text  # noqa: E402

import agent_marks  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)
from monitor.monitor_shared import (  # noqa: E402
    MARK_EMPTY_GLYPH, MARK_GLYPH, format_mark_glyph,
)

# `#mini-key-hints` carries `padding: 0 1`, leaving this many usable columns.
_HINT_WIDTH_BUDGET = 38

SESSION = "demo"


def pane(window: str, *, session: str = SESSION, pane_id: str = "%1",
         category: PaneCategory = PaneCategory.AGENT) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command="node", width=80, height=24,
        category=category, session_name=session,
    )


def snapshot(window: str, **kw) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane(window, **kw), content="hello", timestamp=0.0,
        idle_seconds=1.0, is_idle=False,
    )


class _FakeMonitor:
    multi_session = False

    def __init__(self, root: Path, sessions: dict[str, Path] | None = None) -> None:
        self._mapping = sessions if sessions is not None else {SESSION: root}

    def get_session_to_project_mapping(self) -> dict[str, Path]:
        return self._mapping

    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None


class _FakeTaskCache:
    def get_task_id_for_pane(self, pane): return None
    def get_task_info(self, task_id, session): return None
    def update_session_mapping(self, mapping): pass


class _MarksFixture(unittest.TestCase):
    """Isolated store + a repo root, wired into an unmounted app."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.store = self.tmp / "marks.json"
        self.root = self.tmp / "repo"
        self.root.mkdir()

    def mark(self, window: str) -> None:
        mf = agent_marks.load(self.store)
        agent_marks.toggle(mf, self.root, window)
        agent_marks.dump(mf, self.store)

    def app(self, cls, sessions: dict[str, Path] | None = None):
        app = cls.__new__(cls)
        app._monitor = _FakeMonitor(self.root, sessions)
        app._completed_pane_ids = frozenset()
        app._task_cache = _FakeTaskCache()
        app._project_root = self.root
        app._has_fresh_concerns = lambda pane_id: False
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = 0.0
        app._marks_purge_inflight = False
        app._set_session_root_map(app._monitor.get_session_to_project_mapping())
        app._refresh_marks()
        return app

    @staticmethod
    def row(app, snap) -> str:
        builder = (
            app._agent_card_text if isinstance(app, MiniMonitorApp)
            else app._format_agent_card_text
        )
        return builder(snap)


class GlyphFormatterTests(unittest.TestCase):
    def test_marked_is_bold_white_star(self):
        """White, not the repo-wide marked=bold-yellow: yellow is the IDLE state
        colour of the ● two columns away, and the two would read as one cluster."""
        self.assertEqual(format_mark_glyph(True), f"[bold white]{MARK_GLYPH}[/]")

    def test_unmarked_is_dim_hollow_star(self):
        self.assertEqual(format_mark_glyph(False), f"[dim]{MARK_EMPTY_GLYPH}[/]")

    def test_pair_is_always_on(self):
        """Unlike format_shadow_glyph, neither state may render as "" — an
        absent glyph would shift the row on toggle and read as a bug."""
        for state in (True, False):
            self.assertNotEqual(format_mark_glyph(state), "")

    def test_glyphs_are_single_column_and_distinct(self):
        self.assertEqual(len(MARK_GLYPH), 1)
        self.assertEqual(len(MARK_EMPTY_GLYPH), 1)
        self.assertNotEqual(MARK_GLYPH, MARK_EMPTY_GLYPH)
        # Must not collide with the live-state glyphs sharing the row.
        self.assertNotIn(MARK_GLYPH, {"●", "◆", "≈", "="})
        self.assertNotIn(MARK_EMPTY_GLYPH, {"●", "◆", "≈", "="})


class CardBuilderTests(_MarksFixture):
    def test_marked_agent_row_shows_filled_star(self):
        self.mark("agent-t1")
        for cls in (MiniMonitorApp, MonitorApp):
            with self.subTest(app=cls.__name__):
                row = self.row(self.app(cls), snapshot("agent-t1"))
                self.assertIn(f"[bold white]{MARK_GLYPH}[/]", row)
                self.assertIn(MARK_GLYPH, Text.from_markup(row).plain)

    def test_unmarked_agent_row_shows_hollow_star(self):
        for cls in (MiniMonitorApp, MonitorApp):
            with self.subTest(app=cls.__name__):
                row = self.row(self.app(cls), snapshot("agent-plain"))
                self.assertIn(f"[dim]{MARK_EMPTY_GLYPH}[/]", row)
                self.assertNotIn(MARK_GLYPH, Text.from_markup(row).plain)

    def test_mark_is_leftmost_before_the_state_dot(self):
        """Leftmost is deliberate: a durable annotation outside the live-state
        cluster, and the first thing to survive truncation."""
        self.mark("agent-t1")
        for cls in (MiniMonitorApp, MonitorApp):
            with self.subTest(app=cls.__name__):
                plain = Text.from_markup(
                    self.row(self.app(cls), snapshot("agent-t1"))
                ).plain
                self.assertLess(plain.index(MARK_GLYPH), plain.index("●"))

    def test_unresolvable_session_renders_unmarked_and_does_not_raise(self):
        """Strict root resolution: no `_project_root` fallback, so a foreign
        session can never inherit this repo's marks."""
        self.mark("agent-t1")
        for cls in (MiniMonitorApp, MonitorApp):
            with self.subTest(app=cls.__name__):
                app = self.app(cls, sessions={})
                plain = Text.from_markup(
                    self.row(app, snapshot("agent-t1"))
                ).plain
                self.assertIn(MARK_EMPTY_GLYPH, plain)
                self.assertNotIn(MARK_GLYPH, plain)

    def test_identical_window_names_in_two_roots_do_not_collide(self):
        """The motivating cross-repo case: two repos whose sessions both fall
        back to the name "aitasks"."""
        other = self.tmp / "other_repo"
        other.mkdir()
        self.mark("agent-pick-42")  # marked in self.root only
        app = self.app(
            MiniMonitorApp, sessions={SESSION: self.root, "s2": other}
        )
        here = Text.from_markup(self.row(app, snapshot("agent-pick-42"))).plain
        there = Text.from_markup(
            self.row(app, snapshot("agent-pick-42", session="s2"))
        ).plain
        self.assertIn(MARK_GLYPH, here)
        self.assertIn(MARK_EMPTY_GLYPH, there)
        self.assertNotIn(MARK_GLYPH, there)

    def test_expired_mark_is_not_rendered(self):
        mf = agent_marks.load(self.store)
        agent_marks.toggle(
            mf, self.root, "agent-old",
            now=int(__import__("time").time() - 10 * 86400),
        )
        agent_marks.dump(mf, self.store)
        plain = Text.from_markup(
            self.row(self.app(MiniMonitorApp), snapshot("agent-old"))
        ).plain
        self.assertNotIn(MARK_GLYPH, plain)


class MountedRenderTests(_MarksFixture):
    """The composited widget, not just the builder's return value."""

    def test_mounted_card_renders_the_mark(self):
        self.mark("agent-t1")

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(100, 30)) as pilot:
                app._monitor = _FakeMonitor(self.root)
                app._marks_view = agent_marks.MarksView(self.store)
                app._set_session_root_map(
                    app._monitor.get_session_to_project_mapping()
                )
                app._refresh_marks()
                snaps = {"%1": snapshot("agent-t1"), "%2": snapshot(
                    "agent-plain", pane_id="%2")}
                app._snapshots = snaps
                app._focused_pane_id = "%1"
                app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#pane-list PaneCard"))
                self.assertTrue(cards, "no PaneCard mounted")
                texts = []
                for card in cards:
                    rendered = card.render()
                    texts.append(getattr(
                        rendered, "plain", Text.from_markup(str(rendered)).plain
                    ))
                joined = "\n".join(texts)
                self.assertIn(MARK_GLYPH, joined)
                self.assertIn(MARK_EMPTY_GLYPH, joined)

        asyncio.run(runner())


class BindingSurfaceTests(unittest.TestCase):
    def test_space_is_bound_to_toggle_mark_in_both_apps(self):
        for cls in (MiniMonitorApp, MonitorApp):
            with self.subTest(app=cls.__name__):
                pairs = {(b.key, b.action) for b in cls.BINDINGS}
                self.assertIn(("space", "toggle_mark"), pairs)

    def test_action_exists_and_is_async(self):
        for cls in (MiniMonitorApp, MonitorApp):
            with self.subTest(app=cls.__name__):
                self.assertTrue(inspect.iscoroutinefunction(cls.action_toggle_mark))

    def test_space_does_not_collide_with_an_existing_binding(self):
        for cls in (MiniMonitorApp, MonitorApp):
            with self.subTest(app=cls.__name__):
                spaces = [b for b in cls.BINDINGS if b.key == "space"]
                self.assertEqual(len(spaces), 1)

    def test_monitor_binding_is_disabled_outside_the_pane_list_zone(self):
        """check_action already gates every pane-list binding by zone, so
        `space` keeps reaching the tmux pane in the preview/shadow zones."""
        from monitor.monitor_app import Zone
        app = MonitorApp.__new__(MonitorApp)
        app._active_zone = Zone.PREVIEW
        self.assertFalse(app.check_action("toggle_mark", ()))
        app._active_zone = Zone.PANE_LIST
        self.assertTrue(app.check_action("toggle_mark", ()))


class KeyHintsTests(unittest.TestCase):
    def _hints(self) -> str:
        app = MiniMonitorApp.__new__(MiniMonitorApp)
        for widget in MiniMonitorApp.compose(app):
            if getattr(widget, "id", None) == "mini-key-hints":
                return widget.render().plain
        self.fail("compose yielded no #mini-key-hints widget")

    def test_hints_mention_the_mark_key(self):
        self.assertIn("space:mark", self._hints())

    def test_hints_stay_within_the_width_budget(self):
        too_wide = [
            ln for ln in self._hints().split("\n") if len(ln) > _HINT_WIDTH_BUDGET
        ]
        self.assertEqual(
            too_wide, [], f"hint lines exceed {_HINT_WIDTH_BUDGET} cols"
        )


class WidthBudgetTests(_MarksFixture):
    """The mark costs two columns on every minimonitor row; the name budget was
    cut 22 -> 20 to pay for it."""

    def test_long_window_name_is_truncated_to_20(self):
        app = self.app(MiniMonitorApp)
        long_name = "agent-" + "x" * 40
        plain = Text.from_markup(self.row(app, snapshot(long_name))).plain
        head = plain.split("  ")[0]
        name_part = head.split(" ")[-1]
        self.assertEqual(len(name_part), 20)
        self.assertTrue(name_part.endswith("…"))

    def test_full_monitor_does_not_truncate(self):
        app = self.app(MonitorApp)
        long_name = "agent-" + "y" * 40
        plain = Text.from_markup(self.row(app, snapshot(long_name))).plain
        self.assertIn(long_name, plain)


if __name__ == "__main__":
    unittest.main(verbosity=1)
