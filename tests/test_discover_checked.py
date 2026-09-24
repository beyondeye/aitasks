"""`discover_aitasks_sessions_checked()` — discovery that says whether it saw
everything (t1869).

The default discovery folds every tmux failure into emptiness. The checked
variant runs the SAME walk (`_collect_live_roots`) but reports
``complete=False`` whenever a query failed for a reason that is not a definite
"nothing there". These cases pin each per-command disposition, and in
particular that a failed query is distinct from an empty server.

Run: python3 tests/test_discover_checked.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

import agent_launch_utils  # noqa: E402
from tmux_exec import TmuxResult  # noqa: E402

OK = "ok"


class _FakeTmux:
    """Scripted `run_checked` answers keyed by the tmux subcommand."""

    def __init__(self, sessions=None, panes=None, env=None, list_sessions=None):
        self.list_sessions = list_sessions
        self.sessions = sessions or []
        self.panes = panes or {}     # session -> TmuxResult | list[str]
        self.env = env or {}         # session -> TmuxResult
        self.pane_targets = []

    def run_checked(self, args, timeout=5.0):
        cmd = args[0]
        if cmd == "list-sessions":
            if self.list_sessions is not None:
                return self.list_sessions
            return TmuxResult(OK, 0, "".join(s + "\n" for s in self.sessions), "")
        if cmd == "list-panes":
            target = args[args.index("-t") + 1]
            self.pane_targets.append(target)
            session = target.lstrip("=").rstrip(":")
            v = self.panes.get(session, [])
            if isinstance(v, TmuxResult):
                return v
            return TmuxResult(OK, 0, "".join(p + "\n" for p in v), "")
        if cmd == "show-environment":
            session = args[-1].replace("AITASKS_PROJECT_", "")
            return self.env.get(
                session, TmuxResult("failed", 1, "", f"unknown variable: {args[-1]}\n"))
        raise AssertionError(f"unexpected tmux call {args}")


def _project(tmp: Path, name: str) -> Path:
    root = tmp / name
    (root / "aitasks" / "metadata").mkdir(parents=True)
    (root / "aitasks" / "metadata" / "project_config.yaml").write_text("x: 1\n")
    return root


class CheckedDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.proj = _project(self.tmp, "alpha")
        self._saved = agent_launch_utils._TMUX

    def tearDown(self):
        agent_launch_utils._TMUX = self._saved
        self._td.cleanup()

    def _run(self, fake):
        agent_launch_utils._TMUX = fake
        return agent_launch_utils.discover_aitasks_sessions_checked()

    def test_live_session_complete(self):
        sessions, complete = self._run(
            _FakeTmux(sessions=["alpha"], panes={"alpha": [str(self.proj)]}))
        self.assertTrue(complete)
        self.assertEqual([s.session for s in sessions], ["alpha"])

    def test_pane_query_uses_exact_session_target(self):
        # A bare "=<s>" is resolved as a WINDOW by tmux 3.7c and falls back to
        # the most recent session; the checked walk must use "=<s>:".
        fake = _FakeTmux(sessions=["alpha"], panes={"alpha": [str(self.proj)]})
        self._run(fake)
        self.assertEqual(fake.pane_targets, ["=alpha:"])

    def test_no_server_is_definite_empty(self):
        sessions, complete = self._run(_FakeTmux(
            list_sessions=TmuxResult("no_server", 1, "", "no server running on x\n")))
        self.assertEqual((sessions, complete), ([], True))

    def test_no_tmux_is_definite_empty(self):
        sessions, complete = self._run(_FakeTmux(
            list_sessions=TmuxResult("no_tmux", -1, "", "")))
        self.assertEqual((sessions, complete), ([], True))

    def test_list_sessions_failure_is_incomplete_not_empty(self):
        # The distinction this whole function exists for.
        sessions, complete = self._run(_FakeTmux(
            list_sessions=TmuxResult("failed", -1, "", "")))
        self.assertEqual((sessions, complete), ([], False))

    def test_list_panes_failure_is_incomplete(self):
        _, complete = self._run(_FakeTmux(
            sessions=["alpha"],
            panes={"alpha": TmuxResult("failed", 1, "", "server exited unexpectedly\n")}))
        self.assertFalse(complete)

    def test_vanished_session_stays_complete(self):
        sessions, complete = self._run(_FakeTmux(
            sessions=["alpha"],
            panes={"alpha": TmuxResult("failed", 1, "", "can't find session: alpha\n")}))
        self.assertEqual((sessions, complete), ([], True))

    def test_show_environment_failure_is_incomplete(self):
        # Pane paths name no project, so discovery falls back to the tmux
        # global env var — and that query fails for a non-benign reason.
        _, complete = self._run(_FakeTmux(
            sessions=["beta"], panes={"beta": ["/"]},
            env={"beta": TmuxResult("failed", -1, "", "")}))
        self.assertFalse(complete)

    def test_unset_variable_stays_complete(self):
        sessions, complete = self._run(_FakeTmux(sessions=["beta"], panes={"beta": ["/"]}))
        self.assertEqual((sessions, complete), ([], True))

    def test_registry_env_var_resolves(self):
        sessions, complete = self._run(_FakeTmux(
            sessions=["beta"], panes={"beta": ["/"]},
            env={"beta": TmuxResult(OK, 0, f"AITASKS_PROJECT_beta={self.proj}\n", "")}))
        self.assertTrue(complete)
        self.assertEqual([Path(s.project_root) for s in sessions], [self.proj])


if __name__ == "__main__":
    unittest.main()
