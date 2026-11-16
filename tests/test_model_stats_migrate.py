#!/usr/bin/env python3
"""Tests for the legacy-counter migration (lib/model_stats_migrate.py, t1912_5).

Scratch repositories only: a bare ``origin``, a ``seed`` clone that publishes the
task-data branch and plays "an older framework" (writes registry counters
straight onto origin's ``aitask-data``), and working clones with a
``.aitask-data`` worktree. Global and system git config and HOME are isolated
per test.

Races are staged deterministically through ``model_stats_migrate._hook``: a test
runs a second migrator, or an old-framework write, *inside* the first
migrator's hook, and asserts the exact interleaving's outcome.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
LIB = REPO / ".aitask-scripts" / "lib"
CLI = REPO / ".aitask-scripts" / "aitask_model_stats.py"
CAPTURE = REPO / "tests" / "lib" / "stats_reader_capture.py"
GOLDEN = REPO / "tests" / "golden" / "stats_readers"
sys.path.insert(0, str(LIB))

import model_stats_migrate as msm  # noqa: E402
import model_stats_store as mss  # noqa: E402
import orphan_ref_store as ors  # noqa: E402

REG = "aitasks/metadata/models_claudecode.json"


class Crash(BaseException):
    """A simulated process death: not an Exception, so nothing converts it."""


def git(cwd, *args, check=True, env=None):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check, env=env,
                          capture_output=True, text=True).stdout.strip()


def usage(runs, month="2026-11", week="2026-W46"):
    return {"all_time": {"runs": runs}, "prev_month": {"period": "", "runs": 0},
            "month": {"period": month, "runs": runs}, "week": {"period": week, "runs": runs}}


def registry(runs=None, verified_runs=None, extra_rows=()):
    """A claudecode registry; ``runs`` None => a row with no counters at all."""
    row = {"name": "opus", "cli_id": "claude-opus", "notes": "n",
           "verified": {"pick": 90}}
    if runs is not None:
        row["usagestats"] = {"pick": usage(runs)}
    if verified_runs is not None:
        row["verifiedstats"] = {"pick": {"all_time": {"runs": verified_runs,
                                                      "score_sum": 90 * verified_runs}}}
    rows = [row, *extra_rows]
    return (json.dumps({"models": rows}, indent=2, ensure_ascii=False) + "\n").encode()


class MigrateBase(unittest.TestCase):
    """Bare origin + seed + clones; isolated git config and HOME."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="ait-msm-")
        self.tmp = Path(self._td.name)
        home = self.tmp / "home"
        home.mkdir()
        self.real_home = os.environ.get("HOME", "")
        env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
               "HOME": str(home), "GIT_TERMINAL_PROMPT": "0"}
        self._env = mock.patch.dict(os.environ, env)
        self._env.start()
        for key in ("TASK_DIR", "AIT_STATS_FETCH_TIMEOUT"):
            os.environ.pop(key, None)
        self._hook = mock.patch.object(msm, "_hook", self._dispatch)
        self._hook.start()
        self.hooks = {}
        self.remote = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.seed = self.tmp / "seed"
        self.seed.mkdir()
        git(self.seed, "init", "-q", "-b", "main")
        self.config(self.seed)
        git(self.seed, "remote", "add", "origin", str(self.remote))
        (self.seed / "README").write_text("x\n")
        git(self.seed, "add", "README")
        git(self.seed, "commit", "-q", "-m", "init")
        git(self.seed, "push", "-q", "origin", "main")

    def tearDown(self):
        self._hook.stop()
        self._env.stop()
        self._td.cleanup()

    # ------------------------------------------------------------ hooks
    def _dispatch(self, point, **ctx):
        fn = self.hooks.get(point)
        if fn is not None:
            fn(**ctx)

    def once(self, point, fn):
        """Run ``fn`` the first time ``point`` fires, then never again."""
        fired = []

        def wrapper(**ctx):
            if not fired:
                fired.append(1)
                fn(**ctx)
        self.hooks[point] = wrapper

    # ---------------------------------------------------------- fixtures
    @staticmethod
    def config(root):
        git(root, "config", "user.email", "t@example.com")
        git(root, "config", "user.name", "T")

    def publish_data(self, blob):
        """Seed origin's task-data branch with one registry commit."""
        commit = ors.build_commit(self.seed, None, {REG: blob}, "data")
        git(self.seed, "push", "-q", "origin", f"+{commit}:refs/heads/aitask-data")
        return commit

    def origin_data(self):
        return git(self.remote, "rev-parse", "refs/heads/aitask-data")

    def origin_stats(self):
        return git(self.remote, "rev-parse", "--verify", "-q", "refs/heads/aitask-stats",
                   check=False) or None

    def old_write(self, blob=None, edit=None, other=None, delete=False):
        """An older framework commits onto origin's task-data branch."""
        git(self.seed, "fetch", "-q", "origin", "+refs/heads/aitask-data:refs/tmp/d")
        tip = git(self.seed, "rev-parse", "refs/tmp/d")
        changes = {}
        if edit is not None:
            data = json.loads(git(self.seed, "show", f"{tip}:{REG}"))
            edit(data)
            changes[REG] = (json.dumps(data, indent=2) + "\n").encode()
        if blob is not None:
            changes[REG] = blob
        if other is not None:
            changes["aitasks/t9.md"] = other.encode()
        if delete:
            changes[REG] = None
        commit = ors.build_commit(self.seed, tip, changes, "old framework write")
        git(self.seed, "push", "-q", "origin", f"{commit}:refs/heads/aitask-data")
        return commit

    def clone(self, name):
        root = self.tmp / name
        git(self.tmp, "clone", "-q", str(self.remote), str(root))
        self.config(root)
        git(root, "worktree", "add", "-q", "-b", "aitask-data", ".aitask-data",
            "origin/aitask-data")
        os.symlink(".aitask-data/aitasks", root / "aitasks")  # the real layout
        return root

    def total(self, root, agent="claudecode"):
        stats = mss.load_agent_stats(root, agent)
        row = stats.get("opus") or {}
        out = 0
        for key in mss.STATS_KEYS:
            for entry in (row.get(key) or {}).values():
                out += mss._num((mss._normalize(entry).get("all_time") or {}).get("runs"))
        return out

    def baselines(self, ref="refs/heads/aitask-data", repo=None):
        repo = repo or self.remote
        found = msm.scan(repo, git(repo, "rev-parse", ref))
        return [s for s in found if s.kind == "baseline"]

    def origin_marker(self):
        raw = git(self.remote, "show", "aitask-stats:migrations/claudecode.json", check=False)
        return json.loads(raw) if raw else None

    def migrate(self, root, **kw):
        return msm.migrate(root, "claudecode", **kw)


# ======================================================================= core

class TestFirstRun(MigrateBase):
    def test_counters_baseline_one_invocation(self):
        o = self.publish_data(registry(runs=100, verified_runs=10))
        a = self.clone("a")
        out = self.migrate(a)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith("MIGRATED:claudecode|"), out)
        s1 = out[0].split("|")[1]
        self.assertTrue(out[0].endswith("|110"), out)
        marker = self.origin_marker()
        self.assertEqual(marker["strip_commit"], s1)
        self.assertEqual(marker["source_commit"], o)
        self.assertEqual(git(self.remote, "rev-parse", f"{s1}^"), o)
        self.assertNotIn("usagestats", git(self.remote, "show", f"aitask-data:{REG}"))
        self.assertIn('"verified"', git(self.remote, "show", f"aitask-data:{REG}"))
        b = self.clone("b")
        git(b, "fetch", "-q", "origin", "aitask-stats:aitask-stats")
        self.assertEqual(self.total(b), 110)
        self.assertEqual(len(self.baselines()), 1)

    def test_empty_baseline_one_invocation(self):
        o = self.publish_data(registry(runs=None))
        a = self.clone("a")
        out = self.migrate(a)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith("MIGRATED:claudecode|") and out[0].endswith("|0"), out)
        s1 = out[0].split("|")[1]
        self.assertEqual(git(self.remote, "rev-parse", f"{s1}^{{tree}}"),
                         git(self.remote, "rev-parse", f"{o}^{{tree}}"))
        self.assertEqual(self.origin_marker()["strip_commit"], s1)
        # Discovery: the empty commit is found at once, and a path-limited log
        # really would have missed it (why the scan takes no pathspec).
        self.assertEqual([b.sha for b in self.baselines()], [s1])
        limited = git(self.remote, "log", "--full-history", "--format=%H", "aitask-data",
                      "--", REG).split()
        self.assertNotIn(s1, limited)

    def test_marker_gate_tip_ordering(self):
        o = self.publish_data(registry(runs=5))
        a = self.clone("a")
        self.migrate(a)
        marker_bytes = git(self.remote, "show",
                           "aitask-stats:migrations/claudecode.json").encode() + b"\n"
        s1 = json.loads(marker_bytes)["strip_commit"]
        ctx = msm.resolve_context(a)
        git(a, "fetch", "-q", "origin", "aitask-data")
        with self.assertRaises(mss.MarkerUnpublishable):
            msm.MarkerGate(ctx, o).check("claudecode", marker_bytes)
        msm.MarkerGate(ctx, s1).check("claudecode", marker_bytes)


class TestIdempotentAndUntouched(MigrateBase):
    def test_second_run_is_noop(self):
        self.publish_data(registry(runs=7))
        a = self.clone("a")
        self.migrate(a)
        data, stats = self.origin_data(), self.origin_stats()
        out = self.migrate(a)
        self.assertEqual(out, ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual((self.origin_data(), self.origin_stats()), (data, stats))

    def test_remote_mode_leaves_data_worktree_untouched(self):
        self.publish_data(registry(runs=3))
        a = self.clone("a")
        wt = a / ".aitask-data"
        (wt / "aitasks" / "t1.md").write_text("untracked\n")
        reg = wt / REG
        reg.write_bytes(reg.read_bytes().replace(b'"n"', b'"edited"'))

        def snap():
            idx = subprocess.run(["git", "ls-files", "-s"], cwd=wt, check=True,
                                 capture_output=True).stdout
            return (git(wt, "rev-parse", "HEAD"), hashlib.sha256(idx).hexdigest(),
                    git(wt, "status", "--porcelain"),
                    git(a, "rev-parse", "refs/heads/aitask-data"), reg.read_bytes())
        before = snap()
        out = self.migrate(a)
        self.assertTrue(out[0].startswith("MIGRATED:"), out)
        self.assertEqual(snap(), before)

    def test_unreachable_remote_defers_and_writes_nothing(self):
        self.publish_data(registry(runs=4))
        a = self.clone("a")
        data = self.origin_data()
        git(a, "remote", "set-url", "origin", str(self.tmp / "missing.git"))
        out = self.migrate(a)
        self.assertTrue(out[0].startswith("MIGRATE_DEFERRED:claudecode|unreachable"), out)
        self.assertEqual(self.origin_data(), data)
        self.assertIsNone(self.origin_stats())
        self.assertIsNone(git(a, "rev-parse", "--verify", "-q", "refs/heads/aitask-stats",
                              check=False) or None)
        self.assertEqual(self.total(a), 4)  # loader: file + (empty) branch


class TestStaleLocalAndOriginMoves(MigrateBase):
    def test_stale_local_vs_newer_remote(self):
        self.publish_data(registry(runs=100))
        a = self.clone("a")  # local data branch + worktree at 100
        newer = self.old_write(blob=registry(runs=110))
        out = self.migrate(a)
        self.assertTrue(out[0].endswith("|110"), out)
        self.assertEqual(self.origin_marker()["source_commit"], newer)
        self.assertIn(b'"runs": 100', (a / ".aitask-data" / REG).read_bytes())

    def _moves_between_pin_and_strip(self, write):
        self.publish_data(registry(runs=10))
        a = self.clone("a")
        self.once("after_pin", lambda **_: write())
        out = self.migrate(a)
        return a, out

    def test_unrelated_commit_between_pin_and_strip(self):
        a, out = self._moves_between_pin_and_strip(lambda: self.old_write(other="x\n"))
        self.assertTrue(out[0].endswith("|10"), out)
        self.assertEqual(len(self.baselines()), 1)

    def test_old_framework_write_between_pin_and_strip(self):
        a, out = self._moves_between_pin_and_strip(
            lambda: self.old_write(blob=registry(runs=11)))
        self.assertTrue(out[0].endswith("|11"), out)
        self.assertEqual(len(self.baselines()), 1)
        git(a, "fetch", "-q", "origin", "aitask-stats:aitask-stats")
        self.assertEqual(self.total(a), 11)


class TestConcurrentAndCrash(MigrateBase):
    def test_two_clones_concurrently(self):
        self.publish_data(registry(runs=50))
        a, b = self.clone("a"), self.clone("b")
        results = {}
        self.once("after_pin", lambda **_: results.setdefault("b", self.migrate(b)))
        results["a"] = self.migrate(a)
        self.assertTrue(results["b"][0].startswith("MIGRATED:"), results)
        self.assertEqual(results["a"], ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(len(self.baselines()), 1)
        self.assertEqual(self.total(a), 50)
        self.assertEqual(self.total(b), 50)

    def test_crash_after_strip_recovers_once(self):
        self.publish_data(registry(runs=20))
        a = self.clone("a")

        def crash(**_):
            raise Crash()
        self.once("after_strip", crash)
        with self.assertRaises(Crash):
            self.migrate(a)
        self.assertIsNone(self.origin_stats())
        out = self.migrate(a)
        self.assertTrue(out[0].endswith("|20"), out)
        self.assertEqual(self.migrate(a), ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(self.total(a), 20)
        self.assertEqual(len(self.baselines()), 1)

    def test_empty_baseline_crash_recovers_in_fresh_process(self):
        self.publish_data(registry(runs=None))
        a = self.clone("a")

        def crash(**_):
            raise Crash()
        self.once("after_strip", crash)
        with self.assertRaises(Crash):
            self.migrate(a)
        proc = subprocess.run([sys.executable, str(CLI), "migrate", "--agent", "claudecode",
                               "--root", str(a)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip().endswith("|0"), proc.stdout)
        self.assertEqual(len(self.baselines()), 1)


class TestDeletedRegistryAfterStrip(MigrateBase):
    """A registry deleted after its baseline strip must not orphan the counters."""

    def _strip_crash_then_delete(self):
        self.publish_data(registry(runs=20))
        a = self.clone("a")

        def crash(**_):
            raise Crash()
        self.once("after_strip", crash)
        with self.assertRaises(Crash):
            self.migrate(a)
        self.old_write(delete=True)
        self.assertEqual(git(self.remote, "show", f"aitask-data:{REG}", check=False), "")
        return a

    def test_explicit_agent_recovers_from_s1_parent(self):
        a = self._strip_crash_then_delete()
        out = self.migrate(a)
        self.assertTrue(out[0].startswith("MIGRATED:claudecode|") and out[0].endswith("|20"), out)
        self.assertEqual(self.total(a), 20)

    def test_default_discovery_includes_pending_baselines(self):
        a = self._strip_crash_then_delete()
        out = msm.migrate(a)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith("MIGRATED:claudecode|") and out[0].endswith("|20"), out)
        self.assertEqual(self.origin_marker()["absorbed_runs"], 20)

    def test_no_registry_and_no_baseline_still_skips(self):
        self.publish_data(registry(runs=3))
        a = self.clone("a")
        self.assertEqual(msm.migrate(a, "codex"), ["MIGRATE_SKIPPED:codex|no_registry"])


class TestBaselineRecoveryRace(MigrateBase):
    def test_b_completes_while_a_pauses_before_absorb(self):
        self.publish_data(registry(runs=110))
        a, b = self.clone("a"), self.clone("b")
        results = {}

        def during(**_):
            self.old_write(edit=lambda d: d["models"][0].setdefault("usagestats", {}).update(
                {"explain": usage(1)}))
            results["b"] = self.migrate(b)
        self.once("before_absorb", during)
        results["a"] = self.migrate(a)
        self.assertTrue(results["b"][0].endswith("|110"), results)
        self.assertEqual(results["b"][1], "STRIPPED_RESIDUE:claudecode|1")
        self.assertEqual(results["a"], ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(self.total(a), 110)
        self.assertEqual(len(self.baselines()), 1)

    def test_a_resumes_before_b_then_residue_after_marker(self):
        self.publish_data(registry(runs=110))
        a, b = self.clone("a"), self.clone("b")
        out_a = self.migrate(a)
        self.assertTrue(out_a[0].endswith("|110"), out_a)
        self.old_write(edit=lambda d: d["models"][0].setdefault("usagestats", {}).update(
            {"explain": usage(1)}))
        out_b = self.migrate(b)
        self.assertEqual(out_b, ["MIGRATE_NOOP:claudecode|marked",
                                 "STRIPPED_RESIDUE:claudecode|1"])
        self.assertEqual(self.total(b), 110)
        self.assertEqual(len(self.baselines()), 1)


class TestEmptySourceCutover(MigrateBase):
    def test_a_pins_empty_old_writer_then_b_strips(self):
        self.publish_data(registry(runs=None))
        a, b = self.clone("a"), self.clone("b")
        results = {}

        def during(**_):
            self.old_write(blob=registry(runs=9))
            results["b"] = self.migrate(b)
        self.once("after_pin", during)
        results["a"] = self.migrate(a)
        self.assertTrue(results["b"][0].endswith("|9"), results)
        self.assertEqual(results["a"], ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(len(self.baselines()), 1)
        self.assertEqual(self.total(a), 9)
        self.assertFalse(any("marker_mismatch" in x for x in results["a"] + results["b"]))

    def test_empty_baseline_lands_then_old_writer_is_residue(self):
        self.publish_data(registry(runs=None))
        a, b = self.clone("a"), self.clone("b")
        results = {}

        def during(**_):
            self.old_write(blob=registry(runs=9))
            results["b"] = self.migrate(b)
        self.once("before_absorb", during)
        results["a"] = self.migrate(a)
        self.assertTrue(results["b"][0].endswith("|0"), results)
        self.assertEqual(results["b"][1], "STRIPPED_RESIDUE:claudecode|9")
        self.assertEqual(results["a"], ["MIGRATE_NOOP:claudecode|marked"])
        s1 = self.baselines()
        self.assertEqual(len(s1), 1)
        self.assertEqual(self.origin_marker()["strip_commit"], s1[0].sha)
        self.assertEqual(self.total(a), 0)
        self.assertFalse(any("marker_mismatch" in x for x in results["a"] + results["b"]))


class TestReadRefConvergence(MigrateBase):
    def _migrated_elsewhere(self):
        self.publish_data(registry(runs=30))
        a = self.clone("a")
        self.migrate(a)
        return a

    def test_absent_local_stats_ref_converges(self):
        self._migrated_elsewhere()
        b = self.clone("b")
        self.assertEqual(self.total(b), 0)  # registry already stripped on origin
        self.assertEqual(self.migrate(b), ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(self.total(b), 30)
        self.assertEqual(git(b, "rev-parse", "refs/heads/aitask-stats"), self.origin_stats())

    def test_stale_local_stats_ref_converges(self):
        self.publish_data(registry(runs=30))
        a, b = self.clone("a"), self.clone("b")
        mss.update(b, "claudecode", lambda bl: mss.bump_usage(
            bl, "opus", "pick", __import__("datetime").date(2026, 11, 12)))
        stale = git(b, "rev-parse", "refs/heads/aitask-stats")
        self.migrate(a)
        self.assertNotEqual(self.origin_stats(), stale)
        self.assertEqual(self.migrate(b), ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(git(b, "rev-parse", "refs/heads/aitask-stats"), self.origin_stats())
        self.assertEqual(self.total(b), 31)

    def test_local_progress_ahead_is_never_rewound(self):
        self._migrated_elsewhere()
        b = self.clone("b")
        tip = self.origin_stats()
        git(b, "fetch", "-q", "origin", f"{tip}")
        ahead = ors.build_commit(b, tip, {"codex.json": b'{"schema": 1, "models": {}}\n'},
                                 "local-only write")
        git(b, "update-ref", "refs/heads/aitask-stats", ahead)
        self.assertEqual(self.migrate(b), ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(git(b, "rev-parse", "refs/heads/aitask-stats"), ahead)
        self.assertEqual(self.origin_stats(), ahead)  # published, not rewound
        self.assertEqual(self.total(b), 30)

    def test_marker_found_on_absorb_retry_advances_local(self):
        self.publish_data(registry(runs=12))
        a, b = self.clone("a"), self.clone("b")
        results = {}
        self.once("before_absorb", lambda **_: results.setdefault("a", self.migrate(a)))
        results["b"] = self.migrate(b)
        self.assertEqual(results["b"], ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(git(b, "rev-parse", "refs/heads/aitask-stats"), self.origin_stats())
        self.assertEqual(self.total(b), 12)


# ===================================================================== no-remote

class NoRemoteBase(MigrateBase):
    def local_project(self, blob, name="p", branch_mode=True):
        root = self.tmp / name
        root.mkdir()
        git(root, "init", "-q", "-b", "main")
        self.config(root)
        (root / "README").write_text("x\n")
        git(root, "add", "README")
        git(root, "commit", "-q", "-m", "init")
        if branch_mode:
            data = ors.build_commit(root, None, {REG: blob}, "data")
            git(root, "update-ref", "refs/heads/aitask-data", data)
            git(root, "worktree", "add", "-q", ".aitask-data", "aitask-data")
            os.symlink(".aitask-data/aitasks", root / "aitasks")
            wt = root / ".aitask-data"
        else:
            (root / REG).parent.mkdir(parents=True)
            (root / REG).write_bytes(blob)
            git(root, "add", REG)
            git(root, "commit", "-q", "-m", "data")
            wt = root
        return root, wt


class TestNoRemote(NoRemoteBase):
    def test_clean_strip_carries_trailers(self):
        root, wt = self.local_project(registry(runs=6))
        out = self.migrate(root)
        self.assertTrue(out[0].startswith("MIGRATED:") and out[0].endswith("|6"), out)
        s1 = out[0].split("|")[1]
        body = git(wt, "log", "-1", "--format=%B", s1)
        self.assertIn("Stats-Migration-Kind: baseline", body)
        self.assertNotIn(b"usagestats", (wt / REG).read_bytes())
        self.assertEqual(git(wt, "status", "--porcelain"), "")
        self.assertEqual(self.total(root), 6)
        self.assertEqual(self.migrate(root), ["MIGRATE_NOOP:claudecode|marked"])

    def test_legacy_mode(self):
        root, wt = self.local_project(registry(runs=2), branch_mode=False)
        out = self.migrate(root)
        self.assertTrue(out[0].endswith("|2"), out)
        self.assertEqual(self.total(root), 2)

    def test_dirty_worktree_defers(self):
        root, wt = self.local_project(registry(runs=6))
        reg = wt / REG
        dirty = reg.read_bytes().replace(b'"n"', b'"edited"')
        reg.write_bytes(dirty)
        head = git(wt, "rev-parse", "HEAD")
        self.assertEqual(self.migrate(root), ["MIGRATE_DEFERRED:claudecode|dirty"])
        self.assertEqual(reg.read_bytes(), dirty)
        self.assertEqual(git(wt, "rev-parse", "HEAD"), head)

    def test_commit_failure_rolls_back(self):
        root, wt = self.local_project(registry(runs=6))
        before = (wt / REG).read_bytes()
        hooks = Path(git(root, "rev-parse", "--git-common-dir"))
        hooks = (root / hooks if not hooks.is_absolute() else hooks) / "hooks"
        hooks.mkdir(exist_ok=True)
        (hooks / "pre-commit").write_text("#!/bin/sh\nexit 1\n")
        (hooks / "pre-commit").chmod(0o755)
        out = self.migrate(root)
        self.assertTrue(out[0].startswith("MIGRATE_DEFERRED:claudecode|commit_failed"), out)
        self.assertEqual((wt / REG).read_bytes(), before)

    def test_failed_commit_never_restores_over_a_competing_edit(self):
        # A registry edit landing IMMEDIATELY after the strip's atomic rename,
        # before anything else the helper does, must survive a failing commit:
        # the rollback compares against the bytes the strip rendered (captured
        # before the swap), never against a sample of the live file taken after
        # it. The edit is injected by a one-shot `mv` shim that performs the real
        # rename and then edits the registry, so it lands at the earliest point
        # after the swap in any helper version that renames through `mv`.
        root, wt = self.local_project(registry(runs=6))
        hooks = Path(git(root, "rev-parse", "--git-common-dir"))
        hooks = (root / hooks if not hooks.is_absolute() else hooks) / "hooks"
        hooks.mkdir(exist_ok=True)
        (hooks / "pre-commit").write_text("#!/bin/sh\nexit 1\n")
        (hooks / "pre-commit").chmod(0o755)
        bindir = self.tmp / "shimbin"
        bindir.mkdir()
        real_mv = shutil.which("mv")
        fired = self.tmp / "mv.fired"
        target = os.path.realpath(wt / REG)
        (bindir / "mv").write_text(
            "#!/bin/sh\n"
            f'"{real_mv}" "$@" || exit $?\n'
            'for last; do :; done\n'
            f'if [ ! -e "{fired}" ] && [ "$(realpath "$last" 2>/dev/null)" = "{target}" ]; then\n'
            f'  touch "{fired}"\n'
            f"  sed -i 's/\"notes\": \"n\"/\"notes\": \"competing\"/' \"$last\"\n"
            "fi\n")
        (bindir / "mv").chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": f"{bindir}:{os.environ['PATH']}"}):
            out = self.migrate(root)
        self.assertTrue(fired.exists(), "the shim never saw the strip's rename")
        self.assertTrue(out[0].startswith("MIGRATE_DEFERRED:claudecode|commit_failed"), out)
        self.assertIn(b'"competing"', (wt / REG).read_bytes())

    def test_empty_no_remote_baseline_keeps_index_and_status(self):
        root, wt = self.local_project(registry(runs=None))
        (wt / "aitasks" / "t5.md").write_text("u\n")

        def snap():
            return (subprocess.run(["git", "ls-files", "-s"], cwd=wt, capture_output=True,
                                   check=True).stdout, git(wt, "status", "--porcelain"))
        before = snap()
        out = self.migrate(root)
        self.assertTrue(out[0].endswith("|0"), out)
        self.assertEqual(snap(), before)
        self.assertEqual(git(wt, "rev-parse", "HEAD"), out[0].split("|")[1])

    def test_unrelated_commit_after_strip_is_not_taken_for_it(self):
        root, wt = self.local_project(registry(runs=8))
        hooks = Path(git(root, "rev-parse", "--git-common-dir"))
        hooks = (root / hooks if not hooks.is_absolute() else hooks) / "hooks"
        hooks.mkdir(exist_ok=True)
        flag = self.tmp / "u.done"
        (hooks / "post-commit").write_text(
            "#!/bin/sh\n"
            f"[ -e '{flag}' ] && exit 0\n"
            f"touch '{flag}'\n"
            "git commit -q --allow-empty -m 'unrelated U'\n")
        (hooks / "post-commit").chmod(0o755)
        out = self.migrate(root)
        self.assertTrue(out[0].endswith("|8"), out)
        s1 = out[0].split("|")[1]
        self.assertEqual(git(wt, "log", "-1", "--format=%s"), "unrelated U")
        self.assertNotEqual(git(wt, "rev-parse", "HEAD"), s1)
        self.assertIn("Stats-Migration-Id", git(wt, "log", "-1", "--format=%B", s1))
        self.assertEqual(self.total(root), 8)

    def test_killed_between_rewrite_and_commit_resumes(self):
        root, wt = self.local_project(registry(runs=13))
        hook = self.tmp / "kill.sh"
        hook.write_text('#!/bin/sh\nkill -9 "$AIT_STATS_STRIP_PID"\n')
        with mock.patch.dict(os.environ, {"AIT_STATS_STRIP_AFTER_REWRITE_HOOK": str(hook)}):
            out = self.migrate(root)
        self.assertTrue(out[0].startswith("MIGRATE_DEFERRED:claudecode|strip_interrupted"), out)
        self.assertNotIn(b"usagestats", (wt / REG).read_bytes())
        self.assertIn("usagestats", git(wt, "show", f"HEAD:{REG}"))
        self.assertEqual(self.total(root), 0)  # the transient under-report
        proc = subprocess.run([sys.executable, str(CLI), "migrate", "--root", str(root)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip().endswith("|13"), proc.stdout)
        self.assertEqual(self.total(root), 13)

    def test_interrupted_state_plus_edit_stays_deferred(self):
        root, wt = self.local_project(registry(runs=13))
        stripped = msm.strip_blob((wt / REG).read_bytes())
        edited = stripped.replace(b'"n"', b'"hand edit"')
        (wt / REG).write_bytes(edited)
        self.assertEqual(self.migrate(root), ["MIGRATE_DEFERRED:claudecode|dirty"])
        self.assertEqual((wt / REG).read_bytes(), edited)


class TestStripScratchHygiene(NoRemoteBase):
    """The no-remote strip leaves nothing in TMPDIR on any exit route (t2319).

    Two layers, tested separately. Caller level: ``migrate`` runs the helper
    under a TMPDIR it owns, which is the only cover for SIGKILL (untrappable).
    Script level: the helper's own EXIT trap removes its work dir on every
    catchable exit, run directly with no caller wrapping.
    """

    def private_tmp(self):
        """A fresh TMPDIR for both this process's tempfile and its children."""
        d = self.tmp / "scratch"
        d.mkdir()
        for p in (mock.patch.object(tempfile, "tempdir", str(d)),
                  mock.patch.dict(os.environ, {"TMPDIR": str(d)})):
            p.start()
            self.addCleanup(p.stop)
        return d

    def assert_empty(self, d):
        self.assertEqual(sorted(os.listdir(d)), [], f"left behind in {d}")

    @staticmethod
    def fail_commits(root):
        hooks = Path(git(root, "rev-parse", "--git-common-dir"))
        hooks = (root / hooks if not hooks.is_absolute() else hooks) / "hooks"
        hooks.mkdir(exist_ok=True)
        (hooks / "pre-commit").write_text("#!/bin/sh\nexit 1\n")
        (hooks / "pre-commit").chmod(0o755)

    # --------------------------------------------- caller level (migrate)
    def test_strip_route_leaves_no_scratch(self):
        root, _ = self.local_project(registry(runs=6))
        d = self.private_tmp()
        out = self.migrate(root)
        self.assertTrue(out[0].startswith("MIGRATED:"), out)
        self.assert_empty(d)

    def test_deferred_dirty_route_leaves_no_scratch(self):
        root, wt = self.local_project(registry(runs=6))
        (wt / REG).write_bytes((wt / REG).read_bytes().replace(b'"n"', b'"edited"'))
        d = self.private_tmp()
        self.assertEqual(self.migrate(root), ["MIGRATE_DEFERRED:claudecode|dirty"])
        self.assert_empty(d)

    def test_commit_failed_route_leaves_no_scratch(self):
        root, _ = self.local_project(registry(runs=6))
        self.fail_commits(root)
        d = self.private_tmp()
        out = self.migrate(root)
        self.assertTrue(out[0].startswith("MIGRATE_DEFERRED:claudecode|commit_failed"), out)
        self.assert_empty(d)

    def test_sigkilled_helper_leaves_no_scratch(self):
        root, _ = self.local_project(registry(runs=13))
        hook = self.tmp / "kill.sh"
        hook.write_text('#!/bin/sh\nkill -9 "$AIT_STATS_STRIP_PID"\n')
        d = self.private_tmp()
        with mock.patch.dict(os.environ, {"AIT_STATS_STRIP_AFTER_REWRITE_HOOK": str(hook)}):
            out = self.migrate(root)
        self.assertTrue(out[0].startswith("MIGRATE_DEFERRED:claudecode|strip_interrupted"), out)
        self.assert_empty(d)

    # ------------------------------------------ script level (no wrapping)
    def run_helper(self, root, wt, hook=None):
        """Run the strip helper directly under a private TMPDIR; (proc, tmpdir)."""
        committed = subprocess.run(["git", "show", f"HEAD:{REG}"], cwd=wt,
                                   capture_output=True, check=True).stdout

        def blob_id(data):
            return subprocess.run(["git", "hash-object", "--stdin"], cwd=wt, input=data,
                                  capture_output=True, check=True).stdout.decode().strip()
        msg = self.tmp / "strip.msg"
        msg.write_text("test strip\n")
        d = self.tmp / "helper-tmp"
        d.mkdir()
        env = {**os.environ, "TMPDIR": str(d)}
        if hook is not None:
            env["AIT_STATS_STRIP_AFTER_REWRITE_HOOK"] = str(hook)
        proc = subprocess.run(
            ["bash", msm.STRIP_HELPER, "--path", REG,
             "--expect-blob", blob_id(committed),
             "--expect-stripped-blob", blob_id(msm.strip_blob(committed)),
             "--message-file", str(msg)],
            cwd=root, env=env, capture_output=True, text=True, check=False)
        return proc, d

    def test_helper_stripped_leaves_no_scratch(self):
        root, wt = self.local_project(registry(runs=6))
        proc, d = self.run_helper(root, wt)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, "STRIPPED"), proc.stderr)
        self.assert_empty(d)

    def test_helper_deferred_dirty_leaves_no_scratch(self):
        root, wt = self.local_project(registry(runs=6))
        (wt / REG).write_bytes((wt / REG).read_bytes().replace(b'"n"', b'"edited"'))
        proc, d = self.run_helper(root, wt)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (2, "STRIP_DEFERRED:dirty"),
                         proc.stderr)
        self.assert_empty(d)

    def test_helper_commit_failed_leaves_no_scratch(self):
        root, wt = self.local_project(registry(runs=6))
        self.fail_commits(root)
        proc, d = self.run_helper(root, wt)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertTrue(proc.stdout.strip().startswith("STRIP_DEFERRED:commit_failed:"),
                        proc.stdout)
        self.assert_empty(d)

    def test_helper_sigterm_leaves_no_scratch(self):
        root, wt = self.local_project(registry(runs=6))
        hook = self.tmp / "term.sh"
        hook.write_text('#!/bin/sh\nkill -TERM "$AIT_STATS_STRIP_PID"\n')
        proc, d = self.run_helper(root, wt, hook=hook)
        self.assertEqual(proc.returncode, -15, proc.stdout + proc.stderr)
        self.assertNotIn("STRIPPED", proc.stdout)
        self.assert_empty(d)


class TestParity(NoRemoteBase):
    def test_migrated_fixture_reproduces_reader_golden(self):
        root = self.tmp / "proj"
        meta = root / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        for agent in ("claudecode", "codex", "opencode"):
            shutil.copy(GOLDEN / f"models_{agent}.json", meta / f"models_{agent}.json")
        git(root, "init", "-q", "-b", "main")
        self.config(root)
        git(root, "add", "aitasks")
        git(root, "commit", "-q", "-m", "fixture")
        out = msm.migrate(root)
        self.assertEqual(sorted(x.split(":")[0] for x in out), ["MIGRATED"] * 3, out)
        self.assertEqual(mss.branch_state(root)["markers"], ["claudecode", "codex", "opencode"])
        for agent in ("claudecode", "codex", "opencode"):
            self.assertNotIn(b"usagestats", (meta / f"models_{agent}.json").read_bytes())
            self.assertNotIn(b"verifiedstats", (meta / f"models_{agent}.json").read_bytes())
        # The capture runs `ait codeagent list-models`, which resolves the
        # framework's Python venv under the real HOME (as the golden test does).
        env = {k: v for k, v in os.environ.items() if k not in ("TASK_DIR", "METADATA_DIR")}
        env["HOME"] = self.real_home
        proc = subprocess.run([sys.executable, str(CAPTURE), str(root)], cwd=root,
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, (GOLDEN / "expected.txt").read_text())


# ====================================================== offline migrate, reconnect

class TestOfflineThenAttach(NoRemoteBase):
    """An offline migration whose strip origin's registry history does not hold."""

    def _offline_then_divergent_origin(self, pre_write=False):
        root, wt = self.local_project(registry(runs=100))
        if pre_write:  # a stats commit that predates the migration marker
            mss.update(root, "codex", lambda bl: mss.bump_usage(
                bl, "x", "pick", __import__("datetime").date(2026, 11, 1)))
        self.assertTrue(self.migrate(root)[0].endswith("|100"))
        # origin: an unrelated task-data history that reached 110 runs.
        self.publish_data(registry(runs=110))
        git(root, "remote", "add", "origin", str(self.remote))
        return root, wt

    def _bump(self, root, agent="claudecode"):
        return subprocess.run([sys.executable, str(CLI), "bump-usage", "--agent", agent,
                               "--model", "opus", "--skill", "pick", "--date", "2026-11-12",
                               "--root", str(root)], capture_output=True, text=True)

    def test_ordinary_writers_hold_local_and_migrate_fails_closed(self):
        root, _ = self._offline_then_divergent_origin()
        data = self.origin_data()
        for agent in ("claudecode", "codex"):
            proc = self._bump(root, agent)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(proc.stdout.startswith("UPDATED:"), proc.stdout)
            self.assertIn("recorded locally only", proc.stderr)
            self.assertIsNone(self.origin_stats())  # no marker of any agent leaked
        proc = subprocess.run([sys.executable, str(CLI), "record-verified", "--agent", "codex",
                               "--model", "opus", "--skill", "pick", "--score", "5",
                               "--root", str(root)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(self.origin_stats())
        cli = subprocess.run([sys.executable, str(CLI), "migrate", "--root", str(root)],
                             capture_output=True, text=True)
        self.assertEqual(cli.returncode, 1, cli.stdout)
        self.assertIn("KEEP the local", cli.stderr)  # never advise a lossy discard
        self.assertIn("NOT lossless", cli.stderr)
        out = msm.migrate(root)
        self.assertTrue(out, out)
        for line in out:
            self.assertTrue(line.startswith("MIGRATE_ERROR:")
                            and line.endswith("|blocked:claudecode:marker_not_in_source"), out)
        self.assertEqual(self.origin_data(), data)
        self.assertIsNone(self.origin_stats())
        self.assertEqual(self.baselines(), [])

    def test_held_when_origin_stats_exists_and_is_behind(self):
        root, _ = self._offline_then_divergent_origin(pre_write=True)
        # origin aitask-stats exists and is an ancestor of local: the pre-marker
        # commit only, so the marker is still local-only.
        first = git(root, "rev-list", "--max-parents=0", "refs/heads/aitask-stats").split()[0]
        self.assertEqual(git(root, "show", f"{first}:migrations/claudecode.json", check=False), "")
        git(root, "push", "-q", "origin", f"{first}:refs/heads/aitask-stats")
        proc = self._bump(root)
        self.assertIn("recorded locally only", proc.stderr)
        self.assertEqual(self.origin_stats(), first)

    def test_unpushed_strip_defers_then_publishes_after_data_push(self):
        root, wt = self.local_project(registry(runs=40))
        # origin holds the same task-data history, before the strip.
        git(root, "remote", "add", "origin", str(self.remote))
        git(root, "push", "-q", "origin", "aitask-data")
        self.assertEqual(git(root, "remote"), "origin")
        git(root, "remote", "remove", "origin")
        self.assertTrue(self.migrate(root)[0].endswith("|40"))  # offline
        git(root, "remote", "add", "origin", str(self.remote))
        out = msm.migrate(root)
        self.assertEqual(out, ["MIGRATE_DEFERRED:claudecode|blocked:claudecode:strip_unpublished"])
        self.assertIsNone(self.origin_stats())
        proc = self._bump(root)
        self.assertIn("recorded locally only", proc.stderr)
        git(root, "push", "-q", "origin", "aitask-data")
        self.assertEqual(msm.migrate(root), ["MIGRATE_NOOP:claudecode|marked"])
        self.assertEqual(self.origin_stats(), git(root, "rev-parse", "refs/heads/aitask-stats"))
        b = self.clone("b")
        git(b, "fetch", "-q", "origin", "aitask-stats:aitask-stats")
        self.assertEqual(self.total(b), 41)  # absorbed 40 + the held write

    def test_diverged_stats_fail_closed(self):
        self.publish_data(registry(runs=5))
        a, b = self.clone("a"), self.clone("b")
        day = __import__("datetime").date(2026, 11, 12)
        mss.update(a, "claudecode", lambda bl: mss.bump_usage(bl, "opus", "pick", day))
        mss.update(b, "codex", lambda bl: mss.bump_usage(bl, "x", "pick", day))
        git(b, "update-ref", "-d", "refs/heads/aitask-stats")
        orphan = ors.build_commit(b, None, {"codex.json": b'{"schema": 1, "models": {}}\n'},
                                  "orphan")
        git(b, "update-ref", "refs/heads/aitask-stats", orphan)
        data = self.origin_data()
        out = self.migrate(b)
        self.assertEqual(out, ["MIGRATE_ERROR:claudecode|stats_diverged"])
        self.assertEqual(self.origin_data(), data)

    def test_already_published_marker_does_not_hold(self):
        self.publish_data(registry(runs=3))
        a = self.clone("a")
        self.migrate(a)
        res = mss.update(a, "claudecode", lambda bl: mss.bump_usage(
            bl, "opus", "pick", __import__("datetime").date(2026, 11, 12)),
            return_commit=True)
        self.assertEqual(res.local_ref, "ADVANCED")
        self.assertEqual(self.origin_stats(), res.commit)


class TestDryRun(MigrateBase):
    def test_dry_run_writes_nothing_and_predicts(self):
        self.publish_data(registry(runs=21))
        a = self.clone("a")
        refs = lambda: (self.origin_data(), self.origin_stats(),  # noqa: E731
                        git(a, "for-each-ref", "--format=%(refname) %(objectname)"))
        before = refs()
        plan = self.migrate(a, dry_run=True)
        self.assertEqual(plan, ["MIGRATE_PLAN:claudecode|marker=no|baseline=none"
                                "|absorb_runs=21|residue_runs=0"])
        self.assertEqual(refs(), before)
        out = self.migrate(a)
        self.assertTrue(out[0].endswith("|21"))
        after = self.migrate(a, dry_run=True)
        self.assertTrue(after[0].startswith("MIGRATE_PLAN:claudecode|marker=yes|"), after)


if __name__ == "__main__":
    unittest.main()
