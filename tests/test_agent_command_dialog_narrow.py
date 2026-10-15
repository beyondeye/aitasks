"""Tests for AgentCommandScreen narrow mode (t1012, t2013).

The minimonitor companion pane is ~40 cols wide. Pressing `n` (pick next
sibling) eventually pushes AgentCommandScreen ("Pick Task t<N>"), which in its
default 80%-wide layout overflowed the pane (truncated buttons, clipped command
text, cut-off Select boxes). `narrow=True` widens the dialog and stacks the
horizontal rows vertically so every control fits.

t2013 adds the vertical axis: at real minimonitor pane sizes (31-40 cols x 44
rows) the pick dialog's Run / Cancel sat below the dialog's bottom edge and were
clipped. The narrow layout is now compact enough to show them on open, and the
dialog body scrolls (a focused button is scrolled into view) when the content
still cannot fit. The wide dialog must render exactly as before.

Mirrors tests/test_kill_confirm_dialog.py::test_buttons_fit_inside_narrow_dialog
— drive the screen with a small terminal and assert every control's region sits
within the dialog's region.

Run: python3 -m pytest tests/test_agent_command_dialog_narrow.py -v
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Button, Input, Label, Select, TabbedContent  # noqa: E402

import agent_command_screen as acs  # noqa: E402
import keybinding_registry  # noqa: E402
import shortcuts_mixin  # noqa: E402
from agent_command_screen import AgentCommandScreen  # noqa: E402
from agent_launch_utils import TmuxLaunchConfig  # noqa: E402

_SESSIONS = ["aitasks", "other"]
_WINDOWS = [("0", "monitor"), ("1", "board")]
_TMUX_DEFAULTS = {
    "default_session": "aitasks",
    "default_split": "horizontal",
    "prefer_tmux": False,
    "git_tui": "",
    "syncer_autostart": False,
}

_TMUX_ACTIONS = ("btn_run_tmux", "btn_tmux_cancel")
_DIRECT_ACTIONS = (
    "btn_copy_prompt", "btn_copy_command", "btn_run_terminal", "btn_cancel",
)
_ACTIONS = {"tab_tmux": _TMUX_ACTIONS, "tab_direct": _DIRECT_ACTIONS}

# Real minimonitor panes measure 31-40 cols x 44 rows (t2013).
_PANE_SIZES = ((31, 44), (35, 44), (40, 44))
# Short enough that the tallest state cannot fit, so it must scroll.
_SHORT_PANE = (40, 30)

# Wide-mode regions (x, y, width, height) at 120x40, captured from the pre-t2013
# code (Textual 8.2.x) under this file's isolated environment. Every t2013 rule
# is scoped under `AgentCommandScreen.narrow`, so these must not move.
# Regenerate only for a deliberate wide-mode layout change.
_WIDE_SIZE = (120, 40)
_WIDE_HEADER = {
    "agent_cmd_dialog": (0, 0, 96, 36),
    "agent_cmd_title": (3, 2, 14, 2),
    "profile_row": (3, 4, 90, 3),
    "btn_edit_profile": (19, 4, 10, 3),
    "agent_row": (3, 8, 90, 3),
    "btn_change_agent": (31, 8, 10, 3),
    "agent_cmd_input": (3, 13, 90, 3),
    "agent_cmd_tabs": (3, 17, 90, 20),
}
_WIDE_GOLDEN = {
    "tab_tmux": {
        **_WIDE_HEADER,
        "tmux_session_select": (15, 19, 78, 3),
        "tmux_window_select": (15, 23, 78, 3),
        "tmux_new_window_input": (15, 27, 78, 3),
        "btn_run_tmux": (31, 31, 16, 3),
        "btn_tmux_cancel": (48, 31, 16, 3),
    },
    "tab_direct": {
        **_WIDE_HEADER,
        "agent_cmd_prompt_label": (3, 20, 75, 1),
        "btn_copy_prompt": (78, 20, 15, 3),
        "btn_copy_command": (21, 24, 16, 3),
        "btn_run_terminal": (38, 24, 19, 3),
        "btn_cancel": (58, 24, 16, 3),
    },
}


def _isolate(test: unittest.TestCase) -> None:
    """Pin every ambient input the dialog's layout reads, for one test.

    Without this the active tab follows the runner's own `TMUX`, the tmux rows
    follow the live tmux server, and button labels (hence widths) follow the
    developer's userconfig.yaml shortcut overrides.
    """
    stack = ExitStack()
    test.addCleanup(stack.close)
    stack.enter_context(
        mock.patch.dict(os.environ, {"TMUX": "/tmp/fake-tmux,1,0"})
    )
    for name, value in (
        ("is_tmux_available", lambda: True),
        ("get_tmux_sessions", lambda: list(_SESSIONS)),
        ("get_tmux_windows", lambda session: list(_WINDOWS)),
        ("load_tmux_defaults", lambda root: dict(_TMUX_DEFAULTS)),
        # It globs profiles/local/ relative to cwd — never delete repo files.
        ("_prune_stale_skillrun_overrides", lambda: None),
    ):
        stack.enter_context(mock.patch.object(acs, name, value))
    for memory in (
        AgentCommandScreen._previous_agent_override,
        AgentCommandScreen._last_session_by_project,
        AgentCommandScreen._last_window_by_project,
    ):
        stack.enter_context(mock.patch.dict(memory, clear=True))
    stack.enter_context(
        mock.patch.object(keybinding_registry, "_OVERRIDES_CACHE", {})
    )
    stack.enter_context(
        mock.patch.object(shortcuts_mixin, "_LABEL_CASE_CACHE", True)
    )


class _DialogHost(App):
    def __init__(self, narrow: bool = True, shadow: bool = False) -> None:
        super().__init__()
        self._narrow = narrow
        self._shadow = shadow
        self.results: list = []

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        if self._shadow:
            # Mirrors minimonitor's Shift+E shadow launch: no skill_name, so
            # no Profile row.
            screen = AgentCommandScreen(
                "Shadow (pick agent)",
                "claude --model claude-opus-4-8 '/aitask-shadow %3 5_5'",
                "/aitask-shadow %3 5_5",
                project_root=REPO_ROOT,
                operation="shadow",
                operation_args=["%3", "5_5"],
                default_agent_string="claudecode/opus4_8",
                narrow=self._narrow,
            )
        else:
            screen = AgentCommandScreen(
                title="Pick Task t5_5",
                full_command="claude --model claude-opus-4-8 '/aitask-pick 5_5'",
                prompt_str="/aitask-pick 5_5",
                default_window_name="agent-pick-5_5",
                project_root=REPO_ROOT,
                operation="pick",
                operation_args=["5_5"],
                default_agent_string="claudecode/opus4_8",
                skill_name="pick",
                default_profile="fast",
                narrow=self._narrow,
            )
        self.push_screen(screen, self.results.append)


async def _settle(pilot, rounds: int = 4) -> None:
    for _ in range(rounds):
        await pilot.pause()


async def _show_tab(app: App, pilot, tab: str) -> None:
    app.screen.query_one("#agent_cmd_tabs", TabbedContent).active = tab
    await _settle(pilot)


async def _enter_tallest_state(app: App, pilot) -> None:
    """Profile row + (U)se previous + the new-session row, all at once.

    The new-session row is shown the way a user reaches it after the dialog
    opened — choosing "+ Create new session" — since that growth is what used
    to push the buttons off a dialog that fitted on open.
    """
    app.screen.query_one("#tmux_session_select", Select).value = (
        acs._NEW_SESSION_SENTINEL
    )
    await _settle(pilot)


class AgentCommandDialogNarrowTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def _run(self, coro):
        return asyncio.run(coro)

    def _assert_inside_dialog(self, screen, widget_id, size, where=""):
        """`#widget_id` is displayed fully inside the dialog's content area
        (border, padding and scrollbar excluded) and inside the screen."""
        inner = screen.query_one("#agent_cmd_dialog").scrollable_content_region
        region = screen.query_one(f"#{widget_id}").region
        ctx = f"{where} #{widget_id} {region} vs dialog content {inner}"
        self.assertTrue(region.width and region.height, f"not displayed: {ctx}")
        self.assertGreaterEqual(region.y, inner.y, f"top clipped: {ctx}")
        self.assertLessEqual(region.bottom, inner.bottom, f"bottom clipped: {ctx}")
        self.assertGreaterEqual(region.x, inner.x, f"left clipped: {ctx}")
        self.assertLessEqual(region.right, inner.right, f"right clipped: {ctx}")
        self.assertGreaterEqual(region.y, 0, f"above the screen: {ctx}")
        self.assertLessEqual(region.bottom, size[1], f"below the screen: {ctx}")

    def test_narrow_class_applied(self):
        async def runner():
            app = _DialogHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                # The `narrow` class is added to the screen itself (the CSS
                # selector is `AgentCommandScreen.narrow #agent_cmd_dialog`).
                self.assertIsInstance(app.screen, AgentCommandScreen)
                self.assertIn("narrow", app.screen.classes)

        self._run(runner())

    def test_default_is_not_narrow(self):
        async def runner():
            app = _DialogHost(narrow=False)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, AgentCommandScreen)
                self.assertNotIn("narrow", app.screen.classes)

        self._run(runner())

    def test_controls_fit_inside_narrow_dialog(self):
        """Every button/input/select renders fully within the dialog at 40 cols."""
        async def runner():
            app = _DialogHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()

                dialog = app.screen.query_one("#agent_cmd_dialog")
                dialog_left = dialog.region.x
                dialog_right = dialog.region.x + dialog.region.width

                controls = [
                    w
                    for w in app.screen.query("Button, Input, Select")
                    if isinstance(w, (Button, Input, Select))
                ]
                # The dialog always has at least the command Input and the
                # Direct-tab buttons; guard against a query that silently
                # returns nothing.
                self.assertGreater(len(controls), 0)
                for widget in controls:
                    # Skip widgets that are not currently displayed (e.g. the
                    # inactive tab's content or hidden new-session rows).
                    if widget.region.width == 0 and widget.region.height == 0:
                        continue
                    left = widget.region.x
                    right = widget.region.x + widget.region.width
                    self.assertGreaterEqual(
                        left, dialog_left,
                        f"{widget!r} left {left} < dialog left {dialog_left}",
                    )
                    self.assertLessEqual(
                        right, dialog_right,
                        f"{widget!r} right {right} > dialog right {dialog_right}",
                    )

        self._run(runner())

    def test_action_buttons_fit_vertically_on_open(self):
        """At real minimonitor pane sizes every action button is fully visible
        the moment the dialog opens — pick (with its Profile row) and shadow
        (without), on both tabs — with no scrolling."""
        async def runner(shadow, size, tab):
            app = _DialogHost(shadow=shadow)
            async with app.run_test(size=size) as pilot:
                await _settle(pilot)
                screen = app.screen
                # TMUX is pinned, so the dialog opens on its tmux tab.
                tabs = screen.query_one("#agent_cmd_tabs", TabbedContent)
                self.assertEqual(tabs.active, "tab_tmux")
                if tab != "tab_tmux":
                    await _show_tab(app, pilot, tab)
                where = f"{'shadow' if shadow else 'pick'} {size} {tab}"
                self.assertEqual(
                    screen.query_one("#agent_cmd_dialog").scroll_y, 0, where,
                )
                for button_id in _ACTIONS[tab]:
                    self._assert_inside_dialog(screen, button_id, size, where)

        for shadow in (False, True):
            for size in _PANE_SIZES:
                for tab in ("tab_tmux", "tab_direct"):
                    with self.subTest(shadow=shadow, size=size, tab=tab):
                        self._run(runner(shadow, size, tab))

    def test_action_buttons_fit_vertically_without_tmux(self):
        """Without tmux there are no tabs: the Direct content sits directly in
        the dialog, and its buttons fit on open too."""
        async def runner(size):
            app = _DialogHost()
            async with app.run_test(size=size) as pilot:
                await _settle(pilot)
                screen = app.screen
                self.assertEqual(len(screen.query(TabbedContent)), 0)
                for button_id in _DIRECT_ACTIONS:
                    self._assert_inside_dialog(screen, button_id, size, "no tmux")

        with mock.patch.object(acs, "is_tmux_available", lambda: False):
            for size in _PANE_SIZES:
                with self.subTest(size=size):
                    self._run(runner(size))

    def test_tab_content_has_no_filler_rows(self):
        """The tab content ends at its last action button. A `1fr` content
        container used to fill the whole dialog with blank rows — dead space
        that a scrollable dialog would make the user scroll through."""
        async def runner(tab, container_id, last_id):
            app = _DialogHost()
            async with app.run_test(size=(40, 44)) as pilot:
                await _settle(pilot)
                if tab != "tab_tmux":
                    await _show_tab(app, pilot, tab)
                screen = app.screen
                container = screen.query_one(f"#{container_id}").region
                last = screen.query_one(f"#{last_id}").region
                self.assertEqual(
                    container.bottom, last.bottom,
                    f"#{container_id} {container} vs #{last_id} {last}",
                )

        for tab, container_id, last_id in (
            ("tab_tmux", "tmux_content", "btn_tmux_cancel"),
            ("tab_direct", "direct_content", "btn_cancel"),
        ):
            with self.subTest(tab=tab):
                self._run(runner(tab, container_id, last_id))

    def test_tallest_state_buttons_reachable(self):
        """With the Profile row, (U)se previous and the new-session row all
        shown in a short pane the content cannot fit; the dialog scrolls and
        focusing each action button brings it fully into view."""
        async def runner(tab):
            AgentCommandScreen._previous_agent_override["pick"] = "codex/gpt5_codex"
            app = _DialogHost()
            async with app.run_test(size=_SHORT_PANE) as pilot:
                await _settle(pilot)
                await _enter_tallest_state(app, pilot)
                screen = app.screen
                # The tallest combination is really on screen...
                shown = ["profile_row", "btn_use_last_agent", "tmux_new_session_row"]
                for widget_id in shown:
                    region = screen.query_one(f"#{widget_id}").region
                    self.assertTrue(region.height, f"#{widget_id} not shown")
                if tab != "tab_tmux":
                    await _show_tab(app, pilot, tab)
                # ...and it overflows, so reachability is what is under test.
                dialog = screen.query_one("#agent_cmd_dialog")
                self.assertGreater(dialog.max_scroll_y, 0, f"no overflow on {tab}")
                for button_id in _ACTIONS[tab]:
                    screen.query_one(f"#{button_id}", Button).focus()
                    await _settle(pilot)
                    self._assert_inside_dialog(
                        screen, button_id, _SHORT_PANE, f"focused, {tab}",
                    )

        for tab in ("tab_tmux", "tab_direct"):
            with self.subTest(tab=tab):
                self._run(runner(tab))

    def test_keys_work_in_scrolled_narrow_dialog(self):
        """`r` and Escape keep working when the dialog overflows and nothing is
        focused: `r` launches into the new session, Escape cancels."""
        async def runner(key):
            AgentCommandScreen._previous_agent_override["pick"] = "codex/gpt5_codex"
            app = _DialogHost()
            async with app.run_test(size=_SHORT_PANE) as pilot:
                await _settle(pilot)
                await _enter_tallest_state(app, pilot)
                screen = app.screen
                dialog = screen.query_one("#agent_cmd_dialog")
                self.assertGreater(dialog.max_scroll_y, 0)
                screen.set_focus(None)
                await pilot.press(key)
                await _settle(pilot)
                self.assertNotIsInstance(app.screen, AgentCommandScreen)
                return app.results

        results = self._run(runner("r"))
        self.assertEqual(len(results), 1)
        config = results[0]
        self.assertIsInstance(config, TmuxLaunchConfig)
        self.assertTrue(config.new_session)
        self.assertEqual(config.session, "aitasks")
        self.assertTrue(config.new_window)
        self.assertEqual(config.window, "agent-pick-5_5")

        self.assertEqual(self._run(runner("escape")), [None])

    def test_wide_layout_unchanged(self):
        """The wide dialog (board, monitor, codebrowser, ...) renders exactly
        as before t2013, on both tabs."""
        async def runner(tab):
            app = _DialogHost(narrow=False)
            async with app.run_test(size=_WIDE_SIZE) as pilot:
                await _settle(pilot)
                if tab != "tab_tmux":
                    await _show_tab(app, pilot, tab)
                got = {}
                for widget_id in _WIDE_GOLDEN[tab]:
                    r = app.screen.query_one(f"#{widget_id}").region
                    got[widget_id] = (r.x, r.y, r.width, r.height)
                return got

        for tab, expected in _WIDE_GOLDEN.items():
            with self.subTest(tab=tab):
                self.assertEqual(self._run(runner(tab)), expected)


if __name__ == "__main__":
    unittest.main()
