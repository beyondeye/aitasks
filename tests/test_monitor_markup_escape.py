"""User-derived text renders literally in `ait monitor` (t2006).

Window names are tmux-side user input (any user can rename a window), task
titles are task-file prose, and a pane's current command is whatever process
runs there. All three reach markup-enabled widgets, so each must survive the
parser that actually renders them — Textual's, not Rich's:

* Textual opens a tag at any ``[`` not preceded by a backslash, un-escapes
  exactly ``\\[`` in text, and keeps every other backslash literal. So
  ``rich.markup.escape`` — which doubles the backslashes before a bracket —
  displays ``agent-\\[bold]y`` with a doubled backslash, and a value ending in
  ``\\`` turns the template's next tag into literal text.
* Rich's ``Text.from_markup`` renders both of those correctly, so every
  assertion here parses with ``Content.from_markup`` or reads a mounted
  widget; a Rich-parsed check could not see the defect.

Every check compares the EXACT rendered text (and, where a field ends its row,
the span that styles it), so a doubled backslash, a leaked ``[/]`` and a
swallowed ``[bold]`` all fail alike.

The kill confirmation dialog — the third surface of this fix — is covered in
``tests/test_kill_confirm_dialog.py``.

Run: python3 tests/test_monitor_markup_escape.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MonitorApp only renames its tmux window when constructed with
# rename_window=True, but scrub the ambient tmux env too (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.markup import escape as rich_escape  # noqa: E402
from textual.content import Content  # noqa: E402
from textual.markup import MarkupError  # noqa: E402

import agent_marks  # noqa: E402
import workflow_phase  # noqa: E402
# Module-qualified rather than `from … import markup_literal`, so the row and
# mounted tests still run (and fail for the real reason) against a tree where
# the helper does not exist yet.
from monitor import monitor_shared as ms  # noqa: E402
from monitor.monitor_app import MonitorApp, Zone  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TaskInfo, TmuxPaneInfo,
)

SESSION = "demo"

NAMES = [
    "agent-[/]x",                    # raises MarkupError unescaped
    "agent-[bold]y",                 # silently swallowed unescaped
    "agent-\\[bold]y",               # backslash before a bracket
    "agent-x\\",                     # trailing backslash
    "agent-" + "[/]x[dim]" * 5,
]
TITLES = [
    "Fix [/] and " + "[dim]x[/dim]",  # split: one literal trips Rule C
                                      # (test_textual_markup_colours.py)
    "a \\[bold] b",
    "ends with \\",                  # trailing backslash before the row's end
]
COMMANDS = ["[/]cmd", "\\[x]", "cmd\\"]


def pane(window: str, *, pane_id: str = "%1", command: str = "node",
         category: PaneCategory = PaneCategory.AGENT) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command=command, width=80, height=24,
        category=category, session_name=SESSION,
    )


def snapshot(window: str, *, content: str = "hello", parked: bool = False,
             frozen: bool = False, **kw) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane(window, **kw), content=content, timestamp=0.0,
        idle_seconds=1.0, is_idle=False, parked=parked, frozen=frozen,
    )


def task_info(title: str) -> TaskInfo:
    return TaskInfo(
        task_id="42", task_file="aitasks/t42_x.md", title=title,
        priority="medium", effort="low", issue_type="bug",
        status="Implementing", body="", plan_content=None,
    )


class _FakeMonitor:
    multi_session = False

    def __init__(self, root: Path) -> None:
        self._root = root

    def get_session_to_project_mapping(self) -> dict[str, Path]:
        return {SESSION: self._root}

    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None


class _FakeTaskCache:
    def __init__(self, title: str | None) -> None:
        self._title = title

    def get_task_id_for_pane(self, pane): return "42" if self._title is not None else None

    def get_task_info(self, task_id, session):
        return task_info(self._title) if self._title is not None else None

    def update_session_mapping(self, mapping): pass


class _FakeGateCache:
    def summary_for(self, info): return ""
    def phase_for(self, info, **kw): return workflow_phase.PhaseSignal()
    def clear(self): pass


def wire(app: MonitorApp, root: Path, title: str | None) -> MonitorApp:
    """Install the render-path collaborators on an app (built or mounted)."""
    app._monitor = _FakeMonitor(root)
    app._completed_pane_ids = frozenset()
    app._has_fresh_concerns = lambda pane_id: False
    app._mark_kind = lambda snap: agent_marks.KIND_NONE
    app._task_cache = _FakeTaskCache(title)
    app._gate_cache = _FakeGateCache()
    return app


def parse(markup: str) -> Content:
    """The widget's parser: what a `Static` does with a markup string."""
    return Content.from_markup(markup)


def covering_style(content: Content, start: int) -> set[str]:
    """Styles of the spans that run from ``start`` to the end of the text."""
    end = len(content.plain)
    return {str(s.style) for s in content.spans
            if s.start == start and s.end == end}


class MarkupLiteralTests(unittest.TestCase):
    def test_round_trips_every_value_under_textual(self):
        for value in NAMES + TITLES + COMMANDS + ["[", "[[", "x]", "a\\b",
                                                  "\\\\[b]", ""]:
            with self.subTest(value=value):
                rendered = parse(f"[bold]{ms.markup_literal(value)} (0)[/]")
                self.assertEqual(rendered.plain, f"{value} (0)")

    def test_rich_escape_does_not_round_trip_under_textual(self):
        """Negative control: the reason the helper exists. If this ever
        passes, Textual's parser changed and the helper's docstring is stale."""
        value = "agent-\\[bold]y"
        rendered = parse(f"[bold]{rich_escape(value)} (0)[/]")
        self.assertNotEqual(rendered.plain, f"{value} (0)")

    def test_the_split_title_fixture_is_still_hostile(self):
        """TITLES[0] is built with `+` only so the repo-wide Rule C scan
        (tests/test_textual_markup_colours.py) does not read it as live
        markup. It must stay a string Textual refuses unescaped: escaping it
        to quiet the scan would remove the input this file exists to test."""
        with self.assertRaises(MarkupError):
            parse(TITLES[0])


class RowShapeTests(unittest.TestCase):
    """Render level: each card builder's markup through Textual's parser."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def app(self, title: str | None = None) -> MonitorApp:
        return wire(MonitorApp.__new__(MonitorApp), self.root, title)

    def test_live_row_keeps_the_name(self):
        app = self.app()
        for name in NAMES:
            with self.subTest(name=name):
                plain = parse(app._format_agent_card_text(snapshot(name))).plain
                self.assertIn(f"1:{name} (0)", plain)

    def test_parked_and_frozen_rows_keep_the_name_and_their_marker(self):
        app = self.app()
        for name in NAMES:
            for kind in ("parked", "frozen"):
                with self.subTest(name=name, kind=kind):
                    snap = snapshot(name, parked=kind == "parked",
                                    frozen=kind == "frozen")
                    plain = parse(app._format_agent_card_text(snap)).plain
                    self.assertIn(f"1:{name} (0)", plain)
                    # The trailing `[dim]…[/]` still parsed as a tag.
                    self.assertTrue(plain.endswith(f"(0)  {kind}"), repr(plain))

    def test_task_title_row_is_exact_and_fully_styled(self):
        for title in TITLES:
            with self.subTest(title=title):
                row = parse(self.app(title)._format_agent_card_text(
                    snapshot("agent-pick-42")))
                lines = row.plain.split("\n")
                self.assertEqual(len(lines), 2, repr(row.plain))
                self.assertEqual(lines[1], f"     t42: {title}")
                start = row.plain.index("t42: ")
                self.assertIn("dim italic", covering_style(row, start))

    def test_other_row_is_exact_and_the_command_is_styled(self):
        app = self.app()
        for name in NAMES:
            for cmd in COMMANDS:
                with self.subTest(name=name, cmd=cmd):
                    row = parse(app._format_other_card_text(snapshot(
                        name, command=cmd, category=PaneCategory.OTHER)))
                    self.assertEqual(row.plain, f" ○ 1:{name} (0)  {cmd}")
                    start = len(row.plain) - len(cmd)
                    self.assertIn("dim", covering_style(row, start))


class MountedTests(unittest.TestCase):
    """The real widgets: a `Static` that cannot parse its markup raises out of
    the app, so these also pin "no crash" for the card list and the header."""

    NAME = "agent-\\[bold]y"
    TITLE = "ends with \\"
    OTHER = "agent-[/]x"
    CMD = "cmd\\"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _snaps(self) -> dict[str, PaneSnapshot]:
        return {
            "%1": snapshot(self.NAME, content=""),
            "%2": snapshot(self.OTHER, pane_id="%2", command=self.CMD,
                           category=PaneCategory.OTHER),
        }

    def test_cards_render_user_text_literally(self):
        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(120, 30)) as pilot:
                wire(app, self.root, self.TITLE)
                app._snapshots = self._snaps()
                app._rebuild_pane_list()
                await pilot.pause()
                cards = {c.pane_id: c.render().plain
                         for c in app.query("#pane-list PaneCard")}
                self.assertEqual(set(cards), {"%1", "%2"})
                self.assertIn(f"1:{self.NAME} (0)", cards["%1"])
                self.assertEqual(cards["%1"].split("\n")[1],
                                 f"     t42: {self.TITLE}")
                self.assertEqual(cards["%2"],
                                 f" ○ 1:{self.OTHER} (0)  {self.CMD}")
                self.assertIsNone(app.return_code)

        asyncio.run(runner())

    def test_preview_header_renders_user_text_literally(self):
        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(120, 30)) as pilot:
                wire(app, self.root, self.TITLE)
                app._snapshots = self._snaps()
                # Empty content takes the `(empty)` branch: no render worker.
                app._focused_pane_id = "%1"
                header = app.query_one("#content-header")
                expected = f"Content Preview (1:{self.NAME}) t42: {self.TITLE}"

                app._active_zone = Zone.PANE_LIST
                app._update_content_preview()
                await pilot.pause()
                self.assertEqual(header.render().plain, expected)

                # PREVIEW zone appends the LIVE tag after the title: it must
                # still parse as a tag, not leak as text.
                app._active_zone = Zone.PREVIEW
                app._update_content_preview()
                await pilot.pause()
                self.assertEqual(header.render().plain, f"{expected} LIVE")
                self.assertIsNone(app.return_code)

        asyncio.run(runner())


if __name__ == "__main__":
    unittest.main(verbosity=2)
