"""The control-client helper session against a REAL tmux server (t2051).

tmux takes a pane's default colours — what it answers to OSC 10/11 — from the
first client attached to the pane's session, and a control-mode client reports
black. So the monitor's `tmux -C` clients attach to a dedicated helper session,
`_ait_control`, instead of the project session. This file pins that move and
everything it put at risk:

- the colours a pane reads, in the `ait ide` order (control client first), with
  the old attach as the in-fixture negative control;
- commands still act on the project session (explicit targets);
- the helper stays off the framework's session lists, and is destroyed with its
  last client;
- a user's own `_ait_control` session is never joined, hooked or modified — also
  when it only *inherits* the marker text, and when it replaces the owned helper
  between inspection and join;
- a destroyed, replaced or renamed project is noticed (`exit_seen`), a transport
  failure is not mistaken for it, and no `tmux -C` process is left attached
  after a timeout or a cancelled start;
- the bounce hook moves a real terminal out of the helper under both
  `detach-on-destroy` settings, acts only while the terminal is still there, and
  does not depend on any checkout.

Each test gets its own tmux server (`-L ait_t2051_<pid>_<n>`, started with
`-f /dev/null`, under a short scratch `TMUX_TMPDIR`) and a scratch `HOME`. The
backends run in this process, so the gateway singletons that were built at
import time are rebuilt onto that socket (`tests/lib/tmux_socket_containment.py`
explains why setting the environment alone is not enough).

Skip vs fail: `SkipTest` only when `tmux` is missing or no pty can be opened —
both checked without running any code under test. Everything after that is the
regression this file exists to catch and fails.

Run:
  python3 tests/test_control_helper_session_live.py
"""
from __future__ import annotations

import asyncio
import itertools
import os
import pty
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

import agent_launch_utils  # noqa: E402
import tmux_exec  # noqa: E402
from fake_terminal import (  # noqa: E402
    BLACK, REAL_COLOURS, FakeTerminal, parse_probe, probe_command,
)
from monitor import monitor_core  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    HELPER_MODE_CREATE, HELPER_MODE_JOIN, HELPER_MODE_LEGACY,
    TmuxControlBackend, TmuxControlClient, TmuxControlState, TmuxMonitor,
)
from tmux_exec import (  # noqa: E402
    AIT_CONTROL_BOUNCE_HOOK, AIT_CONTROL_MARKER, AIT_CONTROL_MARKER_OPTION,
    AIT_CONTROL_SESSION,
)

HELPER = AIT_CONTROL_SESSION
DEADLINE = 15.0
_COUNTER = itertools.count()

#: The pre-t2051 attach: a control client in the project session itself.
OLD_ATTACH = ["attach", "-t", "{target}", "-f", "no-output,ignore-size"]

#: The bounce hook without its run-time guard — the pre-fix control for the
#: "hook runs after the rest of its command list" finding.
UNGUARDED_HOOK = ("if-shell -F '#{client_control_mode}' '' "
                  "{ if-shell -F '#{==:#{server_sessions},1}' "
                  "{ detach-client } { switch-client -n } }")


def _short_tmp() -> str:
    """A short scratch dir: tmux's socket path is an AF_UNIX path (~104 bytes)."""
    for base in ("/tmp", None):
        try:
            return tempfile.mkdtemp(prefix="ait2051_", dir=base)
        except OSError:
            continue
    raise unittest.SkipTest("no writable temp directory")


def wait_for(pred, timeout: float = DEADLINE, step: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(step)
    return bool(pred())


class RawControl:
    """A raw `tmux -C` client the test holds open (no framework code)."""

    def __init__(self, case: "LiveCase", argv: list[str]):
        self.proc = subprocess.Popen(
            [*case.tmux_argv, "-C", *argv], env=case.env, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


class LiveCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Capability gate only — nothing here runs the code under test.
        if shutil.which("tmux") is None:
            raise unittest.SkipTest("tmux not installed")
        try:
            a, b = pty.openpty()
        except OSError as exc:
            raise unittest.SkipTest(f"no pty available: {exc}")
        os.close(a)
        os.close(b)

    def setUp(self):
        self.base = Path(_short_tmp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.sock = f"ait_t2051_{os.getpid()}_{next(_COUNTER)}"
        for sub in ("tt", "home", "out"):
            (self.base / sub).mkdir(mode=0o700)
        env_patch = patch.dict(os.environ, {
            "AITASKS_TMUX_SOCKET": self.sock,
            "TMUX_TMPDIR": str(self.base / "tt"),
            "HOME": str(self.base / "home"),
        }, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        for name in ("TMUX", "TMUX_PANE", "XDG_CONFIG_HOME"):
            os.environ.pop(name, None)
        self.env = dict(os.environ)
        # `-f /dev/null`: whichever call starts the server must not read the
        # developer's tmux.conf (which may set detach-on-destroy, hooks, …).
        self.tmux_argv = ["tmux", "-L", self.sock, "-f", "/dev/null"]

        # Import-time gateway singleton -> this test's socket.
        saved = agent_launch_utils._TMUX
        agent_launch_utils._TMUX = agent_launch_utils.TmuxClient()
        self.addCleanup(setattr, agent_launch_utils, "_TMUX", saved)
        self.assertEqual(agent_launch_utils._TMUX.socket_args, ["-L", self.sock])

        for name, value in (("_RECONNECT_BACKOFFS", (0.2,) * 5),
                            ("_DEATH_POLL_INTERVAL", 0.1)):
            p = patch.object(monitor_core, name, value)
            p.start()
            self.addCleanup(p.stop)

        self._backends: list[TmuxControlBackend] = []
        self._terminals: list[FakeTerminal] = []
        self._raw: list[RawControl] = []
        self._procs: list[subprocess.Popen] = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for b in self._backends:
            try:
                b.stop()
            except Exception:  # noqa: BLE001
                pass
        for proc in self._procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        for raw in self._raw:
            raw.close()
        for ft in self._terminals:
            ft.close()
        subprocess.run([*self.tmux_argv, "kill-server"], env=self.env,
                       capture_output=True)

    # -- helpers -------------------------------------------------------------

    def tmux(self, *args, check=True) -> str:
        out = subprocess.run([*self.tmux_argv, *args], env=self.env,
                             capture_output=True, text=True)
        if check and out.returncode != 0:
            raise AssertionError(f"tmux {args} failed: {out.stderr}")
        return out.stdout

    def project(self, name: str) -> Path:
        root = self.base / name
        (root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
        (root / "aitasks" / "metadata" / "project_config.yaml").write_text(
            "tmux:\n  monitor:\n    refresh_seconds: 60\n")
        return root

    def session(self, name: str, root: Path | None = None) -> str:
        """Create a detached session; return its id (``$N``)."""
        root = root or self.project(name)
        self.tmux("new-session", "-d", "-s", name, "-x", "120", "-y", "40",
                  "-c", str(root), "sleep 3600")
        return self.session_id(name)

    def sessions(self) -> list[str]:
        return self.tmux("list-sessions", "-F", "#{session_name}",
                         check=False).split("\n")[:-1]

    def session_id(self, name: str) -> str | None:
        out = self.tmux("list-sessions", "-F", "#{session_id}\t#{session_name}",
                        check=False)
        for row in out.split("\n"):     # not splitlines(): names may hold U+2028
            sid, _, row_name = row.partition("\t")
            if row_name == name:
                return sid
        return None

    def clients(self) -> list[tuple[str, str, str, str]]:
        """``(control, session, client_name, client_pid)`` per attached client."""
        out = self.tmux("list-clients", "-F",
                        "#{client_control_mode}\t#{client_session}\t"
                        "#{client_name}\t#{client_pid}", check=False)
        return [tuple(row.split("\t")) for row in out.splitlines() if row]

    def control_sessions(self) -> list[str]:
        return sorted(c[1] for c in self.clients() if c[0] == "1")

    def real_sessions(self) -> list[str]:
        return sorted(c[1] for c in self.clients() if c[0] == "0")

    def backend(self, session: str, **kw) -> TmuxControlBackend:
        b = TmuxControlBackend(session=session, command_timeout=3.0, **kw)
        self._backends.append(b)
        return b

    def started(self, session: str) -> TmuxControlBackend:
        b = self.backend(session)
        self.assertTrue(b.start(), f"backend for {session!r} did not start")
        return b

    def terminal(self, session: str) -> FakeTerminal:
        before = len(self.real_sessions())
        ft = FakeTerminal(self.tmux_argv, self.env, session)
        self._terminals.append(ft)
        self.assertTrue(wait_for(lambda: len(self.real_sessions()) > before or ft.exited(), 5),
                        "the fake terminal never attached")
        time.sleep(0.3)   # let tmux read the terminal's colour replies
        return ft

    def place(self, ft: FakeTerminal, settle: float = 0.6) -> str:
        """Where the fake terminal is now: a session name, or ``DETACHED``."""
        time.sleep(settle)
        if ft.exited():
            return "DETACHED"
        real = self.real_sessions()
        return real[0] if real else "NO-CLIENT"

    def terminal_name(self) -> str:
        return [c[2] for c in self.clients() if c[0] == "0"][0]

    def raw_control(self, *argv: str) -> RawControl:
        raw = RawControl(self, list(argv))
        self._raw.append(raw)
        return raw

    def probe(self, session: str) -> dict:
        out = self.base / "out" / f"probe_{next(_COUNTER)}"
        self.tmux("new-window", "-d", "-t", f"={session}:", probe_command(str(out)))
        self.assertTrue(wait_for(out.exists, 6), "the OSC probe never reported")
        result = parse_probe(out.read_text())
        self.assertTrue(result.pop("read"), "the probe did not reach a terminal")
        return result

    def local_option(self, session_id: str, option: str) -> str:
        return self.tmux("show-options", "-qv", "-t", f"{session_id}:", option).strip()

    def hooks(self, session_id: str) -> str:
        return self.tmux("show-hooks", "-t", f"{session_id}:")

    def on_loop(self, backend: TmuxControlBackend, coro, timeout: float = 10.0):
        return asyncio.run_coroutine_threadsafe(coro, backend._loop).result(timeout)

    def served(self, backend: TmuxControlBackend, session: str):
        rc, out = backend.request_sync(
            ["display-message", "-p", "-t", f"={session}:", "#S"])
        return rc, out.strip()


# ---------------------------------------------------------------------------
# Where the client lives, and the colours a pane reads
# ---------------------------------------------------------------------------

class ColourTests(LiveCase):

    def test_client_lives_in_the_helper_and_panes_read_real_colours(self):
        self.session("s")
        ft = self.terminal("s")
        b = self.started("s")
        self.assertEqual(b._client.helper_mode, HELPER_MODE_CREATE)
        self.assertEqual(self.control_sessions(), [HELPER])
        self.assertEqual(self.real_sessions(), ["s"])
        self.assertEqual(self.probe("s"), REAL_COLOURS)
        self.assertFalse(ft.exited())

    def test_ide_order_control_client_first(self):
        # `ait ide` creates the monitor window and only then attaches the
        # terminal, so the control client always comes first. That order is
        # the bug's normal trigger.
        self.session("s")
        self.started("s")
        self.terminal("s")
        self.assertEqual(self.control_sessions(), [HELPER])
        self.assertEqual(self.probe("s"), REAL_COLOURS)

    def test_negative_control_old_attach_gives_black(self):
        # Same fixture, the pre-t2051 attach: the control client sits in the
        # project session and attached first. Without this, "real colours"
        # above could be a property of the fixture rather than of the fix.
        self.session("s")
        raw = self.raw_control(*[a.format(target="=s") for a in OLD_ATTACH])
        self.assertTrue(wait_for(lambda: self.control_sessions() == ["s"], 5))
        self.terminal("s")
        self.assertEqual(self.probe("s"), BLACK)
        self.assertTrue(raw.alive())

    def test_old_attach_after_the_real_terminal_is_harmless(self):
        # Order matters, not presence: this is why the bug looked intermittent.
        self.session("s")
        self.terminal("s")
        self.raw_control(*[a.format(target="=s") for a in OLD_ATTACH])
        self.assertTrue(wait_for(lambda: self.control_sessions() == ["s"], 5))
        self.assertEqual(self.probe("s"), REAL_COLOURS)


# ---------------------------------------------------------------------------
# Commands still act on the project; the helper is off the framework's lists
# ---------------------------------------------------------------------------

class TargetAndListingTests(LiveCase):

    def test_commands_still_target_the_project(self):
        root = self.project("s")
        self.session("s", root)
        b = self.started("s")
        self.assertEqual(self.served(b, "s"), (0, "s"))

        # monitor_app's "which session am I in" query, both target forms.
        from monitor.monitor_app import MonitorApp
        for own_pane in (None, self.tmux("display-message", "-p", "-t", "=s:",
                                         "#{pane_id}").strip()):
            stub = types.SimpleNamespace(_own_pane_id=own_pane, _session="s")
            args = MonitorApp._attached_session_args(stub)
            self.assertIn("-t", args)
            self.assertEqual(b.request_sync(args), (0, "s\n"), args)
        # Pre-fix control: the untargeted form answers the helper's name.
        self.assertEqual(b.request_sync(["display-message", "-p", "#S"]),
                         (0, HELPER + "\n"))

        # The frozen coordinator's detached job keeps the project's cwd.
        from monitor.monitor_shared import AgentMarksMixin
        stub = types.SimpleNamespace(_session="s")
        frozen = AgentMarksMixin._frozen_detached_args(stub, ["drop", "x"])
        self.assertEqual(frozen[:4], ["run-shell", "-b", "-t", "=s:"])

        def job_cwd(*target):
            out = self.base / "out" / f"cwd_{next(_COUNTER)}"
            rc, _ = b.request_sync(["run-shell", "-b", *target, f"pwd > {out}"])
            self.assertEqual(rc, 0)
            self.assertTrue(wait_for(lambda: out.exists() and out.read_text(), 5))
            return out.read_text().strip()

        self.assertEqual(job_cwd(*frozen[2:4]), str(root))
        # Pre-fix control: without the target the job starts in the helper's cwd.
        self.assertEqual(job_cwd(), "/")

    def test_owned_helper_is_marked_and_off_the_framework_lists(self):
        self.session("s")
        self.session("p2")
        b = self.started("s")
        hid = self.session_id(HELPER)
        self.assertIsNotNone(hid)

        # Raw tmux still lists it; the framework's own listing does not.
        self.assertIn(HELPER, self.sessions())
        self.assertEqual(agent_launch_utils.get_tmux_sessions(), ["p2", "s"])

        found = agent_launch_utils.discover_aitasks_sessions()
        self.assertEqual(sorted(x.session for x in found), ["p2", "s"])
        found = asyncio.run(agent_launch_utils.discover_aitasks_sessions_async())
        self.assertEqual(sorted(x.session for x in found), ["p2", "s"])
        found, complete = agent_launch_utils.discover_aitasks_sessions_checked()
        self.assertTrue(complete)
        self.assertEqual(sorted(x.session for x in found), ["p2", "s"])

        monitor = TmuxMonitor(session="s", agent_prefixes=[""])
        panes = monitor.discover_panes()
        self.assertNotIn(HELPER, {p.session_name for p in panes})

        # The marker and destroy-unattached are the session's OWN values, and
        # the hook is session-local and names no file.
        self.assertEqual(self.local_option(hid, AIT_CONTROL_MARKER_OPTION),
                         AIT_CONTROL_MARKER)
        self.assertEqual(self.local_option(hid, "destroy-unattached"), "on")
        self.assertIs(tmux_exec.control_helper_owned(agent_launch_utils._TMUX.run, hid),
                      True)
        hooks = self.hooks(hid)
        self.assertIn("client-session-changed[0] if-shell -F", hooks)
        self.assertIn("switch-client -n", hooks)
        for token in ("run-shell", "$", str(REPO_ROOT), "/"):
            self.assertNotIn(token, hooks)
        self.assertEqual(self.tmux("show-hooks", "-g", "client-session-changed").strip(),
                         "client-session-changed")
        self.assertEqual(self.local_option(self.session_id("s"),
                                           AIT_CONTROL_MARKER_OPTION), "")

        # Destroyed with its last control client: it never keeps a server alive.
        b.stop()
        self.assertTrue(wait_for(lambda: HELPER not in self.sessions(), 5),
                        self.sessions())
        self.assertEqual(self.control_sessions(), [])

    def test_two_projects_share_one_helper(self):
        self.session("p1")
        self.session("p2")
        b1 = self.started("p1")
        b2 = self.started("p2")
        self.assertEqual(b1._client.helper_mode, HELPER_MODE_CREATE)
        self.assertEqual(b2._client.helper_mode, HELPER_MODE_JOIN)
        self.assertEqual(self.control_sessions(), [HELPER, HELPER])
        self.assertEqual(self.sessions().count(HELPER), 1)
        b1.stop()
        self.assertEqual(self.sessions().count(HELPER), 1)
        self.assertEqual(self.served(b2, "p2"), (0, "p2"))
        b2.stop()
        self.assertTrue(wait_for(lambda: HELPER not in self.sessions(), 5))

    def test_session_name_with_a_unicode_line_separator(self):
        # U+2028 is a legal session name character and a line boundary for
        # str.splitlines(), but not for tmux, which frames rows with "\n".
        name = "a\u2028b"
        self.assertTrue(agent_launch_utils._tmux_session_name_ok(name))
        sid = self.session(name)
        self.assertIsNotNone(sid)
        b = self.started(name)
        self.assertEqual(b._client.helper_mode, HELPER_MODE_CREATE)
        self.assertEqual(b._client._project_id, sid)
        self.assertEqual(self.served(b, name), (0, name))
        self.assertEqual(b._client.last_project_check, "present")
        self.assertIn(name, agent_launch_utils.get_tmux_sessions())
        b.stop()

        # Pre-fix control: rows split with splitlines() cut the name in two,
        # so the project reads as absent and nothing is started.
        def split_rows(out):
            rows = []
            for line in out.splitlines():
                rid, sep, row_name = line.partition("\t")
                if sep and rid.startswith("$") and rid[1:].isdigit():
                    rows.append((rid, row_name))
            return rows

        with patch.object(monitor_core, "parse_session_rows", split_rows):
            self.assertFalse(self.backend(name).start(),
                             "control: splitlines() was expected to lose the session")
        self.assertNotIn(HELPER, self.sessions())

    def test_create_join_race(self):
        self.session("p1")
        self.session("p2")
        b1, b2 = self.backend("p1"), self.backend("p2")
        results = {}
        threads = [threading.Thread(target=lambda b=b, k=k: results.update({k: b.start()}))
                   for k, b in (("p1", b1), ("p2", b2))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(results, {"p1": True, "p2": True})
        modes = sorted((b1._client.helper_mode, b2._client.helper_mode))
        self.assertNotIn(HELPER_MODE_LEGACY, modes)
        self.assertIn(HELPER_MODE_JOIN, modes)
        self.assertEqual(self.sessions().count(HELPER), 1)
        self.assertEqual(self.control_sessions(), [HELPER, HELPER])
        self.assertEqual(b1.state, TmuxControlState.CONNECTED)
        self.assertEqual(b2.state, TmuxControlState.CONNECTED)


# ---------------------------------------------------------------------------
# A session named like the helper that is not ours
# ---------------------------------------------------------------------------

class ForeignHelperTests(LiveCase):

    def snapshot(self, sid: str) -> dict:
        return {
            "panes": self.tmux("list-panes", "-s", "-t", f"{sid}:", "-F",
                               "#{window_id} #{pane_id} #{pane_pid}"),
            "options": self.tmux("show-options", "-t", f"{sid}:"),
            "hooks": self.hooks(sid),
            "name": [n for n in self.sessions() if n == HELPER],
        }

    def foreign(self, marker: str | None, inherited: bool = False) -> str:
        self.tmux("new-session", "-d", "-s", HELPER, "-c", str(self.base), "sleep 600")
        fid = self.session_id(HELPER)
        self.tmux("new-window", "-d", "-t", f"{fid}:", "sleep 600")
        self.tmux("set-option", "-t", f"{fid}:", "@user_opt", "keep")
        self.tmux("set-option", "-t", f"{fid}:", "destroy-unattached", "off")
        self.tmux("set-hook", "-t", f"{fid}:", "client-session-changed",
                  "display-message user-hook")
        if inherited:
            self.tmux("set-option", "-g", AIT_CONTROL_MARKER_OPTION, AIT_CONTROL_MARKER)
        elif marker is not None:
            self.tmux("set-option", "-t", f"{fid}:", AIT_CONTROL_MARKER_OPTION, marker)
        return fid

    def check_preserved(self, marker, inherited=False):
        self.session("s")
        fid = self.foreign(marker, inherited)
        before = self.snapshot(fid)

        b = self.started("s")
        self.assertEqual(b._client.helper_mode, HELPER_MODE_LEGACY)
        self.assertEqual(b.state, TmuxControlState.CONNECTED)
        self.assertEqual(self.control_sessions(), ["s"])
        # The legacy channel is a working one, not a degraded one.
        self.assertEqual(self.served(b, "s"), (0, "s"))
        self.assertEqual(b.request_sync(["display-message", "-p", "#S"]), (0, "s\n"))

        self.assertEqual(self.session_id(HELPER), fid)
        self.assertEqual(self.snapshot(fid), before)
        self.assertIn(HELPER, agent_launch_utils.get_tmux_sessions())

        b.stop()
        self.assertEqual(self.session_id(HELPER), fid, "the foreign session was destroyed")
        self.assertEqual(self.snapshot(fid), before)

    def test_unmarked_foreign_session_is_preserved(self):
        self.check_preserved(None)

    def test_foreign_session_with_another_marker_value_is_preserved(self):
        self.check_preserved("someone-elses-v1")

    def test_inherited_only_marker_is_not_ownership(self):
        # A global option of the same name: a format read reports the text for
        # EVERY session, the user's `_ait_control` included.
        self.check_preserved(None, inherited=True)
        fid = self.session_id(HELPER)
        # Pre-fix control: the format-based read takes it for ours...
        rows = self.tmux("list-sessions", "-F",
                         "#{session_name}\t#{" + AIT_CONTROL_MARKER_OPTION + "}")
        self.assertIn(f"{HELPER}\t{AIT_CONTROL_MARKER}", rows.splitlines())
        # ...while the session-local read does not.
        self.assertEqual(self.local_option(fid, AIT_CONTROL_MARKER_OPTION), "")
        self.assertIs(tmux_exec.control_helper_owned(agent_launch_utils._TMUX.run, fid),
                      False)

    def swap_helper(self, old_id: str) -> str:
        """Replace the owned helper with an unmarked same-name session."""
        self.tmux("kill-session", "-t", old_id)
        self.tmux("new-session", "-d", "-s", HELPER, "-c", str(self.base), "sleep 600")
        new_id = self.session_id(HELPER)
        self.tmux("set-option", "-t", f"{new_id}:", "@user_opt", "keep")
        return new_id

    def owned_helper(self) -> str:
        """An owned helper held open by a raw client (no backend to disturb)."""
        c = TmuxControlClient("s")
        holder = self.raw_control(*c._attach_argv()[c._attach_argv().index("-C") + 1:])
        self.assertTrue(wait_for(lambda: self.session_id(HELPER) is not None, 5))
        self.assertTrue(holder.alive())
        hid = self.session_id(HELPER)
        self.assertEqual(self.local_option(hid, AIT_CONTROL_MARKER_OPTION),
                         AIT_CONTROL_MARKER)
        return hid

    def test_replacement_between_inspect_and_join(self):
        self.session("s")
        self.tmux("set-option", "-g", "detach-on-destroy", "on")
        hid = self.owned_helper()
        state = {}

        async def go():
            c = TmuxControlClient("s", command_timeout=3.0)
            real_owned = c._helper_owned

            async def owned_then_swap(helper_id):
                verdict = await real_owned(helper_id)
                if "new" not in state:
                    # The pass now believes helper `hid` is ours. Swap it.
                    state["verdict"] = verdict
                    state["new"] = self.swap_helper(helper_id)
                return verdict

            c._helper_owned = owned_then_swap
            ok = await c.start()
            where = self.control_sessions()
            mode = c.helper_mode
            await c.close()
            return ok, where, mode

        ok, where, mode = asyncio.run(go())
        new_id = state["new"]
        self.assertIs(state["verdict"], True, "the inspect step never saw the owned helper")
        self.assertNotEqual(new_id, hid)
        self.assertTrue(ok)
        # The join named the inspected id, so it failed; the retry found a
        # foreign session and attached to the project instead.
        self.assertEqual(mode, HELPER_MODE_LEGACY)
        self.assertEqual(where, ["s"])
        self.assertEqual(self.local_option(new_id, AIT_CONTROL_MARKER_OPTION), "")
        self.assertEqual(self.local_option(new_id, "@user_opt"), "keep")
        self.assertEqual(self.hooks(new_id).strip(), "")

    def test_control_join_by_name_lands_on_the_replacement(self):
        # Pre-fix control for the test above: the same swap, then a join that
        # names the helper instead of the inspected id (and installs the hook
        # by name, as an earlier design did).
        self.session("s")
        self.tmux("set-option", "-g", "detach-on-destroy", "on")
        hid = self.owned_helper()
        new_id = self.swap_helper(hid)
        self.raw_control(
            "has-session", "-t", "=s", ";",
            "attach-session", "-t", "=" + HELPER, "-f", "no-output,ignore-size", ";",
            "set-hook", "-t", f"={HELPER}:", "client-session-changed",
            AIT_CONTROL_BOUNCE_HOOK)
        self.assertTrue(wait_for(lambda: self.control_sessions() == [HELPER], 5),
                        self.control_sessions())
        self.assertEqual(self.session_id(HELPER), new_id)
        self.assertIn("switch-client -n", self.hooks(new_id),
                      "control: the by-name join did not hook the replacement")


# ---------------------------------------------------------------------------
# The project goes away while the client is connected
# ---------------------------------------------------------------------------

class ProjectDeletionTests(LiveCase):

    def wait_state(self, b, state, timeout=DEADLINE):
        self.assertTrue(wait_for(lambda: b.state == state, timeout),
                        f"state={b.state!r}, wanted {state!r}")

    def test_project_deletion_with_a_shared_helper(self):
        self.session("p1")
        self.session("p2")
        self.terminal("p2")
        b1, b2 = self.started("p1"), self.started("p2")
        first = b1._client
        self.tmux("kill-session", "-t", "=p1")

        self.wait_state(b1, TmuxControlState.FALLBACK)
        self.assertEqual(first.last_project_check, "gone")
        self.assertTrue(b1.exit_seen)
        self.assertFalse(b1.is_alive)

        # The other project is untouched: same helper, one client, still served.
        self.assertEqual(self.control_sessions(), [HELPER])
        self.assertEqual(b2.state, TmuxControlState.CONNECTED)
        self.assertFalse(b2.exit_seen)
        self.assertEqual(b2._client.last_project_check, "present")
        self.assertEqual(self.served(b2, "p2"), (0, "p2"))
        self.assertEqual(self.probe("p2"), REAL_COLOURS)

        b2.stop()
        self.assertTrue(wait_for(lambda: HELPER not in self.sessions(), 5))

    def test_control_display_message_cannot_prove_absence(self):
        # Pre-fix control for the check's choice of verb: over the helper's
        # control connection a deleted project answers rc 0 with an empty
        # body, which an "rc 1 means gone" check reads as present.
        self.session("p1")
        self.session("p2")
        b2 = self.started("p2")
        self.tmux("kill-session", "-t", "=p1")
        self.assertEqual(
            b2.request_sync(["display-message", "-p", "-t", "=p1:", "#{session_id}"]),
            (0, "\n"))
        rc, out = b2.request_sync(["list-sessions", "-F", tmux_exec.SESSION_ID_NAME_FORMAT])
        names = [name for _, name in tmux_exec.parse_session_rows(out)]
        self.assertEqual((rc, sorted(names)), (0, [HELPER, "p2"]))

    def stale_first_check(self, client):
        """Make the first check return a result read BEFORE the project died.

        The first check really queries tmux (and sees the project), then its
        result is held back. The test destroys the project while it is held,
        so the notification arrives during an active check. Releasing the gate
        delivers the stale "present". Only a SECOND query can see the deletion.
        """
        gate, queried = threading.Event(), threading.Event()
        real_check = client.check_project
        verdicts = []

        async def held_check():
            verdict = await real_check()
            verdicts.append(verdict)
            if len(verdicts) == 1:
                queried.set()
                while not gate.is_set():
                    await asyncio.sleep(0.02)
                client.last_project_check = verdict
            return verdict

        client.check_project = held_check
        return gate, queried, verdicts

    def deletion_during_a_check(self):
        self.session("other")
        self.session("p1")
        b = self.started("p1")
        client = b._client
        gate, queried, verdicts = self.stale_first_check(client)
        self.tmux("kill-session", "-t", "=other")
        self.assertTrue(queried.wait(5), "the first check never queried")
        self.assertEqual(verdicts, ["present"])
        self.tmux("kill-session", "-t", "=p1")
        time.sleep(0.5)            # the notification lands while the check is held
        self.assertTrue(client.is_alive)
        gate.set()
        return b, client, verdicts

    def test_deletion_during_a_check_is_not_lost(self):
        b, client, verdicts = self.deletion_during_a_check()
        self.assertTrue(wait_for(lambda: not client.is_alive, 5),
                        "the project's deletion was lost")
        # The stale first result, then a second query that saw the deletion.
        self.assertEqual(verdicts, ["present", "gone"])
        self.assertTrue(client.saw_exit)
        self.assertTrue(wait_for(lambda: b.exit_seen, 5))

    def test_control_dropping_notifications_during_a_check_loses_the_deletion(self):
        # Pre-fix control: a scheduler that ignores a notification while a
        # check is active (no "again" flag). The stale result stands.
        def drop_while_active(client):
            if not client._alive or client._own_session_id is None:
                return
            if client._check_task is not None and not client._check_task.done():
                return
            client._check_task = asyncio.get_running_loop().create_task(
                client._project_check_loop())

        with patch.object(TmuxControlClient, "_schedule_project_check", drop_while_active):
            b, client, verdicts = self.deletion_during_a_check()
            time.sleep(2.0)
            self.assertEqual(verdicts, ["present"],
                             "control: a second query was not expected")
            self.assertTrue(client.is_alive,
                            "control: the deletion was expected to be lost")
            self.assertFalse(b.exit_seen)

    def test_kill_and_recreate_under_the_same_name(self):
        self.session("p1")
        self.session("keep")
        b = self.started("p1")
        first = b._client
        old_id = first._project_id
        self.assertEqual(old_id, self.session_id("p1"))
        self.tmux("kill-session", "-t", "=p1", ";",
                  "new-session", "-d", "-s", "p1", "-c", str(self.base), "sleep 3600")
        new_id = self.session_id("p1")
        self.assertNotEqual(new_id, old_id)

        self.assertTrue(wait_for(lambda: b._client is not first
                                 and b.state == TmuxControlState.CONNECTED),
                        f"state={b.state!r}")
        self.assertEqual(first.last_project_check, "replaced")
        self.assertTrue(b.exit_seen, "a replaced project did not raise exit_seen")
        self.assertEqual(b._client._project_id, new_id)
        self.assertEqual(self.served(b, "p1"), (0, "p1"))
        self.assertEqual(self.control_sessions(), [HELPER])

    def test_control_by_name_check_misses_the_replacement(self):
        # Pre-fix control: `has-session` by name succeeds against the new session.
        self.session("p1")
        self.session("keep")
        b = self.started("keep")
        self.tmux("kill-session", "-t", "=p1", ";",
                  "new-session", "-d", "-s", "p1", "-c", str(self.base), "sleep 3600")
        self.assertEqual(b.request_sync(["has-session", "-t", "=p1"]), (0, ""))

    def test_renamed_project_reads_as_gone(self):
        self.session("p1")
        self.session("keep")
        b = self.started("p1")
        first = b._client
        self.tmux("rename-session", "-t", "=p1", "p1_renamed")
        self.assertTrue(wait_for(lambda: not first.is_alive, 5))
        self.assertEqual(first.last_project_check, "gone")
        self.wait_state(b, TmuxControlState.FALLBACK)

    def test_helper_killed_by_hand_is_recreated(self):
        for dod in ("on", "off"):
            with self.subTest(detach_on_destroy=dod):
                name = f"p_{dod}"
                self.session(name)
                self.tmux("set-option", "-g", "detach-on-destroy", dod)
                b = self.started(name)
                first = b._client
                old_helper = self.session_id(HELPER)
                self.tmux("kill-session", "-t", old_helper)
                self.assertTrue(wait_for(lambda: b._client is not first
                                         and b.state == TmuxControlState.CONNECTED),
                                f"state={b.state!r}")
                new_helper = self.session_id(HELPER)
                self.assertNotIn(new_helper, (None, old_helper))
                self.assertEqual(self.local_option(new_helper, AIT_CONTROL_MARKER_OPTION),
                                 AIT_CONTROL_MARKER)
                self.assertEqual(self.control_sessions(), [HELPER])
                self.assertEqual(self.served(b, name), (0, name))
                b.stop()
                self.assertTrue(wait_for(lambda: HELPER not in self.sessions(), 5))
                self.tmux("kill-session", "-t", f"={name}")


# ---------------------------------------------------------------------------
# No `tmux -C` process is left attached
# ---------------------------------------------------------------------------

class NoLeakedClientTests(LiveCase):

    def server_pid(self) -> int:
        return int(self.tmux("display-message", "-p", "#{pid}").strip())

    def timeout_then_recover(self, b):
        """Freeze the server, time a check out, thaw; return the old client."""
        first = b._client
        pid = self.server_pid()
        os.kill(pid, signal.SIGSTOP)
        try:
            verdict = self.on_loop(b, first.check_project(), timeout=10)
            state_frozen = b.state
        finally:
            os.kill(pid, signal.SIGCONT)
        self.assertEqual(verdict, "transport")
        self.assertEqual(first.last_project_check, "transport")
        self.assertNotEqual(state_frozen, TmuxControlState.FALLBACK)
        self.assertFalse(first.is_alive, "a timed-out request must mark the client dead")
        self.assertTrue(wait_for(lambda: b._client is not first
                                 and b.state == TmuxControlState.CONNECTED),
                        f"state={b.state!r}")
        return first

    def test_timed_out_client_is_closed_before_it_is_replaced(self):
        self.session("p2")
        b = self.started("p2")
        first = self.timeout_then_recover(b)
        # A transport failure is never read as "project gone".
        self.assertFalse(b.exit_seen)
        self.assertFalse(first.saw_exit)
        self.assertEqual(self.served(b, "p2"), (0, "p2"))
        # Exactly one control client: the old process was closed, not leaked.
        self.assertTrue(wait_for(lambda: self.control_sessions() == [HELPER], 5),
                        self.control_sessions())
        self.assertIsNone(first._proc)
        self.assertEqual(self.local_option(self.session_id(HELPER),
                                           AIT_CONTROL_MARKER_OPTION), AIT_CONTROL_MARKER)
        b.stop()
        self.assertTrue(wait_for(lambda: self.control_sessions() == []
                                 and HELPER not in self.sessions(), 5),
                        (self.control_sessions(), self.sessions()))

    def test_control_unclosed_client_pins_the_helper(self):
        # Pre-fix control: the supervisor replaced a dead client without
        # closing it. Injected at that exact call: close() does nothing while
        # the supervisor reconnects, and is restored before stop().
        self.session("p2")
        b = self.started("p2")
        real_close = TmuxControlClient.close

        async def no_close(self):
            return None

        TmuxControlClient.close = no_close
        try:
            first = self.timeout_then_recover(b)
        finally:
            TmuxControlClient.close = real_close
        self.assertEqual(self.control_sessions(), [HELPER, HELPER],
                         "control: the old client was expected to stay attached")
        b.stop()
        time.sleep(1.0)
        self.assertEqual(self.control_sessions(), [HELPER])
        self.assertIn(HELPER, self.sessions(),
                      "control: the leaked client was expected to pin the helper")
        self.assertIsNotNone(first._proc)
        first._proc.kill()

    # -- the project is lost while no client is connected ---------------------

    def timeout_then(self, b, action):
        """Time a check out, then run ``action`` before the reconnect starts."""
        first = b._client
        pid = self.server_pid()
        os.kill(pid, signal.SIGSTOP)
        try:
            self.assertEqual(self.on_loop(b, first.check_project(), timeout=10),
                             "transport")
        finally:
            os.kill(pid, signal.SIGCONT)
        action()
        return first

    def lost_during_reconnect(self, action):
        self.session("p1")
        self.session("keep")
        # A first backoff long enough for `action` to land before the reconnect.
        with patch.object(monitor_core, "_RECONNECT_BACKOFFS", (1.5, 0.2, 0.2, 0.2, 0.2)):
            b = self.started("p1")
            first = self.timeout_then(b, action)
            self.assertFalse(first.saw_exit, "the timeout itself must not signal")
            self.assertTrue(wait_for(lambda: b.state in (TmuxControlState.FALLBACK,
                                                         TmuxControlState.CONNECTED)
                                     and b._client is not None
                                     and (b._client is not first
                                          or b.state == TmuxControlState.FALLBACK)),
                            f"state={b.state!r}")
        return b

    def test_project_deleted_between_timeout_and_reconnect(self):
        b = self.lost_during_reconnect(lambda: self.tmux("kill-session", "-t", "=p1"))
        self.assertTrue(wait_for(lambda: b.state == TmuxControlState.FALLBACK))
        self.assertTrue(b.exit_seen,
                        "a project deleted while no client was connected raised no signal")
        self.assertEqual(self.control_sessions(), [])

    def test_project_replaced_between_timeout_and_reconnect(self):
        b = self.lost_during_reconnect(lambda: self.tmux(
            "kill-session", "-t", "=p1", ";",
            "new-session", "-d", "-s", "p1", "-c", str(self.base), "sleep 3600"))
        self.assertTrue(wait_for(lambda: b.state == TmuxControlState.CONNECTED))
        self.assertTrue(b.exit_seen, "a replaced project raised no signal")
        self.assertEqual(b._client._project_id, self.session_id("p1"))
        self.assertEqual(b._client.lost_project, "replaced")
        self.assertFalse(b._client.saw_exit)
        self.assertEqual(self.served(b, "p1"), (0, "p1"))

    def test_project_untouched_between_timeout_and_reconnect_is_no_signal(self):
        # A failed transport probe stays distinct from proved absence.
        b = self.lost_during_reconnect(lambda: None)
        self.assertEqual(b.state, TmuxControlState.CONNECTED)
        self.assertFalse(b.exit_seen)
        self.assertEqual(b._client.lost_project, "")

    def test_server_shut_down_between_timeout_and_reconnect(self):
        # tmux goes away while the timed-out client is being closed. That
        # client's %exit is ignored (it is closing), and no listing can prove
        # anything about the project once the server is gone — so the
        # reconnect must recognise tmux's own "no server" answer.
        self.session("p1")
        self.session("keep")
        with patch.object(monitor_core, "_RECONNECT_BACKOFFS", (1.5, 0.2, 0.2, 0.2, 0.2)):
            b = self.started("p1")
            first = self.timeout_then(b, lambda: self.tmux("kill-server"))
            self.assertTrue(wait_for(lambda: b.state == TmuxControlState.FALLBACK))
        self.assertTrue(b.exit_seen, "a tmux shutdown during recovery raised no signal")
        self.assertIsNone(first._proc)

    def test_control_server_shutdown_without_the_no_server_probe_is_silent(self):
        # Pre-fix control: a failed reconnect listing is never classified.
        async def never(self):
            return False

        self.session("p1")
        with patch.object(TmuxControlClient, "_server_is_gone", never), \
                patch.object(monitor_core, "_RECONNECT_BACKOFFS", (1.5, 0.2, 0.2, 0.2, 0.2)):
            b = self.started("p1")
            self.timeout_then(b, lambda: self.tmux("kill-server"))
            self.assertTrue(wait_for(lambda: b.state == TmuxControlState.FALLBACK))
        self.assertFalse(b.exit_seen, "control: FALLBACK without a signal was expected")

    def test_stalled_server_during_reconnect_is_not_a_shutdown(self):
        # The server stays frozen through every reconnect attempt: each
        # listing times out. That is a transport failure, never "no server".
        self.session("p1")
        b = self.started("p1")
        first = b._client
        pid = self.server_pid()
        os.kill(pid, signal.SIGSTOP)
        try:
            self.assertEqual(self.on_loop(b, first.check_project(), timeout=10),
                             "transport")
            self.assertTrue(wait_for(lambda: b.state == TmuxControlState.FALLBACK, 60),
                            f"state={b.state!r}")
            self.assertFalse(b.exit_seen, "a stalled server was read as a shutdown")
        finally:
            os.kill(pid, signal.SIGCONT)

    def test_control_reconnect_without_the_prior_identity_is_silent(self):
        # Pre-fix control: the reconnecting client is not told which project
        # session the last one served.
        class Forgetful(TmuxControlBackend):
            @property
            def _last_project_id(self):
                return None

            @_last_project_id.setter
            def _last_project_id(self, value):
                pass

        self.session("p1")
        self.session("keep")
        with patch.object(monitor_core, "_RECONNECT_BACKOFFS", (1.5, 0.2, 0.2, 0.2, 0.2)):
            b = Forgetful(session="p1", command_timeout=3.0)
            self._backends.append(b)
            self.assertTrue(b.start())
            self.timeout_then(b, lambda: self.tmux("kill-session", "-t", "=p1"))
            self.assertTrue(wait_for(lambda: b.state == TmuxControlState.FALLBACK))
        self.assertFalse(b.exit_seen,
                         "control: FALLBACK without a signal was expected")

    # -- stop during startup verification -----------------------------------

    def hold_verification(self):
        """Make `_verify_attach` wait forever; return an event set on entry."""
        entered = threading.Event()

        async def held(client):
            entered.set()
            await asyncio.Event().wait()

        p = patch.object(TmuxControlClient, "_verify_attach", held)
        p.start()
        self.addCleanup(p.stop)
        return entered

    def stop_during_reconnect(self, backend_cls):
        self.session("p2")
        b = backend_cls(session="p2", command_timeout=3.0)
        self._backends.append(b)
        self.assertTrue(b.start())
        first = b._client
        entered = self.hold_verification()
        first._proc.kill()
        self.assertTrue(entered.wait(DEADLINE), "the reconnect never reached verification")
        self.assertTrue(wait_for(lambda: self.control_sessions() == [HELPER], 5),
                        self.control_sessions())
        b.stop()
        time.sleep(0.8)
        return b

    def stop_during_initial_start(self, backend_cls):
        self.session("p2")
        entered = self.hold_verification()
        b = backend_cls(session="p2", command_timeout=3.0)
        self._backends.append(b)
        with patch.object(monitor_core, "_BACKEND_START_TIMEOUT", 1.0):
            started = b.start()     # times out, then stops itself
        self.assertFalse(started)
        self.assertTrue(entered.is_set())
        time.sleep(0.8)
        return b

    def test_stop_during_reconnect_leaves_nothing_attached(self):
        self.stop_during_reconnect(TmuxControlBackend)
        self.assertEqual(self.control_sessions(), [])
        self.assertNotIn(HELPER, self.sessions())

    def test_start_timeout_leaves_nothing_attached(self):
        self.stop_during_initial_start(TmuxControlBackend)
        self.assertEqual(self.control_sessions(), [])
        self.assertNotIn(HELPER, self.sessions())

    def old_backend(self):
        """Pre-fix control: no `_starting` reference, no abort on cancel."""

        class OldBackend(TmuxControlBackend):
            @property
            def _starting(self):
                return None

            @_starting.setter
            def _starting(self, value):
                pass

        p = patch.object(TmuxControlClient, "_abort_spawned", lambda self: None)
        p.start()
        self.addCleanup(p.stop)
        return OldBackend

    def test_control_cancelled_reconnect_leaks_its_candidate(self):
        self.stop_during_reconnect(self.old_backend())
        self.assertEqual(self.control_sessions(), [HELPER],
                         "control: the candidate was expected to stay attached")
        self.assertIn(HELPER, self.sessions())

    def test_control_timed_out_start_leaks_its_candidate(self):
        self.stop_during_initial_start(self.old_backend())
        self.assertEqual(self.control_sessions(), [HELPER],
                         "control: the candidate was expected to stay attached")
        self.assertIn(HELPER, self.sessions())


# ---------------------------------------------------------------------------
# A real terminal that lands in the helper is bounced out
# ---------------------------------------------------------------------------

class BounceTests(LiveCase):

    def setup_bounce(self, dod: str, others=()):
        self.session("s")
        for name in others:
            self.session(name)
        self.tmux("set-option", "-g", "detach-on-destroy", dod)
        b = self.started("s")
        ft = self.terminal("s")
        return b, ft

    def test_detach_on_destroy_off_moves_to_the_next_session(self):
        b, ft = self.setup_bounce("off", ["p2"])
        self.tmux("kill-session", "-t", "=s")
        self.assertEqual(self.place(ft), "p2")
        self.assertEqual(self.real_sessions(), ["p2"])
        # The backend served `s`, so its client left with it; with the
        # terminal bounced out nothing holds the helper, and it is gone. This
        # is the other half of the measured gap ("the helper never goes away").
        self.assertTrue(wait_for(lambda: b.state == TmuxControlState.FALLBACK))
        self.assertTrue(wait_for(lambda: HELPER not in self.sessions(), 5),
                        self.sessions())
        self.assertEqual(self.sessions(), ["p2"])

    def test_detach_on_destroy_off_next_session_by_name(self):
        b, ft = self.setup_bounce("off", ["p3", "p2"])
        self.tmux("kill-session", "-t", "=s")
        self.assertEqual(self.place(ft), "p2")

    def test_detach_on_destroy_off_alone_detaches(self):
        b, ft = self.setup_bounce("off")
        self.tmux("kill-session", "-t", "=s")
        self.assertEqual(self.place(ft), "DETACHED")
        # Nothing is left to hold the helper once the backend gives up.
        b.stop()
        self.assertTrue(wait_for(lambda: self.sessions() == [], 5), self.sessions())

    def test_control_without_the_hook_the_terminal_stays_in_the_helper(self):
        # Negative control: the measured gap. A helper without the bounce hook
        # keeps the terminal, and then never goes away.
        self.session("s")
        self.session("p2")
        self.tmux("set-option", "-g", "detach-on-destroy", "off")
        with patch.object(monitor_core, "AIT_CONTROL_BOUNCE_HOOK", "display-message -p x"):
            b = self.started("s")
        ft = self.terminal("s")
        self.tmux("kill-session", "-t", "=s")
        self.assertEqual(self.place(ft), HELPER)
        b.stop()
        time.sleep(0.6)
        self.assertIn(HELPER, self.sessions(),
                      "control: the terminal was expected to pin the helper")

    def test_detach_on_destroy_on(self):
        for others in (["p2"], []):
            with self.subTest(others=others):
                b, ft = self.setup_bounce("on", others)
                self.tmux("kill-session", "-t", "=s")
                self.assertEqual(self.place(ft), "DETACHED")
                b.stop()
                self.assertTrue(wait_for(lambda: HELPER not in self.sessions(), 5))
                self.assertEqual(self.sessions(), others)
                for name in others:
                    self.tmux("kill-session", "-t", f"={name}")

    def test_entering_the_helper_directly_is_bounced(self):
        # A user picking it in `prefix s`, or attaching to it by name.
        b, ft = self.setup_bounce("off", ["p2"])
        self.tmux("switch-client", "-c", self.terminal_name(), "-t", "=" + HELPER)
        self.assertEqual(self.place(ft), "p2")
        direct = FakeTerminal(self.tmux_argv, self.env, HELPER)
        self._terminals.append(direct)
        self.assertTrue(wait_for(lambda: len(self.real_sessions()) == 2, 5),
                        self.real_sessions())
        time.sleep(0.6)
        self.assertEqual(self.real_sessions(), ["p2", "p2"])

    def test_hook_starts_no_job_and_never_acts_late(self):
        b, ft = self.setup_bounce("off", ["p2", "p3"])
        hooks = self.hooks(self.session_id(HELPER))
        self.assertNotIn("run-shell", hooks)
        self.assertNotIn("$", hooks)
        # Bounced to p2, then moved on by the user: nothing moves it back.
        self.tmux("kill-session", "-t", "=s")
        self.assertEqual(self.place(ft), "p2")
        self.tmux("switch-client", "-c", self.terminal_name(), "-t", "=p3")
        self.assertEqual(self.place(ft, settle=1.5), "p3")

    def two_switches_in_one_list(self, hook):
        self.session("s")
        self.session("p2")
        self.session("p3")
        self.tmux("set-option", "-g", "detach-on-destroy", "off")
        with patch.object(monitor_core, "AIT_CONTROL_BOUNCE_HOOK", hook):
            self.started("s")
        ft = self.terminal("s")
        name = self.terminal_name()
        # tmux queues the hook behind the rest of this list, so it runs when
        # the terminal is already in p3.
        self.tmux("switch-client", "-c", name, "-t", "=" + HELPER, ";",
                  "switch-client", "-c", name, "-t", "=p3")
        return self.place(ft)

    def test_hook_does_not_act_on_a_terminal_that_already_left(self):
        self.assertEqual(self.two_switches_in_one_list(AIT_CONTROL_BOUNCE_HOOK), "p3")

    def test_control_unguarded_hook_moves_a_terminal_that_left(self):
        self.assertNotEqual(self.two_switches_in_one_list(UNGUARDED_HOOK), "p3",
                            "control: the unguarded hook was expected to act late")

    # -- the bounce does not depend on the checkout --------------------------

    RUNNER = (
        "import sys\n"
        "sys.path[:0] = [sys.argv[1], sys.argv[1] + '/lib']\n"
        "from monitor.monitor_core import TmuxControlBackend\n"
        "b = TmuxControlBackend(session=sys.argv[2])\n"
        "print('READY' if b.start() else 'FAILED', flush=True)\n"
        "sys.stdin.read()\n"
        "b.stop()\n"
    )

    def framework_copy(self) -> Path:
        copy = self.base / "fw" / ".aitask-scripts"
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for sub in ("lib", "monitor"):
            shutil.copytree(SCRIPTS / sub, copy / sub, ignore=ignore)
        return copy

    def backend_from_copy(self, copy: Path, session: str) -> subprocess.Popen:
        proc = subprocess.Popen(
            [sys.executable, "-c", self.RUNNER, str(copy), session], env=self.env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, cwd=str(self.base))
        self._procs.append(proc)
        self.assertEqual(proc.stdout.readline().strip(), "READY")
        return proc

    def check_bounce_survives(self, dispose):
        self.session("s")
        self.session("p2")
        self.tmux("set-option", "-g", "detach-on-destroy", "off")
        copy = self.framework_copy()
        proc = self.backend_from_copy(copy, "s")
        self.assertEqual(self.control_sessions(), [HELPER])
        ft = self.terminal("s")
        # The checkout that installed the hook goes away; nobody else joins.
        dispose(copy)
        self.assertFalse(copy.exists())
        self.tmux("kill-session", "-t", "=s")
        self.assertEqual(self.place(ft), "p2")
        proc.terminate()
        proc.wait(10)
        self.assertTrue(wait_for(lambda: HELPER not in self.sessions(), 5),
                        self.sessions())

    def test_bounce_survives_a_moved_checkout(self):
        self.check_bounce_survives(lambda c: c.parent.rename(self.base / "fw_moved"))

    def test_bounce_survives_a_deleted_checkout(self):
        self.check_bounce_survives(lambda c: shutil.rmtree(c.parent))

    def test_control_hook_that_runs_a_checkout_script_strands_the_terminal(self):
        # Pre-fix control: an earlier design ran a script from the checkout.
        self.session("s")
        self.session("p2")
        self.tmux("set-option", "-g", "detach-on-destroy", "off")
        scripts = self.base / "fw2"
        scripts.mkdir()
        script = scripts / "bounce.sh"
        script.write_text("#!/bin/sh\ntmux switch-client -c \"$1\" -t =p2\n")
        script.chmod(0o755)
        hook = f"run-shell -b '{script} #{{hook_client}}'"
        with patch.object(monitor_core, "AIT_CONTROL_BOUNCE_HOOK", hook):
            b = self.started("s")
        ft = self.terminal("s")
        shutil.rmtree(scripts)
        self.tmux("kill-session", "-t", "=s")
        self.assertEqual(self.place(ft), HELPER,
                         "control: the script hook was expected to fail")
        b.stop()
        time.sleep(0.6)
        self.assertIn(HELPER, self.sessions())


if __name__ == "__main__":
    unittest.main()
