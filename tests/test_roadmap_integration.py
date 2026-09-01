"""End-to-end roadmap fixture: ORIGIN_FACT -> policy -> decide -> trail (t1569_5).

WHY THIS EXISTS SEPARATELY FROM THE UNIT TESTS. Units, a hand-authored trail
document and a live shape smoke can all pass while the real output is wrong: a
record-parser mismatch or an omitted ``data_tracked`` is invisible to every one
of them. This drives the WHOLE path in one pass -- real gatherer records, a real
batch map, real ``ORIGIN_FACT:`` rows, the real ``parallel_admission.decide``,
and the real trail encoder -- and asserts lane, confidence, caveats,
observations, relations and evidence TOGETHER on the same entries.

Two negative controls keep it non-vacuous. Each must change the result, and the
test asserts the change rather than assuming it.

Pure: no git, no subprocess, no filesystem. (The producer side -- that the real
collector emits records this path accepts -- is proven separately in
``tests/test_roadmap_origin_facts.py``, which does shell out.)

Run: ``python3 -m unittest tests.test_roadmap_integration -v``
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))

import parallel_admission as pa  # noqa: E402
import roadmap_policy as rp  # noqa: E402
import roadmap_premise as premise  # noqa: E402
import trail_schema  # noqa: E402

PROJECT = "aitasks"
NOW = 1_800_000_000
NOW_ORD = rp.day_ordinal("2026-08-31")
DAY = 86400

CANDIDATE = "%s#100" % PROJECT      # collides with the in-flight task
CLEAN = "%s#200" % PROJECT          # no overlap
INFLIGHT = "%s#900" % PROJECT

# The shared surface is a TASK-DATA path on purpose: it is the exact case the
# `data_tracked` control below turns on and off.
SHARED = "aitasks/metadata/profiles/fast.yaml"
DATA_TRACKED = {SHARED}


def member(task_id, rch, rga, created_at="2026-08-20 10:00",
           followup_kind="risk_mitigation"):
    ref = "%s#%s" % (PROJECT, task_id)
    return ["MEMBER:%s|Ready|medium|low|unknown||%s|aitasks/t%s_x.md"
            % (ref, followup_kind, task_id),
            "MEMBER_EXT:%s|%s|1500||%s|%s" % (ref, created_at, rch, rga)]


MEMBERS = member("100", "high", "low") + member("200", "low", "low")

ORIGIN_FACTS = [
    # t100's two origins DISAGREE -- the reduction must take the max.
    "ORIGIN_FACT:100|9001|exact|high|low|archived",
    "ORIGIN_FACT:100|9002|exact|low|low|archived",
    "ORIGIN_FACT:200|9003|topic|low|low|active",
]

INFLIGHT_LINES = [
    "INFLIGHT_PATH:%s|phantom|%s" % (INFLIGHT, SHARED),
    "INFLIGHT_PATH:%s|tracked|.aitask-scripts/other.py" % INFLIGHT,
]

BATCH_MAP = [
    "TASKFILES:100|%s" % SHARED,
    "TASKFILES:200|docs/unrelated.md",
    "STATUS:100|FILES",
    "STATUS:200|FILES",
    # The origin's LANDING is a code path. Its task-data commit at the same
    # instant is deliberately not one -- that is the distinction Step 1 turns on.
    "COMMIT:.aitask-scripts/landed.py|aaalanding|%d|9001" % (NOW - 40 * DAY),
    "COMMIT:%s|zzzmeta|%d|9001" % (SHARED, NOW - 40 * DAY),
    # ...and the shared file has since moved under another task.
    "COMMIT:%s|later|%d|777" % (SHARED, NOW - 2 * DAY),
    "COMMIT:docs/unrelated.md|other|%d|9003" % (NOW - 60 * DAY),
]

EVIDENCE = [{
    "evidence_id": "ev-checker",
    "source_type": "command_output",
    "ref": "aitask_parallel_admission.sh check --from origin "
           "--lock-freshness allow-cached",
    "observed_at": "2026-08-31T12:00Z",
    "summary": "parallel-admission verdicts over the candidate set",
}, {
    "evidence_id": "ev-gatherer",
    "source_type": "command_output",
    "ref": "aitask_trail_gather.sh snapshot --with-inflight",
    "observed_at": "2026-08-31T12:00Z",
    "summary": "in-flight and planned-surface facts",
}]

SCOPE = {"kind": "ad_hoc", "topics": ["%s#1500" % PROJECT]}
GENERATION = {
    "generated_at": "2026-08-31T12:00Z",
    "generator": {"agent_string": "claudecode/opus5",
                  "skill": "aitask-backlog-roadmap"},
    "input_digest": "53be6b59867b49ac",
    "inputs": [{"kind": "task_file", "ref": CANDIDATE}],
}
FRESHNESS = {"state": "current", "checked_at": "2026-08-31T12:00Z"}
NARRATIVE = {
    "problem_statement": "Auto-spawned follow-up work is never picked "
                         "proactively, so the backlog grows and goes stale.",
    "recommendation_summary": "An estimate over origin/topic evidence and "
                              "in-flight state as of the run. It reserves "
                              "nothing: no known conflict at check time.",
}


def run(data_tracked=DATA_TRACKED, origin_facts=None, members=None):
    """The real path, end to end, with nothing stubbed but the clock."""
    candidates = rp.parse_members(members or MEMBERS)
    origin_rows = rp.parse_origin_facts(origin_facts or ORIGIN_FACTS)

    surfaces = pa.surfaces_from_batch_map(BATCH_MAP)
    candidate_paths, admission, premises = {}, {}, {}

    for ref, candidate in candidates.items():
        surface = surfaces.get(candidate.task_id) or pa.Surface(
            ref=candidate.task_id, provenance="origin_derived",
            resolution="unknown_origin")
        # `--from origin` is a FIELD, not a subprocess flag.
        surface = pa.Surface(ref=surface.ref, provenance="origin_derived",
                             paths=surface.paths, resolution=surface.resolution,
                             quality=origin_rows.get(candidate.task_id,
                                                     [("", "unknown")])[0][1])
        candidate_paths[ref] = set(surface.paths)

        inflight_claims = [pa.InflightClaim(
            ref=INFLIGHT, sources=("lock",), task_status="Implementing",
            liveness="live", same_host=True, claim_at_s=NOW - 3600)]

        admission[ref] = pa.decide(pa.input_from_records(
            candidate_ref=candidate.task_id, candidate_surface=surface,
            inflight_lines=INFLIGHT_LINES, batch_map_lines=BATCH_MAP,
            inflight_claims=inflight_claims,
            # `--lock-freshness allow-cached` is a FIELD too, and is the default.
            locks=pa.LockEvidence(mode="allow-cached"),
            corpora=(pa.CorpusEvidence("code", "ok", 10),
                     pa.CorpusEvidence("data", "ok", 5)),
            data_tracked=data_tracked, now=NOW))

        origins = [row[0] for row in origin_rows.get(candidate.task_id, [])
                   if row[0]]
        premises[ref] = premise.check(origins, surface.paths, BATCH_MAP)

    inflight_paths = {p for s in pa.surfaces_from_inflight_records(
        INFLIGHT_LINES, data_tracked=data_tracked).values() for p in s.paths}

    return rp.build(candidates, origin_rows, admission, premises,
                    candidate_paths, inflight_paths, NOW_ORD)


def document_for(roadmap):
    return rp.to_trail(roadmap.entries, "trail-backlog-roadmap",
                       "Background-work roadmap", "%s#1500" % PROJECT,
                       SCOPE, GENERATION, FRESHNESS, NARRATIVE, EVIDENCE,
                       inflight_refs=[INFLIGHT])


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.roadmap = run()
        self.by_ref = {e.candidate.ref: e for e in self.roadmap.entries}

    def test_the_whole_path_agrees_on_one_entry(self):
        """Lane, classification, confidence, caveats and evidence together.

        Asserted on the SAME entry rather than as separate per-field tests: a
        parser mismatch that shifts one field usually leaves the others
        plausible, and only the joint assertion catches that.
        """
        entry = self.by_ref[CANDIDATE]
        self.assertEqual(entry.verdict, "CONFLICT")
        self.assertEqual((entry.lane, entry.classification),
                         (2, "coordination_only"))
        # Origins disagreed high/low -> the max, not the first.
        self.assertEqual(entry.risk_band, 3)
        self.assertEqual(entry.origin.rch, "high")
        self.assertTrue(any("origins disagree" in c for c in entry.caveats))
        # The shared file changed after the origin landed.
        self.assertEqual(entry.premise_decision, premise.ASK_STALE)
        # ASK_STALE caps confidence at low even though the origin is exact.
        self.assertEqual(entry.confidence, "low")
        self.assertIn("Risk band 3", entry.rationale)

    def test_the_clean_candidate_lands_in_the_safe_lane_hedged_by_quality(self):
        entry = self.by_ref[CLEAN]
        self.assertIn(entry.verdict, ("CLEAR", "CLEAR_CAVEATED"))
        self.assertEqual(entry.lane, 1)
        self.assertEqual(entry.classification, "core")
        # topic-quality origin: it may never read as exact.
        self.assertNotEqual(entry.confidence, "high")
        self.assertTrue(any("not an exact origin" in c for c in entry.caveats))

    def test_risk_outranks_the_conflicting_lane(self):
        """The high-risk task ranks first even though it is coordination-only:
        the lane is a lane, not a demotion."""
        self.assertEqual([e.candidate.ref for e in self.roadmap.entries],
                         [CANDIDATE, CLEAN])

    def test_the_emitted_document_validates_at_deep(self):
        document = document_for(self.roadmap)
        issues = trail_schema.validate_trail(document, expect_depth="deep")
        self.assertEqual([str(i) for i in issues], [])

    def test_the_document_carries_the_whole_encoding_contract(self):
        document = document_for(self.roadmap)
        self.assertEqual(document["rendering_hints"]["depth"], "deep")
        self.assertEqual([w["ordinal"] for w in document["waves"]], [1, 2])

        relation = document["relations"][0]
        self.assertEqual((relation["type"], relation["provenance"]),
                         ("coordinates_with", "advisory"))
        self.assertEqual((relation["from"], relation["to"]),
                         (CANDIDATE, INFLIGHT))

        kinds = {o["kind"] for o in document["observations"]}
        self.assertEqual(kinds, {"in_flight_conflict", "stale_premise"})
        for observation in document["observations"]:
            self.assertTrue(observation["evidence_refs"])
            for ref in observation["evidence_refs"]:
                self.assertIn(ref, {e["evidence_id"] for e in EVIDENCE})

    def test_no_output_anywhere_claims_safe_to_run_in_parallel(self):
        """The forbidden phrase. CLEAR observes; it never reserves."""
        blob = repr(document_for(self.roadmap)) + repr(self.roadmap.entries)
        self.assertNotIn("safe to run in parallel", blob)
        self.assertIn("no known conflict at check time", blob)

    def test_determinism_two_runs_are_byte_identical(self):
        first = document_for(run())
        second = document_for(run())
        self.assertEqual(first, second)


class NegativeControlTests(unittest.TestCase):
    """Each control must CHANGE the result, so the assertions above cannot pass
    vacuously."""

    def test_omitting_data_tracked_hides_the_collision(self):
        """`aitasks/` is a gitignored symlink on the code branch, so the
        gatherer marks every task-data path `phantom`. Without the set the
        shared profile YAML disappears and the CONFLICT silently becomes a
        clean verdict -- the exact upstream blind spot t1569_3 fixed, and one
        no unit test in this suite would notice."""
        with_set = run()
        without = run(data_tracked=None)
        self.assertEqual(
            {e.candidate.ref: e.verdict for e in with_set.entries}[CANDIDATE],
            "CONFLICT")
        self.assertNotEqual(
            {e.candidate.ref: e.verdict for e in without.entries}[CANDIDATE],
            "CONFLICT")
        self.assertNotEqual(document_for(with_set), document_for(without))

    def test_flipping_a_mixed_risk_pair_does_not_change_the_ranking(self):
        """Symmetry: `(high, low)` and `(low, high)` must rank identically."""
        flipped = [row.replace("|high|low|", "|low|high|")
                   for row in ORIGIN_FACTS]
        self.assertNotEqual(flipped, ORIGIN_FACTS)      # the edit really applied
        self.assertEqual([e.candidate.ref for e in run().entries],
                         [e.candidate.ref
                          for e in run(origin_facts=flipped).entries])

    def test_raising_an_axis_does_change_the_ranking(self):
        """The other half of the control: symmetry must not be indifference."""
        raised = [row.replace("ORIGIN_FACT:200|9003|topic|low|low|",
                              "ORIGIN_FACT:200|9003|topic|high|high|")
                  for row in ORIGIN_FACTS]
        self.assertNotEqual(raised, ORIGIN_FACTS)
        self.assertEqual([e.candidate.ref for e in run(origin_facts=raised).entries],
                         [CLEAN, CANDIDATE])

    def test_followup_kind_permutation_leaves_the_document_identical(self):
        permuted = member("100", "high", "low", followup_kind="docs_gap") + \
            member("200", "low", "low", followup_kind="carry_over")
        self.assertNotEqual(permuted, MEMBERS)
        base = document_for(run())
        other = document_for(run(members=permuted))
        # Only the display-only snapshot field may differ.
        for document in (base, other):
            for wave in document["waves"]:
                for entry in wave["entries"]:
                    entry["snapshot"].pop("followup_kind", None)
        self.assertEqual(base, other)


if __name__ == "__main__":
    unittest.main()
