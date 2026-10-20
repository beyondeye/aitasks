"""User-derived text renders literally in every remaining monitor sink (t2017).

t2006 fixed three `ait monitor` surfaces (card rows, preview header,
``KillConfirmDialog``) and left the rest: dialogs, the session bars, the
session divider, minimonitor's rows / own panel / own header, and the toasts.
Each interpolated a tmux window name, a session name, a task title or
frontmatter field, or a pane command either raw or through
``rich.markup.escape`` — which is wrong under Textual's parser (it doubles a
backslash before a bracket, doubles a trailing backslash, and leaves a lone
``[`` that swallows the next tag).

The rule each sink now follows depends on what comes after the value:

* a toast that carries no styling      → ``notify(..., markup=False)``;
* followed by text, or ending markup   → ``markup_literal`` (an ending style
  is left open — Textual closes it at end of input);
* directly before a tag                → ``Content.from_markup(template,
  **variables)``, every user field a ``$variable``;
* no markup at all                     → ``Content(text)``.

Every assertion parses with Textual (``Content.from_markup``, a ``Static``'s
``render()``, or a mounted widget), never with Rich, which renders the
``escape()`` output correctly and so cannot see the defect.

**Fixture construction.** ``tests/test_textual_markup_colours.py``'s Rule C
parses every string constant and f-string under ``tests/`` with Textual when it
holds a named closing tag. A hostile fixture written as one literal is
therefore a finding of its own (one already exists in
``test_monitor_markup_escape.py``, tracked by t2021). So no literal here
carries a named closing tag: hostile values and expected markup are assembled
at runtime with :func:`tag`, and :class:`ScannerSelfCheckTests` runs the
scanner over this file, so an existing finding elsewhere cannot mask a new one.

Run: python3 tests/test_monitor_markup_literal_sinks.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Neither app is run against a real tmux here; scrub the ambient env (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.markup import escape as rich_escape  # noqa: E402
from textual.app import App  # noqa: E402
from textual.content import Content  # noqa: E402
from textual.widgets import Static  # noqa: E402

import agent_marks  # noqa: E402
import workflow_phase  # noqa: E402
from agent_launch_utils import TmuxLaunchConfig  # noqa: E402
from monitor import minimonitor_app as mm  # noqa: E402
from monitor import monitor_app as ma  # noqa: E402
from monitor import monitor_shared as ms  # noqa: E402
from monitor import review_loop  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import (  # noqa: E402
    MonitorApp, RestartConfirmDialog, SessionRenameDialog,
)
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TaskInfo, TmuxPaneInfo,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402

SESSION = "demo"
OPEN, CLOSE = "[", "]"


def tag(body: str) -> str:
    """``[body]`` — assembled, so no literal in this file holds a tag pair."""
    return OPEN + body + CLOSE


#: Window names. Each defeats a different treatment: raw markup (the first two
#: raise / are eaten), `escape()` (a backslash before a bracket is doubled, a
#: lone `[` swallows the next tag), and string escaping in general (a trailing
#: backslash before a closing tag).
NAMES = [
    "agent-" + tag("/") + "x",
    "agent-" + tag("bold") + "y",
    "agent-\\" + tag("bold") + "y",
    "agent-x\\",
    "agent-x" + OPEN + " y",
]
TITLES = [
    "Fix " + tag("/") + " and " + tag("dim") + "x" + tag("/dim"),
    "a \\" + tag("bold") + " b",
    "ends with \\",
    "lone " + OPEN + " bracket",
]
COMMANDS = [tag("/") + "cmd", "\\" + tag("x"), "cmd\\", "cmd" + OPEN]
SESSIONS = [
    "s-" + tag("/") + "x",
    "s-" + tag("dim") + "y",
    "s-\\" + tag("b") + "z",
    "s\\",
    "s" + OPEN + " t",
]
#: One name that is all three hazards at once — what the toast table uses.
#: No `/`, because one driver writes a log file named after it.
TOAST_NAME = "agent-" + tag("bold") + "y" + OPEN + "z\\"
#: The hostile part alone: the log toasts name the agent without its prefix.
HOSTILE = TOAST_NAME[len("agent-"):]


def parse(markup: str) -> Content:
    """Textual's parser — what a ``Static`` does with a markup string."""
    return Content.from_markup(markup)


def covering(content: Content, start: int, end: int | None = None) -> set[str]:
    """Styles of every span that covers ``[start, end)`` (``end``: the end)."""
    end = len(content.plain) if end is None else end
    return {str(s.style) for s in content.spans
            if s.start <= start and s.end >= end}


def pane(window: str, *, pane_id: str = "%1", command: str = "node",
         session: str = SESSION, window_index: str = "1",
         category: PaneCategory = PaneCategory.AGENT) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index=window_index, window_name=window, pane_index="0",
        pane_id=pane_id, pane_pid=4242, current_command=command, width=80,
        height=24, category=category, session_name=session,
    )


def snapshot(window: str, *, parked: bool = False, frozen: bool = False,
             **kw) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane(window, **kw), content="x", timestamp=0.0,
        idle_seconds=1.0, is_idle=False, parked=parked, frozen=frozen,
    )


def task_info(title: str, *, status: str = "Implementing") -> TaskInfo:
    return TaskInfo(
        task_id="42", task_file="aitasks/t42_x.md", title=title,
        priority="medium", effort="low", issue_type="bug", status=status,
        body="body", plan_content="plan",
    )


class _TitleCache:
    """A task cache that maps every pane to t42 with ``title`` (None: no task)."""

    def __init__(self, title: str | None) -> None:
        self._title = title

    def get_task_id_for_pane(self, pane): return "42" if self._title is not None else None

    def get_task_info(self, task_id, session):
        return task_info(self._title) if self._title is not None else None


def rendered(visual) -> tuple[str, list[tuple[int, int, str]]]:
    """What a ``Static`` shows for ``visual``: plain text and its spans."""
    content = Static(visual).render()
    return content.plain, [(s.start, s.end, str(s.style)) for s in content.spans]


# --- pre-phase: the docked panel before its Content conversion ---------------

OWN_TITLE = ("Render the remaining user text literally across every monitor "
             "markup sink")
OWN_LONG_NAME = "agent-pick-" + "very-long-window-name-" * 2 + "end"

#: Captured from the pre-t2017 code (``str`` markup), and never edited after:
#: the conversion of the own panel to ``Content`` must not change one cell or
#: one span of what benign input renders.
OWN_PANEL_BEFORE = {
    "name_only": (
        "agent-followed",
        [(0, 14, "bold")],
    ),
    "mark_and_name": (
        "☆ agent-followed",
        [(0, 1, "dim"), (2, 16, "bold")],
    ),
    "name_and_title": (
        "☆ agent-followed\n  Render the remaining user text\n"
        "  literally across every monitor…",
        [(0, 1, "dim"), (2, 16, "bold"), (19, 49, "dim"), (52, 83, "dim")],
    ),
    "title_and_phase": (
        "☆ agent-followed\n  Render the remaining user text\n"
        "  literally across every monitor…\n  planning",
        [(0, 1, "dim"), (2, 16, "bold"), (19, 49, "dim"), (52, 83, "dim"),
         (86, 94, "dim")],
    ),
    "frozen": (
        "F agent-followed\n  Render the remaining user text\n"
        "  literally across every monitor…\n  frozen 2026-09-04T09:20:00Z",
        [(0, 1, "bold cyan"), (2, 16, "bold"), (19, 49, "dim"), (52, 83, "dim"),
         (86, 113, "dim")],
    ),
    "frozen_marked_long_name": (
        "★F agent-pick-very-long-window-name-\nvery-long-window-name-end\n"
        "  frozen",
        [(0, 1, "bold white"), (1, 2, "bold cyan"), (3, 36, "bold"),
         (37, 62, "bold"), (65, 71, "dim")],
    ),
}

#: (title, window, mark_kind, phase, frozen_at) per case above.
OWN_PANEL_CASES = {
    "name_only": (None, "agent-followed", None, "", None),
    "mark_and_name": (None, "agent-followed", agent_marks.KIND_NONE, "", None),
    "name_and_title": (OWN_TITLE, "agent-followed", agent_marks.KIND_NONE, "",
                       None),
    "title_and_phase": (OWN_TITLE, "agent-followed", agent_marks.KIND_NONE,
                        "planning", None),
    "frozen": (OWN_TITLE, "agent-followed", None, "", "2026-09-04T09:20:00Z"),
    "frozen_marked_long_name": (None, OWN_LONG_NAME, agent_marks.KIND_PRIORITY,
                                "", ""),
}


def own_card(title, window, mark_kind, phase, frozen_at, *, width: int = 40):
    """``_own_card_text`` over a freshly built identity, as the panel mounts it."""
    app = MiniMonitorApp.__new__(MiniMonitorApp)
    app._target_width = width
    app._task_cache = _TitleCache(title)
    app._own_identity_text = app._own_agent_identity_text(snapshot(window))
    return app._own_card_text(mark_kind, phase, frozen_at)


class OwnPanelCharacterizationTests(unittest.TestCase):
    """Benign input renders exactly as it did before the conversion."""

    def test_every_case_renders_as_before(self):
        self.assertEqual(set(OWN_PANEL_CASES), set(OWN_PANEL_BEFORE))
        for key, args in OWN_PANEL_CASES.items():
            with self.subTest(case=key):
                self.assertEqual(rendered(own_card(*args)), OWN_PANEL_BEFORE[key])


class OwnPanelHostileTests(unittest.TestCase):
    """The docked panel with hostile names and titles: exact text, the name
    bold, the title dim, and the phase row exactly as styled as ever."""

    def test_name_title_and_phase_render_literally(self):
        for name in NAMES:
            for title in TITLES:
                with self.subTest(name=name, title=title):
                    card = Static(own_card(title, name, agent_marks.KIND_NONE,
                                           "planning", None)).render()
                    self.assertEqual(card.plain,
                                     f"☆ {name}\n  {title}\n  planning")
                    self.assertIn("bold", covering(card, 2, 2 + len(name)))
                    start = card.plain.index("\n") + 3
                    self.assertIn("dim", covering(card, start, start + len(title)))
                    phase_at = len(card.plain) - len("planning")
                    self.assertEqual(
                        cell_styles(card, phase_at, len(card.plain)),
                        [frozenset({"dim"})] * len("planning"))

    def test_a_frozen_hostile_name_keeps_the_frozen_row(self):
        for name in NAMES:
            with self.subTest(name=name):
                plain, _spans = rendered(own_card(None, name, None, "", ""))
                self.assertEqual(plain, f"F {name}\n  frozen")


# --- shared formatters, session bars, list rows --------------------------------

def cell_styles(content: Content, start: int, end: int) -> list[frozenset]:
    """The set of style strings covering each cell of ``[start, end)``."""
    return [frozenset(str(s.style) for s in content.spans
                      if s.start <= i < s.end) for i in range(start, end)]


class RuleTests(unittest.TestCase):
    def test_markup_literal_round_trips_every_hostile_value(self):
        for value in NAMES + TITLES + COMMANDS + SESSIONS + [TOAST_NAME]:
            with self.subTest(value=value):
                markup = (tag("bold") + ms.markup_literal(value) + " (0)"
                          + tag("/"))
                self.assertEqual(parse(markup).plain, value + " (0)")

    def test_escape_is_not_a_textual_escape(self):
        """Negative control — the reason every `escape()` user was migrated.
        If this passes one day, Textual's parser changed."""
        for value in ("a" + OPEN + " b", "x\\", "agent-\\" + tag("bold") + "y"):
            with self.subTest(value=value):
                markup = (tag("bold") + rich_escape(value) + " (0)" + tag("/"))
                self.assertNotEqual(parse(markup).plain, value + " (0)")

    def test_a_dollar_name_inside_a_variable_stays_literal(self):
        """Variables are substituted once, after tokenizing: a title that
        itself reads `$task_id` is not substituted again."""
        title = "$task_id and $$ " + tag("/")
        content = Content.from_markup(
            tag("bold") + "t$task_id: $title" + tag("/"),
            task_id="42", title=title)
        self.assertEqual(content.plain, "t42: " + title)


class SharedFormatterTests(unittest.TestCase):
    def test_session_divider_is_exact_and_one_cyan_span(self):
        for session in SESSIONS:
            with self.subTest(session=session):
                content = Static(ms.format_session_divider(session)).render()
                self.assertEqual(content.plain, f"── {session} ──")
                self.assertTrue(any("cyan" in s for s in covering(content, 0)),
                                content.spans)

    def test_minimonitor_own_header_is_exact_and_dim(self):
        for session in SESSIONS:
            with self.subTest(session=session):
                content = Static(
                    mm._own_header_text("this agent", session, 40)).render()
                self.assertEqual(content.plain,
                                 f"── this agent · {session} ──")
                self.assertIn("dim", covering(content, 0))


class _Bar:
    """Stands in for the session-bar ``Static``: keeps what ``update`` got."""

    display = True
    markup = ""

    def update(self, markup) -> None:
        self.markup = markup


class SessionBarTests(unittest.TestCase):
    @staticmethod
    def _monitor(multi: bool):
        return SimpleNamespace(multi_session=multi,
                               control_state=lambda: TmuxControlState.CONNECTED)

    def _monitor_bar(self, session: str, *, multi: bool) -> str:
        app = MonitorApp.__new__(MonitorApp)
        app._snapshots = {"%1": snapshot("agent-a", session=session)}
        app._completed_pane_ids = frozenset()
        app._auto_switch = False
        app._session = session
        app._monitor = self._monitor(multi)
        bar = _Bar()
        app.query_one = lambda *a, **k: bar
        app._rebuild_session_bar(attached_session=session, desync="")
        return parse(bar.markup).plain

    def test_monitor_single_session_bar(self):
        for session in SESSIONS:
            with self.subTest(session=session):
                plain = self._monitor_bar(session, multi=False)
                self.assertIn(f"session: {session} (1 pane)", plain)
                self.assertTrue(plain.endswith("Tab: switch panel"), plain)

    def test_monitor_multi_session_bar(self):
        for session in SESSIONS:
            with self.subTest(session=session):
                plain = self._monitor_bar(session, multi=True)
                self.assertIn(f"(attached: {session})", plain)
                self.assertTrue(plain.endswith("Tab: switch panel"), plain)

    def test_minimonitor_bar(self):
        for session in SESSIONS:
            with self.subTest(session=session):
                app = MiniMonitorApp.__new__(MiniMonitorApp)
                app._snapshots = {"%1": snapshot("agent-a", session=session)}
                app._completed_pane_ids = frozenset()
                app._session_bar_enabled = True
                app._session = session
                app._monitor = self._monitor(False)
                bar = _Bar()
                app.query_one = lambda *a, **k: bar
                app._rebuild_session_bar(desync="")
                self.assertEqual(parse(bar.markup).plain, f"{session}  1 agent")


def mini_app(title: str | None = None, *, summary: str = "",
             phase: workflow_phase.PhaseSignal | None = None) -> MiniMonitorApp:
    """`__new__` stub, enough for `_agent_card_text` incl. the gated row."""
    app = MiniMonitorApp.__new__(MiniMonitorApp)
    app._target_width = 40
    app._completed_pane_ids = frozenset()
    app._monitor = SimpleNamespace(
        get_compare_mode=lambda pid: "stripped",
        is_compare_mode_overridden=lambda pid: False,
        get_shadow_snapshot=lambda pid: None,
    )
    app._task_cache = _TitleCache(title)
    app._gate_cache = SimpleNamespace(
        summary_for=lambda info: summary,
        phase_for=lambda info, **kw: phase or workflow_phase.PhaseSignal(),
        clear=lambda: None,
    )
    app._init_agent_marks()
    app._mark_kind = lambda snap: agent_marks.KIND_NONE
    return app


class MiniListRowTests(unittest.TestCase):
    def test_name_row_keeps_the_name_and_its_marker(self):
        app = mini_app()
        for name in NAMES:
            for kind in ("live", "parked", "frozen"):
                with self.subTest(name=name, kind=kind):
                    snap = snapshot(name, parked=kind == "parked",
                                    frozen=kind == "frozen")
                    line0 = parse(app._agent_card_text(snap)).plain
                    self.assertIn(f"{name}  ", line0)
                    if kind != "live":
                        self.assertTrue(line0.endswith(f"{name}  {kind}"),
                                        repr(line0))

    def test_title_row_is_exact_and_dim(self):
        for title in TITLES:
            with self.subTest(title=title):
                card = parse(mini_app(title)._agent_card_text(
                    snapshot("agent-a")))
                lines = card.plain.split("\n")
                self.assertEqual(lines[1], f"  {title}")
                start = len(lines[0]) + 3
                self.assertIn("dim", covering(card, start, start + len(title)))

    def test_frozen_title_row_is_exact_and_dim(self):
        """t2042: a frozen row keeps the task title, under the same literal
        rendering as the live row — and nothing after it (no gate/phase row)."""
        budget = min(mm._TITLE_MAX_CELLS, mm._detail_budget(40))
        for title in TITLES:
            with self.subTest(title=title):
                card = parse(mini_app(title, summary="2/2 pass")._agent_card_text(
                    snapshot("agent-a", frozen=True)))
                lines = card.plain.split("\n")
                self.assertEqual(len(lines), 2, repr(card.plain))
                # The `[dim]frozen[/]` before the title still parsed as a tag.
                self.assertTrue(lines[0].endswith("agent-a  frozen"),
                                repr(lines[0]))
                expected = mm._clip(title, budget)
                self.assertEqual(lines[1], f"  {expected}")
                start = len(lines[0]) + 3
                self.assertIn("dim", covering(card, start, start + len(expected)))

    def test_the_open_title_span_changes_nothing_the_phase_row_renders(self):
        """The title row leaves `[dim]` open (a trailing backslash cannot sit
        before its `[/]`). The gate/phase row after it must render exactly as
        it does parsed on its own — same text, and the same styles on every
        visible cell. Only the row's two-space indent picks up the open dim,
        and a style on a blank cell draws nothing."""
        sig = workflow_phase.PhaseSignal(phase="PLAN")
        for title in TITLES + ["benign title"]:
            with self.subTest(title=title):
                text = mini_app(title, summary="2/2 pass",
                                phase=sig)._agent_card_text(snapshot("agent-a"))
                rows = text.split("\n")
                self.assertEqual(len(rows), 3, text)
                card = parse(text)
                alone = parse(rows[2])
                offset = card.plain.rindex("\n") + 1
                self.assertEqual(card.plain[offset:], alone.plain)
                visible = [i for i, ch in enumerate(alone.plain) if ch != " "]
                self.assertTrue(visible)
                whole = cell_styles(card, offset, len(card.plain))
                own = cell_styles(alone, 0, len(alone.plain))
                self.assertEqual([whole[i] for i in visible],
                                 [own[i] for i in visible])

    def test_other_row_is_exact_and_the_command_is_dim(self):
        app = mini_app()
        for name in NAMES:
            for cmd in COMMANDS:
                with self.subTest(name=name, cmd=cmd):
                    row = parse(app._other_card_text(snapshot(
                        name, command=cmd, category=PaneCategory.OTHER)))
                    self.assertEqual(row.plain, f"  ○ {name}  {cmd}")
                    self.assertIn("dim", covering(row, len(row.plain) - len(cmd)))

    def test_sibling_row_keeps_the_title(self):
        for title in TITLES:
            for blockers in ([], ["7"]):
                with self.subTest(title=title, blockers=blockers):
                    plain = parse(ms._SiblingRow("42_3", title, blockers,
                                                 "").render()).plain
                    expected = f"  t42_3  {title}"
                    if blockers:
                        expected += "  ⛔ blocked by t7"
                    self.assertEqual(plain, expected)


# --- dialogs, mounted -----------------------------------------------------------

STATUS = "Impl" + tag("dim") + "x\\"


class _Host(App):
    def __init__(self, screen) -> None:
        super().__init__()
        self._dialog = screen

    def on_mount(self) -> None:
        self.push_screen(self._dialog)


def mounted(screen, selectors, *, act=None, size=(120, 40)) -> dict:
    """Mount ``screen`` and return ``{selector: rendered plain text}``.

    ``act(app, pilot)`` (async) runs before reading, for key-driven updates.
    """
    async def runner():
        app = _Host(screen)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            if act is not None:
                await act(app, pilot)
                await pilot.pause()
            return {sel: app.screen.query_one(sel).render().plain
                    for sel in selectors}

    return asyncio.run(runner())


class DialogTests(unittest.TestCase):
    def test_restart_dialog(self):
        for title in TITLES:
            with self.subTest(title=title):
                got = mounted(RestartConfirmDialog("42", title, STATUS, 12.0),
                              ["#restart-details"])["#restart-details"]
                lines = got.split("\n")
                self.assertEqual(lines[0],
                                 f"Current:   t42: {title}  (Status: {STATUS})")
                self.assertIn(f"⚠ Task status is '{STATUS}' (not Ready)", got)
                self.assertEqual(lines[-1], "The current pane will be killed "
                                            "after you confirm the spawn dialog.")

    def test_session_rename_dialog(self):
        current, expected = SESSIONS[0], SESSIONS[3]
        got = mounted(SessionRenameDialog(current, expected),
                      ["#rename-message"])["#rename-message"]
        self.assertEqual(got, (
            f"Session name mismatch\n\nCurrent session: {current}\n"
            f"Expected session: {expected}\n\nRename session to {expected}?"))

    def test_next_sibling_dialog(self):
        cur, sug = TITLES[0], TITLES[2]
        got = mounted(
            ms.NextSiblingDialog("42_1", cur, STATUS, "42_2", sug, "42"),
            ["#next-sib-details"])["#next-sib-details"]
        self.assertEqual(got.split("\n"), [
            f"Current:   t42_1: {cur}  (Status: {STATUS})",
            f"Suggested:   t42_2: {sug}",
        ])

    def test_task_detail_header_meta_and_toggle_label(self):
        """After `p` the header names the view; `[Plan]` / `[Task]` used to
        be read as an unknown tag and never rendered."""
        for title in TITLES:
            with self.subTest(title=title):
                info = task_info(title, status=STATUS)

                async def toggle(app, pilot):
                    await pilot.press("p")

                before = mounted(ms.TaskDetailDialog(info),
                                 ["#task-detail-header", "#task-detail-meta"])
                self.assertEqual(before["#task-detail-header"], f"t42: {title}")
                self.assertEqual(
                    before["#task-detail-meta"],
                    f"Priority: medium  Effort: low  Type: bug  Status: {STATUS}")
                after = mounted(ms.TaskDetailDialog(info),
                                ["#task-detail-header"], act=toggle)
                self.assertEqual(after["#task-detail-header"],
                                 f"t42: {title} {tag('Plan')}")

    def test_task_pick_confirm_lines(self):
        label = f"t42 · {STATUS} · {TOAST_NAME}"
        running = f"⚠ t42 is already running in this session, window 1:{TOAST_NAME}"
        info = task_info(TITLES[0], status=STATUS)

        async def tick(app, pilot):
            app.screen.query_one("#pick-kill").value = True

        sels = ["#pick-eligibility", "#pick-running", "#pick-kill-detail"]
        before = mounted(ms.TaskPickConfirmDialog(
            info, kill_target_label=label, already_running=running), sels)
        self.assertEqual(before["#pick-eligibility"],
                         f"⚠ t42 is {STATUS} — not Ready to pick")
        self.assertEqual(before["#pick-running"], running)
        self.assertEqual(before["#pick-kill-detail"], f"keeps {label}")
        after = mounted(ms.TaskPickConfirmDialog(
            info, kill_target_label=label, already_running=running),
            ["#pick-kill-detail"], act=tick)
        self.assertEqual(after["#pick-kill-detail"], f"KILLS {label}")


class FreezeBodyTests(unittest.TestCase):
    """The freeze / drop confirmation bodies, built by the real callers in both
    apps and then mounted."""

    def _captured(self, app) -> list:
        shown = []
        app.push_screen = lambda screen, callback=None: shown.append(screen)
        return shown

    def _body(self, dialog) -> str:
        return mounted(dialog, ["#freeze-details"])["#freeze-details"]

    def test_freeze_one_body_in_both_apps(self):
        for cls in (MonitorApp, MiniMonitorApp):
            for name in NAMES:
                with self.subTest(app=cls.__name__, name=name):
                    app = cls.__new__(cls)
                    snap = snapshot(name)
                    app._current_agent_snapshot = lambda snap=snap: snap
                    shown = self._captured(app)
                    app.action_freeze_current()
                    body = self._body(shown[0])
                    self.assertTrue(body.startswith(f"{name}\n\nThe agent "
                                                    "process ends."), body)

    def test_drop_body_in_both_apps(self):
        for cls in (MonitorApp, MiniMonitorApp):
            for name in NAMES:
                with self.subTest(app=cls.__name__, name=name):
                    app = cls.__new__(cls)
                    shown = self._captured(app)
                    app._confirm_drop_frozen(snapshot(name, frozen=True))
                    body = self._body(shown[0])
                    self.assertTrue(body.startswith(
                        f"{name}\n\nIts captured output is deleted"), body)


# --- toasts ---------------------------------------------------------------------

class _Spy:
    """Records every ``notify`` as ``(message, markup)``."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def __call__(self, message, *, title="", severity="information",
                 timeout=None, markup=True) -> None:
        self.calls.append((message, markup))


def _app(cls):
    app = cls.__new__(cls)
    app.notify = _Spy()
    app.call_later = lambda *a, **k: None
    app.push_screen = lambda *a, **k: None
    return app


class _FakeMonitor:
    multi_session = False

    def __init__(self, *, switch=True, kill_ok=True,
                 frozen_read=(True, "")) -> None:
        self._switch, self._kill_ok = switch, kill_ok
        # The pick flows' kill-time `@aitask_frozen` read (t2057); the default
        # is a verified unset option, i.e. a live agent.
        self._frozen_read = frozen_read

    def switch_to_pane(self, pane_id, **kw): return self._switch

    def kill_agent_pane_smart(self, pane_id): return self._kill_ok, False

    def get_pane_option_sync(self, pane_id, option, timeout=2.0):
        return self._frozen_read

    def get_pane(self, pane_id):
        # Unknown to the discovery cache: no cached frozen record (t2065).
        return None


def _focused(app, name: str, **kw) -> None:
    snap = snapshot(name, **kw)
    app._snapshots = {"%1": snap}
    app._focused_pane_id = "%1"
    app._get_focused_pane_id = lambda: "%1"


def toast_monitor_mismatch(name):
    app = _app(MonitorApp)
    app._wire_preview_hooks = lambda: None
    app._rename_window = False
    app._mark_pane = False
    app._multi_session = False
    app._session, app._expected_session = name, name + "-configured"
    app._start_monitoring = lambda: None
    with patch.dict(os.environ, {"TMUX": "/tmp/x,1,0"}), \
            patch.object(ma, "_TMUX", SimpleNamespace(run=lambda argv: (0, ""))):
        app.on_mount()
    return app.notify.calls


def toast_monitor_renamed(name):
    app = _app(MonitorApp)
    app._expected_session = name
    app._start_monitoring = lambda: None
    app._on_session_rename(True)
    return app.notify.calls


def _switch_to(cls):
    def driver(name):
        app = _app(cls)
        app._monitor = _FakeMonitor()
        _focused(app, name)
        app.action_switch_to()
        return app.notify.calls
    return driver


def _log_toast(with_log: bool):
    def driver(name):
        app = _app(MonitorApp)
        _focused(app, name)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if with_log:
                crew = root / ".aitask-crews" / "crew-a"
                crew.mkdir(parents=True)
                (crew / f"{name[len('agent-'):]}_log.txt").write_text("x")
            app._root_for_snap = lambda snap: root
            with patch.object(ma.subprocess, "Popen", lambda *a, **k: None):
                app.action_open_log()
        return app.notify.calls
    return driver


def _kill_toast(cls, ok: bool, frozen_read=(True, "")):
    def driver(name):
        app = _app(cls)
        app._monitor = _FakeMonitor(kill_ok=ok, frozen_read=frozen_read)
        _focused(app, name)
        if cls is MonitorApp:
            app._on_kill_confirmed(True, "%1")
        else:
            app._on_own_kill_confirmed(True, "%1")
        return app.notify.calls
    return driver


def _launch(app, module, run, name):
    """Run ``run()`` with the pick dialog stubbed, then answer the dialog with
    a launch whose tmux error names ``name``."""
    callbacks = []
    app.push_screen = lambda screen, callback=None: callbacks.append(callback)
    config = TmuxLaunchConfig(session="s", window="w", new_session=False,
                              new_window=True)
    with patch.object(module, "build_pick_screen",
                      lambda *a, **k: SimpleNamespace(full_command="cmd")), \
            patch.object(module, "launch_in_tmux",
                         lambda *a, **k: (None, f"no session {name}")):
        run()
        callbacks[0](config)
    return app.notify.calls


def toast_monitor_sibling_launch(name, frozen_read=(True, "")):
    app = _app(MonitorApp)
    app._monitor = _FakeMonitor(frozen_read=frozen_read)
    _focused(app, name)
    app._task_cache = _TitleCache("t")
    app._root_for_snap = lambda snap: Path(".")
    return _launch(app, ma, lambda: app._launch_pick_for_sibling("43"), name)


def toast_monitor_restart(name, frozen_read=(True, ""), kill_ok=True):
    app = _app(MonitorApp)
    app._monitor = _FakeMonitor(kill_ok=kill_ok, frozen_read=frozen_read)
    _focused(app, name)
    app._root_for_snap = lambda snap: Path(".")
    return _launch(app, ma, lambda: app._on_restart_confirmed(True, "%1", "42"),
                   name)


def toast_mini_launch(name):
    app = _app(MiniMonitorApp)
    app._monitor = _FakeMonitor()
    return _launch(app, mm, lambda: app._launch_pick("42", Path("."), None), name)


def _mark_toast(cls, out: str, *, hide: bool = False):
    def driver(name):
        app = _app(cls)
        app._hide_inactive = hide
        app._strict_root_for_snap = lambda snap: "/r"

        async def run_marks(args, **kw):
            return (0 if out != "ERROR" else 1,
                    f"ERROR: malformed entry {name}" if out == "ERROR"
                    else f"{out}:{name}")

        app._run_marks_cmd = run_marks
        app._marks_view = SimpleNamespace(invalidate=lambda: None)
        app._refresh_marks = lambda: None
        app._publish_parked_agents = lambda: None
        asyncio.run(app._cycle_mark_for(snapshot(name)))
        return app.notify.calls
    return driver


def _verdict_toast():
    """The detached-drop poll's toast — the only verdict these apps watch."""
    def driver(name):
        app = _app(MonitorApp)
        ticks = []
        app.set_interval = lambda interval, fn: ticks.append(fn)

        class View:
            def by_id(self, record_id): return None
            def invalidate(self): pass

        with patch.object(ms.agent_sessions, "SessionsView", View):
            app._poll_frozen_outcome("rec-1")
            ticks[0]()
        return app.notify.calls
    return driver


def toast_mini_disarm(name):
    app = _app(MiniMonitorApp)
    app._review_loop = SimpleNamespace(last_disarm_reason="", disarm=lambda: None)
    app._loop_event_context = lambda: {}
    app._set_loop_banner = lambda text: None
    with patch.object(mm.review_loop_log, "record_event", lambda *a, **k: True):
        app._loop_auto_disarm(review_loop.DISARM_NO_DETECTOR, subject=name)
    return app.notify.calls


def _recheck_toast(followed_supported: bool):
    def driver(name):
        app = _app(MiniMonitorApp)
        app._review_loop = SimpleNamespace(armed=False, generation=0)
        snap = snapshot("agent-a", command=name)
        app._find_own_agent_snapshot = lambda: snap
        app._monitor = _FakeMonitor()

        async def shadow_info(monitor, pane_id):
            return True, "%9", name, 4242

        async def resolve(command, pid, pane_id):
            return "no-such-agent"

        app._resolve_shadow_agent_key = resolve
        with patch.object(mm.review_loop, "review_loop_agent_supported",
                          lambda key: followed_supported), \
                patch.object(mm, "find_shadow_pane_info_async", shadow_info):
            asyncio.run(app.action_toggle_review_loop())
        return app.notify.calls
    return driver


#: Every in-scope toast site: (label, driver). A driver puts ``name`` where the
#: site takes user text and returns the recorded ``(message, markup)`` calls.
TOAST_SITES = [
    ("monitor: session differs from configured", toast_monitor_mismatch),
    ("monitor: session renamed", toast_monitor_renamed),
    ("monitor: switched to", _switch_to(MonitorApp)),
    ("monitor: no log file found", _log_toast(False)),
    ("monitor: opening log", _log_toast(True)),
    ("monitor: killed", _kill_toast(MonitorApp, True)),
    ("monitor: failed to kill", _kill_toast(MonitorApp, False)),
    ("monitor: sibling pick killed + launch failed",
     toast_monitor_sibling_launch),
    # The two kill-skipped toasts name the window too (t2057).
    ("monitor: sibling pick frozen, not killed",
     lambda name: toast_monitor_sibling_launch(name, (True, "rec-1"))),
    ("monitor: sibling pick unverified, not killed",
     lambda name: toast_monitor_sibling_launch(name, (False, ""))),
    ("monitor: restart killed + launch failed", toast_monitor_restart),
    # The kill/restart confirm callbacks' kill-skipped toasts (t2065).
    ("monitor: kill frozen, not killed",
     _kill_toast(MonitorApp, True, (True, "rec-1"))),
    ("monitor: kill unverified, not killed",
     _kill_toast(MonitorApp, True, (False, ""))),
    ("monitor: restart frozen, not restarted",
     lambda name: toast_monitor_restart(name, (True, "rec-1"))),
    ("monitor: restart unverified, not restarted",
     lambda name: toast_monitor_restart(name, (False, ""))),
    # A failed restart kill launches nothing (t2075).
    ("monitor: restart kill failed, not restarted",
     lambda name: toast_monitor_restart(name, kill_ok=False)),
    ("both: prioritized (monitor)", _mark_toast(MonitorApp, "MARKED")),
    ("both: prioritized (minimonitor)", _mark_toast(MiniMonitorApp, "MARKED")),
    ("both: parked", _mark_toast(MonitorApp, "PARKED")),
    ("both: parked and hidden", _mark_toast(MonitorApp, "PARKED", hide=True)),
    ("both: unmarked", _mark_toast(MiniMonitorApp, "UNMARKED")),
    ("both: mark failed", _mark_toast(MonitorApp, "ERROR")),
    ("minimonitor: switched to", _switch_to(MiniMonitorApp)),
    ("minimonitor: killed", _kill_toast(MiniMonitorApp, True)),
    ("minimonitor: failed to kill", _kill_toast(MiniMonitorApp, False)),
    ("minimonitor: kill frozen, not killed",
     _kill_toast(MiniMonitorApp, True, (True, "rec-1"))),
    ("minimonitor: kill unverified, not killed",
     _kill_toast(MiniMonitorApp, True, (False, ""))),
    ("minimonitor: launch failed", toast_mini_launch),
    ("minimonitor: loop disarmed (shadow command)", toast_mini_disarm),
    ("minimonitor: recheck unavailable (followed command)",
     _recheck_toast(False)),
    ("minimonitor: recheck unavailable (shadow command)",
     _recheck_toast(True)),
]


class ToastTests(unittest.TestCase):
    def test_every_toast_carries_the_name_unparsed(self):
        for label, driver in TOAST_SITES:
            with self.subTest(site=label):
                calls = driver(TOAST_NAME)
                hits = [c for c in calls if HOSTILE in c[0]]
                self.assertTrue(hits, f"no toast named the value: {calls!r}")
                for message, markup in hits:
                    self.assertIs(markup, False, message)

    def test_the_drop_verdict_toast_is_unparsed_too(self):
        """Its notes carry no user text today, so this pins the boundary,
        not a value."""
        calls = _verdict_toast()(TOAST_NAME)
        self.assertEqual(calls, [("dropped — capture removed", False)])

    def test_a_mounted_toast_shows_the_name_verbatim(self):
        """End to end through Textual's own `Toast`, so the spy table is not
        the only evidence that `markup=False` reaches the screen."""
        async def runner():
            with tempfile.TemporaryDirectory() as tmp:
                app = MonitorApp(session=SESSION, project_root=Path(tmp))
                # `run_test` disables notifications unless asked: without
                # this no `Toast` is ever mounted.
                async with app.run_test(size=(120, 30),
                                        notifications=True) as pilot:
                    app._monitor = _FakeMonitor()
                    _focused(app, TOAST_NAME)
                    app.action_switch_to()
                    await pilot.pause()
                    await pilot.pause()
                    return [t.render().plain
                            for t in app.screen.query("Toast")]

        self.assertIn(f"Switched to {TOAST_NAME}", asyncio.run(runner()))


# --- the scanner must find nothing in this file -------------------------------

def _load_scanner():
    """``scan_source_structure`` from the repo-wide guard, loaded by path.

    Loaded under a private module name so this file's namespace never holds
    the guard's TestCase classes (which would run them twice).
    """
    path = REPO_ROOT / "tests" / "test_textual_markup_colours.py"
    spec = importlib.util.spec_from_file_location("_t2017_markup_scanner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.scan_source_structure


class ScannerSelfCheckTests(unittest.TestCase):
    """Rule C over this file alone, so an unrelated red finding cannot hide one
    of ours (``test_textual_markup_colours.py`` is one aggregate assertion)."""

    @classmethod
    def setUpClass(cls):
        cls.scan = staticmethod(_load_scanner())

    def test_this_module_adds_no_structure_findings(self):
        relpath = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()
        findings, gated = self.scan(Path(__file__).read_text(encoding="utf-8"),
                                    relpath)
        self.assertEqual([], findings)

    def test_negative_control_a_hostile_literal_is_a_finding(self):
        """The same scan over source that writes the hostile title as ONE
        literal — what this file deliberately never does."""
        hostile = ("Fix " + tag("/") + " and " + tag("dim") + "x"
                   + tag("/dim"))
        source = "TITLE = " + repr(hostile) + "\n"
        findings, _gated = self.scan(source, "tests/_probe.py")
        self.assertEqual(len(findings), 1, findings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
