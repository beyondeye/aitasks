"""Tests for the Node Hub overlay (t983_5).

t983_5 (child of the t983 brainstorm-TUI IA redesign) routes ``Enter`` on the
cursor node through a **Node Hub** overlay: the shared Detail surface
(``NodeDetailPanel`` Metadata tab + Proposal/minimap, inherited from
``NodeDetailModal``) plus an **Operations** entry that launches the contextual
Operations dialog (t983_4, ``NodeActionSelectModal``) seeded from the current
selection.

Coverage:
- Structural: ``NodeHub`` subclasses ``NodeDetailModal`` and binds ``a`` →
  ``operations`` (the inherited Detail behavior is covered by the t983_1
  panel/minimap tests).
- Bare-host pilot: the Hub renders the Detail content + the Operations button,
  and ``a`` / the button dismiss with a typed
  ``NodeHubResult(NODE_HUB_OPERATIONS, node_id)``.
- App integration (``_SmokeApp``): ``Enter`` opens the Hub from BOTH the
  list-view binding and the graph ``NodeSelected`` path; the graph path's
  Operations entry actually pushes ``NodeActionSelectModal`` (non-vacuous — a
  read-only session is asserted NOT to push it, so the positive case can't pass
  by a short-circuited guard).
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
from textual.widgets import Button, Footer, Label  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    NODE_HUB_OPERATIONS,
    BrainstormApp,
    NodeActionSelectModal,
    NodeDetailModal,
    NodeDetailPanel,
    NodeHub,
    NodeHubResult,
    NodeSelection,
)
from brainstorm.brainstorm_dag_display import DAGDisplay  # noqa: E402


def _make_session(td: str, node_id: str, *, proposal: str = "# Proposal\n") -> Path:
    """Write a minimal brainstorm session with one node + graph state.

    ``br_graph_state.yaml`` is required: ``_node_action_op_states`` reads it via
    ``_read_graph_state`` (which raises ``FileNotFoundError`` when absent), so a
    realistic Operations-launch test needs it present."""
    session = Path(td)
    (session / "br_nodes").mkdir(parents=True, exist_ok=True)
    (session / "br_proposals").mkdir(parents=True, exist_ok=True)
    node = {
        "description": "A test node",
        "parents": [],
        "created_at": "2026-06-14 10:00",
    }
    (session / "br_nodes" / f"{node_id}.yaml").write_text(
        yaml.safe_dump(node), encoding="utf-8"
    )
    (session / "br_proposals" / f"{node_id}.md").write_text(
        proposal, encoding="utf-8"
    )
    (session / "br_graph_state.yaml").write_text(
        yaml.safe_dump({"current_heads": {"_umbrella": node_id}}),
        encoding="utf-8",
    )
    return session


def _text(widget) -> str:
    try:
        return str(widget.render())
    except Exception:
        return str(getattr(widget, "content", ""))


class NodeHubStructureTests(unittest.TestCase):
    """No-pilot structural guards for the Hub's contract."""

    def test_subclasses_node_detail_modal(self):
        self.assertTrue(issubclass(NodeHub, NodeDetailModal))

    def test_binds_a_to_operations(self):
        # NodeHub's own binding adds `a → operations`; the inherited
        # escape/tab/v/e bindings (merged across the MRO by Textual) are proven
        # at runtime by the `a` press in the pilot tests below.
        own = {(b.key, b.action) for b in NodeHub.BINDINGS}
        self.assertIn(("a", "operations"), own)
        # The Detail bindings still live on the base class (so they merge in).
        base = {b.key for b in NodeDetailModal.BINDINGS}
        self.assertTrue({"v", "e"}.issubset(base))

    def test_result_is_typed(self):
        r = NodeHubResult(NODE_HUB_OPERATIONS, "n001_test")
        self.assertEqual(r.action, NODE_HUB_OPERATIONS)
        self.assertEqual(r.node_id, "n001_test")


class _HostHubApp(App):
    """Bare host that pushes a NodeHub on mount and captures its dismiss result."""

    task_num = "0"  # inherited action_export reads this off the app.

    def __init__(self, node_id: str, session_path: Path) -> None:
        super().__init__()
        self._node_id = node_id
        self._session_path = session_path
        self.result = "UNSET"

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            NodeHub(self._node_id, self._session_path), self._capture
        )

    def _capture(self, result) -> None:
        self.result = result


class NodeHubPilotTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_hub_renders_detail_content_and_operations_button(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test")
                app = _HostHubApp("n001_test", session)
                cm = app.run_test(size=(140, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await pilot.pause()
                try:
                    screen = app.screen
                    self.assertIsInstance(screen, NodeHub)
                    # Title reads "Node Hub: …" (the override).
                    self.assertEqual(
                        _text(screen.query_one("#node_detail_title", Label)),
                        "Node Hub: n001_test",
                    )
                    # Detail surface inherited from NodeDetailModal: the shared
                    # Metadata panel + the Proposal tab.
                    self.assertIsInstance(
                        screen.query_one("#modal_node_panel", NodeDetailPanel),
                        NodeDetailPanel,
                    )
                    self.assertEqual(
                        len(list(screen.query("#proposal_content"))), 1
                    )
                    # The Operations entry button is present.
                    self.assertEqual(
                        len(list(screen.query("#btn_node_hub_ops"))), 1
                    )
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_a_key_dismisses_with_typed_operations_result(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test")
                app = _HostHubApp("n001_test", session)
                cm = app.run_test(size=(140, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await pilot.pause()
                try:
                    await pilot.press("a")
                    await pilot.pause()
                    self.assertEqual(
                        app.result, NodeHubResult(NODE_HUB_OPERATIONS, "n001_test")
                    )
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_operations_button_handler_dismisses_with_typed_result(self):
        # The button's @on(Button.Pressed) handler dismisses identically to the
        # `a` binding (the real key path is exercised in the test above; here we
        # confirm the button handler body, avoiding a geometry-dependent click).
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test")
                app = _HostHubApp("n001_test", session)
                cm = app.run_test(size=(140, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await pilot.pause()
                try:
                    app.screen._open_operations()
                    await pilot.pause()
                    self.assertEqual(
                        app.result, NodeHubResult(NODE_HUB_OPERATIONS, "n001_test")
                    )
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())


class _StyledHubHost(App):
    """Host that borrows ``BrainstormApp.CSS`` so the ``#node_detail_dialog``
    layout rules apply — needed to assert the Hub's button-row geometry (the
    dialog CSS lives on the app, not on the modal)."""

    CSS = BrainstormApp.CSS
    task_num = "0"

    def __init__(self, node_id: str, session_path: Path) -> None:
        super().__init__()
        self._node_id = node_id
        self._session_path = session_path

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(NodeHub(self._node_id, self._session_path))


class NodeHubLayoutTests(unittest.TestCase):
    """Guards the t983_5 review fix: the dialog button row must not be
    overdrawn by the docked Footer (the truncation the user reported)."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_button_row_clears_the_footer(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test")
                app = _StyledHubHost("n001_test", session)
                # Two heights, incl. the live terminal size that surfaced the bug.
                for size in ((164, 43), (120, 30)):
                    cm = app.run_test(size=size)
                    pilot = await cm.__aenter__()
                    await pilot.pause()
                    await pilot.pause()
                    try:
                        screen = app.screen
                        self.assertIsInstance(screen, NodeHub)
                        btns = screen.query_one("#node_detail_buttons")
                        foot = screen.query_one(Footer)
                        # The full 3-row button widget sits entirely above the
                        # footer's row (no overlap → bottom border visible).
                        self.assertLessEqual(btns.region.bottom, foot.region.y)
                    finally:
                        await cm.__aexit__(None, None, None)
                    app = _StyledHubHost("n001_test", session)

        self._run(runner())


def _bare_app(session_path=None):
    """A BrainstormApp with ``__init__`` bypassed (the established pattern — full
    app boot is not a test pattern in this suite). ``push_screen``/``notify`` are
    stubbed to capture, so handler logic is testable without a running app."""
    app = BrainstormApp.__new__(BrainstormApp)
    app.session_path = session_path
    app._selection = NodeSelection()
    app._current_focused_node_id = None
    app.read_only = False
    app.session_data = {"status": "active"}
    app.pushed = []
    app.notices = []
    app.push_screen = lambda screen, *a, **k: app.pushed.append(screen)
    app.notify = lambda msg, **kw: app.notices.append((msg, kw))
    return app


class _ListEnterApp(BrainstormApp):
    """Bypasses ``__init__`` and overrides the App ``screen``/``focused``
    properties so ``action_open_node_detail`` (which reads both) is testable
    without a running app."""

    def __init__(self, session_path, focused):
        self.session_path = session_path
        self._fake_focused = focused
        self.pushed = []
        self.push_screen = lambda screen, *a, **k: self.pushed.append(screen)

    @property
    def screen(self):  # non-modal sentinel → the modal guard falls through
        return object()

    @property
    def focused(self):
        return self._fake_focused


class NodeHubEnterRoutingTests(unittest.TestCase):
    """Both Enter paths push a NodeHub; the result callback dispatches."""

    def test_graph_enter_pushes_hub(self):
        app = _bare_app("/tmp/x")
        app.on_dag_display_node_selected(DAGDisplay.NodeSelected("n001_test"))
        self.assertEqual(len(app.pushed), 1)
        self.assertIsInstance(app.pushed[0], NodeHub)
        self.assertEqual(app.pushed[0].node_id, "n001_test")

    def test_list_enter_pushes_hub_for_focused_node_row(self):
        from brainstorm.brainstorm_app import NodeRow
        row = NodeRow("n001_test", "A test node")
        app = _ListEnterApp("/tmp/x", row)
        app.action_open_node_detail()
        self.assertEqual(len(app.pushed), 1)
        self.assertIsInstance(app.pushed[0], NodeHub)
        self.assertEqual(app.pushed[0].node_id, "n001_test")

    def test_list_enter_skips_when_focus_is_not_a_node_row(self):
        from textual.actions import SkipAction
        app = _ListEnterApp("/tmp/x", Label("not a node row"))
        with self.assertRaises(SkipAction):
            app.action_open_node_detail()
        self.assertEqual(app.pushed, [])

    def test_on_node_hub_result_dispatches_operations(self):
        app = _bare_app()
        app.opened = []
        app._open_operations_dialog = lambda nid: app.opened.append(nid)
        app._on_node_hub_result(NodeHubResult(NODE_HUB_OPERATIONS, "n001_test"))
        self.assertEqual(app.opened, ["n001_test"])
        # None (Escape/Close) and unknown verbs are no-ops.
        app._on_node_hub_result(None)
        app._on_node_hub_result(NodeHubResult("compare", "n001_test"))
        self.assertEqual(app.opened, ["n001_test"])


class OpenOperationsDialogTests(unittest.TestCase):
    """The shared launch helper actually pushes the Operations dialog (so the
    Hub's Operations entry is non-vacuous), with the cursor-anchor invariant and
    the read-only guard."""

    def test_pushes_dialog_and_anchors_cursor(self):
        with tempfile.TemporaryDirectory() as td:
            session = _make_session(td, "n001_test")
            app = _bare_app(session)
            app._open_operations_dialog("n001_test")
            self.assertEqual(len(app.pushed), 1)
            self.assertIsInstance(app.pushed[0], NodeActionSelectModal)
            # Cursor-anchor invariant: primary pinned to the launched node.
            self.assertEqual(app._selection.primary, "n001_test")
            self.assertEqual(app._current_focused_node_id, "n001_test")

    def test_read_only_blocks_dialog(self):
        with tempfile.TemporaryDirectory() as td:
            session = _make_session(td, "n001_test")
            app = _bare_app(session)
            app.read_only = True
            app._open_operations_dialog("n001_test")
            self.assertEqual(app.pushed, [])  # not vacuous: positive case pushes
            self.assertTrue(app.notices)

    def test_non_active_session_blocks_dialog(self):
        with tempfile.TemporaryDirectory() as td:
            session = _make_session(td, "n001_test")
            app = _bare_app(session)
            app.session_data = {"status": "finalized"}
            app._open_operations_dialog("n001_test")
            self.assertEqual(app.pushed, [])
            self.assertTrue(app.notices)


if __name__ == "__main__":
    unittest.main()
