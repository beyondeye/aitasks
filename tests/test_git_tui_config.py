"""Unit tests for git TUI config field and detection utility (t507_1).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_git_tui_config.py -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "monitor"))

from agent_launch_utils import KNOWN_GIT_TUIS, detect_git_tuis, load_tmux_defaults


# ---------------------------------------------------------------------------
# detect_git_tuis
# ---------------------------------------------------------------------------


class TestDetectGitTuis(unittest.TestCase):
    def test_detect_all_installed(self):
        """All known git TUIs are installed."""
        def fake_which(name):
            return f"/usr/bin/{name}" if name in KNOWN_GIT_TUIS else None

        with patch("agent_launch_utils.shutil.which", side_effect=fake_which):
            result = detect_git_tuis()
        self.assertEqual(result, ["lazygit", "gitui", "tig"])

    def test_detect_some_installed(self):
        """Only lazygit is installed."""
        def fake_which(name):
            return "/usr/bin/lazygit" if name == "lazygit" else None

        with patch("agent_launch_utils.shutil.which", side_effect=fake_which):
            result = detect_git_tuis()
        self.assertEqual(result, ["lazygit"])

    def test_detect_none_installed(self):
        """No git TUIs are installed."""
        with patch("agent_launch_utils.shutil.which", return_value=None):
            result = detect_git_tuis()
        self.assertEqual(result, [])

    def test_known_git_tuis_order(self):
        """KNOWN_GIT_TUIS has expected tools in preference order."""
        self.assertEqual(KNOWN_GIT_TUIS, ["lazygit", "gitui", "tig"])


# ---------------------------------------------------------------------------
# load_tmux_defaults — git_tui field
# ---------------------------------------------------------------------------


class TestLoadTmuxDefaultsGitTui(unittest.TestCase):
    def _write_config(self, tmpdir, content):
        meta = Path(tmpdir) / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        (meta / "project_config.yaml").write_text(content)
        return Path(tmpdir)

    def test_git_tui_from_config(self):
        """git_tui value is read from project_config.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._write_config(tmpdir, "tmux:\n  git_tui: lazygit\n")
            result = load_tmux_defaults(root)
        self.assertEqual(result["git_tui"], "lazygit")

    def test_git_tui_default_when_missing(self):
        """git_tui defaults to empty string when not in config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._write_config(tmpdir, "tmux:\n  default_session: test\n")
            result = load_tmux_defaults(root)
        self.assertEqual(result["git_tui"], "")

    def test_git_tui_default_when_no_config(self):
        """git_tui defaults to empty string when config file is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_tmux_defaults(Path(tmpdir))
        self.assertEqual(result["git_tui"], "")

    def test_git_tui_null_in_yaml(self):
        """git_tui set to null in YAML returns empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._write_config(tmpdir, "tmux:\n  git_tui: null\n")
            result = load_tmux_defaults(root)
        self.assertEqual(result["git_tui"], "")

    def test_git_tui_with_other_fields(self):
        """git_tui coexists with other tmux defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._write_config(
                tmpdir,
                "tmux:\n  default_session: mysession\n  prefer_tmux: true\n  git_tui: gitui\n",
            )
            result = load_tmux_defaults(root)
        self.assertEqual(result["git_tui"], "gitui")
        self.assertEqual(result["default_session"], "mysession")
        self.assertTrue(result["prefer_tmux"])


# ---------------------------------------------------------------------------
# Set membership — "git" in TUI name sets
# ---------------------------------------------------------------------------


class TestGitInTuiSets(unittest.TestCase):
    def test_git_in_default_tui_names(self):
        """'git' is in DEFAULT_TUI_NAMES in tmux_monitor."""
        from tmux_monitor import DEFAULT_TUI_NAMES
        self.assertIn("git", DEFAULT_TUI_NAMES)

    def test_git_in_tui_switcher_names(self):
        """'git' is in _TUI_NAMES in tui_switcher."""
        from tui_switcher import _TUI_NAMES
        self.assertIn("git", _TUI_NAMES)

    def test_stats_in_default_tui_names(self):
        """'stats' is in DEFAULT_TUI_NAMES in tmux_monitor."""
        from tmux_monitor import DEFAULT_TUI_NAMES
        self.assertIn("stats", DEFAULT_TUI_NAMES)

    def test_stats_in_tui_switcher_names(self):
        """'stats' is in _TUI_NAMES in tui_switcher."""
        from tui_switcher import _TUI_NAMES
        self.assertIn("stats", _TUI_NAMES)


# ---------------------------------------------------------------------------
# tui_registry — central source of truth
# ---------------------------------------------------------------------------


class TestTuiRegistry(unittest.TestCase):
    def test_registry_contains_all_framework_tuis(self):
        """TUI_NAMES covers every framework TUI window name."""
        from tui_registry import TUI_NAMES
        for name in ("board", "codebrowser", "settings", "brainstorm",
                     "monitor", "minimonitor", "diffviewer", "stats", "git"):
            self.assertIn(name, TUI_NAMES)

    def test_switcher_excludes_non_switcher_entries(self):
        """brainstorm and minimonitor classify as TUI but are hidden from the switcher."""
        from tui_registry import switcher_tuis
        switcher_names = {n for n, _, _ in switcher_tuis()}
        self.assertNotIn("brainstorm", switcher_names)
        self.assertNotIn("minimonitor", switcher_names)
        self.assertIn("stats", switcher_names)


# ---------------------------------------------------------------------------
# load_monitor_config — tui_window_names merge semantics
# ---------------------------------------------------------------------------


class TestTuiWindowNamesMergeSemantics(unittest.TestCase):
    def _write_config(self, tmpdir, content):
        meta = Path(tmpdir) / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        (meta / "project_config.yaml").write_text(content)
        return Path(tmpdir)

    def test_config_tui_names_merges_with_defaults(self):
        """Custom tui_window_names in config augment (not replace) the registry defaults."""
        from tmux_monitor import load_monitor_config
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._write_config(
                tmpdir,
                "tmux:\n  monitor:\n    tui_window_names:\n      - my_custom_tui\n",
            )
            result = load_monitor_config(root)
        tui_names = result["tui_names"]
        self.assertIn("my_custom_tui", tui_names)
        # Registry defaults must still be present — new framework TUIs are
        # never masked by a stale override list.
        self.assertIn("stats", tui_names)
        self.assertIn("board", tui_names)


if __name__ == "__main__":
    unittest.main()
