"""Roadmap scoring, lanes, freshness and trail encoding (t1569_5).

Pure-core tests: no git, no subprocess, no filesystem. Every input is the
already-materialised text the roadmap actually consumes -- gatherer records,
batch-map rows and ``ORIGIN_FACT:`` rows -- which is exactly the shape t1569_6's
skill will hand over.

Run: ``python3 -m unittest tests.test_roadmap_policy -v``
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))

import parallel_admission as pa  # noqa: E402
import parallel_admission_vocab as vocab  # noqa: E402
import roadmap_policy as rp  # noqa: E402
import roadmap_premise as premise  # noqa: E402
import trail_schema  # noqa: E402

DAY = 86400
NOW_ORD = rp.day_ordinal("2026-08-31")
PROJECT = "aitasks"


# --- fixture builders -------------------------------------------------------

def member(task_id, status="Ready", priority="medium", effort="low",
           boardcol="unknown", labels="", followup_kind="risk_mitigation",
           path=None, created_at="2026-08-01 10:00", anchor="",
           verifies="", rch="unknown", rga="unknown"):
    """The two gatherer records for one member, with the REAL sentinels.

    The gatherer writes `unknown` (not `-`) for an absent optional value; a test
    that used `-` here would pass while production data still broke.
    """
    ref = "%s#%s" % (PROJECT, task_id)
    return [
        "MEMBER:%s|%s|%s|%s|%s|%s|%s|%s"
        % (ref, status, priority, effort, boardcol, labels, followup_kind,
           path or "aitasks/t%s_x.md" % task_id),
        "MEMBER_EXT:%s|%s|%s|%s|%s|%s"
        % (ref, created_at, anchor, verifies, rch, rga),
    ]


def origin_fact(task_id, origin, quality="exact", rch="-", rga="-",
                source="archived"):
    return "ORIGIN_FACT:" + "|".join(
        vocab.encode_path(f) for f in
        (task_id, origin, quality, rch, rga, source))


def admission(verdict, overlaps=()):
    """An AdmissionResult with the verdict and OVERLAP rows a real run emits."""
    lines = tuple("OVERLAP:%s|specific|1|%s" % (ref, path)
                  for ref, path in overlaps) + ("VERDICT:%s" % verdict,)
    return pa.AdmissionResult(verdict=verdict, lines=lines)


def premise_result(decision, changed=(), unknown=()):
    return premise.PremiseResult(
        decision=decision, baseline=premise.Baseline(sha="abc", committed_at=1),
        changed=tuple(changed), unknown=tuple(unknown),
        lines=("DECISION:%s" % decision,))


EVIDENCE = [{
    "evidence_id": "ev-checker",
    "source_type": "command_output",
    "ref": "aitask_parallel_admission.sh check --from origin",
    "observed_at": "2026-08-31T12:00Z",
    "summary": "parallel-admission verdicts for every candidate",
}]

SCOPE = {"kind": "ad_hoc", "topics": ["%s#1569" % PROJECT]}
GENERATION = {
    "generated_at": "2026-08-31T12:00Z",
    "generator": {"agent_string": "claudecode/opus5",
                  "skill": "aitask-backlog-roadmap"},
    "input_digest": "53be6b59867b49ac",
    "inputs": [{"kind": "task_file", "ref": "%s#100" % PROJECT}],
}
FRESHNESS = {"state": "current", "checked_at": "2026-08-31T12:00Z"}
NARRATIVE = {
    "problem_statement": "Auto-spawned follow-up work is never picked proactively.",
    "recommendation_summary": "An estimate — no known conflict at check time; "
                              "it reserves nothing.",
}


def build_roadmap(members, origin_lines, verdicts, premises=None,
                  candidate_paths=None, inflight_paths=()):
    candidates = rp.parse_members(members)
    rows = rp.parse_origin_facts(origin_lines)
    return rp.build(candidates, rows,
                    {r: admission(v) if isinstance(v, str) else v
                     for r, v in verdicts.items()},
                    premises or {}, candidate_paths or {}, inflight_paths,
                    NOW_ORD)


# --- risk -------------------------------------------------------------------

class RiskAxisTests(unittest.TestCase):
    """The combination rule, row by row.

    The symmetric pair is the discriminating case: an implementation that reads
    only `risk_code_health` passes every same-value row and fails exactly there.
    """

    CASES = [
        ("high", "low", 3, 1),
        ("low", "high", 3, 1),
        ("high", "high", 3, 2),
        ("medium", None, 2, 1),
        ("low", None, 1, 1),
        (None, None, 1, 2),
        ("low", "low", 0, 2),
    ]

    def test_combination_table(self):
        for rch, rga, band, axes in self.CASES:
            with self.subTest(rch=rch, rga=rga):
                self.assertEqual(rp.combine_risk(rch, rga), (band, axes))

    def test_symmetry(self):
        for rch, rga, _, _ in self.CASES:
            with self.subTest(rch=rch, rga=rga):
                self.assertEqual(rp.combine_risk(rch, rga),
                                 rp.combine_risk(rga, rch))

    def test_monotone_raising_an_axis_never_lowers_the_band(self):
        order = ["low", None, "medium", "high"]
        for i in range(len(order) - 1):
            lower = rp.combine_risk(order[i], "low")[0]
            higher = rp.combine_risk(order[i + 1], "low")[0]
            self.assertLess(lower, higher)

    def test_unknown_sits_between_medium_and_low(self):
        self.assertLess(rp.axis_band("low"), rp.axis_band(None))
        self.assertLess(rp.axis_band(None), rp.axis_band("medium"))

    def test_sentinels_are_absent_not_data(self):
        for sentinel in ("", "-", "unknown", "invalid"):
            with self.subTest(sentinel=sentinel):
                self.assertEqual(rp.axis_band(sentinel), rp.axis_band(None))

    def test_an_undeclared_level_raises_rather_than_failing_open(self):
        with self.assertRaises(vocab.VocabularyError):
            rp.axis_band("critical")


# --- multi-origin reduction -------------------------------------------------

class MultiOriginTests(unittest.TestCase):
    """25 of 89 exact follow-ups carry >1 origin; 13 disagree on a level.

    A "first origin wins" implementation passes every single-origin test and
    fails the reorder assertion below.
    """

    ROWS = [origin_fact("1064", "1018_1", rch="medium", rga="low"),
            origin_fact("1064", "1018_2", rch="low", rga="low"),
            origin_fact("1064", "1018_3", rch="low", rga="low")]

    def _reduce(self, lines):
        return rp.reduce_origin_facts(
            rp.parse_origin_facts(lines)["1064"])

    def test_reduction_is_the_max_not_the_first(self):
        facts = self._reduce(self.ROWS)
        self.assertEqual(facts.rch, "medium")
        self.assertEqual(rp.combine_risk(facts.rch, facts.rga)[0], 2)

    def test_reordering_the_origins_is_byte_identical(self):
        forward = self._reduce(self.ROWS)
        backward = self._reduce(list(reversed(self.ROWS)))
        self.assertEqual(forward, backward)

    def test_disagreement_is_reported_and_the_setter_named(self):
        facts = self._reduce(self.ROWS)
        self.assertIn("risk_code_health", facts.disagreeing_axes)
        self.assertEqual(facts.setter, "1018_1")

    def test_both_axes_can_disagree(self):
        rows = [origin_fact("1064", "a1", rch="high", rga="low"),
                origin_fact("1064", "a2", rch="low", rga="high")]
        facts = rp.reduce_origin_facts(rp.parse_origin_facts(rows)["1064"])
        self.assertEqual((facts.rch, facts.rga), ("high", "high"))
        self.assertEqual(sorted(facts.disagreeing_axes),
                         ["risk_code_health", "risk_goal_achievement"])

    def test_an_absent_origin_contributes_unknown_never_zero(self):
        rows = [origin_fact("1064", "a1", rch="low", rga="low"),
                origin_fact("1064", "a2", rch="-", rga="-", source="absent")]
        facts = rp.reduce_origin_facts(rp.parse_origin_facts(rows)["1064"])
        self.assertEqual(facts.rch, None)                # the unknown band
        self.assertEqual(rp.axis_band(facts.rch), rp.AXIS_BAND[None])
        self.assertEqual(facts.absent_origins, ("a2",))

    def test_mixed_sources_render_as_mixed(self):
        rows = [origin_fact("1064", "a1", source="active"),
                origin_fact("1064", "a2", source="archived")]
        facts = rp.reduce_origin_facts(rp.parse_origin_facts(rows)["1064"])
        self.assertEqual(facts.provenance, "mixed")

    def test_uniform_sources_render_as_themselves(self):
        for source in ("active", "archived", "absent"):
            rows = [origin_fact("1064", "a1", source=source)]
            facts = rp.reduce_origin_facts(rp.parse_origin_facts(rows)["1064"])
            self.assertEqual(facts.provenance, source)

    def test_the_pre_reduction_values_survive_the_max(self):
        """A `max` a human cannot audit is a number they cannot override."""
        facts = self._reduce(self.ROWS)
        self.assertEqual(facts.per_origin,
                         (("1018_1", "medium", "low"),
                          ("1018_2", "low", "low"),
                          ("1018_3", "low", "low")))

    def test_the_tasks_own_axis_participates(self):
        """The signal is "on the task OR its origin", so both are in the max."""
        rows = [origin_fact("1064", "a1", rch="low", rga="low")]
        facts = rp.reduce_origin_facts(
            rp.parse_origin_facts(rows)["1064"], own_code_health="high")
        self.assertEqual(facts.rch, "high")


# --- confidence -------------------------------------------------------------

class ConfidenceTests(unittest.TestCase):
    def test_table_in_both_directions(self):
        cases = {
            ("CLEAR", "exact"): "high",
            ("CLEAR", "topic"): "medium",
            ("CLEAR_CAVEATED", "exact"): "medium",
            ("CLEAR_CAVEATED", "topic"): "low",
            ("CONFLICT", "exact"): "high",
            ("CONFLICT", "topic"): "medium",
            ("UNCHECKABLE", "exact"): "low",
            ("UNCHECKABLE", "topic"): "low",
        }
        for (verdict, quality), expected in cases.items():
            with self.subTest(verdict=verdict, quality=quality):
                self.assertEqual(
                    rp.confidence_for(verdict, quality, premise.FRESH),
                    expected)

    def test_no_topic_entry_ever_reaches_high(self):
        for verdict in rp.LANES:
            for decision in premise.DECISIONS:
                for quality in ("topic", "unknown"):
                    with self.subTest(verdict=verdict, quality=quality):
                        self.assertNotEqual(
                            rp.confidence_for(verdict, quality, decision),
                            "high")

    def test_ask_stale_caps_confidence_at_low(self):
        for verdict in rp.LANES:
            with self.subTest(verdict=verdict):
                self.assertEqual(
                    rp.confidence_for(verdict, "exact", premise.ASK_STALE),
                    "low")

    def test_skip_caps_at_medium_never_high(self):
        self.assertEqual(
            rp.confidence_for("CLEAR", "exact", premise.SKIP), "medium")

    def test_ceiling_never_raises_only_lowers(self):
        for verdict in rp.LANES:
            for quality in ("exact", "topic", "unknown"):
                ceiling_free = rp.confidence_for(verdict, quality,
                                                 premise.FRESH)
                for decision in premise.DECISIONS:
                    self.assertLessEqual(
                        rp.RANK[rp.confidence_for(verdict, quality, decision)],
                        rp.RANK[ceiling_free])


# --- lanes ------------------------------------------------------------------

class LaneTests(unittest.TestCase):
    def test_verdict_to_lane(self):
        self.assertEqual(rp.lane_for("CLEAR"), (1, "core"))
        self.assertEqual(rp.lane_for("CLEAR_CAVEATED"), (1, "core"))
        self.assertEqual(rp.lane_for("CONFLICT"), (2, "coordination_only"))
        self.assertEqual(rp.lane_for("UNCHECKABLE"), (3, "optional"))

    def test_uncheckable_is_never_in_the_safe_lane(self):
        self.assertNotEqual(rp.lane_for("UNCHECKABLE")[0],
                            rp.lane_for("CLEAR")[0])

    def test_every_checker_verdict_is_mapped(self):
        """A verdict the checker can emit but the policy cannot place would be
        an unhandled lane at runtime, not a test failure -- so pin the set."""
        self.assertEqual(sorted(rp.LANES), sorted(vocab.VERDICTS))


# --- ranking ----------------------------------------------------------------

class RankingTests(unittest.TestCase):
    def _corpus(self, kinds=None):
        kinds = kinds or {}
        members = []
        for task_id, rch in (("100", "high"), ("200", "low"), ("300", "medium")):
            members += member(task_id, followup_kind=kinds.get(task_id,
                                                               "risk_mitigation"),
                              rch=rch, rga=rch)
        origins = [origin_fact(t, "9%s" % t, rch=r, rga=r)
                   for t, r in (("100", "high"), ("200", "low"),
                                ("300", "medium"))]
        verdicts = {"%s#%s" % (PROJECT, t): "CLEAR" for t in ("100", "200", "300")}
        return build_roadmap(members, origins, verdicts)

    def test_risk_dominates_the_order(self):
        entries = self._corpus().entries
        self.assertEqual([e.candidate.task_id for e in entries],
                         ["100", "300", "200"])

    def test_followup_kind_permutation_is_byte_identical(self):
        """The schema declares followup_kind display-only and NOT ordering
        relevant. This converts that settled decision into an enforced one."""
        base = [e.candidate.task_id for e in self._corpus().entries]
        for permutation in ({"100": "carry_over", "200": "upstream_defect",
                             "300": "docs_gap"},
                            {"100": "docs_gap", "200": "carry_over",
                             "300": "upstream_defect"}):
            with self.subTest(permutation=permutation):
                self.assertEqual(
                    [e.candidate.task_id
                     for e in self._corpus(permutation).entries], base)

    def test_negative_control_risk_does_change_the_order(self):
        """So the permutation assertion above cannot pass vacuously."""
        members = member("100", rch="low", rga="low") + member("200", rch="high",
                                                               rga="high")
        origins = [origin_fact("100", "9100", rch="low", rga="low"),
                   origin_fact("200", "9200", rch="high", rga="high")]
        verdicts = {"%s#100" % PROJECT: "CLEAR", "%s#200" % PROJECT: "CLEAR"}
        entries = build_roadmap(members, origins, verdicts).entries
        self.assertEqual([e.candidate.task_id for e in entries], ["200", "100"])

    def test_affinity_reorders_within_a_band_but_never_across_one(self):
        members = member("100", rch="high", rga="high") + \
            member("200", rch="low", rga="low")
        origins = [origin_fact("100", "9100", rch="high", rga="high"),
                   origin_fact("200", "9200", rch="low", rga="low")]
        verdicts = {"%s#100" % PROJECT: "CLEAR", "%s#200" % PROJECT: "CLEAR"}
        # The LOW-risk task has affinity; it must still not outrank the high one.
        result = build_roadmap(members, origins, verdicts,
                               candidate_paths={"%s#200" % PROJECT: {"hot.py"}},
                               inflight_paths={"hot.py"})
        self.assertEqual([e.candidate.task_id for e in result.entries],
                         ["100", "200"])
        self.assertEqual(result.entries[1].affinity, 1)

    def test_effort_is_not_in_the_sort_key(self):
        """Effort is a capacity constraint, not value."""
        a = build_roadmap(member("100", effort="high"),
                          [origin_fact("100", "9100")],
                          {"%s#100" % PROJECT: "CLEAR"}).entries[0]
        b = build_roadmap(member("100", effort="low"),
                          [origin_fact("100", "9100")],
                          {"%s#100" % PROJECT: "CLEAR"}).entries[0]
        self.assertEqual(a.sort_key, b.sort_key)

    def test_child_ids_sort_numerically_not_lexically(self):
        members = member("1569_9") + member("1569_10")
        origins = [origin_fact("1569_9", "1"), origin_fact("1569_10", "1")]
        verdicts = {"%s#1569_9" % PROJECT: "CLEAR",
                    "%s#1569_10" % PROJECT: "CLEAR"}
        entries = build_roadmap(members, origins, verdicts).entries
        self.assertEqual([e.candidate.task_id for e in entries],
                         ["1569_9", "1569_10"])

    def test_determinism_same_fixture_twice_is_byte_identical(self):
        first = self._corpus().entries
        second = self._corpus().entries
        self.assertEqual([e.sort_key for e in first],
                         [e.sort_key for e in second])
        self.assertEqual([e.rationale for e in first],
                         [e.rationale for e in second])


# --- freshness --------------------------------------------------------------

class RecencyTests(unittest.TestCase):
    def test_day_ordinal_is_pure_integer_arithmetic(self):
        self.assertEqual(rp.day_ordinal("1970-01-01"), 0)
        self.assertEqual(rp.day_ordinal("2026-08-31") -
                         rp.day_ordinal("2026-08-01"), 30)

    def test_a_bad_stamp_is_none_not_a_crash(self):
        for bad in ("", "not-a-date", "2026-13-01", "unknown"):
            with self.subTest(bad=bad):
                self.assertIsNone(rp.day_ordinal(bad))

    def test_unknown_age_scores_the_oldest_band(self):
        """Ignorance must not promote a task."""
        self.assertEqual(rp.recency_band("unknown", NOW_ORD), 0)

    def test_buckets(self):
        self.assertEqual(rp.recency_band("2026-08-30", NOW_ORD), 3)
        self.assertEqual(rp.recency_band("2026-08-15", NOW_ORD), 2)
        self.assertEqual(rp.recency_band("2026-07-01", NOW_ORD), 1)
        self.assertEqual(rp.recency_band("2025-01-01", NOW_ORD), 0)


# --- caveats ----------------------------------------------------------------

class CaveatTests(unittest.TestCase):
    def _entry(self, quality="exact", decision=premise.FRESH, rows=None):
        ref = "%s#100" % PROJECT
        rows = rows or [origin_fact("100", "9100", quality=quality)]
        return build_roadmap(
            member("100"), rows, {ref: "CLEAR"},
            premises={ref: premise_result(decision)}).entries[0]

    def test_a_topic_entry_is_visibly_hedged(self):
        entry = self._entry(quality="topic")
        self.assertTrue(any("not an exact origin" in c for c in entry.caveats))
        self.assertIn("topic", entry.rationale)

    def test_an_exact_fresh_entry_carries_no_hedge(self):
        self.assertEqual(self._entry().caveats, ())

    def test_ask_stale_always_caveats(self):
        entry = self._entry(decision=premise.ASK_STALE)
        self.assertTrue(any("premise may no longer hold" in c
                            for c in entry.caveats))

    def test_skip_stays_silent_per_the_borrowed_convention(self):
        """SKIP is fail-open and silent, and is the common state. It still caps
        confidence, and the run summary reports the count."""
        entry = self._entry(decision=premise.SKIP)
        self.assertEqual(entry.caveats, ())
        self.assertEqual(entry.confidence, "medium")

    def test_a_disagreement_names_the_setter(self):
        entry = self._entry(rows=[
            origin_fact("100", "a1", rch="high", rga="low"),
            origin_fact("100", "a2", rch="low", rga="low")])
        self.assertTrue(any("origins disagree" in c and "a1" in c
                            for c in entry.caveats))

    def test_multi_origin_rationale_shows_every_origin_not_just_the_winner(self):
        """The reduced pair alone hides the losing origins entirely.

        With 900=(high,low) and 901=(low,low) the reduced pair reads
        `high/unknown` and the caveat names only the setter -- 901's values were
        invisible, which defeats the auditability the reduction depends on.
        """
        entry = self._entry(rows=[
            origin_fact("100", "900", rch="high", rga="low"),
            origin_fact("100", "901", rch="low", rga="low")])
        self.assertIn("Per-origin risk:", entry.rationale)
        self.assertIn("900=high/low", entry.rationale)
        self.assertIn("901=low/low", entry.rationale)

    def test_a_single_origin_names_its_source_instead(self):
        entry = self._entry(rows=[origin_fact("100", "900", rch="high",
                                              rga="low")])
        self.assertIn("Origin risk read from: 900", entry.rationale)

    def test_every_score_component_appears_in_the_rationale(self):
        entry = self._entry()
        for fragment in ("Risk band", "Origin quality", "Premise",
                         "affinity", "Priority", "effort"):
            self.assertIn(fragment, entry.rationale)


# --- trail encoding ---------------------------------------------------------

class TrailEncodingTests(unittest.TestCase):
    def _document(self, verdicts, premises=None, inflight_refs=()):
        members = []
        origins = []
        for task_id in sorted(v.split("#")[1] for v in verdicts):
            members += member(task_id)
            origins.append(origin_fact(task_id, "9000"))
        roadmap = build_roadmap(members, origins, verdicts, premises)
        return rp.to_trail(roadmap.entries, "trail-backlog-roadmap",
                           "Background-work roadmap", "%s#1569" % PROJECT,
                           SCOPE, GENERATION, FRESHNESS, NARRATIVE, EVIDENCE,
                           inflight_refs=inflight_refs)

    def _assert_valid(self, document):
        issues = trail_schema.validate_trail(document, expect_depth="deep")
        self.assertEqual([str(i) for i in issues], [])

    def test_a_corpus_with_no_coordination_emits_two_waves_not_an_empty_one(self):
        """`wave.entries` is minItems:1 and coordination is 0 on the live corpus,
        so an always-three-waves author emits an INVALID document on run one."""
        document = self._document({"%s#100" % PROJECT: "CLEAR",
                                   "%s#200" % PROJECT: "UNCHECKABLE"})
        self.assertEqual(len(document["waves"]), 2)
        self.assertEqual([w["ordinal"] for w in document["waves"]], [1, 2])
        self._assert_valid(document)

    def test_ordinals_stay_strictly_increasing_with_a_gap_in_the_lanes(self):
        document = self._document({"%s#100" % PROJECT: "UNCHECKABLE"})
        self.assertEqual([w["ordinal"] for w in document["waves"]], [1])
        self._assert_valid(document)

    def test_all_three_lanes_validate(self):
        document = self._document({"%s#100" % PROJECT: "CLEAR",
                                   "%s#200" % PROJECT: "CONFLICT",
                                   "%s#300" % PROJECT: "UNCHECKABLE"})
        self.assertEqual(len(document["waves"]), 3)
        self._assert_valid(document)

    def test_depth_is_deep_because_lite_forbids_observations_and_relations(self):
        document = self._document({"%s#100" % PROJECT: "CONFLICT"})
        self.assertEqual(document["rendering_hints"]["depth"], "deep")

    def test_a_sentinel_followup_kind_is_omitted_not_written(self):
        """Writing the transport sentinel into the enum invalidates the doc."""
        members = member("100", followup_kind="unknown", priority="unknown",
                         effort="unknown", boardcol="unknown")
        roadmap = build_roadmap(members, [origin_fact("100", "9000")],
                                {"%s#100" % PROJECT: "CLEAR"})
        document = rp.to_trail(roadmap.entries, "trail-backlog-roadmap", "T",
                               "%s#1569" % PROJECT,
                               SCOPE, GENERATION, FRESHNESS, NARRATIVE,
                               EVIDENCE)
        snapshot = document["waves"][0]["entries"][0]["snapshot"]
        for key in ("followup_kind", "priority", "effort", "boardcol"):
            self.assertNotIn(key, snapshot)
        self._assert_valid(document)

    def test_a_stale_premise_produces_the_observation_the_contract_names(self):
        ref = "%s#100" % PROJECT
        document = self._document(
            {ref: "CLEAR"}, premises={ref: premise_result(
                premise.ASK_STALE, changed=[("a.py", 1, ("7",))])})
        kinds = [o["kind"] for o in document.get("observations", [])]
        self.assertIn("stale_premise", kinds)
        for observation in document["observations"]:
            self.assertTrue(observation["evidence_refs"])
        self._assert_valid(document)

    def test_a_conflict_produces_a_coordinates_with_advisory_relation(self):
        ref = "%s#100" % PROJECT
        inflight = "%s#900" % PROJECT
        members = member("100")
        roadmap = rp.build(
            rp.parse_members(members),
            rp.parse_origin_facts([origin_fact("100", "9000")]),
            {ref: admission("CONFLICT", overlaps=[(inflight, "hot.py")])},
            {}, {}, (), NOW_ORD)
        document = rp.to_trail(roadmap.entries, "trail-backlog-roadmap", "T",
                               "%s#1569" % PROJECT,
                               SCOPE, GENERATION, FRESHNESS, NARRATIVE,
                               EVIDENCE, inflight_refs=[inflight])
        relation = document["relations"][0]
        self.assertEqual(relation["type"], "coordinates_with")
        self.assertEqual(relation["provenance"], "advisory")
        self.assertEqual((relation["from"], relation["to"]), (ref, inflight))
        self._assert_valid(document)

    def test_a_zero_candidate_scope_raises_instead_of_emitting_empty_waves(self):
        """`waves` and `wave.entries` are both minItems:1.

        Emitting `waves: []` would produce an artifact that can never validate
        while `to_trail` claims to return a complete document. What a
        zero-candidate run means is the caller's decision.
        """
        with self.assertRaises(rp.EmptyRoadmapError):
            rp.to_trail((), "trail-empty", "T", "%s#1569" % PROJECT, SCOPE,
                        GENERATION, FRESHNESS, NARRATIVE, EVIDENCE)

    def test_the_topic_falls_back_to_the_task_when_there_is_no_anchor(self):
        document = self._document({"%s#100" % PROJECT: "CLEAR"})
        entry = document["waves"][0]["entries"][0]
        self.assertEqual(entry["topic"], entry["task"])


# --- measurement ------------------------------------------------------------

class MeasurementTests(unittest.TestCase):
    def test_histogram_is_mutually_exclusive(self):
        members = (member("100") + member("200") + member("300"))
        origins = [origin_fact("100", "9", quality="exact"),
                   origin_fact("200", "9", quality="topic"),
                   origin_fact("300", "-", quality="unknown")]
        verdicts = {"%s#%s" % (PROJECT, t): "CLEAR"
                    for t in ("100", "200", "300")}
        roadmap = build_roadmap(members, origins, verdicts)
        self.assertEqual(roadmap.histogram,
                         {"exact": 1, "topic": 1, "unknown": 1})
        lines = rp.measurement_lines(roadmap.entries)
        self.assertIn("ORIGIN_QUALITY:1|1|1", lines)

    def test_counts_sum_to_the_candidate_total(self):
        members = member("100") + member("200")
        origins = [origin_fact("100", "9"), origin_fact("200", "9")]
        verdicts = {"%s#100" % PROJECT: "CLEAR",
                    "%s#200" % PROJECT: "UNCHECKABLE"}
        roadmap = build_roadmap(members, origins, verdicts)
        self.assertEqual(sum(roadmap.histogram.values()),
                         len(roadmap.entries))


class CounterfactualTests(unittest.TestCase):
    """The metric must be a real rank/lane comparison, not a proxy.

    Comparing the two origin FILE SETS for inequality is cheaper and wrong: two
    different surfaces routinely leave every position and lane untouched, so set
    inequality overstates the effect -- and the enhancement threshold for a
    persisted direct-origin field keys off this number.
    """

    MEMBERS = (member("100", verifies="t900", anchor="800") +
               member("200", verifies="t901", anchor="801"))
    ORIGINS = [origin_fact("100", "900"), origin_fact("200", "901")]

    def _ranking(self, verdicts):
        return build_roadmap(self.MEMBERS, self.ORIGINS, verdicts).entries

    def test_dual_signal_refs_needs_both_signals(self):
        candidates = rp.parse_members(
            member("100", verifies="t900", anchor="800") +
            member("200", verifies="t901") +          # no anchor
            member("300", anchor="802"))              # no verifies
        self.assertEqual(rp.dual_signal_refs(candidates),
                         ("%s#100" % PROJECT,))

    def test_different_surfaces_that_do_not_move_anything_count_zero(self):
        """The pinning fixture: the file sets differ, the ranking does not.

        This is the case a set-inequality proxy reports as a ranking change. If
        this test ever reads 1, the metric has regressed to the proxy.
        """
        both_clear = {"%s#100" % PROJECT: "CLEAR", "%s#200" % PROJECT: "CLEAR"}
        exact = self._ranking(both_clear)
        topic = self._ranking(both_clear)
        dual = rp.dual_signal_refs(rp.parse_members(self.MEMBERS))
        self.assertEqual(len(dual), 2)
        # The surfaces genuinely differ...
        self.assertNotEqual({"a.py", "b.py"}, {"x.py"})
        # ...but nothing moved.
        self.assertEqual(rp.counterfactual_rank_delta(exact, topic, dual),
                         (0, 2))

    def test_a_lane_change_counts(self):
        exact = self._ranking({"%s#100" % PROJECT: "CLEAR",
                               "%s#200" % PROJECT: "CLEAR"})
        topic = self._ranking({"%s#100" % PROJECT: "CONFLICT",
                               "%s#200" % PROJECT: "CLEAR"})
        dual = rp.dual_signal_refs(rp.parse_members(self.MEMBERS))
        differing, total = rp.counterfactual_rank_delta(exact, topic, dual)
        self.assertEqual((differing, total), (1, 2))

    def test_a_position_change_counts(self):
        members = (member("100", verifies="t900", anchor="800", rch="low") +
                   member("200", verifies="t901", anchor="801", rch="low"))
        verdicts = {"%s#100" % PROJECT: "CLEAR", "%s#200" % PROJECT: "CLEAR"}
        exact = build_roadmap(members,
                              [origin_fact("100", "900", rch="high", rga="high"),
                               origin_fact("200", "901", rch="low", rga="low")],
                              verdicts).entries
        topic = build_roadmap(members,
                              [origin_fact("100", "900", rch="low", rga="low"),
                               origin_fact("200", "901", rch="high", rga="high")],
                              verdicts).entries
        self.assertNotEqual([e.candidate.ref for e in exact],
                            [e.candidate.ref for e in topic])
        dual = rp.dual_signal_refs(rp.parse_members(members))
        self.assertEqual(rp.counterfactual_rank_delta(exact, topic, dual),
                         (2, 2))

    def test_only_dual_signal_tasks_are_counted(self):
        members = member("100", verifies="t900")      # no anchor -> not dual
        verdicts = {"%s#100" % PROJECT: "CLEAR"}
        ranking = build_roadmap(members, [origin_fact("100", "900")],
                                verdicts).entries
        dual = rp.dual_signal_refs(rp.parse_members(members))
        self.assertEqual(rp.counterfactual_rank_delta(ranking, ranking, dual),
                         (0, 0))


if __name__ == "__main__":
    unittest.main()
