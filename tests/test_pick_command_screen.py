"""The shared pick-launch pieces (t1946).

* `agent_command_screen.build_pick_screen` — the one `/aitask-pick <N>` dialog
  construction used by the board, `ait trails`, monitor and minimonitor. Pinned
  as a golden: the construction every caller got before the dedupe, with
  `narrow` passed only when set.
* `agent_launch_utils.current_tmux_session` — the caller's session on the
  GATEWAY server, trusted only when the caller is verifiably a pane of that
  server (`$TMUX_PANE`-targeted, `#{socket_path}` compared with `$TMUX`).
* `agent_launch_utils.focus_existing_agent_window` — switch to a running
  `agent-pick-<id>` / `agent-resume-<id>` window instead of launching a
  duplicate; never in an unrelated session.

The probe is tested for real, not mocked: `LiveTwoServerTests` runs two private
tmux servers whose pane ids collide (`%0` on both) and whose task numbers
overlap, and asserts that a caller on the other server can neither resolve a
gateway session nor select another project's `agent-pick-42`.

Run: python3 tests/test_pick_command_screen.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_command_screen as acs  # noqa: E402
import agent_launch_utils as alu  # noqa: E402
from tmux_exec import TmuxClient  # noqa: E402

_ROOT = Path("/proj/alpha")


class _Seams:
    """Stubs the builder's four reaches and records every call."""

    def __init__(self, testcase, full_cmd="cmd --go"):
        self.constructed: list[tuple] = []
        self.argv: list[tuple] = []
        self.agent: list[tuple] = []
        self.profile: list[tuple] = []
        seams = self

        class _FakeScreen:
            def __init__(self, *a, **k):
                seams.constructed.append((a, k))

        def _argv(root, task_id, agent_string=None):
            self.argv.append((root, task_id, agent_string))
            return full_cmd, f"agent-pick-{task_id}"

        def _agent(root, op):
            self.agent.append((root, op))
            return "claudecode/x"

        def _profile(skill, root="."):
            self.profile.append((skill, root))
            return "fast"

        for name, stub in (("pick_launch_argv", _argv),
                           ("resolve_agent_string", _agent),
                           ("resolve_skill_profile", _profile),
                           ("AgentCommandScreen", _FakeScreen)):
            p = patch.object(acs, name, stub)
            p.start()
            testcase.addCleanup(p.stop)


class BuildPickScreenTests(unittest.TestCase):

    GOLDEN_ARGS = ("Pick Task t123_5", "cmd --go", "/aitask-pick 123_5")
    GOLDEN_KWARGS = {
        "default_window_name": "agent-pick-123_5",
        "project_root": _ROOT,
        "operation": "pick",
        "operation_args": ["123_5"],
        "default_agent_string": "claudecode/x",
        "skill_name": "pick",
        "default_profile": "fast",
    }

    def test_construction_without_narrow_carries_no_narrow_key(self):
        seams = _Seams(self)
        self.assertIsNotNone(acs.build_pick_screen(_ROOT, "123_5"))
        self.assertEqual(seams.constructed,
                         [(self.GOLDEN_ARGS, self.GOLDEN_KWARGS)])
        self.assertEqual(seams.agent, [(_ROOT, "pick")])
        self.assertEqual(seams.profile, [("pick", _ROOT)])

    def test_narrow_variant_adds_exactly_narrow_true(self):
        seams = _Seams(self)
        acs.build_pick_screen(_ROOT, "123_5", narrow=True)
        self.assertEqual(seams.constructed,
                         [(self.GOLDEN_ARGS, {**self.GOLDEN_KWARGS, "narrow": True})])

    def test_configured_agent_is_resolved_never_a_record(self):
        """`pick_launch_argv`'s agent_string=None contract
        (tests/test_pick_launch_argv.py) survives the builder."""
        seams = _Seams(self)
        acs.build_pick_screen(_ROOT, "123_5")
        self.assertEqual(seams.argv, [(_ROOT, "123_5", None)])

    def test_unresolved_command_builds_nothing(self):
        seams = _Seams(self, full_cmd=None)
        self.assertIsNone(acs.build_pick_screen(_ROOT, "123_5"))
        self.assertEqual(seams.constructed, [])
        self.assertEqual(seams.agent, [])
        self.assertEqual(seams.profile, [])

    def test_real_screen_is_returned_unstubbed(self):
        """Negative control on the stubbing: the real class comes back."""
        with patch.object(acs, "pick_launch_argv",
                          lambda root, tid, agent_string=None: ("c", f"agent-pick-{tid}")), \
                patch.object(acs, "resolve_agent_string", lambda r, o: None), \
                patch.object(acs, "resolve_skill_profile", lambda s, r=".": "fast"):
            screen = acs.build_pick_screen(_ROOT, "7")
        self.assertIsInstance(screen, acs.AgentCommandScreen)
        self.assertEqual(screen.full_command, "c")
        self.assertEqual(screen.operation_args, ["7"])


class CurrentTmuxSessionTests(unittest.TestCase):
    """The real probe with only the gateway call stubbed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t1946_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sock = self.tmp / "ait"
        self.sock.write_text("")
        self.calls: list[list[str]] = []
        self.answer = (0, f"{self.sock}\tprojA\n")

        def _run(args, timeout=5.0):
            self.calls.append(list(args))
            return self.answer

        p = patch.object(alu._TMUX, "run", _run)
        p.start()
        self.addCleanup(p.stop)

    def _env(self, tmux=None, pane="%3"):
        values = {}
        if tmux is not None:
            values["TMUX"] = tmux
        if pane is not None:
            values["TMUX_PANE"] = pane
        ctx = patch.dict(os.environ, values, clear=False)
        ctx.start()
        self.addCleanup(ctx.stop)
        for var in ("TMUX", "TMUX_PANE"):
            if var not in values:
                os.environ.pop(var, None)

    def test_outside_tmux_is_none_without_probing(self):
        self._env(tmux=None, pane=None)
        self.assertIsNone(alu.current_tmux_session())
        self.assertEqual(self.calls, [])

    def test_missing_pane_is_none_without_probing(self):
        self._env(tmux=f"{self.sock},1,0", pane=None)
        self.assertIsNone(alu.current_tmux_session())
        self.assertEqual(self.calls, [])

    def test_probe_targets_the_callers_own_pane(self):
        self._env(tmux=f"{self.sock},1,0", pane="%3")
        self.assertEqual(alu.current_tmux_session(), "projA")
        self.assertEqual(self.calls, [[
            "display-message", "-p", "-t", "%3",
            "#{socket_path}\t#{session_name}"]])

    def test_same_socket_through_a_symlink_matches(self):
        link = self.tmp / "link"
        link.symlink_to(self.tmp, target_is_directory=True)
        self._env(tmux=f"{link / 'ait'},1,0")
        self.assertEqual(alu.current_tmux_session(), "projA")

    def test_a_different_server_is_rejected(self):
        self._env(tmux=f"{self.tmp / 'other'},1,0")
        self.assertIsNone(alu.current_tmux_session())

    def test_failed_or_empty_answers_are_none(self):
        self._env(tmux=f"{self.sock},1,0")
        for answer in ((1, ""), (-1, ""), (0, ""), (0, f"{self.sock}\t\n")):
            with self.subTest(answer=answer):
                self.answer = answer
                self.assertIsNone(alu.current_tmux_session())


class FocusExistingAgentWindowTests(unittest.TestCase):
    """`current_tmux_session` is NOT mocked: the gateway answer is. Session
    ownership comes from a stubbed `discover_aitasks_sessions`."""

    def setUp(self):
        self.selects: list[list[str]] = []
        self.searched: list[tuple[str, str]] = []
        self.windows: dict[tuple[str, str], tuple[str, str]] = {}
        self.probe = (0, "/sock/ait\tprojA\n")
        # Both candidate sessions are project alpha's unless a test says not.
        self.discovered = [
            alu.AitasksSession(session="projA", project_root=_ROOT,
                               project_name="alpha"),
            alu.AitasksSession(session="configured", project_root=_ROOT,
                               project_name="alpha")]

        def _run(args, timeout=5.0):
            if args[0] == "display-message":
                return self.probe
            self.selects.append(list(args))
            return (0, "")

        def _find(name, session):
            self.searched.append((name, session))
            return self.windows.get((name, session))

        for target, attr, value in (
                (alu._TMUX, "run", _run),
                (alu, "find_window_by_name", _find),
                (alu, "discover_aitasks_sessions", lambda: self.discovered),
                (alu, "load_tmux_defaults",
                 lambda root: {"default_session": "configured"})):
            p = patch.object(target, attr, value)
            p.start()
            self.addCleanup(p.stop)
        env = patch.dict(os.environ,
                         {"TMUX": "/sock/ait,1,0", "TMUX_PANE": "%3"})
        env.start()
        self.addCleanup(env.stop)

    def test_pick_window_wins_and_is_selected_through_the_gateway(self):
        self.windows[("agent-pick-42", "projA")] = ("projA", "2")
        self.windows[("agent-resume-42", "projA")] = ("projA", "5")
        self.assertTrue(alu.focus_existing_agent_window("42", _ROOT))
        self.assertEqual(self.selects, [["select-window", "-t", "=projA:2"]])

    def test_resume_window_is_found_too(self):
        self.windows[("agent-resume-42", "projA")] = ("projA", "5")
        self.assertTrue(alu.focus_existing_agent_window("42", _ROOT))
        self.assertEqual(self.selects, [["select-window", "-t", "=projA:5"]])

    def test_no_window_is_false_and_selects_nothing(self):
        self.assertFalse(alu.focus_existing_agent_window("42", _ROOT))
        self.assertEqual(self.selects, [])
        self.assertEqual(self.searched, [("agent-pick-42", "projA"),
                                         ("agent-resume-42", "projA")])

    def test_session_of_another_project_searches_only_the_configured_session(self):
        """Same server, verified pane, but discovery roots the session in a
        different project: its same-numbered window must stay untouched."""
        self.probe = (0, "/sock/ait\tprojB\n")
        self.discovered = [
            alu.AitasksSession(session="projB", project_root=Path("/proj/beta"),
                               project_name="beta"),
            alu.AitasksSession(session="configured", project_root=_ROOT,
                               project_name="alpha")]
        self.windows[("agent-pick-42", "projB")] = ("projB", "1")
        self.assertFalse(alu.focus_existing_agent_window("42", _ROOT))
        self.assertEqual({s for _, s in self.searched}, {"configured"})
        self.assertEqual(self.selects, [])

    def test_unattributed_session_searches_only_the_configured_session(self):
        self.discovered = [alu.AitasksSession(
            session="configured", project_root=_ROOT, project_name="alpha")]
        self.windows[("agent-pick-42", "projA")] = ("projA", "2")
        self.assertFalse(alu.focus_existing_agent_window("42", _ROOT))
        self.assertEqual({s for _, s in self.searched}, {"configured"})

    def test_configured_session_of_another_project_is_never_searched(self):
        """`default_session` is a NAME (every project defaults to `aitasks`):
        when discovery roots it elsewhere and the caller's session is not ours
        either, nothing is searched and the caller launches."""
        self.probe = (0, "/elsewhere/sock\tprojB\n")
        self.discovered = [alu.AitasksSession(
            session="configured", project_root=Path("/proj/beta"),
            project_name="beta")]
        self.windows[("agent-pick-42", "configured")] = ("configured", "1")
        self.assertFalse(alu.focus_existing_agent_window("42", _ROOT))
        self.assertEqual((self.searched, self.selects), ([], []))

    def test_unverified_caller_searches_only_the_configured_session(self):
        """A caller on another server must not search the gateway's answer —
        `projB` holds a same-numbered window that must stay untouched."""
        self.probe = (0, "/elsewhere/sock\tprojB\n")
        self.windows[("agent-pick-42", "projB")] = ("projB", "1")
        self.assertFalse(alu.focus_existing_agent_window("42", _ROOT))
        self.assertEqual({s for _, s in self.searched}, {"configured"})
        self.assertEqual(self.selects, [])


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class LiveTwoServerTests(unittest.TestCase):
    """Two private servers: the gateway (projB with `agent-pick-42`, projA the
    configured default) and another server the caller sits on. Every fixture
    command names its socket with `-S`, so nothing reaches a live server."""

    GW = "t1946gw"

    def setUp(self):
        # Short path: unix socket paths are length-limited.
        self.tmp = tempfile.mkdtemp(prefix="t1946_", dir="/tmp")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = patch.dict(os.environ, {"TMUX_TMPDIR": self.tmp,
                                      "AITASKS_TMUX_SOCKET": self.GW})
        env.start()
        self.addCleanup(env.stop)
        # `-L` resolves to $TMUX_TMPDIR/tmux-<uid>/<name>; `-S` does not create
        # that directory, and tmux wants it private.
        sockdir = Path(self.tmp) / f"tmux-{os.getuid()}"
        sockdir.mkdir(mode=0o700)
        self.gw_sock = str(sockdir / self.GW)
        self.other_sock = str(sockdir / "t1946ot")
        # The gateway singleton was built at import time; rebuild it onto the
        # private socket (tests/lib/tmux_socket_containment.py's rule).
        saved = alu._TMUX
        alu._TMUX = TmuxClient()
        self.addCleanup(setattr, alu, "_TMUX", saved)
        self.assertEqual(alu._TMUX.socket_args, ["-L", self.GW])
        for sock in (self.gw_sock, self.other_sock):
            self.addCleanup(self._tmux, sock, "kill-server", check=False)

        # Two real project roots; each session's panes sit in its own root, so
        # discovery attributes it by pane vote (no registration stamp needed).
        self.root_a = self._project("alpha")
        self.root_b = self._project("beta")
        self.projb_pane = self._tmux(self.gw_sock, "new-session", "-d", "-s", "projB",
                                     "-c", str(self.root_b), "-n", "main",
                                     "-P", "-F", "#{pane_id}", "sleep 600")
        self._tmux(self.gw_sock, "new-window", "-d", "-t", "=projB:", "-c",
                   str(self.root_b), "-n", "agent-pick-42", "sleep 600")
        self.proja_pane = self._tmux(self.gw_sock, "new-session", "-d", "-s", "projA",
                                     "-c", str(self.root_a), "-n", "main",
                                     "-P", "-F", "#{pane_id}", "sleep 600")
        self.other_pane = self._tmux(self.other_sock, "new-session", "-d", "-s",
                                     "elsewhere", "-P", "-F", "#{pane_id}", "sleep 600")

    def _project(self, name):
        root = Path(self.tmp) / name
        (root / "aitasks" / "metadata").mkdir(parents=True)
        (root / "aitasks" / "metadata" / "project_config.yaml").write_text("{}\n")
        return root

    def _tmux(self, sock, *args, check=True):
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        proc = subprocess.run(["tmux", "-S", sock, *args], capture_output=True,
                              text=True, env=env, timeout=10)
        if check and proc.returncode != 0:
            self.fail(f"tmux {args}: {proc.stderr}")
        return proc.stdout.strip()

    def _caller(self, sock, pane):
        ctx = patch.dict(os.environ, {"TMUX": f"{sock},{os.getpid()},0",
                                      "TMUX_PANE": pane})
        ctx.start()
        self.addCleanup(ctx.stop)

    def _defaults(self, session):
        p = patch.object(alu, "load_tmux_defaults",
                         lambda root: {"default_session": session})
        p.start()
        self.addCleanup(p.stop)

    def _active_window(self, session):
        return self._tmux(self.gw_sock, "display-message", "-p", "-t",
                          f"={session}:", "#{window_name}")

    def test_caller_on_another_server_never_selects_another_projects_window(self):
        # The trap is real: the caller's pane id names projB's pane on the
        # gateway, so a pane-targeted probe WITHOUT the socket check would
        # answer projB.
        self.assertEqual(self.other_pane, self.projb_pane)
        self.assertEqual(self._tmux(self.gw_sock, "display-message", "-p", "-t",
                                    self.other_pane, "#{session_name}"), "projB")
        self._caller(self.other_sock, self.other_pane)
        self._defaults("projA")
        self.assertIsNone(alu.current_tmux_session())
        self.assertFalse(alu.focus_existing_agent_window("42", self.root_a))
        self.assertEqual(self._active_window("projB"), "main")

    def test_caller_on_the_gateway_resolves_its_own_session(self):
        """Positive control: a verified caller searches its own session (not
        the configured default) and the window really becomes active."""
        self._tmux(self.gw_sock, "new-window", "-d", "-t", "=projA:", "-c",
                   str(self.root_a), "-n", "agent-pick-42", "sleep 600")
        self._caller(self.gw_sock, self.proja_pane)
        self._defaults("no-such-session")
        self.assertEqual(alu.current_tmux_session(), "projA")
        self.assertTrue(alu.focus_existing_agent_window("42", self.root_a))
        self.assertEqual(self._active_window("projA"), "agent-pick-42")
        self.assertEqual(self._active_window("projB"), "main")

    def test_caller_in_another_projects_session_on_the_same_server(self):
        """Same server, verified pane — but the session is project B's. Project
        A's lookup must use A's configured session, never B's same-numbered
        `agent-pick-42` (which would suppress A's launch)."""
        self._caller(self.gw_sock, self.projb_pane)
        self._defaults("projA")
        self.assertEqual(alu.current_tmux_session(), "projB")
        self.assertFalse(alu.focus_existing_agent_window("42", self.root_a))
        self.assertEqual(self._active_window("projB"), "main")


    def test_configured_session_of_another_project_is_not_searched(self):
        """Every project defaults to `default_session: aitasks`, so the
        configured fallback can name ANOTHER project's session too. Here the
        `aitasks` session is project B's (and holds its `agent-pick-42`): the
        caller is rejected for project A, and so must the fallback be."""
        pane = self._tmux(self.gw_sock, "new-session", "-d", "-s", "aitasks",
                          "-c", str(self.root_b), "-n", "main",
                          "-P", "-F", "#{pane_id}", "sleep 600")
        self._tmux(self.gw_sock, "new-window", "-d", "-t", "=aitasks:", "-c",
                   str(self.root_b), "-n", "agent-pick-42", "sleep 600")
        self._caller(self.gw_sock, pane)
        self._defaults("aitasks")
        self.assertEqual(alu.current_tmux_session(), "aitasks")
        self.assertFalse(alu.focus_existing_agent_window("42", self.root_a))
        self.assertEqual(self._active_window("aitasks"), "main")


if __name__ == "__main__":
    unittest.main()
