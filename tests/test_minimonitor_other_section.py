"""Tests for minimonitor's uncategorized ("other") section (t1382).

Renaming a tmux agent window off the ``agent-`` prefix flips every pane in it to
``PaneCategory.OTHER``. ``ait monitor`` has had an ``OTHER`` zone since forever;
minimonitor had **no** ``OTHER`` handling at all, so the renamed window simply
disappeared from it. This covers the section that fixes that, plus the two
consequences of adding it:

* ``_find_own_window_snapshot`` — the identity/presentation seam, so the docked
  "this agent" panel builds at all in a renamed window (the AGENT-only lookup
  returned ``None`` every cycle and the panel was never mounted). Its
  counterpart ``_find_own_agent_snapshot`` stays AGENT-only, which is what keeps
  ``k`` / ``n`` / ``e`` / ``E`` / ``space`` refusing there — the deliberate half
  of the decision, pinned here so a later change cannot loosen it silently.
* Action guards — "the focused card is an agent" stops being an invariant once
  the list can hold OTHER cards, so ``d`` / ``i`` re-check inside the action.
  The mark guard lives in ``AgentMarksMixin._toggle_mark_for``, the write path
  both apps share, so it is asserted for **both** — through the sink, because
  since t1383 the two apps no longer resolve their target the same way
  (monitor: live focus; minimonitor: the followed agent).

Mock-based: no live tmux, no real ``TmuxMonitor``. The ``_rebuild_pane_list``
cases use the capture-``mount_all`` container harness from
``tests/test_multi_session_minimonitor.sh``; the width case mounts a real
40-column Textual screen because a widget's render string cannot reveal Rich
ellipsising (t1351).

Run: python3 tests/test_minimonitor_other_section.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MiniMonitorApp/MonitorApp only rename their tmux window when constructed by
# the production launcher, but scrub the ambient tmux env anyway so nothing here
# can touch the pane the suite is running in (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual.app import App, ComposeResult  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402
from textual.widgets import Static  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import PaneCategory  # noqa: E402

# 40-wide tmux pane minus MiniPaneCard's `padding: 0 1`.
_ROW_WIDTH_BUDGET = 38


def _snap(
    pane_id: str,
    *,
    window_index: str = "1",
    pane_index: str = "0",
    window_name: str = "agent-pick-42",
    category=PaneCategory.AGENT,
    session: str = "s1",
    command: str = "python",
):
    pane = SimpleNamespace(
        pane_id=pane_id,
        session_name=session,
        window_index=window_index,
        pane_index=pane_index,
        window_name=window_name,
        category=category,
        current_command=command,
    )
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)


class _FakeContainer:
    """Captures what `_rebuild_pane_list` mounts."""

    def __init__(self) -> None:
        self.mounted: list = []

    async def remove_children(self):
        pass

    async def mount_all(self, widgets):
        self.mounted = list(widgets)


def _mk_list_app(snapshots, *, own_window_index=None, multi_session=False):
    """MiniMonitorApp stubbed down to what `_rebuild_pane_list` touches."""
    container = _FakeContainer()
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app.query_one = lambda *a, **k: container
    app._own_window_index = own_window_index
    app._session = "s1"
    app._snapshots = {s.pane.pane_id: s for s in snapshots}
    app._task_cache = SimpleNamespace(
        get_task_id=lambda w: None,
        get_task_id_for_pane=lambda p: None,
        get_task_info=lambda t, s=None: None,
    )
    app._monitor = SimpleNamespace(
        multi_session=multi_session,
        get_compare_mode=lambda pid: "stripped",
        is_compare_mode_overridden=lambda pid: False,
        get_shadow_snapshot=lambda pid: None,
        get_session_to_project_mapping=lambda: {},
    )
    app._completed_pane_ids = frozenset()
    app._gate_cache = SimpleNamespace(summary_for=lambda i: None, clear=lambda: None)
    app._init_agent_marks()
    return app, container


def _statics(widgets):
    return [w for w in widgets if isinstance(w, Static)
            and not isinstance(w, mm.MiniPaneCard)]


def _cards(widgets):
    return [w for w in widgets if isinstance(w, mm.MiniPaneCard)]


class OtherSectionRenderTests(unittest.TestCase):
    """`_rebuild_pane_list` must render OTHER panes under their own header."""

    def test_renamed_window_is_listed_under_an_other_header(self):
        """The reported defect: the renamed window must not vanish."""
        app, container = _mk_list_app([
            _snap("%1", window_index="1", window_name="agent-pick-42"),
            _snap("%2", window_index="7", window_name="noam_bugs",
                  category=PaneCategory.OTHER, command="bash"),
        ])
        asyncio.run(app._rebuild_pane_list())

        self.assertEqual([c.pane_id for c in _cards(container.mounted)],
                         ["%1", "%2"])
        headers = [s.render().plain for s in _statics(container.mounted)]
        self.assertEqual(len(headers), 1, f"expected one header, got {headers}")
        self.assertIn("other (1)", headers[0])
        # Order: agents first, then the header, then the OTHER cards.
        kinds = ["card" if isinstance(w, mm.MiniPaneCard) else "static"
                 for w in container.mounted]
        self.assertEqual(kinds, ["card", "static", "card"])

    def test_no_other_panes_means_no_header(self):
        """Negative control: an agents-only list is unchanged from before."""
        app, container = _mk_list_app([
            _snap("%1", window_name="agent-pick-42"),
            _snap("%2", window_index="2", window_name="agent-pick-43"),
        ])
        asyncio.run(app._rebuild_pane_list())

        self.assertEqual(_statics(container.mounted), [])
        self.assertEqual(len(_cards(container.mounted)), 2)

    def test_tui_panes_are_rendered_by_neither_section(self):
        """Same as the full monitor: TUI windows are not list material."""
        app, container = _mk_list_app([
            _snap("%1", window_name="agent-pick-42"),
            _snap("%9", window_index="3", window_name="board",
                  category=PaneCategory.TUI),
        ])
        asyncio.run(app._rebuild_pane_list())

        self.assertEqual([c.pane_id for c in _cards(container.mounted)], ["%1"])
        self.assertEqual(_statics(container.mounted), [])

    def test_own_renamed_pane_is_excluded_from_the_other_section(self):
        """The followed pane lives in the docked panel — never listed twice."""
        app, container = _mk_list_app(
            [
                _snap("%2", window_index="7", window_name="noam_bugs",
                      category=PaneCategory.OTHER, command="bash"),
                _snap("%3", window_index="8", window_name="scratch",
                      category=PaneCategory.OTHER, command="bash"),
            ],
            own_window_index="7",
        )
        asyncio.run(app._rebuild_pane_list())

        self.assertEqual([c.pane_id for c in _cards(container.mounted)], ["%3"])
        self.assertIn("other (1)", _statics(container.mounted)[0].render().plain)

    def test_session_dividers_are_emitted_inside_the_other_section(self):
        """The divider rule is shared by both sections, not agent-only."""
        app, container = _mk_list_app(
            [
                _snap("%1", window_name="noam_bugs", session="sA",
                      category=PaneCategory.OTHER),
                _snap("%2", window_index="2", window_name="scratch",
                      session="sB", category=PaneCategory.OTHER),
            ],
            multi_session=True,
        )
        asyncio.run(app._rebuild_pane_list())

        texts = [s.render().plain for s in _statics(container.mounted)]
        # header + one divider per session
        self.assertEqual(len(texts), 3,
                         f"expected an other header and two dividers: {texts}")
        self.assertIn("other (2)", texts[0])
        self.assertTrue(any("sA" in t for t in texts), texts)
        self.assertTrue(any("sB" in t for t in texts), texts)


class OtherCardTextTests(unittest.TestCase):
    def test_long_name_and_command_are_truncated(self):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        text = app._other_card_text(_snap(
            "%2", window_name="a" * 40, category=PaneCategory.OTHER,
            command="some-very-long-command",
        ))
        self.assertIn("…", text)

    def test_row_fits_the_column_budget(self):
        """Terminal width of the worst case must fit the ~38 usable columns.

        Measured with ``cell_len``, not ``len``: cells are what the budget is
        denominated in. **Single-cell input only** — the caps in
        ``_other_card_text`` are applied with ``len()``, so a double-width name
        still overflows (36 code points, 64 cells). That gap is inherited from
        ``_agent_card_text`` and is deferred to the row-width audit in t1351,
        which owns both rows; add a wide-character case here when it lands.
        """
        from rich.cells import cell_len
        from rich.text import Text

        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        markup = app._other_card_text(_snap(
            "%2", window_name="w" * 60, category=PaneCategory.OTHER,
            command="c" * 60,
        ))
        plain = Text.from_markup(markup).plain
        self.assertLessEqual(
            cell_len(plain), _ROW_WIDTH_BUDGET,
            f"other row is {cell_len(plain)} cells, budget is "
            f"{_ROW_WIDTH_BUDGET}: {plain!r}",
        )


class _RowHost(App):
    """A 40-column host that renders one OTHER row with minimonitor's metrics.

    Mounting is what makes this a *composited*-screen assertion: a widget's own
    render string cannot reveal that Rich ellipsised the row on its way to the
    terminal (t1351).
    """

    CSS = """
    #mini-pane-list { height: 1fr; }
    MiniPaneCard { height: auto; padding: 0 1; }
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        scroll = VerticalScroll(id="mini-pane-list")
        yield scroll

    def on_mount(self) -> None:
        self.query_one("#mini-pane-list", VerticalScroll).mount(
            mm.MiniPaneCard("%2", self._text)
        )


class OtherRowCompositedTests(unittest.TestCase):
    def test_row_is_not_ellipsised_at_40_columns(self):
        app_stub = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        # Worst case that the truncation is supposed to make fit: both fields
        # already at their caps.
        text = app_stub._other_card_text(_snap(
            "%2", window_name="w" * 60, category=PaneCategory.OTHER,
            command="c" * 60,
        ))

        async def run():
            host = _RowHost(text)
            async with host.run_test(size=(40, 10)):
                await host.workers.wait_for_complete()
                screen = "\n".join(
                    strip.text for strip in host.screen._compositor.render_strips()
                )
            return screen

        screen = asyncio.run(run())
        row = next((ln for ln in screen.split("\n") if "○" in ln), None)
        self.assertIsNotNone(row, f"no OTHER row on screen:\n{screen}")
        # Exactly the two ellipses our own truncation inserted — Rich adding a
        # third would mean the row overflowed the composited width.
        self.assertEqual(
            row.count("…"), 2,
            f"row was ellipsised by the compositor: {row!r}",
        )


class OwnWindowResolverTests(unittest.TestCase):
    """The identity seam vs the action seam."""

    def _app(self, snapshots, own_window_index="7"):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._snapshots = {s.pane.pane_id: s for s in snapshots}
        app._session = "s1"
        app._own_window_index = own_window_index
        return app

    def test_agent_seam_still_refuses_in_a_renamed_window(self):
        """Deliberate: a renamed window is out of the agent rotation.

        This is what keeps `k` / `n` / `e` / `E` / `I` reporting "no followed
        agent" there, and it must not be loosened by the panel fix.
        """
        app = self._app([_snap("%2", window_index="7", window_name="noam_bugs",
                               category=PaneCategory.OTHER)])
        self.assertIsNone(app._find_own_agent_snapshot())

    def test_window_seam_resolves_the_renamed_pane(self):
        app = self._app([_snap("%2", window_index="7", window_name="noam_bugs",
                               category=PaneCategory.OTHER)])
        snap = app._find_own_window_snapshot()
        self.assertIsNotNone(snap)
        self.assertEqual(snap.pane.pane_id, "%2")

    def test_window_seam_prefers_the_agent_pane(self):
        """A window holding an agent AND a stray shell resolves to the agent."""
        app = self._app([
            _snap("%5", window_index="7", pane_index="1", window_name="scratch",
                  category=PaneCategory.OTHER),
            _snap("%4", window_index="7", pane_index="0",
                  window_name="agent-pick-42"),
        ])
        self.assertEqual(app._find_own_window_snapshot().pane.pane_id, "%4")

    def test_window_seam_is_deterministic_and_numeric(self):
        """Lowest pane_index wins, compared numerically — "10" is not < "2"."""
        app = self._app([
            _snap("%10", window_index="7", pane_index="10",
                  window_name="noam_bugs", category=PaneCategory.OTHER),
            _snap("%2", window_index="7", pane_index="2",
                  window_name="noam_bugs", category=PaneCategory.OTHER),
        ])
        self.assertEqual(app._find_own_window_snapshot().pane.pane_id, "%2")

    def test_window_seam_is_session_scoped(self):
        app = self._app([_snap("%2", window_index="7", window_name="noam_bugs",
                               category=PaneCategory.OTHER, session="other")])
        self.assertIsNone(app._find_own_window_snapshot())

    def test_no_own_window_index_returns_none(self):
        app = self._app([_snap("%2", window_index="7", window_name="noam_bugs",
                               category=PaneCategory.OTHER)],
                        own_window_index=None)
        self.assertIsNone(app._find_own_window_snapshot())


class _FakePanel:
    def __init__(self) -> None:
        self.mounted: list = []
        self.removals = 0

    async def remove_children(self):
        self.removals += 1

    async def mount_all(self, widgets):
        self.mounted = list(widgets)


class OwnAgentPanelTests(unittest.TestCase):
    def _app(self, snapshots, own_window_index="7"):
        panel = _FakePanel()
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app.query_one = lambda *a, **k: panel
        app._snapshots = {s.pane.pane_id: s for s in snapshots}
        app._session = "s1"
        app._own_window_index = own_window_index
        app._own_panel_built = False
        app._own_card = None
        app._own_identity_text = ""
        app._own_mark_state = None
        app._target_width = 40
        app._task_cache = SimpleNamespace(
            get_task_id_for_pane=lambda p: None,
            get_task_info=lambda t, s=None: None,
        )
        # The docked card carries the prioritized-mark glyph since t1383, so
        # the panel build reads the marks view. The empty session→root map
        # `_init_agent_marks` installs makes `_is_marked` deterministically
        # False here without touching the real store.
        app._init_agent_marks()
        return app, panel

    def test_panel_builds_in_a_renamed_window(self):
        """The defect: today the AGENT-only lookup never resolves here."""
        app, panel = self._app([_snap("%2", window_index="7",
                                      window_name="noam_bugs",
                                      category=PaneCategory.OTHER)])
        asyncio.run(app._maybe_build_own_agent_panel())

        self.assertTrue(app._own_panel_built)
        self.assertEqual(len(panel.mounted), 2)
        header = panel.mounted[0].render().plain
        self.assertIn("this window", header)
        self.assertNotIn("this agent", header)
        self.assertIn("noam_bugs", panel.mounted[1].render().plain)

    def test_agent_window_keeps_the_this_agent_header(self):
        """Positive control: the unrenamed case is untouched."""
        app, panel = self._app([_snap("%4", window_index="7",
                                      window_name="agent-pick-42")])
        asyncio.run(app._maybe_build_own_agent_panel())

        self.assertIn("this agent", panel.mounted[0].render().plain)

    def test_panel_stays_one_shot(self):
        """A rename after the panel built must not rebuild it.

        The task puts that explicitly out of scope ("captured once and not
        re-read"); pinned so the resolver change does not quietly turn the
        docked panel into a refreshing one.
        """
        app, panel = self._app([_snap("%4", window_index="7",
                                      window_name="agent-pick-42")])
        asyncio.run(app._maybe_build_own_agent_panel())
        self.assertEqual(panel.removals, 1)

        app._snapshots = {
            "%4": _snap("%4", window_index="7", window_name="noam_bugs",
                        category=PaneCategory.OTHER)
        }
        asyncio.run(app._maybe_build_own_agent_panel())
        self.assertEqual(panel.removals, 1, "panel was rebuilt on a later cycle")
        self.assertIn("this agent", panel.mounted[0].render().plain)


class _Notifier:
    """Mixin-ish helper: records notify() calls on a stubbed app."""

    @staticmethod
    def attach(app):
        app.notifications = []
        app.notify = lambda msg, **kw: app.notifications.append(
            (msg, kw.get("severity", "information"))
        )
        return app


class ActionGuardTests(unittest.TestCase):
    """`d` / `i` / `space` must re-check the category inside the action."""

    def _mini(self, snap):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._snapshots = {snap.pane.pane_id: snap}
        app._focused_pane_id = snap.pane.pane_id
        app.cycled = []
        app._monitor = SimpleNamespace(
            cycle_compare_mode=lambda pid: (app.cycled.append(pid), ("raw", False))[1],
        )
        app.call_later = lambda *a, **k: None
        app._refresh_data = lambda: None
        app._get_focused_pane_id = lambda: snap.pane.pane_id
        app.pushed = []
        app.push_screen = lambda screen, callback=None: app.pushed.append(screen)
        app._task_cache = SimpleNamespace(
            get_task_id_for_pane=lambda p: "42",
            invalidate=lambda *a, **k: None,
            get_task_info=lambda *a, **k: None,
        )
        return _Notifier.attach(app)

    def test_cycle_compare_mode_refuses_on_an_other_pane(self):
        app = self._mini(_snap("%2", window_name="noam_bugs",
                               category=PaneCategory.OTHER))
        app.action_cycle_compare_mode()
        self.assertEqual(app.cycled, [], "compare mode was written for a non-agent")
        self.assertTrue(any("agent panes only" in m for m, _ in app.notifications),
                        app.notifications)

    def test_cycle_compare_mode_still_works_on_an_agent_pane(self):
        """Positive control."""
        app = self._mini(_snap("%1", window_name="agent-pick-42"))
        app.action_cycle_compare_mode()
        self.assertEqual(app.cycled, ["%1"])

    def test_show_task_info_refuses_on_an_other_pane(self):
        app = self._mini(_snap("%2", window_name="noam_bugs",
                               category=PaneCategory.OTHER))
        app.action_show_task_info()
        self.assertEqual(app.pushed, [])
        self.assertTrue(any("Not an agent pane" in m for m, _ in app.notifications),
                        app.notifications)

    def test_show_task_info_reaches_the_dialog_for_an_agent_pane(self):
        """Positive control: the guard is not a blanket refusal."""
        app = self._mini(_snap("%1", window_name="agent-pick-42"))
        app.action_show_task_info()
        # No TaskInfo in this stub, so it stops at "not found" — but it got past
        # the category guard, which is what this pins.
        self.assertFalse(any("Not an agent pane" in m for m, _ in app.notifications),
                         app.notifications)


class SharedMarkGuardTests(unittest.TestCase):
    """The AGENT-only guard lives in `AgentMarksMixin._toggle_mark_for` — the
    shared write path both apps reach — so it is asserted for BOTH apps.

    Driven through the sink rather than `action_toggle_mark`, because since
    t1383 the two apps resolve their target differently: the monitor through
    live focus, the minimonitor through the agent it follows. Only the sink is
    common, and the guard is what this class pins. The minimonitor's own
    resolution is covered in `test_minimonitor_own_mark.py`.
    """

    def _stub(self, cls, snap):
        app = cls.__new__(cls)
        app._snapshots = {snap.pane.pane_id: snap}
        app._get_focused_pane_id = lambda: snap.pane.pane_id
        app.root_calls = []
        app._strict_root_for_snap = lambda s: (
            app.root_calls.append(s), REPO_ROOT)[1]
        # Stub the rest of the happy path too, so that removing the guard lets
        # the action run to completion and trips the assertions below — rather
        # than erroring on a missing collaborator, which would make the negative
        # control pass for the wrong reason.
        app.marks_argv = []

        async def _run_marks_cmd(argv):
            app.marks_argv.append(argv)
            return 0, "MARKED:x"

        app._run_marks_cmd = _run_marks_cmd
        app._marks_view = SimpleNamespace(invalidate=lambda: None)
        app._refresh_marks = lambda: None
        app.call_later = lambda *a, **k: None
        app._refresh_data = lambda: None
        return _Notifier.attach(app)

    def _assert_refuses(self, cls):
        snap = _snap("%2", window_name="noam_bugs", category=PaneCategory.OTHER)
        app = self._stub(cls, snap)
        asyncio.run(app._toggle_mark_for(snap))
        self.assertEqual(app.marks_argv, [],
                         f"{cls.__name__} wrote a mark for a non-agent pane")
        self.assertEqual(app.root_calls, [],
                         f"{cls.__name__} resolved a project root for a non-agent")
        self.assertTrue(
            any("agent panes only" in m for m, _ in app.notifications),
            f"{cls.__name__}: {app.notifications}",
        )

    def test_minimonitor_refuses_to_mark_an_other_pane(self):
        self._assert_refuses(mm.MiniMonitorApp)

    def test_monitor_refuses_to_mark_an_other_pane(self):
        """The full monitor has rendered focusable OTHER cards all along."""
        self._assert_refuses(MonitorApp)

    def test_agent_pane_still_reaches_the_marks_writer(self):
        """Positive control: the guard fires on category, not on everything."""
        snap = _snap("%1", window_name="agent-pick-42")
        app = self._stub(mm.MiniMonitorApp, snap)
        asyncio.run(app._toggle_mark_for(snap))
        self.assertEqual(len(app.root_calls), 1)
        self.assertEqual([argv[0] for argv in app.marks_argv], ["toggle"])

    def test_minimonitor_space_ignores_a_focused_other_card(self):
        """The t1383 inversion, stated where the old contract used to live.

        A focused OTHER card used to make `space` refuse with "agent panes
        only". It now does not reach the guard at all: the minimonitor resolves
        the *followed* agent instead, and the focused card — whatever it is —
        is irrelevant.
        """
        other = _snap("%2", window_index="9", window_name="noam_bugs",
                      category=PaneCategory.OTHER)
        followed = _snap("%1", window_index="7", window_name="agent-pick-42")
        app = self._stub(mm.MiniMonitorApp, other)
        app._snapshots = {"%1": followed, "%2": other}
        app._session = "s1"
        app._own_window_index = "7"

        asyncio.run(app.action_toggle_mark())

        self.assertEqual(len(app.marks_argv), 1)
        self.assertEqual(app.marks_argv[0][2], "agent-pick-42")
        self.assertFalse(
            any("agent panes only" in m for m, _ in app.notifications),
            f"the focused OTHER card was consulted: {app.notifications}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
