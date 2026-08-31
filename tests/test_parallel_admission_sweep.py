"""Measurement harness for the parallel-admission checker (t1643).

Pure-core tests: no git, no subprocess, no filesystem. The harness's whole value
is that it grades the SHIPPED ``decide`` against a ground truth, so these tests
pin the counting and the scope transform -- never a replica of the verdict logic.

THE CLAIM BEING RETIRED. t1569_3 argued, without measuring it across thresholds,
that demotion makes a wrong hub threshold cost verdict *grading* rather than
recall. ``RecallInvarianceTests`` measures exactly that, and pairs it with a
negative control: an invariance assertion alone passes on any degenerate fixture
where nothing varies, so precision and the hard-stop share must be shown to MOVE
over the same thresholds.
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, ".aitask-scripts", "lib"))

import parallel_admission as pa           # noqa: E402
import parallel_admission_sweep as pas    # noqa: E402

# Swept in every threshold test, including the degenerate ends: 1 demotes
# essentially everything, 10**9 demotes nothing (the "unnarrowed" control that
# cross-validates against t1569_3's published row).
THRESHOLDS = (1, 8, 10, 20, 50, 10 ** 9)


def surface(ref, paths=(), resolution="resolved"):
    return pa.Surface(ref, "plan_declared", tuple(paths), resolution, "n/a")


def population(*rows):
    """``(ref, plan_paths, landed_paths)`` triples -> a sweep population."""
    return tuple((ref, surface(ref, plan), frozenset(landed))
                 for ref, plan, landed in rows)


# A hand-built world with a known answer at every threshold.
#
#   hub.py       touched by 30 tasks -> `hub` at 8/10/20, `specific` at 50
#   shared.py    touched by 15 tasks -> `hub` at 8/10,    `specific` at 20/50
#   narrow.py    touched by 2 tasks  -> `specific` everywhere above 2
#
# The two middle counts are what make the sweep discriminate: a threshold
# override that never reaches `decide` would return identical rows for all of
# 8/10/20/50, and every other assertion here would still pass.
TOUCH = {"hub.py": 30, "shared.py": 15, "narrow.py": 2, "solo.py": 1}

# Ground truth is set by the LANDED sets, independently of the plans:
#   a landed {x.py, y.py}   b landed {x.py}   c landed {y.py}   d landed {z.py}
# so a-b collide (x.py) and a-c collide (y.py), while b-c do not.
#
# a & b: plans overlap on narrow.py -> specific above 2 -> CONFLICT, and they
#        really collide -> a hard-stopped true positive.
# a & c: plans overlap only on hub.py -> CLEAR_CAVEATED until 50, CONFLICT at
#        50; they really collide -> a true collision that the threshold DOWNGRADES
#        to a confirmation, which is the grading cost invariant recall hides.
# b & c: plans overlap on shared.py but they did NOT collide -> a false positive
#        that moves from caveat to hard stop at 20.
# d:     overlaps nobody and collides with nobody -> keeps plain CLEAR reachable.
POP = population(
    ("a", ("narrow.py", "hub.py"), ("x.py", "y.py")),
    ("b", ("narrow.py", "shared.py"), ("x.py",)),
    ("c", ("hub.py", "shared.py"), ("y.py",)),
    ("d", ("solo.py",), ("z.py",)),
)


class PairVerdictTests(unittest.TestCase):
    """The comparison the harness builds is the one `decide` would render."""

    def test_verdict_is_symmetric_in_the_two_surfaces(self):
        """Counting UNORDERED pairs is only sound if this holds.

        `confusion` iterates `combinations`, so each pair is judged once, in an
        arbitrary order. If the verdict depended on which task was the candidate
        the totals would silently depend on population ordering.
        """
        for threshold in THRESHOLDS:
            for (a_ref, a_surf, _al) in POP:
                for (b_ref, b_surf, _bl) in POP:
                    if a_ref == b_ref:
                        continue
                    forward = pas.pair_verdict(a_surf, b_ref, b_surf, TOUCH,
                                               threshold)
                    backward = pas.pair_verdict(b_surf, a_ref, a_surf, TOUCH,
                                                threshold)
                    self.assertEqual(forward, backward,
                                     (a_ref, b_ref, threshold))

    def test_the_scaffolding_never_manufactures_uncheckable(self):
        """Every probe/corpus/lock is pinned healthy on purpose.

        An `UNCHECKABLE` leaking in from degraded scaffolding would drop the pair
        out of the graded population and move every rate, while looking like a
        property of the data.
        """
        for threshold in THRESHOLDS:
            conf = pas.confusion(POP, TOUCH, threshold)
            self.assertEqual(conf.count("UNCHECKABLE"), 0, threshold)

    def test_the_demotion_boundary_is_inclusive(self):
        """`count >= threshold` is a hub -- pinned ON the boundary, not near it.

        The main fixture's touch counts deliberately straddle the swept
        thresholds, which catches a missing or inverted demotion but NOT an
        off-by-one: mutating `>=` to `>` leaves every one of those assertions
        passing. This is the case that fails.
        """
        touch = {"edge.py": 10}
        pop = population(("a", ("edge.py",), ("x.py",)),
                         ("b", ("edge.py",), ("x.py",)))
        self.assertEqual(pas.confusion(pop, touch, 10).count("CLEAR_CAVEATED"), 1)
        self.assertEqual(pas.confusion(pop, touch, 10).count("CONFLICT"), 0)
        # One above the count, the same path is specific again.
        self.assertEqual(pas.confusion(pop, touch, 11).count("CONFLICT"), 1)

    def test_an_untouched_path_is_always_specific(self):
        """A path with no attributed touches must never be demoted.

        Touch counts are a systematic LOWER bound (78% of commits name no task),
        so an unattributed path is the common case, and demoting it would hide
        real collisions wholesale.
        """
        pop = population(("a", ("unknown.py",), ("x.py",)),
                         ("b", ("unknown.py",), ("x.py",)))
        for threshold in THRESHOLDS:
            self.assertEqual(pas.confusion(pop, {}, threshold).count("CONFLICT"),
                             1, threshold)

    def test_the_blocking_tier_is_what_is_measured(self):
        """A CONFLICT is only reachable from a blocking claim."""
        inp = pas.pair_input(surface("a", ("narrow.py",)), "b",
                             surface("b", ("narrow.py",)), TOUCH, 10)
        self.assertEqual(pa.tier(inp.inflight[0], inp.max_claim_age_s, inp.now),
                         "blocking")


class ConfusionArithmeticTests(unittest.TestCase):
    """Exact counts on the hand-built world -- no derived rate is trusted."""

    def test_pairs_and_ground_truth(self):
        conf = pas.confusion(POP, TOUCH, 10)
        self.assertEqual(conf.pairs, 6)          # 4 choose 2
        self.assertEqual(conf.colliding, 2)      # a-b and a-c both landed x.py

    def test_verdict_split_at_the_shipped_threshold(self):
        conf = pas.confusion(POP, TOUCH, 10)
        # a-b overlap narrow.py (2 touches) -> specific -> CONFLICT
        self.assertEqual(conf.count("CONFLICT"), 1)
        # a-c on hub.py and b-c on shared.py are both hubs at 10
        self.assertEqual(conf.count("CLEAR_CAVEATED"), 2)
        self.assertEqual(conf.count("CLEAR"), 3)

    def test_true_positives_partition_the_collisions(self):
        for threshold in THRESHOLDS:
            conf = pas.confusion(POP, TOUCH, threshold)
            self.assertEqual(conf.tp_conflict + conf.tp_caveated + conf.missed,
                             conf.colliding, threshold)
            self.assertEqual(conf.tp_flagged,
                             conf.tp_conflict + conf.tp_caveated, threshold)

    def test_derived_rates(self):
        conf = pas.confusion(POP, TOUCH, 10)
        # a-b is the only hard stop and it is a true collision.
        self.assertEqual(pas.precision_conflict(conf), 1.0)
        self.assertEqual(conf.tp_conflict, 1)
        # a-c is a real collision graded down to a caveat.
        self.assertEqual(conf.tp_caveated, 1)
        self.assertEqual(pas.recall_flagged(conf), 1.0)
        self.assertEqual(pas.share_hard_stopped(conf), 0.5)
        self.assertEqual(pas.share_downgraded(conf), 0.5)
        self.assertEqual(pas.share_missed(conf), 0.0)

    def test_a_missed_collision_is_counted_as_missed(self):
        """Two tasks that really collided but whose plans never overlapped."""
        pop = population(("a", ("one.py",), ("landed.py",)),
                         ("b", ("two.py",), ("landed.py",)))
        conf = pas.confusion(pop, {}, 10)
        self.assertEqual(conf.colliding, 1)
        self.assertEqual(conf.missed, 1)
        self.assertEqual(conf.tp_flagged, 0)
        self.assertEqual(pas.recall_flagged(conf), 0.0)

    def test_counts_only_no_stored_rates(self):
        """Rates are derived on demand; a frozen float would drift silently."""
        conf = pas.confusion(POP, TOUCH, 10)
        for value in vars(conf).values():
            self.assertNotIsInstance(value, float)


class UndefinedMetricTests(unittest.TestCase):
    """A zero denominator is its own state, never a plausible-looking default."""

    def test_no_colliding_pairs_makes_recall_undefined(self):
        pop = population(("a", ("one.py",), ("p.py",)),
                         ("b", ("two.py",), ("q.py",)))
        conf = pas.confusion(pop, {}, 10)
        self.assertEqual(conf.colliding, 0)
        for metric in (pas.recall_flagged, pas.share_hard_stopped,
                       pas.share_downgraded, pas.share_missed):
            self.assertIsNone(metric(conf), metric.__name__)

    def test_no_hard_stops_makes_precision_undefined(self):
        pop = population(("a", ("hub.py",), ("x.py",)),
                         ("b", ("hub.py",), ("x.py",)))
        conf = pas.confusion(pop, TOUCH, 10)     # hub.py is a hub at 10
        self.assertEqual(conf.pred_conflict, 0)
        self.assertIsNone(pas.precision_conflict(conf))

    def test_an_empty_population_is_not_a_perfect_score(self):
        conf = pas.confusion((), {}, 10)
        self.assertEqual(conf.pairs, 0)
        self.assertIsNone(pas.recall_flagged(conf))
        self.assertIsNone(pas.precision_conflict(conf))


class RecallInvarianceTests(unittest.TestCase):
    """The t1569_3 claim this task exists to measure."""

    def test_recall_is_invariant_in_the_hub_threshold(self):
        """Demotion RE-GRADES an overlap; it never discards one.

        This is the guarantee that bounds the damage of a wrong threshold: a
        collision the checker would flag at one threshold is flagged at every
        threshold, only under a different verdict.
        """
        recalls = {t: pas.recall_flagged(pas.confusion(POP, TOUCH, t))
                   for t in THRESHOLDS}
        self.assertEqual(len(set(recalls.values())), 1, recalls)

    def test_missed_collisions_are_invariant_too(self):
        missed = {t: pas.confusion(POP, TOUCH, t).missed for t in THRESHOLDS}
        self.assertEqual(len(set(missed.values())), 1, missed)

    def test_negative_control_precision_and_grading_do_move(self):
        """Without this, the invariance above passes on a degenerate fixture.

        A population whose touch counts never straddle a swept threshold would
        return identical rows for everything, and "recall is invariant" would be
        a statement about the fixture rather than about demotion.
        """
        precisions = {t: pas.precision_conflict(pas.confusion(POP, TOUCH, t))
                      for t in THRESHOLDS}
        shares = {t: pas.share_hard_stopped(pas.confusion(POP, TOUCH, t))
                  for t in THRESHOLDS}
        self.assertGreater(len(set(precisions.values())), 1, precisions)
        self.assertGreater(len(set(shares.values())), 1, shares)

    def test_hard_stops_are_monotone_in_the_threshold(self):
        """Raising the threshold can only turn hubs back into specifics."""
        counts = [pas.confusion(POP, TOUCH, t).pred_conflict
                  for t in sorted(THRESHOLDS)]
        self.assertEqual(counts, sorted(counts), counts)

    def test_the_unnarrowed_control_flags_every_overlap(self):
        """A threshold above every touch count demotes nothing."""
        conf = pas.confusion(POP, TOUCH, 10 ** 9)
        self.assertEqual(conf.count("CLEAR_CAVEATED"), 0)
        self.assertEqual(conf.count("CONFLICT"), conf.pairs - conf.count("CLEAR"))


class CutPostImplementationTests(unittest.TestCase):
    """The `pre-implementation` scope transform, in both directions."""

    def test_cuts_at_the_post_work_heading(self):
        body = ("Edit `alpha.py`.\n\n"
                "## Final Implementation Notes\n\n"
                "Also touched `beta.py`.\n")
        cut = pas.cut_post_implementation(body)
        self.assertIn("alpha.py", cut)
        self.assertNotIn("beta.py", cut)
        self.assertNotIn("Final Implementation Notes", cut)

    def test_cut_provably_changes_the_extracted_content(self):
        """A cut that silently did nothing would leave the whole scope inert.

        Every downstream count would still look plausible, so the transform must
        be shown to remove something, not merely to run.
        """
        body = "Edit `alpha.py`.\n\n## Final Implementation Notes\n\n`beta.py`\n"
        self.assertNotEqual(pas.cut_post_implementation(body), body)

    def test_is_a_no_op_without_a_post_work_heading(self):
        body = "Edit `alpha.py`.\n\n## Verification\n\nRun the tests.\n"
        self.assertEqual(pas.cut_post_implementation(body), body)

    def test_an_early_verification_pass_heading_does_not_truncate(self):
        """THE REGRESSION GUARD for the artefact t1643 found in its own draft.

        A `## Verification pass` section is written when a plan is RE-PICKED, so
        it sits BEFORE the implementation body it precedes -- in `p1569_3` it is
        at line 32, ahead of the entire plan. Cutting on it discarded 9 of 281
        archived tasks from the population outright (no resolved surface left)
        and inflated the reported hindsight correction from 3pp to 6pp, while
        every emitted number still looked reasonable.
        """
        body = ("## Verification pass -- 2026-08-30\n\nRe-verified.\n\n"
                "## Step 1\n\nEdit `alpha.py`.\n")
        self.assertEqual(pas.cut_post_implementation(body), body)
        self.assertIn("alpha.py", pas.cut_post_implementation(body))

    def test_post_work_headings_is_the_single_source(self):
        """The cut set is one named constant, so widening it is a visible edit."""
        self.assertEqual(pas.POST_WORK_HEADINGS, ("Final Implementation Notes",))
        for heading in pas.POST_WORK_HEADINGS:
            body = "before\n\n## %s\n\nafter\n" % heading
            self.assertEqual(pas.cut_post_implementation(body), "before\n\n")

    def test_matches_at_any_heading_depth_but_not_mid_line(self):
        deep = "before\n\n#### Final Implementation Notes\n\nafter\n"
        self.assertEqual(pas.cut_post_implementation(deep), "before\n\n")
        prose = "See the Final Implementation Notes below for `alpha.py`.\n"
        self.assertEqual(pas.cut_post_implementation(prose), prose)


class PlanExtractionRecordTests(unittest.TestCase):
    """The record that carries drop accounting out of extraction."""

    def test_as_surface_agrees_with_the_record(self):
        rec = pas.PlanExtraction("t1", ("a.py",), "resolved", 3, 2)
        surf = rec.as_surface()
        self.assertEqual(surf.ref, "t1")
        self.assertEqual(surf.paths, ("a.py",))
        self.assertEqual(surf.resolution, "resolved")
        self.assertEqual(surf.provenance, "plan_declared")

    def test_an_unresolved_record_makes_an_unresolved_surface(self):
        for resolution in ("all_phantom", "no_extractable_paths", "unreadable"):
            surf = pas.PlanExtraction("t1", (), resolution, 4, 4).as_surface()
            self.assertEqual(surf.resolution, resolution)
            self.assertEqual(surf.paths, ())


if __name__ == "__main__":
    unittest.main()
