"""Pure unit tests for the board's by-topic (group-by-anchor) core (t1016_4).

`group_tasks_by_topic` / `topic_key` are the import-testable heart of the
board's by-topic view: they bucket tasks by their topic key (anchor, else a
child's parent-topic fallback, else own id) into per-anchor lanes, collapsing
singletons into a trailing "Ungrouped" lane. No widgets are involved.

Also covers the scalar `anchor` normalization added to
`task_yaml.parse_frontmatter` (mirrors the list normalization for depends /
children_to_implement).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_topic_group.py -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))


class TopicGroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from aitask_board import (  # noqa: E402
            Task, group_tasks_by_topic, topic_key, task_own_id, task_anchor_id,
        )
        cls.Task = Task
        cls.group_tasks_by_topic = staticmethod(group_tasks_by_topic)
        cls.topic_key = staticmethod(topic_key)
        cls.task_own_id = staticmethod(task_own_id)
        cls.task_anchor_id = staticmethod(task_anchor_id)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _mk(self, filename, anchor=None, updated=None):
        fm = "---\n"
        if anchor is not None:
            fm += f"anchor: {anchor}\n"
        if updated is not None:
            fm += f"updated_at: {updated}\n"
        fm += "priority: medium\nstatus: Ready\n---\nbody"
        return self.Task.from_text(Path(filename), fm)

    def _labels(self, lanes):
        return [label for label, _ in lanes]

    def _members(self, lanes, label):
        for lbl, members in lanes:
            if lbl == label:
                return [m.filename for m in members]
        return None

    def test_root_followups_and_inherited_children_cluster(self):
        """A root + its --followup-of followups + an inherited child (carrying
        anchor: <root>) all land in one lane keyed by the root id."""
        root = self._mk("t130_root_topic.md")
        f1 = self._mk("t150_followup_one.md", anchor=130)
        f2 = self._mk("t160_followup_two.md", anchor=130)
        child = self._mk("t130_2_inherited_child.md", anchor=130)

        lanes = self.group_tasks_by_topic([root, f1, f2, child])

        self.assertEqual(len(lanes), 1, "all four share one topic lane")
        label, members = lanes[0]
        self.assertTrue(label.startswith("t130 "),
                        f"lane label should carry root id+title, got {label!r}")
        self.assertEqual(
            sorted(m.filename for m in members),
            sorted([root.filename, f1.filename, f2.filename, child.filename]),
        )

    def test_legacy_anchorless_child_groups_with_parent(self):
        """A legacy child with NO anchor line still clusters with its parent
        via the display-time parent-topic fallback (no file migration)."""
        parent = self._mk("t77_legacy_parent.md")
        legacy_child = self._mk("t77_3_legacy_child.md")  # no anchor:

        lanes = self.group_tasks_by_topic([parent, legacy_child])

        self.assertEqual(len(lanes), 1)
        label, members = lanes[0]
        self.assertTrue(label.startswith("t77 "))
        self.assertEqual(
            sorted(m.filename for m in members),
            sorted([parent.filename, legacy_child.filename]),
        )

    def test_anchorless_singleton_collapses_to_ungrouped(self):
        """A task that shares its key with nothing else lands in 'Ungrouped'."""
        solo = self._mk("t200_lonely.md")
        lanes = self.group_tasks_by_topic([solo])
        self.assertEqual(self._labels(lanes), ["Ungrouped"])
        self.assertEqual(self._members(lanes, "Ungrouped"), [solo.filename])

    def test_archived_or_absent_root_is_a_stable_lane_key(self):
        """Two followups anchored to a root that is NOT in the task set still
        form a lane keyed by the root id (label falls back, key stays stable)."""
        f1 = self._mk("t301_orphan_a.md", anchor=999)
        f2 = self._mk("t302_orphan_b.md", anchor=999)

        lanes = self.group_tasks_by_topic([f1, f2])

        self.assertEqual(len(lanes), 1)
        label, members = lanes[0]
        self.assertTrue(label.startswith("t999"),
                        f"absent root id must remain the lane key, got {label!r}")
        self.assertEqual(len(members), 2)

    def test_singletons_collapse_while_clusters_keep_their_lanes(self):
        """Mixed set: a ≥2 cluster keeps its own lane; loners go to Ungrouped,
        which is always the trailing lane."""
        root = self._mk("t130_root_topic.md")
        follow = self._mk("t150_followup.md", anchor=130)
        loner_a = self._mk("t200_lonely_a.md")
        loner_b = self._mk("t210_lonely_b.md")

        lanes = self.group_tasks_by_topic([root, follow, loner_a, loner_b])

        self.assertEqual(len(lanes), 2)
        self.assertTrue(lanes[0][0].startswith("t130 "))
        self.assertEqual(lanes[-1][0], "Ungrouped",
                         "Ungrouped must be the trailing lane")
        self.assertEqual(
            sorted(m.filename for m in lanes[-1][1]),
            sorted([loner_a.filename, loner_b.filename]),
        )

    def test_topic_lanes_ordered_most_recent_first(self):
        """Default order: the topic with the newest member sorts before older
        topics; 'Ungrouped' stays last regardless of timestamps."""
        old_root = self._mk("t10_old_root.md", updated="2026-01-01 09:00")
        old_follow = self._mk("t11_old_follow.md", anchor=10,
                               updated="2026-01-02 09:00")
        new_root = self._mk("t20_new_root.md", updated="2026-06-01 09:00")
        new_follow = self._mk("t21_new_follow.md", anchor=20,
                              updated="2026-06-02 09:00")
        loner = self._mk("t30_loner.md", updated="2026-12-01 09:00")

        lanes = self.group_tasks_by_topic(
            [old_root, old_follow, new_root, new_follow, loner])
        labels = [label for label, _ in lanes]

        self.assertTrue(labels[0].startswith("t20"),
                        f"newest topic should lead, got {labels!r}")
        self.assertTrue(labels[1].startswith("t10"))
        self.assertEqual(labels[-1], "Ungrouped",
                         "Ungrouped stays last even though its loner is newest")

    def test_topic_key_child_without_loaded_parent_uses_parent_id(self):
        """If a child's parent isn't in the set, the key is still the bare
        parent id (cluster under the parent even when it's not loaded)."""
        child = self._mk("t88_4_orphan_child.md")
        self.assertEqual(self.topic_key(child, {}), "88")

    def test_explicit_anchor_overrides_parent_fallback(self):
        """A child with its own anchor uses it, not the parent fallback."""
        child = self._mk("t88_4_child.md", anchor=500)
        self.assertEqual(self.task_anchor_id(child), "500")
        self.assertEqual(self.topic_key(child, {}), "500")


class TopicSortModeTests(unittest.TestCase):
    """Selectable lane sort modes (t1035). One fixture, four distinct orderings,
    with 'Ungrouped' pinned last in every mode.

    Fixture — three ≥2 lanes plus a loner, engineered so each mode yields a
    *different* lane order (ids listed top-first, Ungrouped excluded):

    | lane | key | members | recency  |
    |------|-----|---------|----------|
    | α    | 10  | 3       | 2026-03  |
    | γ    | 5   | 2       | 2026-05  |
    | β    | 20  | 2       | 2026-01  |

    First-seen key order (input order) is 10, 5, 20 → drives 'size' tie-breaks.
      recency (newest lane first): 5, 10, 20
      topic_id (numeric desc):     20, 10, 5
      size (most members first):   10, 5, 20   (5 before 20 = first-seen tie)
      alphabetical (label casefold): 10, 20, 5 ('t10' < 't20' < 't5')
    """

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from aitask_board import Task, group_tasks_by_topic, TOPIC_SORT_MODES  # noqa: E402
        cls.Task = Task
        cls.group_tasks_by_topic = staticmethod(group_tasks_by_topic)
        cls.MODES = TOPIC_SORT_MODES

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _mk(self, filename, anchor=None, updated=None):
        fm = "---\n"
        if anchor is not None:
            fm += f"anchor: {anchor}\n"
        if updated is not None:
            fm += f"updated_at: {updated}\n"
        fm += "priority: medium\nstatus: Ready\n---\nbody"
        return self.Task.from_text(Path(filename), fm)

    def _fixture(self):
        # Members listed so first-seen key order is 10, 5, 20.
        alpha = [
            self._mk("t10_alpha.md", updated="2026-03-01 09:00"),      # key 10
            self._mk("t10_1_a.md", updated="2026-03-01 09:00"),
            self._mk("t10_2_b.md", updated="2026-03-01 09:00"),
        ]
        gamma = [
            self._mk("t5_gamma.md", updated="2026-05-01 09:00"),       # key 5
            self._mk("t6_g.md", anchor=5, updated="2026-05-01 09:00"),
        ]
        beta = [
            self._mk("t20_beta.md", updated="2026-01-01 09:00"),       # key 20
            self._mk("t21_b.md", anchor=20, updated="2026-01-01 09:00"),
        ]
        loner = self._mk("t99_solo.md", updated="2026-12-01 09:00")
        return alpha + gamma + beta + [loner]

    def _topic_ids(self, lanes):
        """Leading topic ids of the non-Ungrouped lanes, in order."""
        ids = []
        for label, _members in lanes:
            if label == "Ungrouped":
                continue
            m = re.match(r"^t(\d+)", label)
            ids.append(m.group(1) if m else label)
        return ids

    def test_recency_default_and_explicit(self):
        tasks = self._fixture()
        default = self.group_tasks_by_topic(tasks)
        explicit = self.group_tasks_by_topic(tasks, sort_mode="recency")
        self.assertEqual(self._topic_ids(default), ["5", "10", "20"])
        self.assertEqual(self._topic_ids(explicit), ["5", "10", "20"])

    def test_topic_id_numeric_descending(self):
        lanes = self.group_tasks_by_topic(self._fixture(), sort_mode="topic_id")
        self.assertEqual(self._topic_ids(lanes), ["20", "10", "5"])

    def test_topic_id_is_numeric_not_lexical(self):
        """t9 must sort before t10 under topic_id (numeric, not string, order)."""
        r9 = self._mk("t9_root.md")
        f9 = self._mk("t9b_follow.md", anchor=9)
        r10 = self._mk("t10_root.md")
        f10 = self._mk("t10b_follow.md", anchor=10)
        lanes = self.group_tasks_by_topic([r9, f9, r10, f10], sort_mode="topic_id")
        self.assertEqual(self._topic_ids(lanes), ["10", "9"],
                         "numeric desc: 10 before 9 (lexical would give 9,10)")

    def test_size_most_members_first_stable_ties(self):
        lanes = self.group_tasks_by_topic(self._fixture(), sort_mode="size")
        # 10 (3 members) leads; 5 and 20 tie at 2 → first-seen order (5 before 20).
        self.assertEqual(self._topic_ids(lanes), ["10", "5", "20"])

    def test_alphabetical_by_label_casefold(self):
        lanes = self.group_tasks_by_topic(self._fixture(), sort_mode="alphabetical")
        self.assertEqual(self._topic_ids(lanes), ["10", "20", "5"])

    def test_unknown_mode_falls_back_to_recency(self):
        tasks = self._fixture()
        self.assertEqual(
            self.group_tasks_by_topic(tasks, sort_mode="bogus"),
            self.group_tasks_by_topic(tasks, sort_mode="recency"),
        )

    def test_ungrouped_pinned_last_in_every_mode(self):
        tasks = self._fixture()
        for mode in self.MODES:
            lanes = self.group_tasks_by_topic(tasks, sort_mode=mode)
            self.assertEqual(lanes[-1][0], "Ungrouped",
                             f"Ungrouped must be last in mode {mode!r}")


class TopicBuildCacheTests(unittest.TestCase):
    """The TaskManager caches the sort-independent lane *build* and re-sorts it
    on mode change (t1035). Invalidated by an ordered (filename, anchor)
    signature and cleared at the three object-replacement reload seams.

    TaskManager.__init__ does real disk I/O (mkdir + metadata write + repo
    glob), so construct via __new__ (per tests/test_board_inflight_view.py) and
    set only the fields the tested methods touch.
    """

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        import aitask_board as b  # noqa: E402
        cls.b = b
        cls.Task = b.Task

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def setUp(self):
        # Call-counting spy over the module-global build fn (restored in tearDown).
        self._orig_build = self.b._build_topic_lanes
        self.build_calls = {"n": 0}

        def spy(tasks):
            self.build_calls["n"] += 1
            return self._orig_build(tasks)

        self.b._build_topic_lanes = spy

    def tearDown(self):
        self.b._build_topic_lanes = self._orig_build

    def _mk(self, filename, anchor=None, updated=None):
        fm = "---\n"
        if anchor is not None:
            fm += f"anchor: {anchor}\n"
        if updated is not None:
            fm += f"updated_at: {updated}\n"
        fm += "priority: medium\nstatus: Ready\n---\nbody"
        return self.Task.from_text(Path(filename), fm)

    def _mgr(self):
        mgr = self.b.TaskManager.__new__(self.b.TaskManager)
        mgr.topic_lane_cache = None
        return mgr

    def _tasks(self):
        return [
            self._mk("t10_root.md", updated="2026-01-01 09:00"),
            self._mk("t11_follow.md", anchor=10, updated="2026-02-01 09:00"),
            self._mk("t20_root.md", updated="2026-03-01 09:00"),
            self._mk("t21_follow.md", anchor=20, updated="2026-04-01 09:00"),
        ]

    def _ids(self, lanes):
        return [re.match(r"^t(\d+)", lbl).group(1)
                for lbl, _m in lanes if lbl != "Ungrouped"]

    def test_cache_hit_on_same_signature_resorts_without_rebuild(self):
        # Recency (t10 lane newest) inverts the id order so the two modes yield
        # genuinely different orders off a single cached build.
        tasks = [
            self._mk("t10_root.md", updated="2026-09-01 09:00"),
            self._mk("t11_follow.md", anchor=10, updated="2026-09-01 09:00"),
            self._mk("t20_root.md", updated="2026-01-01 09:00"),
            self._mk("t21_follow.md", anchor=20, updated="2026-01-01 09:00"),
        ]
        mgr = self._mgr()
        rec = mgr.grouped_topic_lanes(tasks, "recency")
        tid = mgr.grouped_topic_lanes(tasks, "topic_id")
        # Built once; the second call re-sorts the cached build.
        self.assertEqual(self.build_calls["n"], 1)
        # ...yet the two orders genuinely differ (proves re-sort off the cache
        # and that the cached triples were not mutated in place).
        self.assertEqual(self._ids(rec), ["10", "20"])   # 10 newer
        self.assertEqual(self._ids(tid), ["20", "10"])   # numeric desc

    def test_rebuild_on_anchor_change(self):
        mgr = self._mgr()
        tasks = self._tasks()
        mgr.grouped_topic_lanes(tasks, "recency")
        tasks[1].metadata["anchor"] = 20  # re-key t11 from topic 10 → 20
        mgr.grouped_topic_lanes(tasks, "recency")
        self.assertEqual(self.build_calls["n"], 2)

    def test_rebuild_on_membership_change(self):
        mgr = self._mgr()
        tasks = self._tasks()
        mgr.grouped_topic_lanes(tasks, "recency")
        tasks.append(self._mk("t30_new.md", updated="2026-05-01 09:00"))
        mgr.grouped_topic_lanes(tasks, "recency")
        self.assertEqual(self.build_calls["n"], 2)

    def test_rebuild_on_input_reorder(self):
        """Same membership, different input order → signature differs → rebuild.
        Guards the first-seen order contract (a sorted signature would wrongly
        hit the cache and serve stale tie/Ungrouped order)."""
        mgr = self._mgr()
        tasks = self._tasks()
        mgr.grouped_topic_lanes(tasks, "recency")
        mgr.grouped_topic_lanes(list(reversed(tasks)), "recency")
        self.assertEqual(self.build_calls["n"], 2)

    def test_reload_task_seam_clears_cache(self):
        """Negative control: object-replacement seam must not serve a stale
        cache. reload_task takes the fast false-return path (no disk writes)."""
        mgr = self._mgr()
        mgr.task_datas = {}
        mgr.child_task_datas = {}
        mgr.topic_lane_cache = ("stale-signature", [], [])
        self.assertFalse(mgr.reload_task("nope.md"))
        self.assertIsNone(mgr.topic_lane_cache)

    def test_load_child_tasks_seam_clears_cache(self):
        """load_child_tasks rebuilds child objects → must clear the cache.
        glob is stubbed to [] to avoid coupling to the real repo tree."""
        mgr = self._mgr()
        mgr.child_task_datas = {}
        mgr.topic_lane_cache = ("stale-signature", [], [])
        orig_glob = self.b.glob.glob
        self.b.glob.glob = lambda *a, **k: []
        try:
            mgr.load_child_tasks()
        finally:
            self.b.glob.glob = orig_glob
        self.assertIsNone(mgr.topic_lane_cache)


class TopicSortModeScreenLogicTests(unittest.TestCase):
    """Selection/cursor math of the sort-order picker (t1035). Widget mounting
    is stubbed (_sync_selection) so the logic is exercised without a running
    app — the picker applies only on Confirm/Enter, never on a bare cursor move."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        import aitask_board as b  # noqa: E402
        cls.Screen = b.TopicSortModeScreen

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _screen(self, current):
        s = self.Screen(current)
        s._sync_selection = lambda: None  # avoid touching unmounted widgets
        return s

    def test_initial_selection_tracks_current_mode(self):
        s = self._screen("size")
        self.assertEqual(s._modes[s.selected], "size")

    def test_unknown_current_defaults_to_first_mode(self):
        s = self._screen("bogus")
        self.assertEqual(s._modes[s.selected], "recency")

    def test_cursor_moves_and_wraps(self):
        s = self._screen("recency")  # index 0
        s.action_cursor_up()
        self.assertEqual(s._modes[s.selected], s._modes[-1], "wraps to last")
        s.action_cursor_down()
        self.assertEqual(s._modes[s.selected], "recency", "wraps back to first")
        s.action_cursor_down()
        self.assertEqual(s._modes[s.selected], "topic_id")

    def test_select_index_sets_selection(self):
        s = self._screen("recency")
        s.select_index(2)
        self.assertEqual(s._modes[s.selected], "size")


class ScalarAnchorNormalizationTests(unittest.TestCase):
    """parse_frontmatter normalizes the scalar `anchor` like the id lists."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from task_yaml import parse_frontmatter, _normalize_task_id  # noqa: E402
        cls.parse_frontmatter = staticmethod(parse_frontmatter)
        cls._normalize_task_id = staticmethod(_normalize_task_id)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _anchor(self, raw_anchor):
        meta, _body, _order = self.parse_frontmatter(
            f"---\nanchor: {raw_anchor}\npriority: low\n---\nbody")
        return meta["anchor"]

    def test_bare_child_anchor_gets_t_prefix(self):
        self.assertEqual(self._anchor("130_2"), "t130_2")

    def test_bare_parent_anchor_stays_int(self):
        self.assertEqual(self._anchor("130"), 130)

    def test_already_prefixed_anchor_unchanged(self):
        self.assertEqual(self._anchor("t77_3"), "t77_3")

    def test_normalize_scalar_helper_edge_cases(self):
        self.assertIsNone(self._normalize_task_id(None))
        self.assertEqual(self._normalize_task_id(""), "")
        self.assertEqual(self._normalize_task_id("42_5"), "t42_5")
        self.assertEqual(self._normalize_task_id(42), 42)
        self.assertEqual(self._normalize_task_id("t42_5"), "t42_5")

    def test_absent_anchor_not_injected(self):
        meta, _body, _order = self.parse_frontmatter(
            "---\npriority: low\n---\nbody")
        self.assertNotIn("anchor", meta)


if __name__ == "__main__":
    unittest.main()
