---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [shadow, concurrency]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-09-24 15:29
updated_at: 2026-09-25 11:23
---

## Origin

Spawned from t1873 during Step 8b review.

## Upstream defect

- `tests/test_change_surface.sh:95-110 (and most assert_contains/assert_not_contains calls in the file)` — arguments passed as (desc, haystack, needle) against the helper's (desc, needle, haystack), so the multi-line output becomes the grep pattern set and the negative assertions are weaker than they read.

## Diagnostic context

`tests/lib/asserts.sh` defines `assert_contains desc needle haystack` (same for `assert_not_contains`), and the helper greps the haystack for the needle with `grep -qF -- "$needle"`. Most calls in `tests/test_change_surface.sh` pass `"$out1" "TASK:a.md"`, i.e. haystack first. The whole multi-line helper output then becomes the pattern: `grep -F` treats each newline-separated line as an OR'ed pattern, and the fixed string is searched against it.

- Positive asserts still usually pass, because one output line equals the fixed string.
- The negative controls (`assert_not_contains "... NEG: concurrent edit must NOT be attributed" "$out1" "TASK:b.md"`) only fail if some output line is a substring of `TASK:b.md`. They are therefore much weaker than they read. An empty output line (an empty pattern matches everything) or a short line could make them pass or fail for the wrong reason.

The t1873 additions at the end of the file use the correct order and say so in a comment.

## Suggested fix

Swap the argument order on every affected call (needle second, haystack third), then run `bash tests/test_change_surface.sh` and add a mutation check: temporarily make `cmd_list` print `TASK:b.md` and confirm the negative control now fails. Grep the other `tests/*.sh` for the same haystack-first pattern while there.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-25T08:23:56Z status=pass attempt=1 type=human
