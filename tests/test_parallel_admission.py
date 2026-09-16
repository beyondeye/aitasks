"""Verdict logic for the shared parallel-admission checker (t1569_3).

Pure-core tests: no git, no subprocess, no filesystem. Every input is a frozen
``AdmissionInput``, which is exactly the shape t1569_5 will construct.
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, ".aitask-scripts", "lib"))

import parallel_admission as pa            # noqa: E402
import parallel_admission_vocab as vocab   # noqa: E402

DAY = 24 * 3600
NOW = 1_000_000


def enum(gate="ok", lock="ok", status="ok", reason=None):
    return (pa.SourceEvidence("gate", gate, None, reason if gate != "ok" else None),
            pa.SourceEvidence("lock", lock, None, reason if lock != "ok" else None),
            pa.SourceEvidence("status", status, None, reason if status != "ok" else None))


def surface(ref, paths=(), resolution="resolved", provenance="plan_declared"):
    return pa.Surface(ref, provenance, tuple(paths), resolution, "n/a")


def claim(ref="t9", paths=("shared.py",), liveness="live", age=0,
          resolution="resolved", same_host=True, age_reason=None, at=None,
          provenance="plan_declared"):
    return pa.InflightClaim(
        ref=ref, sources=("lock",), task_status="Implementing", liveness=liveness,
        same_host=same_host,
        claim_at_s=(NOW - age) if (at is None and age_reason is None) else at,
        claim_age_reason=age_reason,
        surface=surface(ref, paths, resolution, provenance))


def build(candidate=None, inflight=(), touch=None, **kw):
    kw.setdefault("enumeration", enum())
    return pa.AdmissionInput(
        candidate=candidate or surface("cand", ("a.py",)),
        inflight=tuple(inflight), touch_counts=touch or {}, now=NOW, **kw)


def verdict(**kw):
    return pa.decide(build(**kw)).verdict


def lines(**kw):
    return pa.render(pa.decide(build(**kw))).splitlines()


class VerdictBasicsTests(unittest.TestCase):
    def test_no_overlap_is_clear(self):
        self.assertEqual(verdict(inflight=[claim(paths=("other.py",))]), "CLEAR")

    def test_specific_overlap_is_conflict(self):
        self.assertEqual(verdict(inflight=[claim(paths=("a.py",))]), "CONFLICT")

    def test_no_inflight_at_all_is_clear(self):
        self.assertEqual(verdict(), "CLEAR")

    def test_verdict_is_a_declared_member(self):
        self.assertIn(verdict(), vocab.VERDICTS)


class DemotionTests(unittest.TestCase):
    """Hub overlaps are DEMOTED, never dropped -- dropping them costs recall."""

    def test_hub_only_overlap_caveats_instead_of_conflicting(self):
        v = verdict(inflight=[claim(paths=("hub.py",))],
                    candidate=surface("cand", ("hub.py",)),
                    touch={"hub.py": 50})
        self.assertEqual(v, "CLEAR_CAVEATED")

    def test_hub_only_overlap_is_never_plain_clear(self):
        out = lines(inflight=[claim(paths=("hub.py",))],
                    candidate=surface("cand", ("hub.py",)), touch={"hub.py": 50})
        self.assertIn("VERDICT:CLEAR_CAVEATED", out)
        self.assertTrue(any(l.startswith("CAVEAT:") and "hub_overlap_only" in l
                            for l in out))

    def test_demoted_path_still_appears_as_an_overlap_record(self):
        # Demoted, not removed: the evidence must stay visible.
        out = lines(inflight=[claim(paths=("hub.py",))],
                    candidate=surface("cand", ("hub.py",)), touch={"hub.py": 50})
        self.assertIn("OVERLAP:t9|hub|50|hub.py", out)
        self.assertIn("NARROWED:hub.py|hub|50", out)

    def test_same_path_below_threshold_conflicts(self):
        # The discriminating control: identical fixture, sub-threshold count.
        v = verdict(inflight=[claim(paths=("hub.py",))],
                    candidate=surface("cand", ("hub.py",)), touch={"hub.py": 9})
        self.assertEqual(v, "CONFLICT")

    def test_one_specific_overlap_outranks_many_hub_overlaps(self):
        v = verdict(inflight=[claim(paths=("hub.py", "a.py"))],
                    candidate=surface("cand", ("hub.py", "a.py")),
                    touch={"hub.py": 99})
        self.assertEqual(v, "CONFLICT")

    def test_narrowing_can_never_empty_a_surface(self):
        # Standing guard replacing `all_narrowed`: demotion relabels, so no
        # threshold can empty the candidate side and manufacture a CLEAR.
        for threshold in (0, 1, 10, 10 ** 9):
            inp = build(inflight=[claim(paths=("a.py",))],
                        touch={"a.py": 10 ** 6}, hub_threshold=threshold)
            self.assertEqual(len(inp.candidate.paths), 1)
            self.assertIn(pa.decide(inp).verdict, ("CONFLICT", "CLEAR_CAVEATED"))


class TierTests(unittest.TestCase):
    def test_dead_is_excluded_even_with_matching_paths(self):
        self.assertEqual(verdict(inflight=[claim(paths=("a.py",), liveness="dead")]),
                         "CLEAR")

    def test_dead_holder_emits_no_overlap_and_no_caveat(self):
        out = lines(inflight=[claim(paths=("a.py",), liveness="dead")])
        self.assertFalse([l for l in out if l.startswith("OVERLAP:")])
        self.assertFalse([l for l in out if l.startswith("CAVEAT:")])
        # ...but stays visible, so the exclusion is auditable rather than silent.
        self.assertIn("INFLIGHT:t9|lock|dead|1|resolved|plan_declared", out)

    def test_positive_control_same_fixture_alive_conflicts(self):
        # Proves the dead fixture's paths really do intersect.
        self.assertEqual(verdict(inflight=[claim(paths=("a.py",), liveness="live")]),
                         "CONFLICT")

    def test_liveness_outranks_age_a_fresh_dead_holder_is_still_excluded(self):
        self.assertEqual(pa.tier(claim(liveness="dead", age=0), pa.MAX_CLAIM_AGE_S, NOW),
                         "excluded")

    def test_stale_holder_with_matching_paths_never_conflicts(self):
        v = verdict(inflight=[claim(paths=("a.py",), age=20 * DAY)])
        self.assertEqual(v, "CLEAR_CAVEATED")

    def test_stale_holder_overlap_is_reported_not_hidden(self):
        out = lines(inflight=[claim(paths=("a.py",), age=20 * DAY)])
        self.assertIn("OVERLAP:t9|specific|0|a.py", out)
        self.assertTrue(any("stale_claim_overlap:a.py" in l for l in out))

    def test_boundary_exactly_at_bound_still_blocks(self):
        self.assertEqual(verdict(inflight=[claim(paths=("a.py",),
                                                 age=pa.MAX_CLAIM_AGE_S)]),
                         "CONFLICT")

    def test_boundary_one_second_past_bound_is_advisory(self):
        self.assertEqual(verdict(inflight=[claim(paths=("a.py",),
                                                 age=pa.MAX_CLAIM_AGE_S + 1)]),
                         "CLEAR_CAVEATED")


class ClaimAgeTests(unittest.TestCase):
    """An unknown age is not a stale age -- it must not demote a live holder."""

    def test_absent_timestamp_is_unknown_not_stale(self):
        c = claim(paths=("a.py",), at=None, age_reason=None)
        c = pa.InflightClaim(ref=c.ref, sources=c.sources, task_status=c.task_status,
                             liveness=c.liveness, same_host=True, claim_at_s=None,
                             surface=c.surface)
        self.assertEqual(pa.claim_age(c, NOW), (None, "absent"))
        self.assertEqual(pa.tier(c, pa.MAX_CLAIM_AGE_S, NOW), "blocking")
        self.assertEqual(verdict(inflight=[c]), "CONFLICT")

    def test_malformed_timestamp_is_unknown_not_stale(self):
        c = claim(paths=("a.py",), age_reason="malformed")
        self.assertEqual(pa.claim_age(c, NOW), (None, "malformed"))
        self.assertEqual(verdict(inflight=[c]), "CONFLICT")

    def test_future_timestamp_is_clock_skew_never_a_negative_age(self):
        c = claim(paths=("a.py",), at=NOW + 500)
        age, reason = pa.claim_age(c, NOW)
        self.assertIsNone(age)
        self.assertEqual(reason, "clock_skew")
        self.assertEqual(verdict(inflight=[c]), "CONFLICT")

    def test_unknown_age_carries_a_named_caveat(self):
        c = claim(paths=("z.py",), age_reason="malformed")
        out = lines(inflight=[c])
        self.assertTrue(any("unknown_claim_age:malformed" in l for l in out))

    def test_none_never_reaches_the_comparison(self):
        for reason in ("absent", "malformed"):
            c = claim(age_reason=reason)
            self.assertEqual(pa.tier(c, pa.MAX_CLAIM_AGE_S, NOW), "blocking")

    def test_shared_default_is_a_module_constant(self):
        self.assertEqual(pa.MAX_CLAIM_AGE_S, 14 * DAY)
        self.assertEqual(pa.AdmissionInput.__dataclass_fields__[
            "max_claim_age_s"].default, pa.MAX_CLAIM_AGE_S)

    def test_effective_bound_is_reproducible_from_the_display_line(self):
        out = lines()
        display = [l for l in out if l.startswith("DISPLAY:")][0]
        self.assertIn("max_claim_age=%d" % pa.MAX_CLAIM_AGE_S, display)


class LivenessClassTests(unittest.TestCase):
    def test_status_only_no_overlap_caveats(self):
        self.assertEqual(verdict(inflight=[claim(paths=("z.py",),
                                                 liveness="status_only")]),
                         "CLEAR_CAVEATED")

    def test_status_only_with_overlap_still_conflicts(self):
        # The half-evidenced classes weaken the all-clear, never the collision.
        self.assertEqual(verdict(inflight=[claim(paths=("a.py",),
                                                 liveness="status_only")]),
                         "CONFLICT")

    def test_lock_only_no_overlap_caveats(self):
        self.assertEqual(verdict(inflight=[claim(paths=("z.py",),
                                                 liveness="lock_only")]),
                         "CLEAR_CAVEATED")

    def test_unknown_liveness_no_overlap_caveats(self):
        self.assertEqual(verdict(inflight=[claim(paths=("z.py",),
                                                 liveness="unknown")]),
                         "CLEAR_CAVEATED")

    def test_only_live_permits_plain_clear(self):
        for liveness in ("status_only", "lock_only", "unknown"):
            self.assertNotEqual(verdict(inflight=[claim(paths=("z.py",),
                                                        liveness=liveness)]),
                                "CLEAR", liveness)
        self.assertEqual(verdict(inflight=[claim(paths=("z.py",), liveness="live")]),
                         "CLEAR")


class UncheckableTests(unittest.TestCase):
    def test_unresolved_candidate_surface_is_uncheckable(self):
        for reason in ("no_plan", "all_phantom", "unknown_history",
                       "unknown_origin", "no_extractable_paths"):
            v = verdict(candidate=surface("cand", (), reason))
            self.assertEqual(v, "UNCHECKABLE", reason)

    def test_blocking_source_with_no_visible_surface_is_uncheckable(self):
        for reason in ("no_plan", "unreadable", "no_tokens", "all_phantom"):
            v = verdict(inflight=[claim(paths=(), resolution=reason)])
            self.assertEqual(v, "UNCHECKABLE", reason)

    def test_uncheckable_cause_names_the_source(self):
        out = lines(inflight=[claim(ref="t1576", paths=(), resolution="no_plan")])
        self.assertIn("UNCHECKABLE_CAUSE:inflight:t1576|no_plan", out)

    def test_excluded_source_produces_no_uncheckable_cause(self):
        # A dead holder must not make the verdict WORSE in either direction.
        v = verdict(inflight=[claim(paths=(), resolution="no_plan", liveness="dead")])
        self.assertEqual(v, "CLEAR")

    def test_conflict_outranks_uncheckable(self):
        v = verdict(inflight=[claim(paths=("a.py",)),
                              claim(ref="t8", paths=(), resolution="no_plan")])
        self.assertEqual(v, "CONFLICT")


class EnumerationTests(unittest.TestCase):
    def test_all_three_records_are_always_emitted_in_order(self):
        out = [l for l in lines() if l.startswith("INFLIGHT_SOURCE:")]
        self.assertEqual([l.split("|")[0] for l in out],
                         ["INFLIGHT_SOURCE:gate", "INFLIGHT_SOURCE:lock",
                          "INFLIGHT_SOURCE:status"])

    def test_healthy_empty_probe_permits_clear(self):
        self.assertEqual(verdict(enumeration=enum(status="ok")), "CLEAR")

    def test_unavailable_probe_with_zero_claims_is_never_clear(self):
        # The false-CLEAR regression: "found nothing" must not look like
        # "could not look".
        v = verdict(enumeration=enum(status="unavailable", reason="scan_error"))
        self.assertNotEqual(v, "CLEAR")

    def test_not_consulted_is_treated_as_unavailable(self):
        v = verdict(enumeration=enum(status="not_consulted"))
        self.assertNotEqual(v, "CLEAR")

    def test_degraded_probe_caveats(self):
        self.assertEqual(verdict(enumeration=enum(gate="degraded", reason="timeout")),
                         "CLEAR_CAVEATED")

    def test_unavailable_is_uncheckable_under_require_fresh(self):
        v = verdict(enumeration=enum(status="unavailable", reason="scan_error"),
                    locks=pa.LockEvidence(mode="require-fresh", state="fetched"))
        self.assertEqual(v, "UNCHECKABLE")

    def test_incomplete_enumeration_raises_rather_than_emitting_a_partial_set(self):
        for bad in ((pa.SourceEvidence("gate"), pa.SourceEvidence("lock")),
                    (pa.SourceEvidence("gate"),) * 3,
                    enum() + (pa.SourceEvidence("tracked"),)):
            with self.assertRaises(vocab.VocabularyError):
                pa.decide(build(enumeration=bad))


class LockFreshnessTests(unittest.TestCase):
    def test_require_fresh_refuses_a_cached_ref(self):
        v = verdict(locks=pa.LockEvidence("require-fresh", "cached", 900, "no_reflog"))
        self.assertEqual(v, "UNCHECKABLE")

    def test_allow_cached_labels_instead_of_refusing(self):
        v = verdict(locks=pa.LockEvidence("allow-cached", "cached", 900, None))
        self.assertEqual(v, "CLEAR_CAVEATED")

    def test_neither_mode_reports_clear_on_unestablished_lock_evidence(self):
        for mode in ("require-fresh", "allow-cached"):
            for state in ("cached", "unavailable"):
                v = verdict(locks=pa.LockEvidence(mode, state, 900, "no_local_ref"))
                self.assertNotEqual(v, "CLEAR", (mode, state))

    def test_require_fresh_rejects_a_ref_older_than_max_lock_age(self):
        v = verdict(locks=pa.LockEvidence("require-fresh", "fetched", 900, None),
                    max_lock_age_s=60)
        self.assertEqual(v, "UNCHECKABLE")


class RecoveredEvidenceTests(unittest.TestCase):
    """RECOVERED_* may caveat; it may never conflict nor move toward CLEAR."""

    def test_recovered_only_never_yields_plain_clear(self):
        self.assertEqual(verdict(recovered_used=True), "CLEAR_CAVEATED")

    def test_recovered_evidence_cannot_assert_a_conflict(self):
        self.assertNotEqual(verdict(recovered_used=True), "CONFLICT")


class SelfExclusionTests(unittest.TestCase):
    def test_candidate_present_in_all_three_sources_never_conflicts_with_itself(self):
        cand = surface("1569_3", ("a.py", "b.py"))
        me = pa.InflightClaim(ref="aitasks#1569_3",
                              sources=("gate", "lock", "status"),
                              task_status="Implementing", liveness="live",
                              same_host=True, claim_at_s=NOW,
                              surface=surface("1569_3", ("a.py", "b.py")))
        inp = pa.input_from_records(
            candidate_ref="1569_3", candidate_surface=cand,
            inflight_lines=[], batch_map_lines=[], inflight_claims=[me], now=NOW)
        result = pa.decide(inp)
        self.assertEqual(result.verdict, "CLEAR")
        self.assertFalse([l for l in result.lines if l.startswith("OVERLAP:")])
        self.assertFalse([l for l in result.lines if l.startswith("INFLIGHT:")])

    def test_canonical_ref_accepts_every_spelling(self):
        for spelling in ("aitasks#1569_3", "t1569_3", "1569_3"):
            self.assertEqual(pa.canonical_ref(spelling), "1569_3")


class AdapterTests(unittest.TestCase):
    def test_touch_count_is_distinct_tasks_not_commits(self):
        counts = pa.touch_counts_from_batch_map([
            "COMMIT:x.py|" + "a" * 40 + "|1|t1",
            "COMMIT:x.py|" + "b" * 40 + "|2|t1",   # same task twice
            "COMMIT:x.py|" + "c" * 40 + "|3|t2",
        ])
        self.assertEqual(counts["x.py"], 2)

    def test_unattributed_commits_contribute_nothing(self):
        counts = pa.touch_counts_from_batch_map(["COMMIT:x.py|" + "a" * 40 + "|1|"])
        self.assertEqual(counts["x.py"], 0)

    def test_commit_row_is_parsed_right_to_left(self):
        # A path containing '|' must not corrupt the split: t1569_2 emits raw.
        counts = pa.touch_counts_from_batch_map(
            ["COMMIT:we|ird.py|" + "a" * 40 + "|1|t1"])
        self.assertEqual(counts["we|ird.py"], 1)

    def test_unknown_history_is_not_an_empty_resolved_surface(self):
        s = pa.surfaces_from_batch_map(["STATUS:40|UNKNOWN_HISTORY"], ["40"])["40"]
        self.assertEqual(s.resolution, "unknown_history")
        self.assertEqual(s.paths, ())

    def test_planned_new_counts_as_resolved(self):
        s = pa.surfaces_from_inflight_records(
            ["INFLIGHT_PATH:t9|planned_new|brand/new.py"])["t9"]
        self.assertEqual(s.resolution, "resolved")
        self.assertEqual(s.paths, ("brand/new.py",))

    def test_data_paths_are_rescued_by_the_task_data_corpus(self):
        line = ["INFLIGHT_PATH:t9|phantom|aitasks/metadata/profiles/fast.yaml"]
        rescued = pa.surfaces_from_inflight_records(
            line, data_tracked={"aitasks/metadata/profiles/fast.yaml"})["t9"]
        self.assertEqual(rescued.resolution, "resolved")
        # Legacy control: without the corpus the upstream blind spot is
        # reproduced exactly, which is what makes the union load-bearing.
        blind = pa.surfaces_from_inflight_records(line)["t9"]
        self.assertEqual(blind.resolution, "all_phantom")

    def test_two_tasks_editing_the_same_profile_yaml_do_conflict(self):
        path = "aitasks/metadata/profiles/fast.yaml"
        s = pa.surfaces_from_inflight_records(
            ["INFLIGHT_PATH:t9|phantom|" + path], data_tracked={path})["t9"]
        v = pa.decide(build(candidate=surface("cand", (path,)),
                            inflight=[pa.InflightClaim(
                                ref="t9", sources=("lock",), liveness="live",
                                same_host=True, claim_at_s=NOW, surface=s)])).verdict
        self.assertEqual(v, "CONFLICT")

    def test_sentinels_survive_as_resolutions(self):
        for sentinel in ("no_plan", "no_tokens", "unreadable", "unclassified"):
            s = pa.surfaces_from_inflight_records(
                ["INFLIGHT_PATH:t9|%s|-" % sentinel])["t9"]
            self.assertEqual(s.resolution, sentinel)


class RenderTests(unittest.TestCase):
    def test_paths_are_encoded_on_output(self):
        out = lines(candidate=surface("cand", ("we|ird%.py",)),
                    inflight=[claim(paths=("we|ird%.py",))])
        overlap = [l for l in out if l.startswith("OVERLAP:")][0]
        self.assertTrue(overlap.endswith("we%7Cird%25.py"))
        self.assertEqual(overlap.split("|"), ["OVERLAP:t9", "specific", "0",
                                              "we%7Cird%25.py"])

    def test_encoding_round_trips(self):
        for raw in ("we|ird.py", "a%b.py", "%7C.py"):
            self.assertEqual(vocab.decode_path(vocab.encode_path(raw)), raw)

    def test_record_order_is_fixed(self):
        out = lines(inflight=[claim(paths=("a.py",))],
                    corpora=(pa.CorpusEvidence("code", "ok", 5),))
        prefixes = [l.split(":", 1)[0] for l in out]
        self.assertEqual(prefixes[0], "CORPUS")
        self.assertEqual(prefixes[-1], "VERDICT")
        self.assertEqual(prefixes[-2], "DISPLAY")

    def test_determinism_same_input_twice_is_byte_identical(self):
        kw = dict(inflight=[claim(paths=("a.py", "hub.py")),
                            claim(ref="t8", paths=("z.py",), liveness="lock_only")],
                  candidate=surface("cand", ("a.py", "hub.py")),
                  touch={"hub.py": 44},
                  corpora=(pa.CorpusEvidence("code", "ok", 5),
                           pa.CorpusEvidence("data", "unavailable", 0, "no_local_ref")))
        self.assertEqual(pa.render(pa.decide(build(**kw))),
                         pa.render(pa.decide(build(**kw))))

    def test_corpus_unavailable_is_never_silent(self):
        out = lines(corpora=(pa.CorpusEvidence("data", "unavailable", 0, "no_local_ref"),))
        self.assertIn("CORPUS:data|unavailable|0|no_local_ref", out)
        self.assertTrue(any("corpus_unavailable:data" in l for l in out))


class ClearWordingTests(unittest.TestCase):
    """The observation-not-reservation guarantee, made executable."""

    FORBIDDEN = "safe to run in parallel"
    REQUIRED = "no known conflict at check time"

    def _display(self, **kw):
        return [l for l in lines(**kw) if l.startswith("DISPLAY:")][0]

    def test_clear_says_no_known_conflict_at_check_time(self):
        self.assertIn(self.REQUIRED, self._display())

    def test_clear_caveated_says_it_too(self):
        d = self._display(inflight=[claim(paths=("z.py",), liveness="lock_only")])
        self.assertIn(self.REQUIRED, d)

    def test_no_verdict_ever_claims_parallel_safety(self):
        for kw in ({}, dict(inflight=[claim(paths=("a.py",))]),
                   dict(inflight=[claim(paths=("z.py",), liveness="unknown")]),
                   dict(candidate=surface("cand", (), "no_plan"))):
            for line in lines(**kw):
                self.assertNotIn(self.FORBIDDEN, line)


class NegativeControlTests(unittest.TestCase):
    """None of these may produce plain CLEAR."""

    def test_a_demoted_path_cannot_produce_plain_clear(self):
        self.assertNotEqual(
            verdict(inflight=[claim(paths=("hub.py",))],
                    candidate=surface("cand", ("hub.py",)), touch={"hub.py": 50}),
            "CLEAR")

    def test_an_empty_candidate_surface_cannot_produce_plain_clear(self):
        self.assertNotEqual(verdict(candidate=surface("cand", (), "all_phantom")),
                            "CLEAR")

    def test_an_unverified_holder_cannot_produce_plain_clear(self):
        for liveness in ("status_only", "lock_only", "unknown"):
            self.assertNotEqual(
                verdict(inflight=[claim(paths=("z.py",), liveness=liveness)]),
                "CLEAR", liveness)


class TaskDeclaredTests(unittest.TestCase):
    """A no-plan task read from its description is unverified evidence (t1688)."""

    def test_an_inflight_description_surface_grades_clear_caveated(self):
        out = lines(inflight=[claim(paths=("z.py",), provenance="task_declared")])
        self.assertIn("VERDICT:CLEAR_CAVEATED", out)
        self.assertIn("CAVEAT:inflight:t9|task_declared", out)
        self.assertIn("INFLIGHT:t9|lock|live|1|resolved|task_declared", out)

    def test_control_the_same_claim_from_a_plan_is_bare_clear(self):
        self.assertEqual(verdict(inflight=[claim(paths=("z.py",))]), "CLEAR")

    def test_a_candidate_description_surface_grades_clear_caveated(self):
        out = lines(candidate=surface("cand", ("a.py",), provenance="task_declared"))
        self.assertIn("VERDICT:CLEAR_CAVEATED", out)
        self.assertIn("CAVEAT:candidate|task_declared", out)
        self.assertIn("CANDIDATE:cand|task_declared|1|resolved|n/a", out)

    def test_an_advisory_tier_description_claim_gets_no_task_declared_caveat(self):
        out = lines(inflight=[claim(paths=("z.py",), age=20 * DAY,
                                    provenance="task_declared")])
        self.assertFalse([l for l in out
                          if l.startswith("CAVEAT:") and "|task_declared" in l])

    def test_an_undeclared_inflight_provenance_raises(self):
        bad = pa.InflightClaim(ref="t9", sources=("lock",), liveness="live",
                               same_host=True, claim_at_s=NOW,
                               surface=surface("t9", ("z.py",),
                                               provenance="not_a_provenance"))
        with self.assertRaises(vocab.VocabularyError):
            pa.decide(build(inflight=[bad]))


class TaskDeclaredOverlapTests(unittest.TestCase):
    """Description evidence reports an overlap; it never asserts a conflict."""

    def test_an_inflight_description_overlap_is_declared_not_a_conflict(self):
        out = lines(inflight=[claim(paths=("a.py",), provenance="task_declared")])
        self.assertIn("VERDICT:CLEAR_CAVEATED", out)
        self.assertIn("OVERLAP:t9|declared|0|a.py", out)
        self.assertIn("CAVEAT:inflight:t9|task_declared_overlap:a.py", out)
        self.assertIn("CAVEAT:inflight:t9|task_declared", out)
        self.assertFalse([l for l in out
                          if l.startswith("OVERLAP:") and "|specific|" in l])

    def test_a_candidate_description_overlapping_a_plan_is_declared_too(self):
        out = lines(candidate=surface("cand", ("a.py",), provenance="task_declared"),
                    inflight=[claim(paths=("a.py",))])
        self.assertIn("VERDICT:CLEAR_CAVEATED", out)
        self.assertIn("OVERLAP:t9|declared|0|a.py", out)
        self.assertIn("CAVEAT:inflight:t9|task_declared_overlap:a.py", out)

    def test_control_plans_on_both_sides_conflict(self):
        out = lines(inflight=[claim(paths=("a.py",))])
        self.assertIn("VERDICT:CONFLICT", out)
        self.assertIn("OVERLAP:t9|specific|0|a.py", out)

    def test_a_mixed_result_names_only_the_strong_counterparty(self):
        result = pa.decide(build(inflight=[
            claim(ref="t9", paths=("a.py",), provenance="task_declared"),
            claim(ref="t10", paths=("a.py",))]))
        self.assertEqual(result.verdict, "CONFLICT")
        self.assertIn("OVERLAP:t9|declared|0|a.py", result.lines)
        self.assertIn("OVERLAP:t10|specific|0|a.py", result.lines)
        # The weak overlap is not masked: its evidence is still rendered.
        self.assertIn("CAVEAT:inflight:t9|task_declared_overlap:a.py", result.lines)
        display = [l for l in result.lines if l.startswith("DISPLAY:")][0]
        self.assertIn("t10", display)
        self.assertNotIn("t9", display)
        self.assertEqual(pa.conflict_refs(result.lines), ("t10",))

    def test_a_weak_overlap_on_a_hub_path_stays_hub(self):
        out = lines(inflight=[claim(paths=("a.py",), provenance="task_declared")],
                    touch={"a.py": 50})
        self.assertIn("OVERLAP:t9|hub|50|a.py", out)
        self.assertTrue(any("hub_overlap_only:a.py" in l for l in out))
        self.assertFalse(any("task_declared_overlap" in l for l in out))

    def test_an_advisory_tier_declared_overlap_carries_the_stale_caveat_only(self):
        out = lines(inflight=[claim(paths=("a.py",), age=20 * DAY,
                                    provenance="task_declared")])
        self.assertIn("OVERLAP:t9|declared|0|a.py", out)
        self.assertTrue(any("stale_claim_overlap:a.py" in l for l in out))
        self.assertFalse(any("task_declared_overlap" in l for l in out))


class ConflictRefsTests(unittest.TestCase):
    """`conflict_refs` recovers `decide`'s own counterparties from its lines."""

    def test_a_stale_claims_specific_row_is_not_a_counterparty(self):
        result = pa.decide(build(inflight=[
            claim(ref="t9", paths=("a.py",), age=20 * DAY),
            claim(ref="t10", paths=("a.py",))]))
        self.assertEqual(result.verdict, "CONFLICT")
        # The stale claim still renders a `specific` row -- which is exactly
        # why a consumer cannot read the class alone.
        self.assertIn("OVERLAP:t9|specific|0|a.py", result.lines)
        self.assertEqual(pa.conflict_refs(result.lines), ("t10",))

    def test_a_hub_row_is_not_a_counterparty(self):
        result = pa.decide(build(
            candidate=surface("cand", ("a.py", "b.py")),
            inflight=[claim(ref="t9", paths=("a.py",)),
                      claim(ref="t10", paths=("b.py",))],
            touch={"a.py": 50}))
        self.assertEqual(pa.conflict_refs(result.lines), ("t10",))

    def test_conflict_overlaps_decodes_the_path(self):
        result = pa.decide(build(candidate=surface("cand", ("we|ird.py",)),
                                 inflight=[claim(paths=("we|ird.py",))]))
        self.assertEqual(pa.conflict_overlaps(result.lines), (("t9", "we|ird.py"),))

    def test_nothing_conflicts_nothing_is_returned(self):
        result = pa.decide(build(inflight=[claim(paths=("a.py",),
                                                 provenance="task_declared")]))
        self.assertEqual(pa.conflict_refs(result.lines), ())


def _fake_classify(path, files, dirs):
    """`plan_paths.classify`'s rule without importing it (this module is pure)."""
    if path in files:
        return "tracked"
    parent = os.path.dirname(path)
    return "planned_new" if parent and parent in dirs else "phantom"


class AdapterTaskDeclaredTests(unittest.TestCase):
    """The gatherer's `task_declared` marker and the injected classifier."""

    def test_the_marker_retags_a_resolved_surface(self):
        s = pa.surfaces_from_inflight_records([
            "INFLIGHT_PATH:t9|task_declared|-",
            "INFLIGHT_PATH:t9|tracked|a.py"])["t9"]
        self.assertEqual((s.resolution, s.provenance, s.paths),
                         ("resolved", "task_declared", ("a.py",)))

    def test_a_marked_ref_that_resolves_nothing_is_no_plan_not_all_phantom(self):
        s = pa.surfaces_from_inflight_records([
            "INFLIGHT_PATH:t9|task_declared|-",
            "INFLIGHT_PATH:t9|phantom|nowhere/x.py",
            "INFLIGHT_PATH:t9|malformed|-x.md"])["t9"]
        self.assertEqual((s.resolution, s.provenance, s.paths),
                         ("no_plan", "plan_declared", ()))

    def test_control_an_unmarked_phantom_only_plan_is_still_all_phantom(self):
        s = pa.surfaces_from_inflight_records(
            ["INFLIGHT_PATH:t9|phantom|nowhere/x.py"])["t9"]
        self.assertEqual(s.resolution, "all_phantom")

    def test_the_injected_classifier_promotes_a_new_file_under_a_data_directory(self):
        line = ["INFLIGHT_PATH:t9|phantom|aitasks/metadata/profiles/custom.yaml"]
        data = {"aitasks/metadata/profiles/fast.yaml"}
        exact = pa.surfaces_from_inflight_records(line, data_tracked=data)["t9"]
        self.assertEqual(exact.resolution, "all_phantom")
        promoted = pa.surfaces_from_inflight_records(
            line, data_tracked=data, data_dirs={"aitasks/metadata/profiles"},
            classify=_fake_classify)["t9"]
        self.assertEqual((promoted.resolution, promoted.paths),
                         ("resolved", ("aitasks/metadata/profiles/custom.yaml",)))

    def test_input_from_records_threads_the_classifier_through(self):
        path = "aitasks/metadata/profiles/custom.yaml"
        holder = pa.InflightClaim(ref="t9", sources=("lock",), liveness="live",
                                  same_host=True, claim_at_s=NOW)
        kw = dict(candidate_ref="cand", candidate_surface=surface("cand", (path,)),
                  inflight_lines=["INFLIGHT_PATH:t9|phantom|" + path],
                  batch_map_lines=[], inflight_claims=[holder], now=NOW,
                  data_tracked={"x"}, data_dirs={"aitasks/metadata/profiles"})
        self.assertEqual(
            pa.decide(pa.input_from_records(classify=_fake_classify, **kw)).verdict,
            "CONFLICT")
        self.assertNotEqual(pa.decide(pa.input_from_records(**kw)).verdict,
                            "CONFLICT")


class TaskDeclaredNegativeControlTests(unittest.TestCase):
    def test_no_description_surface_ever_conflicts_or_reads_bare_clear(self):
        """Every provenance pair where either side is a description."""
        provenances = ("plan_declared", "origin_derived", "task_declared")
        checked = 0
        for cand_prov in provenances:
            for inf_prov in ("plan_declared", "task_declared"):
                if "task_declared" not in (cand_prov, inf_prov):
                    continue
                for paths in (("a.py",), ("z.py",)):
                    out = lines(
                        candidate=surface("cand", ("a.py",), provenance=cand_prov),
                        inflight=[claim(paths=paths, provenance=inf_prov)])
                    what = (cand_prov, inf_prov, paths)
                    self.assertNotIn("VERDICT:CONFLICT", out, what)
                    self.assertNotIn("VERDICT:CLEAR", out, what)
                    self.assertFalse([l for l in out if l.startswith("OVERLAP:")
                                      and "|specific|" in l], what)
                    checked += 1
        self.assertEqual(checked, 8)


if __name__ == "__main__":
    unittest.main()
