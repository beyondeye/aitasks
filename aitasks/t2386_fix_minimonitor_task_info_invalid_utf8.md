---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [trails]
gates: [risk_evaluated]
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-27 11:57
updated_at: 2026-11-27 11:57
---

## Origin

Spawned from t2379 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:7111 — TaskInfoCache._resolve reads the task file with Path.read_text() and does not catch UnicodeDecodeError, so get_task_info() (minimonitor task picker) raises on a task file that is not valid UTF-8 (probed: t410 with a 0xff byte raises; its dependent t411 resolves 410 as UNRESOLVABLE correctly)`

## Diagnostic context

t2379 made the local dependency core (`lib/dep_resolution.py`) and the
blocking scan treat a task file that is not valid UTF-8 as unreadable:
`facts()` returns `None` (the dependency renders `<id> (UNRESOLVED)`), the
scan writes an `UNVERIFIED<TAB><path>` row, and `ait ls` lists that task as
`Blocked (by …) [unverified]`. The minimonitor's own reader was left out of
scope. A probe on the `tests/test_local_dep_parity.py` fixture tree
(`make_tree` + `populate`, plus `t410_x.md` with a `0xff` byte in its body)
showed `TaskInfoCache(tree).get_task_info("410")` raising
`UnicodeDecodeError` from `_resolve` (`Path.read_text()`, line 7111 against
commit 751b4c59f), while a dependent of it resolves correctly through the
shared core. The board was not probed. Re-check line numbers before editing.

## Suggested fix

Catch `UnicodeDecodeError` beside the existing read failures in
`TaskInfoCache._resolve` and give the task the same unreadable outcome an
I/O error gets there; add a test with an invalid-UTF-8 task file through
`get_task_info()` (and probe the board's task reader the same way).
