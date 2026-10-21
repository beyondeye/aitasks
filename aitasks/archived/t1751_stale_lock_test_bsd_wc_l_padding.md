---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [bash_scripts, testing, macos, tests]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1681
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-09-08 22:28
updated_at: 2026-10-21 12:19
completed_at: 2026-10-21 12:19
---

## Origin

Spawned from t1746 during Step 8b review. Found while establishing a dual-shell
(bash 3.2 / 5.3.9) baseline for t1746 — the failures are **pre-existing and
unrelated to t1746's change**, and were proven so by running
`git show HEAD:tests/test_stale_lock.sh` unmodified.

## Upstream defect

- `tests/test_stale_lock.sh:470` — `assert_eq "no .reap residue is left behind" "0" "$(find … | wc -l)"` → got `'       0'`
- `tests/test_stale_lock.sh:671` — `assert_eq "exactly ONE record remains in the guard" "1" "$(find … | wc -l)"` → got `'       1'`

## Problem

Both assertions compare an exact string against BSD `wc -l` output, which pads
with leading spaces on macOS. `aidocs/framework/sed_macos_issues.md` §
"`wc -l` Output Whitespace" already documents exactly this trap, including the
distinction that arithmetic contexts (`-gt`, `$(( ))`) are safe while exact
string comparisons are not.

Measured on macOS 15 / Darwin 24.6.0, both shells:

```
Results: 132/134 passed, 2 failed      (rc=1)
FAIL: no .reap residue is left behind (expected '0', got '       0')
FAIL: exactly ONE record remains in the guard (expected '1', got '       1')
```

Identical at HEAD, so `tests/test_stale_lock.sh` is currently **red on macOS**
for every developer, masking any genuine regression the file would otherwise
catch.

## Proposed fix

Use `assert_eq_trim` (already in `tests/lib/asserts.sh`) at both sites, or pipe
the count through `tr -d ' '`. Prefer `assert_eq_trim` — it is the existing
shared helper for exactly this shape.

## Blast radius

Sweep the whole `tests/` tree for the same shape before fixing only these two:
an exact `assert_eq` whose actual value comes from `| wc -l`. The documented
rule says arithmetic uses are fine, so scope the sweep to string comparisons.

## Verification

- `bash tests/test_stale_lock.sh` → `134/134 passed`, rc=0 on macOS.
- Also run under `/bin/bash` (3.2): must be green there too.
- Confirm no assertion was weakened — the trimmed compare must still fail if the
  count is genuinely wrong (probe by temporarily seeding a second record).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T08:58:16Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-21T09:17:11Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-21T09:19:43Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:d06a13e3341126ec

> **✅ gate:risk_evaluated** run=2026-10-21T09:19:43Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1751/risk_evaluated_2026-10-21T09:19:43Z-risk_evaluated-a1.log`
