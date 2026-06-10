"""Tests for the tmux command gateway (t952_1).

`tmux_exec.TmuxClient` is the single Python owner of raw ``tmux`` spawns. These
tests pin its three contracts: the socket-flag knob (``AITASKS_TMUX_SOCKET``,
cached once at construction), the mandatory ``=session`` target formatting, the
``(rc, stdout)`` / ``(-1, "")`` spawn contract, and the new-session persistence
ladder (systemd-run → setsid → plain). The live test runs under a private
``TMUX_TMPDIR`` + unique socket so it never touches the user's tmux server (the
Python analogue of ``tests/lib/tmux_isolation.sh``'s ``require_isolated_tmux``).
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"

sys.path.insert(0, str(LIB_DIR))
import tmux_exec  # noqa: E402
from tmux_exec import (  # noqa: E402
    TMUX_SOCKET_ENV,
    TmuxClient,
    session_target,
    tmux_socket_args,
    window_target,
)


class _FakeRunResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _clear_socket_env():
    """Context manager dropping AITASKS_TMUX_SOCKET from the environment."""
    env = patch.dict(os.environ, {}, clear=False)
    env.start()
    os.environ.pop(TMUX_SOCKET_ENV, None)
    return env


class TestSocketArgs(unittest.TestCase):
    def test_unset_is_empty(self):
        env = _clear_socket_env()
        try:
            self.assertEqual(tmux_socket_args(), [])
        finally:
            env.stop()

    def test_set_is_dash_L(self):
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: "aitsock"}, clear=False):
            self.assertEqual(tmux_socket_args(), ["-L", "aitsock"])

    def test_whitespace_is_empty(self):
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: "   "}, clear=False):
            self.assertEqual(tmux_socket_args(), [])

    def test_cached_at_construction(self):
        # The client must read the env ONCE at construction — the monitor
        # fallback is a hot path that must not re-read os.environ per call.
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: "frozen"}, clear=False):
            client = TmuxClient()
        # Mutate the env AFTER construction; the cached value must not change.
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: "changed"}, clear=False):
            self.assertEqual(client.socket_args, ["-L", "frozen"])

    def test_explicit_socket_args_override(self):
        client = TmuxClient(socket_args=["-S", "/tmp/x"])
        self.assertEqual(client.socket_args, ["-S", "/tmp/x"])


class TestTargetFormatting(unittest.TestCase):
    def test_session_target_exact_match(self):
        self.assertEqual(session_target("aitasks"), "=aitasks")

    def test_window_target(self):
        self.assertEqual(window_target("aitasks", "monitor"), "=aitasks:monitor")

    def test_window_target_trailing_colon_idiom(self):
        # ``new-window -t =sess:`` means "create in this session".
        self.assertEqual(window_target("aitasks", ""), "=aitasks:")

    def test_window_target_index(self):
        self.assertEqual(window_target("aitasks", 0), "=aitasks:0")

    def test_client_static_reexports(self):
        self.assertEqual(TmuxClient.session_target("s"), "=s")
        self.assertEqual(TmuxClient.window_target("s", "w"), "=s:w")


class TestRunContract(unittest.TestCase):
    def test_prepends_tmux_and_socket(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return _FakeRunResult(0, "out\n", "")

        client = TmuxClient(socket_args=["-L", "sock"])
        with patch.object(subprocess, "run", side_effect=fake_run):
            rc, out = client.run(["list-sessions", "-F", "#{session_name}"])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "out\n")
        self.assertEqual(
            captured["argv"],
            ["tmux", "-L", "sock", "list-sessions", "-F", "#{session_name}"],
        )

    def test_no_socket_when_unset(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return _FakeRunResult(0, "", "")

        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run", side_effect=fake_run):
            client.run(["kill-server"])
        self.assertEqual(captured["argv"], ["tmux", "kill-server"])

    def test_file_not_found_is_minus_one(self):
        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(client.run(["list-sessions"]), (-1, ""))

    def test_timeout_is_minus_one(self):
        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("tmux", 5)):
            self.assertEqual(client.run(["list-sessions"]), (-1, ""))

    def test_nonzero_returncode_passthrough(self):
        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run",
                          return_value=_FakeRunResult(1, "", "no server")):
            self.assertEqual(client.run(["list-sessions"]), (1, ""))


class TestRunAsyncContract(unittest.TestCase):
    def test_oserror_is_minus_one(self):
        client = TmuxClient(socket_args=[])
        with patch.object(asyncio, "create_subprocess_exec",
                          side_effect=OSError):
            rc, out = asyncio.run(client.run_async(["list-sessions"]))
        self.assertEqual((rc, out), (-1, ""))


class TestSpawn(unittest.TestCase):
    def test_argv_shape(self):
        captured = {}

        def fake_popen(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return object()

        client = TmuxClient(socket_args=["-L", "sock"])
        with patch.object(subprocess, "Popen", side_effect=fake_popen):
            client.spawn(["switch-client", "-t", "=sess"],
                         stderr=subprocess.DEVNULL)
        self.assertEqual(
            captured["argv"],
            ["tmux", "-L", "sock", "switch-client", "-t", "=sess"],
        )
        self.assertIn("stderr", captured["kwargs"])


class TestNewSessionArgv(unittest.TestCase):
    """new_session_argv: persistence ladder + socket injection (t956/t943)."""

    def _build(self, socket_args=None, **patches):
        defaults = {
            "server_running": False,        # genuine creation by default
            "systemd_available": False,
            "setsid": None,                 # shutil.which("setsid")
        }
        defaults.update(patches)

        def fake_which(name):
            if name == "setsid":
                return defaults["setsid"]
            return f"/usr/bin/{name}"

        def fake_run(argv, **kwargs):
            if argv[:1] == ["systemd-escape"]:
                return _FakeRunResult(0, "testsess\n", "")
            return _FakeRunResult(0, "", "")

        client = TmuxClient(socket_args=socket_args if socket_args is not None else [])
        with patch.object(TmuxClient, "_server_running",
                          return_value=defaults["server_running"]), \
             patch.object(tmux_exec, "_systemd_user_available",
                          return_value=defaults["systemd_available"]), \
             patch.object(tmux_exec.shutil, "which", side_effect=fake_which), \
             patch.object(subprocess, "run", side_effect=fake_run):
            return client.new_session_argv("testsess", "win", "echo hi")

    def test_server_running_is_plain_attach(self):
        argv = self._build(server_running=True)
        self.assertEqual(
            argv,
            ["tmux", "new-session", "-d", "-s", "testsess", "-n", "win", "echo hi"],
        )

    def test_no_server_with_systemd_wraps_in_session_slice(self):
        argv = self._build(systemd_available=True)
        self.assertEqual(argv[0], "systemd-run")
        self.assertIn("--slice=session.slice", argv)
        self.assertIn("--property=Type=forking", argv)
        self.assertIn("--property=KillMode=none", argv)
        self.assertIn("--collect", argv)
        tail = argv[argv.index("--") + 1:]
        self.assertEqual(tail[:3], ["tmux", "new-session", "-d"])
        self.assertIn("-c", tail)

    def test_no_server_no_systemd_with_setsid(self):
        argv = self._build(setsid="/usr/bin/setsid")
        self.assertEqual(argv[0], "setsid")
        self.assertEqual(argv[1:4], ["tmux", "new-session", "-d"])
        self.assertIn("-c", argv)

    def test_no_server_no_systemd_no_setsid_is_plain_with_cwd(self):
        argv = self._build()
        self.assertEqual(argv[:3], ["tmux", "new-session", "-d"])
        self.assertNotIn("systemd-run", argv)
        self.assertNotIn("setsid", argv)
        self.assertIn("-c", argv)

    def test_socket_flag_injected_after_tmux_on_attach(self):
        argv = self._build(socket_args=["-L", "sock"], server_running=True)
        self.assertEqual(argv[:3], ["tmux", "-L", "sock"])
        self.assertIn("new-session", argv)

    def test_socket_flag_injected_in_wrapped_creation(self):
        argv = self._build(socket_args=["-L", "sock"], setsid="/usr/bin/setsid")
        tail = argv[argv.index("setsid") + 1:]
        self.assertEqual(tail[:3], ["tmux", "-L", "sock"])


@unittest.skipIf(shutil.which("tmux") is None, "tmux not installed")
class TestGatewayIntegration(unittest.TestCase):
    """Live spawn through the gateway under a private socket + TMUX_TMPDIR.

    Fully isolated from the user's tmux server: a unique ``-L`` socket on a
    throwaway ``TMUX_TMPDIR`` (the Python analogue of ``require_isolated_tmux``).
    """

    SESSION = "_t952_1_gw_integration"
    SOCK = "ait_t952_1_test"

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="ait_t952_1_tmux_")
        # AIT_NO_SYSTEMD_RUN forces the setsid/plain rung of new_session_argv:
        # systemd-run --user spawns the server in a transient unit that does not
        # inherit this test's TMUX_TMPDIR, which would land the server on a
        # different socket than the isolated one we probe. setsid/plain inherit
        # the env, keeping the server on our private socket.
        self._env = patch.dict(
            os.environ,
            {"TMUX_TMPDIR": self._tmpdir, TMUX_SOCKET_ENV: self.SOCK,
             "AIT_NO_SYSTEMD_RUN": "1"},
            clear=False,
        )
        self._env.start()
        os.environ.pop("TMUX", None)  # not nested under the user's server
        self.client = TmuxClient()  # picks up the isolated socket

    def tearDown(self):
        self.client.run(["kill-server"])
        self._env.stop()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_spawn_and_list_through_gateway(self):
        # No server yet → empty list.
        rc, out = self.client.run(["list-sessions", "-F", "#{session_name}"])
        self.assertFalse([s for s in out.splitlines() if s])
        # Create a detached session via the gateway argv builder, on the
        # isolated socket.
        argv = self.client.new_session_argv(self.SESSION, "w0", "sleep 30")
        proc = subprocess.Popen(argv, stderr=subprocess.PIPE)
        _, stderr = proc.communicate()  # drain pipe (closes the reader)
        self.assertEqual(proc.returncode, 0, (stderr or b"").decode())
        # The isolated server now lists exactly our session.
        rc, out = self.client.run(["list-sessions", "-F", "#{session_name}"])
        self.assertEqual(rc, 0)
        self.assertIn(self.SESSION, out.splitlines())

    def test_socket_isolation_keeps_default_server_untouched(self):
        # Sanity: the gateway argv carries our test socket, so nothing here can
        # reach the user's default server.
        argv = self.client.new_session_argv(self.SESSION, "w0", "sleep 1")
        # The tmux token is followed by our -L socket in every rung.
        tmux_idx = argv.index("tmux")
        self.assertEqual(argv[tmux_idx + 1:tmux_idx + 3], ["-L", self.SOCK])


if __name__ == "__main__":
    unittest.main()
