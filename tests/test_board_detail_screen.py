"""board_detail_screen.py — the task editor extracted from aitask_board.py (t1794_7).

Three contracts the move must keep, all checkable only against the loaded board:

* **Re-export identity.** `aitask_board.py` imports every moved name back from
  `board_detail_screen`, so `ab.TaskDetailScreen` IS
  `ab.board_detail_screen.TaskDetailScreen`. A definition left behind in the
  board would shadow the import: `SettingsScreen` would bind a stale
  `CycleField`, and tests would patch a class the editor never uses.
* **Injected board helpers (C1).** The editor may not import the board, so the
  three helpers it calls — task types, the user's email, the tmux session — are
  REQUIRED keyword-only arguments, and `ab.make_task_detail_screen()` is the one
  place the board binds them. A default here would be a silent fallback that no
  longer reaches the board's helper (and could not reference it anyway).
* **No task-directory read (C2).** The parent-field check compares against the
  manager's `tasks_dir`, not a board constant.

Reaches the module only as `self.ab.board_detail_screen` — the fixture-loaded
board's own binding — never by a canonical import (see `MIGRATED_MODULES` in
test_board_fixture_harness.py). The headless-import pin lives in
test_board_package_contract.py beside the other subprocess checks.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_board_detail_screen.py -q
"""

from __future__ import annotations

import inspect
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

#: Every name t1794_7 moved out of aitask_board.py — the board's re-export list.
MOVED_NAMES = (
    "AnchorEditScreen", "AnchorField", "ChildPickerItem", "ChildPickerScreen",
    "ChildrenField", "CrossRepoDepsField", "CrossRepoRefItem",
    "CrossRepoRefPickerScreen", "CycleField", "DependencyPickerScreen",
    "DependsField", "DepPickerItem", "FileReferenceItem",
    "FileReferencePickerScreen", "FileReferencesField", "FoldedIntoField",
    "FoldedTaskPickerItem", "FoldedTaskPickerScreen", "FoldedTasksField",
    "FollowupKindField", "FollowupKindPickerItem", "FollowupKindPickerScreen",
    "IssueField", "LockEmailScreen", "ParentField", "PullRequestField",
    "ReadOnlyField", "RemoveDepConfirmScreen", "ResetTaskConfirmScreen",
    "TaskDetailScreen", "UnlockConfirmScreen", "VerifiesField",
    "_reload_detail_screen", "_remove_dep_from_task", "_remove_verify_from_task",
)

#: The board helpers the editor takes by injection, and the board function
#: `make_task_detail_screen` must bind each one to.
PROVIDERS = {
    "task_types_provider": "_load_task_types",
    "user_email_provider": "_get_user_email",
    "tmux_session_provider": "_owned_tmux_session",
}


def _non_identical(board, module, names) -> list[str]:
    """Names `board` does not bind to the very object `module` defines.

    A name missing from either side is reported too, so an empty result cannot
    come from comparing two absences.
    """
    absent = object()
    return [n for n in names
            if getattr(board, n, absent) is not getattr(module, n, None)]


def _required_kwonly(func) -> set[str]:
    return {p.name for p in inspect.signature(func).parameters.values()
            if p.kind is inspect.Parameter.KEYWORD_ONLY
            and p.default is inspect.Parameter.empty}


def _ORDER():
    """The fixture-loaded editor's newest-wins focus order."""
    return sys.modules["board_detail_screen"]._CODEBROWSER_FOCUS_ORDER


def _ui_thread_app():
    """A stand-in App whose `call_from_thread` runs the callback inline, so a
    worker body's notifications land on `app.notify` for the assertions."""
    app = MagicMock()
    app.call_from_thread.side_effect = lambda fn, *a, **k: fn(*a, **k)
    return app


class ReexportIdentityTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`ab.<name>` is `ab.board_detail_screen.<name>` for every moved name."""

    def test_every_moved_name_is_the_detail_module_object(self):
        self.assertEqual(len(set(MOVED_NAMES)), 35)
        self.assertEqual(
            _non_identical(self.ab, self.ab.board_detail_screen, MOVED_NAMES), [],
            "aitask_board.py must re-export these from board_detail_screen, "
            "not define (or keep) its own copy")

    def test_the_identity_check_can_fail(self):
        """Negative control: a stand-in board holding a copy, or missing the
        name, is reported."""
        module = self.ab.board_detail_screen
        copy = type("TaskDetailScreen", (), {})
        stand_in = type("Board", (), {"TaskDetailScreen": copy})
        self.assertEqual(
            _non_identical(stand_in, module, ("TaskDetailScreen", "CycleField")),
            ["TaskDetailScreen", "CycleField"])

    def test_the_editor_defines_them_the_board_does_not(self):
        for name in MOVED_NAMES:
            with self.subTest(name=name):
                obj = getattr(self.ab.board_detail_screen, name)
                self.assertEqual(obj.__module__, "board_detail_screen")


class InjectedHelperTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """The three board helpers reach the editor only by injection (C1)."""

    def _task(self, rel="aitasks/t9101_x.md"):
        return self.ab.Task.from_text(Path(rel), "---\nstatus: Ready\n---\nbody\n")

    def test_the_providers_are_required_keyword_only(self):
        self.assertEqual(_required_kwonly(self.ab.TaskDetailScreen.__init__),
                         set(PROVIDERS))
        self.assertEqual(_required_kwonly(self.ab.FileReferencesField.__init__),
                         {"tmux_session_provider"})
        with self.assertRaises(TypeError):
            self.ab.TaskDetailScreen(self._task())

    def test_the_factory_binds_each_board_helper(self):
        """Each provider resolves the board's helper at CALL time, so a stub
        on the board module reaches the editor. Mutant-checked: binding any
        provider to a different callable turns its subtest red."""
        screen = self.ab.make_task_detail_screen(self._task())
        sentinel = object()
        for provider, helper in PROVIDERS.items():
            with self.subTest(provider=provider):
                with patch.object(self.ab, helper, return_value=sentinel) as spy:
                    self.assertIs(getattr(screen, "_" + provider)(), sentinel)
                self.assertEqual(spy.call_count, 1)

    def test_file_references_launch_uses_the_injected_session(self):
        module = self.ab.board_detail_screen
        app = _ui_thread_app()
        cls = self.ab.FileReferencesField

        def launch(session):
            field = cls(["a.py"], MagicMock(), self._task(),
                        tmux_session_provider=lambda: session)
            with patch.object(cls, "app", new_callable=PropertyMock,
                              return_value=app), \
                 patch.object(module, "launch_or_focus_codebrowser",
                              return_value=(True, None)) as spy:
                field._focus_codebrowser("a.py", _ORDER().ticket())
            return spy

        spy = launch("sess")
        spy.assert_called_once_with("sess", "a.py")
        # Control: no session → the tmux notice, and nothing is launched.
        spy = launch(None)
        self.assertFalse(spy.called)
        self.assertIn("No tmux session of this project",
                      app.notify.call_args.args[0])

    def test_the_launch_resolves_the_session_off_the_event_loop(self):
        """t1952: the ownership lookup is gateway calls with 5s timeouts, so
        the Enter handler only REQUESTS a thread worker — the provider is never
        called on the event loop. `run_worker` is the one choke point `@work`
        dispatches through, so standing in for it records the request without
        letting a real worker run."""
        provider = MagicMock(return_value="sess")
        cls = self.ab.FileReferencesField
        field = cls(["a.py"], MagicMock(), self._task(),
                    tmux_session_provider=provider)
        with patch.object(field, "run_worker") as run_worker, \
             patch.object(cls, "app", new_callable=PropertyMock,
                          return_value=_ui_thread_app()), \
             patch.object(self.ab.board_detail_screen,
                          "launch_or_focus_codebrowser",
                          return_value=(True, None)):
            field._launch_codebrowser("a.py")
        run_worker.assert_called_once()
        self.assertTrue(run_worker.call_args.kwargs.get("thread"))
        provider.assert_not_called()
        # The ticket is taken at REQUEST time, on the event loop: the worker
        # carries the newest one, so request order decides the winner.
        work = run_worker.call_args.args[0]
        self.assertEqual(work.args, (field, "a.py", _ORDER()._latest))

    def test_the_session_helper_is_the_owned_lookup_for_the_cwd(self):
        """t1952: the codebrowser focus searches only a session discovery
        attributes to this project, never an ambient `#S`."""
        with patch.object(self.ab, "owned_lookup_session",
                          return_value="sess") as spy:
            self.assertEqual(self.ab._owned_tmux_session(), "sess")
        spy.assert_called_once_with(Path.cwd())

    def test_the_parent_field_compares_against_the_managers_tasks_dir(self):
        """C2: the child-task check reads `manager.tasks_dir`, not a board
        constant — a manager rooted elsewhere changes the answer."""
        manager = MagicMock()
        manager.get_parent_num_for_child.return_value = "9101"
        screen = self.ab.make_task_detail_screen(
            self._task("aitasks/t9101/t9101_1_child.md"))
        screen.manager = manager

        def parent_fields(tasks_dir):
            manager.tasks_dir = Path(tasks_dir)
            return [w for w in screen._build_relations_fields({})
                    if isinstance(w, self.ab.ParentField)]

        self.assertEqual(len(parent_fields("aitasks")), 1,
                         "a task below the manager's tasks_dir is a child")
        self.assertEqual(parent_fields("aitasks/t9101"), [],
                         "a task directly in the manager's tasks_dir is not")


class CodebrowserOwnedSessionTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """End to end from the factory-bound provider through the REAL resolver
    (`owned_lookup_session` → `current_tmux_session` → `_sessions_owned_by`)
    to the REAL `launch_or_focus_codebrowser` (t1952). Only the gateway's
    answers are controlled: the caller is a verified pane of project B's
    session, and the configured `default_session` is stamped per test."""

    _MUTATING = ("set-environment", "select-window", "new-window")

    def setUp(self):
        self.alu = sys.modules[self.ab.owned_lookup_session.__module__]
        # Project A is the fixture tree (the class cwd, which carries a
        # project_config.yaml, so its registration stamp resolves); project B
        # is a second marked root outside it.
        self.proj_a = self.tree
        self.assertTrue(
            (self.proj_a / "aitasks" / "metadata" / "project_config.yaml")
            .is_file())
        self.proj_b = Path(tempfile.mkdtemp(prefix="t1952_proj_b_"))
        self.addCleanup(shutil.rmtree, self.proj_b, True)
        (self.proj_b / "aitasks" / "metadata").mkdir(parents=True)
        (self.proj_b / "aitasks" / "metadata" / "project_config.yaml").write_text("")
        self.calls: list[list[str]] = []
        self.configured_root = self.proj_b

        def _run(args, timeout=5.0):
            self.calls.append(list(args))
            if args[0] == "display-message":
                return (0, "/sock/ait\tprojB\n")
            if args[0] == "list-sessions":
                return (0, f"projB\t{self.proj_b}\n"
                           f"configured\t{self.configured_root}\n")
            if args[0] == "list-windows":
                return (0, "codebrowser\n")
            return (0, "")

        for target, attr, value in (
                (self.alu._TMUX, "run", _run),
                (self.alu, "load_tmux_defaults",
                 lambda root: {"default_session": "configured"})):
            p = patch.object(target, attr, value)
            p.start()
            self.addCleanup(p.stop)
        env = patch.dict(os.environ,
                         {"TMUX": "/sock/ait,1,0", "TMUX_PANE": "%3"})
        env.start()
        self.addCleanup(env.stop)

    def _launch(self):
        task = self.ab.Task.from_text(Path("aitasks/t9101_x.md"),
                                      "---\nstatus: Ready\n---\nbody\n")
        provider = self.ab.make_task_detail_screen(task)._tmux_session_provider
        cls = self.ab.FileReferencesField
        field = cls(["a.py"], MagicMock(), task,
                    tmux_session_provider=provider)
        app = _ui_thread_app()
        with patch.object(cls, "app", new_callable=PropertyMock,
                          return_value=app):
            field._focus_codebrowser("a.py", _ORDER().ticket())
        return app, [c for c in self.calls if c[0] in self._MUTATING]

    def test_foreign_caller_and_foreign_fallback_launch_nothing(self):
        app, mutating = self._launch()
        self.assertEqual(mutating, [])
        self.assertIn("No tmux session of this project",
                      app.notify.call_args.args[0])

    def test_owned_fallback_is_the_target(self):
        self.configured_root = self.proj_a
        app, mutating = self._launch()
        self.assertEqual(mutating, [
            ["set-environment", "-t", "=configured",
             "AITASK_CODEBROWSER_FOCUS", "a.py"],
            ["select-window", "-t", "=configured:codebrowser"]])
        self.assertFalse(any("projB" in " ".join(c) for c in mutating))
        app.notify.assert_not_called()

    # ── Overlapping requests: the newest request's file is the final focus ──
    #
    # Two thread workers can overlap, and `exclusive=True` would not stop one
    # already running. Each ordering below is forced deterministically with
    # Events, and runs real threads through the real resolver and launch.

    def _overlap(self, hold):
        """Request first.py then second.py, with first.py held at `hold`
        ("lookup": inside the session lookup, or "act": inside its
        `set-environment`) while second.py runs; return the focus values
        written, in order."""
        self.configured_root = self.proj_a
        gateway_run = self.alu._TMUX.run
        held, release = threading.Event(), threading.Event()
        focus = []

        def run(args, timeout=5.0):
            if args[0] == "set-environment":
                focus.append(args[-1])
                if hold == "act" and args[-1] == "first.py":
                    held.set()
                    release.wait(5)
            return gateway_run(args, timeout)

        task = self.ab.Task.from_text(Path("aitasks/t9101_x.md"),
                                      "---\nstatus: Ready\n---\nbody\n")
        real = self.ab.make_task_detail_screen(task)._tmux_session_provider
        lookups = []

        def provider():
            lookups.append(1)
            if hold == "lookup" and len(lookups) == 1:
                held.set()
                release.wait(5)
            return real()

        cls = self.ab.FileReferencesField
        field = cls(["first.py", "second.py"], MagicMock(), task,
                    tmux_session_provider=provider)
        threads = []

        def start(entry):
            th = threading.Thread(target=field._focus_codebrowser,
                                  args=(entry, _ORDER().ticket()))
            threads.append(th)
            th.start()
            return th

        with patch.object(self.alu._TMUX, "run", run), \
             patch.object(cls, "app", new_callable=PropertyMock,
                          return_value=_ui_thread_app()):
            try:
                start("first.py")
                self.assertTrue(held.wait(5), "first.py never reached the hold")
                second = start("second.py")
                if hold == "lookup":
                    second.join(5)       # nothing blocks it: it acts now
                else:
                    second.join(0.3)     # it must WAIT for the acting first.py
                    self.assertTrue(second.is_alive(),
                                    "second.py acted while first.py was acting")
            finally:
                # Join inside the patches, even on failure, so no thread
                # outlives them.
                release.set()
                for th in threads:
                    th.join(5)
        self.assertFalse(any(th.is_alive() for th in threads))
        return focus

    def test_an_overtaken_older_request_performs_no_side_effect(self):
        """first.py's lookup is still running when second.py is requested and
        completes: the stale first.py must not write the focus afterwards."""
        self.assertEqual(self._overlap("lookup"), ["second.py"])

    def test_an_older_request_already_acting_finishes_before_the_newer(self):
        """first.py is mid-launch when second.py is requested: second.py waits
        its turn, so its focus is the last one written."""
        self.assertEqual(self._overlap("act"), ["first.py", "second.py"])


if __name__ == "__main__":
    unittest.main()
