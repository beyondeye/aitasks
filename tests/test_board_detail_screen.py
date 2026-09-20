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
import sys
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
    "tmux_session_provider": "_current_tmux_session",
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
        app = MagicMock()
        cls = self.ab.FileReferencesField

        def launch(session):
            field = cls(["a.py"], MagicMock(), self._task(),
                        tmux_session_provider=lambda: session)
            with patch.object(cls, "app", new_callable=PropertyMock,
                              return_value=app), \
                 patch.object(module, "launch_or_focus_codebrowser",
                              return_value=(True, None)) as spy:
                field._launch_codebrowser("a.py")
            return spy

        spy = launch("sess")
        spy.assert_called_once_with("sess", "a.py")
        # Control: no session → the tmux notice, and nothing is launched.
        spy = launch(None)
        self.assertFalse(spy.called)
        self.assertIn("requires tmux", app.notify.call_args.args[0])

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


if __name__ == "__main__":
    unittest.main()
