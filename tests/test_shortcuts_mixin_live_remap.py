"""Tests for ShortcutsMixin live-keymap remapping (t964).

Covers the fix for the framework-wide bug where a per-TUI key rebind reached
``self.BINDINGS`` (and the registry / footer hint / tab title) but NOT Textual's
*live* keymap, so pressing the new key did nothing. ``ShortcutsMixin.__init__``
registers bindings *after* ``super().__init__()`` has already copied the
class-level ``_merged_bindings`` (default keys) into ``self._bindings``;
``_relink_live_bindings`` now moves each remapped binding onto its override key
in the live map.

Asserts the behaviour with real key-presses (not just ``self.BINDINGS``):
  - App scope: the override key fires the action; the retired default key does
    not.
  - Modal scope: same, proving the fix covers ``ShortcutsMixin`` modals
    (AgentCommandScreen / StaleEntryModal register via the mixin too, contrary
    to t964's original "only Apps affected" diagnosis).
  - Framework bindings (command palette, quit) survive the relink.
  - No override → the default key still fires (no-op path).

Run: python3 tests/test_shortcuts_mixin_live_remap.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import Static  # noqa: E402

import keybinding_registry  # noqa: E402
import shortcut_persist  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402


class _DemoApp(ShortcutsMixin, App):
    """Minimal App-scope TUI with one observable, remappable binding."""

    _shortcuts_scope = "demo"
    BINDINGS = [Binding("e", "do_thing", "Thing")]

    def __init__(self) -> None:
        super().__init__()
        self.fired = False

    def action_do_thing(self) -> None:
        self.fired = True


class _DemoModal(ShortcutsMixin, ModalScreen):
    """Minimal modal-scope screen with one observable, remappable binding."""

    _shortcuts_scope = "demo.modal"
    BINDINGS = [Binding("e", "do_thing", "Thing")]

    def __init__(self) -> None:
        super().__init__()
        self.fired = False

    def compose(self):
        yield Static("modal")

    def action_do_thing(self) -> None:
        self.fired = True


class _ModalHostApp(App):
    """Host app that pushes a _DemoModal on mount so its key-presses route."""

    def __init__(self) -> None:
        super().__init__()
        self.modal = _DemoModal()

    def on_mount(self) -> None:
        self.push_screen(self.modal)


class _Fixture(unittest.TestCase):
    """chdir into a temp workspace; reset registry state around each test."""

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
        (self.root / "aitasks" / "metadata" / "userconfig.yaml").write_text(
            "# Local user configuration (gitignored, not shared)\n"
            "email: tester@example.com\n",
            encoding="utf-8",
        )
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()
        keybinding_registry._reset_for_tests()

    def _run(self, coro):
        return asyncio.run(coro)


class AppScopeTests(_Fixture):
    def test_override_key_fires_and_default_retired(self):
        async def runner():
            shortcut_persist.save_override("demo", "do_thing", "x")
            keybinding_registry.refresh_all()
            app = _DemoApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                # Override key now fires the action live.
                await pilot.press("x")
                await pilot.pause()
                self.assertTrue(app.fired, "override key 'x' did not fire")
                # The retired default key must no longer fire.
                app.fired = False
                await pilot.press("e")
                await pilot.pause()
                self.assertFalse(app.fired, "default key 'e' still fires")
        self._run(runner())

    def test_live_keymap_keys_reflect_override(self):
        async def runner():
            shortcut_persist.save_override("demo", "do_thing", "x")
            keybinding_registry.refresh_all()
            app = _DemoApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                keys = app._bindings.key_to_bindings
                self.assertIn("x", keys)
                self.assertNotIn("e", keys)
        self._run(runner())

    def test_framework_bindings_preserved(self):
        async def runner():
            shortcut_persist.save_override("demo", "do_thing", "x")
            keybinding_registry.refresh_all()
            app = _DemoApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                keys = app._bindings.key_to_bindings
                # Command palette / quit bindings live alongside in the same map
                # and must survive the relink (a naive rebuild would drop them).
                self.assertIn("ctrl+p", keys)
                self.assertIn("ctrl+c", keys)
        self._run(runner())

    def test_no_override_default_key_still_fires(self):
        async def runner():
            # No override saved — the default key must keep working.
            app = _DemoApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                self.assertIn("e", app._bindings.key_to_bindings)
                await pilot.press("e")
                await pilot.pause()
                self.assertTrue(app.fired, "default key 'e' did not fire")
        self._run(runner())


class ModalScopeTests(_Fixture):
    def test_modal_override_key_fires_and_default_retired(self):
        async def runner():
            shortcut_persist.save_override("demo.modal", "do_thing", "x")
            keybinding_registry.refresh_all()
            app = _ModalHostApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                self.assertIs(app.screen, app.modal)
                await pilot.press("x")
                await pilot.pause()
                self.assertTrue(app.modal.fired, "modal override 'x' did not fire")
                app.modal.fired = False
                await pilot.press("e")
                await pilot.pause()
                self.assertFalse(
                    app.modal.fired, "modal default key 'e' still fires"
                )
        self._run(runner())

    def test_modal_live_keymap_keys_reflect_override(self):
        async def runner():
            shortcut_persist.save_override("demo.modal", "do_thing", "x")
            keybinding_registry.refresh_all()
            app = _ModalHostApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                keys = app.modal._bindings.key_to_bindings
                self.assertIn("x", keys)
                self.assertNotIn("e", keys)
        self._run(runner())


if __name__ == "__main__":
    unittest.main()
