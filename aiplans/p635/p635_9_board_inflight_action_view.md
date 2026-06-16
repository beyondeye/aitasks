---
Task: t635_9_board_inflight_action_view.md
Parent Task: aitasks/t635_gates_framework.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_*.md ... p635_8_python_gate_ledger_parser.md
Base branch: main
---

# t635_9 - Board In-Flight Action View

## Summary

Add an `i` In-Flight mode inside `ait board`, not a separate TUI. The mode shows
active work grouped by next required action while preserving the existing board
views and failing closed when gate state cannot be derived.

## Key Changes

- Add cached gate-state derivation to the board `TaskManager`, using
  `.aitask-scripts/lib/gate_ledger.py` as the single source of truth.
- Add an In-Flight board mode with three mutually exclusive action groups:
  `Needs your action`, `Agent can continue`, and `Blocked`.
- Include every active `status: Implementing` parent/child task; tasks without a
  gate ledger are shown as resumable instead of disappearing.
- Wire gate-aware dependency release into normal board dependency display, but
  fail closed to the existing active-dependency behavior on parser/registry
  errors.
- Add contextual In-Flight actions: `p` pick/resume, `g` direct resume, and
  `s`/`f` human-gate sign-off/fail with a gate selector when multiple gates are
  eligible.
- Reuse existing project-scoped tmux windows named `agent-pick-<id>` or
  `agent-resume-<id>` instead of launching duplicate agents.
- Update current-state board documentation for the new mode and shortcuts.

## Test Plan

- New board In-Flight model and Pilot tests:
  - implementing task without a ledger is included;
  - ready task with a ledger is excluded;
  - pending human gate maps to `Needs your action`;
  - satisfied gated dependency no longer blocks dependents;
  - parser failure fails closed and stays visible;
  - `i` swaps kanban columns for In-Flight columns and `a` returns;
  - existing agent window guard reuses the tmux window.
- Full verification:
  - `bash tests/run_all_python_tests.sh`
  - `python tests/test_gate_ledger_python_parser.py`
  - `bash tests/test_query_files_inflight.sh`
  - `python -m py_compile .aitask-scripts/board/aitask_board.py tests/test_board_inflight_view.py`
  - `hugo --minify --quiet` from `website/`

## Final Implementation Notes

- **Actual work done:** Implemented the board In-Flight mode as an in-board base
  view. Added cached gate-state helpers, In-Flight rows/columns, explicit
  human-gate selection, direct resume launch, duplicate pick/resume window
  detection, and current-state docs.
- **Deviations from plan:** Kept `g`, `s`, and `f` as contextual In-Flight
  shortcuts because those keys already mean Git, Sync, and Free in normal board
  mode. Selector clicks and normal board use keep their previous behavior.
- **Issues encountered:** The website docs had stale pre-existing wording for an
  older `a/g/i` view model; the touched board docs were corrected to the current
  base-view plus add-on-filter model while adding In-Flight.
- **Key decisions:** Gate-aware dependency display is consumed through the same
  cached parser path as In-Flight and fails closed, so existing views do not
  crash or unblock tasks when registry/parser state is unavailable.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** t635_10 can use the same `TaskManager.gate_state_for`
  pattern for monitor-visible gate status instead of adding a second parser path.
  Future public `ait gate pass/fail` commands can replace the board's internal
  `aitask_gate.sh append` call without changing the In-Flight grouping model.
- **Verification:** `bash tests/run_all_python_tests.sh` (1225 tests);
  `python tests/test_gate_ledger_python_parser.py` (28/28);
  `bash tests/test_query_files_inflight.sh` (6/6);
  `python -m py_compile .aitask-scripts/board/aitask_board.py tests/test_board_inflight_view.py`;
  `hugo --minify --quiet`.
