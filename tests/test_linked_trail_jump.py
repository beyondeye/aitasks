"""The linked-trail jump (t1957_4): prepare / finish and the session helpers.

* **Prepare** (`board_trail_screen.prepare_linked_trail_jump`) — every check
  that can refuse a jump, the session lookup and the bootstrap, and the
  warnings the user must read BEFORE the client moves. It never launches and
  never switches: those are finish's, so a warning can still be confirmed.
* **Finish** (`finish_linked_trail_jump`) — re-checks the destination (the
  confirm dialog may have stayed open while the session stopped and its name
  was reused by another project), opens the trail, switches the client. It
  returns notices only on a path that did NOT switch: after a switch nobody is
  looking at the App that would show them.
* **Helpers** (`agent_launch_utils`) — `bootstrap_project_session` (shared with
  the TUI switcher), `live_project_session`, `session_owned_by`,
  `trails_supports_focus`, `switch_client_to`, against a stubbed gateway: no
  real tmux server is touched. The live counterpart is
  `tests/test_linked_trail_jump_live.sh`.

The jump names are patched on `board_trail_screen` (reached through the board
fixture as `ab.board_trail_screen`), the module whose namespace the jump reads.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_linked_trail_jump.py -q
"""

from __future__ import annotations

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
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils as alu  # noqa: E402
import board_fixture as bf  # noqa: E402

HANDLE = "art:trail-y"


def _make_project(parent: Path, name: str, default_session: str = "",
                  trails_flag: bool | None = True) -> Path:
    """An aitasks project root: the marker config, optionally a
    `tmux.default_session`, and optionally a `trails_app.py` with (or without)
    `--trail`."""
    root = parent / name
    (root / "aitasks" / "metadata").mkdir(parents=True)
    cfg = f"project:\n  name: {name}\n"
    if default_session:
        cfg += f"tmux:\n  default_session: {default_session}\n"
    (root / "aitasks" / "metadata" / "project_config.yaml").write_text(cfg)
    if trails_flag is not None:
        board = root / ".aitask-scripts" / "board"
        board.mkdir(parents=True)
        body = ('parser.add_argument("--trail")\n' if trails_flag
                else 'parser.add_argument("--tasks-dir")\n')
        (board / "trails_app.py").write_text(body)
    return root


class _JumpStubs:
    """Stand-ins for every helper the jump reads, recording calls in order."""

    def __init__(self, testcase, ts):
        self.calls: list[tuple] = []
        self.tmux_session = "x"
        self.live = ["ysess"]            # successive live_project_session answers
        self.boot = alu.BootstrapResult(True)
        self.owned = True
        self.launch = (True, None)
        self.switch = True
        for name in ("current_tmux_session", "live_project_session",
                     "bootstrap_project_session", "session_owned_by",
                     "launch_or_focus_trails", "switch_client_to"):
            p = patch.object(ts, name, getattr(self, "_" + name))
            p.start()
            testcase.addCleanup(p.stop)

    def names(self):
        return [c[0] for c in self.calls]

    def _current_tmux_session(self):
        self.calls.append(("current_tmux_session",))
        return self.tmux_session

    def _live_project_session(self, root):
        self.calls.append(("live_project_session", str(root)))
        return self.live.pop(0) if self.live else None

    def _bootstrap_project_session(self, root):
        self.calls.append(("bootstrap_project_session", str(root)))
        return self.boot

    def _session_owned_by(self, session, root):
        self.calls.append(("session_owned_by", session, str(root)))
        return self.owned

    def _launch_or_focus_trails(self, session, root, handle):
        self.calls.append(("launch_or_focus_trails", session, str(root), handle))
        return self.launch

    def _switch_client_to(self, session):
        self.calls.append(("switch_client_to", session))
        return self.switch


class _JumpTestBase(bf.FixtureBoardTestBase, unittest.TestCase):

    def setUp(self):
        self.ts = self.ab.board_trail_screen
        self.tmp = Path(tempfile.mkdtemp(prefix="ait_t1957_4_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = _make_project(self.tmp, "proj_y")
        self.link = SimpleNamespace(project="proj_y", root=str(self.root),
                                    handle=HANDLE, name="Y trail",
                                    reasons=("rev-member: aitasks#1",))
        self.stubs = _JumpStubs(self, self.ts)


class PrepareJumpTests(_JumpTestBase):

    def test_a_live_session_is_prepared_without_touching_the_client(self):
        jump = self.ts.prepare_linked_trail_jump(self.link)
        self.assertEqual((jump.error, jump.session, jump.launch, jump.warnings),
                         ("", "ysess", True, ()))
        self.assertEqual(self.stubs.names(),
                         ["current_tmux_session", "live_project_session"])

    def test_no_session_bootstraps_then_looks_it_up_again(self):
        self.stubs.live = [None, "ysess"]
        jump = self.ts.prepare_linked_trail_jump(self.link)
        self.assertEqual((jump.error, jump.session, jump.warnings),
                         ("", "ysess", ()))
        self.assertEqual(self.stubs.names(),
                         ["current_tmux_session", "live_project_session",
                          "bootstrap_project_session", "live_project_session"])
        self.assertEqual(self.stubs.calls[2][1], str(self.root))

    def test_a_bootstrap_failure_is_terminal(self):
        self.stubs.live = [None]
        self.stubs.boot = alu.BootstrapResult(False, error="tmux exploded")
        jump = self.ts.prepare_linked_trail_jump(self.link)
        self.assertIn("Could not start a tmux session for proj_y", jump.error)
        self.assertIn("tmux exploded", jump.error)
        self.assertNotIn("launch_or_focus_trails", self.stubs.names())
        self.assertNotIn("switch_client_to", self.stubs.names())

    def test_a_bootstrapped_session_that_cannot_be_found_is_terminal(self):
        self.stubs.live = [None, None]
        jump = self.ts.prepare_linked_trail_jump(self.link)
        self.assertIn("could not find it", jump.error)
        self.assertEqual(jump.session, "")

    def test_a_fallback_session_name_is_a_one_time_notice(self):
        """An event of THIS prepare (it started the session), not a property of
        the target: a `notice`, carried across a pause, never a `warning`."""
        self.stubs.live = [None, "aitasks"]
        self.stubs.boot = alu.BootstrapResult(
            True, default_session_problem="block_scalar")
        jump = self.ts.prepare_linked_trail_jump(self.link)
        self.assertEqual((jump.error, jump.warnings), ("", ()))
        self.assertEqual(len(jump.notices), 1)
        for part in ("proj_y", "block_scalar", "'aitasks'"):
            self.assertIn(part, jump.notices[0])
        self.assertEqual(jump.to_confirm, jump.notices)

    def test_outside_the_gateway_only_the_manual_command_is_returned(self):
        self.stubs.tmux_session = None
        jump = self.ts.prepare_linked_trail_jump(self.link)
        self.assertIn(f"ait projects exec proj_y -- ./ait trails --trail {HANDLE}",
                      jump.error)
        self.assertEqual(self.stubs.names(), ["current_tmux_session"])

    def test_the_manual_command_survives_shell_parsing(self):
        """A registry name may hold spaces; the displayed command must parse
        back to exactly that project and handle."""
        self.stubs.tmux_session = None
        self.link.project = "my project"
        jump = self.ts.prepare_linked_trail_jump(self.link)
        command = jump.error.split("open the trail with: ", 1)[1]
        self.assertEqual(shlex.split(command), [
            "ait", "projects", "exec", "my project", "--",
            "./ait", "trails", "--trail", HANDLE])

    def test_an_older_target_skips_the_launch_and_warns(self):
        _make_project(self.tmp, "proj_old", trails_flag=False)
        self.link.root = str(self.tmp / "proj_old")
        jump = self.ts.prepare_linked_trail_jump(self.link)
        self.assertEqual((jump.error, jump.launch), ("", False))
        self.assertEqual(len(jump.warnings), 1)
        self.assertIn("ait upgrade", jump.warnings[0])
        self.assertIn(HANDLE, jump.warnings[0])

    def test_a_root_that_lost_its_marker_is_refused_before_any_tmux_call(self):
        (self.root / "aitasks" / "metadata" / "project_config.yaml").unlink()
        jump = self.ts.prepare_linked_trail_jump(self.link)
        self.assertIn("no longer an aitasks project", jump.error)
        self.assertEqual(self.stubs.names(), ["current_tmux_session"])


class FinishJumpTests(_JumpTestBase):

    def _jump(self, **kw):
        return self.ts.TrailJump(self.link, **{"session": "ysess",
                                               "launch": True, **kw})

    def test_a_clean_jump_returns_no_notice(self):
        """The invariant: a successful switch says nothing, because the App
        that would say it is no longer on screen."""
        self.assertEqual(self.ts.finish_linked_trail_jump(self._jump()), [])
        self.assertEqual(self.stubs.calls, [
            ("session_owned_by", "ysess", str(self.root)),
            ("launch_or_focus_trails", "ysess", str(self.root), HANDLE),
            ("switch_client_to", "ysess"),
        ])

    def test_without_launch_support_it_only_switches(self):
        self.assertEqual(
            self.ts.finish_linked_trail_jump(self._jump(launch=False)), [])
        self.assertEqual(self.stubs.names(),
                         ["session_owned_by", "switch_client_to"])

    def test_a_launch_failure_does_not_switch(self):
        self.stubs.launch = (False, "tmux new-window failed")
        notices = self.ts.finish_linked_trail_jump(self._jump())
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][1], "error")
        self.assertIn("tmux new-window failed", notices[0][0])
        self.assertNotIn("switch_client_to", self.stubs.names())

    def test_a_switch_failure_names_the_manual_command(self):
        self.stubs.switch = False
        self.link.project = "my project"
        notices = self.ts.finish_linked_trail_jump(self._jump())
        self.assertEqual(len(notices), 1)
        self.assertIn("Could not switch to tmux session 'ysess'", notices[0][0])
        command = notices[0][0].split(" — ", 1)[1]
        self.assertEqual(shlex.split(command)[3], "my project")

    def test_a_session_no_longer_owned_by_the_target_is_refused(self):
        """Stopped and its name reused by another project while a dialog was
        open: neither the trail nor the client may go there."""
        self.stubs.owned = False
        notices = self.ts.finish_linked_trail_jump(self._jump())
        self.assertEqual(len(notices), 1)
        self.assertIn("changed before the jump", notices[0][0])
        self.assertEqual(self.stubs.names(), ["session_owned_by"])

    def test_a_root_that_lost_its_marker_is_refused_before_any_tmux_call(self):
        (self.root / "aitasks" / "metadata" / "project_config.yaml").unlink()
        notices = self.ts.finish_linked_trail_jump(self._jump())
        self.assertIn("changed before the jump", notices[0][0])
        self.assertEqual(self.stubs.calls, [])


# --- agent_launch_utils helpers ---------------------------------------------------


class _Gateway:
    """A stubbed `_TMUX.run`: records argv; answers from `respond(args)`."""

    def __init__(self, testcase, respond):
        self.calls: list[list[str]] = []
        self.respond = respond
        p = patch.object(alu._TMUX, "run", self.run)
        p.start()
        testcase.addCleanup(p.stop)

    def run(self, args, timeout=5.0):
        self.calls.append(list(args))
        return self.respond(list(args))


class BootstrapProjectSessionTests(unittest.TestCase):

    def _run(self, *, rc=0, stderr="", raises=None):
        calls = []

        def fake_run(argv, *a, **k):
            calls.append(argv)
            if raises is not None:
                raise raises
            return subprocess.CompletedProcess(argv, rc, stdout="", stderr=stderr)

        with patch.object(subprocess, "run", side_effect=fake_run):
            result = alu.bootstrap_project_session(Path("/p/proj_y"))
        return result, calls

    def test_success_runs_the_standalone_bootstrap(self):
        result, calls = self._run()
        self.assertEqual(result, alu.BootstrapResult(True))
        self.assertEqual(calls[0][0], "bash")
        self.assertTrue(calls[0][1].endswith("lib/tmux_bootstrap.sh"), calls)
        self.assertEqual(calls[0][2], "/p/proj_y")

    def test_success_under_a_fallback_name_reports_the_shape(self):
        sentinel = (f"{alu.DEFAULT_SESSION_UNREADABLE_SENTINEL}block_scalar:"
                    "/p/proj_y/aitasks/metadata/project_config.yaml\n")
        result, _ = self._run(stderr=sentinel)
        self.assertTrue(result.ok)
        self.assertEqual(result.default_session_problem, "block_scalar")

    def test_a_failure_keeps_the_last_stderr_line(self):
        result, _ = self._run(rc=4, stderr="first\nnew-session failed\n")
        self.assertEqual((result.ok, result.error, result.stale),
                         (False, "new-session failed", False))

    def test_a_stale_path_is_flagged(self):
        result, _ = self._run(
            rc=42, stderr="BOOTSTRAP_FAILED:stale_path:/p/proj_y\nnot a project\n")
        self.assertEqual((result.ok, result.stale, result.error),
                         (False, True, "not a project"))

    def test_a_silent_failure_says_unknown_error(self):
        result, _ = self._run(rc=1)
        self.assertEqual(result.error, "unknown error")

    def test_a_spawn_error_is_a_failure_not_an_exception(self):
        result, _ = self._run(raises=subprocess.TimeoutExpired(["bash"], 15))
        self.assertFalse(result.ok)
        self.assertIn("timed out", result.error)


class SessionLookupTests(unittest.TestCase):
    """`live_project_session` / `session_owned_by` over the canonical
    attribution rule: a session's registration stamp, else its pane vote."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ait_t1957_4_sess_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.y = _make_project(self.tmp, "proj_y", default_session="ydef")
        self.z = _make_project(self.tmp, "proj_z")
        self.sessions: list[tuple[str, str]] = []    # (name, stamp)
        self.panes: dict[str, list[str]] = {}
        self.gw = _Gateway(self, self._respond)

    def _respond(self, args):
        if args[0] == "list-sessions":
            return 0, "".join(f"{n}\t{s}\n" for n, s in self.sessions)
        if args[0] == "list-panes":
            session = args[args.index("-t") + 1].lstrip("=").rstrip(":")
            return 0, "".join(f"{p}\n" for p in self.panes.get(session, []))
        return 1, ""                     # show-environment: no legacy entry

    def test_the_stamped_default_session(self):
        self.sessions = [("ydef", str(self.y))]
        self.assertEqual(alu.live_project_session(self.y), "ydef")

    def test_a_session_under_another_name(self):
        self.sessions = [("custom", str(self.y))]
        self.assertEqual(alu.live_project_session(self.y), "custom")

    def test_the_default_wins_over_the_first_by_name(self):
        self.sessions = [("aaa", str(self.y)), ("ydef", str(self.y))]
        self.assertEqual(alu.live_project_session(self.y), "ydef")

    def test_another_projects_session_is_not_ours(self):
        self.sessions = [("ydef", str(self.z))]
        self.assertIsNone(alu.live_project_session(self.y))

    def test_an_unstamped_session_is_attributed_by_its_panes(self):
        self.sessions = [("legacy", "")]
        self.panes = {"legacy": [str(self.y / "aitasks"), str(self.y)]}
        self.assertEqual(alu.live_project_session(self.y), "legacy")

    def test_session_owned_by(self):
        self.sessions = [("ydef", str(self.y)), ("zs", str(self.z))]
        self.assertTrue(alu.session_owned_by("ydef", self.y))
        self.assertFalse(alu.session_owned_by("zs", self.y))
        self.assertFalse(alu.session_owned_by("gone", self.y))

    def test_session_owned_by_an_empty_name_asks_nothing(self):
        self.assertFalse(alu.session_owned_by("", self.y))
        self.assertEqual(self.gw.calls, [])


class TrailsSupportAndSwitchTests(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ait_t1957_4_misc_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_trails_supports_focus(self):
        self.assertTrue(alu.trails_supports_focus(
            _make_project(self.tmp, "new", trails_flag=True)))
        self.assertFalse(alu.trails_supports_focus(
            _make_project(self.tmp, "old", trails_flag=False)))
        self.assertFalse(alu.trails_supports_focus(
            _make_project(self.tmp, "none", trails_flag=None)))

    def test_switch_client_to(self):
        answers = [(0, ""), (1, "")]
        gw = _Gateway(self, lambda args: answers.pop(0))
        self.assertTrue(alu.switch_client_to("ysess"))
        self.assertFalse(alu.switch_client_to("ysess"))
        self.assertEqual(gw.calls[0], ["switch-client", "-t", "=ysess"])


if __name__ == "__main__":
    unittest.main()
