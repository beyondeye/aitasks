"""Minimonitor row-width budget (t1351).

The pane's column arithmetic lives in one place — the budget block near the top
of ``.aitask-scripts/monitor/minimonitor_app.py`` — and this module pins it from
four directions:

* **The status reserve is tight.** ``PANE_STATUS_MAX_CELLS`` is asserted EQUAL to
  the widest ``format_pane_status`` output over a boundary sweep, so the name
  budget is neither unsafe (too small a reserve) nor wasteful (too large).
* **Display names mirror the classifier.** Agent rows drop the agent prefix that
  made them agents; ``agent_display_name`` and ``classify_pane`` share one
  matcher, and an agreement table runs both against a real ``TmuxMonitor``.
* **Every glyph combination fits.** A render-string matrix over mark x shadow
  (absent / ``◆`` / ``◆!``) x compare mode x override x status x name x width.
* **The composited screen agrees.** The AC's check: the REAL ``MiniMonitorApp``
  (real compose, real CSS, only its tmux-facing collaborators stubbed) renders
  the widest combination — ``◆!`` forced, because production minimonitor never
  passes ``has_concerns`` — at width 40, both with the list's scrollbar hidden
  and visible. A widget's render string cannot show that the compositor wrapped
  or clipped a row; the screen can.

Run: python3 tests/test_minimonitor_row_budget.py
"""

from __future__ import annotations

import asyncio
import itertools
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Scrub the ambient tmux env so nothing here can touch the pane the suite runs
# in (t1240), and so the real `on_mount` takes its "Not inside tmux" return.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.cells import cell_len  # noqa: E402
from rich.text import Text  # noqa: E402
from textual.content import Content  # noqa: E402
from textual.errors import NoWidget  # noqa: E402

import agent_marks  # noqa: E402
import workflow_phase  # noqa: E402
# The real app with only its tmux-facing collaborators stubbed (t1653) — the
# same base the live bottom-pin harness builds on.
import test_minimonitor_scroll_preservation as sp  # noqa: E402
from monitor import minimonitor_app as mm  # noqa: E402
from monitor import monitor_shared as ms  # noqa: E402
# Module-qualified rather than `from … import`, so the composited tests still run
# (and fail for the real reason) against a tree where the new symbols are absent.
from monitor import monitor_core as mc  # noqa: E402
from monitor.monitor_core import PaneCategory, TaskInfo, TmuxMonitor  # noqa: E402

_TARGET_WIDTH = 40
_PREFIXES = ["agent-"]

# Names that stress every edge of the name budget. The CJK runs are double
# width: 1 code point, 2 cells — the case `len()`-based caps got wrong.
_NAMES = [
    "agent-pick-1351_12",              # the common launch name; must survive whole
    "agent-" + "x" * 60,               # long ASCII
    "agent-" + "漢" * 30,              # all double-width
    "agent-a" + "漢" * 20,             # double-width straddling the clip point
    "agent-" + "[/]x[dim]" * 5,        # markup-looking user input
    "agent-",                          # prefix only: nothing left to strip to
]

_REAL_SHADOW_GLYPH = ms.format_shadow_glyph


def _shadow_with_concerns(shadow_snap, **_kw):
    """`◆!` — the widest shadow glyph. Production minimonitor never asks for
    it (only `ait monitor` passes `has_concerns`), so the worst case has to be
    forced to be measured at all."""
    return _REAL_SHADOW_GLYPH(shadow_snap, has_concerns=True)


def _plain(markup: str) -> str:
    return Text.from_markup(markup).plain


def _snap(pane_id="%1", *, window_name="agent-pick-1351_12", window_index="1",
          status="prompt", seconds=999.0, parked=False, frozen=False):
    pane = SimpleNamespace(
        pane_id=pane_id, session_name="s1", window_index=window_index,
        pane_index="0", window_name=window_name, category=PaneCategory.AGENT,
        current_command="claude",
    )
    return SimpleNamespace(
        pane=pane, content="", is_idle=status in ("idle", "done"),
        idle_seconds=seconds, awaiting_input=status == "prompt",
        awaiting_input_kind="", agent_key="", scoped=False,
        parked=parked, frozen=frozen, frozen_record_id="",
    )


def _row_app(*, width=_TARGET_WIDTH, mark=agent_marks.KIND_NONE,
             compare="stripped", override=False, shadow=True, completed=()):
    """`__new__` stub: enough for `_agent_card_text`'s line 1 (no task, so no
    title / gate rows)."""
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._target_width = width
    app._completed_pane_ids = frozenset(completed)
    shadow_snap = SimpleNamespace(awaiting_input=False, is_idle=True)
    app._monitor = SimpleNamespace(
        get_compare_mode=lambda pid: compare,
        is_compare_mode_overridden=lambda pid: override,
        get_shadow_snapshot=lambda pid: shadow_snap if shadow else None,
        agent_prefixes=list(_PREFIXES),
    )
    app._task_cache = SimpleNamespace(
        get_task_id_for_pane=lambda pane: None,
        get_task_info=lambda task_id, session=None: None,
    )
    app._gate_cache = SimpleNamespace(summary_for=lambda info: None,
                                      clear=lambda: None)
    app._init_agent_marks()
    app._mark_kind = lambda snap: mark
    return app


def _line1(app, snap) -> str:
    return _plain(app._agent_card_text(snap).split("\n")[0])


class StatusBoundTests(unittest.TestCase):
    _SECONDS = (0, 9, 10, 99, 100, 999, 1000, 14400, 14459, 14460, 10**9)

    def test_reserve_equals_the_widest_status(self):
        widths = []
        for seconds in self._SECONDS:
            for status, completed in (("prompt", False), ("done", True),
                                      ("idle", False), ("active", False)):
                snap = _snap(status=status, seconds=float(seconds))
                widths.append(cell_len(_plain(
                    ms.format_pane_status(snap, completed))))
            # The candidate badge of an unassociated question (t2281).
            maybe = _snap(status="prompt", seconds=float(seconds))
            maybe.awaiting_input_kind = ms.QUESTION_UNASSOCIATED_KIND
            widths.append(cell_len(_plain(ms.format_pane_status(maybe))))
        self.assertEqual(max(widths), ms.PANE_STATUS_MAX_CELLS)


class PrefixTests(unittest.TestCase):
    def test_strips_the_matched_prefix(self):
        self.assertEqual(mc.agent_display_name("agent-pick-42", _PREFIXES), "pick-42")

    def test_first_match_in_list_order_wins(self):
        # The classifier's own rule: first prefix in list order, not the longest.
        prefixes = ["agent-", "agent-pick-"]
        self.assertEqual(mc.match_agent_prefix("agent-pick-42", prefixes), "agent-")
        self.assertEqual(mc.agent_display_name("agent-pick-42", prefixes), "pick-42")
        self.assertEqual(
            mc.agent_display_name("agent-pick-42", list(reversed(prefixes))), "42")

    def test_custom_prefixes(self):
        prefixes = ["agent-", "claude-"]
        self.assertEqual(mc.agent_display_name("claude-t7", prefixes), "t7")

    def test_unchanged_when_nothing_would_remain_or_nothing_matched(self):
        self.assertEqual(mc.agent_display_name("agent-", _PREFIXES), "agent-")
        self.assertEqual(mc.agent_display_name("zsh", _PREFIXES), "zsh")
        self.assertEqual(mc.agent_display_name("agent-x", [""]), "agent-x")
        self.assertEqual(mc.agent_display_name("agent-x", []), "agent-x")

    def test_display_strip_agrees_with_classification(self):
        """`classify_pane` says AGENT exactly when a prefix matches — the two
        share one matcher, so a display name can never be stripped by a rule
        the classifier did not use."""
        for prefixes in (["agent-"], ["agent-", "claude-"], ["claude-"]):
            monitor = TmuxMonitor(session="t1351", agent_prefixes=prefixes)
            for name in ("agent-pick-1", "claude-x", "agent-", "zsh",
                         "xagent-1", "board"):
                with self.subTest(prefixes=prefixes, name=name):
                    is_agent = monitor.classify_pane(name) is PaneCategory.AGENT
                    self.assertEqual(
                        is_agent, mc.match_agent_prefix(name, prefixes) is not None)


class AgentRowMatrixTests(unittest.TestCase):
    """Render-string level: every combination stays inside the row budget."""

    _STATUSES = (("active", False), ("idle", False), ("prompt", False),
                 ("done", True))

    def _check_name(self, plain: str, name: str, room: int):
        display = mc.agent_display_name(name, _PREFIXES)
        if cell_len(display) <= room:
            self.assertIn(display, plain)
        else:
            # Clipped: the tail gave way behind a single ellipsis.
            self.assertIn("…", plain)
        if name != "agent-":
            self.assertNotIn("agent-", plain)

    def test_live_rows_fit_every_combination(self):
        product = itertools.product(
            (agent_marks.KIND_NONE, agent_marks.KIND_PRIORITY),
            ("absent", "diamond", "concern"),
            ("stripped", "raw"),
            (False, True),
            self._STATUSES,
            _NAMES,
            (40, 32, 60),
        )
        for mark, shadow, compare, override, (status, done), name, width in product:
            app = _row_app(width=width, mark=mark, compare=compare,
                           override=override, shadow=shadow != "absent",
                           completed={"%1"} if done else ())
            snap = _snap(window_name=name, status=status)
            patcher = (mock.patch.object(mm, "format_shadow_glyph",
                                         _shadow_with_concerns)
                       if shadow == "concern" else mock.patch.object(
                           mm, "format_shadow_glyph", mm.format_shadow_glyph))
            with self.subTest(mark=mark, shadow=shadow, compare=compare,
                              override=override, status=status, name=name,
                              width=width), patcher:
                plain = _line1(app, snap)
                budget = mm._row_budget(width)
                self.assertLessEqual(cell_len(plain), budget,
                                     f"{cell_len(plain)} > {budget}: {plain!r}")
                if shadow == "concern":
                    self.assertIn("◆!", plain)
                prefix_cells = {"absent": 6, "diamond": 8, "concern": 9}[shadow]
                room = budget - prefix_cells - 2 - ms.PANE_STATUS_MAX_CELLS
                self._check_name(plain, name, room)

    def test_parked_and_frozen_rows_fit(self):
        for name, width, kind in itertools.product(
                _NAMES, (40, 32, 60), ("parked", "frozen")):
            app = _row_app(width=width)
            snap = _snap(window_name=name, parked=kind == "parked",
                         frozen=kind == "frozen")
            with self.subTest(name=name, width=width, kind=kind):
                plain = _line1(app, snap)
                budget = mm._row_budget(width)
                self.assertLessEqual(cell_len(plain), budget,
                                     f"{cell_len(plain)} > {budget}: {plain!r}")
                self.assertTrue(plain.endswith(kind), plain)
                prefix_cells = 2 if kind == "parked" else 3
                self._check_name(plain, name, budget - prefix_cells - 2 - 6)

    def test_double_width_title_fits_the_detail_budget(self):
        app = _row_app()
        app._task_cache = SimpleNamespace(
            get_task_id_for_pane=lambda pane: "1351",
            get_task_info=lambda task_id, session=None: _task_info("漢" * 40),
        )
        app._gate_cache = SimpleNamespace(
            summary_for=lambda info: "",
            phase_for=lambda info, **kw: workflow_phase.PhaseSignal(),
            clear=lambda: None)
        title = _plain(app._agent_card_text(_snap()).split("\n")[1])
        self.assertLessEqual(cell_len(title),
                             2 + mm._detail_budget(_TARGET_WIDTH), repr(title))
        self.assertTrue(title.endswith("…"), repr(title))


    def test_frozen_title_fits_the_detail_budget(self):
        """t2042: a frozen row's title row is held to the same budget as the
        live one, and no gate/phase row follows it."""
        app = _row_app()
        app._task_cache = SimpleNamespace(
            get_task_id_for_pane=lambda pane: "1351",
            get_task_info=lambda task_id, session=None: _task_info("漢" * 40),
        )
        app._gate_cache = SimpleNamespace(
            summary_for=lambda info: "1/1 pass",
            phase_for=lambda info, **kw: workflow_phase.PhaseSignal(
                phase="IMPLEMENT"),
            clear=lambda: None)
        rows = app._agent_card_text(_snap(frozen=True)).split("\n")
        self.assertEqual(len(rows), 2, rows)
        title = _plain(rows[1])
        self.assertLessEqual(cell_len(title),
                             2 + mm._detail_budget(_TARGET_WIDTH), repr(title))
        self.assertTrue(title.endswith("…"), repr(title))


class NameFloorTests(unittest.TestCase):
    """The budget the NEXT always-on glyph must fit inside."""

    def test_widest_live_row_leaves_the_floor(self):
        app = _row_app(mark=agent_marks.KIND_PRIORITY, override=True)
        with mock.patch.object(mm, "format_shadow_glyph", _shadow_with_concerns):
            plain = _line1(app, _snap(window_name="agent-" + "x" * 60))
        self.assertTrue(plain.endswith("PROMPT 999s"), plain)
        # Measure the rendered name ITSELF — the one `x…` run on the row. Row
        # width minus an assumed prefix would not do: clipping keeps the row
        # full, so a wider prefix would be miscounted as name cells.
        names = re.findall(r"x+…", plain)
        self.assertEqual(len(names), 1, plain)
        self.assertGreaterEqual(cell_len(names[0]), mm._MIN_NAME_CELLS, plain)

    def test_common_launch_name_survives_the_worst_case(self):
        app = _row_app(mark=agent_marks.KIND_PRIORITY, override=True)
        with mock.patch.object(mm, "format_shadow_glyph", _shadow_with_concerns):
            plain = _line1(app, _snap())
        self.assertEqual(plain, "★ ● ◆! ≈ pick-1351_12  PROMPT 999s")


class FrozenBadgeNameFloorTests(unittest.TestCase):
    """t2354: a frozen row keeps the name floor in EVERY sitrep badge state.

    Looping over the badge table itself (plus ``None``, no verdict yet) is the
    point: a badge state added later that is too wide fails here instead of
    silently cutting the task id off the name's tail.
    """

    _STATES = (None, *ms.FROZEN_SITREP_BADGES)
    _MARKS = (agent_marks.KIND_NONE, agent_marks.KIND_PRIORITY)

    @staticmethod
    def _app(state, mark=agent_marks.KIND_NONE):
        app = _row_app(mark=mark)
        app._frozen_sitrep_state = lambda snap: state
        return app

    @staticmethod
    def _shown(state) -> str:
        """What follows the name: `frozen`, or the badge in its place."""
        if state is None:
            return "frozen"
        return "".join(text for text, _style in ms.FROZEN_SITREP_BADGES[state])

    def test_long_name_keeps_the_floor_in_every_state(self):
        for state, mark in itertools.product(self._STATES, self._MARKS):
            with self.subTest(state=state, mark=mark):
                plain = _line1(self._app(state, mark),
                               _snap(window_name="agent-" + "x" * 60,
                                     frozen=True))
                budget = mm._row_budget(_TARGET_WIDTH)
                self.assertLessEqual(cell_len(plain), budget,
                                     f"{cell_len(plain)} > {budget}: {plain!r}")
                names = re.findall(r"x+…", plain)
                self.assertEqual(len(names), 1, plain)
                self.assertGreaterEqual(cell_len(names[0]), mm._MIN_NAME_CELLS,
                                        plain)
                self.assertTrue(plain.endswith("  " + self._shown(state)), plain)
                if state is not None:
                    self.assertNotIn("frozen", plain)

    def test_the_frozen_prefix_survives_every_state(self):
        """With a badge shown, the `F` is the row's only frozen marker."""
        for state, mark in itertools.product(self._STATES, self._MARKS):
            with self.subTest(state=state, mark=mark):
                plain = _line1(self._app(state, mark), _snap(frozen=True))
                prefix = _plain(ms.format_frozen_prefix(mark)) + " "
                self.assertTrue(plain.startswith(prefix), (prefix, plain))

    def test_launch_names_survive_whole_in_every_state(self):
        for state, name in itertools.product(
                self._STATES, ("agent-pick-2261_2", "agent-pick-1351_12")):
            with self.subTest(state=state, name=name):
                plain = _line1(self._app(state),
                               _snap(window_name=name, frozen=True))
                self.assertIn(f" {name.removeprefix('agent-')}  ", plain)
                self.assertNotIn("…", plain)


class DockedFrozenLineBudgetTests(unittest.TestCase):
    """t2359: the docked own-agent card's frozen line fits its ONE row.

    ``_OWN_PANEL_MAX_ROWS`` counts one row for this line (it replaces the phase
    line), so a wrapped continuation is hidden by the panel cap. Looped over
    the badge table itself (plus ``None``) for the reason
    ``FrozenBadgeNameFloorTests`` gives. The budget is the CONFIGURED width's
    (``_own_phase_budget``); a pane narrower than its configured width is
    t2007's.
    """

    _STATES = (None, *ms.FROZEN_SITREP_BADGES)
    #: The widest canonical stamp (`agent_sessions._TS_FMT`) — every field at
    #: its two-digit maximum.
    _STAMP = "2026-12-31T23:59:59Z"
    _SHORT = "12-31 23:59Z"

    @staticmethod
    def _line(width, stamp, state) -> str:
        """The frozen detail line's text, without its two-cell indent."""
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._target_width = width
        app._own_identity_text = Content("agent-pick-2359")
        plain = app._own_card_text(None, "", stamp, state).plain
        lines = plain.split("\n")
        # Exactly one detail line: the identity line plus this one.
        assert len(lines) == 2, lines
        assert lines[1].startswith("  "), lines[1]
        return lines[1][2:]

    @staticmethod
    def _badge(state) -> str:
        return "".join(text for text, _style in ms.FROZEN_SITREP_BADGES[state])

    def test_every_state_fits_whole_at_the_default_width(self):
        budget = mm._own_phase_budget(_TARGET_WIDTH)
        for state in self._STATES:
            with self.subTest(state=state):
                line = self._line(_TARGET_WIDTH, self._STAMP, state)
                self.assertLessEqual(cell_len(line), budget,
                                     f"{cell_len(line)} > {budget}: {line!r}")
                expected = f"frozen {self._SHORT}"
                if state is not None:
                    expected += " " + self._badge(state)
                # Nothing shed at the default width: word, stamp, whole badge.
                self.assertEqual(line, expected)

    def test_every_state_fits_at_narrow_widths(self):
        for width, state in itertools.product((30, 22, 17, 11, 10, 6, 4, 2),
                                              self._STATES):
            with self.subTest(width=width, state=state):
                line = self._line(width, self._STAMP, state)
                budget = mm._own_phase_budget(width)
                self.assertLessEqual(cell_len(line), budget,
                                     f"{cell_len(line)} > {budget}: {line!r}")

    def test_the_stamp_goes_first(self):
        """At 30 the widest badge no longer fits beside the stamp; the stamp
        is informational, the badge is the drop verdict."""
        line = self._line(30, self._STAMP, "triaged")
        self.assertEqual(line, "frozen drop ok, triaged")

    def test_the_word_goes_next_so_the_whole_badge_fits(self):
        """At 22 the whole 16-cell badge fits the 18-cell budget, but not with
        the word in front; line 1's cyan F already says frozen (the t2354
        rule). Without this rung truncation reads `frozen drop ok, t…`."""
        line = self._line(22, self._STAMP, "triaged")
        self.assertEqual(line, "drop ok, triaged")

    def test_a_clipped_badge_keeps_its_verdict(self):
        line = self._line(17, self._STAMP, "triaged")
        self.assertTrue(line.startswith("drop ok"), line)
        self.assertTrue(line.endswith("…"), line)

    def test_no_verdict_keeps_the_word(self):
        """`None` has no badge: the word IS the state and is never shed."""
        self.assertEqual(self._line(22, self._STAMP, None), "frozen")
        self.assertEqual(self._line(_TARGET_WIDTH, self._STAMP, None),
                         f"frozen {self._SHORT}")

    def test_an_unreadable_record_shows_the_word_and_badge(self):
        """`""` = frozen, record unreadable: no stamp, still `frozen`."""
        self.assertEqual(self._line(_TARGET_WIDTH, "", None), "frozen")
        self.assertEqual(self._line(_TARGET_WIDTH, "", "triaged"),
                         "frozen drop ok, triaged")

    def test_an_unparseable_stamp_is_shown_raw_and_bounded(self):
        for stamp in ("yesterday", "x" * 80):
            with self.subTest(stamp=stamp):
                line = self._line(_TARGET_WIDTH, stamp, "triaged")
                self.assertLessEqual(cell_len(line),
                                     mm._own_phase_budget(_TARGET_WIDTH), line)
                self.assertTrue(line.endswith("drop ok, triaged"), line)
        self.assertEqual(self._line(_TARGET_WIDTH, "yesterday", None),
                         "frozen yesterday")

    def test_a_markup_looking_stamp_renders_literally(self):
        """The stamp is store text: a `$variable`, never parsed (t2017)."""
        self.assertEqual(self._line(_TARGET_WIDTH, "[red]x[/]", None),
                         "frozen [red]x[/]")


def _task_info(title: str) -> TaskInfo:
    return TaskInfo(
        task_id="1351", task_file="aitasks/t1351_demo.md", title=title,
        priority="low", effort="low", issue_type="chore", status="Implementing",
        body="", plan_content=None, task_file_abs="/nonexistent/t1351_demo.md",
    )


class _WorstCaseHost(sp._RefreshHost):
    """The real `MiniMonitorApp` rendering N copies of the widest row.

    Every card: priority mark, a bound shadow (rendered `◆!` by the caller's
    patch), compare mode overridden, `PROMPT 999s`, a double-width task title
    and a full gate+phase row — three rows per card, none of which may wrap.
    """

    _NAME_CYCLE = ("agent-pick-1351_12", "agent-" + "x" * 60,
                   "agent-" + "漢" * 30)

    def __init__(self, count: int) -> None:
        super().__init__([f"%{i}" for i in range(count)])
        shadow_snap = SimpleNamespace(awaiting_input=False, is_idle=True)
        self._monitor.get_compare_mode = lambda pid: "stripped"
        self._monitor.is_compare_mode_overridden = lambda pid: True
        self._monitor.get_shadow_snapshot = lambda pid: shadow_snap
        self._monitor.agent_prefixes = list(_PREFIXES)
        self._task_cache = SimpleNamespace(
            get_task_id=lambda w: "1351",
            get_task_id_for_pane=lambda p: "1351",
            get_task_info=lambda t, s=None: _task_info("漢字" * 20),
            update_session_mapping=lambda m: None,
        )
        self._gate_cache = SimpleNamespace(
            summary_for=lambda info: "0/4 pass, 1 pending, 1 failed, 1 stale",
            phase_for=lambda info, **kw: workflow_phase.PhaseSignal(
                phase="IMPLEMENT", waiting="WAITING", recording="on"),
            clear=lambda: None,
        )

    async def _capture_all_async(self):
        return {
            pid: _snap(pid, window_index=str(i + 2),
                       window_name=self._NAME_CYCLE[i % len(self._NAME_CYCLE)])
            for i, pid in enumerate(self._pane_ids)
        }

    def _mark_kind(self, snap):
        return agent_marks.KIND_PRIORITY


async def _settle(pilot, frames=12):
    for _ in range(frames):
        await pilot.pause()


class CompositedRowTests(unittest.TestCase):
    """The AC: the composited screen at width 40, worst case, both list states."""

    def _render(self, count: int, height: int):
        async def run():
            app = _WorstCaseHost(count)
            async with app.run_test(size=(_TARGET_WIDTH, height)) as pilot:
                await app._refresh_data()
                await _settle(pilot)
                container = app.query_one("#mini-pane-list", mm.MiniPaneList)
                lines = [strip.text for strip in
                         app.screen._compositor.render_strips()]
                cards = []
                for card in app.query(mm.MiniPaneCard):
                    try:
                        region = app.screen.find_widget(card).region
                    except NoWidget:
                        region = None
                    cards.append((card.pane_id, card.size.height, region))
                expected = {
                    pid: _plain(app._agent_card_text(snap).split("\n")[0])
                    for pid, snap in app._snapshots.items()
                }
                return (container.show_vertical_scrollbar,
                        container.styles.scrollbar_size_vertical,
                        lines, cards, expected,
                        app.screen.find_widget(container).region)

        with mock.patch.object(mm, "format_shadow_glyph", _shadow_with_concerns):
            return asyncio.run(run())

    def _assert_no_row_wraps_or_clips(self, count: int, height: int,
                                      scrollbar: bool):
        shown, bar_cells, lines, cards, expected, list_region = self._render(
            count, height)
        self.assertEqual(shown, scrollbar,
                         "precondition: the list's scrollbar state is the one "
                         "this scenario exists to measure")
        self.assertEqual(len(cards), count)
        screen = "\n".join(lines)
        self.assertIn("◆!", screen, "precondition: the widest glyph rendered")
        checked = 0
        for pane_id, height, region in cards:
            with self.subTest(pane_id=pane_id):
                # Screen-level evidence first: a failing budget assertion would
                # otherwise stop the subtest before the wrap/clip is reported.
                self.assertEqual(height, 3, f"card wrapped:\n{screen}")
                # Only a card wholly inside the list's own visible region is on
                # screen: below it, the docked key hints own those rows.
                if (region is not None and region.y >= list_region.y
                        and region.y + 3 <= list_region.bottom):
                    self.assertIn(expected[pane_id], lines[region.y],
                                  f"row clipped on screen:\n{screen}")
                    checked += 1
                self.assertLessEqual(cell_len(expected[pane_id]),
                                     mm._row_budget(_TARGET_WIDTH))
        self.assertGreaterEqual(checked, 3, f"too few visible cards:\n{screen}")
        if scrollbar:
            self.assertEqual(bar_cells, mm._LIST_SCROLLBAR)

    # Tall enough that 3 cards fit even pre-fix (when each wrapped to ~5 rows),
    # so the hidden-scrollbar precondition never depends on the bug under test.
    def test_worst_case_fits_with_the_scrollbar_hidden(self):
        self._assert_no_row_wraps_or_clips(3, 40, scrollbar=False)

    def test_worst_case_fits_with_the_scrollbar_visible(self):
        self._assert_no_row_wraps_or_clips(30, 24, scrollbar=True)

    def test_common_name_renders_whole_on_screen(self):
        lines = self._render(3, 40)[2]
        self.assertTrue(
            any("★ ● ◆! ≈ pick-1351_12  PROMPT 999s" in ln for ln in lines),
            "\n".join(lines))


class ScrollbarConstantTests(unittest.TestCase):
    def test_reserved_width_matches_the_stylesheet(self):
        async def run():
            app = sp._ListHost()
            async with app.run_test(size=(_TARGET_WIDTH, 12)):
                return app.query_one(
                    "#mini-pane-list", mm.MiniPaneList
                ).styles.scrollbar_size_vertical
        self.assertEqual(asyncio.run(run()), mm._LIST_SCROLLBAR)


if __name__ == "__main__":
    unittest.main()
