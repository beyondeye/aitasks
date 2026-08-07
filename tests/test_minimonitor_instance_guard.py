"""`maybe_spawn_minimonitor`'s marker guard and hook arming (t1451).

Three defects are pinned here, all in the one function:

1. **The single-instance guard was dead code.** It matched
   `#{pane_current_command}` against `minimonitor` / `monitor_app`, but a live
   minimonitor pane reports `python` (confirmed live during t1446:
   `%423 4041322 python`), so it could never fire. It now matches the
   `@aitask_monitor_kind` marker each app stamps on itself.

2. **The spawner must never stamp the pane it creates.** If it did, the
   minimonitor booting inside that pane would find its own marker and refuse to
   start unless it could identify its own pane from ambient state — a
   self-deadlock in the primary spawn path. `test_spawner_never_stamps_the_marker`
   is the invariant that keeps that design decision from being quietly undone.

3. **No `pane-died` cleanup hook was armed here at all**, so every board- /
   codebrowser- / crew-launched window carried a companion with no hook.

The tmux gateway is faked wholesale, so no tmux call leaves the test.

Run: python3 tests/test_minimonitor_instance_guard.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils  # noqa: E402
from agent_launch_utils import MONITOR_KIND_OPTION, maybe_spawn_minimonitor  # noqa: E402

LIVE = f"minimonitor:{os.getpid()}"


def _dead_pid() -> int:
    import subprocess
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


STALE = f"minimonitor:{_dead_pid()}"


class _FakeTmux:
    """Scripted gateway. `panes` is a list of `(pane_id, marker, shadow_target)`."""

    def __init__(self, panes, *, active_pane="%1", split_rc=0):
        self._panes = panes
        self._active_pane = active_pane
        self._split_rc = split_rc
        self.ran: list[list[str]] = []
        self.spawned: list[list[str]] = []

    def run(self, args, timeout=5.0):
        self.ran.append(list(args))
        verb = args[0] if args else ""
        if verb == "list-windows":
            return (0, "3:agent-demo")
        if verb == "list-panes":
            return (0, "\n".join("|".join(p) for p in self._panes))
        if verb == "display-message":
            return (0, self._active_pane) if self._active_pane else (1, "")
        if verb == "split-window":
            return (self._split_rc, "%77" if self._split_rc == 0 else "")
        if verb == "show-hooks":
            return (0, "")
        return (0, "")

    def spawn(self, args, **kwargs):
        self.spawned.append(list(args))

    # --- assertions helpers -------------------------------------------------
    def _all(self) -> list[list[str]]:
        return self.ran + self.spawned

    def verbs(self, verb: str) -> list[list[str]]:
        return [a for a in self._all() if a and a[0] == verb]

    def marker_writes(self) -> list[list[str]]:
        """Any call that SETS the marker (`-u` unset calls excluded)."""
        return [
            a for a in self._all()
            if a and a[0] == "set-option" and MONITOR_KIND_OPTION in a
            and "-pu" not in a
        ]

    def marker_clears(self) -> list[list[str]]:
        return [
            a for a in self._all()
            if a and a[0] == "set-option" and MONITOR_KIND_OPTION in a
            and "-pu" in a
        ]


class MaybeSpawnMinimonitorGuardTests(unittest.TestCase):

    def _install(self, tmux):
        saved = agent_launch_utils._TMUX
        agent_launch_utils._TMUX = tmux
        self.addCleanup(lambda: setattr(agent_launch_utils, "_TMUX", saved))

        hooks: list[tuple[str, str]] = []
        saved_hook = agent_launch_utils.attach_companion_cleanup_hook
        agent_launch_utils.attach_companion_cleanup_hook = (
            lambda agent, companion: hooks.append((agent, companion)) or "installed"
        )
        self.addCleanup(
            lambda: setattr(agent_launch_utils, "attach_companion_cleanup_hook",
                            saved_hook)
        )
        self.hooks = hooks
        return tmux

    def _spawn(self, panes, **kwargs):
        tmux = self._install(_FakeTmux(panes, **kwargs))
        # project_root points at a dir with no project_config.yaml, so the
        # defaults apply (auto_spawn on, width 40).
        result = maybe_spawn_minimonitor(
            "demo", "agent-demo", window_index="3",
            project_root=Path("/nonexistent-for-config"),
        )
        return tmux, result

    # -- guard ---------------------------------------------------------------

    def test_live_marker_blocks_the_spawn(self):
        """The whole point: a booted monitor in the window stops a second one.

        Against the pre-fix code this pane would present as `python` and the
        substring match would miss it entirely.
        """
        tmux, result = self._spawn([("%1", "", ""), ("%2", LIVE, "")])
        self.assertIsNone(result)
        self.assertEqual(tmux.verbs("split-window"), [], "must not spawn")
        self.assertEqual(self.hooks, [])

    def test_monitor_kind_marker_also_blocks(self):
        tmux, result = self._spawn(
            [("%1", "", ""), ("%2", f"monitor:{os.getpid()}", "")]
        )
        self.assertIsNone(result)
        self.assertEqual(tmux.verbs("split-window"), [])

    def test_stale_marker_does_not_block_and_self_heals(self):
        """A marker whose process is gone is residue, not a monitor. It must be
        cleared so it cannot block this window forever."""
        tmux, result = self._spawn([("%1", "", ""), ("%2", STALE, "")])
        self.assertEqual(result, "%77")
        clears = tmux.marker_clears()
        self.assertEqual(len(clears), 1, "stale marker must be cleared")
        self.assertIn("%2", clears[0])

    def test_unverifiable_marker_blocks(self):
        """`garbage:123` is not ours to interpret — and is exactly the value a
        hand-rolled shell parse would read as a dead pid and clear."""
        tmux, result = self._spawn([("%1", "", ""), ("%2", "garbage:123", "")])
        self.assertIsNone(result)
        self.assertEqual(tmux.verbs("split-window"), [])
        self.assertEqual(tmux.marker_clears(), [], "must never clear it")

    def test_no_marker_proceeds(self):
        tmux, result = self._spawn([("%1", "", ""), ("%2", "", "%1")])
        self.assertEqual(result, "%77")
        self.assertEqual(len(tmux.verbs("split-window")), 1)

    def test_stale_marked_pane_is_not_counted_toward_overcrowding(self):
        """A monitor pane is a helper either way. Counting a stale-marked one
        would let three real panes plus residue trip the >= 3 limit."""
        tmux, result = self._spawn([
            ("%1", "", ""), ("%2", "", ""), ("%3", "", ""),
            ("%4", STALE, ""),
        ])
        self.assertIsNone(result, "3 real panes already trips the limit")
        # ...and with only two real panes plus the stale one, it proceeds:
        tmux, result = self._spawn([
            ("%1", "", ""), ("%2", "", ""), ("%4", STALE, ""),
        ])
        self.assertEqual(result, "%77")

    def test_shadow_panes_still_excluded_from_overcrowding(self):
        """Pre-existing t986 behaviour must survive the format change."""
        tmux, result = self._spawn([
            ("%1", "", ""), ("%2", "", ""), ("%3", "", "%1"), ("%4", "", "%2"),
        ])
        self.assertEqual(result, "%77")

    # -- no self-stamp -------------------------------------------------------

    def test_spawner_never_stamps_the_marker(self):
        """Design invariant (t1451): only a booted app writes the marker.

        A spawner-side stamp would land before the child's own guard runs, so
        the child would see its own marker. Removing the stamp is what makes the
        self-deadlock impossible rather than merely guarded against.
        """
        tmux, result = self._spawn([("%1", "", "")])
        self.assertEqual(result, "%77")
        self.assertEqual(
            tmux.marker_writes(), [],
            "the spawner must not stamp @aitask_monitor_kind on any pane",
        )

    # -- hook arming ---------------------------------------------------------

    def test_cleanup_hook_is_armed_with_the_agent_and_companion(self):
        _tmux, result = self._spawn([("%1", "", "")], active_pane="%1")
        self.assertEqual(result, "%77")
        self.assertEqual(self.hooks, [("%1", "%77")])

    def test_no_hook_when_the_agent_pane_is_unknown(self):
        """`display-message` failing leaves agent_pane == "". Arming a hook
        against an unknown pane is worse than not arming one."""
        _tmux, result = self._spawn([("%1", "", "")], active_pane="")
        self.assertEqual(result, "%77", "the companion still spawns")
        self.assertEqual(self.hooks, [])

    def test_no_hook_when_the_split_fails(self):
        _tmux, result = self._spawn([("%1", "", "")], split_rc=1)
        self.assertIsNone(result)
        self.assertEqual(self.hooks, [])


if __name__ == "__main__":
    unittest.main()
