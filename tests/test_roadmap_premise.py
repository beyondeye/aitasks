"""Premise-drift interface tests (t1569_5).

Pure: no git, no subprocess, no filesystem. Every input is a frozen list of
``COMMIT:`` lines, which is exactly the shape the roadmap builds from t1569_2's
``--batch-map`` output.

Run: ``python3 -m unittest tests.test_roadmap_premise -v``
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))

import roadmap_premise as rp  # noqa: E402

DAY = 86400
T0 = 1_000_000


def commit(path, sha, ct, ids):
    """One ``COMMIT:`` row, exactly as t1569_2 emits it (path RAW)."""
    return "COMMIT:%s|%s|%d|%s" % (path, sha, ct, ",".join(ids))


class PublicSurfaceTests(unittest.TestCase):
    """`__all__` is the substitution contract with t1561.

    This module is deliberately narrow because t1561 replaces it. A name that
    appears without being added to `__all__` on purpose is scope creep toward a
    second permanent staleness framework -- the thing the design record forbids.
    """

    def test_public_names_are_exactly_all(self):
        import types
        public = {name for name, value in vars(rp).items()
                  if not name.startswith("_")
                  and not isinstance(value, types.ModuleType)
                  and name not in ("dataclass", "field")}
        self.assertEqual(sorted(public), sorted(rp.__all__))

    def test_the_interface_t1561_replaces_is_two_functions(self):
        self.assertTrue(callable(rp.baseline_for))
        self.assertTrue(callable(rp.check))


class BaselineTests(unittest.TestCase):
    def test_newest_landing_commit_wins(self):
        rows = [commit("a.py", "sha1", T0, ["100"]),
                commit("b.py", "sha2", T0 + DAY, ["100"])]
        base = rp.baseline_for(["100"], rows)
        self.assertEqual(base.sha, "sha2")
        self.assertEqual(base.committed_at, T0 + DAY)
        self.assertIsNone(base.reason)

    def test_a_later_task_data_commit_does_not_move_the_baseline(self):
        """The live defect: `ait git commit` tags task-data commits `(tNN)` too.

        Measured 2026-08-31, 35 of 1615 tagged ids have a metadata-only NEWEST
        tagged commit (t1636_3, t1544_8, t1569 itself). Taking it would move the
        baseline past real code changes, which would then read as pre-baseline
        and be silently reported FRESH.
        """
        rows = [commit("code.py", "landing", T0, ["100"]),
                commit("aitasks/t100_x.md", "meta", T0 + 5 * DAY, ["100"])]
        base = rp.baseline_for(["100"], rows)
        self.assertEqual(base.sha, "landing")

    def test_an_intervening_change_is_still_drift_after_a_metadata_commit(self):
        """The consequence the previous test exists to protect."""
        rows = [commit("code.py", "landing", T0, ["100"]),
                commit("code.py", "other", T0 + 2 * DAY, ["777"]),
                commit("aitasks/t100_x.md", "meta", T0 + 5 * DAY, ["100"])]
        result = rp.check(["100"], ["code.py"], rows)
        self.assertEqual(result.decision, rp.ASK_STALE)
        self.assertEqual([c[0] for c in result.changed], ["code.py"])

    def test_only_task_data_commits_is_metadata_only_not_unknown_history(self):
        rows = [commit("aiplans/p100.md", "meta", T0, ["100"])]
        base = rp.baseline_for(["100"], rows)
        self.assertIsNone(base.sha)
        self.assertEqual(base.reason, "metadata_only")

    def test_no_tagged_commit_at_all_is_unknown_history(self):
        rows = [commit("code.py", "sha", T0, ["999"])]
        self.assertEqual(rp.baseline_for(["100"], rows).reason,
                         "unknown_history")

    def test_no_origin_is_its_own_reason(self):
        self.assertEqual(rp.baseline_for([], []).reason, "no_origin")

    def test_data_prefixes_are_a_parameter_not_a_hardcoded_layout(self):
        """TASK_DIR / PLAN_DIR are configurable; a pure module must not assume."""
        rows = [commit("code.py", "landing", T0, ["100"]),
                commit("mytasks/t100.md", "meta", T0 + DAY, ["100"])]
        self.assertEqual(rp.baseline_for(["100"], rows).sha, "meta")
        self.assertEqual(
            rp.baseline_for(["100"], rows,
                            data_prefixes=("mytasks/",)).sha, "landing")

    def test_ties_break_deterministically(self):
        rows = [commit("a.py", "bbb", T0, ["100"]),
                commit("b.py", "aaa", T0, ["100"])]
        self.assertEqual(rp.baseline_for(["100"], rows).sha,
                         rp.baseline_for(["100"], list(reversed(rows))).sha)


class RejectedAlternativeTests(unittest.TestCase):
    """The `created_at -> nearest ancestor commit` rule, encoded as its failure.

    A `risk_mitigation` "before" follow-up is created by task-workflow Step 7
    BEFORE its origin's code lands, so its `created_at` precedes the origin's own
    landing commit. The rejected rule would take a pre-landing baseline and then
    report the origin's OWN landing commit as drift -- a false ASK_STALE on every
    such task. The chosen rule cannot: it starts at the landing commit.
    """

    def test_chosen_rule_does_not_flag_the_origins_own_landing(self):
        spawned_at = T0 - DAY                    # follow-up created pre-landing
        rows = [commit("code.py", "landing", T0, ["100"])]
        result = rp.check(["100"], ["code.py"], rows)
        self.assertEqual(result.decision, rp.FRESH)
        self.assertEqual(result.baseline.committed_at, T0)
        self.assertLess(spawned_at, result.baseline.committed_at)

    def test_the_rejected_rule_would_have_flagged_it(self):
        """The discriminating assertion: a pre-landing baseline sees drift."""
        rows = [commit("code.py", "landing", T0, ["100"])]
        rejected = rp.Baseline(sha="ancestor", committed_at=T0 - DAY)
        result = rp.check(["100"], ["code.py"], rows, baseline=rejected)
        self.assertEqual(result.decision, rp.ASK_STALE)


class CheckTests(unittest.TestCase):
    def test_unchanged_is_fresh(self):
        rows = [commit("a.py", "sha", T0, ["100"])]
        self.assertEqual(rp.check(["100"], ["a.py"], rows).decision, rp.FRESH)

    def test_unknown_drives_the_verdict_exactly_like_changed(self):
        """A path that cannot be checked means the check covers LESS scope than
        it claims, so FRESH would be a false all-clear."""
        rows = [commit("a.py", "sha", T0, ["100"])]
        result = rp.check(["100"], ["a.py", "never-committed.py"], rows)
        self.assertEqual(result.decision, rp.ASK_STALE)
        self.assertEqual(result.changed, ())
        self.assertEqual(result.unknown, (("never-committed.py",
                                           "no_index_history"),))

    def test_absent_at_baseline_is_distinct_from_no_history(self):
        rows = [commit("a.py", "sha", T0, ["100"]),
                commit("later.py", "sha2", T0 + DAY, ["777"])]
        result = rp.check(["100"], ["later.py"], rows)
        self.assertEqual(result.unknown, (("later.py", "absent_at_baseline"),))

    def test_an_empty_scope_is_never_fresh(self):
        """A resolved baseline over zero files checked NOTHING.

        FRESH here would be the module's own false all-clear -- "all 0 files
        unchanged" reads as verified, and it would raise the confidence ceiling
        to `high` for a task whose premise was never examined. Reachable: a
        candidate whose batch-map STATUS is NO_FILES has an empty surface.
        """
        rows = [commit("code.py", "landing", T0, ["100"])]
        result = rp.check(["100"], [], rows)
        self.assertEqual(result.decision, rp.SKIP)
        self.assertEqual(result.reason, "empty_scope")
        self.assertIn("empty_scope", result.reason)
        self.assertTrue(result.baseline.resolved)
        self.assertNotIn("DECISION:FRESH", result.lines)
        self.assertIn("UNCHECKED:empty_scope", result.lines)

    def test_an_empty_scope_is_not_ask_stale_either(self):
        """There is no evidence the premise moved -- only nothing to check."""
        rows = [commit("code.py", "landing", T0, ["100"])]
        self.assertNotEqual(rp.check(["100"], [], rows).decision, rp.ASK_STALE)

    def test_uncomputable_baseline_is_skip_and_never_fabricated(self):
        result = rp.check([], ["a.py"], [])
        self.assertEqual(result.decision, rp.SKIP)
        self.assertEqual(result.reason, "no_origin")
        self.assertIsNone(result.baseline.sha)
        self.assertIn("BASELINE:NONE", result.lines)

    def test_protocol_shape(self):
        rows = [commit("a.py", "sha", T0, ["100"]),
                commit("a.py", "sha2", T0 + DAY, ["777"])]
        lines = rp.check(["100"], ["a.py"], rows).lines
        self.assertTrue(lines[0].startswith("BASELINE:"))
        self.assertTrue(lines[1].startswith("FILES:"))
        self.assertTrue(lines[-1].startswith("DECISION:"))
        self.assertTrue(lines[-2].startswith("DISPLAY:"))

    def test_delimiters_in_a_path_round_trip(self):
        """`%`-then-`|` encoding, via vocab.encode_path rather than a second copy."""
        weird = "a|b%c.py"
        rows = [commit(weird, "sha", T0, ["100"]),
                commit(weird, "sha2", T0 + DAY, ["777"])]
        lines = rp.check(["100"], [weird], rows).lines
        changed = [line for line in lines if line.startswith("CHANGED:")]
        self.assertEqual(len(changed), 1)
        self.assertIn("a%7Cb%25c.py", changed[0])

    def test_deletion_surfaces_as_changed_the_accepted_narrowing(self):
        """No DELETED: record exists -- the COMMIT index records paths TOUCHED.

        A smaller claim than aitask_verification_stale.sh's, pinned so it stays
        a documented narrowing rather than becoming an unnoticed gap.
        """
        rows = [commit("gone.py", "sha", T0, ["100"]),
                commit("gone.py", "del", T0 + DAY, ["777"])]
        result = rp.check(["100"], ["gone.py"], rows)
        self.assertEqual(result.decision, rp.ASK_STALE)
        self.assertFalse(any(line.startswith("DELETED:")
                             for line in result.lines))

    def test_malformed_rows_are_skipped_not_raised_on(self):
        rows = ["COMMIT:broken", "not a record",
                commit("a.py", "sha", T0, ["100"])]
        self.assertEqual(rp.check(["100"], ["a.py"], rows).decision, rp.FRESH)

    def test_determinism_same_input_twice_is_byte_identical(self):
        rows = [commit("a.py", "sha", T0, ["100"]),
                commit("b.py", "sha2", T0 + DAY, ["777"]),
                commit("c.py", "sha3", T0 + 2 * DAY, ["888"])]
        paths = ["a.py", "b.py", "c.py", "missing.py"]
        first = rp.check(["100"], paths, rows).lines
        second = rp.check(["100"], list(reversed(paths)), list(reversed(rows)))
        self.assertEqual(first, second.lines)

    def test_negative_control_a_real_change_changes_the_output(self):
        """So the determinism assertion above cannot pass vacuously."""
        rows = [commit("a.py", "sha", T0, ["100"])]
        base = rp.check(["100"], ["a.py"], rows).lines
        drifted = rp.check(["100"], ["a.py"],
                           rows + [commit("a.py", "x", T0 + DAY, ["777"])]).lines
        self.assertNotEqual(base, drifted)


if __name__ == "__main__":
    unittest.main()
