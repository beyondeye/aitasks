---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [frozen, tui, minimonitor, aitask_monitor]
gates: [risk_evaluated]
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-16 12:41
updated_at: 2026-09-16 12:41
---

## Origin

Spawned from t1777 during Step 8b review, while measuring whether that task's
reworded drop-confirmation body still fitted the minimonitor's host width.

## Upstream defect

- `monitor/monitor_shared.py:2594-2606` — `FreezeConfirmDialog` sets
  `height: auto` with no `max-height` and hosts its content in a plain
  `Container` (not a `VerticalScroll`), so at 40 columns its buttons land
  off-screen at a 16-row host. **Measured on unmodified code** (t1777 stashed):
  at 40x16 both `#btn-confirm` and `#btn-cancel` render at `bottom=17` against a
  16-row screen, leaving `Escape` as the only way out of a destructive
  confirmation; at 40x15 the dialog body itself is clipped (`y=-2`). Pre-existing
  and independent of t1777's copy change.

## Diagnostic context

The class docstring already records the *horizontal* version of this bug and its
fix (t1705_7): Textual's `Button` defaults to `min-width: 16`, which put two
side-by-side buttons past the right edge at the minimonitor's 40-column host --
"the second one is then unclickable even though it renders". The width was
capped and a per-button `min-width: 10` added. The **vertical** axis never got
the same treatment.

Measured heights at 40 columns with the real drop-confirmation body:

| host | dialog | buttons |
|---|---|---|
| 40x15 | h=19, y=-2 (body clipped) | on screen |
| 40x16 | h=19, y=0 | **bottom=17 -- off screen** |
| 40x17 | h=19, y=0 | on screen |
| 40x18 | h=18 | on screen |

The 16-row case is the sharp one: the dialog is tall enough to push the button
row past the bottom edge but not tall enough to be re-centred off the top, so
both buttons are unreachable by mouse.

**Existing coverage does not catch it.** `tests/test_monitor_frozen_filter.py`
("both buttons fit inside a forty column screen") asserts only `region.right <=
40` and `region.x >= 0` -- the width axis -- and constructs the dialog with a
placeholder `"body"` string rather than real copy, so dialog height is never
exercised. A height-axis assertion with the real body is what surfaced this.

t1777 deliberately shipped a body of exactly 18 rows -- identical to the pre-fix
body -- so it neither introduces nor widens this defect. But it means any future
edit to that copy silently re-opens the question, because nothing tests it.

## Suggested fix

Give `#freeze-dialog` a `max-height` (e.g. `90%`) and make the content region
scrollable, mirroring how `frozenagent_app.py`'s `ConfirmDialog` already wraps
its content in a `VerticalScroll`. Then extend the existing 40-column test to
assert the **bottom** edge as well as the right, using the real drop-confirmation
body rather than a placeholder, so the height axis is covered for both monitors.
