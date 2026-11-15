#!/usr/bin/env python3
"""Unit tests for the sitrep crash detector (lib/sitrep_crash.py, t2299_2).

The bash suite (tests/test_sitrep_crash.sh) owns the end-to-end runs with the
real writer, real lock refs and real dead/live PIDs. This file owns the rules:
every row of the ordered decision table (driven through the module's liveness
and host hooks), host precedence, the episode key, outcome hygiene, the strict
lock/task readers (active, loose archived and bundled), the local retain
pointer against the real writer, the lock-age buckets, plan freshness and the
work attribution against scratch git repositories.

Run: python3 tests/test_sitrep_crash.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

import parallel_admission_collect as pac  # noqa: E402
import sitrep_crash as sc  # noqa: E402
import sitrep_refresh as sr  # noqa: E402

WRITER = PROJECT_DIR / ".aitask-scripts" / "aitask_sitrep_todo.sh"
GIT_ENV = dict(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_NOSYSTEM="1")


def git(root, *args, data=None):
    env = dict(os.environ, **GIT_ENV)
    p = subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True,
                       env=env, check=True)
    return p.stdout.decode().strip()


def lock(tid, host="here", pid="4242", start="777", kind="proc", locked_at="2026-11-10 09:00",
         by="a@b"):
    f = {"task_id": tid, "locked_by": by, "locked_at": locked_at, "hostname": host}
    if pid is not None:
        f["pid"] = pid
        f["pid_starttime"] = start
        f["pid_starttime_kind"] = kind
    return sc.LockRec(tid, f)


def active(tid, status="Implementing", **kw):
    return sc.TaskRec(tid, "active", status=status, **kw)


def task_text(status="Implementing", extra="", body="body"):
    lines = ["---"]
    if status is not None:
        lines.append(f"status: {status}")
    if extra:
        lines.append(extra)
    return "\n".join(lines + ["---", "", body, ""])


class HookCase(unittest.TestCase):
    """Pins the liveness / host hooks for one test."""

    def setUp(self):
        self._saved = (sc._LIVENESS, sc._LOCAL_HOST)
        sc._LOCAL_HOST = "here"
        self.calls = []
        self.answer = "dead"

        def fake(pid, start, kind):
            self.calls.append((pid, start, kind))
            return self.answer
        sc._LIVENESS = fake

    def tearDown(self):
        sc._LIVENESS, sc._LOCAL_HOST = self._saved

    def verdict(self, lk, task):
        live = sc.liveness_of(lk) if lk is not None and lk.state == "ok" else ""
        return sc.recovery_verdict(lk, task, live)


# --- the decision table -------------------------------------------------------

class DecisionTable(HookCase):
    def test_every_row(self):
        err = sc.TaskRec("1", "error", why="t1_x.md: no status")
        cases = [
            # (lock, liveness answer, task, row, category, stored, item_state)
            (sc.LockRec("1", state="error", why="malformed"), "dead", active("1"),
             1, "unreadable", False, ""),
            (lock("1"), "dead", err, 1, "unreadable", False, ""),
            (None, "dead", err, 1, "unreadable", False, ""),
            (lock("1", host="elsewhere"), "dead", active("1"), 2, "other_host", False, "unknown"),
            (lock("1"), "alive", active("1"), 3, "alive", False, "done"),
            (lock("1"), "alive", active("1", "Ready"), 3, "alive", False, "done"),
            (lock("1"), "unknown", active("1"), 4, "unknown", False, "unknown"),
            (lock("1"), "unknown", active("1", "Ready"), 4, "unknown", False, "unknown"),
            (lock("1", pid=None), "dead", active("1"), 5, "stale_lock", True, "open"),
            (lock("1", pid=None), "dead", active("1", "Ready"), 5, "stale_lock", True, "open"),
            (lock("1"), "dead", active("1"), 6, "crashed", True, "open"),
            (lock("1"), "dead", active("1", "Ready"), 7, "stale_lock", True, "open"),
            (lock("1"), "dead", active("1", "Done"), 7, "stale_lock", True, "open"),
            (lock("1"), "dead", sc.TaskRec("1", "archived", status="Done"),
             7, "stale_lock", True, "open"),
            (lock("1"), "dead", sc.TaskRec("1", "fold_scan", status="Folded", folded=True),
             7, "stale_lock", True, "open"),
            (lock("1"), "dead", sc.TaskRec("1", "missing"), 7, "stale_lock", True, "open"),
            (lock("1"), "dead", active("1", folded=True), 7, "stale_lock", True, "open"),
            (None, "dead", active("1"), 8, "orphan", True, "open"),
            (None, "dead", active("1", "Ready"), 9, "recovered", False, "done"),
            (None, "dead", active("1", "Editing"), 9, "recovered", False, "done"),
            (None, "dead", active("1", "Postponed"), 9, "recovered", False, "done"),
            (None, "dead", sc.TaskRec("1", "archived", status="Done"), 9, "recovered", False, "done"),
            (None, "dead", sc.TaskRec("1", "missing"), 9, "recovered", False, "done"),
        ]
        for lk, answer, task, row, cat, stored, state in cases:
            with self.subTest(row=row, task=task.where, status=task.status):
                self.answer = answer
                v = self.verdict(lk, task)
                self.assertEqual((v.row, v.category, v.stored, v.item_state),
                                 (row, cat, stored, state))

    def test_unknown_is_never_crashed(self):
        self.answer = "unknown"
        v = self.verdict(lock("1"), active("1"))
        self.assertEqual(v.row, 4)
        self.assertFalse(v.stored)

    def test_row1_never_writes(self):
        v = self.verdict(sc.LockRec("1", state="error", why="x"), active("1"))
        self.assertEqual(v.item_state, "")
        self.assertFalse(v.stored)


class HostPrecedence(HookCase):
    def test_foreign_and_unknown_host_win_over_every_pid_shape(self):
        for host in ("elsewhere", "unknown", ""):
            for pid in (None, "", "0", "-", "abc", "4242"):
                with self.subTest(host=host, pid=pid):
                    self.calls.clear()
                    lk = lock("1", host=host, pid=pid)
                    v = self.verdict(lk, active("1"))
                    self.assertEqual((v.row, v.category, v.stored), (2, "other_host", False))
                    self.assertEqual(self.calls, [], "liveness must not run off-host")

    def test_no_anchor_on_this_host_is_row5_without_liveness(self):
        for pid in (None, "", "0", "-", "abc"):
            with self.subTest(pid=pid):
                self.calls.clear()
                v = self.verdict(lock("1", pid=pid), active("1"))
                self.assertEqual(v.row, 5)
                self.assertEqual(self.calls, [])

    def test_host_guard_agrees_with_classify_liveness(self):
        saved = pac._LIVENESS
        pac._LIVENESS = lambda *a: "dead"
        try:
            for host in ("here", "elsewhere", "unknown", ""):
                for pid in ("4242", None, "0", "abc"):
                    meta = dict(lock("1", host=host, pid=pid).fields)
                    _, same = pac.classify_liveness(meta, True, "here")
                    with self.subTest(host=host, pid=pid):
                        self.assertEqual(bool(same), sc.host_ok(host, "here"))
        finally:
            pac._LIVENESS = saved


# --- episode keys and outcomes ------------------------------------------------

class EpisodeKey(unittest.TestCase):
    def test_anchored_key_ignores_locked_at(self):
        a = sc.episode_key("7", lock("7", locked_at="2026-11-01 10:00"), None)
        b = sc.episode_key("7", lock("7", locked_at="2026-11-02 11:00"), "ffffffffffff")
        self.assertEqual(a, b)
        self.assertRegex(a, r"^[0-9a-f]{12}$")

    def test_anchored_key_changes_with_the_claim(self):
        a = sc.episode_key("7", lock("7"), None)
        self.assertNotEqual(a, sc.episode_key("7", lock("7", pid="4243"), None))
        self.assertNotEqual(a, sc.episode_key("7", lock("7", start="778"), None))
        self.assertNotEqual(a, sc.episode_key("7", lock("7", host="other"), None))
        self.assertNotEqual(a, sc.episode_key("8", lock("8"), None))

    def test_unanchored_key_uses_locked_at(self):
        a = sc.episode_key("7", lock("7", pid=None), None)
        self.assertNotEqual(a, sc.episode_key("7", lock("7", pid=None, locked_at="2026-11-11 09:00"),
                                              None))
        self.assertNotEqual(a, sc.episode_key("7", lock("7", pid=None, by="c@d"), None))

    def test_no_lock_carries_the_recorded_key(self):
        self.assertEqual(sc.episode_key("7", None, "0123456789ab"), "0123456789ab")
        seed = sc.episode_key("7", None, None)
        self.assertEqual(seed, sc.episode_key("t7", None, ""))
        self.assertNotEqual(seed, sc.episode_key("8", None, None))


class Outcome(unittest.TestCase):
    def test_round_trip(self):
        text = sc.format_outcome("crashed", "holder pid 12 is gone")
        self.assertEqual(text, "crashed · holder pid 12 is gone")
        self.assertEqual(sc.parse_outcome(text), ("crashed", "holder pid 12 is gone"))
        self.assertEqual(sc.parse_outcome("crashed"), ("crashed", ""))

    def test_hygiene_and_cap(self):
        text = sc.format_outcome("unreadable", "a|b\nc" + "x" * 400)
        self.assertNotIn("|", text)
        self.assertNotIn("\n", text)
        self.assertLessEqual(len(text), 200)


# --- clock -----------------------------------------------------------------------

class LockAge(unittest.TestCase):
    def setUp(self):
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()

    def tearDown(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()

    def test_buckets_at_their_boundaries(self):
        now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)

        def at(delta):
            return (now - delta).strftime("%Y-%m-%d %H:%M")
        self.assertEqual(sc.age_bucket(at(timedelta(minutes=59)), now), "<1h")
        self.assertEqual(sc.age_bucket(at(timedelta(hours=1)), now), "1h-1d")
        self.assertEqual(sc.age_bucket(at(timedelta(hours=23, minutes=59)), now), "1h-1d")
        self.assertEqual(sc.age_bucket(at(timedelta(days=1)), now), "1d-7d")
        self.assertEqual(sc.age_bucket(at(timedelta(days=7)), now), ">7d")
        self.assertEqual(sc.age_bucket(at(timedelta(minutes=-30)), now), "<1h")
        self.assertEqual(sc.age_bucket("garbage", now), "unknown")

    def test_pinned_clock(self):
        os.environ["AITASK_SITREP_NOW"] = "2026-11-15T12:00:00Z"
        try:
            self.assertEqual(sc.now_utc(), datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc))
        finally:
            del os.environ["AITASK_SITREP_NOW"]


class RetainPointer(unittest.TestCase):
    def test_local_pointer_equals_the_writer(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, AITASK_SITREP_DIR=os.path.join(d, "store"))
            for data in (b"one line\n", b"a\nb\nc\n", b"no trailing newline", b"x\n\ny"):
                with self.subTest(data=data):
                    p = subprocess.run([str(WRITER), "retain"], input=data, cwd=d, env=env,
                                       capture_output=True, check=True)
                    got = [ln for ln in p.stdout.decode().splitlines()
                           if ln.startswith("RETAINED:")]
                    self.assertEqual(got, [f"RETAINED:{sc.retain_pointer(data)}"])


# --- strict readers ----------------------------------------------------------------

class LockBlobs(unittest.TestCase):
    def test_strict_parse(self):
        good = b"task_id: 7\nlocked_by: a@b\nlocked_at: 2026-11-13 11:04\nhostname: h\npid: 1\n"
        rec = sc.parse_lock_blob("7", good)
        self.assertEqual(rec.state, "ok")
        self.assertEqual(rec.fields["locked_at"], "2026-11-13 11:04")
        for name, blob in [
            ("not utf-8", b"task_id: 7\nhostname: \xff\xfe\n"),
            ("no task_id", b"hostname: h\npid: 1\n"),
            ("no hostname", b"task_id: 7\npid: 1\n"),
            ("mismatched id", b"task_id: 8\nhostname: h\n"),
            ("duplicate key", b"task_id: 7\nhostname: h\nhostname: g\n"),
            ("malformed line", b"task_id: 7\nhostname: h\ngarbage\n"),
        ]:
            with self.subTest(name):
                self.assertEqual(sc.parse_lock_blob("7", blob).state, "error")


def lock_branch(root, files: dict, ref="refs/remotes/origin/aitask-locks"):
    """Commit `files` ({name: bytes}) as the lock tree under `ref`."""
    entries = []
    for name, data in files.items():
        oid = git(root, "hash-object", "-w", "--stdin", data=data)
        entries.append(f"100644 blob {oid}\t{name}")
    tree = git(root, "mktree", data=("\n".join(entries) + "\n").encode() if entries else b"")
    commit = git(root, "commit-tree", tree, "-m", "locks")
    git(root, "update-ref", ref, commit)


class GitCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        os.makedirs(os.path.join(self.root, "aitasks", "archived"))
        os.makedirs(os.path.join(self.root, "aiplans"))
        self.write(".gitignore", ".aitask-sitrep/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")

    def tearDown(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            for n in dirnames + filenames:
                try:
                    os.chmod(os.path.join(dirpath, n), 0o755)
                except OSError:
                    pass
        self._tmp.cleanup()

    def write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def commit(self, msg="c"):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", msg)
        return git(self.root, "rev-parse", "HEAD")


class LockReader(GitCase):
    def test_reads_full_tree_from_any_cwd(self):
        lock_branch(self.root, {
            "t7_lock.yaml": b"task_id: 7\nhostname: h\npid: 1\n",
            "t8_2_lock.yaml": b"task_id: 8_2\nhostname: h\n",
            "t9_lock.yaml": b"task_id: 9\n",
            "README": b"not a lock\n",
        })
        os.makedirs(os.path.join(self.root, "sub"))
        cwd = os.getcwd()
        os.chdir(os.path.join(self.root, "sub"))
        try:
            locks = sc.read_locks(self.root)
        finally:
            os.chdir(cwd)
        self.assertEqual(sorted(locks), ["7", "8_2", "9"])
        self.assertEqual(locks["7"].state, "ok")
        self.assertEqual(locks["8_2"].state, "ok")
        self.assertEqual(locks["9"].state, "error")

    def test_local_branch_fallback_and_missing_ref(self):
        with self.assertRaises(sc.SourceError) as cm:
            sc.read_locks(self.root)
        self.assertEqual(str(cm.exception), "no_lock_ref")
        lock_branch(self.root, {"t7_lock.yaml": b"task_id: 7\nhostname: h\n"},
                    ref="refs/heads/aitask-locks")
        self.assertEqual(sorted(sc.read_locks(self.root)), ["7"])

    def test_absent_from_tree_means_no_lock(self):
        lock_branch(self.root, {"t7_lock.yaml": b"task_id: 7\nhostname: h\n"})
        self.assertNotIn("8", sc.read_locks(self.root))

    def test_unreadable_blob_is_a_per_lock_error(self):
        lock_branch(self.root, {"t7_lock.yaml": b"task_id: 7\nhostname: h\n",
                                "t8_lock.yaml": b"task_id: 8\nhostname: h\n"})
        oid = git(self.root, "rev-parse", "refs/remotes/origin/aitask-locks:t8_lock.yaml")
        obj = os.path.join(self.root, ".git", "objects", oid[:2], oid[2:])
        os.chmod(obj, 0o644)
        os.unlink(obj)
        locks = sc.read_locks(self.root)
        self.assertEqual(locks["7"].state, "ok")
        self.assertEqual(locks["8"].state, "error")


class TaskReader(GitCase):
    def bundle(self, files: dict):
        d = os.path.join(self.root, "aitasks", "archived", "_b0")
        os.makedirs(d, exist_ok=True)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for member, text in files.items():
                data = text.encode("utf-8")
                info = tarfile.TarInfo(member)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        with open(os.path.join(d, "old0.tar.gz"), "wb") as fh:
            fh.write(buf.getvalue())

    def test_active_records(self):
        self.write("aitasks/t1_ok.md", task_text("Implementing"))
        self.write("aitasks/t2_nostatus.md", task_text(None))
        self.write("aitasks/t3_banana.md", task_text("Banana"))
        self.write("aitasks/t4_yaml.md", "---\nstatus: [unclosed\n---\n")
        self.write("aitasks/t5/t5_1_child.md", task_text("Implementing"))
        self.write("aitasks/t6_folded.md", task_text("Implementing", "folded_into: 1"))
        tasks = sc.read_active_tasks(self.root)
        self.assertTrue(tasks["1"].implementing)
        self.assertEqual(tasks["1"].rel, "aitasks/t1_ok.md")
        self.assertEqual(tasks["1"].slug, "ok")
        for tid in ("2", "3", "4"):
            self.assertEqual(tasks[tid].where, "error", tid)
        self.assertTrue(tasks["5_1"].implementing)
        self.assertEqual(tasks["5_1"].stem, "t5_1_child")
        self.assertFalse(tasks["6"].implementing)

    @unittest.skipIf(os.geteuid() == 0, "root reads chmod-000 files")
    def test_unreadable_active_file(self):
        p = self.write("aitasks/t1_ok.md", task_text("Implementing"))
        os.chmod(p, 0)
        self.assertEqual(sc.read_active_tasks(self.root)["1"].where, "error")

    @unittest.skipIf(os.geteuid() == 0, "root lists chmod-000 dirs")
    def test_unlistable_task_dir_fails_the_pass(self):
        os.makedirs(os.path.join(self.root, "aitasks", "t5"))
        os.chmod(os.path.join(self.root, "aitasks", "t5"), 0)
        with self.assertRaises(sc.SourceError):
            sc.read_active_tasks(self.root)

    def test_archived_records_are_validated(self):
        idx = sr.TaskIndex(self.root)
        self.write("aitasks/archived/t10_ok.md", task_text("Done"))
        self.write("aitasks/archived/t11_nostatus.md", task_text(None))
        self.write("aitasks/archived/t12_banana.md", task_text("Banana"))
        self.write("aitasks/archived/t13/t13_1_child.md", task_text(""))
        self.bundle({"t20_ok.md": task_text("Done"),
                     "t21_nostatus.md": task_text(None),
                     "t22_banana.md": task_text("Banana"),
                     "t23_yaml.md": "---\nstatus: [unclosed\n---\n"})
        got = {t: sc.read_inactive_task(self.root, t, idx)
               for t in ("10", "11", "12", "13_1", "20", "21", "22", "23", "99")}
        self.assertEqual((got["10"].where, got["10"].status), ("archived", "Done"))
        self.assertEqual(got["10"].rel, "aitasks/archived/t10_ok.md")
        self.assertEqual((got["20"].where, got["20"].status), ("archived", "Done"))
        self.assertEqual(got["20"].rel, "")
        for tid in ("11", "12", "13_1", "21", "22", "23"):
            self.assertEqual(got[tid].where, "error", tid)
        # An unparseable record anywhere makes the fold scan unable to prove
        # "missing": fail closed, never absent.
        self.assertEqual(got["99"].where, "error")
        self.assertIn("fold scan", got["99"].why)
        # TaskIndex validates the status too (t2307): the same verdict class.
        facts = idx.lookup("12")
        self.assertEqual(facts.found, "error")
        self.assertIn("invalid status 'Banana'", facts.detail)

    def test_fold_scan(self):
        idx = sr.TaskIndex(self.root)
        self.write("aitasks/t30_receiver.md", task_text("Ready", "folded_tasks: [31]"))
        rec = sc.read_inactive_task(self.root, "31", idx)
        self.assertEqual((rec.where, rec.folded), ("fold_scan", True))
        self.assertEqual(sc.read_inactive_task(self.root, "99", idx).where, "missing")


# --- evidence -----------------------------------------------------------------------

class Porcelain(unittest.TestCase):
    def test_renames_skip_the_source(self):
        out = b" M a.py\0R  new.py\0old.py\0?? c.py\0"
        self.assertEqual(sc.parse_porcelain(out), ["a.py", "c.py", "new.py"])


class Names(unittest.TestCase):
    def test_exact_and_unique_suffix(self):
        tracked = {".aitask-scripts/lib/a.py", "tests/a.py", "docs/x.md", "README.md"}
        idx = sc.build_suffix_index(tracked)
        text = ("edit `lib/a.py:12`, then docs/x.md. Also a.py and README.md; "
                "../escape/y.md and lib/missing.py")
        self.assertEqual(sc.named_paths(text, tracked, idx),
                         {".aitask-scripts/lib/a.py", "docs/x.md", "README.md"})


class NamesHidden(unittest.TestCase):
    def test_hidden_directory_paths_keep_their_leading_dot(self):
        universe = {".aitask-scripts/lib/a.py", ".github/workflows/ci.yml", "src/b.py"}
        idx = sc.build_suffix_index(universe)
        text = ("Edit `.aitask-scripts/lib/a.py`, then ./src/b.py. "
                "See .github/workflows/ci.yml.")
        self.assertEqual(sc.named_paths(text, universe, idx), universe)


class NamesWhole(unittest.TestCase):
    def test_explicit_entries_and_backticked_spans_are_complete_paths(self):
        universe = {"src/my file.py", "docs/a b/c.md", "src/x.py"}
        idx = sc.build_suffix_index(universe)
        self.assertEqual(sc.named_paths("", universe, idx, explicit=["src/my file.py:12"]),
                         {"src/my file.py"})
        self.assertEqual(sc.named_paths("see `docs/a b/c.md#L3-L9` and `src/x.py:4-8`.",
                                        universe, idx), {"docs/a b/c.md", "src/x.py"})
        # Bare prose never reassembles a spaced name.
        self.assertEqual(sc.named_paths("edit src/my file.py", universe, idx), set())


class PlanAndWork(GitCase):
    def setUp(self):
        super().setUp()
        self._cwd = os.getcwd()
        self.write("src/a.py", "a\n")
        self.write("src/b.py", "b\n")
        self.base = self.commit("files")
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._cwd)
        super().tearDown()

    def run_survey(self, tid, extra="", body="", ledger=""):
        text = task_text("Implementing", extra, body) + ledger
        self.write(f"aitasks/t{tid}_x.md", text)
        p = sc.Pass(self.root, dry_run=True)
        tasks = sc.read_active_tasks(self.root)
        verdicts = {t: sc.Verdict(8, "orphan", True, "open", "x") for t in tasks}
        s = p.survey(tasks[tid], verdicts[tid], None, "0123456789ab", verdicts, tasks)
        return p, s

    def test_no_files_and_no_baseline(self):
        _, s = self.run_survey("1", body="nothing named")
        self.assertEqual(s.plan_fresh, "unknown:no_files")
        _, s = self.run_survey("2", body="edits src/a.py")
        self.assertEqual(s.plan_fresh, "unknown:no_baseline")

    def test_commits_since_the_premise_baseline(self):
        self.write("src/a.py", "a2\n")
        self.commit("touch a")
        _, s = self.run_survey("1", f"premise_baseline: {self.base} @ 2026-11-01 10:00",
                               "edits src/a.py")
        self.assertEqual(s.plan_fresh, "stale:1_commits")
        _, s = self.run_survey("2", f"premise_baseline: {self.base} @ 2026-11-01 10:00",
                               "edits src/b.py")
        self.assertEqual(s.plan_fresh, "fresh")

    def test_dirty_shared_file_is_stale_and_attributed(self):
        head = git(self.root, "rev-parse", "HEAD")
        self.write("src/a.py", "dirty\n")
        self.write("src/b.py", "dirty\n")
        p, s = self.run_survey("1", f"premise_baseline: {head} @ 2026-11-01 10:00",
                               "edits src/a.py")
        self.assertEqual(s.plan_fresh, "stale:dirty_referenced:1")
        self.assertEqual(s.attributed, [("src/a.py", "task")])
        self.assertTrue(s.survivors)
        # Control: the unnamed dirty file is never attributed.
        self.assertNotIn("src/b.py", [x for x, _ in s.attributed])

    def test_dirty_hidden_directory_file_is_attributed(self):
        self.write(".aitask-scripts/lib/a.py", "a\n")
        self.write(".aitask-scripts/lib/clean.py", "c\n")
        head = self.commit("hidden")
        self.write(".aitask-scripts/lib/a.py", "dirty\n")
        _, s = self.run_survey("1", f"premise_baseline: {head} @ x",
                               "edits `.aitask-scripts/lib/a.py` and .aitask-scripts/lib/clean.py")
        self.assertEqual(s.attributed, [(".aitask-scripts/lib/a.py", "task")])
        self.assertEqual(s.plan_fresh, "stale:dirty_referenced:1")
        self.assertTrue(s.survivors)

    def test_spaced_filename_from_file_references_and_backticks(self):
        self.write("src/my file.py", "a\n")
        head = self.commit("spaced")
        self.write("src/my file.py", "dirty\n")
        for extra, body in [
            (f"premise_baseline: {head} @ x\nfile_references: ['src/my file.py:3', 'src/b.py']",
             "nothing named in prose"),
            (f"premise_baseline: {head} @ x", "edits `src/my file.py` and src/b.py"),
        ]:
            with self.subTest(extra=extra):
                _, s = self.run_survey("1", extra, body)
                self.assertEqual(s.attributed, [("src/my file.py", "task")])
                self.assertEqual(s.plan_fresh, "stale:dirty_referenced:1")

    def test_named_untracked_file_is_attributed(self):
        head = git(self.root, "rev-parse", "HEAD")
        self.write("src/new.py", "new\n")         # untracked, named
        self.write("src/stray.py", "stray\n")     # untracked, unnamed (control)
        p, s = self.run_survey("1", f"premise_baseline: {head} @ x", "creates src/new.py")
        self.assertEqual(s.attributed, [("src/new.py", "task")])
        self.assertEqual(s.plan_fresh, "stale:dirty_referenced:1")
        self.assertNotIn("src/stray.py", [x for x, _ in s.attributed])
        tasks = sc.read_active_tasks(self.root)
        verdicts = {t: sc.Verdict(8, "orphan", True, "open", "x") for t in tasks}
        self.assertIn("src/stray.py", p._unattributed(verdicts, tasks))
        self.assertNotIn("src/new.py", p._unattributed(verdicts, tasks))
        # Task data (the untracked aitasks/t1_x.md itself) is not code work.
        self.assertFalse([x for x in p.shared_dirty() if x.startswith(("aitasks/", "aiplans/"))])

    def test_failed_status_is_never_an_empty_tree(self):
        with open(os.path.join(self.root, ".git", "index"), "wb") as fh:
            fh.write(b"garbage")
        p = sc.Pass(self.root, dry_run=True)
        with self.assertRaises(sc.CrashFailure) as cm:
            p.shared_dirty()
        self.assertEqual(str(cm.exception), "shared_status_unreadable")

    @unittest.skipIf(os.geteuid() == 0, "root reads chmod-000 files")
    def test_unreadable_plan_is_recorded_not_empty(self):
        self.write("aitasks/t2_x.md", task_text("Implementing", body="x"))
        plan = self.write("aiplans/p2_x.md", "edits src/a.py\n")
        os.chmod(plan, 0)
        self.write("src/a.py", "dirty\n")
        p, s = self.run_survey("1", body="edits src/a.py")
        self.assertIn("2", p.plan_errors)
        self.assertIn(("?", "t2", "plan_unreadable"), s.overlaps)

    def test_dirty_file_in_a_dedicated_worktree_is_surviving_work_not_stale(self):
        head = git(self.root, "rev-parse", "HEAD")
        wt = os.path.join(self.root, "aiwork", "t1_x")
        git(self.root, "worktree", "add", "-q", "-b", "aitask/t1_x", wt, "main")
        with open(os.path.join(wt, "src", "a.py"), "w") as fh:
            fh.write("wt\n")
        _, s = self.run_survey("1", f"premise_baseline: {head} @ 2026-11-01 10:00",
                               "edits src/a.py")
        self.assertEqual(s.worktree, f"worktree {wt}")
        self.assertEqual(s.attributed, [("src/a.py", "worktree")])
        self.assertEqual(s.plan_fresh, "fresh")
        self.assertTrue(s.branch_head)

    def test_overlap_between_two_implementing_tasks(self):
        self.write("aitasks/t2_x.md", task_text("Implementing", body="also src/a.py"))
        self.write("src/a.py", "dirty\n")
        _, s = self.run_survey("1", body="edits src/a.py")
        self.assertEqual(s.overlaps, [("src/a.py", "t2", "crashed")])

    def test_ledger_phases_and_signature(self):
        ledger = ("\n## Gate Runs\n\n"
                  "> **✅ gate:plan_approved** run=2026-11-15T10:00:00Z status=pass "
                  "attempt=1 type=human\n")
        _, s = self.run_survey("1", "gates: [plan_approved]", "edits src/a.py", ledger)
        self.assertEqual((s.phase, s.phase_provenance), ("implementing", "ledger"))
        self.assertEqual((s.plan, s.plan_signature), ("approved", "valid"))
        post = ledger + ("> **✅ gate:review_approved** run=2026-11-15T11:00:00Z "
                         "status=pass attempt=1 type=human\n")
        _, s = self.run_survey("2", "gates: [plan_approved, docs_updated]", "x", post)
        self.assertEqual(s.phase, "post_impl")
        self.assertIn("docs_updated", s.pending_gates)
        _, s = self.run_survey("3", "", "x")
        self.assertEqual((s.phase, s.phase_provenance, s.plan), ("unknown", "unknown", "none"))

    def test_stale_signature_from_a_witness_digest_mismatch(self):
        self.write("aitasks/metadata/gates.yaml",
                   "gates:\n  plan_approved:\n    type: human\n"
                   "    signal_target: witness/<task-id>_<gate>\n")
        self.write("witness/t1_plan_approved", "code_digest=deadbeef\n")
        ledger = ("\n## Gate Runs\n\n"
                  "> **✅ gate:plan_approved** run=2026-11-15T10:00:00Z status=pass "
                  "attempt=1 type=human\n")
        head = git(self.root, "rev-parse", "HEAD")
        _, s = self.run_survey("1", f"gates: [plan_approved]\npremise_baseline: {head} @ x",
                               "edits src/a.py", ledger)
        self.assertEqual(s.plan_signature, "stale")
        self.assertTrue(s.plan_fresh.startswith("stale:signature_stale"), s.plan_fresh)

    def test_unreadable_ledger_is_an_error_phase(self):
        saved = sc.gl.resume_point_from_text

        def boom(_text):
            raise ValueError("bad ledger")
        sc.gl.resume_point_from_text = boom
        try:
            ledger = "\n## Gate Runs\n\n> **✅ gate:plan_approved** run=x status=pass\n"
            _, s = self.run_survey("1", "", "x", ledger)
        finally:
            sc.gl.resume_point_from_text = saved
        self.assertEqual((s.phase, s.phase_provenance), ("error", "error"))


class Rendering(unittest.TestCase):
    def survey(self, **kw):
        task = sc.TaskRec("12", "active", status="Implementing", slug="fix_it", rel="aitasks/t12_fix_it.md")
        s = sc.Survey(task=task, verdict=sc.Verdict(6, "crashed", True, "open", "gone"),
                      key="0123456789ab", lock=lock("12"))
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    def test_survey_is_deterministic_and_starts_with_the_header(self):
        s = self.survey(attributed=[("src/a.py", "plan")], overlaps=[("src/a.py", "t9", "live")])
        a, b = sc.Pass.survey_text(s), sc.Pass.survey_text(s)
        self.assertEqual(a, b)
        lines = a.decode().splitlines()
        self.assertEqual(lines[0], sc.SURVEY_HEADER)
        keys = [ln.split(":", 1)[0] for ln in lines[1:]]
        self.assertEqual(keys, ["task", "category", "incarnation", "lock", "lock_age", "phase",
                                "phase_provenance", "pending_gates", "plan", "plan_signature",
                                "plan_fresh", "worktree", "uncommitted_files", "attributed",
                                "overlap", "commits", "warning"])
        self.assertIn(sc.SURVIVOR_WARNING, lines[-1])

    def test_unattributed_and_incomplete_evidence_still_warn(self):
        s = self.survey(unattributed=2)
        self.assertFalse(s.survivors)
        self.assertEqual(s.warning(), sc.UNATTRIBUTED_WARNING)
        self.assertIn("warning: " + sc.UNATTRIBUTED_WARNING,
                      sc.Pass.survey_text(s).decode())
        s = self.survey(incomplete=["commits"])
        self.assertIn("evidence incomplete (commits)", s.warning())
        self.assertIn("commits: unknown", sc.Pass.survey_text(s).decode())
        self.assertEqual(self.survey().warning(), "none")

    def test_title_and_group(self):
        s = self.survey(phase="implementing", plan="approved", plan_signature="valid",
                        plan_fresh="stale:dirty_referenced:2",
                        attributed=[("a", "plan")], overlaps=[("a", "t2286", "crashed")])
        title = sc.Pass.title_of(s)
        self.assertEqual(title, "Recover t12 fix_it (crashed): implementing, approved plan "
                                "(stale: dirty_referenced), 1 files, overlaps t2286")
        self.assertEqual(sc.Pass.group_of(s), "now")
        s.plan = "draft"
        self.assertEqual(sc.Pass.group_of(s), "next")
        s.verdict = sc.Verdict(7, "stale_lock", True, "open", "x")
        self.assertEqual(sc.Pass.group_of(s), "waiting")
        s.verdict = sc.Verdict(8, "orphan", True, "open", "x")
        s.plan = "approved"
        self.assertEqual(sc.Pass.group_of(s), "next")

    def test_rank(self):
        s = self.survey(phase="implementing", plan="approved", plan_signature="valid",
                        plan_fresh="fresh", attributed=[("a", "plan")])
        self.assertEqual(sc.Pass.rank_of(s), 1)
        s.plan_fresh = "unknown:no_baseline"
        self.assertEqual(sc.Pass.rank_of(s), 2)
        s.plan = "draft"
        self.assertEqual(sc.Pass.rank_of(s), 3)
        s.plan = "none"
        self.assertEqual(sc.Pass.rank_of(s), 4)


if __name__ == "__main__":
    unittest.main()
