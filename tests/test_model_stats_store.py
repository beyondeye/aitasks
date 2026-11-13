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
            ("bump-usage", "--agent", "claudecode", "--model", "m", "--skill", "a:b"),
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


if __name__ == "__main__":
    unittest.main()
