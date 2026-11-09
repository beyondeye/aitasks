"""`ait board --focus <id>` and the board's pane mailbox, app side (t2211_3).

* **argv** -- `main()` accepts `12`, `t12`, `12_3` and refuses anything else
  with a usage error before any App exists; `$TMUX_PANE` / `$TMUX` are read
  there only.
* **cold focus** -- `KanbanApp(focus_task=...)` selects that card after the
  first load, a child's parent expanded; it wins over the startup anchor.
* **reports** -- an archived id, an unknown id, and a card the current view
  hides are each reported, never silently dropped.
* **mailbox** -- a request delivered to the board's pane focuses the card; the
  boot baseline is never replayed; a repeated request id is ignored; a
  malformed one is recorded as seen and only warned about.

Boots the real `KanbanApp` against a fixture tree (`tests/lib/board_fixture.py`).
The tmux reads are stubbed at the mixin's import seam -- nothing reaches a real
tmux server. The writer side is `test_board_focus_writer.py`.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_board_focus.py -q
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

REQ_A = "a" * 32
REQ_B = "b" * 32


class _BoardCase(bf.FixtureBoardTestBase, unittest.IsolatedAsyncioTestCase):
    SIZE = (200, 50)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        archived = cls.tree / "aitasks" / "archived"
        archived.mkdir(parents=True, exist_ok=True)
        (archived / "t8999_old_thing.md").write_text(
            "---\npriority: low\neffort: low\nissue_type: chore\nstatus: Done\n---\n"
            "# old\n")

    @property
    def bfr(self):
        """The mixin's module, as the fixture-loaded board imported it (test
        modules never import a board module themselves)."""
        return sys.modules[self.ab.BoardFocusMailboxMixin.__module__]

    def make_app(self, **kw):
        app = self.ab.KanbanApp(**kw)
        self.toasts = []
        real = app.notify

        def notify(message, *a, **k):
            self.toasts.append(str(message))
            return real(message, *a, **k)

        app.notify = notify
        return app

    async def settle(self, pilot, n: int = 8):
        for _ in range(n):
            await pilot.pause()

    def focused_filename(self, app) -> str:
        card = app._focused_card()
        return card.task_data.filename if card is not None else ""


class MainArgvTests(_BoardCase):
    def test_normalize(self):
        for raw, want in (("12", "12"), ("t12", "12"), ("12_3", "12_3"),
                          ("t12_3", "12_3"), (" 7 ", "7")):
            self.assertEqual(self.ab.normalize_task_id(raw), want)
        for bad in ("", None, "tt12", "12_", "12_3_4", "x12", "12 13", "-1"):
            self.assertIsNone(self.ab.normalize_task_id(bad), bad)

    def test_main_parses_focus_and_passes_the_pane(self):
        seen = {}

        class _Fake:
            def __init__(self, **kw):
                seen.update(kw)

            def run(self):
                seen["ran"] = True

        with mock.patch.object(self.ab, "KanbanApp", _Fake), \
                mock.patch.dict("os.environ", {"TMUX_PANE": "%9", "TMUX": "/s,1,0"}):
            self.ab.main(["--focus", "t9000_1"])
        self.assertEqual(seen, {"focus_task": "9000_1", "focus_pane": "%9",
                                "focus_tmux_env": "/s,1,0", "ran": True})

    def test_main_without_args_is_the_plain_board(self):
        seen = {}

        class _Fake:
            def __init__(self, **kw):
                seen.update(kw)

            def run(self):
                pass

        with mock.patch.object(self.ab, "KanbanApp", _Fake), \
                mock.patch.dict("os.environ", {}, clear=False):
            self.ab.main([])
        self.assertIsNone(seen["focus_task"])

    def test_an_invalid_id_is_a_usage_error(self):
        with mock.patch.object(self.ab, "KanbanApp") as app_cls:
            for bad in ("x", "12_", "t"):
                with self.subTest(bad=bad), self.assertRaises(SystemExit) as cm:
                    self.ab.main(["--focus", bad])
                self.assertEqual(cm.exception.code, 2)
        app_cls.assert_not_called()


class ColdFocusTests(_BoardCase):
    async def test_a_parent_card_is_selected_after_load(self):
        app = self.make_app(focus_task="9003")
        async with app.run_test(size=self.SIZE) as pilot:
            await self.settle(pilot)
            self.assertEqual(self.focused_filename(app), "t9003_gamma.md")
        # Control: without --focus the startup anchor (leftmost card) wins.
        app = self.make_app()
        async with app.run_test(size=self.SIZE) as pilot:
            await self.settle(pilot)
            self.assertNotEqual(self.focused_filename(app), "t9003_gamma.md")

    async def test_a_child_card_expands_its_parent(self):
        app = self.make_app(focus_task="9000_2")
        async with app.run_test(size=self.SIZE) as pilot:
            await self.settle(pilot)
            self.assertIn("t9000_parent.md", app.expanded_tasks)
            self.assertEqual(self.focused_filename(app), "t9000_2_childtwo.md")

    async def test_archived_and_unknown_ids_are_reported(self):
        for task_id, want in (("8999", "t8999 is archived"), ("4242", "t4242 not found")):
            with self.subTest(task_id=task_id):
                app = self.make_app(focus_task=task_id)
                async with app.run_test(size=self.SIZE) as pilot:
                    await self.settle(pilot)
                self.assertTrue(any(want in t for t in self.toasts), self.toasts)

    async def test_a_card_the_view_hides_is_reported(self):
        app = self.make_app()
        async with app.run_test(size=self.SIZE) as pilot:
            await self.settle(pilot)
            app.search_filter = "zz-no-such-card"
            app.apply_filter()
            await self.settle(pilot)
            app.focus_task_by_id("9003")
            await self.settle(pilot, 12)
            self.assertNotEqual(self.focused_filename(app), "t9003_gamma.md")
        self.assertTrue(any("not visible in the current view" in t for t in self.toasts),
                        self.toasts)

    async def test_a_request_behind_a_modal_waits_for_it(self):
        app = self.make_app()
        async with app.run_test(size=self.SIZE) as pilot:
            await self.settle(pilot)
            with mock.patch.object(app, "_modal_is_active", return_value=True):
                app.focus_task_by_id("9003")
            self.assertEqual(app._pending_focus_task, "9003")
            self.assertNotEqual(self.focused_filename(app), "t9003_gamma.md")
            app._resume_focus_request()
            await self.settle(pilot)
            self.assertEqual(self.focused_filename(app), "t9003_gamma.md")
            self.assertIsNone(app._pending_focus_task)


class MailboxTests(_BoardCase):
    def patch_tmux(self, values: list):
        """The mixin's tmux seam: the gateway check, the stamp and the reads.
        ``values`` is consumed by successive reads (the first is the baseline)."""
        self.reads = list(values)
        self.stamps = []
        patches = [
            mock.patch.object(self.bfr, "pane_on_gateway_server", return_value=True),
            mock.patch.object(self.bfr, "mark_board_receiver",
                              side_effect=lambda p: self.stamps.append(("mark", p)) or True),
            mock.patch.object(self.bfr, "unmark_board_receiver",
                              side_effect=lambda p: self.stamps.append(("unmark", p)) or True),
            mock.patch.object(self.bfr, "read_board_focus_request", side_effect=self._read),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _read(self, pane):
        return self.reads.pop(0) if self.reads else self.last

    async def deliver(self, app, pilot, value: str):
        self.last = value
        app._focus_req_busy = False
        app._poll_focus_req()
        await app.workers.wait_for_complete()
        await self.settle(pilot)

    async def test_a_delivered_request_focuses_the_card_and_the_baseline_is_not_replayed(self):
        self.last = f"{REQ_A} 9003"
        self.patch_tmux([f"{REQ_A} 9003"])          # a leftover from an earlier board
        app = self.make_app(focus_pane="%3", focus_tmux_env="/sock,1,0")
        async with app.run_test(size=self.SIZE) as pilot:
            await app.workers.wait_for_complete()
            await self.settle(pilot)
            self.assertIn(("mark", "%3"), self.stamps, "stamped after the baseline")
            self.assertTrue(app._focus_req_stamped)
            await self.deliver(app, pilot, f"{REQ_A} 9003")
            self.assertNotEqual(self.focused_filename(app), "t9003_gamma.md",
                                "the baseline request is never replayed")
            await self.deliver(app, pilot, f"{REQ_B} 9003")
            self.assertEqual(self.focused_filename(app), "t9003_gamma.md")
            app._first_board_focus_target().focus()
            await self.deliver(app, pilot, f"{REQ_B} 9003")
            self.assertNotEqual(self.focused_filename(app), "t9003_gamma.md",
                                "a repeated request id is ignored")
            await self.deliver(app, pilot, f"{'c' * 32} 9000_1")
            self.assertEqual(self.focused_filename(app), "t9000_1_childone.md")
        self.assertIn(("unmark", "%3"), self.stamps, "unstamped on exit")

    async def test_a_malformed_request_is_warned_once(self):
        self.last = ""
        self.patch_tmux([""])
        app = self.make_app(focus_pane="%3", focus_tmux_env="/sock,1,0")
        async with app.run_test(size=self.SIZE) as pilot:
            await app.workers.wait_for_complete()
            await self.settle(pilot)
            await self.deliver(app, pilot, f"{REQ_A} 12;rm")
            await self.deliver(app, pilot, f"{REQ_A} 12;rm")
        warned = [t for t in self.toasts if "malformed board focus request" in t]
        self.assertEqual(len(warned), 1)
        self.assertFalse(any("12;rm" in t for t in self.toasts), "never echoed")

    async def test_no_pane_means_no_mailbox(self):
        self.last = ""
        self.patch_tmux([""])
        app = self.make_app()
        async with app.run_test(size=self.SIZE) as pilot:
            await self.settle(pilot)
            self.assertFalse(app._focus_req_stamped)
        self.assertEqual(self.stamps, [])

    async def test_a_pane_of_another_server_is_never_stamped(self):
        self.last = ""
        self.patch_tmux([""])
        with mock.patch.object(self.bfr, "pane_on_gateway_server", return_value=False):
            app = self.make_app(focus_pane="%3", focus_tmux_env="/other,1,0")
            async with app.run_test(size=self.SIZE) as pilot:
                await app.workers.wait_for_complete()
                await self.settle(pilot)
                self.assertFalse(app._focus_req_stamped)
        self.assertEqual(self.stamps, [])


if __name__ == "__main__":
    unittest.main()
