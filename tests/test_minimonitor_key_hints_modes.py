"""Minimonitor's key-hint modes: full band, collapsed line, help modal (t2212).

Every assertion that is about what the user SEES reads the composited screen
(`_compositor.render_strips`) or a rendered region, never the widget's text
alone: the collapsed line's whole contract — one row, both active keys visible
— is a statement about the screen.

Every test runs in a scratch workspace (cwd + ``TASK_DIR``), so key overrides
are written to, and the toggle persists into, a throwaway userconfig — never the
developer's real one. The key registry is reset around each test, because
overrides are cached process-wide.

Run: python3 tests/test_minimonitor_key_hints_modes.py
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

from monitor import minimonitor_app as mm  # noqa: E402
from monitor import minimonitor_keys as mk  # noqa: E402
import keybinding_registry  # noqa: E402
import shortcut_persist  # noqa: E402
import shortcuts_mixin  # noqa: E402
import userconfig_persist  # noqa: E402
from rich.cells import cell_len  # noqa: E402
from textual.app import App  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402

_USERCONFIG_HEADER = (
    "# Local user configuration (gitignored, not shared)\n"
    "email: tester@example.com\n"
)

#: Collapsed-line rung expected for each (override pair, pane width), derived
#: by hand from cell counts — content width is the pane width minus the band's
#: 2-cell horizontal padding. Rung 1 is the labelled line: `^y:keys ^u:help` is
#: 15 cells, `alt+y:keys alt+u:help` is 21. A literal table, never recomputed
#: through the code under test.
RUNG_TABLE = {
    ("ctrl+y", "ctrl+u"): {15: 2, 18: 1, 22: 1, 24: 1, 40: 1},
    ("alt+y", "alt+u"): {15: 2, 18: 2, 22: 2, 24: 1, 40: 1},
}
LONG_PAIR = ("ctrl+shift+f11", "ctrl+shift+f12")


def _rows(app) -> list[str]:
    return [
        strip.text
        for strip in app.screen._compositor.render_strips(app.screen.size)
    ]


def _plain(widget) -> str:
    content = widget.content
    return getattr(content, "plain", str(content))


class _Workspace(unittest.TestCase):
    """Scratch cwd + TASK_DIR + a reset key registry, TMUX unset.

    With ``TMUX`` unset, ``on_mount`` returns before ``_start_monitoring()`` —
    a real-app boot with no tmux I/O and no refresh timer.
    """

    def setUp(self) -> None:
        self._saved_env = {
            k: os.environ.pop(k, None) for k in ("TMUX", "TMUX_PANE", "TASK_DIR")
        }
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.meta = self.root / "aitasks" / "metadata"
        self.meta.mkdir(parents=True)
        self.userconfig = self.meta / "userconfig.yaml"
        self.userconfig.write_text(_USERCONFIG_HEADER, encoding="utf-8")
        os.chdir(self.root)
        os.environ["TASK_DIR"] = str(self.root / "aitasks")
        self._reset_registry()

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()
        self._reset_registry()

    @staticmethod
    def _reset_registry() -> None:
        keybinding_registry._reset_for_tests()
        shortcuts_mixin.register_shared_bindings()
        shortcuts_mixin.refresh_label_case()

    def _override(self, toggle: str | None, help_key: str | None) -> None:
        if toggle:
            shortcut_persist.save_override("minimonitor", "toggle_key_hints", toggle)
        if help_key:
            shortcut_persist.save_override("minimonitor", "show_key_help", help_key)
        keybinding_registry.refresh_all()

    def _app(self, width: int = 40, collapsed: bool = False):
        return mm.MiniMonitorApp(
            session="probe-session",
            project_root=REPO_ROOT,
            refresh_seconds=999,
            target_width=width,
            key_hints_collapsed=collapsed,
        )

    def _boot(self, size, after, *, collapsed=False):
        """Boot the real app at ``size``, settle, and hand it to ``after``."""
        result: dict = {}

        async def runner():
            app = self._app(width=size[0], collapsed=collapsed)
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                await pilot.pause()
                await after(app, pilot, result)

        asyncio.run(runner())
        return result

    @staticmethod
    def _band(app) -> tuple[int, str]:
        """(rendered height, composited first row) of the hint band."""
        region = app.query_one("#mini-key-hints").region
        return region.height, _rows(app)[region.y]

    @staticmethod
    async def _settle(pilot, n: int = 3) -> None:
        for _ in range(n):
            await pilot.pause()


class TableParityTests(unittest.TestCase):
    """The table, the help entries and the bindings describe one key set."""

    def setUp(self) -> None:
        self.actions = {b.action for b in mm.MiniMonitorApp.BINDINGS}

    def _band_actions(self, lines) -> list[str]:
        return [a for _sep, segs in lines for seg in segs for a in seg.actions]

    def test_every_binding_is_in_the_full_band_exactly_once(self):
        listed = self._band_actions(mk.FULL_HINT_LINES)
        self.assertEqual(sorted(listed), sorted(set(listed)), "an action is listed twice")
        self.assertEqual(set(listed), self.actions)

    def test_every_binding_has_exactly_one_help_entry(self):
        helped = [a for e in mk.KEY_HELP for a in e.actions]
        self.assertEqual(sorted(helped), sorted(set(helped)), "an action is explained twice")
        self.assertEqual(set(helped), self.actions)
        for entry in mk.KEY_HELP:
            self.assertTrue(entry.description.strip(), f"empty help description: {entry.title}")
            self.assertTrue(
                bool(entry.actions) != bool(entry.literal_keys),
                f"{entry.title}: exactly one of actions / literal_keys",
            )

    def test_new_keys_are_on_the_first_line_and_in_the_collapsed_line(self):
        first = self._band_actions((mk.FULL_HINT_LINES[0],))
        collapsed = self._band_actions((mk.COLLAPSED_HINT_LINE,))
        for action in ("toggle_key_hints", "show_key_help"):
            self.assertIn(action, self.actions)
            self.assertIn(action, first, "short mode would clip it away")
            self.assertIn(action, collapsed)

    def test_default_band_lines_fit_the_companion_width(self):
        # `#mini-key-hints` carries `padding: 0 1`, leaving 38 of 40 columns.
        for line in mm.KEY_HINTS_TEXT.split("\n"):
            self.assertLessEqual(cell_len(line), 38, line)
        self.assertEqual(mm.KEY_HINTS_TEXT.count("\n") + 1, mm._KEY_HINTS_ROWS)
        self.assertEqual(mm.KEY_HINTS_COLLAPSED_TEXT, "x:keys H:help")

    def test_full_monitor_leaves_x_and_H_unbound(self):
        from monitor import monitor_app

        keys = {b.key for b in monitor_app.MonitorApp.BINDINGS}
        self.assertNotIn("x", keys)
        self.assertNotIn("H", keys)


class KeyDisplayTests(unittest.TestCase):
    def test_default_keys_render_as_their_names(self):
        for b in mm.MiniMonitorApp.BINDINGS:
            with self.subTest(key=b.key):
                self.assertEqual(mk.key_display(b.key), b.key)

    def test_modifier_chords_match_textual(self):
        app = App()
        for key in ("ctrl+y", "alt+y", "ctrl+shift+f12", "shift+tab", "question_mark"):
            with self.subTest(key=key):
                self.assertEqual(
                    mk.key_display(key), app.get_key_display(Binding(key, "a"))
                )
        self.assertEqual(mk.key_display("ctrl+y"), "^y")
        self.assertEqual(mk.key_display("question_mark"), "?")


class OverrideRenderAndDispatchTests(_Workspace):
    def test_single_key_overrides_render_and_dispatch(self):
        self._override("y", "Y")

        async def after(app, pilot, result):
            band = _plain(app.query_one("#mini-key-hints"))
            self.assertIn("y:hide", band)
            self.assertIn("Y:help", band)
            self.assertNotIn("x:hide", band)
            self.assertNotIn("H:help", band)
            await pilot.press("x")
            await self._settle(pilot)
            self.assertFalse(app._key_hints_collapsed, "the retired x still fires")
            await pilot.press("y")
            await self._settle(pilot)
            self.assertTrue(app._key_hints_collapsed)
            self.assertEqual(self._band(app)[0], 1)
            await pilot.press("Y")
            await self._settle(pilot)
            self.assertIsInstance(app.screen, mk.KeyHelpModal)
            footer = _plain(app.screen.query_one("#mm-help-footer"))
            self.assertIn("Y", footer)
            await pilot.press("Y")
            await self._settle(pilot)
            self.assertNotIsInstance(app.screen, mk.KeyHelpModal)

        self._boot((40, 30), after)

    def test_modifier_overrides_dispatch_both_ways(self):
        for pair in RUNG_TABLE:
            with self.subTest(pair=pair):
                self._reset_registry()
                self._override(*pair)
                toggle, help_key = pair

                async def after(app, pilot, result, toggle=toggle, help_key=help_key):
                    await pilot.press(toggle)
                    await self._settle(pilot)
                    self.assertTrue(app._key_hints_collapsed)
                    await pilot.press(toggle)
                    await self._settle(pilot)
                    self.assertFalse(app._key_hints_collapsed)
                    await pilot.press(help_key)
                    await self._settle(pilot)
                    self.assertIsInstance(app.screen, mk.KeyHelpModal)
                    await pilot.press(help_key)
                    await self._settle(pilot)
                    self.assertNotIsInstance(app.screen, mk.KeyHelpModal)

                self._boot((40, 30), after)


class CollapsedLineGeometryTests(_Workspace):
    """One row at every supported width, both ACTIVE keys on screen."""

    def test_rung_matrix(self):
        for pair, by_width in RUNG_TABLE.items():
            self._reset_registry()
            self._override(*pair)
            shown = tuple(mk.key_display(k) for k in pair)
            for width, rung in by_width.items():
                with self.subTest(pair=pair, width=width):

                    async def after(app, pilot, result):
                        result["band"] = self._band(app)

                    height, row = self._boot((width, 30), after, collapsed=True)["band"]
                    self.assertEqual(height, 1, f"{row!r}")
                    for disp in shown:
                        self.assertIn(disp, row, f"{disp} not on screen: {row!r}")
                    if rung == 1:
                        self.assertIn(f"{shown[0]}:keys", row)
                        self.assertIn(f"{shown[1]}:help", row)
                    else:
                        self.assertEqual(row.strip(), f"{shown[0]} {shown[1]}")

    def test_one_row_backstop_holds_overlong_chords(self):
        self._override(*LONG_PAIR)
        for width in (15, 18, 22, 24, 40):
            with self.subTest(width=width):

                async def after(app, pilot, result):
                    result["band"] = self._band(app)

                height, row = self._boot((width, 30), after, collapsed=True)["band"]
                self.assertEqual(height, 1, f"{row!r}")
        # At 40 both chords still fit with their labels.
        self.assertIn("shift+^f11:keys", row)
        self.assertIn("shift+^f12:help", row)

    def test_backstop_control_without_the_collapsed_rule_it_wraps(self):
        """CONTROL: the `.collapsed` CSS rule is what holds the overlong line."""
        self._override(*LONG_PAIR)

        async def after(app, pilot, result):
            hints = app.query_one("#mini-key-hints")
            self.assertEqual(hints.region.height, 1)
            hints.remove_class("collapsed")
            await self._settle(pilot)
            result["height"] = hints.region.height

        out = self._boot((18, 30), after, collapsed=True)
        self.assertGreater(out["height"], 1)

    def test_resize_re_picks_the_rung_both_ways(self):
        cases = (
            (("alt+y", "alt+u"), 18),
            (("ctrl+y", "ctrl+u"), 15),
        )
        for pair, narrow in cases:
            with self.subTest(pair=pair, narrow=narrow):
                self._reset_registry()
                self._override(*pair)
                a, b = (mk.key_display(k) for k in pair)

                async def after(app, pilot, result, narrow=narrow, a=a, b=b):
                    seen = []
                    for width in (40, narrow, 40):
                        await pilot.resize_terminal(width, 30)
                        await self._settle(pilot)
                        seen.append(self._band(app))
                    result["seen"] = seen
                    result["ab"] = (a, b)

                seen = self._boot((40, 30), after, collapsed=True)["seen"]
                self.assertEqual([h for h, _ in seen], [1, 1, 1])
                self.assertIn(f"{a}:keys", seen[0][1])
                self.assertEqual(seen[1][1].strip(), f"{a} {b}")
                self.assertIn(f"{a}:keys", seen[2][1])

    def test_full_band_measures_long_overrides_honestly(self):
        self._override(*LONG_PAIR)

        async def after(app, pilot, result):
            result["desired"] = app._key_hints_desired_rows()
            result["height"] = app.query_one("#mini-key-hints").region.height

        out = self._boot((22, 60), after)
        self.assertEqual(out["desired"], out["height"])


class HelpModalTests(_Workspace):
    def _open(self, size, after_open):
        async def after(app, pilot, result):
            await pilot.press("H")
            await self._settle(pilot)
            self.assertIsInstance(app.screen, mk.KeyHelpModal)
            await after_open(app, pilot, result)

        return self._boot(size, after)

    def test_fits_scrolls_and_lists_every_key(self):
        for size in ((24, 20), (40, 20)):
            with self.subTest(size=size):

                async def after_open(app, pilot, result):
                    screen = app.screen
                    dialog = screen.query_one("#mm-help-dialog").region
                    self.assertLessEqual(dialog.right, size[0])
                    self.assertLessEqual(dialog.bottom, size[1])
                    scroll = screen.query_one("#mm-help-scroll", VerticalScroll)
                    self.assertGreater(scroll.max_scroll_y, 0, "nothing to scroll")
                    entries = [_plain(w) for w in screen.query(".mm-help-entry")]
                    keymap = app._active_keymap()
                    for entry, text in zip(mk.KEY_HELP, entries):
                        self.assertTrue(
                            text.startswith(mk.help_entry_keys(entry, keymap)),
                            f"{entry.title}: {text[:30]!r}",
                        )
                    self.assertEqual(len(entries), len(mk.KEY_HELP))

                self._open(size, after_open)

    def test_escape_q_and_the_help_key_each_close_it(self):
        for key in ("escape", "q", "H"):
            with self.subTest(key=key):

                async def after_open(app, pilot, result, key=key):
                    await pilot.press(key)
                    await self._settle(pilot)
                    self.assertNotIsInstance(app.screen, mk.KeyHelpModal)
                    self.assertTrue(app.is_running, f"{key} quit the app")

                self._open((40, 20), after_open)

    def test_rebind_entry_points_at_the_shortcut_editor(self):
        entry = next(e for e in mk.KEY_HELP if "open_shortcuts_editor" in e.actions)
        self.assertIn("shortcut editor", entry.description)


class PersistenceTests(_Workspace):
    def test_round_trip_preserves_other_keys(self):
        shortcut_persist.save_override("minimonitor", "quit", "Q")
        userconfig_persist.set_minimonitor_key_hints_collapsed(True)
        self.assertTrue(userconfig_persist.get_minimonitor_key_hints_collapsed())
        text = self.userconfig.read_text(encoding="utf-8")
        self.assertIn("minimonitor_key_hints: collapsed", text)
        self.assertIn("email: tester@example.com", text)
        self.assertIn("quit: Q", text)
        userconfig_persist.set_minimonitor_key_hints_collapsed(False)
        self.assertFalse(userconfig_persist.get_minimonitor_key_hints_collapsed())
        self.assertIn("minimonitor_key_hints: full",
                      self.userconfig.read_text(encoding="utf-8"))

    def test_missing_unknown_and_malformed_read_as_full(self):
        self.userconfig.unlink()
        self.assertFalse(userconfig_persist.get_minimonitor_key_hints_collapsed())
        self.userconfig.write_text("minimonitor_key_hints: yes\n", encoding="utf-8")
        self.assertFalse(userconfig_persist.get_minimonitor_key_hints_collapsed())
        self.userconfig.write_text("email: [unclosed\n", encoding="utf-8")
        with mock.patch("sys.stderr"):
            self.assertFalse(userconfig_persist.get_minimonitor_key_hints_collapsed())

    def test_malformed_config_is_never_overwritten(self):
        raw = b"email: [unclosed\n"
        self.userconfig.write_bytes(raw)
        with self.assertRaises(userconfig_persist.MalformedUserConfigError):
            userconfig_persist.set_minimonitor_key_hints_collapsed(True)
        self.assertEqual(self.userconfig.read_bytes(), raw)

    def test_the_toggle_persists(self):
        async def after(app, pilot, result):
            await pilot.press("x")
            await self._settle(pilot)

        self._boot((40, 30), after)
        self.assertTrue(userconfig_persist.get_minimonitor_key_hints_collapsed())

    def test_toggle_with_a_malformed_config_still_collapses_and_warns(self):
        raw = b"email: [unclosed\n"

        async def after(app, pilot, result):
            self.userconfig.write_bytes(raw)
            notes = []
            app.notify = lambda msg, **kw: notes.append((msg, kw))
            await pilot.press("x")
            await self._settle(pilot)
            result["collapsed"] = app._key_hints_collapsed
            result["height"] = app.query_one("#mini-key-hints").region.height
            result["notes"] = notes

        out = self._boot((40, 30), after)
        self.assertTrue(out["collapsed"])
        self.assertEqual(out["height"], 1)
        self.assertEqual(len(out["notes"]), 1)
        self.assertEqual(out["notes"][0][1].get("severity"), "warning")
        self.assertEqual(self.userconfig.read_bytes(), raw)


class StartupTests(_Workspace):
    def test_collapsed_start_renders_one_row(self):
        async def after(app, pilot, result):
            result["band"] = self._band(app)

        height, row = self._boot((40, 30), after, collapsed=True)["band"]
        self.assertEqual(height, 1)
        self.assertEqual(row.strip(), "x:keys H:help")

    def test_main_passes_the_persisted_mode(self):
        for persisted in (True, False):
            with self.subTest(persisted=persisted):
                captured = {}

                class _Stub:
                    def __init__(self, **kwargs):
                        captured.update(kwargs)

                    def run(self):
                        captured["ran"] = True

                with mock.patch.object(mm, "MiniMonitorApp", _Stub), \
                        mock.patch.object(sys, "argv", ["minimonitor"]), \
                        mock.patch.object(mm, "_detect_tmux_session",
                                          return_value="probe"), \
                        mock.patch.object(
                            userconfig_persist,
                            "get_minimonitor_key_hints_collapsed",
                            return_value=persisted):
                    mm.main()
                self.assertTrue(captured.get("ran"))
                self.assertIs(captured["key_hints_collapsed"], persisted)


if __name__ == "__main__":
    unittest.main()
