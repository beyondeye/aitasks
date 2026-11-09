"""The monitor status server restart procedure (t2246): ``status_restart.py``.

The procedure stops the server of one socket through its VERIFIED process
(``serve --socket <sock>`` in its args, re-read before the signal), with
SIGTERM, a bounded wait and no SIGKILL. These tests run REAL child processes
(``tests/lib/fake_status_server.py``) so the real ``ps`` identifies them, plus
fake ``ps`` / ``kill`` seams for the cases a real process cannot stage
(ambiguity, zombies, an unavailable ps).

Safety is asserted in the negative direction too: a socket no verifiable
process owns is never signalled, and this test process is never a target.

Run:
  python3 tests/test_monitor_status_restart.py
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MONITOR = REPO_ROOT / ".aitask-scripts" / "monitor"
sys.path.insert(0, str(MONITOR))

import status_paths as spaths  # noqa: E402
import status_restart as srst  # noqa: E402

FAKE = REPO_ROOT / "tests" / "lib" / "fake_status_server.py"
KEY = "0123456789abcdef"


def _short_tmp() -> str:
    for base in ("/tmp", None):
        try:
            return tempfile.mkdtemp(prefix="ait2246_", dir=base)
        except OSError:
            continue
    raise unittest.SkipTest("no writable temp directory")


class Case(unittest.TestCase):

    def setUp(self):
        if shutil.which("ps") is None:
            raise unittest.SkipTest("ps not installed")
        self.base = Path(_short_tmp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.procs: list = []
        self.addCleanup(self._reap)

    def _reap(self):
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            proc.stdout.close()

    def spawn(self, sock, mode="graceful", script=FAKE) -> subprocess.Popen:
        proc = subprocess.Popen(
            [sys.executable, str(script), "serve", "--socket", str(sock), "--mode", mode],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.procs.append(proc)
        self.assertEqual(proc.stdout.readline().strip(), "READY")
        return proc

    def sock(self, name="s.sock") -> Path:
        return self.base / name


class RecordingKill:
    def __init__(self, real=False):
        self.calls: list = []
        self.real = real

    def __call__(self, pid, sig):
        self.calls.append((pid, sig))
        if self.real:
            os.kill(pid, sig)

    def signals(self):
        return [c for c in self.calls if c[1] != 0]


class RetireTests(Case):

    def test_graceful_server_is_retired_and_gone(self):
        sock = self.sock()
        proc = self.spawn(sock)
        line = srst.retire_one(sock, wait=5.0)
        self.assertEqual(line, f"RETIRED:{sock}|pid={proc.pid}")
        self.assertEqual(proc.wait(timeout=5), 0)
        self.assertFalse(sock.exists(), "the server did not unlink its socket")

    def test_hung_server_is_reported_not_forced(self):
        sock = self.sock()
        proc = self.spawn(sock, mode="hung")
        start = time.monotonic()
        line = srst.retire_one(sock, wait=0.6)
        self.assertEqual(line, f"RETIRE_FAILED:{sock}|pid={proc.pid}|still_running")
        self.assertLess(time.monotonic() - start, 5.0, "the wait was not bounded")
        self.assertIsNone(proc.poll(), "a hung server must not be force-killed")

    def test_unverified_listener_is_never_signalled(self):
        sock = self.sock()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(sock))
        listener.listen(1)
        self.addCleanup(listener.close)
        kill = RecordingKill()
        line = srst.retire_one(sock, wait=0.5, kill=kill)
        self.assertEqual(line, f"RETIRE_FAILED:{sock}|unverified")
        self.assertEqual(kill.calls, [])
        # With an owner (the upgrade hook) it is not ours to report as a failure.
        self.assertEqual(srst.retire_one(sock, owner=str(FAKE), kill=kill),
                         f"SKIPPED:{sock}|unverified")
        self.assertEqual(kill.calls, [])

    def test_this_process_is_never_a_target(self):
        sock = self.sock()
        me = os.getpid()

        def ps(argv):
            if "-eo" in argv:
                return f"{me} python3 x.py serve --socket {sock}\n"
            return ""
        kill = RecordingKill()
        line = srst.retire_one(sock, ps=ps, kill=kill, connectable=lambda s: False)
        self.assertEqual(line, f"STALE:{sock}")
        self.assertEqual(kill.calls, [])

    def test_ambiguous_pids_signal_nothing(self):
        sock = self.sock()

        def ps(argv):
            return (f"4001 python3 a.py serve --socket {sock} --lock-fd 3\n"
                    f"4002 /bin/ait-monitord serve --socket {sock}\n")
        kill = RecordingKill()
        line = srst.retire_one(sock, ps=ps, kill=kill)
        self.assertEqual(line, f"RETIRE_FAILED:{sock}|ambiguous_pids:4001,4002")
        self.assertEqual(kill.calls, [])

    def test_owner_filter(self):
        sock = self.sock()
        proc = self.spawn(sock)
        other = self.base / "other" / "status_server.py"
        self.assertEqual(srst.retire_one(sock, owner=str(other)),
                         f"SKIPPED:{sock}|other_owner")
        self.assertIsNone(proc.poll(), "a server of another owner was stopped")
        self.assertEqual(srst.retire_one(sock, owner=str(FAKE), wait=5.0),
                         f"RETIRED:{sock}|pid={proc.pid}")

    def test_stale_socket_file(self):
        sock = self.sock()
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(sock))
        s.close()                          # bound, never listened: nobody answers
        kill = RecordingKill()
        self.assertEqual(srst.retire_one(sock, kill=kill), f"STALE:{sock}")
        self.assertEqual(kill.calls, [])

    def test_ps_unavailable_is_a_failure_not_an_all_clear(self):
        sock = self.sock()
        kill = RecordingKill()
        line = srst.retire_one(sock, ps=lambda argv: None, kill=kill)
        self.assertEqual(line, f"RETIRE_FAILED:{sock}|ps_unavailable")
        self.assertEqual(kill.calls, [])

    def test_args_changed_before_the_signal_sends_nothing(self):
        sock = self.sock()

        def ps(argv):
            if "-eo" in argv:
                return f"4100 python3 a.py serve --socket {sock}\n"
            return "something else entirely\n"          # recycled before the signal
        kill = RecordingKill()
        self.assertEqual(srst.retire_one(sock, ps=ps, kill=kill), f"STALE:{sock}")
        self.assertEqual(kill.signals(), [])


class _Completed:
    def __init__(self, returncode, stdout=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, ""


class InspectionFailureTests(unittest.TestCase):
    """A failed `ps` is UNKNOWN, never absence — exercised through the real
    `run_ps`, with only `subprocess.run` replaced."""
    SOCK = "/run/x/monitor-0123456789abcdef-0.40.1.sock"
    ARGS = f"python3 /t/status_server.py serve --socket {SOCK}"

    def fake_run(self, recheck_rc=0, after_signal_rc=2):
        state = {"signalled": False}

        def run(argv, **kw):
            if "-eo" in argv:
                return _Completed(0, f"4200 {self.ARGS}\n")
            if "args=" in argv:
                if state["signalled"]:
                    return _Completed(after_signal_rc, "")     # ps itself failed
                return _Completed(recheck_rc, self.ARGS + "\n" if recheck_rc == 0 else "")
            return _Completed(0, "")
        return run, state

    def test_run_ps_nonzero_exit_is_unknown(self):
        from unittest import mock
        with mock.patch.object(srst.subprocess, "run", return_value=_Completed(2, "")):
            self.assertIsNone(srst.run_ps(["ps", "-o", "args=", "-p", "1"]))
            # the process exists (kill(0) succeeds), so the failed read is not "gone"
            self.assertFalse(srst.pid_gone(4200, self.SOCK, kill=lambda p, s: None))

    def test_failed_inspection_after_the_signal_is_never_reported_retired(self):
        from unittest import mock
        run, state = self.fake_run()
        kill = RecordingKill()

        def recording_kill(pid, sig):
            kill(pid, sig)
            if sig == signal.SIGTERM:
                state["signalled"] = True
        with mock.patch.object(srst.subprocess, "run", side_effect=run):
            line = srst.retire_one(self.SOCK, wait=0.3, kill=recording_kill)
        self.assertEqual(line, f"RETIRE_FAILED:{self.SOCK}|pid=4200|still_running")


class OwnerRecheckTests(unittest.TestCase):
    """The pre-signal re-read keeps the owner scope: a pid that now belongs to
    another installation's server on the same socket receives nothing."""
    SOCK = "/run/x/monitor-0123456789abcdef-0.40.1.sock"

    def test_changed_owner_before_the_signal_sends_nothing(self):
        mine = "/a/.aitask-scripts/monitor/status_server.py"
        theirs = "/b/.aitask-scripts/monitor/status_server.py"

        def ps(argv):
            if "-eo" in argv:
                return f"4300 python3 {mine} serve --socket {self.SOCK}\n"
            return f"python3 {theirs} serve --socket {self.SOCK}\n"   # exec'd since
        kill = RecordingKill()
        line = srst.retire_one(self.SOCK, owner=mine, ps=ps, kill=kill)
        self.assertEqual(line, f"SKIPPED:{self.SOCK}|other_owner")
        self.assertEqual(kill.signals(), [])


class PidGoneTests(unittest.TestCase):
    SOCK = "/run/x/monitor-k-v.sock"

    def test_zombie_counts_as_gone(self):
        self.assertTrue(srst.pid_gone(
            7, self.SOCK, ps=lambda argv: "[python3] <defunct>\n", kill=lambda p, s: None))

    def test_still_matching_is_not_gone(self):
        self.assertFalse(srst.pid_gone(
            7, self.SOCK, ps=lambda argv: f"python3 a.py serve --socket {self.SOCK}\n",
            kill=lambda p, s: None))

    def test_unreadable_ps_is_not_gone(self):
        self.assertFalse(srst.pid_gone(7, self.SOCK, ps=lambda argv: None,
                                       kill=lambda p, s: None))

    def test_no_such_process_is_gone(self):
        def kill(pid, sig):
            raise ProcessLookupError
        self.assertTrue(srst.pid_gone(7, self.SOCK, ps=lambda argv: None, kill=kill))


class ArgsMatchTests(unittest.TestCase):
    S = "/run/aitasks/monitor-0123456789abcdef-0.40.1.sock"

    def test_whole_tokens(self):
        m = srst.args_match
        self.assertTrue(m(f"python3 /t/status_server.py serve --socket {self.S} --lock-fd 4", self.S))
        self.assertTrue(m(f"/bin/ait-monitord serve --socket {self.S}", self.S))
        self.assertFalse(m(f"python3 x serve --socket {self.S}0", self.S))
        self.assertFalse(m(f"python3 xserve --socket {self.S}", self.S))
        self.assertFalse(m(f"python3 x serve --lock-fd 4 --socket {self.S}", self.S),
                         "the contract is `serve --socket <sock>` adjacent")
        self.assertFalse(m(f"grep serve-socket {self.S}", self.S))

    def test_owner_is_the_token_before_serve(self):
        m = srst.args_match
        args = f"python3 /t/.aitask-scripts/monitor/status_server.py serve --socket {self.S}"
        self.assertTrue(m(args, self.S, owner="/t/.aitask-scripts/monitor/status_server.py"))
        self.assertFalse(m(args, self.S, owner="/.aitask-scripts/monitor/status_server.py"))
        self.assertFalse(m(args, self.S, owner="/u/.aitask-scripts/monitor/status_server.py"))
        self.assertTrue(m(f"/e/ait-monitord serve --socket {self.S}", self.S,
                          owner="/e/ait-monitord"))


class ListSocketsTests(unittest.TestCase):

    def test_version_and_key_are_exact(self):
        d = Path(_short_tmp())
        self.addCleanup(shutil.rmtree, d, True)
        other = "fedcba9876543210"
        hashed = spaths.version_slug("weird version!")
        for name in (f"monitor-{KEY}-0.40.1.sock", f"monitor-{KEY}-0.40.10.sock",
                     f"monitor-{other}-0.40.1.sock", f"monitor-{KEY}-{hashed}.sock",
                     f"monitor-{KEY}-0.40.1.lock", "monitor-short-0.40.1.sock", "junk"):
            (d / name).touch()
        names = lambda **kw: [e.path.name for e in spaths.list_server_sockets(d, **kw)]  # noqa: E731
        self.assertEqual(names(version="0.40.1"),
                         [f"monitor-{KEY}-0.40.1.sock", f"monitor-{other}-0.40.1.sock"])
        self.assertEqual(names(key=KEY, version="0.40.1"), [f"monitor-{KEY}-0.40.1.sock"])
        self.assertEqual(names(key=KEY, version="weird version!"), [f"monitor-{KEY}-{hashed}.sock"])
        self.assertEqual(len(names()), 4)
        self.assertEqual(spaths.list_server_sockets(d / "missing"), [])


class CliTests(Case):

    def run_cli(self, *argv) -> tuple[int, str]:
        buf = StringIO()
        with redirect_stdout(buf):
            try:
                rc = srst.main(list(argv))
            except SystemExit as exc:          # argparse errors
                rc = exc.code
        return rc, buf.getvalue()

    def test_scope_flags_are_mandatory(self):
        self.assertEqual(self.run_cli("retire", "--owner-path", str(FAKE))[0], 2)
        self.assertEqual(self.run_cli("retire", "--all-keys", "--owner-path", str(FAKE))[0], 2)
        self.assertEqual(self.run_cli("retire", "--all-keys", "--all-versions")[0], 2,
                         "--owner-path is required")

    def test_wait_must_be_finite(self):
        for bad in ("inf", "nan", "0", "-1"):
            self.assertEqual(self.run_cli("retire", "--all-keys", "--all-versions",
                                          "--owner-path", str(FAKE), "--wait", bad)[0], 2, bad)
        with self.assertRaises(ValueError):
            srst.retire_one(self.sock(), wait=float("inf"))

    def test_owner_scoped_retire_over_a_runtime_dir(self):
        run = self.base / "run"
        run.mkdir()
        mine = self.spawn(run / f"monitor-{KEY}-0.40.1.sock")
        theirs_script = self.base / "theirs" / "status_server.py"
        theirs_script.parent.mkdir()
        shutil.copy(FAKE, theirs_script)
        theirs = self.spawn(run / f"monitor-fedcba9876543210-0.40.1.sock", script=theirs_script)
        rc, out = self.run_cli("retire", "--all-keys", "--all-versions",
                               "--owner-path", str(FAKE), "--runtime-dir", str(run))
        self.assertEqual(rc, 0, out)
        self.assertIn(f"RETIRED:{run}/monitor-{KEY}-0.40.1.sock|pid={mine.pid}", out)
        self.assertIn("|other_owner", out)
        self.assertEqual(mine.wait(timeout=5), 0)
        self.assertIsNone(theirs.poll(), "a server started from another tree was stopped")

    def test_empty_runtime_dir(self):
        rc, out = self.run_cli("retire", "--all-keys", "--all-versions",
                               "--owner-path", str(FAKE), "--runtime-dir", str(self.base))
        self.assertEqual((rc, out.strip()), (0, "NO_SERVER"))


if __name__ == "__main__":
    unittest.main()
