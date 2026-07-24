---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [testing]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-24 15:17
updated_at: 2026-07-24 15:17
---

## Origin

Risk-mitigation ("after") follow-up for t1217, created at Step 8d after implementation landed.

## Risk addressed

Code-health — from t1217's plan:

> A missed or wrong `sys.path` bootstrap surfaces only at TUI runtime, **not**
> under the test suite — `tests/run_all_python_tests.sh` exports both `board/`
> and `lib/` on `PYTHONPATH`, so it passes even with a broken per-file
> bootstrap. `diffviewer/plan_loader.py` and `codebrowser/history_data.py` are
> the thinnest-covered consumers · severity: medium

t1217 defeated this with **manual** verification steps (an `env -u PYTHONPATH`
pytest run plus entry-module import assertions). That only works while someone
remembers to run them — the masking itself is still in place.

## Goal

Make the masking structurally impossible rather than relying on a manual check.

`tests/run_all_python_tests.sh:17-18` currently does:

```bash
# Add board and lib modules to PYTHONPATH for imports
export PYTHONPATH="$PROJECT_DIR/.aitask-scripts/board:$PROJECT_DIR/.aitask-scripts/lib${PYTHONPATH:+:$PYTHONPATH}"
```

Every test file already sets up its own `sys.path` from `__file__`, so this
export is a belt-and-braces convenience that hides real bootstrap bugs: a test
whose own `sys.path.insert` is wrong still passes.

Pick one of:

1. **Drop the export** and fix any test that turns out to depend on it (the
   honest fix — each test then proves its own bootstrap).
2. **Add an isolated lane** — a second pass over the same test files with
   `env -u PYTHONPATH`, so per-file bootstraps are exercised as shipped while
   the convenience export stays for the main pass.

Option 1 is preferred if the fallout is small; measure it first by running the
suite with the export removed and counting failures.

## Key files

- `tests/run_all_python_tests.sh` — the runner (lines 17-18)
- any test file that fails once the export is removed

## Verification

- The suite passes with no `PYTHONPATH` inherited from the runner.
- **Negative control (required — the point of the task):** temporarily break
  one test file's own `sys.path.insert` (e.g. point
  `tests/test_history_data.py` at a nonexistent dir) and confirm the runner now
  **exits non-zero**. Before this change it exits 0. Undo by reversing that one
  edit — do NOT `git checkout --`, which would discard unrelated uncommitted
  work in a shared checkout.
- `bash tests/test_no_lib_to_tui_import.sh` still passes.
