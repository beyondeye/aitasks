"""Tests for the brainstorm node-action picker (t819).

Covers two pieces:

- ``NodeActionSelectModal`` — the dialog opened by ``A`` on the Graph and
  Dashboard tabs to pick a single-node operation. Pilot-driven, pushed onto a
  minimal host App (the modal needs no session infrastructure).
- ``_actions_advance_from_node_select`` — the wizard-routing helper shared by
  the Next button, keyboard ``Enter``, and the modal callback. Unit-tested with
  ``BrainstormApp.__init__`` bypassed and a temp session on disk.

The ``explore``-with-sections case is a regression guard: routing all
node-select advances through this helper fixed a pre-existing bug where keyboard
``Enter`` skipped section selection for a node-select operation.

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
from textual.widgets import Checkbox, Label  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    FuzzyCheckList,
    NodeActionSelectModal,
    OperationHelpModal,
    OperationRow,
)


# --------------------------------------------------------------------------
# NodeActionSelectModal — Pilot tests
# --------------------------------------------------------------------------

class _ModalHost(App):
    """Minimal host App that pushes a NodeActionSelectModal on mount."""

    def __init__(self, node_id: str, op_states=None, targets=None) -> None:
        super().__init__()
        self._node_id = node_id
        self._op_states = op_states
        self._targets = targets
        self.result = "UNSET"

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            NodeActionSelectModal(
                self._node_id, self._op_states, targets=self._targets
            ),
            self._record,
        )

    def _record(self, result) -> None:
        self.result = result


class NodeActionSelectModalTests(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_all_ops_listed_and_enabled_without_op_states(self):
        async def runner():
            # No op_states -> every op renders enabled (default-enabled). The
            # relevance/cardinality filtering itself is unit-tested separately.
            # Order is the contextual t983_4 order (compare/synthesize added).
            app = _ModalHost("n001_x")
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rows = list(app.screen.query(OperationRow))
                self.assertEqual(
                    [r.op_key for r in rows],
                    ["explore", "compare", "synthesize",
                     "module_decompose", "module_merge", "module_sync",
                     "fast_track", "delete"],
                )
                self.assertTrue(all(not r.op_disabled for r in rows))
                self.assertTrue(all(r.can_focus for r in rows))

        self._run(runner())

    def test_op_states_grey_multi_ops_at_single_selection(self):
        async def runner():
            # Cardinality-style op_states: single-node ops enabled, multi-node
            # ops greyed with reason (as the wrapper produces at cardinality 1).
            states = {
                "compare": (True, "mark 2+ nodes"),
                "synthesize": (True, "mark 2+ nodes"),
            }
            app = _ModalHost("n001_x", op_states=states)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rows = {r.op_key: r for r in app.screen.query(OperationRow)}
                self.assertTrue(rows["compare"].op_disabled)
                self.assertTrue(rows["synthesize"].op_disabled)
                self.assertIn("mark 2+ nodes", str(rows["compare"].render()))
                self.assertFalse(rows["explore"].op_disabled)

        self._run(runner())

    def test_op_states_disable_module_sync_with_reason(self):
        async def runner():
            states = {
                "module_decompose": (False, ""),
                "module_merge": (True, "no ancestor subgraph"),
                "module_sync": (True, "module has no linked task"),
            }
            app = _ModalHost("n001_x", op_states=states)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rows = {r.op_key: r for r in app.screen.query(OperationRow)}
                self.assertFalse(rows["module_decompose"].op_disabled)
                self.assertTrue(rows["module_merge"].op_disabled)
                self.assertTrue(rows["module_sync"].op_disabled)
                self.assertIn(
                    "module has no linked task",
                    str(rows["module_sync"].render()),
                )
                # delete has no op_states entry -> default enabled + focusable.
                self.assertFalse(rows["delete"].op_disabled)
                self.assertTrue(rows["delete"].can_focus)

        self._run(runner())

    def test_fast_track_row_label_and_select(self):
        async def runner():
            app = _ModalHost("n7")
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rows = {r.op_key: r for r in app.screen.query(OperationRow)}
                self.assertIn("Fast-track this module", str(rows["fast_track"].render()))
                # New order: explore, compare, synthesize, module_*×3,
                # fast_track(6), delete. Six downs from explore -> fast_track.
                for _ in range(6):
                    await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, "fast_track")

        self._run(runner())

    def test_title_is_operations_and_targets_carries_node_id(self):
        async def runner():
            app = _ModalHost("n042_special")
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                title = app.screen.query_one("#node_action_title", Label)
                self.assertIn("Operations", str(title.render()))
                # The contextual target set is surfaced in its own summary line.
                targets = app.screen.query_one("#node_action_targets", Label)
                rendered = str(targets.render())
                self.assertIn("n042_special", rendered)
                self.assertIn("Targets (1)", rendered)

        self._run(runner())

    def test_targets_summary_lists_marked_set(self):
        async def runner():
            app = _ModalHost(
                "n1", targets=["n1", "n2", "n3"]
            )
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rendered = str(
                    app.screen.query_one("#node_action_targets", Label).render()
                )
                self.assertIn("Targets (3)", rendered)
                for nid in ("n1", "n2", "n3"):
                    self.assertIn(nid, rendered)

        self._run(runner())

    def test_h_opens_help_for_help_bearing_op(self):
        async def runner():
            app = _ModalHost("n1")
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                # First enabled row is explore, which HAS an _OPERATION_HELP
                # entry -> H pushes the OperationHelpModal.
                await pilot.press("H")
                await pilot.pause()
                self.assertIsInstance(app.screen, OperationHelpModal)

        self._run(runner())

    def test_h_on_helpless_op_notifies_without_crash(self):
        async def runner():
            app = _ModalHost("n1")
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                notices = []
                app.notify = lambda msg, **kw: notices.append((msg, kw))
                # fast_track is the only op with NO _OPERATION_HELP entry (the
                # session-level delete/pause/etc. DO have help). It is row index
                # 6 — 6 downs from explore reach it.
                for _ in range(6):
                    await pilot.press("down")
                focused = app.screen.focused
                self.assertIsInstance(focused, OperationRow)
                self.assertEqual(focused.op_key, "fast_track")
                await pilot.press("H")
                await pilot.pause()
                # No help modal pushed; the dialog stays up and a notice fired.
                self.assertIsInstance(app.screen, NodeActionSelectModal)
                self.assertTrue(notices)
                self.assertIn("No help available", notices[0][0])

        self._run(runner())

    def test_enter_selects_first_enabled_op(self):
        async def runner():
            app = _ModalHost("n1")
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, "explore")

        self._run(runner())

    def test_down_navigates_then_enter_selects_compare(self):
        async def runner():
            app = _ModalHost("n1")
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                # Contextual order: explore -> compare. One down lands on the
                # second focusable row (compare, t983_4).
                await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, "compare")

        self._run(runner())

    def test_escape_cancels_with_none(self):
        async def runner():
            app = _ModalHost("n1")
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

class AdvanceFromNodeSelectTests(unittest.TestCase):
    """Routing assertions for the shared node-select advance helper."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_node_action_")
        self.wt = Path(self.tmpdir)
        (self.wt / "br_nodes").mkdir()
        (self.wt / "br_proposals").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_proposal(self, node_id: str, content: str) -> None:
        (self.wt / "br_proposals" / f"{node_id}.md").write_text(
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

    def test_explore_with_sections_goes_to_section_select(self):
        # Regression guard (re-expressed via the surviving `explore` op, which
        # uses section_select): keyboard Enter previously skipped section
        # selection; the shared helper now applies it uniformly.
        self._write_proposal("n1", _PROPOSAL_WITH_SECTIONS)
        app = self._make_app("explore")
        result = app._actions_advance_from_node_select("n1")
        self.assertTrue(result)
        self.assertEqual(app.calls, ["section"])

    def test_empty_node_is_blocked(self):
        app = self._make_app("explore")
        result = app._actions_advance_from_node_select("")
        self.assertFalse(result)
        self.assertEqual(app.calls, [])
        self.assertTrue(app.notices)
        self.assertIn("Select a node first", app.notices[0][0])


# --------------------------------------------------------------------------
# _on_node_action_result — callback contract
# --------------------------------------------------------------------------

class _FakeSelection:
    """Minimal NodeSelection stand-in for the callback harness (t983_6)."""

    def __init__(self, marked=()):
        self._marked = list(marked)

    def effective(self):
        return set(self._marked)


class OnNodeActionResultTests(unittest.TestCase):
    """The modal callback: cancel is a no-op (no tab was switched); a valid
    pick seeds the wizard and schedules the deferred Actions-tab entry."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_node_action_cb_")
        self.wt = Path(self.tmpdir)
        (self.wt / "br_nodes").mkdir()
        (self.wt / "br_proposals").mkdir()

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

    def _make_app(self, marked=()):
        app = BrainstormApp.__new__(BrainstormApp)
        app.session_path = self.wt
        app._wizard_op = ""
        app._wizard_config = {}
        app._wizard_total_steps = 3
        app._wizard_has_sections = False
        app._cmp_section_checks = {}
        app.calls = []
        app.notices = []
        app.scheduled = []
        # Minimal NodeSelection stand-in (t983_6): the compare/synthesize branch
        # reads self._selection.effective() to pre-check the source checklist.
        app._selection = _FakeSelection(marked)

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
        app._preseed_multi_node_checklist = (
            lambda op, m: app.calls.append(("preseed", op, tuple(m)))
        )

        def fake_car(cb, *a, **kw):
            app.calls.append("after_refresh")
            app.scheduled.append(cb)

        app.call_after_refresh = fake_car
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
        app._on_node_action_result("ghost", "explore")
        self.assertTrue(app.notices)
        self.assertIn("no longer exists", app.notices[0][0])
        self.assertEqual(app.calls, [])

    def test_valid_pick_seeds_wizard_and_drops_node_select(self):
        # explore: the node is contextual, so the launch seeds _selected_node +
        # pre_seeded_node and skips the in-wizard node-pick step (t983_6),
        # advancing straight into section_select/config.
        self._write_node("n1")
        app = self._make_app()
        app._on_node_action_result("n1", "explore")
        self.assertEqual(app._wizard_op, "explore")
        self.assertEqual(app._wizard_config.get("_selected_node"), "n1")
        self.assertTrue(app._wizard_config.get("pre_seeded_node"))
        self.assertNotIn("node_select", app.calls)  # node-pick step dropped
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
        # pre_seeded_node drops the (over-counted) node_select step (t983_6).
        self.assertTrue(app._wizard_config.get("pre_seeded_node"))
        self.assertIn("after_refresh", app.calls)

    def test_module_decompose_sets_pre_seeded_node(self):
        # Contextual module_decompose seeds the subgraph and flags
        # pre_seeded_node so step numbering omits node_select (t983_6).
        self._write_node("n1")
        app = self._make_app()
        app._on_node_action_result("n1", "module_decompose")
        self.assertEqual(app._wizard_op, "module_decompose")
        self.assertTrue(app._wizard_config.get("pre_seeded_node"))
        self.assertIn("config", app.calls)
        self.assertNotIn("node_select", app.calls)

    def test_compare_routes_to_config_not_node_select(self):
        # Multi-node ops pick nodes in the config step (cmp_nodes/syn_nodes),
        # so the t983_4 branch must render config directly — NOT the explore-only
        # node-select branch, which would mis-drive them (seedless-launch guard).
        self._write_node("n1")
        app = self._make_app()
        app._on_node_action_result("n1", "compare")
        self.assertEqual(app._wizard_op, "compare")
        self.assertIn("config", app.calls)
        self.assertNotIn("node_select", app.calls)
        self.assertIn("after_refresh", app.calls)

    def test_synthesize_routes_to_config_not_node_select(self):
        self._write_node("n1")
        app = self._make_app()
        app._on_node_action_result("n1", "synthesize")
        self.assertEqual(app._wizard_op, "synthesize")
        self.assertIn("config", app.calls)
        self.assertNotIn("node_select", app.calls)
        self.assertIn("after_refresh", app.calls)

    def test_compare_preseeds_checklist_from_marked_set(self):
        # With a 2+ marked set driving the launch (t983_6), the source-node
        # checklist is pre-checked from the marked ids. The pre-check is
        # scheduled via call_after_refresh (boxes must be mounted first).
        self._write_node("n1")
        self._write_node("n2")
        app = self._make_app(marked=["n1", "n2"])
        app._on_node_action_result("n1", "compare")
        for cb in app.scheduled:  # run the deferred callbacks
            cb()
        self.assertIn(("preseed", "compare", ("n1", "n2")), app.calls)

    def test_synthesize_preseeds_checklist_from_marked_set(self):
        self._write_node("n1")
        self._write_node("n2")
        app = self._make_app(marked=["n2", "n1"])
        app._on_node_action_result("n1", "synthesize")
        for cb in app.scheduled:
            cb()
        # marked is sorted before seeding
        self.assertIn(("preseed", "synthesize", ("n1", "n2")), app.calls)

    def test_compare_without_marked_set_does_not_preseed(self):
        # A lone primary (no marked set) → no pre-check scheduled. (In the live
        # app compare is greyed at cardinality 1; this guards the seedless path.)
        self._write_node("n1")
        app = self._make_app()  # no marked nodes
        app._on_node_action_result("n1", "compare")
        for cb in app.scheduled:
            cb()
        self.assertNotIn(
            ("preseed", "compare", ()), [c for c in app.calls if isinstance(c, tuple) and c[0] == "preseed"]
        )
        self.assertFalse(
            [c for c in app.calls if isinstance(c, tuple) and c[0] == "preseed"]
        )


class _FclHost(App):
    """Minimal host mounting a syn_nodes FuzzyCheckList for the preseed pilot."""

    def __init__(self, nodes) -> None:
        super().__init__()
        self._node_ids = nodes

    def compose(self) -> ComposeResult:
        yield FuzzyCheckList(
            self._node_ids, item_class="chk_node", id="syn_nodes"
        )


class PreseedChecklistPilotTests(unittest.TestCase):
    """Runtime check that _preseed_multi_node_checklist actually flips the
    marked rows' Checkbox.value (the code the callback unit tests stub out)."""

    def test_marked_nodes_get_checked(self):
        async def run():
            host = _FclHost(["n1", "n2", "n3"])
            async with host.run_test() as pilot:
                await pilot.pause()
                # synthesize takes the no-refresh path (compare also calls the
                # session-backed dimension/section refreshes).
                BrainstormApp._preseed_multi_node_checklist(
                    host, "synthesize", ["n1", "n3"]
                )
                await pilot.pause()
                checked = {
                    str(cb.label): cb.value
                    for cb in host.query("Checkbox.chk_node")
                }
            return checked

        checked = asyncio.run(run())
        self.assertEqual(checked, {"n1": True, "n2": False, "n3": True})


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
