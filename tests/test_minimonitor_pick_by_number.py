"""Tests for the minimonitor `p` pick-a-task-by-number command (t1310).

`n` can only ever launch the followed pane's next *Ready sibling*, so acting on
the task numbers an agent reports at the end of a run meant detouring through
`ait board`. `p` prompts for a number, shows that task's details with an opt-in
"kill followed agent" checkbox, and launches through the same `_launch_pick`
that `n` uses.

Covers, in the order the flow runs:

- the binding, with `n` as a negative control, and the key-hints budget;
- the entry-level `Monitor not ready` guard — without it the user completes both
  dialogs and `_launch_pick`'s silent guard makes confirmation appear to do
  nothing;
- id normalization/validation *before* any lookup (the id is interpolated into
  a `Path.glob` pattern and passed to the pick command);
- eligibility warnings (`not Ready` / `blocked by`) and the `Launch anyway`
  relabel, with a Ready-and-unblocked negative control;
- `blocking_dependencies` against a REAL `TaskInfoCache` over real files,
  including the staleness regression and a `refresh=False` negative control;
- the session-scoped already-running scan (the cross-project false positive);
- checkbox → kill wiring, including the non-launch dismissals that must not
  kill;
- narrow rendering at 40 cols, asserted on composited screen text (a region-fit
  check passes on an ellipsised checkbox label) with a `.narrow`-removal
  negative control.

Reference: tests/test_minimonitor_own_task_info.py (app-stub style),
tests/test_agent_command_dialog_narrow.py (narrow render harness),
tests/test_concern_picker_modal.py (`_screen_text`).

Run: python3 tests/test_minimonitor_pick_by_number.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
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

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Button, Checkbox, Input, Label  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, TaskInfo, TaskInfoCache,
)
from monitor.monitor_shared import (  # noqa: E402
    TaskNumberInputModal, TaskPickConfirmDialog,
)

_HINT_WIDTH_BUDGET = 38
_ROOT = Path("/proj/alpha")


def _task_info(task_id: str, status: str = "Ready", depends=None) -> TaskInfo:
    return TaskInfo(
        task_id=task_id,
        task_file=f"aitasks/t{task_id}_x.md",
        title=f"task {task_id}",
        priority="medium",
        effort="low",
        issue_type="feature",
        status=status,
        body="body",
        plan_content=None,
        depends=list(depends or []),
    )


def _snap(pane_id: str, window_index: str = "1", session: str = "s1",
          window_name: str | None = None):
    return SimpleNamespace(
        pane=SimpleNamespace(
            pane_id=pane_id,
            session_name=session,
            window_index=window_index,
            window_name=window_name or f"agent-pick-{window_index}",
            category=PaneCategory.AGENT,
        )
    )


class _FakeTaskCache:
    """Resolves ids from a dict; records lookups so tests can prove a rejected
    id never reached resolution."""

    def __init__(self, infos: dict[str, TaskInfo], pane_to_task=None) -> None:
        self._infos = infos
        self._pane_to_task = pane_to_task or {}
        self.lookups: list[str] = []
        self.invalidated: list[str] = []
        self.blocking: list[str] = []

    def get_task_id_for_pane(self, pane):
        return self._pane_to_task.get(pane.pane_id)

    def get_task_info(self, task_id, session_name=""):
        self.lookups.append(task_id)
        return self._infos.get(task_id)

    def invalidate(self, task_id, session_name=""):
        self.invalidated.append(task_id)

    def blocking_dependencies(self, info, session_name="", *, refresh=True):
        return list(self.blocking)


class _FakeMonitor:
    def __init__(self) -> None:
        self.killed: list[str] = []

    def get_session_to_project_mapping(self):
        return {"s1": _ROOT}

    def kill_agent_pane_smart(self, pane_id):
        self.killed.append(pane_id)
        return (True, False)


def _mk_app(infos, snapshots=(), pane_to_task=None, monitor=True):
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._snapshots = {s.pane.pane_id: s for s in snapshots}
    app._task_cache = _FakeTaskCache(infos, pane_to_task)
    app._session = "s1"
    app._own_window_index = "1"
    app._project_root = Path("/proj/fallback")
    app._focused_pane_id = None
    app._monitor = _FakeMonitor() if monitor else None
    app.spy_notify = []
    app.spy_pushed = []
    app.spy_launch = []
    app.notify = lambda msg, **kw: app.spy_notify.append(
        (msg, kw.get("severity", "information"))
    )
    app.push_screen = lambda screen, callback=None: app.spy_pushed.append(
        (screen, callback)
    )
    app._launch_pick = lambda tid, root, kill: app.spy_launch.append(
        (tid, root, kill)
    )
    return app


def _enter(app, value):
    """Run the action, then feed `value` into the number modal's callback."""
    app.action_pick_task_by_number()
    if not app.spy_pushed:
        return None
    _screen, callback = app.spy_pushed[0]
    callback(value)
    if len(app.spy_pushed) < 2:
        return None
    return app.spy_pushed[1]


# -- Binding / hints ---------------------------------------------------------

class BindingTests(unittest.TestCase):
    def test_p_bound_to_pick_task_by_number(self):
        pairs = {(b.key, b.action) for b in mm.MiniMonitorApp.BINDINGS}
        self.assertIn(("p", "pick_task_by_number"), pairs)

    def test_n_binding_untouched(self):
        """Negative control: the sibling-pick shortcut keeps its own action."""
        pairs = {(b.key, b.action) for b in mm.MiniMonitorApp.BINDINGS}
        self.assertIn(("n", "pick_next_for_own"), pairs)

    def test_key_hints_advertise_p_within_budget(self):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        hints = None
        for widget in mm.MiniMonitorApp.compose(app):
            if getattr(widget, "id", None) == "mini-key-hints":
                hints = widget.render().plain
        self.assertIsNotNone(hints)
        self.assertIn("p:pick", hints)
        too_wide = [ln for ln in hints.split("\n") if len(ln) > _HINT_WIDTH_BUDGET]
        self.assertEqual(too_wide, [], f"hint lines exceed {_HINT_WIDTH_BUDGET} cols")


# -- Entry guard -------------------------------------------------------------

class MonitorReadyGuardTests(unittest.TestCase):
    def test_monitor_not_ready_warns_and_pushes_nothing(self):
        """Guarding only inside _launch_pick would let the user complete both
        dialogs and then silently do nothing."""
        app = _mk_app({"1310": _task_info("1310")}, monitor=False)
        app.action_pick_task_by_number()
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(app.spy_notify, [("Monitor not ready", "warning")])

    def test_with_monitor_the_input_modal_is_pushed(self):
        """Negative control for the guard above."""
        app = _mk_app({"1310": _task_info("1310")})
        app.action_pick_task_by_number()
        self.assertEqual(len(app.spy_pushed), 1)
        self.assertIsInstance(app.spy_pushed[0][0], TaskNumberInputModal)
        self.assertEqual(app.spy_notify, [])


# -- Validation --------------------------------------------------------------

class ValidationTests(unittest.TestCase):
    def _run(self, raw):
        app = _mk_app({"1310": _task_info("1310"), "1310_2": _task_info("1310_2")})
        pushed = _enter(app, raw)
        return app, pushed

    def test_accepted_forms_resolve(self):
        for raw, expected in [
            ("1310", "1310"),
            ("t1310", "1310"),
            ("  1310  ", "1310"),
            ("1310_2", "1310_2"),
        ]:
            with self.subTest(raw=raw):
                app, pushed = self._run(raw)
                self.assertIsNotNone(pushed, f"{raw!r} should have resolved")
                self.assertEqual(pushed[0]._info.task_id, expected)

    def test_rejected_forms_warn_without_touching_resolution(self):
        """Rejection must happen before `get_task_info`: the id is interpolated
        into a glob pattern and into the launched pick command."""
        for raw in ["", "   ", "abc", "12*", "1[0-9]", "13-10", "1;id", "1_2_3"]:
            with self.subTest(raw=raw):
                app, pushed = self._run(raw)
                self.assertIsNone(pushed, f"{raw!r} should not have resolved")
                self.assertEqual(app._task_cache.lookups, [])
                self.assertEqual(app.spy_launch, [])
                if raw.strip():
                    self.assertEqual(len(app.spy_notify), 1)
                    self.assertEqual(app.spy_notify[0][1], "warning")

    def test_unknown_task_warns_and_opens_no_confirm_dialog(self):
        app = _mk_app({"1310": _task_info("1310")})
        pushed = _enter(app, "9999")
        self.assertIsNone(pushed)
        self.assertEqual(app.spy_notify, [("Task t9999 not found", "warning")])

    def test_target_is_invalidated_before_resolution(self):
        app = _mk_app({"1310": _task_info("1310")})
        _enter(app, "1310")
        self.assertEqual(app._task_cache.invalidated, ["1310"])


# -- Eligibility -------------------------------------------------------------

class EligibilityTests(unittest.TestCase):
    def _dialog(self, status="Ready", blocking=()):
        app = _mk_app({"1310": _task_info("1310", status=status)})
        app._task_cache.blocking = list(blocking)
        pushed = _enter(app, "1310")
        self.assertIsNotNone(pushed)
        return pushed[0]

    def test_ready_and_unblocked_has_no_warning(self):
        """Negative control: proves the warnings below are conditional."""
        dialog = self._dialog()
        self.assertFalse(dialog.has_eligibility_warning)
        self.assertEqual(dialog._eligibility_lines(), [])

    def test_non_ready_status_warns(self):
        dialog = self._dialog(status="Done")
        self.assertTrue(dialog.has_eligibility_warning)
        self.assertIn("not Ready to pick", dialog._eligibility_lines()[0])

    def test_blocked_dependencies_warn(self):
        dialog = self._dialog(blocking=["1200", "900"])
        self.assertTrue(dialog.has_eligibility_warning)
        self.assertIn("⛔ blocked by t1200 t900", dialog._eligibility_lines())

    def test_both_conditions_produce_both_lines(self):
        dialog = self._dialog(status="Postponed", blocking=["1200"])
        self.assertEqual(len(dialog._eligibility_lines()), 2)


# -- blocking_dependencies (real cache, real files) --------------------------

def _write_task(tasks_dir: Path, task_id: str, status: str, depends=()) -> None:
    if "_" in task_id:
        parent, child = task_id.split("_", 1)
        d = tasks_dir / f"t{parent}"
        name = f"t{parent}_{child}_x.md"
    else:
        d = tasks_dir
        name = f"t{task_id}_x.md"
    d.mkdir(parents=True, exist_ok=True)
    dep_line = "[" + ", ".join(str(x) for x in depends) + "]"
    (d / name).write_text(
        f"---\nstatus: {status}\ndepends: {dep_line}\n---\n\n# task {task_id}\n",
        encoding="utf-8",
    )


class BlockingDependenciesTests(unittest.TestCase):
    """Exercises the real TaskInfoCache — a stub cannot show the staleness bug."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.tasks = self.root / "aitasks"
        self.tasks.mkdir(parents=True)
        self.cache = TaskInfoCache(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def _info(self, task_id):
        info = self.cache.get_task_info(task_id)
        self.assertIsNotNone(info, f"t{task_id} should resolve")
        return info

    def test_no_dependencies(self):
        _write_task(self.tasks, "1310", "Ready")
        self.assertEqual(self.cache.blocking_dependencies(self._info("1310")), [])

    def test_done_dependency_is_not_blocking(self):
        _write_task(self.tasks, "1200", "Done")
        _write_task(self.tasks, "1310", "Ready", depends=[1200])
        self.assertEqual(self.cache.blocking_dependencies(self._info("1310")), [])

    def test_ready_dependency_is_blocking(self):
        _write_task(self.tasks, "1200", "Ready")
        _write_task(self.tasks, "1310", "Ready", depends=[1200])
        self.assertEqual(self.cache.blocking_dependencies(self._info("1310")), ["1200"])

    def test_unresolvable_dependency_is_blocking(self):
        """Fail-closed: a dangling id must be visible, not silently satisfied."""
        _write_task(self.tasks, "1310", "Ready", depends=[4242])
        self.assertEqual(self.cache.blocking_dependencies(self._info("1310")), ["4242"])

    def test_depends_normalized_from_t_prefixed_entries(self):
        _write_task(self.tasks, "1200", "Done")
        _write_task(self.tasks, "1310", "Ready", depends=["t1200"])
        self.assertEqual(self._info("1310").depends, ["1200"])
        self.assertEqual(self.cache.blocking_dependencies(self._info("1310")), [])

    def test_stale_cached_dependency_is_refreshed(self):
        """The regression: this cache is process-lifetime in the minimonitor, so
        a dependency completing while the TUI is open must not keep reporting
        the target as blocked."""
        _write_task(self.tasks, "1200", "Ready")
        _write_task(self.tasks, "1310", "Ready", depends=[1200])
        info = self._info("1310")
        self.assertEqual(self.cache.blocking_dependencies(info), ["1200"])

        _write_task(self.tasks, "1200", "Done")  # sibling agent finished
        self.assertEqual(self.cache.blocking_dependencies(info), [])

    def test_negative_control_refresh_forces_reresolve(self):
        """Proves the test above actually exercises the cache.

        Rewritten for t1322: the cache is now identity-keyed, so a dependency
        rewritten on disk is picked up even with ``refresh=False`` — the old
        mechanism (rewrite the file, assert the stale answer persists) no longer
        discriminates and would just re-assert the new freshness behaviour.

        The distinction ``refresh`` still makes is whether the entry is
        force-invalidated, so measure that directly over an **unchanged** file:
        ``refresh=False`` serves the cached entry (no extra ``_resolve``),
        ``refresh=True`` re-resolves. A run where both counts were equal would
        mean the cache was never populated.
        """
        _write_task(self.tasks, "1200", "Ready")
        _write_task(self.tasks, "1310", "Ready", depends=[1200])
        info = self._info("1310")

        resolves = {"n": 0}
        orig = TaskInfoCache._resolve

        def counting(inner_self, *a, **k):
            resolves["n"] += 1
            return orig(inner_self, *a, **k)

        TaskInfoCache._resolve = counting
        self.addCleanup(setattr, TaskInfoCache, "_resolve", orig)

        # Populate the dependency's entry.
        self.assertEqual(self.cache.blocking_dependencies(info), ["1200"])
        after_first = resolves["n"]
        self.assertGreater(after_first, 0, "cache was never populated")

        # Unchanged file + refresh=False => served from cache, no re-resolve.
        self.assertEqual(
            self.cache.blocking_dependencies(info, refresh=False), ["1200"]
        )
        self.assertEqual(resolves["n"], after_first)

        # refresh=True => forced invalidation, so a re-resolve happens.
        self.assertEqual(self.cache.blocking_dependencies(info), ["1200"])
        self.assertGreater(resolves["n"], after_first)


class TaskInfoDefaultTests(unittest.TestCase):
    def test_depends_defaults_to_empty(self):
        """The keyword set used by the pre-existing test stubs must still
        construct a TaskInfo."""
        info = TaskInfo(
            task_id="1", task_file="f", title="t", priority="p", effort="e",
            issue_type="bug", status="Implementing", body="b", plan_content=None,
        )
        self.assertEqual(info.depends, [])


# -- Already-running scan ----------------------------------------------------

class AlreadyRunningScanTests(unittest.TestCase):
    def test_warns_for_agent_in_the_same_session(self):
        running = _snap("%run", window_index="3", session="s1",
                        window_name="agent-pick-1310")
        app = _mk_app({"1310": _task_info("1310")}, snapshots=[running],
                      pane_to_task={"%run": "1310"})
        pushed = _enter(app, "1310")
        self.assertIsNotNone(pushed)
        self.assertIn("already running", pushed[0]._already_running)
        self.assertIn("window 3:agent-pick-1310", pushed[0]._already_running)

    def test_ignores_same_id_in_another_session(self):
        """The cross-project false positive: task ids come from the window name
        alone, so t1310 in another project would otherwise match."""
        other = _snap("%other", window_index="3", session="s2",
                      window_name="agent-pick-1310")
        app = _mk_app({"1310": _task_info("1310")}, snapshots=[other],
                      pane_to_task={"%other": "1310"})
        pushed = _enter(app, "1310")
        self.assertIsNotNone(pushed)
        self.assertIsNone(pushed[0]._already_running)

    def test_ignores_non_agent_panes(self):
        helper = _snap("%tui", window_index="3", session="s1",
                       window_name="agent-pick-1310")
        helper.pane.category = PaneCategory.TUI
        app = _mk_app({"1310": _task_info("1310")}, snapshots=[helper],
                      pane_to_task={"%tui": "1310"})
        pushed = _enter(app, "1310")
        self.assertIsNone(pushed[0]._already_running)


# -- Confirm → launch --------------------------------------------------------

class ConfirmAndLaunchTests(unittest.TestCase):
    def _app_with_followed(self, target_status="Ready"):
        own = _snap("%own", window_index="1", session="s1",
                    window_name="agent-pick-77")
        app = _mk_app(
            {"1310": _task_info("1310", status=target_status),
             "77": _task_info("77", status="Done")},
            snapshots=[own],
            pane_to_task={"%own": "77"},
        )
        return app

    def test_ok_unchecked_does_not_kill_even_when_followed_task_is_done(self):
        """The checkbox decides, not n's task-status heuristic."""
        app = self._app_with_followed()
        _screen, callback = _enter(app, "1310")
        callback((True, False))
        self.assertEqual(app.spy_launch, [("1310", _ROOT, None)])

    def test_ok_checked_kills_the_followed_pane(self):
        app = self._app_with_followed()
        _screen, callback = _enter(app, "1310")
        callback((True, True))
        self.assertEqual(app.spy_launch, [("1310", _ROOT, "%own")])

    def test_cancel_launches_nothing(self):
        app = self._app_with_followed()
        _screen, callback = _enter(app, "1310")
        callback(None)
        self.assertEqual(app.spy_launch, [])

    def test_checkbox_omitted_when_no_followed_agent(self):
        app = _mk_app({"1310": _task_info("1310")})
        screen, callback = _enter(app, "1310")
        self.assertIsNone(screen._kill_target_label)
        callback((True, True))
        self.assertEqual(app.spy_launch, [("1310", app._project_root, None)])

    def test_followed_agent_gone_before_confirm_launches_without_kill(self):
        app = self._app_with_followed()
        _screen, callback = _enter(app, "1310")
        app._snapshots.clear()  # agent exited while the dialog was open
        callback((True, True))
        self.assertEqual(app.spy_launch, [("1310", _ROOT, None)])
        self.assertEqual(
            app.spy_notify,
            [("Followed agent no longer exists — launching without kill",
              "warning")],
        )

    def test_kill_label_names_the_followed_task_and_window(self):
        app = self._app_with_followed()
        screen, _cb = _enter(app, "1310")
        self.assertEqual(screen._kill_target_label, "t77 · Done · agent-pick-77")

    def test_followed_task_status_is_refreshed_before_being_shown(self):
        """The label is what the user reads before arming the kill; a stale
        `Done` would encourage killing an agent that is still working."""
        app = self._app_with_followed()
        _enter(app, "1310")
        self.assertIn("77", app._task_cache.invalidated)

    def test_unresolvable_followed_task_reports_unknown_status(self):
        own = _snap("%own", window_index="1", session="s1",
                    window_name="agent-pick-77")
        app = _mk_app({"1310": _task_info("1310")}, snapshots=[own],
                      pane_to_task={"%own": "77"})  # t77 not in the infos dict
        screen, _cb = _enter(app, "1310")
        self.assertEqual(screen._kill_target_label, "t77 · unknown · agent-pick-77")


class SharedLaunchImplementationTests(unittest.TestCase):
    """`p` must not grow its own copy of the launch path.

    Asserted behaviourally — drive both keys at the same target and compare the
    resulting `AgentCommandScreen` construction. An earlier version of this test
    scanned the module source with `inspect.getsource` and counting; that is
    brittle (it silently reads the wrong slice if the file changes after import)
    and it proves a textual property rather than the one that matters.
    """

    def _capture_launch_args(self, drive):
        constructed: list[tuple] = []

        class _FakeScreen:
            def __init__(self, *a, **k):
                constructed.append((a, k))
                self.full_command = a[1]

        own = _snap("%own", window_index="1", session="s1",
                    window_name="agent-pick-77")
        app = _mk_app(
            {"1310": _task_info("1310"), "77": _task_info("77", status="Done")},
            snapshots=[own], pane_to_task={"%own": "77"},
        )
        del app._launch_pick  # exercise the real implementation, not the spy
        with patch.object(mm, "resolve_dry_run_command", return_value="cmd --go"), \
             patch.object(mm, "resolve_agent_string", return_value="claudecode/x"), \
             patch.object(mm, "resolve_skill_profile", return_value="fast"), \
             patch.object(mm, "AgentCommandScreen", _FakeScreen):
            drive(app)
        self.assertEqual(len(constructed), 1)
        return constructed[0]

    def test_n_and_p_build_the_same_launch_dialog(self):
        def drive_n(app):
            app._launch_pick_for_own("1310", "%own", "77", "s1")

        def drive_p(app):
            _screen, callback = _enter(app, "1310")
            callback((True, False))

        self.assertEqual(
            self._capture_launch_args(drive_n),
            self._capture_launch_args(drive_p),
        )

    def test_launch_dialog_args_are_the_expected_ones(self):
        """Pins what that shared construction actually is, so the equality
        above cannot be satisfied by two identically-wrong paths."""
        args, kwargs = self._capture_launch_args(
            lambda app: app._launch_pick_for_own("1310", "%own", "77", "s1")
        )
        self.assertEqual(
            args, ("Pick Task t1310", "cmd --go", "/aitask-pick 1310")
        )
        self.assertEqual(kwargs["default_window_name"], "agent-pick-1310")
        self.assertEqual(kwargs["operation_args"], ["1310"])
        self.assertEqual(kwargs["project_root"], _ROOT)
        self.assertTrue(kwargs["narrow"])


# -- Narrow rendering --------------------------------------------------------

def _screen_text(app: App) -> str:
    """The COMPOSITED screen — a widget's render string would not reveal that
    Rich ellipsised the checkbox label on the way to the terminal."""
    return "\n".join(strip.text for strip in app.screen._compositor.render_strips())


def _flat(app: App) -> str:
    """`_screen_text` with the dialog's box-drawing chrome dropped and runs of
    whitespace collapsed, so an assertion is not defeated by a phrase wrapping
    across two 40-column lines (the borders would otherwise land mid-phrase).
    """
    text = "".join(
        " " if "▀" <= ch <= "▟" else ch for ch in _screen_text(app)
    )
    return " ".join(text.split())


class _ConfirmHost(App):
    def __init__(self, narrow: bool, status: str = "Done",
                 blocking=("1200",), already_running: str | None = None) -> None:
        super().__init__()
        self._narrow = narrow
        self._status = status
        self._blocking = list(blocking)
        self._already_running = already_running

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            TaskPickConfirmDialog(
                _task_info("1310", status=self._status),
                kill_target_label="t77 · Done · agent-pick-77",
                already_running=self._already_running,
                blocking=self._blocking,
                narrow=self._narrow,
            )
        )


class _InputHost(App):
    def __init__(self, narrow: bool) -> None:
        super().__init__()
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(TaskNumberInputModal(narrow=self._narrow))


def _drop_narrow_rules(css: str) -> str:
    """Remove whole `.narrow` rule blocks, leaving valid CSS behind.

    Dropping only the lines that mention `narrow` would orphan the declaration
    bodies and make Textual raise a TokenError — which would satisfy a naive
    `assertRaises` without ever proving anything about the layout.
    """
    out: list[str] = []
    skipping = False
    for line in css.splitlines():
        if skipping:
            if line.strip().endswith("}"):
                skipping = False
            continue
        if "narrow" in line:
            if not line.strip().endswith("}"):
                skipping = True
            continue
        out.append(line)
    return "\n".join(out)


def _assert_controls_inside(testcase, app, dialog_id):
    """Every control fits the dialog on BOTH axes.

    Checking only x is not enough: the minimonitor pane is as short as the tmux
    window, and a flow-laid confirm row overflows *downward* at ~20 rows — the
    buttons then sit below the dialog and never reach the screen at all.
    """
    dialog = app.screen.query_one(dialog_id)
    left, right = dialog.region.x, dialog.region.x + dialog.region.width
    top, bottom = dialog.region.y, dialog.region.y + dialog.region.height
    controls = [
        w for w in app.screen.query("Button, Checkbox, Input")
        if isinstance(w, (Button, Checkbox, Input))
    ]
    testcase.assertGreater(len(controls), 0)
    for widget in controls:
        if widget.region.width == 0 and widget.region.height == 0:
            continue
        testcase.assertGreaterEqual(
            widget.region.x, left,
            f"{widget!r} left {widget.region.x} < dialog left {left}")
        testcase.assertLessEqual(
            widget.region.x + widget.region.width, right,
            f"{widget!r} right overflows dialog right {right}")
        testcase.assertGreaterEqual(
            widget.region.y, top,
            f"{widget!r} top {widget.region.y} above dialog top {top}")
        testcase.assertLessEqual(
            widget.region.y + widget.region.height, bottom,
            f"{widget!r} bottom {widget.region.y + widget.region.height} "
            f"overflows dialog bottom {bottom}")


class NarrowRenderTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_narrow_class_applied_to_both_dialogs(self):
        async def runner():
            for host, cls in ((_ConfirmHost(True), TaskPickConfirmDialog),
                              (_InputHost(True), TaskNumberInputModal)):
                async with host.run_test(size=(40, 50)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    self.assertIsInstance(host.screen, cls)
                    self.assertIn("narrow", host.screen.classes)
        self._run(runner())

    def test_confirm_controls_fit_at_40_cols(self):
        """40x16 is included on purpose: the minimonitor pane is only as tall as
        the tmux window, which on a laptop is routinely under 25 rows."""
        async def runner():
            for size in ((40, 50), (40, 20), (40, 16)):
                app = _ConfirmHost(narrow=True)
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    _assert_controls_inside(self, app, "#task-detail-dialog")
        self._run(runner())

    def test_confirm_labels_visible_on_a_short_pane(self):
        """Region containment alone would not notice a control rendered
        off-screen; assert the composited text at the tightest size too."""
        async def runner():
            app = _ConfirmHost(narrow=True)
            async with app.run_test(size=(40, 20)) as pilot:
                await pilot.pause()
                await pilot.pause()
                text = _screen_text(app)
                for label in ("kill followed agent", "Launch anyway", "Cancel"):
                    self.assertIn(label, text)
        self._run(runner())

    def test_input_controls_fit_at_40_cols(self):
        async def runner():
            app = _InputHost(narrow=True)
            async with app.run_test(size=(40, 20)) as pilot:
                await pilot.pause()
                await pilot.pause()
                _assert_controls_inside(self, app, "#task-num-dialog")
        self._run(runner())

    def test_checkbox_and_button_labels_are_not_ellipsised(self):
        """The assertion a region-fit check cannot make: `ToggleButton` is
        `text-overflow: ellipsis`, so a clipped label still sits *inside* the
        dialog."""
        async def runner():
            app = _ConfirmHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                text = _screen_text(app)
                self.assertIn("kill followed agent", text)
                self.assertIn("Launch anyway", text)
                self.assertIn("Cancel", text)
                self.assertNotIn("…", text)
        self._run(runner())

    def test_warnings_reach_the_screen(self):
        """Each warning Static is its own widget — asserting one renders says
        nothing about the others."""
        async def runner():
            app = _ConfirmHost(
                narrow=True, status="Done", blocking=("1200",),
                already_running="⚠ t1310 is already running in this session, "
                                "window 3:agent-pick-1310",
            )
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                text = _flat(app)
                self.assertIn("not Ready to pick", text)
                self.assertIn("blocked by t1200", text)
                self.assertIn("already running", text)
                self.assertIn("t77", text)  # kill-target detail line
        self._run(runner())

    def test_kill_detail_states_the_checkbox_effect_in_words(self):
        """Textual draws the same `X` glyph ticked or not — only the colour
        changes. For a control that closes down an agent, the state must be
        legible without colour."""
        async def runner():
            app = _ConfirmHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                self.assertIn("keeps t77", _flat(app))
                self.assertNotIn("KILLS", _flat(app))

                app.screen.query_one("#pick-kill", Checkbox).value = True
                await pilot.pause()
                self.assertIn("KILLS t77", _flat(app))
                self.assertNotIn("keeps t77", _flat(app))
        self._run(runner())

    def test_ok_button_label_plain_when_eligible(self):
        """Negative control for the `Launch anyway` relabel."""
        async def runner():
            app = _ConfirmHost(narrow=True, status="Ready", blocking=())
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                text = _screen_text(app)
                self.assertNotIn("Launch anyway", text)
                self.assertNotIn("not Ready to pick", text)
                self.assertNotIn("blocked by", text)
        self._run(runner())

    def test_negative_control_without_narrow_css(self):
        """Removing the `.narrow` rules must break the fit — otherwise the
        tests above would pass no matter what the CSS said."""
        stripped = _drop_narrow_rules(TaskPickConfirmDialog.DEFAULT_CSS)
        self.assertNotIn("narrow", stripped)
        self.assertIn("#pick-buttons", stripped)  # non-narrow rules survive

        async def runner():
            app = _ConfirmHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                _assert_controls_inside(self, app, "#task-detail-dialog")

        with patch.object(TaskPickConfirmDialog, "DEFAULT_CSS", stripped):
            with self.assertRaises(AssertionError):
                self._run(runner())


class ModalKeyGatingTests(unittest.TestCase):
    """`p` is app-level and `TaskDetailDialog` binds its own `p` (plan toggle).

    Textual truncates the binding chain at the first modal screen, so no
    `check_action` is needed — but that is a framework guarantee this feature
    now depends on, so pin it. The host stands in for `MiniMonitorApp` only as
    the carrier of an app-level `p`; that the real app binds it is asserted in
    `BindingTests`. Everything else here is the real dialog.
    """

    def test_app_level_p_does_not_fire_inside_the_detail_dialog(self):
        from monitor.monitor_shared import TaskDetailDialog

        fired: list[str] = []

        class _Host(App):
            BINDINGS = [("p", "app_p", "App p")]

            def compose(self) -> ComposeResult:
                yield Label("host")

            def action_app_p(self) -> None:
                fired.append("app")

            def on_mount(self) -> None:
                info = _task_info("1310")
                info.plan_content = "# the plan"
                self.push_screen(TaskDetailDialog(info))

        async def runner():
            app = _Host()
            async with app.run_test(size=(60, 24)) as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.press("p")
                await pilot.pause()
                return app.screen._showing_plan

        # Asserted on `_showing_plan` rather than the header's "[Plan]" badge:
        # `action_toggle_plan` writes it unescaped, so Rich parses `[Plan]` as
        # markup and it never reaches the screen. Pre-existing, out of scope
        # here — recorded as an upstream defect.
        showing_plan = asyncio.run(runner())
        self.assertEqual(fired, [], "app-level p leaked into the modal")
        self.assertTrue(showing_plan, "the dialog's own p did not toggle")


class ConfirmDialogDismissalTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_escape_cancels_rather_than_confirming(self):
        """The inherited q/Esc must never produce a truthy result."""
        results = []

        class _Host(App):
            def compose(self) -> ComposeResult:
                yield Label("host")

            def on_mount(self) -> None:
                self.push_screen(
                    TaskPickConfirmDialog(
                        _task_info("1310"),
                        kill_target_label="t77 · Done · w",
                        narrow=True,
                    ),
                    results.append,
                )

        async def runner():
            app = _Host()
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()

        self._run(runner())
        self.assertEqual(results, [None])

    def test_focus_starts_on_ok_and_reaches_the_checkbox(self):
        """Enter confirms straight away on the safe default (unchecked), and the
        destructive option is one Shift+Tab away. Both are DOM-order artifacts
        that a compose reorder would silently change."""
        class _Host(App):
            def compose(self) -> ComposeResult:
                yield Label("host")

            def on_mount(self) -> None:
                self.push_screen(
                    TaskPickConfirmDialog(
                        _task_info("1310"),
                        kill_target_label="t77 · Done · w",
                        narrow=True,
                    )
                )

        async def runner():
            app = _Host()
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                first = app.focused.id
                await pilot.press("shift+tab")
                await pilot.pause()
                return first, app.focused.id

        first, back = self._run(runner())
        self.assertEqual(first, "btn-pick-ok")
        self.assertEqual(back, "pick-kill")

    def test_ok_returns_checkbox_state(self):
        results = []

        class _Host(App):
            def compose(self) -> ComposeResult:
                yield Label("host")

            def on_mount(self) -> None:
                self.push_screen(
                    TaskPickConfirmDialog(
                        _task_info("1310"),
                        kill_target_label="t77 · Done · w",
                        narrow=True,
                    ),
                    results.append,
                )

        async def runner():
            app = _Host()
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                app.screen.query_one("#pick-kill", Checkbox).value = True
                await pilot.pause()
                app.screen.query_one("#btn-pick-ok", Button).press()
                await pilot.pause()

        self._run(runner())
        self.assertEqual(results, [(True, True)])


if __name__ == "__main__":
    unittest.main()
