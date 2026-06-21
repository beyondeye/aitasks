"""Behavioral tests for two-axis project-group navigation (t1025_2, t1036).

Covers the wiring of the pure grouping helpers into the TUI switcher and the
stats TUI. As of t1036, ←/→ crosses group boundaries (one continuous ring over
all groups, global wrap) and keeps the selected-group axis in sync; the switcher
shows only the selected group's projects:

  * switcher ``_ensure_session_live`` preserves ``project_group`` across
    bootstrap (review concern #1 — the frozen dataclass must not be rebuilt
    field-by-field, dropping the group).
  * switcher ``_group_member_names`` lists ONLY the selected group's members;
    ``_cycle_session`` crosses boundaries and re-points the group axis (t1036).
  * switcher cross-group preselection: opening with a ``selected_session`` in
    another group defaults the group axis to THAT session's group (not the
    attached one); ←/→ crosses boundaries and ``]`` advances the group axis.
  * stats ``_session_ring`` is the cross-group walk with the ``__all__``
    aggregate layered as a fixed final member (left/right reaches it; ``[`` /
    ``]`` group cycling never does).
  * stats ``[`` / ``]`` are pane-guarded: time-window on the agents panes,
    project-group elsewhere.
  * stats group cycling re-points the selected session via the shared
    ``_apply_session_selection`` onto the new group's first member when the
    current selection isn't one of its members (t1036).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_tui_group_nav.py -v
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = REPO_ROOT / ".aitask-scripts"
for _p in (_SCRIPTS, _SCRIPTS / "lib", _SCRIPTS / "stats", _SCRIPTS / "board"):
    sys.path.insert(0, str(_p))

from agent_launch_utils import AitasksSession  # noqa: E402


def _sess(name, group, *, is_live=True, is_stale=False):
    return AitasksSession(
        session=name,
        project_root=Path("/tmp/" + name),
        project_name=name,
        is_live=is_live,
        is_stale=is_stale,
        project_group=group,
    )


class SwitcherBootstrapTests(unittest.TestCase):
    """`_ensure_session_live` must keep project_group when flipping to live."""

    def test_bootstrap_preserves_group(self):
        import tui_switcher as ts

        ov = ts.TuiSwitcherOverlay(session="sA", selected_session="sB")
        grouped = _sess("sB", "g1", is_live=False)
        ov._all_sessions = [_sess("sA", "g0"), grouped]
        ov._session = "sB"

        def fake_run(cmd, *a, **k):
            r = MagicMock()
            r.returncode = 0
            r.stdout = ""
            r.stderr = ""
            return r

        with patch.object(subprocess, "run", side_effect=fake_run):
            ok = ov._ensure_session_live()
        self.assertTrue(ok)
        live = next(s for s in ov._all_sessions if s.session == "sB")
        self.assertTrue(live.is_live)
        self.assertEqual(
            live.project_group, "g1",
            "bootstrap must not drop project_group (dataclasses.replace)",
        )


class SwitcherRingTests(unittest.TestCase):
    """`_group_member_names` lists ONLY the selected group's members (t1036)."""

    def test_member_names_are_group_scoped(self):
        import tui_switcher as ts

        ov = ts.TuiSwitcherOverlay(session="sA")
        ov._all_sessions = [
            _sess("sA", "g1"),
            _sess("sC", "g1"),
            _sess("sB", "g2"),         # live out-of-group: NOT listed
            _sess("sD", "g1", is_live=False, is_stale=True),  # stale in-group: kept
        ]
        ov._selected_group = "g1"
        self.assertEqual(ov._group_member_names(), ["sA", "sC", "sD"])


class SwitcherPilotTests(unittest.TestCase):
    """Mount the overlay in a host App and drive the two axes via keys."""

    def _run(self, coro):
        return asyncio.run(coro)

    def _fixtures(self):
        # g1: sA (attached), sC, sD(stale) ; g2: sB (preselected).
        # cross_group_ring order: [sA, sC, sD, sB] (g1 members, then g2).
        return [
            _sess("sA", "g1"),
            _sess("sC", "g1"),
            _sess("sB", "g2"),
            _sess("sD", "g1", is_live=False, is_stale=True),
        ]

    def test_cross_group_preselection_and_axes(self):
        import tui_switcher as ts
        from textual.app import App
        from textual.widgets import Static

        sessions = self._fixtures()

        class HostApp(App):
            def compose(self):
                yield Static("host")

        async def go():
            app = HostApp()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                with patch.object(
                    ts, "discover_aitasks_sessions", return_value=sessions
                ), patch.object(
                    ts, "get_tmux_windows", return_value=[]
                ), patch.object(
                    ts.TuiSwitcherOverlay, "_compute_desync_summary",
                    return_value="",
                ):
                    # Attached session sA is in group g1; preselect sB (g2).
                    overlay = ts.TuiSwitcherOverlay(
                        session="sA", current_tui="board", selected_session="sB"
                    )
                    await app.push_screen(overlay)
                    await pilot.pause()

                    # Cross-group preselection: default group follows the
                    # SELECTED session (sB -> g2), NOT the attached one (g1).
                    self.assertTrue(overlay._multi_mode)
                    self.assertEqual(overlay._selected_group, "g2")
                    # Switcher row shows ONLY the selected group's member (sB).
                    self.assertEqual(overlay._group_member_names(), ["sB"])

                    # → on sB (last member of last group g2) wraps globally to
                    # sA (first member of g1) and switches the group axis.
                    await pilot.press("right")
                    await pilot.pause()
                    self.assertEqual(overlay._session, "sA")
                    self.assertEqual(overlay._selected_group, "g1")
                    self.assertEqual(
                        overlay._group_member_names(), ["sA", "sC", "sD"]
                    )

                    # ← on sA (first member of first group g1) wraps back to
                    # sB (last member of last group g2), crossing the boundary.
                    await pilot.press("left")
                    await pilot.pause()
                    self.assertEqual(overlay._session, "sB")
                    self.assertEqual(overlay._selected_group, "g2")

                    # `]` advances the group axis g2 -> g1 and re-points the
                    # operating session onto g1's first member (sA).
                    await pilot.press("]")
                    await pilot.pause()
                    self.assertEqual(overlay._selected_group, "g1")
                    self.assertEqual(overlay._session, "sA")

        self._run(go())


class StatsRingTests(unittest.TestCase):
    """Stats ring/aggregate layering + pane-guarded `[`/`]` routing."""

    def _app(self, sessions, selected, group):
        import stats_app as sa

        with patch.object(sa, "discover_aitasks_sessions", return_value=[]):
            app = sa.StatsApp()
        app.sessions = sessions
        app.multi_session = True
        app.selected_session = selected
        app._selected_group = group
        return sa, app

    def test_aggregate_is_fixed_final_ring_member(self):
        sa, app = self._app(
            [_sess("sA", "g1"), _sess("sC", "g1"), _sess("sB", "g2")],
            "sB", "g2",
        )
        ring = app._session_ring()
        self.assertEqual(ring[-1], sa.ALL_SESSIONS_KEY)
        self.assertEqual(ring.count(sa.ALL_SESSIONS_KEY), 1)
        # Cross-group walk [sA, sC, sB] (group order, not selected-group first),
        # then the aggregate as the fixed final member (t1036).
        self.assertEqual(ring, ["sA", "sC", "sB", sa.ALL_SESSIONS_KEY])

    def test_bracket_pane_guard_routes_window_vs_group(self):
        _sa, app = self._app([_sess("sA", "g1"), _sess("sB", "g2")], "sA", "g1")
        app._cycle_window = MagicMock()
        app._cycle_group = MagicMock()

        with patch.object(app, "_current_pane_id", return_value="agents.verified"):
            app._cycle_window_or_group(+1)
        app._cycle_window.assert_called_once()
        app._cycle_group.assert_not_called()

        app._cycle_window.reset_mock()
        with patch.object(app, "_current_pane_id", return_value="agents.timeline"):
            app._cycle_window_or_group(+1)
        app._cycle_group.assert_called_once()
        app._cycle_window.assert_not_called()

    def test_group_cycle_repoints_when_selection_not_in_new_group(self):
        # Selection is not a member of the new group -> re-point to its first
        # member (t1036: `[`/`]` lands on a member of the target group).
        _sa, app = self._app(
            [_sess("sA", "g1"), _sess("sB", "g2")], "sB", "g2",
        )
        app._apply_session_selection = MagicMock()
        app._update_title = MagicMock()
        app.notify = MagicMock()
        app._cycle_group(+1)  # g2 -> g1; sB not a g1 member -> re-point to sA
        self.assertEqual(app._selected_group, "g1")
        app._apply_session_selection.assert_called_once_with("sA")
        app._update_title.assert_not_called()

    def test_cycle_session_crosses_boundary_and_syncs_group(self):
        sa, app = self._app(
            [_sess("sA", "g1"), _sess("sC", "g1"), _sess("sB", "g2")],
            "sC", "g1",
        )
        app._apply_session_selection = MagicMock()
        # → on sC (last g1 member) crosses into g2's sB; group axis follows.
        app._cycle_session(+1)
        self.assertEqual(app._selected_group, "g2")
        app._apply_session_selection.assert_called_once_with("sB")

    def test_cycle_session_onto_aggregate_keeps_group(self):
        sa, app = self._app(
            [_sess("sA", "g1"), _sess("sC", "g1"), _sess("sB", "g2")],
            "sB", "g2",
        )
        app._apply_session_selection = MagicMock()
        # → on sB (last real entry) lands on the aggregate; group is unchanged
        # (the aggregate is group-agnostic).
        app._cycle_session(+1)
        self.assertEqual(app._selected_group, "g2")
        app._apply_session_selection.assert_called_once_with(sa.ALL_SESSIONS_KEY)

    def test_group_cycle_keeps_selection_when_already_in_new_group(self):
        # Selection already belongs to the group landed on -> no re-point.
        _sa, app = self._app(
            [_sess("sA", "g1"), _sess("sB", "g1"), _sess("sC", "g2")],
            "sB", "g2",
        )
        app._apply_session_selection = MagicMock()
        app._update_title = MagicMock()
        app.notify = MagicMock()
        app._cycle_group(+1)  # g2 -> g1; sB is a g1 member -> stays
        self.assertEqual(app._selected_group, "g1")
        app._apply_session_selection.assert_not_called()
        app._update_title.assert_called_once()


if __name__ == "__main__":
    unittest.main()
