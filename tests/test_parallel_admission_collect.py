"""Collector tests for the parallel-admission checker (t1569_3).

Drives the impure half through its injectable seams (``_GATE_PROBE``,
``_LOCK_PROBE``, ``_STATUS_PROBE``, ``_TRACKED_SETS``, ``_DATA_TREE``,
``_LIVENESS``, ``_FETCH``, ``_BATCH_MAP``, ``_LOCAL_HOST``) -- the
``trail_gather._GATE_PROBE`` convention -- so no test needs a live repo, a
network, or a real process table.
"""

import os
import shutil
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, ".aitask-scripts", "lib"))

import parallel_admission as pa               # noqa: E402
import parallel_admission_collect as col      # noqa: E402

PROFILE = "aitasks/metadata/profiles/fast.yaml"
TASK_DOC = "aitasks/t1157_chatlink.md"

PLAN = """---
Task: t42_thing.md
Parent Task: aitasks/t1157_chatlink.md
Sibling Tasks: aitasks/t99_other.md
---

# t42

Modify `.aitask-scripts/lib/thing.py` and `%s`.
""" % PROFILE


class FrontmatterTests(unittest.TestCase):
    """Citation noise is removed by stripping, not by a namespace rule."""

    def test_frontmatter_citations_are_stripped_and_reported(self):
        body, stripped = col.strip_frontmatter(PLAN)
        self.assertNotIn("Parent Task", body)
        self.assertIn(TASK_DOC, stripped)
        self.assertIn("aitasks/t99_other.md", stripped)

    def test_body_paths_survive_the_strip(self):
        body, _ = col.strip_frontmatter(PLAN)
        self.assertIn(".aitask-scripts/lib/thing.py", body)
        self.assertIn(PROFILE, body)

    def test_a_plan_without_frontmatter_is_untouched(self):
        body, stripped = col.strip_frontmatter("# t1\n\nsee a/b.py\n")
        self.assertIn("a/b.py", body)
        self.assertEqual(stripped, [])


class SurfaceFromPlanTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pa_plan_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.plan = os.path.join(self.dir, "p42_thing.md")
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write(PLAN)

    def _surface(self, tracked, dirs):
        return col.surface_from_plan("42", self.plan, tracked, dirs)[0]

    def test_frontmatter_citation_is_not_part_of_the_surface(self):
        s = self._surface({".aitask-scripts/lib/thing.py", TASK_DOC},
                          {".aitask-scripts", ".aitask-scripts/lib", "aitasks"})
        self.assertNotIn(TASK_DOC, s.paths)

    def test_a_body_declared_task_document_IS_a_modification_target(self):
        """The regression the rejected `citation` namespace rule would cause.

        A plan may legitimately declare a task document as a file it modifies;
        nothing may demote that just because of where it lives.
        """
        plan = os.path.join(self.dir, "p43_edit_tasks.md")
        with open(plan, "w", encoding="utf-8") as fh:
            fh.write("# t43\n\nRewrite `%s` in place.\n" % TASK_DOC)
        s, _ = col.surface_from_plan("43", plan, {TASK_DOC}, {"aitasks"})
        self.assertEqual(s.resolution, "resolved")
        self.assertIn(TASK_DOC, s.paths)

    def test_task_data_paths_resolve_when_the_data_corpus_is_unioned(self):
        # The union is what stops two tasks editing the same profile YAML from
        # reporting no conflict.
        s = self._surface({PROFILE}, {"aitasks", "aitasks/metadata",
                                      "aitasks/metadata/profiles"})
        self.assertIn(PROFILE, s.paths)

    def test_legacy_control_without_the_data_corpus_the_path_is_phantom(self):
        s = self._surface(set(), set())
        self.assertEqual(s.resolution, "all_phantom")
        self.assertEqual(s.paths, ())

    def test_planned_new_counts_as_resolved(self):
        plan = os.path.join(self.dir, "p44_new.md")
        with open(plan, "w", encoding="utf-8") as fh:
            fh.write("# t44\n\nCreate `.aitask-scripts/lib/brand_new.py`.\n")
        s, _ = col.surface_from_plan("44", plan, {".aitask-scripts/lib/old.py"},
                                     {".aitask-scripts", ".aitask-scripts/lib"})
        self.assertEqual(s.resolution, "resolved")
        self.assertIn(".aitask-scripts/lib/brand_new.py", s.paths)

    def test_an_unreadable_plan_is_its_own_state(self):
        s, _ = col.surface_from_plan("45", os.path.join(self.dir, "nope.md"),
                                     set(), set())
        self.assertEqual(s.resolution, "unreadable")

    def test_a_plan_with_no_extractable_paths_is_its_own_state(self):
        plan = os.path.join(self.dir, "p46_prose.md")
        with open(plan, "w", encoding="utf-8") as fh:
            fh.write("# t46\n\nAll prose, no paths at all.\n")
        s, _ = col.surface_from_plan("46", plan, set(), set())
        self.assertEqual(s.resolution, "no_extractable_paths")


class LivenessTests(unittest.TestCase):
    """The hostname guard is mandatory before any `dead` claim."""

    def setUp(self):
        self._saved = col._LIVENESS
        self.addCleanup(setattr, col, "_LIVENESS", self._saved)

    def _dead_probe(self):
        col._LIVENESS = lambda pid, st, kind: "dead"

    def test_cross_host_is_unknown_never_dead(self):
        self._dead_probe()
        meta = {"hostname": "otherbox", "pid": "1", "pid_starttime": "2",
                "pid_starttime_kind": "proc"}
        liveness, same_host = col.classify_liveness(meta, True, "thisbox")
        self.assertEqual(liveness, "unknown")
        self.assertFalse(same_host)

    def test_unknown_hostname_is_not_comparable_either(self):
        self._dead_probe()
        meta = {"hostname": "unknown", "pid": "1"}
        self.assertEqual(col.classify_liveness(meta, True, "unknown")[0], "unknown")

    def test_same_host_positive_control_does_classify_dead(self):
        # Without this the cross-host assertion above would pass vacuously.
        self._dead_probe()
        meta = {"hostname": "thisbox", "pid": "1", "pid_starttime": "2",
                "pid_starttime_kind": "proc"}
        self.assertEqual(col.classify_liveness(meta, True, "thisbox")[0], "dead")

    def test_implementing_with_no_lock_is_status_only(self):
        self.assertEqual(col.classify_liveness({}, True, "thisbox")[0], "status_only")

    def test_locked_alive_but_not_implementing_is_lock_only(self):
        col._LIVENESS = lambda pid, st, kind: "alive"
        meta = {"hostname": "thisbox", "pid": "1"}
        self.assertEqual(col.classify_liveness(meta, False, "thisbox")[0], "lock_only")

    def test_locked_alive_and_implementing_is_live(self):
        col._LIVENESS = lambda pid, st, kind: "alive"
        meta = {"hostname": "thisbox", "pid": "1"}
        self.assertEqual(col.classify_liveness(meta, True, "thisbox")[0], "live")

    def test_anchorless_lock_is_unknown_not_dead(self):
        col._LIVENESS = lambda pid, st, kind: "unknown"
        meta = {"hostname": "thisbox"}
        self.assertEqual(col.classify_liveness(meta, True, "thisbox")[0], "unknown")


class TimestampTests(unittest.TestCase):
    def test_valid(self):
        at, reason = col.parse_ts("2026-08-30 08:31")
        self.assertIsInstance(at, int)
        self.assertIsNone(reason)

    def test_absent(self):
        self.assertEqual(col.parse_ts(None), (None, "absent"))
        self.assertEqual(col.parse_ts(""), (None, "absent"))

    def test_malformed(self):
        self.assertEqual(col.parse_ts("not-a-date")[1], "malformed")
        self.assertEqual(col.parse_ts("2026-13-45 99:99")[1], "malformed")


class StatusProbeTests(unittest.TestCase):
    """The third enumeration source -- the t887 false-CLEAR regression."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pa_status_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "aitasks", "archived"))

    def _task(self, name, status, updated="2026-08-30 08:00", sub=""):
        d = os.path.join(self.root, "aitasks", sub) if sub else os.path.join(self.root, "aitasks")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write("---\nstatus: %s\nupdated_at: %s\n---\n\nbody\n" % (status, updated))

    def test_finds_an_implementing_task_with_no_lock_and_no_ledger(self):
        self._task("t887_manual.md", "Implementing")
        ev, ids = col.probe_status_source(self.root)
        self.assertEqual(ev.status, "ok")
        self.assertIn("887", ids)

    def test_ignores_non_implementing_tasks(self):
        self._task("t1_ready.md", "Ready")
        _ev, ids = col.probe_status_source(self.root)
        self.assertEqual(ids, {})

    def test_ignores_archived_tasks(self):
        self._task("t2_old.md", "Implementing", sub="archived")
        _ev, ids = col.probe_status_source(self.root)
        self.assertEqual(ids, {})

    def test_finds_child_tasks(self):
        self._task("t1569_3_child.md", "Implementing", sub="t1569")
        _ev, ids = col.probe_status_source(self.root)
        self.assertIn("1569_3", ids)

    def test_carries_updated_at_for_the_claim_age(self):
        self._task("t887_manual.md", "Implementing", updated="2026-08-13 09:00")
        _ev, ids = col.probe_status_source(self.root)
        self.assertEqual(ids["887"]["updated_at"], "2026-08-13 09:00")

    def test_a_missing_task_dir_is_unavailable_not_empty(self):
        ev, ids = col.probe_status_source(os.path.join(self.root, "nope"))
        self.assertEqual(ev.status, "unavailable")
        self.assertEqual(ids, {})


class DataCorpusTests(unittest.TestCase):
    def test_a_missing_data_ref_is_a_content_state(self):
        saved = col._git
        self.addCleanup(setattr, col, "_git", saved)
        col._git = lambda *a, **k: (1, "")
        files, dirs, reason = col.data_tracked_sets(".")
        self.assertEqual((files, dirs), (set(), set()))
        self.assertEqual(reason, "no_local_ref")

    def test_directory_prefixes_are_derived(self):
        saved = col._git
        self.addCleanup(setattr, col, "_git", saved)
        col._git = lambda *a, **k: (0, "aitasks/metadata/profiles/fast.yaml\n")
        files, dirs, reason = col.data_tracked_sets(".")
        self.assertIsNone(reason)
        self.assertIn("aitasks/metadata/profiles/fast.yaml", files)
        self.assertIn("aitasks/metadata/profiles", dirs)
        self.assertIn("aitasks", dirs)


class CollectIntegrationTests(unittest.TestCase):
    """End-to-end through `collect`, with every external seam injected."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pa_collect_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "aiplans", "p1569"))
        self._write("aiplans/p1569/p1569_3_me.md",
                    "---\nTask: t.md\nParent Task: aitasks/t1569_x.md\n---\n\n"
                    "Edit `%s`.\n" % PROFILE)
        self._write("aiplans/p9_other.md",
                    "# t9\n\nAlso edit `%s`.\n" % PROFILE)
        self._saved = {n: getattr(col, n) for n in
                       ("_GATE_PROBE", "_LOCK_PROBE", "_STATUS_PROBE",
                        "_TRACKED_SETS", "_DATA_TREE", "_LIVENESS", "_FETCH",
                        "_BATCH_MAP", "_LOCAL_HOST")}
        self.addCleanup(self._restore)
        col._GATE_PROBE = lambda root: (pa.SourceEvidence("gate"), {})
        col._LOCK_PROBE = lambda root: (pa.SourceEvidence("lock"), {
            "9": {"hostname": "thisbox", "locked_at": "2026-08-30 08:00",
                  "pid": "1", "pid_starttime": "2", "pid_starttime_kind": "proc"}})
        col._STATUS_PROBE = lambda root, **kw: (pa.SourceEvidence("status"), {})
        col._TRACKED_SETS = lambda root: (set(), set())
        col._LIVENESS = lambda pid, st, kind: "alive"
        col._FETCH = lambda root: True
        col._BATCH_MAP = lambda root, with_recovered=False: []
        col._LOCAL_HOST = "thisbox"

    def _restore(self):
        for n, v in self._saved.items():
            setattr(col, n, v)

    def _write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    # Anchor `now` to the fixture's own lock timestamp, so the holder is fresh
    # by construction. A hard-coded epoch silently ages the fixture past
    # --max-claim-age and turns every CONFLICT assertion into CLEAR_CAVEATED.
    NOW = col.parse_ts("2026-08-30 08:05")[0]

    def _collect(self, with_data=True, freshness="require-fresh"):
        col._DATA_TREE = (
            (lambda root: ({PROFILE},
                           {"aitasks", "aitasks/metadata", "aitasks/metadata/profiles"},
                           None))
            if with_data else (lambda root: (set(), set(), "no_local_ref")))
        return col.collect(self.root, "1569_3", source="plan",
                           freshness=freshness, now=self.NOW)

    def test_two_tasks_editing_the_same_profile_yaml_conflict(self):
        self.assertEqual(pa.decide(self._collect()).verdict, "CONFLICT")

    def test_legacy_control_without_the_data_corpus_it_is_invisible(self):
        # Same fixture, no data branch: the paths are phantom on both sides, so
        # the candidate surface is empty and the answer is UNCHECKABLE -- NOT a
        # silent CLEAR. That is what makes the union load-bearing.
        result = pa.decide(self._collect(with_data=False))
        self.assertNotEqual(result.verdict, "CONFLICT")
        self.assertNotEqual(result.verdict, "CLEAR")

    def test_the_candidate_is_excluded_from_its_own_comparison(self):
        col._LOCK_PROBE = lambda root: (pa.SourceEvidence("lock"), {
            "1569_3": {"hostname": "thisbox", "locked_at": "2026-08-30 08:00"}})
        col._STATUS_PROBE = lambda root, **kw: (
            pa.SourceEvidence("status"), {"1569_3": {"updated_at": "2026-08-30 08:00"}})
        result = pa.decide(self._collect())
        # Nothing remains to compare against, so the candidate cannot conflict
        # with its own plan -- and the exclusion happens BEFORE the records are
        # built, so there is no INFLIGHT: row for it either.
        self.assertEqual(result.verdict, "CLEAR")
        self.assertFalse([l for l in result.lines if l.startswith("INFLIGHT:")])
        self.assertFalse([l for l in result.lines if l.startswith("OVERLAP:")])

    def test_corpus_records_report_both_corpora(self):
        result = pa.decide(self._collect(with_data=False))
        corpora = [l for l in result.lines if l.startswith("CORPUS:")]
        self.assertEqual(len(corpora), 2)
        self.assertTrue(any("CORPUS:data|unavailable" in l for l in corpora))

    def test_allow_cached_caveats_where_require_fresh_does_not(self):
        # Both modes see the same overlap; only the lock evidence differs.
        self.assertEqual(pa.decide(self._collect(freshness="allow-cached")).verdict,
                         "CONFLICT")

    def test_determinism_two_collects_render_identically(self):
        a = pa.render(pa.decide(self._collect()))
        b = pa.render(pa.decide(self._collect()))
        self.assertEqual(a, b)


class CliTests(unittest.TestCase):
    """CLI misuse dies; every content state exits 0."""

    def test_missing_subcommand_dies(self):
        with self.assertRaises(SystemExit) as cm:
            col.main([])
        self.assertEqual(cm.exception.code, 2)

    def test_unknown_subcommand_dies(self):
        with self.assertRaises(SystemExit) as cm:
            col.main(["frobnicate"])
        self.assertEqual(cm.exception.code, 2)

    def test_check_without_candidate_dies(self):
        with self.assertRaises(SystemExit) as cm:
            col.main(["check", "--from", "plan"])
        self.assertEqual(cm.exception.code, 2)

    def test_unknown_flag_dies(self):
        with self.assertRaises(SystemExit) as cm:
            col.main(["check", "--candidate", "1", "--wat", "x"])
        self.assertEqual(cm.exception.code, 2)

    def test_a_typod_plan_path_dies_rather_than_returning_a_silent_verdict(self):
        with self.assertRaises(SystemExit) as cm:
            col.main(["check", "--candidate", "1", "--plan", "/no/such/plan.md"])
        self.assertEqual(cm.exception.code, 2)

    def test_non_positive_safety_thresholds_are_rejected(self):
        """A disarming threshold is misuse, not an ordinary option.

        --hub-threshold <= 0 makes every path (count 0 included) satisfy
        `count >= threshold`, so every specific overlap is demoted to a hub
        caveat; --max-claim-age <= 0 puts every claim past the bound and into
        the advisory tier. Either turns a real CONFLICT into CLEAR_CAVEATED on
        an otherwise-ordinary invocation.
        """
        for flag in ("--hub-threshold", "--max-claim-age"):
            for value in ("0", "-1", "-86400"):
                with self.assertRaises(SystemExit) as cm:
                    col.main(["check", "--candidate", "1", flag, value])
                self.assertEqual(cm.exception.code, 2, (flag, value))

    # NOTE: an earlier version of this file asserted that `1` is an acceptable
    # threshold on `check`, on the reasoning that it is "still count-dependent".
    # That reasoning was wrong in practice -- almost every real path has >= 1
    # task touch, so `--hub-threshold 1` demotes essentially everything
    # (measured: CONFLICT 24 -> 3 over 124 candidates), and `--max-claim-age 1`
    # makes every claim older than a second advisory. The floor is the shared
    # default, not 1.

    def test_check_refuses_a_threshold_below_the_shared_default(self):
        """A CONFLICT is not overridable, so no ordinary flag may weaken it."""
        for flag, floor in (("--hub-threshold", pa.HUB_THRESHOLD),
                            ("--max-claim-age", pa.MAX_CLAIM_AGE_S)):
            for value in (1, floor // 2, floor - 1):
                with self.assertRaises(SystemExit) as cm:
                    col.main(["check", "--candidate", "1", flag, str(value)])
                self.assertEqual(cm.exception.code, 2, (flag, value))

    def test_check_accepts_the_default_and_anything_stricter(self):
        # Both knobs are monotone in strictness: raising either can only turn
        # hub overlaps back into specific ones and advisory claims back into
        # blocking ones. Tightening is always safe.
        for value in (pa.HUB_THRESHOLD, pa.HUB_THRESHOLD + 1, 500):
            _verb, opts = col._parse_args(
                ["check", "--candidate", "1", "--hub-threshold", str(value)])
            self.assertEqual(opts["hub_threshold"], value)
        for value in (pa.MAX_CLAIM_AGE_S, pa.MAX_CLAIM_AGE_S * 10):
            _verb, opts = col._parse_args(
                ["check", "--candidate", "1", "--max-claim-age", str(value)])
            self.assertEqual(opts["max_claim_age"], value)

    def test_replay_may_sweep_thresholds_freely(self):
        """`replay` renders no admission decision; sweeping is its purpose."""
        for value in ("1", "5", "500"):
            _verb, opts = col._parse_args(
                ["replay", "--candidates", "-", "--hub-threshold", value])
            self.assertEqual(opts["hub_threshold"], int(value))

    def test_neither_verb_accepts_a_non_positive_threshold(self):
        for verb, extra in (("check", ["--candidate", "1"]),
                            ("replay", ["--candidates", "-"])):
            for flag in ("--hub-threshold", "--max-claim-age"):
                for value in ("0", "-1"):
                    with self.assertRaises(SystemExit) as cm:
                        col.main([verb] + extra + [flag, value])
                    self.assertEqual(cm.exception.code, 2, (verb, flag, value))

    def test_negative_max_lock_age_is_rejected(self):
        with self.assertRaises(SystemExit) as cm:
            col.main(["check", "--candidate", "1", "--max-lock-age", "-1"])
        self.assertEqual(cm.exception.code, 2)

    def test_zero_max_lock_age_is_allowed(self):
        _verb, opts = col._parse_args(
            ["check", "--candidate", "1", "--max-lock-age", "0"])
        self.assertEqual(opts["max_lock_age"], 0)

    def test_plan_is_rejected_for_replay(self):
        """--plan names one file; replay judges many candidates.

        Accepting and ignoring it would report rates for the on-disk plans while
        the caller believed they were measuring the supplied one.
        """
        with tempfile.NamedTemporaryFile(suffix=".md") as fh:
            with self.assertRaises(SystemExit) as cm:
                col.main(["replay", "--candidates", "-", "--plan", fh.name])
            self.assertEqual(cm.exception.code, 2)

    def test_plan_is_still_accepted_for_check(self):
        with tempfile.NamedTemporaryFile(suffix=".md") as fh:
            _verb, opts = col._parse_args(
                ["check", "--candidate", "1", "--plan", fh.name])
            self.assertEqual(opts["plan"], fh.name)

    def test_bad_enum_values_die(self):
        for argv in (["check", "--candidate", "1", "--from", "sideways"],
                     ["check", "--candidate", "1", "--lock-freshness", "maybe"],
                     ["check", "--candidate", "1", "--max-claim-age", "soon"]):
            with self.assertRaises(SystemExit) as cm:
                col.main(argv)
            self.assertEqual(cm.exception.code, 2, argv)



class ReplayInvariantTests(unittest.TestCase):
    """`replay` must judge every candidate against ONE identical world."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pa_replay_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        # Three candidates; t9 is the one that is actually in flight and whose
        # plan collides with the others.
        for tid, body in (("9", PROFILE), ("11", PROFILE), ("12", PROFILE)):
            self._write("aiplans/p%s_x.md" % tid, "# t%s\n\nEdit `%s`.\n" % (tid, body))
        self._saved = {n: getattr(col, n) for n in
                       ("_GATE_PROBE", "_LOCK_PROBE", "_STATUS_PROBE",
                        "_TRACKED_SETS", "_DATA_TREE", "_LIVENESS", "_FETCH",
                        "_BATCH_MAP", "_LOCAL_HOST")}
        self.addCleanup(self._restore)
        self.calls = {"batch": 0, "corpus": 0}
        col._GATE_PROBE = lambda root: (pa.SourceEvidence("gate"), {})
        col._LOCK_PROBE = lambda root: (pa.SourceEvidence("lock"), {
            "9": {"hostname": "thisbox", "locked_at": "2026-08-30 08:00",
                  "pid": "1", "pid_starttime": "2", "pid_starttime_kind": "proc"}})
        col._STATUS_PROBE = lambda root, **kw: (pa.SourceEvidence("status"), {})
        col._TRACKED_SETS = self._tracked
        col._DATA_TREE = lambda root: ({PROFILE},
                                       {"aitasks", "aitasks/metadata",
                                        "aitasks/metadata/profiles"}, None)
        col._LIVENESS = lambda pid, st, kind: "alive"
        col._FETCH = lambda root: True
        col._BATCH_MAP = self._batch
        col._LOCAL_HOST = "thisbox"

    def _tracked(self, root):
        self.calls["corpus"] += 1
        return set(), set()

    def _batch(self, root, with_recovered=False):
        self.calls["batch"] += 1
        return []

    def _restore(self):
        for n, v in self._saved.items():
            setattr(col, n, v)

    def _write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def _replay(self, order):
        listing = os.path.join(self.root, "cands.txt")
        with open(listing, "w", encoding="utf-8") as fh:
            fh.write("\n".join(order) + "\n")
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            col.main(["replay", "--candidates", listing, "--from", "plan",
                      "--lock-freshness", "require-fresh", "--root", self.root])
        return buf.getvalue().splitlines()

    def test_rates_do_not_depend_on_candidate_order(self):
        """The self-exclusion leak.

        `collect` removes the candidate from the comparison population. If the
        base snapshot is built with self-exclusion, whichever candidate is
        listed FIRST is dropped from every later comparison -- so an in-flight
        task listed first makes itself invisible and understates CONFLICT.
        Measured on the live corpus before the fix: 24 -> 17 of 124.
        """
        first = [l for l in self._replay(["9", "11", "12"]) if l.startswith("RATES:")]
        last = [l for l in self._replay(["11", "12", "9"]) if l.startswith("RATES:")]
        self.assertEqual(first, last)

    def test_the_inflight_task_is_still_compared_when_listed_first(self):
        # Discriminating control: t11 collides with in-flight t9, so it must
        # CONFLICT regardless of where t9 sits in the candidate list.
        for order in (["9", "11", "12"], ["11", "12", "9"]):
            out = self._replay(order)
            row = [l for l in out if l.startswith("VERDICT_FOR:11|")]
            self.assertEqual(row, ["VERDICT_FOR:11|CONFLICT"], order)

    def test_a_candidate_never_conflicts_with_itself(self):
        out = self._replay(["9", "11", "12"])
        self.assertIn("VERDICT_FOR:9|CLEAR", out)

    def test_one_batch_map_and_one_corpus_for_the_whole_run(self):
        """One frozen snapshot, or the rates are not comparable."""
        self.calls = {"batch": 0, "corpus": 0}
        self._replay(["9", "11", "12"])
        self.assertEqual(self.calls["batch"], 1)
        self.assertEqual(self.calls["corpus"], 1)

    def test_every_candidate_surface_is_read_before_any_verdict(self):
        """One snapshot means plans too, not just locks and the batch map.

        Reading plans inside the reporting loop lets a concurrent edit mix plan
        states across a single run, so the rates describe no world that ever
        existed. Assert the ordering directly: no plan read may happen after the
        first verdict is computed.
        """
        state = {"decided": False, "late_reads": []}
        real_surface, real_decide = col.surface_from_plan, pa.decide
        self.addCleanup(setattr, col, "surface_from_plan", real_surface)
        self.addCleanup(setattr, pa, "decide", real_decide)

        def surface(ref, path, tracked, dirs):
            if state["decided"]:
                state["late_reads"].append(ref)
            return real_surface(ref, path, tracked, dirs)

        def decide(inp):
            state["decided"] = True
            return real_decide(inp)

        col.surface_from_plan, pa.decide = surface, decide
        self._replay(["9", "11", "12"])
        self.assertEqual(state["late_reads"], [],
                         "plans re-read after evaluation began: %r"
                         % (state["late_reads"],))

    def test_each_candidate_plan_is_read_exactly_once(self):
        # The first candidate used to be read twice -- once building the base,
        # once when its own turn came -- so it could be judged against a plan
        # state no other candidate saw.
        reads = []
        real_surface = col.surface_from_plan
        self.addCleanup(setattr, col, "surface_from_plan", real_surface)
        col.surface_from_plan = lambda ref, path, t, d: (
            reads.append(ref) or real_surface(ref, path, t, d))
        self._replay(["9", "11", "12"])
        self.assertEqual(sorted(reads), ["11", "12", "9"])

    def test_a_repeated_candidate_is_still_read_once(self):
        reads = []
        real_surface = col.surface_from_plan
        self.addCleanup(setattr, col, "surface_from_plan", real_surface)
        col.surface_from_plan = lambda ref, path, t, d: (
            reads.append(ref) or real_surface(ref, path, t, d))
        self._replay(["9", "11", "9"])
        self.assertEqual(sorted(reads), ["11", "9"])

    def test_an_empty_candidate_list_is_a_content_state(self):
        import contextlib
        import io
        listing = os.path.join(self.root, "empty.txt")
        open(listing, "w").close()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = col.main(["replay", "--candidates", listing, "--root", self.root])
        self.assertEqual(rc, 0)
        self.assertIn("RATES:0|0|0|0|0", buf.getvalue())

if __name__ == "__main__":
    unittest.main()
