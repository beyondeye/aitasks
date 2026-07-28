---
priority: high
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [aitask_board, tui, testing, script-performance]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
implemented_with: claudecode/opus5
created_at: 2026-07-28 01:12
updated_at: 2026-07-28 15:10
---

## Context

**Child 1 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — read it first).

There are **zero board-movement tests today**. Every later child in this
decomposition changes how the board writes `boardidx` / `boardcol` or how it
renders after a move, so the characterization harness and the performance
baseline must exist first. This child also owns the **pre-registered** method
and success rules that decide whether children 4 and 5 are built as planned.

**Anchor re-verification (do this first).** `aitask_board.py` grew from 7378 to
9043 lines across six commits while t1243 was planned. Re-verify every symbol
named below against the current file before editing; anchor on symbol names,
never on line numbers.

## Key files to modify

- `tests/test_board_movement.py` — **new**, the entire deliverable.

## Reference files for patterns

- `tests/test_board_empty_column_focus.py` — the live-repo Pilot harness
  (`sys.path` insert of `.aitask-scripts/board` + `.aitask-scripts/lib`,
  `os.chdir(REPO_ROOT)` in `setUpClass`, `asyncio.run` wrapper, synthetic
  column layout imposed on the real `KanbanApp`).
- `tests/test_board_topic_group.py` — the pure/import harness and the
  `Task.from_text` in-memory fixture builder.
- `.aitask-scripts/lib/config_utils.py` `task_dir()` — honors `TASK_DIR`,
  documented for tests.

## Implementation plan

### 1. Subprocess isolation (NON-OPTIONAL — the fixture is wrong without it)

`TASKS_DIR = task_dir()` in `aitask_board.py` is a **module-load constant**.
`bash tests/run_all_python_tests.sh` runs every `test_*.py` in **one** pytest
process, and 16 `test_board_*.py` files import `aitask_board` in `setUpClass`.
`test_board_movement.py` sorts after `test_board_inflight_view.py`, so by the
time it runs the module is already cached against the **real** `aitasks/` tree
and setting `TASK_DIR` in-process is a silent no-op.

So the test module must **not** drive the board in its own process. It:

1. builds a temp tree (`aitasks/`, `aitasks/metadata/board_config.json`, real
   `t*.md` files with `boardcol` / `boardidx` frontmatter);
2. spawns a child interpreter (`sys.executable`) with `TASK_DIR` pointing at it
   and `PYTHONPATH` covering `.aitask-scripts/board` and `.aitask-scripts/lib`;
3. the child imports `aitask_board` fresh, runs one scenario, and writes results
   to a **JSON path passed as argv** — never stdout, which carries Textual and
   pytest noise;
4. the parent reads the JSON and asserts.

### 2. The write oracle

Two independent signals, both required:

- a **call-count spy** wrapping `Task.reload_and_save_board_fields`;
- a **byte/path differ** over the temp tree: snapshot every file's path + hash
  before the scenario, diff after. This is what proves *which* files changed and
  that non-board frontmatter survived — a spy alone cannot.

### 3. Characterization of today's behaviour

Record, in a **self-enforcing flip table** (a dict of scenario → expected write
count + changed paths, asserted exactly), the current semantics of:

- `_move_task_lateral` — `move_task_col` + `normalize_indices` on **both**
  columns;
- `_move_task_vertical` — `swap_tasks` + `normalize_indices`;
- `_move_task_to_extreme` — direct `±10` write + `normalize_indices`;
- `_shift_column` — metadata only, no task writes.

Child 3 must consciously edit this table; a silent pass after the rewrite is a
bug in the table.

### 4. Pre-registered performance baseline

Fix the method and the rules **before observing any result**:

- **Method.** 200 parent cards over 5 columns (the live tree has ~226 tasks),
  warm headless Pilot. Samples must be **stationary and valid**: 50 consecutive
  `shift+right` saturates at the last column and every later press
  early-returns, so a naive run measures *rejected actions*. **Ping-pong**
  instead — `shift+right`/`shift+left` between two adjacent non-collapsed
  columns, `shift+down`/`shift+up` between two adjacent mid-column positions —
  so state returns to the start after each pair. Discard warm-up samples
  explicitly. **Every recorded sample must be accompanied by a write**
  (spy count > 0); a zero-write sample means the action was rejected and
  **fails the run** rather than being averaged in.
- **Report.** Median and p90 end-to-end keypress latency over valid samples
  only, plus per-span totals from a monotonic-clock wrapper around
  `apply_filter`, `refresh_column(s)` / `_recompose_column`,
  `refresh_git_status`, and `reload_and_save_board_fields`.
- **Premise rule.** Workstream B's premise holds **iff `apply_filter` + column
  recompose together account for >= 40% of median keypress latency.**
- **Target rule.** Children 4 and 5 must deliver **>= 30% reduction in median
  keypress latency** versus this baseline.

### 5. Decision checkpoint (the last step of this child)

Compare the measurement to the premise rule.

- **Premise holds** → record the baseline table in
  `aiplans/p1243_board_task_groups_and_fast_reordering.md` and proceed.
- **Premise refuted** → do **not** let the dependency chain carry a falsified
  premise. **Revise, replace, or postpone t1243_4 and t1243_5** — rewrite those
  task files and their plans to target whichever span actually dominates — and
  record the decision and the data in the parent plan before either is picked.

## Verification

- The suite **exits 1** when a guarded behaviour is reverted (prove the harness
  can fail — a passing test pins nothing until the failure path is exercised).
- Run and assert identical results **both** standalone
  (`python3 -m pytest tests/test_board_movement.py -v`) **and** via the full
  `bash tests/run_all_python_tests.sh`.
- **Negative control:** a variant that sets `TASK_DIR` in-process is shown to
  read the real `aitasks/` tree, proving the subprocess isolation is what makes
  the fixture correct.
- No file under the repo's real `aitasks/` is modified by any test.
- The baseline table and the checkpoint decision are recorded in the parent plan.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-28T12:10:24Z status=pass attempt=1 type=human
