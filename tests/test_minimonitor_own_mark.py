"""Tests for minimonitor's `space` → prioritized mark on the FOLLOWED agent (t1383).

`space` used to resolve through `_get_focused_pane_id()`, i.e. the highlighted
card in the scrollable list. The followed agent — the code agent sharing this
minimonitor's tmux window — is structurally unreachable that way: it is dropped
from the list by `_rebuild_pane_list` and rendered as plain, non-focusable
`Static`s by `_maybe_build_own_agent_panel`. So the one agent this companion
pane exists to watch was the one agent it could not mark.

t1383 **retargets** `space` rather than adding a second key: in the minimonitor
it always acts on the followed agent, whatever the list highlights. The full
monitor keeps the inherited focus-resolved action — it follows nothing, so focus
is its only target, and it stays the way to mark any *other* agent. Minimonitor
list rows keep rendering ★/☆ read-only.

Three layers, deliberately separated so each negative control breaks exactly one:

1. **Resolution** — the followed agent wins over focus. Driven with a *real*
   `MiniPaneCard` focused, because that is the arrangement the old code passes
   and the new code must not.
2. **Render state matrix** — `_refresh_own_mark` in isolation, including the
   agent → renamed transition that must *remove* the glyph rather than strand
   a stale ★ on a pane whose `space` now refuses.
3. **Wiring** — layer 2 calls `_refresh_own_mark()` directly and would pass with
   the production call missing from `_refresh_data`, or ordered before
   `_refresh_marks()` / `_set_session_root_map()`. So the AC-level proof drives a
   real refresh cycle on a mounted app and touches nothing else.

Mock-based apart from layer 3's mounted app; no live tmux, no real TmuxMonitor.

Run: python3 tests/test_minimonitor_own_mark.py
or:  bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_marks  # noqa: E402
from monitor import minimonitor_app as mm  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)
from monitor.monitor_shared import (  # noqa: E402
    MARK_EMPTY_GLYPH, MARK_GLYPH, AgentMarksMixin,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402

SESSION = "demo"
OTHER_SESSION = "other"
OWN_WINDOW_INDEX = "1"
OWN_WINDOW = "agent-followed"
LIST_WINDOW = "agent-in-the-list"

# `#mini-key-hints` carries `padding: 0 1`, leaving this many usable columns.
_HINT_WIDTH_BUDGET = 38


def pane(
    window: str,
    *,
    session: str = SESSION,
    pane_id: str = "%1",
    window_index: str = OWN_WINDOW_INDEX,
    category: PaneCategory = PaneCategory.AGENT,
) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index=window_index, window_name=window, pane_index="0",
        pane_id=pane_id, pane_pid=4242, current_command="node",
        width=80, height=24, category=category, session_name=session,
    )


def snapshot(window: str, **kw) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane(window, **kw), content="x", timestamp=0.0,
        idle_seconds=1.0, is_idle=False,
    )


def own_snapshot(*, category: PaneCategory = PaneCategory.AGENT,
                 window: str = OWN_WINDOW) -> PaneSnapshot:
    """The pane sharing this minimonitor's window (window_index 1)."""
    return snapshot(window, pane_id="%1", category=category)


def list_snapshot(*, session: str = SESSION) -> PaneSnapshot:
    """A different agent, in a different window — a selectable list card."""
    return snapshot(LIST_WINDOW, pane_id="%2", window_index="2", session=session)


class _FakeMonitor:
    multi_session = False

    def __init__(self, mapping):
        self._mapping = mapping

    def get_session_to_project_mapping(self): return self._mapping
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None
    def get_shadow_snapshots(self): return {}
    # Read by `_rebuild_session_bar` on every real tick (layer 3).
    def control_state(self): return TmuxControlState.CONNECTED


class _FakeTaskCache:
    def get_task_id_for_pane(self, pane): return None
    def get_task_info(self, task_id, session=None): return None
    def update_session_mapping(self, mapping): pass
    def invalidate(self, task_id, session=None): pass


class _FakePanel:
    """Stand-in for the `#mini-own-agent` VerticalScroll."""

    def __init__(self) -> None:
        self.mounted: list = []

    async def remove_children(self):
        self.mounted = []

    async def mount_all(self, widgets):
        self.mounted = list(widgets)


class _StoreFixture(unittest.TestCase):
    """An isolated marks store plus two project roots."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.store = self.tmp / "marks.json"
        self.here = self.tmp / "here"
        self.there = self.tmp / "there"
        self.here.mkdir()
        self.there.mkdir()

    def write_mark(self, window: str, *, root: Path | None = None,
                   age_days: float = 0.0) -> None:
        """Set a mark straight in the store — no app, no keypress.

        `age_days` back-dates `marked_at` so the TTL filter can be exercised.
        """
        mf = agent_marks.load(self.store)
        agent_marks.toggle(
            mf, root if root is not None else self.here, window,
            now=time.time() - age_days * 86400.0,
        )
        agent_marks.dump(mf, self.store)

    def mapping(self):
        return {SESSION: self.here, OTHER_SESSION: self.there}


# ---------------------------------------------------------------------------
# Layer 1 — resolution: the followed agent wins over focus
# ---------------------------------------------------------------------------

class _ResolutionFixture(_StoreFixture):
    def app(self, *, snaps=None, mapping=None, reply=(0, "MARKED:x|y"),
            own_window_index=OWN_WINDOW_INDEX):
        app = MiniMonitorApp.__new__(MiniMonitorApp)
        app._project_root = self.here
        app._monitor = _FakeMonitor(
            mapping if mapping is not None else self.mapping()
        )
        app._session = SESSION
        app._own_window_index = own_window_index
        app._snapshots = {
            s.pane.pane_id: s
            for s in (snaps if snaps is not None
                      else [own_snapshot(), list_snapshot()])
        }
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = float("inf")
        app._marks_purge_inflight = False
        app._set_session_root_map(app._monitor.get_session_to_project_mapping())
        app._refresh_marks()

        app.spy_calls: list[list[str]] = []
        app.spy_notify: list[tuple[str, str]] = []
        app.spy_later: list = []
        app.notify = lambda msg, **kw: app.spy_notify.append(
            (msg, kw.get("severity", "information"))
        )
        app.call_later = lambda fn, *a: app.spy_later.append(fn)
        app._refresh_data = lambda: None

        async def fake_cmd(args):
            app.spy_calls.append(list(args))
            return reply

        app._run_marks_cmd = fake_cmd
        return app

    @staticmethod
    def press_space(app, *, focused=None):
        """Drive the action with `focused` as the live focused widget.

        Patches the real `focused` property rather than stubbing
        `_get_focused_pane_id`, so the inherited action's real `isinstance`
        resolution runs — that is what makes the negative control meaningful.
        """
        with patch.object(
            MiniMonitorApp, "focused", new_callable=PropertyMock
        ) as prop:
            prop.return_value = focused
            asyncio.run(app.action_toggle_mark())


class OverrideSurfaceTests(unittest.TestCase):
    def test_minimonitor_overrides_the_inherited_action(self):
        """Structural: the override exists and is still a coroutine."""
        self.assertIsNot(
            MiniMonitorApp.action_toggle_mark,
            AgentMarksMixin.action_toggle_mark,
            "minimonitor must not inherit the focus-resolved toggle",
        )
        self.assertTrue(
            inspect.iscoroutinefunction(MiniMonitorApp.action_toggle_mark)
        )

    def test_space_is_still_the_only_mark_binding(self):
        """No second key was added — the whole point of the design."""
        rows = [b for b in MiniMonitorApp.BINDINGS
                if getattr(b, "action", None) == "toggle_mark"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].key, "space")


class ResolutionTests(_ResolutionFixture):
    def test_followed_agent_wins_while_a_different_card_is_focused(self):
        """THE regression. A list card holds focus; the followed agent is marked.

        Against the inherited focus-resolved action this writes the *focused*
        card's window instead.
        """
        app = self.app()
        card = mm.MiniPaneCard("%2", "some other agent")
        self.press_space(app, focused=card)

        self.assertEqual(len(app.spy_calls), 1)
        self.assertEqual(
            app.spy_calls[0],
            ["toggle", os.path.realpath(self.here), OWN_WINDOW],
        )

    def test_focused_card_from_another_repo_is_still_ignored(self):
        """Focus is not merely deprioritized — it is not consulted at all."""
        app = self.app(
            snaps=[own_snapshot(), list_snapshot(session=OTHER_SESSION)]
        )
        card = mm.MiniPaneCard("%2", "an agent in another repo")
        self.press_space(app, focused=card)

        self.assertEqual(
            app.spy_calls[0],
            ["toggle", os.path.realpath(self.here), OWN_WINDOW],
        )
        self.assertNotEqual(app.spy_calls[0][1], os.path.realpath(self.there))
        self.assertNotEqual(app.spy_calls[0][2], LIST_WINDOW)

    def test_nothing_focused_still_toggles_the_followed_agent(self):
        """The other direction: the old code returned silently here."""
        app = self.app()
        self.press_space(app, focused=None)

        self.assertEqual(
            app.spy_calls,
            [["toggle", os.path.realpath(self.here), OWN_WINDOW]],
        )

    def test_no_followed_agent_warns_and_never_writes(self):
        app = self.app(snaps=[list_snapshot()], own_window_index=None)
        self.press_space(app, focused=None)

        self.assertEqual(app.spy_calls, [])
        self.assertEqual(len(app.spy_notify), 1)
        self.assertEqual(app.spy_notify[0][1], "warning")
        self.assertIn("No followed agent", app.spy_notify[0][0])

    def test_renamed_own_window_refuses_like_k_n_and_I(self):
        """`_find_own_agent_snapshot` is AGENT-only on purpose: renaming a window
        off the `agent-` prefix is how a user takes it out of the rotation."""
        app = self.app(
            snaps=[own_snapshot(category=PaneCategory.OTHER, window="noam_bugs"),
                   list_snapshot()]
        )
        card = mm.MiniPaneCard("%2", "some other agent")
        self.press_space(app, focused=card)

        self.assertEqual(app.spy_calls, [])
        self.assertEqual(app.spy_notify[0][1], "warning")
        self.assertIn("No followed agent", app.spy_notify[0][0])

    def test_marked_outcome_routes_through_the_shared_sink(self):
        app = self.app(reply=(0, f"MARKED:/r|{OWN_WINDOW}"))
        self.press_space(app, focused=None)
        self.assertEqual(app.spy_notify[0][1], "information")
        self.assertIn(OWN_WINDOW, app.spy_notify[0][0])
        self.assertEqual(len(app.spy_later), 1, "must schedule a repaint")

    def test_lock_busy_outcome_routes_through_the_shared_sink(self):
        app = self.app(reply=(3, "LOCK_BUSY"))
        self.press_space(app, focused=None)
        self.assertEqual(app.spy_notify[0][1], "warning")
        self.assertIn("busy", app.spy_notify[0][0].lower())
        self.assertEqual(app.spy_later, [], "must not repaint on a failed write")


# ---------------------------------------------------------------------------
# Layer 2 — docked-panel render state matrix
# ---------------------------------------------------------------------------

class PanelRenderTests(_StoreFixture):
    def app(self, snaps, *, own_window_index=OWN_WINDOW_INDEX):
        panel = _FakePanel()
        app = MiniMonitorApp.__new__(MiniMonitorApp)
        app.query_one = lambda *a, **k: panel
        app._project_root = self.here
        app._monitor = _FakeMonitor(self.mapping())
        app._session = SESSION
        app._own_window_index = own_window_index
        app._target_width = 40
        app._task_cache = _FakeTaskCache()
        app._snapshots = {s.pane.pane_id: s for s in snaps}
        app._own_panel_built = False
        app._own_card = None
        app._own_identity_text = ""
        app._own_mark_state = None
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = float("inf")
        app._marks_purge_inflight = False
        app._set_session_root_map(app._monitor.get_session_to_project_mapping())
        app._refresh_marks()
        return app, panel

    @staticmethod
    def card_text(panel) -> str:
        return panel.mounted[1].render().plain

    def build(self, app):
        asyncio.run(app._maybe_build_own_agent_panel())

    def test_unmarked_agent_shows_the_hollow_star(self):
        app, panel = self.app([own_snapshot()])
        self.build(app)
        text = self.card_text(panel)
        self.assertIn(MARK_EMPTY_GLYPH, text)
        self.assertNotIn(MARK_GLYPH, text)
        self.assertIn(OWN_WINDOW, text)

    def test_marked_agent_shows_the_filled_star(self):
        self.write_mark(OWN_WINDOW)
        app, panel = self.app([own_snapshot()])
        self.build(app)
        text = self.card_text(panel)
        self.assertIn(MARK_GLYPH, text)
        self.assertNotIn(MARK_EMPTY_GLYPH, text)

    def test_non_agent_window_carries_no_glyph_at_all(self):
        """Not a read-only ☆: `space` refuses here, so nothing is markable."""
        app, panel = self.app(
            [own_snapshot(category=PaneCategory.OTHER, window="noam_bugs")]
        )
        self.build(app)
        text = self.card_text(panel)
        self.assertNotIn(MARK_GLYPH, text)
        self.assertNotIn(MARK_EMPTY_GLYPH, text)
        self.assertIn("noam_bugs", text)

    def test_mark_set_elsewhere_appears_on_the_next_repaint(self):
        app, panel = self.app([own_snapshot()])
        self.build(app)
        self.assertIn(MARK_EMPTY_GLYPH, self.card_text(panel))

        # Another repo / `ait monitor` writes the mark. No keypress here.
        self.write_mark(OWN_WINDOW)
        app._marks_view.invalidate()
        app._refresh_marks()
        app._refresh_own_mark()

        self.assertIn(MARK_GLYPH, self.card_text(panel))

    def test_expired_mark_disappears_on_the_next_repaint(self):
        self.write_mark(OWN_WINDOW)
        app, panel = self.app([own_snapshot()])
        self.build(app)
        self.assertIn(MARK_GLYPH, self.card_text(panel))

        # Re-stamp the same mark well beyond the TTL window.
        self.store.unlink()
        self.write_mark(OWN_WINDOW,
                        age_days=agent_marks.DEFAULT_TTL_DAYS + 1.0)
        app._marks_view.invalidate()
        app._refresh_marks()
        app._refresh_own_mark()

        self.assertIn(MARK_EMPTY_GLYPH, self.card_text(panel))
        self.assertNotIn(MARK_GLYPH, self.card_text(panel))

    def test_rename_out_of_the_agent_category_removes_a_marked_glyph(self):
        """The stale-★ case.

        The panel's identity is frozen at build time, so a build-time
        "is this an agent" flag plus an early return would leave the ★ on a
        pane whose `space` now refuses. The glyph must be present exactly when
        `space` would act.
        """
        self.write_mark(OWN_WINDOW)
        app, panel = self.app([own_snapshot()])
        self.build(app)
        self.assertIn(MARK_GLYPH, self.card_text(panel))
        frozen = self.card_text(panel)

        # tmux rename-window: the pane re-categorizes to OTHER.
        renamed = own_snapshot(category=PaneCategory.OTHER, window="noam_bugs")
        app._snapshots = {renamed.pane.pane_id: renamed}
        app._refresh_own_mark()

        text = self.card_text(panel)
        self.assertNotIn(MARK_GLYPH, text)
        self.assertNotIn(MARK_EMPTY_GLYPH, text)
        self.assertIn(
            OWN_WINDOW, text,
            "the identity stays frozen through a rename — only the glyph moves",
        )

        # Renamed back: the glyph returns.
        back = own_snapshot()
        app._snapshots = {back.pane.pane_id: back}
        app._refresh_own_mark()
        self.assertEqual(self.card_text(panel), frozen)

    def test_repaint_is_a_no_op_before_the_panel_is_built(self):
        app, _ = self.app([own_snapshot()])
        app._refresh_own_mark()  # must not raise
        self.assertIsNone(app._own_card)

    def test_static_panel_contract_survives_the_new_glyph(self):
        """The mark is the ONLY live element — every excluded one stays out."""
        self.write_mark(OWN_WINDOW)
        app, panel = self.app([own_snapshot()])
        self.build(app)
        text = self.card_text(panel)
        self.assertIn(MARK_GLYPH, text)
        for banned in ("●", "◆", "≈", "=", "IDLE", "PROMPT", "Active",
                       "COMPLETED"):
            self.assertNotIn(banned, text, f"docked panel leaked {banned!r}")

    def test_identity_text_is_byte_identical_across_a_mark_flip(self):
        app, panel = self.app([own_snapshot()])
        self.build(app)
        before = self.card_text(panel)

        self.write_mark(OWN_WINDOW)
        app._marks_view.invalidate()
        app._refresh_marks()
        app._refresh_own_mark()
        after = self.card_text(panel)

        self.assertNotEqual(before, after)
        self.assertEqual(
            before.split(" ", 1)[1], after.split(" ", 1)[1],
            "only the leading glyph may differ",
        )


class KeyHintsTests(unittest.TestCase):
    def _hints(self) -> str:
        app = MiniMonitorApp.__new__(MiniMonitorApp)
        for widget in MiniMonitorApp.compose(app):
            if getattr(widget, "id", None) == "mini-key-hints":
                return widget.render().plain
        self.fail("compose yielded no #mini-key-hints widget")

    def test_hints_say_the_key_targets_the_followed_agent(self):
        hints = self._hints()
        self.assertIn("space:mark", hints)
        self.assertIn("followed agent", hints)

    def test_hints_stay_within_the_width_budget(self):
        too_wide = [ln for ln in self._hints().split("\n")
                    if len(ln) > _HINT_WIDTH_BUDGET]
        self.assertEqual(too_wide, [],
                         f"hint lines exceed {_HINT_WIDTH_BUDGET} cols")


# ---------------------------------------------------------------------------
# Layer 3 — wiring, proven through a real refresh cycle
# ---------------------------------------------------------------------------

class RefreshCycleWiringTests(_StoreFixture):
    """Drive `_refresh_data` itself; touch no mark method between assertions.

    Layer 2 would pass with `_refresh_own_mark()` missing from `_refresh_data`,
    or placed before `_refresh_marks()` / `_set_session_root_map()`. These
    cannot: everything between the two reads of the mounted card is one real
    tick.
    """

    def _instrument(self, app, snaps) -> None:
        """Isolate the app from tmux and from every non-tick side effect.

        - the refresh timer is stopped (this suite drives ticks by hand);
        - `_run_marks_cmd` is replaced so the purge spawns no subprocess, and
          `_marks_purge_due_at` keeps it out of the way entirely;
        - `_update_own_window_info` is stubbed because it queries tmux, and
          `_own_window_id` is cleared so the auto-close check cannot quit the
          app mid-test;
        - `_maybe_offer_concerns` is stubbed (it reads shadow panes).
        """
        async def fake_cmd(args):
            return (0, "MARKED:x|y")

        if getattr(app, "_refresh_timer", None) is not None:
            app._refresh_timer.stop()
            app._refresh_timer = None
        app._monitor = _FakeMonitor(self.mapping())
        app._monitor.capture_all_async = _capture(snaps)
        app._task_cache = _FakeTaskCache()
        app._session = SESSION
        app._own_window_index = OWN_WINDOW_INDEX
        app._own_window_id = None
        app._update_own_window_info = lambda: None
        app._maybe_offer_concerns = _noop_async
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = float("inf")
        app._marks_purge_inflight = False
        app._run_marks_cmd = fake_cmd

    @staticmethod
    def _card_text(app) -> str:
        cards = list(app.query("#mini-own-agent .mini-own-card"))
        assert cards, "docked panel card not mounted"
        return cards[0].render().plain

    def test_a_mark_written_elsewhere_lands_via_one_refresh_cycle(self):
        seen: list[str] = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.here)
            async with app.run_test(size=(40, 30)) as pilot:
                self._instrument(app, [own_snapshot(), list_snapshot()])
                await app._refresh_data()
                await pilot.pause()
                seen.append(self._card_text(app))

                # Another repo / `ait monitor` writes the mark — nothing in the
                # app is called, only the store on disk changes.
                self.write_mark(OWN_WINDOW)

                await app._refresh_data()
                await pilot.pause()
                seen.append(self._card_text(app))

        asyncio.run(runner())
        self.assertIn(MARK_EMPTY_GLYPH, seen[0])
        self.assertIn(
            MARK_GLYPH, seen[1],
            "a mark set elsewhere did not reach the docked panel through "
            "_refresh_data — the repaint is missing or misordered",
        )

    def test_an_expired_mark_clears_via_one_refresh_cycle(self):
        self.write_mark(OWN_WINDOW)
        seen: list[str] = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.here)
            async with app.run_test(size=(40, 30)) as pilot:
                self._instrument(app, [own_snapshot(), list_snapshot()])
                await app._refresh_data()
                await pilot.pause()
                seen.append(self._card_text(app))

                self.store.unlink()
                self.write_mark(OWN_WINDOW,
                                age_days=agent_marks.DEFAULT_TTL_DAYS + 1.0)

                await app._refresh_data()
                await pilot.pause()
                seen.append(self._card_text(app))

        asyncio.run(runner())
        self.assertIn(MARK_GLYPH, seen[0])
        self.assertIn(MARK_EMPTY_GLYPH, seen[1])

    def test_local_space_reaches_the_panel_through_the_same_cycle(self):
        """Closes the loop `action_toggle_mark`'s `call_later(_refresh_data)`
        relies on: the recording double actually mutates the store."""
        seen: list[str] = []
        fixture = self

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.here)
            async with app.run_test(size=(40, 30)) as pilot:
                self._instrument(app, [own_snapshot(), list_snapshot()])

                async def toggling_cmd(args):
                    fixture.write_mark(args[2], root=Path(args[1]))
                    return (0, f"MARKED:{args[1]}|{args[2]}")

                app._run_marks_cmd = toggling_cmd

                await app._refresh_data()
                await pilot.pause()
                seen.append(self._card_text(app))

                await app.action_toggle_mark()
                await app._refresh_data()
                await pilot.pause()
                seen.append(self._card_text(app))

        asyncio.run(runner())
        self.assertIn(MARK_EMPTY_GLYPH, seen[0])
        self.assertIn(MARK_GLYPH, seen[1])


class CompositedWidthTests(_StoreFixture):
    """The glyph costs 2 columns on a line the docked panel never truncates.

    A render string cannot show folding, so this mounts a real 40-column screen
    and reads the composited strips — the same reason
    `test_minimonitor_other_section._RowHost` exists (t1351).
    """

    # 40-col pane, `padding: 0 1` ⇒ 38 usable, minus "★ " ⇒ 36 for the name.
    LONGEST_UNFOLDED = "agent-" + "x" * 30  # exactly 36

    def _first_card_line(self, window: str) -> str:
        lines: list[str] = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.here)
            async with app.run_test(size=(40, 24)) as pilot:
                RefreshCycleWiringTests._instrument(
                    self, app, [own_snapshot(window=window), list_snapshot()]
                )
                self.write_mark(window)
                await app._refresh_data()
                await pilot.pause()
                for strip in app.screen._compositor.render_strips():
                    text = "".join(s.text for s in strip).rstrip()
                    if MARK_GLYPH in text:
                        lines.append(text)
                        break

        asyncio.run(runner())
        self.assertTrue(lines, "no marked line composited")
        return lines[0]

    def test_a_36_char_name_still_fits_beside_the_glyph(self):
        line = self._first_card_line(self.LONGEST_UNFOLDED)
        self.assertIn(MARK_GLYPH, line)
        self.assertIn(
            self.LONGEST_UNFOLDED, line,
            "the name folded away from the glyph — the width budget shrank",
        )

    def test_a_realistic_agent_name_is_nowhere_near_the_budget(self):
        """Real windows are `agent-pick-1383` / `agent-explore-2` (11-17)."""
        line = self._first_card_line("agent-pick-1383")
        self.assertIn(f"{MARK_GLYPH} agent-pick-1383", line)


def _capture(snaps):
    async def capture_all_async():
        return {s.pane.pane_id: s for s in snaps}
    return capture_all_async


async def _noop_async():
    return None


if __name__ == "__main__":
    unittest.main(verbosity=1)
