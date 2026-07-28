"""Tests for the minimonitor `I` followed-agent Task Info shortcut (t1282).

Mock-based (no live tmux). The followed agent — the code agent sharing the
minimonitor's tmux window — is rendered in the static, non-focusable
``#mini-own-agent`` panel and excluded from the selectable card list, so the
focus-scoped ``i`` (``action_show_task_info``) can never resolve it. And because
``_auto_select_own_window`` always focuses a list card when one exists, a
"nothing focused" fallback on ``i`` would be dead code whenever another agent is
running. Hence the dedicated uppercase ``I``
(``action_show_own_task_info``), resolving through
``_find_own_agent_snapshot`` like ``k`` / ``n`` already do. Covers:

- binding registration for ``I`` (with the untouched ``i`` as negative control);
- ``I`` reaching the followed agent *while a different list card is focused* —
  the regression this task fixes;
- ``i`` precedence unchanged (focused card wins, own agent never substituted);
- the "no followed agent" and "no task ID" guards;
- the key-hints panel advertising ``I`` within the narrow pane's width budget.

Reference: tests/test_minimonitor_shadow_pick.py (t1152, shared app-stub style).

Run: python3 tests/test_minimonitor_own_task_info.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_core import PaneCategory, TaskInfo  # noqa: E402
from monitor.monitor_shared import TaskDetailDialog  # noqa: E402

# The minimonitor is a narrow side column: `_target_width` defaults to 40 and
# `#mini-key-hints` carries `padding: 0 1`, leaving this many usable columns.
_HINT_WIDTH_BUDGET = 38


def _task_info(task_id: str) -> TaskInfo:
    return TaskInfo(
        task_id=task_id,
        task_file=f"aitasks/t{task_id}_x.md",
        title=f"task {task_id}",
        priority="medium",
        effort="low",
        issue_type="bug",
        status="Implementing",
        body="body",
        plan_content=None,
    )


def _snap(pane_id: str, window_index: str, session: str = "s1"):
    """Minimal PaneSnapshot stand-in: only `.pane` fields are read here."""
    return SimpleNamespace(
        pane=SimpleNamespace(
            pane_id=pane_id,
            session_name=session,
            window_index=window_index,
            window_name=f"agent-w{window_index}",
            category=PaneCategory.AGENT,
        )
    )


class _FakeTaskCache:
    """Resolves a per-pane task id and returns a TaskInfo for known ids."""

    def __init__(self, pane_to_task: dict[str, str | None]) -> None:
        self._pane_to_task = pane_to_task
        self.invalidated: list[tuple[str, str]] = []

    def get_task_id_for_pane(self, pane):
        return self._pane_to_task.get(pane.pane_id)

    def invalidate(self, task_id, session_name=""):
        self.invalidated.append((task_id, session_name))

    def get_task_info(self, task_id, session_name=""):
        return _task_info(task_id)


def _mk_app(snapshots, pane_to_task, own_window_index="1"):
    """Real MiniMonitorApp with only the collaborators these actions touch."""
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._snapshots = {s.pane.pane_id: s for s in snapshots}
    app._task_cache = _FakeTaskCache(pane_to_task)
    app._session = "s1"
    app._own_window_index = own_window_index
    app.spy_notify: list = []
    app.spy_pushed: list = []
    app.notify = lambda msg, **kw: app.spy_notify.append(
        (msg, kw.get("severity", "information"))
    )
    app.push_screen = lambda screen, callback=None: app.spy_pushed.append(screen)
    return app


class TestOwnTaskInfoBinding(unittest.TestCase):
    def test_uppercase_i_bound_to_own_task_info(self):
        pairs = {(b.key, b.action) for b in mm.MiniMonitorApp.BINDINGS}
        self.assertIn(("I", "show_own_task_info"), pairs)

    def test_lowercase_i_binding_untouched(self):
        """Negative control: the focused-card shortcut keeps its own action."""
        pairs = {(b.key, b.action) for b in mm.MiniMonitorApp.BINDINGS}
        self.assertIn(("i", "show_task_info"), pairs)

    def test_key_hints_advertise_uppercase_i(self):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        hints = None
        for widget in mm.MiniMonitorApp.compose(app):
            if getattr(widget, "id", None) == "mini-key-hints":
                hints = widget.render().plain
        self.assertIsNotNone(hints, "compose yielded no #mini-key-hints widget")
        self.assertIn("I:info", hints)
        too_wide = [ln for ln in hints.split("\n") if len(ln) > _HINT_WIDTH_BUDGET]
        self.assertEqual(too_wide, [], f"hint lines exceed {_HINT_WIDTH_BUDGET} cols")


class TestShowOwnTaskInfo(unittest.TestCase):
    def test_reaches_followed_agent_while_other_card_focused(self):
        """The regression: a list card is focused, yet `I` targets the own agent."""
        own = _snap("%own", window_index="1")
        other = _snap("%other", window_index="7")
        app = _mk_app([own, other], {"%own": "1282", "%other": "999"})

        card = mm.MiniPaneCard("%other", "other agent")
        with patch.object(
            mm.MiniMonitorApp, "focused", new_callable=PropertyMock
        ) as focused:
            focused.return_value = card
            # Sanity: focus really does resolve the *other* card right now.
            self.assertEqual(app._get_focused_pane_id(), "%other")
            app.action_show_own_task_info()

        self.assertEqual(len(app.spy_pushed), 1)
        dialog = app.spy_pushed[0]
        self.assertIsInstance(dialog, TaskDetailDialog)
        self.assertEqual(dialog._info.task_id, "1282")
        self.assertEqual(app.spy_notify, [])

    def test_reaches_followed_agent_with_no_focus(self):
        own = _snap("%own", window_index="1")
        app = _mk_app([own], {"%own": "1282"})

        with patch.object(
            mm.MiniMonitorApp, "focused", new_callable=PropertyMock
        ) as focused:
            focused.return_value = None
            app.action_show_own_task_info()

        self.assertEqual(len(app.spy_pushed), 1)
        self.assertEqual(app.spy_pushed[0]._info.task_id, "1282")

    def test_refreshes_cache_before_showing(self):
        own = _snap("%own", window_index="1")
        app = _mk_app([own], {"%own": "1282"})
        app.action_show_own_task_info()
        self.assertEqual(app._task_cache.invalidated, [("1282", "s1")])

    def test_warns_when_no_followed_agent(self):
        other = _snap("%other", window_index="7")
        app = _mk_app([other], {"%other": "999"}, own_window_index="1")
        app.action_show_own_task_info()
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(
            app.spy_notify, [("No followed agent in this window", "warning")]
        )

    def test_warns_when_followed_pane_has_no_task_id(self):
        own = _snap("%own", window_index="1")
        app = _mk_app([own], {"%own": None})
        app.action_show_own_task_info()
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(
            app.spy_notify, [("No task ID in window name", "warning")]
        )


class TestShowTaskInfoUnchanged(unittest.TestCase):
    def test_focused_card_wins_over_followed_agent(self):
        own = _snap("%own", window_index="1")
        other = _snap("%other", window_index="7")
        app = _mk_app([own, other], {"%own": "1282", "%other": "999"})

        card = mm.MiniPaneCard("%other", "other agent")
        with patch.object(
            mm.MiniMonitorApp, "focused", new_callable=PropertyMock
        ) as focused:
            focused.return_value = card
            app.action_show_task_info()

        self.assertEqual(len(app.spy_pushed), 1)
        self.assertEqual(app.spy_pushed[0]._info.task_id, "999")

    def test_warns_when_nothing_focused(self):
        own = _snap("%own", window_index="1")
        app = _mk_app([own], {"%own": "1282"})

        with patch.object(
            mm.MiniMonitorApp, "focused", new_callable=PropertyMock
        ) as focused:
            focused.return_value = None
            app.action_show_task_info()

        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(
            app.spy_notify, [("Focus an agent pane first", "warning")]
        )


if __name__ == "__main__":
    unittest.main()
