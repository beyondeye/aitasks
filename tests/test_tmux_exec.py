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
SCRIPTS_DIR = REPO_ROOT / ".aitask-scripts"
LIB_DIR = SCRIPTS_DIR / "lib"

sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))  # for the `monitor` package import below
import tmux_exec  # noqa: E402
from tmux_exec import (  # noqa: E402
    TMUX_SOCKET_ENV,
    TmuxClient,
    session_scope_target,
    session_target,
    tmux_socket_args,
    window_target,
)
from monitor.monitor_core import TmuxMonitor  # noqa: E402
from monitor.tmux_control import TmuxControlClient  # noqa: E402


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


def _short_socket_tmpdir(prefix: str) -> str:
    """A TMUX_TMPDIR short enough for AF_UNIX's ~104-byte ``sun_path`` limit.

    tmux appends ``tmux-<uid>/<socket>`` to TMUX_TMPDIR, and on macOS $TMPDIR is
    ``/private/var/folders/<hash>/<hash>/T/`` — ~53 bytes before this fixture
    adds anything, which pushes the socket path to 106 and makes every connect
    fail with "File name too long" (t1729). ``/tmp`` is short and present on
    every platform this suite runs on; fall back to the platform default if it
    somehow is not.
    """
    base = "/tmp" if os.path.isdir("/tmp") else None
    return tempfile.mkdtemp(prefix=prefix, dir=base)


class TestSocketArgs(unittest.TestCase):
    def test_unset_is_dedicated_default(self):
        # Unset env → the dedicated ait socket (t953).
        env = _clear_socket_env()
        try:
            self.assertEqual(tmux_socket_args(), ["-L", "ait"])
        finally:
            env.stop()

    def test_set_is_dash_L(self):
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: "aitsock"}, clear=False):
            self.assertEqual(tmux_socket_args(), ["-L", "aitsock"])

    def test_empty_string_is_no_flag(self):
        # Set-but-empty is the legacy escape hatch (no flag → tmux follows
        # $TMUX). Load-bearing for tests/lib/tmux_isolation.sh's pin.
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: ""}, clear=False):
            self.assertEqual(tmux_socket_args(), [])

    def test_whitespace_is_no_flag(self):
        # Whitespace-only collapses to the same escape hatch as empty.
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: "   "}, clear=False):
            self.assertEqual(tmux_socket_args(), [])

    def test_default_value_is_default_socket(self):
        # The explicit opt-out spelling: tmux's default socket is literally
        # named "default", so `-L default` targets the user's default server.
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: "default"}, clear=False):
            self.assertEqual(tmux_socket_args(), ["-L", "default"])

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

    def test_session_scope_target_trailing_colon(self):
        # A window-typed ``-t`` (``list-panes -s``) needs the colon, or a
        # window named after the session can capture the lookup (t1874).
        self.assertEqual(session_scope_target("aitasks"), "=aitasks:")

    def test_window_target(self):
        self.assertEqual(window_target("aitasks", "monitor"), "=aitasks:monitor")

    def test_window_target_trailing_colon_idiom(self):
        # ``new-window -t =sess:`` means "create in this session".
        self.assertEqual(window_target("aitasks", ""), "=aitasks:")

    def test_window_target_index(self):
        self.assertEqual(window_target("aitasks", 0), "=aitasks:0")

    def test_client_static_reexports(self):
        self.assertEqual(TmuxClient.session_target("s"), "=s")
        self.assertEqual(TmuxClient.session_scope_target("s"), "=s:")
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

    def test_no_socket_when_empty(self):
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


class TestRunChecked(unittest.TestCase):
    """`run_checked` keeps stderr and classifies — the status-bearing sibling
    of `run` (t1869). "No server" must never be confused with "could not look".
    """

    def _with(self, **kw):
        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run", **kw):
            return client.run_checked(["list-sessions"])

    def test_ok(self):
        r = self._with(return_value=_FakeRunResult(0, "a\nb\n", ""))
        self.assertEqual((r.outcome, r.rc, r.stdout), ("ok", 0, "a\nb\n"))

    def test_no_tmux_binary(self):
        self.assertEqual(self._with(side_effect=FileNotFoundError).outcome,
                         "no_tmux")

    def test_timeout_is_failed_not_empty(self):
        r = self._with(side_effect=subprocess.TimeoutExpired("tmux", 5))
        self.assertEqual(r.outcome, "failed")

    def test_oserror_is_failed(self):
        self.assertEqual(self._with(side_effect=OSError).outcome, "failed")

    def test_missing_socket_is_no_server(self):
        r = self._with(return_value=_FakeRunResult(
            1, "", "error connecting to /tmp/tmux-1000/x (No such file or directory)\n"))
        self.assertEqual(r.outcome, "no_server")

    def test_dead_socket_is_no_server(self):
        r = self._with(return_value=_FakeRunResult(
            1, "", "no server running on /tmp/tmux-1000/x\n"))
        self.assertEqual(r.outcome, "no_server")

    def test_connection_refused_is_failed(self):
        # Not in the measured table: an unknown refusal must fail closed.
        r = self._with(return_value=_FakeRunResult(
            1, "", "error connecting to /tmp/tmux-1000/x (Connection refused)\n"))
        self.assertEqual(r.outcome, "failed")

    def test_other_nonzero_is_failed_and_keeps_stderr(self):
        r = self._with(return_value=_FakeRunResult(1, "", "unknown variable: X\n"))
        self.assertEqual((r.outcome, r.stderr), ("failed", "unknown variable: X\n"))
        self.assertTrue(tmux_exec.tmux_stderr_is("unknown_variable", r.stderr))

    def test_run_contract_unchanged(self):
        # The additive sibling must not have altered `run`'s own contract.
        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run",
                          return_value=_FakeRunResult(1, "", "no server running on x")):
            self.assertEqual(client.run(["list-sessions"]), (1, ""))

    def test_stderr_table(self):
        is_ = tmux_exec.tmux_stderr_is
        self.assertTrue(is_("no_such_session", "can't find session: gone\n"))
        self.assertTrue(is_("no_such_session", "can't find window: gone\n"))
        self.assertFalse(is_("no_such_session", "unknown variable: X"))
        self.assertFalse(is_("no_server", ""))

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_live_messages_match_table(self):
        # Pin the table against the INSTALLED tmux, not against a transcription:
        # if a tmux release rewords a message, this fails instead of the
        # resolver silently treating "no server" as a failure (or vice versa).
        tmpdir = _short_socket_tmpdir("ait_rc_")
        env = patch.dict(os.environ, {"TMUX_TMPDIR": tmpdir})
        env.start()
        try:
            client = TmuxClient(socket_args=["-L", f"ait_rc_{os.getpid()}"])
            self.assertEqual(client.run_checked(["list-sessions"]).outcome,
                             "no_server")
            rc, _ = client.run(["new-session", "-d", "-s", "rc1", "sleep 30"])
            self.assertEqual(rc, 0)
            try:
                r = client.run_checked(["list-panes", "-s", "-t",
                                        session_target("gone"), "-F", "x"])
                self.assertTrue(tmux_exec.tmux_stderr_is("no_such_session", r.stderr),
                                r.stderr)
                r = client.run_checked(["show-environment", "-g",
                                        "AITASKS_PROJECT_nope_zz"])
                self.assertTrue(tmux_exec.tmux_stderr_is("unknown_variable", r.stderr),
                                r.stderr)
            finally:
                client.run(["kill-server"])
        finally:
            env.stop()
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSetClipboard(unittest.TestCase):
    def test_argv_and_stdin(self):
        # `load-buffer -w -` with the text on stdin: sets a tmux buffer AND
        # forwards to attached clients via OSC 52 — the only path that reaches
        # the system clipboard from a non-visible pane.
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["input"] = kwargs.get("input")
            return _FakeRunResult(0, "", "")

        client = TmuxClient(socket_args=["-L", "sock"])
        with patch.object(subprocess, "run", side_effect=fake_run):
            ok = client.set_clipboard("payload text")
        self.assertTrue(ok)
        self.assertEqual(
            captured["argv"], ["tmux", "-L", "sock", "load-buffer", "-w", "-"]
        )
        self.assertEqual(captured["input"], "payload text")

    def test_nonzero_returncode_is_false(self):
        # e.g. tmux < 3.2 rejecting `-w`, or no server.
        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run",
                          return_value=_FakeRunResult(1, "", "unknown flag")):
            self.assertFalse(client.set_clipboard("x"))

    def test_file_not_found_is_false(self):
        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run", side_effect=FileNotFoundError):
            self.assertFalse(client.set_clipboard("x"))

    def test_timeout_is_false(self):
        client = TmuxClient(socket_args=[])
        with patch.object(subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("tmux", 5)):
            self.assertFalse(client.set_clipboard("x"))


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


class _FakeBackend:
    """Duck-typed control-mode backend for dispatcher tests (no real tmux)."""

    def __init__(self, alive: bool, sync_result=None, async_result=None):
        self.is_alive = alive
        self._sync_result = sync_result
        self._async_result = async_result
        self.sync_calls: list[list[str]] = []
        self.async_calls: list[list[str]] = []

    def request_sync(self, args, timeout=None):
        self.sync_calls.append(args)
        return self._sync_result

    async def request_async(self, args, timeout=None):
        self.async_calls.append(args)
        return self._async_result


class TestRunViaControl(unittest.TestCase):
    """The control-mode exec dispatcher (t952_3): control-client when alive,
    subprocess fallback on rc == -1. Behavior-preserving port of the former
    TmuxMonitor.tmux_run / _tmux_async dispatch."""

    def test_none_backend_uses_subprocess(self):
        client = TmuxClient(socket_args=[])
        with patch.object(client, "run", return_value=(0, "viasub")) as m:
            rc, out = client.run_via_control(None, ["list-sessions"])
        self.assertEqual((rc, out), (0, "viasub"))
        m.assert_called_once()

    def test_dead_backend_uses_subprocess(self):
        client = TmuxClient(socket_args=[])
        backend = _FakeBackend(alive=False)
        with patch.object(client, "run", return_value=(0, "viasub")) as m:
            rc, out = client.run_via_control(backend, ["list-sessions"])
        self.assertEqual((rc, out), (0, "viasub"))
        self.assertEqual(backend.sync_calls, [])  # backend never consulted
        m.assert_called_once()

    def test_alive_backend_short_circuits(self):
        client = TmuxClient(socket_args=[])
        backend = _FakeBackend(alive=True, sync_result=(0, "fromctrl"))
        with patch.object(client, "run") as m:
            rc, out = client.run_via_control(backend, ["display-message"])
        self.assertEqual((rc, out), (0, "fromctrl"))
        self.assertEqual(backend.sync_calls, [["display-message"]])
        m.assert_not_called()  # subprocess fallback NOT taken on success

    def test_transport_failure_falls_back(self):
        client = TmuxClient(socket_args=[])
        backend = _FakeBackend(alive=True, sync_result=(-1, ""))
        with patch.object(client, "run", return_value=(0, "fallback")) as m:
            rc, out = client.run_via_control(backend, ["display-message"])
        # rc == -1 from the backend → fall through to subprocess.
        self.assertEqual((rc, out), (0, "fallback"))
        m.assert_called_once()

    def test_tmux_error_rc1_does_not_fall_back(self):
        # rc == 1 is a real tmux command error (not transport) — return it,
        # do NOT retry via subprocess.
        client = TmuxClient(socket_args=[])
        backend = _FakeBackend(alive=True, sync_result=(1, "err-body"))
        with patch.object(client, "run") as m:
            rc, out = client.run_via_control(backend, ["has-session"])
        self.assertEqual((rc, out), (1, "err-body"))
        m.assert_not_called()

    def test_async_alive_short_circuits(self):
        async def go():
            client = TmuxClient(socket_args=[])
            backend = _FakeBackend(alive=True, async_result=(0, "actrl"))
            with patch.object(client, "run_async") as m:
                rc, out = await client.run_async_via_control(backend, ["x"])
            m.assert_not_called()
            return rc, out
        self.assertEqual(asyncio.run(go()), (0, "actrl"))

    def test_async_transport_failure_falls_back(self):
        async def go():
            client = TmuxClient(socket_args=[])
            backend = _FakeBackend(alive=True, async_result=(-1, ""))

            async def fake_run_async(args, timeout=5.0):
                return (0, "afallback")
            with patch.object(client, "run_async", side_effect=fake_run_async):
                return await client.run_async_via_control(backend, ["x"])
        self.assertEqual(asyncio.run(go()), (0, "afallback"))


class TestResizePane(unittest.TestCase):
    """resize_pane: arg construction + optional control-mode dispatch."""

    def test_x_only_argv(self):
        client = TmuxClient(socket_args=["-L", "sock"])
        with patch.object(client, "run", return_value=(0, "")) as m:
            client.resize_pane("%3", x=40)
        m.assert_called_once_with(["resize-pane", "-t", "%3", "-x", "40"], timeout=tmux_exec._DEFAULT_TIMEOUT)

    def test_x_and_y_argv(self):
        client = TmuxClient(socket_args=[])
        with patch.object(client, "run", return_value=(0, "")) as m:
            client.resize_pane("%5", x=40, y=20)
        m.assert_called_once_with(["resize-pane", "-t", "%5", "-x", "40", "-y", "20"], timeout=tmux_exec._DEFAULT_TIMEOUT)

    def test_no_dimensions_is_bare_target(self):
        client = TmuxClient(socket_args=[])
        with patch.object(client, "run", return_value=(0, "")) as m:
            client.resize_pane("%1")
        m.assert_called_once_with(["resize-pane", "-t", "%1"], timeout=tmux_exec._DEFAULT_TIMEOUT)

    def test_backend_dispatches_via_control(self):
        # Direct gateway callers can still opt into control-mode dispatch.
        client = TmuxClient(socket_args=[])
        backend = _FakeBackend(alive=True, sync_result=(0, ""))
        with patch.object(client, "run") as m:
            rc, _ = client.resize_pane("%2", x=40, backend=backend)
        self.assertEqual(rc, 0)
        self.assertEqual(backend.sync_calls, [["resize-pane", "-t", "%2", "-x", "40"]])
        m.assert_not_called()


class TestMonitorResizePane(unittest.TestCase):
    """TmuxMonitor resize uses subprocess to avoid tmux growth reflow races."""

    def test_monitor_resize_does_not_forward_control_backend(self):
        monitor = TmuxMonitor(session="s")
        monitor._backend = _FakeBackend(alive=True, sync_result=(0, "ctrl"))

        with patch.object(monitor._tmux, "resize_pane", return_value=(0, "")) as m:
            rc, out = monitor.resize_pane("%2", x=40, timeout=2.0)

        self.assertEqual((rc, out), (0, ""))
        m.assert_called_once_with("%2", x=40, y=None, timeout=2.0)
        self.assertEqual(monitor._backend.sync_calls, [])


class TestControlAttachArgv(unittest.TestCase):
    """The `tmux -C attach` argv threads the socket flag (t952_3)."""

    def test_socket_flag_in_attach_argv(self):
        c = TmuxControlClient(session="mysess", socket_args=["-L", "sock"])
        self.assertEqual(
            c._attach_argv(),
            ["tmux", "-L", "sock", "-C", "attach", "-t", "mysess",
             "-f", "no-output,ignore-size"],
        )

    def test_no_socket_flag_when_empty(self):
        c = TmuxControlClient(session="mysess", socket_args=[])
        self.assertEqual(
            c._attach_argv(),
            ["tmux", "-C", "attach", "-t", "mysess",
             "-f", "no-output,ignore-size"],
        )

    def test_socket_args_default_from_env(self):
        with patch.dict(os.environ, {TMUX_SOCKET_ENV: "envsock"}, clear=False):
            c = TmuxControlClient(session="s")
        self.assertEqual(c._attach_argv()[:3], ["tmux", "-L", "envsock"])


@unittest.skipIf(shutil.which("tmux") is None, "tmux not installed")
class TestGatewayIntegration(unittest.TestCase):
    """Live spawn through the gateway under a private socket + TMUX_TMPDIR.

    Fully isolated from the user's tmux server: a unique ``-L`` socket on a
    throwaway ``TMUX_TMPDIR`` (the Python analogue of ``require_isolated_tmux``).
    """

    SESSION = "_t952_1_gw_integration"
    SOCK = "ait_t952_1_test"

    def setUp(self):
        self._tmpdir = _short_socket_tmpdir("ait_t952_1_tmux_")
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


# --- Pane PATH (policy 4, t1689) ------------------------------------------

_H = "/h"
_SHIMS = "/h/.local/share/mise/shims"
_LOCAL = "/h/.local/bin"
_FW = "/h/.aitask/bin"
# The hazardous spawner order and what the gateway must turn it into.
_BAD_PATH = f"{_LOCAL}:{_SHIMS}:/usr/bin"
_GOOD_PATH = f"{_SHIMS}:{_LOCAL}:/usr/bin"

_CW = "/h/.local/share/mise/command-wrappers/bin"
_INST = "/h/.local/share/mise/installs"
_OMARCHY = "/usr/share/omarchy/bin"
_OPENCODE = "/h/.opencode/bin"

# (label, path, environ, expected). Every case runs through BOTH the Python
# function and the shell mirror (TestShellParity), so the table is the contract.
_NORMALIZE_CASES = [
    ("no mise entry is unchanged, even with ~/.local/bin first",
     f"{_LOCAL}:/usr/bin", {"HOME": _H}, f"{_LOCAL}:/usr/bin"),
    ("no mise entry: ~/.local/bin last is unchanged",
     f"/usr/bin:{_LOCAL}", {"HOME": _H}, f"/usr/bin:{_LOCAL}"),
    ("no mise entry: repeated ~/.local/bin is unchanged",
     f"{_LOCAL}:/usr/bin:{_LOCAL}", {"HOME": _H}, f"{_LOCAL}:/usr/bin:{_LOCAL}"),
    ("empty path is unchanged", "", {"HOME": _H}, ""),
    ("~/.local/bin moves behind the shims (the t1689 order)",
     _BAD_PATH, {"HOME": _H}, _GOOD_PATH),
    ("only ~/.local/bin moves (the t2143 bad env)",
     f"{_LOCAL}:{_OMARCHY}:{_SHIMS}:/usr/bin", {"HOME": _H},
     f"{_OMARCHY}:{_SHIMS}:{_LOCAL}:/usr/bin"),
    ("~/.local/bin goes behind the LAST mise entry",
     f"{_FW}:{_LOCAL}:{_OMARCHY}:{_SHIMS}:{_INST}/node/20/bin:/usr/bin",
     {"HOME": _H},
     f"{_FW}:{_OMARCHY}:{_SHIMS}:{_INST}/node/20/bin:{_LOCAL}:/usr/bin"),
    ("a fresh mise-activated shell is unchanged (t2144)",
     f"{_OPENCODE}:/h/flutter/bin:{_CW}:{_SHIMS}:{_CW}:{_FW}"
     f":{_INST}/java/21/bin:{_INST}/opencode/latest/node_modules/.bin"
     f":{_OPENCODE}:{_OMARCHY}:/usr/bin:{_LOCAL}:/usr/bin/core_perl",
     {"HOME": _H},
     f"{_OPENCODE}:/h/flutter/bin:{_CW}:{_SHIMS}:{_CW}:{_FW}"
     f":{_INST}/java/21/bin:{_INST}/opencode/latest/node_modules/.bin"
     f":{_OPENCODE}:{_OMARCHY}:/usr/bin:{_LOCAL}:/usr/bin/core_perl"),
    ("the t2143-finding activated order is unchanged",
     f"{_CW}:{_FW}:{_OPENCODE}:/h/flutter/bin:{_INST}/java/21/bin"
     f":/usr/bin:{_LOCAL}", {"HOME": _H},
     f"{_CW}:{_FW}:{_OPENCODE}:/h/flutter/bin:{_INST}/java/21/bin"
     f":/usr/bin:{_LOCAL}"),
    ("command-wrappers counts as a mise entry",
     f"{_LOCAL}:{_CW}:/usr/bin", {"HOME": _H}, f"{_CW}:{_LOCAL}:/usr/bin"),
    ("~/.local/bin between mise entries moves past the last one",
     f"{_CW}:{_LOCAL}:{_SHIMS}:/usr/bin", {"HOME": _H},
     f"{_CW}:{_SHIMS}:{_LOCAL}:/usr/bin"),
    ("other dirs ahead of mise keep their place",
     f"/usr/bin:{_FW}:{_SHIMS}", {"HOME": _H}, f"/usr/bin:{_FW}:{_SHIMS}"),
    ("duplicates move in order; one already behind stays",
     f"{_LOCAL}:{_SHIMS}:{_LOCAL}/", {"HOME": _H},
     f"{_SHIMS}:{_LOCAL}:{_LOCAL}/"),
    ("empty entries survive",
     f"{_LOCAL}::{_SHIMS}:", {"HOME": _H}, f":{_SHIMS}:{_LOCAL}:"),
    ("trailing slashes compare equal but are kept verbatim",
     f"{_LOCAL}/:{_SHIMS}/", {"HOME": _H}, f"{_SHIMS}/:{_LOCAL}/"),
    ("MISE_DATA_DIR replaces the default data dir",
     f"{_LOCAL}:/m/shims:{_SHIMS}", {"HOME": _H, "MISE_DATA_DIR": "/m/"},
     f"/m/shims:{_LOCAL}:{_SHIMS}"),
    ("XDG_DATA_HOME relocates the data dir",
     f"{_LOCAL}:/x/mise/shims", {"HOME": _H, "XDG_DATA_HOME": "/x"},
     f"/x/mise/shims:{_LOCAL}"),
    ("a sibling dir sharing the name prefix is not mise",
     f"{_LOCAL}:/h/.local/share/mise-old/bin", {"HOME": _H},
     f"{_LOCAL}:/h/.local/share/mise-old/bin"),
    ("an all-slash MISE_DATA_DIR is unchanged",
     f"{_LOCAL}:{_SHIMS}", {"HOME": _H, "MISE_DATA_DIR": "/"},
     f"{_LOCAL}:{_SHIMS}"),
    ("no HOME and no data dir override is unchanged",
     f"{_LOCAL}:{_SHIMS}", {}, f"{_LOCAL}:{_SHIMS}"),
    ("no HOME with MISE_DATA_DIR is unchanged (no hazard dir)",
     f"{_LOCAL}:/m/shims", {"MISE_DATA_DIR": "/m"}, f"{_LOCAL}:/m/shims"),
    ("overlapping roles: ~/.local/bin as the last mise entry is kept",
     f"{_LOCAL}:/h/.local/shims:{_LOCAL}/", {"HOME": _H,
                                             "MISE_DATA_DIR": "/h/.local"},
     f"/h/.local/shims:{_LOCAL}:{_LOCAL}/"),
]

_SPAWN_PATH_ENV_KEYS = ("HOME", "PATH", "MISE_DATA_DIR", "XDG_DATA_HOME",
                        "AITASKS_HOME")


def _spawn_path_env(path: str | None, home: str = _H):
    """Patch os.environ to exactly HOME/PATH for the normalizer's inputs."""
    env = patch.dict(os.environ, {}, clear=False)
    env.start()
    for key in _SPAWN_PATH_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["HOME"] = home
    if path is not None:
        os.environ["PATH"] = path
    return env


class TestNormalizeSpawnPath(unittest.TestCase):
    def test_table(self):
        for label, path, environ, expected in _NORMALIZE_CASES:
            with self.subTest(label):
                self.assertEqual(
                    tmux_exec.normalize_spawn_path(path, environ), expected)

    def test_idempotent(self):
        for label, path, environ, _ in _NORMALIZE_CASES:
            with self.subTest(label):
                once = tmux_exec.normalize_spawn_path(path, environ)
                self.assertEqual(
                    tmux_exec.normalize_spawn_path(once, environ), once)

    def test_preserves_entries(self):
        """Only a reorder: no entry dropped or duplicated."""
        for label, path, environ, _ in _NORMALIZE_CASES:
            with self.subTest(label):
                out = tmux_exec.normalize_spawn_path(path, environ)
                self.assertEqual(sorted(out.split(":")),
                                 sorted(path.split(":")))

    def test_reads_os_environ_by_default(self):
        env = _spawn_path_env(_BAD_PATH)
        try:
            self.assertEqual(tmux_exec.normalize_spawn_path(_BAD_PATH),
                             _GOOD_PATH)
        finally:
            env.stop()

    def test_creates_pane(self):
        for args in (["new-window", "-d"], ["split-window"],
                     ["new-session", "-d"], ["respawn-pane", "-k"],
                     ["respawn-window"],
                     ["display-message", ";", "split-window", "-h"]):
            with self.subTest(args):
                self.assertTrue(tmux_exec.creates_pane(args))
        for args in (["list-panes", "-a"], ["display-message", "-p"],
                     ["kill-pane", "-t", "%1"], []):
            with self.subTest(args):
                self.assertFalse(tmux_exec.creates_pane(args))


class TestShellParity(unittest.TestCase):
    """lib/spawn_path.sh must answer the table exactly like the Python rule."""

    BASH = shutil.which("bash")

    def _shell(self, path: str, environ: dict) -> str:
        script = ('source "$0"; ait_spawn_path_normalize "$1"; '
                  'printf %s "$AIT_SPAWN_PATH"')
        result = subprocess.run(
            [self.BASH, "-c", script, str(LIB_DIR / "spawn_path.sh"), path],
            capture_output=True, text=True, env=dict(environ), timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    @unittest.skipIf(shutil.which("bash") is None, "bash not installed")
    def test_table(self):
        for label, path, environ, expected in _NORMALIZE_CASES:
            with self.subTest(label):
                self.assertEqual(self._shell(path, environ), expected)
                self.assertEqual(self._shell(path, environ),
                                 tmux_exec.normalize_spawn_path(path, environ))

    @unittest.skipIf(shutil.which("bash") is None, "bash not installed")
    def test_idempotent_and_preserves_entries(self):
        for label, path, environ, _ in _NORMALIZE_CASES:
            with self.subTest(label):
                once = self._shell(path, environ)
                self.assertEqual(self._shell(once, environ), once)
                self.assertEqual(sorted(once.split(":")),
                                 sorted(path.split(":")))

    @unittest.skipIf(shutil.which("bash") is None, "bash not installed")
    def test_defaults_to_path(self):
        script = ('source "$0"; ait_spawn_path_normalize; '
                  'printf %s "$AIT_SPAWN_PATH"')
        result = subprocess.run(
            [self.BASH, "-c", script, str(LIB_DIR / "spawn_path.sh")],
            capture_output=True, text=True, timeout=10,
            env={"HOME": _H,
                 "PATH": f"{os.path.dirname(self.BASH)}:{_LOCAL}:{_SHIMS}"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout,
                         f"{os.path.dirname(self.BASH)}:{_SHIMS}:{_LOCAL}")


class TestResolveSpawnExe(unittest.TestCase):
    """Reordering PATH for the pane must never change which launcher runs.

    Fixture on a real filesystem: a working ``tmux`` in ``~/.local/bin`` (the
    one dir normalization moves) and a decoy in mise's shims dir, with the
    caller's PATH resolving the working one first.
    """

    BASH = shutil.which("bash")

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="ait_spawnexe_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = os.path.join(self.root, "h")
        self.shims = os.path.join(self.home, ".local/share/mise/shims")
        self.sys = os.path.join(self.home, ".local/bin")
        self.only = os.path.join(self.root, "only")
        for d in (self.shims, self.sys, self.only):
            os.makedirs(d)
        for d, name in ((self.sys, "tmux"), (self.shims, "tmux"),
                        (self.only, "solo")):
            p = os.path.join(d, name)
            with open(p, "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(p, 0o755)
        self.environ = {"HOME": self.home}
        self.orig = f"{self.sys}:{self.shims}:/usr/bin"

    def _cases(self):
        spawn = tmux_exec.normalize_spawn_path(self.orig, self.environ)
        return [
            # (label, name, original_path, spawn_path, expected)
            ("decoy ahead after reorder -> caller's absolute path",
             "tmux", self.orig, spawn, f"{self.sys}/tmux"),
            ("same file either way -> bare name",
             "solo", f"{self.only}:{self.shims}", f"{self.shims}:{self.only}",
             "solo"),
            ("unchanged PATH -> bare name", "tmux", self.orig, self.orig, "tmux"),
            ("caller resolves nothing -> bare name (fails as before)",
             "nothere", self.orig, spawn, "nothere"),
            ("empty entry means the current dir",
             "tmux", f":{self.shims}", f"{self.shims}:", "./tmux"),
        ]

    def test_table(self):
        self.assertEqual(tmux_exec.normalize_spawn_path(self.orig, self.environ),
                         f"{self.shims}:{self.sys}:/usr/bin")
        cwd = os.getcwd()
        os.chdir(self.sys)  # for the empty-entry case
        self.addCleanup(os.chdir, cwd)
        for label, name, orig, spawn, expected in self._cases():
            with self.subTest(label):
                self.assertEqual(
                    tmux_exec.resolve_spawn_exe(name, orig, spawn), expected)

    @unittest.skipIf(shutil.which("bash") is None, "bash not installed")
    def test_shell_parity(self):
        script = ('source "$0"; ait_spawn_exe "$1" "$2" "$3"; '
                  'printf %s "$AIT_SPAWN_EXE"')
        for label, name, orig, spawn, expected in self._cases():
            with self.subTest(label):
                result = subprocess.run(
                    [self.BASH, "-c", script, str(LIB_DIR / "spawn_path.sh"),
                     name, orig, spawn],
                    capture_output=True, text=True, timeout=10, cwd=self.sys,
                    env={"HOME": self.home},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def _captured_argv(self, method, *args):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["env"] = kwargs.get("env")
            return _FakeRunResult(0, "", "")

        def fake_popen(argv, **kwargs):
            captured["argv"] = argv
            captured["env"] = kwargs.get("env")
            return object()

        env = _spawn_path_env(self.orig, home=self.home)
        try:
            with patch.object(subprocess, "run", side_effect=fake_run), \
                 patch.object(subprocess, "Popen", side_effect=fake_popen):
                getattr(TmuxClient(socket_args=[]), method)(*args)
        finally:
            env.stop()
        return captured

    def test_gateway_runs_the_callers_tmux_under_the_pane_path(self):
        for method, args in (("run", (["new-window"],)),
                             ("run_checked", (["new-window"],)),
                             ("set_clipboard", ("text",)),
                             ("spawn", (["new-window"],))):
            with self.subTest(method):
                got = self._captured_argv(method, *args)
                self.assertEqual(got["argv"][0], f"{self.sys}/tmux")
                self.assertEqual(got["env"]["PATH"],
                                 f"{self.shims}:{self.sys}:/usr/bin")

    def test_new_session_argv_spells_every_launcher(self):
        env = _spawn_path_env(self.orig, home=self.home)
        try:
            with patch.object(TmuxClient, "_server_running", return_value=False), \
                 patch.object(tmux_exec, "_systemd_user_available",
                              return_value=False), \
                 patch.object(tmux_exec.shutil, "which",
                              side_effect=lambda n: f"/usr/bin/{n}"):
                argv = TmuxClient(socket_args=[]).new_session_argv(
                    "s", "w", "cmd", cwd="/")
        finally:
            env.stop()
        # setsid is not in the fixture, so the caller resolves none -> bare.
        self.assertEqual(argv[0], "setsid")
        self.assertEqual(argv[1], f"{self.sys}/tmux")

    def test_symlink_dotdot_cwd_keeps_the_kernels_meaning(self):
        # parent/link -> elsewhere/nested, so chdir("link/..") enters
        # `elsewhere`, while a lexical abspath/normpath would collapse it to
        # `parent`. The working tmux lives in elsewhere/bin; parent has no bin.
        parent = os.path.join(self.root, "parent")
        elsewhere = os.path.join(self.root, "elsewhere")
        os.makedirs(parent)
        os.makedirs(os.path.join(elsewhere, "nested"))
        os.makedirs(os.path.join(elsewhere, "bin"))
        os.symlink(os.path.join(elsewhere, "nested"), os.path.join(parent, "link"))
        working = os.path.join(elsewhere, "bin", "tmux")
        with open(working, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(working, 0o755)
        with open(os.path.join(self.shims, "tmux"), "w") as f:
            f.write("#!/bin/sh\nexit 23\n")
        orig = f"bin:{self.shims}:/usr/bin:/bin"
        # Given, not normalized — see test_relative_entry_resolves_from_the_childs_cwd.
        spawn = f"{self.shims}:bin:/usr/bin:/bin"
        # The gateway leg uses a PATH normalization really reorders.
        gw_orig = f"{self.sys}:bin:{self.shims}:/usr/bin:/bin"
        os.remove(os.path.join(self.sys, "tmux"))  # keep `bin` the resolver

        cwd = os.getcwd()
        os.chdir(parent)
        self.addCleanup(os.chdir, cwd)
        rel = os.path.join("link", "..")
        absolute = os.path.join(parent, "link", "..")
        env = _spawn_path_env(gw_orig, home=self.home)
        try:
            for c in (rel, rel.encode(), Path(rel), absolute, absolute.encode()):
                with self.subTest(cwd=c):
                    got = tmux_exec.resolve_spawn_exe("tmux", orig, spawn, cwd=c)
                    self.assertTrue(os.path.isabs(got), got)
                    self.assertEqual(os.path.realpath(got),
                                     os.path.realpath(working))
                    self.assertEqual(
                        subprocess.Popen(["tmux"], cwd=c).wait(), 0)  # control
                    proc = TmuxClient(socket_args=[]).spawn(["x"], cwd=c)
                    self.assertEqual(proc.wait(), 0)
        finally:
            env.stop()

    def test_relative_entry_resolves_from_the_childs_cwd(self):
        # subprocess searches PATH in the child AFTER chdir(cwd): a relative
        # `bin` entry names <cwd>/bin. Our parent dir has no bin/, the child's
        # holds the working tmux, and mise's shims hold a decoy that exits 23.
        # child is a SUBDIRECTORY of parent, so its relative spelling is plain
        # "child": a relative pin "child/bin/tmux" would then be re-resolved as
        # child/child/bin/tmux after the chdir. (A sibling spelled "../child"
        # would hide the bug: that pin happens to resolve again from inside.)
        parent = os.path.join(self.root, "parent")
        child = os.path.join(parent, "child")
        os.makedirs(os.path.join(child, "bin"))
        working = os.path.join(child, "bin", "tmux")
        with open(working, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(working, 0o755)
        with open(os.path.join(self.shims, "tmux"), "w") as f:
            f.write("#!/bin/sh\nexit 23\n")
        # The spawn PATH is given, not normalized: normalization only ever
        # moves the absolute ~/.local/bin backwards, so it never puts a decoy
        # ahead of a relative entry. resolve_spawn_exe's contract still covers
        # any spawn PATH it is handed.
        orig = f"bin:{self.shims}:/usr/bin:/bin"
        spawn = f"{self.shims}:bin:/usr/bin:/bin"

        cwd = os.getcwd()
        os.chdir(parent)
        self.addCleanup(os.chdir, cwd)
        real_working = os.path.realpath(working)
        # A RELATIVE cwd (relative to ours, as Popen reads it) must pin an
        # ABSOLUTE path: the child resolves a relative pin from inside cwd.
        rel_child = os.path.relpath(child, parent)
        for c in (child, rel_child):
            with self.subTest(resolve_cwd=c):
                got = tmux_exec.resolve_spawn_exe("tmux", orig, spawn, cwd=c)
                self.assertTrue(os.path.isabs(got), got)
                self.assertEqual(os.path.realpath(got), real_working)
        # Without the child's cwd the lookup happens here, where bin/ is absent.
        self.assertEqual(tmux_exec.resolve_spawn_exe("tmux", orig, spawn), "tmux")

        # End to end, real processes: the caller's own Popen(cwd=…) runs the
        # working tmux, and so must the gateway's spawn — for absolute and
        # relative cwd, as str, bytes and PathLike. The gateway's PATH really
        # is reordered here (an empty ~/.local/bin moves behind the shims), so
        # the child gets env=PATH while the relative entry still leads.
        os.remove(os.path.join(self.sys, "tmux"))  # keep `bin` the resolver
        orig = f"{self.sys}:bin:{self.shims}:/usr/bin:/bin"
        self.assertEqual(tmux_exec.normalize_spawn_path(orig, self.environ),
                         f"bin:{self.shims}:{self.sys}:/usr/bin:/bin")
        env = _spawn_path_env(orig, home=self.home)
        try:
            for c in (child, child.encode(), Path(child),
                      rel_child, rel_child.encode(), Path(rel_child)):
                with self.subTest(cwd=c):
                    self.assertEqual(
                        subprocess.Popen(["tmux"], cwd=c).wait(), 0)  # control
                    proc = TmuxClient(socket_args=[]).spawn(["x"], cwd=c)
                    self.assertEqual(proc.wait(), 0)
        finally:
            env.stop()


class TestSpawnEnvPlumbing(unittest.TestCase):
    """Every gateway subprocess carries the normalized PATH — and only when it
    differs, so non-mise hosts get no ``env`` kwarg at all."""

    def setUp(self):
        self.client = TmuxClient(socket_args=[])

    def _run_kwargs(self, path, method, *args):
        captured = {}

        def fake_run(argv, **kwargs):
            captured.update(kwargs)
            return _FakeRunResult(0, "", "")

        env = _spawn_path_env(path)
        try:
            with patch.object(subprocess, "run", side_effect=fake_run):
                getattr(self.client, method)(*args)
        finally:
            env.stop()
        return captured

    def test_sync_methods_get_normalized_path(self):
        for method, args in (("run", (["new-window"],)),
                             ("run_checked", (["new-window"],)),
                             ("set_clipboard", ("text",))):
            with self.subTest(method):
                kwargs = self._run_kwargs(_BAD_PATH, method, *args)
                self.assertEqual(kwargs["env"]["PATH"], _GOOD_PATH)
                self.assertEqual(kwargs["env"]["HOME"], _H)

    def test_sync_methods_without_mise_pass_no_env(self):
        for method, args in (("run", (["new-window"],)),
                             ("run_checked", (["new-window"],)),
                             ("set_clipboard", ("text",))):
            with self.subTest(method):
                kwargs = self._run_kwargs("/usr/bin:/bin", method, *args)
                self.assertNotIn("env", kwargs)

    def test_run_async_gets_normalized_path(self):
        captured = {}

        async def fake_exec(*argv, **kwargs):
            captured.update(kwargs)
            raise OSError

        env = _spawn_path_env(_BAD_PATH)
        try:
            with patch.object(asyncio, "create_subprocess_exec",
                              side_effect=fake_exec):
                asyncio.run(self.client.run_async(["new-window"]))
        finally:
            env.stop()
        self.assertEqual(captured["env"]["PATH"], _GOOD_PATH)

    def _spawn_kwargs(self, path, **popen_kwargs):
        captured = {}

        def fake_popen(argv, **kwargs):
            captured.update(kwargs)
            return object()

        env = _spawn_path_env(path)
        try:
            with patch.object(subprocess, "Popen", side_effect=fake_popen):
                self.client.spawn(["new-window"], **popen_kwargs)
        finally:
            env.stop()
        return captured

    def test_spawn_inherited_env(self):
        self.assertEqual(self._spawn_kwargs(_BAD_PATH)["env"]["PATH"],
                         _GOOD_PATH)
        self.assertNotIn("env", self._spawn_kwargs("/usr/bin:/bin"))

    def test_spawn_caller_env_is_normalized_not_replaced(self):
        custom = {"HOME": _H, "PATH": _BAD_PATH, "MARK": "1"}
        kwargs = self._spawn_kwargs("/usr/bin:/bin", env=custom)
        self.assertEqual(kwargs["env"]["PATH"], _GOOD_PATH)
        self.assertEqual(kwargs["env"]["MARK"], "1")
        self.assertEqual(custom["PATH"], _BAD_PATH)  # caller's dict untouched

        plain = {"HOME": _H, "PATH": "/usr/bin"}
        self.assertIs(self._spawn_kwargs(_BAD_PATH, env=plain)["env"], plain)

    def test_spawn_env_none_without_path(self):
        self.assertIsNone(TmuxClient.spawn_env({"HOME": _H}))


class TestControlBypassForPaneCreation(unittest.TestCase):
    """A pane spawned via the attached control client gets the server's global
    PATH, so pane-creating verbs must take the subprocess route."""

    def test_new_window_skips_alive_backend(self):
        client = TmuxClient(socket_args=[])
        backend = _FakeBackend(alive=True, sync_result=(0, "ctrl"))
        with patch.object(client, "run", return_value=(0, "%9")) as m:
            rc, out = client.run_via_control(
                backend, ["new-window", "-t", "=s:", "cmd"])
        self.assertEqual((rc, out), (0, "%9"))
        self.assertEqual(backend.sync_calls, [])
        m.assert_called_once()

    def test_chained_split_skips_alive_backend(self):
        client = TmuxClient(socket_args=[])
        backend = _FakeBackend(alive=True, sync_result=(0, "ctrl"))
        with patch.object(client, "run", return_value=(0, "")):
            client.run_via_control(
                backend, ["select-window", "-t", "=s:1", ";", "split-window"])
        self.assertEqual(backend.sync_calls, [])

    def test_query_still_uses_backend(self):
        client = TmuxClient(socket_args=[])
        backend = _FakeBackend(alive=True, sync_result=(0, "ctrl"))
        with patch.object(client, "run") as m:
            client.run_via_control(backend, ["list-panes", "-a"])
        self.assertEqual(backend.sync_calls, [["list-panes", "-a"]])
        m.assert_not_called()

    def test_async_new_window_skips_alive_backend(self):
        async def go():
            client = TmuxClient(socket_args=[])
            backend = _FakeBackend(alive=True, async_result=(0, "ctrl"))

            async def fake_run_async(args, timeout=5.0):
                return (0, "sub")
            with patch.object(client, "run_async", side_effect=fake_run_async):
                out = await client.run_async_via_control(
                    backend, ["split-window", "-h"])
            return out, backend.async_calls
        out, calls = asyncio.run(go())
        self.assertEqual(out, (0, "sub"))
        self.assertEqual(calls, [])


class TestPersistentPrefixSetenv(unittest.TestCase):
    """The systemd-run rung hands the new server the normalized PATH."""

    def _setenv_flags(self, path):
        env = _spawn_path_env(path)
        try:
            # Borrow the ladder fixture without re-running its test methods.
            argv = TestNewSessionArgv._build(self, systemd_available=True)
        finally:
            env.stop()
        head = argv[:argv.index("--")]
        return [a for a in head if a.startswith("--setenv=")]

    def test_mise_path_is_normalized(self):
        self.assertEqual(self._setenv_flags(_BAD_PATH),
                         [f"--setenv=PATH={_GOOD_PATH}"])

    def test_plain_path_is_passed_through(self):
        self.assertEqual(self._setenv_flags("/usr/bin:/bin"),
                         ["--setenv=PATH=/usr/bin:/bin"])

    def test_no_path_no_setenv(self):
        self.assertEqual(self._setenv_flags(None), [])


if __name__ == "__main__":
    unittest.main()
