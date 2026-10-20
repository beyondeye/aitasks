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

And one identity rule (t1851): a caller that already knows its agent's pane —
the frozen-agent restore resolves it from the launched pid — passes it as
``agent_pane``, and that pane, never whichever one happens to be active, is the
one the companion is split beside, hooked to and refocused on.

And one concurrency rule (t2039): the eligibility read and the split are a
check-then-act, so two callers could both read "no companion" and both split. A
companion that is still BOOTING is recognised by its start command (it has no
marker yet), and the read + split run under a per-server ``flock``, so a second
caller always re-reads after the first one's split. The race is pinned with a
barrier that holds both callers at the lock door, plus a negative control with
the lock removed that must show two splits.

The tmux gateway is faked wholesale, so no tmux call leaves the test.

Run: python3 tests/test_minimonitor_instance_guard.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    MONITOR_KIND_OPTION, maybe_spawn_minimonitor, tmux_window_target,
)

LIVE = f"minimonitor:{os.getpid()}"


def _dead_pid() -> int:
    import subprocess
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


STALE = f"minimonitor:{_dead_pid()}"


#: The positional fields of a fixture pane tuple, mapped to the `#{...}` spec
#: each one answers. Rows are RENDERED from the `-F` format the code under test
#: requests (`_render_panes`), so adding a field to that format — t2073_3
#: appended the scratchpad target — cannot shift `pane_start_command` into a
#: neighbour's slot and silently reclassify a booting companion.
_PANE_TUPLE_SPECS = (
    "#{pane_id}", "#{@aitask_monitor_kind}", "#{@aitask_shadow_target}",
    "#{@aitask_frozen}", "#{pane_dead}", "#{pane_start_command}",
)


def _render_panes(args, panes) -> str:
    """Answer `list-panes -F <fmt>` from positional pane tuples (missing → "")."""
    fmt = args[args.index("-F") + 1]
    rows = []
    for pane in panes:
        values = dict(zip(_PANE_TUPLE_SPECS, pane))
        rows.append("|".join(values.get(spec, "") for spec in fmt.split("|")))
    return "\n".join(rows)


class _FakeTmux:
    """Scripted gateway. `panes` is a list of `(pane_id, marker, shadow_target)`,
    optionally extended with `(frozen, dead, start_command)` — the trailing
    fields of the t2039 list-panes format, which a 3-tuple simply leaves empty.
    Rows are rendered from the requested format (`_render_panes`).

    ``socket_path`` answers the lock's `#{socket_path}` read (rc ``socket_rc``);
    every other `display-message` is the active-pane probe.
    """

    def __init__(self, panes, *, active_pane="%1", split_rc=0, list_rc=0,
                 socket_path="", socket_rc=0, split_raises=False):
        self._panes = panes
        self._active_pane = active_pane
        self._split_rc = split_rc
        self._list_rc = list_rc
        self._socket_path = socket_path
        self._socket_rc = socket_rc
        self._split_raises = split_raises
        self.ran: list[list[str]] = []
        self.spawned: list[list[str]] = []

    def run(self, args, timeout=5.0):
        self.ran.append(list(args))
        verb = args[0] if args else ""
        if verb == "list-windows":
            return (0, "3:agent-demo")
        if verb == "list-panes":
            if self._list_rc:
                return (self._list_rc, "")
            return (0, _render_panes(args, self._panes))
        if verb == "display-message":
            if args[-1] == "#{socket_path}":
                return (self._socket_rc, self._socket_path)
            return (0, self._active_pane) if self._active_pane else (1, "")
        if verb == "split-window":
            if self._split_raises:
                raise RuntimeError("split exploded")
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


class _LockDir:
    """A per-test directory standing in for tmux's socket dir."""

    def setUp(self):
        self.sock_dir = tempfile.mkdtemp(prefix="t2039_sock_")
        self.addCleanup(shutil.rmtree, self.sock_dir, True)
        self.socket_path = os.path.join(self.sock_dir, "ait")
        self.lock_path = self.socket_path + agent_launch_utils._COMPANION_LOCK_SUFFIX


class MaybeSpawnMinimonitorGuardTests(_LockDir, unittest.TestCase):

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

    def _spawn(self, panes, *, agent_pane=None, **kwargs):
        kwargs.setdefault("socket_path", self.socket_path)
        tmux = self._install(_FakeTmux(panes, **kwargs))
        # project_root points at a dir with no project_config.yaml, so the
        # defaults apply (auto_spawn on, width 40).
        extra = {} if agent_pane is None else {"agent_pane": agent_pane}
        result = maybe_spawn_minimonitor(
            "demo", "agent-demo", window_index="3",
            project_root=Path("/nonexistent-for-config"), **extra,
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

    # -- explicit agent pane (t1851) -----------------------------------------

    def test_explicit_agent_pane_wins_over_the_active_pane(self):
        """Something else became active between the launch and the spawn.

        The active-pane read would hand the companion to `%1`. With the agent's
        own pane passed in, every identity-bearing call names `%2` instead.
        """
        tmux, result = self._spawn(
            [("%1", "", ""), ("%2", "", "")], active_pane="%1", agent_pane="%2")
        self.assertEqual(result, "%77")
        self.assertEqual(self.hooks, [("%2", "%77")],
                         "the cleanup hook must be armed on the agent, not the active pane")
        splits = tmux.verbs("split-window")
        self.assertEqual(1, len(splits))
        target = splits[0][splits[0].index("-t") + 1]
        self.assertEqual("%2", target, "the companion must be split beside the agent")
        self.assertEqual([["select-pane", "-t", "%2"]], tmux.verbs("select-pane"),
                         "focus must return to the agent")
        self.assertEqual(
            [], [c for c in tmux.verbs("display-message") if c[-1] == "#{pane_id}"],
            "a known agent pane must not be re-derived from focus")

    def test_agent_pane_outside_the_window_spawns_nothing(self):
        tmux, result = self._spawn([("%1", "", "")], agent_pane="%9")
        self.assertIsNone(result, "a pane not in this window must not get a companion here")
        self.assertEqual([], tmux.verbs("split-window"))
        self.assertEqual([], self.hooks)

    def test_agent_pane_with_unreadable_panes_spawns_nothing(self):
        """Without the pane list there is no proof the agent is in this window."""
        tmux, result = self._spawn([("%1", "", "")], agent_pane="%1", list_rc=1)
        self.assertIsNone(result)
        self.assertEqual([], tmux.verbs("split-window"))
        self.assertEqual([], self.hooks)

    def test_without_an_agent_pane_the_split_still_targets_the_window(self):
        """The default path every existing caller takes is unchanged."""
        tmux, result = self._spawn([("%1", "", "")])
        self.assertEqual(result, "%77")
        split = tmux.verbs("split-window")[0]
        self.assertEqual(tmux_window_target("demo", "3"), split[split.index("-t") + 1])

    # -- a companion that is still booting (t2039) ----------------------------

    def test_a_booting_companion_blocks_the_spawn(self):
        """Split, but not yet mounted: no marker, only its start command."""
        tmux, result = self._spawn(
            [("%1", "", ""), ("%2", "", "", "", "0", "ait minimonitor")])
        self.assertIsNone(result)
        self.assertEqual([], tmux.verbs("split-window"))
        self.assertEqual([], self.hooks)

    def test_a_dead_companion_does_not_block_and_is_not_counted(self):
        tmux, result = self._spawn([
            ("%1", "", ""), ("%2", "", ""),
            ("%3", "", "", "", "1", "ait minimonitor"),
        ])
        self.assertEqual("%77", result, "two real panes plus a dead helper")
        self.assertEqual(1, len(tmux.verbs("split-window")))

    def test_another_start_command_is_counted_as_before(self):
        tmux, result = self._spawn([
            ("%1", "", ""), ("%2", "", "", "", "0", "claude --resume x"),
            ("%3", "", "", "", "0", "ait minimonitor --loop-log"),
        ])
        self.assertIsNone(result, "three real panes trip the overcrowding limit")
        self.assertEqual([], tmux.verbs("split-window"))

    def test_the_split_runs_the_companion_command(self):
        tmux, _result = self._spawn([("%1", "", "")])
        split = tmux.verbs("split-window")[0]
        self.assertEqual(["ait", "minimonitor"], split[-2:])
        self.assertEqual(agent_launch_utils._COMPANION_START_COMMAND, " ".join(split[-2:]),
                         "the booting check must compare against what the split runs")

    # -- the spawn lock fails closed (t2039) ----------------------------------

    def test_an_unreadable_socket_path_spawns_nothing(self):
        tmux, result = self._spawn([("%1", "", "")], socket_rc=1)
        self.assertIsNone(result)
        self.assertEqual([], tmux.verbs("split-window"))
        self.assertEqual([], tmux.verbs("list-panes"), "no eligibility read outside the lock")

    def test_a_relative_socket_path_spawns_nothing(self):
        tmux, result = self._spawn([("%1", "", "")], socket_path="ait")
        self.assertIsNone(result)
        self.assertEqual([], tmux.verbs("split-window"))
        self.assertFalse(os.path.exists("ait" + agent_launch_utils._COMPANION_LOCK_SUFFIX),
                         "no lock file may land in the cwd")

    def test_an_unopenable_lock_file_spawns_nothing(self):
        missing_dir = os.path.join(self.sock_dir, "no-such-dir", "ait")
        tmux, result = self._spawn([("%1", "", "")], socket_path=missing_dir)
        self.assertIsNone(result)
        self.assertEqual([], tmux.verbs("split-window"))

    def test_a_lock_held_past_the_deadline_spawns_nothing(self):
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        with unittest.mock.patch.object(agent_launch_utils, "COMPANION_LOCK_TIMEOUT", 0.2):
            started = time.monotonic()
            tmux, result = self._spawn([("%1", "", "")])
            waited = time.monotonic() - started
        self.assertIsNone(result)
        self.assertEqual([], tmux.verbs("split-window"))
        self.assertGreaterEqual(waited, 0.2, "it waited for the holder")
        self.assertLess(waited, 2.0, "and gave up at the deadline")

    def test_the_lock_is_released_on_every_path(self):
        with self.assertRaises(RuntimeError):
            self._spawn([("%1", "", "")], split_raises=True)
        self._spawn([("%1", "", "", "", "0", "ait minimonitor")])   # a refusal
        fd = os.open(self.lock_path, os.O_RDWR)
        self.addCleanup(os.close, fd)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.fail("a raised split or a refusal left the lock held")
        fcntl.flock(fd, fcntl.LOCK_UN)
        with unittest.mock.patch.object(agent_launch_utils, "COMPANION_LOCK_TIMEOUT", 0.1):
            _tmux, result = self._spawn([("%1", "", "")])
        self.assertEqual("%77", result, "a later call acquires at once")


class _SharedWindowTmux:
    """One window shared by concurrent callers: a split adds a live pane whose
    start command is the companion's, exactly what tmux shows while the new
    minimonitor boots. ``list_barrier`` (negative control only) holds every
    `list-panes` reader until all of them have read."""

    def __init__(self, socket_path, *, list_barrier=None):
        self._lock = threading.Lock()
        self.socket_path = socket_path
        self.list_barrier = list_barrier
        self.panes = [["%1", "", "", "", "0", "claude"]]
        self.splits: list[list[str]] = []

    def run(self, args, timeout=5.0):
        verb = args[0] if args else ""
        if verb == "list-windows":
            return 0, "3:agent-demo"
        if verb == "display-message":
            if args[-1] == "#{socket_path}":
                return 0, self.socket_path
            return 0, "%1"
        if verb == "list-panes":
            with self._lock:
                out = _render_panes(args, self.panes)
            if self.list_barrier is not None:
                self.list_barrier.wait(timeout=5)
            return 0, out
        if verb == "split-window":
            with self._lock:
                pane = f"%{70 + len(self.splits)}"
                self.splits.append(list(args))
                self.panes.append([pane, "", "", "", "0", "ait minimonitor"])
            return 0, pane
        return 0, ""

    def spawn(self, args, **kwargs):
        pass


class ConcurrentSpawnTests(_LockDir, unittest.TestCase):
    """Two callers for one window: both decided to spawn before either split."""

    def setUp(self):
        super().setUp()
        saved_hook = agent_launch_utils.attach_companion_cleanup_hook
        agent_launch_utils.attach_companion_cleanup_hook = lambda *a: "installed"
        self.addCleanup(setattr, agent_launch_utils, "attach_companion_cleanup_hook",
                        saved_hook)

    def _race(self, tmux, lock) -> list:
        saved_tmux, saved_lock = agent_launch_utils._TMUX, agent_launch_utils._companion_spawn_lock
        agent_launch_utils._TMUX = tmux
        agent_launch_utils._companion_spawn_lock = lock
        self.addCleanup(setattr, agent_launch_utils, "_TMUX", saved_tmux)
        self.addCleanup(setattr, agent_launch_utils, "_companion_spawn_lock", saved_lock)
        results: list = []
        errors: list = []

        def caller():
            try:
                # No window_index: the name lookup is a real read BEFORE the lock.
                results.append(maybe_spawn_minimonitor(
                    "demo", "agent-demo",
                    project_root=Path("/nonexistent-for-config")))
            except Exception as exc:          # surfaced below, not swallowed
                errors.append(exc)

        threads = [threading.Thread(target=caller) for _ in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=10)
        self.assertFalse(any(th.is_alive() for th in threads), "a caller hung")
        self.assertEqual([], errors)
        return results

    def test_two_callers_at_the_lock_door_spawn_exactly_one_companion(self):
        real_lock = agent_launch_utils._companion_spawn_lock
        door = threading.Barrier(2)

        @contextlib.contextmanager
        def lock_after_both_arrive(*args, **kwargs):
            # Both callers have done every pre-lock read (the window lookup) and
            # decided to spawn on a window with no companion.
            door.wait(timeout=5)
            with real_lock(*args, **kwargs) as held:
                yield held

        tmux = _SharedWindowTmux(self.socket_path)
        results = self._race(tmux, lock_after_both_arrive)
        self.assertEqual(1, len(tmux.splits), "one window, one companion")
        self.assertEqual(sorted(results, key=str), sorted(["%70", None], key=str))

    def test_negative_control_without_the_lock_both_spawn(self):
        """Proves the race test can fail: with no lock and both eligibility reads
        forced to finish before either split, the booting rule sees nothing and
        two companions are split."""

        @contextlib.contextmanager
        def no_lock(*_args, **_kwargs):
            yield True

        tmux = _SharedWindowTmux(self.socket_path, list_barrier=threading.Barrier(2))
        results = self._race(tmux, no_lock)
        self.assertEqual(2, len(tmux.splits))
        self.assertEqual(["%70", "%71"], sorted(results))


if __name__ == "__main__":
    unittest.main()
