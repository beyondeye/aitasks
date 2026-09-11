---
priority: medium
effort: medium
depends: [1794_8, 1794_10]
issue_type: documentation
status: Ready
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 11 of t1794 — measure, document, and evaluate. The parent promised
every "saves memory / cold-start" claim as a **signed margin measured in the
same interpreter on the same task tree** (contract C8), and deferred the
interpreter choice for `ait trails` to a real benchmark (`tui_conventions.md`
forbids routing a launcher to the PyPy fast path by analogy). This child
closes both, updates the developer docs to the new board layout, and is the
retrospective-evaluation child the planning conventions call for: it files
standalone follow-ups only if the collected data justifies them. It depends
on child 8 (last extraction) and child 10 (website docs), and is the last
child before the parent archives.

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— C6, C8, child 11 section, "Scope decisions";
`aidocs/framework/python_tui_performance.md` (the "t718_6 Empirical
Verification" protocol and the child-1 "t1794 baseline" section);
`aidocs/framework/planning_conventions.md` ("retrospective-evaluation child").

## Key files to modify

- `aidocs/framework/python_tui_performance.md` — results table: RSS at 10 s
  idle and cold-start for `aitask_board` (before: child-1 baseline; after:
  now) and `trails_app`, under `~/.aitask/venv/bin/python` and
  `~/.aitask/pypy_venv/bin/python`, plus the ceiling, all as signed margins
  with the SHA and task-tree size; the t718_6-protocol Pilot benchmark for
  `trails_app` (CPython vs PyPy steady state + cold start) with a KEEP/REVERT
  verdict for the fast path.
- `.aitask-scripts/aitask_trails.sh` — switch `require_ait_python` →
  `require_ait_python_fast` **only** on a measured PyPy win; then extend the
  `AIT_USE_PYPY` table in `aidocs/framework/tui_conventions.md:39–63` and the
  "current scope" line at `:7–11`. Otherwise leave it and record the verdict.
- `aidocs/framework/tui_conventions.md` — a section on the board package
  layout: the file map, C1 (flat imports, `board_` prefix, no import-back,
  injected helpers), C2 (no import-time `TASKS_DIR` in siblings — pass paths),
  C10 (a screen shared by two Apps registers under the owning scope with the
  same `Binding` objects; unsupported actions stay declared-but-hidden), and
  `trails` in the switcher-visible TUI list.
- `CLAUDE.md:143–147` — the board file-map line becomes the package (list the
  modules); `:431–435` already names `trails` (child 6) — verify.
- `aidocs/framework/aitasks_extension_points.md` — a line for "adding a
  second App to an existing TUI package" if the doc's structure warrants it
  (read it first; do not duplicate `tui_conventions.md`).
- `tests/lib/board_fixture.py:1–100` docstring — update the module map it
  cites (`aitask_board.py:NN` references inside the docstring).

## Reference files for patterns

- `aidocs/framework/python_tui_performance.md` "t718_6 Empirical Verification
  — board / codebrowser under PyPy" — workload, reps, reporting shape.
- `tests/perf/board_footprint.sh` (child 1).
- `tests/test_board_view_filter.py:76` — the `App.run_test(size=(160, 48))`
  Pilot driver the t718_6 benchmark used.
- `aidocs/framework/documentation_conventions.md` — current-state-only prose.

## Implementation plan

1. **Rebase check** (parent pre-phase): confirm children 1–10 are archived
   (`aitask_query_files.sh archived-children 1794`); re-read the child plans'
   recorded numbers (child 1 baseline, child 6 margins); `git log --oneline
   -20 -- .aitask-scripts/board/`.
2. Re-run `tests/perf/board_footprint.sh` for `aitask_board` and `trails_app`
   under both interpreters at the current SHA; compute signed margins vs the
   child-1 baseline and the ceiling.
3. Run the t718_6 Pilot benchmark for `trails_app` (workload: boot → selector
   → pick trail → `enter` → `escape` → `v` → `escape` → `d` with drift
   patched → 10× down; 5 warmup + 8 measured reps per interpreter); decide
   KEEP-CPython / SWITCH-to-fast by the documented threshold (≥10% steady-state
   win and the cold-start regression acceptable for the modal session length).
4. Docs: performance aidoc, TUI conventions section, CLAUDE.md, fixture
   docstring, extension points if warranted.
5. **Retrospective**: against the numbers and the residual `aitask_board.py`
   class list (child 8), judge (a) whether further extraction is worth a
   task, (b) whether any `board_*` module should be promoted to `lib/`
   (only if it has no board imports — `tests/test_no_lib_to_tui_import.sh`),
   (c) whether the `?`-editor-imports-the-board limitation (C10) deserves a
   filtered editor. File a standalone follow-up **only** where the data says
   so, with the numbers quoted in its body; otherwise record "no follow-up"
   with the reason.

## Verification steps

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `bash
  tests/test_serial_carveout_doc_drift.sh` green (no carve-out change
  expected — confirm).
- The signed-margin table exists in `python_tui_performance.md` with six
  footprint rows (board ×2, trails ×2, ceiling, before/after) and the
  benchmark verdict; `aitask_trails.sh`'s resolver matches the verdict.
- `grep -n 'board/aitask_board.py' CLAUDE.md` shows the package description;
  `python3 website/check_links.py --build` still green if any website page
  was touched (none expected).
- The parent's acceptance criteria are walked one by one in this child's
  plan with a pointer to the evidence (test / number / page) for each.
