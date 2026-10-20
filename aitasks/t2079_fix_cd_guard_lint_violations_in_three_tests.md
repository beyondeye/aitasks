---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tests]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2073
followup_kind: upstream_defect
created_at: 2026-10-20 12:26
updated_at: 2026-10-20 12:32
---

## Origin

Spawned from t2073_1 during Step 8b review.

## Upstream defect

- `tests/test_ait_git_gateway_pull.sh:769 — unconfined-andchain cd (`(unset …; cd "$FX_LOCAL" && ./ait git …)`) fails test_cd_guard_lint.sh section 1`
- `tests/test_archive_rearm_exit_trap.sh:262 — changes cwd with no enter_scratch_cwd call; fails test_cd_guard_lint.sh (landed with t2032)`
- `tests/test_session_hook.sh:429 — changes cwd with no enter_scratch_cwd call; fails test_cd_guard_lint.sh (landed with t2047)`

## Diagnostic context

While fixing t2073_1's own new test (`tests/test_scratchpad_store.sh` was missing
`enter_scratch_cwd`, reported by `python3 tests/lib/cd_guard_scan.py --helper-order`),
`bash tests/test_cd_guard_lint.sh` still reported `Results: 90 passed, 2 failed`.
The remaining failures are in the three files above, none touched by t2073_1:

- section 1 "no cd/pushd guard violations in tests/" names
  `test_ait_git_gateway_pull.sh:769:unconfined-andchain`;
- "every cwd-changing test calls enter_scratch_cwd first" names
  `test_archive_rearm_exit_trap.sh` (first cd at line 262) and `test_session_hook.sh`
  (first cd at line 429).

`test_ait_git_gateway_pull.sh` was being edited by a concurrent session at the time —
re-check the line before fixing (it may have moved or been fixed). The other two are
committed on main (a822af352 t2032, 00322dab0 t2047).

## Suggested fix

Per `aidocs/framework/testing_conventions.md` / `tests/lib/scratch_cwd.sh`: source
`tests/lib/scratch_cwd.sh` and call `enter_scratch_cwd` right after `PROJECT_DIR` in the
two files; confine or exit-guard the `cd` at the gateway-pull site (the scanner's rule in
`tests/lib/cd_guard_scan.py`). Then `bash tests/test_cd_guard_lint.sh` must report 0 failed,
and each of the three suites must still pass.
