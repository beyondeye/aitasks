---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [test_infrastructure]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2235
followup_kind: upstream_defect
created_at: 2026-11-08 15:08
updated_at: 2026-11-08 15:39
---

## Origin

Spawned from t2235 during Step 8b review.

## Upstream defect

- `tests/test_premise_check_workflow.sh:154,487` — `unconfined-andchain` cd-guard violations (committed in 620039d7b, t1663_4) keep `tests/test_cd_guard_lint.sh` red.

## Diagnostic context

While validating t2235, `bash tests/test_cd_guard_lint.sh` reported its one live-tree failure, unrelated to t2235's changes:

```
FAIL: no cd/pushd guard violations in tests/ (see testing_conventions.md) (expected '0', got '1')
tests/test_premise_check_workflow.sh:154:unconfined-andchain: ( cd "$d" && { ./.aitask-scripts/aitask_lock.sh --check "$id" >/dev/null 2>&1 \
tests/test_premise_check_workflow.sh:487:unconfined-andchain: ( cd "$P" && ./.aitask-scripts/aitask_lock.sh --unlock 606 >/dev/null 2>&1
```

The file has had no uncommitted changes since 620039d7b (t1663_4). The guard (t1826) accepts only exit-guarded or properly confined cd forms; `( cd X && … )` is flagged because a failed cd inside an and-chain does not stop the subshell's later commands in every shape (see `tests/lib/cd_guard_scan.py`).

## Suggested fix

Rewrite both sites into an accepted form, e.g. `( cd "$d" || exit 1; … )`. Then confirm `bash tests/test_cd_guard_lint.sh` is green and `bash tests/test_premise_check_workflow.sh` still passes. See `aidocs/framework/testing_conventions.md` ("Every cd in a bash test is exit-guarded").
