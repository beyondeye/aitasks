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

import contextlib  # noqa: E402
import types  # noqa: E402

from textual.app import App, ComposeResult, active_app  # noqa: E402
from textual.widgets import Checkbox, Label  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    DEFAULT_LAUNCH_MODE,
    ActionsWizardScreen,
    BrainstormApp,
    FuzzyCheckList,
    NodeActionSelectModal,
    OperationHelpModal,
    OperationRow,
)


@contextlib.contextmanager
def _as_active_app(app):
    """Make ``screen.app`` resolve to ``app`` for a __new__'d screen under test
    (t983_11). ``Screen.app`` reads the ``active_app`` ContextVar, so the wizard
    screen's ``self.app._node_*`` disk-reader calls resolve to the fake host."""
    token = active_app.set(app)
    try:
        yield
    finally:
        active_app.reset(token)


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

    def _make_screen(self, wizard_op: str):
        """An ActionsWizardScreen with __init__ bypassed, wired for routing
        capture (t983_11). The helper reads section presence via
        ``self.app._node_has_sections`` — backed by a real BrainstormApp host
        (disk reader) made active via ``_as_active_app``."""
        screen = ActionsWizardScreen.__new__(ActionsWizardScreen)
        screen._wizard_op = wizard_op
        screen._wizard_config = {}
        screen._wizard_has_sections = False
        screen.calls = []
        screen.notices = []
        screen.notify = lambda msg, **kw: screen.notices.append((msg, kw))
        screen._actions_show_config = lambda: screen.calls.append("config")
        screen._actions_show_confirm = lambda: screen.calls.append("confirm")
        screen._actions_show_section_select = (
            lambda: screen.calls.append("section")
        )
        host = BrainstormApp.__new__(BrainstormApp)
        host.session_path = self.wt
        screen._host = host
        return screen

    def test_explore_no_sections_goes_to_config(self):
        self._write_proposal("n1", _PROPOSAL_NO_SECTIONS)
        screen = self._make_screen("explore")
        with _as_active_app(screen._host):
            result = screen._actions_advance_from_node_select("n1")
        self.assertTrue(result)
        self.assertEqual(screen.calls, ["config"])

    def test_explore_with_sections_goes_to_section_select(self):
        # Regression guard (re-expressed via the surviving `explore` op, which
        # uses section_select): keyboard Enter previously skipped section
        # selection; the shared helper now applies it uniformly.
        self._write_proposal("n1", _PROPOSAL_WITH_SECTIONS)
        screen = self._make_screen("explore")
        with _as_active_app(screen._host):
            result = screen._actions_advance_from_node_select("n1")
        self.assertTrue(result)
        self.assertEqual(screen.calls, ["section"])

    def test_empty_node_is_blocked(self):
        screen = self._make_screen("explore")
        result = screen._actions_advance_from_node_select("")
        self.assertFalse(result)
        self.assertEqual(screen.calls, [])
        self.assertTrue(screen.notices)
        self.assertIn("Select a node first", screen.notices[0][0])


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
    """The modal callback (t983_11): cancel/missing-node are no-ops; delete is
    handled inline; every other op pushes ActionsWizardScreen seeded from the
    contextual selection. The per-op seeding/routing it used to do inline now
    lives in the screen's on_mount (see ActionsWizardScreenSeedTests)."""

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
        app.notices = []
        app.pushed = []
        app.deleted = []
        # Minimal NodeSelection stand-in (t983_6): the contextual seed reads
        # self._selection.effective() for the compare/synthesize pre-check.
        app._selection = _FakeSelection(marked)
        app.notify = lambda msg, **kw: app.notices.append((msg, kw))
        app.push_screen = (
            lambda screen, cb=None: app.pushed.append((screen, cb))
        )
        app._open_delete_node_modal = lambda nid: app.deleted.append(nid)
        return app

    def test_cancel_is_a_noop(self):
        # op_key None (Cancel) → nothing pushed, no state touched.
        app = self._make_app()
        app._on_node_action_result("n1", None)
        self.assertEqual(app.pushed, [])

    def test_missing_node_notifies_and_skips_wizard(self):
        app = self._make_app()
        app._on_node_action_result("ghost", "explore")
        self.assertTrue(app.notices)
        self.assertIn("no longer exists", app.notices[0][0])
        self.assertEqual(app.pushed, [])

    def test_delete_handled_inline_without_wizard(self):
        # delete is synchronous (DeleteNodeModal) — no wizard screen is pushed.
        self._write_node("n1")
        app = self._make_app()
        app._on_node_action_result("n1", "delete")
        self.assertEqual(app.deleted, ["n1"])
        self.assertEqual(app.pushed, [])

    def test_valid_pick_pushes_wizard_with_seed(self):
        self._write_node("n1")
        app = self._make_app()
        app._on_node_action_result("n1", "explore")
        self.assertEqual(len(app.pushed), 1)
        screen, cb = app.pushed[0]
        self.assertIsInstance(screen, ActionsWizardScreen)
        self.assertEqual(screen._seed_op, "explore")
        self.assertEqual(screen._seed_node, "n1")
        self.assertEqual(cb, app._on_wizard_result)

    def test_compare_seed_carries_marked_set(self):
        # The contextual marked set rides into the screen as the seed; the
        # screen's on_mount pre-checks the source checklist from it (t983_6).
        self._write_node("n1")
        self._write_node("n2")
        app = self._make_app(marked=["n2", "n1"])
        app._on_node_action_result("n1", "compare")
        screen, _ = app.pushed[0]
        self.assertEqual(screen._seed_op, "compare")
        self.assertEqual(sorted(screen._seed_marked), ["n1", "n2"])

    def test_on_wizard_result_none_is_noop(self):
        app = self._make_app()
        executed = []
        app._execute_design_op = lambda r: executed.append(r)
        app._on_wizard_result(None)
        self.assertEqual(executed, [])

    def test_on_wizard_result_runs_execute_design_op(self):
        app = self._make_app()
        executed = []
        app._execute_design_op = lambda r: executed.append(r)
        payload = {"op": "explore", "config": {"x": 1}, "subgraph": "_umbrella"}
        app._on_wizard_result(payload)
        self.assertEqual(executed, [payload])


class ActionsWizardScreenSeedTests(unittest.TestCase):
    """The wizard screen's on_mount reproduces the per-op seeding/routing the
    modal callback used to perform inline (t983_6 contract, re-hosted into the
    screen in t983_11). Driven with __init__ bypassed + render methods stubbed;
    section/subgraph disk reads resolve via a real BrainstormApp host made
    active with _as_active_app."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_wizard_seed_")
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

    def _make_screen(self, op_key, node_id="n1", marked=()):
        screen = ActionsWizardScreen.__new__(ActionsWizardScreen)
        screen._seed_op = op_key
        screen._seed_node = node_id
        screen._seed_marked = list(marked)
        screen._wizard_op = ""
        screen._wizard_config = {}
        screen._wizard_has_sections = False
        screen._wizard_subgraph_count = 1
        screen._wizard_subgraph = "_umbrella"
        screen._wizard_fast_track = False
        screen._cmp_section_checks = {}
        screen.calls = []
        screen.scheduled = []
        screen._actions_show_config = lambda: screen.calls.append("config")
        screen._actions_show_node_select = (
            lambda: screen.calls.append("node_select")
        )
        screen._actions_advance_from_node_select = (
            lambda node: screen.calls.append(("advance", node)) or True
        )
        screen._preseed_multi_node_checklist = (
            lambda op, m: screen.calls.append(("preseed", op, tuple(m)))
        )

        def fake_car(cb, *a, **kw):
            screen.calls.append("after_refresh")
            screen.scheduled.append(cb)

        screen.call_after_refresh = fake_car
        host = BrainstormApp.__new__(BrainstormApp)
        host.session_path = self.wt
        screen._host = host
        return screen

    def _run_mount(self, screen):
        with _as_active_app(screen._host):
            screen.on_mount()

    def test_explore_seeds_and_drops_node_select(self):
        self._write_node("n1")
        s = self._make_screen("explore")
        self._run_mount(s)
        self.assertEqual(s._wizard_op, "explore")
        self.assertEqual(s._wizard_config.get("_selected_node"), "n1")
        self.assertTrue(s._wizard_config.get("pre_seeded_node"))
        self.assertNotIn("node_select", s.calls)
        self.assertIn(("advance", "n1"), s.calls)

    def test_fast_track_seeds_module_decompose_preset(self):
        self._write_node("n1")
        s = self._make_screen("fast_track")
        self._run_mount(s)
        self.assertEqual(s._wizard_op, "module_decompose")
        self.assertTrue(s._wizard_fast_track)
        from brainstorm.brainstorm_dag import _node_module
        self.assertEqual(s._wizard_subgraph, _node_module(self.wt, "n1"))
        self.assertTrue(s._wizard_config.get("pre_seeded_node"))
        self.assertIn("config", s.calls)
        self.assertNotIn("node_select", s.calls)

    def test_module_decompose_sets_pre_seeded_node(self):
        self._write_node("n1")
        s = self._make_screen("module_decompose")
        self._run_mount(s)
        self.assertEqual(s._wizard_op, "module_decompose")
        self.assertTrue(s._wizard_config.get("pre_seeded_node"))
        self.assertIn("config", s.calls)
        self.assertNotIn("node_select", s.calls)

    def test_compare_routes_to_config_and_preseeds(self):
        self._write_node("n1")
        self._write_node("n2")
        s = self._make_screen("compare", marked=["n1", "n2"])
        self._run_mount(s)
        self.assertEqual(s._wizard_op, "compare")
        self.assertIn("config", s.calls)
        self.assertNotIn("node_select", s.calls)
        for cb in s.scheduled:
            cb()
        self.assertIn(("preseed", "compare", ("n1", "n2")), s.calls)

    def test_synthesize_routes_to_config_and_preseeds(self):
        self._write_node("n1")
        self._write_node("n2")
        s = self._make_screen("synthesize", marked=["n2", "n1"])
        self._run_mount(s)
        self.assertEqual(s._wizard_op, "synthesize")
        self.assertIn("config", s.calls)
        for cb in s.scheduled:
            cb()
        # marked is sorted before pre-check
        self.assertIn(("preseed", "synthesize", ("n1", "n2")), s.calls)

    def test_compare_without_marked_set_does_not_preseed(self):
        self._write_node("n1")
        s = self._make_screen("compare")  # no marked nodes
        self._run_mount(s)
        for cb in s.scheduled:
            cb()
        self.assertFalse(
            [c for c in s.calls if isinstance(c, tuple) and c[0] == "preseed"]
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
                ActionsWizardScreen._preseed_multi_node_checklist(
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
        screen = ActionsWizardScreen.__new__(ActionsWizardScreen)
        screen._wizard_fast_track = True
        screen._wizard_has_sections = True
        screen._cmp_section_checks = {"x": True}
        screen._wizard_subgraph = "some_module"
        screen._set_total_steps()
        self.assertFalse(screen._wizard_fast_track)


class WizardLaunchResultTests(unittest.TestCase):
    """Launch = dismiss-with-result (t983_11): the screen collects launch_mode,
    then dismisses with a ``{op, config, subgraph}`` payload that the App's
    _execute_design_op consumes (the App no longer reads self._wizard_* from the
    wizard directly)."""

    def test_launch_dismisses_with_op_config_subgraph(self):
        screen = ActionsWizardScreen.__new__(ActionsWizardScreen)
        screen._wizard_op = "explore"
        screen._wizard_config = {"mandate": "x", "parallel": 2}
        screen._wizard_subgraph = "_umbrella"
        dismissed = []
        screen.dismiss = lambda result: dismissed.append(result)
        # No launch-mode field mounted → falls back to DEFAULT_LAUNCH_MODE.

        def _raise(*a, **k):
            raise RuntimeError("no launch-mode field in this harness")

        screen.query_one = _raise
        screen._on_actions_launch()

        self.assertEqual(len(dismissed), 1)
        res = dismissed[0]
        self.assertEqual(res["op"], "explore")
        self.assertEqual(res["subgraph"], "_umbrella")
        self.assertEqual(res["config"]["launch_mode"], DEFAULT_LAUNCH_MODE)
        self.assertEqual(res["config"]["mandate"], "x")
        self.assertEqual(res["config"]["parallel"], 2)
        # The payload carries a *copy* of the config — later wizard mutations
        # must not leak into the dispatched result.
        screen._wizard_config["mandate"] = "y"
        self.assertEqual(res["config"]["mandate"], "x")


if __name__ == "__main__":
    unittest.main()
