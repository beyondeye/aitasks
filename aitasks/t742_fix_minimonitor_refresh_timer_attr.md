---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini]
created_at: 2026-05-04 16:24
updated_at: 2026-05-04 16:24
---

## Origin

Spawned from t738 during Step 8b review.

## Upstream defect

`.aitask-scripts/monitor/minimonitor_app.py:202` — `_teardown_prior_monitoring()` references `self._refresh_timer`, which is never assigned in `__init__`. Calling `_teardown_prior_monitoring()` raises `AttributeError: 'MiniMonitorApp' object has no attribute '_refresh_timer'`. Reproduced via `bash tests/test_multi_session_minimonitor.sh` (failure surfaces before any of the multi-session assertions can run).

## Diagnostic context

- Surfaced while running the standard regression smoke (`tests/test_multi_session_minimonitor.sh`) as a sanity check after fixing the archived-task lookup in `monitor_shared.py:_resolve()` (t738).
- Confirmed pre-existing by stashing the t738 edits and re-running the test on clean `main` — same `AttributeError` at the same line, so unrelated to t738's archived-fallback work.
- The traceback also implicates `_start_monitoring` at line 223 (the caller of `_teardown_prior_monitoring`).

## Suggested fix

Initialize `self._refresh_timer = None` in `MiniMonitorApp.__init__` (or wherever sibling state like `self._refresh_data` is set). Audit any other timer-like attributes that `_teardown_prior_monitoring` touches for the same pattern. Re-run `bash tests/test_multi_session_minimonitor.sh` to verify the regression test gets past the teardown step.
