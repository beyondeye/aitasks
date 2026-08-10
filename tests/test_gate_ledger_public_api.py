"""Compatibility contract between gate_ledger and workflow_phase (t1420).

`lib/workflow_phase.py` is a public consumer of `lib/gate_ledger.py`. Without a
pinned contract, an internal ledger refactor could rename or drop a helper and
silently degrade the phase signal — it fails soft everywhere by design, so
nothing would *break*, it would just quietly stop being right.

Two halves, and both are needed:

1. the named surface exists and behaves as documented;
2. `workflow_phase` reaches for **nothing private** — checked structurally over
   its source, because a single `gl._helper()` added later would reintroduce
   exactly the coupling the promoted functions exist to remove.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB))

import gate_ledger as gl  # noqa: E402
import workflow_phase as wp  # noqa: E402

PLAN_RUN = ("> **✅ gate:plan_approved** run=2026-01-01T00:00:00Z "
            "status=pass attempt=1 type=human\n")
REVIEW_RUN = ("> **✅ gate:review_approved** run=2026-01-01T00:01:00Z "
              "status=pass attempt=1 type=human\n")


class PublicSurfaceTest(unittest.TestCase):
    REQUIRED = ("resume_point_from_text", "read_active_gates_profile_from_text",
                "has_gate_markers", "derive_gate_runs")

    def test_names_exist_and_are_public(self):
        for name in self.REQUIRED:
            self.assertTrue(hasattr(gl, name), f"gate_ledger.{name} is missing")
            self.assertFalse(name.startswith("_"), name)

    def test_resume_point_from_text_contract(self):
        self.assertEqual(gl.resume_point_from_text(""), "PLAN")
        self.assertEqual(gl.resume_point_from_text(PLAN_RUN), "IMPLEMENT")
        self.assertEqual(gl.resume_point_from_text(PLAN_RUN + REVIEW_RUN),
                         "POSTIMPL")

    def test_resume_point_file_and_text_agree(self):
        """The file wrapper must stay a wrapper — not a second derivation."""
        import tempfile
        text = "---\nstatus: Implementing\n---\n\n" + PLAN_RUN
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(text)
            path = fh.name
        self.assertEqual(gl.resume_point(path), gl.resume_point_from_text(text))

    def test_read_active_gates_profile_from_text_contract(self):
        text = "---\nstatus: Ready\nactive_gates_profile: fast\n---\n"
        self.assertEqual(gl.read_active_gates_profile_from_text(text), "fast")
        self.assertEqual(gl.read_active_gates_profile_from_text("---\n---\n"), "")
        self.assertEqual(gl.read_active_gates_profile_from_text(""), "")

    def test_has_gate_markers_contract(self):
        self.assertFalse(gl.has_gate_markers("no markers here"))
        self.assertTrue(gl.has_gate_markers(PLAN_RUN))


class NoPrivateCouplingTest(unittest.TestCase):
    """`workflow_phase` must import and touch only public `gate_ledger` names."""

    def _tree(self) -> ast.AST:
        return ast.parse((LIB / "workflow_phase.py").read_text(encoding="utf-8"))

    def test_no_private_attribute_access_on_gate_ledger(self):
        tree = self._tree()
        # Resolve the alias gate_ledger was imported under (`import x as gl`).
        aliases = {
            (a.asname or a.name)
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for a in node.names if a.name == "gate_ledger"
        }
        self.assertTrue(aliases, "workflow_phase no longer imports gate_ledger")
        offenders = [
            f"{node.value.id}.{node.attr}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and node.attr.startswith("_")
        ]
        self.assertEqual(offenders, [], f"private gate_ledger access: {offenders}")

    def test_no_from_import_of_private_names(self):
        offenders = [
            a.name
            for node in ast.walk(self._tree())
            if isinstance(node, ast.ImportFrom) and node.module == "gate_ledger"
            for a in node.names if a.name.startswith("_")
        ]
        self.assertEqual(offenders, [], f"private from-imports: {offenders}")

    def test_detector_catches_a_violation(self):
        """Positive control: the AST check must actually fire on private use,
        otherwise the two assertions above are vacuous."""
        tree = ast.parse("import gate_ledger as gl\nx = gl._secret_helper(1)\n")
        aliases = {
            (a.asname or a.name)
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for a in node.names if a.name == "gate_ledger"
        }
        offenders = [
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and node.attr.startswith("_")
        ]
        self.assertEqual(offenders, ["_secret_helper"])


if __name__ == "__main__":
    unittest.main()
