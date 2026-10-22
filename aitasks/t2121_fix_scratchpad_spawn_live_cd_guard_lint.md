---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-10-22 10:38
updated_at: 2026-10-22 11:17
---

## Origin

Spawned from t2028 during Step 8b review.

## Upstream defect

- `tests/test_scratchpad_spawn_live.sh:218` — an unconfined `(cd "$1" && …)` in `key_for()`, and no `enter_scratch_cwd` call before the file's first `cd`, make `tests/test_cd_guard_lint.sh` fail (2 failures, pre-existing, from t2088's commit 4da69fcfb).

Line numbers are as of commit 8083796bc. Re-derive them before editing.

## Diagnostic context

While running the crew regression set for t2028, `bash tests/test_cd_guard_lint.sh` reported 90 passed / 2 failed:

- `FAIL: no cd/pushd guard violations in tests/ (see testing_conventions.md) (expected '0', got '1')`, naming `tests/test_scratchpad_spawn_live.sh:218:unconfined-andchain: (cd "$1" && if [ -n "${3:-}" ]; then …`
- `FAIL: every cwd-changing test calls enter_scratch_cwd first (expected '', got '…/tests/test_scratchpad_spawn_live.sh: no enter_scratch_cwd call (first cd at line 218)')`

Neither failure involves files that t2028 touched.

## Suggested fix

Follow `aidocs/framework/testing_conventions.md`: source `tests/lib/scratch_cwd.sh` and call `enter_scratch_cwd` at the top of the file, and rewrite `key_for()`'s `cd` in a form the lint accepts (as t2079 did for three other tests). Then re-run `tests/test_cd_guard_lint.sh` and the live test itself.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-22T08:17:15Z status=pass attempt=1 type=human
>
> Note: drift
