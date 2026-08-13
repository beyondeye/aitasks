#!/usr/bin/env python3
"""Rule semantics for the followup_kind backfill classifier (t1468_6).

The load-bearing test here is `test_risk_mitigation_beats_manual_verification`:
it is the negative control for the rule-order correction. The task file and the
parent plan both specify `carry_over -> manual_verification -> risk_mitigation`,
but 8 active tasks match BOTH the risk-mitigation producer sentence and
`issue_type: manual_verification`, and the live Step-8d creation seam has
already marked two of them (t1477, t1508) `risk_mitigation`. Keeping the written
order would split one cohort by creation date.

That test was written against the spec order FIRST and confirmed to fail, so it
cannot pass vacuously if someone later restores the written spec.
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))

import followup_backfill_classify as fbc  # noqa: E402


def make(frontmatter_lines, body, filename="t999_example.md"):
    """Build a task file's text and classify it exactly as the driver would."""
    raw = "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n" + body
    parsed = __import__("task_yaml").parse_frontmatter(raw)
    assert parsed is not None, "fixture has no parseable frontmatter"
    metadata, parsed_body, _ = parsed
    return fbc.classify(metadata, parsed_body, filename)


BASE = ["priority: medium", "effort: medium", "status: Ready"]

RISK_AFTER = 'Risk-mitigation ("after") follow-up for t1474, created at Step 8d.'
RISK_BEFORE = 'Risk-mitigation ("before") for t884, created at Step 7.'
CARRY = (
    "Carry-over of deferred manual-verification items from t1040. "
    "Re-pick this task to continue the remaining checklist."
)


class TestRuleOrder(unittest.TestCase):
    def test_risk_mitigation_beats_manual_verification(self):
        """The corrected precedence. Modelled on the real t1477.

        Body prose records WHO spawned the task; issue_type records what kind of
        work it is. A risk-mitigation follow-up whose work happens to be manual
        verification is still a risk mitigation -- and the live seam already
        marked t1477/t1508 that way.
        """
        res = make(
            BASE + ["issue_type: manual_verification", "verifies: [1474]"],
            "## Origin\n\n" + RISK_AFTER + "\n",
        )
        self.assertEqual(res["kind"], "risk_mitigation")
        self.assertEqual(res["rule"], "risk_mitigation")

    def test_before_variant_is_matched(self):
        """The "before" producer omits the words "follow-up"."""
        res = make(BASE + ["issue_type: test"], "## Origin\n\n" + RISK_BEFORE + "\n")
        self.assertEqual(res["kind"], "risk_mitigation")

    def test_carry_over_beats_manual_verification(self):
        """carry_over is a strict subset of MV and must still win."""
        res = make(
            BASE + ["issue_type: manual_verification"], "## Origin\n\n" + CARRY + "\n"
        )
        self.assertEqual(res["kind"], "carry_over")

    def test_upstream_defect_beats_manual_verification(self):
        res = make(
            BASE + ["issue_type: manual_verification"],
            "## Upstream defect\n\nSomething is broken elsewhere.\n",
        )
        self.assertEqual(res["kind"], "upstream_defect")

    def test_verification_failure_beats_manual_verification(self):
        res = make(
            BASE + ["issue_type: manual_verification"],
            "## Failed verification item from t1498\n\nItem 5 failed.\n",
        )
        self.assertEqual(res["kind"], "verification_failure")

    def test_manual_verification_is_the_fallback(self):
        """An MV task with no more specific provenance still classifies."""
        res = make(BASE + ["issue_type: manual_verification"], "## Checklist\n\n- [ ] x\n")
        self.assertEqual(res["kind"], "manual_verification")


class TestCrossFieldInvariant(unittest.TestCase):
    def test_manual_verification_kind_implies_mv_issue_type(self):
        """The invariant holds by construction, not by a check.

        Rule 5 is the only producer of `followup_kind: manual_verification` and
        it fires only when issue_type already equals it -- so no input can
        produce the pair the CLI refuses to write.
        """
        for issue_type in ("bug", "feature", "test", "chore", "manual_verification"):
            res = make(BASE + ["issue_type: %s" % issue_type], "## Checklist\n\n- [ ] x\n")
            if res["kind"] == "manual_verification":
                self.assertEqual(issue_type, "manual_verification")


class TestFrontmatterScoping(unittest.TestCase):
    def test_example_frontmatter_in_body_is_not_read(self):
        """The t583_9 shape: a body that quotes an example frontmatter block."""
        body = (
            "## Dogfood\n\nA task looks like this:\n\n"
            "```\n---\nissue_type: manual_verification\nstatus: Ready\n---\n```\n"
        )
        res = make(BASE + ["issue_type: test"], body)
        self.assertIsNone(res["kind"], "body example must not classify the task")

    def test_label_match_is_exact_token(self):
        """`aitask_review` / `reviewguides` are different concepts from `review`."""
        res = make(
            BASE + ["issue_type: refactor", "labels: [aitask_review, reviewguides]"],
            "## Scope\n\nnothing\n",
        )
        self.assertIsNone(res["kind"])

        res = make(
            BASE + ["issue_type: refactor", "labels: [review, skill, task-workflow]"],
            "## Scope\n\nnothing\n",
        )
        self.assertEqual(res["kind"], "review_finding")


class TestSelfReferentialSpecTasks(unittest.TestCase):
    """The tasks that SPECIFY this feature quote the marker strings.

    Both t1468 and t1468_6 carry markdown rule tables containing the bare
    prefixes. Anchoring on the producer's full sentence is what keeps the spec
    from classifying itself as its own subject.
    """

    def test_quoted_carry_over_prefix_does_not_match(self):
        body = (
            "## Classification rules\n\n"
            "| kind | detection |\n|---|---|\n"
            "| `carry_over` | body has `Carry-over of deferred "
            "manual-verification items` |\n"
        )
        res = make(BASE + ["issue_type: chore"], body, "t1468_6_backfill.md")
        self.assertIsNone(res["kind"])

    def test_quoted_risk_mitigation_prefix_does_not_match(self):
        body = (
            "Only the body prose `Risk-mitigation (\"after\") follow-up`\n"
            "reveals it.\n"
        )
        res = make(BASE + ["issue_type: feature"], body, "t1468_mark_followup.md")
        self.assertIsNone(res["kind"])


class TestConflictDetection(unittest.TestCase):
    def test_two_prose_rules_report_a_conflict(self):
        """Two producers on one task is a rule bug, not a precedence question."""
        res = make(
            BASE + ["issue_type: bug"],
            "## Origin\n\n" + RISK_AFTER + "\n\n## Upstream defect\n\nalso this\n",
        )
        self.assertEqual(res["conflict"], ["risk_mitigation", "upstream_defect"])

    def test_prose_plus_issue_type_fallback_is_not_a_conflict(self):
        """carry_over + MV co-occur on 7 real tasks; that is expected."""
        res = make(
            BASE + ["issue_type: manual_verification"], "## Origin\n\n" + CARRY + "\n"
        )
        self.assertEqual(res["conflict"], [])


class TestResidueAndAnnotation(unittest.TestCase):
    def test_plain_task_is_residue(self):
        res = make(BASE + ["issue_type: feature"], "## Goal\n\nBuild a thing.\n")
        self.assertIsNone(res["kind"])
        self.assertIsNone(res["rule"])

    def test_origin_annotation_is_reported(self):
        res = make(BASE + ["issue_type: feature"], "## Origin\n\nSpawned from t1.\n")
        self.assertTrue(res["has_origin"])
        res = make(BASE + ["issue_type: feature"], "## Goal\n\nBuild a thing.\n")
        self.assertFalse(res["has_origin"])

    def test_already_marked_is_surfaced(self):
        res = make(
            BASE + ["issue_type: bug", "followup_kind: upstream_defect"],
            "## Upstream defect\n\nx\n",
        )
        self.assertEqual(res["already"], "upstream_defect")


class TestUnparseableIds(unittest.TestCase):
    """Task filenames without a numeric id must surface, never be dropped.

    The live corpus contains `t_refresh_codeagent_suite_default_model_
    expectations.md` -- a genuine upstream-defect follow-up (`## Upstream
    defect` + the Step 8b sentence) whose filename carries no id. The backfill
    cannot write it (`aitask_update.sh --batch` needs an id), but silently
    skipping it is the exact defect t1338 records against the work report.
    """

    def test_id_extraction_returns_none_for_idless_name(self):
        self.assertIsNone(
            fbc.task_id_from_path("aitasks/t_refresh_codeagent_suite_defaults.md")
        )
        self.assertEqual(fbc.task_id_from_path("aitasks/t42_thing.md"), "42")
        self.assertEqual(fbc.task_id_from_path("aitasks/t1468/t1468_6_thing.md"), "1468_6")

    def test_idless_file_is_emitted_as_unparseable_not_dropped(self):
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "t_no_id_here.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(
                    "---\nissue_type: bug\nstatus: Ready\n---\n\n"
                    "## Upstream defect\n\nbroken\n"
                )
            out = subprocess.run(
                [sys.executable, fbc.__file__, path],
                capture_output=True, text=True, check=True,
            ).stdout
        self.assertIn("UNPARSEABLE_ID", out)
        self.assertIn("t_no_id_here.md", out)


class TestDeltaReport(unittest.TestCase):
    """The pre-commit / recovery delta contract.

    Deliberately SEMANTIC rather than a line diff: aitask_update.sh rebuilds
    frontmatter through its own serializer, which reorders keys and
    canonicalises task-id lists. A line-level check called those corruption and
    made reconcile_row report the backfill's own writes as FOREIGN_DRIFT.
    What matters is that nothing is lost or altered.
    """

    BEFORE = (
        "---\npriority: high\nissue_type: bug\nstatus: Ready\n"
        "verifies: ['635_11']\nupdated_at: 2026-01-01 00:00\nboardidx: 70\n---\n\n## Body\n\ntext\n"
    )

    def d(self, after, kind="upstream_defect"):
        return fbc.delta_report(self.BEFORE, after, kind)

    def test_clean_addition_is_ok(self):
        after = self.BEFORE.replace(
            "updated_at: 2026-01-01 00:00",
            "followup_kind: upstream_defect\nupdated_at: 2026-06-06 06:06",
        )
        self.assertEqual(self.d(after)[0], "OK")

    def test_key_reordering_is_not_a_change(self):
        after = (
            "---\nissue_type: bug\nboardidx: 70\npriority: high\n"
            "followup_kind: upstream_defect\nstatus: Ready\nverifies: ['635_11']\n"
            "updated_at: 2026-06-06 06:06\n---\n\n## Body\n\ntext\n"
        )
        self.assertEqual(self.d(after)[0], "OK")

    def test_id_canonicalisation_is_tolerated_but_reported(self):
        after = (
            "---\npriority: high\nissue_type: bug\nstatus: Ready\n"
            "verifies: [t635_11]\nfollowup_kind: upstream_defect\n"
            "updated_at: 2026-06-06 06:06\nboardidx: 70\n---\n\n## Body\n\ntext\n"
        )
        verdict, details = self.d(after)
        self.assertEqual(verdict, "OK_NORMALIZED")
        self.assertTrue(any("verifies" in x for x in details), details)

    # --- the cases that MUST be rejected ---

    def test_removed_key_is_bad(self):
        after = self.BEFORE.replace("boardidx: 70\n", "").replace(
            "updated_at:", "followup_kind: upstream_defect\nupdated_at:"
        )
        verdict, details = self.d(after)
        self.assertEqual(verdict, "BAD")
        self.assertIn("REMOVED", details[0])

    def test_unrelated_value_change_is_bad(self):
        after = self.BEFORE.replace("priority: high", "priority: low").replace(
            "updated_at:", "followup_kind: upstream_defect\nupdated_at:"
        )
        self.assertEqual(self.d(after)[0], "BAD")

    def test_body_blank_line_normalisation_is_tolerated(self):
        """The serializer collapses blank lines around the body (seen on t1399)."""
        before = self.BEFORE.replace("---\n\n## Body", "---\n\n\n## Body")
        after = self.BEFORE.replace(
            "updated_at:", "followup_kind: upstream_defect\nupdated_at:"
        )
        verdict, details = fbc.delta_report(before, after, "upstream_defect")
        self.assertEqual(verdict, "OK_NORMALIZED")
        self.assertTrue(any("whitespace" in x for x in details), details)

    def test_internal_whitespace_change_is_still_bad(self):
        """The whitespace tolerance must not let content hide inside the body."""
        after = self.BEFORE.replace("## Body\n\ntext", "## Body\n\nte  xt").replace(
            "updated_at:", "followup_kind: upstream_defect\nupdated_at:"
        )
        self.assertEqual(self.d(after)[0], "BAD")

    def test_body_change_is_bad(self):
        after = self.BEFORE.replace("text", "tampered").replace(
            "updated_at:", "followup_kind: upstream_defect\nupdated_at:"
        )
        verdict, details = self.d(after)
        self.assertEqual(verdict, "BAD")
        self.assertIn("body", details[0])

    def test_wrong_kind_is_bad(self):
        after = self.BEFORE.replace(
            "updated_at:", "followup_kind: risk_mitigation\nupdated_at:"
        )
        self.assertEqual(self.d(after)[0], "BAD")

    def test_missing_kind_is_bad(self):
        after = self.BEFORE.replace("2026-01-01 00:00", "2026-06-06 06:06")
        self.assertEqual(self.d(after)[0], "BAD")

    def test_extra_key_added_is_bad(self):
        after = self.BEFORE.replace(
            "updated_at:", "followup_kind: upstream_defect\nsneaky: yes\nupdated_at:"
        )
        verdict, details = self.d(after)
        self.assertEqual(verdict, "BAD")
        self.assertIn("sneaky", details[0])

    def test_id_normalisation_does_not_mask_a_real_id_change(self):
        """`t635_11` -> `t999` must still be BAD, not 'canonicalisation'."""
        after = (
            "---\npriority: high\nissue_type: bug\nstatus: Ready\n"
            "verifies: [t999]\nfollowup_kind: upstream_defect\n"
            "updated_at: 2026-06-06 06:06\nboardidx: 70\n---\n\n## Body\n\ntext\n"
        )
        self.assertEqual(self.d(after)[0], "BAD")


class TestRuleOrderConstant(unittest.TestCase):
    def test_every_rule_is_a_known_followup_kind(self):
        import followup_kinds

        self.assertEqual(
            set(fbc.RULE_ORDER), set(followup_kinds.VALID_FOLLOWUP_KINDS),
            "classifier rules and the framework vocabulary must agree",
        )

    def test_prose_rules_exclude_the_issue_type_fallback(self):
        self.assertNotIn("manual_verification", fbc.PROSE_PROVENANCE_RULES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
