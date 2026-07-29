"""Render-level tests for the COMPLETED agent status (t1322).

Adds the fourth state to the monitor/minimonitor status ladder:
``PROMPT > COMPLETED > IDLE > active``, as bold magenta / bold dodger_blue1 /
yellow / green. Before t1322 a finished agent read ``IDLE 412s`` in yellow —
indistinguishable from one that had hung.

Follows the conventions established by ``test_monitor_shadow_status.py``:
colour is asserted on the **raw markup** string (``.plain`` strips styles, so it
proves glyph presence and ordering only), and app instances are constructed
unmounted with duck-typed collaborators where the DOM is not needed.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MonitorApp only renames its tmux window when constructed with
# rename_window=True, but scrub the ambient tmux env so on_mount takes the
# deterministic not-inside-tmux path regardless of where the suite runs.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.text import Text  # noqa: E402

from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TaskInfo, TmuxPaneInfo,
    task_id_from_window_name,
)
from monitor.monitor_shared import (  # noqa: E402
    SHADOW_GLYPH, format_pane_status, format_shadow_glyph, format_state_dot,
    is_task_completed,
)
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402


def _pane(pane_id, window_name="agent-pick-42", category=PaneCategory.AGENT):
    idx = int(pane_id.lstrip("%"))
    return TmuxPaneInfo(
        window_index=str(idx), window_name=window_name, pane_index="0",
        pane_id=pane_id, pane_pid=1000 + idx, current_command="bash",
        width=80, height=24, category=category, session_name="demo",
    )


def _snapshot(pane, *, awaiting=False, idle=False) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane, content="x", timestamp=0.0,
        idle_seconds=412.0 if idle else 0.0, is_idle=idle,
        awaiting_input=awaiting,
        awaiting_input_kind="claude_proceed" if awaiting else "",
    )


def _info(status="Done", task_file_abs="/r/aitasks/t42_x.md") -> TaskInfo:
    return TaskInfo(
        task_id="42", task_file="aitasks/t42_x.md", title="Some task",
        priority="medium", effort="medium", issue_type="feature",
        status=status, body="", plan_content=None,
        task_file_abs=task_file_abs,
    )


class _FakeMonitor:
    """Duck-typed monitor: compare-mode + shadow lookup only."""

    multi_session = False

    def __init__(self, shadow_by_followed=None):
        self._shadow = shadow_by_followed or {}

    def get_compare_mode(self, pane_id):
        return "stripped"

    def is_compare_mode_overridden(self, pane_id):
        return False

    def get_shadow_snapshot(self, followed_pane_id):
        return self._shadow.get(followed_pane_id)

    def control_state(self):
        from monitor.monitor_core import TmuxControlState
        return TmuxControlState.CONNECTED


class _FakeTaskCache:
    """Resolves every agent pane to one task id with a fixed TaskInfo."""

    def __init__(self, info, task_id="42"):
        self._info = info
        self._task_id = task_id

    def get_task_id_for_pane(self, pane):
        return self._task_id

    def get_task_info(self, task_id, session_name=""):
        return self._info

    def update_session_mapping(self, mapping):
        pass


class IsTaskCompletedTests(unittest.TestCase):
    """The predicate: both archive signals, because status is set BEFORE move."""

    def test_status_done(self):
        self.assertTrue(is_task_completed(_info(status="Done")))

    def test_archived_path_before_status_flip(self):
        self.assertTrue(is_task_completed(
            _info(status="Ready", task_file_abs="/r/aitasks/archived/t42_x.md")
        ))

    def test_active_ready_is_not_completed(self):
        self.assertFalse(is_task_completed(_info(status="Ready")))

    def test_none_is_not_completed(self):
        self.assertFalse(is_task_completed(None))

    def test_implementing_in_active_dir_is_not_completed(self):
        self.assertFalse(is_task_completed(_info(status="Implementing")))


class WindowNameTaskIdTests(unittest.TestCase):
    """Every window name the framework's launch sites actually emit.

    ``agent-resume-<id>`` was added in t1322: the board launches resumed agents
    into those windows and they previously matched nothing, so a resumed agent
    had no task id at all — no title, no gate summary, and no way to ever reach
    COMPLETED.
    """

    def test_launcher_emitted_names_resolve(self):
        cases = {
            # monitor_app.py:2507,2587 / minimonitor_app.py:1016 / board:6989,7161
            "agent-pick-42": "42",
            "agent-pick-635_3": "635_3",
            # codebrowser/history_screen.py:430
            "agent-qa-42": "42",
            "agent-qa-100_1": "100_1",
            # board/aitask_board.py:7918 — the t1322 addition
            "agent-resume-1322": "1322",
            "agent-resume-1322_4": "1322_4",
        }
        for name, expected in cases.items():
            with self.subTest(window_name=name):
                self.assertEqual(task_id_from_window_name(name), expected)

    def test_taskless_agent_windows_stay_none(self):
        """Prefixes that carry no task id must not start resolving."""
        for name in (
            "agent-explore-5",       # lib/tui_switcher.py:1112
            "agent-raw-5",           # lib/tui_switcher.py:1257
            "agent-pick-42-2",       # unique_window_name() collision suffix
            "agent-pick-",
            "agent-pick-abc",
            "shadow-agent-pick-42",
            "bash",
        ):
            with self.subTest(window_name=name):
                self.assertIsNone(task_id_from_window_name(name))


class LadderTests(unittest.TestCase):
    """The four states, in precedence order, on the raw markup."""

    def test_active(self):
        s = _snapshot(_pane("%1"))
        self.assertEqual(format_state_dot(s, False), "[green]●[/]")
        self.assertEqual(format_pane_status(s, False), "[green]Active[/]")

    def test_idle(self):
        s = _snapshot(_pane("%1"), idle=True)
        self.assertEqual(format_state_dot(s, False), "[yellow]●[/]")
        self.assertEqual(format_pane_status(s, False), "[yellow]IDLE 412s[/]")

    def test_completed(self):
        s = _snapshot(_pane("%1"), idle=True)
        self.assertEqual(format_state_dot(s, True), "[bold dodger_blue1]●[/]")
        self.assertEqual(format_pane_status(s, True), "[bold dodger_blue1]DONE 412s[/]")

    def test_prompt_outranks_completed(self):
        """A completed agent parked on its final prompt still reads PROMPT."""
        s = _snapshot(_pane("%1"), awaiting=True, idle=True)
        self.assertEqual(format_state_dot(s, True), "[bold magenta]●[/]")
        self.assertEqual(format_pane_status(s, True), "[bold magenta]PROMPT 412s[/]")

    def test_completed_outranks_idle(self):
        s = _snapshot(_pane("%1"), idle=True)
        self.assertIn("dodger_blue1", format_state_dot(s, True))
        self.assertNotIn("yellow", format_state_dot(s, True))

    def test_defaults_preserve_pre_t1322_output(self):
        """Byte-identity negative control for the un-completed path."""
        for kwargs in ({}, {"idle": True}, {"awaiting": True}):
            s = _snapshot(_pane("%1"), **kwargs)
            self.assertEqual(format_state_dot(s), format_state_dot(s, False))
            self.assertEqual(format_pane_status(s), format_pane_status(s, False))

    def test_shadow_glyph_never_renders_completed(self):
        """A shadow is advisory and has no task, so it can never be blue."""
        shadow = _snapshot(_pane("%9"), idle=True)
        self.assertEqual(format_shadow_glyph(shadow), f"[yellow]{SHADOW_GLYPH}[/]")
        self.assertNotIn("dodger_blue1", format_shadow_glyph(shadow))


class CardRenderTests(unittest.TestCase):
    """Both card builders, driven off the per-tick completed set."""

    def _monitor_app(self, completed_ids, info=None):
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        app._monitor = _FakeMonitor()
        app._task_cache = _FakeTaskCache(info if info is not None else _info())
        app._completed_pane_ids = frozenset(completed_ids)
        return app

    def _mini_app(self, completed_ids, info=None):
        app = MiniMonitorApp(session="demo", project_root=REPO_ROOT)
        app._monitor = _FakeMonitor()
        app._task_cache = _FakeTaskCache(info if info is not None else _info())
        app._completed_pane_ids = frozenset(completed_ids)
        return app

    def test_monitor_card_shows_completed(self):
        app = self._monitor_app({"%1"})
        row = app._format_agent_card_text(_snapshot(_pane("%1"), idle=True))
        self.assertIn("[bold dodger_blue1]●[/]", row)
        self.assertIn("[bold dodger_blue1]DONE 412s[/]", row)

    def test_monitor_card_idle_when_not_in_set(self):
        app = self._monitor_app(set())
        row = app._format_agent_card_text(_snapshot(_pane("%1"), idle=True))
        self.assertIn("[yellow]●[/]", row)
        self.assertIn("[yellow]IDLE 412s[/]", row)

    def test_mini_card_shows_completed(self):
        app = self._mini_app({"%1"})
        row = app._agent_card_text(_snapshot(_pane("%1"), idle=True))
        self.assertIn("[bold dodger_blue1]●[/]", row)
        self.assertIn("[bold dodger_blue1]DONE 412s[/]", row)

    def test_mini_card_idle_when_not_in_set(self):
        app = self._mini_app(set())
        row = app._agent_card_text(_snapshot(_pane("%1"), idle=True))
        self.assertIn("[yellow]●[/]", row)

    def test_set_is_sole_source_not_the_card_lookup(self):
        """The set wins over the builder's own get_task_info result.

        Guards the one-tick disagreement: an archive landing between
        _compute_completed_panes and the card build would flip the identity gate
        and leave the badge contradicting the session bar and auto-switch.
        """
        # Task on disk says Done, but the set (this tick) says not completed.
        app = self._monitor_app(set(), info=_info(status="Done"))
        row = app._format_agent_card_text(_snapshot(_pane("%1"), idle=True))
        self.assertIn("[yellow]IDLE 412s[/]", row)
        self.assertNotIn("dodger_blue1", row)

        # And the converse: set says completed, task on disk still Ready.
        app2 = self._monitor_app({"%1"}, info=_info(status="Ready"))
        row2 = app2._format_agent_card_text(_snapshot(_pane("%1"), idle=True))
        self.assertIn("[bold dodger_blue1]DONE 412s[/]", row2)

    def test_mounted_card_renders_completed_dot(self):
        """The composited widget, not just the builder's return string."""
        async def runner():
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                app._monitor = _FakeMonitor()
                app._task_cache = _FakeTaskCache(_info())
                app._completed_pane_ids = frozenset({"%1"})
                app._snapshots = {"%1": _snapshot(_pane("%1"), idle=True)}
                app._focused_pane_id = "%1"
                app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#pane-list PaneCard"))
                self.assertEqual(len(cards), 1)
                rendered = cards[0].render()
                plain = getattr(
                    rendered, "plain", Text.from_markup(str(rendered)).plain
                )
                self.assertIn("●", plain)
                self.assertIn("DONE", plain)
                self.assertNotIn("IDLE", plain)

        asyncio.run(runner())

    def test_agents_header_carries_legend(self):
        app = self._monitor_app(set())
        header = app._agents_header_text(3)
        self.assertIn("CODE AGENTS (3)", header)
        for word in ("active", "prompt", "idle", "done"):
            self.assertIn(word, header)
        self.assertIn("[bold dodger_blue1]●[/]", header)


class CounterPartitionTests(unittest.TestCase):
    """The bars must partition agents on the same ladder as the badges."""

    def _counts(self, app_cls, snapshots, completed_ids):
        """Drive the real bar builder and read the three counters back."""
        app = app_cls(session="demo", project_root=REPO_ROOT)
        app._monitor = _FakeMonitor()
        app._task_cache = _FakeTaskCache(_info())
        app._snapshots = {s.pane.pane_id: s for s in snapshots}
        app._completed_pane_ids = frozenset(completed_ids)

        captured = {}

        class _Bar:
            def update(self, text):
                captured["text"] = text

        app.query_one = lambda *a, **k: _Bar()
        if app_cls is MonitorApp:
            app._auto_switch = False
            app._rebuild_session_bar()
        else:
            app._session = "demo"
            app._rebuild_session_bar()
        return captured["text"]

    def test_completed_not_counted_as_idle(self):
        snaps = [_snapshot(_pane("%1"), idle=True), _snapshot(_pane("%2"), idle=True)]
        text = self._counts(MonitorApp, snaps, {"%1"})
        self.assertIn("1 done", text)
        self.assertIn("1 idle", text)

    def test_completed_and_awaiting_counts_once_as_awaiting(self):
        """The double-count bug: awaiting must exclude it from done."""
        snaps = [_snapshot(_pane("%1"), awaiting=True, idle=True)]
        text = self._counts(MonitorApp, snaps, {"%1"})
        self.assertIn("1 awaiting", text)
        self.assertNotIn("done", text)
        self.assertNotIn("idle", text)

    def test_mini_bar_partitions_identically(self):
        snaps = [
            _snapshot(_pane("%1"), idle=True),
            _snapshot(_pane("%2"), awaiting=True, idle=True),
            _snapshot(_pane("%3"), idle=True),
        ]
        text = self._counts(MiniMonitorApp, snaps, {"%1", "%2"})
        # %1 done, %2 awaiting (not done), %3 idle — one bucket each.
        self.assertIn("1 awaiting", text)
        self.assertIn("1d", text)
        self.assertIn("1 idle", text)


class AutoSwitchTests(unittest.TestCase):
    """A finished agent is idle forever and must never capture focus."""

    def _app(self, snapshots, completed_ids, focused):
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        app._monitor = _FakeMonitor()
        app._task_cache = _FakeTaskCache(_info())
        app._snapshots = {s.pane.pane_id: s for s in snapshots}
        app._completed_pane_ids = frozenset(completed_ids)
        app._focused_pane_id = focused
        return app

    def test_never_switches_to_a_completed_pane(self):
        active = _snapshot(_pane("%1"))
        done = _snapshot(_pane("%2"), idle=True)
        app = self._app([active, done], {"%2"}, "%1")
        self.assertFalse(app._maybe_auto_switch())
        self.assertEqual(app._focused_pane_id, "%1")

    def test_still_switches_to_a_genuinely_idle_pane(self):
        """Negative control: the filter must not disable auto-switch outright."""
        active = _snapshot(_pane("%1"))
        idle = _snapshot(_pane("%2"), idle=True)
        app = self._app([active, idle], set(), "%1")
        self.assertTrue(app._maybe_auto_switch())
        self.assertEqual(app._focused_pane_id, "%2")

    def test_does_not_keep_a_completed_focused_pane(self):
        """A completed current pane needs no attention — move on to the idle one."""
        done = _snapshot(_pane("%1"), idle=True)
        idle = _snapshot(_pane("%2"), idle=True)
        app = self._app([done, idle], {"%1"}, "%1")
        self.assertTrue(app._maybe_auto_switch())
        self.assertEqual(app._focused_pane_id, "%2")


if __name__ == "__main__":
    unittest.main(verbosity=1)
