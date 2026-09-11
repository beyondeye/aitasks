---
Task: t1794_11_measure_document_retrospective.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md … t1794_10_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_11 — Measure, document, retrospective

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C6, C8 PINNED; "Scope decisions"). Depends on `t1794_8` and `t1794_10`.

## Measurements

1. `tests/perf/board_footprint.sh` for `aitask_board` and `trails_app` under
   `~/.aitask/venv/bin/python` and `~/.aitask/pypy_venv/bin/python` at the
   current SHA; signed margins vs the child-1 baseline and ceiling.
2. t718_6-protocol Pilot benchmark for `trails_app` (boot → selector → pick →
   `enter` → `escape` → `v` → `escape` → `d` patched → 10× down; 5 warmup +
   8 measured reps per interpreter). Verdict KEEP-CPython / SWITCH-fast by the
   documented threshold; on SWITCH edit `aitask_trails.sh` and extend the
   `AIT_USE_PYPY` table + scope line in `tui_conventions.md:7–63`.

## Docs

- `aidocs/framework/python_tui_performance.md`: results table (six
  footprint rows + benchmark) and verdict.
- `aidocs/framework/tui_conventions.md`: board package layout section — file
  map, C1, C2, C10 (shared screen registers under the owning scope with the
  same `Binding` objects; unsupported actions declared-but-hidden), `trails`
  in the switcher-visible list.
- `CLAUDE.md:143–147` board line → package; `:431–435` verified.
- `tests/lib/board_fixture.py:1–100` docstring `aitask_board.py:NN` refs.
- `aidocs/framework/aitasks_extension_points.md` only if its structure
  warrants a line (read first; don't duplicate).

## Retrospective

Against the numbers and child 8's residual class list: (a) further
extraction worth a task? (b) any `board_*` module promotable to `lib/`
(only with no board imports — `test_no_lib_to_tui_import.sh`)? (c) does the
C10 `?`-editor-imports-the-board limitation deserve a filtered editor? File a
standalone follow-up **only** where the data says so (numbers quoted in its
body); otherwise record "no follow-up" with the reason. Walk the parent's
acceptance criteria one by one with a pointer to the evidence for each.

## Verification

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `bash
  tests/test_serial_carveout_doc_drift.sh` green.
- The signed-margin table and verdict exist; `aitask_trails.sh`'s resolver
  matches the verdict.
- `grep -n 'board/aitask_board.py' CLAUDE.md` shows the package description.
- Acceptance-criteria walk recorded here.

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_11`. The
parent `t1794` then archives via the orphaned-parent path.
