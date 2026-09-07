"""Driver tests for the background-work roadmap (t1569_6).

The driver is the IMPURE half, so every helper it shells out to is injected
through the module-level ``_RUN`` seam (the ``trail_gather._GATE_PROBE``
convention). Nothing here runs git, the gatherer or the checker for real -- the
live path is covered by the end-to-end verification in the plan.

Every negative control here is written so it CAN fail: each one is paired with
the positive case it is meant to discriminate from, because a refusal test that
would also pass against "refuse everything" measures nothing.
"""

import json
import os
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
LIB_DIR = os.path.join(REPO_ROOT, ".aitask-scripts", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import roadmap_run as rr            # noqa: E402


# --- fixtures ---------------------------------------------------------------

PROJECT = "aitasks"
NOW = 1_760_000_000

# Two follow-ups and one in-flight task they can collide with.
LS_FOLLOWUPS = "\n".join([
    "t100_first_followup.md [Status: Ready, Priority: High, Effort: Medium, "
    "Type: bug, Follow-up: risk_mitigation]",
    "t101_second_followup.md [Status: Ready, Priority: Medium, Effort: Low, "
    "Type: bug, Follow-up: upstream_defect]",
])
LS_GENUINE = "\n".join([
    "t102_low_effort_genuine.md [Status: Ready, Priority: Low, Effort: Low, "
    "Type: chore]",
    "t103_big_genuine.md [Status: Ready, Priority: High, Effort: High, "
    "Type: feature]",          # effort High -> excluded
    "t104_parent.md [Status: Has children, Priority: High, Effort: Low, "
    "Type: feature]",          # Has children -> excluded
])

MEMBERS = "\n".join([
    "MEMBER:%s#100|Ready|high|medium|now|a|risk_mitigation|aitasks/t100_a.md"
    % PROJECT,
    "MEMBER:%s#101|Ready|medium|low|next|b|upstream_defect|aitasks/t101_b.md"
    % PROJECT,
    "MEMBER:%s#102|Ready|low|low|backlog|c||aitasks/t102_c.md" % PROJECT,
    "MEMBER_EXT:%s#100|2026-08-01 10:00|100||high|medium" % PROJECT,
    "MEMBER_EXT:%s#101|2026-08-02 10:00|101||low|low" % PROJECT,
    "MEMBER_EXT:%s#102|2026-08-03 10:00|102||low|low" % PROJECT,
    "INPUT:task_file|true|Ready|||%s#100" % PROJECT,
    "INPUT:task_file|true|Ready|||%s#101" % PROJECT,
    "INPUT:task_file|true|Ready|||%s#102" % PROJECT,
    "INFLIGHT_SOURCE:gate|ok|-|-",
    "INFLIGHT_SOURCE:lock|ok|10|-",
    "INFLIGHT_SOURCE:tracked|ok|-|-",
    "DIGEST:abc123def4567890",
])

ORIGIN_FACTS = "\n".join([
    "ORIGIN_FACT:100|90|exact|high|medium|archived",
    "ORIGIN_FACT:101|91|topic|low|low|archived",
    "ORIGIN_FACT:102|-|unknown|-|-|absent",
])


def _narrative(tmpdir, **overrides):
    data = {"problem_statement": "The backlog grows and nobody picks it.",
            "recommendation_summary": "A ranked estimate that reserves nothing."}
    data.update(overrides)
    path = os.path.join(tmpdir, "narr.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def _write(tmpdir, name, text):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class _Seam:
    """Injected `_RUN`: answers by which helper was invoked."""

    def __init__(self, ls_followups=LS_FOLLOWUPS, ls_genuine=LS_GENUINE,
                 members=MEMBERS, facts=ORIGIN_FACTS, ls_rc=0, snap_rc=0,
                 facts_rc=0):
        self.ls_followups, self.ls_genuine = ls_followups, ls_genuine
        self.members, self.facts = members, facts
        self.ls_rc, self.snap_rc, self.facts_rc = ls_rc, snap_rc, facts_rc
        self.calls = []

    def __call__(self, args, cwd, timeout=300):
        self.calls.append(list(args))
        prog = os.path.basename(args[0])
        if prog == "aitask_ls.sh":
            return self.ls_rc, (self.ls_genuine if "--no-followup-kind" in args
                                else self.ls_followups)
        if prog == "aitask_trail_gather.sh":
            return self.snap_rc, self.members
        if prog == "aitask_backlog_origin_facts.sh":
            return self.facts_rc, self.facts
        raise AssertionError("unexpected helper: %s" % prog)


class _RunHarness(unittest.TestCase):
    """Rebinds the driver's subprocess seam and its collector for each test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="roadmap_run_")
        self._saved_run = rr._RUN
        self.seam = _Seam()
        rr._RUN = self.seam

    def tearDown(self):
        rr._RUN = self._saved_run


# --- candidate enumeration --------------------------------------------------

class EnumerationTests(_RunHarness):

    def test_corpus_is_followups_plus_low_effort_genuine_parents(self):
        ids, unparsable = rr.enumerate_candidates(self.tmp)
        self.assertEqual(ids, ["100", "101", "102"])
        self.assertEqual(unparsable, [])

    def test_high_effort_genuine_and_parents_with_children_are_excluded(self):
        """The discriminating half: the fixture CONTAINS both, so an
        implementation that took every genuine task would fail here."""
        ids, _ = rr.enumerate_candidates(self.tmp)
        self.assertNotIn("103", ids)    # effort High
        self.assertNotIn("104", ids)    # Has children

    def test_a_task_file_with_no_number_is_reported_not_dropped(self):
        self.seam.ls_genuine += (
            "\nt_no_number_at_all.md [Status: Ready, Priority: Low, "
            "Effort: Low, Type: bug]")
        ids, unparsable = rr.enumerate_candidates(self.tmp)
        self.assertEqual(unparsable, ["t_no_number_at_all.md"])
        # And it never becomes an empty id, which would make the snapshot ask
        # about a task that cannot exist.
        self.assertNotIn("", ids)

    def test_ids_sort_numerically_not_lexically(self):
        self.assertEqual(
            sorted(["12_3", "2", "12", "13"], key=rr._numeric_key),
            ["2", "12", "12_3", "13"])


# --- narrative validation ---------------------------------------------------

class NarrativeTests(_RunHarness):

    def test_a_valid_narrative_loads(self):
        """The positive control the refusals below discriminate against."""
        data = rr.load_narrative(_narrative(self.tmp))
        self.assertEqual(sorted(data), ["problem_statement",
                                        "recommendation_summary"])

    def test_missing_file_is_refused_by_name(self):
        with self.assertRaises(rr.NarrativeError) as ctx:
            rr.load_narrative(os.path.join(self.tmp, "nope.json"))
        self.assertIn("cannot read", str(ctx.exception))

    def test_malformed_json_is_refused_by_name(self):
        path = _write(self.tmp, "bad.json", "{not json")
        with self.assertRaises(rr.NarrativeError) as ctx:
            rr.load_narrative(path)
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_missing_required_key_is_refused(self):
        path = _write(self.tmp, "partial.json",
                      json.dumps({"problem_statement": "x"}))
        with self.assertRaises(rr.NarrativeError) as ctx:
            rr.load_narrative(path)
        self.assertIn("recommendation_summary", str(ctx.exception))

    def test_whitespace_only_value_is_refused(self):
        """The schema's `overview` pattern is `\\S`; a blank-but-present value
        would otherwise reach the document and render as an empty section."""
        path = _narrative(self.tmp, problem_statement="   \n\t ")
        with self.assertRaises(rr.NarrativeError) as ctx:
            rr.load_narrative(path)
        self.assertIn("non-whitespace", str(ctx.exception))

    def test_unexpected_key_is_refused_by_name(self):
        """`narrative` is additionalProperties:false, so this must fail HERE
        rather than as an opaque schema error after a full pipeline run."""
        path = _narrative(self.tmp, method_note="I wrote this myself")
        with self.assertRaises(rr.NarrativeError) as ctx:
            rr.load_narrative(path)
        self.assertIn("method_note", str(ctx.exception))

    def test_optional_overview_is_accepted(self):
        """Discriminates the extra-key refusal from "refuse anything extra"."""
        data = rr.load_narrative(_narrative(self.tmp, overview="Some prose."))
        self.assertIn("overview", data)


# --- method note ------------------------------------------------------------

class MethodNoteTests(unittest.TestCase):

    def test_a_capped_run_states_the_corpus_the_cap_and_the_unenumerated_tail(self):
        note = rr.method_note(255, 40, 40, [])
        self.assertIn("255", note)
        self.assertIn("40", note)
        self.assertIn("not enumerated", note)

    def test_a_corpus_smaller_than_the_cap_says_so_instead_of_implying_selection(self):
        note = rr.method_note(7, 7, 40, [])
        self.assertIn("smaller than the cap", note)
        self.assertNotIn("not enumerated", note)

    def test_unparsable_files_are_named_in_the_note(self):
        note = rr.method_note(10, 10, 40, ["t_no_number.md"])
        self.assertIn("t_no_number.md", note)

    def test_the_estimate_language_is_present_and_never_claims_safety(self):
        note = rr.method_note(255, 40, 40, [])
        self.assertIn("no known conflict at check time", note)
        self.assertNotIn("safe to run in parallel", note)


# --- cap contract -----------------------------------------------------------

class CapContractTests(unittest.TestCase):

    def test_a_positive_cap_is_accepted(self):
        self.assertEqual(rr._positive_int("40"), 40)
        self.assertEqual(rr._positive_int("1"), 1)

    def test_zero_negative_and_non_numeric_caps_are_refused(self):
        import argparse
        for bad in ("0", "-1", "ten", ""):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad):
                rr._positive_int(bad)


# --- source health / generation ---------------------------------------------

class RecordParsingTests(unittest.TestCase):

    def test_source_health_reads_every_inflight_source(self):
        health = rr.source_health(MEMBERS.splitlines())
        self.assertEqual(sorted(health), ["gate", "lock", "tracked"])
        self.assertEqual(health["lock"][0], "ok")

    def test_generation_takes_the_ref_from_the_LAST_field(self):
        """`INPUT:` carries different field counts per kind (task_file 6,
        plan_file 4) and the ref is the free-ish last field in both. Indexing
        from the left produced `true` as the ref."""
        lines = [
            "INPUT:task_file|true|Ready|||%s#100" % PROJECT,
            "INPUT:plan_file|true|deadbeef|aitasks:aiplans/p1.md",
            "DIGEST:feedface00000000",
        ]
        gen = rr._generation(lines, "claudecode/opus5", NOW)
        self.assertEqual(gen["input_digest"], "feedface00000000")
        self.assertEqual([i["ref"] for i in gen["inputs"]],
                         ["%s#100" % PROJECT, "aitasks:aiplans/p1.md"])
        self.assertEqual([i["kind"] for i in gen["inputs"]],
                         ["task_file", "plan_file"])


# --- lane reporting ---------------------------------------------------------

class LaneCountTests(unittest.TestCase):

    class _Entry:
        def __init__(self, lane):
            self.lane = lane

    def test_every_lane_is_named_even_at_zero(self):
        """An empty parallel-safe lane must be visible as `safe=0`, not as an
        absent key -- omission reads as "nothing to worry about"."""
        counts = rr._lane_counts([self._Entry(2), self._Entry(3)])
        self.assertIn("safe=0", counts)
        self.assertIn("coordination=1", counts)
        self.assertIn("unresolvable=1", counts)

    def test_a_populated_safe_lane_is_counted(self):
        counts = rr._lane_counts([self._Entry(1), self._Entry(1)])
        self.assertIn("safe=2", counts)


if __name__ == "__main__":
    unittest.main()
