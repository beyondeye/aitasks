"""Tests for the brainstorm wizard step resolver (t898).

Pure-logic tests for the declarative step model backing the Actions-tab wizard:
`active_step_ids`, `step_position`, `next_step_id`, `prev_step_id`. The Textual
TUI dispatch/rendering is verified separately (existing wizard tests +
interactive). These functions take a plain ctx dict and do no I/O, so they are
testable without a running App.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import (  # noqa: E402
    active_step_ids,
    next_step_id,
    prev_step_id,
    step_position,
)


def ctx(op, node_has_sections=False):
    return {"op": op, "node_has_sections": node_has_sections}


class ActiveStepTests(unittest.TestCase):
    def test_explore_without_sections(self):
        self.assertEqual(
            active_step_ids(ctx("explore")),
            ["op_select", "node_select", "config", "confirm"],
        )

    def test_explore_with_sections(self):
        self.assertEqual(
            active_step_ids(ctx("explore", True)),
            ["op_select", "node_select", "section_select", "config", "confirm"],
        )

    def test_compare_and_synthesize_have_no_node_select(self):
        for op in ("compare", "synthesize"):
            self.assertEqual(
                active_step_ids(ctx(op)),
                ["op_select", "config", "confirm"],
            )

    def test_session_ops_jump_to_confirm(self):
        for op in ("pause", "resume", "finalize", "archive"):
            self.assertEqual(active_step_ids(ctx(op)), ["op_select", "confirm"])

    def test_delete_has_no_wizard_steps_beyond_op_select(self):
        # delete opens a modal; confirm predicate excludes it.
        self.assertEqual(active_step_ids(ctx("delete")), ["op_select"])

    def test_empty_op_is_only_op_select(self):
        # At op-select render time the op is "" — confirm must NOT be active.
        self.assertEqual(active_step_ids(ctx("")), ["op_select"])


class StepPositionTests(unittest.TestCase):
    def test_explore_with_sections_indices(self):
        c = ctx("explore", True)
        self.assertEqual(step_position(c, "op_select"), (1, 5))
        self.assertEqual(step_position(c, "node_select"), (2, 5))
        self.assertEqual(step_position(c, "section_select"), (3, 5))
        self.assertEqual(step_position(c, "config"), (4, 5))
        self.assertEqual(step_position(c, "confirm"), (5, 5))

    def test_explore_without_sections_indices(self):
        c = ctx("explore")
        self.assertEqual(step_position(c, "node_select"), (2, 4))
        self.assertEqual(step_position(c, "config"), (3, 4))
        self.assertEqual(step_position(c, "confirm"), (4, 4))

    def test_compare_config_index(self):
        c = ctx("compare")
        self.assertEqual(step_position(c, "config"), (2, 3))
        self.assertEqual(step_position(c, "confirm"), (3, 3))

    def test_session_op_confirm_is_two_of_two(self):
        self.assertEqual(step_position(ctx("pause"), "confirm"), (2, 2))

    def test_inactive_step_reports_index_zero(self):
        # node_select is not active for compare; index 0, total still correct.
        self.assertEqual(step_position(ctx("compare"), "node_select"), (0, 3))


class NextPrevTests(unittest.TestCase):
    def test_next_walks_active_list_in_order(self):
        c = ctx("explore", True)
        ids = active_step_ids(c)
        for a, b in zip(ids, ids[1:]):
            self.assertEqual(next_step_id(c, a), b)
        self.assertIsNone(next_step_id(c, ids[-1]))  # confirm -> None

    def test_prev_is_inverse_of_next(self):
        c = ctx("explore", True)
        ids = active_step_ids(c)
        for a, b in zip(ids, ids[1:]):
            self.assertEqual(prev_step_id(c, b), a)
        self.assertIsNone(prev_step_id(c, ids[0]))  # op_select -> None

    def test_compare_back_from_config_is_op_select(self):
        self.assertEqual(prev_step_id(ctx("compare"), "config"), "op_select")

    def test_dynamic_total_contract(self):
        # The key ordering rule: next() is recomputed against the CURRENT ctx.
        # Before the chosen node's sections are known, node_select -> config.
        self.assertEqual(next_step_id(ctx("explore", False), "node_select"), "config")
        # Once node_has_sections flips true (cached pre-transition by the App),
        # node_select -> section_select.
        self.assertEqual(
            next_step_id(ctx("explore", True), "node_select"), "section_select"
        )

    def test_prev_from_config_depends_on_sections(self):
        self.assertEqual(prev_step_id(ctx("explore", True), "config"), "section_select")
        self.assertEqual(prev_step_id(ctx("explore", False), "config"), "node_select")

    def test_unknown_step_id_returns_none(self):
        self.assertIsNone(next_step_id(ctx("explore"), "nope"))
        self.assertIsNone(prev_step_id(ctx("explore"), "nope"))


class SubgraphSelectStepTests(unittest.TestCase):
    """The optional module subgraph-selector row (t756_2)."""

    def _ctx(self, op, subgraph_count=1, node_has_sections=False):
        return {
            "op": op,
            "node_has_sections": node_has_sections,
            "subgraph_count": subgraph_count,
        }

    def test_inactive_with_single_subgraph(self):
        # Default count of 1 (or absent) keeps the pre-module shape exactly.
        self.assertEqual(
            active_step_ids(self._ctx("explore", subgraph_count=1)),
            ["op_select", "node_select", "config", "confirm"],
        )
        self.assertNotIn("subgraph_select", active_step_ids(ctx("explore")))

    def test_active_for_node_select_ops_with_multi_subgraph(self):
        self.assertEqual(
            active_step_ids(self._ctx("explore", subgraph_count=2)),
            ["op_select", "subgraph_select", "node_select", "config", "confirm"],
        )

    def test_inactive_for_non_node_select_ops(self):
        # compare/synthesize never get a selector (no base-node step).
        self.assertEqual(
            active_step_ids(self._ctx("compare", subgraph_count=3)),
            ["op_select", "config", "confirm"],
        )

    def test_op_select_routing_and_back(self):
        multi = self._ctx("explore", subgraph_count=2)
        single = self._ctx("explore", subgraph_count=1)
        self.assertEqual(next_step_id(multi, "op_select"), "subgraph_select")
        self.assertEqual(next_step_id(single, "op_select"), "node_select")
        self.assertEqual(next_step_id(multi, "subgraph_select"), "node_select")
        # Back from node-select returns to the selector when it is active.
        self.assertEqual(prev_step_id(multi, "node_select"), "subgraph_select")
        self.assertEqual(prev_step_id(single, "node_select"), "op_select")


class ModuleDecomposeNodeSelectTests(unittest.TestCase):
    """module_decompose gains a source-node-select step (t945_3).

    It reuses the node_select step (so the user can pick a source node,
    defaulting to HEAD) but must NOT trigger section_select — that stays gated
    on the narrower _NODE_SELECT_OPS.
    """

    def _ctx(self, subgraph_count=1, node_has_sections=False):
        return {
            "op": "module_decompose",
            "node_has_sections": node_has_sections,
            "subgraph_count": subgraph_count,
        }

    def test_single_subgraph_has_node_select_then_config(self):
        self.assertEqual(
            active_step_ids(self._ctx(subgraph_count=1)),
            ["op_select", "node_select", "config", "confirm"],
        )

    def test_multi_subgraph_has_subgraph_then_node_select(self):
        self.assertEqual(
            active_step_ids(self._ctx(subgraph_count=2)),
            ["op_select", "subgraph_select", "node_select", "config", "confirm"],
        )

    def test_section_select_never_active_even_with_sections(self):
        # Unlike explore, decompose must skip section_select.
        self.assertNotIn(
            "section_select",
            active_step_ids(self._ctx(subgraph_count=2, node_has_sections=True)),
        )

    def test_node_select_routes_to_config(self):
        single = self._ctx(subgraph_count=1)
        multi = self._ctx(subgraph_count=2)
        self.assertEqual(next_step_id(single, "op_select"), "node_select")
        self.assertEqual(next_step_id(multi, "subgraph_select"), "node_select")
        # node_select -> config even when sections are present (no section_select).
        self.assertEqual(
            next_step_id(self._ctx(node_has_sections=True), "node_select"), "config"
        )


class PreSeededNodeTests(unittest.TestCase):
    """Contextual-launch seeding drops the node_select step (t983_6).

    When an op is launched from the Operations dialog / Node Hub the node (or
    marked set) is already known, so the launch sets ``pre_seeded_node`` and the
    in-wizard node-pick step must disappear from the active set. The step is
    kept (gated) — not deleted — so the non-seeded op-select flow is unchanged
    (the rest of this file is the regression guard for that).
    """

    def _ctx(self, op, pre_seeded_node, subgraph_count=1, node_has_sections=False):
        return {
            "op": op,
            "node_has_sections": node_has_sections,
            "subgraph_count": subgraph_count,
            "pre_seeded_node": pre_seeded_node,
        }

    def test_explore_seeded_omits_node_select(self):
        seeded = self._ctx("explore", pre_seeded_node=True)
        self.assertEqual(
            active_step_ids(seeded), ["op_select", "config", "confirm"]
        )
        # one fewer step than the non-seeded explore flow
        self.assertEqual(step_position(seeded, "config"), (2, 3))
        self.assertEqual(
            active_step_ids(self._ctx("explore", pre_seeded_node=False)),
            ["op_select", "node_select", "config", "confirm"],
        )

    def test_explore_seeded_with_sections_still_omits_node_select(self):
        seeded = self._ctx("explore", pre_seeded_node=True, node_has_sections=True)
        self.assertEqual(
            active_step_ids(seeded),
            ["op_select", "section_select", "config", "confirm"],
        )
        self.assertEqual(next_step_id(seeded, "op_select"), "section_select")

    def test_module_decompose_seeded_omits_node_select(self):
        seeded = self._ctx("module_decompose", pre_seeded_node=True)
        self.assertEqual(
            active_step_ids(seeded), ["op_select", "config", "confirm"]
        )
        # multi-subgraph: subgraph_select stays, node_select still gone
        seeded_multi = self._ctx(
            "module_decompose", pre_seeded_node=True, subgraph_count=2
        )
        self.assertEqual(
            active_step_ids(seeded_multi),
            ["op_select", "subgraph_select", "config", "confirm"],
        )

    def test_seed_flag_is_noop_for_ops_without_node_select(self):
        # compare/synthesize never had a node_select step; the flag changes
        # nothing for them.
        for op in ("compare", "synthesize"):
            self.assertEqual(
                active_step_ids(self._ctx(op, pre_seeded_node=True)),
                ["op_select", "config", "confirm"],
            )

    def test_missing_flag_defaults_to_node_select_present(self):
        # A ctx without the key at all (legacy callers) keeps node_select.
        self.assertIn("node_select", active_step_ids(ctx("explore")))


if __name__ == "__main__":
    unittest.main()
