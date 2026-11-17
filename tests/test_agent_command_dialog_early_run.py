"""Run during AgentCommandScreen's initial widget mount (t2323).

Use real Textual mounting/key dispatch, with tmux discovery mocked. The mount
hook deliberately requests Run before Select's own mount handler has applied
its initial value, making the reported race deterministic without sleeps.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual import events  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label, Select  # noqa: E402

import agent_command_screen as acs  # noqa: E402
from agent_command_screen import AgentCommandScreen, TmuxLaunchConfig  # noqa: E402


class _DialogHost(App):
    def __init__(self, **screen_kwargs):
        super().__init__()
        self.screen_kwargs = screen_kwargs
        self.results = []
        self.notify = Mock()

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(AgentCommandScreen(
            "Pick Task t2323", "codex '/aitask-pick 2323'",
            "/aitask-pick 2323", default_window_name="agent-pick-2323",
            project_root=REPO_ROOT, operation="pick", operation_args=["2323"],
            **self.screen_kwargs,
        ), self.results.append)


class EarlyRunTests(unittest.TestCase):
    def _drive(self, *, early=None, after=None, cancel=False, sessions=("lumen", "other"),
               **screen_kwargs):
        original_mount = AgentCommandScreen.on_mount
        observed = {}

        def mount(screen):
            if cancel:
                # Cancel after the children mount, before queued launch work.
                screen.call_after_refresh(screen.action_cancel)
            original_mount(screen)
            observed["screen"] = screen
            observed["initial_session"] = screen.query_one(
                "#tmux_session_select", Select).value
            if early:
                early(screen)
                observed["early_notifications"] = list(screen.app.notify.call_args_list)

        async def go():
            with ExitStack() as stack:
                stack.enter_context(patch.object(acs, "is_tmux_available", return_value=True))
                stack.enter_context(patch.object(acs, "get_tmux_sessions", return_value=list(sessions)))
                stack.enter_context(patch.object(acs, "get_tmux_windows", return_value=[("3", "work")]))
                stack.enter_context(patch.object(acs, "load_tmux_defaults", return_value={
                    "default_split": "horizontal", "default_session": "lumen",
                    "prefer_tmux": True,
                }))
                stack.enter_context(patch.object(AgentCommandScreen, "_last_session_by_project", {}))
                stack.enter_context(patch.object(AgentCommandScreen, "_last_window_by_project", {}))
                stack.enter_context(patch.object(AgentCommandScreen, "on_mount", mount))
                app = _DialogHost(**screen_kwargs)
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    if after:
                        await after(app, pilot)
                    await pilot.pause()
                observed["results"] = app.results
                observed["notifications"] = app.notify.call_args_list

        asyncio.run(go())
        return observed

    def _assert_launch(self, got, *, session="lumen", window="agent-pick-2323",
                       new_session=False, new_window=True):
        self.assertEqual(got["notifications"], [])
        self.assertEqual(len(got["results"]), 1)
        self.assertEqual(got["results"][0], TmuxLaunchConfig(
            session=session, window=window, new_session=new_session,
            new_window=new_window, split_direction="horizontal", cwd=str(REPO_ROOT),
        ))

    def test_run_before_select_mount_waits_for_values(self):
        got = self._drive(early=lambda screen: screen.action_run())
        self.assertIs(got["initial_session"], Select.NULL)
        self.assertEqual(got["early_notifications"], [])
        self._assert_launch(got)

    def test_first_frame_r_dispatch_launches(self):
        got = self._drive(early=lambda screen: screen.post_message(events.Key("r", "r")))
        self.assertIs(got["initial_session"], Select.NULL)
        self._assert_launch(got)

    def test_multiple_early_requests_launch_once(self):
        def early(screen):
            screen.action_run()
            screen.action_run()
            screen.run_tmux()  # The Run button uses this same path.

        self._assert_launch(self._drive(early=early))

    def test_early_run_keeps_existing_split_window(self):
        self._assert_launch(self._drive(
            early=lambda screen: screen.action_run(),
            default_tmux_session="other", default_tmux_window="3",
        ), session="other", window="3", new_window=False)

    def test_early_run_can_create_first_session(self):
        self._assert_launch(self._drive(
            early=lambda screen: screen.action_run(), sessions=(),
        ), new_session=True)

    def test_cancel_discards_pending_run(self):
        got = self._drive(early=lambda screen: screen.action_run(), cancel=True)
        self.assertEqual(got["notifications"], [])
        self.assertEqual(got["results"], [None])

    def test_settled_session_change_wins(self):
        async def after(app, pilot):
            app.screen.query_one("#tmux_session_select", Select).value = "other"
            await pilot.pause()
            await pilot.press("r")

        self._assert_launch(self._drive(after=after), session="other")

    def test_settled_blank_session_still_requires_selection(self):
        async def after(app, pilot):
            app.screen.query_one("#tmux_session_select", Select).clear()
            await pilot.pause()
            await pilot.press("r")

        got = self._drive(after=after)
        self.assertEqual(got["results"], [])
        self.assertEqual(len(got["notifications"]), 1)
        self.assertEqual(got["notifications"][0].args, ("Please select a session",))


if __name__ == "__main__":
    unittest.main()
