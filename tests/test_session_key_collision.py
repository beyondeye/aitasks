"""Regression: default-session name collision must not confuse repos (t1099).

`_read_default_session` falls back to the literal `"aitasks"` for any registered
repo without a `tmux.default_session`, so `discover_aitasks_sessions(
include_registered=True)` can emit several entries that share
`session="aitasks"`. The registry-inclusive consumers (stats TUI, TUI switcher)
and the shared ring/group helpers must key *identity* on the unique
`project_root` key — not the tmux session name — so colliding repos stay
distinguishable (distinct cache entries, distinct rows, unambiguous cycling),
while labels are chosen per surface.

Run: python3 tests/test_session_key_collision.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = REPO_ROOT / ".aitask-scripts"
for _p in (_SCRIPTS, _SCRIPTS / "lib", _SCRIPTS / "stats", _SCRIPTS / "board"):
    sys.path.insert(0, str(_p))

import agent_launch_utils as alu  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    AitasksSession,
    CrossGroupRingEntry,
    cross_group_ring,
    cross_group_step,
    disambiguate_labels,
    resolve_selected_key,
)


def _sess(session, root, project_name, *, group=None, is_live=True):
    return AitasksSession(
        session=session,
        project_root=Path(root),
        project_name=project_name,
        is_live=is_live,
        project_group=group,
    )


# The exact bug shape: two registered repos, both `session="aitasks"`, distinct
# roots / project names.
REPO_A = _sess("aitasks", "/repos/repoA", "repoA")
REPO_B = _sess("aitasks", "/repos/repoB", "repoB", is_live=False)


class IdentityKeyTests(unittest.TestCase):
    def test_key_is_unique_despite_shared_session(self):
        self.assertEqual(REPO_A.session, REPO_B.session)
        self.assertNotEqual(REPO_A.key, REPO_B.key)
        self.assertEqual(REPO_A.key, "/repos/repoA")

    def test_cross_group_ring_and_step_reach_both(self):
        ring = cross_group_ring([REPO_A, REPO_B])
        self.assertEqual({e.key for e in ring}, {REPO_A.key, REPO_B.key})
        # Stepping from each key reaches the OTHER (would be impossible if the
        # step matched on the shared session name).
        step_from_a = cross_group_step(ring, REPO_A.key, +1)
        step_from_b = cross_group_step(ring, REPO_B.key, +1)
        self.assertEqual(step_from_a.key, REPO_B.key)
        self.assertEqual(step_from_b.key, REPO_A.key)


class DisambiguateLabelsTests(unittest.TestCase):
    def test_unique_primaries_pass_through_verbatim(self):
        # "render as before" — no suffix when the primary is unique.
        out = disambiguate_labels(["alpha", "beta"], ["x", "y"], ["/a", "/b"])
        self.assertEqual(out, ["alpha", "beta"])

    def test_repeated_primary_gets_secondary(self):
        out = disambiguate_labels(
            ["aitasks", "aitasks"], ["repoA", "repoB"], ["/a", "/b"]
        )
        self.assertEqual(out, ["aitasks (repoA)", "aitasks (repoB)"])

    def test_primary_and_secondary_collision_escalates_to_fallback(self):
        # Both session AND project name clash -> escalate to the unique root.
        out = disambiguate_labels(
            ["aitasks", "aitasks"], ["dup", "dup"], ["~/x/a", "~/x/b"]
        )
        self.assertEqual(out, ["aitasks (~/x/a)", "aitasks (~/x/b)"])
        self.assertEqual(len(set(out)), 2, "labels must be globally unique")


class ResolveSelectedKeyTests(unittest.TestCase):
    def test_cwd_context_disambiguates_collision(self):
        # cwd walks up to repoB -> select repoB even though the name matches both.
        with patch.object(alu, "_walk_up_to_aitasks",
                          return_value=Path("/repos/repoB")):
            key = resolve_selected_key(
                [REPO_A, REPO_B],
                provisional_session="aitasks",
                cwd=Path("/repos/repoB/sub"),
            )
        self.assertEqual(key, REPO_B.key)

    def test_no_cwd_prefers_live_match(self):
        with patch.object(alu, "_walk_up_to_aitasks", return_value=None):
            key = resolve_selected_key(
                [REPO_B, REPO_A], provisional_session="aitasks", cwd=None
            )
        self.assertEqual(key, REPO_A.key, "prefer the live entry on a name match")

    def test_returns_none_when_nothing_matches(self):
        with patch.object(alu, "_walk_up_to_aitasks", return_value=None):
            self.assertIsNone(
                resolve_selected_key(
                    [REPO_A, REPO_B], provisional_session="other", cwd=None
                )
            )


class SwitcherCollisionTests(unittest.TestCase):
    def _overlay(self, **kw):
        import tui_switcher as ts
        return ts.TuiSwitcherOverlay(**kw)

    def test_initial_selection_uses_cwd_context(self):
        ov = self._overlay(session="aitasks")
        with patch.object(alu, "_walk_up_to_aitasks",
                          return_value=Path("/repos/repoB")):
            ov._init_multi_state([REPO_A, REPO_B])
        self.assertEqual(ov._selected_key, REPO_B.key)
        self.assertEqual(ov._selected_project_root(), Path("/repos/repoB"))
        # The derived operating session name is still the tmux label.
        self.assertEqual(ov._session, "aitasks")

    def test_preselection_prefers_live_match(self):
        # monitor/minimonitor preselect the focused live session by name; cwd
        # is irrelevant. Live REPO_A must win over synthesized REPO_B.
        ov = self._overlay(session="aitasks", selected_session="aitasks")
        with patch.object(alu, "_walk_up_to_aitasks",
                          return_value=Path("/repos/repoB")):
            ov._init_multi_state([REPO_B, REPO_A])
        self.assertEqual(ov._selected_key, REPO_A.key)
        self.assertEqual(ov._selected_project_root(), Path("/repos/repoA"))

    def test_cycling_reaches_both_and_routes_correct_root(self):
        ov = self._overlay(session="aitasks")
        with patch.object(alu, "_walk_up_to_aitasks",
                          return_value=Path("/repos/repoA")):
            ov._init_multi_state([REPO_A, REPO_B])
        # Simulate a left/right step through the cross-group ring.
        ring = cross_group_ring(ov._all_sessions)
        target = cross_group_step(ring, ov._selected_key, +1)
        ov._selected_key = target.key
        self.assertEqual(ov._selected_key, REPO_B.key)
        self.assertEqual(ov._selected_project_root(), Path("/repos/repoB"))

    def test_session_row_labels_are_distinguishable(self):
        # The switcher builds its row via disambiguate_labels(session, project,
        # root) — session-name-primary with a compact disambiguator on collision.
        members = [REPO_A, REPO_B]
        labels = disambiguate_labels(
            [s.session for s in members],
            [s.project_name for s in members],
            [str(s.project_root) for s in members],
        )
        self.assertEqual(labels, ["aitasks (repoA)", "aitasks (repoB)"])

    def test_unique_session_renders_bare_name(self):
        members = [_sess("alpha", "/r/a", "a"), _sess("beta", "/r/b", "b")]
        labels = disambiguate_labels(
            [s.session for s in members],
            [s.project_name for s in members],
            [str(s.project_root) for s in members],
        )
        self.assertEqual(labels, ["alpha", "beta"])


class StatsCollisionTests(unittest.TestCase):
    def _app(self, sessions):
        import stats_app as sa
        with patch.object(sa, "discover_aitasks_sessions", return_value=[]):
            app = sa.StatsApp()
        app.sessions = sessions
        app.multi_session = True
        app._session_cache = {}
        app._labels = app._build_labels()
        return sa, app

    def test_cache_keyed_per_root_no_bleed(self):
        sa, app = self._app([REPO_A, REPO_B])
        with patch.object(sa, "collect_stats",
                          side_effect=lambda *a, **k: MagicMock()):
            data_a = app._stats_for(REPO_A)
            data_b = app._stats_for(REPO_B)
        self.assertIsNot(data_a, data_b, "no cache bleed between colliding repos")
        self.assertEqual(set(app._session_cache), {REPO_A.key, REPO_B.key})

    def test_ring_reaches_both_and_aggregate(self):
        sa, app = self._app([REPO_A, REPO_B])
        ring = app._session_ring()
        self.assertEqual(ring, [REPO_A.key, REPO_B.key, sa.ALL_SESSIONS_KEY])

    def test_labels_are_project_oriented_not_composite(self):
        _sa, app = self._app([REPO_A, REPO_B])
        # Distinct project names -> bare project name, NOT "session (project)".
        self.assertEqual(app._session_key_to_label(REPO_A.key), "repoA")
        self.assertEqual(app._session_key_to_label(REPO_B.key), "repoB")
        self.assertNotIn("aitasks", app._session_key_to_label(REPO_A.key))

    def test_project_name_collision_is_disambiguated(self):
        dup_a = _sess("aitasks", "/repos/x/proj", "proj")
        dup_b = _sess("aitasks", "/repos/y/proj", "proj", is_live=False)
        _sa, app = self._app([dup_a, dup_b])
        la = app._session_key_to_label(dup_a.key)
        lb = app._session_key_to_label(dup_b.key)
        self.assertNotEqual(la, lb, "same project name must still disambiguate")

    def test_aggregate_label_is_project_oriented(self):
        sa, app = self._app([REPO_A, REPO_B])
        self.assertEqual(
            app._session_key_to_label(sa.ALL_SESSIONS_KEY),
            "All projects (aggregate)",
        )

    def test_default_selection_uses_cwd_then_aggregate(self):
        sa, app = self._app([REPO_A, REPO_B])
        import os
        # cwd under repoB -> select repoB.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TMUX", None)
            with patch.object(alu, "_walk_up_to_aitasks",
                              return_value=Path("/repos/repoB")):
                self.assertEqual(app._default_key_selection(), REPO_B.key)
            # cwd outside any repo (helper -> None) -> aggregate, NOT first repo.
            with patch.object(alu, "_walk_up_to_aitasks", return_value=None):
                self.assertEqual(
                    app._default_key_selection(), sa.ALL_SESSIONS_KEY
                )


if __name__ == "__main__":
    unittest.main()
