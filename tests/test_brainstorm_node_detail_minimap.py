"""Pilot tests for NodeDetailModal's separate-pane section minimap (t946).

t946 refactored the modal's Proposal and Plan tabs from an inline minimap
(mounted inside the tab's VerticalScroll, so it scrolled out of view) to the
proven ``SectionViewerScreen`` layout: a fixed-width ``SectionMinimap``
sibling beside a scrollable ``SectionAwareMarkdown``. The minimap is composed
once and shown/hidden via ``display``; section navigation routes through
``SectionAwareMarkdown.request_scroll_to_section`` (exact rendered-heading
scroll, no overshoot) instead of the old ``estimate_section_y`` line-ratio math.

These tests spawn a host App that pushes the modal against a synthesized
brainstorm session directory, then assert against that layout. (The async
TOC-anchor scroll itself stays manual-verification — see the task's
``## Verification`` section.)
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
from textual.containers import Horizontal  # noqa: E402
from textual.widgets import Label  # noqa: E402

from brainstorm.brainstorm_app import NodeDetailModal  # noqa: E402
from section_viewer import SectionAwareMarkdown, SectionRow  # noqa: E402


PROPOSAL_WITH_SECTIONS = """\
# Proposal

<!-- section: intro -->
""" + "Background.\n" * 30 + """\
<!-- /section: intro -->

<!-- section: details -->
""" + "Specifics.\n" * 30 + """\
<!-- /section: details -->
"""

PLAN_NO_SECTIONS = "# Plan\n\nJust prose, no section markers.\n"


def _make_session(td: str, node_id: str, *, proposal: str, plan: str) -> Path:
    """Write a minimal brainstorm session with one node's proposal + plan."""
    session = Path(td)
    (session / "br_nodes").mkdir(parents=True, exist_ok=True)
    (session / "br_proposals").mkdir(parents=True, exist_ok=True)
    (session / "br_plans").mkdir(parents=True, exist_ok=True)
    (session / "br_nodes" / f"{node_id}.yaml").write_text(
        yaml.safe_dump({
            "description": "A test node",
            "parents": [],
            "created_at": "2026-06-09 10:00",
        }),
        encoding="utf-8",
    )
    (session / "br_proposals" / f"{node_id}.md").write_text(
        proposal, encoding="utf-8"
    )
    (session / "br_plans" / f"{node_id}_plan.md").write_text(
        plan, encoding="utf-8"
    )
    return session


class _HostApp(App):
    """Bare host that pushes NodeDetailModal on mount."""

    # NodeDetailModal.action_export reads these off the app.
    task_num = "0"

    def __init__(self, node_id: str, session_path: Path) -> None:
        super().__init__()
        self._node_id = node_id
        self._session_path = session_path

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(NodeDetailModal(self._node_id, self._session_path))


class _FakeMinimap:
    def __init__(self, minimap_id: str) -> None:
        self.id = minimap_id


class _FakeSectionSelected:
    """Stand-in for SectionMinimap.SectionSelected (handler reads .control.id,
    .section_name, and calls .stop())."""

    def __init__(self, minimap_id: str, section_name: str) -> None:
        self.control = _FakeMinimap(minimap_id)
        self.section_name = section_name
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class NodeDetailMinimapTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    async def _drive(self, node_id: str, session: Path):
        app = _HostApp(node_id, session)
        cm = app.run_test(size=(140, 48))
        pilot = await cm.__aenter__()
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        self.assertIsInstance(screen, NodeDetailModal)
        return app, pilot, screen, cm

    def test_tabs_use_fixed_minimap_beside_section_aware_markdown(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(
                    td, "n001_test",
                    proposal=PROPOSAL_WITH_SECTIONS, plan=PLAN_NO_SECTIONS,
                )
                app, pilot, screen, cm = await self._drive("n001_test", session)
                try:
                    # Content widgets are SectionAwareMarkdown, not bare Markdown.
                    prop_content = screen.query_one(
                        "#proposal_content", SectionAwareMarkdown
                    )
                    plan_content = screen.query_one(
                        "#plan_content", SectionAwareMarkdown
                    )
                    # ...sitting inside the new Horizontal panes beside a minimap.
                    self.assertIsInstance(
                        screen.query_one("#proposal_pane"), Horizontal
                    )
                    self.assertIsInstance(
                        screen.query_one("#plan_pane"), Horizontal
                    )
                    self.assertIs(prop_content.parent, screen.query_one("#proposal_pane"))
                    self.assertIs(plan_content.parent, screen.query_one("#plan_pane"))
                    # The old inline scroll wrappers are gone.
                    self.assertEqual(len(list(screen.query("#proposal_scroll"))), 0)
                    self.assertEqual(len(list(screen.query("#plan_scroll"))), 0)
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_sectioned_proposal_shows_minimap_rows(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(
                    td, "n001_test",
                    proposal=PROPOSAL_WITH_SECTIONS, plan=PLAN_NO_SECTIONS,
                )
                app, pilot, screen, cm = await self._drive("n001_test", session)
                try:
                    prop_minimap = screen.query_one("#proposal_minimap")
                    self.assertTrue(prop_minimap.display)
                    rows = list(prop_minimap.query(SectionRow))
                    self.assertEqual(
                        [r.section_name for r in rows], ["intro", "details"]
                    )
                    # Plan has no section markers → its minimap is hidden.
                    plan_minimap = screen.query_one("#plan_minimap")
                    self.assertFalse(plan_minimap.display)
                    self.assertEqual(
                        len(list(plan_minimap.query(SectionRow))), 0
                    )
                    self.assertIsNone(screen._plan_parsed)
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_section_selected_delegates_to_request_scroll(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(
                    td, "n001_test",
                    proposal=PROPOSAL_WITH_SECTIONS, plan=PLAN_NO_SECTIONS,
                )
                app, pilot, screen, cm = await self._drive("n001_test", session)
                try:
                    event = _FakeSectionSelected("proposal_minimap", "details")
                    screen.on_section_minimap_section_selected(event)
                    # Delegated to the proposal content's request_scroll_to_section,
                    # which records the active scroll target (no estimate_section_y
                    # math, no overshoot correction).
                    prop_content = screen.query_one(
                        "#proposal_content", SectionAwareMarkdown
                    )
                    self.assertEqual(
                        prop_content._active_scroll_section, "details"
                    )
                    self.assertTrue(event.stopped)
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
