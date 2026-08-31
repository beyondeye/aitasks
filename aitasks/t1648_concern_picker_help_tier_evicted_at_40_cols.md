---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, concern_format]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1636
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-08-31 12:11
updated_at: 2026-08-31 17:51
---

## Problem

`_apply_measured_width_tier` swaps `_CONCERN_HELP_FULL` for
`_CONCERN_HELP_COMPACT` only at or below `_PICKER_NARROW_MIN_WIDTH` (30). But
the real minimonitor companion width is **40**, which is above that threshold —
so the widest companion pane is the *worst*-served one.

Measured in `ConcernPickerModal` with three concerns:

| | 40x20 | 40x24 | 24x20 |
|---|---|---|---|
| help rows | 6 (full, wrapped) | 6 | 4 (compact) |
| `#concern-list` height | 3 (its `min-height` floor) | 3 | 5 |
| concern markers on screen | AAA only | AAA only | AAA, CCC |
| `esc` / key names visible | **evicted** | yes | yes |

At 40x20 the help line is pushed off screen entirely — the exact failure
`_CONCERN_HELP_COMPACT` was written to prevent, at the one width it does not
cover. Once the OK/Cancel buttons are dropped, that line is the only place
`r` / `t` / `R` / `u` / Esc are named, so the user has no on-screen affordance
at all.

Discovered while implementing t1636_4 (concern trade-profile rendering). It is
**pre-existing and orthogonal** to the impact vector, so it was deliberately
not fixed there.

## Why it was not fixed in t1636_4

The repair means retuning the tier's threshold contract, and that threshold is
pinned by
`ConcernPickerWidthTierTests.test_tier_threshold_is_derived_from_the_declared_min_width`
to the `.narrow` dialog's own declared `min-width`. That derivation is t1293's,
not t1636_4's. t1636_4 measured the defect, guarded against worsening it
(`ConcernGuidanceContractTests` asserts the keys survive at 40x24 and 40x30 and
that the new guidance line yields to them), and handed it here.

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_shared.py`:
  - `_apply_measured_width_tier` (~line 2907) — the shared width-tier mechanism,
    also used by `ConcernPayloadEditModal`; any change affects both dialogs.
  - `_PICKER_NARROW_MIN_WIDTH` / `_PICKER_MIN_COLS` and the `.narrow`
    `min-width: 30` they are derived from.
- `tests/test_concern_picker_modal.py` — `ConcernPickerWidthTierTests`
  (the derivation guard) and `ConcernHelpLineBudgetTests` (the token budget).

## Approach notes

The threshold currently conflates two questions: "is the dialog's chrome too
wide for this screen" (a `min-width` fact) and "does the help line still fit"
(a wrapped-height fact). Consider separating them rather than moving one number
— raising the single threshold to 40 would also apply the xnarrow *dialog*
chrome at 40 columns, which is a different and probably unwanted change.

Whatever is chosen, keep `ConcernHelpLineBudgetTests` green and preserve the
`test_tier_threshold_is_derived_from_the_declared_min_width` guard rather than
deleting it — it is what stops the threshold becoming a magic number again.

## Verification

- A vector-bearing and a legacy modal at 40x20, 40x24, 40x30, 30x24 and 24x20:
  every key token reaches the composited screen.
- `ConcernHelpLineBudgetTests`, `ConcernContextLineBudgetTests`,
  `ConcernGuidanceContractTests` and `ConcernPickerWidthTierTests` all green.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last line.
- Live: a real minimonitor companion pane at 40x20 (render-level assertion on
  the composited strips, not a screenshot claim).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-31T14:50:52Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-31T15:28:19Z status=pass attempt=1 type=human
