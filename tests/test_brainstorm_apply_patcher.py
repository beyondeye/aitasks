"""Tests for ``apply_patcher_output`` (t743).

Covers the engine-side apply flow: parsing the patcher's three-block
output, creating a new node parented on the source, copying the source's
proposal, writing the patched plan, advancing graph state, and surfacing
the IMPACT verdict (NO_IMPACT vs IMPACT_FLAG) plus details for the TUI
banner.
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
    _patcher_needs_apply,
    apply_patcher_output,
)


SOURCE_PROPOSAL = "## Overview\nSource proposal body.\n"


def _metadata_block(*, node_id="n001_patched", parents=None,
                    description="Patched node", created_at=None,
                    created_by_group=None, reference_files=None,
                    extra_lines=None) -> str:
    if parents is None:
        parents = ["n000_init"]
    lines = [
        f"node_id: {node_id}",
        f"parents: {parents!r}".replace("'", ""),  # YAML inline list
        f"description: {description!r}",
        f"proposal_file: br_proposals/n000_init.md",
    ]
    if created_at is not None:
        lines.append(f'created_at: "{created_at}"')
    if created_by_group is not None:
        lines.append(f"created_by_group: {created_by_group}")
    if reference_files is not None:
        lines.append(f"reference_files: {reference_files!r}".replace("'", '"'))
    if extra_lines:
        lines.extend(extra_lines)
    return "\n".join(lines)


def _build_patcher_output(*, plan_text="# Patched plan\nBody.\n",
                          impact_text="**NO_IMPACT** Justification.",
                          metadata_text=None) -> str:
    if metadata_text is None:
        metadata_text = _metadata_block()
    return (
        "--- PATCHED_PLAN_START ---\n"
        f"{plan_text}"
        "--- PATCHED_PLAN_END ---\n"
        "--- IMPACT_START ---\n"
        f"{impact_text}\n"
        "--- IMPACT_END ---\n"
        "--- METADATA_START ---\n"
        f"{metadata_text}\n"
        "--- METADATA_END ---\n"
    )


def _seed_session(wt: Path, *, output_text=None,
                  source_node_id="n000_init",
                  source_proposal=SOURCE_PROPOSAL,
                  agent_name="patcher_001",
                  initial_head="n000_init",
                  initial_next_id=1) -> None:
    """Create a minimal crew worktree with the source node + proposal,
    plus the patcher's _output.md if ``output_text`` is given.
    """
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PLANS_DIR).mkdir(parents=True, exist_ok=True)

    source_node = {
        "node_id": source_node_id,
        "parents": [],
        "description": "Source node",
        "proposal_file": f"{PROPOSALS_DIR}/{source_node_id}.md",
        "created_at": "2026-01-01 00:00",
        "created_by_group": "bootstrap",
    }
    (wt / NODES_DIR / f"{source_node_id}.yaml").write_text(
        yaml.safe_dump(source_node), encoding="utf-8"
    )
    if source_proposal is not None:
        (wt / PROPOSALS_DIR / f"{source_node_id}.md").write_text(
            source_proposal, encoding="utf-8"
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
    if output_text is not None:
        (wt / f"{agent_name}_output.md").write_text(
            output_text, encoding="utf-8"
        )


def _apply(wt: Path, *, agent_name="patcher_001",
           source_node_id="n000_init", task_num="42"):
    with patch(
        "brainstorm.brainstorm_session.crew_worktree",
        return_value=wt,
    ):
        return apply_patcher_output(task_num, agent_name, source_node_id)


class ApplyPatcherHappyPathTests(unittest.TestCase):
    def test_no_impact_creates_node_and_advances_head(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_patcher_output(
                metadata_text=_metadata_block(
                    created_at="2026-05-04 12:52",
                    created_by_group="patch_001",
                    extra_lines=["component_x: foo", "assumption_y: bar"],
                ),
            )
            _seed_session(wt, output_text=output)

            new_id, impact, details = _apply(wt)

            self.assertEqual(new_id, "n001_patched")
            self.assertEqual(impact, "NO_IMPACT")
            self.assertIn("**NO_IMPACT**", details)

            # Node yaml exists, proposal_file points to the new node's file.
            node_data = yaml.safe_load(
                (wt / NODES_DIR / f"{new_id}.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                node_data["proposal_file"], f"{PROPOSALS_DIR}/{new_id}.md"
            )
            self.assertEqual(node_data["plan_file"],
                             f"{PLANS_DIR}/{new_id}_plan.md")
            self.assertEqual(node_data["component_x"], "foo")
            self.assertEqual(node_data["assumption_y"], "bar")

            # Source proposal copied verbatim under the new node id.
            new_prop = (wt / PROPOSALS_DIR / f"{new_id}.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(new_prop, SOURCE_PROPOSAL)

            # Plan written.
            plan = (wt / PLANS_DIR / f"{new_id}_plan.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("# Patched plan", plan)

            # Graph state advanced.
            gs = yaml.safe_load(
                (wt / GRAPH_STATE_FILE).read_text(encoding="utf-8")
            )
            self.assertEqual(gs["current_head"], new_id)
            self.assertEqual(gs["next_node_id"], 2)
            self.assertIn(new_id, gs["history"])

    def test_impact_flag_returns_details(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            impact = (
                "**IMPACT_FLAG**\n"
                "Affected: component_cache (Redis -> Memcached)\n"
                "Recommended action: Re-run Explorer."
            )
            output = _build_patcher_output(impact_text=impact)
            _seed_session(wt, output_text=output)

            new_id, impact_type, details = _apply(wt)

            self.assertEqual(new_id, "n001_patched")
            self.assertEqual(impact_type, "IMPACT_FLAG")
            self.assertIn("component_cache", details)
            self.assertIn("Re-run Explorer", details)

    def test_reference_files_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            meta = _metadata_block(
                reference_files=["aidocs/x.md", "aitasks/t1.md"],
            )
            _seed_session(wt, output_text=_build_patcher_output(metadata_text=meta))

            new_id, _, _ = _apply(wt)

            data = yaml.safe_load(
                (wt / NODES_DIR / f"{new_id}.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(data["reference_files"],
                             ["aidocs/x.md", "aitasks/t1.md"])

    def test_reference_files_absent_when_omitted(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_patcher_output())

            new_id, _, _ = _apply(wt)

            data = yaml.safe_load(
                (wt / NODES_DIR / f"{new_id}.yaml").read_text(encoding="utf-8")
            )
            self.assertNotIn("reference_files", data)


class ApplyPatcherDefaultsTests(unittest.TestCase):
    def test_missing_created_at_is_auto_filled(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            meta = _metadata_block(created_by_group="patch_001")  # no created_at
            _seed_session(wt, output_text=_build_patcher_output(metadata_text=meta))

            new_id, _, _ = _apply(wt)

            data = yaml.safe_load(
                (wt / NODES_DIR / f"{new_id}.yaml").read_text(encoding="utf-8")
            )
            self.assertRegex(
                str(data["created_at"]),
                r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$",
            )

    def test_missing_created_by_group_derived_from_agent_name(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            meta = _metadata_block(created_at="2026-05-04 12:52")  # no group
            _seed_session(
                wt,
                output_text=_build_patcher_output(metadata_text=meta),
                agent_name="patcher_007",
            )

            new_id, _, _ = _apply(wt, agent_name="patcher_007")

            data = yaml.safe_load(
                (wt / NODES_DIR / f"{new_id}.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(data["created_by_group"], "patch_007")


class ApplyPatcherErrorTests(unittest.TestCase):
    def test_missing_output_raises_filenotfound(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=None)
            with self.assertRaises(FileNotFoundError):
                _apply(wt)

    def test_missing_delimiter_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            broken = _build_patcher_output().replace(
                "--- METADATA_END ---", ""
            )
            _seed_session(wt, output_text=broken)
            with self.assertRaises(ValueError) as ctx:
                _apply(wt)
            self.assertIn("METADATA", str(ctx.exception))

    def test_missing_source_proposal_raises_filenotfound(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_patcher_output(),
                          source_proposal=None)
            with self.assertRaises(FileNotFoundError):
                _apply(wt)

    def test_neither_impact_marker_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_patcher_output(
                impact_text="(impact analysis not performed)"
            )
            _seed_session(wt, output_text=output)
            with self.assertRaises(ValueError) as ctx:
                _apply(wt)
            self.assertIn("IMPACT", str(ctx.exception))

    def test_both_impact_markers_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_patcher_output(
                impact_text="**NO_IMPACT** safe.\n\n**IMPACT_FLAG** never mind."
            )
            _seed_session(wt, output_text=output)
            with self.assertRaises(ValueError):
                _apply(wt)

    def test_existing_node_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=_build_patcher_output())
            (wt / NODES_DIR / "n001_patched.yaml").write_text(
                "node_id: n001_patched\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError) as ctx:
                _apply(wt)
            self.assertIn("already exists", str(ctx.exception))

    def test_invalid_yaml_writes_error_log(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            broken = _build_patcher_output(
                metadata_text="node_id: [unbalanced\nparents: [n000_init]"
            )
            _seed_session(wt, output_text=broken)
            with self.assertRaises(yaml.YAMLError):
                _apply(wt)
            self.assertTrue(
                (wt / "patcher_001_apply_error.log").is_file()
            )

    def test_invalid_metadata_writes_error_log(self):
        # validate_node failure (description missing) — exercises the
        # catch-all error log path, not the YAML parse path.
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            meta = (
                "node_id: n001_x\n"
                "parents: [n000_init]\n"
                "proposal_file: br_proposals/n000_init.md\n"
                'created_at: "2026-05-04 12:52"\n'
                "created_by_group: patch_001\n"
            )
            _seed_session(wt, output_text=_build_patcher_output(metadata_text=meta))
            with self.assertRaises(ValueError):
                _apply(wt)
            self.assertTrue(
                (wt / "patcher_001_apply_error.log").is_file()
            )


class PatcherNeedsApplyTests(unittest.TestCase):
    def _gate(self, output_text, *, agent_name="patcher_001",
              pre_create_node=False) -> bool:
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt, output_text=output_text)
            if pre_create_node:
                (wt / NODES_DIR / "n001_patched.yaml").write_text(
                    "node_id: n001_patched\n", encoding="utf-8"
                )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree",
                return_value=wt,
            ):
                return _patcher_needs_apply("42", agent_name)

    def test_returns_false_when_output_missing(self):
        self.assertFalse(self._gate(None))

    def test_returns_false_when_only_some_delimiters_present(self):
        partial = (
            "--- PATCHED_PLAN_START ---\n"
            "x\n"
            "--- PATCHED_PLAN_END ---\n"
        )
        self.assertFalse(self._gate(partial))

    def test_returns_true_when_full_output_and_no_existing_node(self):
        self.assertTrue(self._gate(_build_patcher_output()))

    def test_returns_false_when_target_node_already_exists(self):
        self.assertFalse(self._gate(_build_patcher_output(),
                                    pre_create_node=True))


if __name__ == "__main__":
    unittest.main()
