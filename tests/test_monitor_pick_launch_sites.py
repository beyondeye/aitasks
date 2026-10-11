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
  parent / archived / Done heuristic only, and the tmux result notifies
  "Launched agent for t<id>";
- restart path: the kill runs INSIDE the callback, BEFORE `launch_in_tmux`, and
  notifies "Restarted agent for t<id>";
- both: a launch error returns before `call_later`; cancel only refreshes; the
  launch reads `screen.full_command` (the user may edit it in the dialog).

Only the four construction seams depend on where the screen is built; they are
patched on `SEAM`, the one line the refactor moves. The assertions do not change.

Run: python3 tests/test_monitor_pick_launch_sites.py
"""
from __future__ import annotations

import os
import sys
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
        snap = SimpleNamespace(pane=SimpleNamespace(
            pane_id="%7", session_name="s1", window_name="agent-pick-41"))
        self._snapshots = {"%7": snap}
        log = self.log

        class _Cache:
            def get_task_id_for_pane(self, pane):
                return current_task

            def get_task_info(self, task_id, sess):
                return info

        class _Monitor:
            def kill_agent_pane_smart(self, pane_id):
                log.append(("kill", pane_id))
                return (True, "killed")

        self._task_cache = _Cache()
        self._monitor = _Monitor()
        self._refresh_data = object()

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
                self.assertEqual(host.log, [
                    ("kill", "%7"), ("notify", "Killed agent-pick-41"), ("push",)])
                self.assertIsNone(host._focused_pane_id)

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
            ("kill", "%7"), ("notify", "Killed agent-pick-41"),
            ("launch", "cmd --go"), ("notify", "Launch failed: boom")])

    def test_cancel_only_refreshes(self):
        host, _ = self._open()
        _, callback = host.pushed[0]
        host.log.clear()
        callback(None)
        self.assertEqual(host.log, [("call_later",)])


if __name__ == "__main__":
    unittest.main()
