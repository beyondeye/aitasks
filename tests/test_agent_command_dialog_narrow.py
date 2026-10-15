"""Tests for AgentCommandScreen narrow mode (t1012, t2013) and the wide dialog's
short-terminal fallback (t2020).

The minimonitor companion pane is ~40 cols wide. Pressing `n` (pick next
sibling) eventually pushes AgentCommandScreen ("Pick Task t<N>"), which in its
default 80%-wide layout overflowed the pane (truncated buttons, clipped command
text, cut-off Select boxes). `narrow=True` widens the dialog and stacks the
horizontal rows vertically so every control fits.

t2013 adds the vertical axis: at real minimonitor pane sizes (31-40 cols x 44
rows) the pick dialog's Run / Cancel sat below the dialog's bottom edge and were
clipped. The narrow layout is now compact enough to show them on open, and the
dialog body scrolls (a focused button is scrolled into view) when the content
still cannot fit. t2013 left the wide dialog untouched.

t2020 gives the wide dialog (board, monitor, codebrowser, trails, brainstorm)
the same fallback: the tab content is sized to its content instead of padded to
a 20-row cap, and the dialog body scrolls on terminals shorter than about 40
rows, where Run / Cancel used to sit below the dialog's edge out of reach.

t2025: choosing "+ Create new session" used to hide the window-name row in both
modes — the window Select's set_options([]) posts a Changed(NULL) that reached
the hide branch after the row was shown — so the user could neither see nor
edit the window name the launch used.

t2027: on an existing session, choosing the window Select's blank entry hid
both the window-name row and the split row while the launch still opened a new
window under the hidden default name. The blank entry now shows the name row,
and the launch takes its name from that row's input.

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

# Wide-mode regions (x, y, width, height) at 120x40 under this file's isolated
# environment (Textual 8.2.x), captured after t2020. Relative to the t2013
# layout only the tab heights (20 -> 17 / 10) and the Direct-tab dialog height
# (36 -> 29) changed: the tab content is sized to its content instead of padded
# to the old 20-row cap, and every control is where it was. Regenerate only for
# a deliberate wide-mode layout change.
_WIDE_SIZE = (120, 40)
_WIDE_HEADER = {
    "agent_cmd_title": (3, 2, 14, 2),
    "profile_row": (3, 4, 90, 3),
    "btn_edit_profile": (19, 4, 10, 3),
    "agent_row": (3, 8, 90, 3),
    "btn_change_agent": (31, 8, 10, 3),
    "agent_cmd_input": (3, 13, 90, 3),
}
_WIDE_GOLDEN = {
    "tab_tmux": {
        **_WIDE_HEADER,
        "agent_cmd_dialog": (0, 0, 96, 36),
        "agent_cmd_tabs": (3, 17, 90, 17),
        "tmux_session_select": (15, 19, 78, 3),
        "tmux_window_select": (15, 23, 78, 3),
        "tmux_new_window_input": (15, 27, 78, 3),
        "btn_run_tmux": (31, 31, 16, 3),
        "btn_tmux_cancel": (48, 31, 16, 3),
    },
    "tab_direct": {
        **_WIDE_HEADER,
        "agent_cmd_dialog": (0, 0, 96, 29),
        "agent_cmd_tabs": (3, 17, 90, 10),
        "agent_cmd_prompt_label": (3, 20, 75, 1),
        "btn_copy_prompt": (78, 20, 15, 3),
        "btn_copy_command": (21, 24, 16, 3),
        "btn_run_terminal": (38, 24, 19, 3),
        "btn_cancel": (58, 24, 16, 3),
    },
}
# The same dialog in a host whose Screen is centered (board, trails,
# brainstorm). There the Direct-tab dialog, 7 rows shorter since t2020,
# re-centers, so every Direct control sits 3 rows lower than it did (dialog
# y=2 -> 5, Run in terminal y=26 -> 29) and switching tabs shifts the tab bar.
# That movement is the accepted cost of dropping the filler rows that clipped
# the buttons. The tmux tab is unchanged.
_CENTERED_GOLDEN = {
    "tab_tmux": {
        "agent_cmd_dialog": (12, 2, 96, 36),
        "agent_cmd_tabs": (15, 19, 90, 17),
        "btn_run_tmux": (43, 33, 16, 3),
        "btn_tmux_cancel": (60, 33, 16, 3),
    },
    "tab_direct": {
        "agent_cmd_dialog": (12, 5, 96, 29),
        "agent_cmd_tabs": (15, 22, 90, 10),
        "btn_copy_prompt": (90, 25, 15, 3),
        "btn_copy_command": (33, 29, 16, 3),
        "btn_run_terminal": (50, 29, 19, 3),
        "btn_cancel": (70, 29, 16, 3),
    },
}
# Wide terminals that clipped the tmux tab's Run / Cancel before t2020; the
# shortest also clips the Direct tab's buttons.
_WIDE_SHORT_SIZES = ((120, 38), (120, 34), (120, 30))


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
    def __init__(
        self,
        narrow: bool = True,
        shadow: bool = False,
        default_tmux_window: str | None = None,
    ) -> None:
        super().__init__()
        self._narrow = narrow
        self._shadow = shadow
        self._default_tmux_window = default_tmux_window
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
                default_tmux_window=self._default_tmux_window,
                skill_name="pick",
                default_profile="fast",
                narrow=self._narrow,
            )
        self.push_screen(screen, self.results.append)


class _CenteredDialogHost(_DialogHost):
    """A host whose Screen CSS centers pushed modals, as board, trails and
    brainstorm do (`Screen { align: center middle; }`). `_DialogHost` leaves
    the modal top-anchored, which hides a height change's re-centering."""

    CSS = "Screen { align: center middle; }"


async def _settle(pilot, rounds: int = 4) -> None:
    for _ in range(rounds):
        await pilot.pause()


async def _show_tab(app: App, pilot, tab: str) -> None:
    app.screen.query_one("#agent_cmd_tabs", TabbedContent).active = tab
    await _settle(pilot)


async def _enter_tallest_state(app: App, pilot) -> None:
    """Profile row + (U)se previous + the new-session and window-name rows,
    all at once.

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
        """The tab content ends at its last action button, in both modes. A
        `1fr` content container used to fill the dialog (narrow) or the 20-row
        tab cap (wide) with blank rows — dead space that a scrollable dialog
        would make the user scroll through."""
        async def runner(narrow, size, tab, container_id, last_id):
            app = _DialogHost(narrow=narrow)
            async with app.run_test(size=size) as pilot:
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

        for narrow, size in ((True, (40, 44)), (False, (120, 44))):
            for tab, container_id, last_id in (
                ("tab_tmux", "tmux_content", "btn_tmux_cancel"),
                ("tab_direct", "direct_content", "btn_cancel"),
            ):
                with self.subTest(narrow=narrow, tab=tab):
                    self._run(runner(narrow, size, tab, container_id, last_id))

    def test_tallest_state_buttons_reachable(self):
        """With the Profile row, (U)se previous and the new-session row all
        shown in a short pane (narrow) or short terminal (wide) the content
        cannot fit; the dialog scrolls and focusing each action button brings
        it fully into view."""
        async def runner(narrow, size, tab):
            AgentCommandScreen._previous_agent_override["pick"] = "codex/gpt5_codex"
            app = _DialogHost(narrow=narrow)
            async with app.run_test(size=size) as pilot:
                await _settle(pilot)
                await _enter_tallest_state(app, pilot)
                screen = app.screen
                # The tallest combination is really on screen...
                shown = [
                    "profile_row", "btn_use_last_agent",
                    "tmux_new_session_row", "tmux_new_window_row",
                ]
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
                        screen, button_id, size, f"focused, {tab}",
                    )

        for narrow, size in ((True, _SHORT_PANE), (False, (120, 30))):
            for tab in ("tab_tmux", "tab_direct"):
                with self.subTest(narrow=narrow, tab=tab):
                    self._run(runner(narrow, size, tab))

    def test_wide_buttons_reachable_on_short_terminal(self):
        """On a wide terminal shorter than the dialog's content, every action
        button is brought fully into view by focusing it, in a top-anchored
        and a centered host, on both tabs. Before t2020 the buttons sat below
        the dialog's edge with no way to scroll to them."""
        async def runner(host, size, tab):
            app = host(narrow=False)
            async with app.run_test(size=size) as pilot:
                await _settle(pilot)
                if tab != "tab_tmux":
                    await _show_tab(app, pilot, tab)
                screen = app.screen
                where = f"{host.__name__} {size} {tab}"
                if tab == "tab_tmux":
                    # Every size in the matrix really overflows on this tab, so
                    # reachability is what is under test.
                    dialog = screen.query_one("#agent_cmd_dialog")
                    self.assertGreater(dialog.max_scroll_y, 0, f"no overflow: {where}")
                for button_id in _ACTIONS[tab]:
                    screen.query_one(f"#{button_id}", Button).focus()
                    await _settle(pilot)
                    self._assert_inside_dialog(
                        screen, button_id, size, f"focused, {where}",
                    )

        for host in (_DialogHost, _CenteredDialogHost):
            for size in _WIDE_SHORT_SIZES:
                for tab in ("tab_tmux", "tab_direct"):
                    with self.subTest(host=host.__name__, size=size, tab=tab):
                        self._run(runner(host, size, tab))

    def test_keys_work_in_scrolled_dialog(self):
        """`r` and Escape keep working when the dialog overflows and nothing is
        focused, in both modes: `r` launches into the new session, Escape
        cancels. The scrollable dialog Container must not take the keys."""
        async def runner(narrow, size, key):
            AgentCommandScreen._previous_agent_override["pick"] = "codex/gpt5_codex"
            app = _DialogHost(narrow=narrow)
            async with app.run_test(size=size) as pilot:
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

        for narrow, size in ((True, _SHORT_PANE), (False, (120, 30))):
            with self.subTest(narrow=narrow, key="r"):
                results = self._run(runner(narrow, size, "r"))
                self.assertEqual(len(results), 1)
                config = results[0]
                self.assertIsInstance(config, TmuxLaunchConfig)
                self.assertTrue(config.new_session)
                self.assertEqual(config.session, "aitasks")
                self.assertTrue(config.new_window)
                self.assertEqual(config.window, "agent-pick-5_5")
            with self.subTest(narrow=narrow, key="escape"):
                self.assertEqual(self._run(runner(narrow, size, "escape")), [None])

    def _assert_window_rows(self, screen, name_row: bool, where: str) -> None:
        """The window-name row is displayed iff `name_row`; the split row is
        displayed exactly when it is not."""
        for widget_id, displayed in (
            ("tmux_new_window_row", name_row),
            ("tmux_split_row", not name_row),
        ):
            region = screen.query_one(f"#{widget_id}").region
            self.assertEqual(
                bool(region.width and region.height), displayed,
                f"{where}: #{widget_id} {region}",
            )

    def test_new_session_shows_window_name_row(self):
        """Choosing "+ Create new session" keeps the window-name row shown, in
        both modes and whether the window Select held the new-window default
        or an existing window. `m` reaches the input, the typed name is the
        one launched."""
        async def runner(narrow, size, prior):
            app = _DialogHost(narrow=narrow)
            async with app.run_test(size=size) as pilot:
                await _settle(pilot)
                screen = app.screen
                where = f"narrow={narrow} prior={prior}"
                if prior == "existing":
                    screen.query_one("#tmux_window_select", Select).value = "1"
                    await _settle(pilot)
                    self._assert_window_rows(screen, False, f"{where} before")
                await _enter_tallest_state(app, pilot)
                self._assert_window_rows(screen, True, where)
                screen.set_focus(None)
                await pilot.press("m")
                await _settle(pilot)
                name_input = screen.query_one("#tmux_new_window_input", Input)
                self.assertIs(app.focused, name_input, where)
                self._assert_inside_dialog(
                    screen, "tmux_new_window_input", size, where,
                )
                # The Input selects all on focus: `end` drops the selection,
                # ctrl+u deletes everything left of the cursor.
                await pilot.press("end", "ctrl+u", *"my-win")
                await _settle(pilot)
                self.assertEqual(name_input.value, "my-win", where)
                screen.set_focus(None)
                await pilot.press("r")
                await _settle(pilot)
                self.assertNotIsInstance(app.screen, AgentCommandScreen, where)
                return app.results

        for narrow, size in ((True, (40, 44)), (False, _WIDE_SIZE)):
            for prior in ("new", "existing"):
                with self.subTest(narrow=narrow, prior=prior):
                    results = self._run(runner(narrow, size, prior))
                    self.assertEqual(len(results), 1)
                    config = results[0]
                    self.assertIsInstance(config, TmuxLaunchConfig)
                    self.assertTrue(config.new_session)
                    self.assertEqual(config.session, "aitasks")
                    self.assertTrue(config.new_window)
                    self.assertEqual(config.window, "my-win")

    def test_switching_back_to_existing_session_follows_window_select(self):
        """After "+ Create new session", choosing an existing session hands the
        window rows back to the window Select: the new-window default shows
        the name row, an existing window shows the split row instead."""
        async def runner(narrow, size):
            app = _DialogHost(narrow=narrow)
            async with app.run_test(size=size) as pilot:
                await _settle(pilot)
                await _enter_tallest_state(app, pilot)
                screen = app.screen
                where = f"narrow={narrow}"
                screen.query_one("#tmux_session_select", Select).value = "other"
                await _settle(pilot)
                self.assertEqual(
                    screen.query_one("#tmux_window_select", Select).value,
                    acs._NEW_WINDOW_SENTINEL,
                    where,
                )
                self._assert_window_rows(screen, True, f"{where} new window")
                screen.query_one("#tmux_window_select", Select).value = "1"
                await _settle(pilot)
                self._assert_window_rows(screen, False, f"{where} window 1")

        for narrow, size in ((True, (40, 44)), (False, _WIDE_SIZE)):
            with self.subTest(narrow=narrow):
                self._run(runner(narrow, size))

    def test_blank_window_choice_shows_window_name_row(self):
        """On an existing session, choosing the window Select's blank entry
        launches a new window, so the window-name row shows (and the split row
        hides), whether the Select held the new-window default or an existing
        window. `m` reaches the input, the typed name is the one launched."""
        async def runner(narrow, size, prior):
            app = _DialogHost(narrow=narrow)
            async with app.run_test(size=size) as pilot:
                await _settle(pilot)
                screen = app.screen
                where = f"narrow={narrow} prior={prior}"
                win_select = screen.query_one("#tmux_window_select", Select)
                if prior == "existing":
                    win_select.value = "1"
                    await _settle(pilot)
                    self._assert_window_rows(screen, False, f"{where} before")
                # Choose the blank entry the way a user does: `w` focuses the
                # window Select, enter opens its overlay, the blank entry is
                # the overlay's first option.
                screen.set_focus(None)
                await pilot.press("w")
                await _settle(pilot)
                self.assertIs(app.focused, win_select, where)
                await pilot.press("enter", "home", "enter")
                await _settle(pilot)
                self.assertIs(win_select.value, Select.NULL, where)
                self._assert_window_rows(screen, True, where)
                name_input = screen.query_one("#tmux_new_window_input", Input)
                self.assertEqual(name_input.value, "agent-pick-5_5", where)
                screen.set_focus(None)
                await pilot.press("m")
                await _settle(pilot)
                self.assertIs(app.focused, name_input, where)
                self._assert_inside_dialog(
                    screen, "tmux_new_window_input", size, where,
                )
                # The Input selects all on focus: `end` drops the selection,
                # ctrl+u deletes everything left of the cursor.
                await pilot.press("end", "ctrl+u", *"my-win")
                await _settle(pilot)
                self.assertEqual(name_input.value, "my-win", where)
                screen.set_focus(None)
                await pilot.press("r")
                await _settle(pilot)
                self.assertNotIsInstance(app.screen, AgentCommandScreen, where)
                return app.results

        for narrow, size in ((True, (40, 44)), (False, _WIDE_SIZE)):
            for prior in ("new", "existing"):
                with self.subTest(narrow=narrow, prior=prior):
                    results = self._run(runner(narrow, size, prior))
                    self.assertEqual(len(results), 1)
                    config = results[0]
                    self.assertIsInstance(config, TmuxLaunchConfig)
                    self.assertFalse(config.new_session)
                    self.assertEqual(config.session, "aitasks")
                    self.assertTrue(config.new_window)
                    self.assertEqual(config.window, "my-win")

    def test_session_switch_keeps_existing_window_default(self):
        """A session switch whose window default is an existing window ends
        with the split row shown and launches into that window. Its
        set_options() posts a transient Changed(NULL), which shows the name
        row, before the Changed("1") that settles the rows."""
        async def runner(narrow, size):
            app = _DialogHost(narrow=narrow, default_tmux_window="1")
            async with app.run_test(size=size) as pilot:
                await _settle(pilot)
                screen = app.screen
                where = f"narrow={narrow}"
                win_select = screen.query_one("#tmux_window_select", Select)
                self.assertEqual(win_select.value, "1", f"{where} on open")
                self._assert_window_rows(screen, False, f"{where} on open")
                screen.query_one("#tmux_session_select", Select).value = "other"
                await _settle(pilot)
                self.assertEqual(win_select.value, "1", f"{where} switched")
                self._assert_window_rows(screen, False, f"{where} switched")
                screen.set_focus(None)
                await pilot.press("r")
                await _settle(pilot)
                self.assertNotIsInstance(app.screen, AgentCommandScreen, where)
                return app.results

        for narrow, size in ((True, (40, 44)), (False, _WIDE_SIZE)):
            with self.subTest(narrow=narrow):
                results = self._run(runner(narrow, size))
                self.assertEqual(len(results), 1)
                config = results[0]
                self.assertIsInstance(config, TmuxLaunchConfig)
                self.assertFalse(config.new_session)
                self.assertEqual(config.session, "other")
                self.assertFalse(config.new_window)
                self.assertEqual(config.window, "1")

    def _wide_regions(self, host, tab, widget_ids):
        async def runner():
            app = host(narrow=False)
            async with app.run_test(size=_WIDE_SIZE) as pilot:
                await _settle(pilot)
                if tab != "tab_tmux":
                    await _show_tab(app, pilot, tab)
                got = {}
                for widget_id in widget_ids:
                    r = app.screen.query_one(f"#{widget_id}").region
                    got[widget_id] = (r.x, r.y, r.width, r.height)
                return got

        return self._run(runner())

    def test_wide_layout_unchanged(self):
        """The wide dialog (board, monitor, codebrowser, ...) renders at the
        pinned regions on both tabs: the t2013 layout with content-sized tabs
        (t2020), every control where it was."""
        for tab, expected in _WIDE_GOLDEN.items():
            with self.subTest(tab=tab):
                self.assertEqual(
                    self._wide_regions(_DialogHost, tab, expected), expected,
                )

    def test_wide_layout_in_centered_host(self):
        """In a centered host the content-sized Direct-tab dialog re-centers,
        moving its controls 3 rows down; the tmux tab keeps its place. Pinned
        so the movement stays a deliberate, documented layout choice."""
        for tab, expected in _CENTERED_GOLDEN.items():
            with self.subTest(tab=tab):
                self.assertEqual(
                    self._wide_regions(_CenteredDialogHost, tab, expected),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
