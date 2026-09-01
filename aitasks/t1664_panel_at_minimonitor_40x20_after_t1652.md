---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini, aitask_monitor, tui]
gates: [risk_evaluated]
anchor: 1037
followup_kind: risk_mitigation
created_at: 2026-09-01 15:24
updated_at: 2026-09-01 15:24
---

## Origin

Risk-mitigation ("after") follow-up for t1651, created at Step 8d after implementation landed.

## Risk addressed

From `aiplans/p1651_*.md` `## Risk`:

> The panel is refused at 40x20 / 40x24 — measured, `spare` is −4 and 0 — which
> is minimonitor's real companion geometry and the width the task names as
> "where the picker is most used" · severity: medium

## Problem

t1651 added a focused-concern detail panel to `ConcernPickerModal`, gated by
`_apply_detail_visibility` on measured geometry against the **declared** 80%
budget (`screen_height * _PICKER_MAX_HEIGHT_PCT // 100`) rather than the
dialog's resolved `max-height`. That denominator is deliberate: it is invariant
under the `xshort` class, which is what keeps t1648's "cannot oscillate" proof
intact and stops advisory chrome inflating the dialog to full screen height.

The cost is that the panel is refused wherever the cap withholds the rows, even
when the raw screen has them. Measured at implementation time, with the panel
excluded from the sum:

| screen | budget | needed | spare | panel |
|---|---|---|---|---|
| 40x20 | 16 | 24 | -8 | no |
| 40x24 | 19 | 24 | -5 | no |
| 40x30 | 24 | 24 | +0 | no |
| 80x24 | 19 | 22 | -3 | no |
| 24x20 | 16 | 18 | -2 | no |

40x20 and 40x24 are the real minimonitor companion geometry — the width t1651's
own task text calls "where the picker is most used", because that is where the
row's trade profile degrades hardest.

## Why it is deferred rather than fixed

These are the bands **t1652** owns: the content does not fit even at full screen
height, so there is nothing left for a cap to give back and the repair is a
precedence decision about what yields, not more CSS. t1651's gate is written so
it never *worsens* those bands — the panel simply does not appear there.

## Goal

Once t1652 has landed its precedence order, revisit `_apply_detail_visibility`
so the panel becomes reachable at 40x20 / 40x24 without costing the help line's
key names.

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_shared.py`
  - `_apply_detail_visibility` — the gate and its denominator.
  - `_DETAIL_MIN_ROWS` / `_DETAIL_MAX_ROWS` / `_DETAIL_MIN_CONTENT_CELLS` /
    `_DETAIL_FULL_CONTENT_CELLS` — the measured floors.
- `tests/test_concern_picker_modal.py`
  - `ConcernDetailPanelTests.SHOWN` / `.HIDDEN` — the measured sweep; both
    halves must move together, since a gate asserted only where it says yes is
    half-tested.
  - `ConcernDetailGateOrderTests` — the `xshort`-invariance guard and its
    negative control must keep passing; whatever replaces the denominator has to
    stay invariant under the class, or t1648's non-oscillation proof breaks.

## Verification

- Render-level on the composited strips at 40x20, 40x24, 40x30 and 24x20, for a
  vector-bearing and a legacy block: the panel is shown where intended and
  `_clipped_rows` is empty.
- Every help-line key token still reaches the screen at each of those
  geometries — that precedence rule is not negotiable.
- The `xshort` invariance test still passes with its negative control.
- `bash tests/run_all_python_tests.sh` — read only the last line.
- Live: a real 40x20 minimonitor companion pane, asserted on the captured pane.
