"""Design-contract test for the Implementation Trail deliverables (t1210).

Protects the design artifacts — `aidocs/implementation_trail.schema.json` and
the fixtures in `aidocs/implementation_trail_examples/` — against structural
drift. This is NOT the future production parser/validator: it uses only the
Python standard library and checks the design contract, not full JSON-Schema
conformance. The schema/gatherer implementation task may adopt a real
validator and replace or extend these checks.

Run:  python3 -m unittest tests.test_implementation_trail_design -v
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "aidocs" / "implementation_trail.schema.json"
EXAMPLES_DIR = REPO_ROOT / "aidocs" / "implementation_trail_examples"

FIXTURE_NAMES = [
    "shadow_review_loop.json",
    "gate_framework.json",
    "cross_topic_multiple_trails.json",
]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class SchemaAndFixturesParse(unittest.TestCase):
    def test_schema_parses(self):
        schema = load_json(SCHEMA_PATH)
        self.assertEqual(schema["title"], "Implementation Trail")

    def test_all_fixtures_parse(self):
        for name in FIXTURE_NAMES:
            with self.subTest(fixture=name):
                doc = load_json(EXAMPLES_DIR / name)
                self.assertIsInstance(doc, dict)

    def test_no_unexpected_fixture_files(self):
        found = sorted(p.name for p in EXAMPLES_DIR.glob("*.json"))
        self.assertEqual(found, sorted(FIXTURE_NAMES))


class FixtureContract(unittest.TestCase):
    """Structural checks every fixture must satisfy."""

    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMA_PATH)
        cls.fixtures = {
            name: load_json(EXAMPLES_DIR / name) for name in FIXTURE_NAMES
        }
        defs = cls.schema["$defs"]
        cls.task_ref_re = re.compile(defs["task_ref"]["pattern"])
        cls.timestamp_re = re.compile(defs["timestamp"]["pattern"])
        cls.local_id_re = re.compile(defs["local_id"]["pattern"])
        cls.trail_id_re = re.compile(
            cls.schema["properties"]["trail_id"]["pattern"]
        )

    def each_fixture(self):
        for name, doc in self.fixtures.items():
            yield name, doc

    def test_schema_version_matches_schema_const(self):
        const = self.schema["properties"]["schema_version"]["const"]
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                self.assertEqual(doc["schema_version"], const)

    def test_required_root_keys_present(self):
        required = self.schema["required"]
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                for key in required:
                    self.assertIn(key, doc, f"missing required root key {key!r}")

    def test_no_root_keys_outside_schema(self):
        allowed = set(self.schema["properties"])
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                self.assertLessEqual(
                    set(doc), allowed,
                    f"unexpected root keys: {set(doc) - allowed}",
                )

    def test_trail_id_shape(self):
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                self.assertRegex(doc["trail_id"], self.trail_id_re)

    def test_local_ids_unique(self):
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                wave_ids = [w["wave_id"] for w in doc["waves"]]
                entry_ids = [
                    e["entry_id"] for w in doc["waves"] for e in w["entries"]
                ]
                evidence_ids = [ev["evidence_id"] for ev in doc["evidence"]]
                obs_ids = [
                    o["observation_id"] for o in doc.get("observations", [])
                ]
                for label, ids in (
                    ("wave_id", wave_ids),
                    ("entry_id", entry_ids),
                    ("evidence_id", evidence_ids),
                    ("observation_id", obs_ids),
                ):
                    self.assertEqual(
                        len(ids), len(set(ids)), f"duplicate {label} in {name}"
                    )
                    for i in ids:
                        self.assertRegex(i, self.local_id_re)

    def test_wave_ordinals_strictly_increasing(self):
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                ordinals = [w["ordinal"] for w in doc["waves"]]
                self.assertEqual(
                    ordinals, sorted(ordinals),
                    "waves out of ordinal order",
                )
                self.assertEqual(
                    len(ordinals), len(set(ordinals)),
                    "duplicate wave ordinals",
                )

    def test_entry_positions_strictly_increasing_per_wave(self):
        for name, doc in self.each_fixture():
            for wave in doc["waves"]:
                with self.subTest(fixture=name, wave=wave["wave_id"]):
                    positions = [e["position"] for e in wave["entries"]]
                    self.assertEqual(positions, sorted(positions))
                    self.assertEqual(len(positions), len(set(positions)))

    def test_entries_are_project_qualified_with_topic(self):
        for name, doc in self.each_fixture():
            for wave in doc["waves"]:
                for entry in wave["entries"]:
                    with self.subTest(fixture=name, entry=entry["entry_id"]):
                        self.assertRegex(entry["task"], self.task_ref_re)
                        self.assertRegex(entry["topic"], self.task_ref_re)
                        self.assertTrue(
                            entry["rationale"].strip(),
                            "entry rationale must be non-empty narrative",
                        )
                        self.assertIn(
                            entry["confidence"], ("high", "medium", "low")
                        )

    def test_narrative_is_first_class(self):
        """Trails are explained recommendations, not bare ranked lists."""
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                narrative = doc["narrative"]
                self.assertTrue(narrative["problem_statement"].strip())
                self.assertTrue(narrative["recommendation_summary"].strip())
                for wave in doc["waves"]:
                    self.assertTrue(
                        wave["purpose"].strip(),
                        f"wave {wave['wave_id']} missing purpose narrative",
                    )

    def test_evidence_refs_resolve(self):
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                evidence_ids = {ev["evidence_id"] for ev in doc["evidence"]}
                referrers = [
                    (e["entry_id"], e.get("evidence_refs", []))
                    for w in doc["waves"]
                    for e in w["entries"]
                ] + [
                    (o["observation_id"], o["evidence_refs"])
                    for o in doc.get("observations", [])
                ]
                for source_id, refs in referrers:
                    for ref in refs:
                        self.assertIn(
                            ref, evidence_ids,
                            f"{source_id} references unknown evidence {ref!r}",
                        )

    def test_relation_endpoints_resolve(self):
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                known = {
                    e["task"] for w in doc["waves"] for e in w["entries"]
                }
                known |= {x["task"] for x in doc.get("exclusions", [])}
                for obs in doc.get("observations", []):
                    known |= set(obs.get("affects", []))
                # Tasks named only as recorded `depends` snapshots are also
                # legitimate relation endpoints (facts mirrored from the DAG).
                for w in doc["waves"]:
                    for e in w["entries"]:
                        known |= set(e["snapshot"].get("depends", []))
                for rel in doc.get("relations", []):
                    for end in (rel["from"], rel["to"]):
                        self.assertRegex(end, self.task_ref_re)
                        self.assertIn(
                            end, known,
                            f"relation endpoint {end!r} not referenced "
                            f"anywhere else in {name}",
                        )
                    self.assertIn(rel["provenance"], ("fact", "advisory"))

    def test_timestamps_well_formed(self):
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                stamps = [
                    doc["generation"]["generated_at"],
                    doc["freshness"]["checked_at"],
                ] + [ev["observed_at"] for ev in doc["evidence"]]
                for ts in stamps:
                    self.assertRegex(ts, self.timestamp_re)

    def test_no_anchor_encoding(self):
        """Trail membership must never encode alternate topic anchors."""
        for name, doc in self.each_fixture():
            with self.subTest(fixture=name):
                def walk(node):
                    if isinstance(node, dict):
                        self.assertNotIn(
                            "anchor", node,
                            "trail documents must not carry anchor fields — "
                            "canonical topic membership lives in task "
                            "frontmatter only",
                        )
                        for v in node.values():
                            walk(v)
                    elif isinstance(node, list):
                        for v in node:
                            walk(v)

                walk(doc)


class ManualExampleFidelity(unittest.TestCase):
    """The two distilled manual analyses must retain the blocker /
    coordination / exclusion structure that motivated the feature."""

    @classmethod
    def setUpClass(cls):
        cls.shadow = load_json(EXAMPLES_DIR / "shadow_review_loop.json")
        cls.gate = load_json(EXAMPLES_DIR / "gate_framework.json")
        cls.cross = load_json(
            EXAMPLES_DIR / "cross_topic_multiple_trails.json"
        )

    @staticmethod
    def classifications(doc):
        return {
            e["classification"] for w in doc["waves"] for e in w["entries"]
        }

    def test_shadow_example_key_classes(self):
        cls = self.classifications(self.shadow)
        self.assertIn("hard_prerequisite", cls)  # true parser blocker
        self.assertIn("preferred_predecessor", cls)  # cheap verification bug
        self.assertIn("coordination_only", cls)  # t1118_4 overlap
        self.assertTrue(self.shadow["exclusions"])  # non-blocking work named

    def test_gate_example_key_classes(self):
        obs_kinds = {o["kind"] for o in self.gate["observations"]}
        # Discovered blockers outside the nominal topic:
        self.assertIn("baseline_risk", obs_kinds)  # red Python suite
        self.assertIn("stale_premise", obs_kinds)  # stale task premises
        self.assertIn("shared_surface_collision", obs_kinds)  # skill files
        self.assertGreaterEqual(len(self.gate["waves"]), 4)
        # Serialization wave is coordination, not dependency:
        self.assertIn("coordination_only", self.classifications(self.gate))

    def test_gate_example_models_staleness(self):
        fresh = self.gate["freshness"]
        self.assertEqual(fresh["state"], "stale")
        codes = {r["code"] for r in fresh["drift_reasons"]}
        self.assertIn("task_completed", codes)
        self.assertIn("new_related_task", codes)

    def test_hard_relations_are_facts(self):
        for doc in (self.shadow, self.gate, self.cross):
            for rel in doc.get("relations", []):
                if rel["type"] == "hard_depends":
                    self.assertEqual(
                        rel["provenance"], "fact",
                        "hard_depends must mirror recorded DAG facts",
                    )


class CrossTopicMultipleTrails(unittest.TestCase):
    """One task may be referenced by several trail identities while keeping
    exactly one canonical topic."""

    @classmethod
    def setUpClass(cls):
        cls.shadow = load_json(EXAMPLES_DIR / "shadow_review_loop.json")
        cls.gate = load_json(EXAMPLES_DIR / "gate_framework.json")
        cls.cross = load_json(
            EXAMPLES_DIR / "cross_topic_multiple_trails.json"
        )

    @staticmethod
    def entry_topics(doc):
        return {
            e["task"]: e["topic"] for w in doc["waves"] for e in w["entries"]
        }

    def test_distinct_trail_identities(self):
        ids = {
            self.shadow["trail_id"],
            self.gate["trail_id"],
            self.cross["trail_id"],
        }
        self.assertEqual(len(ids), 3)

    def test_shared_members_keep_one_canonical_topic(self):
        cross_topics = self.entry_topics(self.cross)
        overlaps = 0
        for other in (self.shadow, self.gate):
            other_topics = self.entry_topics(other)
            shared = set(cross_topics) & set(other_topics)
            for task in shared:
                overlaps += 1
                self.assertEqual(
                    cross_topics[task], other_topics[task],
                    f"{task} must keep the same canonical topic in every "
                    "trail that references it",
                )
        self.assertGreaterEqual(
            overlaps, 2,
            "the cross-topic fixture must actually overlap both manual "
            "examples to demonstrate multiple-trail membership",
        )

    def test_cross_topic_scope_spans_topics(self):
        self.assertEqual(self.cross["scope"]["kind"], "multi_topic")
        self.assertGreaterEqual(len(self.cross["scope"]["topics"]), 2)
        entry_topics = set(self.entry_topics(self.cross).values())
        self.assertGreaterEqual(
            len(entry_topics), 2,
            "cross-topic trail must reference members of at least two topics",
        )


if __name__ == "__main__":
    unittest.main()
