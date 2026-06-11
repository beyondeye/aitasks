"""Regression test for `discover_aitasks_sessions()` (no flag) (t826_2).

Verifies that the no-flag call shape is byte-identical to pre-change
behavior, so existing callers (notably `ait monitor`) see no leakage
from the registry-driven inactive-project view introduced by t826_2.

Run: python3 tests/test_discover_default_unchanged.py
  or: bash tests/run_all_python_tests.sh
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

import agent_launch_utils
from agent_launch_utils import discover_aitasks_sessions


def _make_fake_project(tmp: Path) -> Path:
    (tmp / "aitasks" / "metadata").mkdir(parents=True)
    (tmp / "aitasks" / "metadata" / "project_config.yaml").write_text(
        "project:\n  name: fake\n"
    )
    return tmp


class DefaultCallUnchangedTests(unittest.TestCase):
    """The no-flag call shape must remain byte-identical to pre-t826_2."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        # Pin the module-level gateway singleton to NO socket flag: the mocks
        # below prefix-match argv[:2] == ["tmux", "list-sessions"], but since
        # t953 a default-constructed TmuxClient carries `-L ait`. Swapping the
        # singleton (rather than setting the env var pre-import) stays correct
        # under run_all_python_tests.sh, where another module may import
        # agent_launch_utils first and freeze the cached socket args.
        self._saved_tmux = agent_launch_utils._TMUX
        agent_launch_utils._TMUX = agent_launch_utils.TmuxClient(socket_args=[])

    def tearDown(self) -> None:
        agent_launch_utils._TMUX = self._saved_tmux
        self._tmpdir.cleanup()
        os.environ.pop("AITASKS_PROJECTS_INDEX", None)

    def test_no_sessions_returns_empty(self):
        with mock.patch.object(
            agent_launch_utils.subprocess, "run",
            return_value=mock.Mock(returncode=1, stdout="", stderr=""),
        ):
            self.assertEqual(discover_aitasks_sessions(), [])

    def test_live_session_returned_with_is_live_true(self):
        proj = _make_fake_project(self.tmp / "live_proj")

        def _fake_tmux(argv, *a, **k):
            if argv[:2] == ["tmux", "list-sessions"]:
                return mock.Mock(returncode=0, stdout="live_sess\n", stderr="")
            if argv[:2] == ["tmux", "list-panes"]:
                return mock.Mock(returncode=0, stdout=f"{proj}\n", stderr="")
            return mock.Mock(returncode=1, stdout="", stderr="")

        with mock.patch.object(agent_launch_utils.subprocess, "run", side_effect=_fake_tmux):
            result = discover_aitasks_sessions()

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertTrue(entry.is_live)
        self.assertEqual(entry.session, "live_sess")
        self.assertEqual(entry.project_root, proj)
        self.assertEqual(entry.project_name, "live_proj")

    def test_no_leak_from_registry_when_flag_absent(self):
        """A non-empty registry must NOT bleed into the default call."""
        proj_reg = _make_fake_project(self.tmp / "registered_only")
        idx = self.tmp / "projects.yaml"
        idx.write_text(f"projects:\n  - name: registered_only\n    path: {proj_reg}\n")
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)

        with mock.patch.object(
            agent_launch_utils.subprocess, "run",
            return_value=mock.Mock(returncode=1, stdout="", stderr=""),
        ):
            self.assertEqual(discover_aitasks_sessions(), [])

    def test_kwarg_only_signature(self):
        """include_registered MUST be keyword-only to avoid silent breakage of
        positional callers (none exist today, but lock the contract)."""
        with mock.patch.object(
            agent_launch_utils.subprocess, "run",
            return_value=mock.Mock(returncode=1, stdout="", stderr=""),
        ):
            with self.assertRaises(TypeError):
                discover_aitasks_sessions(True)  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
