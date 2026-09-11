---
priority: medium
effort: high
depends: [t1794_3]
issue_type: refactor
status: Ready
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 4 of t1794. Extract the data layer — `Task`, `MoveResult`, `TaskManager`
and the pure workflow-phase derivation — out of `aitask_board.py`. The
stand-alone `ait trails` TUI (child 6) needs `TaskManager` to load tasks
without importing `KanbanApp`, and parent contract C1 forbids any `board/*.py`
from importing `aitask_board`. This is the child with the highest patch-site
count: `TaskManager` reads the board's module globals **at call time**
(`aitask_board.py:1538–1539, 1547, 1561, 1645, 1723, 1775, 1836, 1855, 1879,
1926–1935, 2114, 2863`) and three test files construct `B.TaskManager()` bare
inside a `patch.object(B, "TASKS_DIR"/"METADATA_FILE"/…)` — an extraction that
leaves those patches pointing at the board module makes them silently inert
(the t1613 class). Constructor injection plus rewritten `setUp`s plus a mutant
proof per patch is the contract (C3).

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— C1, C2, C3 in full; "Scope decisions" (workflow-phase is in scope). Anchors
at `e2f12c499` (unchanged at `c78deab36`).

## Key files to modify

- `.aitask-scripts/board/board_task_model.py` — NEW: `Task` (`:753–937`),
  `MoveResult` (`:1364`). `Task.save` writes `updated_at` via `datetime.now()`
  (`:864`) — `datetime` is imported in this module (patch target moves).
- `.aitask-scripts/board/board_task_manager.py` — NEW: `TaskManager`
  (`:1459–2958`) plus the module-level helpers only it calls (enumerate with
  `grep -n` for each candidate between `:947–1160` — `task_matches_filter`,
  topic grouping helpers `:1030–1160` — and keep in the board any helper that
  a non-manager caller also uses). Constructor signature (PINNED):
  `TaskManager(*, tasks_dir: Path, metadata_file: Path, gates_registry_file:
  Path, on_warning=None, …existing kwargs…)` — kw-only, **required**; every
  call-time read of `TASKS_DIR` / `METADATA_FILE` / `GATES_REGISTRY_FILE`
  becomes `self.tasks_dir` / `self.metadata_file` / `self.gates_registry_file`.
  If the manager calls `_get_user_email` / `_load_task_types` (`:730`, `:692`),
  they are injected as callables (`user_email_provider=`,
  `task_types_provider=`) — those helpers stay in the board (C1).
- `.aitask-scripts/board/board_workflow_phase.py` — NEW: `:223–617`
  (`_gate_progress`, `_pending_human_gates`, `_pending_procedure_gates`,
  `_failed_active_gates`, `derive_workflow_phase`, `INFLIGHT_LANES`,
  `LANE_FOR_PHASE`, `PHASE_LABELS`, `_inflight_lane`, `_inflight_next_action`,
  `phase_chip_text`); pure — no global reads (verified).
- `.aitask-scripts/board/aitask_board.py` — `import board_task_model`,
  `import board_task_manager`, `import board_workflow_phase` + flat
  re-imports; `KanbanApp.__init__` (`:8909`) becomes
  `TaskManager(tasks_dir=TASKS_DIR, metadata_file=METADATA_FILE,
  gates_registry_file=GATES_REGISTRY_FILE, on_warning=self.notify, …)`.
- `tests/test_board_persistence_seam.py:135, 198–204, 719–722, 809`,
  `tests/test_board_manager_moves.py:91–97`,
  `tests/test_board_column_manage.py:93–98, 695, 713–745` — rewrite the
  patch-mode `setUp`s to construct `B.TaskManager(tasks_dir=<patched>,
  metadata_file=<patched>, gates_registry_file=<patched>)`; repoint
  `datetime` → `B.board_task_model`, `save_local_config` /
  `save_project_config` / `load_layered_config` / `project_columns_at` →
  `B.board_task_manager`.
- `tests/test_board_fixture_harness.py:344–366` — update the documented
  patch-mode exemption text; add the explicit `board_task_manager` C2 case;
  add the pinning test that constructs `TaskManager` the way the patch-mode
  files do and asserts the injected paths are the ones read (a manager built
  with a temp `tasks_dir` lists that tree's tasks, not the cwd's).
- `tests/test_board_package_contract.py` — the bare-import pairing check now
  has data (`board_task_model`, `board_task_manager`).

## Reference files for patterns

- `aitask_board.py:53–66` — bare-import + flat re-import pairing.
- `tests/lib/board_fixture.py:16–41` — "Two seams" and the TASK_DIR relative
  invariant; `TaskManager.is_modified` compares `str(task.filepath)` against
  `git status --porcelain` paths, so `tasks_dir` must stay the relative
  literal under the fixture.
- `tests/test_board_movement.py` `IsolationNegativeControlTests` — pins
  `aitask_board.TASKS_DIR == Path("aitasks")`; must stay green.
- `tests/test_board_workflow_phase.py` — the workflow-phase seam tests
  (t1603_2); they will import from `board_workflow_phase` via the board's
  re-export or directly.
- `tests/test_followup_kind_phantom_stub.py` — `TaskManager._is_phantom_stub`
  (`:921` today) behaviour.

## Implementation plan

1. **Rebase check** (parent pre-phase) over `:223–617`, `:692–950`,
   `:1364`, `:1459–2958`, `:8904–8964` and the five test files; foreign
   `Implementing` task on these ranges → stop at the checkpoint. t1243
   (TaskManager perf), t1632 (board_columns seam), t1714 (metadata write
   mutex) are the known pending neighbours — read their bodies, do not
   pre-implement them.
2. Enumerate every module-global read inside `:1459–2958` (`grep -n
   'TASKS_DIR\|METADATA_FILE\|GATES_REGISTRY_FILE\|USERCONFIG_FILE\|EMAILS_FILE\|
   TASK_TYPES_FILE\|_get_user_email\|_load_task_types\|save_local_config\|
   save_project_config\|load_layered_config\|project_columns_at\|local_path_for'`)
   and record the list in the child plan with its disposition
   (constructor param / injected callable / lib import).
3. Create the three modules; wire the import pairs; update
   `KanbanApp.__init__`.
4. Rewrite the patch-mode `setUp`s; repoint the other patches; for **each**
   repointed patch record a one-line mutant (bypass the call →
   the test goes red) in the child plan.
5. Pinning test + fixture-harness updates; C2 scan of the three new modules.
6. Full suite; `IsolationNegativeControlTests`; `test_task_dir_module_constants`.

## Verification steps

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `python -m pytest tests/test_board_persistence_seam.py
  tests/test_board_manager_moves.py tests/test_board_movement.py
  tests/test_board_column_manage.py tests/test_followup_kind_phantom_stub.py
  tests/test_atomic_task_writes.py tests/test_board_workflow_phase.py
  tests/test_task_dir_module_constants.py tests/test_board_fixture_harness.py
  tests/test_board_package_contract.py tests/test_board_keymap_characterization.py -q`
  green; mutant list recorded with each red run.
- `grep -n '^class Task\b\|^class TaskManager\|^def derive_workflow_phase'
  .aitask-scripts/board/aitask_board.py` returns nothing.
- `ait board` boots; edit a task in the detail screen and confirm
  `updated_at` is written; move a card between columns (manual in tmux).
