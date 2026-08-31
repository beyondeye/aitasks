---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [macos, tests]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1569
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-31 10:59
updated_at: 2026-08-31 17:35
---

## Origin

Spawned from t1641 during Step 8b review.

## Upstream defect

- `tests/test_sync_branch_mode_automerge.sh:334` — same BSD-sed portability defect
  as the one fixed in t1641, in an unrelated suite:
  `int_clean=$(printf '%s' "$int_out" | sed 's/\x1b\[[0-9;]*m//g')`. GNU sed
  interprets `\x1b` as the ESC byte; **BSD sed (macOS) does not** — it matches a
  literal `x`, `1`, `b`, so the substitution never fires and the ANSI wrapper
  survives the strip. There is no error: the caller just receives the un-stripped
  string.

**Impact correction (verified during implementation).** This task was originally
filed claiming that "whatever `$int_clean` is asserted against fails against
correct code". That is **not** true at this site, and the claim was checked
empirically by capturing the real bytes of `$int_out` from a live run of Test 5b.
All three assertions there tolerate the colour wrapper:

- the two `grep -c … == 0` checks are negative assertions, unaffected by it;
- `assert_contains "Editing: aitasks/t2_body.md"` still matches, because the ESC
  codes sit *outside* the phrase.

Running the suite with the strip replaced by what BSD sed actually sees confirms
it: 15 of 17 assertions still pass. So nothing observable fails on macOS today.

The real defect is that the strip is a **silent no-op** there, which leaves two
live traps: assertion 3 passes for the wrong reason, and any future tightening to
an exact `assert_eq` — precisely the tightening `tests/test_task_lock.sh:592`'s
own comment warns about — would then fail on macOS against correct code.

## Diagnostic context

Surfaced by the class sweep that `aidocs/framework/sed_macos_issues.md` mandates
("After fixing one portability bug, sweep for the whole class") after t1641 hit the
identical bug in a test it had just written. t1641 fixed only its own site
(`tests/test_task_lock.sh`) and added the missing `\xNN` row to that guide; this
site belongs to a different suite and was left out of t1641's commit because
t1641's scope is the lock CLI.

Note the failure mode is macOS-only and silent — on Linux the test passes, so this
will not be caught by any CI or local run on a GNU box.

## Suggested fix

Replace with the portable form now documented in
`aidocs/framework/sed_macos_issues.md`: `sed $'s/\033\[[0-9;]*m//g'`. The `$'...'`
quoting makes **bash** emit the literal ESC byte, so sed never has to interpret an
escape and GNU and BSD behave identically. See `tests/test_task_lock.sh:592` for the
same fix with its explanatory comment. While there, re-run the sweep
(`grep -rnE "(sed|awk)[^|]*\\\\x[0-9a-fA-F]{2}" --include="*.sh" .`) to confirm no
third site has appeared.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-31T14:35:01Z status=pass attempt=1 type=human
