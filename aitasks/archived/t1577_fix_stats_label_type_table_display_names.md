---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [reporting, metrics]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1544
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-18 22:35
updated_at: 2026-08-19 00:48
completed_at: 2026-08-19 00:48
---

## Origin

Spawned from t1544_2 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_stats.py:384` — the label x type table renders types
  with a bare `issue_type.capitalize()`, bypassing the display map that the
  adjacent `### By Task Type` table uses via `get_type_display_name`. The same
  type therefore prints two ways in one report.

## Diagnostic context

Found while implementing t1544_2, which moved the issue-type display map out of
`aitask_stats.py::get_type_display_name` into
`.aitask-scripts/lib/task_category.py::TYPE_DISPLAY_NAMES` and reduced
`get_type_display_name` to a delegator.

Verifying the blast radius of that delegation turned up only **one** caller of
`get_type_display_name` (`aitask_stats.py:365`, the `### By Task Type` table) —
yet the live `ait stats` report clearly renders type names in a *second* place,
the per-label breakdown. The second site does not call the helper at all:

```python
:365   f"| {get_type_display_name(t):<14} | ..."     # -> "Bug Fixes"
:384   f"| {label:<12} | {issue_type.capitalize():<7} | ..."   # -> "Bug"
```

Observable in the current output of `./ait stats`:

```
### By Task Type - Weekly Trend (Last 4 Weeks)
| Bug Fixes      | 70    | ...
| Refactors      | 8     | ...

### By Label and Type
| tui          | Bug         | 12    | ...
| tui          | Refactor    | 3     | ...
```

So `bug` is `Bug Fixes` in one table and `Bug` in the next; `refactor` is
`Refactors` then `Refactor`; `style` is `Style Changes` then `Style`. Only the
types whose display name happens to equal `raw.capitalize()` agree.

This is pre-existing and was deliberately left untouched by t1544_2, which
changes no renderer and had to prove `ait stats` output byte-identical.

## Suggested fix

Point `:384` at `get_type_display_name(issue_type)` (now a one-line delegator to
`task_category.type_display_name`), and widen the `:<7` column — `Manual_verification`
is 19 chars and `Style Changes` is 13, so the current width truncates or ragged-wraps.

Note this **changes existing `ait stats` output** by design, so it needs its own
before/after capture rather than an unchanged-output assertion. Confirm the
intent is "one display convention everywhere" and not "the label table is
deliberately abbreviated to keep the row narrow" — if the latter, the fix is
instead to give `task_category` a documented short-form helper and use it here,
so there is still a single source of truth.

Related: t1544_4 renders the new unified category axis and must pick one of
these conventions explicitly rather than inherit both.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-18T20:52:05Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-18T21:39:20Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-18T21:48:50Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:02ec5ce36b986278

> **✅ gate:risk_evaluated** run=2026-08-18T21:48:50Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1577/risk_evaluated_2026-08-18T21:48:50Z-risk_evaluated-a1.log`
