"""Both monitor TUIs must re-stamp the advisory phase, not just minimonitor (t1420).

The pane-option channel was chosen over argv for exactly one reason: the value
stays *current* as the followed agent advances. That property is lost the moment
a spawning surface forgets to re-stamp — and the full monitor spawns shadows too
(`monitor_app.action_launch_shadow`). A minimonitor-only refresh would leave
every full-monitor shadow frozen at its launch value, which is precisely the argv
failure mode the design rejected.

Source greps are the cheap backstop; the behavioural assertions are what catch a
site that imports the helper and never reaches it.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

from monitor import monitor_core  # noqa: E402
import workflow_phase as wp  # noqa: E402


class FakeMonitor:
    """Duck-typed on ``tmux_run`` only — the contract monitor_core.py:2706-2708
    already documents for the shared shadow seam."""

    def __init__(self, rc: int = 0, raises: bool = False):
        self.calls: list[list[str]] = []
        self._rc = rc
        self._raises = raises

    def tmux_run(self, args, timeout=5.0):
        if self._raises:
            raise RuntimeError("tmux exploded")
        self.calls.append(list(args))
        return self._rc, ""


SIGNAL = wp.PhaseSignal(phase="IMPLEMENT", waiting="WAITING", source="ledger",
                        consulted=["ledger"], recording="on", detail="d")


class RefreshHelperTest(unittest.TestCase):
    def test_writes_the_pane_option(self):
        mon = FakeMonitor()
        self.assertTrue(monitor_core.refresh_shadow_phase_stamp(mon, "%9", SIGNAL))
        self.assertEqual(len(mon.calls), 1)
        args = mon.calls[0]
        self.assertEqual(args[:4], ["set-option", "-p", "-t", "%9"])
        self.assertEqual(args[4], monitor_core.SHADOW_PHASE_OPTION)
        # The value must be the wire format, round-trippable by the reader.
        self.assertEqual(wp.parse_signal(args[5]), SIGNAL)

    def test_best_effort_never_raises(self):
        """Unlike the @aitask_shadow_target stamp, which kills the pane on
        failure, an advisory hint must never disturb anything."""
        self.assertFalse(
            monitor_core.refresh_shadow_phase_stamp(FakeMonitor(rc=1), "%9", SIGNAL))
        self.assertFalse(
            monitor_core.refresh_shadow_phase_stamp(
                FakeMonitor(raises=True), "%9", SIGNAL))
        self.assertFalse(monitor_core.refresh_shadow_phase_stamp(FakeMonitor(), "", SIGNAL))
        self.assertFalse(monitor_core.refresh_shadow_phase_stamp(FakeMonitor(), "%9", None))


class SpawnTimeStampTest(unittest.TestCase):
    """The stamp must land INSIDE spawn_shadow, before it returns.

    The per-tick re-stamp is not sufficient on its own: a user can launch a
    shadow and have it read `--phase` before the next UI tick, and it would then
    miss the very checkpoint they spawned it for. So this asserts ordering, not
    just occurrence — the set-option must precede `schedule_refresh`, which is
    the point control returns to the app.
    """

    def _run_spawn(self, phase_signal):
        """Drive the REAL spawn_shadow, stubbing only what leaves the process.

        `launch_in_tmux` is the seam that actually creates the pane (it does not
        go through `tmux_run`), so it is patched to report success; everything
        else — placement, the duplicate guard, both stamps, the cleanup hook —
        runs for real and lands in `events` in execution order.
        """
        events: list[str] = []

        class Mon:
            def tmux_run(self, args, timeout=5.0):
                if args[0] == "set-option":
                    events.append(f"set-option:{args[4]}")
                    return 0, ""
                if args[0] == "list-panes":
                    return 0, ""
                if args[0] == "display-message":
                    return 0, "%77"
                return 0, ""

        orig = {
            "launch_in_tmux": monitor_core.launch_in_tmux,
            "attach_companion_cleanup_hook": monitor_core.attach_companion_cleanup_hook,
            "resolve_pane_id_by_pid": monitor_core.resolve_pane_id_by_pid,
        }
        monitor_core.launch_in_tmux = lambda cmd, cfg: (4242, "")
        monitor_core.attach_companion_cleanup_hook = lambda *a, **k: "ok"
        monitor_core.resolve_pane_id_by_pid = lambda session, pid: "%77"
        try:
            return self._invoke(Mon(), events, phase_signal)
        finally:
            for name, fn in orig.items():
                setattr(monitor_core, name, fn)

    def _invoke(self, mon, events, phase_signal):
        monitor_core.spawn_shadow(
            mon,
            full_cmd="echo hi",
            followed_pane="%1",
            followed_window="agent-pick-1",
            session="s",
            task_id="1",
            target_root=Path("."),
            companion_pane=None,
            select_window=False,
            notify=lambda *a, **k: None,
            schedule_refresh=lambda: events.append("schedule_refresh"),
            phase_signal=phase_signal,
        )
        return events

    def test_phase_is_stamped_before_control_returns(self):
        events = self._run_spawn(SIGNAL)
        stamp = f"set-option:{monitor_core.SHADOW_PHASE_OPTION}"
        self.assertIn(stamp, events,
                      "spawn_shadow did not stamp the phase at spawn — a shadow "
                      "reading --phase before the first tick would miss it")
        self.assertIn("schedule_refresh", events)
        self.assertLess(events.index(stamp), events.index("schedule_refresh"),
                        "the phase stamp must precede schedule_refresh")

    def test_target_is_stamped_before_the_phase(self):
        """Ordering within the spawn: the binding that makes the pane a shadow
        at all must be written first — the phase is only meaningful once the
        pane is classified."""
        events = self._run_spawn(SIGNAL)
        self.assertLess(
            events.index(f"set-option:{monitor_core.SHADOW_TARGET_OPTION}"),
            events.index(f"set-option:{monitor_core.SHADOW_PHASE_OPTION}"))

    def test_absent_signal_spawns_normally(self):
        """No resolvable phase must not cost the user a shadow."""
        events = self._run_spawn(None)
        self.assertNotIn(f"set-option:{monitor_core.SHADOW_PHASE_OPTION}", events)
        self.assertIn("schedule_refresh", events)

    def test_both_launch_surfaces_pass_a_signal(self):
        """Structural: each app's `_spawn_shadow` forwards `phase_signal=`.
        Without this, only the app I happened to edit would stamp at spawn."""
        for filename in ("monitor_app.py", "minimonitor_app.py"):
            src = (SCRIPTS / "monitor" / filename).read_text(encoding="utf-8")
            self.assertIn("phase_signal=self._phase_signal_for_pane", src,
                          f"{filename} does not pass a spawn-time phase signal")


class BothAppsWireItTest(unittest.TestCase):
    """Structural: the helper is *reached* from each app's per-tick shadow path."""

    APPS = {
        "monitor_app.py": "_format_agent_card_text",
        "minimonitor_app.py": "_restamp_shadow_phase",
    }

    def _calls_within(self, path: Path, func_name: str) -> bool:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name == func_name:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                            and sub.func.id == "refresh_shadow_phase_stamp":
                        return True
        return False

    def test_each_app_calls_the_helper(self):
        for filename, func in self.APPS.items():
            path = SCRIPTS / "monitor" / filename
            self.assertTrue(self._calls_within(path, func),
                            f"{filename}:{func} does not call "
                            f"refresh_shadow_phase_stamp")

    def test_minimonitor_restamp_is_reached_per_tick(self):
        """The helper existing is not enough — `_restamp_shadow_phase` must be
        invoked from the shadow path that runs every refresh, or the stamp is
        written once at spawn and never again."""
        src = (SCRIPTS / "monitor" / "minimonitor_app.py").read_text(encoding="utf-8")
        # Called somewhere other than its own definition.
        self.assertGreaterEqual(src.count("_restamp_shadow_phase"), 2, src.count)

    def test_detector_would_notice_removal(self):
        """Positive control: the AST walk must return False for a function that
        genuinely does not call the helper, else both assertions are vacuous."""
        path = SCRIPTS / "monitor" / "monitor_app.py"
        self.assertFalse(self._calls_within(path, "_format_other_card_text"))


if __name__ == "__main__":
    unittest.main()
