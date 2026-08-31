---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [macos, tests]
anchor: 1569
followup_kind: upstream_defect
created_at: 2026-08-31 10:59
updated_at: 2026-08-31 10:59
---

## Origin

Spawned from t1641 during Step 8b review.

## Upstream defect

- `tests/test_sync_branch_mode_automerge.sh:334` — same BSD-sed portability defect
  as the one fixed in t1641, in an unrelated suite:
  `int_clean=$(printf '%s' "$int_out" | sed 's/\x1b\[[0-9;]*m//g')`. GNU sed
  interprets `\x1b` as the ESC byte; **BSD sed (macOS) does not** — it matches a
  literal `x`, `1`, `b`, so the substitution never fires, the ANSI wrapper survives
  the strip, and whatever `$int_clean` is asserted against fails against correct
  code. There is no error: the caller just receives the un-stripped string.

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
