---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [monitor, tui, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2163
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-29 22:28
updated_at: 2026-10-29 23:14
completed_at: 2026-10-29 23:14
---

## Origin

Spawned from t2164 during Step 8b review.

## Upstream defect

- `tests/test_projects_unreadable_registry.sh:121-123` (as of t2164's commit `354197c47`) — the VERBS table flattens `$ALPHA_ROOT` / `$BETA_ROOT` into a space-split argline (`read -r -a args`), so under a `TMPDIR` containing whitespace the `add` and `update` rows die at the earlier "Path does not exist" check instead of the unreadable-registry read; fails loud (assert_contains "Cannot read…" misses), not silent.

## Diagnostic context

t2164 added `tests/test_projects_lock_released_on_die.sh`, modelled on this
file's scaffold. Step 8 review caught that the new test's case table split its
flattened command string on whitespace, including whitespace inside the
fixture paths (`mktemp -d` honours `TMPDIR`). With a space-containing `TMPDIR`
the rows carrying a path hit "Path does not exist" before reaching the code
they were meant to exercise; the reviewer reproduced 35/38. t2164 fixed its own
file by carrying `@ALPHA@` / `@BAD@` placeholders in the table and substituting
them per element after the split.

The sibling `test_projects_unreadable_registry.sh` has the same pattern in its
VERBS table:

```
"add|-|add $ALPHA_ROOT"
"update|-|update alpha $BETA_ROOT"
```

Under a spaced `TMPDIR` those two rows (× 3 shapes) would fail
`assert_contains "$CANNOT_READ"` — a false red, never a false green. Not
reproduced in t2164 (inferred from the identical construct); verify by running
`TMPDIR="<dir with a space>" bash tests/test_projects_unreadable_registry.sh`.

## Suggested fix

Use the same placeholder-substitution loop as
`tests/test_projects_lock_released_on_die.sh` section 1 (`@ALPHA@` / `@BETA@`
tokens replaced per array element after `read -r -a`), then confirm the
spaced-`TMPDIR` run passes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-29T21:01:32Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-29T21:12:14Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-29T21:13:58Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:b47eef469c44fce4

> **✅ gate:risk_evaluated** run=2026-10-29T21:13:58Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2165/risk_evaluated_2026-10-29T21:13:58Z-risk_evaluated-a1.log`
