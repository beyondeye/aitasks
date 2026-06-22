"""Pilot tests for the t1047 wizard nav/preview consolidation.

t1047 fixed three brainstorm node-op wizard bugs that were fallout from the
t983_11 relocation of the Actions tab into the ``ActionsWizardScreen`` modal:

1. The copied ``_navigate_rows`` hard-coded ``query_one(TabbedContent)`` for its
   tab-bar boundary, which raises ``NoMatches`` in a modal (no ``TabbedContent``)
   and broke wizard arrow-nav. It is now a shared ``RowNavMixin`` whose tab-bar
   boundary is an overridable ``_nav_tab_bar()`` hook (App returns its ``Tabs``;
   the modal inherits ``None`` → stop at top). The ``section_select`` step also
   gained the missing up/down ``on_key`` branch.
2. The preview config steps now mount a contextual shortcut hint label.
3. The proposal-minimap selection is now handled on the wizard (where the pane
   lives); the dead App-level handler was removed.

These tests cover the mixin boundary contract, section_select arrow nav (incl.
the top-boundary no-crash regression), the hint label, and the minimap route.
The async scroll-into-view itself stays manual-verification.
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
from textual.containers import VerticalScroll  # noqa: E402
from textual.widgets import (  # noqa: E402
    Checkbox,
    Label,
    TabbedContent,
    TabPane,
    Tabs,
)

from brainstorm.nav_mixin import RowNavMixin  # noqa: E402
from brainstorm.brainstorm_app import (  # noqa: E402
    ActionsWizardScreen,
    BrainstormApp,
    ProposalPreviewPane,
)


PROPOSAL = """\
# Proposal

<!-- section: auth -->
""" + "Use JWT.\n" * 30 + """\
<!-- /section: auth -->

<!-- section: storage -->
""" + "Postgres.\n" * 30 + """\
<!-- /section: storage -->
"""


# --------------------------------------------------------------------------- #
# RowNavMixin boundary contract (with vs without a tab bar)
# --------------------------------------------------------------------------- #
class _TabHost(RowNavMixin, App):
    """Host WITH a tab bar — overrides the boundary hook like BrainstormApp."""

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("t", id="tp"):
                yield VerticalScroll(Checkbox("a"), Checkbox("b"), id="rows")

    def _nav_tab_bar(self):
        return self.query_one(TabbedContent).query_one(Tabs)


class _NoTabHost(RowNavMixin, App):
    """Host WITHOUT a tab bar — inherits the default _nav_tab_bar (None)."""

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Checkbox("a"), Checkbox("b"), id="rows")


class RowNavMixinContractTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_class_wiring(self):
        # The wizard inherits the default (no tab bar); the App overrides it.
        self.assertIs(
            ActionsWizardScreen._nav_tab_bar, RowNavMixin._nav_tab_bar
        )
        self.assertIsNot(
            BrainstormApp._nav_tab_bar, RowNavMixin._nav_tab_bar
        )
        # Duplication is gone: both nav helpers resolve to the mixin.
        self.assertIs(ActionsWizardScreen._navigate_rows, RowNavMixin._navigate_rows)
        self.assertIs(BrainstormApp._navigate_rows, RowNavMixin._navigate_rows)
        self.assertIs(ActionsWizardScreen._focus_within, RowNavMixin._focus_within)
        self.assertIs(BrainstormApp._focus_within, RowNavMixin._focus_within)

    def test_up_past_top_focuses_tab_bar_when_present(self):
        async def runner():
            app = _TabHost()
            async with app.run_test(size=(80, 24)) as pilot:
                rows = list(app.query("#rows").first().children)
                rows[0].focus()
                await pilot.pause()
                handled = app._navigate_rows(-1, "rows", (Checkbox,))
                await pilot.pause()
                self.assertTrue(handled)
                self.assertIs(app.focused, app.query_one(TabbedContent).query_one(Tabs))

        self._run(runner())

    def test_up_past_top_stops_when_no_tab_bar(self):
        async def runner():
            app = _NoTabHost()
            async with app.run_test(size=(80, 24)) as pilot:
                rows = list(app.query("#rows").first().children)
                rows[0].focus()
                await pilot.pause()
                handled = app._navigate_rows(-1, "rows", (Checkbox,))
                await pilot.pause()
                # No crash, event consumed, focus stays put (no tab bar to leave to).
                self.assertTrue(handled)
                self.assertIs(app.focused, rows[0])

        self._run(runner())

    def test_down_moves_to_next_row(self):
        async def runner():
            app = _NoTabHost()
            async with app.run_test(size=(80, 24)) as pilot:
                rows = list(app.query("#rows").first().children)
                rows[0].focus()
                await pilot.pause()
                app._navigate_rows(1, "rows", (Checkbox,))
                await pilot.pause()
                self.assertIs(app.focused, rows[1])

        self._run(runner())


# --------------------------------------------------------------------------- #
# Wizard harness (explore op) for section_select / hint / minimap
# --------------------------------------------------------------------------- #
class _Sec:
    def __init__(self, name, dims=None):
        self.name = name
        self.dimensions = dims or []


def _make_session(td: str, node_id: str) -> Path:
    session = Path(td)
    (session / "br_nodes").mkdir(parents=True, exist_ok=True)
    (session / "br_proposals").mkdir(parents=True, exist_ok=True)
    (session / "br_nodes" / f"{node_id}.yaml").write_text(
        yaml.safe_dump({"description": "n", "parents": [], "created_at": "2026-06-09 10:00"}),
        encoding="utf-8",
    )
    (session / "br_proposals" / f"{node_id}.md").write_text(PROPOSAL, encoding="utf-8")
    return session


class _WizardHost(App):
    """Minimal host that pushes the explore wizard against a fake session."""

    task_num = "0"

    def __init__(self, session_path: Path, *, has_sections: bool) -> None:
        super().__init__()
        self.session_path = session_path
        self._has_sections = has_sections
        self.read_only = False

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            ActionsWizardScreen(op_key="explore", node_id="n001", marked=[])
        )

    # App-side helpers the explore wizard path reaches via self.app.
    def _node_has_sections(self, node: str) -> bool:
        return self._has_sections

    def _node_sections(self, node: str):
        return [_Sec("auth"), _Sec("storage")]


class _FakeMinimap:
    def __init__(self, has_class: bool) -> None:
        self._has = has_class

    def has_class(self, name: str) -> bool:
        return self._has and name == "preview_proposal_minimap"


class _FakeSectionSelected:
    def __init__(self, *, has_class: bool, section_name: str) -> None:
        self.control = _FakeMinimap(has_class)
        self.section_name = section_name
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class WizardNavTests(unittest.TestCase):
    # t1050: the preview-pane populate-timing race is fixed at the source —
    # ProposalPreviewPane.populate now runs from the pane's own on_mount, so the
    # tolerant populate monkeypatch this setUp used to install is no longer
    # needed. The real populate() runs unpatched under run_test.

    def _run(self, coro):
        return asyncio.run(coro)

    async def _drive(self, has_sections: bool):
        td = tempfile.mkdtemp()
        session = _make_session(td, "n001")
        app = _WizardHost(session, has_sections=has_sections)
        cm = app.run_test(size=(160, 48))
        pilot = await cm.__aenter__()
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        self.assertIsInstance(screen, ActionsWizardScreen)
        return app, pilot, screen, cm

    def test_section_select_arrow_nav_and_top_boundary(self):
        async def runner():
            app, pilot, screen, cm = await self._drive(has_sections=True)
            try:
                self.assertEqual(screen._wizard_step_id, "section_select")
                checks = list(
                    screen.query_one("#actions_content").query("Checkbox.chk_section")
                )
                self.assertGreaterEqual(len(checks), 2)
                checks[0].focus()
                await pilot.pause()
                # Down arrow moves focus to the next checkbox (the bug: was Tab-only).
                await pilot.press("down")
                await pilot.pause()
                self.assertIs(app.focused, checks[1])
                # Back up.
                await pilot.press("up")
                await pilot.pause()
                self.assertIs(app.focused, checks[0])
                # Up at the top boundary must NOT crash (the NoMatches regression).
                await pilot.press("up")
                await pilot.pause()
                self.assertTrue(app.is_running)
                self.assertIs(app.focused, checks[0])
            finally:
                await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_preview_toggles_are_bare_keys_shown_in_footer(self):
        # The line-numbers / preview-width toggles are plain single keys with
        # show=True (footer-visible), not alt+ chords.
        binds = {b.action: b for b in ActionsWizardScreen.BINDINGS}
        for action, key in (("toggle_preview_numbered", "l"), ("cycle_preview_ratio", "w")):
            self.assertIn(action, binds)
            self.assertEqual(binds[action].key, key)
            self.assertTrue(binds[action].show)
            self.assertNotIn("+", binds[action].key)  # no chord

    def test_preview_toggle_scope_follows_focus(self):
        async def runner():
            # No sections → wizard jumps straight to the explore config step.
            app, pilot, screen, cm = await self._drive(has_sections=False)
            try:
                self.assertEqual(screen._wizard_step_id, "config")
                # Focus inside the proposal → toggles are active (footer shows them).
                screen.query_one("#preview_proposal_content").focus()
                await pilot.pause()
                self.assertTrue(screen.check_action("toggle_preview_numbered", None))
                self.assertTrue(screen.check_action("cycle_preview_ratio", None))
                # Focus the Mandate text box → toggles go inactive so w/l type as
                # text instead of toggling.
                from textual.widgets import TextArea
                screen.query(TextArea).first().focus()
                await pilot.pause()
                self.assertFalse(screen.check_action("toggle_preview_numbered", None))
                self.assertFalse(screen.check_action("cycle_preview_ratio", None))
            finally:
                await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_preview_toggles_inactive_off_preview_step(self):
        async def runner():
            # section_select step has no preview pane → toggles never active.
            app, pilot, screen, cm = await self._drive(has_sections=True)
            try:
                self.assertEqual(screen._wizard_step_id, "section_select")
                self.assertFalse(screen.check_action("toggle_preview_numbered", None))
                self.assertFalse(screen.check_action("cycle_preview_ratio", None))
            finally:
                await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_wizard_handles_minimap_selection(self):
        async def runner():
            app, pilot, screen, cm = await self._drive(has_sections=False)
            try:
                panes = list(screen.query(ProposalPreviewPane))
                self.assertTrue(panes, "explore config step did not mount a preview pane")
                pane = panes[0]
                recorded = []
                pane.scroll_to_section = lambda name: recorded.append(name)

                # A non-preview minimap control is ignored (class guard).
                ev_other = _FakeSectionSelected(has_class=False, section_name="auth")
                screen.on_section_minimap_section_selected(ev_other)
                self.assertEqual(recorded, [])
                self.assertFalse(ev_other.stopped)

                # The preview minimap routes to the pane and stops the event.
                ev = _FakeSectionSelected(has_class=True, section_name="storage")
                screen.on_section_minimap_section_selected(ev)
                self.assertEqual(recorded, ["storage"])
                self.assertTrue(ev.stopped)
            finally:
                await cm.__aexit__(None, None, None)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
