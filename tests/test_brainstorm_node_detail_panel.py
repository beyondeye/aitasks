"""Tests for the extracted NodeDetailPanel widget + renderer (t983_1).

t983_1 (foundation child of the t983 brainstorm-TUI IA redesign) DRYs the three
node-detail renderings (Dashboard inline pane, Graph inline pane, and the
NodeDetailModal Metadata tab) onto a single module-level
``render_node_detail_widgets`` renderer wrapped in a reusable
``NodeDetailPanel`` widget.

Coverage:
- A headless unit test of ``render_node_detail_widgets`` (no App needed — the
  renderer depends only on ``session_path``).
- A pilot test driving ``NodeDetailPanel.update`` and asserting the mounted
  title + content.
- A pilot guard that the modal's Metadata tab now hosts a ``NodeDetailPanel``
  while the Proposal tab/minimap is untouched (the fold).
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
from textual.containers import Container  # noqa: E402
from textual.widgets import Label, Static  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    DimensionRow,
    NodeDetailModal,
    NodeDetailPanel,
    render_node_detail_widgets,
)


DIMS = {"requirements_perf": "fast", "component_storage": "sqlite"}


def _make_session(
    td: str, node_id: str, *, proposal: str = "# Proposal\n", dims: dict | None = None,
) -> Path:
    """Write a minimal brainstorm session with one node (+ optional dimensions)."""
    session = Path(td)
    (session / "br_nodes").mkdir(parents=True, exist_ok=True)
    (session / "br_proposals").mkdir(parents=True, exist_ok=True)
    node: dict = {
        "description": "A test node",
        "parents": [],
        "created_at": "2026-06-14 10:00",
    }
    if dims:
        node.update(dims)
    (session / "br_nodes" / f"{node_id}.yaml").write_text(
        yaml.safe_dump(node), encoding="utf-8"
    )
    (session / "br_proposals" / f"{node_id}.md").write_text(
        proposal, encoding="utf-8"
    )
    return session


def _text(widget) -> str:
    """Best-effort stringification of a widget's rendered text for substring
    checks (Textual's Content API exposes text via ``render()`` / ``content``)."""
    try:
        return str(widget.render())
    except Exception:
        return str(getattr(widget, "content", ""))


class RenderNodeDetailWidgetsTests(unittest.TestCase):
    """Headless unit tests of the module-level renderer (no App)."""

    def test_title_and_meta_fields(self):
        with tempfile.TemporaryDirectory() as td:
            session = _make_session(td, "n001_test", dims=DIMS)
            title, widgets = render_node_detail_widgets(session, "n001_test")

            self.assertEqual(title, "Node: n001_test")

            meta = [w for w in widgets if "meta_field" in w.classes]
            # Description + Parents + Created (at least).
            self.assertGreaterEqual(len(meta), 3)
            joined = "\n".join(_text(w) for w in meta)
            self.assertIn("Description:", joined)
            self.assertIn("A test node", joined)
            self.assertIn("Parents:", joined)
            self.assertIn("Created:", joined)

    def test_dimension_rows_for_each_dimension(self):
        with tempfile.TemporaryDirectory() as td:
            session = _make_session(td, "n001_test", dims=DIMS)
            _title, widgets = render_node_detail_widgets(session, "n001_test")

            rows = [w for w in widgets if isinstance(w, DimensionRow)]
            self.assertEqual(
                {r.dim_key for r in rows},
                {"requirements_perf", "component_storage"},
            )

    def test_no_dimension_rows_when_node_has_none(self):
        with tempfile.TemporaryDirectory() as td:
            session = _make_session(td, "n001_test")  # no dims
            _title, widgets = render_node_detail_widgets(session, "n001_test")
            self.assertEqual(
                [w for w in widgets if isinstance(w, DimensionRow)], []
            )

    def test_unreadable_node_returns_placeholder(self):
        with tempfile.TemporaryDirectory() as td:
            session = Path(td)  # empty — no br_nodes
            title, widgets = render_node_detail_widgets(session, "missing")
            self.assertEqual(title, "Node: missing")
            self.assertEqual(len(widgets), 1)


class _HostPanelApp(App):
    """Bare host that mounts a NodeDetailPanel and drives it on mount."""

    def __init__(self, session_path: Path, node_id: str) -> None:
        super().__init__()
        self._session_path = session_path
        self._node_id = node_id

    def compose(self) -> ComposeResult:
        yield NodeDetailPanel(
            self._session_path,
            title_id="t_title",
            info_id="t_info",
            id="t_panel",
        )

    def on_mount(self) -> None:
        self.query_one("#t_panel", NodeDetailPanel).update(self._node_id)


class _HostModalApp(App):
    """Bare host that pushes NodeDetailModal on mount (mirrors the minimap test)."""

    task_num = "0"  # NodeDetailModal.action_export reads this off the app.

    def __init__(self, node_id: str, session_path: Path) -> None:
        super().__init__()
        self._node_id = node_id
        self._session_path = session_path

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(NodeDetailModal(self._node_id, self._session_path))


class NodeDetailPanelPilotTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_panel_update_mounts_title_and_content(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test", dims=DIMS)
                app = _HostPanelApp(session, "n001_test")
                cm = app.run_test(size=(140, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await pilot.pause()
                try:
                    title = app.query_one("#t_title", Label)
                    self.assertEqual(_text(title), "Node: n001_test")

                    info = app.query_one("#t_info", Container)
                    children = list(info.children)
                    self.assertTrue(
                        any(isinstance(c, DimensionRow) for c in children)
                    )
                    self.assertTrue(
                        any("meta_field" in c.classes for c in children)
                    )
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_modal_metadata_tab_uses_shared_panel(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test", dims=DIMS)
                app = _HostModalApp("n001_test", session)
                cm = app.run_test(size=(140, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, NodeDetailModal)
                try:
                    # Metadata tab now hosts the shared NodeDetailPanel...
                    panel = screen.query_one("#modal_node_panel", NodeDetailPanel)
                    self.assertEqual(
                        _text(screen.query_one("#modal_node_title", Label)),
                        "Node: n001_test",
                    )
                    info = screen.query_one("#modal_node_info", Container)
                    self.assertTrue(
                        any(isinstance(c, DimensionRow) for c in info.children)
                    )
                    # ...and the old plain-text metadata Static is gone.
                    self.assertEqual(
                        len(list(screen.query("#metadata_content"))), 0
                    )
                    # The Proposal tab is untouched by the fold.
                    self.assertEqual(
                        len(list(screen.query("#proposal_content"))), 1
                    )
                    self.assertIsNotNone(panel)
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())


class _SmokeApp(BrainstormApp):
    """BrainstormApp with the session-loading on_mount skipped.

    Isolates the dashboard/graph ``compose`` (the part t983_1 changed) plus the
    detail/brief handlers, without dragging in the full session-load pipeline
    (DAG load, agent scans, polling timers). ``session_path`` is repointed at a
    fixture before mount so the composed panels render real node data.
    """

    def on_mount(self) -> None:  # noqa: D401 - intentionally a no-op
        pass


class BrainstormAppComposeSmokeTests(unittest.TestCase):
    """Full-app compose smoke: the real BrainstormApp mounts the panels and the
    detail/brief handlers drive them through the real DOM."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_full_app_mounts_panels_and_handlers_drive_them(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test", dims=DIMS)
                app = _SmokeApp("smoke")
                # compose() reads self.session_path when constructing the panels.
                app.session_path = session
                cm = app.run_test(size=(160, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                try:
                    # Both inline panes are now NodeDetailPanel instances...
                    self.assertIsInstance(
                        app.query_one("#dash_node_panel", NodeDetailPanel),
                        NodeDetailPanel,
                    )
                    self.assertIsInstance(
                        app.query_one("#dag_node_panel", NodeDetailPanel),
                        NodeDetailPanel,
                    )

                    # Dashboard detail handler drives the panel.
                    app._show_node_detail("n001_test")
                    await pilot.pause()
                    self.assertEqual(
                        _text(app.query_one("#dash_node_title", Label)),
                        "Node: n001_test",
                    )
                    self.assertTrue(any(
                        isinstance(c, DimensionRow)
                        for c in app.query_one("#dash_node_info", Container).children
                    ))

                    # Graph detail handler drives its panel.
                    app._show_dag_node_detail("n001_test")
                    await pilot.pause()
                    self.assertEqual(
                        _text(app.query_one("#dag_node_title", Label)),
                        "Node: n001_test",
                    )

                    # Task Brief toggle routes through the panel's public API.
                    app._show_brief_in_detail("brief line 1\nbrief line 2")
                    await pilot.pause()
                    self.assertEqual(
                        _text(app.query_one("#dash_node_title", Label)),
                        "Task Brief",
                    )
                    self.assertIsNone(app._current_focused_node_id)
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
