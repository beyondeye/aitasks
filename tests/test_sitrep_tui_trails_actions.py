#!/usr/bin/env python3
"""The sitrep TUI's "show this task in ait trails" (t2211_10): the `z` key, the
picker, and the trail rows of a task item's details.

Built on ``tests/test_sitrep_tui_actions.py``'s fixture and ``_Case`` (helpers
only). The trail membership comes from a stub ``trails_scan`` seam, optionally
gated by an Event; the launcher ``actions.open_in_trails`` is stubbed, so
nothing reaches tmux.

Groups worth naming:

``SelectionIdentityTests``
    Trail rows are keyed by HANDLE. A rescan that removes or reorders other
    trails keeps the user's row; one that removes the user's trail clears the
    selection -- never a neighbouring row that Enter would then open.

``LookingTests``
    "Trails: looking…" is replaced when the scan lands, on the ACTIVE details
    only; a closed or covered details screen is never written by the callback.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_sitrep_tui_trails_actions.py -q
"""

from __future__ import annotations

import threading
import unittest
from pathlib import Path
from unittest import mock

import test_sitrep_tui_actions as ta  # noqa: E402  (helpers only, never a test class)

from sitrep_tui import sitrep_tui_actions as actions  # noqa: E402
from sitrep_tui import sitrep_tui_app as appmod  # noqa: E402
from sitrep_tui import sitrep_tui_model as model  # noqa: E402
from sitrep_tui import sitrep_tui_trails as tt  # noqa: E402

setUpModule = ta.setUpModule          # noqa: N816 - the shared fixture template
tearDownModule = ta.tearDownModule    # noqa: N816

SIZE = ta.SIZE
A, B, C = "art:trail-alpha", "art:trail-beta", "art:trail-gamma"
REF = {A: tt.TrailRef(A, "Alpha", (1,)), B: tt.TrailRef(B, "Beta", (2,)),
       C: tt.TrailRef(C, "Gamma")}


def member(by_task: dict, partial: str = "") -> tt.Membership:
    return tt.Membership(True, partial=partial, by_task={
        k: tuple(REF[h] for h in v) for k, v in by_task.items()})


class Scan:
    """The `trails_scan` seam: answers `result` (a Membership), counts calls,
    and blocks on `gate` when one is set."""

    def __init__(self, result: "tt.Membership | None" = None):
        self.result = result or member({})
        self.calls = 0
        self.gate: "threading.Event | None" = None

    def __call__(self, root):
        self.calls += 1
        if self.gate is not None:
            self.gate.wait(30)
        return self.result


class _TrailsCase(ta._Case):
    def setUp(self):
        super().setUp()
        self.jumps: list = []
        patcher = mock.patch.object(actions, "open_in_trails", self._jump)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _jump(self, root, handle, task_id, name=""):
        self.jumps.append((root, handle, task_id))
        return [(f"Showing t{task_id} in trail {name}", "information")]

    def make_trails_app(self, scan: Scan, **kw):
        self.scan = scan
        return self.make_app(trails_scan=scan, **kw)

    async def settle(self, app, pilot):
        await app.workers.wait_for_complete()
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()

    def task_id(self, app, name: str) -> str:
        return model.task_ref_id(app.store.items[self.ids[name]])

    def links(self, screen) -> list:
        ol = screen.query_one("#sd-links")
        return [ol.get_option_at_index(i) for i in range(ol.option_count)]

    def link_ids(self, screen) -> list:
        return [o.id for o in self.links(screen)]

    def highlight(self, screen, option_id: str) -> None:
        ol = screen.query_one("#sd-links")
        ol.highlighted = ol.get_option_index(option_id)
        ol.focus()

    def highlighted_id(self, screen) -> "str | None":
        opt = screen.query_one("#sd-links").highlighted_option
        return opt.id if opt is not None else None


# -- bindings ------------------------------------------------------------------------

class TrailsBindingsTests(_TrailsCase):

    async def test_z_only_for_a_task_item_known_to_be_in_a_trail(self):
        for state in ("in", "none", "unknown", "partial-none"):
            with self.subTest(state=state):
                scan = Scan({
                    "in": member({"10": [A], "12": [A]}),
                    "none": member({"12": [A]}),
                    "unknown": tt.Membership(False, "export exceeded 30s"),
                    "partial-none": member({"12": [A]}, partial="art:x did not load"),
                }[state])
                app = self.make_trails_app(scan)
                async with app.run_test(size=SIZE) as pilot:
                    await self.settle(app, pilot)
                    want = state == "in"
                    self.select(app, self.ids["task"])
                    self.assertEqual(self.shown(app, "open_in_trails"), want, "main")
                    await self.open_details(app, pilot, self.ids["task"])
                    await self.settle(app, pilot)
                    self.assertEqual(self.shown(app, "open_in_trails"), want, "details")
                    await pilot.press("escape")
                    await pilot.pause()
                    # Never for a non-task item, whatever its ref names.
                    for other in ("triage", "push", "pushref", "xref", "question"):
                        self.select(app, self.ids[other])
                        self.assertFalse(self.shown(app, "open_in_trails"), other)
                    self.select(app, self.ids["task"])
                    await pilot.press("l")
                    await pilot.pause()
                    self.assertIsInstance(app.screen, appmod.QaLogScreen)
                    self.assertFalse(self.shown(app, "open_in_trails"), "Q&A screen")

    async def test_hidden_while_looking_and_with_no_scanner(self):
        scan = Scan(member({"10": [A]}))
        scan.gate = threading.Event()
        app = self.make_trails_app(scan)
        try:
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.select(app, self.ids["task"])
                self.assertEqual(app.trails_for("10"), tt.TASK_TRAILS_LOOKING)
                self.assertFalse(self.shown(app, "open_in_trails"))
                scan.gate.set()
                await self.settle(app, pilot)
                self.assertTrue(self.shown(app, "open_in_trails"))
        finally:
            scan.gate.set()
        off = self.make_app()
        async with off.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(off, self.ids["task"])
            self.assertEqual(off.trails_for("10"), tt.TASK_TRAILS_OFF)
            self.assertFalse(self.shown(off, "open_in_trails"))
            screen = await self.open_details(off, pilot, self.ids["task"])
            self.assertFalse(any((i or "").startswith("trail") for i in self.link_ids(screen)))
            self.assertNotIn("Trails", screen.body_text(model.resolve_now()))

    async def test_the_footer_names_z(self):
        app = self.make_trails_app(Scan(member({"10": [A]})))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            self.select(app, self.ids["task"])
            app.refresh_bindings()
            await pilot.pause()
            self.assertIn("z", app.screen.active_bindings)
            self.assertEqual(app.key_for("open_in_trails"), "z")


# -- the key on the main list -----------------------------------------------------------

class MainListTests(_TrailsCase):

    async def test_one_trail_opens_it(self):
        app = self.make_trails_app(Scan(member({"10": [A]})))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            self.select(app, self.ids["task"])
            await pilot.press("z")
            await self.settle(app, pilot)
        self.assertEqual(self.jumps, [(self.root, A, "10")])
        self.assertTrue(self.toast_with("Showing t10 in trail Alpha"))

    async def test_two_trails_open_the_picker(self):
        app = self.make_trails_app(Scan(member({"10": [A, B]})))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            self.select(app, self.ids["task"])
            await pilot.press("z")
            await pilot.pause()
            self.assertIsInstance(app.screen, tt.TrailPickerDialog)
            self.assertEqual(self.jumps, [])
            await pilot.press("down")
            await pilot.press("enter")
            await self.settle(app, pilot)
            self.assertEqual(self.jumps, [(self.root, B, "10")])
            await pilot.press("z")
            await pilot.pause()
            await pilot.press("escape")
            await self.settle(app, pilot)
        self.assertEqual(len(self.jumps), 1)

    async def test_the_picker_callback_rechecks_the_item(self):
        num = self.ids["task"]
        app = self.make_trails_app(Scan(member({"10": [A, B]})))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            self.select(app, num)
            with mock.patch.object(app, "push_screen") as push:
                app.action_open_in_trails()
            callback = push.call_args[0][1]
            callback(B)                     # control: unchanged -> shown
            await self.settle(app, pilot)
            self.assertEqual(self.jumps, [(self.root, B, "10")])
            with mock.patch.object(app, "push_screen") as push:
                app.action_open_in_trails()
            callback = push.call_args[0][1]
            self.writer("update", f"c{num}", "--ref", "t12")
            await app._poll_store()
            await self.settle(app, pilot)
            callback(B)
            await self.settle(app, pilot)
        self.assertEqual(len(self.jumps), 1)
        self.assertTrue(self.toast_with("changed while the dialog was open"))


# -- the details ---------------------------------------------------------------------

class DetailsTests(_TrailsCase):

    async def test_the_trails_line_and_one_row_per_trail(self):
        app = self.make_trails_app(Scan(member({"10": [A, B]})))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            screen = await self.open_details(app, pilot, self.ids["task"])
            await self.settle(app, pilot)
            body = screen.body_text(model.resolve_now())
            self.assertIn("Alpha (w1), Beta (w2)", body)
            ids = self.link_ids(screen)
            self.assertEqual([i for i in ids if i.startswith("trail")],
                             [f"trail:{A}", f"trail:{B}"])
            self.assertEqual(ids.index(f"trail:{A}"), ids.index("taskdesc") + 1)
            labels = [str(o.prompt) for o in self.links(screen)]
            self.assertIn("In trail: Beta (art:trail-beta) — wave 2", labels)

    async def test_enter_on_a_row_opens_that_trail_and_a_click_only_selects(self):
        app = self.make_trails_app(Scan(member({"10": [A, B]})))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            screen = await self.open_details(app, pilot, self.ids["task"])
            await self.settle(app, pilot)
            ol = screen.query_one("#sd-links")
            idx = ol.get_option_index(f"trail:{B}")
            await pilot.click("#sd-links", offset=(4, idx + 1))
            await pilot.pause()
            self.assertEqual(self.highlighted_id(screen), f"trail:{B}")
            self.assertEqual(self.jumps, [], "a click only selects")
            await pilot.press("enter")
            await self.settle(app, pilot)
        self.assertEqual(self.jumps, [(self.root, B, "10")])

    async def test_z_acts_on_the_highlighted_row_else_the_picker(self):
        app = self.make_trails_app(Scan(member({"10": [A, B]})))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            screen = await self.open_details(app, pilot, self.ids["task"])
            await self.settle(app, pilot)
            self.highlight(screen, f"trail:{B}")
            await pilot.press("z")
            await self.settle(app, pilot)
            self.assertEqual(self.jumps, [(self.root, B, "10")])
            self.highlight(screen, "taskdesc")
            await pilot.press("z")
            await pilot.pause()
            self.assertIsInstance(app.screen, tt.TrailPickerDialog)
            await pilot.press("escape")
            await self.settle(app, pilot)
        self.assertEqual(len(self.jumps), 1)

    async def test_a_failed_lookup_shows_unknown_and_no_rows(self):
        app = self.make_trails_app(Scan(tt.Membership(False, "export exceeded 30s")))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            screen = await self.open_details(app, pilot, self.ids["task"])
            await self.settle(app, pilot)
            rows = [o for o in self.links(screen) if (o.id or "").startswith("trail")]
            self.assertEqual([(o.id, o.disabled) for o in rows], [("trailx", True)])
            self.assertIn("unknown (export exceeded 30s)", str(rows[0].prompt))
            self.assertIn("unknown (export exceeded 30s)",
                          screen.body_text(model.resolve_now()))
            self.assertFalse(self.shown(app, "open_in_trails"))

    async def test_a_partial_scan_keeps_the_known_rows(self):
        app = self.make_trails_app(Scan(member({"10": [A]}, partial="art:x did not load")))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            screen = await self.open_details(app, pilot, self.ids["task"])
            await self.settle(app, pilot)
            rows = [(o.id, o.disabled) for o in self.links(screen)
                    if (o.id or "").startswith("trail")]
            self.assertEqual(rows, [(f"trail:{A}", False), ("trailx", True)])
            self.assertTrue(self.shown(app, "open_in_trails"))

    async def test_a_moved_rev_refreshes_the_details_and_launches_nothing(self):
        num = self.ids["task"]
        for route in ("z", "enter"):
            with self.subTest(route=route):
                self.jumps.clear()
                app = self.make_trails_app(Scan(member({"10": [A], "12": [A]})))
                async with app.run_test(size=SIZE) as pilot:
                    await self.settle(app, pilot)
                    old = await self.open_details(app, pilot, num)
                    await self.settle(app, pilot)
                    self.highlight(old, f"trail:{A}")
                    self.writer("update", f"c{num}", "--ref", "t12")
                    await app._poll_store()
                    await self.settle(app, pilot)
                    await pilot.press(route)
                    await self.until(pilot, lambda: (isinstance(app.screen, appmod.ItemDetailScreen)
                                                     and app.screen is not old),
                                     "fresh details")
                    await self.settle(app, pilot)
                    self.assertEqual(self.jumps, [])
                    self.assertTrue(self.toast_with("changed since these details were opened"))
                # Restore the fixture item for the next route.
                self.writer("update", f"c{num}", "--ref", "t10")

    async def test_opening_details_rescans(self):
        app = self.make_trails_app(Scan(member({"10": [A]})))
        async with app.run_test(size=SIZE) as pilot:
            await self.settle(app, pilot)
            before = self.scan.calls
            await self.open_details(app, pilot, self.ids["task"])
            await self.settle(app, pilot)
            self.assertEqual(self.scan.calls, before + 1)
            await pilot.press("escape")
            await pilot.pause()
            # A non-task item's details need no trail lookup.
            await self.open_details(app, pilot, self.ids["question"])
            await self.settle(app, pilot)
            self.assertEqual(self.scan.calls, before + 1)


# -- selection identity across a refresh ------------------------------------------------

class SelectionIdentityTests(_TrailsCase):

    async def _details_with_b_highlighted(self, app, pilot):
        await self.settle(app, pilot)
        screen = await self.open_details(app, pilot, self.ids["task"])
        await self.settle(app, pilot)
        self.highlight(screen, f"trail:{B}")
        return screen

    async def test_removal_before_the_selected_row_keeps_it(self):
        app = self.make_trails_app(Scan(member({"10": [A, B, C]})))
        async with app.run_test(size=SIZE) as pilot:
            screen = await self._details_with_b_highlighted(app, pilot)
            app._on_trails_scanned(member({"10": [B, C]}))
            await pilot.pause()
            self.assertEqual(self.highlighted_id(screen), f"trail:{B}")
            await pilot.press("enter")
            await self.settle(app, pilot)
        self.assertEqual(self.jumps, [(self.root, B, "10")])

    async def test_a_reorder_keeps_the_selected_row(self):
        app = self.make_trails_app(Scan(member({"10": [A, B, C]})))
        async with app.run_test(size=SIZE) as pilot:
            screen = await self._details_with_b_highlighted(app, pilot)
            app._on_trails_scanned(tt.Membership(True, by_task={
                "10": (REF[C], REF[B])}))
            await pilot.pause()
            self.assertEqual(self.link_ids(screen)[1:3], [f"trail:{C}", f"trail:{B}"])
            self.assertEqual(self.highlighted_id(screen), f"trail:{B}")
            await pilot.press("z")
            await self.settle(app, pilot)
        self.assertEqual(self.jumps, [(self.root, B, "10")])

    async def test_a_removed_selected_trail_clears_the_selection(self):
        app = self.make_trails_app(Scan(member({"10": [A, B, C]})))
        async with app.run_test(size=SIZE) as pilot:
            screen = await self._details_with_b_highlighted(app, pilot)
            app._on_trails_scanned(member({"10": [A, C]}))
            await pilot.pause()
            self.assertIsNone(self.highlighted_id(screen))
            self.assertTrue(self.toast_with("Beta no longer lists t10 — selection cleared"))
            await pilot.press("enter")
            await self.settle(app, pilot)
            self.assertEqual(self.jumps, [], "Enter opens nothing")
            await pilot.press("z")
            await pilot.pause()
            self.assertIsInstance(app.screen, tt.TrailPickerDialog)
            await pilot.press("escape")
            await self.settle(app, pilot)
        self.assertEqual(self.jumps, [])


# -- "looking…" and the callback's target ------------------------------------------------

class LookingTests(_TrailsCase):

    async def test_looking_is_replaced_when_the_scan_lands(self):
        scan = Scan(member({"10": [A]}))
        scan.gate = threading.Event()
        app = self.make_trails_app(scan)
        try:
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                screen = await self.open_details(app, pilot, self.ids["task"])
                rows = [(o.id, o.disabled, str(o.prompt)) for o in self.links(screen)
                        if (o.id or "").startswith("trail")]
                self.assertEqual(rows, [("trailx", True, "Trails: looking…")])
                self.assertIn("looking…", screen.body_text(model.resolve_now()))
                scan.gate.set()
                await self.settle(app, pilot)
                self.assertIn(f"trail:{A}", self.link_ids(screen))
                self.assertNotIn("trailx", self.link_ids(screen))
                self.assertIn("Alpha (w1)", screen.body_text(model.resolve_now()))
        finally:
            scan.gate.set()

    async def test_a_closed_or_replaced_details_screen_is_never_written(self):
        scan = Scan(member({"10": [A]}))
        scan.gate = threading.Event()
        app = self.make_trails_app(scan)
        try:
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                closed = await self.open_details(app, pilot, self.ids["task"])
                await pilot.press("escape")
                await pilot.pause()
                other = await self.open_details(app, pilot, self.ids["question"])
                other_ids = self.link_ids(other)
                with mock.patch.object(appmod.ItemDetailScreen, "set_trails",
                                       autospec=True,
                                       side_effect=appmod.ItemDetailScreen.set_trails) as st:
                    scan.gate.set()
                    await self.settle(app, pilot)
                    touched = [c.args[0] for c in st.call_args_list]
                self.assertNotIn(closed, touched, "a closed details screen")
                self.assertEqual(closed._trails, tt.TASK_TRAILS_LOOKING)
                self.assertEqual(self.link_ids(other), other_ids,
                                 "the other item's rows are unchanged")
        finally:
            scan.gate.set()

    async def test_a_covered_details_screen_catches_up_on_resume(self):
        scan = Scan(member({"10": [A]}))
        scan.gate = threading.Event()
        app = self.make_trails_app(scan)
        try:
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                screen = await self.open_details(app, pilot, self.ids["task"])
                app.push_screen(appmod.QaLogScreen(app.qa, app.qa_error))   # cover it
                await pilot.pause()
                self.assertIsNot(app.screen, screen)
                scan.gate.set()
                await self.settle(app, pilot)
                self.assertEqual(screen._trails, tt.TASK_TRAILS_LOOKING,
                                 "covered: not written by the callback")
                await pilot.press("escape")
                await self.settle(app, pilot)
                self.assertIs(app.screen, screen)
                self.assertIn(f"trail:{A}", self.link_ids(screen))
        finally:
            scan.gate.set()


# -- the session jump ------------------------------------------------------------------

class OpenInTrailsTests(unittest.TestCase):
    def run_jump(self, own, owned, live="other", launch=(True, None), switch=True):
        with mock.patch.object(actions.alu, "current_tmux_session", return_value=own), \
                mock.patch.object(actions.alu, "session_owned_by",
                                  side_effect=lambda s, _r: owned.get(s, False)), \
                mock.patch.object(actions.alu, "live_project_session", return_value=live), \
                mock.patch.object(actions.alu, "launch_or_focus_trails",
                                  return_value=launch) as lot, \
                mock.patch.object(actions.alu, "switch_client_to",
                                  return_value=switch) as sw:
            notes = actions.open_in_trails("/repo", A, "10", "Al{p}ha")
        return notes, lot, sw

    def test_own_session_needs_no_switch(self):
        notes, lot, sw = self.run_jump("mine", {"mine": True})
        lot.assert_called_once_with("mine", Path("/repo"), A, "10")
        sw.assert_not_called()
        self.assertEqual(notes, [("Showing t10 in trail Al{p}ha", "information")])

    def test_another_session_switches_the_client(self):
        notes, lot, sw = self.run_jump("mine", {"other": True})
        lot.assert_called_once_with("other", Path("/repo"), A, "10")
        sw.assert_called_once_with("other")
        self.assertEqual(notes, [])

    def test_a_failed_switch_names_the_session(self):
        notes, _lot, _sw = self.run_jump("mine", {"other": True}, switch=False)
        self.assertEqual(notes[0][1], "error")
        self.assertIn("ait trails opened in session 'other'", notes[0][0])
        self.assertIn("tmux switch-client -t =other", notes[0][0])

    def test_not_in_tmux_is_refused_before_any_launch(self):
        notes, lot, sw = self.run_jump(None, {})
        lot.assert_not_called()
        sw.assert_not_called()
        self.assertIn(f"./ait trails --trail {A} --task 10", notes[0][0])

    def test_a_destination_no_longer_owned_is_refused(self):
        notes, lot, _sw = self.run_jump("mine", {}, live="reused")
        lot.assert_not_called()
        self.assertIn("changed before the jump", notes[0][0])

    def test_no_project_session(self):
        notes, lot, _sw = self.run_jump("mine", {}, live=None)
        lot.assert_not_called()
        self.assertEqual(notes[0][1], "error")

    def test_the_launchers_warning_and_error(self):
        notes, _lot, _sw = self.run_jump("mine", {"mine": True},
                                         launch=(True, "the running ait trails cannot "
                                                       "focus a card"))
        self.assertEqual(notes, [("the running ait trails cannot focus a card", "warning")])
        notes, _lot, _sw = self.run_jump("mine", {"mine": True},
                                         launch=(False, "tmux list-panes failed"))
        self.assertEqual(notes, [("Could not show t10 in trail Al{p}ha: tmux list-panes "
                                  "failed", "error")])


if __name__ == "__main__":
    unittest.main()
