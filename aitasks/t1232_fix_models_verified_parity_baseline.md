---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-24 14:55
updated_at: 2026-07-24 14:55
---

## Origin

Spawned from t1210_3 during Step 8b review.

## Upstream defect

- `aitasks/metadata/models_claudecode.json` (live task-data) — `opus4_8` carries a stats-accumulated `verified["work-report"]: 100` with no `explain` key, so `tests/test_codeagent_work_report.sh` Test 7 (t1162_2 parity rule: work-report mirrors explain, absent where explain absent) exits 1 at HEAD.

## Diagnostic context

t1210_3's verification battery ran `bash tests/test_codeagent_work_report.sh` as a regression check after registering the `trail` codeagent operation. Test 7 failed on the live `models_claudecode.json`. Comparing against the task-data branch HEAD (before any t1210_3 change) proved the violation pre-existed: the verifiedstats accumulator recorded a real work-report run score of 100 for `opus4_8`, a model whose `verified` map has no `explain` key, which the t1162_2 parity rule forbids ("work-report mirrors explain, absent where explain absent"). t1210_3's own `verified["trail"]` additions correctly left `opus4_8` untouched, and the equivalent parity test in `tests/test_codeagent_trail.sh` Test 7 passes — but it inherits the same fragility: any live-accumulated score on a model without `explain` will break it.

## Suggested fix

Decide which side owns the invariant: either relax the parity assertions in `tests/test_codeagent_work_report.sh` / `tests/test_codeagent_trail.sh` to tolerate live verifiedstats-accumulated scores (e.g. only assert parity in the seed files), or make the verified-score accumulator refrain from creating `verified` entries for operations whose parity partner (`explain`) is absent on that model.
