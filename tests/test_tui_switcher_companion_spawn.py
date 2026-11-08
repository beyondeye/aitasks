"""The TUI switcher's companion key: spawn a minimonitor beside the host TUI (t2174).

Three layers are pinned here:

1. **The read-only presence probe** (`companion_present`) shares the split
   path's classification (`_scan_companion_window`), so the switcher never
   offers a spawn the split would refuse for presence, nor hides one it would
   allow. The parity table drives both. Unlike the split it never self-heals,
   and an unreadable window is "unknown" (None), which the overlay hides.

2. **The spawn plumbing**: `explicit=True` bypasses `auto_spawn` (which governs
   automatic spawning only), and `gateway_pane_window` resolves the caller's
   own window by index under the t1951 server-identity rule.

3. **The overlay**: the key is never offered in monitor / minimonitor, it
   targets `$TMUX_PANE`'s window and not the browsed session, and its hint
   spells `Shift+M` — `render_label` would otherwise show `(M)`, the same as
   monitor's `m`. The window is resolved from the pane when the key is pressed,
   never carried from mount (t2230).

4. **Window rows act on the window id** (t2230): `_session_windows` lists
   `@N` ids, a row selects `=<session>:@N`, and a select that fails (the
   window closed while the overlay was open) neither teleports nor dismisses.

The tmux gateway is faked wholesale, so no tmux call leaves the test.

Run: python3 tests/test_tui_switcher_companion_spawn.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils  # noqa: E402
import tui_switcher as ts  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    MONITOR_KIND_OPTION, AitasksSession, companion_present,
    gateway_pane_window, maybe_spawn_minimonitor,
)

LIVE = f"minimonitor:{os.getpid()}"


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


STALE = f"minimonitor:{_dead_pid()}"

#: Positional fields of a fixture pane tuple -> the `#{...}` spec each answers.
#: Rows are rendered from the format the code under test requests, so a field
#: added to it cannot shift `pane_start_command` into a neighbour's slot.
_PANE_TUPLE_SPECS = (
    "#{pane_id}", "#{@aitask_monitor_kind}", "#{@aitask_shadow_target}",
    "#{@aitask_frozen}", "#{pane_dead}", "#{pane_start_command}",
)


def _render_panes(args, panes) -> str:
    fmt = args[args.index("-F") + 1]
    rows = []
    for pane in panes:
        values = dict(zip(_PANE_TUPLE_SPECS, pane))
        rows.append("|".join(values.get(spec, "") for spec in fmt.split("|")))
    return "\n".join(rows)


class _FakeTmux:
    """Scripted gateway: `list-panes` answers from ``panes``; `display-message`
    answers the lock's socket read, then the gateway pane-location read."""

    def __init__(self, panes, *, list_rc=0, socket_path="", location="",
                 location_rc=0):
        self._panes = panes
        self._list_rc = list_rc
        self._socket_path = socket_path
        self._location = location
        self._location_rc = location_rc
        self.ran: list[list[str]] = []
        self.spawned: list[list[str]] = []

    def run(self, args, timeout=5.0):
        self.ran.append(list(args))
        verb = args[0] if args else ""
        if verb == "list-panes":
            if self._list_rc:
                return (self._list_rc, "")
            return (0, _render_panes(args, self._panes))
        if verb == "display-message":
            if args[-1] == "#{socket_path}":
                return (0, self._socket_path)
            if args[-1].startswith("#{socket_path}\t"):
                return (self._location_rc, self._location)
            return (0, "%1")
        if verb == "split-window":
            return (0, "%77")
        if verb == "show-hooks":
            return (0, "")
        return (0, "")

    def spawn(self, args, **kwargs):
        self.spawned.append(list(args))

    def verbs(self, verb: str) -> list[list[str]]:
        return [a for a in self.ran + self.spawned if a and a[0] == verb]


class _GatewayCase(unittest.TestCase):
    """Installs a `_FakeTmux` as the gateway, plus a per-test lock dir."""

    def setUp(self):
        self.sock_dir = tempfile.mkdtemp(prefix="t2174_sock_")
        self.addCleanup(shutil.rmtree, self.sock_dir, True)
        self.socket_path = os.path.join(self.sock_dir, "ait")

    def _install(self, tmux: _FakeTmux) -> _FakeTmux:
        saved = agent_launch_utils._TMUX
        agent_launch_utils._TMUX = tmux
        self.addCleanup(lambda: setattr(agent_launch_utils, "_TMUX", saved))
        saved_hook = agent_launch_utils.attach_companion_cleanup_hook
        agent_launch_utils.attach_companion_cleanup_hook = (
            lambda agent, companion: "installed")
        self.addCleanup(lambda: setattr(
            agent_launch_utils, "attach_companion_cleanup_hook", saved_hook))
        return tmux


# --- 1. the read-only presence probe ------------------------------------------


class CompanionPresentTests(_GatewayCase):

    def _probe(self, panes, pane="%1", **kwargs):
        tmux = self._install(_FakeTmux(panes, **kwargs))
        return tmux, companion_present(pane)

    def test_a_live_marker_is_present(self):
        _tmux, result = self._probe([("%1", "", ""), ("%2", LIVE, "")])
        self.assertIs(result, True)

    def test_a_stale_marker_is_absent_and_never_healed(self):
        """The probe is read-only: the split path clears this marker, the probe
        must not touch it."""
        tmux, result = self._probe([("%1", "", ""), ("%2", STALE, "")])
        self.assertIs(result, False)
        self.assertEqual([], tmux.verbs("set-option"))

    def test_an_unverifiable_marker_is_present(self):
        _tmux, result = self._probe([("%1", "", ""), ("%2", "garbage:123", "")])
        self.assertIs(result, True)

    def test_a_booting_companion_is_present(self):
        _tmux, result = self._probe(
            [("%1", "", ""), ("%2", "", "", "", "0", "ait minimonitor")])
        self.assertIs(result, True)

    def test_a_dead_companion_is_absent(self):
        _tmux, result = self._probe(
            [("%1", "", ""), ("%2", "", "", "", "1", "ait minimonitor")])
        self.assertIs(result, False)

    def test_a_bound_helper_alone_is_absent(self):
        _tmux, result = self._probe([("%1", "", ""), ("%2", "", "%1")])
        self.assertIs(result, False)

    def test_a_failed_listing_is_unknown(self):
        _tmux, result = self._probe([("%1", "", "")], list_rc=1)
        self.assertIsNone(result)

    def test_a_listing_without_the_pane_is_unknown(self):
        _tmux, result = self._probe([("%5", "", "")], pane="%1")
        self.assertIsNone(result)

    def test_an_empty_pane_is_unknown_without_a_tmux_call(self):
        tmux, result = self._probe([("%1", "", "")], pane="")
        self.assertIsNone(result)
        self.assertEqual([], tmux.ran)

    def test_the_listing_targets_the_pane_itself(self):
        """An untargeted list-panes would resolve to the session's CURRENT
        window, not the caller's (t2039)."""
        tmux, _result = self._probe([("%1", "", "")])
        listing = tmux.verbs("list-panes")[0]
        self.assertEqual("%1", listing[listing.index("-t") + 1])


class ProbeSplitParityTests(_GatewayCase):
    """For every layout under the overcrowding limit, the probe reports present
    exactly when the split path refuses — they share one classification."""

    LAYOUTS = {
        "empty": [("%1", "", "")],
        "live": [("%1", "", ""), ("%2", LIVE, "")],
        "stale": [("%1", "", ""), ("%2", STALE, "")],
        "unverifiable": [("%1", "", ""), ("%2", "garbage:123", "")],
        "booting": [("%1", "", ""), ("%2", "", "", "", "0", "ait minimonitor")],
        "dead": [("%1", "", ""), ("%2", "", "", "", "1", "ait minimonitor")],
        "helper": [("%1", "", ""), ("%2", "", "%1")],
        "frozen": [("%1", "", ""), ("%2", "", "", "1")],
        "stale_then_live": [("%1", "", ""), ("%2", STALE, ""), ("%3", LIVE, "")],
        "live_then_stale": [("%1", "", ""), ("%3", LIVE, ""), ("%2", STALE, "")],
    }

    def test_probe_and_split_agree(self):
        for name, panes in self.LAYOUTS.items():
            with self.subTest(layout=name):
                self._install(_FakeTmux(panes, socket_path=self.socket_path))
                present = companion_present("%1")
                self._install(_FakeTmux(panes, socket_path=self.socket_path))
                spawned = maybe_spawn_minimonitor(
                    "demo", "board", window_index="3", force_companion=True,
                    project_root=Path("/nonexistent-for-config"),
                    agent_pane="%1",
                )
                self.assertIs(present, spawned is None)

    def test_the_split_still_heals_a_stale_marker_beside_a_live_one(self):
        """In either order. live_then_stale is the case that needs the shared
        scan: the old loop returned on the live marker before reaching the
        stale one, so it was never cleared."""
        for name in ("stale_then_live", "live_then_stale"):
            with self.subTest(layout=name):
                tmux = self._install(_FakeTmux(self.LAYOUTS[name],
                                               socket_path=self.socket_path))
                maybe_spawn_minimonitor(
                    "demo", "board", window_index="3", force_companion=True,
                    project_root=Path("/nonexistent-for-config"),
                    agent_pane="%1")
                clears = [a for a in tmux.verbs("set-option")
                          if MONITOR_KIND_OPTION in a and "-pu" in a]
                self.assertEqual(1, len(clears))
                self.assertIn("%2", clears[0])
                self.assertEqual([], tmux.verbs("split-window"))


# --- 2. spawn plumbing --------------------------------------------------------


class ExplicitSpawnTests(_GatewayCase):

    def setUp(self):
        super().setUp()
        self.project = Path(tempfile.mkdtemp(prefix="t2174_proj_"))
        self.addCleanup(shutil.rmtree, self.project, True)
        meta = self.project / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        (meta / "project_config.yaml").write_text(
            "tmux:\n  minimonitor:\n    auto_spawn: false\n")

    def _spawn(self, **kwargs):
        tmux = self._install(_FakeTmux([("%1", "", "")],
                                       socket_path=self.socket_path))
        result = maybe_spawn_minimonitor(
            "demo", "board", window_index="3", force_companion=True,
            project_root=self.project, agent_pane="%1", **kwargs)
        return tmux, result

    def test_auto_spawn_false_refuses_an_automatic_spawn(self):
        tmux, result = self._spawn()
        self.assertIsNone(result)
        self.assertEqual([], tmux.verbs("split-window"))

    def test_an_explicit_request_bypasses_auto_spawn(self):
        tmux, result = self._spawn(explicit=True)
        self.assertEqual("%77", result)
        self.assertEqual(1, len(tmux.verbs("split-window")))

    def test_an_explicit_request_still_respects_an_existing_companion(self):
        tmux = self._install(_FakeTmux([("%1", "", ""), ("%2", LIVE, "")],
                                       socket_path=self.socket_path))
        result = maybe_spawn_minimonitor(
            "demo", "board", window_index="3", force_companion=True,
            explicit=True, project_root=self.project, agent_pane="%1")
        self.assertIsNone(result)
        self.assertEqual([], tmux.verbs("split-window"))


class GatewayPaneWindowTests(_GatewayCase):

    def _resolve(self, *, location, location_rc=0, pane="%4",
                 tmux_env=None):
        tmux = self._install(_FakeTmux([], location=location,
                                       location_rc=location_rc))
        env = f"{self.socket_path},123,0" if tmux_env is None else tmux_env
        return tmux, gateway_pane_window(pane, env)

    def test_the_gateways_own_pane_resolves_to_its_session_and_index(self):
        _tmux, result = self._resolve(location=f"{self.socket_path}\tdemo\t7")
        self.assertEqual(("demo", "7"), result)

    def test_a_pane_answered_by_another_server_is_not_trusted(self):
        other = os.path.join(self.sock_dir, "other")
        _tmux, result = self._resolve(location=f"{other}\tdemo\t7")
        self.assertIsNone(result)

    def test_a_failed_read_is_none(self):
        _tmux, result = self._resolve(location="", location_rc=1)
        self.assertIsNone(result)

    def test_a_malformed_answer_is_none(self):
        _tmux, result = self._resolve(location=f"{self.socket_path}\tdemo\tx")
        self.assertIsNone(result)

    def test_no_pane_or_env_makes_no_tmux_call(self):
        for pane, env in (("", None), ("%4", "")):
            with self.subTest(pane=pane, env=env):
                tmux, result = self._resolve(location="", pane=pane,
                                             tmux_env=env)
                self.assertIsNone(result)
                self.assertEqual([], tmux.ran)


# --- 3. the overlay -----------------------------------------------------------


class _Capture:
    def __init__(self) -> None:
        self.text: str | None = None
        self.display = True

    def update(self, text: str) -> None:
        self.text = text


def _overlay(current_tui: str = "board", multi_mode: bool = False):
    overlay = ts.TuiSwitcherOverlay(session="s1", current_tui=current_tui)
    overlay._multi_mode = multi_mode
    capture = _Capture()
    overlay.query_one = lambda *args, **kwargs: capture
    return overlay, capture


_TARGET = ts._CompanionTarget("%9", Path("/host/project"))


class ResolveCompanionTargetTests(unittest.TestCase):

    def _resolve(self, current_tui, *, probe, location=("s1", "4")):
        overlay, _capture = _overlay(current_tui)
        calls: list[str] = []
        env = {"TMUX_PANE": "%9", "TMUX": "/tmp/sock,1,0"}
        with unittest.mock.patch.dict(os.environ, env), \
                unittest.mock.patch.object(
                    ts, "gateway_pane_window", lambda pane, tmux: location), \
                unittest.mock.patch.object(
                    ts, "companion_present",
                    lambda pane: calls.append(pane) or probe):
            return overlay._resolve_companion_target(), calls

    def test_never_offered_in_the_monitor_or_minimonitor_or_an_unnamed_host(self):
        for host in ("monitor", "minimonitor", ""):
            with self.subTest(host=host):
                target, calls = self._resolve(host, probe=False)
                self.assertIsNone(target)
                self.assertEqual([], calls, "ineligible hosts make no tmux call")

    def test_hidden_when_a_companion_is_present_or_unknown(self):
        for probe in (True, None):
            with self.subTest(probe=probe):
                target, _calls = self._resolve("board", probe=probe)
                self.assertIsNone(target)

    def test_hidden_when_the_pane_is_not_on_the_gateway_server(self):
        target, calls = self._resolve("board", probe=False, location=None)
        self.assertIsNone(target)
        self.assertEqual([], calls)

    def test_offered_for_the_host_pane_window_when_absent(self):
        target, calls = self._resolve("brainstorm-42", probe=False)
        self.assertEqual("%9", target.pane)
        self.assertEqual(Path.cwd(), target.project_root)
        self.assertEqual(["%9"], calls)

    def test_the_target_carries_no_window_index(self):
        """Nothing mount-time about the window survives to the key press."""
        self.assertEqual(("pane", "project_root"), ts._CompanionTarget._fields)


class CompanionHintTests(unittest.TestCase):

    SEGMENT = f"[{ts.TUI_KEY_HINT_STYLE}](Shift+M)[/] minimonitor"

    def test_the_hint_appears_only_with_a_target_in_both_modes(self):
        for multi in (False, True):
            with self.subTest(multi=multi):
                overlay, capture = _overlay(multi_mode=multi)
                if multi:
                    overlay._all_sessions = []
                    overlay._selected_group = None
                overlay._render_hint()
                self.assertNotIn("minimonitor", capture.text)
                overlay._companion_target = _TARGET
                overlay._render_hint()
                second_line = capture.text.split("\n", 1)[1]
                self.assertTrue(second_line.startswith(self.SEGMENT + "  "))

    def test_the_hint_never_reads_like_the_monitor_key(self):
        overlay, capture = _overlay()
        overlay._companion_target = _TARGET
        overlay._render_hint()
        self.assertNotIn("(M)[/]inimonitor", capture.text)

    def test_spell_shift_follows_the_resolved_key(self):
        cases = {
            "M": f"[{ts.TUI_KEY_HINT_STYLE}](Shift+M)[/] minimonitor",
            "w": f"[{ts.TUI_KEY_HINT_STYLE}](W)[/] minimonitor",
            "ctrl+o": f"[{ts.TUI_KEY_HINT_STYLE}](Ctrl+O)[/] minimonitor",
        }
        for key, expected in cases.items():
            with self.subTest(key=key), unittest.mock.patch.object(
                    ts, "resolve_key", lambda scope, action, default, k=key: k):
                self.assertEqual(expected, ts._hint_segment(
                    "spawn_minimonitor", "minimonitor", "M", spell_shift=True))

    def test_existing_segments_are_unchanged_without_spell_shift(self):
        for item in ts._HINT_ITEMS:
            with self.subTest(action=item[0]):
                key = ts.resolve_key(ts._TUI_SWITCHER_SCOPE, item[0], item[2]) or item[2]
                plain = ts._KEY_PAREN_RE.sub(
                    rf"[{ts.TUI_KEY_HINT_STYLE}](\1)[/]",
                    ts.render_label(item[1], key), count=1)
                self.assertEqual(plain, ts._hint_segment(*item))


class SpawnActionTests(unittest.TestCase):

    def _run(self, *, target, result="%77", location=("s1", "4")):
        overlay, _capture = _overlay("board")
        overlay._companion_target = target
        # Browse to ANOTHER session: the spawn must still target the host's.
        overlay._all_sessions = [
            AitasksSession("s1", Path("/host/project"), "host"),
            AitasksSession("other", Path("/elsewhere"), "elsewhere"),
        ]
        overlay._selected_key = overlay._all_sessions[1].key
        calls = []
        dismissed = []
        notified = []
        overlay.dismiss = lambda value=None: dismissed.append(value)
        app = unittest.mock.MagicMock()
        app.notify = lambda *a, **k: notified.append((a, k))
        located: list[tuple[str, str]] = []
        env = {"TMUX_PANE": "%9", "TMUX": "/tmp/sock,1,0"}
        with unittest.mock.patch.dict(os.environ, env), \
                unittest.mock.patch.object(
                    ts, "gateway_pane_window",
                    lambda pane, tmux: located.append((pane, tmux)) or location), \
                unittest.mock.patch.object(
                    agent_launch_utils, "maybe_spawn_minimonitor",
                    lambda *a, **k: calls.append((a, k)) or result), \
                unittest.mock.patch.object(
                    ts.TuiSwitcherOverlay, "app",
                    new_callable=unittest.mock.PropertyMock, return_value=app):
            overlay.action_spawn_minimonitor()
        self.located = located
        return calls, dismissed, notified

    def test_no_target_is_a_no_op(self):
        calls, dismissed, notified = self._run(target=None)
        self.assertEqual(([], [], []), (calls, dismissed, notified))

    def test_spawns_in_the_host_window_not_the_browsed_session(self):
        calls, dismissed, notified = self._run(target=_TARGET)
        self.assertEqual(1, len(calls))
        args, kwargs = calls[0]
        self.assertEqual(("s1", "board"), args)
        self.assertEqual("4", kwargs["window_index"])
        self.assertEqual("%9", kwargs["agent_pane"])
        self.assertEqual([("%9", "/tmp/sock,1,0")], self.located)
        self.assertEqual(Path("/host/project"), kwargs["project_root"])
        self.assertIs(True, kwargs["force_companion"])
        self.assertIs(True, kwargs["explicit"])
        self.assertEqual([None], dismissed)
        self.assertEqual([], notified)

    def test_the_window_is_resolved_from_the_pane_at_key_time(self):
        """t2230: a window closed while the overlay was open renumbers the host
        window from 4 to 2. The spawn must use the index the pane is at NOW."""
        calls, dismissed, _notified = self._run(target=_TARGET,
                                                location=("s1", "2"))
        args, kwargs = calls[0]
        self.assertEqual(("s1", "board"), args)
        self.assertEqual("2", kwargs["window_index"])
        self.assertEqual("%9", kwargs["agent_pane"])
        self.assertEqual([None], dismissed)

    def test_a_pane_that_cannot_be_located_spawns_nothing(self):
        calls, dismissed, notified = self._run(target=_TARGET, location=None)
        self.assertEqual([], calls)
        self.assertEqual([], dismissed)
        self.assertEqual(1, len(notified))
        self.assertEqual("warning", notified[0][1].get("severity"))

    def test_a_refused_spawn_warns_and_keeps_the_overlay(self):
        calls, dismissed, notified = self._run(target=_TARGET, result=None)
        self.assertEqual(1, len(calls))
        self.assertEqual([], dismissed)
        self.assertEqual(1, len(notified))
        self.assertEqual("warning", notified[0][1].get("severity"))


class _FakeSwitcherTmux:
    """Stands in for `tui_switcher._TMUX`: scripted `list-windows` answers and a
    `select-window` that succeeds only for a window that still exists."""

    def __init__(self, windows):
        # (window_id, window_index, name) as the CURRENT server would list them.
        self.windows = list(windows)
        self.list_rc = 0
        self.runs: list[list[str]] = []
        self.spawns: list[list[str]] = []

    def run(self, args, timeout=None):
        self.runs.append(list(args))
        if args[0] == "list-windows":
            if self.list_rc != 0:
                return self.list_rc, ""
            return 0, "".join(f"{i}\t{x}\t{n}\n" for i, x, n in self.windows)
        if args[0] == "select-window":
            window = args[args.index("-t") + 1].split(":", 1)[1]
            known = ({i for i, _x, _n in self.windows}
                     | {x for _i, x, _n in self.windows}
                     | {n for _i, _x, n in self.windows})
            return (0, "") if window in known else (1, "")
        return 0, ""

    def spawn(self, args, **_kwargs):
        self.spawns.append(list(args))
        return unittest.mock.MagicMock()

    def selects(self):
        return [r for r in self.runs if r[0] == "select-window"]


class SessionWindowsParserTests(unittest.TestCase):

    def _list(self, out, rc=0):
        fake = unittest.mock.MagicMock()
        fake.run.return_value = (rc, out)
        with unittest.mock.patch.object(ts, "_TMUX", fake):
            rows = ts._session_windows("s1")
        return rows, fake.run.call_args.args[0]

    def test_rows_carry_the_window_id_and_keep_tabbed_names_whole(self):
        rows, argv = self._list("@5\t1\tagent-a\n@7\t2\tname\twith\ttabs\n")
        self.assertEqual([("@5", "1", "agent-a"), ("@7", "2", "name\twith\ttabs")], rows)
        self.assertEqual(["list-windows", "-t", ts.tmux_session_target("s1"),
                          "-F", "#{window_id}\t#{window_index}\t#{window_name}"], argv)

    def test_rows_without_a_well_formed_id_are_left_out(self):
        rows, _argv = self._list("5\t1\tno-at\n@x\t2\tbad-id\n@9\t3\n@4\t4\tok\n")
        self.assertEqual([("@4", "4", "ok")], rows)

    def test_a_failed_listing_is_empty(self):
        rows, _argv = self._list("@5\t1\tagent-a\n", rc=1)
        self.assertEqual([], rows)


class WindowRowsActOnIdTests(unittest.TestCase):
    """t2230: a window row selects by id, and a failed select changes nothing."""

    def _populated(self, fake, session="s1"):
        overlay = ts.TuiSwitcherOverlay(session=session, current_tui="")
        overlay._attached_session = "s1"
        appended = []
        list_view = unittest.mock.MagicMock()
        list_view.append = appended.append
        overlay.query_one = lambda *a, **k: list_view
        with unittest.mock.patch.object(ts, "_TMUX", fake), \
                unittest.mock.patch.object(ts, "_build_tui_list", return_value=[]), \
                unittest.mock.patch.object(
                    ts, "_discover_brainstorm_sessions", return_value=[]):
            overlay._populate_list_for(session)
        rows = {i.window_name: i for i in appended
                if isinstance(i, ts._WindowListItem)}
        return overlay, rows

    def _enter(self, overlay, item, fake, *, attached="s1"):
        overlay._attached_session = attached
        dismissed, notified = [], []
        overlay.dismiss = lambda value=None: dismissed.append(value)
        app = unittest.mock.MagicMock()
        app.notify = lambda *a, **k: notified.append((a, k))
        with unittest.mock.patch.object(ts, "_TMUX", fake), \
                unittest.mock.patch.object(
                    ts.TuiSwitcherOverlay, "app",
                    new_callable=unittest.mock.PropertyMock, return_value=app):
            overlay._switch_to(item.window_name, True, item.window_id)
        return dismissed, notified

    def test_enter_after_a_renumber_selects_the_listed_window_by_id(self):
        fake = _FakeSwitcherTmux([("@3", "0", "board"), ("@5", "1", "agent-a"),
                                  ("@7", "2", "agent-b")])
        overlay, rows = self._populated(fake)
        self.assertEqual("@7", rows["agent-b"].window_id)
        # agent-a closes while the overlay is open; renumber-windows moves
        # agent-b from 2 to 1, and index 2 now names nothing (or a newcomer).
        fake.windows = [("@3", "0", "board"), ("@7", "1", "agent-b"),
                        ("@9", "2", "agent-c")]
        dismissed, notified = self._enter(overlay, rows["agent-b"], fake)
        self.assertEqual([["select-window", "-t", "=s1:@7"]], fake.selects())
        self.assertEqual(["agent-b"], dismissed)
        self.assertEqual([], notified)

    def test_a_closed_window_neither_teleports_nor_dismisses(self):
        for attached in ("s1", "s0"):            # same-session and cross-session
            with self.subTest(attached=attached):
                fake = _FakeSwitcherTmux([("@5", "1", "agent-a")])
                overlay, rows = self._populated(fake)
                fake.windows = []                # agent-a closed meanwhile
                dismissed, notified = self._enter(
                    overlay, rows["agent-a"], fake, attached=attached)
                self.assertEqual([["select-window", "-t", "=s1:@5"]], fake.selects())
                self.assertEqual([], [s for s in fake.spawns
                                      if s[0] == "switch-client"])
                self.assertEqual([], dismissed)
                self.assertEqual(1, len(notified))
                self.assertEqual("warning", notified[0][1].get("severity"))

    def test_a_live_cross_session_window_selects_then_teleports(self):
        fake = _FakeSwitcherTmux([("@5", "1", "agent-a")])
        overlay, rows = self._populated(fake)
        dismissed, _notified = self._enter(overlay, rows["agent-a"], fake,
                                           attached="s0")
        self.assertEqual([["select-window", "-t", "=s1:@5"]], fake.selects())
        self.assertEqual([["switch-client", "-t", "=s1"]],
                         [s for s in fake.spawns if s[0] == "switch-client"])
        self.assertEqual(["agent-a"], dismissed)

    def test_a_window_name_containing_markup_is_shown_literally(self):
        fake = _FakeSwitcherTmux([("@5", "1", "agent-[b]x")])
        overlay, rows = self._populated(fake)
        fake.windows = []
        _dismissed, notified = self._enter(overlay, rows["agent-[b]x"], fake)
        self.assertIn(ts._markup_literal("agent-[b]x"), notified[0][0][0])


class BindingTableTests(unittest.TestCase):

    def test_one_spawn_binding_on_shift_m(self):
        matches = [b for b in ts._QUICK_JUMP_BINDINGS
                   if b.action == "spawn_minimonitor"]
        self.assertEqual(1, len(matches))
        self.assertEqual("M", matches[0].key)

    def test_no_quick_jump_key_collides(self):
        keys = [b.key for b in ts._QUICK_JUMP_BINDINGS]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
