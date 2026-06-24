"""Drift guard for the global shortcut-scope manifest (t848_5).

The Settings -> Shortcuts tab calls
``shortcut_scopes.register_all_known_bindings()`` to populate every TUI's
bindings in a settings-only process (no other App is instantiated). This test
makes sure that sweep stays complete:

  1. Discover the ground-truth set of scopes by scanning the source tree for
     ``_shortcuts_scope = "..."`` assignments and any ``*register*bindings(...)``
     call's first string literal (catches the aliased shared registration in
     tui_switcher.py too).
  2. Run the sweep in a fresh process state (no App instantiated).
  3. Assert every discovered scope is registered. A scope declared in source
     but not swept fails here, telling the dev to add the declaring module file
     to KNOWN_BINDING_SOURCES in lib/shortcut_scopes.py.

`settings` self-registers via the running SettingsApp (not the sweep), so it is
excluded from the ground-truth set here.

Run: bash tests/run_all_python_tests.sh
  or: python3 tests/test_shortcut_scopes.py
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import keybinding_registry  # noqa: E402
import shortcut_scopes  # noqa: E402

_SCRIPTS_DIR = REPO_ROOT / ".aitask-scripts"

# Scopes that are NOT registered by the sweep:
#  - settings: the running SettingsApp registers it on instantiation.
_NON_SWEPT_SCOPES = {"settings"}

_SCOPE_ASSIGN_RE = re.compile(r"""_shortcuts_scope\s*=\s*["']([^"']+)["']""")
# Tolerant: matches register_app_bindings(...) AND aliased _register_*_bindings(...)
_REGISTER_CALL_RE = re.compile(r"""register[_a-z]*bindings\(\s*["']([^"']+)["']""")
# A real scope is a lowercase dotted identifier (e.g. board, board.detail).
# This drops docstring placeholders like "<scope>" and the empty default.
_VALID_SCOPE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")


def _discover_source_scopes() -> set[str]:
    scopes: set[str] = set()
    for py in _SCRIPTS_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        scopes.update(_SCOPE_ASSIGN_RE.findall(text))
        scopes.update(_REGISTER_CALL_RE.findall(text))
    return {s for s in scopes if _VALID_SCOPE_RE.match(s)}


class ManifestDriftTests(unittest.TestCase):
    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()

    def tearDown(self) -> None:
        keybinding_registry._reset_for_tests()

    def test_sweep_registers_every_source_scope(self):
        expected = _discover_source_scopes() - _NON_SWEPT_SCOPES
        # Sanity: discovery must find the well-known scopes.
        for known in ("board", "monitor", "brainstorm.dag", "shared"):
            self.assertIn(known, expected,
                          f"source scan failed to find scope {known!r}")

        failed = shortcut_scopes.register_all_known_bindings()
        registered = {scope for (scope, _action) in keybinding_registry._DEFAULTS}

        missing = sorted(expected - registered)
        self.assertFalse(
            missing,
            "Scopes declared in source but NOT registered by the global sweep: "
            f"{missing}. Add the declaring module file(s) to "
            "KNOWN_BINDING_SOURCES in .aitask-scripts/lib/shortcut_scopes.py "
            "(see aidocs/framework/tui_conventions.md). "
            f"Modules that failed to import: {failed}",
        )

    def test_sweep_reports_no_import_failures(self):
        failed = shortcut_scopes.register_all_known_bindings()
        self.assertEqual(
            failed, [],
            f"Manifest modules failed to import during the sweep: {failed}",
        )


class ScopeFilteredSweepTests(unittest.TestCase):
    """register_scope_bindings(scope) — the in-TUI `?` editor's filtered sweep
    (t848_9): loads only the active TUI's own scope + sub-scopes + shared, with
    no App instantiated, and skips every unrelated TUI."""

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()

    def tearDown(self) -> None:
        keybinding_registry._reset_for_tests()

    def _registered(self) -> set[str]:
        return {scope for (scope, _action) in keybinding_registry._DEFAULTS}

    def test_board_scope_loads_own_subscopes_and_shared_only(self):
        failed = shortcut_scopes.register_scope_bindings("board")
        self.assertEqual(failed, [], f"unexpected import failures: {failed}")
        registered = self._registered()
        # board's own scope + its modal sub-scope register eagerly, with no
        # TaskDetailScreen ever instantiated.
        for scope in ("board", "board.detail"):
            self.assertIn(scope, registered, f"{scope} not registered eagerly")
        # global shared scopes are always included (the editor surfaces them):
        # the TUI switcher, the stale-entry modal, and the cross-TUI agent
        # command dialog (shared.agent_cmd, reused by board/codebrowser/…).
        for scope in ("shared", "shared.stale_entry", "shared.agent_cmd"):
            self.assertIn(scope, registered, f"{scope} not registered eagerly")
        # unrelated TUIs are NOT imported by the filtered sweep.
        for scope in ("brainstorm", "codebrowser", "monitor", "syncer"):
            self.assertNotIn(scope, registered,
                             f"{scope} should not be loaded for a board editor")

    def test_codebrowser_scope_filtered(self):
        failed = shortcut_scopes.register_scope_bindings("codebrowser")
        self.assertEqual(failed, [], f"unexpected import failures: {failed}")
        registered = self._registered()
        self.assertIn("codebrowser", registered)
        self.assertIn("codebrowser.copypath", registered)
        self.assertIn("shared", registered)
        # the agent command dialog is reused in codebrowser too, so its shared
        # sub-scope surfaces here as well — the point of rescoping it to shared.
        self.assertIn("shared.agent_cmd", registered)
        self.assertNotIn("board", registered)
        self.assertNotIn("brainstorm", registered)


class TuiSwitcherScopeTests(unittest.TestCase):
    """t876: the TUI-switcher overlay's quick-jumps register under
    ``shared.tui_switcher`` and surface in both the Settings tab
    (``iter_all_bindings`` after the full sweep) and the in-TUI ``?`` editor
    (``iter_scope_bindings`` — it's a ``shared.*`` scope, always included). The
    structural keys (escape/enter/←/→/j) stay fixed literals and are NOT
    registered, so only the quick-jumps are customizable."""

    _QUICK_JUMPS = {
        "shortcut_applink", "shortcut_board", "shortcut_monitor",
        "shortcut_codebrowser", "shortcut_settings", "shortcut_stats",
        "shortcut_syncer", "shortcut_brainstorm", "shortcut_explore",
        "shortcut_git", "shortcut_create", "shortcut_agent",
    }
    _STRUCTURAL = {"dismiss_overlay", "select_tui", "prev_session", "next_session"}

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()

    def tearDown(self) -> None:
        keybinding_registry._reset_for_tests()

    def test_quick_jumps_in_iter_all_bindings(self):
        shortcut_scopes.register_all_known_bindings()
        actions = {
            action for (scope, action, _k, _l)
            in keybinding_registry.iter_all_bindings()
            if scope == "shared.tui_switcher"
        }
        self.assertEqual(actions, self._QUICK_JUMPS)
        # The fixed structural keys are intentionally left unregistered.
        self.assertFalse(actions & self._STRUCTURAL)

    def test_quick_jumps_in_scope_filtered_editor(self):
        # A board editor's filtered sweep must surface shared.tui_switcher.
        shortcut_scopes.register_scope_bindings("board")
        actions = {
            action for (scope, action, _k, _l)
            in keybinding_registry.iter_scope_bindings("board")
            if scope == "shared.tui_switcher"
        }
        self.assertEqual(actions, self._QUICK_JUMPS)


if __name__ == "__main__":
    # Ensure cwd doesn't matter for the path-based sweep.
    os.chdir(REPO_ROOT)
    unittest.main()
