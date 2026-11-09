#!/usr/bin/env python3
"""Behavioural pins for the sitrep TUI's actions (t2211_3).

The fixture store is the one ``tests/test_sitrep_tui_app.py`` builds through
the REAL writer (its ``build_fixture`` / ``writer`` helpers, imported by name --
never a test class), built once here into this module's own template and copied
per test. Writes in these tests go through the real writer too: the app's
runner is a recording wrapper that runs the store scripts for real and answers
the harvest / refresh / open scripts from canned output.

Groups worth naming:

``DismissTests``
    ``--expect-rev`` is the rev the user SAW. A change in between comes back
    ``STALE:`` and the dialog is asked again with the new rev -- the item is
    dismissed once, never blindly.

``RestoreRaceTests``
    The confirm dialog is gated on a cached parse error, but the writer decides
    under its lock (``restore --if-damaged``). A repair plus a newer write while
    the dialog is open must survive; the pre-fix control (the unconditional
    verb) rolls the newer write back, proving the test sees the hazard.

``DetailFreshnessTests``
    Details are snapshots. An item whose rev moved since they opened launches
    nothing: the details are refreshed and the key must be pressed again.

``OpenInBoardTests``
    The board may live in another session of the project; the client is
    switched there, and a failed switch is reported with the session's name.

Run: python3 -m pytest tests/test_sitrep_tui_actions.py -q
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / ".aitask-scripts"
for _p in (str(Path(__file__).resolve().parent), str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_sitrep_tui_app as base  # noqa: E402  (helpers only, never a test class)

import agent_launch_utils as alu  # noqa: E402
import sitrep_todo as st  # noqa: E402
from monitor.sitrep_close import run_owned_group  # noqa: E402
from sitrep_tui import sitrep_tui_actions as actions  # noqa: E402
from sitrep_tui import sitrep_tui_app as appmod  # noqa: E402
from sitrep_tui import sitrep_tui_model as model  # noqa: E402

SIZE = (120, 30)
NOW = base.NOW

_TEMPLATE: "tempfile.TemporaryDirectory | None" = None
_FACTS: dict = {}


def setUpModule():  # noqa: N802
    global _TEMPLATE, _FACTS
    _TEMPLATE = tempfile.TemporaryDirectory(prefix="sitrep_actions_fx_")
    _FACTS = base.build_fixture(Path(_TEMPLATE.name))


def tearDownModule():  # noqa: N802
    if _TEMPLATE is not None:
        _TEMPLATE.cleanup()


class Runner:
    """The app's runner seam: records every argv; canned answers by script
    basename (a list is consumed in order, a callable is called with the
    argv), everything else runs FOR REAL with the app's own cwd/env rule."""

    def __init__(self, root: str, canned: "dict | None" = None):
        self.root = root
        self.canned = dict(canned or {})
        self.calls: list = []

    async def __call__(self, argv, timeout):
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        name = Path(argv[0]).name
        answer = self.canned.get(name)
        if isinstance(answer, list) and answer:
            answer = answer.pop(0)
        if callable(answer):
            answer = await answer(argv)
        if isinstance(answer, tuple):
            return answer
        return await run_owned_group(argv, timeout=timeout, cwd=self.root,
                                     env=actions.writer_env())

    def names(self) -> list:
        return [Path(c[0]).name for c in self.calls]


class _Case(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="sitrep_actions_")
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name)
        shutil.copytree(_TEMPLATE.name, work, symlinks=True, dirs_exist_ok=True)
        link = work / "repo" / "escape.md"
        link.unlink()
        os.symlink(work / "outside" / "secret.txt", link)
        self.root = str(work / "repo")
        self.store_dir = os.path.join(self.root, ".aitask-sitrep")
        self.ids = _FACTS["ids"]
        patcher = mock.patch.dict(os.environ, {"AITASK_SITREP_NOW": NOW,
                                               "AIT_SKIP_TERMINAL_CHECK": "1"})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("AITASK_SITREP_DIR", None)
        self.toasts: list = []

    def make_app(self, runner=None, **kw) -> appmod.SitrepTuiApp:
        self.runner = runner or Runner(self.root)
        app = appmod.SitrepTuiApp(self.root, self.store_dir, reload_interval=3600.0,
                                  runner=self.runner, **kw)
        real_notify = app.notify

        def notify(message, *a, **k):
            self.toasts.append(str(message))
            return real_notify(message, *a, **k)

        app.notify = notify
        return app

    def writer(self, *args, stdin: str = "") -> str:
        return base.writer(self.root, *args, stdin=stdin)

    def item(self, name: str) -> "st.Item":
        store = st.load_todo_for_read(self.store_dir)
        return store.items[self.ids[name]]

    def todo_text(self) -> str:
        with open(os.path.join(self.store_dir, "todo.md"), encoding="utf-8") as fh:
            return fh.read()

    def select(self, app, num: int) -> None:
        ol = app.screen_stack[0].query_one("#st-list")
        ol.highlighted = ol.get_option_index(f"c{num}")

    async def until(self, pilot, cond, what: str = "condition", timeout: float = 30.0):
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while not cond():
            if loop.time() > end:
                self.fail(f"timed out waiting for {what}")
            await pilot.pause(0.05)

    async def open_details(self, app, pilot, num: int):
        self.select(app, num)
        await pilot.press("enter")
        await pilot.pause()
        self.assertIsInstance(app.screen, appmod.ItemDetailScreen)
        return app.screen

    def shown(self, app, action: str) -> bool:
        return bool(app.check_action(action, ()))

    def toast_with(self, text: str) -> bool:
        return any(text in t for t in self.toasts)


# -- dismiss ---------------------------------------------------------------------

class DismissTests(_Case):
    async def submit_reason(self, app, pilot, reason: str) -> None:
        await self.until(pilot, lambda: isinstance(app.screen, actions.DismissDialog),
                         "the dismiss dialog")
        app.screen.query_one("#dd-reason").value = reason
        await pilot.press("enter")

    async def test_dismiss_writes_the_reason_once(self):
        num = self.ids["push"]
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, num)
            await pilot.press("x")
            await self.submit_reason(app, pilot, "done by hand")
            await self.until(pilot, lambda: self.toast_with(f"c{num} dismissed"), "toast")
            it = self.item("push")
            self.assertEqual((it.state, it.outcome), ("dismissed", "user: done by hand"))
            self.assertEqual(app.store.items[num].state, "dismissed", "reloaded")
            dismisses = [c for c in self.runner.calls if c[1:2] == ["dismiss"]]
            self.assertEqual(len(dismisses), 1)
            self.assertIn("--expect-rev", dismisses[0])

    async def test_cancel_writes_nothing(self):
        before = self.todo_text()
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, self.ids["push"])
            await pilot.press("x")
            await self.until(pilot, lambda: isinstance(app.screen, actions.DismissDialog),
                             "the dismiss dialog")
            await pilot.press("escape")
            await self.until(pilot, lambda: not isinstance(app.screen, actions.DismissDialog),
                             "dialog closed")
            await app.workers.wait_for_complete()
        self.assertEqual(self.todo_text(), before)
        self.assertEqual(self.runner.calls, [])

    async def test_an_empty_reason_is_refused_in_the_dialog(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, self.ids["push"])
            await pilot.press("x")
            await self.submit_reason(app, pilot, "   ")
            await pilot.pause()
            self.assertIsInstance(app.screen, actions.DismissDialog)
            self.assertIn("required", str(app.screen.query_one("#dd-notice").content))
            await pilot.press("escape")
            await app.workers.wait_for_complete()
        self.assertEqual(self.runner.calls, [])

    async def test_stale_asks_again_with_the_new_rev_never_blind(self):
        num = self.ids["push"]
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            seen_rev = app.store.items[num].rev
            self.select(app, num)
            await pilot.press("x")
            await self.until(pilot, lambda: isinstance(app.screen, actions.DismissDialog),
                             "the dismiss dialog")
            # Someone changes the item while the dialog is open.
            self.writer("update", f"c{num}", "--title", "Push main (renamed)")
            new_rev = self.item("push").rev
            await self.submit_reason(app, pilot, "obsolete")
            await self.until(
                pilot, lambda: (isinstance(app.screen, actions.DismissDialog)
                                and "changed since you looked"
                                in str(app.screen.query_one("#dd-notice").content)),
                "the re-asked dialog")
            notice = str(app.screen.query_one("#dd-notice").content)
            self.assertIn(f"rev {seen_rev}→{new_rev}", notice)
            self.assertEqual(app.screen.query_one("#dd-reason").value, "obsolete",
                             "the typed reason is kept")
            self.assertEqual(self.item("push").state, "open", "the STALE write wrote nothing")
            await pilot.press("enter")
            await self.until(pilot, lambda: self.toast_with(f"c{num} dismissed"), "toast")
        dismisses = [c for c in self.runner.calls if c[1:2] == ["dismiss"]]
        self.assertEqual([c[c.index("--expect-rev") + 1] for c in dismisses],
                         [str(seen_rev), str(new_rev)])
        it = self.item("push")
        self.assertEqual((it.state, it.title), ("dismissed", "Push main (renamed)"))

    async def test_stale_on_an_item_closed_meanwhile_stops(self):
        num = self.ids["push"]
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, num)
            await pilot.press("x")
            await self.until(pilot, lambda: isinstance(app.screen, actions.DismissDialog),
                             "the dismiss dialog")
            self.writer("set-state", f"c{num}", "done", "--outcome", "elsewhere")
            await self.submit_reason(app, pilot, "obsolete")
            await self.until(pilot, lambda: self.toast_with("is now done"), "toast")
            self.assertNotIsInstance(app.screen, actions.DismissDialog)
        self.assertEqual(self.item("push").state, "done")

    async def test_lock_busy_offers_a_retry(self):
        num = self.ids["push"]
        runner = Runner(self.root, {"aitask_sitrep_todo.sh": [(3, "LOCK_BUSY")]})
        app = self.make_app(runner)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, num)
            await pilot.press("x")
            await self.submit_reason(app, pilot, "busy test")
            await self.until(
                pilot, lambda: (isinstance(app.screen, actions.DismissDialog)
                                and "busy" in str(app.screen.query_one("#dd-notice").content)),
                "the retry dialog")
            self.assertEqual(self.item("push").state, "open")
            await pilot.press("enter")
            await self.until(pilot, lambda: self.toast_with(f"c{num} dismissed"), "toast")
        self.assertEqual(self.item("push").state, "dismissed")

    async def test_store_unusable_shows_an_error_with_the_restore_key(self):
        runner = Runner(self.root, {"aitask_sitrep_todo.sh": [(4, "Error: damaged")]})
        app = self.make_app(runner)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, self.ids["push"])
            await pilot.press("x")
            await self.submit_reason(app, pilot, "x")
            await self.until(pilot, lambda: isinstance(app.screen, actions.ResultDialog),
                             "the error panel")
            body = app.screen.body_text()
            self.assertIn("Nothing was dismissed (exit 4)", body)
            self.assertIn("Press R to restore", body)

    async def test_dismiss_from_details_closes_the_snapshot(self):
        num = self.ids["push"]
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await self.open_details(app, pilot, num)
            await pilot.press("x")
            await self.submit_reason(app, pilot, "from details")
            await self.until(pilot, lambda: self.toast_with(f"c{num} dismissed"), "toast")
            await self.until(pilot, lambda: app._is_main_screen(app.screen),
                             "details closed")
        self.assertEqual(self.item("push").outcome, "user: from details")


# -- restore ---------------------------------------------------------------------

def _damage(store_dir: str) -> None:
    path = os.path.join(store_dir, "todo.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace("kind=task", "kind=bogus", 1))


def _recovered(store_dir: str) -> list:
    try:
        return sorted(os.listdir(os.path.join(store_dir, "recovered")))
    except FileNotFoundError:
        return []


class RestoreTests(_Case):
    async def test_restore_recovers_a_damaged_store(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.assertFalse(self.shown(app, "restore_store"), "hidden on a healthy store")
            _damage(self.store_dir)
            await app._poll_store()
            await pilot.pause()
            self.assertTrue(app.todo_error)
            self.assertTrue(self.shown(app, "restore_store"))
            banner = str(app.screen_stack[0].query_one("#st-banner").content)
            self.assertIn("Press R to restore", banner)
            self.assertNotIn("aitask_sitrep_todo.sh", banner)
            for action in actions.ITEM_ACTIONS:
                self.assertFalse(self.shown(app, action), f"{action} on an unusable store")
            await pilot.press("R")
            await self.until(pilot, lambda: isinstance(app.screen, actions.ConfirmDialog),
                             "the confirm dialog")
            app.screen.query_one("#cd-confirm").press()
            await self.until(pilot, lambda: isinstance(app.screen, actions.ResultDialog),
                             "the result panel")
            self.assertIn("todo.md: restored the last good generation", app.screen.body_text())
            self.assertEqual(app.todo_error, "", "reloaded and readable")
        self.assertIn(["restore", "todo", "--if-damaged"], [c[1:] for c in self.runner.calls])

    async def _race(self, runner) -> str:
        app = self.make_app(runner)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            _damage(self.store_dir)
            await app._poll_store()
            await pilot.press("R")
            await self.until(pilot, lambda: isinstance(app.screen, actions.ConfirmDialog),
                             "the confirm dialog")
            # While the dialog is open: a CLI repair, then a NEWER write.
            self.writer("restore", "todo")
            self.writer("add", "--kind", "action", "--title", "Newer than the repair",
                        "--group", "now")
            self.recovered_before = _recovered(self.store_dir)
            app.screen.query_one("#cd-confirm").press()
            await self.until(pilot, lambda: isinstance(app.screen, actions.ResultDialog),
                             "the result panel")
            return app.screen.body_text()

    async def test_a_repair_while_the_dialog_is_open_is_never_rolled_back(self):
        body = await self._race(Runner(self.root))
        self.assertIn("todo.md is healthy again — nothing restored", body)
        self.assertIn("Newer than the repair", self.todo_text())
        self.assertEqual(_recovered(self.store_dir), self.recovered_before,
                         "nothing preserved: nothing was restored")

    async def test_pre_fix_control_the_unconditional_verb_rolls_it_back(self):
        root = self.root

        class _Unconditional(Runner):
            """The same flow with `--if-damaged` stripped: the pre-fix verb."""

            async def __call__(self, argv, timeout):
                argv = [str(a) for a in argv if str(a) != "--if-damaged"]
                return await super().__call__(argv, timeout)

        await self._race(_Unconditional(root))
        self.assertNotIn("Newer than the repair", self.todo_text(),
                         "the hazard is real: the unconditional verb loses the write")


# -- harvest + refresh -----------------------------------------------------------

_HARVEST_OK = ("HARVEST_ITEM:rec1|c90|added|task|t50\n"
               "HARVESTED:rec1|added=1|existing=0\n"
               "HARVEST_NONE:rec2|already_harvested\n"
               "HARVESTED:rec3|added=0|existing=2\n")
_REFRESH_OK = ("REFRESH_ITEM:c1|task|open->done|applied|status: Done\n"
               "REFRESHED:checked=3|changed=1|stale=0|kept=0|unknown=0\n")


class HarvestRefreshTests(_Case):
    async def test_a_key_run_shows_both_verdicts_and_the_lines(self):
        runner = Runner(self.root, {"aitask_sitrep_harvest.sh": (0, _HARVEST_OK),
                                    "aitask_sitrep_refresh.sh": (0, _REFRESH_OK)})
        app = self.make_app(runner)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("r")
            await self.until(pilot, lambda: isinstance(app.screen, actions.ResultDialog),
                             "the panel")
            body = app.screen.body_text()
            self.assertIn("Harvested: 1 added, 2 existing", body, "summed over records")
            self.assertIn("Refreshed: 3 checked, 1 changed", body)
            self.assertIn("harvested: c90 task", body)
            self.assertIn("refreshed c1: task|open->done|applied|status: Done", body)
            header = str(app.screen_stack[0].query_one("#st-header").content)
            self.assertIn("refreshed", header)
            self.assertIn(" ok", header)
        self.assertEqual(runner.calls[0][1:], ["all", "--root", self.root])
        self.assertEqual(runner.calls[1][1:], ["--root", self.root, "--budget", "60"])

    async def test_r_works_from_the_details_that_advertise_it(self):
        runner = Runner(self.root, {"aitask_sitrep_harvest.sh": (0, _HARVEST_OK),
                                    "aitask_sitrep_refresh.sh": (0, _REFRESH_OK)})
        app = self.make_app(runner)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            screen = await self.open_details(app, pilot, self.ids["trailwatch"])
            self.assertIn("Press  r  to harvest + refresh",
                          screen.body_text(model.resolve_now()), "the advertised key")
            self.assertTrue(self.shown(app, "harvest_refresh"))
            await pilot.press("r")
            await self.until(pilot, lambda: isinstance(app.screen, actions.ResultDialog),
                             "the panel over the details")
            await pilot.press("escape")
            await pilot.pause()
            self.assertIs(app.screen, screen, "back on the same details")
        self.assertEqual(runner.names(), ["aitask_sitrep_harvest.sh",
                                          "aitask_sitrep_refresh.sh"])

    async def test_failures_are_reported_never_as_ok(self):
        runner = Runner(self.root, {
            "aitask_sitrep_harvest.sh": (1, "HARVESTED:rec1|added=1|existing=0\n"
                                            "HARVEST_FAILED:rec2|lock_busy\n"),
            "aitask_sitrep_refresh.sh": (1, "ERROR:aitask_sitrep_refresh.sh timed out after 75s"),
        })
        app = self.make_app(runner)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("r")
            await self.until(pilot, lambda: isinstance(app.screen, actions.ResultDialog),
                             "the panel")
            body = app.screen.body_text()
            self.assertIn("Harvest failed: 1 record(s) failed", body)
            self.assertIn("harvest failed: rec2|lock_busy", body)
            self.assertIn("Refresh failed: aitask_sitrep_refresh.sh timed out after 75s", body)
            self.assertTrue(app.screen.has_class("-failed"))

    async def test_a_second_run_while_one_is_in_flight_is_refused(self):
        release = asyncio.Event()

        async def slow(_argv):
            await release.wait()
            return (0, _HARVEST_OK)

        runner = Runner(self.root, {"aitask_sitrep_harvest.sh": slow,
                                    "aitask_sitrep_refresh.sh": (0, _REFRESH_OK)})
        app = self.make_app(runner)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("r")
            await self.until(pilot, lambda: app._harvest_inflight, "the run started")
            self.assertIsNone(app.check_action("harvest_refresh", ()), "shown disabled")
            app.action_harvest_refresh()
            self.assertTrue(self.toast_with("already running"))
            release.set()
            await self.until(pilot, lambda: isinstance(app.screen, actions.ResultDialog),
                             "the panel")
        self.assertEqual(runner.names().count("aitask_sitrep_harvest.sh"), 1)

    async def test_startup_runs_once_and_only_toasts(self):
        runner = Runner(self.root, {"aitask_sitrep_harvest.sh": (0, ""),
                                    "aitask_sitrep_refresh.sh": (0, "REFRESH_NONE:no_targets\n")})
        app = self.make_app(runner, startup_harvest=True)
        async with app.run_test(size=SIZE) as pilot:
            await self.until(pilot, lambda: self.toast_with("Nothing new to harvest"), "toast")
            self.assertTrue(self.toast_with("Nothing to refresh (no_targets)"))
            self.assertTrue(app._is_main_screen(app.screen), "no panel at startup")
        self.assertEqual(runner.names(), ["aitask_sitrep_harvest.sh",
                                          "aitask_sitrep_refresh.sh"])

    def test_refresh_parser(self):
        ok = model.parse_refresh_output(0, _REFRESH_OK)
        self.assertTrue(ok.ok)
        self.assertEqual(dict(ok.counts)["changed"], "1")
        self.assertEqual(ok.items, ("c1|task|open->done|applied|status: Done",))
        failed = model.parse_refresh_output(1, "REFRESH_FAILED:lock_busy\n")
        self.assertEqual((failed.ok, failed.reason), (False, "lock_busy"))
        missing = model.parse_refresh_output(0, "REFRESH_ITEM:c1|x\n")
        self.assertEqual((missing.ok, missing.final_kind, missing.reason),
                         (False, "missing", "no_result"))
        lying = model.parse_refresh_output(1, _REFRESH_OK)
        self.assertEqual((lying.ok, lying.reason), (False, "exit 1"),
                         "a REFRESHED line under a non-zero exit is not proof")
        last = model.parse_refresh_output(0, "REFRESH_FAILED:deadline\nREFRESHED:checked=1\n")
        self.assertTrue(last.ok, "only the last final line counts")

    def test_harvest_all_summary(self):
        self.assertEqual(actions.summarize_harvest_all(0, "")[:2],
                         (True, "Nothing new to harvest"))
        ok, verdict, _ = actions.summarize_harvest_all(1, "")
        self.assertEqual((ok, verdict), (False, "Harvest failed: exit 1"))
        ok, verdict, lines = actions.summarize_harvest_all(
            0, "HARVEST_REVIEW:rec|c7|added|case=ab|banner\nHARVESTED:rec|added=0|existing=0\n")
        self.assertTrue(ok)
        self.assertIn("kept for review: c7 (the full output is in the store)", lines)


# -- bindings --------------------------------------------------------------------

class BindingsTests(_Case):
    def add_triage_with_task_ref(self) -> int:
        out = self.writer("add", "--kind", "question", "--title",
                          "Triage wrap-up of t12 thing: turn its closing notes into "
                          "action/watch items", "--ref", "t12", "--group", "now")
        return int(out.split(":c")[1])

    EXPECT = {
        # name: (pick, board, push, dismiss)
        "task": (True, True, False, True),
        "triage": (False, False, False, True),
        "pushref": (False, False, True, True),
        "push": (False, False, False, True),
        "xref": (False, False, False, True),
        "unknowntask": (False, True, False, True),
        "done": (False, False, False, False),
        "dismissed": (False, False, False, False),
        "status_ready": (True, True, False, True),
    }
    ACTIONS = ("pick_task", "open_in_board", "show_push", "dismiss_item")

    async def test_the_matrix_on_the_main_list_and_on_details(self):
        triage_ref = self.add_triage_with_task_ref()
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("d")                    # show done / dismissed rows
            await pilot.pause()
            cases = dict(self.EXPECT)
            for name, want in cases.items():
                num = self.ids[name]
                with self.subTest(item=name, where="main"):
                    self.select(app, num)
                    self.assertEqual(tuple(self.shown(app, a) for a in self.ACTIONS), want)
                with self.subTest(item=name, where="details"):
                    await self.open_details(app, pilot, num)
                    self.assertEqual(tuple(self.shown(app, a) for a in self.ACTIONS), want)
                    await pilot.press("escape")
                    await pilot.pause()
            with self.subTest(item="triage naming a task in its ref"):
                self.select(app, triage_ref)
                self.assertEqual(app.store.items[triage_ref].ref, "t12")
                self.assertFalse(self.shown(app, "pick_task"), "p never applies to triage")
                self.assertFalse(self.shown(app, "open_in_board"))
            with self.subTest(where="viewer screens"):
                self.select(app, self.ids["task"])
                await pilot.press("l")
                await pilot.pause()
                self.assertIsInstance(app.screen, appmod.QaLogScreen)
                for a in (*self.ACTIONS, "harvest_refresh", "respawn_agent", "restore_store"):
                    self.assertFalse(self.shown(app, a), a)

    async def test_the_footer_carries_the_keys_that_apply(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, self.ids["task"])
            app.refresh_bindings()
            await pilot.pause()
            active = app.screen.active_bindings
            for key in ("p", "b", "x", "r"):
                self.assertIn(key, active)
            self.select(app, self.ids["triage"])
            app.refresh_bindings()
            await pilot.pause()
            self.assertFalse(self.shown(app, "pick_task"))

    async def test_how_texts_name_a_remapped_key(self):
        import keybinding_registry

        real = keybinding_registry.resolve_key

        def remap(scope, action, default=None):
            return "z" if action == "pick_task" else real(scope, action, default)

        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            with mock.patch.object(keybinding_registry, "resolve_key", side_effect=remap):
                screen = await self.open_details(app, pilot, self.ids["task"])
            self.assertIn("Press  z  to launch  /aitask-pick 10", screen.body_text(
                model.resolve_now()))


# -- agent status + respawn -------------------------------------------------------

class AgentTests(_Case):
    async def test_states_drive_the_header_and_the_respawn_key(self):
        state = {"v": (True, "%1", "%2")}
        app = self.make_app(roles_probe=lambda: state["v"], own_session=lambda: "s1")
        async with app.run_test(size=SIZE) as pilot:
            await self.until(pilot, lambda: app.agent_state == "running", "running")
            header = lambda: str(app.screen_stack[0].query_one("#st-header").content)  # noqa: E731
            self.assertIn("agent: running", header())
            self.assertFalse(self.shown(app, "respawn_agent"))
            state["v"] = (True, None, "%2")
            app._kick_agent_poll()
            await self.until(pilot, lambda: app.agent_state == "absent", "absent")
            self.assertIn("agent: not running — press A", header())
            self.assertTrue(self.shown(app, "respawn_agent"))
            state["v"] = (False, None, None)
            app._kick_agent_poll()
            await self.until(pilot, lambda: app.agent_state == "unknown", "unknown")
            self.assertFalse(self.shown(app, "respawn_agent"),
                             "a failed query is never read as 'no agent'")

    async def test_respawn_runs_open_and_decodes_its_line(self):
        runner = Runner(self.root, {"aitask_sitrep.sh":
                                    (0, "SITREP_RESPAWNED_AGENT:%5|s1:agent-sitrep\n")})
        app = self.make_app(runner, roles_probe=lambda: (True, None, "%2"),
                            own_session=lambda: "s1")
        async with app.run_test(size=SIZE) as pilot:
            await self.until(pilot, lambda: app.agent_state == "absent", "absent")
            await pilot.press("A")
            await self.until(pilot, lambda: isinstance(app.screen, actions.ConfirmDialog),
                             "confirm")
            app.screen.query_one("#cd-confirm").press()
            await self.until(pilot, lambda: self.toast_with("Sitrep agent restarted beside "
                                                             "its TUI"), "toast")
        self.assertEqual(runner.calls[-1][1:], ["open", "--root", self.root, "--session", "s1"])

    async def test_each_open_line_is_decoded(self):
        for line, want in (("SITREP_FOCUSED:%5", "Switched to the sitrep window"),
                           ("SITREP_ADDED_TUI:%5|s1:w", "Sitrep TUI added"),
                           ("SITREP_REFUSED:lock_busy", "Sitrep not opened: lock_busy")):
            with self.subTest(line=line):
                self.toasts.clear()
                runner = Runner(self.root, {"aitask_sitrep.sh": (0 if "REFUSED" not in line
                                                                 else 1, line)})
                app = self.make_app(runner, roles_probe=lambda: (True, None, "%2"),
                                    own_session=lambda: "s1")
                async with app.run_test(size=SIZE) as pilot:
                    await self.until(pilot, lambda: app.agent_state == "absent", "absent")
                    app.action_respawn_agent()
                    await self.until(pilot, lambda: isinstance(app.screen,
                                                               actions.ConfirmDialog), "confirm")
                    app.screen.query_one("#cd-confirm").press()
                    await self.until(pilot, lambda: self.toast_with(want), want)

    async def test_an_agent_that_came_back_is_not_respawned(self):
        probes = iter([(True, None, "%2"), (True, "%9", "%2")])
        runner = Runner(self.root)
        app = self.make_app(runner, roles_probe=lambda: next(probes, (True, "%9", "%2")),
                            own_session=lambda: "s1")
        async with app.run_test(size=SIZE) as pilot:
            await self.until(pilot, lambda: app.agent_state == "absent", "absent")
            await pilot.press("A")
            await self.until(pilot, lambda: self.toast_with("The sitrep agent is running"),
                             "re-check")
        self.assertEqual(runner.calls, [])


# -- launches and freshness ------------------------------------------------------

class DetailFreshnessTests(_Case):
    def patch_launchers(self):
        focus = mock.patch.object(actions.alu, "focus_existing_agent_window",
                                  return_value=False)
        build = mock.patch.object(actions, "build_pick_screen", return_value=None)
        self.focus_mock = focus.start()
        self.build_mock = build.start()
        self.addCleanup(focus.stop)
        self.addCleanup(build.stop)

    async def test_a_changed_ref_refreshes_the_details_and_launches_nothing(self):
        self.patch_launchers()
        num = self.ids["task"]
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            old = await self.open_details(app, pilot, num)
            self.writer("update", f"c{num}", "--ref", "t12")
            await app._poll_store()
            await pilot.press("p")
            await self.until(pilot, lambda: (isinstance(app.screen, appmod.ItemDetailScreen)
                                             and app.screen is not old), "fresh details")
            self.build_mock.assert_not_called()
            self.focus_mock.assert_not_called()
            self.assertTrue(self.toast_with("changed since these details were opened"))
            self.assertEqual(app.screen.item_rev, self.item("task").rev)
            await pilot.press("p")
            await pilot.pause()
            self.build_mock.assert_called_once_with(Path(self.root), "12", narrow=True)

    async def test_a_dismissed_item_closes_its_details_and_launches_nothing(self):
        self.patch_launchers()
        num = self.ids["task"]
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await self.open_details(app, pilot, num)
            self.writer("dismiss", f"c{num}", "--outcome", "gone")
            await app._poll_store()
            for key in ("p", "b"):
                await pilot.press(key)
                await pilot.pause()
            await self.until(pilot, lambda: app._is_main_screen(app.screen) or
                             isinstance(app.screen, appmod.ItemDetailScreen), "settled")
        self.build_mock.assert_not_called()
        self.focus_mock.assert_not_called()

    async def test_the_pick_dialog_callback_rechecks_the_item(self):
        num = self.ids["task"]
        fake = types.SimpleNamespace(full_command="agent-cmd")
        cfg = alu.TmuxLaunchConfig(session="s", window="w", new_session=False,
                                   new_window=True)
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, num)
            with mock.patch.object(actions.alu, "focus_existing_agent_window",
                                   return_value=False), \
                    mock.patch.object(actions, "build_pick_screen", return_value=fake), \
                    mock.patch.object(actions.alu, "launch_in_tmux",
                                      return_value=(1, None)) as launch, \
                    mock.patch.object(actions.alu, "maybe_spawn_minimonitor") as mm:
                with mock.patch.object(app, "push_screen") as push:
                    app.action_pick_task()
                callback = push.call_args[0][1]
                # Control: unchanged item -> the launch happens.
                callback(cfg)
                launch.assert_called_once_with("agent-cmd", cfg)
                mm.assert_called_once_with("s", "w")
                launch.reset_mock()
                with mock.patch.object(app, "push_screen") as push:
                    app.action_pick_task()
                callback = push.call_args[0][1]
                self.writer("update", f"c{num}", "--ref", "t12")
                await app._poll_store()
                callback(cfg)
                launch.assert_not_called()
                self.assertTrue(self.toast_with("changed while the dialog was open"))
                callback("run")
                launch.assert_not_called()

    async def test_run_in_this_pane_is_refused(self):
        num = self.ids["task"]
        fake = types.SimpleNamespace(full_command="agent-cmd")
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, num)
            with mock.patch.object(actions.alu, "focus_existing_agent_window",
                                   return_value=False), \
                    mock.patch.object(actions, "build_pick_screen", return_value=fake), \
                    mock.patch.object(actions.alu, "launch_in_tmux") as launch:
                with mock.patch.object(app, "push_screen") as push:
                    app.action_pick_task()
                push.call_args[0][1]("run")
                launch.assert_not_called()
            self.assertTrue(self.toast_with("cannot run the agent"))

    async def test_an_existing_agent_window_is_focused_instead(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, self.ids["task"])
            with mock.patch.object(actions.alu, "focus_existing_agent_window",
                                   return_value=True) as focus, \
                    mock.patch.object(actions, "build_pick_screen") as build:
                await pilot.press("p")
                await pilot.pause()
            focus.assert_called_once_with("10", Path(self.root))
            build.assert_not_called()


class PushTests(_Case):
    async def test_the_command_is_shown_and_never_run(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, self.ids["pushref"])
            await pilot.press("P")
            await self.until(pilot, lambda: isinstance(app.screen, actions.PushCommandDialog),
                             "the push dialog")
            dlg = app.screen
            self.assertEqual(dlg.command, "git push origin main")
            self.assertIn("no push remote is configured", dlg.note)
            buttons = sorted(b.id for b in dlg.query("Button"))
            self.assertEqual(buttons, ["pc-close", "pc-copy"], "no run path")
            await pilot.press("escape")
        self.assertEqual(self.runner.calls, [], "nothing was executed")

    def test_push_command_follows_the_push_remote_and_the_data_branch(self):
        root = self.root
        subprocess.run(["git", "-C", root, "config", "branch.main.pushRemote", "up"],
                       check=True)
        self.assertEqual(model.push_command(root, "main"), ("git push up main", ""))
        subprocess.run(["git", "-C", root, "config", "--unset", "branch.main.pushRemote"],
                       check=True)
        subprocess.run(["git", "-C", root, "config", "remote.pushDefault", "fork"],
                       check=True)
        self.assertEqual(model.push_command(root, "main")[0], "git push fork main")
        # A valid remote name with shell punctuation stays ONE argument.
        subprocess.run(["git", "-C", root, "config", "remote.pushDefault", "origin;printf"],
                       check=True)
        cmd = model.push_command(root, "main")[0]
        self.assertEqual(cmd, "git push 'origin;printf' main")
        import shlex
        self.assertEqual(shlex.split(cmd), ["git", "push", "origin;printf", "main"])
        subprocess.run(["git", "-C", root, "config", "remote.pushDefault", "fork"],
                       check=True)
        data = os.path.join(root, ".aitask-data")
        subprocess.run(["git", "init", "-q", "-b", "aitask-data", data], check=True)
        self.assertEqual(model.push_command(root, "aitask-data")[0], "./ait git push")
        self.assertEqual(model.push_command(root, "main")[0], "git push fork main",
                         "only the branch the data worktree has out is task data")


class TaskMetaTests(_Case):
    """A task item shows its task's priority / effort (short in the list, in
    full in the details, read from the task FILE) and links to the task's
    description."""

    def setUp(self):
        super().setUp()
        aitasks = Path(self.root) / "aitasks"
        (aitasks / "t10_demo.md").write_text(
            "---\npriority: high\neffort: low\nstatus: Ready\n---\n# t10 demo task\n"
            "The full description.\n")
        (aitasks / "archived").mkdir(exist_ok=True)
        (aitasks / "archived" / "t20_recheck.md").write_text(
            "---\npriority: low\neffort: medium\nstatus: Done\n---\n# t20\n")

    def cell(self, row: str, header: str) -> str:
        at = header.index("Pri/Eff")
        return row[at:at + model.PRI_EFF_W].strip()

    def test_the_short_cell(self):
        meta = model.TaskMeta("1", "aitasks/t1_x.md", "medium", "high")
        self.assertEqual(model.pri_eff_cell(meta), "med/hi")
        self.assertEqual(model.pri_eff_cell(model.TaskMeta("1", "p")), "?/?")
        self.assertEqual(model.pri_eff_cell(False), "—")
        self.assertEqual(model.pri_eff_cell(None), "")
        weird = model.TaskMeta("1", "p", "[bold]urgent[/]", "x" * 30)
        self.assertLessEqual(len(model.pri_eff_cell(weird)), model.PRI_EFF_W)

    def test_lookup_active_archived_child_missing(self):
        self.assertEqual(model.task_meta(self.root, "10"),
                         model.TaskMeta("10", "aitasks/t10_demo.md", "high", "low", "Ready"))
        archived = model.task_meta(self.root, "20")
        self.assertEqual((archived.status, archived.archived), ("Done", True))
        child = Path(self.root) / "aitasks" / "t10"
        child.mkdir()
        (child / "t10_2_part.md").write_text("---\npriority: medium\neffort: high\n---\n")
        self.assertEqual(model.task_meta(self.root, "10_2").path, "aitasks/t10/t10_2_part.md")
        self.assertEqual(model.task_meta(self.root, "10").path, "aitasks/t10_demo.md",
                         "a parent id never matches its child's file")
        self.assertIs(model.task_meta(self.root, "15"), False)
        self.assertIsNone(model.task_meta(self.root, None))
        (Path(self.root) / "aitasks" / "t16_broken.md").write_text("---\n: [unclosed\n---\n")
        self.assertEqual(model.task_meta(self.root, "16").priority, "", "never raises")

    async def test_rows_carry_the_short_cell(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            ol = app.screen_stack[0].query_one("#st-list")
            header = model.header_text(model.cid_width(app.store))
            self.assertIn("Pri/Eff", str(app.screen_stack[0].query_one("#st-columns").content))
            row = lambda name: str(ol.get_option(f"c{self.ids[name]}").prompt)  # noqa: E731
            self.assertEqual(self.cell(row("task"), header), "hi/lo")
            self.assertEqual(self.cell(row("unknowntask"), header), "lo/med", "archived file")
            self.assertEqual(self.cell(row("status_ready"), header), "—", "no task file")
            for name in ("triage", "watch", "pushref", "xref"):
                self.assertEqual(self.cell(row(name), header), "", name)
            self.assertEqual(row("task").index("Pick t10"), header.index("What to do"))

    async def test_details_show_the_metadata_and_open_the_description(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            # The details read the file fresh, not the list's cached copy.
            with open(os.path.join(self.root, "aitasks", "t10_demo.md"), "w") as fh:
                fh.write("---\npriority: medium\neffort: low\nstatus: Implementing\n---\n"
                         "# t10 demo task\nThe full description.\n")
            screen = await self.open_details(app, pilot, self.ids["task"])
            body = screen.body_text(model.resolve_now())
            for want in ("Priority    medium\n", "Effort      low\n",
                         "Task status Implementing\n"):
                self.assertIn(want, body)
            links = screen.query_one("#sd-links")
            first = links.get_option_at_index(0)
            self.assertEqual(first.id, "taskdesc")
            self.assertIn("Task description: t10 (aitasks/t10_demo.md)", str(first.prompt))
            links.highlighted = 0
            await pilot.press("enter")
            await self.until(pilot, lambda: isinstance(app.screen, appmod.PointerViewerScreen),
                             "the task viewer")
            self.assertIn("The full description.", app.screen.view.text)
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            screen = await self.open_details(app, pilot, self.ids["unknowntask"])
            self.assertIn("Task status Done (archived)", screen.body_text(model.resolve_now()))
            await pilot.press("escape")
            await pilot.pause()
            screen = await self.open_details(app, pilot, self.ids["status_ready"])
            self.assertIn("Task        task file not found",
                          screen.body_text(model.resolve_now()))
            self.assertNotEqual(screen.query_one("#sd-links").get_option_at_index(0).id,
                                "taskdesc")
            await pilot.press("escape")
            await pilot.pause()
            screen = await self.open_details(app, pilot, self.ids["triage"])
            body = screen.body_text(model.resolve_now())
            self.assertNotIn("Priority", body, "a triage item names no task of its own")
            await app.workers.wait_for_complete()


class OpenInBoardTests(unittest.TestCase):
    def run_jump(self, own, owned, live="other", launch=(True, None), switch=True):
        with mock.patch.object(actions.alu, "current_tmux_session", return_value=own), \
                mock.patch.object(actions.alu, "session_owned_by",
                                  side_effect=lambda s, _r: owned.get(s, False)), \
                mock.patch.object(actions.alu, "live_project_session", return_value=live), \
                mock.patch.object(actions.alu, "launch_or_focus_board",
                                  return_value=launch) as lob, \
                mock.patch.object(actions.alu, "switch_client_to",
                                  return_value=switch) as sw:
            notes = actions.open_in_board("/repo", "10")
        return notes, lob, sw

    def test_own_session_needs_no_switch(self):
        notes, lob, sw = self.run_jump("mine", {"mine": True})
        lob.assert_called_once_with("mine", Path("/repo"), "10")
        sw.assert_not_called()
        self.assertEqual(notes, [("Showing t10 in the board", "information")])

    def test_another_session_switches_the_client(self):
        notes, lob, sw = self.run_jump("mine", {"other": True})
        lob.assert_called_once_with("other", Path("/repo"), "10")
        sw.assert_called_once_with("other")
        self.assertEqual(notes, [], "nobody is looking at this pane after the switch")

    def test_a_failed_switch_names_the_session(self):
        notes, _lob, sw = self.run_jump("mine", {"other": True}, switch=False)
        sw.assert_called_once_with("other")
        self.assertEqual(notes[0][1], "error")
        self.assertIn("session 'other'", notes[0][0])
        self.assertIn("tmux switch-client -t =other", notes[0][0])

    def test_not_in_tmux_is_refused_before_any_launch(self):
        notes, lob, sw = self.run_jump(None, {})
        lob.assert_not_called()
        sw.assert_not_called()
        self.assertIn("./ait board --focus 10", notes[0][0])

    def test_a_destination_no_longer_owned_is_refused(self):
        notes, lob, _sw = self.run_jump("mine", {}, live="reused")
        lob.assert_not_called()
        self.assertIn("changed before the jump", notes[0][0])

    def test_no_project_session(self):
        notes, lob, _sw = self.run_jump("mine", {}, live=None)
        lob.assert_not_called()
        self.assertEqual(notes[0][1], "error")

    def test_a_board_without_focus_support_is_a_warning(self):
        notes, _lob, _sw = self.run_jump("mine", {"mine": True},
                                         launch=(True, "the running board cannot take "
                                                       "focus requests"))
        self.assertEqual(notes, [("the running board cannot take focus requests", "warning")])


class RunnerCwdEnvTests(unittest.IsolatedAsyncioTestCase):
    async def test_cwd_and_env_are_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, SITREP_PROBE="seen")
            rc, out = await run_owned_group(
                ["sh", "-c", 'pwd; echo "$SITREP_PROBE"; echo "${AITASK_SITREP_DIR:-unset}"'],
                timeout=10, cwd=tmp, env={**env, **{}})
            self.assertEqual(rc, 0)
            lines = out.splitlines()
            self.assertEqual(os.path.realpath(lines[0]), os.path.realpath(tmp))
            self.assertEqual(lines[1], "seen")
            with mock.patch.dict(os.environ, {"AITASK_SITREP_DIR": "/elsewhere"}):
                rc, out = await run_owned_group(
                    ["sh", "-c", 'echo "${AITASK_SITREP_DIR:-unset}"'], timeout=10,
                    env=actions.writer_env())
            self.assertEqual(out.strip(), "unset", "the TUI's writer env drops the override")


if __name__ == "__main__":
    unittest.main()
