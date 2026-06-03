"""Tests for the brainstorm node-action picker (t819).

Covers two pieces:

- ``NodeActionSelectModal`` — the dialog opened by ``A`` on the Graph and
  Dashboard tabs to pick a single-node operation. Pilot-driven, pushed onto a
  minimal host App (the modal needs no session infrastructure).
- ``_actions_advance_from_node_select`` — the wizard-routing helper shared by
  the Next button, keyboard ``Enter``, and the modal callback. Unit-tested with
  ``BrainstormApp.__init__`` bypassed and a temp session on disk.

The ``detail``-with-sections case is a regression guard: routing all node-select
advances through this helper fixed a pre-existing bug where keyboard ``Enter``
skipped section selection for the ``detail`` operation.

End-to-end in-TUI flow (press ``A`` -> modal -> Actions wizard) is verified by
manual verification; full ``BrainstormApp`` boot is not an established test
pattern in this repo.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import yaml  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    NodeActionSelectModal,
    OperationRow,
)


# --------------------------------------------------------------------------
# NodeActionSelectModal — Pilot tests
# --------------------------------------------------------------------------

class _ModalHost(App):
    """Minimal host App that pushes a NodeActionSelectModal on mount."""

    def __init__(self, node_id: str, has_plan: bool) -> None:
        super().__init__()
        self._node_id = node_id
        self._has_plan = has_plan
        self.result = "UNSET"

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            NodeActionSelectModal(self._node_id, self._has_plan),
            self._record,
        )

    def _record(self, result) -> None:
        self.result = result


class NodeActionSelectModalTests(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_four_rows_all_enabled_when_node_has_plan(self):
        async def runner():
            app = _ModalHost("n001_x", has_plan=True)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rows = list(app.screen.query(OperationRow))
                self.assertEqual(
                    [r.op_key for r in rows],
                    ["explore", "detail", "patch", "fast_track"],
                )
                self.assertTrue(all(not r.op_disabled for r in rows))
                self.assertTrue(all(r.can_focus for r in rows))

        self._run(runner())

    def test_patch_disabled_when_node_has_no_plan(self):
        async def runner():
            app = _ModalHost("n001_x", has_plan=False)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rows = {r.op_key: r for r in app.screen.query(OperationRow)}
                self.assertFalse(rows["explore"].op_disabled)
                self.assertFalse(rows["detail"].op_disabled)
                self.assertTrue(rows["patch"].op_disabled)
                self.assertFalse(rows["patch"].can_focus)
                # fast_track (t756_6) is a preset, not a node op — always
                # enabled regardless of whether the node has a plan.
                self.assertFalse(rows["fast_track"].op_disabled)
                self.assertTrue(rows["fast_track"].can_focus)

        self._run(runner())

    def test_fast_track_row_label_and_select(self):
        async def runner():
            app = _ModalHost("n7", has_plan=True)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rows = {r.op_key: r for r in app.screen.query(OperationRow)}
                self.assertIn("Fast-track this module", str(rows["fast_track"].render()))
                # explore -> detail -> patch -> fast_track, then Enter selects.
                await pilot.press("down")
                await pilot.press("down")
                await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, "fast_track")

        self._run(runner())

    def test_title_widget_carries_node_id(self):
        async def runner():
            app = _ModalHost("n042_special", has_plan=True)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                title = app.screen.query_one("#node_action_title", Label)
                self.assertIn("n042_special", str(title.render()))

        self._run(runner())

    def test_enter_selects_first_enabled_op(self):
        async def runner():
            app = _ModalHost("n1", has_plan=True)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, "explore")

        self._run(runner())

    def test_down_navigates_then_enter_selects_detail(self):
        async def runner():
            app = _ModalHost("n1", has_plan=True)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, "detail")

        self._run(runner())

    def test_navigation_skips_disabled_patch_row(self):
        async def runner():
            app = _ModalHost("n1", has_plan=False)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                # Focusable rows are explore, detail, fast_track (patch is
                # disabled and not focusable, so navigation skips it).
                # explore -> down: detail -> down: fast_track.
                await pilot.press("down")
                await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, "fast_track")

        self._run(runner())

    def test_escape_cancels_with_none(self):
        async def runner():
            app = _ModalHost("n1", has_plan=True)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsNone(app.result)

        self._run(runner())


# --------------------------------------------------------------------------
# _actions_advance_from_node_select — unit tests
# --------------------------------------------------------------------------

_PROPOSAL_NO_SECTIONS = "# Proposal\n\nPlain prose, no markers.\n"

_PROPOSAL_WITH_SECTIONS = """\
# Proposal

<!-- section: auth [dimensions: component_auth] -->
Use JWT.
<!-- /section: auth -->

<!-- section: storage -->
Postgres.
<!-- /section: storage -->
"""

_PLAN_NO_SECTIONS = "# Plan\n\nPlain plan, no markers.\n"


class AdvanceFromNodeSelectTests(unittest.TestCase):
    """Routing assertions for the shared node-select advance helper."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_node_action_")
        self.wt = Path(self.tmpdir)
        (self.wt / "br_nodes").mkdir()
        (self.wt / "br_proposals").mkdir()
        (self.wt / "br_plans").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_node(self, node_id: str, plan_file: str | None = None) -> None:
        data = {
            "node_id": node_id,
            "parents": [],
            "description": f"desc {node_id}",
            "proposal_file": f"br_proposals/{node_id}.md",
        }
        if plan_file:
            data["plan_file"] = plan_file
        (self.wt / "br_nodes" / f"{node_id}.yaml").write_text(
            yaml.safe_dump(data), encoding="utf-8"
        )

    def _write_proposal(self, node_id: str, content: str) -> None:
        (self.wt / "br_proposals" / f"{node_id}.md").write_text(
            content, encoding="utf-8"
        )

    def _write_plan(self, node_id: str, content: str) -> None:
        (self.wt / "br_plans" / f"{node_id}_plan.md").write_text(
            content, encoding="utf-8"
        )

    def _make_app(self, wizard_op: str):
        """A BrainstormApp with __init__ bypassed, wired for routing capture."""
        app = BrainstormApp.__new__(BrainstormApp)
        app.session_path = self.wt
        app._wizard_op = wizard_op
        app._wizard_config = {}
        app.calls = []
        app.notices = []
        app.notify = lambda msg, **kw: app.notices.append((msg, kw))
        app._actions_show_config = lambda: app.calls.append("config")
        app._actions_show_confirm = lambda: app.calls.append("confirm")
        app._actions_show_section_select = (
            lambda: app.calls.append("section")
        )
        return app

    def test_explore_no_sections_goes_to_config(self):
        self._write_proposal("n1", _PROPOSAL_NO_SECTIONS)
        app = self._make_app("explore")
        result = app._actions_advance_from_node_select("n1")
        self.assertTrue(result)
        self.assertEqual(app.calls, ["config"])

    def test_detail_no_sections_goes_to_confirm(self):
        self._write_proposal("n1", _PROPOSAL_NO_SECTIONS)
        app = self._make_app("detail")
        result = app._actions_advance_from_node_select("n1")
        self.assertTrue(result)
        self.assertEqual(app.calls, ["confirm"])
        self.assertEqual(app._wizard_config.get("node"), "n1")

    def test_detail_with_sections_goes_to_section_select(self):
        # Regression guard: keyboard Enter previously skipped section
        # selection for `detail`; the shared helper now applies it uniformly.
        self._write_proposal("n1", _PROPOSAL_WITH_SECTIONS)
        app = self._make_app("detail")
        result = app._actions_advance_from_node_select("n1")
        self.assertTrue(result)
        self.assertEqual(app.calls, ["section"])

    def test_explore_with_sections_goes_to_section_select(self):
        self._write_proposal("n1", _PROPOSAL_WITH_SECTIONS)
        app = self._make_app("explore")
        result = app._actions_advance_from_node_select("n1")
        self.assertTrue(result)
        self.assertEqual(app.calls, ["section"])

    def test_patch_with_plan_no_sections_goes_to_config(self):
        self._write_node("n1", plan_file="br_plans/n1_plan.md")
        self._write_plan("n1", _PLAN_NO_SECTIONS)
        app = self._make_app("patch")
        result = app._actions_advance_from_node_select("n1")
        self.assertTrue(result)
        self.assertEqual(app.calls, ["config"])

    def test_patch_without_plan_is_blocked(self):
        self._write_node("n1")  # no plan_file
        self._write_proposal("n1", _PROPOSAL_NO_SECTIONS)
        app = self._make_app("patch")
        result = app._actions_advance_from_node_select("n1")
        self.assertFalse(result)
        self.assertEqual(app.calls, [])
        self.assertTrue(app.notices)
        self.assertIn("no plan", app.notices[0][0])

    def test_empty_node_is_blocked(self):
        app = self._make_app("detail")
        result = app._actions_advance_from_node_select("")
        self.assertFalse(result)
        self.assertEqual(app.calls, [])
        self.assertTrue(app.notices)
        self.assertIn("Select a node first", app.notices[0][0])


# --------------------------------------------------------------------------
# _on_node_action_result — callback contract
# --------------------------------------------------------------------------

class OnNodeActionResultTests(unittest.TestCase):
    """The modal callback: cancel is a no-op (no tab was switched); a valid
    pick seeds the wizard and schedules the deferred Actions-tab entry."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_node_action_cb_")
        self.wt = Path(self.tmpdir)
        (self.wt / "br_nodes").mkdir()
        (self.wt / "br_proposals").mkdir()
        (self.wt / "br_plans").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_node(self, node_id: str) -> None:
        data = {
            "node_id": node_id,
            "parents": [],
            "description": f"desc {node_id}",
            "proposal_file": f"br_proposals/{node_id}.md",
        }
        (self.wt / "br_nodes" / f"{node_id}.yaml").write_text(
            yaml.safe_dump(data), encoding="utf-8"
        )
        (self.wt / "br_proposals" / f"{node_id}.md").write_text(
            _PROPOSAL_NO_SECTIONS, encoding="utf-8"
        )

    def _make_app(self):
        app = BrainstormApp.__new__(BrainstormApp)
        app.session_path = self.wt
        app._wizard_op = ""
        app._wizard_config = {}
        app._wizard_total_steps = 3
        app._wizard_has_sections = False
        app._cmp_section_checks = {}
        app.calls = []
        app.notices = []

        def fake_query_one(selector, *args):
            # The harness mounts no widgets; #actions_content lookups are
            # wrapped in try/except in the production code.
            raise RuntimeError("no widgets in this harness")

        app.query_one = fake_query_one
        app.notify = lambda msg, **kw: app.notices.append((msg, kw))
        app._wizard_fast_track = False
        app._wizard_subgraph = "_umbrella"
        app._actions_show_node_select = (
            lambda: app.calls.append("node_select")
        )
        app._actions_show_config = lambda: app.calls.append("config")
        app._actions_advance_from_node_select = (
            lambda node: app.calls.append(("advance", node)) or True
        )
        app.call_after_refresh = (
            lambda cb, *a, **kw: app.calls.append("after_refresh")
        )
        return app

    def test_cancel_is_a_noop(self):
        # No tab was switched when the picker opened, so cancelling leaves
        # the user on the originating tab with no wizard state touched.
        app = self._make_app()
        app._on_node_action_result("n1", None)
        self.assertEqual(app.calls, [])
        self.assertEqual(app._wizard_op, "")

    def test_missing_node_notifies_and_skips_wizard(self):
        app = self._make_app()
        app._on_node_action_result("ghost", "detail")
        self.assertTrue(app.notices)
        self.assertIn("no longer exists", app.notices[0][0])
        self.assertEqual(app.calls, [])

    def test_valid_pick_seeds_wizard_and_defers_tab_entry(self):
        self._write_node("n1")
        app = self._make_app()
        app._on_node_action_result("n1", "detail")
        self.assertEqual(app._wizard_op, "detail")
        self.assertEqual(app._wizard_config.get("_selected_node"), "n1")
        self.assertIn("node_select", app.calls)
        self.assertIn(("advance", "n1"), app.calls)
        # Tab entry is deferred (call_after_refresh) until the modal pop
        # settles — see _on_node_action_result.
        self.assertIn("after_refresh", app.calls)

    def test_fast_track_seeds_module_decompose_preset(self):
        # The "Fast-track this module" preset (t756_6 UC-3) seeds a
        # single-module module_decompose — NOT a new op — with the fast-track
        # arm set, sourced from the focused node's subgraph, and renders config
        # directly (module_decompose has no node-select step).
        self._write_node("n1")
        app = self._make_app()
        app._on_node_action_result("n1", "fast_track")
        self.assertEqual(app._wizard_op, "module_decompose")
        self.assertTrue(app._wizard_fast_track)
        from brainstorm.brainstorm_dag import _node_module
        self.assertEqual(
            app._wizard_subgraph, _node_module(app.session_path, "n1")
        )
        self.assertIn("config", app.calls)
        self.assertNotIn("node_select", app.calls)
        self.assertIn("after_refresh", app.calls)


class SetTotalStepsResetsFastTrackTests(unittest.TestCase):
    """`_set_total_steps` is the single op-select funnel; it must clear the
    transient fast-track arm so the preset's link-to-task pre-check never leaks
    into a later normal module_decompose (t756_6)."""

    def test_set_total_steps_clears_fast_track_flag(self):
        app = BrainstormApp.__new__(BrainstormApp)
        app._wizard_fast_track = True
        app._wizard_has_sections = True
        app._cmp_section_checks = {"x": True}
        app._wizard_subgraph = "some_module"
        app._set_total_steps()
        self.assertFalse(app._wizard_fast_track)


if __name__ == "__main__":
    unittest.main()
