---
Task: t1794_4_extract_task_model_manager_and_workflow_phase.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md … t1794_3_*.md, t1794_5_*.md … t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_4 — Extract `Task`, `TaskManager` and workflow-phase derivation

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1, C2, C3 PINNED; "Scope decisions"). The highest patch-site child.

## Modules

- `board_task_model.py`: `Task :753–937`, `MoveResult :1364` (`datetime`
  imported here — `Task.save :864`).
- `board_task_manager.py`: `TaskManager :1459–2958` + helpers only it calls
  (enumerate `:947–1160` by grep; shared helpers stay in the board).
- `board_workflow_phase.py`: `:223–617` (pure).

## PINNED constructor

`TaskManager(*, tasks_dir: Path, metadata_file: Path, gates_registry_file:
Path, on_warning=None, …)` — kw-only, required. Every call-time global read
(`:1538–1539, 1547, 1561, 1645, 1723, 1775, 1836, 1855, 1879, 1926–1935,
2114, 2863`) becomes an attribute read. `_get_user_email` / `_load_task_types`
(if called) are injected callables; they stay in the board (C1).
`KanbanApp.__init__ :8909` passes `TASKS_DIR`, `METADATA_FILE`,
`GATES_REGISTRY_FILE`.

## C3 obligations

- Rewrite the patch-mode `setUp`s that construct `B.TaskManager()` bare:
  `tests/test_board_persistence_seam.py:198–204, 719–722`,
  `tests/test_board_manager_moves.py:91–97`,
  `tests/test_board_column_manage.py:93–98` → pass the patched values.
- Repoint `datetime` (`persistence_seam:135`) → `B.board_task_model`;
  `save_local_config` / `save_project_config` / `load_layered_config` /
  `project_columns_at` (`persistence_seam:809`, `column_manage:695,713–745`,
  the generic loops at `:95/:96/:200`) → `B.board_task_manager`.
- One recorded mutant per repointed patch (bypass the call → red).
- Pinning test in `tests/test_board_fixture_harness.py`: construct
  `TaskManager` the way the patch-mode files do with a temp `tasks_dir` and
  assert it lists that tree, not cwd's; update the exemption text
  (`:344–366`); explicit `board_task_manager` C2 case.
- `tests/test_board_package_contract.py` pairing now has data.

## Order

Rebase check (t1243, t1632, t1714 neighbours — read, don't pre-implement) →
enumerate global reads with dispositions (record) → three modules → import
pairs + `KanbanApp.__init__` → test rewrites + mutants → pinning test → suite.

## Verification

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `test_board_persistence_seam`, `test_board_manager_moves`,
  `test_board_movement` (incl. `IsolationNegativeControlTests`),
  `test_board_column_manage`, `test_followup_kind_phantom_stub`,
  `test_atomic_task_writes`, `test_board_workflow_phase`,
  `test_task_dir_module_constants`, `test_board_fixture_harness`,
  `test_board_package_contract`, `test_board_keymap_characterization` green;
  mutant list with red runs recorded here.
- `grep -n '^class Task\b\|^class TaskManager\|^def derive_workflow_phase'
  .aitask-scripts/board/aitask_board.py` empty.
- Manual: edit a task in `ait board` (updated_at written); move a card.

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_4`.
