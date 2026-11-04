---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing]
gates: [risk_evaluated]
anchor: 2034
followup_kind: upstream_defect
created_at: 2026-11-04 12:33
updated_at: 2026-11-04 12:33
---

## Origin

Spawned from t2034_3 during Step 8b review.

## Upstream defect

- `tests/test_python_bootstrap_isolation.sh:1 — fails before and after this task on 5 test files whose own sys.path bootstrap is incomplete (test_parallel_admission_vocab.py, test_prompt_detection.py, test_stats_backlog_panes_live.py, test_stats_focus_cycle_and_pane_selector_live.py, test_trails_app.py); they pass only because another module put the directory on sys.path first`

## Diagnostic context

t2034_3's step-0 baseline (2026-11-04, before any edit) ran
`bash tests/test_python_bootstrap_isolation.sh` and got `9 passed, 1 failed`: the check
"every tests/test_*.py imports with its own sys.path bootstrap" listed the five files above.
The same five, and only those, were still listed after t2034_3's new test files were added.
Both new files import cleanly in isolation. Reproduce one with:

    env -u PYTHONPATH python3 tests/lib/import_isolated.py tests/<file>.py

`test_prompt_detection.py`, for example, does `import review_loop_fixtures as fx` and
inserts only `.aitask-scripts` on `sys.path`. In isolation that import fails unless the
`tests/` directory is already on the path, which it is when the file runs as a script,
but not under the isolated importer. Other sessions were editing nearby files during this
window, so check `git log` for when each file regressed before you fix it.

## Suggested fix

Give each of the five files its own complete bootstrap: insert every directory it imports
from (`tests/`, `tests/lib/`, `.aitask-scripts/lib/`, …) at the top, following the
pattern in `tests/test_monitor_status_recording.py`. Then re-run the isolation test until
it reports 10/10.
