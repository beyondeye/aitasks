"""Tests for brainstorm_session helpers.

Covers t670: ``n000_needs_apply`` previously returned True as soon as the
placeholder ``initializer_bootstrap_output.md`` (written by
``aitask_crew_addwork.sh`` at agent registration) appeared, before the
initializer agent had produced any structured output. The fix tightens
the gate to require all four delimiter blocks
(``NODE_YAML_START/END`` + ``PROPOSAL_START/END``) consumed by
``apply_initializer_output``.

Also covers t676: ``apply_initializer_output`` now auto-fills
system-generable fields (``created_at``, ``created_by_group``) when the
agent's NODE_YAML block omits them, so a forgetful agent does not poison
the apply.
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
    apply_initializer_output,
    n000_needs_apply,
)
from brainstorm.brainstorm_dag import NODES_DIR, PROPOSALS_DIR  # noqa: E402


PLACEHOLDER_OUTPUT = (
    "# Output from agent: initializer_bootstrap\n"
    "\n"
    "This file is populated by the agent during/after execution."
)

FULL_OUTPUT = (
    "--- NODE_YAML_START ---\n"
    "id: n000_init\n"
    "description: Imported proposal (reformatted): plan.md\n"
    "--- NODE_YAML_END ---\n"
    "--- PROPOSAL_START ---\n"
    "## Section\n"
    "Body.\n"
    "--- PROPOSAL_END ---\n"
)

PLACEHOLDER_DESC = "Imported proposal (awaiting reformat): plan.md"


def _seed(
    wt: Path,
    *,
    desc: str | None = PLACEHOLDER_DESC,
    output: str | None = PLACEHOLDER_OUTPUT,
) -> None:
    if desc is not None:
        (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
        node_data = {"id": "n000_init", "description": desc, "parents": []}
        (wt / NODES_DIR / "n000_init.yaml").write_text(
            yaml.safe_dump(node_data), encoding="utf-8"
        )
    if output is not None:
        (wt / "initializer_bootstrap_output.md").write_text(
            output, encoding="utf-8"
        )


class N000NeedsApplyTests(unittest.TestCase):
    def _run(
        self,
        *,
        desc: str | None = PLACEHOLDER_DESC,
        output: str | None = PLACEHOLDER_OUTPUT,
    ) -> bool:
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed(wt, desc=desc, output=output)
            with patch(
                "brainstorm.brainstorm_session.crew_worktree",
                return_value=wt,
            ):
                return n000_needs_apply("42")

    def test_returns_false_when_output_only_has_placeholder(self):
        self.assertFalse(self._run())

    def test_returns_false_when_only_node_yaml_start_present(self):
        partial = (
            "--- NODE_YAML_START ---\n"
            "id: n000_init\n"
        )
        self.assertFalse(self._run(output=partial))

    def test_returns_false_when_only_node_block_complete(self):
        partial = (
            "--- NODE_YAML_START ---\n"
            "id: n000_init\n"
            "--- NODE_YAML_END ---\n"
        )
        self.assertFalse(self._run(output=partial))

    def test_returns_true_when_all_four_delimiters_present(self):
        self.assertTrue(self._run(output=FULL_OUTPUT))

    def test_returns_false_when_output_file_missing(self):
        self.assertFalse(self._run(output=None))

    def test_returns_false_when_node_file_missing(self):
        self.assertFalse(self._run(desc=None, output=FULL_OUTPUT))

    def test_returns_false_when_description_does_not_match(self):
        self.assertFalse(
            self._run(desc="Some other description", output=FULL_OUTPUT)
        )


def _build_output(node_yaml_lines: list[str]) -> str:
    """Build a complete initializer_bootstrap_output.md payload.

    The PROPOSAL block has no <!-- section: ... --> markers, which
    validate_sections accepts as valid (no duplicates / unclosed sections).
    """
    yaml_block = "\n".join(node_yaml_lines)
    return (
        "--- NODE_YAML_START ---\n"
        f"{yaml_block}\n"
        "--- NODE_YAML_END ---\n"
        "--- PROPOSAL_START ---\n"
        "## Overview\n"
        "Imported proposal body.\n"
        "--- PROPOSAL_END ---\n"
    )


def _seed_apply(wt: Path, node_yaml_lines: list[str]) -> None:
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / "initializer_bootstrap_output.md").write_text(
        _build_output(node_yaml_lines), encoding="utf-8"
    )


class ApplyInitializerDefaultsTests(unittest.TestCase):
    """Auto-fill of system-generable fields (created_at, created_by_group)."""

    def _run_apply(self, node_yaml_lines: list[str]) -> tuple[Path, dict]:
        td = tempfile.mkdtemp()
        wt = Path(td)
        _seed_apply(wt, node_yaml_lines)
        with patch(
            "brainstorm.brainstorm_session.crew_worktree",
            return_value=wt,
        ):
            apply_initializer_output("42")
        node_data = yaml.safe_load(
            (wt / NODES_DIR / "n000_init.yaml").read_text(encoding="utf-8")
        )
        return wt, node_data

    def test_missing_created_at_is_auto_filled(self):
        # Omit created_at; everything else valid.
        lines = [
            "node_id: n000_init",
            "parents: []",
            "description: Imported proposal",
            "proposal_file: br_proposals/n000_init.md",
            "created_by_group: bootstrap",
        ]
        _, node_data = self._run_apply(lines)
        self.assertIn("created_at", node_data)
        self.assertRegex(
            str(node_data["created_at"]),
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$",
        )

    def test_missing_created_by_group_defaults_to_bootstrap(self):
        # Omit created_by_group; everything else valid.
        lines = [
            "node_id: n000_init",
            "parents: []",
            "description: Imported proposal",
            "proposal_file: br_proposals/n000_init.md",
            'created_at: "2026-04-27 17:19"',
        ]
        _, node_data = self._run_apply(lines)
        self.assertEqual(node_data.get("created_by_group"), "bootstrap")

    def test_provided_values_are_preserved(self):
        # Auto-fill must not clobber values the agent did supply.
        lines = [
            "node_id: n000_init",
            "parents: []",
            "description: Imported proposal",
            "proposal_file: br_proposals/n000_init.md",
            'created_at: "2025-12-31 23:59"',
            "created_by_group: custom_group",
        ]
        _, node_data = self._run_apply(lines)
        self.assertEqual(str(node_data["created_at"]), "2025-12-31 23:59")
        self.assertEqual(node_data["created_by_group"], "custom_group")

    def test_missing_description_still_raises(self):
        # description is semantic content the agent must supply — not
        # auto-filled. The validator should still reject it.
        lines = [
            "node_id: n000_init",
            "parents: []",
            "proposal_file: br_proposals/n000_init.md",
            'created_at: "2026-04-27 17:19"',
            "created_by_group: bootstrap",
        ]
        with self.assertRaises(ValueError) as ctx:
            self._run_apply(lines)
        self.assertIn("description", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
