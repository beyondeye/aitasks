"""Tests for .aitask-scripts/lib/bounded_run.py (t2024).

bounded_run is the runner every crew fetch/push goes through (agentcrew_utils.sh's
_crew_git_bounded, agentcrew_utils.py's git_cmd(timeout=)) and that brainstorm
uses to bound `ait crew addwork`. These cells pin its process contract: what is
killed, when, and what survives. The nested arrangement (brainstorm -> addwork
-> CLI -> git) is driven end to end by tests/test_brainstorm_addwork_deadline.sh.

Run: python3 -m pytest tests/test_bounded_run.py   (or via run_all_python_tests.sh)
"""

from __future__ import annotations

import contextlib
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


@contextlib.contextmanager
def _signal_after(delay: float, sig: int):
    """Send ``sig`` to the main thread ``delay`` s into the block, unless it ended.

    A Timer's cancel() cannot stop a callback already past its wait, which would
    then signal whatever runs next -- a later attempt (t2147). So exiting
    disarms under the lock the callback sends under, then joins it: a signal is
    sent before the disarm, and its handler runs inside this block's exit, or
    never. Thread-directed, so it is pending on the main thread before the
    disarm can take the lock."""
    lock = threading.Lock()
    armed = [True]

    def fire():
        with lock:
            if armed[0]:
                signal.pthread_kill(threading.main_thread().ident, sig)

    timer = threading.Timer(delay, fire)
    timer.start()
    try:
        yield
    finally:
        try:
            with lock:
                armed[0] = False
        finally:
            timer.cancel()
            timer.join()


def _read_pid(path: Path, seconds: float = 30.0) -> int:
    """Wait for a fixture to record its pid. A readiness ceiling, so a quick
    fixture pays nothing for its size — but it only helps a fixture that is
    still alive. Read after the group was killed, a pid that was never written
    stays unwritten however long this waits (t2142)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        text = path.read_text().strip() if path.exists() else ""
        if text:
            return int(text.splitlines()[0])
        time.sleep(0.05)
    raise AssertionError(f"fixture never wrote {path}")


def _written_pid(path: Path) -> int | None:
    """The pid a fixture recorded, read once without waiting; None if it never did."""
    text = path.read_text().strip() if path.exists() else ""
    return int(text.splitlines()[0]) if text else None


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

    def _run_until_started(self, call, check, deadlines, pidfile=None) -> int:
        """Run ``call(deadline)`` under each deadline in turn until its fixture
        demonstrably ran -- wrote its pid -- and return that pid.

        For a pid read after the group was killed: the deadline also bounds the
        fixture's start-up, and under load the group can die before the pid is
        written, which no readiness wait can recover (t2142, t2147). ``call``
        returns its outcome; it catches an expected exception and returns it,
        so an unexpected one propagates. ``check(outcome, elapsed, deadline,
        started)`` asserts the attempt genuinely reached its deadline.

        ``started`` (the pid was written) means the fixture was ready, so the
        test's assertions apply in full. No pid proves nothing about how far the
        fixture got -- it may die at the first SIGTERM, or, paused between its
        trap and its pid write, ignore it and die pid-less at the SIGKILL -- and
        ``elapsed`` also counts start-up that nothing bounds from below. So a
        no-pid check accepts any deadline outcome under the overall ceiling,
        without a lower bound on elapsed."""
        pidfile = self.pidfile if pidfile is None else pidfile
        for deadline in deadlines:
            pidfile.unlink(missing_ok=True)
            start = time.monotonic()
            try:
                outcome = call(deadline)
            finally:
                # Register the fixture BEFORE any assertion: a failing attempt
                # must still leave teardown a pid to kill.
                elapsed = time.monotonic() - start
                pid = _written_pid(pidfile)
                if pid is not None:
                    self.leftovers.append(pid)
            try:
                check(outcome, elapsed, deadline, pid is not None)
            except AssertionError as err:
                ran = "ran" if pid is not None else "never ran"
                err.args = (f"attempt with a {deadline:g}s deadline (fixture {ran}): {err}",)
                raise
            if pid is not None:
                return pid
        self.fail(f"the fixture never wrote {pidfile.name}, even with a "
                  f"{deadlines[-1]:g}s deadline")


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

        def call(deadline):
            try:
                return br.run_bounded(cmd, deadline)
            except subprocess.TimeoutExpired as exc:
                return exc

        def check(outcome, elapsed, deadline, _started):
            self.assertIsInstance(outcome, subprocess.TimeoutExpired)
            self.assertLess(elapsed, deadline + 1 + 1.5)

        with patch.dict(os.environ, {br.GRACE_ENV: "1"}):
            pid = self._run_until_started(call, check, (1, 2, 4, 8))
        self.assertTrue(_gone_within(pid), "the TERM-ignoring grandchild survived")

    def test_expiry_terms_the_whole_group_before_any_sigkill(self):
        # git removes its *.lock files on SIGTERM; a descendant that only ever
        # sees SIGKILL cannot clean up. The grandchild records the TERM it gets.
        marker = self.tmp / "cleaned"
        inner = (f"trap 'echo cleaned > {marker}; exit 0' TERM; "
                 f"echo \\$\\$ > {self.pidfile}; sleep 30 & wait")
        cmd = ["sh", "-c", f"sh -c \"{inner}\" & wait"]

        def call(deadline):
            # A grandchild TERMed between its trap and its pid write leaves a
            # marker but no pid; only the attempt that ran may vouch for it.
            marker.unlink(missing_ok=True)
            try:
                return br.run_bounded(cmd, deadline)
            except subprocess.TimeoutExpired as exc:
                return exc

        def check(outcome, _elapsed, _deadline, _started):
            self.assertIsInstance(outcome, subprocess.TimeoutExpired)

        with patch.dict(os.environ, {br.GRACE_ENV: "2"}):
            self._run_until_started(call, check, (1, 2, 4, 8))
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

        cmd = ["sh", "-c", TERM_IGNORING.format(pidfile=self.pidfile)]

        def call(deadline):
            # The interrupt is this test's deadline; run_bounded's own stays far off.
            signal.setitimer(signal.ITIMER_REAL, deadline)
            try:
                br.run_bounded(cmd, 20)
            except KeyboardInterrupt as exc:
                return exc
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)

        def check(outcome, _elapsed, _deadline, _started):
            self.assertIsInstance(outcome, KeyboardInterrupt)
            self.assertIs(signal.getsignal(signal.SIGINT), signal.default_int_handler,
                          "the SIGINT shield was not restored")

        previous = signal.signal(signal.SIGALRM, interrupt)
        try:
            with patch.dict(os.environ, {br.GRACE_ENV: "1"}):
                pid = self._run_until_started(call, check, (0.5, 1, 2, 4))
        finally:
            signal.signal(signal.SIGALRM, previous)
        self.assertTrue(_gone_within(pid), "KeyboardInterrupt left the child running")

    def test_a_signal_during_cleanup_is_deferred_until_the_group_is_dead(self):
        """A SIGHUP that lands mid-cleanup surfaces only after the SIGKILL."""
        class Hangup(Exception):
            pass

        def on_hup(_signum, _frame):
            raise Hangup

        cmd = ["sh", "-c", TERM_IGNORING.format(pidfile=self.pidfile)]

        def call(deadline):
            # Cleanup starts at the timeout and waits out the 2s grace for the
            # TERM-ignoring child; the SIGHUP lands 0.7s into it, and never in a
            # later attempt (_signal_after).
            try:
                with _signal_after(deadline + 0.7, signal.SIGHUP):
                    br.run_bounded(cmd, deadline)
            except (Hangup, subprocess.TimeoutExpired) as exc:
                return exc

        def check(outcome, elapsed, deadline, started):
            # No pid: either deadline outcome, no elapsed bound (_run_until_started).
            if not started:
                self.assertIsInstance(outcome, (Hangup, subprocess.TimeoutExpired))
                return
            self.assertIsInstance(outcome, Hangup)
            self.assertGreaterEqual(elapsed, deadline + 2 - 0.3,
                                    "the cleanup did not finish first")

        previous = signal.signal(signal.SIGHUP, on_hup)
        try:
            with patch.dict(os.environ, {br.GRACE_ENV: "2"}):
                pid = self._run_until_started(call, check, (0.3, 0.6, 1.2, 2.4))
        finally:
            signal.signal(signal.SIGHUP, previous)
        self.assertFalse(_alive(pid), "the signal cut the cleanup short")

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
        cmd = ["sh", "-c", TERM_IGNORING.format(pidfile=self.pidfile)]

        def call(deadline):
            try:
                return br.run_bounded(cmd, deadline, stop_grace=1)
            except subprocess.TimeoutExpired as exc:
                return exc

        def check(outcome, elapsed, deadline, started):
            self.assertLess(elapsed, deadline + 1 + 1 + 1.5)
            # No pid: a leader that never reached its trap honours the stop;
            # no elapsed lower bound either (_run_until_started).
            if not started:
                if not isinstance(outcome, subprocess.TimeoutExpired):
                    self.assertIsInstance(outcome, br.BoundedResult)
                    self.assertTrue(outcome.stopped, "a normal exit is no deadline")
                return
            self.assertIsInstance(outcome, subprocess.TimeoutExpired)
            self.assertGreaterEqual(elapsed, deadline + 1 - 0.2,
                                    "the stop grace was not honoured")

        with patch.dict(os.environ, {br.GRACE_ENV: "1"}):
            pid = self._run_until_started(call, check, (0.5, 1, 2, 4))
        self.assertTrue(_gone_within(pid))

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
        env = dict(os.environ, **{br.GRACE_ENV: "3"})

        def call(deadline):
            cmd = CLI + ["--timeout", f"{deadline:g}", "--", "sh", "-c",
                         TERM_IGNORING.format(pidfile=self.pidfile)]
            return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)

        def check(proc, elapsed, deadline, started):
            self.assertEqual(proc.returncode, br.TIMED_OUT)
            self.assertLess(elapsed, deadline + 3 + 2.0)
            # No pid: no elapsed lower bound -- the interpreter's start-up is in
            # it too (_run_until_started).
            if started:
                self.assertGreaterEqual(elapsed, deadline + 3 - 0.3)

        pid = self._run_until_started(call, check, (0.5, 1, 2, 4))
        self.assertTrue(_gone_within(pid))


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
        # The deadline also bounds git's own start-up: under load (or a cold
        # /usr/bin/git xcrun shim on macOS) git can spend the whole second
        # before it execs the stub (t2142). Only a genuine timeout may be
        # retried: every attempt must still report the deadline, so an
        # unrelated git failure (e.g. exit 128) fails here instead of passing
        # as a slow start.
        def call(timeout):
            return git_cmd(str(repo), "ls-remote", "origin", check=False, timeout=timeout)

        def check(result, elapsed, timeout, _started):
            self.assertEqual(result.returncode, 124)
            self.assertIn(f"timed out after {timeout}s", result.stderr)
            self.assertIn("AIT_CREW_GIT_TIMEOUT", result.stderr)
            self.assertLess(elapsed, timeout + br.KILL_GRACE_SECONDS + 1)

        pid = self._run_until_started(call, check, (1, 2, 4, 8))
        self.assertTrue(_gone_within(pid))


class TestRunUntilStarted(_TmpDirCase):
    """The retry helper's own contract, driven by in-process fake calls."""

    def _sleeper(self) -> int:
        # A real process of our own: teardown SIGKILLs every registered pid.
        proc = subprocess.Popen(["sleep", "30"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc.pid

    def test_stops_at_the_first_attempt_whose_fixture_ran(self):
        pid, seen = self._sleeper(), []

        def call(deadline):
            if deadline == 2:
                self.pidfile.write_text(f"{pid}\n")
            return deadline

        def check(outcome, _elapsed, deadline, started):
            seen.append((outcome, deadline, started))

        self.assertEqual(self._run_until_started(call, check, (1, 2, 4)), pid)
        self.assertEqual(seen, [(1, 1, False), (2, 2, True)])
        self.assertEqual(self.leftovers, [pid])

    def test_registers_the_pid_before_a_failing_check(self):
        pid = self._sleeper()

        def call(_deadline):
            self.pidfile.write_text(f"{pid}\n")

        def check(*_args):
            self.fail("boom")

        with self.assertRaises(AssertionError) as ctx:
            self._run_until_started(call, check, (1, 2))
        self.assertIn("attempt with a 1s deadline (fixture ran): boom", str(ctx.exception))
        self.assertEqual(self.leftovers, [pid])

    def test_registers_the_pid_before_an_unexpected_exception(self):
        pid = self._sleeper()

        def call(_deadline):
            self.pidfile.write_text(f"{pid}\n")
            raise RuntimeError("unexpected")

        with self.assertRaises(RuntimeError):
            self._run_until_started(call, lambda *_: None, (1, 2))
        self.assertEqual(self.leftovers, [pid])

    def test_fails_once_every_deadline_is_spent(self):
        tried = []
        with self.assertRaises(AssertionError) as ctx:
            self._run_until_started(tried.append, lambda *_: None, (1, 2, 4))
        self.assertEqual(tried, [1, 2, 4])
        self.assertIn("even with a 4s deadline", str(ctx.exception))

    def test_a_stale_pidfile_never_counts_as_a_start(self):
        self.pidfile.write_text("12345\n")
        with self.assertRaises(AssertionError):
            self._run_until_started(lambda _d: None, lambda *_: None, (1,))
        self.assertEqual(self.leftovers, [])


class TestSignalAfter(unittest.TestCase):
    """The per-attempt signal timer: nothing it sends may outlive its block."""

    def test_a_dispatched_signal_never_outlives_the_block(self):
        """A callback past its wait when the block exits: its signal surfaces
        inside the block's exit, never after it."""
        class Hangup(Exception):
            pass

        def on_hup(_signum, _frame):
            raise Hangup

        real_kill = signal.pthread_kill
        entered = threading.Event()

        def slow_kill(*args):
            entered.set()
            # Not a synchronisation: the block exits only after `entered`, and
            # from there a correct helper's exit waits for this send whatever
            # its timing. The pause only widens the window in which a
            # cancel-only helper would let the signal cross the exit.
            time.sleep(0.3)
            real_kill(*args)

        previous = signal.signal(signal.SIGHUP, on_hup)
        try:
            with patch.object(signal, "pthread_kill", slow_kill):
                with self.assertRaises(Hangup):
                    with _signal_after(0, signal.SIGHUP):
                        self.assertTrue(entered.wait(10), "the timer never fired")
            time.sleep(0.5)  # a signal that crossed the exit would raise here
        finally:
            signal.signal(signal.SIGHUP, previous)

    def test_a_block_that_ends_first_is_never_signalled(self):
        class Hangup(Exception):
            pass

        def on_hup(_signum, _frame):
            raise Hangup

        previous = signal.signal(signal.SIGHUP, on_hup)
        try:
            start = time.monotonic()
            # Far beyond any scheduling delay: the block always ends first. The
            # exit joins the timer, so nothing can fire once it returns.
            with _signal_after(60, signal.SIGHUP):
                pass
            self.assertLess(time.monotonic() - start, 10, "the exit waited out the delay")
        finally:
            signal.signal(signal.SIGHUP, previous)


if __name__ == "__main__":
    unittest.main()
