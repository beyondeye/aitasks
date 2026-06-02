"""Tests for module_decompose / module_merge apply paths."""

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
    UMBRELLA_SUBGRAPH,
    create_node,
    get_head,
    read_node,
    set_head,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    GROUPS_FILE,
    apply_module_decompose_from_sections,
    apply_module_decomposer_output,
    apply_module_merger_output,
    record_operation,
)


def _seed_base(wt: Path) -> None:
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / GRAPH_STATE_FILE).write_text(
        yaml.safe_dump({
            "current_head": None,
            "current_heads": {},
            "history": {},
            "next_node_id": 1,
            "active_dimensions": [],
            "module_tasks": {},
            "last_synced_at": {},
        }),
        encoding="utf-8",
    )
    create_node(
        wt,
        "n000_init",
        [],
        "Umbrella",
        {"component_core": "Core"},
        "## Overview\nUmbrella\n",
        "bootstrap",
    )
    set_head(wt, "n000_init")


def _module_block(module: str, node_id: str) -> str:
    return f"""--- MODULE_NODE_START ---
--- MODULE_NAME_START ---
{module}
--- MODULE_NAME_END ---
--- NODE_YAML_START ---
node_id: {node_id}
parents: []
description: "{module} root"
proposal_file: br_proposals/{node_id}.md
created_at: "2026-06-02 12:00"
component_{module}: "{module} component"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
## Overview
{module} proposal
--- PROPOSAL_END ---
--- MODULE_NODE_END ---
"""


def _node_output(node_id: str) -> str:
    return f"""--- NODE_YAML_START ---
node_id: {node_id}
parents: []
description: "Merged parser"
proposal_file: br_proposals/{node_id}.md
created_at: "2026-06-02 12:00"
component_parser: "Merged parser component"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
## Overview
Merged parser into umbrella.
--- PROPOSAL_END ---
"""


class ApplyModuleOpsTests(unittest.TestCase):
    def test_module_decompose_creates_roots_and_preserves_umbrella_head(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            (wt / "module_decomposer_001_output.md").write_text(
                _module_block("parser", "n001_module_decomposer_001_parser")
                + _module_block("cache", "n002_module_decomposer_001_cache"),
                encoding="utf-8",
            )

            with patch("brainstorm.brainstorm_session.crew_worktree", return_value=wt):
                record_operation(
                    "756",
                    "module_decompose_001",
                    "module_decompose",
                    ["module_decomposer_001"],
                    "n000_init",
                    modules=["parser", "cache"],
                    subgraph=UMBRELLA_SUBGRAPH,
                )
                created = apply_module_decomposer_output(
                    "756", "module_decomposer_001"
                )

            self.assertEqual(
                created,
                [
                    "n001_module_decomposer_001_parser",
                    "n002_module_decomposer_001_cache",
                ],
            )
            self.assertEqual(get_head(wt), "n000_init")
            self.assertEqual(get_head(wt, module="parser"), created[0])
            self.assertEqual(get_head(wt, module="cache"), created[1])
            self.assertEqual(read_node(wt, created[0])["parents"], ["n000_init"])
            self.assertEqual(read_node(wt, created[0])["module_label"], "parser")
            groups = yaml.safe_load((wt / GROUPS_FILE).read_text(encoding="utf-8"))
            self.assertEqual(
                groups["groups"]["module_decompose_001"]["nodes_created"],
                created,
            )

    def test_module_merge_creates_two_parent_destination_node(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            create_node(
                wt,
                "n001_parser",
                ["n000_init"],
                "Parser root",
                {"component_parser": "Parser"},
                "## Overview\nParser\n",
                "module_decompose_001",
                module_label="parser",
            )
            set_head(wt, "n001_parser", module="parser")
            (wt / "module_merger_001_output.md").write_text(
                _node_output("n002_module_merger_001"),
                encoding="utf-8",
            )

            with patch("brainstorm.brainstorm_session.crew_worktree", return_value=wt):
                record_operation(
                    "756",
                    "module_merge_001",
                    "module_merge",
                    ["module_merger_001"],
                    "n001_parser",
                    subgraph=UMBRELLA_SUBGRAPH,
                    source_subgraph="parser",
                    destination_subgraph=UMBRELLA_SUBGRAPH,
                )
                new_id = apply_module_merger_output("756", "module_merger_001")

            self.assertEqual(new_id, "n002_module_merger_001")
            self.assertEqual(
                read_node(wt, new_id)["parents"], ["n000_init", "n001_parser"]
            )
            self.assertEqual(get_head(wt), new_id)
            self.assertEqual(get_head(wt, module="parser"), "n001_parser")

    def test_module_decompose_from_sections_creates_roots_without_agent(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt)
            (wt / PROPOSALS_DIR / "n000_init.md").write_text(
                "<!-- section: parser [dimensions: component_parser] -->\n"
                "## Parser\nParser section.\n"
                "<!-- /section: parser -->\n\n"
                "<!-- section: cache [dimensions: component_cache] -->\n"
                "## Cache\nCache section.\n"
                "<!-- /section: cache -->\n",
                encoding="utf-8",
            )
            node = read_node(wt, "n000_init")
            node["component_parser"] = "Parser"
            node["component_cache"] = "Cache"
            (wt / NODES_DIR / "n000_init.yaml").write_text(
                yaml.safe_dump(node), encoding="utf-8"
            )

            with patch("brainstorm.brainstorm_session.crew_worktree", return_value=wt):
                record_operation(
                    "756",
                    "module_decompose_001",
                    "module_decompose",
                    [],
                    "n000_init",
                    modules=["parser", "cache"],
                    from_sections=True,
                    subgraph=UMBRELLA_SUBGRAPH,
                )
                created = apply_module_decompose_from_sections(
                    "756", "module_decompose_001"
                )

            self.assertEqual(len(created), 2)
            self.assertEqual(get_head(wt), "n000_init")
            self.assertEqual(read_node(wt, created[0])["module_label"], "parser")
            self.assertEqual(read_node(wt, created[1])["module_label"], "cache")


if __name__ == "__main__":
    unittest.main()
