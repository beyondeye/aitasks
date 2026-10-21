"""Scratchpad SPAWN from minimonitor `o` (t2073_4), through mocks.

`monitor_core.spawn_scratchpad` is driven with `launch_split_pane`,
`attach_companion_cleanup_hook` and `load_project_tmux_config` patched on
`monitor_core` (where the body lives — patching `minimonitor_app` would intercept
nothing). Everything else is real: the duplicate lookup's parsing, and the REAL
store helper (`aitask_scratchpad_store.sh path`) run against throwaway project
roots, one of them reached through a symlink so canonicalization matters.

The fake gateway renders `list-panes` rows from the REQUESTED `-F` (the
`_render_panes` shape of `test_minimonitor_instance_guard.py`), so a field added
to a format cannot shift a neighbour's value into the wrong slot.

What only a live tmux can answer — the pad leaving discovery, dying with its
agent, surviving freeze/restore, and the real editor opening the stamped store
under a differing server environment — is `tests/test_scratchpad_spawn_live.sh`.

Run: python3 tests/test_minimonitor_scratchpad_spawn.py
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_launch_utils as alu  # noqa: E402
from agent_launch_utils import TmuxLaunchConfig  # noqa: E402
from monitor import minimonitor_app as mm  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from tmux_socket_containment import TmuxSocketContainmentMixin  # noqa: E402

STORE_SH = REPO_ROOT / ".aitask-scripts" / "aitask_scratchpad_store.sh"

# Format spec -> key of a fake pane dict. Unknown specs render empty.
_SPEC_KEYS = {
    "#{pane_id}": "id",
    "#{pane_pid}": "pid",
    f"#{{{mc.SCRATCHPAD_TARGET_OPTION}}}": "target",
    f"#{{{mc.SCRATCHPAD_STORE_OPTION}}}": "store",
    f"#{{{mc.FROZEN_OPTION}}}": "frozen",
}
_OPTION_KEYS = {
    mc.SCRATCHPAD_TARGET_OPTION: "target",
    mc.SCRATCHPAD_STORE_OPTION: "store",
}


def _render(fmt: str, panes: list[dict]) -> str:
    def row(pane):
        return re.sub(r"#\{[^}]+\}",
                      lambda m: str(pane.get(_SPEC_KEYS.get(m.group(0), ""), "")),
                      fmt)
    return "\n".join(row(p) for p in panes)


class _FakeMon:
    """Scripted `tmux_run` gateway over a mutable pane list.

    ``list_rc`` is an int, or a list consumed one per `list-panes` call (the
    last value repeats). ``set_rc`` maps an option to the rc of every write of
    it. ``probes`` is a list of ``(rc, out)`` answers consumed by
    `display-message`; when empty the answer follows the pane list.
    """

    def __init__(self, panes=None, list_rc=0, set_rc=None, probes=None):
        self.panes = [dict(p) for p in (panes or [])]
        self._list_rc = list_rc
        self.set_rc = dict(set_rc or {})
        self.probes = list(probes or [])
        self.calls: list[list[str]] = []

    def _next_list_rc(self):
        if isinstance(self._list_rc, list):
            return self._list_rc.pop(0) if len(self._list_rc) > 1 else self._list_rc[0]
        return self._list_rc

    def _pane(self, pane_id):
        return next((p for p in self.panes if p.get("id") == pane_id), None)

    def tmux_run(self, args, timeout=5.0):
        self.calls.append(list(args))
        verb = args[0]
        if verb == "list-panes":
            rc = self._next_list_rc()
            if rc != 0:
                return (rc, "")
            return (0, _render(args[args.index("-F") + 1], self.panes))
        if verb == "set-option":
            option, value = args[4], args[5]
            rc = self.set_rc.get(option, 0)
            pane = self._pane(args[3])
            if rc == 0 and pane is not None:
                pane[_OPTION_KEYS[option]] = value
            return (rc, "")
        if verb == "display-message":
            if self.probes:
                return self.probes.pop(0)
            pane_id = args[3]
            return (0, pane_id if self._pane(pane_id) else "")
        if verb == "kill-pane":
            self.panes = [p for p in self.panes if p.get("id") != args[2]]
            return (0, "")
        return (0, "")

    def count(self, verb, needle=None):
        return sum(1 for c in self.calls
                   if c[0] == verb and (needle is None or needle in c))


def _key(root: Path, task_id="42", env_dir=None) -> str:
    """The canonical store key the REAL helper prints for ``root``."""
    env = dict(os.environ)
    env.pop("AITASK_SCRATCHPAD_DIR", None)
    if env_dir is not None:
        env["AITASK_SCRATCHPAD_DIR"] = env_dir
    out = subprocess.run([str(STORE_SH), "path", task_id], cwd=str(root),
                         env=env, capture_output=True, text=True, check=True)
    return out.stdout.strip()


class _Spawn:
    """Run `spawn_scratchpad` once with the launch-side mocks installed."""

    def __init__(self, mon, root, *, task_id="42", followed="%1",
                 companion=None, cfg=None, launch=("%9", 999, None),
                 add_pane=True):
        self.notes: list[tuple[str, str]] = []
        self.refreshes = 0
        self.mon = mon

        def fake_launch(command, config):
            pad, pid, _err = launch
            if add_pane and not _err:
                mon.panes.append({"id": pad or "%9", "pid": str(pid or 999)})
            return launch

        with patch.object(mc, "launch_split_pane",
                          side_effect=fake_launch) as self.launch, \
             patch.object(mc, "attach_companion_cleanup_hook",
                          return_value="installed") as self.hook, \
             patch.object(mc, "load_project_tmux_config",
                          return_value={} if cfg is None else cfg), \
             patch.object(mc.time, "sleep"):
            self.result = mc.spawn_scratchpad(
                mon,
                followed_pane=followed,
                followed_window="agent-pick-42",
                session="s1",
                task_id=task_id,
                target_root=root,
                companion_pane=companion,
                select_window=True,
                notify=lambda msg, **kw: self.notes.append(
                    (msg, kw.get("severity", "information"))),
                schedule_refresh=self._refresh,
            )

    def _refresh(self):
        self.refreshes += 1

    @property
    def command(self) -> str:
        return self.launch.call_args.args[0]

    @property
    def cfg(self) -> TmuxLaunchConfig:
        return self.launch.call_args.args[1]

    def said(self, needle) -> bool:
        return any(needle.lower() in m.lower() for m, _ in self.notes)


class _RootsMixin:
    """Throwaway project roots; AITASK_SCRATCHPAD_DIR scrubbed per test."""

    def setUp(self):
        super().setUp()
        self._env_scrub = patch.dict(os.environ, {}, clear=False)
        self._env_scrub.start()
        os.environ.pop("AITASK_SCRATCHPAD_DIR", None)
        self.tmp = Path(tempfile.mkdtemp(prefix="ait_t2073_4_"))
        self.real_a = self.tmp / "real_a"
        self.real_a.mkdir()
        # Root A is reached through a symlink: the key must be the PHYSICAL path.
        self.root_a = self.tmp / "link_a"
        self.root_a.symlink_to(self.real_a)
        self.root_b = self.tmp / "proj_b"
        self.root_b.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._env_scrub.stop()
        super().tearDown()


class LookupAndKeyTests(_RootsMixin, TmuxSocketContainmentMixin,
                        unittest.TestCase):
    CONTAINED_MODULES = (alu,)

    def test_socket_containment_active(self):
        self.assert_contained()

    def test_unverifiable_lookup_refuses(self):
        mon = _FakeMon(list_rc=1)
        s = _Spawn(mon, self.root_a)
        self.assertIsNone(s.result)
        self.assertEqual(s.launch.call_count, 0)
        self.assertTrue(s.said("could not verify"))

    def test_duplicate_store_key_in_same_project_refused(self):
        key = _key(self.root_a)
        mon = _FakeMon(panes=[{"id": "%5", "target": "%7", "store": key}])
        s = _Spawn(mon, self.root_a, followed="%1")
        self.assertIsNone(s.result)
        self.assertEqual(s.launch.call_count, 0)
        self.assertTrue(s.said("already open for t42"))

    def test_key_is_physical_path_through_symlinked_root(self):
        self.assertEqual(
            _key(self.root_a),
            str(self.real_a.resolve() / ".aitask-scratchpad" / "42"))

    def test_same_task_number_in_second_project_allowed_then_first_refused(self):
        key_a = _key(self.root_a)
        mon = _FakeMon(panes=[{"id": "%5", "target": "%7", "store": key_a}])
        s_b = _Spawn(mon, self.root_b, followed="%1")
        self.assertEqual(s_b.result, "%9")
        self.assertEqual(s_b.launch.call_count, 1)
        s_a = _Spawn(mon, self.root_a, followed="%2", add_pane=False)
        self.assertIsNone(s_a.result)
        self.assertEqual(s_a.launch.call_count, 0)

    def test_key_stable_across_store_creation(self):
        self.assertFalse((self.real_a / ".aitask-scratchpad").exists())
        mon = _FakeMon()
        first = _Spawn(mon, self.root_a, followed="%1")
        self.assertEqual(first.result, "%9")
        stamped = mon._pane("%9")["store"]
        # The app's `open` creates the store after the first press.
        (self.real_a / ".aitask-scratchpad" / "42").mkdir(parents=True)
        self.assertEqual(_key(self.root_a), stamped)
        second = _Spawn(mon, self.root_a, followed="%2", add_pane=False)
        self.assertIsNone(second.result)
        self.assertEqual(second.launch.call_count, 0)
        self.assertTrue(second.said("already open"))

    def test_failed_path_call_refuses(self):
        os.environ["AITASK_SCRATCHPAD_DIR"] = "pads/../elsewhere"  # helper exit 2
        mon = _FakeMon()
        s = _Spawn(mon, self.root_a)
        self.assertIsNone(s.result)
        self.assertEqual(s.launch.call_count, 0)
        self.assertEqual(mon.count("list-panes"), 0, "no lookup without a key")
        self.assertTrue(s.said("could not resolve the scratchpad store"))

    def test_store_key_none_on_bad_helper_answers(self):
        cases = (
            subprocess.CompletedProcess([], 1, "/x/42\n", ""),
            subprocess.CompletedProcess([], 0, "relative/42\n", ""),
            subprocess.CompletedProcess([], 0, "/a/42\n/b/42\n", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        )
        for proc in cases:
            with self.subTest(stdout=proc.stdout, rc=proc.returncode), \
                 patch.object(mc.subprocess, "run", return_value=proc):
                self.assertIsNone(mc.scratchpad_store_key(self.root_a, "42"))
        with patch.object(mc.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertIsNone(mc.scratchpad_store_key(self.root_a, "42"))
        with patch.object(mc.subprocess, "run", side_effect=OSError("nope")):
            self.assertIsNone(mc.scratchpad_store_key(self.root_a, "42"))

    def test_unsaved_duplicate_by_target(self):
        mon = _FakeMon(panes=[{"id": "%5", "target": "%1", "store": ""}])
        refused = _Spawn(mon, self.root_a, task_id=None, followed="%1",
                         add_pane=False)
        self.assertIsNone(refused.result)
        self.assertTrue(refused.said("already open for this agent"))
        allowed = _Spawn(mon, self.root_a, task_id=None, followed="%2")
        self.assertEqual(allowed.result, "%9")
        self.assertEqual(mon._pane("%9")["target"], "%2")
        self.assertNotIn("store", mon._pane("%9"), "an unsaved pad has no key")

    def test_frozen_pane_markers_are_skipped(self):
        key = _key(self.root_a)
        rows = (
            {"id": "%5", "target": "%7", "store": key},     # store match
            {"id": "%6", "target": "%1", "store": ""},      # target match
        )
        for row in rows:
            with self.subTest(row=row["id"], frozen=True):
                mon = _FakeMon(panes=[dict(row, frozen="abcd1234")])
                s = _Spawn(mon, self.root_a, followed="%1")
                self.assertEqual(s.result, "%9", s.notes)
            with self.subTest(row=row["id"], frozen=False):  # control
                mon = _FakeMon(panes=[dict(row)])
                s = _Spawn(mon, self.root_a, followed="%1", add_pane=False)
                self.assertIsNone(s.result)
                self.assertEqual(s.launch.call_count, 0)

    def test_match_is_pure_and_tolerates_short_rows(self):
        self.assertEqual(mc.match_scratchpad_pane("%5\t%1", "%1", ""), "%5")
        self.assertIsNone(mc.match_scratchpad_pane("%5", "%1", "/k"))
        self.assertIsNone(mc.match_scratchpad_pane("\n\n", "%1", "/k"))
        self.assertIsNone(
            mc.match_scratchpad_pane("%5\t\t\t", "%1", ""),
            "an empty store must never match an empty key")


class PlacementAndCommandTests(_RootsMixin, TmuxSocketContainmentMixin,
                               unittest.TestCase):
    CONTAINED_MODULES = (alu,)

    def test_split_shape_and_position(self):
        for value, before in (("top", True), ("TOP ", True), ("bottom", False),
                              ("sideways", False), (None, False)):
            cfg = {} if value is None else {"scratchpad_position": value}
            with self.subTest(position=value):
                s = _Spawn(_FakeMon(), self.root_a, cfg=cfg)
                self.assertIs(s.cfg.split_before, before)
                self.assertEqual(s.cfg.split_direction, "vertical")
                self.assertEqual(s.cfg.split_target_pane, "%1")
                self.assertFalse(s.cfg.new_window)
                self.assertFalse(s.cfg.new_session)
                self.assertEqual(s.cfg.cwd, str(self.root_a))
                self.assertEqual(s.cfg.window, "agent-pick-42")
                self.assertEqual(s.cfg.session, "s1")
                self.assertTrue(s.cfg.select_window)

    def test_height_default_and_fallback(self):
        cases = ((None, 12), ("tall", 12), (0, 12), (-3, 12), (True, 12),
                 (20, 20), ("20", 20), (" 7 ", 7), (1, 1), ("-3", 12),
                 ("+5", 12), ("1.5", 12), ("", 12), ([], 12),
                 # What yaml.safe_load yields for `1.5`, `12.0`, `.inf`,
                 # `-.inf` and `.nan`: never truncated, never an exception.
                 (1.5, 12), (12.0, 12), (float("inf"), 12),
                 (float("-inf"), 12), (float("nan"), 12))
        for value, want in cases:
            cfg = {} if value is None else {"scratchpad_height": value}
            with self.subTest(height=value):
                s = _Spawn(_FakeMon(), self.root_a, cfg=cfg)
                self.assertEqual(s.cfg.split_size, want)

    def test_command_and_hook(self):
        task = _Spawn(_FakeMon(), self.root_a, companion="%3")
        root = os.path.dirname(_key(self.root_a))
        self.assertEqual(
            task.command,
            f"env AITASK_SCRATCHPAD_DIR={shlex.quote(root)} "
            "ait scratchpad --task 42 --target %1")
        task.hook.assert_called_once_with("%1", "%3")
        self.assertTrue(task.said("opened scratchpad for t42"))
        self.assertEqual(task.refreshes, 1)

        unsaved = _Spawn(_FakeMon(), self.root_a, task_id=None)
        self.assertEqual(unsaved.command, "ait scratchpad --unsaved --target %1")
        unsaved.hook.assert_called_once_with("%1", "%9")  # companion None -> pad
        self.assertTrue(unsaved.said("not saved"))

    def test_task_command_requires_absolute_root(self):
        for bad in (None, "", "relative/root"):
            with self.subTest(root=bad), self.assertRaises(ValueError):
                mc.scratchpad_command("42", "%1", bad)


class StoreRootPinTests(_RootsMixin, TmuxSocketContainmentMixin,
                        unittest.TestCase):
    """Concern 1: the editor must open the store the lookup stamped.

    The pad runs in the tmux SERVER's environment from the project root, with
    the project's own helper. Replay the command's own `env` prefix under a
    DIFFERENT ambient root and a different cwd: the helper must still print the
    stamped key.
    """

    CONTAINED_MODULES = (alu,)

    def _replay(self, command: str) -> str:
        argv = shlex.split(command)
        prefix = argv[:argv.index("ait")]
        self.assertEqual(prefix[0], "env")
        env = dict(os.environ, AITASK_SCRATCHPAD_DIR=str(self.tmp / "server_pad"))
        out = subprocess.run(prefix + [str(STORE_SH), "path", "42"],
                             cwd=str(self.root_b), env=env,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def test_pinned_with_override_set(self):
        os.environ["AITASK_SCRATCHPAD_DIR"] = str(self.tmp / "driver_pad")
        mon = _FakeMon()
        s = _Spawn(mon, self.root_a)
        stamped = mon._pane("%9")["store"]
        self.assertEqual(stamped, str(self.tmp.resolve() / "driver_pad" / "42"))
        self.assertEqual(self._replay(s.command), stamped)

    def test_pinned_with_override_unset(self):
        mon = _FakeMon()
        s = _Spawn(mon, self.root_a)
        stamped = mon._pane("%9")["store"]
        self.assertEqual(
            stamped, str(self.real_a.resolve() / ".aitask-scratchpad" / "42"))
        self.assertEqual(self._replay(s.command), stamped)

    def test_control_unpinned_command_follows_the_ambient_root(self):
        """Negative control: without the prefix the replay lands elsewhere."""
        mon = _FakeMon()
        _Spawn(mon, self.root_a)
        stamped = mon._pane("%9")["store"]
        env = dict(os.environ, AITASK_SCRATCHPAD_DIR=str(self.tmp / "server_pad"))
        out = subprocess.run([str(STORE_SH), "path", "42"], cwd=str(self.root_a),
                             env=env, capture_output=True, text=True, check=True)
        self.assertNotEqual(out.stdout.strip(), stamped)


class IdentityAndRemovalTests(_RootsMixin, TmuxSocketContainmentMixin,
                              unittest.TestCase):
    """Concerns 2 and 3: identify the launched pane, never claim an unproven gone."""

    CONTAINED_MODULES = (alu,)
    RECOVER = "#{pane_id} #{pane_pid}"

    def test_recovery_finds_the_pane_by_pid(self):
        mon = _FakeMon()
        s = _Spawn(mon, self.root_a, launch=(None, 999, None))
        self.assertEqual(s.result, "%9")
        self.assertEqual(mon._pane("%9")["target"], "%1")
        s.hook.assert_called_once_with("%1", "%9")

    def test_recovery_successful_query_without_the_pid_is_exited(self):
        mon = _FakeMon()
        s = _Spawn(mon, self.root_a, launch=(None, 999, None), add_pane=False)
        self.assertIsNone(s.result)
        self.assertEqual(mon.count("set-option"), 0)
        self.assertEqual(mon.count("kill-pane"), 0)
        s.hook.assert_not_called()
        self.assertTrue(s.said("exited immediately"))

    def test_recovery_failed_queries_are_unknown_and_bounded(self):
        mon = _FakeMon(list_rc=[0, -1])   # lookup ok, every recovery fails
        s = _Spawn(mon, self.root_a, launch=(None, 999, None))
        self.assertIsNone(s.result)
        self.assertEqual(mon.count("list-panes", self.RECOVER), 3)
        self.assertEqual(mon.count("set-option"), 0)
        s.hook.assert_not_called()
        self.assertTrue(s.said("pid 999"))
        self.assertFalse(s.said("exited") or s.said("removed"))
        self.assertEqual(s.refreshes, 1)

    def test_malformed_successful_listing_is_unknown_not_exited(self):
        """An rc=0 listing is evidence only if every row is `%<n> <pid>`."""
        class _Scripted:
            def __init__(self, outs):
                self.outs, self.calls = list(outs), 0

            def tmux_run(self, args, timeout=5.0):
                self.calls += 1
                return (0, self.outs.pop(0) if len(self.outs) > 1 else self.outs[0])

        malformed = ("garbage", "%9 broken", "bogus 999", "%9 999 extra",
                     "%9 0", "%8 111\nnot-a-row")
        for out in malformed:
            with self.subTest(out=out), patch.object(mc.time, "sleep"):
                mon = _Scripted([out])
                self.assertEqual(mc._recover_pad_pane(mon, 999), ("unknown", None))
                self.assertEqual(mon.calls, 3, "retried, bounded")
        with patch.object(mc.time, "sleep"):
            # A malformed answer, then a good one: recovered on the retry.
            mon = _Scripted(["garbage", "%8 111\n%9 999"])
            self.assertEqual(mc._recover_pad_pane(mon, 999), ("found", "%9"))
            # Well-formed and the pid is absent: that, and only that, is exited.
            self.assertEqual(mc._recover_pad_pane(_Scripted(["%8 111"]), 999),
                             ("exited", None))
            for bad_pid in (None, 0, -1, True, "999"):
                with self.subTest(pid=bad_pid):
                    mon = _Scripted(["%9 999"])
                    self.assertEqual(mc._recover_pad_pane(mon, bad_pid),
                                     ("unknown", None))
                    self.assertEqual(mon.calls, 0)

    def test_malformed_listing_through_spawn_never_stamps(self):
        mon = _FakeMon()
        real_run = mon.tmux_run

        def run(args, timeout=5.0):
            if args[0] == "list-panes" and "#{pane_id} #{pane_pid}" in args:
                mon.calls.append(list(args))
                return (0, "bogus 999")
            return real_run(args, timeout)

        mon.tmux_run = run
        s = _Spawn(mon, self.root_a, launch=(None, 999, None))
        self.assertIsNone(s.result)
        self.assertEqual(mon.count("set-option"), 0)
        self.assertEqual(mon.count("kill-pane"), 0)
        s.hook.assert_not_called()
        self.assertTrue(s.said("pid 999"))
        self.assertFalse(s.said("exited"))

    def test_no_pane_id_and_no_pid_queries_nothing(self):
        mon = _FakeMon()
        s = _Spawn(mon, self.root_a, launch=(None, None, None))
        self.assertIsNone(s.result)
        self.assertEqual(mon.count("list-panes", self.RECOVER), 0)
        self.assertEqual(mon.count("set-option"), 0)
        s.hook.assert_not_called()
        self.assertTrue(s.said("close any stray pane by hand"))
        self.assertFalse(s.said("exited") or s.said("removed") or s.said("pid"))

    def test_launch_error_reports_without_refresh(self):
        mon = _FakeMon()
        s = _Spawn(mon, self.root_a, launch=(None, None, "tmux split-window failed (rc=1)"))
        self.assertIsNone(s.result)
        self.assertTrue(s.said("launch failed"))
        self.assertEqual(s.refreshes, 0)

    def test_stamp_failure_probe_matrix(self):
        gone, live, failed = (0, ""), (0, "%9"), (-1, "")
        rows = (
            ("gone", [gone], False, "exited before"),
            ("live->gone", [live, gone], True, "removed it"),
            ("live->failed", [live, failed], True, "close it by hand"),
            ("failed->gone", [failed, gone], True, "removed it"),
            ("failed->failed", [failed, failed], True, "close it by hand"),
            ("junk->gone", [(0, "%12"), gone], True, "removed it"),
        )
        for name, probes, killed, message in rows:
            with self.subTest(row=name):
                mon = _FakeMon(set_rc={mc.SCRATCHPAD_TARGET_OPTION: 1},
                               probes=probes)
                s = _Spawn(mon, self.root_a)
                self.assertIsNone(s.result)
                self.assertEqual(
                    mon.count("set-option", mc.SCRATCHPAD_TARGET_OPTION), 2,
                    "one retry")
                self.assertEqual(mon.count("kill-pane"), 1 if killed else 0)
                self.assertTrue(s.said(message), s.notes)
                if message == "close it by hand":
                    self.assertTrue(s.said("%9"))
                    self.assertFalse(s.said("removed"))
                s.hook.assert_not_called()

    def test_store_stamp_failure_removes_the_pad(self):
        mon = _FakeMon(set_rc={mc.SCRATCHPAD_STORE_OPTION: 1})
        s = _Spawn(mon, self.root_a)
        self.assertIsNone(s.result)
        self.assertEqual(mon.count("set-option", mc.SCRATCHPAD_TARGET_OPTION), 1)
        self.assertEqual(mon.count("set-option", mc.SCRATCHPAD_STORE_OPTION), 2)
        self.assertEqual(mon.count("kill-pane", "%9"), 1)
        self.assertIsNone(mon._pane("%9"))
        self.assertTrue(s.said("removed it"))
        s.hook.assert_not_called()


class _FakeGateway:
    def __init__(self, rc=0, out=""):
        self.rc, self.out = rc, out
        self.ran: list[list[str]] = []
        self.spawned: list[list[str]] = []

    def run(self, args, timeout=None):
        self.ran.append(list(args))
        return (self.rc, self.out)

    def spawn(self, args):
        self.spawned.append(list(args))


class LaunchSplitPaneTests(unittest.TestCase):
    CFG = TmuxLaunchConfig(
        session="s1", window="agent-pick-42", new_session=False,
        new_window=False, split_direction="vertical", split_before=True,
        split_size=12, split_target_pane="%1", cwd="/p1", select_window=True,
    )

    def _launch(self, out, rc=0):
        gw = _FakeGateway(rc, out)
        with patch.object(alu, "_TMUX", gw):
            return alu.launch_split_pane("cmd", self.CFG), gw

    def test_parsing(self):
        cases = (("%9\t999\n", ("%9", 999)), ("x\t999", (None, 999)),
                 ("%9\tabc", ("%9", None)), ("", (None, None)),
                 ("%9\t0", ("%9", None)), ("%9\t-4", ("%9", None)),
                 ("%9", ("%9", None)),
                 # An empty id must not swallow the pid: fields are split
                 # before they are trimmed.
                 ("\t999\n", (None, 999)), ("\n\t999\n", (None, 999)),
                 (" %9 \t 999 \n", ("%9", 999)))
        for out, want in cases:
            with self.subTest(out=out):
                (pane, pid, err), _gw = self._launch(out)
                self.assertEqual((pane, pid), want)
                self.assertIsNone(err)

    def test_nonzero_rc_is_an_error(self):
        (pane, pid, err), gw = self._launch("%9\t999", rc=1)
        self.assertEqual((pane, pid), (None, None))
        self.assertIn("rc=1", err)
        self.assertEqual(gw.spawned, [], "no select-window after a failure")

    def test_argv_matches_launch_in_tmux_but_for_the_format(self):
        _res, gw = self._launch("%9\t999")
        split_pane_argv = gw.ran[0]
        legacy = _FakeGateway(0, "999")
        with patch.object(alu, "_TMUX", legacy):
            alu.launch_in_tmux("cmd", self.CFG)
        legacy_argv = legacy.ran[0]
        fmt_at = split_pane_argv.index("-F") + 1
        self.assertEqual(split_pane_argv[fmt_at], "#{pane_id}\t#{pane_pid}")
        self.assertEqual(legacy_argv[fmt_at], "#{pane_pid}")
        self.assertEqual(split_pane_argv[:fmt_at] + split_pane_argv[fmt_at + 1:],
                         legacy_argv[:fmt_at] + legacy_argv[fmt_at + 1:])
        self.assertEqual(
            split_pane_argv,
            ["split-window", "-P", "-F", "#{pane_id}\t#{pane_pid}", "-v", "-b",
             "-l", "12", "-t", "%1", "-c", "/p1", "cmd"])
        self.assertEqual(gw.spawned, legacy.spawned)
        self.assertEqual(len(gw.spawned), 1)
        self.assertEqual(gw.spawned[0][0], "select-window")


class _FakeTaskCache:
    def __init__(self, task_id):
        self._task_id = task_id

    def get_task_id_for_pane(self, pane):
        return self._task_id


def _mk_app(monitor, root: Path, task_id="42"):
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._monitor = monitor
    app._session = "s1"
    app._task_cache = _FakeTaskCache(task_id)
    app.spy_notify: list = []
    app.spy_later: list = []
    app.notify = lambda msg, **kw: app.spy_notify.append(
        (msg, kw.get("severity", "information")))
    app.call_later = lambda *a, **k: app.spy_later.append(a)
    app._find_own_agent_snapshot = lambda: SimpleNamespace(
        pane=SimpleNamespace(pane_id="%1", session_name="s1",
                             window_name="agent-pick-42"))
    app._root_for_snap = lambda snap: root
    return app


class MinimonitorActionTests(_RootsMixin, TmuxSocketContainmentMixin,
                             unittest.TestCase):
    CONTAINED_MODULES = (alu,)

    def _press(self, task_id, tmux_pane=None):
        mon = _FakeMon()
        app = _mk_app(mon, self.root_a, task_id)

        def fake_launch(command, config):
            mon.panes.append({"id": "%9", "pid": "999"})
            return ("%9", 999, None)

        env = {"TMUX_PANE": tmux_pane} if tmux_pane else {}
        with patch.dict(os.environ, env), \
             patch.object(mc, "launch_split_pane", side_effect=fake_launch) as launch, \
             patch.object(mc, "attach_companion_cleanup_hook",
                          return_value="installed") as hook, \
             patch.object(mc, "load_project_tmux_config", return_value={}):
            app.action_open_scratchpad()
        return app, launch, hook

    def test_binding_and_hint(self):
        match = [b for b in mm.MiniMonitorApp.BINDINGS
                 if getattr(b, "action", None) == "open_scratchpad"]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0].key, "o")
        self.assertIn("o:notes", mm.KEY_HINTS_TEXT)

    def test_task_agent_opens_a_saved_pad(self):
        app, launch, hook = self._press("42", tmux_pane="%3")
        command, cfg = launch.call_args.args
        self.assertTrue(command.endswith("ait scratchpad --task 42 --target %1"))
        self.assertTrue(command.startswith("env AITASK_SCRATCHPAD_DIR="))
        self.assertTrue(cfg.select_window)
        hook.assert_called_once_with("%1", "%3")   # this minimonitor's pane
        self.assertFalse(any("not be saved" in m for m, _ in app.spy_notify))
        self.assertEqual(len(app.spy_later), 1, "refresh scheduled")

    def test_non_task_agent_opens_an_unsaved_pad_and_says_so(self):
        app, launch, hook = self._press(None)
        command, _cfg = launch.call_args.args
        self.assertEqual(command, "ait scratchpad --unsaved --target %1")
        self.assertTrue(any("notes will not be saved" in m
                            for m, _ in app.spy_notify))
        hook.assert_called_once_with("%1", "%9")   # no TMUX_PANE -> the pad

    def test_no_followed_agent(self):
        mon = _FakeMon()
        app = _mk_app(mon, self.root_a)
        app._find_own_agent_snapshot = lambda: None
        with patch.object(mc, "launch_split_pane") as launch:
            app.action_open_scratchpad()
        launch.assert_not_called()
        self.assertTrue(any("no followed agent" in m.lower()
                            for m, _ in app.spy_notify))


if __name__ == "__main__":
    unittest.main()
