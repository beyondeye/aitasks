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
created_at: 2026-09-01 15:35
updated_at: 2026-09-01 15:35
---

## Origin

Risk-mitigation ("after") follow-up for t1651, created at Step 8d after
implementation landed. It **replaces** the planned mitigation
`extend_detail_panel_to_legacy_blocks`, whose premise the task's own scope
reduction invalidated — see "Why this replaces the planned line" below.

## Risk addressed

The original risk is **archived t1293's**, carried forward through the deleted
t1426 and inherited by t1651:

> The inspect view shows the unrecovered lines and the raw block region, but the
> picker still never shows a concern's **full body** — the two-line row
> truncates it at every width, including 40. That is pre-existing and out of
> scope here, but it means "see what the shadow said" is only fully solved for
> the *lost* lines, not for long parsed ones · severity: low
> · → mitigation: t1426

## Problem

`_ConcernRow.render` clips a concern's body to **one line** on the three-line
(vector-bearing) layout, and the two-line legacy layout relies on box clipping.
At no width does the picker show a long parsed body in full. The region is
ellipsized by `_region_seg` on the same rows.

t1651 was the task that inherited this. It built a focused-concern detail panel
that *did* show the un-ellipsized region and the wrapped body — and then, after
visual review, the panel was deliberately reduced to **dimensions only**: one
line per impact entry, full dimension name, magnitude as a word. The body,
region, disposition line and inline rubric were removed because the row directly
above the panel already carries the region and disposition, and repeating them a
few rows down read as duplication rather than detail.

That reduction was the right call for the panel. Its consequence is that
**t1293's full-body risk is once again wholly undischarged** — not merely for
legacy blocks, but for every block. t1651 delivered the vector half of "see what
the shadow said"; the body half is still open.

## Why this replaces the planned line

The plan's `### Planned mitigations` recorded
`extend_detail_panel_to_legacy_blocks` — "extend the detail panel to vector-less
blocks, discharging t1293's risk for them too". That line was written while the
panel still rendered a body. It no longer describes useful work: the panel shows
only the impact vector, so extending it to a vector-less block would render the
single line `no impact vector` and nothing else. The residual it was standing in
for is real; its stated shape is not.

## Current affordances (what already exists)

- **`u` — inspect unrecovered** (`ConcernBlockInspectModal`, t1293) shows the
  raw block region and the marker lines that failed to parse. It is the closest
  existing thing to "show me the whole text", but it is scoped to what was
  *lost*, not to a successfully parsed concern that is merely long.
- **`e` — edit payload** (t1582) opens the outgoing clipboard payload in a
  TextArea, which does contain full bodies — but it is the *forward* path, shown
  only for what you have marked, and it is a text editor rather than a reader.

Either could be the seam; neither is currently the answer.

## Goal

Give the picker a way to read a focused concern's **full body** — and ideally
its un-ellipsized region — without regressing what t1651 settled:

- the row's packing derivation (`MAX_LABEL_CELLS = 5`) must not move;
- the help line's key names outrank everything advisory
  (`ConcernGuidanceContractTests`, `ConcernVerticalFitTierTests`);
- any new vertical chrome must join the precedence ladder rather than sit
  outside it, and must be gated from **measured** geometry against the declared
  budget so it stays invariant under `xshort` (t1648's non-oscillation proof);
- the detail panel's dimensions-only scope is a settled decision — do not
  re-add a body preview to it.

Note the design question t1426 asked and t1651 answered for the *panel* —
inline versus modal-over-modal — is open again here, and the answer may
legitimately differ: a body reader is a different surface from a per-row legend,
and `ConcernBlockInspectModal` already establishes the modal-over-modal
precedent in this package.

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_shared.py` — `_ConcernRow.render` (the clip),
  `_region_seg` (the ellipsis), `ConcernPickerModal` BINDINGS and
  `_apply_size_tier`'s gate order if new chrome is added,
  `ConcernBlockInspectModal` if the raw view is extended instead.
- `tests/test_concern_picker_modal.py` — the packing suites must stay green
  unchanged; a new surface reading a body must be registered in
  `tests/test_concern_body_display_contract.py` with a DISPLAY role.

## Verification

- Render-level on the composited strips: a body longer than the row renders in
  full on the new surface, **with a negative control asserting the row itself
  still truncates** — or the test is not measuring the new surface.
- A body and region containing `[/]` and a bare `[` render literally and do not
  crash (t1636_4; measure and cut raw, escape last).
- Every help-line key token still reaches the screen at 24x20, 40x20, 40x24 and
  80x24.
- `bash tests/run_all_python_tests.sh` — read only the last line.
