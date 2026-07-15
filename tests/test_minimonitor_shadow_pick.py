"""Tests for the minimonitor `E` shadow-with-agent-picker shortcut (t1152).

Mock-based (no live tmux). The uppercase `E` shortcut opens the narrow
`AgentCommandScreen` for `operation="shadow"` so the user can confirm / change
the code agent and model, then — on confirm — launches the shadow via the shared
`_spawn_shadow` helper with the SAME specialized split placement and
`@aitask_shadow_target` stamp + cleanup-hook wiring as the fire-and-forget `e`
shortcut. Covers:

- binding + footer-hint registration (and the untouched `e` negative control);
- the duplicate-shadow guard firing BEFORE the dialog opens;
- the dialog opened with the shadow contract (operation/narrow/args/prompt);
- the confirm path launching with `screen.full_command` and running the full
  post-launch stamp + cleanup-hook wiring;
- cancel / "run" launching nothing.

Reference: tests/test_tui_switcher_agent_launch.py (t1148),
tests/test_minimonitor_concern_action.py (shared app-stub style).

Run: python3 tests/test_minimonitor_shadow_pick.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from monitor import minimonitor_app as mm  # noqa: E402
from agent_command_screen import AgentCommandScreen  # noqa: E402
from agent_launch_utils import TmuxLaunchConfig  # noqa: E402


class _FakeMon:
    """Stub TmuxMonitor exposing only the sync gateway the lookups/stamp use."""

    def __init__(self, sync_list: str = "") -> None:
        self._sync_list = sync_list
        self.sync_calls: list = []

    def tmux_run(self, args, timeout=5.0):
        self.sync_calls.append(args)
        return (0, self._sync_list)


class _FakeTaskCache:
    def __init__(self, task_id: str | None = "42") -> None:
        self._task_id = task_id

    def get_task_id_for_pane(self, pane):
        return self._task_id


def _snap(pane_id="%1", session="s1", window="agent-w"):
    return SimpleNamespace(
        pane=SimpleNamespace(
            pane_id=pane_id, session_name=session, window_name=window
        )
    )


def _mk_app(monitor=None, task_id="42"):
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._monitor = monitor
    app._session = "s1"
    app._task_cache = _FakeTaskCache(task_id)
    app.spy_notify: list = []
    app.spy_pushed: list = []
    app.notify = lambda msg, **kw: app.spy_notify.append(
        (msg, kw.get("severity", "information"))
    )
    app.push_screen = lambda screen, callback=None: app.spy_pushed.append(
        (screen, callback)
    )
    app.call_later = lambda *a, **k: None
    app._find_own_agent_snapshot = lambda: _snap("%1")
    app._root_for_snap = lambda snap: Path("/p1")
    return app


class BindingHintRegistrationTests(unittest.TestCase):
    def test_pick_binding_present(self):
        match = [
            b for b in mm.MiniMonitorApp.BINDINGS
            if getattr(b, "action", None) == "launch_shadow_pick"
        ]
        self.assertEqual(len(match), 1, "exactly one launch_shadow_pick binding")
        self.assertEqual(match[0].key, "E")

    def test_fire_and_forget_e_untouched(self):
        # Negative control: the picker variant must not disturb the original
        # `e` fire-and-forget shadow binding.
        match = [
            b for b in mm.MiniMonitorApp.BINDINGS
            if getattr(b, "action", None) == "launch_shadow"
        ]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0].key, "e")

    def test_footer_hint_advertises_E(self):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        hints = [
            w for w in app.compose()
            if getattr(w, "id", "") == "mini-key-hints"
        ]
        self.assertEqual(len(hints), 1)
        self.assertIn("e/E:shadow", str(hints[0].render()))


class DuplicateGuardTests(unittest.TestCase):
    def test_guard_fires_before_dialog(self):
        mon = _FakeMon(sync_list="%5\t%1")  # an existing shadow bound to %1
        app = _mk_app(mon)
        with patch.object(mm, "resolve_dry_run_command",
                          return_value="claude /aitask-shadow %1 42"), \
             patch.object(mm, "resolve_agent_string",
                          return_value="claudecode/opus4_8"):
            app.action_launch_shadow_pick()
        self.assertEqual(app.spy_pushed, [], "no dialog on duplicate")
        self.assertTrue(
            any("already running" in m.lower() for m, _ in app.spy_notify)
        )
        self.assertTrue(mon.sync_calls, "guard used the sync reader")


class DialogContractTests(unittest.TestCase):
    def _push(self, task_id="42"):
        app = _mk_app(_FakeMon(sync_list=""), task_id=task_id)  # no shadow yet
        with patch.object(mm, "resolve_dry_run_command",
                          return_value="claude /aitask-shadow %1 42"), \
             patch.object(mm, "resolve_agent_string",
                          return_value="claudecode/opus4_8"):
            app.action_launch_shadow_pick()
        self.assertEqual(len(app.spy_pushed), 1)
        return app, app.spy_pushed[0]

    def test_dialog_opened_with_shadow_contract(self):
        _app, (screen, _cb) = self._push()
        self.assertIsInstance(screen, AgentCommandScreen)
        self.assertEqual(screen.operation, "shadow")
        self.assertTrue(screen._narrow, "narrow minimonitor layout")
        self.assertEqual(screen.operation_args, ["%1", "42"])
        self.assertEqual(screen.prompt_str, "/aitask-shadow %1 42")

    def test_operation_args_without_task_id(self):
        # No resolvable task id → args carry only the followed pane.
        _app, (screen, _cb) = self._push(task_id=None)
        self.assertEqual(screen.operation_args, ["%1"])


class ConfirmPathTests(unittest.TestCase):
    def _push_and_get_cb(self, app):
        with patch.object(mm, "resolve_dry_run_command",
                          return_value="claude /aitask-shadow %1 42"), \
             patch.object(mm, "resolve_agent_string",
                          return_value="claudecode/opus4_8"):
            app.action_launch_shadow_pick()
        self.assertEqual(len(app.spy_pushed), 1)
        return app.spy_pushed[0]  # (screen, callback)

    def test_confirm_launches_full_command_and_wires_lifecycle(self):
        mon = _FakeMon(sync_list="")  # guard: no existing shadow
        app = _mk_app(mon)
        screen, callback = self._push_and_get_cb(app)

        with patch.object(mm, "launch_in_tmux",
                          return_value=(999, None)) as mock_launch, \
             patch.object(mm, "resolve_pane_id_by_pid",
                          return_value="%9") as mock_resolve, \
             patch.object(mm, "attach_shadow_cleanup_hook") as mock_hook, \
             patch.object(mm, "_load_project_tmux_config", return_value={}):
            callback(TmuxLaunchConfig("s1", "w", new_session=False, new_window=False))

        # Launched with the (post-override) dialog command, not a stale capture.
        self.assertEqual(mock_launch.call_count, 1)
        self.assertEqual(mock_launch.call_args.args[0], screen.full_command)

        # New pane resolved from its pid, then stamped @aitask_shadow_target -> %1.
        mock_resolve.assert_called_once()
        stamp_calls = [
            c for c in mon.sync_calls
            if len(c) >= 2 and c[0] == "set-option"
            and mm.SHADOW_TARGET_OPTION in c
        ]
        self.assertEqual(len(stamp_calls), 1, "one @aitask_shadow_target stamp")
        stamp = stamp_calls[0]
        self.assertIn("%9", stamp, "stamp targets the new shadow pane")
        self.assertEqual(stamp[-1], "%1", "stamp value = followed agent pane")

        # Cleanup hook bound to the followed agent pane so the shadow dies with it.
        mock_hook.assert_called_once()
        self.assertEqual(mock_hook.call_args.args[0], "%1")

    def test_cancel_and_run_launch_nothing(self):
        app = _mk_app(_FakeMon(sync_list=""))
        _screen, callback = self._push_and_get_cb(app)
        with patch.object(mm, "launch_in_tmux") as mock_launch:
            callback(None)   # dialog cancelled
            callback("run")  # "open in terminal" is not a shadow placement
        self.assertFalse(mock_launch.called)


if __name__ == "__main__":
    unittest.main()
