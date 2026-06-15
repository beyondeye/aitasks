"""Tests for the brainstorm NodeSelection model (t983_2).

Pure-logic tests for the headless selection model backing the Browse-tab IA
redesign (parent t983): a `primary` cursor plus a `marked` set, with
`cardinality` (what the Operations dialog greys ops by) and `effective()` (the
concrete target set). The model does no I/O and imports no Textual, so it is
testable without a running App — same style as test_brainstorm_wizard_steps.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import NodeSelection  # noqa: E402


class ConstructorTests(unittest.TestCase):
    def test_defaults_empty(self):
        sel = NodeSelection()
        self.assertIsNone(sel.primary)
        self.assertEqual(sel.marked, set())
        self.assertEqual(sel.cardinality, 0)
        self.assertEqual(sel.effective(), set())

    def test_seeded_values(self):
        sel = NodeSelection(primary="a", marked={"b", "c"})
        self.assertEqual(sel.primary, "a")
        self.assertEqual(sel.marked, {"b", "c"})

    def test_seeded_marked_is_copied(self):
        # Mutating the model must not mutate the caller's set, and vice versa.
        src = {"b", "c"}
        sel = NodeSelection(marked=src)
        sel.mark("d")
        self.assertEqual(src, {"b", "c"})
        self.assertEqual(sel.marked, {"b", "c", "d"})


class CardinalityTests(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(NodeSelection().cardinality, 0)

    def test_primary_only_is_one(self):
        self.assertEqual(NodeSelection(primary="a").cardinality, 1)

    def test_single_marked_is_one(self):
        sel = NodeSelection()
        sel.mark("a")
        self.assertEqual(sel.cardinality, 1)

    def test_multi_marked_is_count(self):
        sel = NodeSelection()
        sel.mark("a")
        sel.mark("b")
        sel.mark("c")
        self.assertEqual(sel.cardinality, 3)

    def test_marked_overrides_primary(self):
        # The Operations dialog depends on this: once nodes are marked, the
        # cursor no longer contributes to the count.
        sel = NodeSelection(primary="a", marked={"b", "c"})
        self.assertEqual(sel.cardinality, 2)

    def test_primary_also_marked_stays_consistent(self):
        sel = NodeSelection(primary="a", marked={"a"})
        self.assertEqual(sel.cardinality, 1)
        self.assertEqual(sel.effective(), {"a"})


class EffectiveTests(unittest.TestCase):
    def test_empty_is_empty_set(self):
        self.assertEqual(NodeSelection().effective(), set())

    def test_primary_only_is_singleton(self):
        self.assertEqual(NodeSelection(primary="a").effective(), {"a"})

    def test_marked_present_excludes_unmarked_primary(self):
        sel = NodeSelection(primary="a", marked={"b", "c"})
        self.assertEqual(sel.effective(), {"b", "c"})

    def test_effective_returns_a_copy(self):
        sel = NodeSelection(marked={"b", "c"})
        out = sel.effective()
        out.add("z")
        self.assertEqual(sel.marked, {"b", "c"})


class MutatorTests(unittest.TestCase):
    def test_set_primary(self):
        sel = NodeSelection()
        sel.set_primary("a")
        self.assertEqual(sel.primary, "a")
        sel.set_primary(None)
        self.assertIsNone(sel.primary)

    def test_mark_is_idempotent(self):
        sel = NodeSelection()
        sel.mark("a")
        sel.mark("a")
        self.assertEqual(sel.marked, {"a"})

    def test_unmark_removes(self):
        sel = NodeSelection(marked={"a", "b"})
        sel.unmark("a")
        self.assertEqual(sel.marked, {"b"})

    def test_unmark_absent_is_noop(self):
        sel = NodeSelection(marked={"a"})
        sel.unmark("z")
        self.assertEqual(sel.marked, {"a"})

    def test_toggle_round_trip(self):
        sel = NodeSelection()
        sel.toggle("a")
        self.assertEqual(sel.marked, {"a"})
        sel.toggle("a")
        self.assertEqual(sel.marked, set())

    def test_toggle_does_not_move_primary(self):
        sel = NodeSelection(primary="a")
        sel.toggle("b")
        self.assertEqual(sel.primary, "a")
        self.assertEqual(sel.marked, {"b"})

    def test_clear_empties_marked_but_keeps_primary(self):
        sel = NodeSelection(primary="a", marked={"b", "c"})
        sel.clear()
        self.assertEqual(sel.marked, set())
        self.assertEqual(sel.primary, "a")


class RemoveTests(unittest.TestCase):
    def test_remove_primary_clears_cursor(self):
        sel = NodeSelection(primary="a", marked={"b"})
        sel.remove("a")
        self.assertIsNone(sel.primary)
        self.assertEqual(sel.marked, {"b"})

    def test_remove_marked_leaves_others_and_primary(self):
        sel = NodeSelection(primary="a", marked={"b", "c"})
        sel.remove("b")
        self.assertEqual(sel.marked, {"c"})
        self.assertEqual(sel.primary, "a")

    def test_remove_node_that_is_both_clears_both(self):
        sel = NodeSelection(primary="a", marked={"a", "b"})
        sel.remove("a")
        self.assertIsNone(sel.primary)
        self.assertEqual(sel.marked, {"b"})

    def test_remove_absent_is_noop(self):
        sel = NodeSelection(primary="a", marked={"b"})
        sel.remove("z")
        self.assertEqual(sel.primary, "a")
        self.assertEqual(sel.marked, {"b"})


if __name__ == "__main__":
    unittest.main()
