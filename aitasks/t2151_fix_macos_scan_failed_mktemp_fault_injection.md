---
priority: medium
risk_code_health: low
risk_goal_achievement: low
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
anchor: 1689
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 14:46
updated_at: 2026-10-26 15:27
---

## Origin

Spawned from t2146 during Step 8b review.

## Upstream defect

- `tests/test_sync_protect_paths.sh:241 — drive_scan_failed injects failure via TMPDIR=<missing dir>, but macOS mktemp ignores a nonexistent TMPDIR and succeeds, so the scan_failed reason never fires on macOS (1 failure, independent of t2146)`

## Diagnostic context

t2146's step-0 sweep ran `tests/test_sync_protect_paths.sh` on macOS (Darwin 24.6). It failed 2 of 31. One of those, `live_lock`, was the weak-token issue t2146 fixed. The other remains after t2146:

    FAIL: scan_failed: the reason actually fired (expected output containing 'nothing swept', got '')

`drive_scan_failed` (around line 241) runs the sweep with `TMPDIR="$t/no_such_dir"` so that `mktemp` in `aitask_sync.sh:1007` (`dirtyf="$(mktemp)" || { _protect "scan_failed" ... "nothing swept" ...}`) fails. On macOS, BSD `mktemp` falls back to the per-user confstr temp dir when `$TMPDIR` does not exist:

    $ TMPDIR=/nonexistent_dir_x mktemp
    /var/folders/fm/.../T/tmp.nv4VQWoOMl   (rc=0)

The fault injection never fires, the branch is never reached, and the test fails on macOS while passing on GNU/Linux.

## Suggested fix

Use a fault seam that works on both platforms. Options: a PATH shim `mktemp` that exits 1 in the fixture's `bin/`, or an existing `AIT_SYNC_SEAM_*` hook if one covers this point. Keep the "the reason actually fired" assertion, and run the pre-fix control on macOS.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-26T13:27:53Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-26T13:46:54Z status=pass attempt=1 type=human
