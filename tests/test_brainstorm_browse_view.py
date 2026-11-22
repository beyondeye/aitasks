"""Tests for the Browse tab (t983_3): view-state helper, persistence, and the
graph⇄list toggle + space-marking pilot.

t983_3 (the highest-risk structural seam of the t983 brainstorm-TUI IA
redesign) collapses the Dashboard (list) and Graph tabs into one **Browse** tab
with a ``v`` graph⇄list toggle (graph default, per-session persist), ONE shared
``NodeDetailPanel``, and ``space``-marking wired to ``NodeSelection``.

Coverage:
- Headless unit tests of the pure view-state helper ``browse_toggle_view`` +
  the ``BROWSE_DEFAULT_VIEW`` / ``BROWSE_VIEWS`` constants (no Textual).
- A tmp-worktree round-trip of ``_read_browse_view`` / ``_write_browse_view``.
- A pilot test: ``v`` flips ``#browse_switcher.current``, the shared
  ``#browse_node_panel`` persists across toggles, and ``space`` toggles
  membership in ``NodeSelection.marked`` with the NodeRow glyph reflecting it.
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

from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import ContentSwitcher, Label  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    BROWSE_DEFAULT_VIEW,
    BROWSE_VIEWS,
    BrainstormApp,
    NodeDetailPanel,
    NodeRow,
    browse_toggle_view,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    _read_browse_view,
    _write_browse_view,
)


def _make_session(td: str, *node_ids: str) -> Path:
    """Write a minimal brainstorm session with the given node(s)."""
    session = Path(td)
    (session / "br_nodes").mkdir(parents=True, exist_ok=True)
    (session / "br_proposals").mkdir(parents=True, exist_ok=True)
    for nid in node_ids:
        (session / "br_nodes" / f"{nid}.yaml").write_text(
            yaml.safe_dump(
                {
                    "description": f"node {nid}",
                    "parents": [],
                    "created_at": "2026-06-15 10:00",
                }
            ),
            encoding="utf-8",
        )
        (session / "br_proposals" / f"{nid}.md").write_text(
            "# Proposal\n", encoding="utf-8"
        )
    # Minimal graph state so get_head()/_populate_node_list() don't trip over a
    # missing br_graph_state.yaml.
    (session / "br_graph_state.yaml").write_text(
        yaml.safe_dump({"current_heads": {}}), encoding="utf-8"
    )
    return session


class _BrowseSmokeApp(BrainstormApp):
    """BrainstormApp with the session-loading on_mount neutralized.

    Isolates the Browse compose (switcher + shared panel) and the toggle/mark
    handlers without the heavy session-load pipeline. ``session_path`` is
    repointed at a fixture before mount. Note Textual still dispatches the base
    ``BrainstormApp.on_mount`` (which pushes ``InitSessionModal``) across the
    MRO; the pilots pop that modal via :func:`_dismiss_modals` before driving
    keys at the base Browse screen.
    """

    def on_mount(self) -> None:  # noqa: D401 - intentionally a no-op
        pass


async def _dismiss_modals(app, pilot) -> None:
    """Pop any modal (e.g. the auto-pushed InitSessionModal) so key presses
    reach the base Browse screen."""
    while isinstance(app.screen, ModalScreen):
        app.pop_screen()
        await pilot.pause()


class BrowseToggleViewHelperTests(unittest.TestCase):
    """Pure, headless tests of the view-state helper (no App)."""

    def test_default_is_graph(self):
        self.assertEqual(BROWSE_DEFAULT_VIEW, "graph")
        self.assertEqual(set(BROWSE_VIEWS), {"graph", "list"})

    def test_toggle_flips_graph_and_list(self):
        self.assertEqual(browse_toggle_view("graph"), "list")
        self.assertEqual(browse_toggle_view("list"), "graph")

    def test_toggle_round_trips(self):
        self.assertEqual(
            browse_toggle_view(browse_toggle_view("graph")), "graph"
        )

    def test_toggle_unknown_flips_to_graph(self):
        # A corrupt persisted value still toggles deterministically.
        self.assertEqual(browse_toggle_view("bogus"), "graph")


class BrowseViewPersistenceTests(unittest.TestCase):
    """Tmp-worktree round-trip of the session-state read/write pair."""

    def test_default_when_unset(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(_read_browse_view(Path(td)), "graph")

    def test_write_then_read_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _write_browse_view(wt, "list")
            self.assertEqual(_read_browse_view(wt), "list")
            _write_browse_view(wt, "graph")
            self.assertEqual(_read_browse_view(wt), "graph")

    def test_invalid_value_coerced_to_graph(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _write_browse_view(wt, "bogus")
            self.assertEqual(_read_browse_view(wt), "graph")


class BrowseTabPilotTests(unittest.TestCase):
    """Compose/toggle/mark pilot on the real BrainstormApp Browse tab."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_v_toggles_view_and_panel_persists(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test")
                app = _BrowseSmokeApp("smoke")
                app.session_path = session
                cm = app.run_test(size=(160, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await _dismiss_modals(app, pilot)
                try:
                    switcher = app.query_one("#browse_switcher", ContentSwitcher)
                    panel = app.query_one("#browse_node_panel", NodeDetailPanel)
                    # Graph is the default view.
                    self.assertEqual(switcher.current, "dag_content")

                    await pilot.press("v")
                    await pilot.pause()
                    self.assertEqual(switcher.current, "node_list_pane")
                    # The shared detail panel survives the toggle (same widget).
                    self.assertIs(
                        app.query_one("#browse_node_panel", NodeDetailPanel),
                        panel,
                    )

                    await pilot.press("v")
                    await pilot.pause()
                    self.assertEqual(switcher.current, "dag_content")
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_space_marks_node_and_reflects_in_list(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test")
                app = _BrowseSmokeApp("smoke")
                app.session_path = session
                cm = app.run_test(size=(160, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await _dismiss_modals(app, pilot)
                try:
                    app._populate_node_list()
                    app._set_browse_view("list")
                    await pilot.pause()

                    rows = list(app.query(NodeRow))
                    self.assertTrue(rows, "expected a NodeRow in list view")
                    app.set_focus(rows[0])
                    await pilot.pause()
                    # Focusing the row set the selection primary cursor.
                    self.assertEqual(app._selection.primary, "n001_test")

                    await pilot.press("space")
                    await pilot.pause()
                    self.assertIn("n001_test", app._selection.marked)
                    self.assertTrue(rows[0].marked)

                    # Toggling again unmarks it.
                    await pilot.press("space")
                    await pilot.pause()
                    self.assertNotIn("n001_test", app._selection.marked)
                    self.assertFalse(rows[0].marked)
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_space_mark_populates_marked_summary_in_both_views(self):
        """`#browse_marked_info` lists the marked node names (t983_4); it lives
        in the shared detail pane so it shows in list AND graph views, and
        clears when the marked set empties."""
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test")
                app = _BrowseSmokeApp("smoke")
                app.session_path = session
                cm = app.run_test(size=(160, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await _dismiss_modals(app, pilot)
                try:
                    app._populate_node_list()
                    app._set_browse_view("list")
                    await pilot.pause()
                    rows = list(app.query(NodeRow))
                    app.set_focus(rows[0])
                    await pilot.pause()

                    summary = app.query_one("#browse_marked_info", Label)
                    # Nothing marked yet -> empty.
                    self.assertEqual(str(summary.render()).strip(), "")

                    await pilot.press("space")
                    await pilot.pause()
                    rendered = str(summary.render())
                    self.assertIn("Marked (1)", rendered)
                    self.assertIn("n001_test", rendered)

                    # Shared detail pane: switch to graph view, summary persists.
                    app._set_browse_view("graph")
                    await pilot.pause()
                    self.assertIn("n001_test", str(summary.render()))

                    # Unmark (back in list view) -> summary clears.
                    app._set_browse_view("list")
                    await pilot.pause()
                    await pilot.press("space")
                    await pilot.pause()
                    self.assertEqual(str(summary.render()).strip(), "")
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_set_browse_view_drives_switcher_to_persisted_pane(self):
        """The restore primitive (_set_browse_view, used by the on-load restore
        in _load_existing_session) drives the switcher to a persisted view."""
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n001_test")
                _write_browse_view(session, "list")
                app = _BrowseSmokeApp("smoke")
                app.session_path = session
                cm = app.run_test(size=(160, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await _dismiss_modals(app, pilot)
                try:
                    switcher = app.query_one("#browse_switcher", ContentSwitcher)
                    # Compose default is graph; reading the persisted value and
                    # driving the switcher (what _load_existing_session does)
                    # lands on the list pane.
                    app._set_browse_view(_read_browse_view(session))
                    await pilot.pause()
                    self.assertEqual(switcher.current, "node_list_pane")
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())


# ---------------------------------------------------------------------------
# t2339 — root brief without frontmatter; task text rendered literally.
# ---------------------------------------------------------------------------

_BRACKETED = "- [x] done; use `[/]` here; path\\[x] and $HOME"

_LEGACY_SPEC = (
    "---\npriority: medium\neffort: low\n---\n\n## Origin\n\nFix the brief.\n"
)


def _plain(widget) -> str:
    """The rendered plain text of a widget — what the user sees.

    A ``str`` render is markup that Textual parses at paint time, so parse it
    the same way (this is where a stray ``[/]`` raises ``MarkupError`` and a
    ``[x]`` vanishes). Never compare against the markup source.
    """
    from textual.markup import to_content
    rendered = widget.render()
    if isinstance(rendered, str):
        return to_content(rendered).plain
    return str(rendered)


def _write_session(session: Path, **fields) -> dict:
    data = {
        "status": "active",
        "created_at": "2026-11-20 10:00",
        "updated_at": "2026-11-20 10:00",
        "created_by": "t@example.com",
    }
    data.update(fields)
    (session / "br_session.yaml").write_text(
        yaml.safe_dump(data), encoding="utf-8")
    return data


def _set_description(session: Path, nid: str, desc: str) -> None:
    path = session / "br_nodes" / f"{nid}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["description"] = desc
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _detail_texts(app) -> list[str]:
    panel = app.query_one("#browse_node_panel", NodeDetailPanel)
    from textual.widgets import Static
    return [_plain(w) for w in panel.query(Static)]


class BrowseRootBriefAndLiteralTextTests(unittest.TestCase):
    """t2339 pilots on the real Browse widgets."""

    def _drive(self, setup, check):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, "n000_init")
                session_data = setup(session)
                app = _BrowseSmokeApp("smoke")
                app.session_path = session
                cm = app.run_test(size=(160, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await _dismiss_modals(app, pilot)
                try:
                    if session_data is not None:
                        app.session_data = session_data
                    app._populate_node_list()
                    app._set_browse_view("list")
                    await pilot.pause()
                    await check(app, pilot)
                finally:
                    await cm.__aexit__(None, None, None)

        asyncio.run(runner())

    def test_root_without_session_file_renders_stored_description(self):
        async def check(app, pilot):
            rows = list(app.query(NodeRow))
            self.assertIn("node n000_init", _plain(rows[0]))
            app._show_browse_node_detail("n000_init")
            await pilot.pause()
            self.assertTrue(any("Description: node n000_init" in t
                                for t in _detail_texts(app)))

        # No br_session.yaml at all, and no session_data on the app.
        self._drive(lambda session: None, check)

    def test_legacy_session_shows_clean_root_label(self):
        def setup(session):
            _set_description(session, "n000_init", "priority: medium")
            return _write_session(session, initial_spec=_LEGACY_SPEC)

        async def check(app, pilot):
            row_text = _plain(list(app.query(NodeRow))[0])
            self.assertIn("## Origin", row_text)
            self.assertNotIn("priority", row_text)
            app._show_browse_node_detail("n000_init")
            await pilot.pause()
            texts = _detail_texts(app)
            self.assertTrue(any("Description: ## Origin" in t for t in texts))
            self.assertFalse(any("priority: medium" in t for t in texts))

        self._drive(setup, check)

    def test_bracketed_task_text_renders_verbatim_everywhere(self):
        spec = "## Origin\n\n" + _BRACKETED + "\n\nlast line [b]x[/b]\n"

        def setup(session):
            _set_description(session, "n000_init", _BRACKETED)
            return _write_session(session, initial_spec=spec)

        async def check(app, pilot):
            # NodeRow (list view).
            self.assertIn(_BRACKETED, _plain(list(app.query(NodeRow))[0]))
            # Node-detail Description field.
            app._show_browse_node_detail("n000_init")
            await pilot.pause()
            self.assertTrue(any(_BRACKETED in t for t in _detail_texts(app)))
            # Brief line, and its bracketed hint, in the session status label.
            app._update_session_status()
            await pilot.pause()
            info = _plain(app.query_one("#session_status_info", Label))
            self.assertIn("Brief: ## Origin | " + _BRACKETED, info)
            self.assertIn("[press b for full text]", info)
            # `b` on the Browse tab shows the full spec verbatim.
            app.set_focus(None)
            await pilot.press("b")
            await pilot.pause()
            title = app.query_one("#browse_node_panel", NodeDetailPanel)
            self.assertIn("Task Brief", _plain(title.query(Label).first()))
            texts = _detail_texts(app)
            self.assertTrue(any(_BRACKETED in t and "last line [b]x[/b]" in t
                                for t in texts), texts)

        self._drive(setup, check)


class OperationRowLiteralDescriptionTests(unittest.TestCase):
    """`literal_description` renders task text verbatim; the default keeps
    interpreting framework markup for the existing callers (t2339)."""

    def _plain_render(self, row) -> str:
        from textual.markup import to_content
        rendered = row.render()
        return to_content(rendered).plain if isinstance(rendered, str) else str(rendered)

    def test_literal_description_enabled_and_disabled(self):
        from brainstorm.widgets import OperationRow
        for disabled in (False, True):
            row = OperationRow("n000_init", "n000_init [green]HEAD[/]",
                               _BRACKETED, disabled=disabled,
                               literal_description=True)
            text = self._plain_render(row)
            self.assertIn(_BRACKETED, text, f"disabled={disabled}")
            # The label is still framework markup: the tag is parsed away.
            self.assertIn("n000_init HEAD", text)
            self.assertNotIn("[green]", text)

    def test_default_still_interprets_markup(self):
        from brainstorm.widgets import OperationRow
        row = OperationRow("k", "Label", "[dim]framework hint[/]")
        self.assertEqual(self._plain_render(row).strip(), "Label  framework hint")


if __name__ == "__main__":
    unittest.main()
