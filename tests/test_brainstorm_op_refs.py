"""Tests for OpDataRef and the operation-data reference helpers (t749_2)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_op_refs import (  # noqa: E402
    OpDataRef,
    _extract_md_section,
    file_for_ref,
    list_op_definition,
    list_op_inputs,
    list_op_logs,
    list_op_outputs,
    resolve_ref,
)
from brainstorm.brainstorm_dag import (  # noqa: E402
    NODES_DIR,
    PLANS_DIR,
    PROPOSALS_DIR,
)
from brainstorm.brainstorm_schemas import canonical_op  # noqa: E402


class TestOpDataRefValidation(unittest.TestCase):
    def test_valid_kinds_accepted(self):
        for kind in [
            "agent_input", "agent_output", "agent_log",
            "node_proposal", "node_plan", "node_metadata",
            "session_spec",
        ]:
            OpDataRef(kind=kind, target="x")

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            OpDataRef(kind="nope", target="x")

    def test_frozen_dataclass(self):
        ref = OpDataRef("agent_input", "explorer_a")
        with self.assertRaises(Exception):
            ref.target = "other"  # type: ignore[misc]


class TestFileForRef(unittest.TestCase):
    def setUp(self):
        self.session = Path("/tmp/fake_session")

    def test_agent_input(self):
        ref = OpDataRef("agent_input", "explorer_a")
        self.assertEqual(
            file_for_ref(self.session, ref),
            self.session / "explorer_a_input.md",
        )

    def test_agent_output(self):
        ref = OpDataRef("agent_output", "explorer_a")
        self.assertEqual(
            file_for_ref(self.session, ref),
            self.session / "explorer_a_output.md",
        )

    def test_agent_log(self):
        ref = OpDataRef("agent_log", "explorer_a")
        self.assertEqual(
            file_for_ref(self.session, ref),
            self.session / "explorer_a_log.txt",
        )

    def test_node_proposal(self):
        ref = OpDataRef("node_proposal", "n005_x")
        self.assertEqual(
            file_for_ref(self.session, ref),
            self.session / PROPOSALS_DIR / "n005_x.md",
        )

    def test_node_plan(self):
        ref = OpDataRef("node_plan", "n005_x")
        self.assertEqual(
            file_for_ref(self.session, ref),
            self.session / PLANS_DIR / "n005_x_plan.md",
        )

    def test_node_metadata(self):
        ref = OpDataRef("node_metadata", "n005_x")
        self.assertEqual(
            file_for_ref(self.session, ref),
            self.session / NODES_DIR / "n005_x.yaml",
        )

    def test_session_spec(self):
        ref = OpDataRef("session_spec", "")
        self.assertEqual(
            file_for_ref(self.session, ref),
            self.session / "br_session.yaml",
        )


class TestExtractMdSection(unittest.TestCase):
    def test_extracts_basic_section(self):
        text = (
            "# Title\n"
            "\n"
            "## Foo\n"
            "foo body line 1\n"
            "foo body line 2\n"
            "\n"
            "## Bar\n"
            "bar body\n"
        )
        result = _extract_md_section(text, "Foo")
        self.assertEqual(result, "foo body line 1\nfoo body line 2")

    def test_stops_at_next_double_hash(self):
        text = "## A\nbody A\n## B\nbody B\n"
        self.assertEqual(_extract_md_section(text, "A"), "body A")

    def test_runs_to_eof_when_no_next_section(self):
        text = "## Only\nline 1\nline 2\n"
        self.assertEqual(_extract_md_section(text, "Only"), "line 1\nline 2")

    def test_missing_header_returns_empty(self):
        text = "## Foo\nbody\n"
        self.assertEqual(_extract_md_section(text, "Bar"), "")

    def test_only_double_hash_matches(self):
        text = "### Foo\nsubheading body\n## Foo\nreal body\n"
        self.assertEqual(_extract_md_section(text, "Foo"), "real body")


class TestResolveRef(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            session = Path(td)
            ref = OpDataRef("agent_input", "ghost")
            self.assertEqual(resolve_ref(session, ref), "")

    def test_returns_full_text_when_section_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            session = Path(td)
            (session / "explorer_a_output.md").write_text(
                "## Heading\nbody\n", encoding="utf-8"
            )
            ref = OpDataRef("agent_output", "explorer_a")
            self.assertEqual(resolve_ref(session, ref), "## Heading\nbody\n")

    def test_returns_section_slice_when_section_set(self):
        with tempfile.TemporaryDirectory() as td:
            session = Path(td)
            (session / "explorer_a_input.md").write_text(
                "# Explorer Input\n\n"
                "## Exploration Mandate\n"
                "do this thing\n"
                "\n"
                "## Reference Files\n"
                "ignored\n",
                encoding="utf-8",
            )
            ref = OpDataRef(
                "agent_input", "explorer_a", section="Exploration Mandate"
            )
            self.assertEqual(resolve_ref(session, ref), "do this thing")


class TestListOpInputs(unittest.TestCase):
    def test_returns_first_agent_with_op_section(self):
        info = {"operation": "explore", "agents": ["a", "b", "c"]}
        refs = list_op_inputs(info)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].kind, "agent_input")
        self.assertEqual(refs[0].target, "a")
        self.assertEqual(refs[0].section, "Exploration Mandate")

    def test_section_per_operation(self):
        cases = {
            "explore":    "Exploration Mandate",
            "compare":    "Comparison Request",
            "synthesize": "Merge Rules",
            "bootstrap":  "Mandate",
        }
        for op, expected_section in cases.items():
            with self.subTest(op=op):
                info = {"operation": op, "agents": ["a"]}
                refs = list_op_inputs(info)
                self.assertEqual(len(refs), 1)
                self.assertEqual(refs[0].section, expected_section)

    def test_legacy_hybridize_operation_still_resolves(self):
        # Backward-compat (t807): in-flight sessions persist
        # operation: hybridize; it must still resolve to the Merge Rules
        # section, the same as the canonical "synthesize".
        legacy = list_op_inputs({"operation": "hybridize",
                                 "agents": ["synthesizer_001"]})
        current = list_op_inputs({"operation": "synthesize",
                                  "agents": ["synthesizer_001"]})
        self.assertEqual(legacy[0].section, "Merge Rules")
        self.assertEqual(legacy[0].section, current[0].section)

    def test_unknown_operation_section_is_none(self):
        info = {"operation": "weird_unknown_op", "agents": ["a"]}
        refs = list_op_inputs(info)
        self.assertEqual(len(refs), 1)
        self.assertIsNone(refs[0].section)

    def test_empty_agents_returns_empty_list(self):
        info = {"operation": "explore", "agents": []}
        self.assertEqual(list_op_inputs(info), [])

    def test_missing_agents_returns_empty_list(self):
        info = {"operation": "explore"}
        self.assertEqual(list_op_inputs(info), [])


class TestListOpOutputs(unittest.TestCase):
    def test_one_ref_per_agent(self):
        info = {"agents": ["a", "b", "c"]}
        refs = list_op_outputs(info)
        self.assertEqual([r.target for r in refs], ["a", "b", "c"])
        self.assertTrue(all(r.kind == "agent_output" for r in refs))

    def test_empty_agents(self):
        self.assertEqual(list_op_outputs({"agents": []}), [])

    def test_missing_agents_field(self):
        self.assertEqual(list_op_outputs({}), [])


class TestListOpLogs(unittest.TestCase):
    def test_one_ref_per_agent(self):
        info = {"agents": ["x", "y"]}
        refs = list_op_logs(info)
        self.assertEqual([r.target for r in refs], ["x", "y"])
        self.assertTrue(all(r.kind == "agent_log" for r in refs))

    def test_missing_agents_field(self):
        self.assertEqual(list_op_logs({}), [])


class TestListOpDefinition(unittest.TestCase):
    def test_includes_head_and_created(self):
        info = {
            "head_at_creation": "n003_a",
            "nodes_created": ["n004_b", "n005_c"],
        }
        refs = list_op_definition(info)
        self.assertEqual(
            [(r.kind, r.target) for r in refs],
            [
                ("node_metadata", "n003_a"),
                ("node_metadata", "n004_b"),
                ("node_metadata", "n005_c"),
            ],
        )

    def test_skips_empty_head(self):
        info = {"head_at_creation": None, "nodes_created": ["n004_b"]}
        refs = list_op_definition(info)
        self.assertEqual([r.target for r in refs], ["n004_b"])

    def test_skips_empty_nodes_created(self):
        info = {"head_at_creation": "n003_a", "nodes_created": []}
        refs = list_op_definition(info)
        self.assertEqual([r.target for r in refs], ["n003_a"])

    def test_missing_fields_returns_empty(self):
        self.assertEqual(list_op_definition({}), [])


class TestCanonicalOp(unittest.TestCase):
    """Backward-compat normalization of legacy operation names (t807)."""

    def test_legacy_hybridize_maps_to_synthesize(self):
        self.assertEqual(canonical_op("hybridize"), "synthesize")

    def test_canonical_synthesize_passes_through(self):
        self.assertEqual(canonical_op("synthesize"), "synthesize")

    def test_other_operations_pass_through(self):
        for op in ("explore", "compare", "bootstrap"):
            self.assertEqual(canonical_op(op), op)

    def test_unknown_value_passes_through(self):
        self.assertEqual(canonical_op("weird_unknown_op"), "weird_unknown_op")


if __name__ == "__main__":
    unittest.main()
