"""Pilot tests for OperationDetailScreen (t749_5).

Spawns a minimal host App that pushes the screen against a synthesized
brainstorm session directory (br_groups.yaml + fixture agent files), then
verifies the screen renders the expected title, tab structure, and Overview
content. Driving the screen via Pilot — rather than instantiating it bare —
matches the runtime path where ``compose()`` and the per-tab widgets only
materialize once mounted.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import yaml  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label, Static, TabbedContent, TabPane  # noqa: E402

from brainstorm.brainstorm_app import OperationDetailScreen  # noqa: E402


class _HostApp(App):
    """Bare host that pushes OperationDetailScreen on mount."""

    def __init__(self, group_name: str, session_path: Path) -> None:
        super().__init__()
        self._group_name = group_name
        self._session_path = session_path
        self.screen_pushed = False

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            OperationDetailScreen(self._group_name, self._session_path)
        )
        self.screen_pushed = True


def _write_groups(session: Path, groups: dict) -> None:
    (session / "br_groups.yaml").write_text(
        yaml.safe_dump({"groups": groups}), encoding="utf-8"
    )


def _write_agent_fixtures(session: Path, agent: str, *, input_md: str,
                          output_md: str = "", log_txt: str = "",
                          status: str = "Running",
                          agent_type: str = "explorer") -> None:
    (session / f"{agent}_input.md").write_text(input_md, encoding="utf-8")
    if output_md:
        (session / f"{agent}_output.md").write_text(
            output_md, encoding="utf-8"
        )
    if log_txt:
        (session / f"{agent}_log.txt").write_text(log_txt, encoding="utf-8")
    (session / f"{agent}_status.yaml").write_text(
        yaml.safe_dump({
            "agent_name": agent,
            "agent_type": agent_type,
            "status": status,
        }),
        encoding="utf-8",
    )


class OperationDetailScreenTests(unittest.TestCase):
    """End-to-end Pilot tests for the screen."""

    def _run(self, coro):
        return asyncio.run(coro)

    async def _drive(self, session: Path, group_name: str):
        """Run the host app to the point where the screen is mounted."""
        app = _HostApp(group_name, session)
        async with app.run_test(size=(140, 48)) as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            self.assertIsInstance(screen, OperationDetailScreen)
            return app, pilot, screen

    def test_renders_overview_and_two_agent_tabs(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = Path(td)
                _write_groups(session, {
                    "explore_001": {
                        "operation": "explore",
                        "agents": ["explorer_001a", "explorer_001b"],
                        "status": "Running",
                        "created_at": "2026-05-05 12:00",
                        "head_at_creation": "n000_init",
                        "nodes_created": ["n001_a", "n002_b"],
                    },
                })
                _write_agent_fixtures(
                    session, "explorer_001a",
                    input_md=(
                        "# Explorer Input\n\n"
                        "## Exploration Mandate\n"
                        "Go big or go home.\n"
                    ),
                    output_md="## Output\nproduced.\n",
                    log_txt="line1\nline2\n",
                )
                _write_agent_fixtures(
                    session, "explorer_001b",
                    input_md=(
                        "# Explorer Input\n\n"
                        "## Exploration Mandate\n"
                        "Same mandate copy.\n"
                    ),
                )

                app = _HostApp("explore_001", session)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    screen = app.screen
                    self.assertIsInstance(screen, OperationDetailScreen)

                    title_str = str(screen.query_one(
                        "#op_detail_title", Label
                    ).render())
                    self.assertIn("Operation: explore", title_str)
                    self.assertIn("explore_001", title_str)
                    self.assertIn("Running", title_str)

                    tabs = screen.query_one(TabbedContent)
                    panes = list(tabs.query(TabPane))
                    self.assertEqual(
                        len(panes), 3,
                        "expected Overview + 2 agent tabs",
                    )
                    pane_ids = sorted(p.id for p in panes)
                    self.assertEqual(
                        pane_ids,
                        sorted([
                            "op_overview",
                            "tab_agent_explorer_001a",
                            "tab_agent_explorer_001b",
                        ]),
                    )

                    overview = screen.query_one("#op_overview", TabPane)
                    overview_text = " ".join(
                        str(s.render()) for s in overview.query(Static)
                    )
                    self.assertIn("n000_init", overview_text)
                    self.assertIn("n001_a", overview_text)
                    self.assertIn("explorer_001a", overview_text)

                    await pilot.press("escape")
                    await pilot.pause()
                    self.assertNotIsInstance(app.screen, OperationDetailScreen)

        self._run(runner())

    def test_missing_group_shows_placeholder(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = Path(td)
                _write_groups(session, {})

                app = _HostApp("nope_001", session)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    screen = app.screen
                    self.assertIsInstance(screen, OperationDetailScreen)

                    placeholder = screen.query_one(
                        "#op_detail_missing", Label
                    )
                    self.assertIn(
                        "no group entry recorded",
                        str(placeholder.render()),
                    )
                    self.assertFalse(screen.query(TabbedContent))

        self._run(runner())

    def test_empty_agents_uses_input_pending_placeholder(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = Path(td)
                _write_groups(session, {
                    "bootstrap": {
                        "operation": "bootstrap",
                        "agents": [],
                        "status": "Waiting",
                        "created_at": "2026-05-05 11:00",
                        "head_at_creation": None,
                        "nodes_created": ["n000_init"],
                    },
                })

                app = _HostApp("bootstrap", session)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    screen = app.screen
                    overview = screen.query_one("#op_overview", TabPane)
                    overview_text = " ".join(
                        str(lbl.render()) for lbl in overview.query(Label)
                    )
                    self.assertIn(
                        "no agents registered yet",
                        overview_text,
                    )
                    tabs = screen.query_one(TabbedContent)
                    panes = list(tabs.query(TabPane))
                    self.assertEqual(len(panes), 1)
                    self.assertEqual(panes[0].id, "op_overview")

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
