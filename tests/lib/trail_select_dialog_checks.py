"""Host-agnostic checks for the two-pane trail selector (t2173_2).

``TrailSelectDialogChecks`` is written ONCE here and mixed into one TestCase
per host App that pushes ``TrailSelectScreen`` — the board (KanbanApp) and
``ait trails`` (TrailsApp). It lives in tests/lib/, not in either test module,
so neither module holds a same-module base carrying ``test_*`` methods
(tests/test_collection_structure.py).
"""
from __future__ import annotations

import asyncio
import contextlib


class TrailSelectDialogChecks:
    """The two-pane trail selector (t2173_2), driven by keys inside a host App.

    Host-agnostic on purpose: the board's By-Trail view and `ait trails` push
    the same `TrailSelectScreen`, and each App binds the arrows with
    `priority=True`, so every check runs in BOTH —
    `BoardTrailSelectDialogTests` in tests/test_board_bytrail_view.py and
    `TrailsAppSelectDialogTests` in tests/test_trails_app.py. A host class provides `_dlg_app()` (a fresh
    App), `_dlg_patches()` (context managers held for the run) and
    `await _dlg_boot(app, pilot)`.

    What the user sees is read from rendered lines or the composited frame,
    never from a stored prompt or style: a markup-parsed title or a header
    scrolled out of view is exactly what a stored value hides (t1366)."""

    HANDLE_A = "art:trail-alpha"
    HANDLE_B = "art:trail-beta"

    def _dlg_info(self, handle, title, **kw):
        fields = dict(
            handle=handle, owner_id="9000", owner_archived=False,
            owner_folded=False, name=title,
            doc={"title": title, "scope": {"kind": "repo"},
                 "generation": {"generated_at": "2026-08-01"},
                 "freshness": {"state": "current"}})
        fields.update(kw)
        return self.ab.TrailInfo(**fields)

    def _dlg_long(self, handle, title, n=60):
        """A trail whose detail pane overflows: a failed load with many
        recorded versions (the last one is `v<n-1>-end`)."""
        versions = [f"v{i:03d}" for i in range(n - 1)] + [f"v{n - 1:03d}-end"]
        return self._dlg_info(handle, title, doc=None,
                              load_error="blob missing", versions=versions)

    @staticmethod
    async def _dlg_settle(pilot, times=5):
        for _ in range(times):
            await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    def _dlg_run(self, infos, body, *, size=(120, 40), overlaps=None,
                 open_handles=(), allow_rescan=False):
        """Push a selector over a booted host App, run `body(app, pilot,
        screen, results)`, and return the dismissal values."""
        results = []

        async def go():
            app = self._dlg_app()
            with contextlib.ExitStack() as stack:
                for cm in self._dlg_patches():
                    stack.enter_context(cm)
                async with app.run_test(size=size) as pilot:
                    await self._dlg_boot(app, pilot)
                    screen = self.ab.TrailSelectScreen(
                        infos, overlaps or {}, open_handles=open_handles,
                        allow_rescan=allow_rescan)
                    app.push_screen(screen, results.append)
                    await self._dlg_settle(pilot)
                    await body(app, pilot, screen, results)

        asyncio.run(go())
        return results

    @staticmethod
    def _dlg_rows(screen) -> list[str]:
        """The title list's RENDERED rows (not the options' stored prompts)."""
        options = screen.query_one("#trail_select_list")
        rows = [options.render_line(y).text.rstrip()
                for y in range(options.size.height)]
        return [row.strip() for row in rows if row.strip()]

    @staticmethod
    def _dlg_row_look(screen, y):
        """How list row ``y`` RENDERS: background, foreground and bold of its
        text segments (one option per row: the list has no border/padding)."""
        options = screen.query_one("#trail_select_list")
        looks = {(str(seg.style.bgcolor), str(seg.style.color),
                  bool(seg.style.bold))
                 for seg in options.render_line(y)
                 if seg.text.strip() and seg.style is not None}
        assert looks, f"list row {y} rendered no text"
        return frozenset(looks)

    @staticmethod
    def _dlg_detail(screen) -> str:
        return str(screen.query_one("#trail_select_detail_body").render())

    @staticmethod
    def _dlg_text(app, widget) -> str:
        """The composited frame sliced to `widget`, whitespace collapsed."""
        region = widget.region
        rows = [strip.text for strip
                in app.screen._compositor.render_strips(app.screen.size)]
        raw = " ".join(row[region.x:region.right]
                       for row in rows[region.y:region.bottom])
        return " ".join(
            "".join(" " if "▀" <= ch <= "▟" else ch for ch in raw).split())

    @staticmethod
    def _dlg_pane(screen):
        return screen.query_one("#trail_select_detail")

    async def _dlg_type(self, pilot, text):
        await pilot.press(*text)
        await self._dlg_settle(pilot)

    async def _dlg_clear(self, pilot, screen):
        for _ in screen.query_one("#trail_select_search").value:
            await pilot.press("backspace")
        await self._dlg_settle(pilot)

    # --- filtering ------------------------------------------------------------

    def test_dlg_filters_by_title_only_with_subsequence_match(self):
        infos = [self._dlg_info(self.HANDLE_A, "Alpha runner"),
                 self._dlg_info(self.HANDLE_B, "Beta crew")]

        async def body(app, pilot, screen, results):
            self.assertEqual(self._dlg_rows(screen),
                             ["Alpha runner", "Beta crew"])
            # Owner and scope are shown in the detail pane but never searched.
            for query in ("repo", "t9000"):
                with self.subTest(query=query):
                    await self._dlg_type(pilot, query)
                    self.assertEqual(self._dlg_rows(screen), [])
                    self.assertIn(f'No trail title matches "{query}"',
                                  self._dlg_detail(screen))
                    await pilot.press("enter")    # nothing to open
                    await self._dlg_settle(pilot)
                    self.assertIs(app.screen, screen)
                    await self._dlg_clear(pilot, screen)
            await self._dlg_type(pilot, "bcw")    # a subsequence, not a substring
            self.assertEqual(self._dlg_rows(screen), ["Beta crew"])
            self.assertIn("Beta crew", self._dlg_detail(screen))
            await self._dlg_clear(pilot, screen)
            self.assertEqual(self._dlg_rows(screen),
                             ["Alpha runner", "Beta crew"])

        self.assertEqual(self._dlg_run(infos, body), [])

    def test_dlg_bracketed_titles_render_and_match_literally(self):
        """A `str` OptionList prompt is parsed as markup — `Plan [bold] x`
        would render `Plan  x` while the filter matched the raw title."""
        infos = [self._dlg_info(self.HANDLE_A, "Plan [bold] x"),
                 self._dlg_info(self.HANDLE_B, "Other")]

        async def body(app, pilot, screen, results):
            self.assertEqual(self._dlg_rows(screen), ["Plan [bold] x", "Other"])
            self.assertIn("Plan [bold] x",
                          self._dlg_text(app, self._dlg_pane(screen)))
            await self._dlg_type(pilot, "[bold]")
            self.assertEqual(self._dlg_rows(screen), ["Plan [bold] x"])

        self._dlg_run(infos, body)

    # --- keys -------------------------------------------------------------------

    def test_dlg_arrows_move_the_highlight_and_the_detail_while_the_box_keeps_focus(self):
        infos = [self._dlg_info(f"art:t{i}", f"Trail number {i:02d}")
                 for i in range(3)]

        async def body(app, pilot, screen, results):
            options = screen.query_one("#trail_select_list")
            search = screen.query_one("#trail_select_search")
            self.assertIs(app.focused, search)
            self.assertIn("Trail number 00", self._dlg_detail(screen))
            # The highlight must be VISIBLE on the unfocused list: the selected
            # row renders differently from an idle one, and the difference
            # moves with the cursor (t1366's invisible-selection defect). The
            # detail pane changes on every move too, so a whole-frame diff
            # would pass with no highlight at all.
            selected, idle = (self._dlg_row_look(screen, 0),
                              self._dlg_row_look(screen, 1))
            self.assertNotEqual(selected, idle,
                                "the selected row looks like an idle one")
            await pilot.press("down")
            await self._dlg_settle(pilot)
            self.assertEqual(options.highlighted, 1)
            self.assertIn("Trail number 01", self._dlg_detail(screen))
            self.assertIs(app.focused, search)
            self.assertEqual(self._dlg_row_look(screen, 1), selected,
                             "the highlight did not move to the new row")
            self.assertEqual(self._dlg_row_look(screen, 0), idle,
                             "the old row kept the highlight")
            await pilot.press("up")
            await self._dlg_settle(pilot)
            self.assertEqual(options.highlighted, 0)
            self.assertEqual(self._dlg_row_look(screen, 0), selected)
            self.assertIs(app.focused, search)

        self.assertEqual(self._dlg_run(infos, body), [])

    def test_dlg_enter_opens_the_highlighted_trail(self):
        infos = [self._dlg_info(self.HANDLE_A, "Alpha"),
                 self._dlg_info(self.HANDLE_B, "Beta")]

        async def body(app, pilot, screen, results):
            await pilot.press("down")
            await self._dlg_settle(pilot)
            await pilot.press("enter")
            await self._dlg_settle(pilot)

        self.assertEqual(self._dlg_run(infos, body), [self.HANDLE_B])

    def test_dlg_a_click_opens_that_trail(self):
        infos = [self._dlg_info(self.HANDLE_A, "Alpha"),
                 self._dlg_info(self.HANDLE_B, "Beta")]

        async def body(app, pilot, screen, results):
            await pilot.click("#trail_select_list", offset=(2, 1))
            await self._dlg_settle(pilot)

        self.assertEqual(self._dlg_run(infos, body), [self.HANDLE_B])

    def test_dlg_escape_opens_nothing(self):
        infos = [self._dlg_info(self.HANDLE_A, "Alpha")]

        async def body(app, pilot, screen, results):
            await pilot.press("escape")
            await self._dlg_settle(pilot)
            self.assertIsNot(app.screen, screen)

        # The board's priority `escape` dismisses with no value; the trails
        # App's reaches the screen's own `cancel`. Neither opens a trail.
        self.assertIn(self._dlg_run(infos, body), ([], [None]))

    def test_dlg_a_typed_r_is_text_and_ctrl_r_rescans(self):
        infos = [self._dlg_info(self.HANDLE_A, "Alpha")]

        async def body(app, pilot, screen, results):
            hint = str(screen.query_one("#trail_select_hint").render())
            self.assertIn("Ctrl+R rescan", hint)
            await self._dlg_type(pilot, "r")
            self.assertEqual(screen.query_one("#trail_select_search").value, "r")
            self.assertIs(app.screen, screen)
            self.assertEqual(results, [])
            await pilot.press("ctrl+r")
            await self._dlg_settle(pilot)

        self.assertEqual(self._dlg_run(infos, body, allow_rescan=True),
                         [self.ab.TRAIL_SELECT_RESCAN])

    def test_dlg_ctrl_r_is_inert_without_allow_rescan(self):
        infos = [self._dlg_info(self.HANDLE_A, "Alpha")]

        async def body(app, pilot, screen, results):
            hint = str(screen.query_one("#trail_select_hint").render())
            self.assertNotIn("Ctrl+R", hint)
            await pilot.press("ctrl+r")
            await self._dlg_settle(pilot)
            self.assertIs(app.screen, screen)

        self.assertEqual(self._dlg_run(infos, body), [])

    # --- what each pane shows -------------------------------------------------

    def test_dlg_open_marker_in_the_list_and_the_detail(self):
        infos = [self._dlg_info(self.HANDLE_A, "Alpha"),
                 self._dlg_info(self.HANDLE_B, "Beta")]

        async def body(app, pilot, screen, results):
            self.assertEqual(self._dlg_rows(screen), ["Alpha  ● open", "Beta"])
            self.assertIn("● open", self._dlg_detail(screen))
            await pilot.press("down")
            await self._dlg_settle(pilot)
            self.assertNotIn("● open", self._dlg_detail(screen))

        self._dlg_run(infos, body, open_handles={self.HANDLE_A})

    def test_dlg_shared_tasks_show_in_the_detail_not_the_list(self):
        infos = [self._dlg_info(self.HANDLE_A, "Alpha"),
                 self._dlg_info(self.HANDLE_B, "Beta")]
        overlaps = {self.HANDLE_A: [("t42", "Beta")],
                    self.HANDLE_B: [("t42", "Alpha")]}

        async def body(app, pilot, screen, results):
            self.assertEqual(self._dlg_rows(screen), ["Alpha", "Beta"])
            self.assertIn("t42 — also in Beta",
                          self._dlg_text(app, self._dlg_pane(screen)))

        self._dlg_run(infos, body, overlaps=overlaps)

    def test_dlg_an_error_trail_shows_its_error_and_versions(self):
        infos = [self._dlg_info(self.HANDLE_A, "Broken", doc=None,
                                load_error="blob missing",
                                versions=["sha256:aaa", "sha256:bbb"])]

        async def body(app, pilot, screen, results):
            text = self._dlg_text(app, self._dlg_pane(screen))
            for needle in ("Broken", "✗ unreadable", "blob missing",
                           "sha256:aaa", "sha256:bbb"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, text)

        self._dlg_run(infos, body)

    # --- layout -----------------------------------------------------------------

    def test_dlg_the_last_trail_is_reachable_and_cancel_is_visible(self):
        infos = [self._dlg_info(f"art:t{i}", f"Trail number {i:02d}")
                 for i in range(30)]

        async def body(app, pilot, screen, results):
            for _ in range(29):
                await pilot.press("down")
            await self._dlg_settle(pilot)
            self.assertEqual(screen.query_one("#trail_select_list").highlighted,
                             29)
            self.assertIn("Trail number 29", self._dlg_rows(screen))
            cancel = screen.query_one("#btn_trail_select_cancel")
            self.assertTrue(screen.can_view_entire(cancel),
                            "Cancel is off-screen")

        self._dlg_run(infos, body, size=(100, 30))

    def test_dlg_the_hint_fits_80x24(self):
        infos = [self._dlg_info(f"art:t{i}", f"Trail {i:02d}")
                 for i in range(10)]

        async def body(app, pilot, screen, results):
            text = self._dlg_text(app, screen.query_one("#trail_select_dialog"))
            for line in ("Type to filter · ↑/↓ move · Enter open · Esc cancel",
                         "PgUp/PgDn scroll details · Ctrl+R rescan"):
                with self.subTest(line=line):
                    self.assertIn(line, text, "hint truncated at 80×24")
            self.assertTrue(screen.can_view_entire(
                screen.query_one("#btn_trail_select_cancel")))

        self._dlg_run(infos, body, size=(80, 24), allow_rescan=True)

    # --- focus cycle and the overflowing detail pane --------------------------

    def test_dlg_focus_cycles_box_and_cancel_and_pgup_pgdn_scroll_details(self):
        infos = [self._dlg_long(self.HANDLE_A, "Long trail"),
                 self._dlg_info(self.HANDLE_B, "Short trail")]

        async def body(app, pilot, screen, results):
            search = screen.query_one("#trail_select_search")
            cancel = screen.query_one("#btn_trail_select_cancel")
            pane = self._dlg_pane(screen)
            seen = []
            for key in ("tab", "tab", "shift+tab", "shift+tab"):
                await pilot.press(key)
                await self._dlg_settle(pilot)
                seen.append(app.focused)
            self.assertEqual(seen, [cancel, search, cancel, search],
                             "focus visited something other than box/Cancel")
            self.assertGreater(pane.max_scroll_y, 0, "fixture must overflow")

            await pilot.press("pagedown")
            await self._dlg_settle(pilot)
            first = pane.scroll_y
            self.assertGreater(first, 0)
            for _ in range(20):
                await pilot.press("pagedown")
            await self._dlg_settle(pilot)
            self.assertEqual(pane.scroll_y, pane.max_scroll_y)
            self.assertIn("v059-end", self._dlg_text(app, pane))
            await pilot.press("pageup")
            await self._dlg_settle(pilot)
            self.assertLess(pane.scroll_y, pane.max_scroll_y)
            self.assertIs(app.focused, search)

            # ↑/↓ still drive the list after a Tab round trip.
            await pilot.press("tab", "shift+tab", "down")
            await self._dlg_settle(pilot)
            self.assertEqual(screen.query_one("#trail_select_list").highlighted,
                             1)
            # From Cancel, ↑ goes back to the box — no scroll, no exit.
            await pilot.press("tab")
            await self._dlg_settle(pilot)
            self.assertIs(app.focused, cancel)
            await pilot.press("up")
            await self._dlg_settle(pilot)
            self.assertIs(app.focused, search)
            self.assertIs(app.screen, screen)

        self.assertEqual(self._dlg_run(infos, body, size=(100, 30)), [])

    def test_dlg_a_new_selection_opens_its_detail_at_the_top(self):
        """Replacing the detail body keeps the pane's scroll offset, so after
        paging through one long trail the next one's header would sit above
        the viewport — by ↓ and by filtering alike."""
        infos = [self._dlg_long(self.HANDLE_A, "Alpha long"),
                 self._dlg_long(self.HANDLE_B, "Beta long")]

        async def body(app, pilot, screen, results):
            pane = self._dlg_pane(screen)

            async def page_down():
                await pilot.press("pagedown")
                await self._dlg_settle(pilot)
                self.assertGreater(pane.scroll_y, 0)

            await page_down()
            await pilot.press("down")                    # → Beta
            await self._dlg_settle(pilot)
            self.assertEqual(pane.scroll_y, 0)
            self.assertIn("Beta long", self._dlg_text(app, pane))

            await page_down()
            await self._dlg_type(pilot, "alp")           # filter → Alpha
            self.assertEqual(self._dlg_rows(screen), ["Alpha long"])
            self.assertEqual(pane.scroll_y, 0)
            self.assertIn("Alpha long", self._dlg_text(app, pane))

            # Control: a filter that keeps the same trail keeps the position.
            await page_down()
            kept = pane.scroll_y
            await self._dlg_type(pilot, "h")
            self.assertEqual(self._dlg_rows(screen), ["Alpha long"])
            self.assertEqual(pane.scroll_y, kept)

        self.assertEqual(self._dlg_run(infos, body, size=(100, 30)), [])
