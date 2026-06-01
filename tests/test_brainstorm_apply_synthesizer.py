"""Tests for ``apply_synthesizer_output`` (t740).

Covers the engine-side apply flow for synthesizer agents: parsing the
two-block NODE_YAML + PROPOSAL output (no NEW_DIMENSIONS), creating a
new synthesized node parented on every source node the synthesizer
specified, and advancing graph state.
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
    PROPOSALS_DIR,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    _synthesizer_needs_apply,
    apply_synthesizer_output,
)


PROPOSAL_BODY = (
    "## Overview\n"
    "Synthesized proposal body.\n"
)


def _node_yaml(
    *,
    node_id: str = "n002_synth",
    parents=None,
    description: str = "Synthesized node",
    proposal_file: str | None = None,
    created_at: str | None = None,
    created_by_group: str | None = None,
    reference_files=None,
    extra_lines=None,
) -> str:
    if parents is None:
        parents = ["n000_init", "n001_explored"]
    if proposal_file is None:
        proposal_file = f"{PROPOSALS_DIR}/{node_id}.md"
    lines = [
        f"node_id: {node_id}",
        f"parents: {parents!r}".replace("'", ""),  # YAML inline list
        f"description: {description!r}",
        f"proposal_file: {proposal_file}",
    ]
    if created_at is not None:
        lines.append(f'created_at: "{created_at}"')
    if created_by_group is not None:
        lines.append(f"created_by_group: {created_by_group}")
    if reference_files is not None:
        lines.append(
            f"reference_files: {reference_files!r}".replace("'", '"')
        )
    if extra_lines:
        lines.extend(extra_lines)
    return "\n".join(lines)


def _build_output(
    *,
    node_yaml_text: str | None = None,
    proposal_text: str = PROPOSAL_BODY,
    drop_delimiter: str | None = None,
) -> str:
    if node_yaml_text is None:
        node_yaml_text = _node_yaml()
    parts = []
    if drop_delimiter != "NODE_YAML_START":
        parts.append("--- NODE_YAML_START ---")
    parts.append(node_yaml_text)
    if drop_delimiter != "NODE_YAML_END":
        parts.append("--- NODE_YAML_END ---")
    if drop_delimiter != "PROPOSAL_START":
        parts.append("--- PROPOSAL_START ---")
    parts.append(proposal_text.rstrip("\n"))
    if drop_delimiter != "PROPOSAL_END":
        parts.append("--- PROPOSAL_END ---")
    return "\n".join(parts) + "\n"


def _seed_session(
    wt: Path,
    *,
    output_text: str | None = None,
    agent_name: str = "synthesizer_001",
    parent_node_ids=None,
    initial_head: str = "n001_explored",
    initial_next_id: int = 2,
    active_dimensions: list[str] | None = None,
) -> None:
    """Create a minimal crew worktree: source nodes + graph state.

    Synthesizers merge multiple nodes, so the seed writes one yaml file
    per parent in ``parent_node_ids`` (defaulting to ``[n000_init,
    n001_explored]``).
    """
    if parent_node_ids is None:
        parent_node_ids = ["n000_init", "n001_explored"]
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)

    for nid in parent_node_ids:
        node = {
            "node_id": nid,
            "parents": [],
            "description": f"Source node {nid}",
            "proposal_file": f"{PROPOSALS_DIR}/{nid}.md",
            "created_at": "2026-01-01 00:00",
            "created_by_group": "bootstrap",
        }
        (wt / NODES_DIR / f"{nid}.yaml").write_text(
            yaml.safe_dump(node), encoding="utf-8"
        )
        (wt / PROPOSALS_DIR / f"{nid}.md").write_text(
            PROPOSAL_BODY, encoding="utf-8"
        )

    (wt / GRAPH_STATE_FILE).write_text(
        yaml.safe_dump({
            "current_head": initial_head,
            "history": list(parent_node_ids),
            "next_node_id": initial_next_id,
            "active_dimensions": list(active_dimensions or []),
        }),
        encoding="utf-8",
    )
    if output_text is not None:
        (wt / f"{agent_name}_output.md").write_text(
            output_text, encoding="utf-8"
        )


def _apply(wt: Path, agent_name: str = "synthesizer_001", task_num: str = "42"):
    with patch(
        "brainstorm.brainstorm_session.crew_worktree",
        return_value=wt,
    ):
        return apply_synthesizer_output(task_num, agent_name)


class ApplySynthesizerHappyPathTests(unittest.TestCase):
    def test_creates_node_and_advances_head(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(
                    created_at="2026-05-04 12:52",
                    created_by_group="synthesize_001",
                    extra_lines=[
                        "component_cache: Redis",
                        "assumption_pool: bounded",
                    ],
                ),
            )
            _seed_session(wt, output_text=output)

            new_id = _apply(wt)

            self.assertEqual(new_id, "n002_synth")
            node_data = yaml.safe_load(
                (wt / NODES_DIR / f"{new_id}.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                node_data["proposal_file"],
                f"{PROPOSALS_DIR}/{new_id}.md",
            )
            self.assertEqual(node_data["component_cache"], "Redis")
            self.assertEqual(node_data["assumption_pool"], "bounded")
            self.assertEqual(
                node_data["parents"], ["n000_init", "n001_explored"],
            )

            new_prop = (wt / PROPOSALS_DIR / f"{new_id}.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(new_prop.strip(), PROPOSAL_BODY.strip())

            gs = yaml.safe_load(
                (wt / GRAPH_STATE_FILE).read_text(encoding="utf-8")
            )
            self.assertEqual(gs["current_head"], new_id)
            # next_node_id is consumed at registration time (t795); apply
            # no longer bumps the counter. Initial value is preserved.
            self.assertEqual(gs["next_node_id"], 2)
            # history is a per-module map (t756); the legacy list fixture is
            # migrated into the _umbrella subgraph on set_head.
            self.assertIn(new_id, gs["history"]["_umbrella"])

    def test_multi_parent_node_links_all_parents(self):
        """Synthesizers merge ≥2 nodes — the new node's parents list
        must carry every source id from NODE_YAML (no truncation,
        ordering preserved)."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            parents = ["n000_init", "n001_explored", "n002_explored_b"]
            output = _build_output(
                node_yaml_text=_node_yaml(
                    node_id="n003_synth",
                    parents=parents,
                    created_by_group="synthesize_001",
                ),
            )
            _seed_session(
                wt, output_text=output, parent_node_ids=parents,
                initial_head="n002_explored_b", initial_next_id=3,
            )
            new_id = _apply(wt)
            self.assertEqual(new_id, "n003_synth")
            node_data = yaml.safe_load(
                (wt / NODES_DIR / f"{new_id}.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(node_data["parents"], parents)

    def test_reference_files_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(
                    created_by_group="synthesize_001",
                    reference_files=["src/a.py", "https://example.com/x"],
                ),
            )
            _seed_session(wt, output_text=output)

            new_id = _apply(wt)
            node_data = yaml.safe_load(
                (wt / NODES_DIR / f"{new_id}.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                node_data["reference_files"],
                ["src/a.py", "https://example.com/x"],
            )

    def test_missing_created_at_is_auto_filled(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(created_by_group="synthesize_001"),
            )
            _seed_session(wt, output_text=output)
            _apply(wt)
            node_data = yaml.safe_load(
                (wt / NODES_DIR / "n002_synth.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("created_at", node_data)
            self.assertTrue(node_data["created_at"])

    def test_missing_created_by_group_derived_from_agent_name(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            # No created_by_group line in NODE_YAML — derive from
            # agent_name (synthesizer_001 → synthesize_001 via
            # _agent_to_group_name).
            output = _build_output(node_yaml_text=_node_yaml())
            _seed_session(wt, output_text=output)
            _apply(wt, agent_name="synthesizer_001")
            node_data = yaml.safe_load(
                (wt / NODES_DIR / "n002_synth.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(node_data["created_by_group"], "synthesize_001")


class ApplySynthesizerErrorTests(unittest.TestCase):
    def test_missing_output_raises_filenotfound(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            with self.assertRaises(FileNotFoundError):
                _apply(wt)

    def test_missing_delimiter_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(drop_delimiter="NODE_YAML_END")
            _seed_session(wt, output_text=output)
            with self.assertRaises(ValueError):
                _apply(wt)

    def test_existing_node_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            # Pre-seed the target node id.
            (wt / NODES_DIR / "n002_synth.yaml").write_text(
                yaml.safe_dump({"node_id": "n002_synth"}),
                encoding="utf-8",
            )
            output = _build_output(node_yaml_text=_node_yaml(
                created_by_group="synthesize_001",
            ))
            (wt / "synthesizer_001_output.md").write_text(
                output, encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                _apply(wt)

    def test_invalid_yaml_writes_error_log(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            broken_yaml = "node_id: n002_synth\nparents: [n000_init\n"
            output = _build_output(node_yaml_text=broken_yaml)
            _seed_session(wt, output_text=output)
            with self.assertRaises(yaml.YAMLError):
                _apply(wt)
            log = wt / "synthesizer_001_apply_error.log"
            self.assertTrue(log.is_file())
            self.assertIn("apply_synthesizer_output", log.read_text())

    def test_invalid_node_data_writes_error_log(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            # Description omitted → validate_node fails.
            output = _build_output(node_yaml_text=(
                "node_id: n002_synth\n"
                "parents: [n000_init, n001_explored]\n"
                "proposal_file: br_proposals/n002_synth.md\n"
                "created_by_group: synthesize_001\n"
            ))
            _seed_session(wt, output_text=output)
            with self.assertRaises(ValueError):
                _apply(wt)
            log = wt / "synthesizer_001_apply_error.log"
            self.assertTrue(log.is_file())


class SynthesizerNeedsApplyTests(unittest.TestCase):
    def _needs(self, wt: Path, agent: str = "synthesizer_001") -> bool:
        with patch(
            "brainstorm.brainstorm_session.crew_worktree",
            return_value=wt,
        ):
            return _synthesizer_needs_apply("42", agent)

    def test_returns_false_when_output_missing(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            self.assertFalse(self._needs(wt))

    def test_returns_false_when_only_some_delimiters_present(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            (wt / "synthesizer_001_output.md").write_text(
                "--- NODE_YAML_START ---\nfoo\n", encoding="utf-8"
            )
            self.assertFalse(self._needs(wt))

    def test_returns_true_when_full_output_and_no_existing_node(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(created_by_group="synthesize_001"),
            )
            _seed_session(wt, output_text=output)
            self.assertTrue(self._needs(wt))

    def test_returns_false_when_target_node_already_exists(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(created_by_group="synthesize_001"),
            )
            _seed_session(wt, output_text=output)
            (wt / NODES_DIR / "n002_synth.yaml").write_text(
                yaml.safe_dump({"node_id": "n002_synth"}),
                encoding="utf-8",
            )
            self.assertFalse(self._needs(wt))


if __name__ == "__main__":
    unittest.main()
