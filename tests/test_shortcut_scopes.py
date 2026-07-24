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

import importlib.util
import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import keybinding_registry  # noqa: E402
import shortcut_scopes  # noqa: E402
import tui_switcher  # noqa: E402

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

    # Derived from the switcher's canonical quick-jump table (t1160) so this
    # guard cannot drift when a quick-jump is added/removed — a hand-maintained
    # copy silently fell behind when t1148 added shortcut_explore_pick. The
    # equality assertions below still verify the registration + sweep pipeline
    # surfaces exactly these actions under shared.tui_switcher, and that the
    # fixed structural keys (escape/enter/←/→/j) are left unregistered.
    _QUICK_JUMPS = {b.action for b in tui_switcher._QUICK_JUMP_BINDINGS}
    _STRUCTURAL = {"dismiss_overlay", "select_tui", "prev_session", "next_session"}

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()

    def tearDown(self) -> None:
        keybinding_registry._reset_for_tests()

    def test_quick_jumps_in_iter_all_bindings(self):
        # Sanity: the derived expectation must be non-empty and contain anchors,
        # so a broken import/derivation can't make the equality below vacuous.
        for anchor in ("shortcut_board", "shortcut_explore", "shortcut_explore_pick"):
            self.assertIn(anchor, self._QUICK_JUMPS)

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


class ModuleIdentityTests(unittest.TestCase):
    """t1211: a sweep must never rebind a canonical ``sys.modules`` entry.

    The sweep re-executes each manifest module's body. If it did so under the
    module's *canonical* name, ``sys.modules[name]`` would be replaced by a fresh
    module object and its classes would gain a second identity — so anything
    holding the pre-sweep class fails ``isinstance`` against the post-sweep one.
    That is a live-process bug (``ShortcutsMixin.action_open_shortcuts_editor``
    sweeps inside running TUIs, and ``shared.*`` always matches) and it also made
    ``tests/test_tui_switcher_agent_launch.py`` fail under full-suite discovery
    while passing in isolation. ``_load_and_register`` therefore execs under
    ``_PROBE_PREFIX + module_name``.

    **Do not "simplify" this by reusing an already-imported module instead of
    re-executing it.** The re-exec is what re-fires module-level / class-body
    registrations (``shared.tui_switcher``, ``brainstorm.dag``) after
    ``keybinding_registry._reset_for_tests()``; a reuse implementation makes
    ``ManifestDriftTests`` and ``TuiSwitcherScopeTests`` above fail. Both
    properties are required, and each is pinned by a different test here.
    """

    _CANONICAL = "agent_command_screen"

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()

    def tearDown(self) -> None:
        keybinding_registry._reset_for_tests()

    def _identity(self) -> tuple[object, object]:
        """(module object, class object) currently bound to the canonical name."""
        module = sys.modules[self._CANONICAL]
        return module, module.AgentCommandScreen

    def test_full_sweep_preserves_canonical_module_identity(self):
        import agent_command_screen  # noqa: F401 — ensure it is canonically imported

        before = self._identity()
        shortcut_scopes.register_all_known_bindings()
        self.assertEqual(
            self._identity(), before,
            "register_all_known_bindings() rebound sys.modules"
            f"[{self._CANONICAL!r}] — its classes now have a second identity",
        )

    def test_filtered_sweep_preserves_canonical_module_identity(self):
        # The in-TUI `?` editor path: shared.* is always scope-relevant, so a
        # board editor loads agent_command_screen too.
        import agent_command_screen  # noqa: F401

        before = self._identity()
        shortcut_scopes.register_scope_bindings("board")
        self.assertEqual(
            self._identity(), before,
            "register_scope_bindings('board') rebound sys.modules"
            f"[{self._CANONICAL!r}]",
        )

    def test_repeated_sweeps_preserve_canonical_module_identity(self):
        """The probe key is fixed, so later sweeps overwrite the probe entry.

        A live TUI can sweep many times (``_subscopes_registered`` guards per
        *instance*, not per process), so identity must hold after **every** call,
        not just the first.
        """
        import agent_command_screen  # noqa: F401

        before = self._identity()
        probe_key = shortcut_scopes._PROBE_PREFIX + self._CANONICAL
        probe_objects = []

        for round_no in range(1, 4):
            for label, sweep in (
                ("register_all_known_bindings", lambda: shortcut_scopes.register_all_known_bindings()),
                ("register_scope_bindings('board')", lambda: shortcut_scopes.register_scope_bindings("board")),
                ("register_scope_bindings('codebrowser')", lambda: shortcut_scopes.register_scope_bindings("codebrowser")),
            ):
                failed = sweep()
                self.assertEqual(failed, [], f"round {round_no} {label}: import failures {failed}")
                self.assertEqual(
                    self._identity(), before,
                    f"round {round_no}: {label} rebound sys.modules[{self._CANONICAL!r}]",
                )
            probe_objects.append(sys.modules[probe_key])

        # Distinguish expected probe churn from the bug: the probe entry IS
        # replaced every round, the canonical entry is not. Without this the
        # assertions above could pass on a build that never loaded anything.
        self.assertEqual(
            len({id(o) for o in probe_objects}), len(probe_objects),
            "probe entry was not re-executed on later sweeps",
        )
        self.assertNotIn(
            id(before[0]), {id(o) for o in probe_objects},
            "probe entry must never be the canonical module object",
        )

    def test_canonical_name_load_is_detected(self):
        """Negative control: the identity assertions above must be falsifiable.

        Reproduce the pre-fix behaviour (exec under the canonical name) directly
        and assert the same comparison *does* catch it. Without this, an
        ``assertEqual`` on two reads of an untouched entry would pass forever
        even if the sweep stopped loading modules altogether.
        """
        import agent_command_screen  # noqa: F401

        before = self._identity()
        path = shortcut_scopes._SCRIPTS_DIR / "lib" / "agent_command_screen.py"
        try:
            spec = importlib.util.spec_from_file_location(self._CANONICAL, path)
            assert spec is not None and spec.loader is not None
            clobber = importlib.util.module_from_spec(spec)
            sys.modules[self._CANONICAL] = clobber
            spec.loader.exec_module(clobber)
            self.assertNotEqual(
                self._identity(), before,
                "a canonical-name re-exec went undetected — the identity "
                "assertions in this class are vacuous",
            )
        finally:
            # Undo only our own mutation; never `git checkout --` here.
            sys.modules[self._CANONICAL] = before[0]

        self.assertEqual(self._identity(), before, "negative control failed to restore state")


if __name__ == "__main__":
    # Ensure cwd doesn't matter for the path-based sweep.
    os.chdir(REPO_ROOT)
    unittest.main()
