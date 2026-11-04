---
Task: t2195_fix_test_bootstrap_isolation_incomplete_paths.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t2195 — complete the sys.path bootstrap in five test files

## Context

`tests/test_python_bootstrap_isolation.sh` imports every `tests/test_*.py` in its
own PYTHONPATH-free interpreter (driver `tests/lib/import_isolated.py`). Baseline
on 2026-11-04: `9 passed, 1 failed` — Test 1 lists five files. Every one fails the
same way: it imports a **sibling module living in `tests/`** without putting
`tests/` on `sys.path`. Under pytest / `unittest discover`, `tests/` is already on
the path (or another module inserted it), which masked the gap.

| file | failing import | current bootstrap |
|---|---|---|
| `tests/test_parallel_admission_vocab.py` | `import test_parallel_admission` (in `_fixtures()`, called at module level line 182) | `.aitask-scripts/lib` only |
| `tests/test_prompt_detection.py` | `import review_loop_fixtures` (`tests/review_loop_fixtures.py`) | `.aitask-scripts` only |
| `tests/test_stats_backlog_panes_live.py` | `from test_stats_backlog_panes import _stats` | `.aitask-scripts`, `.aitask-scripts/lib` loop |
| `tests/test_stats_focus_cycle_and_pane_selector_live.py` | `from test_stats_backlog_panes_live import _fixture` | same loop |
| `tests/test_trails_app.py` | `from test_board_bytrail_view import …` | `tests/lib`, `.aitask-scripts/board`, `.aitask-scripts/lib` |

None of the five is dirty in the working tree (checked `git status --short`).

## Change (one pattern, five files)

Add the `tests/` directory (the file's own directory) to the existing bootstrap,
following the guarded-insert pattern of `tests/test_monitor_status_recording.py:30-34`.
No other directory is missing — every other import in these files already resolves
(verified by the tracebacks: each stops at the sibling import).

1. `test_parallel_admission_vocab.py` — after `sys.path.insert(0, LIB_DIR)` add
   `sys.path.insert(0, TESTS_DIR)` (TESTS_DIR already defined).
2. `test_prompt_detection.py` — add
   `sys.path.insert(0, str(Path(__file__).resolve().parent))` next to the existing
   `.aitask-scripts` insert.
3. `test_stats_backlog_panes_live.py` and
4. `test_stats_focus_cycle_and_pane_selector_live.py` — extend the existing loop
   tuple to `(str(SCRIPTS), str(SCRIPTS / "lib"), str(PROJECT_DIR / "tests"))`.
5. `test_trails_app.py` — add `sys.path.insert(0, str(REPO_ROOT / "tests"))`
   beside the existing `tests/lib` insert.

Insertion order is irrelevant here: no module name in `tests/` shadows one in
`.aitask-scripts/` for these imports (they are all `test_*` / `review_loop_fixtures`).

## Verification

- Each file: `env -u PYTHONPATH ~/.aitask/venv/bin/python tests/lib/import_isolated.py tests/<file>.py` exits 0.
- `bash tests/test_python_bootstrap_isolation.sh` → `10 passed, 0 failed`.
- Run the five modules normally to prove nothing regressed:
  `~/.aitask/venv/bin/python -m pytest -q tests/test_parallel_admission_vocab.py tests/test_prompt_detection.py tests/test_trails_app.py tests/test_stats_backlog_panes_live.py tests/test_stats_focus_cycle_and_pane_selector_live.py`
  (falls back to `python -m unittest` per file if pytest is absent).

Step 9 (Post-Implementation): commit the five test files with
`bug: Complete sys.path bootstrap in five test files (t2195)`, then archive.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
