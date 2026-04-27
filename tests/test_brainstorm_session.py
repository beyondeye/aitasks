"""Tests for brainstorm_session helpers.

Covers t670: ``n000_needs_apply`` previously returned True as soon as the
placeholder ``initializer_bootstrap_output.md`` (written by
``aitask_crew_addwork.sh`` at agent registration) appeared, before the
initializer agent had produced any structured output. The fix tightens
the gate to require all four delimiter blocks
(``NODE_YAML_START/END`` + ``PROPOSAL_START/END``) consumed by
``apply_initializer_output``.
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

from brainstorm.brainstorm_session import n000_needs_apply  # noqa: E402
from brainstorm.brainstorm_dag import NODES_DIR  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
