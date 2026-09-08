---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, testing, macos, tests]
gates: [risk_evaluated]
anchor: 1681
followup_kind: upstream_defect
created_at: 2026-09-08 22:28
updated_at: 2026-09-08 22:28
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
