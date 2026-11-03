"""The switcher's `g` quick-jump gates on the SELECTED project's config (t2180).

`action_shortcut_git` decides whether a Git TUI is configured by reading
`tmux.git_tui` from a project's `project_config.yaml`. It must read the
SELECTED session's project, the same root `_get_launch_command` launches from
(t814/t1099). Reading the process cwd instead made `g` depend on which project
the overlay's Python process happened to start in. In a cross-repo selection it
no-op'd when the selected project configured git, and switched when it did not.

Each case puts the selected project and the cwd on opposite sides of
"configures git", so a gate on the wrong root fails in both directions.

Run: python3 tests/test_tui_switcher_git_shortcut_root.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import tui_switcher as ts  # noqa: E402


def _project(root: Path, git_tui: str | None) -> Path:
    """A minimal project: `tmux.git_tui` set, or no config file at all."""
    root.mkdir(parents=True)
    if git_tui is not None:
        metadata = root / "aitasks" / "metadata"
        metadata.mkdir(parents=True)
        (metadata / "project_config.yaml").write_text(
            f"tmux:\n  git_tui: {git_tui}\n", encoding="utf-8"
        )
    return root


class GitShortcutGatesOnSelectedRootTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.with_git = _project(base / "with_git", "lazygit")
        self.without_git = _project(base / "without_git", None)
        self._cwd = os.getcwd()

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def _press_g(self, *, selected: Path, cwd: Path) -> list[str]:
        """Run the real action with the selected root and the cwd pinned apart."""
        overlay = object.__new__(ts.TuiSwitcherOverlay)
        switched: list[str] = []
        overlay._selected_project_root = lambda: selected
        overlay._shortcut_switch = switched.append
        os.chdir(cwd)
        overlay.action_shortcut_git()
        return switched

    def test_fixture_configures_git_on_exactly_one_side(self):
        """Self-check: the two projects really differ in the gate's input."""
        names = lambda root: [name for name, _, _ in ts._build_tui_list(root)]
        self.assertIn("git", names(self.with_git))
        self.assertNotIn("git", names(self.without_git))

    def test_selected_project_with_git_switches_even_when_cwd_has_none(self):
        self.assertEqual(
            self._press_g(selected=self.with_git, cwd=self.without_git), ["git"]
        )

    def test_selected_project_without_git_is_a_noop_even_when_cwd_has_it(self):
        self.assertEqual(
            self._press_g(selected=self.without_git, cwd=self.with_git), []
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
