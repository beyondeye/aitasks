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
