"""Tests for ``apply_detailer_output`` (t741).

Covers the engine-side apply flow for the detailer role: parsing the
single delimited DETAILED_PLAN block, writing it to
``br_plans/<node>_plan.md``, setting ``plan_file`` on the target node, and
flipping the detail operation group Completed. Unlike explorer/synthesizer/
patcher, the detailer ENRICHES an existing node — it creates no node and
leaves ``current_head`` / ``next_node_id`` untouched.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PLANS_DIR,
    PROPOSALS_DIR,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    GROUPS_FILE,
    _detailer_needs_apply,
    apply_detailer_output,
)


PLAN_BODY = (
    "# Implementation Plan\n"
    "<!-- section: prerequisites -->\n"
    "### Prerequisites\n"
    "- Python 3.11\n"
    "<!-- /section: prerequisites -->\n"
)


def _build_detailer_output(plan_text: str = PLAN_BODY) -> str:
    return (
        "--- DETAILED_PLAN_START ---\n"
        f"{plan_text}"
        "--- DETAILED_PLAN_END ---\n"
    )


def _seed_session(wt: Path, *, output_text=None,
                  target_node_id="n000_init",
                  agent_name="detailer_001",
                  create_target=True,
                  initial_head="n000_init",
                  initial_next_id=5,
                  groups=None) -> None:
    """Create a minimal crew worktree with the target node + graph state,
    plus the detailer's _output.md if ``output_text`` is given.
    """
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PLANS_DIR).mkdir(parents=True, exist_ok=True)

    if create_target:
        target_node = {
            "node_id": target_node_id,
            "parents": [],
            "description": "Target node",
            "proposal_file": f"{PROPOSALS_DIR}/{target_node_id}.md",
            "created_at": "2026-01-01 00:00",
            "created_by_group": "bootstrap",
        }
        (wt / NODES_DIR / f"{target_node_id}.yaml").write_text(
            yaml.safe_dump(target_node), encoding="utf-8"
        )

    (wt / GRAPH_STATE_FILE).write_text(
        yaml.safe_dump({
            "current_head": initial_head,
            "history": [initial_head],
            "next_node_id": initial_next_id,
            "active_dimensions": [],
        }),
        encoding="utf-8",
    )
    if groups is not None:
        (wt / GROUPS_FILE).write_text(
            yaml.safe_dump({"groups": groups}), encoding="utf-8"
        )
    if output_text is not None:
        (wt / f"{agent_name}_output.md").write_text(
            output_text, encoding="utf-8"
        )


def _apply(wt: Path, *, agent_name="detailer_001",
           target_node_id="n000_init", task_num="42"):
    with patch(
        "brainstorm.brainstorm_session.crew_worktree",
        return_value=wt,
    ):
        return apply_detailer_output(task_num, agent_name, target_node_id)


class ApplyDetailerHappyPathTests(unittest.TestCase):
    def test_writes_plan_and_sets_plan_file(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_detailer_output())

            plan_rel = _apply(wt)

            self.assertEqual(plan_rel, f"{PLANS_DIR}/n000_init_plan.md")
            plan_path = wt / PLANS_DIR / "n000_init_plan.md"
            self.assertTrue(plan_path.is_file())

            node_data = yaml.safe_load(
                (wt / NODES_DIR / "n000_init.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(node_data["plan_file"],
                             f"{PLANS_DIR}/n000_init_plan.md")

    def test_section_markers_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_detailer_output())

            _apply(wt)

            plan = (wt / PLANS_DIR / "n000_init_plan.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("<!-- section: prerequisites -->", plan)
            self.assertIn("<!-- /section: prerequisites -->", plan)
            self.assertIn("# Implementation Plan", plan)

    def test_graph_state_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_detailer_output(),
                          initial_head="n000_init", initial_next_id=5)

            _apply(wt)

            gs = yaml.safe_load(
                (wt / GRAPH_STATE_FILE).read_text(encoding="utf-8")
            )
            # The detailer enriches an existing node — no head advance,
            # no node-id consumption.
            self.assertEqual(gs["current_head"], "n000_init")
            self.assertEqual(gs["next_node_id"], 5)
            self.assertEqual(gs["history"], ["n000_init"])

    def test_no_new_node_created(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_detailer_output())

            _apply(wt)

            node_files = sorted(
                p.name for p in (wt / NODES_DIR).iterdir()
                if p.suffix == ".yaml"
            )
            self.assertEqual(node_files, ["n000_init.yaml"])

    def test_redetail_overwrites_plan(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_detailer_output())
            _apply(wt)

            # A second detailer on the same node, different content.
            new_body = "# Revised Plan\nNew steps.\n"
            (wt / "detailer_002_output.md").write_text(
                _build_detailer_output(new_body), encoding="utf-8"
            )
            plan_rel = _apply(wt, agent_name="detailer_002")

            self.assertEqual(plan_rel, f"{PLANS_DIR}/n000_init_plan.md")
            plan = (wt / PLANS_DIR / "n000_init_plan.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("# Revised Plan", plan)
            self.assertNotIn("# Implementation Plan", plan)

    def test_operation_group_flipped_completed(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(
                wt,
                output_text=_build_detailer_output(),
                groups={
                    "detail_001": {
                        "operation": "detail",
                        "agents": [],
                        "status": "Waiting",
                        "created_at": "2026-01-01 00:00",
                        "head_at_creation": "n000_init",
                        "nodes_created": [],
                    }
                },
            )

            _apply(wt)

            data = yaml.safe_load(
                (wt / GROUPS_FILE).read_text(encoding="utf-8")
            )
            grp = data["groups"]["detail_001"]
            self.assertEqual(grp["status"], "Completed")
            self.assertEqual(grp["agents"], ["detailer_001"])
            # No new node — nodes_created stays empty.
            self.assertEqual(grp["nodes_created"], [])


class ApplyDetailerErrorTests(unittest.TestCase):
    def test_missing_output_raises_filenotfound(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=None)
            with self.assertRaises(FileNotFoundError):
                _apply(wt)
            # No error log — the missing-output check precedes the try block.
            self.assertFalse((wt / "detailer_001_apply_error.log").exists())

    def test_missing_delimiter_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            broken = _build_detailer_output().replace(
                "--- DETAILED_PLAN_END ---", ""
            )
            _seed_session(wt, output_text=broken)
            with self.assertRaises(ValueError):
                _apply(wt)
            self.assertTrue(
                (wt / "detailer_001_apply_error.log").is_file()
            )

    def test_empty_plan_block_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_detailer_output("\n\n"))
            with self.assertRaises(ValueError) as ctx:
                _apply(wt)
            self.assertIn("empty", str(ctx.exception))
            self.assertTrue(
                (wt / "detailer_001_apply_error.log").is_file()
            )

    def test_missing_target_node_raises_filenotfound(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_detailer_output(),
                          create_target=False)
            with self.assertRaises(FileNotFoundError) as ctx:
                _apply(wt)
            self.assertIn("target node", str(ctx.exception))
            # Missing target is checked inside the try block — log written.
            self.assertTrue(
                (wt / "detailer_001_apply_error.log").is_file()
            )


class DetailerNeedsApplyTests(unittest.TestCase):
    def _gate(self, output_text, *, agent_name="detailer_001",
              target_node_id="n000_init", plan_on_disk=None) -> bool:
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=output_text,
                          agent_name=agent_name,
                          target_node_id=target_node_id)
            if plan_on_disk is not None:
                (wt / PLANS_DIR / f"{target_node_id}_plan.md").write_text(
                    plan_on_disk, encoding="utf-8"
                )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree",
                return_value=wt,
            ):
                return _detailer_needs_apply("42", agent_name, target_node_id)

    def test_returns_false_when_output_missing(self):
        self.assertFalse(self._gate(None))

    def test_returns_false_when_no_delimiters(self):
        # The registration-time placeholder _output.md has no delimiters.
        self.assertFalse(self._gate("placeholder — agent not run yet\n"))

    def test_returns_false_when_only_some_delimiters_present(self):
        partial = "--- DETAILED_PLAN_START ---\nx\n"
        self.assertFalse(self._gate(partial))

    def test_returns_true_when_full_output_and_no_plan_on_disk(self):
        self.assertTrue(self._gate(_build_detailer_output()))

    def test_returns_false_when_plan_on_disk_matches(self):
        # Plan body as it would be written by a prior apply (delimiters
        # stripped, trailing newline trimmed by _extract_block).
        self.assertFalse(
            self._gate(_build_detailer_output(), plan_on_disk=PLAN_BODY.strip("\n"))
        )

    def test_returns_true_when_plan_on_disk_differs(self):
        # Re-detail: a newer output whose body differs from the on-disk plan.
        self.assertTrue(
            self._gate(_build_detailer_output("# Newer plan\n"),
                       plan_on_disk=PLAN_BODY.strip("\n"))
        )


if __name__ == "__main__":
    unittest.main()
