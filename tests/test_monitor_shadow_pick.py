"""Tests for shadow SPAWN (`e` / `E`) in the FULL monitor (t1216_4).

Mirrors `tests/test_minimonitor_shadow_pick.py` for the monitor, and pins the
four lifecycle contracts the lift into `monitor_core.spawn_shadow` exposes. The
tests that fail on the un-fixed code:

* **PINNED companion pane.** `aitask_companion_cleanup.sh` job 2 runs
  `kill-pane -t "$companion"` with **no marker check**, so if the monitor passed
  its own `TMUX_PANE` the followed agent's exit would kill the monitor — on a
  delay, long after the session that armed it ended. The monitor must pass the
  **shadow** pane. Asserted as a complete call plus a sentinel negative control.
* **Focus preservation.** Both placement branches select the new pane's window
  (`select-window` on the split branch; `new-window` without `-d` creates *and*
  selects), so an unfixed spawn yanks the client out of `ait monitor`.
* **Fail-closed duplicate guard.** `find_shadow_pane` returns None both for "no
  shadow" and for a failed query, so gating a *create* on it spawns a second
  shadow whenever `list-panes` fails. And the cache (`_current_shadow_pane_id`)
  cannot report a shadow it has not observed yet — a 3–6s double-spawn window.
* **Stamp verification.** An unstamped shadow is indistinguishable from a real
  agent forever: it lists as an agent, is targeted by `k`/`n`, counts as a real
  sibling, evades the duplicate guard, and — because the cleanup script matches
  on the marker — is never cleaned up.
* **Hook idempotence.** `set-hook -p … pane-died` writes index `[0]` and so
  replaces whatever sits there; overwriting a minimonitor's companion hook
  orphans it, and overwriting an unrelated hook destroys it silently.

Socket-contained per `tests/lib/tmux_socket_containment.py`: the mocks are the
primary protection, the throwaway socket is the belt, and containment is asserted
statically via `socket_args` — never by attempting a launch.

Run: python3 tests/test_monitor_shadow_pick.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

# MonitorApp.on_mount takes the deterministic not-inside-tmux path only when the
# ambient tmux env is absent; scrub it before importing.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_launch_utils  # noqa: E402
from monitor import monitor_app as ma  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from monitor.monitor_app import MonitorApp, Zone  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxPaneInfo,
)
from agent_command_screen import AgentCommandScreen  # noqa: E402
from agent_launch_utils import TmuxLaunchConfig  # noqa: E402
from tmux_socket_containment import TmuxSocketContainmentMixin  # noqa: E402


def _pane(
    pane_id: str,
    window_name: str = "agent-1",
    category: PaneCategory = PaneCategory.AGENT,
) -> TmuxPaneInfo:
    idx = int(pane_id.lstrip("%"))
    return TmuxPaneInfo(
        window_index=str(idx), window_name=window_name, pane_index="0",
        pane_id=pane_id, pane_pid=1000 + idx, current_command="bash",
        width=80, height=24, category=category, session_name="demo",
        shadow_target="",
    )


def _snap(pane: TmuxPaneInfo) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane, content="idle output", timestamp=0.0, idle_seconds=0.0,
        is_idle=False,
    )


class _FakeMon:
    """Duck-typed monitor: the sync gateway the guard / stamp / kill use.

    `sync_list` is the `list-panes` payload the duplicate guard reads.
    `stamp_rc` drives the `@aitask_shadow_target` write (C4). `rc` applies to the
    `list-panes` query so the fail-closed path can be driven.
    """

    multi_session = False

    def __init__(self, sync_list="", rc=0, stamp_rc=0,
                 shadow_by_followed=None, list_panes_hook=None):
        self._sync_list = sync_list
        self._rc = rc
        self._stamp_rc = stamp_rc
        self._shadow_by_followed = dict(shadow_by_followed or {})
        self._list_panes_hook = list_panes_hook
        self.sync_calls: list = []

    def tmux_run(self, args, timeout=5.0):
        self.sync_calls.append(args)
        if args and args[0] == "list-panes":
            if self._list_panes_hook is not None:
                return self._list_panes_hook(len(self.sync_calls))
            return (self._rc, self._sync_list)
        if args and args[0] == "set-option":
            return (self._stamp_rc, "")
        return (0, "")

    def get_shadow_snapshot(self, followed_pane_id):
        return self._shadow_by_followed.get(followed_pane_id)

    def get_session_to_project_mapping(self):
        return {"demo": Path("/p1")}

    def get_compare_mode(self, pane_id):
        return "stripped"

    def is_compare_mode_overridden(self, pane_id):
        return False


class _FakeTaskCache:
    def __init__(self, task_id="42"):
        self._task_id = task_id

    def get_task_id_for_pane(self, pane):
        return self._task_id


def _mk_app(monitor=None, focused="%1", task_id="42",
            category=PaneCategory.AGENT):
    """A MonitorApp with __init__ bypassed and only the fields under test set."""
    app = MonitorApp.__new__(MonitorApp)
    app._monitor = monitor if monitor is not None else _FakeMon()
    app._session = "demo"
    app._project_root = Path("/p1")
    app._focused_pane_id = focused
    app._snapshots = {"%1": _snap(_pane("%1", category=category))}
    app._task_cache = _FakeTaskCache(task_id)
    app._active_zone = Zone.PANE_LIST
    app.spy_notify: list = []
    app.spy_pushed: list = []
    app.spy_later: list = []
    app.notify = lambda msg, **kw: app.spy_notify.append(
        (msg, kw.get("severity", "information"))
    )
    app.push_screen = lambda screen, callback=None: app.spy_pushed.append(
        (screen, callback)
    )
    app.call_later = lambda *a, **k: app.spy_later.append(a)
    return app


def _notified(app, needle):
    return any(needle.lower() in m.lower() for m, _ in app.spy_notify)


class _SpawnMocks:
    """Context manager installing the monitor_core-level spawn mocks.

    Patch targets are on `mc` on purpose: the body was lifted there, so patching
    `ma` would intercept nothing and reach real tmux.
    """

    def __init__(self, tmux_cfg=None, pane_id="%9", launch=(999, None),
                 hook_status="installed"):
        self._tmux_cfg = {} if tmux_cfg is None else tmux_cfg
        self._pane_id = pane_id
        self._launch = launch
        self._hook_status = hook_status

    def __enter__(self):
        self._patches = [
            patch.object(mc, "launch_in_tmux", return_value=self._launch),
            patch.object(mc, "resolve_pane_id_by_pid",
                         return_value=self._pane_id),
            patch.object(mc, "attach_companion_cleanup_hook",
                         return_value=self._hook_status),
            patch.object(mc, "load_project_tmux_config",
                         return_value=self._tmux_cfg),
            patch.object(ma, "resolve_dry_run_command",
                         return_value="claude /aitask-shadow %1 42"),
            patch.object(ma, "resolve_agent_string",
                         return_value="claudecode/opus4_8"),
        ]
        self.launch, self.resolve, self.hook, self.cfg, self.dry, self.agent = (
            p.start() for p in self._patches
        )
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        return False


# -- Bindings / footer ---------------------------------------------------------


class BindingRegistrationTests(unittest.TestCase):
    def _bindings_for(self, action):
        return [
            b for b in MonitorApp.BINDINGS
            if getattr(b, "action", None) == action
        ]

    def test_launch_shadow_binding(self):
        match = self._bindings_for("launch_shadow")
        self.assertEqual(len(match), 1, "exactly one launch_shadow binding")
        self.assertEqual(match[0].key, "e")
        self.assertTrue(match[0].show)

    def test_launch_shadow_pick_binding(self):
        match = self._bindings_for("launch_shadow_pick")
        self.assertEqual(len(match), 1, "exactly one launch_shadow_pick binding")
        self.assertEqual(match[0].key, "E")
        self.assertTrue(match[0].show)

    def test_multi_session_now_shown(self):
        # A distinct operation surfaced nowhere else -- it belongs in the footer.
        match = self._bindings_for("toggle_multi_session")
        self.assertEqual(len(match), 1)
        self.assertTrue(match[0].show)

    def test_f5_stays_hidden_because_it_aliases_r(self):
        # Encodes the justification, not just the flag: f5 is hidden *because* it
        # is an alias of an already-visible binding with the same action.
        f5 = [b for b in MonitorApp.BINDINGS if b.key == "f5"]
        r = [b for b in MonitorApp.BINDINGS if b.key == "r"]
        self.assertEqual(len(f5), 1)
        self.assertEqual(len(r), 1)
        self.assertFalse(f5[0].show)
        self.assertTrue(r[0].show)
        self.assertEqual(f5[0].action, r[0].action)

    def test_concerns_binding_untouched(self):
        # Negative control: adding e/E must not disturb the t1216_3 `c` binding.
        match = self._bindings_for("pick_concerns")
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0].key, "c")


class ZoneGatingTests(unittest.TestCase):
    def test_disabled_in_preview_zones_enabled_in_pane_list(self):
        app = _mk_app()
        for action in ("launch_shadow", "launch_shadow_pick"):
            for zone in (Zone.PREVIEW, Zone.SHADOW):
                app._active_zone = zone
                self.assertFalse(
                    app.check_action(action, ()),
                    f"{action} must be inert in {zone} (keys forward to tmux)",
                )
            app._active_zone = Zone.PANE_LIST
            self.assertTrue(app.check_action(action, ()))


# -- Selection guards ----------------------------------------------------------


class SelectionGuardTests(unittest.TestCase):
    def test_no_focused_pane_refuses(self):
        app = _mk_app(focused=None)
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        self.assertFalse(m.launch.called)
        self.assertTrue(_notified(app, "focus an agent pane"))

    def test_focused_pane_absent_from_snapshots_refuses(self):
        app = _mk_app(focused="%99")
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        self.assertFalse(m.launch.called)
        self.assertTrue(_notified(app, "focus an agent pane"))

    def test_non_agent_pane_refuses(self):
        # Monitor-only guard: _rebuild_pane_list renders OTHER panes as focusable
        # PaneCards, so the selection can be a shell or lazygit pane.
        app = _mk_app(category=PaneCategory.OTHER)
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        self.assertFalse(m.launch.called)
        self.assertTrue(_notified(app, "only applies to agent panes"))

    def test_non_agent_pane_refuses_before_dialog(self):
        app = _mk_app(category=PaneCategory.OTHER)
        with _SpawnMocks() as m:
            app.action_launch_shadow_pick()
        self.assertEqual(app.spy_pushed, [])
        self.assertFalse(m.launch.called)


# -- Duplicate guard -----------------------------------------------------------


class DuplicateGuardTests(unittest.TestCase):
    def test_existing_shadow_refuses(self):
        mon = _FakeMon(sync_list="%5\t%1")  # a shadow already bound to %1
        app = _mk_app(mon)
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        self.assertFalse(m.launch.called)
        self.assertTrue(_notified(app, "already running"))

    def test_existing_shadow_refuses_before_dialog(self):
        mon = _FakeMon(sync_list="%5\t%1")
        app = _mk_app(mon)
        with _SpawnMocks() as m:
            app.action_launch_shadow_pick()
        self.assertEqual(app.spy_pushed, [], "no dialog just to fail")
        self.assertFalse(m.launch.called)
        self.assertTrue(_notified(app, "already running"))

    def test_cache_is_not_the_guard(self):
        """A stale cache must not license a second shadow.

        `get_shadow_snapshot` reports nothing while live tmux reports a shadow --
        the real 3-6s window between a shadow being spawned and the ~3s
        `commit_snapshots` observing it. This fails if someone swaps the live
        lookup for `_current_shadow_pane_id()`.
        """
        mon = _FakeMon(sync_list="%5\t%1", shadow_by_followed={})
        app = _mk_app(mon)
        self.assertIsNone(app._current_shadow_pane_id(), "cache sees no shadow")
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        self.assertFalse(m.launch.called, "live lookup must still refuse")
        self.assertTrue(_notified(app, "already running"))

    def test_failed_query_fails_closed(self):
        # rc != 0 means "cannot tell", which must not read as "no shadow".
        mon = _FakeMon(sync_list="", rc=1)
        app = _mk_app(mon)
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        self.assertFalse(m.launch.called)
        self.assertTrue(_notified(app, "could not verify"))

    def test_confirm_time_recheck_refuses(self):
        """A shadow that appears while the E dialog is open must not be doubled.

        The pre-dialog guard cannot cover the seconds the picker is open. First
        `list-panes` (the guard) reports nothing; the second (inside spawn_shadow,
        just before launching) reports a live shadow.
        """
        def hook(call_no):
            return (0, "" if call_no == 1 else "%5\t%1")

        mon = _FakeMon(list_panes_hook=hook)
        app = _mk_app(mon)
        with _SpawnMocks() as m:
            app.action_launch_shadow_pick()
            self.assertEqual(len(app.spy_pushed), 1, "dialog did open")
            screen, callback = app.spy_pushed[0]
            callback(TmuxLaunchConfig("demo", "w", new_session=False,
                                      new_window=False))
        self.assertFalse(m.launch.called, "re-check must refuse at confirm time")
        self.assertTrue(_notified(app, "already running"))


# -- Spawn / placement / lifecycle --------------------------------------------


class SpawnContractTests(TmuxSocketContainmentMixin, unittest.TestCase):
    CONTAINED_MODULES = (agent_launch_utils, ma)

    def test_socket_containment_active(self):
        self.assert_contained()

    def test_split_placement_targets_the_agent_pane(self):
        mon = _FakeMon()
        app = _mk_app(mon)
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        self.assertEqual(m.launch.call_count, 1)
        cmd, cfg = m.launch.call_args.args
        self.assertEqual(cmd, "claude /aitask-shadow %1 42")
        self.assertFalse(cfg.new_window)
        self.assertEqual(cfg.split_target_pane, "%1")
        self.assertEqual(cfg.split_size, 60)
        self.assertEqual(cfg.cwd, "/p1")

    def test_separate_window_placement(self):
        mon = _FakeMon()
        app = _mk_app(mon)
        with _SpawnMocks(tmux_cfg={"shadow_same_window": False}) as m:
            app.action_launch_shadow()
        _cmd, cfg = m.launch.call_args.args
        self.assertTrue(cfg.new_window)
        self.assertEqual(cfg.window, "agent-shadow-42")

    def test_unparsable_width_falls_back_to_60(self):
        mon = _FakeMon()
        app = _mk_app(mon)
        with _SpawnMocks(tmux_cfg={"shadow_pane_width": "wide"}) as m:
            app.action_launch_shadow()
        _cmd, cfg = m.launch.call_args.args
        self.assertEqual(cfg.split_size, 60)

    def test_stamp_written_once_targeting_the_new_pane(self):
        mon = _FakeMon()
        app = _mk_app(mon)
        with _SpawnMocks():
            app.action_launch_shadow()
        stamps = [
            c for c in mon.sync_calls
            if c and c[0] == "set-option" and mc.SHADOW_TARGET_OPTION in c
        ]
        self.assertEqual(len(stamps), 1)
        self.assertIn("%9", stamps[0], "stamp targets the new shadow pane")
        self.assertEqual(stamps[0][-1], "%1", "value = followed agent pane")

    def test_focus_is_not_stolen_on_either_branch(self):
        for tmux_cfg in ({}, {"shadow_same_window": False}):
            mon = _FakeMon()
            app = _mk_app(mon)
            with _SpawnMocks(tmux_cfg=tmux_cfg) as m:
                app.action_launch_shadow()
            _cmd, cfg = m.launch.call_args.args
            self.assertIs(
                cfg.select_window, False,
                f"monitor must not steal focus (cfg={tmux_cfg})",
            )


class CompanionPaneContractTests(unittest.TestCase):
    """PINNED (D3): the monitor binds cleanup to the SHADOW, never to itself."""

    def test_hook_bound_to_shadow_pane(self):
        mon = _FakeMon()
        app = _mk_app(mon)
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        m.hook.assert_called_once_with("%1", "%9")

    def test_monitor_tmux_pane_never_passed(self):
        """Negative control: a sentinel TMUX_PANE must appear in no argument.

        If it did, `aitask_companion_cleanup.sh` job 2 -- whose `kill-pane` has no
        marker check -- would close the monitor when the followed agent exits.
        """
        mon = _FakeMon()
        app = _mk_app(mon)
        with patch.dict(os.environ, {"TMUX_PANE": "%77"}), _SpawnMocks() as m:
            app.action_launch_shadow()
        m.hook.assert_called_once_with("%1", "%9")
        for call in m.hook.call_args_list:
            self.assertNotIn("%77", call.args)
            self.assertNotIn("%77", call.kwargs.values())

    def test_spawn_shadow_does_not_read_tmux_pane(self):
        """Structural control: no executable reference to the env var.

        Asserted on the compiled code object rather than `inspect.getsource`,
        because the docstring legitimately names `TMUX_PANE` to document the
        contract -- a source substring scan would false-positive on the
        documentation it is meant to protect.
        """
        code = mc.spawn_shadow.__code__
        literals = [
            c for c in code.co_consts
            if isinstance(c, str) and c != mc.spawn_shadow.__doc__
        ]
        self.assertNotIn("TMUX_PANE", literals)
        self.assertNotIn("environ", code.co_names)


class StampVerificationTests(unittest.TestCase):
    """C4: an unstamped shadow is worse than no shadow, so remove it."""

    def test_stamp_failure_retries_then_kills_the_pane(self):
        mon = _FakeMon(stamp_rc=1)
        app = _mk_app(mon)
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        stamps = [c for c in mon.sync_calls if c and c[0] == "set-option"]
        self.assertEqual(len(stamps), 2, "one retry before giving up")
        kills = [c for c in mon.sync_calls if c and c[0] == "kill-pane"]
        self.assertEqual(kills, [["kill-pane", "-t", "%9"]])
        self.assertFalse(m.hook.called, "no cleanup hook for a dead pane")
        self.assertTrue(
            any(sev == "error" and "%9" in msg for msg, sev in app.spy_notify)
        )

    def test_success_path_installs_hook_once(self):
        mon = _FakeMon()
        app = _mk_app(mon)
        with _SpawnMocks() as m:
            app.action_launch_shadow()
        self.assertEqual(m.hook.call_count, 1)
        self.assertEqual(
            [c for c in mon.sync_calls if c and c[0] == "kill-pane"], []
        )


class LaunchOutcomeTests(unittest.TestCase):
    """D4: schedule_refresh must not fire when the launch itself failed."""

    def test_launch_error_notifies_and_skips_refresh(self):
        mon = _FakeMon()
        app = _mk_app(mon)
        with _SpawnMocks(launch=(None, "boom")) as m:
            app.action_launch_shadow()
        self.assertFalse(m.hook.called)
        self.assertEqual(app.spy_later, [], "no refresh on launch error")
        self.assertTrue(
            any(sev == "error" and "boom" in msg for msg, sev in app.spy_notify)
        )

    def test_success_schedules_one_refresh(self):
        app = _mk_app(_FakeMon())
        with _SpawnMocks():
            app.action_launch_shadow()
        self.assertEqual(len(app.spy_later), 1)

    def test_unclassifiable_pane_warns_and_skips_stamp_and_hook(self):
        mon = _FakeMon()
        app = _mk_app(mon)
        with _SpawnMocks(pane_id=None) as m:
            app.action_launch_shadow()
        self.assertFalse(m.hook.called)
        self.assertEqual(
            [c for c in mon.sync_calls if c and c[0] == "set-option"], []
        )
        self.assertTrue(_notified(app, "could not be classified"))
        self.assertEqual(len(app.spy_later), 1)

    def test_unverified_hook_warns_but_keeps_the_shadow(self):
        app = _mk_app(_FakeMon())
        with _SpawnMocks(hook_status="unverified"):
            app.action_launch_shadow()
        self.assertTrue(_notified(app, "auto-cleanup"))
        self.assertFalse(_notified(app, "launched shadow agent"))


# -- Hook idempotence (C5 + S3), at the agent_launch_utils level ---------------


class _HookTmux:
    """Stub gateway recording set-option / set-hook and scripting show-hooks."""

    def __init__(self, hooks_out="", rc=0):
        self._hooks_out = hooks_out
        self._rc = rc
        self.spawned: list = []
        self.ran: list = []

    def spawn(self, args, **kwargs):
        self.spawned.append(args)

    def run(self, args, timeout=5.0):
        self.ran.append(args)
        if args and args[0] == "show-hooks":
            return (self._rc, self._hooks_out)
        return (0, "")


class HookIdempotenceTests(unittest.TestCase):
    def _install(self, tmux):
        saved = agent_launch_utils._TMUX
        agent_launch_utils._TMUX = tmux
        self.addCleanup(lambda: setattr(agent_launch_utils, "_TMUX", saved))

    def _set_hooks(self, tmux):
        return [a for a in tmux.spawned if a and a[0] == "set-hook"]

    def _remain_on_exit(self, tmux):
        return [
            a for a in tmux.spawned
            if a and a[0] == "set-option" and "remain-on-exit" in a
        ]

    def test_existing_cleanup_hook_is_not_overwritten(self):
        # Live-verified output shape. The prior companion (%3) must survive.
        tmux = _HookTmux(
            'pane-died[0] run-shell ".../aitask_companion_cleanup.sh %2 %3"\n'
        )
        self._install(tmux)
        status = agent_launch_utils.attach_companion_cleanup_hook("%2", "%9")
        self.assertEqual(status, "existing")
        self.assertEqual(self._set_hooks(tmux), [], "no set-hook at all")
        self.assertEqual(len(self._remain_on_exit(tmux)), 1, "still ensured")

    def test_no_pane_died_hook_installs_at_index_0(self):
        tmux = _HookTmux("client-attached[0] display-message hi\n")
        self._install(tmux)
        status = agent_launch_utils.attach_companion_cleanup_hook("%2", "%9")
        self.assertEqual(status, "installed")
        hooks = self._set_hooks(tmux)
        self.assertEqual(len(hooks), 1)
        self.assertIn("pane-died[0]", hooks[0])
        self.assertIn("%2 %9", hooks[0][-1])

    def test_unrelated_pane_died_hook_is_preserved(self):
        """Appends at [1]; the unrelated [0] hook must still be there.

        Negative control: asserting only "our hook is present" passes even when
        the unrelated one was destroyed, so both entries are asserted -- ours by
        the index it was written to, theirs by never having been overwritten.
        """
        tmux = _HookTmux('pane-died[0] display-message custom-user-hook\n')
        self._install(tmux)
        status = agent_launch_utils.attach_companion_cleanup_hook("%2", "%9")
        self.assertEqual(status, "installed")
        hooks = self._set_hooks(tmux)
        self.assertEqual(len(hooks), 1)
        self.assertIn("pane-died[1]", hooks[0], "appended, not overwritten")
        # Nothing was written to [0], so the user's hook survives.
        self.assertFalse(
            any("pane-died[0]" in h for h in hooks),
            "must never write index 0 over an unrelated hook",
        )

    def test_probe_failure_fails_closed(self):
        tmux = _HookTmux("", rc=1)
        self._install(tmux)
        status = agent_launch_utils.attach_companion_cleanup_hook("%2", "%9")
        self.assertEqual(status, "unverified")
        self.assertEqual(self._set_hooks(tmux), [], "install nothing")
        self.assertEqual(len(self._remain_on_exit(tmux)), 1)

    def test_multiple_pane_died_hooks_append_after_the_max(self):
        tmux = _HookTmux(
            "pane-died[0] display-message a\n"
            "pane-died[2] display-message b\n"
        )
        self._install(tmux)
        agent_launch_utils.attach_companion_cleanup_hook("%2", "%9")
        self.assertIn("pane-died[3]", self._set_hooks(tmux)[0])


class SelectWindowArgvTests(unittest.TestCase):
    """C2 at the gateway level, incl. the existing-caller negative control."""

    def _run_launch(self, cfg):
        tmux = MagicMock()
        tmux.run.return_value = (0, "4242")
        saved = agent_launch_utils._TMUX
        agent_launch_utils._TMUX = tmux
        self.addCleanup(lambda: setattr(agent_launch_utils, "_TMUX", saved))
        agent_launch_utils.launch_in_tmux("cmd", cfg)
        return tmux

    def _split_cfg(self, **kw):
        return TmuxLaunchConfig(
            session="demo", window="w", new_session=False, new_window=False,
            split_target_pane="%1", **kw
        )

    def _window_cfg(self, **kw):
        return TmuxLaunchConfig(
            session="demo", window="w", new_session=False, new_window=True, **kw
        )

    def test_split_default_still_selects_window(self):
        tmux = self._run_launch(self._split_cfg())
        selects = [
            c for c in tmux.spawn.call_args_list
            if c.args and c.args[0] and c.args[0][0] == "select-window"
        ]
        self.assertEqual(len(selects), 1, "default preserves today's argv")

    def test_split_false_emits_no_select_window(self):
        tmux = self._run_launch(self._split_cfg(select_window=False))
        selects = [
            c for c in tmux.spawn.call_args_list
            if c.args and c.args[0] and c.args[0][0] == "select-window"
        ]
        self.assertEqual(selects, [])

    def test_new_window_default_has_no_dash_d(self):
        tmux = self._run_launch(self._window_cfg())
        argv = tmux.run.call_args.args[0]
        self.assertNotIn("-d", argv, "default preserves today's argv")

    def test_new_window_false_adds_dash_d(self):
        tmux = self._run_launch(self._window_cfg(select_window=False))
        argv = tmux.run.call_args.args[0]
        self.assertIn("-d", argv)


# -- `E` dialog contract -------------------------------------------------------


class DialogContractTests(unittest.TestCase):
    def _push(self, task_id="42"):
        app = _mk_app(_FakeMon(), task_id=task_id)
        with _SpawnMocks():
            app.action_launch_shadow_pick()
        self.assertEqual(len(app.spy_pushed), 1)
        return app, app.spy_pushed[0]

    def test_dialog_shadow_contract(self):
        _app, (screen, _cb) = self._push()
        self.assertIsInstance(screen, AgentCommandScreen)
        self.assertEqual(screen.operation, "shadow")
        self.assertEqual(screen.operation_args, ["%1", "42"])
        self.assertEqual(screen.prompt_str, "/aitask-shadow %1 42")

    def test_dialog_is_not_narrow(self):
        # The monitor is full-width; assert it, or a copy-paste of narrow=True
        # from minimonitor goes unnoticed.
        _app, (screen, _cb) = self._push()
        self.assertFalse(screen._narrow)

    def test_operation_args_without_task_id(self):
        _app, (screen, _cb) = self._push(task_id=None)
        self.assertEqual(screen.operation_args, ["%1"])
        self.assertEqual(screen.prompt_str, "/aitask-shadow %1")

    def test_confirm_launches_post_override_command(self):
        app = _mk_app(_FakeMon())
        with _SpawnMocks() as m:
            app.action_launch_shadow_pick()
            screen, callback = app.spy_pushed[0]
            screen.full_command = "codex /aitask-shadow %1 42"  # agent override
            callback(TmuxLaunchConfig("demo", "w", new_session=False,
                                      new_window=False))
        self.assertEqual(m.launch.call_count, 1)
        self.assertEqual(
            m.launch.call_args.args[0], "codex /aitask-shadow %1 42",
            "must use screen.full_command, not the stale capture",
        )

    def test_confirm_discards_the_dialogs_own_placement(self):
        app = _mk_app(_FakeMon())
        with _SpawnMocks() as m:
            app.action_launch_shadow_pick()
            _screen, callback = app.spy_pushed[0]
            # A dialog-authored placement that must NOT survive.
            callback(TmuxLaunchConfig("other", "other-w", new_session=True,
                                      new_window=True))
        _cmd, cfg = m.launch.call_args.args
        self.assertEqual(cfg.session, "demo")
        self.assertFalse(cfg.new_session)
        self.assertEqual(cfg.split_target_pane, "%1")

    def test_cancel_and_run_launch_nothing(self):
        app = _mk_app(_FakeMon())
        with _SpawnMocks() as m:
            app.action_launch_shadow_pick()
            _screen, callback = app.spy_pushed[0]
            callback(None)   # cancelled
            callback("run")  # "open in terminal" is not a shadow placement
        self.assertFalse(m.launch.called)


if __name__ == "__main__":
    unittest.main()
