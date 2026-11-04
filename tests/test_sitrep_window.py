"""The sitrep window spawn and its one-per-root guard (t2175_4), through mocks.

`monitor_core.spawn_sitrep` is driven with `launch_window_pane`,
`maybe_spawn_minimonitor`, `resolve_dry_run_command` and
`switch_to_pane_anywhere` patched on `monitor_core` (where the body lives). The
duplicate lookup's parsing, the shared helper rule (`pane_is_helper`), the stamp
and the per-server lock are real. The fake gateway renders `list-panes` rows from
the REQUESTED `-F` format, so a field added to the format cannot shift a
neighbour's value into the wrong slot.

What only a live tmux server can answer — the window really created, the stamp
on it, two concurrent spawns, a linked worktree, a frozen pane beside its
companion — is `tests/test_sitrep_window_live.sh`.

Run: python3 -m unittest tests.test_sitrep_window
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_launch_utils as alu  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from tmux_socket_containment import TmuxSocketContainmentMixin  # noqa: E402

SITREP_SH = REPO_ROOT / ".aitask-scripts" / "aitask_sitrep.sh"

_SPEC_KEYS = {
    "#{pane_id}": "id",
    "#{pane_pid}": "pid",
    f"#{{{mc.SHADOW_TARGET_OPTION}}}": "shadow",
    f"#{{{mc.MONITOR_KIND_OPTION}}}": "kind",
    f"#{{{mc.FROZEN_OPTION}}}": "frozen",
    "#{pane_dead}": "dead",
    f"#{{{mc.SCRATCHPAD_TARGET_OPTION}}}": "scratch",
    f"#{{{mc.SITREP_ROOT_OPTION}}}": "stamp",
    "#{window_name}": "window",
    "#{pane_current_path}": "cwd",
}

#: A pid that is NOT a companion process (this test runner).
LIVE_PID = os.getpid()


def pane(pid=LIVE_PID, **kw) -> dict:
    row = {"pid": str(pid)}
    row.update(kw)
    return row


def render(fmt: str, panes: list[dict]) -> str:
    specs = fmt.split("\t")
    return "".join(
        "\t".join(str(p.get(_SPEC_KEYS.get(s, ""), "")) for s in specs) + "\n"
        for p in panes)


def canon_identity(path: str) -> str:
    return path


class FakeMon:
    """`monitor.tmux_run` over a scripted server."""

    def __init__(self, panes=(), *, list_rc=0, socket="", set_rc=0,
                 windows=("zsh",), window_rc=0):
        self.panes = list(panes)
        self.list_rc = list_rc
        self.socket = socket
        self.set_rc = set_rc
        self.windows = list(windows)
        self.window_rc = window_rc
        self.calls: list[list[str]] = []
        self.stamps: dict[tuple[str, str], str] = {}
        self.killed: list[str] = []

    def tmux_run(self, args, timeout=5.0):
        self.calls.append(list(args))
        verb = args[0]
        if verb == "list-panes":
            if self.list_rc != 0:
                return self.list_rc, ""
            return 0, render(args[args.index("-F") + 1], self.panes)
        if verb == "display-message":
            if args[-1] == "#{socket_path}":
                return 0, self.socket + "\n"
            # _probe_pane: the pane is live unless it was killed.
            target = args[args.index("-t") + 1]
            return 0, ("" if target in self.killed else target) + "\n"
        if verb == "list-windows":
            return self.window_rc, "\n".join(self.windows) + "\n"
        if verb == "set-option":
            if self.set_rc == 0:
                self.stamps[(args[3], args[4])] = args[5]
            return self.set_rc, ""
        if verb == "kill-pane":
            self.killed.append(args[args.index("-t") + 1])
            return 0, ""
        return 1, ""

    def verbs(self) -> list[str]:
        return [c[0] for c in self.calls]


class MatcherTests(unittest.TestCase):
    ROOT = "/repo"

    def match(self, panes, root=ROOT, canon=canon_identity):
        return mc.match_sitrep_pane(render(mc.SITREP_PANE_FORMAT, panes), root, canon)

    def test_stamp_for_the_root_matches(self):
        self.assertEqual(self.match([pane(id="%5", stamp=self.ROOT, window="w")]), "%5")

    def test_stamp_for_another_root_does_not(self):
        self.assertIsNone(self.match([pane(id="%5", stamp="/other", window="agent-sitrep",
                                           cwd=self.ROOT)]))

    def test_frozen_and_dead_panes_never_match(self):
        self.assertIsNone(self.match([pane(id="%5", stamp=self.ROOT, frozen="rec1")]))
        self.assertIsNone(self.match([pane(id="%5", stamp=self.ROOT, dead="1")]))

    def test_name_fallback(self):
        self.assertEqual(self.match([pane(id="%7", window="agent-sitrep", cwd=self.ROOT)]), "%7")
        self.assertEqual(self.match([pane(id="%7", window="agent-sitrep-3", cwd=self.ROOT)]), "%7")
        self.assertIsNone(self.match([pane(id="%7", window="agent-sitrep", cwd="/other")]))
        # canon maps a worktree path to its main root
        self.assertEqual(self.match([pane(id="%7", window="agent-sitrep", cwd="/repo/aiwork/t1")],
                                    canon=lambda p: "/repo"), "%7")

    def test_window_name_near_misses(self):
        for win in ("agent-sitrepx", "agent-pick-sitrep", "agent-sitrep-0", "sitrep"):
            self.assertIsNone(self.match([pane(id="%7", window=win, cwd=self.ROOT)]), win)

    def test_malformed_rows_are_skipped(self):
        out = "garbage\n%5\t1\n\n" + render(mc.SITREP_PANE_FORMAT,
                                             [pane(id="nope", stamp=self.ROOT),
                                              pane(id="%6", pid="x", stamp=self.ROOT)])
        self.assertIsNone(mc.match_sitrep_pane(out, self.ROOT, canon_identity))

    def test_cwd_with_a_tab_is_data(self):
        self.assertEqual(self.match([pane(id="%7", window="agent-sitrep", cwd="/re\tpo")],
                                    root="/re\tpo"), "%7")

    # --- the sitrep window's own companion -------------------------------------

    def test_frozen_sitrep_beside_its_live_companion_does_not_match(self):
        companion = pane(id="%9", kind=f"minimonitor:{LIVE_PID}", window="agent-sitrep",
                         cwd=self.ROOT)
        frozen_agent = pane(id="%8", stamp=self.ROOT, frozen="rec1", window="agent-sitrep",
                            cwd=self.ROOT)
        self.assertIsNone(self.match([companion, frozen_agent]))
        self.assertIsNone(self.match([frozen_agent, companion]))

    def test_booting_companion_without_a_marker_does_not_match(self):
        """No marker yet: the cmdline fallback of the shared rule classifies it."""
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)",
                                 "minimonitor"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        companion = pane(id="%9", pid=proc.pid, window="agent-sitrep", cwd=self.ROOT)
        self.assertIsNone(self.match([companion]))

    def test_live_stamped_sitrep_listed_after_its_companion(self):
        companion = pane(id="%9", kind=f"minimonitor:{LIVE_PID}", window="agent-sitrep",
                         cwd=self.ROOT)
        agent = pane(id="%8", stamp=self.ROOT, window="agent-sitrep", cwd=self.ROOT)
        self.assertEqual(self.match([companion, agent]), "%8")

    def test_bound_helpers_never_match(self):
        for kw in ({"shadow": "%1"}, {"scratch": "%1"}):
            self.assertIsNone(self.match([pane(id="%9", window="agent-sitrep", cwd=self.ROOT,
                                               **kw)]), kw)

    # --- stamp precedence (tells stamp-first from single-pass) -----------------

    def test_stamp_wins_over_an_earlier_fallback_candidate(self):
        candidate = pane(id="%3", window="agent-sitrep", cwd=self.ROOT)
        stamped = pane(id="%8", stamp=self.ROOT, window="agent-sitrep-2", cwd=self.ROOT)
        self.assertEqual(self.match([candidate, stamped]), "%8")
        self.assertEqual(self.match([stamped, candidate]), "%8")


class ClassifyParityTests(unittest.TestCase):
    """`classify_window_panes` keeps its verdicts after the `pane_is_helper` lift."""

    def test_classify_uses_the_shared_rule(self):
        out = render(mc.FROZEN_AWARE_PANE_FORMAT, [
            pane(id="%1"),
            pane(id="%2", shadow="%1"),
            pane(id="%3", kind=f"minimonitor:{LIVE_PID}"),
            pane(id="%4", shadow="%1", frozen="rec"),
            pane(id="%5", scratch="%1"),
        ])
        verdicts = {p.pane_id: p.is_helper for p in mc.classify_window_panes(out)}
        self.assertEqual(verdicts, {"%1": False, "%2": True, "%3": True, "%4": False,
                                    "%5": True})


class SpawnTests(TmuxSocketContainmentMixin, unittest.TestCase):
    CONTAINED_MODULES = (alu,)

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = self.tmp / "proj"            # not a git repo: canonical = itself
        self.root.mkdir()
        self.sock = str(self.tmp / "sock")
        self.launch = patch.object(mc, "launch_window_pane",
                                   return_value=("%42", 4242, None)).start()
        self.companion = patch.object(mc, "maybe_spawn_minimonitor",
                                      return_value="%43").start()
        self.cmd = patch.object(mc, "resolve_dry_run_command",
                                return_value="env AITASK_AGENT_STRING=x claude").start()
        self.focus = patch.object(mc, "switch_to_pane_anywhere", return_value=True).start()
        self.addCleanup(patch.stopall)

    def spawn(self, mon, **kw):
        kw.setdefault("select_window", True)
        return mc.spawn_sitrep(mon, target_root=self.root, session="s", **kw)

    def test_socket_containment_active(self):
        self.assert_contained()

    def test_spawn_launches_stamps_and_adds_the_companion(self):
        mon = FakeMon(socket=self.sock, windows=("zsh", "agent-sitrep"))
        res = self.spawn(mon)
        self.assertEqual(res.status, "spawned")
        self.assertEqual(res.pane, "%42")
        cfg = self.launch.call_args.args[1]
        self.assertEqual(cfg.window, "agent-sitrep-2")        # unique in the session
        self.assertTrue(cfg.new_window)
        self.assertEqual(cfg.cwd, str(self.root))
        self.assertEqual(mon.stamps[("%42", mc.SITREP_ROOT_OPTION)], str(self.root))
        self.assertEqual(self.cmd.call_args.args[1], "sitrep")
        kw = self.companion.call_args.kwargs
        self.assertEqual(self.companion.call_args.args, ("s", "agent-sitrep-2"))
        self.assertEqual(kw["agent_pane"], "%42")
        self.assertTrue(kw["explicit"])
        # Forced too: `companion_window_prefixes` / TUI-name filtering must not
        # drop the companion the sitrep window requires.
        self.assertTrue(kw["force_companion"])
        self.assertEqual(res.window, "s:agent-sitrep-2")
        self.assertEqual(res.detail, "")

    def test_lookup_failure_refuses_without_launching(self):
        res = self.spawn(FakeMon(socket=self.sock, list_rc=1))
        self.assertEqual((res.status, res.detail), ("refused", "lookup_failed"))
        self.launch.assert_not_called()
        self.companion.assert_not_called()

    def test_existing_sitrep_is_focused_not_relaunched(self):
        mon = FakeMon([pane(id="%5", stamp=str(self.root))], socket=self.sock)
        res = self.spawn(mon)
        self.assertEqual((res.status, res.pane), ("focused", "%5"))
        self.focus.assert_called_once_with("%5")
        self.launch.assert_not_called()

    def test_no_select_does_not_move_focus(self):
        mon = FakeMon([pane(id="%5", stamp=str(self.root))], socket=self.sock)
        self.focus.return_value = False      # never consulted without a switch
        self.assertEqual(self.spawn(mon, select_window=False).status, "focused")
        self.focus.assert_not_called()

    def test_a_failed_focus_is_reported_not_claimed(self):
        self.focus.return_value = False
        mon = FakeMon([pane(id="%5", stamp=str(self.root))], socket=self.sock)
        res = self.spawn(mon)
        self.assertEqual((res.status, res.pane, res.detail),
                         ("focus_failed", "%5", "focus_failed"))
        self.focus.assert_called_once_with("%5")
        self.launch.assert_not_called()

    def test_lock_not_held_refuses_before_the_lookup(self):
        fd = os.open(self.sock + mc._SITREP_LOCK_SUFFIX, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        mon = FakeMon(socket=self.sock)
        res = self.spawn(mon, lock_timeout=0.1)
        self.assertEqual((res.status, res.detail), ("refused", "lock_busy"))
        self.assertNotIn("list-panes", mon.verbs())
        self.launch.assert_not_called()

    def test_no_socket_path_fails_closed(self):
        res = self.spawn(FakeMon(socket=""))
        self.assertEqual(res.detail, "lock_busy")
        self.launch.assert_not_called()

    def test_stamp_failure_removes_the_pane_and_skips_the_companion(self):
        mon = FakeMon(socket=self.sock, set_rc=1)
        res = self.spawn(mon)
        self.assertEqual(res.status, "refused")
        self.assertEqual(res.detail, "stamp:removed")
        self.assertEqual(mon.killed, ["%42"])
        self.companion.assert_not_called()

    def test_no_command_refuses(self):
        self.cmd.return_value = None
        res = self.spawn(FakeMon(socket=self.sock))
        self.assertEqual(res.detail, "no_command")
        self.launch.assert_not_called()

    def test_launch_error_refuses(self):
        self.launch.return_value = (None, None, "tmux new-window failed (rc=1)")
        res = self.spawn(FakeMon(socket=self.sock))
        self.assertEqual(res.detail, "launch:tmux new-window failed (rc=1)")
        self.companion.assert_not_called()

    def test_companion_not_spawned_is_a_warning(self):
        self.companion.return_value = None
        res = self.spawn(FakeMon(socket=self.sock))
        self.assertEqual((res.status, res.detail), ("spawned", "companion_not_spawned"))

    def test_window_list_failure_refuses(self):
        res = self.spawn(FakeMon(socket=self.sock, window_rc=1))
        self.assertEqual(res.detail, "window_list_failed")
        self.launch.assert_not_called()

    def test_a_missing_root_is_refused(self):
        res = mc.spawn_sitrep(FakeMon(socket=self.sock), target_root=self.tmp / "gone",
                              session="s", select_window=True)
        self.assertEqual(res.status, "refused")
        self.assertTrue(res.detail.startswith("root:"), res.detail)


class CliTests(unittest.TestCase):
    def run_cli(self, *args, cwd=None, env=None):
        e = dict(os.environ)
        e.pop("TMUX", None)
        e.pop("TMUX_PANE", None)
        e.update(env or {})
        return subprocess.run(["bash", str(SITREP_SH), *args], cwd=cwd, env=e,
                              capture_output=True, text=True, timeout=60)

    def test_root_reports_cwd_ok_and_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            d = os.path.realpath(d)
            sub = os.path.join(d, "sub")
            os.mkdir(sub)
            r = self.run_cli("root", cwd=d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.splitlines(), [f"ROOT:{d}", "CWD_OK"])
            r = self.run_cli("root", "--root", d, cwd=sub)
            self.assertEqual(r.stdout.splitlines(), [f"ROOT:{d}", f"CWD_MISMATCH:{sub}"])

    def test_open_outside_tmux_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(cwd=d)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "SITREP_REFUSED:not_in_tmux")

    def test_bad_root_is_refused_in_every_spelling(self):
        """The parser is the one check: every spelling it accepts, every verb."""
        spellings = (["--root", "a/../b"], ["--root=a/../b"], ["--root", ""],
                     ["--root="], ["--root=.."], ["--roo", "a/../b"])
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "a"))
            os.makedirs(os.path.join(d, "b"))
            for verb in ("root", "triage", "open"):
                for spelling in spellings:
                    args = [verb] + (["c1"] if verb == "triage" else []) + spelling
                    r = self.run_cli(*args, cwd=d)
                    self.assertEqual(r.returncode, 2, args)
                    self.assertEqual(r.stdout, "", args)

    def test_option_abbreviations_are_not_accepted(self):
        """`--root P` / `--root=P` are the only spellings (documented), even for a
        valid path: an abbreviation is an unknown option."""
        with tempfile.TemporaryDirectory() as d:
            for verb in ("root", "triage", "open"):
                args = [verb] + (["c1"] if verb == "triage" else []) + ["--roo", d]
                r = self.run_cli(*args, cwd=d)
                self.assertEqual(r.returncode, 2, args)
                self.assertEqual(r.stdout, "", args)

    def test_a_good_root_in_the_equals_spelling_works(self):
        with tempfile.TemporaryDirectory() as d:
            d = os.path.realpath(d)
            r = self.run_cli("root", f"--root={d}", cwd=d)
        self.assertEqual(r.stdout.splitlines(), [f"ROOT:{d}", "CWD_OK"])

    def test_unknown_verb_is_usage(self):
        self.assertEqual(self.run_cli("frobnicate").returncode, 2)

    def test_triage_needs_an_id_or_open(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_cli("triage", cwd=d).returncode, 2)
            self.assertEqual(self.run_cli("triage", "c1", "--open", cwd=d).returncode, 2)
            r = self.run_cli("triage", "--open", cwd=d)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "NO_TRIAGE"))



class OpenCliTests(TmuxSocketContainmentMixin, unittest.TestCase):
    """`monitor/sitrep_open.py` turns each spawn outcome into its wire line."""
    CONTAINED_MODULES = (alu,)

    def setUp(self):
        super().setUp()
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sitrep_open_under_test",
            REPO_ROOT / ".aitask-scripts" / "monitor" / "sitrep_open.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        patch.dict(os.environ, {"TMUX": "/tmp/x,1,0", "TMUX_PANE": "%1"}).start()
        patch.object(self.mod, "pane_session", return_value="s").start()
        self.addCleanup(patch.stopall)

    def run_main(self, outcome, *argv):
        import contextlib
        import io
        patch.object(self.mod.monitor_core, "spawn_sitrep", return_value=outcome).start()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.mod.main(list(argv))
        return rc, buf.getvalue().strip()

    def test_focus_failed_exits_1(self):
        rc, out = self.run_main(mc.SitrepSpawn("focus_failed", "%5", "", "focus_failed"))
        self.assertEqual((rc, out), (1, "SITREP_FOCUS_FAILED:%5"))

    def test_focused_and_spawned(self):
        self.assertEqual(self.run_main(mc.SitrepSpawn("focused", "%5", "", "")),
                         (0, "SITREP_FOCUSED:%5"))
        self.assertEqual(self.run_main(mc.SitrepSpawn("spawned", "%6", "s:agent-sitrep",
                                                      "companion_not_spawned")),
                         (0, "SITREP_SPAWNED:%6|s:agent-sitrep\nSITREP_WARN:companion_not_spawned"))

    def test_refused(self):
        self.assertEqual(self.run_main(mc.SitrepSpawn("refused", None, "", "lookup_failed")),
                         (1, "SITREP_REFUSED:lookup_failed"))

    def test_no_select_reaches_the_spawn(self):
        spawn = patch.object(self.mod.monitor_core, "spawn_sitrep",
                             return_value=mc.SitrepSpawn("focused", "%5", "", "")).start()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.main(["--no-select"])
        self.assertFalse(spawn.call_args.kwargs["select_window"])

    # -- --session (t2175_5: the TUIs name the selected agent's session) ------

    def _session_run(self, has_session_rc, *argv):
        import contextlib
        import io
        asked = []

        def fake_run(_gw, args, timeout=5.0):
            asked.append(list(args))
            return has_session_rc, ""

        patch.object(self.mod._Gateway, "tmux_run", fake_run).start()
        spawn = patch.object(self.mod.monitor_core, "spawn_sitrep",
                             return_value=mc.SitrepSpawn("focused", "%5", "", "")
                             ).start()
        lookup = patch.object(self.mod, "pane_session", return_value="own").start()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.mod.main(list(argv))
        return rc, buf.getvalue().strip(), spawn, lookup, asked

    def test_a_named_session_reaches_the_spawn_instead_of_the_own_one(self):
        rc, out, spawn, lookup, asked = self._session_run(0, "--session", "other")
        self.assertEqual((rc, out), (0, "SITREP_FOCUSED:%5"))
        self.assertEqual(spawn.call_args.kwargs["session"], "other")
        self.assertEqual(asked, [["has-session", "-t", "=other"]],
                         "the named session must be checked by EXACT name")
        lookup.assert_not_called()

    def test_an_unknown_named_session_is_refused_and_nothing_spawns(self):
        rc, out, spawn, _lookup, _asked = self._session_run(1, "--session", "gone")
        self.assertEqual((rc, out), (1, "SITREP_REFUSED:no_session"))
        spawn.assert_not_called()

    def test_without_session_the_own_pane_session_is_used(self):
        rc, _out, spawn, lookup, asked = self._session_run(0)
        self.assertEqual(spawn.call_args.kwargs["session"], "own")
        self.assertEqual(asked, [])
        lookup.assert_called_once()

    def test_a_malformed_session_name_is_usage(self):
        import contextlib
        import io
        for bad in ("", "-x", "a:b", "a.b", "a\nb", "a\x7fb"):
            spawn = patch.object(self.mod.monitor_core, "spawn_sitrep").start()
            with self.subTest(bad=bad), \
                    contextlib.redirect_stderr(io.StringIO()), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as cm:
                    self.mod.main(["--session", bad])
                self.assertEqual(cm.exception.code, 2)
                self.assertEqual(out.getvalue(), "")
                spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
