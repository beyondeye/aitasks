#!/usr/bin/env python3
"""The sitrep TUI's "source agent still frozen" line (t2350).

A question item's details show a ``Frozen`` line per frozen record linked to
it (``frozen_sitrep.FrozenSourceIndex`` -- stubbed here as the ``frozen_scan``
seam, optionally gated per call by Events). Display only: no key, no action.

Built on ``tests/test_sitrep_tui_actions.py``'s fixture and ``_Case`` (helpers
only), as the trails tests are.

Groups worth naming:

``FreshnessTests``
    A screen shows only a scan STARTED at or after its latest activation:
    never a map scanned before it opened, never one from before it was
    covered. Activation (ScreenResume, posted on the initial push too) is the
    one request path, so a first open makes exactly one scan.

``LateCallbackTests``
    A scan for a question item that lands after the user moved to a task item
    neither raises nor shows anything there, and a rerun queued meanwhile still
    runs (the scan loop never wedges).

Run: ~/.aitask/venv/bin/python -m pytest tests/test_sitrep_tui_frozen_source.py -q
"""

from __future__ import annotations

import threading
import unittest
from unittest import mock

import test_sitrep_tui_actions as ta  # noqa: E402  (helpers only, never a test class)

import frozen_sitrep as fs  # noqa: E402
from textual.screen import Screen  # noqa: E402
from sitrep_tui import sitrep_tui_actions as actions  # noqa: E402
from sitrep_tui import sitrep_tui_app as appmod  # noqa: E402
from sitrep_tui import sitrep_tui_model as model  # noqa: E402

setUpModule = ta.setUpModule          # noqa: N816 - the shared fixture template
tearDownModule = ta.tearDownModule    # noqa: N816

SIZE = ta.SIZE


def source(window: str = "agent-pick-7", link: str = "triage",
           state: str = fs.TRIAGE_OPEN) -> fs.FrozenSource:
    return fs.FrozenSource("0123abcd", window, "2337", "2026-11-22 10:00", link,
                           fs.FrozenSitrepState(state))


class Scan:
    """The `frozen_scan` seam. ``results`` is consumed per call (the last one
    repeats); ``gates`` likewise (None: no gate). Counts calls."""

    def __init__(self, *results, raises: bool = False):
        self.results = list(results) or [{}]
        self.gates: list = []
        self.calls = 0
        self.raises = raises

    def __call__(self, store_dir):
        i = self.calls
        self.calls += 1
        gate = self.gates[i] if i < len(self.gates) else None
        if gate is not None:
            gate.wait(30)
        if self.raises:
            raise RuntimeError("scan boom")
        return self.results[min(i, len(self.results) - 1)]


class _FrozenCase(ta._Case):
    def setUp(self):
        super().setUp()
        # The production rescan timer (5 s) must never fire inside a test: a
        # slow run would add a call to an "exactly one scan" assertion. Ticks
        # are driven explicitly (`app._frozen_tick()`) where a test needs one.
        patcher = mock.patch.object(actions, "FROZEN_RESCAN_INTERVAL", 3600.0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_frozen_app(self, scan: "Scan | None"):
        return self.make_app(frozen_scan=scan)

    def body(self, screen) -> str:
        return screen.body_text(model.resolve_now())

    def body_rendered(self, screen) -> str:
        """What the body widget SHOWS now -- not a fresh rebuild (``body``),
        which would re-read the review case itself."""
        return str(screen.query_one("#sd-body", appmod.Static).content)

    async def settled(self, app, pilot) -> None:
        await self.until(pilot, lambda: not app._frozen_busy, "the frozen scan")
        await pilot.pause()


class DetailsLineTests(_FrozenCase):

    async def test_a_linked_triage_item_shows_the_line(self):
        q = self.ids["question"]
        scan = Scan({q: (source(),)})
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, q)
            await self.settled(app, pilot)
            body = self.body(screen)
            # The label is padded to the label column, then the value: never
            # run together ("Frozenagent-…").
            self.assertIn("Frozen      agent-pick-7 (t2337, frozen 2026-11-22 10:00)",
                          body)
            self.assertIn("ait frozenagent", body)
            self.assertNotIn("--record", body)

    async def test_two_sources_are_two_lines(self):
        q = self.ids["question"]
        scan = Scan({q: (source("agent-a"), source("agent-b"))})
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, q)
            await self.settled(app, pilot)
            self.assertEqual(2, self.body(screen).count("\nFrozen      agent-"))

    async def test_a_review_case_says_raw_output_kept(self):
        r = self.ids["review"]
        scan = Scan({r: (source(link="review", state=fs.REVIEW_PENDING),)})
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, r)
            await self.settled(app, pilot)
            self.assertIn("(raw output kept)", self.body(screen))

    async def test_a_hint_update_does_not_reread_the_review_case(self):
        r = self.ids["review"]
        scan = Scan({}, {r: (source(link="review", state=fs.REVIEW_PENDING),)})
        real = model.sitrep_cli.review_case
        calls = []

        def counting(*a, **k):
            calls.append(threading.current_thread().name)
            return real(*a, **k)
        app = self.make_frozen_app(scan)
        with mock.patch.object(model.sitrep_cli, "review_case", counting):
            async with app.run_test(size=SIZE) as pilot:
                screen = await self.open_details(app, pilot, r)
                await self.settled(app, pilot)
                self.assertGreaterEqual(len(calls), 1)      # the open read it
                self.assertIn("Review case ", self.body_rendered(screen))
                before = len(calls)
                app._frozen_tick()                          # a hint change lands
                await self.settled(app, pilot)
                self.assertIn("(raw output kept)", self.body_rendered(screen))
                self.assertIn("Review case ", self.body_rendered(screen))
                self.assertEqual(before, len(calls))        # the redraw reused it

    async def test_the_review_line_recovers_on_the_age_tick_without_reopening(self):
        # A case record unreadable at open must show once readable again, on
        # the ordinary redraw -- with or without a frozen scanner.
        r = self.ids["review"]
        for scan in (None, Scan({})):
            with self.subTest(scanner=scan is not None):
                real = model.sitrep_cli.review_case
                state = {"down": True}

                def flaky(*a, **k):
                    if state["down"]:
                        raise OSError("analysis file unavailable")
                    return real(*a, **k)
                app = self.make_frozen_app(scan)
                with mock.patch.object(model.sitrep_cli, "review_case", flaky):
                    async with app.run_test(size=SIZE) as pilot:
                        screen = await self.open_details(app, pilot, r)
                        if scan is not None:
                            await self.settled(app, pilot)
                        self.assertNotIn("Review case ", self.body_rendered(screen))
                        state["down"] = False
                        screen.refresh_ages(model.resolve_now())
                        await pilot.pause()
                        self.assertIn("Review case ", self.body_rendered(screen))

    async def test_an_unlinked_question_shows_no_line(self):
        scan = Scan({self.ids["review"]: (source(),)})
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, self.ids["question"])
            await self.settled(app, pilot)
            self.assertEqual(1, scan.calls)
            self.assertNotIn("Frozen ", self.body(screen))

    async def test_a_non_question_item_never_scans(self):
        t = self.ids["task"]
        scan = Scan({t: (source(),)})
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, t)
            await pilot.pause()
            app._frozen_tick()
            await pilot.pause()
            self.assertEqual(0, scan.calls)
            self.assertFalse(screen.wants_frozen_sources)
            self.assertNotIn("Frozen ", self.body(screen))

    async def test_no_scanner_no_line_no_worker(self):
        app = self.make_frozen_app(None)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, self.ids["question"])
            await pilot.pause()
            self.assertFalse(screen.wants_frozen_sources)
            self.assertEqual(0, app._frozen_seq)
            self.assertIsNone(app.request_frozen_sources())
            self.assertNotIn("Frozen ", self.body(screen))

    async def test_a_raising_scan_shows_nothing(self):
        scan = Scan(raises=True)
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, self.ids["question"])
            await self.settled(app, pilot)
            self.assertEqual(1, scan.calls)
            self.assertNotIn("Frozen ", self.body(screen))
            self.assertEqual({}, app._frozen_map)

    async def test_the_tick_does_not_scan_on_the_main_list(self):
        scan = Scan()
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app._frozen_tick()
            await pilot.pause()
            self.assertEqual(0, scan.calls)

    async def test_the_tick_rescans_while_the_details_are_shown(self):
        q = self.ids["question"]
        scan = Scan({q: (source(),)}, {})
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, q)
            await self.settled(app, pilot)
            self.assertIn("Frozen ", self.body(screen))
            app._frozen_tick()              # the record was dropped meanwhile
            await self.settled(app, pilot)
            self.assertEqual(2, scan.calls)
            self.assertNotIn("Frozen ", self.body(screen))

    async def test_no_binding_is_added(self):
        q = self.ids["question"]
        keys = []
        for scan in (None, Scan({q: (source(),)})):
            app = self.make_frozen_app(scan)
            async with app.run_test(size=SIZE) as pilot:
                await self.open_details(app, pilot, q)
                await pilot.pause()
                keys.append(sorted(app.screen.active_bindings))
        self.assertEqual(keys[0], keys[1])


class FreshnessTests(_FrozenCase):

    async def test_the_rescan_timer_is_off_in_these_tests(self):
        self.assertEqual(3600.0, actions.FROZEN_RESCAN_INTERVAL)

    async def test_a_first_open_makes_exactly_one_scan(self):
        q = self.ids["question"]
        scan = Scan({q: (source(),)})
        app = self.make_frozen_app(scan)     # rescan timer patched off (setUp)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, q)
            await self.settled(app, pilot)
            await pilot.pause(0.2)
            self.assertEqual(1, scan.calls)
            self.assertEqual(1, screen.frozen_min_seq)
            self.assertIn("Frozen ", self.body(screen))

    async def test_a_scan_started_before_the_open_is_not_shown(self):
        q = self.ids["question"]
        scan = Scan({q: (source("agent-old"),)}, {q: (source("agent-new"),)})
        early, late = threading.Event(), threading.Event()
        scan.gates = [early, late]
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app._kick_frozen_scan()          # seq 1, started on the main list
            screen = await self.open_details(app, pilot, q)
            self.assertEqual(2, screen.frozen_min_seq)
            early.set()                      # seq 1 lands while seq 2 waits
            await self.until(pilot, lambda: app._frozen_map_seq == 1, "scan 1")
            await pilot.pause()
            self.assertNotIn("agent-old", self.body(screen))
            late.set()
            await self.until(pilot, lambda: app._frozen_map_seq == 2, "scan 2")
            await self.settled(app, pilot)
            body = self.body(screen)
            self.assertIn("agent-new", body)
            self.assertNotIn("agent-old", body)

    async def _covered(self, app, pilot, q):
        screen = await self.open_details(app, pilot, q)
        await self.settled(app, pilot)
        self.assertIn("Frozen ", self.body(screen))
        cover = Screen()
        await app.push_screen(cover)
        await pilot.pause()
        return screen, cover

    async def test_a_drop_while_covered_never_reappears_on_resume(self):
        q = self.ids["question"]
        scan = Scan({q: (source(),)})
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen, _cover = await self._covered(app, pilot, q)
            scan.results = [{}]              # dropped while covered (no tick ran)
            gate = threading.Event()
            scan.gates = [None, gate]
            app.pop_screen()
            await pilot.pause()
            # Withheld at once on resume -- before the fresh scan lands.
            self.assertIs(app.screen, screen)
            self.assertNotIn("Frozen ", self.body(screen))
            self.assertEqual(2, screen.frozen_min_seq)
            gate.set()
            await self.settled(app, pilot)
            self.assertEqual(2, scan.calls)
            self.assertNotIn("Frozen ", self.body(screen))

    async def test_still_frozen_after_resume_comes_back_from_the_fresh_scan(self):
        q = self.ids["question"]
        scan = Scan({q: (source(),)})
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen, _cover = await self._covered(app, pilot, q)
            gate = threading.Event()
            scan.gates = [None, gate]
            app.pop_screen()
            await pilot.pause()
            self.assertNotIn("Frozen ", self.body(screen))
            gate.set()
            await self.settled(app, pilot)
            self.assertIn("Frozen ", self.body(screen))

    async def test_a_scan_landing_while_covered_leaves_the_covered_screen(self):
        q = self.ids["question"]
        scan = Scan({q: (source(),)})
        gate = threading.Event()
        scan.gates = [gate]
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            screen = await self.open_details(app, pilot, q)
            await app.push_screen(Screen())
            await pilot.pause()
            gate.set()
            await self.until(pilot, lambda: app._frozen_map_seq == 1, "scan 1")
            await pilot.pause()
            self.assertNotIn("Frozen ", self.body(screen))


class LateCallbackTests(_FrozenCase):

    async def test_a_question_scan_landing_on_a_task_item_is_harmless(self):
        q, t = self.ids["question"], self.ids["task"]
        scan = Scan({q: (source(),), t: (source("agent-wrong"),)})
        gate = threading.Event()
        scan.gates = [gate]
        app = self.make_frozen_app(scan)
        async with app.run_test(size=SIZE) as pilot:
            await self.open_details(app, pilot, q)
            await pilot.press("escape")
            await pilot.pause()
            task_screen = await self.open_details(app, pilot, t)
            self.assertIsNone(task_screen.frozen_min_seq)
            app._kick_frozen_scan()          # queues a dirty rerun
            self.assertTrue(app._frozen_dirty)
            gate.set()
            await self.until(pilot, lambda: scan.calls == 2 and not app._frozen_busy,
                             "the rerun")
            await pilot.pause()
            self.assertIs(app.screen, task_screen)
            self.assertNotIn("Frozen ", self.body(task_screen))
            self.assertFalse(app._frozen_dirty)


if __name__ == "__main__":
    unittest.main()
