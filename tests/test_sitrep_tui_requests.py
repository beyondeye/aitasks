#!/usr/bin/env python3
"""The sitrep TUI's agent-request keys (t2211_4) — App-level behaviour.

The delivery protocol itself is pinned in ``tests/test_sitrep_request_delivery.py``
(pure) and ``tests/test_sitrep_request_delivery_live.sh`` (real tmux). Here the
app's ``deliver`` seam is a recording fake, and what is pinned is the TUI side:

* ``AGENT_REQUESTS`` is ONE table — the bindings, the How-text keys and the
  re-export the skill's parity test imports all come from it;
* a request key is shown only where its item fits AND the agent runs, is
  disabled while a request is in flight, and every action re-checks (a moved
  rev from details sends nothing; a second press is refused, never queued);
* the ask dialog refuses what cannot be typed safely and its callback
  re-resolves the item; it stays usable in a short pane (real clicks);
* every outcome is toasted, and anything but ``submitted`` opens the result
  panel.

Run: python3 tests/test_sitrep_tui_requests.py
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / ".aitask-scripts"
for _p in (str(HERE), str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_sitrep_tui_actions as ta  # noqa: E402  (helpers only, never a test class)

from monitor import agent_request_delivery as delivery  # noqa: E402
from sitrep_tui import sitrep_tui_actions as actions  # noqa: E402
from sitrep_tui import sitrep_tui_app as appmod  # noqa: E402
from sitrep_tui import sitrep_tui_model as model  # noqa: E402
from sitrep_tui import sitrep_tui_requests as reqs  # noqa: E402

SIZE = (120, 30)
RUNNING = (True, "%1", "%2")


def setUpModule():  # noqa: N802
    ta.setUpModule()


def tearDownModule():  # noqa: N802
    ta.tearDownModule()


class FakeDeliver:
    """The app's ``deliver`` seam: records each line; answers ``result`` (a
    code), optionally holding until ``release`` is set."""

    def __init__(self, code: str = delivery.SUBMITTED, detail: str = "", hold: bool = False):
        self.lines: list = []
        self.code = code
        self.detail = detail
        self.release = asyncio.Event()
        if not hold:
            self.release.set()

    async def __call__(self, line: str):
        self.lines.append(line)
        await self.release.wait()
        return delivery.DeliveryResult(self.code, self.detail, line)


class _ReqCase(ta._Case):
    def make_app(self, runner=None, deliver=None, probe=RUNNING, **kw):
        self.deliver = deliver if deliver is not None else FakeDeliver()
        return super().make_app(runner, roles_probe=lambda: probe, deliver=self.deliver, **kw)

    async def started(self, app, pilot):
        await self.until(pilot, lambda: app.agent_state == "running", "agent running")

    def trail_watch(self, app) -> int:
        """Make the fixture's watch a trail-checked one (what refresh reports)."""
        num = self.ids["watch"]
        app._checks[num] = "trail"
        app.refresh_bindings()
        return num


# -- the one table --------------------------------------------------------------------

class TableTests(unittest.TestCase):
    def test_one_table_feeds_the_bindings_and_the_reexport(self):
        self.assertIs(appmod.AGENT_REQUESTS, reqs.AGENT_REQUESTS)
        rows = set(actions.ACTION_BINDINGS)
        for r in reqs.AGENT_REQUESTS:
            self.assertIn((r.action, r.key, r.label), rows)
            self.assertTrue(r.template.startswith(">"), r)
        self.assertEqual(actions.REQUEST_ACTIONS, {r.action for r in reqs.AGENT_REQUESTS})
        self.assertTrue(reqs.ITEM_REQUESTS <= actions.ITEM_ACTIONS)

    def test_no_key_collides(self):
        # The app's BINDINGS already carry every ACTION_BINDINGS row.
        keys = [b.key for b in appmod.SitrepTuiApp.BINDINGS]
        self.assertTrue({k for _a, k, _l in actions.ACTION_BINDINGS} <= set(keys))
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        self.assertEqual(dupes, [], "two bindings on one key")

    def test_how_text_defaults_follow_the_bindings(self):
        defaults = {a: k for a, k, _l in actions.ACTION_BINDINGS}
        for placeholder, action in actions._KEY_PLACEHOLDERS.items():
            with self.subTest(placeholder):
                self.assertEqual(model.DEFAULT_KEYS[placeholder], defaults[action])


class BuildRequestTests(unittest.TestCase):
    def item(self, num=12):
        from sitrep_todo import Item
        return Item(num, 1, "question", "open", "now", "", "", "", "", "t")

    def test_the_lines(self):
        it = self.item()
        by = reqs.REQUESTS_BY_ACTION
        self.assertEqual(reqs.build_request(by["request_triage"], it), ">t c12")
        self.assertEqual(reqs.build_request(by["request_trail_refresh"], it), ">tr c12")
        self.assertEqual(reqs.build_request(by["request_pick_advice"]), ">p")
        self.assertEqual(reqs.build_request(by["request_ask"], it, text="  why   {x}?  "),
                         ">q c12 why {x}?")

    def test_unbuildable_requests_are_empty(self):
        by = reqs.REQUESTS_BY_ACTION
        self.assertEqual(reqs.build_request(by["request_triage"], None), "")
        self.assertEqual(reqs.build_request(by["request_situation"], self.item()), "",
                         "no theme")
        for bad in ("", "a\nb", "a\tb", "see @tests/x", "x" * 301):
            with self.subTest(repr(bad)):
                self.assertEqual(reqs.build_request(by["request_ask"], self.item(), text=bad),
                                 "")

    def test_a_question_may_start_with_any_character(self):
        by = reqs.REQUESTS_BY_ACTION
        for text in ("/tmp/report.md is this related?", "#2211 is this the same issue?",
                     "$PATH looks wrong here"):
            with self.subTest(text):
                self.assertEqual(reqs.ask_text_error(text), "")
                self.assertEqual(reqs.build_request(by["request_ask"], self.item(), text=text),
                                 f">q c12 {text}")

    def test_ask_reasons(self):
        self.assertIn("@mention", reqs.ask_text_error("look at @a/b"))
        self.assertIn("one plain line", reqs.ask_text_error("a\nb"))
        self.assertEqual(reqs.ask_text_error("is @a/b related"), "")
        self.assertEqual(reqs.normalize_ask_text("  a   b  "), "a b")


# -- bindings ------------------------------------------------------------------------------

class BindingTests(_ReqCase):
    ITEM_ACTIONS = ("request_triage", "request_ask", "request_situation",
                    "request_trail_refresh")
    # name: (triage, ask, situation, trail refresh)
    EXPECT = {
        "triage": (True, True, False, False),
        "review": (True, True, False, False),
        "task": (False, True, True, False),        # the fixture's task has theme=sitrep
        "question": (False, True, False, False),
        "watch": (False, True, False, True),       # made trail-checked below
        "done": (False, True, False, False),
    }

    async def test_the_matrix_on_the_main_list_and_on_details(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            self.trail_watch(app)
            await pilot.press("d")
            await pilot.pause()
            for name, want in self.EXPECT.items():
                num = self.ids[name]
                with self.subTest(item=name, where="main"):
                    self.select(app, num)
                    self.assertEqual(tuple(self.shown(app, a) for a in self.ITEM_ACTIONS), want)
                    self.assertTrue(self.shown(app, "request_pick_advice"))
                with self.subTest(item=name, where="details"):
                    await self.open_details(app, pilot, num)
                    self.assertEqual(tuple(self.shown(app, a) for a in self.ITEM_ACTIONS), want)
                    self.assertTrue(self.shown(app, "request_pick_advice"))
                    await pilot.press("escape")
                    await pilot.pause()
            with self.subTest(where="viewer screens"):
                await pilot.press("l")
                await pilot.pause()
                for a in actions.REQUEST_ACTIONS:
                    self.assertFalse(self.shown(app, a), a)

    async def test_hidden_unless_the_agent_runs(self):
        for probe in ((True, None, "%2"), (False, None, None)):
            with self.subTest(probe=probe):
                app = self.make_app(probe=probe)
                async with app.run_test(size=SIZE) as pilot:
                    want = "absent" if probe[0] else "unknown"
                    await self.until(pilot, lambda: app.agent_state == want, want)
                    self.select(app, self.ids["triage"])
                    for a in actions.REQUEST_ACTIONS:
                        self.assertFalse(self.shown(app, a), a)
        app = self.make_app()
        app._deliver = None                        # not in tmux
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            self.select(app, self.ids["triage"])
            self.assertFalse(self.shown(app, "request_triage"))

    async def test_the_footer_names_the_keys(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            self.select(app, self.ids["triage"])
            app.refresh_bindings()
            await pilot.pause()
            active = app.screen.active_bindings
            for key in ("t", "a", "n"):
                self.assertIn(key, active)


# -- sending ------------------------------------------------------------------------------

class SendTests(_ReqCase):
    async def test_triage_from_details_sends_and_toasts(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            num = self.ids["triage"]
            await self.open_details(app, pilot, num)
            await pilot.press("t")
            await self.until(pilot, lambda: self.toast_with("Sent to the sitrep agent"),
                             "toast")
            self.assertEqual(self.deliver.lines, [f">t c{num}"])
            self.assertIsInstance(app.screen, appmod.ItemDetailScreen, "no result panel")

    async def test_pick_advice_and_situation(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            self.select(app, self.ids["task"])
            await pilot.press("w")
            await self.until(pilot, lambda: len(self.deliver.lines) == 1, "situation sent")
            await self.until(pilot, lambda: not app._request_inflight, "settled")
            await pilot.press("n")
            await self.until(pilot, lambda: len(self.deliver.lines) == 2, "pick advice sent")
        self.assertEqual(self.deliver.lines, [">w sitrep", ">p"])

    async def test_trail_refresh(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            num = self.trail_watch(app)
            self.select(app, num)
            await pilot.press("T")
            await self.until(pilot, lambda: self.deliver.lines, "sent")
        self.assertEqual(self.deliver.lines, [f">tr c{num}"])

    async def test_every_other_outcome_opens_the_result_panel(self):
        for code, detail in ((delivery.TYPED_IN_MODE, ""), (delivery.UNKNOWN, "enter"),
                             ("refused:not_ready:dialog", ""), (delivery.SKIPPED, "in_mode")):
            with self.subTest(code=code):
                self.toasts.clear()
                app = self.make_app(deliver=FakeDeliver(code, detail))
                async with app.run_test(size=SIZE) as pilot:
                    await self.started(app, pilot)
                    self.select(app, self.ids["triage"])
                    await pilot.press("t")
                    await self.until(pilot, lambda: isinstance(app.screen, actions.ResultDialog),
                                     "result panel")
                    body = app.screen.body_text()
                    self.assertIn(f"result: {code}", body)
                    self.assertIn(delivery.DeliveryResult(code).message(), body)
                    self.assertFalse(self.toast_with("Sent to the sitrep agent"))

    async def test_a_moved_rev_from_details_sends_nothing(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            num = self.ids["triage"]
            await self.open_details(app, pilot, num)
            self.writer("set-state", f"c{num}", "open", "--outcome", "touched")
            await app._poll_store()
            await pilot.press("t")
            await self.until(pilot, lambda: self.toast_with("changed since these details"),
                             "freshness toast")
        self.assertEqual(self.deliver.lines, [])

    async def test_one_request_at_a_time(self):
        held = FakeDeliver(hold=True)
        app = self.make_app(deliver=held)
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            self.select(app, self.ids["triage"])
            await pilot.press("t")
            await self.until(pilot, lambda: held.lines, "first sent")
            self.assertIsNone(app.check_action("request_triage", ()), "disabled, not hidden")
            app.action_request_triage()                 # the action re-checks
            await pilot.pause()
            self.assertTrue(self.toast_with("already being delivered"))
            held.release.set()
            await self.until(pilot, lambda: not app._request_inflight, "settled")
            self.assertTrue(app.check_action("request_triage", ()))
        self.assertEqual(len(held.lines), 1)

    async def test_the_how_text_names_a_remapped_key(self):
        import keybinding_registry

        real = keybinding_registry.resolve_key

        def remap(scope, action, default=None):
            return "g" if action == "request_triage" else real(scope, action, default)

        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            with mock.patch.object(keybinding_registry, "resolve_key", side_effect=remap):
                screen = await self.open_details(app, pilot, self.ids["triage"])
            body = screen.body_text(model.resolve_now())
        self.assertIn("Press  g  to have the sitrep agent", body)
        self.assertIn(f">t c{self.ids['triage']}", body)


# -- the ask dialog -----------------------------------------------------------------------

class AskTests(_ReqCase):
    async def open_ask(self, app, pilot, num):
        self.select(app, num)
        await pilot.press("a")
        await self.until(pilot, lambda: isinstance(app.screen, actions.AskAgentDialog),
                         "ask dialog")
        return app.screen

    async def test_a_question_is_sent_as_q(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            num = self.ids["question"]
            dlg = await self.open_ask(app, pilot, num)
            dlg.query_one("#aq-text").value = "why   is it waiting?"
            await pilot.click("#aq-ask")
            await self.until(pilot, lambda: self.deliver.lines, "sent")
        self.assertEqual(self.deliver.lines, [f">q c{num} why is it waiting?"])

    async def test_unsafe_text_is_refused_in_the_dialog(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            dlg = await self.open_ask(app, pilot, self.ids["question"])
            for bad, why in (("look at @tests/x", "@mention"), ("", "Type a question"),
                             ("tab\there", "one plain line")):
                with self.subTest(repr(bad)):
                    # Enter in the input (on_input_submitted): back-to-back clicks
                    # on one button read as a double press.
                    box = dlg.query_one("#aq-text")
                    box.value = bad
                    box.focus()
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertIs(app.screen, dlg, "the dialog stays open")
                    notice = dlg.query_one("#aq-notice")
                    self.assertIn(why, str(notice.content))
                    self.assertNotIn("hidden", notice.classes)
            await pilot.press("escape")
            await pilot.pause()
        self.assertEqual(self.deliver.lines, [])

    async def test_the_callback_re_resolves_the_item(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await self.started(app, pilot)
            num = self.ids["question"]
            dlg = await self.open_ask(app, pilot, num)
            # The item is dismissed while the dialog is open.
            self.writer("dismiss", f"c{num}", "--outcome", "user: gone")
            await app._poll_store()
            app.store.items.pop(num, None)
            dlg.query_one("#aq-text").value = "still there?"
            await pilot.click("#aq-ask")
            await self.until(pilot, lambda: self.toast_with("changed while the dialog was open"),
                             "refusal")
        self.assertEqual(self.deliver.lines, [])

    async def test_the_dialog_fits_a_short_pane(self):
        for rows in (10, 12, 16):
            with self.subTest(rows=rows):
                self.deliver = None
                app = self.make_app()
                async with app.run_test(size=(60, rows)) as pilot:
                    await self.started(app, pilot)
                    dlg = await self.open_ask(app, pilot, self.ids["question"])
                    await pilot.pause()
                    for sel in ("#aq-text", "#aq-ask", "#aq-cancel"):
                        region = dlg.query_one(sel).region
                        self.assertGreater(region.height, 0, sel)
                        self.assertLessEqual(region.bottom, rows, sel)
                    dlg.query_one("#aq-text").value = "fits?"
                    await pilot.click("#aq-ask")
                    await self.until(pilot, lambda: self.deliver.lines, "sent")


if __name__ == "__main__":
    unittest.main(verbosity=1)
