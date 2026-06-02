"""Unit / contract tests for the brainstorm ``module_sync`` op (t756_4).

Covers the correctness surfaces in the t756_4 plan's Verification section:

  A. Refuse guard — ``register_module_syncer`` refuses a module with no
     ``module_tasks`` entry (free-form context is ``patch``'s job).
  B. Input bundling — register assembles the three Sync Sources streams
     (linked-task plan / scoped diff / explain-context) with the scan helpers
     stubbed (the deeper live-bundling integration is owned by the after-test
     mitigation ``module_sync_apply_contract_tests``).
  C. Apply — ``apply_module_syncer_output`` advances the module's *own* HEAD
     (single parent = prior HEAD), leaves the umbrella HEAD untouched, and
     stamps ``last_synced_at[module]``.
  D. Needs-apply lifecycle — the pure gate the Textual poller relies on.
  E. Group/agent name round-trip — regression guard for the ``_group_seq``
     last-underscore fix that the module ops depend on.
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

from brainstorm.brainstorm_crew import (  # noqa: E402
    _group_seq,
    register_module_syncer,
)
from brainstorm.brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    _read_graph_state,
    create_node,
    get_head,
    read_node,
    set_head,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    _agent_to_group_name,
    _module_syncer_needs_apply,
    apply_module_syncer_output,
    record_operation,
)

TASK = "756"


def _seed_base(wt: Path, module_tasks=None, last_synced=None) -> None:
    """Seed a worktree with an umbrella root + a 'parser' module subgraph."""
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / GRAPH_STATE_FILE).write_text(
        yaml.safe_dump({
            "current_head": None,
            "current_heads": {},
            "history": {},
            "next_node_id": 1,
            "active_dimensions": [],
            "module_tasks": module_tasks or {},
            "last_synced_at": last_synced or {},
        }),
        encoding="utf-8",
    )
    create_node(
        wt, "n000_init", [], "Umbrella", {"component_core": "Core"},
        "## Overview\nUmbrella\n", "bootstrap",
    )
    set_head(wt, "n000_init")
    create_node(
        wt, "n001_parser", ["n000_init"], "Parser root",
        {"component_parser": "Parser"}, "## Overview\nParser\n",
        "module_decompose_001", module_label="parser",
    )
    set_head(wt, "n001_parser", module="parser")


def _sync_output(node_id: str) -> str:
    return f"""--- NODE_YAML_START ---
node_id: {node_id}
parents: []
description: "Synced parser to as-built"
proposal_file: br_proposals/{node_id}.md
created_at: "2026-06-02 12:00"
component_parser: "Parser as implemented"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
## Overview
Refreshed parser proposal reflecting the landed task.
--- PROPOSAL_END ---
"""


class RefuseGuardTests(unittest.TestCase):
    def test_refuses_module_without_linked_task(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt, module_tasks={})  # no linkage
            with self.assertRaisesRegex(ValueError, "requires a linked task"):
                register_module_syncer(wt, "crew-756", "parser", "module_sync_001")


class InputBundlingTests(unittest.TestCase):
    def test_register_bundles_three_streams(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(
                wt,
                module_tasks={"parser": "756_8"},
                last_synced={"parser": "2026-06-01 09:00"},
            )
            captured = {}

            def _capture_input(session_dir, agent_name, content):
                captured["agent"] = agent_name
                captured["content"] = content

            with patch("brainstorm.brainstorm_crew._run_addwork"), \
                 patch("brainstorm.brainstorm_crew._write_agent_input", _capture_input), \
                 patch("brainstorm.brainstorm_crew._resolve_linked_plan_path", return_value=None), \
                 patch("brainstorm.brainstorm_crew._sync_touched_files", return_value=["a.py"]) as touched, \
                 patch("brainstorm.brainstorm_crew._sync_scoped_diff", return_value="DIFFBODY"), \
                 patch("brainstorm.brainstorm_crew._sync_explain_context", return_value="EXPLAINBODY"):
                agent = register_module_syncer(
                    wt, "crew-756", "parser", "module_sync_001",
                    instructions="focus on the cache path",
                )

            # Agent name round-trips back to the group (poller contract).
            self.assertEqual(agent, "module_syncer_001")
            self.assertEqual(_agent_to_group_name(agent), "module_sync_001")
            # Scan horizon is the module's last_synced_at.
            self.assertEqual(touched.call_args.args, ("756_8", "2026-06-01 09:00"))
            body = captured["content"]
            self.assertIn("## Sync Sources", body)
            self.assertIn("t756_8", body)
            self.assertIn("DIFFBODY", body)
            self.assertIn("EXPLAINBODY", body)
            self.assertIn("focus on the cache path", body)


class ApplyTests(unittest.TestCase):
    def test_apply_advances_module_head_single_parent_and_stamps_synced(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt, module_tasks={"parser": "756_8"})
            (wt / "module_syncer_001_output.md").write_text(
                _sync_output("n002_module_syncer_001"), encoding="utf-8"
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                record_operation(
                    TASK, "module_sync_001", "module_sync",
                    ["module_syncer_001"], "n001_parser",
                    subgraph="parser",
                )
                self.assertTrue(
                    _module_syncer_needs_apply(TASK, "module_syncer_001")
                )
                new_id = apply_module_syncer_output(TASK, "module_syncer_001")

            node = read_node(wt, new_id)
            self.assertEqual(node["parents"], ["n001_parser"])  # single parent
            self.assertEqual(node["module_label"], "parser")
            self.assertEqual(get_head(wt, module="parser"), new_id)
            self.assertEqual(get_head(wt), "n000_init")  # umbrella untouched
            synced = _read_graph_state(wt).get("last_synced_at", {})
            self.assertIn("parser", synced)
            self.assertTrue(synced["parser"])  # non-empty timestamp

    def test_needs_apply_is_false_after_apply(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt, module_tasks={"parser": "756_8"})
            (wt / "module_syncer_001_output.md").write_text(
                _sync_output("n002_module_syncer_001"), encoding="utf-8"
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                record_operation(
                    TASK, "module_sync_001", "module_sync",
                    ["module_syncer_001"], "n001_parser", subgraph="parser",
                )
                apply_module_syncer_output(TASK, "module_syncer_001")
                self.assertFalse(
                    _module_syncer_needs_apply(TASK, "module_syncer_001")
                )


class GroupSeqRoundTripTests(unittest.TestCase):
    def test_multi_token_op_names_round_trip(self):
        for op, role in (
            ("module_decompose", "module_decomposer"),
            ("module_merge", "module_merger"),
            ("module_sync", "module_syncer"),
            ("explore", "explorer"),
        ):
            group = f"{op}_001"
            agent = f"{role}_{_group_seq(group)}"
            self.assertEqual(_agent_to_group_name(agent), group)


if __name__ == "__main__":
    unittest.main()
