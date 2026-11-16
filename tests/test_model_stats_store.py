#!/usr/bin/env python3
"""Tests for lib/model_stats_store.py and aitask_model_stats.py (t1912_1).

Scratch repos plus a bare ``origin`` under a temp dir; never the real
repository. Global/system git config and HOME are isolated per test.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
LIB = REPO / ".aitask-scripts" / "lib"
CLI = REPO / ".aitask-scripts" / "aitask_model_stats.py"
sys.path.insert(0, str(LIB))

import model_stats_store as mss  # noqa: E402
import orphan_ref_store as ors  # noqa: E402

D = date.fromisoformat


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check,
                          capture_output=True, text=True).stdout.strip()


class IsolatedGit(unittest.TestCase):
    """Per-test temp dir with git config and HOME isolated."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="ait-mss-")
        self.tmp = Path(self._td.name)
        home = self.tmp / "home"
        home.mkdir()
        env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
               "HOME": str(home), "GIT_TERMINAL_PROMPT": "0"}
        self._env = mock.patch.dict(os.environ, env)
        self._env.start()
        for key in ("TASK_DIR", "AIT_STATS_FETCH_TIMEOUT"):
            os.environ.pop(key, None)
        self.remote = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", str(self.remote))

    def tearDown(self):
        self._env.stop()
        self._td.cleanup()

    # ---------------------------------------------------------- fixtures
    def repo(self, name, remote=True) -> Path:
        root = self.tmp / name
        root.mkdir()
        git(root, "init", "-q", "-b", "main")
        git(root, "config", "user.email", "t@example.com")
        git(root, "config", "user.name", "T")
        if remote:
            git(root, "remote", "add", "origin", str(self.remote))
        return root

    def bump(self, root, model="opus", skill="pick", day="2026-11-12", agent="claudecode"):
        return mss.update(root, agent,
                          lambda b: mss.bump_usage(b, model, skill, D(day)))

    @staticmethod
    def runs(root, model="opus", skill="pick", agent="claudecode"):
        stats = mss.load_agent_stats(root, agent)
        try:
            return stats[model]["usagestats"][skill]["all_time"]["runs"]
        except KeyError:
            return 0

    def origin_tip(self):
        return git(self.remote, "rev-parse", "--verify", "-q",
                   "refs/heads/aitask-stats", check=False) or None

    def origin_blob(self, agent="claudecode"):
        return json.loads(git(self.remote, "show", f"aitask-stats:{agent}.json"))


def write_legacy(root, rows, agent="claudecode", task_dir="aitasks"):
    meta = Path(root) / task_dir / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / f"models_{agent}.json").write_text(json.dumps({"models": rows}, indent=2))


def usage_entry(runs, month="2026-11", week="2026-W46"):
    return {"all_time": {"runs": runs}, "prev_month": {"period": "", "runs": 0},
            "month": {"period": month, "runs": runs},
            "week": {"period": week, "runs": runs}}


# ====================================================================== pure

class TestBumpUsage(unittest.TestCase):
    def entry(self, blob, model="m", skill="pick"):
        return blob["models"][model]["usagestats"][skill]

    def test_fresh(self):
        blob, value = mss.bump_usage(mss.empty_blob(), "m", "pick", D("2026-11-12"))
        self.assertEqual(value, 1)
        self.assertEqual(self.entry(blob), {
            "all_time": {"runs": 1}, "prev_month": {"period": "", "runs": 0},
            "month": {"period": "2026-11", "runs": 1},
            "week": {"period": "2026-W46", "runs": 1}})

    def test_same_week_then_new_week_same_month(self):
        blob, _ = mss.bump_usage(mss.empty_blob(), "m", "pick", D("2026-11-12"))
        blob, v = mss.bump_usage(blob, "m", "pick", D("2026-11-13"))
        self.assertEqual(v, 2)
        self.assertEqual(self.entry(blob)["week"], {"period": "2026-W46", "runs": 2})
        blob, v = mss.bump_usage(blob, "m", "pick", D("2026-11-17"))
        self.assertEqual(v, 3)
        self.assertEqual(self.entry(blob)["week"], {"period": "2026-W47", "runs": 1})
        self.assertEqual(self.entry(blob)["all_time"], {"runs": 3})

    def test_adjacent_month_rolls_prev_month(self):
        blob, _ = mss.bump_usage(mss.empty_blob(), "m", "pick", D("2026-10-30"))
        blob, _ = mss.bump_usage(blob, "m", "pick", D("2026-10-31"))
        blob, v = mss.bump_usage(blob, "m", "pick", D("2026-11-02"))
        e = self.entry(blob)
        self.assertEqual(v, 1)
        self.assertEqual(e["prev_month"], {"period": "2026-10", "runs": 2})
        self.assertEqual(e["month"], {"period": "2026-11", "runs": 1})

    def test_month_gap_empties_prev_month(self):
        blob, _ = mss.bump_usage(mss.empty_blob(), "m", "pick", D("2026-08-03"))
        blob, _ = mss.bump_usage(blob, "m", "pick", D("2026-11-12"))
        self.assertEqual(self.entry(blob)["prev_month"], {"period": "", "runs": 0})

    def test_year_boundary_keeps_iso_week(self):
        # 2026-12-31 and 2027-01-01 are both ISO week 2026-W53.
        blob, _ = mss.bump_usage(mss.empty_blob(), "m", "pick", D("2026-12-31"))
        blob, _ = mss.bump_usage(blob, "m", "pick", D("2027-01-01"))
        e = self.entry(blob)
        self.assertEqual(e["week"], {"period": "2026-W53", "runs": 2})
        self.assertEqual(e["month"], {"period": "2027-01", "runs": 1})
        self.assertEqual(e["prev_month"], {"period": "2026-12", "runs": 1})
        blob, _ = mss.bump_usage(blob, "m", "pick", D("2027-01-04"))
        self.assertEqual(self.entry(blob)["week"], {"period": "2027-W01", "runs": 1})

    def test_null_and_missing_fields_follow_jq(self):
        blob = {"schema": 1, "models": {"m": {"usagestats": {
            "pick": {"all_time": {"runs": None}, "prev_month": False,
                     "month": {"period": "2026-11"}}}}}}
        out, v = mss.bump_usage(blob, "m", "pick", D("2026-11-12"))
        e = self.entry(out)
        self.assertEqual(v, 1)  # null + 1
        self.assertEqual(e["all_time"], {"runs": 1})
        self.assertEqual(e["prev_month"], {"period": "", "runs": 0})  # //= replaces false
        self.assertEqual(e["week"], {"period": "2026-W46", "runs": 1})

    def test_non_object_entry_starts_fresh_and_input_unchanged(self):
        blob = {"schema": 1, "models": {"m": {"usagestats": {"pick": 7}}}}
        before = copy.deepcopy(blob)
        out, v = mss.bump_usage(blob, "m", "pick", D("2026-11-12"))
        self.assertEqual(v, 1)
        self.assertEqual(blob, before)
        self.assertEqual(self.entry(out)["all_time"], {"runs": 1})

    def test_extra_prev_month_keys_are_carried(self):
        blob = {"schema": 1, "models": {"m": {"usagestats": {"pick": {
            "all_time": {"runs": 4}, "prev_month": {"period": "2026-10", "runs": 3, "x": 1},
            "month": {"period": "2026-11", "runs": 1},
            "week": {"period": "2026-W45", "runs": 1}}}}}}
        out, _ = mss.bump_usage(blob, "m", "pick", D("2026-11-12"))
        self.assertEqual(self.entry(out)["prev_month"], {"period": "2026-10", "runs": 3, "x": 1})


class TestRecordVerified(unittest.TestCase):
    def entry(self, blob):
        return blob["models"]["m"]["verifiedstats"]["pick"]

    def test_fresh_and_average(self):
        blob, v = mss.record_verified(mss.empty_blob(), "m", "pick", 100, D("2026-11-12"))
        self.assertEqual(v, 100)
        blob, v = mss.record_verified(blob, "m", "pick", 80, D("2026-11-12"))
        self.assertEqual(v, 90)
        e = self.entry(blob)
        self.assertEqual(e["all_time"], {"runs": 2, "score_sum": 180})
        self.assertEqual(e["week"], {"period": "2026-W46", "runs": 2, "score_sum": 180})
        self.assertNotIn("verified", blob["models"]["m"])

    def test_flat_legacy_entry_is_bucketed(self):
        blob = {"schema": 1, "models": {"m": {"verifiedstats": {"pick": {"runs": 3, "score_sum": 240}}}}}
        out, v = mss.record_verified(blob, "m", "pick", 100, D("2026-11-12"))
        e = self.entry(out)
        self.assertEqual(e["all_time"], {"runs": 4, "score_sum": 340})
        self.assertEqual(e["month"], {"period": "2026-11", "runs": 1, "score_sum": 100})
        self.assertEqual(e["prev_month"], {"period": "", "runs": 0, "score_sum": 0})
        self.assertEqual(v, 85)

    def test_flat_entry_without_score_sum(self):
        blob = {"schema": 1, "models": {"m": {"verifiedstats": {"pick": {"runs": 1}}}}}
        out, v = mss.record_verified(blob, "m", "pick", 60, D("2026-11-12"))
        self.assertEqual(self.entry(out)["all_time"], {"runs": 2, "score_sum": 60})
        self.assertEqual(v, 30)

    def test_half_rounds_away_from_zero(self):
        # 20 / 8 = 2.5: jq round -> 3 (Python round would give 2).
        blob = {"schema": 1, "models": {"m": {"verifiedstats": {"pick": {
            "all_time": {"runs": 7, "score_sum": 0},
            "prev_month": {"period": "", "runs": 0, "score_sum": 0},
            "month": {"period": "2026-11", "runs": 7, "score_sum": 0},
            "week": {"period": "2026-W46", "runs": 7, "score_sum": 0}}}}}}
        _, v = mss.record_verified(blob, "m", "pick", 20, D("2026-11-12"))
        self.assertEqual(v, 3)

    def test_month_rollover_with_scores(self):
        blob, _ = mss.record_verified(mss.empty_blob(), "m", "pick", 40, D("2026-10-31"))
        blob, _ = mss.record_verified(blob, "m", "pick", 100, D("2026-11-01"))
        e = self.entry(blob)
        self.assertEqual(e["prev_month"], {"period": "2026-10", "runs": 1, "score_sum": 40})
        self.assertEqual(e["month"], {"period": "2026-11", "runs": 1, "score_sum": 100})


class TestMerge(unittest.TestCase):
    def test_all_time_adds_and_same_periods_sum(self):
        a = usage_entry(2)
        b = usage_entry(3)
        m = mss.merge_buckets(a, b)
        self.assertEqual(m["all_time"], {"runs": 5})
        self.assertEqual(m["month"], {"period": "2026-11", "runs": 5})
        self.assertEqual(m["week"], {"period": "2026-W46", "runs": 5})
        self.assertEqual(m["prev_month"], {"period": "", "runs": 0})
        self.assertNotIn("score_sum", m["month"])

    def test_reslot_around_newest_month(self):
        a = {"all_time": {"runs": 5}, "prev_month": {"period": "2026-09", "runs": 2},
             "month": {"period": "2026-10", "runs": 3}, "week": {"period": "2026-W44", "runs": 1}}
        b = {"all_time": {"runs": 1}, "prev_month": {"period": "", "runs": 0},
             "month": {"period": "2026-11", "runs": 1}, "week": {"period": "2026-W46", "runs": 1}}
        m = mss.merge_buckets(a, b)
        self.assertEqual(m["month"], {"period": "2026-11", "runs": 1})
        self.assertEqual(m["prev_month"], {"period": "2026-10", "runs": 3})
        self.assertEqual(m["week"], {"period": "2026-W46", "runs": 1})
        self.assertEqual(m["all_time"], {"runs": 6})

    def test_gap_leaves_prev_month_empty(self):
        a = usage_entry(1, month="2026-08", week="2026-W32")
        b = usage_entry(1, month="2026-11")
        m = mss.merge_buckets(a, b)
        self.assertEqual(m["prev_month"], {"period": "", "runs": 0})
        self.assertEqual(m["month"], {"period": "2026-11", "runs": 1})

    def test_year_boundary_prev_month(self):
        a = usage_entry(2, month="2026-12", week="2026-W53")
        b = usage_entry(1, month="2027-01", week="2026-W53")
        m = mss.merge_buckets(a, b)
        self.assertEqual(m["prev_month"], {"period": "2026-12", "runs": 2})
        self.assertEqual(m["week"], {"period": "2026-W53", "runs": 3})

    def test_flat_side_counts_all_time_only(self):
        flat = {"runs": 4, "score_sum": 320}
        b = {"all_time": {"runs": 1, "score_sum": 100},
             "prev_month": {"period": "", "runs": 0, "score_sum": 0},
             "month": {"period": "2026-11", "runs": 1, "score_sum": 100},
             "week": {"period": "2026-W46", "runs": 1, "score_sum": 100}}
        m = mss.merge_buckets(flat, b)
        self.assertEqual(m["all_time"], {"runs": 5, "score_sum": 420})
        self.assertEqual(m["month"], {"period": "2026-11", "runs": 1, "score_sum": 100})
        self.assertEqual(m["prev_month"], {"period": "", "runs": 0, "score_sum": 0})

    def test_merge_stats_one_sided_is_identity(self):
        legacy = {"opus": {"usagestats": {"pick": usage_entry(4)},
                           "verifiedstats": {"pick": {"runs": 2, "score_sum": 180}}}}
        out = mss.merge_stats(legacy, {})
        self.assertEqual(out, legacy)
        out["opus"]["usagestats"]["pick"]["all_time"]["runs"] = 99
        self.assertEqual(legacy["opus"]["usagestats"]["pick"]["all_time"]["runs"], 4)
        both = mss.merge_stats(legacy, {"opus": {"usagestats": {"pick": usage_entry(1)},
                                                 "verifiedstats": {}},
                                        "new": {"usagestats": {"qa": usage_entry(1)}}})
        self.assertEqual(both["opus"]["usagestats"]["pick"]["all_time"], {"runs": 5})
        self.assertEqual(both["opus"]["verifiedstats"]["pick"], {"runs": 2, "score_sum": 180})
        self.assertEqual(both["new"]["usagestats"]["qa"], usage_entry(1))

    def test_parse_blob_errors(self):
        self.assertEqual(mss.parse_blob(None), mss.empty_blob())
        for bad in (b"{", b"[]", b'{"schema": 2, "models": {}}', b'{"schema": 1}'):
            with self.assertRaises(mss.StatsError):
                mss.parse_blob(bad)
        self.assertEqual(mss.parse_blob(mss.render_blob(mss.empty_blob())), mss.empty_blob())


# ======================================================================= git

class TestWritePaths(IsolatedGit):
    def test_no_remote_record_and_load(self):
        root = self.repo("solo", remote=False)
        self.assertEqual(self.bump(root), 1)
        self.assertEqual(self.bump(root), 2)
        self.assertEqual(self.runs(root), 2)
        self.assertEqual(int(git(root, "rev-list", "--count", "refs/heads/aitask-stats")), 2)
        # The code branch and the index were never touched.
        self.assertEqual(git(root, "status", "--porcelain"), "")
        self.assertEqual(git(root, "rev-parse", "--verify", "-q", "HEAD", check=False), "")

    def test_absent_creates_root_commit(self):
        a = self.repo("a")
        self.assertIsNone(self.origin_tip())
        self.assertEqual(self.bump(a), 1)
        tip = self.origin_tip()
        self.assertIsNotNone(tip)
        self.assertEqual(git(self.remote, "rev-list", "--count", tip), "1")
        self.assertEqual(git(a, "rev-parse", "refs/heads/aitask-stats"), tip)
        self.assertEqual(self.origin_blob()["models"]["opus"]["usagestats"]["pick"]["all_time"],
                         {"runs": 1})
        # The private fetch namespace is left empty.
        self.assertEqual(git(a, "for-each-ref", "refs/aitask-stats/"), "")

    def test_local_only_history_is_published_when_remote_appears(self):
        root = self.repo("solo", remote=False)
        self.bump(root)
        self.bump(root)
        old_local = git(root, "rev-parse", "refs/heads/aitask-stats")
        git(root, "remote", "add", "origin", str(self.remote))
        self.assertEqual(self.bump(root), 3)
        tip = self.origin_tip()
        subprocess.run(["git", "merge-base", "--is-ancestor", old_local, tip],
                       cwd=root, check=True)
        self.assertEqual(self.origin_blob()["models"]["opus"]["usagestats"]["pick"]["all_time"],
                         {"runs": 3})

    def test_local_ahead_of_origin_fast_forwards(self):
        a = self.repo("a")
        self.bump(a)
        # Simulate local-only commits on top of the published tip (remote
        # dropped and re-added).
        git(a, "remote", "remove", "origin")
        self.bump(a)
        git(a, "remote", "add", "origin", str(self.remote))
        self.assertEqual(self.bump(a), 3)
        self.assertEqual(self.origin_blob()["models"]["opus"]["usagestats"]["pick"]["all_time"],
                         {"runs": 3})

    def test_diverged_fails_closed_and_refresh_does_not_move(self):
        a = self.repo("a")
        self.bump(a)
        c = self.repo("c")
        lonely = ors.build_commit(c, None, {"claudecode.json": mss.render_blob(mss.empty_blob())},
                                  "lonely", ident=mss.IDENT)
        git(c, "update-ref", "refs/heads/aitask-stats", lonely)
        with self.assertRaises(mss.StatsDiverged) as ctx:
            self.bump(c)
        self.assertEqual(ctx.exception.local, lonely)
        kind, detail = mss.refresh(c)
        self.assertEqual(kind, "diverged")
        self.assertEqual(detail, f"{lonely}|{self.origin_tip()}")
        self.assertEqual(git(c, "rev-parse", "refs/heads/aitask-stats"), lonely)
        out = subprocess.run([sys.executable, str(CLI), "bump-usage", "--root", str(c),
                              "--agent", "claudecode", "--model", "opus", "--skill", "pick"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertEqual(out.stdout, f"STATS_DIVERGED:{lonely}|{self.origin_tip()}\n")

    def test_forced_conflict_retry_loses_nothing(self):
        a, b = self.repo("a"), self.repo("b")
        self.bump(a)  # origin exists, so both clones take the PRESENT path
        statuses = []
        fired = []

        def hook(point, **ctx):
            if point == "after_push":
                statuses.append(ctx["status"])
            if point == "after_pin" and not fired:
                fired.append(True)
                self.assertEqual(self.bump(b), 2)  # B lands between A's pin and push

        with mock.patch.object(mss, "_test_hook", hook), \
                mock.patch.object(mss, "_jitter", lambda attempt: None):
            value = self.bump(a)
        self.assertEqual(value, 3)
        self.assertIn("CONFLICT", statuses)
        self.assertEqual(statuses[-1], "OK")
        self.assertEqual(self.origin_blob()["models"]["opus"]["usagestats"]["pick"]["all_time"],
                         {"runs": 3})
        mss.refresh(b)
        self.assertEqual(self.runs(a), 3)
        self.assertEqual(self.runs(b), 3)

    def test_different_agents_do_not_interfere(self):
        a = self.repo("a")
        self.bump(a, agent="claudecode")
        self.bump(a, agent="codex", model="gpt")
        self.assertEqual(self.runs(a), 1)
        self.assertEqual(self.runs(a, model="gpt", agent="codex"), 1)
        self.assertEqual(set(mss.load_all_stats(a)), {"claudecode", "codex"})


class TestVisibility(IsolatedGit):
    def setUp(self):
        super().setUp()
        seed = self.repo("seed")
        (seed / "README").write_text("x\n")
        git(seed, "add", "README")
        git(seed, "commit", "-q", "-m", "init")
        git(seed, "push", "-q", "origin", "main")
        empty = ors.build_commit(seed, None, {"aitasks/.keep": b""}, "data")
        git(seed, "push", "-q", "origin", f"{empty}:refs/heads/aitask-data")
        self.writer = self.repo("writer")

    def clone(self, name, *extra):
        path = self.tmp / name
        git(self.tmp, "clone", "-q", *extra, str(self.remote), str(path))
        git(path, "config", "user.email", "t@example.com")
        git(path, "config", "user.name", "T")
        return path

    def git_logger(self):
        real = shutil.which("git")
        bindir = self.tmp / "logbin"
        bindir.mkdir()
        log = self.tmp / "git.log"
        script = bindir / "git"
        script.write_text(f'#!/bin/sh\nprintf "%s\\t%s\\n" "$PWD" "$*" >> "{log}"\n'
                          f'exec "{real}" "$@"\n')
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return bindir, log

    def check_reader(self, reader):
        self.bump(self.writer)
        bindir, log = self.git_logger()
        with mock.patch.dict(os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}):
            self.assertEqual(self.runs(reader), 0)
            self.bump(self.writer)
            self.assertEqual(self.runs(reader), 0)  # the reader never fetches
            lines = log.read_text().splitlines() if log.exists() else []
            # Only the reader's own calls: the writer runs in this process too.
            calls = [ln.split("\t", 1)[1] for ln in lines
                     if os.path.realpath(ln.split("\t", 1)[0]).startswith(
                         os.path.realpath(reader))]
            self.assertTrue(calls, "the git logger saw no reader calls")
            for call in calls:
                verb = call.split()[0] if call.split() else ""
                self.assertNotIn(verb, ("fetch", "ls-remote", "pull", "push", "remote-https"),
                                 call)
        # A tracking ref at the newest tip (a fetch that maps it) is not a read
        # source either: only refs/heads/aitask-stats is.
        git(reader, "fetch", "-q", "origin",
            "+refs/heads/aitask-stats:refs/remotes/origin/aitask-stats")
        self.assertEqual(self.runs(reader), 0)
        git(reader, "update-ref", "-d", "refs/remotes/origin/aitask-stats")
        kind, detail = mss.refresh(reader)
        self.assertEqual(kind, "refreshed")
        self.assertEqual(detail, self.origin_tip())
        self.assertEqual(self.runs(reader), 2)
        # ... and its absence does not matter after a refresh.
        git(reader, "update-ref", "-d", "refs/remotes/origin/aitask-stats", check=False)
        self.assertEqual(self.runs(reader), 2)

    def test_default_refspec(self):
        self.check_reader(self.clone("default"))

    def test_single_branch_clone(self):
        reader = self.clone("single", "--single-branch", "--branch", "main")
        git(reader, "config", "--add", "remote.origin.fetch",
            "+refs/heads/aitask-data:refs/remotes/origin/aitask-data")
        self.check_reader(reader)
        self.assertEqual(git(reader, "for-each-ref", "refs/remotes/origin/aitask-stats"), "")

    def test_negative_refspec(self):
        reader = self.clone("negative")
        git(reader, "config", "--add", "remote.origin.fetch", "^refs/heads/aitask-stats")
        git(reader, "fetch", "-q", "origin")
        # Observed (git 2.56): fetch_pinned's explicit-refspec fetch still
        # opportunistically updates refs/remotes/origin/aitask-stats under a
        # negative refspec. Harmless: check_reader proves the loader reads
        # neither its presence nor its absence.
        self.check_reader(reader)

    def test_cli_refresh_outputs(self):
        reader = self.clone("cli")

        def cli(*args):
            return subprocess.run([sys.executable, str(CLI), *args, "--root", str(reader)],
                                  capture_output=True, text=True)

        out = cli("refresh")
        self.assertEqual((out.returncode, out.stdout), (0, "REFRESH_SKIPPED:absent\n"))
        self.bump(self.writer)
        out = cli("refresh")
        self.assertEqual((out.returncode, out.stdout), (0, f"REFRESHED:{self.origin_tip()}\n"))
        exported = json.loads(cli("export", "--agent", "claudecode").stdout)
        self.assertEqual(exported["models"]["opus"]["usagestats"]["pick"]["all_time"], {"runs": 1})
        show = cli("show").stdout.splitlines()
        self.assertEqual(show[0], f"BRANCH:{self.origin_tip()}")
        self.assertIn("claudecode/opus usagestats pick all_time=1", show)
        solo = self.repo("solo", remote=False)
        out = subprocess.run([sys.executable, str(CLI), "refresh", "--root", str(solo)],
                             capture_output=True, text=True)
        self.assertEqual((out.returncode, out.stdout), (0, "REFRESH_SKIPPED:no_remote\n"))


class TestLoader(IsolatedGit):
    def test_legacy_edit_is_seen_without_ref_change(self):
        root = self.repo("p", remote=False)
        write_legacy(root, [{"name": "opus", "usagestats": {"pick": usage_entry(4)}}])
        self.bump(root)
        sha = git(root, "rev-parse", "refs/heads/aitask-stats")
        self.assertEqual(self.runs(root), 5)
        write_legacy(root, [{"name": "opus", "usagestats": {"pick": usage_entry(10)}}])
        self.assertEqual(git(root, "rev-parse", "refs/heads/aitask-stats"), sha)
        self.assertEqual(self.runs(root), 11)

    def test_two_projects_in_one_process(self):
        p1, p2 = self.repo("p1", remote=False), self.repo("p2", remote=False)
        self.bump(p1)
        for _ in range(3):
            self.bump(p2)
        write_legacy(p1, [{"name": "opus", "usagestats": {"pick": usage_entry(10)}}])
        self.assertEqual((self.runs(p1), self.runs(p2)), (11, 3))
        self.assertEqual((self.runs(p1), self.runs(p2)), (11, 3))

    def test_marker_means_branch_only(self):
        root = self.repo("p", remote=False)
        write_legacy(root, [{"name": "opus", "usagestats": {"pick": usage_entry(4)}}])
        self.bump(root)
        self.assertEqual(self.runs(root), 5)
        tip = git(root, "rev-parse", "refs/heads/aitask-stats")
        marked = ors.build_commit(root, tip, {"migrations/claudecode.json": b"{}\n"}, "marker")
        git(root, "update-ref", "refs/heads/aitask-stats", marked, tip)
        self.assertEqual(self.runs(root), 1)
        self.assertEqual(mss.branch_state(root)["markers"], ["claudecode"])

    def test_root_isolation_under_task_dir(self):
        a, b = self.repo("A", remote=False), self.repo("B", remote=False)
        decoy = self.tmp / "C"
        write_legacy(a, [{"name": "opus", "usagestats": {"pick": usage_entry(10)}}])
        write_legacy(b, [{"name": "opus", "usagestats": {"pick": usage_entry(20)}}])
        write_legacy(a, [{"name": "opus", "usagestats": {"pick": usage_entry(100)}}],
                     task_dir="mytasks")
        write_legacy(b, [{"name": "opus", "usagestats": {"pick": usage_entry(200)}}],
                     task_dir="mytasks")
        meta = decoy / "metadata"
        meta.mkdir(parents=True)
        (meta / "models_claudecode.json").write_text(json.dumps(
            {"models": [{"name": "opus", "usagestats": {"pick": usage_entry(5000)}}]}))
        self.bump(a)
        self.bump(b)
        self.bump(b)
        with mock.patch.dict(os.environ, {"TASK_DIR": str(decoy)}):
            self.assertEqual((self.runs(a), self.runs(b)), (11, 22))
        with mock.patch.dict(os.environ, {"TASK_DIR": "mytasks"}):
            self.assertEqual((self.runs(a), self.runs(b)), (101, 202))
        with mock.patch.dict(os.environ, {"TASK_DIR": "mytasks"}):
            got = mss.load_agent_stats(a, "claudecode", metadata_path=meta)
            self.assertEqual(got["opus"]["usagestats"]["pick"]["all_time"], {"runs": 5001})

    def test_nested_root_reads_the_repository_registry(self):
        # The branch is read at the toplevel, so the legacy registry must be
        # too: from <repo>/website/deep both come from the repository (t2315).
        root = self.repo("p", remote=False)
        write_legacy(root, [{"name": "opus", "usagestats": {"pick": usage_entry(4)}}])
        # codex exists ONLY in the root registry (no branch data, no marker), so
        # load_all_stats can discover it solely through its models_*.json
        # listing; claudecode is also on the branch and would be found anyway.
        write_legacy(root, [{"name": "gpt5", "usagestats": {"pick": usage_entry(7)}}],
                     agent="codex")
        self.bump(root)
        nested = root / "website" / "deep"
        nested.mkdir(parents=True)
        self.assertEqual((self.runs(root), self.runs(nested)), (5, 5))
        everything = mss.load_all_stats(nested)
        self.assertEqual(set(everything), {"claudecode", "codex"})
        self.assertEqual(everything["codex"]["gpt5"]["usagestats"]["pick"]["all_time"],
                         {"runs": 7})
        self.assertEqual(
            everything["claudecode"]["opus"]["usagestats"]["pick"]["all_time"], {"runs": 5})

    def test_git_failure_reads_as_legacy_only(self):
        plain = self.tmp / "not-a-repo"
        write_legacy(plain, [{"name": "opus", "usagestats": {"pick": usage_entry(4)}}])
        with mock.patch("sys.stderr") as err:
            self.assertEqual(self.runs(plain), 4)
            self.assertEqual(self.runs(plain), 4)
        written = "".join(c.args[0] for c in err.write.call_args_list)
        self.assertEqual(written.count("stats branch unreadable"), 1)


class TestDataWorktreeUntouched(IsolatedGit):
    def test_store_write_leaves_data_worktree_byte_identical(self):
        seed = self.repo("seed")
        (seed / "README").write_text("x\n")
        git(seed, "add", "README")
        git(seed, "commit", "-q", "-m", "init")
        git(seed, "push", "-q", "origin", "main")
        data = ors.build_commit(seed, None, {"aitasks/t1.md": b"one\n"}, "data")
        git(seed, "push", "-q", "origin", f"{data}:refs/heads/aitask-data")

        local = self.tmp / "local"
        git(self.tmp, "clone", "-q", str(self.remote), str(local))
        git(local, "config", "user.email", "t@example.com")
        git(local, "config", "user.name", "T")
        git(local, "worktree", "add", "-q", "-b", "aitask-data", ".aitask-data",
            "origin/aitask-data")
        wt = local / ".aitask-data"
        (wt / "aitasks/t1.md").write_text("one, edited\n")      # modified tracked
        (wt / "aitasks/t2.md").write_text("untracked\n")        # untracked
        # Origin moves ahead of the local data branch.
        ahead = ors.build_commit(seed, data, {"aitasks/t3.md": b"three\n"}, "ahead")
        git(seed, "push", "-q", "origin", f"{ahead}:refs/heads/aitask-data")

        def snapshot():
            index = subprocess.run(["git", "ls-files", "-s"], cwd=wt, check=True,
                                   capture_output=True).stdout
            return (git(wt, "rev-parse", "HEAD"),
                    hashlib.sha256(index).hexdigest(),
                    subprocess.run(["git", "status", "--porcelain"], cwd=wt, check=True,
                                   capture_output=True).stdout,
                    git(local, "rev-parse", "refs/remotes/origin/aitask-data"),
                    git(local, "rev-parse", "refs/heads/aitask-data"))

        before = snapshot()
        self.bump(local)
        mss.update(local, "claudecode",
                   lambda bl: mss.record_verified(bl, "opus", "pick", 100, D("2026-11-12")))
        mss.refresh(local)
        self.assertEqual(snapshot(), before)
        self.assertEqual(self.runs(local), 1)


class TestRefreshTimeoutBound(IsolatedGit):
    """[refresh_timeout_bound] A remote that never answers costs at most ~2x
    the refresh timeout, and is reported as exactly a timeout."""

    def test_hanging_remote_is_bounded(self):
        hang = self.tmp / "hang"
        hang.write_text("#!/bin/sh\nexec sleep 30\n")
        hang.chmod(0o755)
        if " " in str(hang):
            self.skipTest("ext:: splits its command on spaces")
        reader = self.repo("reader", remote=False)
        git(reader, "remote", "add", "origin", f"ext::{hang}")
        env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "protocol.ext.allow",
               "GIT_CONFIG_VALUE_0": "always"}
        with mock.patch.dict(os.environ, env):
            t0 = time.monotonic()
            self.assertEqual(ors.probe_remote_branch(reader, mss.BRANCH, 1), "ERROR:timeout")
            elapsed = time.monotonic() - t0
            self.assertGreaterEqual(elapsed, 0.9)
            self.assertLess(elapsed, 5)

            t0 = time.monotonic()
            self.assertEqual(mss.refresh(reader, timeout=1), ("skipped", "unreachable:timeout"))
            elapsed = time.monotonic() - t0
            self.assertGreaterEqual(elapsed, 0.9)
            self.assertLess(elapsed, 5)

            t0 = time.monotonic()
            out = subprocess.run([sys.executable, str(CLI), "refresh", "--timeout", "1",
                                  "--root", str(reader)], capture_output=True, text=True)
            elapsed = time.monotonic() - t0
        self.assertEqual((out.returncode, out.stdout), (0, "REFRESH_SKIPPED:unreachable:timeout\n"))
        self.assertGreaterEqual(elapsed, 0.9)
        self.assertLess(elapsed, 5)


class TestCliValidation(IsolatedGit):
    def run_cli(self, *args):
        root = self.repo("v", remote=False)
        return subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)],
                              capture_output=True, text=True)

    def test_usage_errors(self):
        cases = [
            ("bump-usage", "--agent", "Claude", "--model", "m", "--skill", "pick"),
            ("bump-usage", "--agent", "claudecode", "--model", "M-1", "--skill", "pick"),
            ("bump-usage", "--agent", "claudecode", "--model", "m", "--skill", "a\nb"),
            ("bump-usage", "--agent", "claudecode", "--model", "m", "--skill", "a\tb"),
            ("bump-usage", "--agent", "claudecode", "--model", "m", "--skill", ""),
            ("bump-usage", "--agent", "claudecode", "--model", "m", "--skill", "pick",
             "--date", "20261112"),
            ("record-verified", "--agent", "claudecode", "--model", "m", "--skill", "pick",
             "--score", "6"),
            ("export", "--agent", "../x"),
        ]
        for args in cases:
            out = self.run_cli(*args)
            self.assertEqual(out.returncode, 2, args)
            self.assertTrue(out.stdout.startswith("STATS_ERROR:usage:"), out.stdout)
            self.assertEqual(out.stdout.count("\n"), 1)
            shutil.rmtree(self.tmp / "v")

    def test_record_and_bump_lines(self):
        root = self.repo("ok", remote=False)

        def cli(*args):
            return subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)],
                                  capture_output=True, text=True).stdout

        self.assertEqual(cli("bump-usage", "--agent", "codex", "--model", "gpt_5",
                             "--skill", "batch-review", "--date", "2026-11-12"),
                         "UPDATED:codex/gpt_5:batch-review:1\n")
        self.assertEqual(cli("record-verified", "--agent", "codex", "--model", "gpt_5",
                             "--skill", "pick", "--score", "4"),
                         "UPDATED:codex/gpt_5:pick:80\n")


class TestOverlay(IsolatedGit):
    """overlay_rows / overlay_data: the readers' seam (t1912_2)."""

    # Skills deliberately out of sorted order: the overlay must keep file order.
    ROWS = [
        {"name": "opus", "cli_id": "c-opus", "verified": {"wrap": 80, "pick": 90},
         "verifiedstats": {
             "wrap": {"all_time": {"runs": 1, "score_sum": 80}},
             "pick": {"all_time": {"runs": 2, "score_sum": 180},
                      "month": {"period": "2026-11", "runs": 2, "score_sum": 180}}},
         "usagestats": {"wrap": {"all_time": {"runs": 1}},
                        "pick": usage_entry(4)}},
        {"name": "flat", "verified": {"pick": 75},
         "verifiedstats": {"pick": {"runs": 2, "score_sum": 150}}},
        {"name": "bare", "verified": {}},
        "not-a-row",
        {"cli_id": "nameless", "usagestats": {"pick": usage_entry(9)}},
    ]

    def record(self, root, model, skill, score, day="2026-11-12"):
        return mss.update(root, "claudecode",
                          lambda b: mss.record_verified(b, model, skill, score * 20, D(day)))

    def mark(self, root):
        tip = git(root, "rev-parse", "refs/heads/aitask-stats")
        marked = ors.build_commit(root, tip, {"migrations/claudecode.json": b"{}\n"}, "marker")
        git(root, "update-ref", "refs/heads/aitask-stats", marked, tip)

    def test_empty_branch_is_identity_in_content_and_order(self):
        root = self.repo("p", remote=False)
        rows = copy.deepcopy(self.ROWS)
        out = mss.overlay_rows(root, "claudecode", rows)
        self.assertEqual(out, self.ROWS)
        self.assertEqual(list(out[0]["verifiedstats"]), ["wrap", "pick"])
        self.assertEqual(list(out[0]["usagestats"]), ["wrap", "pick"])
        self.assertEqual(list(out[0]), list(self.ROWS[0]))   # key order of the row
        self.assertIsNot(out[0], rows[0])
        self.assertIsNot(out[0]["verified"], rows[0]["verified"])
        self.assertEqual(rows, self.ROWS)                    # input not mutated

    def test_no_marker_sums_file_and_branch_keeping_file_order(self):
        root = self.repo("p", remote=False)
        self.record(root, "opus", "pick", 5)                 # 1 run, 100
        self.record(root, "opus", "explore", 4)              # branch-only skill
        self.record(root, "opus", "ask", 3)                  # branch-only, sorts first
        self.bump(root, model="opus", skill="pick")
        rows = copy.deepcopy(self.ROWS)
        out = mss.overlay_rows(root, "claudecode", rows)
        vs = out[0]["verifiedstats"]
        self.assertEqual(list(vs), ["wrap", "pick", "ask", "explore"])
        self.assertEqual(vs["pick"]["all_time"], {"runs": 3, "score_sum": 280})
        self.assertEqual(vs["wrap"], self.ROWS[0]["verifiedstats"]["wrap"])
        self.assertEqual(vs["explore"]["all_time"], {"runs": 1, "score_sum": 80})
        self.assertEqual(out[0]["usagestats"]["pick"]["all_time"], {"runs": 5})
        self.assertEqual(out[0]["verified"], {"wrap": 80, "pick": 90})  # prior untouched
        # Rows the branch knows nothing about are unchanged.
        self.assertEqual(out[1], self.ROWS[1])
        self.assertEqual(out[2], self.ROWS[2])
        self.assertEqual(out[3:], self.ROWS[3:])
        self.assertEqual(rows, self.ROWS)

    def test_marker_means_branch_only_and_drops_unbacked_keys(self):
        root = self.repo("p", remote=False)
        self.record(root, "opus", "pick", 2)
        self.mark(root)
        out = mss.overlay_rows(root, "claudecode", copy.deepcopy(self.ROWS))
        self.assertEqual(list(out[0]["verifiedstats"]), ["pick"])
        self.assertEqual(out[0]["verifiedstats"]["pick"]["all_time"],
                         {"runs": 1, "score_sum": 40})
        self.assertNotIn("usagestats", out[0])               # branch has no usage row
        self.assertNotIn("verifiedstats", out[1])            # flat: no branch data
        self.assertEqual(out[1]["verified"], {"pick": 75})   # the prior survives
        self.assertEqual(out[2], self.ROWS[2])
        self.assertEqual(out[3:], self.ROWS[3:])             # non-rows pass through

    def test_duplicate_names_keep_their_own_counters(self):
        root = self.repo("p", remote=False)
        self.bump(root, model="dup", skill="pick")
        rows = [{"name": "dup", "usagestats": {"pick": {"all_time": {"runs": 2}}}},
                {"name": "dup", "usagestats": {"pick": {"all_time": {"runs": 7}}}}]
        out = mss.overlay_rows(root, "claudecode", rows)
        self.assertEqual([r["usagestats"]["pick"]["all_time"]["runs"] for r in out], [3, 8])

    def test_overlay_data_shape_guard_and_non_git_dir(self):
        root = self.repo("p", remote=False)
        self.assertEqual(mss.overlay_data(root, "claudecode", ["x"]), ["x"])
        self.assertEqual(mss.overlay_data(root, "claudecode", {"models": {}}), {"models": {}})
        data = {"version": 2, "models": copy.deepcopy(self.ROWS)}
        self.assertEqual(mss.overlay_data(root, "claudecode", data), data)
        plain = self.tmp / "not-a-repo"
        plain.mkdir()
        self.assertEqual(mss.overlay_rows(plain, "claudecode", copy.deepcopy(self.ROWS)),
                         self.ROWS)

    def test_repo_is_the_given_directory_not_the_cwd(self):
        here, there = self.repo("here", remote=False), self.repo("there", remote=False)
        self.bump(here, model="opus", skill="pick")
        self.bump(here, model="opus", skill="pick")
        meta = there / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        old = os.getcwd()
        os.chdir(here)
        try:
            out = mss.overlay_rows(meta, "claudecode", copy.deepcopy(self.ROWS))
        finally:
            os.chdir(old)
        self.assertEqual(out, self.ROWS)                     # cwd's branch not read

    def test_cli_overlay_verb(self):
        root = self.repo("p", remote=False)
        write_legacy(root, self.ROWS[:3])
        self.record(root, "opus", "pick", 5)
        cli = Path(__file__).resolve().parent.parent / ".aitask-scripts" / "aitask_model_stats.py"
        path = root / "aitasks" / "metadata" / "models_claudecode.json"
        proc = subprocess.run([sys.executable, str(cli), "overlay", "--agent", "claudecode",
                               "--file", str(path)], capture_output=True, text=True,
                              cwd=str(self.tmp))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["models"][0]["verifiedstats"]["pick"]["all_time"],
                         {"runs": 3, "score_sum": 280})
        self.assertEqual(list(out["models"][0]["verifiedstats"]), ["wrap", "pick"])
        bad = subprocess.run([sys.executable, str(cli), "overlay", "--agent", "claudecode",
                              "--file", str(self.tmp / "missing.json")],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertTrue(bad.stdout.startswith("STATS_ERROR:usage:"), bad.stdout)


def _load_cli():
    import importlib.util
    spec = importlib.util.spec_from_file_location("aitask_model_stats_cli", CLI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEffectiveTotal(IsolatedGit):
    """The writers' printed value is the reader-visible total, from the write's
    own commit; once a write is durable nothing may turn it into a failure
    (t1912_4)."""

    MODEL = "opus"

    def setUp(self):
        super().setUp()
        self.cli = _load_cli()

    def run_cli(self, *args):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = self.cli.main(list(args))
        return rc, out.getvalue(), err.getvalue()

    def rate(self, root, score, day="2026-11-12"):
        return self.run_cli("record-verified", "--root", str(root), "--agent", "claudecode",
                            "--model", self.MODEL, "--skill", "pick", "--score", str(score),
                            "--date", day)

    def use(self, root, day="2026-11-12"):
        return self.run_cli("bump-usage", "--root", str(root), "--agent", "claudecode",
                            "--model", self.MODEL, "--skill", "pick", "--date", day)

    def legacy_rating(self, root, runs=1, score_sum=20):
        write_legacy(root, [{"name": self.MODEL, "verified": {"pick": 20},
                             "verifiedstats": {"pick": {
                                 "all_time": {"runs": runs, "score_sum": score_sum}}}}])

    @staticmethod
    def branch_runs(root, key="verifiedstats", ref=mss.L_REF):
        sha = ors.resolve(ors.toplevel(root), ref)
        blob = mss.parse_blob(ors.read_file(ors.toplevel(root), sha, "claudecode.json"))
        return blob["models"]["opus"][key]["pick"]["all_time"]["runs"]

    def mark(self, root):
        top = ors.toplevel(root)
        base = ors.resolve(top, mss.L_REF)
        commit = ors.build_commit(top, base, {mss.marker_path("claudecode"): b"{}\n"},
                                  "marker", ident=mss.IDENT)
        self.assertEqual(ors.cas_local(top, mss.L_REF, commit, base), "OK")

    # ------------------------------------------------------------ totals
    def test_legacy_plus_branch_is_the_printed_average(self):
        root = self.repo("v", remote=False)
        self.legacy_rating(root)                       # 1 run, 20
        rc, out, _ = self.rate(root, 5)                # + 100
        self.assertEqual((rc, out), (0, "UPDATED:claudecode/opus:pick:60\n"))

    def test_legacy_usage_same_month_is_summed(self):
        root = self.repo("u", remote=False)
        write_legacy(root, [{"name": self.MODEL, "usagestats": {"pick": usage_entry(3)}}])
        rc, out, _ = self.use(root)
        self.assertEqual((rc, out), (0, "UPDATED:claudecode/opus:pick:4\n"))

    def test_marker_in_the_written_commit_ignores_legacy(self):
        root = self.repo("m", remote=False)
        self.legacy_rating(root)
        self.mark(root)
        rc, out, _ = self.rate(root, 5)
        self.assertEqual((rc, out), (0, "UPDATED:claudecode/opus:pick:100\n"))

    def test_the_fail_soft_loader_is_never_consulted(self):
        # The loader reads a git failure as "no branch" (legacy-only totals);
        # making it explode proves the total does not come from it.
        root = self.repo("s", remote=False)
        self.legacy_rating(root)
        boom = mock.Mock(side_effect=AssertionError("loader consulted"))
        with mock.patch.object(mss, "_branch_content", boom), \
                mock.patch.object(mss, "load_agent_stats", boom):
            rc, out, err = self.rate(root, 5)
        self.assertEqual((rc, out), (0, "UPDATED:claudecode/opus:pick:60\n"), err)

    def test_total_ignores_a_local_ref_left_behind(self):
        root = self.repo("l")
        self.legacy_rating(root)
        with mock.patch.object(ors, "advance_ref", return_value="DIVERGED"):
            rc, out, err = self.rate(root, 5)
        self.assertEqual((rc, out), (0, "UPDATED:claudecode/opus:pick:60\n"))
        self.assertIn("was not advanced (DIVERGED)", err)
        self.assertIsNone(ors.resolve(ors.toplevel(root), mss.L_REF))

    # ------------------------------------------------ unavailable totals
    def assert_recorded_unknown(self, root, rc, out, err):
        self.assertEqual(rc, 0, err)
        self.assertEqual(out, "UPDATED:claudecode/opus:pick:unknown\n")
        self.assertNotEqual(out, "UPDATED:claudecode/opus:pick:100\n")  # branch-only
        self.assertIn("effective total is unavailable", err)
        self.assertEqual(self.branch_runs(root), 1)   # the write itself stands

    def test_unreadable_marker_is_unknown(self):
        root = self.repo("a", remote=False)
        self.legacy_rating(root)
        real = ors.read_file

        def read_file(repo, commit, path):
            if path == mss.marker_path("claudecode"):
                raise ors.GitError("simulated ls-tree failure")
            return real(repo, commit, path)

        with mock.patch.object(ors, "read_file", read_file):
            rc, out, err = self.rate(root, 5)
        self.assert_recorded_unknown(root, rc, out, err)

    def test_invalid_legacy_file_is_unknown(self):
        root = self.repo("b", remote=False)
        meta = root / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        (meta / "models_claudecode.json").write_text("{ not json")
        rc, out, err = self.rate(root, 5)
        self.assert_recorded_unknown(root, rc, out, err)

    def test_any_failure_in_the_total_is_unknown(self):
        root = self.repo("c", remote=False)
        self.legacy_rating(root)
        with mock.patch.object(mss, "merge_stats", side_effect=RuntimeError("boom")):
            rc, out, err = self.rate(root, 5)
        self.assert_recorded_unknown(root, rc, out, err)

    def test_backdated_write_outside_the_view_is_unknown_never_zero(self):
        root = self.repo("d", remote=False)
        write_legacy(root, [{"name": self.MODEL, "usagestats": {"pick": {
            "all_time": {"runs": 5},
            "prev_month": {"period": "2026-10", "runs": 2},
            "month": {"period": "2026-11", "runs": 3},
            "week": {"period": "2026-W46", "runs": 3}}}}])
        rc, out, err = self.use(root, day="2026-08-03")
        self.assertEqual(rc, 0, err)
        self.assertEqual(out, "UPDATED:claudecode/opus:pick:unknown\n")
        self.assertEqual(self.branch_runs(root, "usagestats"), 1)

    # ---------------------------------------------- post-push boundary
    def _post_push_failure(self, exc):
        root = self.repo("p")
        with mock.patch.object(ors, "advance_ref", side_effect=exc):
            rc, out, err = self.rate(root, 4)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out, "UPDATED:claudecode/opus:pick:80\n")
        self.assertIn("was not advanced (ERROR:", err)
        self.assertNotIn("STATS_ERROR", out)
        # Exactly one increment on origin: one commit (the root), runs = 1.
        self.assertEqual(git(self.remote, "rev-list", "--count", "refs/heads/aitask-stats"), "1")
        self.assertEqual(self.origin_blob()["models"]["opus"]["verifiedstats"]["pick"]
                         ["all_time"], {"runs": 1, "score_sum": 80})
        self.assertIsNone(ors.resolve(ors.toplevel(root), mss.L_REF))
        # A later normal write builds on origin: no double count, no loss.
        rc, out, err = self.rate(root, 5)
        self.assertEqual((rc, out), (0, "UPDATED:claudecode/opus:pick:90\n"), err)
        self.assertEqual(self.origin_blob()["models"]["opus"]["verifiedstats"]["pick"]
                         ["all_time"], {"runs": 2, "score_sum": 180})

    def test_post_push_git_error_is_a_recorded_success(self):
        self._post_push_failure(ors.GitError("simulated update-ref failure"))

    def test_post_push_os_error_is_a_recorded_success(self):
        self._post_push_failure(OSError("simulated fork failure"))

    def test_nested_cwd_without_root_reads_the_repository_registry(self):
        # --root defaults to the cwd; update() resolves it to the toplevel, and
        # the legacy registry must be read from that same root.
        root = self.repo("nested", remote=False)
        self.legacy_rating(root)                       # 1 run, 20
        nested = root / "website" / "deep"
        nested.mkdir(parents=True)
        old = os.getcwd()
        os.chdir(nested)
        try:
            rc, out, err = self.run_cli(
                "record-verified", "--agent", "claudecode", "--model", self.MODEL,
                "--skill", "pick", "--score", "5", "--date", "2026-11-12")
        finally:
            os.chdir(old)
        self.assertEqual((rc, out), (0, "UPDATED:claudecode/opus:pick:60\n"), err)

    def test_total_reads_the_resolved_root_without_a_second_lookup(self):
        # effective_total already holds the toplevel; its legacy read must use it
        # verbatim, not re-resolve it through _layout (3 more rev-parse calls in
        # a fresh writer process, whose _layout_cache is empty) (t2315).
        root = self.repo("onelookup", remote=False)
        self.legacy_rating(root)
        committed = {}

        def fn(blob):
            new, value = mss.record_verified(blob, self.MODEL, "pick", 100, D("2026-11-12"))
            committed["m"] = new["models"]
            return new, value

        res = mss.update(root, "claudecode", fn, return_commit=True)
        calls = []
        real = ors.git

        def spy(repo, *args, **kw):
            calls.append(args)
            return real(repo, *args, **kw)

        mss._layout_cache.clear()
        with mock.patch.object(ors, "git", spy):
            total = mss.effective_total(root, "claudecode", self.MODEL, "verifiedstats",
                                        "pick", D("2026-11-12"), committed["m"], res.commit)
        self.assertEqual(total, 60)                    # legacy 20 + branch 100, 2 runs
        rev_parse = [a for a in calls if a[:1] == ("rev-parse",)]
        self.assertEqual(rev_parse, [("rev-parse", "--show-toplevel")], calls)

    def test_nested_cwd_export_and_show_read_the_repository_registry(self):
        # The display verbs, run from a nested cwd without --root, show the
        # repository's legacy counters merged with the branch, not the branch
        # alone (t2315).
        root = self.repo("nested_display", remote=False)
        self.legacy_rating(root)                       # legacy: 1 run, 20
        rc, out, err = self.rate(root, 5)              # branch: 1 run, 100
        self.assertEqual(rc, 0, err)
        # A legacy-only agent: reachable only through the registry listing.
        write_legacy(root, [{"name": "gpt5", "usagestats": {"pick": usage_entry(7)}}],
                     agent="codex")
        nested = root / "website" / "deep"
        nested.mkdir(parents=True)
        old = os.getcwd()
        os.chdir(nested)
        try:
            rc_e, out_e, err_e = self.run_cli("export", "--agent", "claudecode")
            rc_s, out_s, err_s = self.run_cli("show")
        finally:
            os.chdir(old)
        self.assertEqual(rc_e, 0, err_e)
        exported = json.loads(out_e)
        self.assertEqual(exported["models"]["opus"]["verifiedstats"]["pick"]["all_time"],
                         {"runs": 2, "score_sum": 120})
        self.assertEqual(rc_s, 0, err_s)
        lines = out_s.splitlines()
        self.assertIn("claudecode/opus verifiedstats pick all_time=2 avg=60", lines)
        self.assertIn("MARKER:codex:no", lines)
        self.assertIn("codex/gpt5 usagestats pick all_time=7", lines)

    def test_every_skill_the_writers_accepted_is_accepted(self):
        # The counter writers took any non-empty skill (a JSON key); the CLI they
        # now route through must not narrow that. Echoed verbatim.
        root = self.repo("skills", remote=False)
        skills = ["custom/skill", "a:b", "two words", "*glob[x]", "ñandú", ".dot",
                  "batch-review", "x|y"]
        for skill in skills:
            rc, out, err = self.run_cli(
                "record-verified", "--root", str(root), "--agent", "claudecode",
                "--model", self.MODEL, "--skill", skill, "--score", "4")
            self.assertEqual((rc, out), (0, f"UPDATED:claudecode/opus:{skill}:80\n"),
                             (skill, err))
        stats = mss.load_agent_stats(root, "claudecode")["opus"]["verifiedstats"]
        self.assertEqual(sorted(stats), sorted(skills))

    def test_no_remote_cas_failure_is_still_an_error(self):
        # Without a remote the local ref IS the store: a failed CAS means the
        # write did not land, so it must stay a failure.
        root = self.repo("n", remote=False)
        with mock.patch.object(ors, "cas_local", side_effect=ors.GitError("locked")):
            rc, out, _ = self.rate(root, 4)
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STATS_ERROR:"), out)


if __name__ == "__main__":
    unittest.main()
