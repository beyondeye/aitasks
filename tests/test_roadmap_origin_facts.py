"""Origin-facts collector, and the producer -> consumer seam (t1569_5).

This is the ONE module in the roadmap suite that shells out, on purpose.
``tests/test_roadmap_integration.py`` starts from *synthetic* ``ORIGIN_FACT:``
lines, so it proves the policy path but not that the collector emits records
that path accepts: an escaping, sentinel, archive-lookup or field-order mismatch
passes every other test in this suite and breaks real roadmap runs. The
``RealCollectorSeamTests`` below run the actual wrapper over temporary active and
archived task data and feed its stdout **verbatim** into the policy layer.

Run: ``python3 -m unittest tests.test_roadmap_origin_facts -v``
"""

import os
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))

import roadmap_origin_facts as rof  # noqa: E402
import roadmap_policy as rp  # noqa: E402

WRAPPER = os.path.join(PROJECT_DIR, ".aitask-scripts",
                       "aitask_backlog_origin_facts.sh")


def task_file(directory, task_id, **fields):
    """One task file with the frontmatter the collector reads."""
    lines = "\n".join("%s: %s" % (k, v) for k, v in fields.items())
    path = Path(directory) / ("t%s_fixture.md" % task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent("""\
        ---
        %s
        ---

        Fixture body for t%s.
        """) % (lines, task_id), encoding="utf-8")
    return path


class Scaffold:
    """A temp project: active tasks, loose archived tasks, and a real bundle."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="roadmap-origin-"))
        self.task_dir = self.root / "aitasks"
        self.archived = self.task_dir / "archived"
        self.task_dir.mkdir(parents=True)
        self.archived.mkdir(parents=True)

    def bundle(self, task_id, **fields):
        """Put an archived task inside a numbered `.tar.gz` bundle.

        Exercises the archive-lookup branch rather than the loose-file one --
        `tarfile` writes it natively, so no external tool is needed.
        """
        staging = self.root / "staging"
        staging.mkdir(exist_ok=True)
        member = task_file(staging, task_id, **fields)
        parent = int(str(task_id).split("_")[0])
        bundle_no = parent // 100
        directory = self.archived / ("_b%d" % (bundle_no // 10))
        directory.mkdir(parents=True, exist_ok=True)
        with tarfile.open(directory / ("old%d.tar.gz" % bundle_no), "w:gz") as tar:
            tar.add(member, arcname=member.name)
        member.unlink()

    def run_wrapper(self, *task_ids):
        return subprocess.run(
            [WRAPPER, "--task-dir", str(self.task_dir),
             "--archived-dir", str(self.archived), *task_ids],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120)

    def cleanup(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.scaffold = Scaffold()
        self.addCleanup(self.scaffold.cleanup)

    def test_one_row_per_origin_never_one_per_task(self):
        task_file(self.scaffold.task_dir, "100",
                  followup_kind="manual_verification",
                  verifies="[900, 901, 902]")
        for origin in ("900", "901", "902"):
            task_file(self.scaffold.archived, origin, risk_code_health="low")
        lines = rof.collect(["100"], self.scaffold.task_dir,
                            self.scaffold.archived)
        self.assertEqual(len(lines), 3)

    def test_a_task_with_no_origin_still_gets_exactly_one_row(self):
        """Absence is reported, never inferred from a missing line."""
        task_file(self.scaffold.task_dir, "100", followup_kind="carry_over")
        lines = rof.collect(["100"], self.scaffold.task_dir,
                            self.scaffold.archived)
        self.assertEqual(len(lines), 1)
        self.assertIn("|unknown|", lines[0])
        self.assertTrue(lines[0].endswith("|absent"))

    def test_active_origin_beats_archived(self):
        task_file(self.scaffold.task_dir, "100",
                  followup_kind="risk_mitigation", verifies="[900]")
        task_file(self.scaffold.task_dir, "900", risk_code_health="high")
        task_file(self.scaffold.archived, "900", risk_code_health="low")
        line, = rof.collect(["100"], self.scaffold.task_dir,
                            self.scaffold.archived)
        self.assertIn("|high|", line)
        self.assertTrue(line.endswith("|active"))

    def test_an_archived_origin_is_found_inside_a_bundle(self):
        task_file(self.scaffold.task_dir, "100",
                  followup_kind="risk_mitigation", verifies="[900]")
        self.scaffold.bundle("900", risk_code_health="medium",
                             risk_goal_achievement="high")
        line, = rof.collect(["100"], self.scaffold.task_dir,
                            self.scaffold.archived)
        self.assertIn("|medium|high|archived", line)

    def test_a_missing_origin_is_absent_not_a_crash(self):
        task_file(self.scaffold.task_dir, "100",
                  followup_kind="risk_mitigation", verifies="[9999]")
        line, = rof.collect(["100"], self.scaffold.task_dir,
                            self.scaffold.archived)
        self.assertTrue(line.endswith("|absent"))

    def test_anchor_is_topic_quality_never_exact(self):
        task_file(self.scaffold.task_dir, "100",
                  followup_kind="risk_mitigation", anchor="900")
        task_file(self.scaffold.archived, "900", risk_code_health="low")
        line, = rof.collect(["100"], self.scaffold.task_dir,
                            self.scaffold.archived)
        self.assertIn("|topic|", line)

    def test_only_follow_ups_are_swept_by_default(self):
        task_file(self.scaffold.task_dir, "100", followup_kind="carry_over")
        task_file(self.scaffold.task_dir, "200", priority="high")
        lines = rof.collect(None, self.scaffold.task_dir, self.scaffold.archived)
        self.assertEqual([line.split("|")[0].split(":")[1] for line in lines],
                         ["100"])


    def test_an_explicitly_named_non_follow_up_still_gets_a_row(self):
        """Named ids are reported whether or not they are follow-ups.

        The alternative -- silence -- would make absence mean "not a follow-up",
        and nothing in this protocol may be inferred from a missing line.
        """
        task_file(self.scaffold.task_dir, "200", priority="high")
        lines = rof.collect(["200"], self.scaffold.task_dir,
                            self.scaffold.archived)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("ORIGIN_FACT:200|"))

    def test_a_named_non_follow_up_with_an_anchor_still_resolves_topic(self):
        """Origin resolution reads `anchor:`/`verifies:`, not `followup_kind:`."""
        task_file(self.scaffold.task_dir, "200", priority="high", anchor="900")
        task_file(self.scaffold.archived, "900", risk_code_health="high")
        line, = rof.collect(["200"], self.scaffold.task_dir,
                            self.scaffold.archived)
        self.assertIn("|topic|", line)
        self.assertIn("|high|", line)


class RealCollectorSeamTests(unittest.TestCase):
    """The producer, driven for real, feeding the consumer verbatim.

    Everything else in the roadmap suite trusts a hand-written record. This is
    the only test that would fail if the collector's field order, sentinels or
    encoding drifted from what `roadmap_policy.parse_origin_facts` expects.
    """

    def setUp(self):
        self.scaffold = Scaffold()
        self.addCleanup(self.scaffold.cleanup)

    def test_wrapper_output_feeds_the_policy_layer_unmodified(self):
        task_file(self.scaffold.task_dir, "100",
                  followup_kind="manual_verification", verifies="[900, 901]")
        task_file(self.scaffold.archived, "900", risk_code_health="medium",
                  risk_goal_achievement="low")
        self.scaffold.bundle("901", risk_code_health="low",
                             risk_goal_achievement="low")

        result = self.scaffold.run_wrapper("100")
        self.assertEqual(result.returncode, 0, result.stderr)

        # Verbatim: no reformatting, no re-splitting, no normalisation.
        rows = rp.parse_origin_facts(result.stdout.splitlines())
        self.assertIn("100", rows)
        facts = rp.reduce_origin_facts(rows["100"])

        self.assertEqual(facts.origins, ("900", "901"))
        self.assertEqual(facts.quality, "exact")
        self.assertEqual(facts.provenance, "archived")
        # The reduction takes the max across the two disagreeing origins.
        self.assertEqual(facts.rch, "medium")
        self.assertEqual(facts.setter, "900")
        self.assertEqual(rp.combine_risk(facts.rch, facts.rga), (2, 1))

    def test_delimiters_in_a_field_round_trip_producer_to_consumer(self):
        """`%`-then-`|` encoding proven ACROSS the seam, not inside one encoder.

        `risk_code_health:` is user-authored YAML, so a value carrying `|` or
        `%` is reachable. Unencoded it would split into extra fields and shift
        every column after it -- silently, because the row would still parse.
        """
        task_file(self.scaffold.task_dir, "100",
                  followup_kind="risk_mitigation", verifies="[900]")
        task_file(self.scaffold.archived, "900",
                  risk_code_health='"a|b%c"', risk_goal_achievement="low")

        result = self.scaffold.run_wrapper("100")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("a%7Cb%25c", result.stdout)

        rows = rp.parse_origin_facts(result.stdout.splitlines())["100"]
        self.assertEqual(len(rows), 1)
        origin, quality, rch, rga, source = rows[0]
        self.assertEqual((origin, quality, source), ("900", "exact", "archived"))
        self.assertEqual(rch, "a|b%c")          # decoded back to the original
        self.assertEqual(rga, "low")            # the column after it is intact

    def test_a_named_id_with_no_task_file_still_produces_a_row(self):
        result = self.scaffold.run_wrapper("4242")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = rp.parse_origin_facts(result.stdout.splitlines())
        self.assertIn("4242", rows)
        self.assertIn("no active task file", result.stderr)

    def test_every_content_state_exits_zero(self):
        for args in ((), ("100",), ("4242",)):
            with self.subTest(args=args):
                self.assertEqual(self.scaffold.run_wrapper(*args).returncode, 0)

    def test_cli_misuse_exits_two(self):
        """A silent empty result for a typo is the hazard the split prevents."""
        result = subprocess.run([WRAPPER, "--bogus"], capture_output=True,
                                text=True, cwd=PROJECT_DIR, timeout=120)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_output_is_deterministic_across_two_runs(self):
        task_file(self.scaffold.task_dir, "100",
                  followup_kind="manual_verification", verifies="[900, 901]")
        for origin in ("900", "901"):
            task_file(self.scaffold.archived, origin, risk_code_health="low")
        first = self.scaffold.run_wrapper("100").stdout
        second = self.scaffold.run_wrapper("100").stdout
        self.assertEqual(first, second)
        self.assertTrue(first.strip())          # not vacuously equal-and-empty


class LiveSmokeTests(unittest.TestCase):
    """Shape only, over the real corpus. NEVER a count of anything volatile.

    The live corpus is an unstable oracle by construction: locks, statuses and
    the in-flight set move minute to minute, and other agents run on the same
    checkout. So this asserts INVARIANTS -- exit status, that every line parses,
    that every field is inside its closed vocabulary, and that the histogram
    sums to the candidate total -- and never a lane count, a verdict, or a
    population size.
    """

    def setUp(self):
        result = subprocess.run([WRAPPER], capture_output=True, text=True,
                                cwd=PROJECT_DIR, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.lines = [line for line in result.stdout.splitlines() if line]

    def test_every_line_parses_as_a_record(self):
        self.assertTrue(self.lines, "the live corpus produced no records at all")
        for line in self.lines:
            self.assertTrue(line.startswith("ORIGIN_FACT:"), line)
            self.assertEqual(len(line[len("ORIGIN_FACT:"):].split("|")), 6, line)

    def test_every_field_is_inside_its_closed_vocabulary(self):
        rows = rp.parse_origin_facts(self.lines)
        for task_id, entries in rows.items():
            for origin, quality, _rch, _rga, source in entries:
                self.assertIn(quality, ("exact", "topic", "unknown"),
                              "%s -> %s" % (task_id, quality))
                self.assertIn(source, rof.SOURCES, "%s -> %s" % (task_id, source))
                if quality == "unknown":
                    self.assertIsNone(origin)

    def test_the_histogram_sums_to_the_candidate_total(self):
        rows = rp.parse_origin_facts(self.lines)
        histogram = {"exact": 0, "topic": 0, "unknown": 0}
        for entries in rows.values():
            histogram[entries[0][1]] += 1
        self.assertEqual(sum(histogram.values()), len(rows))

    def test_the_reduction_survives_every_live_shape(self):
        """A total function over the real data: no row combination may raise."""
        for entries in rp.parse_origin_facts(self.lines).values():
            facts = rp.reduce_origin_facts(entries)
            self.assertIn(facts.provenance,
                          ("active", "archived", "absent", "mixed"))
            rp.combine_risk(facts.rch, facts.rga)


if __name__ == "__main__":
    unittest.main()
