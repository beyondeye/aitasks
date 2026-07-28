"""Tests for AgentCommandScreen's opening-window debounce (t1279).

A host that opens this dialog with a key the dialog itself binds (the board's
By-Trail `R`, which lands on the dialog's own `R -> run`) passes that key as
`debounce_key`. An immediate repeat is then swallowed for
OPENING_DEBOUNCE_SECONDS after the dialog is first painted, so a double-tap
cannot confirm a dialog the user has not read yet.

Everything here is deterministic: `agent_command_screen._monotonic` is patched
with a fake clock the tests advance explicitly, so no test sleeps.

Run: python3 -m pytest tests/test_agent_command_open_debounce.py -v
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.keys import _character_to_key  # noqa: E402
from textual.widgets import Button, Input, Label, Select  # noqa: E402

import agent_command_screen as acs  # noqa: E402
from agent_command_screen import AgentCommandScreen  # noqa: E402

WINDOW = acs.OPENING_DEBOUNCE_SECONDS


class FakeClock:
    """Monotonic-clock stand-in the tests drive by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _DialogHost(App):
    """Plain App that pushes the real AgentCommandScreen and keeps its result."""

    def __init__(self, debounce_key: str = "") -> None:
        super().__init__()
        self._debounce_key = debounce_key
        self.results: list = []

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            AgentCommandScreen(
                title="Implementation Trail",
                full_command="claude --model claude-opus-5 '/aitask-trail --refresh art:demo'",
                prompt_str="/aitask-trail --refresh art:demo",
                default_window_name="agent-trail-demo",
                project_root=REPO_ROOT,
                operation="trail",
                operation_args=["--refresh", "art:demo"],
                default_agent_string="claudecode/opus5",
                skill_name="trail",
                debounce_key=self._debounce_key,
            ),
            self.results.append,
        )


def _tmux_patches(available: bool, sessions=("work",), on_sessions=None):
    """Pin the tmux surface so the dialog's shape never depends on the host."""
    def _sessions():
        if on_sessions is not None:
            on_sessions()
        return list(sessions)

    return [
        patch.object(acs, "is_tmux_available", lambda: available),
        patch.object(acs, "get_tmux_sessions", _sessions),
        patch.object(acs, "get_tmux_windows", lambda session: [("0", "main")]),
        patch.object(acs, "load_tmux_defaults", lambda root: {
            "default_split": "vertical",
            "default_session": "work",
            "prefer_tmux": available,
        }),
    ]


class OpeningDebounceTests(unittest.TestCase):
    """The mechanism, driven through real key dispatch."""

    def _run(self, coro):
        return asyncio.run(coro)

    def _drive(self, runner, *, debounce_key="R", tmux=False, on_sessions=None):
        """Run `runner(app, pilot, clock)` with the clock and tmux surface pinned."""
        clock = FakeClock()

        async def go():
            app = _DialogHost(debounce_key=debounce_key)
            stack = [patch.object(acs, "_monotonic", clock)]
            stack += _tmux_patches(tmux, on_sessions=on_sessions)
            for ctx in stack:
                ctx.start()
            try:
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    self.assertIsInstance(app.screen, AgentCommandScreen)
                    await runner(app, pilot, clock)
            finally:
                for ctx in reversed(stack):
                    ctx.stop()

        return self._run(go())

    # --- the reported failure ------------------------------------------------

    def test_immediate_repeat_is_swallowed(self):
        """A repeat of the launching key inside the window confirms nothing."""
        async def runner(app, pilot, clock):
            await pilot.press("R")
            await pilot.pause()
            self.assertIsInstance(app.screen, AgentCommandScreen)
            self.assertEqual(app.results, [])

        self._drive(runner)

    def test_key_runs_normally_after_the_window(self):
        """The guard is time-limited, not a permanent shortcut removal."""
        async def runner(app, pilot, clock):
            clock.advance(WINDOW + 0.05)
            await pilot.press("R")
            await pilot.pause()
            self.assertEqual(app.results, ["run"])

        self._drive(runner)

    def test_window_starts_at_first_paint_not_construction(self):
        """A slow mount must not consume the window before the dialog appears.

        Mirrors the real cost: on_mount calls get_tmux_sessions(), a tmux
        subprocess on the UI thread. Stamping in __init__ would leave the
        window already expired at first paint and the immediate `R` would
        launch — which is exactly the bug this task fixes.
        """
        clock_ref = {}

        def slow_sessions():
            clock_ref["clock"].advance(WINDOW * 10)

        def runner_factory():
            async def runner(app, pilot, clock):
                # The mount-time subprocess burned far more than the window...
                self.assertGreater(clock.now, 1000.0 + WINDOW)
                # ...yet the first repeat after the dialog appears is still inert.
                await pilot.press("R")
                await pilot.pause()
                self.assertIsInstance(app.screen, AgentCommandScreen)
                self.assertEqual(app.results, [])
            return runner

        clock = FakeClock()
        clock_ref["clock"] = clock

        async def go():
            app = _DialogHost(debounce_key="R")
            stack = [patch.object(acs, "_monotonic", clock)]
            stack += _tmux_patches(True, on_sessions=slow_sessions)
            for ctx in stack:
                ctx.start()
            try:
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    await runner_factory()(app, pilot, clock)
            finally:
                for ctx in reversed(stack):
                    ctx.stop()

        self._run(go())

    # --- what stays available throughout the window --------------------------

    def test_case_sibling_runs_immediately(self):
        """Only the configured key is suppressed — `r` still runs."""
        async def runner(app, pilot, clock):
            await pilot.press("r")
            await pilot.pause()
            self.assertEqual(app.results, ["run"])

        self._drive(runner)

    def test_enter_on_focused_run_button_runs_immediately(self):
        async def runner(app, pilot, clock):
            app.screen.query_one("#btn_run_terminal", Button).focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(app.results, ["run"])

        self._drive(runner)

    def test_clicking_run_button_runs_immediately(self):
        async def runner(app, pilot, clock):
            await pilot.click("#btn_run_terminal")
            await pilot.pause()
            self.assertEqual(app.results, ["run"])

        self._drive(runner)

    # --- guard placement -----------------------------------------------------

    def test_suppressed_with_tmux_select_focused(self):
        """Guard must sit ABOVE the Input/Select early-return in on_key.

        A collapsed Select defines neither _on_key nor check_consume_key, so
        the key bubbles to App._on_key and fires the `R -> run` binding. This
        test fails if the guard is ever moved below that early-return.
        """
        async def runner(app, pilot, clock):
            app.screen.query_one("#tmux_session_select", Select).focus()
            await pilot.pause()
            await pilot.press("R")
            await pilot.pause()
            self.assertIsInstance(app.screen, AgentCommandScreen)
            self.assertEqual(app.results, [])

        self._drive(runner, tmux=True)

    def test_typing_the_key_into_the_command_input_still_works(self):
        """A deliberately focused field keeps receiving the character."""
        async def runner(app, pilot, clock):
            field = app.screen.query_one("#agent_cmd_input", Input)
            field.focus()
            await pilot.pause()
            await pilot.press("R")
            await pilot.pause()
            # Focus selects the whole command, so the keystroke replaces it —
            # what matters is that the character reached the field at all and
            # that it did not confirm the dialog.
            self.assertTrue(field.value.endswith("R"), field.value)
            self.assertEqual(app.results, [])

        self._drive(runner)

    # --- remapped keys -------------------------------------------------------

    def test_resolver_form_matches_the_delivered_event_key(self):
        """Keys are user-remappable, so the guard must normalise like Textual.

        resolve_key() returns the literal a user typed ("#"); event.key and
        BindingsMap use the normalised name ("number_sign"). `#` is the
        discriminating case — without _character_to_key the guard silently
        compares "#" against "number_sign" and never fires.
        """
        for literal in ("R", "#", "ctrl+r"):
            with self.subTest(key=literal):
                seen: list[str] = []

                async def runner(app, pilot, clock, seen=seen, literal=literal):
                    screen = app.screen
                    original = screen._in_opening_window

                    def recording(key: str) -> bool:
                        seen.append(key)
                        return original(key)

                    screen._in_opening_window = recording
                    await pilot.press(literal)
                    await pilot.pause()
                    self.assertTrue(seen, "the guard never saw a key event")
                    self.assertEqual(seen[0], screen._debounce_key)
                    self.assertEqual(app.results, [])

                self._drive(runner, debounce_key=literal)

    def test_normalisation_of_stored_key(self):
        screen = AgentCommandScreen(
            title="t", full_command="c", prompt_str="p", debounce_key="#")
        self.assertEqual(screen._debounce_key, _character_to_key("#"))
        self.assertEqual(screen._debounce_key, "number_sign")
        multi = AgentCommandScreen(
            title="t", full_command="c", prompt_str="p", debounce_key="ctrl+r")
        self.assertEqual(multi._debounce_key, "ctrl+r")

    # --- every other call site is untouched ----------------------------------

    def test_default_construction_runs_the_key_immediately(self):
        """debounce_key is opt-in: the other AgentCommandScreen hosts are unchanged."""
        async def runner(app, pilot, clock):
            await pilot.press("R")
            await pilot.pause()
            self.assertEqual(app.results, ["run"])

        self._drive(runner, debounce_key="")


if __name__ == "__main__":
    unittest.main()
