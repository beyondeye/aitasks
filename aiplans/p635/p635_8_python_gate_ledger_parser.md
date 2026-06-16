---
Task: t635_8_python_gate_ledger_parser.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_9_board_inflight_action_view.md, aitasks/t635/t635_10_monitor_gate_status_column.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_*.md ... p635_7_gate_aware_aitask_pick.md
Base branch: main
---

# t635_8 - Shared Python Gate Ledger Parser

## Summary

Extend `.aitask-scripts/lib/gate_ledger.py` as the shared Python derivation
surface for future TUI work. Preserve existing CLI behavior and legacy helper
functions while adding structured, importable APIs that board, monitor, and
future TUI code can consume without forking gate parsing logic.

## Key Changes

- Add structured parser APIs: `GateRun`, `parse_gate_run_blocks`,
  `derive_gate_runs`, and `has_gate_markers`.
- Add `TaskGateState` plus `read_task_gate_state(task_file, registry_file=None)`
  to bundle declared gates, current gate runs, formatted status, archive
  readiness, dependency-unblock status, and workflow resume point.
- Keep the module stdlib-only and keep existing CLI output byte-compatible with
  the bash `aitask_gate.sh status/list/deps-unblock/archive-ready/resume-point`
  surfaces.
- Do not integrate board or monitor UI in this task; t635_9 and t635_10 consume
  this parser API later.

## Test Plan

- Add `tests/test_gate_ledger_python_parser.py`, runnable directly with the
  project Python.
- Cover repeated gate runs, last-run current-state derivation, body-field
  parsing, malformed non-marker lines ignored, empty/no-marker fast path,
  declared gates, archive/dependency/resume derivations, and a parity fixture
  comparing Python formatted status against `aitask_gate.sh status`.
- Run focused verification:
  - `python tests/test_gate_ledger_python_parser.py`
  - `bash tests/test_gate_ledger.sh`
  - `bash tests/test_dependency_unblock.sh`
  - `bash tests/test_query_files_inflight.sh`

## Assumptions

- No new frontmatter fields, cached gate summary, or task status values.
- No PyYAML or third-party dependency; this remains safe for the board PyPy fast
  path.
- Existing unrelated local changes remain untouched.
- Website docs are deferred to later t635 documentation tasks because this task
  adds internal parser infrastructure only.

## Final Implementation Notes

- **Actual work done:** Extended `.aitask-scripts/lib/gate_ledger.py` with
  structured `GateRun` and `TaskGateState` dataclasses, `parse_gate_run_blocks`,
  `derive_gate_runs`, `has_gate_markers`, `read_declared_gates_from_text`, and
  `read_task_gate_state`. Existing legacy dict APIs and CLI output remain
  compatible.
- **Deviations from plan:** Kept the implementation in the existing module and
  made `dependents_status`, `archive_status`, and `resume_point` derive from the
  same structured parser rather than maintaining a parallel parser path.
- **Issues encountered:** The new direct Python test initially loaded the module
  via `importlib` without inserting it into `sys.modules`, which trips
  `dataclasses`; the test harness now registers the module before execution.
- **Key decisions:** Body fields are parsed generically from `> Label: value`
  lines into normalized lowercase keys, with single wrapping backticks stripped
  for TUI-friendly display. The marker prefilter keys off gate marker lines, not
  the section header, so edited/missing headers do not hide valid runs.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** t635_9 and t635_10 should import
  `read_task_gate_state` / `has_gate_markers` from `gate_ledger.py` instead of
  shelling out or re-parsing task bodies. `status_text` preserves current
  `aitask_gate.sh status` formatting for compact display; `current` and
  `archive_*` / `dependents_*` / `resume_point` provide structured state for
  grouping and action routing.
- **Verification:** `python tests/test_gate_ledger_python_parser.py`;
  `bash tests/test_gate_ledger.sh`; `bash tests/test_dependency_unblock.sh`;
  `bash tests/test_query_files_inflight.sh`; `python -m py_compile
  .aitask-scripts/lib/gate_ledger.py tests/test_gate_ledger_python_parser.py`.
