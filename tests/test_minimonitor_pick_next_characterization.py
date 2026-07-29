"""Characterization tests for the minimonitor `n` launch path (t1310).

``_launch_pick_for_own`` (minimonitor_app.py) launches an agent and then kills a
tmux pane, and until this file existed it had **no unit coverage at all** — the
only reference was a ``hasattr`` smoke check in
``tests/test_multi_session_minimonitor.sh``. t1310 extracts a shared
``_launch_pick`` out of it so the new ``p`` (pick-by-number) command and ``n``
use one implementation, and this suite is what makes that refactor safe.

**These tests were written against the pre-refactor code and must pass
unchanged afterwards.** Each one pins a behaviour that is easy to "clean up"
into a silent change:

- the launch reads ``screen.full_command``, not the pre-resolved ``full_cmd``
  (the user can change agent/model inside ``AgentCommandScreen``);
- ``current_info`` is read *before* ``push_screen``, so a task completing while
  the dialog is open cannot flip the kill decision;
- ``_launch_pick_for_own`` deliberately does **not** invalidate the task cache
  (it reuses the entry ``action_pick_next_for_own`` just refreshed);
- the launch-failure branch returns *before* ``call_later``, while cancel and
  "run" fall through to it;
- ``self._monitor is None`` returns **silently** here, unlike
  ``action_pick_next_for_own`` which notifies;
- ``_focused_pane_id`` is cleared only on the kill branch.

Reference: tests/test_minimonitor_own_task_info.py (t1282, shared app-stub style).

Run: python3 tests/test_minimonitor_pick_next_characterization.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_core import PaneCategory, TaskInfo  # noqa: E402

_ROOT = Path("/proj/alpha")


def _task_info(task_id: str, status: str = "Implementing") -> TaskInfo:
    return TaskInfo(
        task_id=task_id,
        task_file=f"aitasks/t{task_id}_x.md",
        title=f"task {task_id}",
        priority="medium",
        effort="low",
        issue_type="bug",
        status=status,
        body="body",
        plan_content=None,
    )


def _snap(pane_id: str, window_index: str = "1", session: str = "s1"):
    return SimpleNamespace(
        pane=SimpleNamespace(
            pane_id=pane_id,
            session_name=session,
            window_index=window_index,
            window_name=f"agent-pick-{window_index}",
            category=PaneCategory.AGENT,
        )
    )


class _FakeTaskCache:
    """Returns a fixed TaskInfo (or None) and records every call."""

    def __init__(self, info: TaskInfo | None) -> None:
        self._info = info
        self.calls: list[tuple[str, str]] = []
        self.invalidated: list[tuple[str, str]] = []

    def get_task_info(self, task_id, session_name=""):
        self.calls.append((task_id, session_name))
        return self._info

    def invalidate(self, task_id, session_name=""):
        self.invalidated.append((task_id, session_name))


class _FakeMonitor:
    def __init__(self, log: list[str]) -> None:
        self._log = log
        self.killed: list[str] = []

    def get_session_to_project_mapping(self):
        return {"s1": _ROOT}

    def kill_agent_pane_smart(self, pane_id):
        self._log.append("kill")
        self.killed.append(pane_id)
        return (True, False)


class _FakeScreen:
    """Stands in for AgentCommandScreen; only `full_command` is read back."""

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.full_command = args[1] if len(args) > 1 else ""


def _mk_app(info: TaskInfo | None, log: list[str], monitor: bool = True):
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._snapshots = {}
    app._task_cache = _FakeTaskCache(info)
    app._session = "s1"
    app._project_root = Path("/proj/fallback")
    app._focused_pane_id = "%sentinel"
    app._monitor = _FakeMonitor(log) if monitor else None
    app.spy_notify = []
    app.spy_pushed = []
    app.spy_later = []
    app.notify = lambda msg, **kw: app.spy_notify.append(
        (msg, kw.get("severity", "information"))
    )
    app.push_screen = lambda screen, callback=None: app.spy_pushed.append(
        (screen, callback)
    )
    app.call_later = lambda fn, *a: app.spy_later.append(fn)
    app._refresh_data = lambda: None
    return app


class _Harness:
    """Drives `_launch_pick_for_own` end to end and captures the effects."""

    def __init__(self, testcase, *, task_id="123_4", status="Implementing",
                 info_missing=False, monitor=True, dry_run="cmd --go",
                 target_id="123_5"):
        self.log: list[str] = []
        info = None if info_missing else _task_info(task_id, status)
        self.app = _mk_app(info, self.log, monitor=monitor)
        self.task_id = task_id
        self.target_id = target_id
        self.pane_id = "%own"
        self.app._snapshots[self.pane_id] = _snap(self.pane_id)
        self.dry_run = dry_run
        self.launch_result: tuple[int | None, str | None] = (1234, None)
        self.launched: list[tuple[str, object]] = []
        self.spawned: list[tuple[str, str]] = []
        self._tc = testcase

    def _launch(self, command, config):
        self.log.append("launch")
        self.launched.append((command, config))
        return self.launch_result

    def _spawn(self, session, window):
        self.spawned.append((session, window))

    def run(self):
        """Invoke the action; return (screen, callback) for the pushed dialog."""
        with patch.object(mm, "resolve_dry_run_command",
                          return_value=self.dry_run), \
             patch.object(mm, "resolve_agent_string", return_value="claudecode/x"), \
             patch.object(mm, "resolve_skill_profile", return_value="fast"), \
             patch.object(mm, "AgentCommandScreen", _FakeScreen), \
             patch.object(mm, "launch_in_tmux", self._launch), \
             patch.object(mm, "maybe_spawn_minimonitor", self._spawn):
            self.app._launch_pick_for_own(
                self.target_id, self.pane_id, self.task_id, "s1"
            )
            if not self.app.spy_pushed:
                return None, None
            screen, callback = self.app.spy_pushed[0]
            self._screen = screen
            self._callback = callback
            return screen, callback

    def confirm(self, result):
        """Invoke the pushed dialog's callback with `result`, inside the patches."""
        with patch.object(mm, "launch_in_tmux", self._launch), \
             patch.object(mm, "maybe_spawn_minimonitor", self._spawn):
            self._callback(result)


def _cfg(new_window=True, session="s1", window="agent-pick-123_5"):
    return mm.TmuxLaunchConfig(session=session, window=window,
                               new_session=False, new_window=new_window)


class GoldenLaunchArgsTests(unittest.TestCase):
    """The AgentCommandScreen construction `p` must reproduce exactly."""

    def test_screen_constructed_with_expected_args(self):
        h = _Harness(self)
        screen, _ = h.run()
        self.assertIsNotNone(screen)
        self.assertEqual(
            screen.args,
            ("Pick Task t123_5", "cmd --go", "/aitask-pick 123_5"),
        )
        self.assertEqual(screen.kwargs, {
            "default_window_name": "agent-pick-123_5",
            "project_root": _ROOT,
            "operation": "pick",
            "operation_args": ["123_5"],
            "default_agent_string": "claudecode/x",
            "skill_name": "pick",
            "default_profile": "fast",
            "narrow": True,
        })

    def test_project_root_comes_from_snapshot_session(self):
        """_root_for_snap resolves via the monitor's session mapping, not the
        minimonitor's own project root."""
        h = _Harness(self)
        screen, _ = h.run()
        self.assertEqual(screen.kwargs["project_root"], _ROOT)
        self.assertNotEqual(screen.kwargs["project_root"], h.app._project_root)


class LaunchCommandSourceTests(unittest.TestCase):
    def test_launch_uses_screen_full_command_not_resolved_command(self):
        """The user can change agent/model in the dialog, which rewrites
        `screen.full_command`. Closing over the pre-resolved string would
        silently break model selection."""
        h = _Harness(self)
        screen, _ = h.run()
        screen.full_command = "cmd --other-model"
        h.confirm(_cfg())
        self.assertEqual([c for c, _ in h.launched], ["cmd --other-model"])


class KillHeuristicTests(unittest.TestCase):
    def _kill_for(self, task_id, status=None, info_missing=False):
        h = _Harness(self, task_id=task_id,
                     status=status or "Implementing",
                     info_missing=info_missing)
        h.run()
        h.confirm(_cfg())
        return h

    def test_parent_task_id_kills(self):
        h = self._kill_for("123")
        self.assertEqual(h.app._monitor.killed, ["%own"])

    def test_child_done_kills(self):
        h = self._kill_for("123_4", status="Done")
        self.assertEqual(h.app._monitor.killed, ["%own"])

    def test_child_with_missing_task_file_kills(self):
        h = self._kill_for("123_4", info_missing=True)
        self.assertEqual(h.app._monitor.killed, ["%own"])

    def test_child_still_implementing_does_not_kill(self):
        h = self._kill_for("123_4", status="Implementing")
        self.assertEqual(h.app._monitor.killed, [])

    def test_focused_pane_cleared_only_on_kill(self):
        killed = self._kill_for("123")
        self.assertIsNone(killed.app._focused_pane_id)
        spared = self._kill_for("123_4", status="Implementing")
        self.assertEqual(spared.app._focused_pane_id, "%sentinel")


class LaunchBeforeKillOrderingTests(unittest.TestCase):
    def test_launch_precedes_kill(self):
        """The minimonitor shares the followed agent's window, so killing first
        would tear down this app before the next agent exists."""
        h = _Harness(self, task_id="123")
        h.run()
        h.confirm(_cfg())
        self.assertEqual(h.log, ["launch", "kill"])


class NonLaunchResultTests(unittest.TestCase):
    def test_cancel_does_not_launch_or_kill_but_refreshes(self):
        h = _Harness(self, task_id="123")
        h.run()
        h.confirm(None)
        self.assertEqual(h.launched, [])
        self.assertEqual(h.app._monitor.killed, [])
        self.assertEqual(len(h.app.spy_later), 1)

    def test_run_in_terminal_does_not_launch_or_kill_but_refreshes(self):
        """AgentCommandScreen can dismiss the string "run" (run in terminal)."""
        h = _Harness(self, task_id="123")
        h.run()
        h.confirm("run")
        self.assertEqual(h.launched, [])
        self.assertEqual(h.app._monitor.killed, [])
        self.assertEqual(len(h.app.spy_later), 1)

    def test_launch_failure_skips_kill_spawn_and_refresh(self):
        """The error branch returns *before* call_later — an asymmetry that is
        easy to 'tidy' into a single tail refresh."""
        h = _Harness(self, task_id="123")
        h.launch_result = (None, "tmux new-window failed (rc=1)")
        h.run()
        h.confirm(_cfg())
        self.assertEqual(h.app._monitor.killed, [])
        self.assertEqual(h.spawned, [])
        self.assertEqual(h.app.spy_later, [])
        self.assertEqual(
            h.app.spy_notify,
            [("Launch failed: tmux new-window failed (rc=1)", "error")],
        )


class CompanionSpawnTests(unittest.TestCase):
    def test_spawns_minimonitor_for_new_window(self):
        h = _Harness(self)
        h.run()
        h.confirm(_cfg(new_window=True))
        self.assertEqual(h.spawned, [("s1", "agent-pick-123_5")])

    def test_no_spawn_when_splitting_an_existing_window(self):
        h = _Harness(self)
        h.run()
        h.confirm(_cfg(new_window=False))
        self.assertEqual(h.spawned, [])


class GuardTests(unittest.TestCase):
    def test_monitor_none_returns_silently(self):
        """Deliberately silent here — action_pick_next_for_own notifies
        'Monitor not ready' at its own entry instead."""
        h = _Harness(self, monitor=False)
        screen, _ = h.run()
        self.assertIsNone(screen)
        self.assertEqual(h.app.spy_notify, [])

    def test_missing_snapshot_warns_and_does_not_push(self):
        h = _Harness(self)
        h.app._snapshots.clear()
        screen, _ = h.run()
        self.assertIsNone(screen)
        self.assertEqual(
            h.app.spy_notify, [("Followed agent no longer exists", "warning")]
        )

    def test_unresolvable_command_errors_and_does_not_push(self):
        h = _Harness(self, dry_run=None)
        screen, _ = h.run()
        self.assertIsNone(screen)
        self.assertEqual(
            h.app.spy_notify,
            [("Failed to resolve pick command for t123_5", "error")],
        )


class DecisionTimingTests(unittest.TestCase):
    def test_task_info_read_before_dialog_is_pushed(self):
        """The kill decision must be pinned before AgentCommandScreen opens —
        otherwise a task completing while the dialog is up flips it."""
        h = _Harness(self)
        h.run()
        self.assertEqual(h.app._task_cache.calls, [("123_4", "s1")])
        self.assertEqual(len(h.app.spy_pushed), 1)

    def test_does_not_invalidate_the_task_cache(self):
        """It reuses the entry action_pick_next_for_own just refreshed; adding
        an invalidate here would change n's kill decision."""
        h = _Harness(self)
        h.run()
        h.confirm(_cfg())
        self.assertEqual(h.app._task_cache.invalidated, [])


if __name__ == "__main__":
    unittest.main()
