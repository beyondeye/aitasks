"""Tests for ``apply_explorer_output`` (t739).

Covers the engine-side apply flow for explorer agents: parsing the
two-block NODE_YAML + PROPOSAL output, creating a new node parented as
the explorer specified, advancing graph state, and merging any
NEW_DIMENSIONS into the session's active_dimensions list.
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
    _explorer_needs_apply,
    apply_explorer_output,
)


PROPOSAL_BODY = (
    "## Overview\n"
    "Explored proposal body.\n"
)


def _node_yaml(
    *,
    node_id: str = "n001_explored",
    parents=None,
    description: str = "Explored node",
    proposal_file: str | None = None,
    created_at: str | None = None,
    created_by_group: str | None = None,
    reference_files=None,
    extra_lines=None,
) -> str:
    if parents is None:
        parents = ["n000_init"]
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
    new_dimensions: str | None = None,
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
    if new_dimensions is not None:
        parts.append("--- NEW_DIMENSIONS ---")
        parts.append(new_dimensions)
    return "\n".join(parts) + "\n"


def _seed_session(
    wt: Path,
    *,
    output_text: str | None = None,
    agent_name: str = "explorer_001a",
    initial_head: str = "n000_init",
    initial_next_id: int = 1,
    active_dimensions: list[str] | None = None,
) -> None:
    """Create a minimal crew worktree: one source node + graph state."""
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)

    source_node = {
        "node_id": initial_head,
        "parents": [],
        "description": "Source node",
        "proposal_file": f"{PROPOSALS_DIR}/{initial_head}.md",
        "created_at": "2026-01-01 00:00",
        "created_by_group": "bootstrap",
    }
    (wt / NODES_DIR / f"{initial_head}.yaml").write_text(
        yaml.safe_dump(source_node), encoding="utf-8"
    )
    (wt / PROPOSALS_DIR / f"{initial_head}.md").write_text(
        PROPOSAL_BODY, encoding="utf-8"
    )
    (wt / GRAPH_STATE_FILE).write_text(
        yaml.safe_dump({
            "current_head": initial_head,
            "history": [initial_head],
            "next_node_id": initial_next_id,
            "active_dimensions": list(active_dimensions or []),
        }),
        encoding="utf-8",
    )
    if output_text is not None:
        (wt / f"{agent_name}_output.md").write_text(
            output_text, encoding="utf-8"
        )


def _apply(wt: Path, agent_name: str = "explorer_001a", task_num: str = "42"):
    with patch(
        "brainstorm.brainstorm_session.crew_worktree",
        return_value=wt,
    ):
        return apply_explorer_output(task_num, agent_name)


class ApplyExplorerHappyPathTests(unittest.TestCase):
    def test_creates_node_and_advances_head(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(
                    created_at="2026-05-04 12:52",
                    created_by_group="explore_001",
                    extra_lines=[
                        "component_cache: Redis",
                        "assumption_pool: bounded",
                    ],
                ),
            )
            _seed_session(wt, output_text=output)

            new_id = _apply(wt)

            self.assertEqual(new_id, "n001_explored")
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
            self.assertEqual(node_data["parents"], ["n000_init"])

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
            self.assertEqual(gs["next_node_id"], 1)
            # history is a per-module map (t756); the legacy list fixture is
            # migrated into the _umbrella subgraph on set_head.
            self.assertIn(new_id, gs["history"]["_umbrella"])

    def test_reference_files_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(
                    created_by_group="explore_001",
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
                node_yaml_text=_node_yaml(created_by_group="explore_001"),
            )
            _seed_session(wt, output_text=output)
            _apply(wt)
            node_data = yaml.safe_load(
                (wt / NODES_DIR / "n001_explored.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("created_at", node_data)
            self.assertTrue(node_data["created_at"])

    def test_missing_created_by_group_derived_from_agent_name(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            # No created_by_group line in NODE_YAML — derive from
            # agent_name (explorer_001a → explore_001).
            output = _build_output(node_yaml_text=_node_yaml())
            _seed_session(wt, output_text=output)
            _apply(wt, agent_name="explorer_001a")
            node_data = yaml.safe_load(
                (wt / NODES_DIR / "n001_explored.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(node_data["created_by_group"], "explore_001")


class NewDimensionsTests(unittest.TestCase):
    def test_new_dimensions_merged_into_graph_state(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(created_by_group="explore_001"),
                new_dimensions="component_cache, assumption_pool",
            )
            _seed_session(
                wt, output_text=output,
                active_dimensions=["component_cache"],
            )

            _apply(wt)

            gs = yaml.safe_load(
                (wt / GRAPH_STATE_FILE).read_text(encoding="utf-8")
            )
            self.assertEqual(
                gs["active_dimensions"],
                ["component_cache", "assumption_pool"],
            )

    def test_new_dimensions_none_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(created_by_group="explore_001"),
                new_dimensions="none",
            )
            _seed_session(
                wt, output_text=output,
                active_dimensions=["component_existing"],
            )
            _apply(wt)
            gs = yaml.safe_load(
                (wt / GRAPH_STATE_FILE).read_text(encoding="utf-8")
            )
            self.assertEqual(
                gs["active_dimensions"], ["component_existing"],
            )

    def test_new_dimensions_absent_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(created_by_group="explore_001"),
            )
            _seed_session(
                wt, output_text=output,
                active_dimensions=["component_existing"],
            )
            _apply(wt)
            gs = yaml.safe_load(
                (wt / GRAPH_STATE_FILE).read_text(encoding="utf-8")
            )
            self.assertEqual(
                gs["active_dimensions"], ["component_existing"],
            )


class ApplyExplorerErrorTests(unittest.TestCase):
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
            (wt / NODES_DIR / "n001_explored.yaml").write_text(
                yaml.safe_dump({"node_id": "n001_explored"}),
                encoding="utf-8",
            )
            output = _build_output(node_yaml_text=_node_yaml(
                created_by_group="explore_001",
            ))
            (wt / "explorer_001a_output.md").write_text(
                output, encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                _apply(wt)

    def test_invalid_yaml_writes_error_log(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            broken_yaml = "node_id: n001_explored\nparents: [n000_init\n"
            output = _build_output(node_yaml_text=broken_yaml)
            _seed_session(wt, output_text=output)
            with self.assertRaises(yaml.YAMLError):
                _apply(wt)
            log = wt / "explorer_001a_apply_error.log"
            self.assertTrue(log.is_file())
            self.assertIn("apply_explorer_output", log.read_text())

    def test_invalid_node_data_writes_error_log(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            # Description omitted → validate_node fails.
            output = _build_output(node_yaml_text=(
                "node_id: n001_explored\n"
                "parents: [n000_init]\n"
                "proposal_file: br_proposals/n001_explored.md\n"
                "created_by_group: explore_001\n"
            ))
            _seed_session(wt, output_text=output)
            with self.assertRaises(ValueError):
                _apply(wt)
            log = wt / "explorer_001a_apply_error.log"
            self.assertTrue(log.is_file())


class ExplorerNeedsApplyTests(unittest.TestCase):
    def _needs(self, wt: Path, agent: str = "explorer_001a") -> bool:
        with patch(
            "brainstorm.brainstorm_session.crew_worktree",
            return_value=wt,
        ):
            return _explorer_needs_apply("42", agent)

    def test_returns_false_when_output_missing(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            self.assertFalse(self._needs(wt))

    def test_returns_false_when_only_some_delimiters_present(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            (wt / "explorer_001a_output.md").write_text(
                "--- NODE_YAML_START ---\nfoo\n", encoding="utf-8"
            )
            self.assertFalse(self._needs(wt))

    def test_returns_true_when_full_output_and_no_existing_node(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(created_by_group="explore_001"),
            )
            _seed_session(wt, output_text=output)
            self.assertTrue(self._needs(wt))

    def test_returns_false_when_target_node_already_exists(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            output = _build_output(
                node_yaml_text=_node_yaml(created_by_group="explore_001"),
            )
            _seed_session(wt, output_text=output)
            (wt / NODES_DIR / "n001_explored.yaml").write_text(
                yaml.safe_dump({"node_id": "n001_explored"}),
                encoding="utf-8",
            )
            self.assertFalse(self._needs(wt))


if __name__ == "__main__":
    unittest.main()
