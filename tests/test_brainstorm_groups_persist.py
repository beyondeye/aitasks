"""Tests for record_operation / update_operation (t749_1).

Covers the br_groups.yaml persistence layer that the new operation
provenance UI depends on.
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

from brainstorm.brainstorm_session import (  # noqa: E402
    GROUPS_FILE,
    record_operation,
    update_operation,
)


def _read_groups(wt: Path) -> dict:
    p = wt / GROUPS_FILE
    if not p.is_file():
        return {}
    with p.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("groups", {}) or {}


def _seed_empty_groups(wt: Path) -> None:
    (wt / GROUPS_FILE).write_text("groups: {}\n", encoding="utf-8")


def _patch_worktree(wt: Path):
    return patch(
        "brainstorm.brainstorm_session.crew_worktree", return_value=wt,
    )


class RecordOperationTests(unittest.TestCase):
    def test_writes_full_entry(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_empty_groups(wt)
            with _patch_worktree(wt):
                record_operation(
                    "42",
                    group_name="explore_001",
                    operation="explore",
                    agents=["explorer_001a", "explorer_001b"],
                    head_at_creation="n000_init",
                )

            groups = _read_groups(wt)
            self.assertIn("explore_001", groups)
            entry = groups["explore_001"]
            self.assertEqual(entry["operation"], "explore")
            self.assertEqual(entry["agents"], ["explorer_001a", "explorer_001b"])
            self.assertEqual(entry["status"], "Waiting")
            self.assertEqual(entry["head_at_creation"], "n000_init")
            self.assertEqual(entry["nodes_created"], [])
            self.assertIn("created_at", entry)

    def test_overwrites_existing_entry(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_empty_groups(wt)
            with _patch_worktree(wt):
                record_operation(
                    "42", "explore_001", "explore",
                    ["a"], head_at_creation="n0",
                )
                record_operation(
                    "42", "explore_001", "explore",
                    ["a", "b"], head_at_creation="n1",
                )

            groups = _read_groups(wt)
            self.assertEqual(groups["explore_001"]["agents"], ["a", "b"])
            self.assertEqual(groups["explore_001"]["head_at_creation"], "n1")

    def test_missing_groups_file_is_created(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            # No br_groups.yaml at all — record_operation should create it.
            with _patch_worktree(wt):
                record_operation(
                    "42", "compare_001", "compare", ["comparator_001"], None,
                )
            self.assertTrue((wt / GROUPS_FILE).is_file())
            groups = _read_groups(wt)
            self.assertIn("compare_001", groups)


class UpdateOperationTests(unittest.TestCase):
    def test_overwrite_field(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_empty_groups(wt)
            with _patch_worktree(wt):
                record_operation(
                    "42", "explore_001", "explore", ["a"], "n0",
                )
                update_operation("42", "explore_001", status="Completed")
            groups = _read_groups(wt)
            self.assertEqual(groups["explore_001"]["status"], "Completed")

    def test_nodes_created_appends_unique(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_empty_groups(wt)
            with _patch_worktree(wt):
                record_operation(
                    "42", "explore_001", "explore", ["a"], "n0",
                )
                update_operation("42", "explore_001", nodes_created="n001_x")
                update_operation("42", "explore_001", nodes_created="n002_y")
                # Duplicate add — should be a no-op
                update_operation("42", "explore_001", nodes_created="n001_x")
            groups = _read_groups(wt)
            self.assertEqual(
                groups["explore_001"]["nodes_created"],
                ["n001_x", "n002_y"],
            )

    def test_agents_append_unique(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_empty_groups(wt)
            with _patch_worktree(wt):
                record_operation(
                    "42", "bootstrap", "bootstrap", [], None,
                )
                update_operation(
                    "42", "bootstrap",
                    agents_append="initializer_bootstrap",
                )
                # Duplicate
                update_operation(
                    "42", "bootstrap",
                    agents_append="initializer_bootstrap",
                )
            groups = _read_groups(wt)
            self.assertEqual(
                groups["bootstrap"]["agents"], ["initializer_bootstrap"],
            )

    def test_silent_noop_for_missing_group(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_empty_groups(wt)
            with _patch_worktree(wt):
                # Should not raise
                update_operation("42", "nonexistent", status="Completed")
            groups = _read_groups(wt)
            self.assertEqual(groups, {})

    def test_head_at_creation_none_roundtrips(self):
        """head_at_creation=None must remain None after YAML round-trip
        (relevant for the bootstrap entry written by init_session)."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_empty_groups(wt)
            with _patch_worktree(wt):
                record_operation(
                    "42", "bootstrap", "bootstrap", [],
                    head_at_creation=None,
                )
            groups = _read_groups(wt)
            self.assertIsNone(groups["bootstrap"]["head_at_creation"])


# ---------------------------------------------------------------------------
# Integration tests: call sites in init_session / apply_initializer_output /
# apply_patcher_output / _run_design_op all produce the expected br_groups.yaml
# state.
# ---------------------------------------------------------------------------


from brainstorm.brainstorm_session import (  # noqa: E402
    GRAPH_STATE_FILE,
    SESSION_FILE,
    apply_initializer_output,
    apply_patcher_output,
    init_session,
)
from brainstorm.brainstorm_dag import (  # noqa: E402
    NODES_DIR,
    PLANS_DIR,
    PROPOSALS_DIR,
)


class InitSessionBootstrapTests(unittest.TestCase):
    def test_blank_init_records_bootstrap_completed(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td) / "crew-brainstorm-99"
            wt.mkdir()
            with _patch_worktree(wt):
                init_session(
                    99, "aitasks/t99.md", "u@example.com",
                    "Initial spec line",
                )
            groups = _read_groups(wt)
            self.assertIn("bootstrap", groups)
            b = groups["bootstrap"]
            self.assertEqual(b["operation"], "bootstrap")
            self.assertEqual(b["agents"], [])
            self.assertEqual(b["nodes_created"], ["n000_init"])
            self.assertEqual(b["status"], "Completed")
            self.assertIsNone(b["head_at_creation"])

    def test_proposal_file_init_records_bootstrap_waiting(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td) / "crew-brainstorm-100"
            wt.mkdir()
            proposal_path = Path(td) / "incoming.md"
            proposal_path.write_text("# Imported\nbody\n", encoding="utf-8")
            with _patch_worktree(wt):
                init_session(
                    100, "aitasks/t100.md", "u@example.com",
                    "Initial spec",
                    initial_proposal_file=str(proposal_path),
                )
            groups = _read_groups(wt)
            b = groups["bootstrap"]
            self.assertEqual(b["status"], "Waiting")
            self.assertEqual(b["nodes_created"], ["n000_init"])


class ApplyInitializerUpdatesBootstrapTests(unittest.TestCase):
    def test_initializer_appends_agent_and_flips_status(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td) / "crew-brainstorm-101"
            wt.mkdir()
            proposal_path = Path(td) / "incoming.md"
            proposal_path.write_text("# Imported\n", encoding="utf-8")
            with _patch_worktree(wt):
                init_session(
                    101, "aitasks/t101.md", "u@example.com",
                    "Initial spec",
                    initial_proposal_file=str(proposal_path),
                )

                # Build a valid initializer output: the four delimiter
                # blocks parsed by apply_initializer_output.
                node_yaml = (
                    "node_id: n000_init\n"
                    "parents: []\n"
                    "description: Reformatted proposal\n"
                    "proposal_file: br_proposals/n000_init.md\n"
                    "created_at: '2026-05-05 12:00'\n"
                    "created_by_group: bootstrap\n"
                )
                proposal_md = (
                    "<!-- section: overview -->\n"
                    "Reformatted body.\n"
                    "<!-- /section: overview -->\n"
                )
                output = (
                    "--- NODE_YAML_START ---\n"
                    f"{node_yaml}"
                    "--- NODE_YAML_END ---\n"
                    "--- PROPOSAL_START ---\n"
                    f"{proposal_md}"
                    "--- PROPOSAL_END ---\n"
                )
                (wt / "initializer_bootstrap_output.md").write_text(
                    output, encoding="utf-8",
                )

                apply_initializer_output(101)

            groups = _read_groups(wt)
            b = groups["bootstrap"]
            self.assertEqual(b["status"], "Completed")
            self.assertIn("initializer_bootstrap", b["agents"])


class ApplyPatcherUpdatesGroupTests(unittest.TestCase):
    def test_patcher_apply_updates_group_nodes_and_status(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td) / "crew-brainstorm-102"
            wt.mkdir()
            with _patch_worktree(wt):
                init_session(
                    102, "aitasks/t102.md", "u@example.com",
                    "Initial spec",
                )

                # Pre-record a patch_001 group so apply_patcher_output's
                # update_operation has a target to update.
                record_operation(
                    102, "patch_001", "patch", ["patcher_001"],
                    head_at_creation="n000_init",
                )

                # Seed a patcher output that creates n001_patched parented
                # on n000_init.
                node_meta = (
                    "node_id: n001_patched\n"
                    "parents: [n000_init]\n"
                    "description: Patched node\n"
                    "proposal_file: br_proposals/n000_init.md\n"
                    "created_at: '2026-05-05 12:05'\n"
                    "created_by_group: patch_001\n"
                )
                output = (
                    "--- PATCHED_PLAN_START ---\n"
                    "# Patched plan\nbody\n"
                    "--- PATCHED_PLAN_END ---\n"
                    "--- IMPACT_START ---\n"
                    "**NO_IMPACT** Justification.\n"
                    "--- IMPACT_END ---\n"
                    "--- METADATA_START ---\n"
                    f"{node_meta}"
                    "--- METADATA_END ---\n"
                )
                (wt / "patcher_001_output.md").write_text(
                    output, encoding="utf-8",
                )

                new_id, _impact, _details = apply_patcher_output(
                    102, "patcher_001", "n000_init",
                )

            groups = _read_groups(wt)
            self.assertEqual(new_id, "n001_patched")
            p = groups["patch_001"]
            self.assertEqual(p["status"], "Completed")
            self.assertEqual(p["nodes_created"], ["n001_patched"])


if __name__ == "__main__":
    unittest.main()
