"""Characterization pins for monitor_app's two `/aitask-pick` launch paths (t1946).

`MonitorApp._launch_pick_for_sibling` (the next-sibling pick) and
`MonitorApp._on_restart_confirmed` (restart an idle agent) each build the pick
`AgentCommandScreen` and own their result policy. t1946 routes the screen
construction through the shared `agent_command_screen.build_pick_screen`; this
file was written against the pre-refactor code and pins what each caller does,
so the dedupe cannot silently change either one:

- the exact dialog construction (positional args + kwargs dict — no `narrow`);
- resolve failure → one error notify, no kill, no dialog;
- sibling path: the outgoing pane is killed BEFORE the dialog opens, by the
  parent / archived / Done heuristic only — and only when the live
  `@aitask_frozen` read proves it is not a frozen stand-in (t2057); a failed
  kill is reported and keeps focus (t2078) — and the tmux result notifies
  "Launched agent for t<id>";
- restart path: the kill runs INSIDE the callback, BEFORE `launch_in_tmux`, and
  notifies "Restarted agent for t<id>" — and only when `_kill_target_state`
  proves the pane live at that moment; otherwise nothing is killed OR launched
  (t2065); a failed kill launches nothing either (t2075);
- both: a launch error returns before `call_later`; cancel only refreshes; the
  launch reads `screen.full_command` (the user may edit it in the dialog).

Only the four construction seams depend on where the screen is built; they are
patched on `SEAM`, the one line the refactor moves. The assertions do not change.

Run: python3 tests/test_monitor_pick_launch_sites.py
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_command_screen as acs  # noqa: E402
from monitor import monitor_app as ma  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from monitor.monitor_core import TaskInfo  # noqa: E402

#: Where the pick dialog is constructed — the module whose names the four
#: construction seams are patched on. `monitor_app` until t1946 moved the
#: construction into `agent_command_screen.build_pick_screen`.
SEAM = acs

_ROOT = Path("/proj/alpha")
_EDITED = "opencode run --model x '/aitask-pick 42'"
_GOLDEN_KWARGS = {
    "default_window_name": "agent-pick-42",
    "project_root": _ROOT,
    "operation": "pick",
    "operation_args": ["42"],
    "default_agent_string": "claudecode/x",
    "skill_name": "pick",
    "default_profile": "fast",
}


def _info(task_id: str, status: str) -> TaskInfo:
    return TaskInfo(
        task_id=task_id, task_file=f"aitasks/t{task_id}_x.md",
        title=f"task {task_id}", priority="medium", effort="low",
        issue_type="bug", status=status, body="body", plan_content=None,
    )


class _Host:
    """The attributes the two methods read, with every side effect logged."""

    def __init__(self, current_task: str, info: TaskInfo | None):
        self.log: list[tuple] = []
        self.notes: list[tuple[str, str]] = []
        self.pushed: list[tuple] = []
        self._focused_pane_id = "%7"
        snap = SimpleNamespace(
            pane=SimpleNamespace(
                pane_id="%7", session_name="s1", window_name="agent-pick-41"),
            # Completed for `_is_frozen`'s strict `snap.frozen` read (t2057).
            frozen=False, frozen_record_id="")
        self._snapshots = {"%7": snap}
        log = self.log
        #: What the live `@aitask_frozen` read answers, per pane (t2057). The
        #: default is a VERIFIED unset option: a live agent.
        self.pane_option: dict[str, tuple[bool, str]] = {}
        #: The monitor's discovery-cache row per pane (t2065) — where the smart
        #: kill reads the record it drops. Absent ⇒ unknown to the cache.
        self.cached: dict[str, SimpleNamespace] = {}
        #: What the smart kill reports (t2075). The default is a kill that
        #: succeeded.
        self.kill_ok = True
        host = self

        class _Cache:
            def get_task_id_for_pane(self, pane):
                return current_task

            def get_task_info(self, task_id, sess):
                return info

        class _Monitor:
            def kill_agent_pane_smart(self, pane_id):
                log.append(("kill", pane_id))
                return (host.kill_ok, "killed")

            def get_pane_option_sync(self, pane_id, option, timeout=2.0):
                log.append(("read", pane_id, option))
                return host.pane_option.get(pane_id, (True, ""))

            def get_pane(self, pane_id):
                return host.cached.get(pane_id)

        self._task_cache = _Cache()
        self._monitor = _Monitor()
        self._refresh_data = object()

    # The REAL kill-time check and its frozen predicate, not stubs (t2057).
    _kill_target_state = ma.MonitorApp._kill_target_state
    _is_frozen = ma.MonitorApp._is_frozen

    def _root_for_snap(self, snap):
        return _ROOT

    def notify(self, message, severity="information", **_):
        self.log.append(("notify", message))
        self.notes.append((message, severity))

    def push_screen(self, screen, callback=None):
        self.log.append(("push",))
        self.pushed.append((screen, callback))

    def call_later(self, fn, *a):
        self.log.append(("call_later",))


class _Seams:
    """Patches the construction seams on `SEAM` and the launch seams on `ma`."""

    def __init__(self, full_cmd="cmd --go"):
        self.constructed: list[tuple] = []
        self.calls: dict[str, list] = {"argv": [], "agent": [], "profile": []}
        self.launch_result = (1234, None)
        self.spawned: list[tuple] = []
        self.full_cmd = full_cmd
        self._patches = []

    def start(self, host: _Host):
        seams = self

        class _FakeScreen:
            def __init__(self, *a, **k):
                seams.constructed.append((a, k))
                self.full_command = a[1]

        def _argv(root, task_id, agent_string=None):
            self.calls["argv"].append((root, task_id, agent_string))
            return self.full_cmd, f"agent-pick-{task_id}"

        def _agent(root, op):
            self.calls["agent"].append((root, op))
            return "claudecode/x"

        def _profile(skill, root="."):
            self.calls["profile"].append((skill, root))
            return "fast"

        def _launch(command, config):
            host.log.append(("launch", command))
            return self.launch_result

        def _spawn(session, window):
            host.log.append(("spawn", session, window))
            self.spawned.append((session, window))

        self._patches = [
            patch.object(SEAM, "pick_launch_argv", _argv),
            patch.object(SEAM, "resolve_agent_string", _agent),
            patch.object(SEAM, "resolve_skill_profile", _profile),
            patch.object(SEAM, "AgentCommandScreen", _FakeScreen),
            patch.object(ma, "launch_in_tmux", _launch),
            patch.object(ma, "maybe_spawn_minimonitor", _spawn),
        ]
        for p in self._patches:
            p.start()
        return self

    def stop(self):
        for p in reversed(self._patches):
            p.stop()


def _cfg(new_window=True):
    return ma.TmuxLaunchConfig(session="s1", window="agent-pick-42",
                               new_session=False, new_window=new_window)


class _Base(unittest.TestCase):
    def _seams(self, host, **kw):
        seams = _Seams(**kw).start(host)
        self.addCleanup(seams.stop)
        return seams

    def _assert_golden(self, seams):
        self.assertEqual(len(seams.constructed), 1)
        args, kwargs = seams.constructed[0]
        self.assertEqual(args, ("Pick Task t42", "cmd --go", "/aitask-pick 42"))
        self.assertEqual(kwargs, _GOLDEN_KWARGS)
        # The configured pick agent — never a record's (tests/test_pick_launch_argv.py).
        self.assertEqual(seams.calls["argv"], [(_ROOT, "42", None)])
        self.assertEqual(seams.calls["agent"], [(_ROOT, "pick")])
        self.assertEqual(seams.calls["profile"], [("pick", _ROOT)])


class SiblingPickTests(_Base):
    """`_launch_pick_for_sibling` — kill (by heuristic) before the dialog opens."""

    def _open(self, current_task="41_2", info=None, **kw):
        if info is None:
            info = _info(current_task, "Implementing")
        host = _Host(current_task, info)
        seams = self._seams(host, **kw)
        ma.MonitorApp._launch_pick_for_sibling(host, "42")
        return host, seams

    def test_dialog_construction_is_pinned(self):
        host, seams = self._open()
        self._assert_golden(seams)
        self.assertEqual(host.log, [("push",)])

    def test_resolve_failure_notifies_and_neither_kills_nor_opens(self):
        host, seams = self._open(current_task="41", full_cmd=None)
        self.assertEqual(host.notes,
                         [("Failed to resolve pick command for t42", "error")])
        self.assertEqual(seams.constructed, [])
        self.assertNotIn(("kill", "%7"), host.log)
        self.assertEqual(host.pushed, [])

    def test_live_child_task_is_not_killed(self):
        host, _ = self._open(current_task="41_2",
                             info=_info("41_2", "Implementing"))
        self.assertNotIn(("kill", "%7"), host.log)
        self.assertEqual(host._focused_pane_id, "%7")

    def test_parent_archived_and_done_are_killed_before_the_dialog(self):
        for label, task, info in (
                ("parent", "41", _info("41", "Implementing")),
                ("archived", "41_2", None),
                ("done", "41_2", _info("41_2", "Done"))):
            with self.subTest(label):
                host = _Host(task, info)
                seams = _Seams().start(host)
                try:
                    ma.MonitorApp._launch_pick_for_sibling(host, "42")
                finally:
                    seams.stop()
                # The live frozen read runs immediately before the kill (t2057).
                self.assertEqual(host.log, [
                    ("read", "%7", "@aitask_frozen"),
                    ("kill", "%7"), ("notify", "Killed agent-pick-41"), ("push",)])
                self.assertIsNone(host._focused_pane_id)

    def test_failed_kill_is_reported_keeps_focus_and_still_opens_the_dialog(self):
        """t2078: the pane is still running, so no "Killed" toast and no focus
        loss. The live Done row of the test above is the control."""
        host = _Host("41_2", _info("41_2", "Done"))
        host.kill_ok = False
        seams = self._seams(host)
        ma.MonitorApp._launch_pick_for_sibling(host, "42")
        self.assertEqual(host.log, [
            ("read", "%7", "@aitask_frozen"),
            ("kill", "%7"), ("notify", "Failed to kill agent-pick-41"),
            ("push",)])
        self.assertEqual(host.notes,
                         [("Failed to kill agent-pick-41", "error")])
        self.assertEqual(host._focused_pane_id, "%7")
        self._assert_golden(seams)

    def _open_done(self, *, frozen_snapshot=False, read=(True, "")):
        host = _Host("41_2", _info("41_2", "Done"))
        host._snapshots["%7"].frozen = frozen_snapshot
        host.pane_option["%7"] = read
        seams = self._seams(host)
        ma.MonitorApp._launch_pick_for_sibling(host, "42")
        return host, seams

    def test_frozen_snapshot_is_not_killed_but_the_dialog_opens(self):
        """t2058 on the full monitor: a frozen Done card must not reach
        `kill_agent_pane_smart`'s unleased kill-then-drop path. The live
        Done row of the test above is the control."""
        host, seams = self._open_done(frozen_snapshot=True)
        self.assertNotIn(("kill", "%7"), host.log)
        self.assertEqual(host._focused_pane_id, "%7")
        self.assertEqual(host.notes, [
            ("agent-pick-41 is frozen — not killed; drop it with k", "warning")])
        self.assertEqual(len(host.pushed), 1)
        self._assert_golden(seams)

    def test_frozen_on_the_live_read_is_not_killed(self):
        """The snapshot is a tick stale; the pane option is the truth."""
        host, _ = self._open_done(read=(True, "7f3a2c1d"))
        self.assertNotIn(("kill", "%7"), host.log)
        self.assertEqual(host.notes[0][1], "warning")
        self.assertEqual(len(host.pushed), 1)

    def test_unverified_read_fails_closed(self):
        host, _ = self._open_done(read=(False, ""))
        self.assertNotIn(("kill", "%7"), host.log)
        self.assertEqual(host.notes, [
            ("Could not confirm agent-pick-41 is still live — not killed",
             "warning")])
        self.assertEqual(len(host.pushed), 1)

    def test_tmux_success_launches_the_edited_command(self):
        host, seams = self._open()
        screen, callback = host.pushed[0]
        screen.full_command = _EDITED
        host.log.clear()
        callback(_cfg(new_window=True))
        self.assertEqual(host.log, [
            ("launch", _EDITED), ("spawn", "s1", "agent-pick-42"),
            ("notify", "Launched agent for t42"), ("call_later",)])

    def test_existing_window_launch_spawns_no_companion(self):
        host, seams = self._open()
        _, callback = host.pushed[0]
        callback(_cfg(new_window=False))
        self.assertEqual(seams.spawned, [])
        self.assertIn(("notify", "Launched agent for t42"), host.log)

    def test_launch_error_returns_before_refresh(self):
        host, seams = self._open()
        seams.launch_result = (None, "boom")
        _, callback = host.pushed[0]
        host.log.clear()
        callback(_cfg())
        self.assertEqual(host.log, [("launch", "cmd --go"),
                                    ("notify", "Launch failed: boom")])
        self.assertEqual(host.notes[-1], ("Launch failed: boom", "error"))

    def test_cancel_only_refreshes(self):
        host, _ = self._open()
        _, callback = host.pushed[0]
        host.log.clear()
        callback(None)
        self.assertEqual(host.log, [("call_later",)])


class RestartPickTests(_Base):
    """`_on_restart_confirmed` — the kill happens in the callback, before launch."""

    def _open(self, confirmed=True, **kw):
        host = _Host("42", _info("42", "Implementing"))
        seams = self._seams(host, **kw)
        ma.MonitorApp._on_restart_confirmed(host, confirmed, "%7", "42")
        return host, seams

    def test_dialog_construction_is_pinned_and_nothing_is_killed_yet(self):
        host, seams = self._open()
        self._assert_golden(seams)
        self.assertEqual(host.log, [("push",)])

    def test_not_confirmed_does_nothing(self):
        host, seams = self._open(confirmed=False)
        self.assertEqual(host.log, [])
        self.assertEqual(seams.constructed, [])

    def test_vanished_pane_warns(self):
        host = _Host("42", None)
        host._snapshots = {}
        seams = self._seams(host)
        ma.MonitorApp._on_restart_confirmed(host, True, "%7", "42")
        self.assertEqual(host.notes,
                         [("Focused pane no longer exists", "warning")])
        self.assertEqual(seams.constructed, [])

    def test_resolve_failure_notifies_and_opens_nothing(self):
        host, seams = self._open(full_cmd=None)
        self.assertEqual(host.notes,
                         [("Failed to resolve pick command for t42", "error")])
        self.assertEqual(seams.constructed, [])
        self.assertEqual(host.pushed, [])

    def test_tmux_kills_then_launches_the_edited_command(self):
        host, _ = self._open()
        screen, callback = host.pushed[0]
        screen.full_command = _EDITED
        host.log.clear()
        callback(_cfg(new_window=True))
        self.assertEqual(host.log, [
            ("read", "%7", "@aitask_frozen"),
            ("kill", "%7"), ("notify", "Killed agent-pick-41"),
            ("launch", _EDITED), ("spawn", "s1", "agent-pick-42"),
            ("notify", "Restarted agent for t42"), ("call_later",)])
        self.assertIsNone(host._focused_pane_id)

    def test_launch_error_after_kill_returns_before_refresh(self):
        host, seams = self._open()
        seams.launch_result = (None, "boom")
        _, callback = host.pushed[0]
        host.log.clear()
        callback(_cfg())
        self.assertEqual(host.log, [
            ("read", "%7", "@aitask_frozen"),
            ("kill", "%7"), ("notify", "Killed agent-pick-41"),
            ("launch", "cmd --go"), ("notify", "Launch failed: boom")])

    def test_cancel_only_refreshes(self):
        host, _ = self._open()
        _, callback = host.pushed[0]
        host.log.clear()
        callback(None)
        self.assertEqual(host.log, [("call_later",)])

    def test_failed_kill_neither_launches_nor_reports_restart(self):
        """The old agent is still alive: a launch would duplicate the task
        (t2075)."""
        host, _ = self._open()
        _, callback = host.pushed[0]
        host.kill_ok = False
        host.log.clear()
        callback(_cfg(new_window=True))
        failed = "Failed to kill agent-pick-41 — not restarted"
        self.assertEqual(host.log, [
            ("read", "%7", "@aitask_frozen"),
            ("kill", "%7"), ("notify", failed), ("call_later",)])
        self.assertEqual(host.notes, [(failed, "warning")])
        self.assertEqual(host._focused_pane_id, "%7")

    # -- t2065: the agent may be frozen while the dialogs are open ----------

    def _confirm_after(self, between):
        host, _ = self._open()
        _, callback = host.pushed[0]
        between(host)
        host.log.clear()
        callback(_cfg())
        return host

    def _assert_not_restarted(self, host, message):
        kinds = [entry[0] for entry in host.log]
        self.assertNotIn("kill", kinds)
        self.assertNotIn("launch", kinds)
        self.assertIn((message, "warning"), host.notes)
        self.assertEqual(host.log[-1], ("call_later",))
        self.assertEqual(host._focused_pane_id, "%7")

    _FROZEN = ("agent-pick-41 is frozen — not restarted; press s to switch to "
               "its viewer, then R to restore or P to re-pick")

    def test_frozen_meanwhile_snapshot_is_neither_killed_nor_relaunched(self):
        def freeze(host):
            host._snapshots["%7"].frozen = True
        self._assert_not_restarted(self._confirm_after(freeze), self._FROZEN)

    def test_frozen_meanwhile_on_the_live_read(self):
        def freeze(host):
            host.pane_option["%7"] = (True, "rec-1")
        self._assert_not_restarted(self._confirm_after(freeze), self._FROZEN)

    def test_cached_record_with_a_cleared_live_stamp(self):
        """A restore cleared the live stamp; discovery has not caught up."""
        def stale(host):
            host.cached["%7"] = SimpleNamespace(frozen_record="rec-1")
        self._assert_not_restarted(self._confirm_after(stale), self._FROZEN)

    def test_unverified_read_fails_closed(self):
        def unreadable(host):
            host.pane_option["%7"] = (False, "")
        self._assert_not_restarted(
            self._confirm_after(unreadable),
            "Could not confirm agent-pick-41 is still live — not restarted")


class KillConfirmRecheckTests(unittest.TestCase):
    """`k` in the full monitor: the target is BOUND when the dialog opens and
    re-checked when it closes (t2065).

    Drives the real `action_kill_pane` → dialog callback → `_on_kill_confirmed`
    → `_kill_target_state`; only the dialog class is stubbed.
    """

    def setUp(self):
        stub = patch.object(ma, "KillConfirmDialog",
                            lambda snap, info: ("dialog", snap.pane.pane_id))
        stub.start()
        self.addCleanup(stub.stop)

    def _host(self):
        host = _Host("41", _info("41", "Implementing"))
        host._get_focused_pane_id = lambda: host._focused_pane_id
        host._confirm_drop_frozen = lambda snap: host.log.append(
            ("drop-confirm", snap.pane.pane_id))
        host._on_kill_confirmed = types.MethodType(
            ma.MonitorApp._on_kill_confirmed, host)
        return host

    def _open(self, host):
        ma.MonitorApp.action_kill_pane(host)
        (screen, callback), = host.pushed
        self.assertEqual(screen, ("dialog", "%7"))
        host.log.clear()
        return callback

    def _add_live_b(self, host):
        host._snapshots["%8"] = SimpleNamespace(
            pane=SimpleNamespace(pane_id="%8", session_name="s1",
                                 window_name="agent-pick-99"),
            frozen=False, frozen_record_id="")

    def test_live_control_is_killed(self):
        host = self._host()
        self._open(host)(True)
        self.assertEqual(host.log, [
            ("read", "%7", "@aitask_frozen"), ("kill", "%7"),
            ("notify", "Killed agent-pick-41"), ("call_later",)])
        self.assertIsNone(host._focused_pane_id)

    def _assert_not_killed(self, host, message):
        self.assertNotIn("kill", [entry[0] for entry in host.log])
        self.assertIn((message, "warning"), host.notes)

    _FROZEN = "agent-pick-41 is frozen — not killed; press k again to drop it"

    def test_frozen_meanwhile_snapshot(self):
        host = self._host()
        callback = self._open(host)
        host._snapshots["%7"].frozen = True
        callback(True)
        self._assert_not_killed(host, self._FROZEN)

    def test_frozen_meanwhile_on_the_live_read(self):
        host = self._host()
        callback = self._open(host)
        host.pane_option["%7"] = (True, "rec-1")
        callback(True)
        self._assert_not_killed(host, self._FROZEN)

    def test_cached_record_with_a_cleared_live_stamp(self):
        host = self._host()
        callback = self._open(host)
        host.cached["%7"] = SimpleNamespace(frozen_record="rec-1")
        callback(True)
        self._assert_not_killed(host, self._FROZEN)
        # The cache answered; the live read never had to.
        self.assertNotIn(("read", "%7", "@aitask_frozen"), host.log)

    def test_unverified_read_fails_closed(self):
        host = self._host()
        callback = self._open(host)
        host.pane_option["%7"] = (False, "")
        callback(True)
        self._assert_not_killed(
            host, "Could not confirm agent-pick-41 is still live — not killed")

    def test_focus_moving_to_a_live_agent_never_redirects_the_kill(self):
        """The dialog described A; A froze and refresh moved focus to live B.
        Neither is killed, and B is never even read."""
        host = self._host()
        callback = self._open(host)
        host._snapshots["%7"].frozen = True
        self._add_live_b(host)
        host._focused_pane_id = "%8"
        callback(True)
        self._assert_not_killed(host, self._FROZEN)
        self.assertNotIn("%8", [entry[1] for entry in host.log
                                if len(entry) > 1])
        self.assertEqual(host._focused_pane_id, "%8")

    def test_focus_move_control_kills_the_described_pane_and_keeps_focus(self):
        host = self._host()
        callback = self._open(host)
        self._add_live_b(host)
        host._focused_pane_id = "%8"
        callback(True)
        self.assertEqual([e for e in host.log if e[0] == "kill"],
                         [("kill", "%7")])
        self.assertEqual(host._focused_pane_id, "%8")

    def test_frozen_at_open_still_routes_to_the_leased_drop(self):
        host = self._host()
        host._snapshots["%7"].frozen = True
        ma.MonitorApp.action_kill_pane(host)
        self.assertEqual(host.log, [("drop-confirm", "%7")])
        self.assertEqual(host.pushed, [])


def _real_core_monitor(frozen_record: str):
    """A real `TmuxMonitor` — real `get_pane`, `get_pane_option_sync` and
    `kill_agent_pane_smart` — over a scripted `tmux_run`. Its discovery cache
    names ``frozen_record`` while the live option reads a VERIFIED empty value:
    the state a liveness-only restore leaves until discovery refreshes."""
    mon = mc.TmuxMonitor.__new__(mc.TmuxMonitor)
    mon.session = "s1"
    mon._pane_cache = {"%7": mc.TmuxPaneInfo(
        window_index="1", window_name="agent-pick-41", pane_index="0",
        pane_id="%7", pane_pid=1, current_command="claude", width=80,
        height=24, category=mc.PaneCategory.AGENT, session_name="s1",
        frozen_record=frozen_record)}
    mon._last_content, mon._last_change_time = {}, {}
    mon.tmux_calls, mon.dropped = [], []

    def tmux_run(args, timeout=5.0):
        mon.tmux_calls.append(list(args))
        if args[0] == "show-options":
            return (0, "")
        if args[0] == "display-message":
            return (0, "%7")
        # `list-panes` answers no other agent in the window, so the smart kill
        # takes its whole-window branch — the one that retires the record.
        return (0, "")

    mon.tmux_run = tmux_run
    mon._drop_session_record = lambda rid: mon.dropped.append(rid) or True
    return mon


class RealSmartKillCacheTests(unittest.TestCase):
    """Pins the guard against the REAL consumer of the cached record (t2065)."""

    def _confirm(self, mon):
        host = _Host("41", _info("41", "Implementing"))
        host._monitor = mon
        ma.MonitorApp._on_kill_confirmed(host, True, "%7")
        return host

    def test_cached_record_with_empty_live_stamp_drops_nothing(self):
        mon = _real_core_monitor("rec-1")
        self._confirm(mon)
        self.assertEqual(mon.dropped, [])
        self.assertNotIn(["kill-pane", "-t", "%7"], mon.tmux_calls)
        self.assertNotIn(["kill-window", "-t", "%7"], mon.tmux_calls)

    def test_control_live_pane_is_killed_with_no_drop(self):
        mon = _real_core_monitor("")
        self._confirm(mon)
        self.assertIn(["kill-window", "-t", "%7"], mon.tmux_calls)
        self.assertEqual(mon.dropped, [])

    def test_the_smart_kill_itself_would_drop_the_cached_record(self):
        """Why the guard reads the cache: unguarded, the real smart kill
        drops the stale record even though the live stamp is empty."""
        mon = _real_core_monitor("rec-1")
        self.assertEqual(mon.get_pane_option_sync("%7", mc.FROZEN_OPTION),
                         (True, ""))
        mon.kill_agent_pane_smart("%7")
        self.assertEqual(mon.dropped, ["rec-1"])


if __name__ == "__main__":
    unittest.main()
