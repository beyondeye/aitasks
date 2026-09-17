"""The task data layer extracted from aitask_board.py (t1794_4).

`Task`, `TaskManager` and the workflow-phase derivation moved into three
modules. Three contracts, checkable only against the sources or the loaded
board:

* **Single home.** Each moved name is defined exactly once, in the module the
  split put it in, and nowhere in `aitask_board.py`, which imports every one of
  them back. Checked on the SOURCE, name by name (see
  tests/lib/board_single_home.py for why identity alone is not enough).
* **Re-export identity.** `ab.TaskManager` IS `ab.board_task_manager.TaskManager`
  on the fixture-loaded board.
* **Injected paths (parent contract C2).** `TaskManager` takes `tasks_dir`,
  `metadata_file` and `gates_registry_file` as REQUIRED keywords, so an
  old-style construction fails at the call instead of silently reading
  whatever tree the process happens to be in; `make_task_manager()` binds the
  loaded board's own constants. The "reads the injected tree, not the cwd's"
  pin lives in test_board_fixture_harness.py (`InjectedManagerPathTests`).

Reaches the modules only as `self.ab.<module>` or by reading their source —
never by a canonical import (`MIGRATED_MODULES` in
test_board_fixture_harness.py).

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_board_task_manager.py -q
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402
from board_single_home import (  # noqa: E402
    _imported_from, _single_home_findings, _top_level_bindings,
)

BOARD_DIR = REPO_ROOT / ".aitask-scripts" / "board"
BOARD_SRC = BOARD_DIR / "aitask_board.py"

#: Every name t1794_4 moved, by the module it now lives in — the one table the
#: checks below read. A name added to one of these modules must be added here.
MOVED = {
    "board_task_model": (
        "Task", "MoveResult", "MERGE_METADATA_KEY", "MERGE_METADATA_LOCAL_KEY",
        "MERGE_UNVERIFIABLE_KEY", "MergeResult",
    ),
    "board_workflow_phase": (
        "GateStateResult", "InFlightItem", "_resolve_plan_path_for_task",
        "WORKFLOW_PHASES", "WORKFLOW_PROVENANCES", "WorkflowPhase",
        "_gate_progress", "_pending_human_gates", "_pending_procedure_gates",
        "_failed_active_gates", "derive_workflow_phase", "INFLIGHT_LANES",
        "LANE_FOR_PHASE", "PHASE_LABELS", "_inflight_lane",
        "_inflight_next_action", "phase_chip_text",
    ),
    "board_task_manager": (
        "_DIGEST_UNSET", "_task_git_cmd", "TOPIC_SORT_MODES",
        "TOPIC_SORT_MODE_LABELS", "_topic_lane_label", "_task_recency",
        "_lane_recency", "_topic_id_sortkey", "_sort_topic_lanes",
        "_topic_membership_signature", "_build_topic_lanes",
        "_assemble_topic_lanes", "group_tasks_by_topic", "MetadataWriteError",
        "TaskManager",
    ),
}

CLASSES = {"Task": "board_task_model", "MoveResult": "board_task_model",
           "MergeResult": "board_task_model", "GateStateResult": "board_workflow_phase",
           "InFlightItem": "board_workflow_phase", "WorkflowPhase": "board_workflow_phase",
           "MetadataWriteError": "board_task_manager", "TaskManager": "board_task_manager"}

PATH_KEYWORDS = ("tasks_dir", "metadata_file", "gates_registry_file")


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class SingleHomeTests(unittest.TestCase):
    """Each moved definition lives in its new module and only there."""

    @classmethod
    def setUpClass(cls):
        cls.board_src = _src(BOARD_SRC)
        cls.module_src = {m: _src(BOARD_DIR / f"{m}.py") for m in MOVED}

    def test_every_moved_name_has_exactly_one_home(self):
        for module, names in MOVED.items():
            for name in names:
                with self.subTest(module=module, name=name):
                    self.assertEqual(
                        _single_home_findings(self.board_src, self.module_src[module],
                                              (name,), view_label=f"{module}.py"), [])

    def test_each_module_defines_exactly_its_moved_names(self):
        for module, names in MOVED.items():
            with self.subTest(module=module):
                self.assertEqual(set(_top_level_bindings(self.module_src[module])),
                                 set(names))

    def test_no_name_is_defined_in_two_new_modules(self):
        seen: dict[str, str] = {}
        for module in MOVED:
            for name in _top_level_bindings(self.module_src[module]):
                self.assertNotIn(name, seen, f"{name}: {seen.get(name)} and {module}")
                seen[name] = module

    def test_the_board_imports_every_name_back(self):
        for module, names in MOVED.items():
            with self.subTest(module=module):
                self.assertEqual(set(names) - _imported_from(self.board_src, module),
                                 set(), "the board's re-export list shrank")

    def test_a_copy_left_above_the_board_import_is_flagged(self):
        """Negative control on the real table: a stale `TaskManager` class ahead
        of the re-export is exactly the shape identity cannot see."""
        stale = "class TaskManager:\n    pass\n\n" + self.board_src
        self.assertIn(
            "TaskManager: still defined in aitask_board.py:1",
            _single_home_findings(stale, self.module_src["board_task_manager"],
                                  ("TaskManager",), view_label="board_task_manager.py"))


class ReexportIdentityTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """The fixture-loaded board binds the extracted objects."""

    def test_every_moved_name_is_the_owning_module_object(self):
        for module, names in MOVED.items():
            owner = getattr(self.ab, module)
            for name in names:
                with self.subTest(module=module, name=name):
                    self.assertIs(getattr(self.ab, name), getattr(owner, name))

    def test_the_classes_belong_to_their_modules(self):
        for name, module in CLASSES.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(self.ab, name).__module__, module)


class ConstructorContractTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """Paths are required keywords; the factory binds the board's constants."""

    def test_an_old_style_construction_fails_at_the_call(self):
        for label, kwargs in (("no arguments", {}),
                              ("on_warning only", {"on_warning": print})):
            with self.subTest(form=label):
                with self.assertRaises(TypeError):
                    self.ab.TaskManager(**kwargs)

    def test_a_missing_path_or_a_positional_path_fails(self):
        full = {"tasks_dir": self.ab.TASKS_DIR, "metadata_file": self.ab.METADATA_FILE,
                "gates_registry_file": self.ab.GATES_REGISTRY_FILE}
        for missing in PATH_KEYWORDS:
            with self.subTest(missing=missing):
                with self.assertRaises(TypeError):
                    self.ab.TaskManager(**{k: v for k, v in full.items() if k != missing})
        with self.assertRaises(TypeError):
            self.ab.TaskManager(self.ab.TASKS_DIR, self.ab.METADATA_FILE,
                                self.ab.GATES_REGISTRY_FILE)

    def test_the_factory_binds_this_boards_constants_and_forwards_keywords(self):
        def sink(message, **kwargs):
            pass
        manager = self.ab.make_task_manager(on_warning=sink)
        self.assertEqual(manager.tasks_dir, self.ab.TASKS_DIR)
        self.assertEqual(manager.metadata_file, self.ab.METADATA_FILE)
        self.assertEqual(manager.gates_registry_file, self.ab.GATES_REGISTRY_FILE)
        self.assertIs(manager._on_warning, sink)
        # The fixture binds a RELATIVE tasks dir (board_fixture's TASK_DIR
        # invariant) — the factory must not resolve it, or `is_modified` breaks.
        self.assertFalse(manager.tasks_dir.is_absolute())


if __name__ == "__main__":
    unittest.main()
