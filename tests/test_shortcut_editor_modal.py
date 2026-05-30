"""Tests for the in-TUI shortcut editor modal (t848_4).

Covers:
  - keybinding_registry.iter_scope_bindings: scope + sub-scope + shared filter.
  - Modal logic (direct-method, test_stale_entry_modal.py style): effective-key
    resolution, edit-time collision blocking on rebind and reset-to-default,
    revert, and save persistence into userconfig.yaml.
  - Pilot integration: pressing `?` opens the editor with a populated table;
    a full rebind → save round-trip writes the override.

Run: python3 tests/test_shortcut_editor_modal.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import yaml  # noqa: E402
from textual.app import App  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.widgets import DataTable  # noqa: E402

import keybinding_registry  # noqa: E402
import shortcut_persist  # noqa: E402
from shortcut_editor_modal import _CLEAR, ShortcutEditorModal  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402


def _read_userconfig() -> dict:
    p = Path("aitasks/metadata/userconfig.yaml")
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


class _Fixture(unittest.TestCase):
    """chdir into a temp workspace with userconfig.yaml; reset registry state."""

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
        (root / "aitasks" / "metadata" / "userconfig.yaml").write_text(
            "# Local user configuration (gitignored, not shared)\n"
            "email: tester@example.com\n",
            encoding="utf-8",
        )
        os.chdir(root)

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()
        keybinding_registry._reset_for_tests()


class IterScopeBindingsTests(_Fixture):
    def test_scope_subscope_and_shared_filter(self):
        keybinding_registry.register_app_bindings(
            "board", [Binding("p", "pick", "Pick")]
        )
        keybinding_registry.register_app_bindings(
            "board.detail", [Binding("c", "close", "Close")]
        )
        keybinding_registry.register_app_bindings(
            "shared", [Binding("j", "tui_switcher", "Switch")]
        )
        keybinding_registry.register_app_bindings(
            "brainstorm", [Binding("h", "op_help", "Help")]
        )

        rows = keybinding_registry.iter_scope_bindings("board")
        scopes = {(s, a) for s, a, _, _ in rows}
        self.assertIn(("board", "pick"), scopes)
        self.assertIn(("board.detail", "close"), scopes)   # sub-scope included
        self.assertIn(("shared", "tui_switcher"), scopes)  # global shared included
        self.assertNotIn(("brainstorm", "op_help"), scopes)  # other TUI excluded
        # sorted by (scope, action_id)
        self.assertEqual(rows, sorted(rows, key=lambda r: (r[0], r[1])))

    def test_shared_action_not_duplicated_under_app_scope(self):
        # Runtime order: shared scope registered first (tui_switcher import),
        # then an App splices the same binding into its own BINDINGS.
        keybinding_registry.register_app_bindings(
            "shared", [Binding("j", "tui_switcher", "Switch")]
        )
        keybinding_registry.register_app_bindings(
            "monitor",
            [Binding("j", "tui_switcher", "Switch"), Binding("f5", "refresh", "Refresh")],
        )
        # tui_switcher is NOT shadowed under the app scope...
        self.assertNotIn(("monitor", "tui_switcher"), keybinding_registry._DEFAULTS)
        self.assertIn(("shared", "tui_switcher"), keybinding_registry._DEFAULTS)
        # ...so the monitor editor lists it exactly once (under "shared").
        sw_rows = [
            r for r in keybinding_registry.iter_scope_bindings("monitor")
            if r[1] == "tui_switcher"
        ]
        self.assertEqual(len(sw_rows), 1)
        self.assertEqual(sw_rows[0][0], "shared")

    def test_shared_override_applies_to_app_binding(self):
        keybinding_registry.register_app_bindings(
            "shared", [Binding("j", "tui_switcher", "Switch")]
        )
        shortcut_persist.save_override("shared", "tui_switcher", "k")
        keybinding_registry.refresh()
        applied = keybinding_registry.register_app_bindings(
            "monitor", [Binding("j", "tui_switcher", "Switch")]
        )
        self.assertEqual(applied[0].key, "k")  # resolved from the shared override


class ModalLogicTests(_Fixture):
    """Direct-method tests with the textual-runtime slots mocked."""

    def setUp(self) -> None:
        super().setUp()
        keybinding_registry.register_app_bindings(
            "testscope",
            [Binding("p", "pick", "Pick"), Binding("b", "brainstorm", "Brainstorm")],
        )
        self._app_patch = mock.patch.object(
            ShortcutEditorModal, "app", mock.Mock()
        )
        self._app_patch.start()

    def tearDown(self) -> None:
        self._app_patch.stop()
        super().tearDown()

    def _modal(self) -> ShortcutEditorModal:
        modal = ShortcutEditorModal("testscope")
        modal.dismiss = mock.Mock()
        modal._refresh_table = mock.Mock()
        return modal

    def test_effective_key_pending_and_override(self):
        modal = self._modal()
        self.assertEqual(modal._effective_key("testscope", "pick", "p"), "p")
        modal._pending[("testscope", "pick")] = "o"
        self.assertEqual(modal._effective_key("testscope", "pick", "p"), "o")
        modal._pending[("testscope", "pick")] = _CLEAR
        self.assertEqual(modal._effective_key("testscope", "pick", "p"), "p")

    def test_would_collide_detects_in_scope_clash(self):
        modal = self._modal()
        self.assertEqual(modal._would_collide("testscope", "pick", "b"), "brainstorm")
        self.assertIsNone(modal._would_collide("testscope", "pick", "x"))

    def test_apply_capture_blocks_collision(self):
        modal = self._modal()
        modal._apply_capture("testscope", "pick", "b")  # collides with brainstorm
        self.assertNotIn(("testscope", "pick"), modal._pending)
        modal.app.notify.assert_called_once()
        self.assertEqual(
            modal.app.notify.call_args.kwargs.get("severity"), "error"
        )
        modal._refresh_table.assert_not_called()

    def test_apply_capture_accepts_free_key(self):
        modal = self._modal()
        modal._apply_capture("testscope", "pick", "x")
        self.assertEqual(modal._pending[("testscope", "pick")], "x")
        modal._refresh_table.assert_called_once()

    def test_reset_default_blocked_when_default_taken(self):
        # Move brainstorm onto pick's default key "p" first.
        shortcut_persist.save_override("testscope", "brainstorm", "p")
        modal = self._modal()
        modal._cursor_key = mock.Mock(return_value=("testscope", "pick"))
        modal.action_reset_default()
        self.assertNotIn(("testscope", "pick"), modal._pending)
        msg = modal.app.notify.call_args.args[0]
        self.assertIn("Cannot reset", msg)

    def test_reset_default_marks_clear_when_free(self):
        modal = self._modal()
        modal._cursor_key = mock.Mock(return_value=("testscope", "pick"))
        modal.action_reset_default()
        self.assertIs(modal._pending[("testscope", "pick")], _CLEAR)

    def test_revert_row_drops_pending(self):
        modal = self._modal()
        modal._pending[("testscope", "pick")] = "x"
        modal._cursor_key = mock.Mock(return_value=("testscope", "pick"))
        modal.action_revert_row()
        self.assertNotIn(("testscope", "pick"), modal._pending)

    def test_save_persists_and_clears(self):
        # Pre-existing override on pick that we'll clear; new override on brainstorm.
        shortcut_persist.save_override("testscope", "pick", "x")
        keybinding_registry.refresh("testscope")
        modal = self._modal()
        modal._pending[("testscope", "pick")] = _CLEAR        # reset to default
        modal._pending[("testscope", "brainstorm")] = "z"     # rebind
        modal.action_save()
        cfg = _read_userconfig().get("shortcuts", {}).get("testscope", {})
        self.assertNotIn("pick", cfg)            # override cleared
        self.assertEqual(cfg.get("brainstorm"), "z")
        modal.dismiss.assert_called_once_with(None)
        # email sibling key preserved
        self.assertEqual(_read_userconfig().get("email"), "tester@example.com")

    def test_save_rebind_to_default_clears_instead_of_storing(self):
        shortcut_persist.save_override("testscope", "pick", "x")
        keybinding_registry.refresh("testscope")
        modal = self._modal()
        modal._pending[("testscope", "pick")] = "p"   # equals default
        modal.action_save()
        cfg = _read_userconfig().get("shortcuts", {}).get("testscope", {})
        self.assertNotIn("pick", cfg)


class HostApp(ShortcutsMixin, App):
    _shortcuts_scope = "testscope"
    BINDINGS = [
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,   # ? -> open_shortcuts_editor
        Binding("p", "noop_pick", "Pick"),
        Binding("b", "noop_brainstorm", "Brainstorm"),
    ]

    def action_noop_pick(self) -> None:
        pass

    def action_noop_brainstorm(self) -> None:
        pass


class PilotTests(_Fixture):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_question_mark_opens_editor_and_populates(self):
        async def runner():
            app = HostApp()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.press("question_mark")
                await pilot.pause()
                self.assertIsInstance(app.screen, ShortcutEditorModal)
                table = app.screen.query_one("#se_table", DataTable)
                # 3 registered actions in testscope: noop_pick, noop_brainstorm,
                # open_shortcuts_editor (no shared scope registered in this test).
                self.assertEqual(table.row_count, 3)

        self._run(runner())

    def test_rebind_and_save_round_trip(self):
        async def runner():
            app = HostApp()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.press("question_mark")
                await pilot.pause()
                modal = app.screen
                self.assertIsInstance(modal, ShortcutEditorModal)
                # Rows sorted by action_id: noop_brainstorm(0), noop_pick(1),
                # open_shortcuts_editor(2). Move to noop_pick.
                table = modal.query_one("#se_table", DataTable)
                table.move_cursor(row=1)
                await pilot.pause()
                await pilot.press("enter")        # -> KeyCaptureScreen
                await pilot.pause()
                await pilot.press("o")             # capture new key
                await pilot.pause()
                await pilot.press("s")             # save
                await pilot.pause()

            cfg = _read_userconfig().get("shortcuts", {}).get("testscope", {})
            self.assertEqual(cfg.get("noop_pick"), "o")

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
