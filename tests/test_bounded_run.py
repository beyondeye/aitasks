"""Tests for .aitask-scripts/lib/bounded_run.py (t2024).

bounded_run is the runner every crew fetch/push goes through (agentcrew_utils.sh's
_crew_git_bounded, agentcrew_utils.py's git_cmd(timeout=)) and that brainstorm
uses to bound `ait crew addwork`. These cells pin its process contract: what is
killed, when, and what survives. The nested arrangement (brainstorm -> addwork
-> CLI -> git) is driven end to end by tests/test_brainstorm_addwork_deadline.sh.

Run: python3 -m pytest tests/test_bounded_run.py   (or via run_all_python_tests.sh)
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB = REPO_ROOT / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

import bounded_run as br  # noqa: E402
from agentcrew.agentcrew_utils import crew_git_timeout, git_cmd  # noqa: E402

CLI = [sys.executable, str(LIB / "bounded_run.py")]

# A child that records its pid, ignores SIGTERM and sleeps: only a SIGKILL ends it.
TERM_IGNORING = "trap '' TERM; echo $$ > {pidfile}; exec sleep 30"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _gone_within(pid: int, seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return not _alive(pid)


def _read_pid(path: Path, seconds: float = 5.0) -> int:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        text = path.read_text().strip() if path.exists() else ""
        if text:
            return int(text.splitlines()[0])
        time.sleep(0.05)
    raise AssertionError(f"fixture never wrote {path}")


class _TmpDirCase(unittest.TestCase):
    """Per-test scratch dir plus a list of pids to SIGKILL on teardown."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ait_bounded_run_")
        self.tmp = Path(self._tmp.name)
        self.pidfile = self.tmp / "child.pid"
        self.leftovers: list[int] = []

    def tearDown(self):
        for pid in self.leftovers:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self._tmp.cleanup()


class TestRunBounded(_TmpDirCase):
    def test_normal_output_and_returncode(self):
        result = br.run_bounded(["sh", "-c", "echo out; echo err >&2; exit 3"], 10)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (3, "out\n", "err\n"))
        self.assertFalse(result.stopped)

    def test_expiry_kills_a_term_ignoring_grandchild(self):
        # \$\$: the INNER shell must expand it, or the pid recorded is the leader's.
        inner = TERM_IGNORING.format(pidfile=self.pidfile).replace("$$", "\\$\\$")
        cmd = ["sh", "-c", f"sh -c \"{inner}\" & wait"]
        start = time.monotonic()
        with patch.dict(os.environ, {br.GRACE_ENV: "1"}):
            with self.assertRaises(subprocess.TimeoutExpired):
                br.run_bounded(cmd, 1)
        elapsed = time.monotonic() - start
        pid = _read_pid(self.pidfile)
        self.leftovers.append(pid)
        self.assertTrue(_gone_within(pid), "the TERM-ignoring grandchild survived")
        self.assertLess(elapsed, 1 + 1 + 1.5)

    def test_expiry_terms_the_whole_group_before_any_sigkill(self):
        # git removes its *.lock files on SIGTERM; a descendant that only ever
        # sees SIGKILL cannot clean up. The grandchild records the TERM it gets.
        marker = self.tmp / "cleaned"
        inner = (f"trap 'echo cleaned > {marker}; exit 0' TERM; "
                 f"echo \\$\\$ > {self.pidfile}; sleep 30 & wait")
        cmd = ["sh", "-c", f"sh -c \"{inner}\" & wait"]
        with patch.dict(os.environ, {br.GRACE_ENV: "2"}):
            with self.assertRaises(subprocess.TimeoutExpired):
                br.run_bounded(cmd, 1)
        self.leftovers.append(_read_pid(self.pidfile))
        self.assertTrue(marker.exists(), "the grandchild never got SIGTERM")

    def test_normal_exit_neither_waits_for_nor_kills_a_lingering_descendant(self):
        # The descendant holds stdout/stderr open, as an ssh ControlPersist master would.
        cmd = ["sh", "-c", f"sleep 30 & echo $! > {self.pidfile}; echo done"]
        start = time.monotonic()
        result = br.run_bounded(cmd, 10)
        elapsed = time.monotonic() - start
        pid = _read_pid(self.pidfile)
        self.leftovers.append(pid)
        self.assertEqual(result.stdout, "done\n")
        self.assertLess(elapsed, 2.0)
        self.assertTrue(_alive(pid), "a normal exit must not signal the group")

    def test_keyboard_interrupt_kills_the_child(self):
        def interrupt(_signum, _frame):
            raise KeyboardInterrupt

        previous = signal.signal(signal.SIGALRM, interrupt)
        try:
            signal.setitimer(signal.ITIMER_REAL, 0.5)
            with patch.dict(os.environ, {br.GRACE_ENV: "1"}):
                with self.assertRaises(KeyboardInterrupt):
                    br.run_bounded(
                        ["sh", "-c", TERM_IGNORING.format(pidfile=self.pidfile)], 20)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        pid = _read_pid(self.pidfile)
        self.leftovers.append(pid)
        self.assertTrue(_gone_within(pid), "KeyboardInterrupt left the child running")
        self.assertIs(signal.getsignal(signal.SIGINT), signal.default_int_handler,
                      "the SIGINT shield was not restored")

    def test_a_signal_during_cleanup_is_deferred_until_the_group_is_dead(self):
        """A SIGHUP that lands mid-cleanup surfaces only after the SIGKILL."""
        class Hangup(Exception):
            pass

        def on_hup(_signum, _frame):
            raise Hangup

        previous = signal.signal(signal.SIGHUP, on_hup)
        # Cleanup starts at the 0.3s timeout and waits out the 2s grace for the
        # TERM-ignoring child; the SIGHUP lands in the middle of it.
        timer = threading.Timer(1.0, os.kill, (os.getpid(), signal.SIGHUP))
        start = time.monotonic()
        try:
            timer.start()
            with patch.dict(os.environ, {br.GRACE_ENV: "2"}):
                with self.assertRaises(Hangup):
                    br.run_bounded(["sh", "-c", TERM_IGNORING.format(pidfile=self.pidfile)],
                                   0.3)
        finally:
            timer.cancel()
            signal.signal(signal.SIGHUP, previous)
        elapsed = time.monotonic() - start
        pid = _read_pid(self.pidfile)
        self.leftovers.append(pid)
        self.assertFalse(_alive(pid), "the signal cut the cleanup short")
        self.assertGreaterEqual(elapsed, 0.3 + 2 - 0.3, "the cleanup did not finish first")

    def test_stop_request_lets_a_cooperating_child_finish(self):
        script = (f"trap 'echo stopping; exit 0' TERM; echo $$ > {self.pidfile}; "
                  "sleep 30 & wait")
        start = time.monotonic()
        result = br.run_bounded(["sh", "-c", script], 0.5, stop_grace=5)
        elapsed = time.monotonic() - start
        self.assertTrue(result.stopped)
        self.assertEqual(result.returncode, 0)
        self.assertIn("stopping", result.stdout)
        self.assertLess(elapsed, 0.5 + 2.0)

    def test_stop_request_ignored_is_killed_after_the_stop_grace(self):
        start = time.monotonic()
        with patch.dict(os.environ, {br.GRACE_ENV: "1"}):
            with self.assertRaises(subprocess.TimeoutExpired):
                br.run_bounded(["sh", "-c", TERM_IGNORING.format(pidfile=self.pidfile)],
                               0.5, stop_grace=1)
        elapsed = time.monotonic() - start
        pid = _read_pid(self.pidfile)
        self.leftovers.append(pid)
        self.assertTrue(_gone_within(pid))
        self.assertGreaterEqual(elapsed, 0.5 + 1 - 0.2, "the stop grace was not honoured")
        self.assertLess(elapsed, 0.5 + 1 + 1 + 1.5)

    def test_timeout_carries_the_output_so_far(self):
        with self.assertRaises(subprocess.TimeoutExpired) as ctx:
            br.run_bounded(["sh", "-c", "echo partial; exec sleep 30"], 0.5)
        self.assertEqual(ctx.exception.output, "partial\n")


class TestGracePropagation(_TmpDirCase):
    def test_a_child_sees_a_strictly_smaller_grace(self):
        probe = [sys.executable, "-c",
                 f"import os; print(os.environ.get({br.GRACE_ENV!r}))"]
        env = {k: v for k, v in os.environ.items() if k != br.GRACE_ENV}
        with patch.dict(os.environ, env, clear=True):
            top = br.run_bounded(probe, 10)
        self.assertEqual(float(top.stdout), br.KILL_GRACE_SECONDS - br.NESTING_MARGIN_SECONDS)
        with patch.dict(os.environ, {br.GRACE_ENV: "2.5"}):
            nested = br.run_bounded(probe, 10)
        self.assertEqual(float(nested.stdout), br.MIN_GRACE_SECONDS)

    def test_effective_grace_normalization(self):
        for raw in ("", "abc", "0", "-1", "nan", "inf", "61"):
            self.assertEqual(br.effective_grace({br.GRACE_ENV: raw}), br.KILL_GRACE_SECONDS, raw)
        self.assertEqual(br.effective_grace({br.GRACE_ENV: "2.5"}), 2.5)
        self.assertEqual(br.effective_grace({}), br.KILL_GRACE_SECONDS)

    def test_the_cli_honours_an_inherited_grace(self):
        """The grace the CLI waits before SIGKILL is the one its parent handed it."""
        cmd = CLI + ["--timeout", "0.5", "--", "sh", "-c",
                     TERM_IGNORING.format(pidfile=self.pidfile)]
        env = dict(os.environ, **{br.GRACE_ENV: "3"})
        start = time.monotonic()
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        elapsed = time.monotonic() - start
        pid = _read_pid(self.pidfile)
        self.leftovers.append(pid)
        self.assertEqual(proc.returncode, br.TIMED_OUT)
        self.assertTrue(_gone_within(pid))
        self.assertGreaterEqual(elapsed, 0.5 + 3 - 0.3)
        self.assertLess(elapsed, 0.5 + 3 + 2.0)


class TestCli(_TmpDirCase):
    def test_passthrough(self):
        proc = subprocess.run(CLI + ["--timeout", "10", "--", "sh", "-c",
                                     "echo o; echo e >&2; exit 4"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (4, "o\n", "e\n"))

    def test_timeout_exits_124(self):
        proc = subprocess.run(CLI + ["--timeout", "0.5", "--", "sleep", "5"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, br.TIMED_OUT)
        self.assertIn("timed out after 0.5s", proc.stderr)

    def test_missing_command_exits_127(self):
        proc = subprocess.run(CLI + ["--timeout", "5", "--", "/nonexistent/ait-no-such-cmd"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, br.NOT_FOUND)

    def test_sigint_kills_the_tree_and_the_cli_dies_by_sigint(self):
        cmd = CLI + ["--timeout", "30", "--", "sh", "-c",
                     TERM_IGNORING.format(pidfile=self.pidfile)]
        env = dict(os.environ, **{br.GRACE_ENV: "1"})
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        try:
            pid = _read_pid(self.pidfile)
            self.leftovers.append(pid)
            proc.send_signal(signal.SIGINT)
            rc = proc.wait(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
        self.assertEqual(rc, -signal.SIGINT, "the CLI must die by the signal it got")
        self.assertTrue(_gone_within(pid), "the TERM-ignoring grandchild survived")

    def test_term_or_hup_during_the_timeout_cleanup(self):
        """A signal after the timeout cleanup has begun: the cleanup still reaches
        SIGKILL, and only then does the CLI die by that signal."""
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=sig.name):
                pidfile = self.tmp / f"{sig.name}.pid"
                cmd = CLI + ["--timeout", "0.3", "--", "sh", "-c",
                             TERM_IGNORING.format(pidfile=pidfile)]
                env = dict(os.environ, **{br.GRACE_ENV: "2"})
                start = time.monotonic()
                proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                try:
                    pid = _read_pid(pidfile)
                    self.leftovers.append(pid)
                    # Cleanup runs from the 0.3s timeout to about 2.3s.
                    time.sleep(max(0.0, 1.0 - (time.monotonic() - start)))
                    proc.send_signal(sig)
                    rc = proc.wait(timeout=10)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                elapsed = time.monotonic() - start
                self.assertEqual(rc, -sig, "the CLI must still die by the signal")
                self.assertFalse(_alive(pid), "the signal cut the cleanup short")
                self.assertGreaterEqual(elapsed, 0.3 + 2 - 0.3,
                                        "the CLI died before its cleanup finished")


class TestNoninteractivePolicy(unittest.TestCase):
    def test_noninteractive_env(self):
        base = {
            "GIT_SSH_COMMAND": "ssh -i key", "GIT_SSH": "/usr/bin/plink",
            "SSH_ASKPASS": "/usr/bin/ksshaskpass", "DISPLAY": ":0",
            "WAYLAND_DISPLAY": "wayland-0", "GIT_ASKPASS": "/bin/askpass",
            "SSH_ASKPASS_REQUIRE": "force", "KEEP": "1",
        }
        snapshot = dict(base)
        env = br.noninteractive_env(base)
        self.assertEqual(base, snapshot, "the base mapping must not be modified")
        for name in ("SSH_ASKPASS", "DISPLAY", "WAYLAND_DISPLAY"):
            self.assertNotIn(name, env)
        self.assertEqual(env["GIT_ASKPASS"], "")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["SSH_ASKPASS_REQUIRE"], "never")
        self.assertEqual(env["GCM_INTERACTIVE"], "never")
        # Configured SSH commands are left alone: no option injection.
        self.assertEqual(env["GIT_SSH_COMMAND"], "ssh -i key")
        self.assertEqual(env["GIT_SSH"], "/usr/bin/plink")
        self.assertEqual(env["KEEP"], "1")


class TestChildIsolation(unittest.TestCase):
    """The child never has a controlling terminal, and leads its own group
    (t2035). A new session only when this runner has a terminal to drop;
    otherwise the caller's session, so a session-scoped stop still reaches it."""

    def test_a_controlling_terminal_forces_a_new_session(self):
        with patch.object(br, "_has_controlling_terminal", lambda: True):
            self.assertEqual(br._child_isolation(), {"start_new_session": True})

    def test_no_terminal_keeps_the_callers_session(self):
        with patch.object(br, "_has_controlling_terminal", lambda: False):
            kw = br._child_isolation()
        if sys.version_info >= (3, 11):
            self.assertEqual(kw, {"process_group": 0})
        else:
            self.assertNotIn("start_new_session", kw)  # single-threaded test run

    def test_threaded_pre_311_falls_back_to_a_new_session(self):
        with patch.object(br, "_has_controlling_terminal", lambda: False), \
                patch.object(br.sys, "version_info", (3, 10)), \
                patch.object(br.threading, "active_count", lambda: 2):
            self.assertEqual(br._child_isolation(), {"start_new_session": True})

    def test_without_a_terminal_the_child_shares_our_session_in_its_own_group(self):
        script = "import os; print(os.getsid(0), os.getpgid(0), os.getpid())"
        with patch.object(br, "_has_controlling_terminal", lambda: False):
            result = br.run_bounded([sys.executable, "-c", script], 10)
        sid, pgid, pid = (int(v) for v in result.stdout.split())
        self.assertEqual(sid, os.getsid(0))
        self.assertEqual(pgid, pid)

    def test_with_a_terminal_the_child_gets_a_session_of_its_own(self):
        script = "import os; print(os.getsid(0), os.getpid())"
        with patch.object(br, "_has_controlling_terminal", lambda: True):
            result = br.run_bounded([sys.executable, "-c", script], 10)
        sid, pid = (int(v) for v in result.stdout.split())
        self.assertEqual(sid, pid)

    @unittest.skipUnless(Path("/proc/self/stat").exists(), "/proc backend")
    def test_a_stop_reaps_the_group_even_after_the_leader_ended(self):
        # A session-scoped stop SIGTERMs the leader directly, so it can be gone
        # before the runner notices the stop; its TERM-ignoring child must still
        # be reaped. Deterministic: the stop reads true only once the leader has
        # exited, so the only path that can reap the child is the post-exit one.
        import shutil
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        pidfile, leaderfile = tmp / "child.pid", tmp / "leader.pid"
        # The stubborn child is its own script, so its `$$` is its own pid and
        # no shell quoting can hand it the leader's.
        child_script = tmp / "child.sh"
        child_script.write_text(TERM_IGNORING.format(pidfile=pidfile) + "\n")
        leader = (f"echo $$ > {leaderfile}; sh {child_script} & "
                  f"while [ ! -s {pidfile} ]; do sleep 0.02; done; exit 0")

        def read_pid(path: Path) -> int | None:
            try:
                text = path.read_text().strip()
            except FileNotFoundError:
                return None
            return int(text) if text else None

        def kill_child():
            pid = read_pid(pidfile)
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self.addCleanup(kill_child)

        def leader_gone() -> bool:
            pid = read_pid(leaderfile)
            if pid is None:
                return False
            try:
                stat = Path(f"/proc/{pid}/stat").read_text()
            except FileNotFoundError:
                return True
            return stat[stat.rfind(")") + 2:].split()[0] == "Z"

        with patch.dict(os.environ, {br.GRACE_ENV: "1"}):
            with self.assertRaises(br.Cancelled):
                br.run_bounded(["sh", "-c", leader], 10, cancelled=leader_gone)
        leader_pid, child = read_pid(leaderfile), read_pid(pidfile)
        self.assertIsNotNone(child, "fixture: the stubborn child never started")
        self.assertNotEqual(child, leader_pid,
                            "fixture: child.pid must be the child's own pid")
        time.sleep(0.2)
        self.assertFalse(_alive(child), "the stop left the leader's child running")


class TestCrewGitTimeout(_TmpDirCase):
    def test_normalization(self):
        cases = {"": 10, "0": 10, "-1": 10, "abc": 10, "08x": 10, "1234567": 10,
                 "08": 8, "3": 3}
        for raw, want in cases.items():
            with patch.dict(os.environ, {"AIT_CREW_GIT_TIMEOUT": raw}):
                self.assertEqual(crew_git_timeout(), want, raw)

    def test_git_cmd_timeout_reports_124(self):
        repo = self.tmp / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        stub = self.tmp / "hang-ssh"
        stub.write_text(f"#!/bin/sh\necho $$ > {self.pidfile}\nexec sleep 30\n")
        stub.chmod(0o755)
        for key, value in (("core.sshCommand", str(stub)), ("ssh.variant", "ssh")):
            subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin",
                        "ssh://crew-hang.invalid/repo.git"], check=True)
        start = time.monotonic()
        result = git_cmd(str(repo), "ls-remote", "origin", check=False, timeout=1)
        elapsed = time.monotonic() - start
        pid = _read_pid(self.pidfile)
        self.leftovers.append(pid)
        self.assertEqual(result.returncode, 124)
        self.assertIn("timed out after 1s", result.stderr)
        self.assertIn("AIT_CREW_GIT_TIMEOUT", result.stderr)
        self.assertLess(elapsed, 1 + br.KILL_GRACE_SECONDS + 1)
        self.assertTrue(_gone_within(pid))


if __name__ == "__main__":
    unittest.main()
