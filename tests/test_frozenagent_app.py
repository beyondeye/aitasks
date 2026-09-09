#!/usr/bin/env python3
"""Behavioural pins for the `ait frozenagent` viewer TUI (t1705_6).

Everything here runs headless under ``App.run_test`` against a temporary store
(``AITASKS_AGENT_SESSIONS_FILE`` / ``AITASKS_FROZEN_DIR``) and a fake
``TmuxClient`` that records argv. Nothing touches a real tmux server; the live
half — that a respawned stand-in stamps its own pane — belongs to
``tests/test_frozenagent_standin_stamp.sh``.

Three groups are worth naming, because each pins a defect the plan's
re-verification found rather than a feature:

``CaptureLogSelectionTests``
    ``RichLog`` does **not** implement ``get_selection`` in Textual 8.2.7, so a
    stock ``RichLog`` extracts nothing from a mouse drag and paints no
    highlight. ``CaptureLog`` adds the three overrides ``Log`` has; these tests
    pin both the behaviour and the Textual internals it reaches into, so an
    upgrade fails by name instead of silently breaking selection.

``RestoreOutcomeTests``
    ``run-shell -b`` returns no nonce, and ``restore-begin`` is what clears
    ``last_error`` — so a poll firing before the coordinator starts reads the
    *previous* attempt's error. The pin is that a stale error must NOT be
    reported as this restore failing.

``DropOutcomeTests``
    ``drop`` never enters ``restoring`` or ``live``; the record disappears. The
    pin is that it has its own terminal path and never enters the restore
    interpreter, plus the per-record single-flight guard that stops a ``drop``
    racing a restore the user just started.

Run: python3 tests/run_all_python_tests.sh (or this file directly)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

FIXTURE_DIR = Path(__file__).resolve().parent / "data" / "frozen_capture"


class FakeTmux:
    """Records argv; never spawns anything."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.rc = 0

    def run(self, args, timeout=None):
        self.calls.append(list(args))
        return (self.rc, "")

    def run_shell_argvs(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] == ["run-shell", "-b"]]


class _StoreFixture:
    """A temp store plus capture files, driven through the module API."""

    def __init__(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="ait_fa_"))
        self.store = self.dir / "agent_sessions.json"
        self.frozen = self.dir / "frozen"
        os.environ["AITASKS_AGENT_SESSIONS_FILE"] = str(self.store)
        os.environ["AITASKS_FROZEN_DIR"] = str(self.frozen)

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)
        os.environ.pop("AITASKS_AGENT_SESSIONS_FILE", None)
        os.environ.pop("AITASKS_FROZEN_DIR", None)

    def write(self, records: list[dict]) -> None:
        self.store.write_text(json.dumps({"version": 1, "sessions": records}))

    def read(self) -> list[dict]:
        return json.loads(self.store.read_text())["sessions"]

    def capture(self, record_id: str, *, present: bool = True) -> tuple[str, str]:
        if not present:
            return (str(self.frozen / record_id / "capture.ansi"),
                    str(self.frozen / record_id / "capture.txt"))
        d = self.frozen / record_id
        d.mkdir(parents=True, exist_ok=True)
        ansi = d / "capture.ansi"
        txt = d / "capture.txt"
        shutil.copy(FIXTURE_DIR / "sample.ansi", ansi)
        shutil.copy(FIXTURE_DIR / "sample.txt", txt)
        return str(ansi), str(txt)


def _header_plain(app) -> str:
    """The header's RENDERED text, with markup already resolved."""
    rendered = app.query_one("#fa-header").render()
    return rendered.plain if hasattr(rendered, "plain") else str(rendered)


def _record(rid: str, **over) -> dict:
    """A schema-v1 record with every field the parser requires."""
    base = {
        "id": rid, "root": "/tmp/proj", "window": "agent-pick-1705",
        "window_slot": 0, "pane_id": "%9", "pane_pid": 4242,
        "session": "aitasks", "operation": "pick", "task_id": "1705",
        "agent_string": "claudecode/opus5", "agent_kind": "claudecode",
        "codeagent_session_id": "", "transcript_path": "",
        "started_at": "2026-09-04T09:12:03Z", "state": "frozen",
        "state_at": "2026-09-04T09:20:00Z",
        "op_nonce": "", "op_owner_pid": 0, "op_started_at": "",
        "frozen_at": "2026-09-04T09:20:00Z",
        "capture_ansi": "", "capture_txt": "", "capture_lines": 6,
        "last_phase": "", "standin_pid": 0, "launch_pid": 0,
        "restore_attempts": 0, "restore_mode": "", "ack": "", "last_error": "",
    }
    base.update(over)
    # The store REFUSES an incoherent lease (`op_nonce` / `op_owner_pid` /
    # `op_started_at` must be all set or all empty), so a fixture that sets only
    # the nonce is unparseable and `by_id` silently returns None — which looks
    # like an app bug and is not one. Fill the triple in.
    if base["op_nonce"]:
        base.setdefault("op_owner_pid", 0)
        base["op_owner_pid"] = base["op_owner_pid"] or 999999
        base["op_started_at"] = base["op_started_at"] or "2026-09-04T09:21:00Z"
    return base


class _AppCase(unittest.IsolatedAsyncioTestCase):
    """Shared fixture: a temp store, a fake tmux, one frozen record."""

    RECORD_ID = "7f3a2c1d"

    def setUp(self) -> None:
        self.fx = _StoreFixture()
        self.addCleanup(self.fx.cleanup)
        ansi, txt = self.fx.capture(self.RECORD_ID)
        self.fx.write([_record(self.RECORD_ID, capture_ansi=ansi, capture_txt=txt)])

        import frozenagent.frozenagent_app as app_mod
        self.app_mod = app_mod
        self.tmux = FakeTmux()
        self._real_tmux = app_mod._TMUX
        app_mod._TMUX = self.tmux
        self.addCleanup(lambda: setattr(app_mod, "_TMUX", self._real_tmux))
        # A stand-in only stamps when it is really inside a pane; the tests that
        # care set TMUX_PANE explicitly.
        self._old_pane = os.environ.pop("TMUX_PANE", None)
        self.addCleanup(
            lambda: os.environ.__setitem__("TMUX_PANE", self._old_pane)
            if self._old_pane is not None else None
        )

    def make_app(self, record_id: str | None = RECORD_ID):
        return self.app_mod.FrozenAgentApp(record_id)


# ───────────────────────── CaptureLog ─────────────────────────────────────


class CaptureLogSelectionTests(unittest.IsolatedAsyncioTestCase):
    """`RichLog` has no native selection; `CaptureLog` adds it."""

    async def test_stock_richlog_still_lacks_get_selection(self):
        """The premise `CaptureLog` exists for.

        If a Textual release ever implements this, `CaptureLog` becomes
        redundant and should be deleted rather than left shadowing the stock
        behaviour — so the premise is asserted, not assumed.
        """
        from textual.widgets import RichLog
        self.assertNotIn("get_selection", RichLog.__dict__)

    async def test_textual_internals_capture_log_depends_on_still_exist(self):
        """Upgrade guard for the un-promised internals `CaptureLog` reaches into.

        Without this a Textual upgrade breaks mouse selection SILENTLY — the
        drag still runs, it just copies nothing.
        """
        from textual.selection import Selection
        from textual.strip import Strip
        from textual.widgets import RichLog
        for name in ("apply_offsets", "divide", "join", "apply_style"):
            self.assertTrue(hasattr(Strip, name), f"Strip.{name} vanished")
        self.assertTrue(hasattr(Selection, "get_span"))
        self.assertTrue(hasattr(Selection, "extract"))
        probe = RichLog()
        for name in ("_line_cache", "_start_line", "_widest_line_width", "lines"):
            self.assertTrue(hasattr(probe, name), f"RichLog.{name} vanished")

    async def test_extraction_and_painting_match_stock_log(self):
        """Parity with the one stock widget that does support selection.

        Comparing against `Log` rather than against hard-coded colours keeps the
        pin honest when the theme changes: what matters is that `CaptureLog`
        behaves like the widget Textual itself ships.
        """
        from textual.app import App, ComposeResult
        from textual.geometry import Offset
        from textual.selection import Selection
        from textual.widgets import Log
        from rich.text import Text
        from frozenagent.capture_log import CaptureLog

        lines = ["alpha", "bravo", "charlie"]

        class Harness(App):
            def compose(self) -> ComposeResult:
                yield CaptureLog(highlight=False, markup=False, wrap=False, id="cl")
                yield Log(id="lg")

        app = Harness()
        async with app.run_test(size=(40, 12)) as pilot:
            cl = app.query_one("#cl", CaptureLog)
            lg = app.query_one("#lg", Log)
            cl.write(Text.from_ansi("\n".join(lines) + "\n"))
            cl.set_plain(lines)
            for line in lines:
                lg.write_line(line)
            await pilot.pause()

            selection = Selection(Offset(1, 0), Offset(3, 0))
            app.screen.selections[cl] = selection
            app.screen.selections[lg] = selection
            cl.selection_updated(selection)
            lg.selection_updated(selection)
            await pilot.pause()

            self.assertEqual(cl.get_selection(selection),
                             lg.get_selection(selection))

            def spans(strip):
                out, pos = [], 0
                for seg in strip:
                    out.append((pos, len(seg.text),
                                str(seg.style.bgcolor if seg.style else None)))
                    pos += len(seg.text)
                return out

            cl_spans = spans(cl.render_line(0))
            lg_spans = spans(lg.render_line(0))
            # Same cut positions, and the same background on the selected run.
            self.assertEqual([(p, n) for p, n, _ in cl_spans][:3],
                             [(p, n) for p, n, _ in lg_spans][:3])
            self.assertEqual(cl_spans[1][2], lg_spans[1][2])
            # …and that background is genuinely different from the unselected run.
            self.assertNotEqual(cl_spans[1][2], cl_spans[0][2])

    async def test_render_line_applies_offsets(self):
        """No offsets => the compositor cannot map a click to a text position."""
        from textual.app import App, ComposeResult
        from rich.text import Text
        from frozenagent.capture_log import CaptureLog

        class Harness(App):
            def compose(self) -> ComposeResult:
                yield CaptureLog(highlight=False, markup=False, wrap=False, id="cl")

        app = Harness()
        async with app.run_test(size=(40, 8)) as pilot:
            cl = app.query_one("#cl", CaptureLog)
            cl.write(Text.from_ansi("alpha\nbravo\n"))
            cl.set_plain(["alpha", "bravo"])
            await pilot.pause()
            strip = cl.render_line(0)
            self.assertTrue(
                any(seg.style and "offset" in (seg.style.meta or {})
                    for seg in strip),
                "render_line produced no offset meta",
            )


# ───────────────────────── viewer ─────────────────────────────────────────


class ViewerRenderTests(_AppCase):

    async def test_ansi_and_plain_render_and_startup_focus(self):
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            from frozenagent.capture_log import CaptureLog
            log = app.query_one("#fa-log", CaptureLog)
            self.assertIs(app.focused, log, "startup focus must be the log")
            rendered = "\n".join(str(s.text) for s in log.lines)
            self.assertIn("boot: ok", rendered)
            self.assertIn("step one [a]", rendered)

            await pilot.press("r")
            await pilot.pause()
            # The RENDERED text must show a literal `[plain]`. The source is
            # escaped (`\\[plain]`); if that escape were dropped Textual would
            # eat it as an unknown tag and the indicator would vanish (t1486).
            self.assertIn("[plain]", _header_plain(app))

    async def test_startup_focus_on_the_missing_capture_path(self):
        """The early return must NOT skip the focus call (t1486)."""
        self.fx.write([_record(self.RECORD_ID, capture_ansi="", capture_txt="")])
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            from frozenagent.capture_log import CaptureLog
            log = app.query_one("#fa-log", CaptureLog)
            self.assertIs(app.focused, log)
            rendered = "\n".join(str(s.text) for s in log.lines)
            self.assertIn("capture file missing", rendered)
            await pilot.pause()

    async def test_header_escapes_brackets_in_a_window_name(self):
        """A `[x]` in a window name is an unknown tag and vanishes (t1486)."""
        self.fx.write([_record(
            self.RECORD_ID, window="agent-[weird]-1705",
            capture_ansi=str(self.fx.frozen / self.RECORD_ID / "capture.ansi"),
            capture_txt=str(self.fx.frozen / self.RECORD_ID / "capture.txt"),
        )])
        app = self.make_app()
        async with app.run_test(size=(120, 20)) as pilot:
            await pilot.pause()
            self.assertIn("agent-[weird]-1705", _header_plain(app))


class SearchTests(_AppCase):

    async def test_hit_wrap_and_not_found(self):
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            app._search_term = "step"
            app.action_search_next()
            await pilot.pause()
            self.assertEqual(app._match_line, 2)      # "  - step one [a]"
            app.action_search_next()
            await pilot.pause()
            self.assertEqual(app._match_line, 3)      # "  - step two"
            app.action_search_next()                  # wraps back to line 2
            await pilot.pause()
            self.assertEqual(app._match_line, 2)

            app._search_term = "nowhere-at-all"
            app._match_line = None
            app.action_search_next()
            await pilot.pause()
            self.assertIsNone(app._match_line)


class MarkVisibilityTests(_AppCase):
    """A mark the user cannot SEE is not a mark.

    Every other selection test asserts the copied text, which is identical
    whether or not the range is painted — so an invisible highlight passed them
    all. It shipped once: `Text(line, style="reverse").render()` yields
    `Segment(text, None)`, because a Text's BASE style is applied by the Console
    at print time and never baked into the segments. Only `stylize()` writes a
    span that survives into the Strip.
    """

    def _styles(self, log, idx):
        return [seg.style for seg in log.lines[idx]]

    async def test_a_keyboard_range_is_actually_painted(self):
        from frozenagent.capture_log import CaptureLog
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            log = app.query_one("#fa-log", CaptureLog)
            plain_before = self._styles(log, 1)
            await pilot.press("g")
            await pilot.press("shift+down")
            await pilot.pause()
            styles = self._styles(log, 1)
            self.assertTrue(
                any(st is not None and st.reverse for st in styles),
                f"the selected line carries no visible style: {styles}",
            )
            self.assertNotEqual(styles, plain_before)

    async def test_a_search_hit_is_actually_painted_and_differs_from_a_selection(self):
        from frozenagent.capture_log import CaptureLog
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            log = app.query_one("#fa-log", CaptureLog)
            app._search_term = "charlie"
            app.action_search_next()
            await pilot.pause()
            hit = app._match_line
            styles = self._styles(log, hit)
            self.assertTrue(
                any(st is not None and st.reverse and st.bold for st in styles),
                f"the search hit carries no visible style: {styles}",
            )


class StartupCursorTests(_AppCase):

    async def test_the_cursor_starts_where_the_viewport_does(self):
        """Mount scrolls to the tail; the selection cursor must follow it.

        Otherwise the first `shift+up` after opening a frozen session grows a
        range from line 0 — text the user is not looking at and, on a real
        capture, thousands of lines away.
        """
        copied: list[str] = []
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            self.app_mod.copy_to_system_clipboard = (
                lambda _a, text: copied.append(text)
            )
            await pilot.pause()
            self.assertEqual(app._cursor, len(app._lines) - 1)
            await pilot.press("shift+up")
            await pilot.press("y")
            await pilot.pause()
        self.assertEqual(copied, ["alpha bravo charlie\ndone"])


class SelectionAndCopyTests(_AppCase):

    async def test_keyboard_range_copies_exactly_those_lines(self):
        copied: list[str] = []
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            self.app_mod.copy_to_system_clipboard = (
                lambda _app, text: copied.append(text)
            )
            # `g` FIRST: the viewer mounts scrolled to the tail (it is a
            # session transcript — the newest output is what you want), so the
            # cursor starts there. A range that means "from the top" has to say
            # so, which is the whole navigation/selection contract.
            await pilot.press("g")
            await pilot.press("shift+down")
            await pilot.press("shift+down")
            await pilot.press("y")
            await pilot.pause()
        self.assertEqual(copied, ["boot: ok\nPLAN for t1705_6\n  - step one [a]"])

    async def test_native_selection_is_copied_when_no_keyboard_range(self):
        from textual.geometry import Offset
        from textual.selection import Selection
        from frozenagent.capture_log import CaptureLog

        copied: list[str] = []
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            self.app_mod.copy_to_system_clipboard = (
                lambda _app, text: copied.append(text)
            )
            log = app.query_one("#fa-log", CaptureLog)
            app.screen.selections[log] = Selection(Offset(0, 1), Offset(4, 1))
            await pilot.press("y")
            await pilot.pause()
        self.assertEqual(copied, ["PLAN"])

    async def test_nothing_selected_copies_nothing(self):
        copied: list[str] = []
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            self.app_mod.copy_to_system_clipboard = (
                lambda _app, text: copied.append(text)
            )
            await pilot.press("y")
            await pilot.pause()
        self.assertEqual(copied, [])

    async def test_markdown_modal_renders_the_selected_range(self):
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("g")
            await pilot.press("shift+down")
            await pilot.press("m")
            await pilot.pause()
            screen = app.screen
            self.assertIsInstance(screen, self.app_mod.MarkdownScreen)
            self.assertEqual(screen._text, "boot: ok\nPLAN for t1705_6")
            await pilot.press("escape")
            await pilot.pause()


# ───────────────────────── actions ────────────────────────────────────────


class LargeCaptureTests(unittest.IsolatedAsyncioTestCase):
    """Selection and search must not re-render the capture (t1705_6).

    `CaptureLog` was chosen over a `Static` precisely because it renders
    O(visible rows) at the 50000-line capture cap. Routing every mark move
    through `_render_log()` gave that back: one `shift+down` re-parsed the whole
    ANSI buffer, seconds of blocked event loop per keystroke.
    """

    LINES = 20000

    def setUp(self) -> None:
        self.fx = _StoreFixture()
        self.addCleanup(self.fx.cleanup)
        rid = "beefcafe"
        d = self.fx.frozen / rid
        d.mkdir(parents=True)
        body = "\n".join(f"line {i} alpha bravo" for i in range(self.LINES))
        (d / "capture.ansi").write_text(body + "\n")
        (d / "capture.txt").write_text(body + "\n")
        self.fx.write([_record(rid, capture_ansi=str(d / "capture.ansi"),
                               capture_txt=str(d / "capture.txt"),
                               capture_lines=self.LINES)])
        import frozenagent.frozenagent_app as app_mod
        self.app_mod = app_mod
        self._real_tmux = app_mod._TMUX
        app_mod._TMUX = FakeTmux()
        self.addCleanup(lambda: setattr(app_mod, "_TMUX", self._real_tmux))
        os.environ.pop("TMUX_PANE", None)
        self.rid = rid

    async def test_selection_and_search_do_not_re_render(self):
        import time as _time
        app = self.app_mod.FrozenAgentApp(self.rid)
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.pause()
            renders = {"n": 0}
            real_render = app._render_log

            def counting_render():
                renders["n"] += 1
                return real_render()

            app._render_log = counting_render

            t0 = _time.perf_counter()
            for _ in range(10):
                await pilot.press("shift+down")
            app._search_term = "line 19000"
            app.action_search_next()
            await pilot.pause()
            elapsed = _time.perf_counter() - t0

            self.assertEqual(renders["n"], 0,
                             "mark movement must not re-render the capture")
            # Generous: the point is orders of magnitude, not a tight budget.
            self.assertLess(elapsed, 2.0,
                            f"11 mark moves over {self.LINES} lines took "
                            f"{elapsed:.1f}s — the incremental repaint is gone")

    async def test_a_match_moving_inside_the_selection_still_repaints(self):
        """The set is unchanged; the painting must not be.

        A match line is styled differently from a plain selected line, so a
        short-circuit keyed on the marked SET alone would leave the old match
        highlighted and the new one plain.
        """
        from frozenagent.capture_log import CaptureLog
        app = self.app_mod.FrozenAgentApp(self.rid)
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.pause()
            log = app.query_one("#fa-log", CaptureLog)
            for _ in range(6):
                await pilot.press("shift+down")
            app._search_term = "line 2 "
            app.action_search_next()
            await pilot.pause()
            def style_of(idx):
                # Strip.__repr__ omits styles, so compare the styles directly.
                return [str(seg.style) for seg in log.lines[idx]]

            first = app._match_line
            first_as_match = style_of(first)
            app._search_term = "line 4 "
            app._match_line = None
            app.action_search_next()
            await pilot.pause()
            second = app._match_line
            self.assertNotEqual(first, second)
            self.assertNotEqual(
                style_of(first), first_as_match,
                "the old match must lose its match styling")
            self.assertEqual(
                style_of(second), first_as_match,
                "the new match must gain it")

    async def test_marks_are_lifted_cleanly(self):
        """A repaint must restore what it overwrote, not leave a trail."""
        from frozenagent.capture_log import CaptureLog
        app = self.app_mod.FrozenAgentApp(self.rid)
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.pause()
            log = app.query_one("#fa-log", CaptureLog)
            before = [str(log.lines[i].text) for i in range(6)]
            for _ in range(3):
                await pilot.press("shift+down")
            await pilot.press("escape")
            await pilot.pause()
            after = [str(log.lines[i].text) for i in range(6)]
            self.assertEqual(before, after)
            self.assertEqual(app._pristine, {},
                             "every saved strip must be handed back")


class NavigationCursorTests(_AppCase):

    async def test_G_then_shift_down_selects_at_the_BOTTOM(self):
        """`_cursor` must follow navigation, not only selection.

        Before this, `G` moved the viewport while the cursor stayed at 0, so the
        next `shift+down` grew a range from the opening lines and `y` copied
        text the user had navigated away from.
        """
        copied: list[str] = []
        app = self.make_app()
        async with app.run_test(size=(80, 12)) as pilot:
            self.app_mod.copy_to_system_clipboard = (
                lambda _a, text: copied.append(text)
            )
            await pilot.press("G")
            await pilot.press("shift+down")
            await pilot.press("y")
            await pilot.pause()
        self.assertEqual(copied, ["done"])          # the LAST line, not the first

    async def test_search_then_shift_down_selects_at_the_HIT(self):
        copied: list[str] = []
        app = self.make_app()
        async with app.run_test(size=(80, 12)) as pilot:
            self.app_mod.copy_to_system_clipboard = (
                lambda _a, text: copied.append(text)
            )
            app._search_term = "bravo"              # line 4: "alpha bravo charlie"
            app.action_search_next()
            await pilot.press("shift+down")
            await pilot.press("y")
            await pilot.pause()
        self.assertEqual(copied, ["alpha bravo charlie\ndone"])


class DegradedCaptureTests(_AppCase):

    async def test_an_unreadable_ANSI_falls_back_to_the_surviving_text(self):
        """The two files fail independently; text alone is still a capture."""
        ansi = self.fx.frozen / self.RECORD_ID / "capture.ansi"
        ansi.unlink()
        app = self.make_app()
        async with app.run_test(size=(140, 20)) as pilot:
            await pilot.pause()
            from frozenagent.capture_log import CaptureLog
            log = app.query_one("#fa-log", CaptureLog)
            rendered = "\n".join(str(s.text) for s in log.lines)
            self.assertIn("alpha bravo charlie", rendered)
            self.assertNotIn("capture file missing", rendered)
            self.assertIn("colour unavailable", _header_plain(app))

    async def test_the_header_names_a_missing_capture(self):
        """The body says so; the header is what a user reads first.

        And it must read as "missing", not "broken" — restore / re-pick / drop
        are all still available on the record.
        """
        for name in ("capture.ansi", "capture.txt"):
            (self.fx.frozen / self.RECORD_ID / name).unlink()
        app = self.make_app()
        async with app.run_test(size=(150, 20)) as pilot:
            await pilot.pause()
            self.assertIn("capture missing", _header_plain(app))
            self.assertTrue(app.check_action("restore", ()))
            self.assertTrue(app.check_action("drop", ()))

    async def test_the_header_flags_missing_colour_data(self):
        (self.fx.frozen / self.RECORD_ID / "capture.ansi").unlink()
        app = self.make_app()
        async with app.run_test(size=(150, 20)) as pilot:
            await pilot.pause()
            self.assertIn("colour data missing", _header_plain(app))
            self.assertNotIn("capture missing", _header_plain(app))

    async def test_the_plain_toggle_cannot_blank_a_text_only_capture(self):
        ansi = self.fx.frozen / self.RECORD_ID / "capture.ansi"
        ansi.unlink()
        app = self.make_app()
        async with app.run_test(size=(140, 20)) as pilot:
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()
            from frozenagent.capture_log import CaptureLog
            log = app.query_one("#fa-log", CaptureLog)
            rendered = "\n".join(str(s.text) for s in log.lines)
            self.assertIn("alpha bravo charlie", rendered)


class ScrollCursorTests(unittest.IsolatedAsyncioTestCase):
    """Selection must follow ORDINARY scrolling, not just our own navigations.

    `pagedown`, the mouse wheel and a scrollbar drag go straight through
    `RichLog` and never reach the app, so binding a fixed list of keys cannot
    cover them. The contract is derived from the viewport instead. Needs content
    LONGER than the viewport — a six-line fixture cannot scroll and so cannot
    see this at all.
    """

    LINES = 400

    def setUp(self) -> None:
        self.fx = _StoreFixture()
        self.addCleanup(self.fx.cleanup)
        rid = "5ca11ab1"
        d = self.fx.frozen / rid
        d.mkdir(parents=True)
        body = "\n".join(f"row {i:04d}" for i in range(self.LINES))
        (d / "capture.ansi").write_text(body + "\n")
        (d / "capture.txt").write_text(body + "\n")
        self.fx.write([_record(rid, capture_ansi=str(d / "capture.ansi"),
                               capture_txt=str(d / "capture.txt"),
                               capture_lines=self.LINES)])
        import frozenagent.frozenagent_app as app_mod
        self.app_mod = app_mod
        self._real_tmux = app_mod._TMUX
        app_mod._TMUX = FakeTmux()
        self.addCleanup(lambda: setattr(app_mod, "_TMUX", self._real_tmux))
        os.environ.pop("TMUX_PANE", None)
        self.rid = rid

    async def test_selection_follows_a_plain_scroll(self):
        from frozenagent.capture_log import CaptureLog
        copied: list[str] = []
        app = self.app_mod.FrozenAgentApp(self.rid)
        async with app.run_test(size=(60, 12)) as pilot:
            self.app_mod.copy_to_system_clipboard = (
                lambda _a, text: copied.append(text)
            )
            await pilot.press("g")                 # top
            await pilot.pause()
            log = app.query_one("#fa-log", CaptureLog)
            # Scroll the WIDGET directly — the path no key binding of ours sees.
            log.scroll_to(y=100, animate=False)
            await pilot.pause()
            self.assertGreater(int(log.scroll_offset.y), 50,
                               "fixture must actually scroll")
            await pilot.press("shift+down")
            await pilot.press("y")
            await pilot.pause()
        self.assertTrue(copied, "nothing was copied")
        first = copied[0].splitlines()[0]
        self.assertNotEqual(first, "row 0000",
                            "the range must not start at the top after a scroll")
        self.assertIn("row 01", first)


class TransitionalMountTests(_AppCase):
    """A replacement viewer routinely mounts on a record that is still moving.

    `agent_restore._rollback` respawns the stand-in BEFORE it calls
    `standin-respawned`, so the new viewer arrives while the record is
    `aborting`. It dispatched nothing itself, so without a settle watch its
    header would show `aborting` forever and never surface the failure that
    lands milliseconds later.
    """

    async def test_the_header_follows_a_settlement_it_did_not_start(self):
        ansi = str(self.fx.frozen / self.RECORD_ID / "capture.ansi")
        txt = str(self.fx.frozen / self.RECORD_ID / "capture.txt")
        self.fx.write([_record(
            self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
            state="aborting", restore_attempts=1, op_nonce="bbbbbbbb",
        )])
        app = self.make_app()
        async with app.run_test(size=(150, 20)) as pilot:
            await pilot.pause()
            self.assertIn("aborting", _header_plain(app))
            # Recovery completes, exactly as `standin_respawned` leaves it:
            # back to `frozen`, lease CLEARED, error retained.
            self.fx.write([_record(
                self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
                state="frozen", restore_attempts=1, op_nonce="",
                last_error="bbbbbbbb:agent_exited",
            )])
            await pilot.pause(self.app_mod.POLL_INTERVAL * 1.5)
            header = _header_plain(app)
            self.assertNotIn("aborting", header)
            self.assertIn("last restore failed: agent_exited", header)


class PersistedFailureTests(_AppCase):
    """The failure the replacement viewer shows must be one the engine WRITES."""

    def test_restore_abort_persists_the_reason_for_every_outcome(self):
        """Driven through the real store verb, not a hand-inserted value.

        `agent_exited` — the ordinary "the resumed agent died immediately" case
        — was never persisted: only the hook's `session_mismatch` ever reached
        `last_error`. So the persisted-failure note was dead on the main path,
        and a test that inserted the value by hand could not tell.
        """
        import agent_sessions as A

        for reason in ("agent_exited", "respawn", "launch_refused"):
            with self.subTest(reason=reason):
                sf = A.SessionsFile()
                sf, line = A.upsert(sf, root="/tmp/proj", window="w",
                                    pane="%1", pane_pid=1,
                                    pane_alive=lambda pid: True)
                rid = line.split(":")[1].split("|")[0]
                sf, fl = A.freeze_begin(sf, rid, capture_ansi="/a",
                                        capture_txt="/b", lines=1,
                                        owner_pid=os.getpid())
                sf, _ = A.freeze_commit(sf, rid, nonce=fl.split("|")[1],
                                        pane="%1", pane_pid=1)
                sf, rl = A.restore_begin(sf, rid, mode="resume",
                                         owner_pid=os.getpid())
                nonce = rl.split("|")[1]
                sf, _ = A.restore_abort(sf, rid, nonce=nonce, error=reason)
                self.assertEqual(sf.by_id(rid).last_error, f"{nonce}:{reason}")
                # …and it SURVIVES the recovery that clears the lease.
                sf, _ = A.standin_respawned(sf, rid, nonce=nonce, pane="%1",
                                            pane_pid=2)
                rec = sf.by_id(rid)
                self.assertEqual(rec.op_nonce, "")
                self.assertEqual(rec.last_error, f"{nonce}:{reason}")
                self.assertEqual(
                    self.app_mod.FrozenAgentApp._persisted_note(rec),
                    f"last restore failed: {reason} — capture kept",
                )


class ActionArgvTests(_AppCase):

    async def test_restore_repick_and_drop_argv(self):
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("R")
            await pilot.pause()
        argvs = self.tmux.run_shell_argvs()
        self.assertEqual(len(argvs), 1)
        self.assertIn(f"aitask_frozen.sh restore {self.RECORD_ID}", argvs[0][2])

    async def test_repick_is_refused_without_a_task_id(self):
        self.fx.write([_record(
            self.RECORD_ID, task_id="",
            capture_ansi=str(self.fx.frozen / self.RECORD_ID / "capture.ansi"),
            capture_txt=str(self.fx.frozen / self.RECORD_ID / "capture.txt"),
        )])
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("p")
            await pilot.pause()
        self.assertEqual(self.tmux.run_shell_argvs(), [],
                         "re-pick must issue no coordinator call without a task id")

    async def test_drop_argv_after_confirmation(self):
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("k")
            await pilot.pause()
            self.assertIsInstance(app.screen, self.app_mod.ConfirmDialog)
            await pilot.press("y")
            await pilot.pause()
        argvs = self.tmux.run_shell_argvs()
        self.assertEqual(len(argvs), 1)
        self.assertIn(f"aitask_frozen.sh drop {self.RECORD_ID}", argvs[0][2])

    async def test_cancelling_the_confirm_dispatches_nothing(self):
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("k")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        self.assertEqual(self.tmux.run_shell_argvs(), [])


class RestoreOutcomeTests(_AppCase):
    """The correlation rules a detached coordinator forces on the viewer."""

    async def test_a_stale_last_error_is_not_reported_as_this_restore_failing(self):
        """The pin for the pre-begin gate.

        The record carries an error from an EARLIER attempt. `restore-begin`
        would have cleared it, but the coordinator has not run yet — so a poll
        firing now must say "dispatching…", never "restore failed".
        """
        ansi = str(self.fx.frozen / self.RECORD_ID / "capture.ansi")
        txt = str(self.fx.frozen / self.RECORD_ID / "capture.txt")
        # The realistic shape of a record whose PREVIOUS restore failed: back at
        # `frozen`, lease cleared by `standin-respawned`, but `last_error` still
        # naming that older attempt's nonce.
        self.fx.write([_record(
            self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
            restore_attempts=1, op_nonce="",
            last_error="aaaaaaaa:session_mismatch",
        )])
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("R")
            await pilot.pause()
            self.assertEqual(app._header_note, "dispatching…")
            # Tick the poll with the store UNCHANGED — the coordinator has not
            # reached `restore-begin`, so nothing may be concluded.
            app._poll_restore(self.RECORD_ID, (1, ""), {"t": 0.0})
            await pilot.pause()
            self.assertEqual(app._header_note, "dispatching…")
            self.assertIn(self.RECORD_ID, app._pending)

            # Now the coordinator starts: attempts bumps, a NEW nonce, and the
            # store has cleared the old error. Only now may an error count.
            self.fx.write([_record(
                self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
                state="frozen", restore_attempts=2, op_nonce="bbbbbbbb",
                last_error="bbbbbbbb:agent_exited",
            )])
            app._poll_restore(self.RECORD_ID, (1, ""), {"t": 1.0})
            await pilot.pause()
            self.assertIn("agent_exited", app._header_note)
            self.assertIn("capture kept", app._header_note)
            self.assertNotIn(self.RECORD_ID, app._pending)

    async def test_a_failure_survives_the_REAL_recovery_transitions(self):
        """Driven through the store's own verbs, not a hand-built record.

        The recovery a failed restore actually performs is
        `restore-abort` -> `standin-respawned`, and `standin_respawned` CLEARS
        the lease while PRESERVING `last_error`. A poll that re-read `op_nonce`
        and prefix-matched the error against it therefore matched nothing once
        recovery had run, fell through, and reported the failure as a timeout.
        A fixture that keeps a nonce cannot see that — real recovery clears it.
        """
        import agent_sessions as A

        ansi = str(self.fx.frozen / self.RECORD_ID / "capture.ansi")
        txt = str(self.fx.frozen / self.RECORD_ID / "capture.txt")

        # Build the post-recovery record by running the real transitions.
        sf = A.SessionsFile()
        sf, line = A.upsert(sf, root="/tmp/proj", window="agent-pick-1705",
                            pane="%9", pane_pid=4242,
                            pane_alive=lambda pid: True)
        rid = line.split(":")[1].split("|")[0]
        rec = sf.by_id(rid)
        rec.capture_ansi, rec.capture_txt = ansi, txt
        sf, fline = A.freeze_begin(sf, rid, capture_ansi=ansi, capture_txt=txt,
                                   lines=6, owner_pid=os.getpid())
        sf, _ = A.freeze_commit(sf, rid, nonce=fline.split("|")[1],
                                pane="%9", pane_pid=4242)
        sf, rline = A.restore_begin(sf, rid, mode="resume",
                                    owner_pid=os.getpid())
        nonce = rline.split("|")[1]
        sf.by_id(rid).last_error = f"{nonce}:session_mismatch"
        sf, _ = A.restore_abort(sf, rid, nonce=nonce)
        sf, _ = A.standin_respawned(sf, rid, nonce=nonce, pane="%9",
                                    pane_pid=8888)

        settled = sf.by_id(rid)
        self.assertEqual(settled.state, "frozen")
        self.assertEqual(settled.op_nonce, "",
                         "real recovery clears the lease — that is the point")
        self.assertTrue(settled.last_error, "…while keeping the error")

        self.fx.write([{k: v for k, v in vars(settled).items()}])
        app = self.app_mod.FrozenAgentApp(rid)
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("R")
            await pilot.pause()
            app._poll_restore(rid, (0, ""), {"t": 1.0})
            await pilot.pause()
            self.assertIn("session_mismatch", app._header_note)
            self.assertIn("capture kept", app._header_note)

    async def test_a_replacement_viewer_shows_the_persisted_failure(self):
        """The dispatching viewer is gone by the time the outcome lands.

        A failed restore respawns the stand-in, so a NEW viewer mounts on a
        `frozen` record carrying `last_error`. Without surfacing it the user
        sees a plain `frozen` header and no sign their restore was attempted.
        """
        ansi = str(self.fx.frozen / self.RECORD_ID / "capture.ansi")
        txt = str(self.fx.frozen / self.RECORD_ID / "capture.txt")
        self.fx.write([_record(
            self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
            state="frozen", restore_attempts=1, op_nonce="",
            last_error="aaaaaaaa:agent_exited",
        )])
        app = self.make_app()
        async with app.run_test(size=(140, 20)) as pilot:
            await pilot.pause()
            self.assertIn("last restore failed: agent_exited",
                          _header_plain(app))

    async def test_a_timeout_never_reads_as_success(self):
        """Still transitional at the grace = unknown, not restored."""
        ansi = str(self.fx.frozen / self.RECORD_ID / "capture.ansi")
        txt = str(self.fx.frozen / self.RECORD_ID / "capture.txt")
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("R")
            await pilot.pause()
            self.fx.write([_record(
                self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
                state="restoring", restore_attempts=1, op_nonce="bbbbbbbb",
            )])
            app._poll_restore(self.RECORD_ID, (0, ""),
                              {"t": self.app_mod.DISPATCH_GRACE + 31.0})
            await pilot.pause()
            self.assertIn("reconcile", app._header_note)
            self.assertNotIn("restored", app._header_note)

    async def test_liveness_ack_reads_as_success(self):
        """A codex record can ONLY ever reach `liveness` (amendment B4)."""
        ansi = str(self.fx.frozen / self.RECORD_ID / "capture.ansi")
        txt = str(self.fx.frozen / self.RECORD_ID / "capture.txt")
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("R")
            await pilot.pause()
            self.fx.write([_record(
                self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
                state="live", restore_attempts=1, op_nonce="",
                ack="liveness",
            )])
            app._poll_restore(self.RECORD_ID, (0, ""), {"t": 1.0})
            await pilot.pause()
            self.assertIn("restored, unverified", app._header_note)
            self.assertNotIn("fail", app._header_note.lower())

    async def test_dispatch_grace_expiry(self):
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("R")
            await pilot.pause()
            app._poll_restore(self.RECORD_ID, (0, ""),
                              {"t": self.app_mod.DISPATCH_GRACE})
            await pilot.pause()
            self.assertIn("did not start", app._header_note)
            self.assertNotIn(self.RECORD_ID, app._pending)


class DropOutcomeTests(_AppCase):

    async def test_drop_completes_on_record_disappearance(self):
        """`drop` never reaches `restoring`/`live`; it needs its own terminal."""
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("k")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            self.assertEqual(app._header_note, "dropping…")
            self.fx.write([])                        # the coordinator removed it
            app._poll_drop(self.RECORD_ID, {"t": 1.0})
            await pilot.pause()
            self.assertIn("dropped", app._header_note)
            self.assertNotIn(self.RECORD_ID, app._pending)
            self.assertNotIn(self.RECORD_ID, app._op_timers)

    async def test_drop_grace_expiry_reports_failure(self):
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("k")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            app._poll_drop(self.RECORD_ID, {"t": self.app_mod.DROP_GRACE})
            await pilot.pause()
            self.assertIn("drop failed", app._header_note)


class SingleFlightTests(_AppCase):
    """`drop` is legal from ANY state and takes no nonce, so it can race."""

    async def test_drop_is_refused_while_a_restore_is_pending(self):
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("R")
            await pilot.pause()
            self.assertEqual(len(self.tmux.run_shell_argvs()), 1)
            self.assertFalse(app.check_action("drop", ()))
            await pilot.press("k")
            await pilot.pause()
            # No confirm dialog, and no second coordinator dispatched.
            self.assertNotIsInstance(app.screen, self.app_mod.ConfirmDialog)
            self.assertEqual(len(self.tmux.run_shell_argvs()), 1)

    async def test_a_repeated_restore_dispatches_once(self):
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("R")
            await pilot.press("R")
            await pilot.press("R")
            await pilot.pause()
            self.assertEqual(len(self.tmux.run_shell_argvs()), 1)

    async def test_bindings_come_back_after_a_terminal_outcome(self):
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("R")
            await pilot.pause()
            self.assertFalse(app.check_action("drop", ()))
            app._finish(self.RECORD_ID, "restored")
            await pilot.pause()
            self.assertTrue(app.check_action("drop", ()))


# ───────────────────────── list mode ──────────────────────────────────────


class ListModeTests(_AppCase):

    def setUp(self) -> None:
        super().setUp()
        ansi, txt = self.fx.capture("aaaaaaaa")
        self.fx.write([
            _record(self.RECORD_ID,
                    capture_ansi=str(self.fx.frozen / self.RECORD_ID / "capture.ansi"),
                    capture_txt=str(self.fx.frozen / self.RECORD_ID / "capture.txt")),
            _record("aaaaaaaa", window="agent-qa-99", task_id="99",
                    pane_id="%11", capture_ansi=ansi, capture_txt=txt),
            _record("bbbbbbbb", state="live", pane_id="%12"),
        ])

    async def test_only_frozen_records_are_listed(self):
        from textual.widgets import DataTable
        app = self.make_app(None)
        async with app.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            table = app.query_one("#fa-list", DataTable)
            self.assertEqual(table.row_count, 2)
            self.assertEqual({r.id for r in app._rows},
                             {self.RECORD_ID, "aaaaaaaa"})

    async def test_enter_opens_the_highlighted_record_in_place(self):
        from frozenagent.capture_log import CaptureLog
        app = self.make_app(None)
        async with app.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertFalse(app._list_mode)
            self.assertIn(app._record_id, {self.RECORD_ID, "aaaaaaaa"})
            log = app.query_one("#fa-log", CaptureLog)
            self.assertFalse(log.has_class("hidden"))
            self.assertIs(app.focused, log)

    async def test_opening_a_row_that_went_transitional_still_settles(self):
        """The list-entry path needs the settle watch too.

        A row is listed while `frozen`, then another coordinator moves it — the
        viewer opens onto `aborting` and, without the watch, never learns how it
        ended.
        """
        ansi = str(self.fx.frozen / self.RECORD_ID / "capture.ansi")
        txt = str(self.fx.frozen / self.RECORD_ID / "capture.txt")
        app = self.make_app(None)
        async with app.run_test(size=(150, 20)) as pilot:
            await pilot.pause()
            # It moved between the listing and the keypress.
            self.fx.write([_record(
                self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
                state="aborting", restore_attempts=1, op_nonce="bbbbbbbb",
            )])
            app._open_selected(self.RECORD_ID)
            await pilot.pause()
            self.assertIn("aborting", _header_plain(app))
            self.fx.write([_record(
                self.RECORD_ID, capture_ansi=ansi, capture_txt=txt,
                state="frozen", restore_attempts=1, op_nonce="",
                last_error="bbbbbbbb:agent_exited",
            )])
            await pilot.pause(self.app_mod.POLL_INTERVAL * 1.5)
            header = _header_plain(app)
            self.assertNotIn("aborting", header)
            self.assertIn("last restore failed: agent_exited", header)
        # …and opening from a list still stamps nothing.
        self.assertEqual(
            [c for c in self.tmux.calls if c and c[0] == "set-option"], []
        )

    async def test_list_mode_stamps_nothing(self):
        """A list is not a stand-in — stamping would mark an unrelated pane."""
        os.environ["TMUX_PANE"] = "%77"
        self.addCleanup(lambda: os.environ.pop("TMUX_PANE", None))
        app = self.make_app(None)
        async with app.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
        self.assertEqual(
            [c for c in self.tmux.calls if c and c[0] == "set-option"], []
        )


class StampTests(_AppCase):

    async def test_the_viewer_stamps_its_own_pane_after_mount(self):
        os.environ["TMUX_PANE"] = "%42"
        self.addCleanup(lambda: os.environ.pop("TMUX_PANE", None))
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
        from monitor.monitor_core import STANDIN_READY_OPTION
        self.assertIn(
            ["set-option", "-p", "-t", "%42", STANDIN_READY_OPTION,
             self.RECORD_ID],
            self.tmux.calls,
        )

    async def test_no_stamp_outside_tmux(self):
        """`TMUX_PANE` unset => there is no pane of ours to mark."""
        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
        self.assertEqual(
            [c for c in self.tmux.calls if c and c[0] == "set-option"], []
        )


class CliTests(unittest.TestCase):

    def test_unknown_record_exits_2(self):
        fx = _StoreFixture()
        self.addCleanup(fx.cleanup)
        fx.write([])
        import frozenagent.frozenagent_app as app_mod
        self.assertEqual(app_mod.main(["--record", "7f3a2c1d"]), 2)

    def test_malformed_record_id_exits_2(self):
        fx = _StoreFixture()
        self.addCleanup(fx.cleanup)
        fx.write([])
        import frozenagent.frozenagent_app as app_mod
        self.assertEqual(app_mod.main(["--record", "../../etc"]), 2)

    def test_bad_usage_exits_2(self):
        import frozenagent.frozenagent_app as app_mod
        self.assertEqual(app_mod.main(["--nope"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
