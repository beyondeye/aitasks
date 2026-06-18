"""Behavioral tests for two-axis project-group navigation (t1025_2).

Covers the wiring of t1025_1's pure ``group_sessions`` into the TUI switcher
and the stats TUI:

  * switcher ``_ensure_session_live`` preserves ``project_group`` across
    bootstrap (review concern #1 — the frozen dataclass must not be rebuilt
    field-by-field, dropping the group).
  * switcher ``_ring_names`` cycles the SELECTED group's derived ring.
  * switcher cross-group preselection: opening with a ``selected_session`` in
    another group defaults the group axis to THAT session's group (not the
    attached one), and ``]`` advances the group axis while ←/→ stays in the ring.
  * stats ``_session_ring`` layers the ``__all__`` aggregate as a fixed final
    ring member (left/right reaches it; ``[`` / ``]`` group cycling never does).
  * stats ``[`` / ``]`` are pane-guarded: time-window on the agents panes,
    project-group elsewhere.
  * stats group cycling re-points the selected session via the shared
    ``_apply_session_selection`` only when the current selection falls out of
    the new ring.

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
    """`_ring_names` derives from the selected group, not the flat list."""

    def test_ring_is_group_scoped_with_live_out_of_group(self):
        import tui_switcher as ts

        ov = ts.TuiSwitcherOverlay(session="sA")
        ov._all_sessions = [
            _sess("sA", "g1"),
            _sess("sC", "g1"),
            _sess("sB", "g2"),
            _sess("sD", "g2", is_live=False, is_stale=True),  # stale out-of-grp
        ]
        ov._selected_group = "g1"
        # g1 members first, then live out-of-group (sB); stale sD dropped.
        self.assertEqual(ov._ring_names(), ["sA", "sC", "sB"])


class SwitcherPilotTests(unittest.TestCase):
    """Mount the overlay in a host App and drive the two axes via keys."""

    def _run(self, coro):
        return asyncio.run(coro)

    def _fixtures(self):
        # g1: sA (attached), sC, sD(stale) ; g2: sB (preselected).
        # sD is stale AND out-of-group relative to g2, so it is dropped from
        # g2's ring — proving the ring is group-scoped, not the flat list.
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
                    # Ring for g2: member sB + live out-of-group sA, sC.
                    self.assertEqual(overlay._ring_names(), ["sB", "sA", "sC"])

                    # ←/→ cycles within the ring (stays in g2's ring).
                    await pilot.press("right")
                    await pilot.pause()
                    self.assertEqual(overlay._session, "sA")
                    self.assertEqual(overlay._selected_group, "g2")

                    # `]` advances the group axis g2 -> g1 (wrap over [g1, g2]).
                    await pilot.press("]")
                    await pilot.pause()
                    self.assertEqual(overlay._selected_group, "g1")

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
        # g2 ring: member sB + live out-of-group sA, sC, then aggregate.
        self.assertEqual(ring, ["sB", "sA", "sC", sa.ALL_SESSIONS_KEY])

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

    def test_group_cycle_repoints_only_when_selection_falls_out(self):
        # Live selection stays in the ring across a group change.
        _sa, app = self._app(
            [_sess("sA", "g1"), _sess("sB", "g2")], "sB", "g2",
        )
        app._apply_session_selection = MagicMock()
        app._update_title = MagicMock()
        app.notify = MagicMock()
        app._cycle_group(+1)  # g2 -> g1; sB is live out-of-group -> stays
        self.assertEqual(app._selected_group, "g1")
        app._apply_session_selection.assert_not_called()
        app._update_title.assert_called_once()

        # A stale in-group selection is dropped from the new ring -> re-point.
        _sa, app = self._app(
            [_sess("sA", "g1"), _sess("sB", "g2", is_live=False, is_stale=True)],
            "sB", "g2",
        )
        app._apply_session_selection = MagicMock()
        app._update_title = MagicMock()
        app.notify = MagicMock()
        app._cycle_group(+1)  # g2 -> g1; stale sB out-of-group dropped
        self.assertEqual(app._selected_group, "g1")
        app._apply_session_selection.assert_called_once()
        # Re-pointed to the first ring member (sA, then aggregate appended).
        called_key = app._apply_session_selection.call_args[0][0]
        self.assertEqual(called_key, "sA")


if __name__ == "__main__":
    unittest.main()
