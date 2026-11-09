"""The monitor status server's process lifecycle against a REAL tmux server (t2037_1).

Each test gets its own isolated tmux server (`-L ait_t2037_1_<pid>_<n>` under a
scratch `TMUX_TMPDIR`) and a scratch `XDG_RUNTIME_DIR`, `HOME` and marks file,
all under one short scratch directory (AF_UNIX paths are short). The server is
started the way clients start it — the `ensure` CLI in a subprocess — so the
lock, the detached spawn, the socket key and the exit paths are the shipped
ones. Covered:

- single start under eight concurrent `ensure` calls;
- stale-socket recovery; per-version isolation; idle exit;
- per-session `tmux.monitor` config (agent prefixes, idle threshold);
- exit when the tmux server goes away (`%exit`);
- destroying the served session, under both `detach-on-destroy` settings,
  restarts the control client on the live session (t2245);
- [record_live_server_stream] the real producer's stream, recorded and checked.

Skip vs fail: `SkipTest` only when `tmux` is missing. Everything after the tmux
server is up is the regression this file exists to catch and fails.

Cleanup is ownership-checked: only server pids learned from this test's own
`ensure` output whose command line names this test's scratch socket are
signalled, and the tmux server is killed by its explicit `-L` name only.

Run:
  python3 tests/test_monitor_status_server_live.py
"""
from __future__ import annotations

import asyncio
import fcntl
import itertools
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

from monitor import status_protocol as sp  # noqa: E402
from monitor import status_recording as sr  # noqa: E402

SERVER = SCRIPTS / "monitor" / "status_server.py"
DEADLINE = 20.0
_COUNTER = itertools.count()
TIMING = ("ts", "idle_seconds", "last_change")


def _short_tmp() -> str:
    """A short scratch dir: AF_UNIX paths (ours and tmux's) are ~104 bytes."""
    for base in ("/tmp", None):
        try:
            return tempfile.mkdtemp(prefix="ait21_", dir=base)
        except OSError:
            continue
    raise unittest.SkipTest("no writable temp directory")


def _cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
    except OSError:
        out = subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                             capture_output=True, text=True)
        return out.stdout


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A zombie still answers kill(0); treat it as gone.
    try:
        state = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0]
        return state != "Z"
    except (OSError, IndexError):
        return True


class Client:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    @classmethod
    async def open(cls, path):
        r, w = await asyncio.open_unix_connection(str(path), limit=sp.MAX_SERVER_LINE_BYTES)
        return cls(r, w)

    async def send(self, msg):
        self.writer.write(sp.encode(msg, direction=sp.CLIENT))
        await self.writer.drain()

    async def recv(self, timeout=DEADLINE):
        line = await asyncio.wait_for(sp.read_line(self.reader), timeout)
        return None if line is None else sp.decode(line, direction=sp.SERVER)

    async def hello(self, version):
        await self.send({"type": "hello", "proto": sp.PROTO, "version": version,
                         "client": {"kind": "test"}})
        return await self.recv()

    async def until(self, kind, **match):
        while True:
            msg = await self.recv()
            if msg is None:
                raise AssertionError(f"stream ended waiting for {kind}")
            if msg["type"] == kind and all(msg.get(k) == v for k, v in match.items()):
                return msg

    async def close(self):
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


class LiveCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if shutil.which("tmux") is None:
            raise unittest.SkipTest("tmux not installed")

    def setUp(self):
        self.base = Path(_short_tmp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.sock_name = f"ait_t2037_1_{os.getpid()}_{next(_COUNTER)}"
        for sub in ("tt", "run", "home"):
            (self.base / sub).mkdir(mode=0o700)
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        env.update({
            "AITASKS_TMUX_SOCKET": self.sock_name,
            "TMUX_TMPDIR": str(self.base / "tt"),
            "XDG_RUNTIME_DIR": str(self.base / "run"),
            "HOME": str(self.base / "home"),
            "AITASKS_AGENT_MARKS_FILE": str(self.base / "marks.json"),
        })
        self.env = env
        self.pids: set = set()
        self.addCleanup(self._cleanup)

    # -- helpers -------------------------------------------------------------

    def tmux(self, *args, check=True) -> str:
        out = subprocess.run(["tmux", "-L", self.sock_name, *args], env=self.env,
                             capture_output=True, text=True)
        if check and out.returncode != 0:
            raise AssertionError(f"tmux {args} failed: {out.stderr}")
        return out.stdout

    def project(self, name: str, monitor_yaml: str = "    refresh_seconds: 60\n") -> Path:
        root = self.base / name
        (root / "aitasks" / "metadata").mkdir(parents=True)
        (root / "aitasks" / "metadata" / "project_config.yaml").write_text(
            "tmux:\n  monitor:\n" + monitor_yaml)
        return root

    def session(self, name: str, root: Path, window: str, cmd: str = "sleep 3600") -> str:
        self.tmux("new-session", "-d", "-s", name, "-x", "120", "-y", "30",
                  "-n", window, "-c", str(root), cmd)
        return self.tmux("display-message", "-p", "-t", f"={name}:", "#{pane_id}").strip()

    def window(self, session: str, root: Path, window: str, cmd: str = "sleep 3600") -> str:
        return self.tmux("new-window", "-d", "-P", "-F", "#{pane_id}", "-t", f"={session}:",
                         "-n", window, "-c", str(root), cmd).strip()

    def server_cli(self, *args, cwd=None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SERVER), *args], env=self.env,
                              cwd=str(cwd or self.base), capture_output=True, text=True,
                              timeout=DEADLINE + 10)

    def ensure(self, *args, cwd=None) -> tuple[str, str, int | None]:
        out = self.server_cli("ensure", "--deadline", str(DEADLINE), *args, cwd=cwd)
        line = out.stdout.strip()
        state, _, rest = line.partition(":")
        if state == "UNAVAILABLE":
            raise AssertionError(f"ensure: {line}\n{out.stderr}")
        sock, _, pid = rest.rpartition("|")
        pid_i = int(pid) if pid else None
        if pid_i:
            self.pids.add(pid_i)
        return state, sock, pid_i

    def wait_gone(self, pid: int, timeout: float = DEADLINE) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if not _alive(pid):
                return True
            time.sleep(0.1)
        return False

    def _cleanup(self):
        for pid in self.pids:
            if _alive(pid) and str(self.base) in _cmdline(pid):
                with __import__("contextlib").suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGTERM)
                if not self.wait_gone(pid, 5):
                    with __import__("contextlib").suppress(ProcessLookupError):
                        os.kill(pid, signal.SIGKILL)
                    self.wait_gone(pid, 5)
        subprocess.run(["tmux", "-L", self.sock_name, "kill-server"], env=self.env,
                       capture_output=True)

    @staticmethod
    def server_log(sock: str) -> str:
        return Path(sock).with_name(Path(sock).stem + ".log").read_text(errors="replace")

    @staticmethod
    def lock_is_held(sock: str) -> bool:
        lock = Path(sock).with_name(Path(sock).stem + ".lock")
        fd = os.open(lock, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        finally:
            os.close(fd)
        return False

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, DEADLINE * 3))


# ---------------------------------------------------------------------------

class EnsureTests(LiveCase):

    def setUp(self):
        super().setUp()
        self.root = self.project("proj")
        self.session("s1", self.root, "agent-pick-1")

    def test_single_start_under_concurrent_ensure(self):
        procs = [subprocess.Popen(
            [sys.executable, str(SERVER), "ensure", "--version", "conc",
             "--deadline", str(DEADLINE)],
            env=self.env, cwd=str(self.root), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True) for _ in range(8)]
        lines = []
        for p in procs:
            out, err = p.communicate(timeout=DEADLINE + 10)
            lines.append(out.strip())
        states, socks, pids = [], set(), set()
        for line in lines:
            state, _, rest = line.partition(":")
            self.assertIn(state, ("STARTED", "RUNNING"), line)
            sock, _, pid = rest.rpartition("|")
            states.append(state)
            socks.add(sock)
            pids.add(int(pid))
        self.pids |= pids
        self.assertEqual(states.count("STARTED"), 1, lines)
        self.assertEqual(len(socks), 1, lines)
        self.assertEqual(len(pids), 1, f"more than one server answered: {lines}")
        self.assertTrue(self.lock_is_held(next(iter(socks))))

    def test_stale_socket_is_replaced(self):
        out = self.server_cli("path", "--version", "stale")
        path = out.stdout.strip()
        Path(path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(path)
        stale.close()                      # bound, never listened, never unlinked
        self.assertTrue(os.path.exists(path))
        state, sock, pid = self.ensure("--version", "stale")
        self.assertEqual((state, sock), ("STARTED", path))
        answer = sr_probe(sock, "stale")
        self.assertEqual(answer["server"]["pid"], pid)

    def test_versions_are_isolated(self):
        _, sock_a, pid_a = self.ensure("--version", "va")
        _, sock_b, pid_b = self.ensure("--version", "vb")
        self.assertNotEqual(sock_a, sock_b)
        self.assertNotEqual(pid_a, pid_b)
        err = sr_probe(sock_a, "vb")
        self.assertEqual((err["type"], err["code"]), ("error", "version_mismatch"))

    def test_idle_exit(self):
        state, sock, pid = self.ensure("--version", "idle", "--grace", "1")
        self.assertEqual(state, "STARTED")
        self.assertTrue(self.wait_gone(pid), "the idle server did not exit")
        self.assertFalse(os.path.exists(sock))
        self.assertFalse(self.lock_is_held(sock))
        self.assertIn("EXIT:idle", self.server_log(sock))


class RestartTests(LiveCase):
    """`status_server.py restart` / `status` (t2246): verified SIGTERM of THIS tmux
    server's server for one version, then a fresh one for the SAME version."""

    FAKE = REPO_ROOT / "tests" / "lib" / "fake_status_server.py"

    def setUp(self):
        super().setUp()
        self.root = self.project("proj")
        self.session("s1", self.root, "agent-pick-1")

    def other_key_server(self, version: str) -> tuple[subprocess.Popen, str]:
        """A same-version server of ANOTHER tmux server, in the shared runtime dir."""
        from monitor import status_paths as spaths
        run = self.base / "run" / "aitasks"
        run.mkdir(mode=0o700, parents=True, exist_ok=True)
        sock = str(run / f"monitor-{spaths.tmux_key('/elsewhere/tmux-0/default')}-{version}.sock")
        proc = subprocess.Popen([sys.executable, str(self.FAKE), "serve", "--socket", sock],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(lambda: (proc.poll() is None and proc.kill(), proc.wait(5),
                                 proc.stdout.close()))
        self.assertEqual(proc.stdout.readline().strip(), "READY")
        return proc, sock

    def restart(self, version: str) -> tuple[subprocess.CompletedProcess, list]:
        out = self.server_cli("restart", "--version", version, "--deadline", str(DEADLINE),
                              cwd=self.root)
        return out, out.stdout.strip().splitlines()

    def test_restart_replaces_this_tmux_servers_server_only(self):
        _, sock, p1 = self.ensure("--version", "rst", cwd=self.root)
        other, other_sock = self.other_key_server("rst")

        status = self.server_cli("status").stdout
        self.assertIn(f"SERVER:{sock}|pid={p1}|", status)
        self.assertIn(f"|version=rst|script={SERVER}", status)
        self.assertNotIn(other_sock, status, "status listed another tmux server's socket")

        out, lines = self.restart("rst")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(lines[0], f"RETIRED:{sock}|pid={p1}")
        self.assertTrue(self.wait_gone(p1, 5), "the retired server is still alive")
        state, _, rest = lines[1].partition(":")
        new_sock, _, p2 = rest.rpartition("|")
        p2 = int(p2)
        self.pids.add(p2)
        self.assertEqual((state, new_sock), ("STARTED", sock), lines)
        self.assertNotEqual(p2, p1)
        self.assertEqual(lines[2], f"REPLACEMENT:{sock}|pid={p2}|version=rst")
        answer = sr_probe(sock, "rst")
        self.assertEqual((answer["version"], answer["server"]["pid"]), ("rst", p2))
        self.assertIsNone(other.poll(), "another tmux server's server was stopped")

    def test_restart_without_a_running_server_starts_one(self):
        out, lines = self.restart("fresh")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue(lines[0].startswith("NO_SERVER:"), lines)
        sock = lines[0].partition(":")[2]
        state, _, rest = lines[1].partition(":")
        p2 = int(rest.rpartition("|")[2])
        self.pids.add(p2)
        self.assertEqual(state, "STARTED")
        self.assertEqual(lines[2], f"REPLACEMENT:{sock}|pid={p2}|version=fresh")


class PerSessionConfigTests(LiveCase):

    def test_each_session_uses_its_own_project_config(self):
        root_a = self.project("pa", "    refresh_seconds: 60\n"
                                    "    agent_window_prefixes: [agent-, work-]\n"
                                    "    idle_threshold_seconds: 1\n")
        root_b = self.project("pb")
        self.session("sa", root_a, "agent-a1")
        self.window("sa", root_a, "work-x")
        self.session("sb", root_b, "agent-b1")
        self.window("sb", root_b, "work-y")
        _, sock, _ = self.ensure("--version", "cfg", cwd=root_a)

        async def go():
            c = await Client.open(sock)
            self.assertEqual((await c.hello("cfg"))["type"], "welcome")
            await c.send({"type": "subscribe"})
            state = sp.StreamState()
            state.apply(await c.until("snapshot"))
            await asyncio.sleep(1.8)
            await c.send({"type": "refresh", "id": "r"})
            while True:
                msg = await c.recv()
                if msg["type"] == "delta":
                    state.apply(msg)
                elif msg["type"] == "result" and msg.get("id") == "r":
                    break
            await c.close()
            return {r["pane"]["window_name"]: r for r in state.records().values()}

        by_window = self.run_async(go())
        self.assertEqual(set(by_window) >= {"agent-a1", "work-x", "agent-b1", "work-y"}, True,
                         sorted(by_window))
        self.assertEqual(by_window["work-x"]["pane"]["category"], "agent")
        self.assertEqual(by_window["work-y"]["pane"]["category"], "other")
        self.assertTrue(by_window["agent-a1"]["is_idle"], "1 s threshold not applied in sa")
        self.assertFalse(by_window["agent-b1"]["is_idle"], "sb used sa's threshold")


class TmuxExitTests(LiveCase):

    def test_server_exits_when_tmux_goes_away(self):
        root = self.project("proj")
        self.session("s1", root, "agent-pick-1")
        _, sock, pid = self.ensure("--version", "ex", "--grace", "120")

        async def connected():
            c = await Client.open(sock)
            await c.hello("ex")
            await c.send({"type": "subscribe"})
            snap = await c.until("snapshot")
            state = snap["control_state"]
            end = time.monotonic() + DEADLINE
            while state != "connected" and time.monotonic() < end:
                await c.send({"type": "refresh", "id": "r"})
                while True:
                    msg = await c.recv()
                    if msg["type"] == "delta" and "control_state" in msg:
                        state = msg["control_state"]
                    if msg["type"] == "result":
                        break
                await asyncio.sleep(0.2)
            await c.close()
            return state

        self.assertEqual(self.run_async(connected()), "connected")
        self.tmux("kill-server")
        self.assertTrue(self.wait_gone(pid, 10), "the server outlived its tmux server")
        self.assertFalse(os.path.exists(sock))
        self.assertIn("EXIT:exit_seen", self.server_log(sock),
                      "the server exited, but not through the %exit path")

    def control_clients(self) -> list[str]:
        out = self.tmux("list-clients", "-F", "#{client_control_mode} #{session_name}",
                        check=False)
        return [ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("1 ")]

    def test_session_switch_restarts_the_control_client(self):
        # t2245: under `detach-on-destroy off` destroying the served session
        # moves the control client onto another session instead of sending
        # %exit. The server must restart its client, not keep serving the
        # switched one.
        self._served_session_destroyed("off")

    def test_session_destroy_restarts_on_a_live_session(self):
        # The %exit route (`detach-on-destroy on`): the restart must pick a live
        # session, not the destroyed one the last tick's mapping still lists.
        self._served_session_destroyed("on")

    def _served_session_destroyed(self, detach_on_destroy: str):
        self.session("s1", self.project("pa"), "agent-pick-1")
        self.session("s2", self.project("pb"), "agent-pick-2")
        self.tmux("set-option", "-g", "detach-on-destroy", detach_on_destroy)
        _, sock, pid = self.ensure("--version", "sw", "--grace", "120")

        async def control_state(c):
            await c.send({"type": "refresh", "id": "r"})
            state = None
            while True:
                msg = await c.recv()
                if msg["type"] == "delta" and "control_state" in msg:
                    state = msg["control_state"]
                if msg["type"] == "result":
                    return state

        async def go():
            c = await Client.open(sock)
            await c.hello("sw")
            await c.send({"type": "subscribe"})
            state = (await c.until("snapshot"))["control_state"]
            end = time.monotonic() + DEADLINE
            while state != "connected" and time.monotonic() < end:
                state = await control_state(c) or state
                await asyncio.sleep(0.2)
            self.assertEqual(state, "connected")
            served = self.control_clients()
            self.assertEqual(len(served), 1, served)
            self.tmux("kill-session", "-t", f"={served[0]}")
            end = time.monotonic() + DEADLINE
            while ("restarting the control client" not in self.server_log(sock)
                   and time.monotonic() < end):
                await asyncio.sleep(0.2)
                await control_state(c)
            await c.close()
            return served[0]

        killed = self.run_async(go())
        log = self.server_log(sock)
        self.assertIn("restarting the control client", log,
                      "the destroyed session was not treated as the session going away")
        self.assertNotIn("subprocess fallback", log,
                         "the restart did not reach the live session")
        self.assertNotIn("EXIT:", log)
        self.assertTrue(_alive(pid), "the server exited on a session switch")
        survivor = ({"s1", "s2"} - {killed}).pop()
        end = time.monotonic() + DEADLINE
        while self.control_clients() != [survivor] and time.monotonic() < end:
            time.sleep(0.2)
        self.assertEqual(self.control_clients(), [survivor],
                         "the switched control client was left attached, or none restarted")


class LiveStreamTests(LiveCase):
    """[record_live_server_stream] The real producer's tick-to-tick stream."""

    def test_live_stream_records_and_checks(self):
        root = self.project("proj")
        printer = "sh -c 'i=0; while :; do i=$((i+1)); echo line $i; sleep 0.2; done'"
        p1 = self.session("sr", root, "agent-r1", printer)
        p2 = self.window("sr", root, "agent-r2")
        version = sr.framework_version()
        _, sock, _ = self.ensure(cwd=root)
        out = self.base / "live.jsonl"

        async def drive():
            recording = asyncio.create_task(sr.record_connect(sock, out, max_deltas=5))
            await asyncio.sleep(0.5)
            d = await Client.open(sock)
            await d.hello(version)

            async def refresh():
                await d.send({"type": "refresh", "id": "r"})
                await d.until("result", id="r")

            await refresh()                                     # content changes
            shadow = self.tmux("split-window", "-d", "-P", "-F", "#{pane_id}",
                               "-t", p2, "-c", str(root), "sleep 3600").strip()
            self.tmux("set-option", "-p", "-t", shadow, "@aitask_shadow_target", p2)
            await refresh()                                     # a shadow binds
            self.window("sr", root, "agent-r3")
            await refresh()                                     # a pane appears
            self.tmux("kill-pane", "-t", p1)
            await refresh()                                     # a pane disappears
            await refresh()
            result = await asyncio.wait_for(recording, DEADLINE)
            await d.send({"type": "subscribe", "id": "fresh"})
            fresh = await d.until("snapshot", id="fresh")
            await d.close()
            return result, fresh

        result, fresh = self.run_async(drive())
        self.assertTrue(result.published, result.reason)
        sr.check_recording(out)
        rec = sr.read_recording(out)
        initial = set(rec.snapshot["panes"])
        deltas = rec.deltas
        self.assertTrue(any(p1 in m.get("removed", []) for m in deltas), "no removal recorded")
        self.assertTrue(any(pid not in initial and "content" in r
                            for m in deltas for pid, r in m.get("panes", {}).items()),
                        "no new full record recorded")
        self.assertTrue(any(p2 in m.get("shadows", {}) for m in deltas), "no shadow recorded")

        state = sp.StreamState()
        for msg in rec.messages[1:]:
            state.apply(msg)
        # refresh_seconds is 60, so no scheduled tick lands between the
        # recording's last delta and the fresh subscribe.
        self.assertEqual(fresh["gen"], state.gen)

        def strip(records):
            return {k: {m: v for m, v in r.items() if m not in TIMING}
                    for k, r in records.items()}
        self.assertEqual(strip(state.records()), strip(fresh["panes"]))
        self.assertEqual(strip(state.shadow_records()), strip(fresh["shadows"]))
        self.assertEqual(sorted(state.completed), fresh["completed"])


def sr_probe(sock: str, version: str) -> dict:
    from monitor import status_server as ss
    answer = ss.probe(sock, version, timeout=5.0)
    if answer is None:
        raise AssertionError(f"nothing answered on {sock}")
    return answer


if __name__ == "__main__":
    unittest.main(verbosity=2)
