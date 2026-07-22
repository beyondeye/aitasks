"""Unit tests for the trail schema library (t1210_1).

Production check for .aitask-scripts/lib/trail_schema.py: the schema-driven
structural interpreter, the semantic checks, the RFC par.8.1 input-snapshot
normalization/digest, and the validate CLI. Fixtures under
aidocs/implementation_trail_examples/ are the valid corpus; every mutation
operates on a deep copy (in-memory or under a tempdir) -- the aidocs fixtures
are never modified. The design-contract test
(tests/test_implementation_trail_design.py) remains the aidocs-drift guard.

Run:  python3 -m unittest tests.test_trail_schema -v
"""

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB_DIR))

import trail_schema  # noqa: E402
from trail_schema import (  # noqa: E402
    TrailValidationError,
    canonical_input_snapshot,
    input_digest,
    load_schema,
    load_trail,
    validate_trail,
)

AIDOCS_SCHEMA = REPO_ROOT / "aidocs" / "implementation_trail.schema.json"
LIB_SCHEMA = LIB_DIR / "implementation_trail.schema.json"
EXAMPLES_DIR = REPO_ROOT / "aidocs" / "implementation_trail_examples"
FIXTURE_NAMES = [
    "shadow_review_loop.json",
    "gate_framework.json",
    "cross_topic_multiple_trails.json",
]


def fixture(name):
    with open(EXAMPLES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def issues_for(doc):
    """validate_trail issues for an in-memory (usually mutated) document."""
    return validate_trail(doc)


def rules(issues):
    return {i.rule for i in issues}


class SchemaCopyDrift(unittest.TestCase):
    def test_lib_schema_byte_identical_to_aidocs_contract(self):
        self.assertEqual(
            LIB_SCHEMA.read_bytes(), AIDOCS_SCHEMA.read_bytes(),
            "the shipped lib schema copy drifted from the pinned aidocs "
            "contract -- edit both files together")


class ValidFixtures(unittest.TestCase):
    def test_fixtures_load_from_path_and_bytes(self):
        for name in FIXTURE_NAMES:
            path = EXAMPLES_DIR / name
            with self.subTest(fixture=name, source="path"):
                doc = load_trail(path)
                self.assertIn("trail_id", doc)
            with self.subTest(fixture=name, source="bytes"):
                doc = load_trail(path.read_bytes())
                self.assertIn("trail_id", doc)

    def test_fixtures_have_no_issues(self):
        for name in FIXTURE_NAMES:
            with self.subTest(fixture=name):
                self.assertEqual(issues_for(fixture(name)), [])


class InterpreterSemantics(unittest.TestCase):
    """Pinned JSON-Schema-subset semantics (plan decision 2)."""

    def test_rendering_hints_bool_value_is_valid(self):
        doc = fixture("shadow_review_loop.json")
        doc["rendering_hints"] = {"collapse_landed": True, "badge": "W",
                                  "max_rows": 5}
        self.assertEqual(issues_for(doc), [])

    def test_rendering_hints_object_value_is_invalid(self):
        doc = fixture("shadow_review_loop.json")
        doc["rendering_hints"] = {"nested": {"no": "objects"}}
        found = issues_for(doc)
        self.assertIn("type", rules(found))
        self.assertTrue(any(i.path.endswith("rendering_hints.nested")
                            for i in found))

    def test_rendering_hints_array_value_is_invalid(self):
        doc = fixture("shadow_review_loop.json")
        doc["rendering_hints"] = {"list": [1, 2]}
        self.assertIn("type", rules(issues_for(doc)))

    def test_project_revision_non_string_value_is_invalid(self):
        doc = fixture("cross_topic_multiple_trails.json")
        doc["generation"]["project_revision"]["aitasks"] = 12345
        found = issues_for(doc)
        self.assertIn("type", rules(found))
        self.assertTrue(any("project_revision.aitasks" in i.path
                            for i in found))

    def test_boolean_is_not_an_integer(self):
        doc = fixture("cross_topic_multiple_trails.json")
        doc["waves"][0]["ordinal"] = True
        self.assertIn("type", rules(issues_for(doc)))

    def test_duplicate_topics_rejected_by_unique_items(self):
        doc = fixture("cross_topic_multiple_trails.json")
        doc["scope"]["topics"].append(doc["scope"]["topics"][0])
        self.assertIn("uniqueItems", rules(issues_for(doc)))

    def test_unknown_keyword_tripwire_fires(self):
        schema = load_schema()
        test_schema = copy.deepcopy(schema)
        test_schema["properties"]["title"]["patternProperties"] = {}
        doc = fixture("shadow_review_loop.json")
        with self.assertRaises(RuntimeError):
            validate_trail(doc, test_schema)


class StructuralNegativeControls(unittest.TestCase):
    """One mutation per structural rule; each must fail with the named rule."""

    def assert_rule(self, doc, rule, path_fragment=None):
        found = issues_for(doc)
        self.assertIn(rule, rules(found),
                      "expected rule %r, got %s" % (rule, found))
        if path_fragment is not None:
            self.assertTrue(
                any(path_fragment in i.path for i in found
                    if i.rule == rule),
                "no %r issue at a path containing %r: %s"
                % (rule, path_fragment, found))

    def test_unknown_root_key(self):
        doc = fixture("shadow_review_loop.json")
        doc["surprise"] = 1
        self.assert_rule(doc, "additionalProperties")

    def test_missing_required_root_key(self):
        doc = fixture("shadow_review_loop.json")
        del doc["narrative"]
        self.assert_rule(doc, "required")

    def test_wrong_schema_version(self):
        doc = fixture("shadow_review_loop.json")
        doc["schema_version"] = "2.0.0"
        self.assert_rule(doc, "const", "schema_version")

    def test_bad_trail_id(self):
        doc = fixture("shadow_review_loop.json")
        doc["trail_id"] = "not-a-trail-id!"
        self.assert_rule(doc, "pattern", "trail_id")

    def test_bad_task_ref(self):
        doc = fixture("shadow_review_loop.json")
        doc["waves"][0]["entries"][0]["task"] = "t1208"  # missing project#
        self.assert_rule(doc, "pattern", "task")

    def test_bad_timestamp(self):
        doc = fixture("shadow_review_loop.json")
        doc["generation"]["generated_at"] = "yesterday"
        self.assert_rule(doc, "pattern", "generated_at")

    def test_bad_local_id(self):
        doc = fixture("shadow_review_loop.json")
        doc["waves"][0]["wave_id"] = "Wave One"
        self.assert_rule(doc, "pattern", "wave_id")

    def test_bad_classification_enum(self):
        doc = fixture("shadow_review_loop.json")
        doc["waves"][0]["entries"][0]["classification"] = "mandatory"
        self.assert_rule(doc, "enum", "classification")

    def test_empty_rationale(self):
        doc = fixture("shadow_review_loop.json")
        doc["waves"][0]["entries"][0]["rationale"] = ""
        self.assert_rule(doc, "minLength", "rationale")

    def test_unknown_nested_key_at_entry_level(self):
        doc = fixture("shadow_review_loop.json")
        doc["waves"][0]["entries"][0]["estimate_days"] = 3
        self.assert_rule(doc, "additionalProperties")

    def test_invalid_json_bytes(self):
        with self.assertRaises(TrailValidationError) as ctx:
            load_trail(b"{not json")
        self.assertEqual(ctx.exception.issues[0].rule, "json")

    def test_nan_infinity_payload_rejected_at_parse(self):
        doc = fixture("shadow_review_loop.json")
        for literal in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(literal=repr(literal)):
                doc["rendering_hints"] = {"weight": literal}
                payload = json.dumps(doc).encode("utf-8")  # emits NaN etc.
                with self.assertRaises(TrailValidationError) as ctx:
                    load_trail(payload)
                self.assertEqual(ctx.exception.issues[0].rule, "json")

    def test_in_memory_nan_rejected_by_number_type(self):
        doc = fixture("shadow_review_loop.json")
        doc["rendering_hints"] = {"weight": float("nan")}
        self.assertIn("type", rules(issues_for(doc)))

    def test_non_dict_root(self):
        found = validate_trail([1, 2, 3])
        self.assertEqual([i.rule for i in found], ["type"])

    def test_unreadable_path(self):
        with self.assertRaises(TrailValidationError) as ctx:
            load_trail("/nonexistent/trail.json")
        self.assertEqual(ctx.exception.issues[0].rule, "io")


class SemanticNegativeControls(unittest.TestCase):
    def assert_rule(self, doc, rule):
        found = issues_for(doc)
        self.assertIn(rule, rules(found),
                      "expected rule %r, got %s" % (rule, found))

    def test_duplicate_wave_ordinal(self):
        doc = fixture("gate_framework.json")
        doc["waves"][1]["ordinal"] = doc["waves"][0]["ordinal"]
        self.assert_rule(doc, "wave_ordinal")

    def test_decreasing_wave_ordinal(self):
        doc = fixture("gate_framework.json")
        doc["waves"][1]["ordinal"] = doc["waves"][0]["ordinal"] - 1
        found = issues_for(doc)
        # ordinal minimum is 1; wave 0 has ordinal 1, so 0 also violates
        # `minimum` -- the strictness rule must be reported regardless.
        self.assertIn("wave_ordinal", rules(found))

    def test_duplicate_entry_position(self):
        doc = fixture("cross_topic_multiple_trails.json")
        doc["waves"][0]["entries"][1]["position"] = \
            doc["waves"][0]["entries"][0]["position"]
        self.assert_rule(doc, "entry_position")

    def test_duplicate_entry_id(self):
        doc = fixture("cross_topic_multiple_trails.json")
        doc["waves"][0]["entries"][1]["entry_id"] = \
            doc["waves"][0]["entries"][0]["entry_id"]
        self.assert_rule(doc, "duplicate_local_id")

    def test_unresolved_evidence_ref(self):
        doc = fixture("shadow_review_loop.json")
        doc["waves"][0]["entries"][0]["evidence_refs"] = ["ev-ghost"]
        self.assert_rule(doc, "evidence_ref")

    def test_unresolved_relation_endpoint(self):
        doc = fixture("cross_topic_multiple_trails.json")
        doc["relations"].append({
            "from": "aitasks#9999", "to": "aitasks#1187",
            "type": "informs", "provenance": "advisory"})
        self.assert_rule(doc, "relation_endpoint")

    def test_hard_depends_advisory_provenance(self):
        doc = fixture("gate_framework.json")
        hard = [r for r in doc["relations"] if r["type"] == "hard_depends"]
        self.assertTrue(hard, "fixture must contain a hard_depends edge")
        hard[0]["provenance"] = "advisory"
        self.assert_rule(doc, "hard_depends_fact")

    def test_hard_depends_mirror_violation(self):
        doc = fixture("cross_topic_multiple_trails.json")
        # Both endpoints are known entries, but neither entry's recorded
        # depends contains the other -> the fact claim is checkable and false.
        doc["relations"].append({
            "from": "aitasks#1183", "to": "aitasks#1187",
            "type": "hard_depends", "provenance": "fact"})
        self.assert_rule(doc, "hard_depends_mirror")

    def test_hard_depends_unverifiable_endpoint_is_accepted(self):
        doc = fixture("gate_framework.json")
        hard = [r for r in doc["relations"] if r["type"] == "hard_depends"]
        from_ref = hard[0]["from"]
        entries = {e["task"] for w in doc["waves"] for e in w["entries"]}
        # gate_framework's first hard edge points from a non-entry task; a
        # hard edge INTO it (to = non-entry) has no snapshot to check against
        # and must be skipped, not rejected (documented limitation).
        self.assertNotIn(from_ref, entries)
        doc["relations"].append({
            "from": "aitasks#1183", "to": from_ref,
            "type": "hard_depends", "provenance": "fact"})
        self.assertEqual(issues_for(doc), [])

    def test_anchor_key_under_rendering_hints(self):
        doc = fixture("shadow_review_loop.json")
        doc["rendering_hints"] = {"anchor": "aitasks#986"}
        self.assert_rule(doc, "no_anchor")


class MalformedShapeRobustness(unittest.TestCase):
    """Untrusted-JSON shapes must produce issues, never crashes, and must
    not mask independent errors elsewhere (plan decision 3)."""

    def test_waves_as_object(self):
        doc = fixture("shadow_review_loop.json")
        doc["waves"] = {}
        found = issues_for(doc)  # must not raise TypeError
        self.assertTrue(any(i.rule == "type" and "waves" in i.path
                            for i in found))

    def test_relations_with_null_member(self):
        doc = fixture("shadow_review_loop.json")
        doc["relations"] = [None]
        found = issues_for(doc)
        self.assertTrue(any(i.rule == "type" and "relations" in i.path
                            for i in found))

    def test_scalar_snapshot(self):
        doc = fixture("shadow_review_loop.json")
        doc["waves"][0]["entries"][0]["snapshot"] = "Ready"
        found = issues_for(doc)
        self.assertTrue(any(i.rule == "type" and "snapshot" in i.path
                            for i in found))

    def test_malformed_branch_does_not_mask_independent_error(self):
        doc = fixture("gate_framework.json")
        doc["waves"][0]["entries"][0]["snapshot"] = "Ready"   # malformed
        doc["waves"][1]["entries"][0]["evidence_refs"] = ["ev-ghost"]
        found = issues_for(doc)
        self.assertTrue(any(i.rule == "type" and "snapshot" in i.path
                            for i in found))
        self.assertIn("evidence_ref", rules(found))

    def test_multiple_structural_issues_collected_in_one_raise(self):
        doc = fixture("shadow_review_loop.json")
        doc["surprise"] = 1
        doc["trail_id"] = "BAD ID"
        with self.assertRaises(TrailValidationError) as ctx:
            load_trail(json.dumps(doc).encode("utf-8"))
        self.assertLessEqual({"additionalProperties", "pattern"},
                             rules(ctx.exception.issues))


class DigestContract(unittest.TestCase):
    """RFC par.8.1 normalization (plan decision 4)."""

    @staticmethod
    def sample_inputs():
        return [
            {"ref": "aitasks#1210_1", "kind": "task_file", "exists": True,
             "status": "Ready", "depends": ["aitasks#1210", "aitasks#1209"],
             "gates_pending": ["risk_evaluated"]},
            {"ref": "aiplans/p1210/p1210_1.md", "kind": "plan_file",
             "exists": True, "content_hash": "abc123"},
            {"ref": "board state snapshot", "kind": "board_state",
             "exists": True, "content_hash": "def456"},
            {"ref": "aitasks#404", "kind": "task_file", "exists": False},
        ]

    def test_deterministic_under_permutation(self):
        base = self.sample_inputs()
        reordered = [base[3], base[1], base[0], base[2]]
        deps_swapped = copy.deepcopy(base)
        deps_swapped[0]["depends"] = list(reversed(deps_swapped[0]["depends"]))
        key_order_changed = copy.deepcopy(base)
        rec = key_order_changed[0]
        key_order_changed[0] = {k: rec[k] for k in reversed(list(rec))}
        expected = input_digest(base)
        for variant in (reordered, deps_swapped, key_order_changed):
            self.assertEqual(input_digest(variant), expected)

    def test_known_answer_canonical_bytes(self):
        """Pins NORMALIZATION_VERSION and the exact record shape: any change
        to the canonical form must show up here as a deliberate edit."""
        inputs = [
            {"ref": "aitasks#1", "kind": "task_file", "exists": True,
             "status": "Ready", "depends": ["aitasks#2"],
             "gates_pending": []},
            {"ref": "p1.md", "kind": "plan_file", "exists": True,
             "content_hash": "aa"},
        ]
        expected = (
            b'{"inputs":['
            b'{"content_hash":"aa","exists":true,"kind":"plan_file",'
            b'"ref":"p1.md"},'
            b'{"depends":["aitasks#2"],"exists":true,"gates_pending":[],'
            b'"kind":"task_file","ref":"aitasks#1","status":"Ready"}],'
            b'"normalization_version":"1.0.0"}'
        )
        self.assertEqual(canonical_input_snapshot(inputs), expected)

    def test_sensitivity(self):
        base = self.sample_inputs()
        expected = input_digest(base)
        status_flip = copy.deepcopy(base)
        status_flip[0]["status"] = "Implementing"
        gates_change = copy.deepcopy(base)
        gates_change[0]["gates_pending"] = []
        exists_flip = copy.deepcopy(base)
        exists_flip[3] = {"ref": "aitasks#404", "kind": "task_file",
                          "exists": True, "status": "Ready", "depends": [],
                          "gates_pending": []}
        removed = base[:-1]
        added = base + [{"ref": "extra.md", "kind": "plan_file",
                         "exists": True, "content_hash": "ff"}]
        for variant in (status_flip, gates_change, exists_flip,
                        removed, added):
            self.assertNotEqual(input_digest(variant), expected)

    def test_per_kind_fail_closed(self):
        cases = [
            ("unknown_key",
             {"ref": "aitasks#1", "kind": "task_file", "exists": True,
              "status": "Ready", "depends": [], "gates_pending": [],
              "boardidx": 50}),
            ("forbidden_field",
             {"ref": "aitasks#1", "kind": "task_file", "exists": True,
              "status": "Ready", "depends": [], "gates_pending": [],
              "content_hash": "aa"}),
            ("forbidden_field",
             {"ref": "p.md", "kind": "plan_file", "exists": True,
              "content_hash": "aa", "status": "Ready"}),
            ("missing_field",
             {"ref": "p.md", "kind": "plan_file", "exists": True}),
            ("forbidden_field",
             {"ref": "b", "kind": "board_state", "exists": True,
              "content_hash": "aa", "depends": []}),
            ("forbidden_field",
             {"ref": "aitasks#1", "kind": "task_file", "exists": False,
              "status": "Ready"}),
            # Forbidden field present as null: presence is presence.
            ("forbidden_field",
             {"ref": "p.md", "kind": "plan_file", "exists": True,
              "content_hash": "aa", "status": None}),
            ("exists",
             {"ref": "aitasks#1", "kind": "task_file", "exists": "yes",
              "status": "Ready", "depends": [], "gates_pending": []}),
            ("kind",
             {"ref": "aitasks#1", "kind": "task", "exists": True,
              "status": "Ready", "depends": [], "gates_pending": []}),
            ("ref", {"ref": "", "kind": "other", "exists": True,
                     "content_hash": "aa"}),
            ("type", "not-a-record"),
        ]
        for expected_rule, record in cases:
            with self.subTest(rule=expected_rule, record=record):
                with self.assertRaises(TrailValidationError) as ctx:
                    canonical_input_snapshot([record])
                self.assertIn(expected_rule, rules(ctx.exception.issues))

    def test_duplicate_set_members_fail_closed(self):
        """depends / gates_pending are sets: ["g"] and ["g","g"] must never
        hash differently -- duplicates are a hard error, not a dedup."""
        for field, dupes in (("gates_pending", ["risk", "risk"]),
                             ("depends", ["aitasks#2", "aitasks#2"])):
            record = {"ref": "aitasks#1", "kind": "task_file", "exists": True,
                      "status": "Ready", "depends": [], "gates_pending": []}
            record[field] = dupes
            with self.subTest(field=field):
                with self.assertRaises(TrailValidationError) as ctx:
                    canonical_input_snapshot([record])
                self.assertIn("duplicate_member", rules(ctx.exception.issues))

    def test_duplicate_kind_ref_pair(self):
        record = {"ref": "aitasks#1", "kind": "task_file", "exists": True,
                  "status": "Ready", "depends": [], "gates_pending": []}
        with self.assertRaises(TrailValidationError) as ctx:
            canonical_input_snapshot([record, dict(record)])
        self.assertIn("duplicate_input", rules(ctx.exception.issues))

    def test_digest_matches_schema_pattern(self):
        schema = load_schema()
        pattern = schema["properties"]["generation"]["properties"][
            "input_digest"]["pattern"]
        self.assertRegex(input_digest(self.sample_inputs()),
                         re.compile(pattern))


class CliValidate(unittest.TestCase):
    SCRIPT = LIB_DIR / "trail_schema.py"

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), *args],
            capture_output=True, text=True, cwd=REPO_ROOT)

    def test_valid_fixture_exits_zero(self):
        result = self.run_cli(
            "validate", str(EXAMPLES_DIR / "shadow_review_loop.json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("VALID:trail-"))

    def test_mutated_copy_exits_one(self):
        doc = fixture("shadow_review_loop.json")
        del doc["evidence"]
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            result = self.run_cli("validate", bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("INVALID:", result.stdout)
        self.assertIn("required", result.stdout)

    def test_nan_payload_exits_one(self):
        doc = fixture("shadow_review_loop.json")
        doc["rendering_hints"] = {"weight": float("nan")}
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "nan.json")
            with open(bad, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)  # writes the non-JSON literal NaN
            result = self.run_cli("validate", bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("INVALID:$|json|", result.stdout)

    def test_usage_error_exits_two(self):
        self.assertEqual(self.run_cli("frobnicate").returncode, 2)


if __name__ == "__main__":
    unittest.main()
