"""The sitrep window spawn and its one-per-root guard (t2175_4), through mocks.

`monitor_core.spawn_sitrep` is driven with `launch_window_pane`,
`maybe_spawn_minimonitor`, `resolve_dry_run_command` and
`switch_to_pane_anywhere` patched on `monitor_core` (where the body lives). The
duplicate lookup's parsing, the shared helper rule (`pane_is_helper`), the stamp
and the per-server lock are real. The fake gateway renders `list-panes` rows from
the REQUESTED `-F` format, so a field added to the format cannot shift a
neighbour's value into the wrong slot.

What only a live tmux server can answer — the window really created, the stamp
on it, two concurrent spawns, a linked worktree, a frozen pane beside its
companion — is `tests/test_sitrep_window_live.sh`.

Run: python3 -m unittest tests.test_sitrep_window
"""

from __future__ import annotations

import fcntl
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_launch_utils as alu  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from tmux_socket_containment import TmuxSocketContainmentMixin  # noqa: E402

SITREP_SH = REPO_ROOT / ".aitask-scripts" / "aitask_sitrep.sh"

_SPEC_KEYS = {
    "#{pane_id}": "id",
    "#{pane_pid}": "pid",
    f"#{{{mc.SHADOW_TARGET_OPTION}}}": "shadow",
    f"#{{{mc.MONITOR_KIND_OPTION}}}": "kind",
    f"#{{{mc.FROZEN_OPTION}}}": "frozen",
    "#{pane_dead}": "dead",
    f"#{{{mc.SCRATCHPAD_TARGET_OPTION}}}": "scratch",
    f"#{{{mc.SITREP_ROOT_OPTION}}}": "stamp",
    f"#{{{mc.SITREP_TUI_ROOT_OPTION}}}": "tui",
    "#{window_name}": "window",
    "#{pane_current_path}": "cwd",
}

#: A pid that is NOT a companion process (this test runner).
LIVE_PID = os.getpid()


def pane(pid=LIVE_PID, **kw) -> dict:
    row = {"pid": str(pid)}
    row.update(kw)
    return row


def render(fmt: str, panes: list[dict]) -> str:
    specs = fmt.split("\t")
    return "".join(
        "\t".join(str(p.get(_SPEC_KEYS.get(s, ""), "")) for s in specs) + "\n"
        for p in panes)


def canon_identity(path: str) -> str:
    return path


#: A generous ceiling, far above interpreter start-up on a loaded box. It turns a
#: wedged stand-in into a failure instead of a hang, and it is never a sleep.
READY_DEADLINE_S = 20.0


def await_announcement(proc, deadline_s: float, token: bytes = b"ready\n") -> str | None:
    """Wait, bounded, for ``proc`` to write ``token`` on its stdout pipe.

    None on success, else why not. Three exits: the token arrives, EOF (the
    child exited), or the deadline passes (the child is alive but stopped or
    wedged before writing). A bare ``readline()`` only ends on the first two, so
    it hangs on the third. Raw ``os.read`` on the fd, never the buffered reader,
    so ``select`` never misses bytes held in a userspace buffer.
    """
    fd, buf = proc.stdout.fileno(), b""
    deadline = time.monotonic() + deadline_s
    while b"\n" not in buf:
        left = deadline - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            return (f"stand-in did not announce itself within {deadline_s}s "
                    f"(read so far: {buf!r})")
        chunk = os.read(fd, 64)
        if not chunk:
            return f"stand-in exited before announcing itself (read so far: {buf!r})"
        buf += chunk
    return None if buf == token else f"unexpected announcement {buf!r}"


class FakeMon:
    """`monitor.tmux_run` over a scripted server.

    ``list-panes -a`` renders ``panes``; a window-scoped ``list-panes -t <pane>``
    renders ``window_panes`` (default: ``panes``). ``places`` answers the sitrep
    place read per pane, ``active`` the active-pane read per window id (a list
    is consumed one answer per read, the last one repeating).
    """

    def __init__(self, panes=(), *, list_rc=0, socket="", set_rc=0,
                 windows=("zsh",), window_rc=0, window_panes=None,
                 window_list_rc=0, places=None, active=None, join_rc=0,
                 select_rc=0, pane_windows=None):
        self.panes = list(panes)
        self.list_rc = list_rc
        self.socket = socket
        self.set_rc = set_rc
        self.windows = list(windows)
        self.window_rc = window_rc
        self.window_panes = window_panes
        self.window_list_rc = window_list_rc
        self.places = places or {}
        self.active = {k: (list(v) if isinstance(v, list) else [v])
                       for k, v in (active or {}).items()}
        self.join_rc = join_rc
        self.select_rc = select_rc
        self.pane_windows = pane_windows or {}
        self.calls: list[list[str]] = []
        self.stamps: dict[tuple[str, str], str] = {}
        self.killed: list[str] = []

    def tmux_run(self, args, timeout=5.0):
        self.calls.append(list(args))
        verb = args[0]
        if verb == "list-panes":
            fmt = args[args.index("-F") + 1]
            if "-a" in args:
                if self.list_rc != 0:
                    return self.list_rc, ""
                return 0, render(fmt, self.panes)
            if self.window_list_rc != 0:
                return self.window_list_rc, ""
            rows = self.panes if self.window_panes is None else self.window_panes
            return 0, render(fmt, rows)
        if verb == "display-message":
            target = args[args.index("-t") + 1]
            if args[-1] == "#{socket_path}":
                return 0, self.socket + "\n"
            if args[-1] == mc._SITREP_PLACE_FORMAT:
                place = self.places.get(target)
                return (0, place + "\n") if place else (1, "")
            if args[-1] == "#{pane_id}\t#{window_id}":
                w = self.pane_windows.get(target)
                return (0, f"{target}\t{w}\n") if w else (1, "")
            if target in self.active:
                answers = self.active[target]
                answer = answers.pop(0) if len(answers) > 1 else answers[0]
                return (0, answer + "\n") if answer else (1, "")
            # _probe_pane: the pane is live unless it was killed.
            return 0, ("" if target in self.killed else target) + "\n"
        if verb == "list-windows":
            return self.window_rc, "\n".join(self.windows) + "\n"
        if verb == "set-option":
            if self.set_rc == 0:
                self.stamps[(args[3], args[4])] = args[5]
            return self.set_rc, ""
        if verb == "kill-pane":
            self.killed.append(args[args.index("-t") + 1])
            return 0, ""
        if verb == "join-pane":
            return self.join_rc, ""
        if verb == "select-pane":
            return self.select_rc, ""
        return 1, ""

    def verbs(self) -> list[str]:
        return [c[0] for c in self.calls]

    def calls_of(self, verb: str) -> list[list[str]]:
        return [c for c in self.calls if c[0] == verb]


class MatcherTests(unittest.TestCase):
    ROOT = "/repo"

    def match(self, panes, root=ROOT, canon=canon_identity):
        return mc.match_sitrep_pane(render(mc.SITREP_PANE_FORMAT, panes), root, canon)

    def test_stamp_for_the_root_matches(self):
        self.assertEqual(self.match([pane(id="%5", stamp=self.ROOT, window="w")]), "%5")

    def test_stamp_for_another_root_does_not(self):
        self.assertIsNone(self.match([pane(id="%5", stamp="/other", window="agent-sitrep",
                                           cwd=self.ROOT)]))

    def test_frozen_and_dead_panes_never_match(self):
        self.assertIsNone(self.match([pane(id="%5", stamp=self.ROOT, frozen="rec1")]))
        self.assertIsNone(self.match([pane(id="%5", stamp=self.ROOT, dead="1")]))

    def test_name_fallback(self):
        self.assertEqual(self.match([pane(id="%7", window="agent-sitrep", cwd=self.ROOT)]), "%7")
        self.assertEqual(self.match([pane(id="%7", window="agent-sitrep-3", cwd=self.ROOT)]), "%7")
        self.assertIsNone(self.match([pane(id="%7", window="agent-sitrep", cwd="/other")]))
        # canon maps a worktree path to its main root
        self.assertEqual(self.match([pane(id="%7", window="agent-sitrep", cwd="/repo/aiwork/t1")],
                                    canon=lambda p: "/repo"), "%7")

    def test_window_name_near_misses(self):
        for win in ("agent-sitrepx", "agent-pick-sitrep", "agent-sitrep-0", "sitrep"):
            self.assertIsNone(self.match([pane(id="%7", window=win, cwd=self.ROOT)]), win)

    def test_malformed_rows_are_skipped(self):
        out = "garbage\n%5\t1\n\n" + render(mc.SITREP_PANE_FORMAT,
                                             [pane(id="nope", stamp=self.ROOT),
                                              pane(id="%6", pid="x", stamp=self.ROOT)])
        self.assertIsNone(mc.match_sitrep_pane(out, self.ROOT, canon_identity))

    def test_cwd_with_a_tab_is_data(self):
        self.assertEqual(self.match([pane(id="%7", window="agent-sitrep", cwd="/re\tpo")],
                                    root="/re\tpo"), "%7")

    # --- the sitrep window's own companion -------------------------------------

    def test_frozen_sitrep_beside_its_live_companion_does_not_match(self):
        companion = pane(id="%9", kind=f"minimonitor:{LIVE_PID}", window="agent-sitrep",
                         cwd=self.ROOT)
        frozen_agent = pane(id="%8", stamp=self.ROOT, frozen="rec1", window="agent-sitrep",
                            cwd=self.ROOT)
        self.assertIsNone(self.match([companion, frozen_agent]))
        self.assertIsNone(self.match([frozen_agent, companion]))

    def spawn_standin(self, code: str):
        """A real child running ``code`` with argv ``minimonitor``, reaped at cleanup."""
        proc = subprocess.Popen([sys.executable, "-c", code, "minimonitor"],
                                stdout=subprocess.PIPE)
        self.addCleanup(proc.stdout.close)   # LIFO: runs last
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc

    def alarm_guard(self, seconds: int):
        """Fail, rather than hang, if a blocking read outlives ``seconds``."""
        def on_alarm(signum, frame):
            raise AssertionError(f"blocked for more than {seconds}s")
        previous = signal.signal(signal.SIGALRM, on_alarm)
        self.addCleanup(signal.signal, signal.SIGALRM, previous)
        self.addCleanup(signal.alarm, 0)
        signal.alarm(seconds)

    def test_booting_companion_without_a_marker_does_not_match(self):
        """No marker yet: the cmdline fallback of the shared rule classifies it.

        `Popen` returning does not mean the child's new argv is readable: the
        parent resumes mid-exec, while `/proc/<pid>/cmdline` is still empty or
        the parent's argv (t2220). The child announces itself from its own Python
        code, which runs only after exec has completed, so the cmdline rung reads
        the real `minimonitor` argv rather than racing the exec.
        """
        proc = self.spawn_standin(
            "import time; print('ready', flush=True); time.sleep(30)")
        problem = await_announcement(proc, READY_DEADLINE_S)
        if problem:
            self.fail(problem)
        companion = pane(id="%9", pid=proc.pid, window="agent-sitrep", cwd=self.ROOT)
        self.assertIsNone(self.match([companion]))

    def test_await_announcement_is_bounded_for_a_stopped_child(self):
        """Alive but stopped before writing: the deadline ends the wait, not EOF."""
        self.alarm_guard(10)
        proc = self.spawn_standin(
            "import os, signal; os.kill(os.getpid(), signal.SIGSTOP); "
            "print('ready', flush=True)")
        started = time.monotonic()
        problem = await_announcement(proc, 0.5)
        self.assertLess(time.monotonic() - started, 5.0)
        self.assertIn("did not announce itself", problem or "")

    def test_await_announcement_reports_a_child_that_exits_silently(self):
        self.alarm_guard(10)
        proc = self.spawn_standin("pass")
        problem = await_announcement(proc, READY_DEADLINE_S)
        self.assertIn("exited before announcing itself", problem or "")

    def test_live_stamped_sitrep_listed_after_its_companion(self):
        companion = pane(id="%9", kind=f"minimonitor:{LIVE_PID}", window="agent-sitrep",
                         cwd=self.ROOT)
        agent = pane(id="%8", stamp=self.ROOT, window="agent-sitrep", cwd=self.ROOT)
        self.assertEqual(self.match([companion, agent]), "%8")

    def test_bound_helpers_never_match(self):
        for kw in ({"shadow": "%1"}, {"scratch": "%1"}):
            self.assertIsNone(self.match([pane(id="%9", window="agent-sitrep", cwd=self.ROOT,
                                               **kw)]), kw)

    # --- stamp precedence (tells stamp-first from single-pass) -----------------

    def test_stamp_wins_over_an_earlier_fallback_candidate(self):
        candidate = pane(id="%3", window="agent-sitrep", cwd=self.ROOT)
        stamped = pane(id="%8", stamp=self.ROOT, window="agent-sitrep-2", cwd=self.ROOT)
        self.assertEqual(self.match([candidate, stamped]), "%8")
        self.assertEqual(self.match([stamped, candidate]), "%8")


class ClassifyParityTests(unittest.TestCase):
    """`classify_window_panes` keeps its verdicts after the `pane_is_helper` lift."""

    def test_classify_uses_the_shared_rule(self):
        out = render(mc.FROZEN_AWARE_PANE_FORMAT, [
            pane(id="%1"),
            pane(id="%2", shadow="%1"),
            pane(id="%3", kind=f"minimonitor:{LIVE_PID}"),
            pane(id="%4", shadow="%1", frozen="rec"),
            pane(id="%5", scratch="%1"),
        ])
        verdicts = {p.pane_id: p.is_helper for p in mc.classify_window_panes(out)}
        self.assertEqual(verdicts, {"%1": False, "%2": True, "%3": True, "%4": False,
                                    "%5": True})


class _SpawnFixture(TmuxSocketContainmentMixin, unittest.TestCase):
    """The spawn patches and helpers, shared by both spawn classes. No tests of
    its own, so neither subclass inherits (and re-runs) another's tests."""

    CONTAINED_MODULES = (alu,)

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = self.tmp / "proj"            # not a git repo: canonical = itself
        self.root.mkdir()
        self.sock = str(self.tmp / "sock")
        self.launch = patch.object(mc, "launch_window_pane",
                                   return_value=("%42", 4242, None)).start()
        self.companion = patch.object(mc, "maybe_spawn_minimonitor",
                                      return_value="%43").start()
        self.cmd = patch.object(mc, "resolve_dry_run_command",
                                return_value="env AITASK_AGENT_STRING=x claude").start()
        self.focus = patch.object(mc, "switch_to_pane_anywhere", return_value=True).start()
        self.split = patch.object(mc, "launch_split_pane",
                                  return_value=("%50", 5050, None)).start()
        self.found_companion = patch.object(mc, "window_companion_pane",
                                            return_value=None).start()
        self.hook = patch.object(mc, "attach_companion_cleanup_hook",
                                 return_value="installed").start()
        self.addCleanup(patch.stopall)

    def spawn(self, mon, **kw):
        kw.setdefault("select_window", True)
        return mc.spawn_sitrep(mon, target_root=self.root, session="s", **kw)

    def both_alive(self):
        return [pane(id="%5", stamp=str(self.root)), pane(id="%6", tui=str(self.root))]


class SpawnTests(_SpawnFixture):
    def test_socket_containment_active(self):
        self.assert_contained()

    def test_spawn_launches_stamps_and_adds_the_companion(self):
        mon = FakeMon(socket=self.sock, windows=("zsh", "agent-sitrep"))
        res = self.spawn(mon)
        self.assertEqual(res.status, "spawned")
        self.assertEqual(res.pane, "%42")
        cfg = self.launch.call_args.args[1]
        self.assertEqual(cfg.window, "agent-sitrep-2")        # unique in the session
        self.assertTrue(cfg.new_window)
        self.assertEqual(cfg.cwd, str(self.root))
        self.assertEqual(mon.stamps[("%42", mc.SITREP_ROOT_OPTION)], str(self.root))
        self.assertEqual(self.cmd.call_args.args[1], "sitrep")
        kw = self.companion.call_args.kwargs
        self.assertEqual(self.companion.call_args.args, ("s", "agent-sitrep-2"))
        self.assertEqual(kw["agent_pane"], "%42")
        self.assertTrue(kw["explicit"])
        # Forced too: `companion_window_prefixes` / TUI-name filtering must not
        # drop the companion the sitrep window requires.
        self.assertTrue(kw["force_companion"])
        self.assertEqual(res.window, "s:agent-sitrep-2")
        self.assertEqual(res.detail, "")
        # The TUI: a detached 40% split UNDER the agent, stamped for the root.
        command, tcfg = self.split.call_args.args
        self.assertEqual(command, mc.sitrep_tui_command(str(self.root)))
        self.assertEqual((tcfg.split_target_pane, tcfg.split_direction,
                          tcfg.split_before, tcfg.split_size, tcfg.split_detached,
                          tcfg.cwd, tcfg.select_window),
                         ("%42", "vertical", False, "40%", True, str(self.root), False))
        self.assertEqual(mon.stamps[("%50", mc.SITREP_TUI_ROOT_OPTION)], str(self.root))
        self.assertEqual(res.tui, "%50")
        self.assertTrue(kw["full_height"])

    def test_lookup_failure_refuses_without_launching(self):
        res = self.spawn(FakeMon(socket=self.sock, list_rc=1))
        self.assertEqual((res.status, res.detail), ("refused", "lookup_failed"))
        self.launch.assert_not_called()
        self.companion.assert_not_called()

    def test_existing_sitrep_is_focused_not_relaunched(self):
        mon = FakeMon(self.both_alive(), socket=self.sock)
        res = self.spawn(mon)
        self.assertEqual((res.status, res.pane), ("focused", "%5"))
        self.focus.assert_called_once_with("%5")
        self.launch.assert_not_called()

    def test_no_select_does_not_move_focus(self):
        mon = FakeMon(self.both_alive(), socket=self.sock)
        self.focus.return_value = False      # never consulted without a switch
        self.assertEqual(self.spawn(mon, select_window=False).status, "focused")
        self.focus.assert_not_called()

    def test_a_failed_focus_is_reported_not_claimed(self):
        self.focus.return_value = False
        mon = FakeMon(self.both_alive(), socket=self.sock)
        res = self.spawn(mon)
        self.assertEqual((res.status, res.pane, res.detail),
                         ("focus_failed", "%5", "focus_failed"))
        self.focus.assert_called_once_with("%5")
        self.launch.assert_not_called()

    def test_lock_not_held_refuses_before_the_lookup(self):
        fd = os.open(self.sock + mc._SITREP_LOCK_SUFFIX, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        mon = FakeMon(socket=self.sock)
        res = self.spawn(mon, lock_timeout=0.1)
        self.assertEqual((res.status, res.detail), ("refused", "lock_busy"))
        self.assertNotIn("list-panes", mon.verbs())
        self.launch.assert_not_called()

    def test_no_socket_path_fails_closed(self):
        res = self.spawn(FakeMon(socket=""))
        self.assertEqual(res.detail, "lock_busy")
        self.launch.assert_not_called()

    def test_stamp_failure_removes_the_pane_and_skips_the_companion(self):
        mon = FakeMon(socket=self.sock, set_rc=1)
        res = self.spawn(mon)
        self.assertEqual(res.status, "refused")
        self.assertEqual(res.detail, "stamp:removed")
        self.assertEqual(mon.killed, ["%42"])
        self.companion.assert_not_called()

    def test_no_command_refuses(self):
        self.cmd.return_value = None
        res = self.spawn(FakeMon(socket=self.sock))
        self.assertEqual(res.detail, "no_command")
        self.launch.assert_not_called()

    def test_launch_error_refuses(self):
        self.launch.return_value = (None, None, "tmux new-window failed (rc=1)")
        res = self.spawn(FakeMon(socket=self.sock))
        self.assertEqual(res.detail, "launch:tmux new-window failed (rc=1)")
        self.companion.assert_not_called()

    def test_companion_not_spawned_is_a_warning(self):
        self.companion.return_value = None
        res = self.spawn(FakeMon(socket=self.sock))
        self.assertEqual((res.status, res.detail), ("spawned", "companion_not_spawned"))

    def test_window_list_failure_refuses(self):
        res = self.spawn(FakeMon(socket=self.sock, window_rc=1))
        self.assertEqual(res.detail, "window_list_failed")
        self.launch.assert_not_called()

    def test_a_missing_root_is_refused(self):
        res = mc.spawn_sitrep(FakeMon(socket=self.sock), target_root=self.tmp / "gone",
                              session="s", select_window=True)
        self.assertEqual(res.status, "refused")
        self.assertTrue(res.detail.startswith("root:"), res.detail)


class RoleSpawnTests(_SpawnFixture):
    """The four-way spawn (t2211_2): which role is missing decides the repair."""

    PLACE = "s\t@7\t3\tagent-sitrep"

    def mon(self, panes, **kw):
        kw.setdefault("socket", self.sock)
        places = kw.pop("places", {"%5": self.PLACE, "%6": self.PLACE})
        return FakeMon(panes, places=places, **kw)

    def agent_only(self):
        return [pane(id="%5", stamp=str(self.root))]

    def tui_only(self):
        return [pane(id="%6", tui=str(self.root))]

    def companion_row(self):
        return pane(id="%9", kind=f"minimonitor:{LIVE_PID}")

    def splits(self):
        return [c.args for c in self.split.call_args_list]

    # -- role lookup ------------------------------------------------------------

    def test_roles_lookup(self):
        root = str(self.root)
        self.assertEqual(mc.find_sitrep_roles(FakeMon(list_rc=1), root),
                         (False, None, None))
        mon = FakeMon([pane(id="%5", stamp=root, window="agent-sitrep"),
                       pane(id="%6", tui=root, window="elsewhere", cwd="/x")])
        self.assertEqual(mc.find_sitrep_roles(mon, root, canon_identity),
                         (True, "%5", "%6"))
        for bad in (dict(tui=root, frozen="rec1"), dict(tui=root, dead="1"),
                    dict(tui="/other")):
            with self.subTest(bad=bad):
                mon = FakeMon([pane(id="%6", **bad)])
                self.assertEqual(mc.find_sitrep_roles(mon, root, canon_identity),
                                 (True, None, None))
        self.assertEqual(mc.find_sitrep_pane_status(
            FakeMon([pane(id="%5", stamp=root)]), root, canon_identity), (True, "%5"))

    # -- agent alive, TUI missing ---------------------------------------------

    def test_agent_only_adds_the_tui_under_it(self):
        mon = self.mon(self.agent_only())
        res = self.spawn(mon)
        self.assertEqual((res.status, res.pane, res.tui, res.window, res.detail),
                         ("added_tui", "%5", "%50", "s:agent-sitrep", ""))
        self.launch.assert_not_called()
        command, cfg = self.split.call_args.args
        self.assertEqual(command, mc.sitrep_tui_command(str(self.root)))
        self.assertEqual((cfg.split_target_pane, cfg.split_before, cfg.split_size,
                          cfg.split_detached, cfg.session),
                         ("%5", False, "40%", True, "s"))
        self.assertEqual(mon.stamps[("%50", mc.SITREP_TUI_ROOT_OPTION)], str(self.root))
        args, kw = self.companion.call_args
        self.assertEqual(args, ("s", "agent-sitrep"))
        self.assertEqual((kw["window_index"], kw["agent_pane"], kw["full_height"],
                          kw["force_companion"], kw["explicit"]),
                         ("3", "%5", True, True, True))
        self.focus.assert_called_once_with("%5")

    def test_a_tui_that_cannot_be_added_refuses(self):
        self.split.return_value = (None, None, "tmux split-window failed (rc=1)")
        res = self.spawn(self.mon(self.agent_only()))
        self.assertEqual((res.status, res.detail),
                         ("refused", "tui:launch:tmux split-window failed (rc=1)"))
        self.companion.assert_not_called()
        mon = self.mon(self.agent_only(), set_rc=1)
        self.split.return_value = ("%50", 5050, None)
        res = self.spawn(mon)
        self.assertEqual((res.status, res.detail), ("refused", "tui:stamp:removed"))
        self.assertIn("%50", mon.killed)

    def test_an_unreadable_place_refuses(self):
        res = self.spawn(self.mon(self.agent_only(), places={}))
        self.assertEqual((res.status, res.detail), ("refused", "place_unreadable"))
        self.split.assert_not_called()

    # -- TUI alive, agent missing ---------------------------------------------

    def test_tui_only_respawns_the_agent_above_it(self):
        mon = self.mon(self.tui_only(),
                       window_panes=[pane(id="%6", tui=str(self.root)),
                                     self.companion_row()])
        self.companion.return_value = None        # the companion survived
        self.found_companion.return_value = "%9"
        self.split.return_value = ("%51", 5151, None)
        res = self.spawn(mon)
        self.assertEqual((res.status, res.pane, res.tui, res.detail),
                         ("respawned_agent", "%51", "%6", ""))
        command, cfg = self.split.call_args.args
        self.assertEqual(command, "env AITASK_AGENT_STRING=x claude")
        self.assertEqual((cfg.split_target_pane, cfg.split_before, cfg.split_size,
                          cfg.split_detached), ("%6", True, "60%", True))
        self.assertEqual(mon.stamps[("%51", mc.SITREP_ROOT_OPTION)], str(self.root))
        self.hook.assert_called_once_with("%51", "%9")
        self.assertTrue(self.companion.call_args.kwargs["full_height"])

    def test_a_respawn_whose_companion_is_gone_restores_it(self):
        mon = self.mon(self.tui_only(), window_panes=[pane(id="%6", tui=str(self.root))])
        res = self.spawn(mon)
        self.assertEqual((res.status, res.detail), ("respawned_agent", ""))
        self.companion.assert_called_once()
        self.hook.assert_not_called()             # maybe_spawn_minimonitor arms it

    def test_a_respawn_without_any_companion_warns(self):
        self.companion.return_value = None
        res = self.spawn(self.mon(self.tui_only(),
                                  window_panes=[pane(id="%6", tui=str(self.root))]))
        self.assertEqual((res.status, res.detail),
                         ("respawned_agent", "companion_not_spawned"))
        self.hook.assert_not_called()

    def test_a_respawn_that_cannot_be_stamped_refuses(self):
        res = self.spawn(self.mon(self.tui_only(), set_rc=1,
                                  window_panes=[pane(id="%6", tui=str(self.root))]))
        self.assertEqual((res.status, res.detail), ("refused", "stamp:removed"))
        self.companion.assert_not_called()

    # -- TUI alive, agent slot occupied: relocate --------------------------------

    def test_an_occupied_slot_relocates_the_tui_to_a_new_window(self):
        occupants = {
            "frozen agent": pane(id="%5", stamp=str(self.root), frozen="rec1"),
            "dead pane": pane(id="%5", dead="1"),
            "user shell": pane(id="%5"),
        }
        for name, occupant in occupants.items():
            with self.subTest(occupant=name):
                self.split.reset_mock()
                self.companion.reset_mock()
                mon = self.mon(self.tui_only(),
                               window_panes=[occupant, pane(id="%6", tui=str(self.root)),
                                             self.companion_row()],
                               windows=("zsh", "agent-sitrep"))
                res = self.spawn(mon)
                self.assertEqual((res.status, res.pane, res.tui, res.window, res.detail),
                                 ("spawned", "%42", "%6", "s:agent-sitrep-2", "tui_moved"))
                self.assertEqual(mon.calls_of("join-pane"),
                                 [["join-pane", "-d", "-v", "-l", "40%",
                                   "-s", "%6", "-t", "%42"]])
                self.split.assert_not_called()        # never a second TUI
                self.assertNotIn(("%6", mc.SITREP_TUI_ROOT_OPTION), mon.stamps)
                self.assertEqual(self.companion.call_args.args, ("s", "agent-sitrep-2"))
                self.assertTrue(self.companion.call_args.kwargs["full_height"])

    def test_a_failed_move_keeps_the_one_tui_and_warns(self):
        mon = self.mon(self.tui_only(), join_rc=1,
                       window_panes=[pane(id="%5", frozen="rec1"),
                                     pane(id="%6", tui=str(self.root))])
        res = self.spawn(mon)
        self.assertEqual((res.status, res.detail), ("spawned", "tui_not_moved"))
        self.split.assert_not_called()

    def test_an_unreadable_slot_refuses(self):
        res = self.spawn(self.mon(self.tui_only(), window_list_rc=1))
        self.assertEqual((res.status, res.detail), ("refused", "lookup_failed"))
        # A listing that does not contain the TUI is not the TUI's window.
        res = self.spawn(self.mon(self.tui_only(), window_panes=[pane(id="%5")]))
        self.assertEqual((res.status, res.detail), ("refused", "lookup_failed"))
        self.launch.assert_not_called()
        self.split.assert_not_called()

    # -- cold start ---------------------------------------------------------------

    def test_a_cold_tui_failure_is_a_warning(self):
        self.split.return_value = (None, None, "tmux split-window failed (rc=1)")
        res = self.spawn(self.mon([]))
        self.assertEqual((res.status, res.pane, res.tui), ("spawned", "%42", None))
        self.assertEqual(res.detail, "tui_not_spawned:launch:tmux split-window failed (rc=1)")
        self.companion.assert_called_once()

    def test_every_role_split_is_detached(self):
        cases = (([], {}),
                 (self.agent_only(), {}),
                 (self.tui_only(), {"window_panes": [pane(id="%6", tui=str(self.root))]}))
        for panes, kw in cases:
            self.split.reset_mock()
            self.spawn(self.mon(panes, **kw))
            self.assertTrue(self.split.call_args_list)
            for _command, cfg in self.splits():
                self.assertTrue(cfg.split_detached)
                self.assertFalse(cfg.select_window)

    # -- focus on a repair --------------------------------------------------------

    def test_no_select_restores_a_moved_active_pane(self):
        mon = self.mon(self.agent_only(), active={"@7": ["%9", "%5"]},
                       pane_windows={"%9": "@7"})
        res = self.spawn(mon, select_window=False)
        self.assertEqual((res.status, res.detail), ("added_tui", ""))
        self.assertEqual(mon.calls_of("select-pane"), [["select-pane", "-t", "%9"]])
        self.focus.assert_not_called()

    def test_no_select_leaves_an_unmoved_active_pane_alone(self):
        mon = self.mon(self.agent_only(), active={"@7": "%9"})
        self.spawn(mon, select_window=False)
        self.assertEqual(mon.calls_of("select-pane"), [])

    def test_a_failed_restore_warns(self):
        mon = self.mon(self.agent_only(), active={"@7": ["%9", "%5"]}, select_rc=1,
                       pane_windows={"%9": "@7"})
        res = self.spawn(mon, select_window=False)
        self.assertEqual(res.detail, "focus_not_restored")

    def test_no_original_active_pane_warns_only_when_the_companion_moved_it(self):
        res = self.spawn(self.mon(self.agent_only(), active={"@7": ""}),
                         select_window=False)
        self.assertEqual(res.detail, "focus_not_restored")
        self.companion.return_value = None          # present: nothing spawned
        self.found_companion.return_value = "%9"
        res = self.spawn(self.mon(self.agent_only(), active={"@7": ""}),
                         select_window=False)
        self.assertEqual(res.detail, "")

    def test_a_moved_original_pane_is_not_selected_elsewhere(self):
        """Moved out of the repaired window meanwhile: never select it there."""
        for where in ("@8", None):          # another window, or unreadable/gone
            with self.subTest(where=where):
                mon = self.mon(self.agent_only(), active={"@7": ["%9", "%5"]},
                               pane_windows={"%9": where} if where else {})
                res = self.spawn(mon, select_window=False)
                self.assertEqual(res.detail, "focus_not_restored")
                self.assertEqual(mon.calls_of("select-pane"), [])

    def test_a_repair_reports_a_required_companion_that_is_missing(self):
        """`None` from the companion spawn is checked on BOTH repair paths."""
        self.companion.return_value = None
        cases = {"added_tui": (self.agent_only(), {}),
                 "respawned_agent": (self.tui_only(),
                                     {"window_panes": [pane(id="%6", tui=str(self.root))]})}
        for status, (panes, kw) in cases.items():
            with self.subTest(status=status):
                self.hook.reset_mock()
                self.found_companion.return_value = None
                res = self.spawn(self.mon(panes, **kw))
                self.assertEqual((res.status, res.detail),
                                 (status, "companion_not_spawned"))
                self.hook.assert_not_called()
                # ... and is silent when the companion is simply present; only
                # the respawn re-arms the hook on its new agent.
                self.found_companion.return_value = "%9"
                res = self.spawn(self.mon(panes, **kw))
                self.assertEqual((res.status, res.detail), (status, ""))
                if status == "added_tui":
                    self.hook.assert_not_called()
                else:
                    self.hook.assert_called_once_with(res.pane, "%9")

    def test_select_switches_to_the_agent_and_reports_a_failure(self):
        mon = self.mon(self.agent_only(), active={"@7": ["%9", "%5"]})
        self.focus.return_value = False
        res = self.spawn(mon)
        self.assertEqual((res.status, res.detail), ("added_tui", "focus_failed"))
        self.focus.assert_called_once_with("%5")
        self.assertEqual(mon.calls_of("select-pane"), [])
        # select_window=True never reads the active pane to restore it.
        self.assertFalse([c for c in mon.calls_of("display-message")
                          if c[c.index("-t") + 1] == "@7"])


class CompanionFullHeightTests(unittest.TestCase):
    """`full_height` adds only tmux `-f`; every other caller's argv is unchanged."""

    class Tmux:
        def __init__(self, panes):
            self.panes = panes
            self.calls: list[list[str]] = []

        def run(self, args, timeout=None):
            self.calls.append(list(args))
            if args[0] == "list-panes":
                return 0, model_render(args[args.index("-F") + 1], self.panes, sep="|")
            if args[0] == "split-window":
                return 0, "%99\n"
            return 0, ""

    def split_argv(self, **kw):
        stub = self.Tmux([model_pane("%1", pane_start_command="claude")])
        with patch.object(alu, "_TMUX", stub):
            alu._companion_check_and_split("demo", "1", "%1", 40, None, **kw)
        (argv,) = [c for c in stub.calls if c[0] == "split-window"]
        return argv

    def test_default_argv_is_unchanged(self):
        self.assertEqual(self.split_argv(),
                         ["split-window", "-h", "-P", "-F", "#{pane_id}", "-l", "40",
                          "-t", "%1", *alu._COMPANION_ARGV])

    def test_full_height_adds_only_f(self):
        self.assertEqual(self.split_argv(full_height=True),
                         ["split-window", "-h", "-f", "-P", "-F", "#{pane_id}", "-l", "40",
                          "-t", "%1", *alu._COMPANION_ARGV])

    def test_split_argv_of_an_unchanged_caller(self):
        """`split_detached` / percentage sizes default to today's split argv."""
        cfg = alu.TmuxLaunchConfig(session="s", window="w", new_session=False,
                                   new_window=False, split_direction="vertical",
                                   split_size=10, split_target_pane="%1", cwd="/r")
        self.assertEqual(alu._split_window_argv("cmd", cfg, "F"),
                         ["split-window", "-P", "-F", "F", "-v", "-l", "10",
                          "-t", "%1", "-c", "/r", "cmd"])
        cfg.split_detached, cfg.split_size, cfg.split_before = True, "40%", True
        self.assertEqual(alu._split_window_argv("cmd", cfg, "F"),
                         ["split-window", "-P", "-F", "F", "-v", "-d", "-b", "-l", "40%",
                          "-t", "%1", "-c", "/r", "cmd"])

    def test_the_scan_names_the_companions_it_counts(self):
        out = model_render(alu._companion_pane_format(), [
            model_pane("%1"),
            model_pane("%2", **{"@aitask_monitor_kind": f"minimonitor:{LIVE_PID}"}),
            model_pane("%3", pane_start_command=alu._COMPANION_START_COMMAND),
            model_pane("%4", **{"@aitask_monitor_kind": "minimonitor:999999999"}),
        ], sep="|")
        scan = alu._scan_companion_window(out)
        self.assertEqual(scan.companion_panes, ("%2", "%3"))
        self.assertEqual(scan.stale_marked, ("%4",))


class CliTests(unittest.TestCase):
    def run_cli(self, *args, cwd=None, env=None):
        e = dict(os.environ)
        e.pop("TMUX", None)
        e.pop("TMUX_PANE", None)
        e.update(env or {})
        return subprocess.run(["bash", str(SITREP_SH), *args], cwd=cwd, env=e,
                              capture_output=True, text=True, timeout=60)

    def test_root_reports_cwd_ok_and_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            d = os.path.realpath(d)
            sub = os.path.join(d, "sub")
            os.mkdir(sub)
            r = self.run_cli("root", cwd=d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.splitlines(), [f"ROOT:{d}", "CWD_OK"])
            r = self.run_cli("root", "--root", d, cwd=sub)
            self.assertEqual(r.stdout.splitlines(), [f"ROOT:{d}", f"CWD_MISMATCH:{sub}"])

    def test_open_outside_tmux_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(cwd=d)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "SITREP_REFUSED:not_in_tmux")

    def test_bad_root_is_refused_in_every_spelling(self):
        """The parser is the one check: every spelling it accepts, every verb."""
        spellings = (["--root", "a/../b"], ["--root=a/../b"], ["--root", ""],
                     ["--root="], ["--root=.."], ["--roo", "a/../b"])
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "a"))
            os.makedirs(os.path.join(d, "b"))
            for verb in ("root", "triage", "open"):
                for spelling in spellings:
                    args = [verb] + (["c1"] if verb == "triage" else []) + spelling
                    r = self.run_cli(*args, cwd=d)
                    self.assertEqual(r.returncode, 2, args)
                    self.assertEqual(r.stdout, "", args)

    def test_option_abbreviations_are_not_accepted(self):
        """`--root P` / `--root=P` are the only spellings (documented), even for a
        valid path: an abbreviation is an unknown option."""
        with tempfile.TemporaryDirectory() as d:
            for verb in ("root", "triage", "open"):
                args = [verb] + (["c1"] if verb == "triage" else []) + ["--roo", d]
                r = self.run_cli(*args, cwd=d)
                self.assertEqual(r.returncode, 2, args)
                self.assertEqual(r.stdout, "", args)

    def test_a_good_root_in_the_equals_spelling_works(self):
        with tempfile.TemporaryDirectory() as d:
            d = os.path.realpath(d)
            r = self.run_cli("root", f"--root={d}", cwd=d)
        self.assertEqual(r.stdout.splitlines(), [f"ROOT:{d}", "CWD_OK"])

    def test_unknown_verb_is_usage(self):
        self.assertEqual(self.run_cli("frobnicate").returncode, 2)

    def test_triage_needs_an_id_or_open(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_cli("triage", cwd=d).returncode, 2)
            self.assertEqual(self.run_cli("triage", "c1", "--open", cwd=d).returncode, 2)
            r = self.run_cli("triage", "--open", cwd=d)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "NO_TRIAGE"))



class OpenCliTests(TmuxSocketContainmentMixin, unittest.TestCase):
    """`monitor/sitrep_open.py` turns each spawn outcome into its wire line."""
    CONTAINED_MODULES = (alu,)

    def setUp(self):
        super().setUp()
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sitrep_open_under_test",
            REPO_ROOT / ".aitask-scripts" / "monitor" / "sitrep_open.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        patch.dict(os.environ, {"TMUX": "/tmp/x,1,0", "TMUX_PANE": "%1"}).start()
        patch.object(self.mod, "pane_session", return_value="s").start()
        self.addCleanup(patch.stopall)

    def run_main(self, outcome, *argv):
        import contextlib
        import io
        patch.object(self.mod.monitor_core, "spawn_sitrep", return_value=outcome).start()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.mod.main(list(argv))
        return rc, buf.getvalue().strip()

    def test_focus_failed_exits_1(self):
        rc, out = self.run_main(mc.SitrepSpawn("focus_failed", "%5", "", "focus_failed"))
        self.assertEqual((rc, out), (1, "SITREP_FOCUS_FAILED:%5"))

    def test_focused_and_spawned(self):
        self.assertEqual(self.run_main(mc.SitrepSpawn("focused", "%5", "", "")),
                         (0, "SITREP_FOCUSED:%5"))
        self.assertEqual(self.run_main(mc.SitrepSpawn("spawned", "%6", "s:agent-sitrep",
                                                      "companion_not_spawned")),
                         (0, "SITREP_SPAWNED:%6|s:agent-sitrep\nSITREP_WARN:companion_not_spawned"))

    def test_refused(self):
        self.assertEqual(self.run_main(mc.SitrepSpawn("refused", None, "", "lookup_failed")),
                         (1, "SITREP_REFUSED:lookup_failed"))

    def test_the_repair_lines_and_one_warn_line_per_item(self):
        self.assertEqual(
            self.run_main(mc.SitrepSpawn("added_tui", "%5", "s:agent-sitrep", "", "%6")),
            (0, "SITREP_ADDED_TUI:%5|s:agent-sitrep"))
        self.assertEqual(
            self.run_main(mc.SitrepSpawn("respawned_agent", "%7", "s:agent-sitrep",
                                         "companion_not_spawned,focus_failed", "%6")),
            (0, "SITREP_RESPAWNED_AGENT:%7|s:agent-sitrep\n"
                "SITREP_WARN:companion_not_spawned\nSITREP_WARN:focus_failed"))
        self.assertEqual(
            self.run_main(mc.SitrepSpawn("spawned", "%8", "s:agent-sitrep-2", "tui_moved",
                                         "%6")),
            (0, "SITREP_SPAWNED:%8|s:agent-sitrep-2\nSITREP_WARN:tui_moved"))

    def test_the_toast_wording_of_every_success_line(self):
        import sitrep_cli
        msg = sitrep_cli.sitrep_open_message
        self.assertEqual(msg(0, "SITREP_ADDED_TUI:%5|s:w\n"),
                         ("Sitrep TUI added to the sitrep window", "information"))
        self.assertEqual(msg(0, "SITREP_RESPAWNED_AGENT:%5|s:w\n"),
                         ("Sitrep agent restarted beside its TUI", "information"))
        self.assertEqual(
            msg(0, "SITREP_SPAWNED:%5|s:w\nSITREP_WARN:tui_moved\n"
                   "SITREP_WARN:companion_not_spawned\n"),
            ("Sitrep window opened (tui_moved, companion_not_spawned)", "warning"))
        self.assertEqual(msg(1, "SITREP_REFUSED:tui:stamp:removed\n"),
                         ("Sitrep not opened: tui:stamp:removed", "error"))

    def test_no_select_reaches_the_spawn(self):
        spawn = patch.object(self.mod.monitor_core, "spawn_sitrep",
                             return_value=mc.SitrepSpawn("focused", "%5", "", "")).start()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.main(["--no-select"])
        self.assertFalse(spawn.call_args.kwargs["select_window"])

    # -- --session (t2175_5: the TUIs name the selected agent's session) ------

    def _session_run(self, has_session_rc, *argv):
        import contextlib
        import io
        asked = []

        def fake_run(_gw, args, timeout=5.0):
            asked.append(list(args))
            return has_session_rc, ""

        patch.object(self.mod._Gateway, "tmux_run", fake_run).start()
        spawn = patch.object(self.mod.monitor_core, "spawn_sitrep",
                             return_value=mc.SitrepSpawn("focused", "%5", "", "")
                             ).start()
        lookup = patch.object(self.mod, "pane_session", return_value="own").start()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.mod.main(list(argv))
        return rc, buf.getvalue().strip(), spawn, lookup, asked

    def test_a_named_session_reaches_the_spawn_instead_of_the_own_one(self):
        rc, out, spawn, lookup, asked = self._session_run(0, "--session", "other")
        self.assertEqual((rc, out), (0, "SITREP_FOCUSED:%5"))
        self.assertEqual(spawn.call_args.kwargs["session"], "other")
        self.assertEqual(asked, [["has-session", "-t", "=other"]],
                         "the named session must be checked by EXACT name")
        lookup.assert_not_called()

    def test_an_unknown_named_session_is_refused_and_nothing_spawns(self):
        rc, out, spawn, _lookup, _asked = self._session_run(1, "--session", "gone")
        self.assertEqual((rc, out), (1, "SITREP_REFUSED:no_session"))
        spawn.assert_not_called()

    def test_without_session_the_own_pane_session_is_used(self):
        rc, _out, spawn, lookup, asked = self._session_run(0)
        self.assertEqual(spawn.call_args.kwargs["session"], "own")
        self.assertEqual(asked, [])
        lookup.assert_called_once()

    def test_a_malformed_session_name_is_usage(self):
        import contextlib
        import io
        for bad in ("", "-x", "a:b", "a.b", "a\nb", "a\x7fb"):
            spawn = patch.object(self.mod.monitor_core, "spawn_sitrep").start()
            with self.subTest(bad=bad), \
                    contextlib.redirect_stderr(io.StringIO()), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as cm:
                    self.mod.main(["--session", bad])
                self.assertEqual(cm.exception.code, 2)
                self.assertEqual(out.getvalue(), "")
                spawn.assert_not_called()


# -- the sitrep TUI pane, one row per consumer (t2211_2) -----------------------
#
# The TUI pane (`ait sitrep tui`) shares the agent's window and cwd. It is NOT an
# agent for anything that LISTS agents, and it IS a real occupant for anything
# that decides whether a window still holds one. Each test below is one consumer
# of the pane listings, fed a TUI pane stamped for the root. The option name is
# spelled out rather than imported, so the rows also ran BEFORE the production
# constant existed (the characterization pre-phase).
#
# The pane model's keys are the `#{...}` names without the braces, so every fake
# renders whatever format production asks for.

TUI_OPT = "@aitask_sitrep_tui_root"
CT_ROOT = "/repo"
CT_AGENT, CT_MM, CT_TUI = "%1", "%2", "%3"


def model_pane(pane_id: str, **opts) -> dict:
    return {"pane_id": pane_id, "pane_pid": str(LIVE_PID), "pane_dead": "0",
            "pid": "99",   # `#{pid}`: the tmux SERVER pid
            "window_index": "1", "window_name": "agent-sitrep",
            "pane_index": pane_id.lstrip("%"), "pane_current_command": "python",
            "pane_width": "80", "pane_height": "24", "history_size": "0",
            "pane_current_path": CT_ROOT, "pane_start_command": "", **opts}


def model_render(fmt: str, panes: list[dict], sep: str = "\t") -> str:
    return "".join(
        sep.join(str(p.get(spec.strip("#{}"), "")) for spec in fmt.split(sep)) + "\n"
        for p in panes)


def ct_agent(**kw) -> dict:
    return model_pane(CT_AGENT, **{"@aitask_sitrep_root": CT_ROOT, **kw})


def ct_mm() -> dict:
    return model_pane(CT_MM, **{"@aitask_monitor_kind": f"minimonitor:{LIVE_PID}"})


def ct_tui(**kw) -> dict:
    return model_pane(CT_TUI, **{TUI_OPT: CT_ROOT, **kw})


def no_cmdline_companions():
    """This runner's own pid must not reach the real /proc cmdline rung."""
    return patch.object(mc, "_is_companion_process", lambda pid: False)


class ConsumerTableTests(unittest.TestCase):
    """Listing consumers skip the TUI pane; retention consumers count it."""

    # -- listing: not an agent ------------------------------------------------

    def test_discovery_never_lists_the_tui(self):
        mon = mc.TmuxMonitor(session="s", all_sessions=False, agent_prefixes=["agent-"])
        out = model_render(mon._LIST_PANES_FORMAT, [ct_agent(), ct_tui(), ct_mm()])
        with no_cmdline_companions():
            panes, shadows = mon._parse_list_panes(out, "s")
        self.assertEqual([p.pane_id for p in panes], [CT_AGENT])
        self.assertEqual(shadows, [])
        self.assertNotIn(CT_TUI, mon._pane_cache)

    def test_discovery_keeps_a_frozen_pane_whatever_tui_stamp_it_retained(self):
        """Frozen first: a stand-in is listed, even with a TUI stamp on it."""
        mon = mc.TmuxMonitor(session="s", all_sessions=False, agent_prefixes=["agent-"])
        out = model_render(mon._LIST_PANES_FORMAT,
                           [ct_tui(**{"@aitask_frozen": "rec00001"})])
        with no_cmdline_companions():
            panes, _ = mon._parse_list_panes(out, "s")
        self.assertEqual([p.pane_id for p in panes], [CT_TUI])

    def test_the_matcher_fallback_never_takes_the_tui_for_the_agent(self):
        """Agent gone: the TUI has the sitrep window and the root cwd, no agent stamp."""
        out = model_render(mc.SITREP_PANE_FORMAT, [ct_tui(), ct_mm()])
        with no_cmdline_companions():
            self.assertIsNone(mc.match_sitrep_pane(out, CT_ROOT, canon_identity))
            both = model_render(mc.SITREP_PANE_FORMAT, [ct_tui(), ct_agent()])
            self.assertEqual(mc.match_sitrep_pane(both, CT_ROOT, canon_identity),
                             CT_AGENT)

    def _rung2(self, panes):
        from monitor import minimonitor_app as mm

        class Mon:
            def tmux_run(self, args, timeout=None):
                if args[0] != "list-panes":
                    return 1, ""
                return 0, model_render(args[args.index("-F") + 1], panes)

        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._monitor = Mon()
        app._own_window_id = "@1"
        app._own_window_index = "1"
        app._session = "s"
        app._snapshots = {}
        app.notes = []
        app.notify = lambda msg, **kw: app.notes.append(msg)
        app._find_own_window_snapshot = lambda *a, **kw: None
        with patch.dict(os.environ, {"TMUX_PANE": CT_MM}), no_cmdline_companions():
            return app._find_sibling_pane_id()

    def test_the_minimonitor_never_follows_the_tui(self):
        self.assertIsNone(self._rung2([ct_mm(), ct_tui()]))
        self.assertEqual(self._rung2([ct_mm(), ct_tui(), ct_agent()]), CT_AGENT)

    def test_h_refuses_the_tui_pane(self):
        """A TUI snapshot (e.g. from a status server older than this change)."""
        from monitor import sitrep_close as sc
        panes = {CT_TUI: ct_tui()}
        harvests: list = []

        class Mon:
            calls: list = []

            async def _tmux_async(self, args, timeout=5.0):
                self.calls.append(list(args))
                if args[0] == "display-message":
                    p = panes.get(args[args.index("-t") + 1])
                    return (0, model_render(args[-1], [p])) if p else (1, "")
                if args[0] == "capture-pane":
                    return 0, "screen\n"
                return 1, ""

        class Host(sc.SitrepCloseMixin):
            _monitor = Mon()
            _task_cache = None

            async def _run_sitrep_harvest(self, args, *, stdin=None, timeout):
                harvests.append(args)
                return 0, "HARVESTED:capture|added=1|existing=0\n"

        snap = mc.PaneSnapshot(
            pane=mc.TmuxPaneInfo(
                window_index="1", window_name="agent-sitrep", pane_index="3",
                pane_id=CT_TUI, pane_pid=LIVE_PID, current_command="python",
                width=80, height=24, category=mc.PaneCategory.AGENT,
                session_name="s"),
            content="x", timestamp=0.0, idle_seconds=1.0, is_idle=True)
        import asyncio
        report, _ident = asyncio.run(Host()._harvest_for_close(snap, "live", CT_ROOT))
        self.assertFalse(report.ok, report)
        self.assertEqual(report.reason, "not_an_agent")
        self.assertEqual(harvests, [])
        self.assertFalse(any(c[0] == "capture-pane" for c in Host._monitor.calls))

    # -- retention: a real occupant ---------------------------------------------

    def test_the_companion_scan_counts_the_tui_as_an_occupant(self):
        fmt = alu._companion_pane_format()
        scan = alu._scan_companion_window(
            model_render(fmt, [ct_agent(), ct_tui()], sep="|").rstrip("\n"))
        self.assertFalse(scan.present)
        self.assertEqual(scan.real_panes, 2)

    def test_classify_counts_the_tui_as_real(self):
        out = model_render(mc.FROZEN_AWARE_PANE_FORMAT, [ct_agent(), ct_tui(), ct_mm()])
        with no_cmdline_companions():
            panes = mc.classify_window_panes(out)
        helper = {p.pane_id: p.is_helper for p in panes}
        self.assertEqual(helper, {CT_AGENT: False, CT_TUI: False, CT_MM: True})
        self.assertEqual(mc.count_other_real_agents(
            [(p.pane_id, p.is_helper) for p in panes], CT_AGENT), 1)

    def test_the_freeze_coordinator_counts_the_tui_as_real(self):
        import agent_freeze
        out = model_render(mc.FROZEN_AWARE_PANE_FORMAT, [ct_agent(), ct_tui(), ct_mm()])
        with patch.object(agent_freeze.frozen_ops, "run",
                          lambda args, **kw: (0, out)), no_cmdline_companions():
            self.assertEqual(agent_freeze._other_real_agents(CT_AGENT), 1)

    def test_the_minimonitor_is_not_alone_beside_the_tui(self):
        import asyncio
        import tempfile as _tf
        from monitor import minimonitor_app as mm
        mon = mc.TmuxMonitor(session="s", all_sessions=False)
        out = model_render(mon._WINDOW_PANES_FORMAT, [ct_mm(), ct_tui()])

        async def run_async(args, timeout=5.0):
            return 0, out
        mon.tmux_run_async = run_async
        with _tf.TemporaryDirectory() as d:
            app = mm.MiniMonitorApp(session="s", project_root=Path(d))
            app._monitor = mon
            app._own_window_id = "@1"
            exits: list = []
            app.exit = lambda *a, **kw: exits.append(True)
            with patch.dict(os.environ, {"TMUX_PANE": CT_MM}):
                for _ in range(mm.AUTO_CLOSE_CONFIRMATIONS + 2):
                    asyncio.run(app._check_auto_close())
        self.assertEqual(exits, [])
        self.assertEqual(app._empty_window_streak, 0)


if __name__ == "__main__":
    unittest.main()
