---
priority: medium
effort: medium
depends: [1648]
issue_type: bug
status: Ready
labels: [aitask_monitormini, concern_format]
anchor: 1636
followup_kind: risk_mitigation
created_at: 2026-08-31 18:29
updated_at: 2026-08-31 18:29
---

## Origin

Risk-mitigation ("after") follow-up for t1648, created at Step 8d after
implementation landed.

## Risk addressed

From `aiplans/p1648_*.md` `## Risk`:

> The fix does **not** rescue a 20-row pane carrying *both* banners — measured,
> no CSS variant does; that needs a precedence decision about which content
> yields · severity: medium

t1648 separated the picker's width tier (`xnarrow`, the horizontal chrome and the
help wording) from a new vertical-fit tier (`xshort`, which lifts
`#concern-dialog`'s `max-height: 80%` cap to `100%` whenever the cap cannot seat
the laid-out content). That fixed the reported 40x20 case and the
banner-at-80x24 case.

It does **not** fix the geometries where the content does not fit *even at full
screen height*. There is nothing left for a cap to give back, so this is a
precedence decision, not more CSS.

## Problem

Two measured bands, both **pre-existing** — verified against t1648's parent
commit, where they were already broken, and unchanged by t1648:

1. **~31–50 columns × 20 rows.** Just above the compact-help breakpoint
   (`_PICKER_NARROW_MIN_WIDTH` = 30) the *full* help line is at its longest
   relative to the dialog width: 7 wrapped rows at 31 columns, 5 at 45. At 31x20
   `needed` = 26 against 20 available rows.
   Note the shape: this is the same "the width just above the breakpoint is the
   worst-served" defect t1648 was raised for, one band lower.

2. **Both banners composed in ~20 rows, at any width.** With `stale` *and*
   `unrecovered` present, no CSS variant tried during t1648 seats banners + help
   + one concern row — including `max-height: 100%` combined with dropping the
   OK/Cancel buttons and forcing the compact help.

In both bands the help line — the only place `r` / `t` / `R` / `u` / Esc are
named once the buttons are dropped — is partly or wholly off screen.

## Goal

Decide and implement a **precedence order** for what yields when the picker
genuinely cannot fit, and make that order explicit and tested rather than an
accident of DOM order. The candidates, in the order t1648's evidence suggests:

- the OK/Cancel buttons (already dropped at `xnarrow`; fully redundant with
  Enter/Esc, which the help names);
- the compact help wording, decoupled from the width tier so it can also be
  chosen on a *fit* basis (t1648 deliberately left the swap width-keyed, because
  compacting alone does not fix 40x20 — but in these bands it contributes);
- the banners, which could collapse to a single glyph or a one-line summary;
- the concern rows, which should yield **last**.

Whatever is chosen, the invariant to hold is the one `ConcernGuidanceContractTests`
and `ConcernVerticalFitTierTests` already state: **the help line's key names
outrank everything advisory.**

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_shared.py`
  - `_apply_measured_height_tier` (~line 3430) — the fit predicate; it already
    computes `needed` vs `available` and is the natural place to detect
    "does not fit even at 100%".
  - `ConcernPickerModal.DEFAULT_CSS` — the `xnarrow` / `xshort` tiers.
  - `_CONCERN_HELP_COMPACT`, `_PICKER_NARROW_MIN_WIDTH` — if the help swap is to
    become fit-keyed as well as width-keyed, `t1648` requires
    `ConcernPickerWidthTierTests.test_tier_threshold_is_derived_from_the_declared_min_width`
    to keep passing: the width tier's derivation must survive.
- `tests/test_concern_picker_modal.py`
  - `ConcernVerticalFitTierTests` — extend rather than fork; it already carries
    the `_needed` recomputation helper and the composited-strip assertions.
  - `ConcernGuidanceContractTests` — its negative control was re-anchored to
    40x20 by t1648; re-check it still discriminates after any further change.

## Verification

- Render-level, on the composited strips (never a `render()` string): every key
  token reaches the screen at 31x20, 35x20, 45x20 and 40x20, for a vector-bearing
  and a legacy block, with `_clipped_rows` empty at each.
- The same with `stale=True` and `unrecovered=("x",)` both set, at 40x20 and
  24x20.
- A negative control per decision: the chosen precedence, mutated one rung, must
  visibly cost the keys.
- `bash tests/run_all_python_tests.sh` — read only the last line.
- Live: a real ~31-column and ~45-column pane at 20 rows, asserted on the
  captured pane, not on a screenshot claim.
