---
Task: t1648_concern_picker_help_tier_evicted_at_40_cols.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1648 — Concern picker help tier evicted at 40 cols

## Context

`ConcernPickerModal` at the real minimonitor companion geometry (40x20) renders
**no key affordance at all**: the help line — the only place `r` / `t` / `R` /
`u` / Esc are named once the OK/Cancel buttons are dropped — is pushed off
screen. t1636_4 measured this, guarded against worsening it, and handed it here.

The task's own approach note guesses the cause is the help-compaction threshold
(`_CONCERN_HELP_COMPACT` swaps only at ≤ `_PICKER_NARROW_MIN_WIDTH` = 30, so the
40-column pane gets the 6-row full line). **That guess is measurably wrong.**
Probing the real class (not a replica) across 11 geometries:

| variant at 40x20 | keys on screen |
|---|---|
| today | ✗ |
| compact help forced on | **✗** |
| OK/Cancel dropped | ✗ |
| `max-height: 100%` on `#concern-dialog` | **✓** |

The evictor is `#concern-dialog { max-height: 80% }`. On a 20-row pane that
withholds the rows the dialog needs; the compact help returns only 3 and still
loses. Swapping the help line earlier does **not** fix this bug.

A second, broader finding: an optional banner (`stale`, or `unrecovered`) costs
~2 more rows and evicts the keys at **80x24** — a comfortable width — and both
banners together break 40x30 and 60x24. So the defect is not "40 columns", it is
"chrome + help exceeds the 80% cap". The general form is fixed here; the residual
that no vertical tier can rescue gets a spawned follow-up (see Risk).

**Intended outcome:** separate the two questions the single threshold conflates —
"is the chrome too *wide*" (a `min-width` fact, unchanged) from "does the content
*fit vertically*" (a new tier) — and make every key token reach the composited
screen at the companion geometry.

## Approach

Add a second, independent tier class `xshort` to `ConcernPickerModal` that lifts
the vertical cap when the cap cannot seat the dialog's content.
`_PICKER_NARROW_MIN_WIDTH`, `_apply_measured_width_tier` and
`ConcernPickerWidthTierTests`'s derivation guard are **untouched** — the task
requires preserving them, and the width tier is correct for what it decides.

**The predicate measures; it does not model.** An earlier draft of this plan used
a fitted `_PICKER_FIXED_CHROME_ROWS = 13` justified as "border 2 + padding 2 +
header 2 + context 2 + list 4 + help margin 1". That justification is false:
`#concern-context` measures **3 rows** at 40 columns, because `_context_line()`
wraps at the dialog's inner width and grows further with `format_block_meta`.
The constant happened to fit the sampled geometries and would have understated
the requirement for a longer context line or a long `stale_detail` — re-creating
the very eviction being fixed. It is dropped, along with the Rich wrap model that
supported it.

Instead, sum what Textual actually laid out:

```
needed    = dialog.gutter.height                       # border + padding
          + Σ over dialog.children where child.display:
                child is the list ? declared min-height : child.size.height
              + child.styles.margin.top + .bottom
available = screen.height * _PICKER_MAX_HEIGHT_PCT // 100
xshort    = needed > available
```

This needs exactly one value from the stylesheet — `_PICKER_MAX_HEIGHT_PCT = 80`,
the `max-height` declared on `#concern-dialog`, drift-guarded the way
`_PICKER_NARROW_MIN_WIDTH` is. Every other input is a measured fact, so a longer
context line, a long `stale_detail`, a wrapped banner or a future widget are all
counted automatically rather than needing a new term.

Measured children heights are correct **even when the widget is currently
evicted** (the help reports `h=6` at 40x20 while off screen), so the predicate
reads the same in the broken state as in the fixed one.

**Ordering — the guidance gate runs first.** `#concern-guidance` is composed
`display=True` and only hidden by `_apply_guidance_visibility` below 80x24;
measured, `display` is still `True` when the tier is first reached. Computing
`needed` before that gate would count ~3 rows that never render and fire the tier
at healthy vector-bearing geometries. `_apply_guidance_visibility` depends only
on `self.size`, never on `xshort`, so running it first is deterministic and
non-circular. `_apply_size_tier` order becomes: width tier → **guidance gate** →
height tier.

**A help swap must settle before the height tier reads it.** The width tier calls
`help.update(...)`, and the new text is **not** laid out by the time the next
statement runs. Instrumented across the 30-column breakpoint:

| resize | text after `update()` | `size.height` then | settled |
|---|---|---|---|
| 31 → 30 | compact | 6 | 3 (over by 3) |
| 30 → 31 | full | 3 | **7 (under by 4)** |

The second row is the harmful one: the tier would size the full help at 3 rows,
decline to set `xshort`, and leave the keys evicted — the very defect being
fixed. So `_apply_measured_width_tier` gains a return value (whether it changed
the help text), and `_apply_size_tier` runs the height tier **inline when nothing
changed** and via `call_after_refresh` **when it did**.

That cannot loop: on the deferred pass the width tier finds the text already
correct, returns `False`, and the height tier runs inline. `ConcernPayloadEditModal`
ignores the new return value and is otherwise unaffected.

**No oscillation.** `xshort` changes only `max-height`, which changes only the
`1fr` list's height. Non-list children are width-driven and the list contributes
its *declared* `min-height`, so `needed` is invariant under the class. This is
pinned by a test, not just asserted.

Verified discrimination — exact on every probed case, with no fitted constant:

| geometry | needed | available | fires | broken today |
|---|---|---|---|---|
| 40x20 vector | 24 | 16 | yes | yes |
| 40x24 vector | 24 | 19 | yes | buttons clipped |
| 80x24 legacy | 19 | 19 | no | no |
| 80x24 legacy + stale | 21 | 19 | yes | yes |
| 100x30 legacy | 18 | 24 | no | no |

**Why the tier does only `max-height: 100%`** and does not also drop the buttons
or compact the help: measured, those buy no extra concern rows at 40x20 (markers
= 1 either way), so the minimal change is also the fully effective one.

## Files to modify

### 1. `.aitask-scripts/monitor/monitor_shared.py`

- Near `_PICKER_NARROW_MIN_WIDTH` (~line 3299): add `_PICKER_MAX_HEIGHT_PCT` with
  the same "derived, not chosen" comment style as the existing constant, and a
  note that it is the *only* stylesheet value the height tier needs.
- Add `_apply_measured_height_tier(screen, dialog_id, list_id, pct)` beside
  `_apply_measured_width_tier`, mirroring its "threshold passed in by the calling
  dialog, never read here" contract. Return without touching the class when the
  dialog or list is absent or `dialog.size.height == 0` (pre-layout), so a
  first-paint call cannot latch a wrong answer.
- `_apply_measured_width_tier`: **return whether it changed the help text**, and
  document that a caller which *measures* the help afterwards must wait a refresh
  — the swapped text is not laid out yet. Both call sites keep working;
  `ConcernPayloadEditModal` ignores the value.
- `ConcernPickerModal.DEFAULT_CSS`: add
  `ConcernPickerModal.xshort #concern-dialog { max-height: 100%; }`, commented
  with why the cap is the evictor and why this tier is height-keyed while
  `xnarrow` stays width-keyed.
- `ConcernPickerModal._apply_size_tier`: reorder to width tier → guidance gate →
  height tier, and record in the docstring **why** the guidance gate must precede
  the height tier (it decides a row the predicate counts) and **why** the height
  tier is deferred a refresh when the width tier swapped the help text (the new
  text is not laid out yet, and the stale height is wrong in both directions).
- `ConcernPickerModal.on_mount`: probe whether the children have real heights at
  mount. Measured, `#concern-guidance` reports `h=0` on the first gate call, so a
  `call_after_refresh(self._apply_size_tier)` is likely required — add it only
  once the probe confirms it, and let the first-paint test below be what proves
  it.
- **Correct the stale prose** in the `_GUIDANCE_MIN_WIDTH` docstring, which says
  "at 40 columns … the dialog has ~4 rows of headroom — adding a wrapped guidance
  line there evicts the keys outright". After this fix the keys are no longer
  evictable at 40 columns; restate what the gate now protects (the concern rows'
  usable height) and keep the precedence rule.

`ConcernPayloadEditModal` is **not** touched: it has no `1fr` list competing with
its footer, and its own tier tests must stay green unchanged.

### 2. `tests/test_concern_picker_modal.py`

New `ConcernVerticalFitTierTests`:

- `test_keys_reach_the_screen_at_the_companion_geometry` — 40x20, vector-bearing
  **and** legacy concerns, every `KEY_TOKENS_FULL` token on the composited
  strips, asserted **after mount with no resize** (this is also the first-paint
  guard). The task's headline acceptance.
- `test_the_predicate_matches_the_laid_out_children` — recompute `needed` from
  `dialog.children` in the test and assert it equals the helper's, at 40x20,
  80x24 and 100x30. Independent ground truth.
- `test_tier_fires_only_where_the_cap_cannot_seat_the_content` — the five rows of
  the table above, asserting `has_class("xshort")` each way.
- `test_a_long_context_line_is_counted` — a `block_meta` whose `reviewed_at`
  pushes `_context_line()` to an extra wrapped row: the tier fires and the keys
  survive at a geometry that is fine with a short context. This is the case the
  dropped fitted constant would have gotten wrong.
- `test_a_long_stale_detail_is_counted` — same shape via `stale_detail`.
- `test_a_composed_banner_is_counted` — 80x24 with `stale=True`: the tier fires
  and the keys survive (they do not today).
- `test_the_guidance_gate_runs_before_the_predicate` — at 40x24 with vector
  concerns the guidance is hidden, so it must contribute 0; assert the tier's
  `needed` matches the hidden-guidance sum. Negative control: force the gate to
  run *after* and assert the count changes, proving the ordering is load-bearing.
- `test_the_predicate_is_invariant_under_its_own_class` — compute `needed` with
  and without `xshort` applied; equal. Pins no oscillation.
- `test_negative_control_without_the_tier_40x20_breaks` — patch
  `_PICKER_MAX_HEIGHT_PCT` to a value large enough that the tier can never fire;
  assert the keys vanish at 40x20. Proves the tier, not something else, fixed it.
- `test_max_height_pct_is_derived_from_the_declared_stylesheet` — parse
  `max-height: N%` out of `DEFAULT_CSS`, in the shape of
  `test_tier_threshold_is_derived_from_the_declared_min_width`.
- `test_tier_is_reapplied_on_resize` — 40x30 → 40x20 flips the class. This
  geometry does **not** cross the help breakpoint, so it cannot catch a stale
  measurement on its own — hence the two below.
- `test_crossing_the_help_breakpoint_settles_the_tier` — resize **30 → 31** and
  **31 → 30** (and the same pair at height 20), asserting on the *settled* state:
  the `xshort` class matches a `needed` recomputed from the settled children,
  **and** every key token for the rendered help variant reaches the composited
  strips. 30 → 31 is the direction that fails without the deferral.
- `test_negative_control_measuring_before_the_swap_settles` — force the height
  tier to run inline on a text change (skip the `call_after_refresh` hop) and
  assert 30 → 31 ends with the wrong class and the keys off screen. Proves the
  deferral is load-bearing rather than incidental.
- `test_the_width_tier_is_unchanged_by_the_height_tier` — `xnarrow` still keyed on
  width alone at 40x20 (False) and 24x30 (True). Pins the separation itself.

Existing tests to update — both currently **pin the defect**:

- `ConcernGuidanceContractTests.test_40x20_is_no_worse_than_its_baseline` — its
  `assertFalse(self._keys_visible(...))  # pre-existing, not ours` is the bug
  characterization. Rewrite as a real contract at 40x20 (keys **do** reach the
  screen) and keep its existing guidance/marker assertions. Rename accordingly.
- `test_negative_control_forcing_guidance_on_breaks_40x24` — re-run it. Forcing
  the guidance on adds ~4 rows, which should still overflow even the lifted cap,
  so it is expected to stay green. **If it stops discriminating, do not delete
  it** — re-anchor it at a geometry where forcing the guidance on still costs
  something, and say in the docstring what it now proves.

### 3. `website/content/docs/tuis/minimonitor/how-to.md` (~line 196)

The existing sentence about the 30-column button drop stays true. Add one clause
that on a short pane the picker uses the pane's full height rather than 80% of
it, so the key hints stay on screen **for a picker whose content fits the pane** —
qualified, not an unconditional "always reachable" guarantee, because the
two-banner case below is a known residual.

## Verification

1. `python3 -m pytest tests/test_concern_picker_modal.py -q` — all green,
   including the untouched `ConcernPickerWidthTierTests`,
   `ConcernHelpLineBudgetTests`, `ConcernContextLineBudgetTests` and
   `ConcernPayloadEditWidthTierTests`.
2. `python3 -m pytest tests/test_monitor_concern_action.py -q` — the other
   consumer of the picker.
3. `bash tests/run_all_python_tests.sh` — **read only the last line**
   (`PYTHON SUITE: …`); do not trust an earlier `Results:` line, and do not pipe
   without `pipefail`.
4. Render-level sweep (a script under the scratchpad, not committed): a
   vector-bearing and a legacy modal at 40x20, 40x24, 40x30, 30x24, 24x20 —
   every key token on the composited strips and `_clipped_rows` empty at each.
5. Live: a real minimonitor companion pane at 40x20 with a shadow concern block,
   asserted at render level on the composited strips — not a screenshot claim.

## Risk

### Code-health risk: **low**

- One CSS rule, one derived constant and one helper, all in one dialog in one
  module · severity: low · → mitigation: none needed
- `_apply_measured_width_tier` and `_PICKER_NARROW_MIN_WIDTH` are untouched, so
  `ConcernPayloadEditModal` cannot be affected · severity: low ·
  → mitigation: inline — `test_the_width_tier_is_unchanged_by_the_height_tier`
- Reordering `_apply_size_tier` changes when the guidance gate runs relative to
  the rest · severity: low · → mitigation: inline —
  `test_the_guidance_gate_runs_before_the_predicate` and its negative control
- The `call_after_refresh` hop adds a second entry point into the tier, so a
  future edit could reintroduce a refresh loop · severity: low ·
  → mitigation: inline — the deferral is taken **only** when the width tier
  reports a text change, which is false on the deferred pass by construction;
  `test_the_predicate_is_invariant_under_its_own_class` and the breakpoint tests
  fail if it ever re-arms

### Goal-achievement risk: **medium**

- The predicate reads laid-out geometry, so it is only as good as the layout
  being settled when it runs; measured, children report `h=0` at the first gate
  call · severity: medium · → mitigation: inline — the headline acceptance test
  asserts after mount with **no** resize, so a first-paint miss fails the build
- The fix does **not** rescue a 20-row pane carrying *both* banners — measured,
  no CSS variant does; that needs a precedence decision about which content
  yields · severity: medium · → mitigation: spawned "after" follow-up (below)

### Mitigations

All inline (the tests above) except one **spawned "after" follow-up, to be
created at Step 8d — it does not exist yet**:

- **`concern_picker_banner_rows_evict_keys`** — at 20 rows with `stale` *and*
  `unrecovered` composed, no vertical tier can seat banners + help + a concern
  row. Needs a precedence decision (which of banner / help / rows yields), not
  more CSS. To be created at Step 8d with an explicit `depends: [1648]`, and its
  real `t<id>` back-filled into this section then.

## Post-implementation

Step 9 applies as normal: commit on the current branch (profile `fast`,
`create_worktree: false`, base and output branch `main`), then the
`risk_evaluated` gate, then archival of `aitasks/t1648_*.md` and
`aiplans/p1648_*.md`.

Note: the working tree carries unrelated uncommitted `parallel_admission` work
from another session. **Commit only this task's paths** (`git commit -o -- <paths>`),
never the index.

## Final Implementation Notes

- **Actual work done:** Implemented as planned. `ConcernPickerModal` gained an
  `xshort` tier (`max-height: 100%`) applied by a new
  `_apply_measured_height_tier`, which sums the **laid-out** children (the list
  contributing its declared `min-height`) against
  `screen.height * _PICKER_MAX_HEIGHT_PCT // 100`.
  `_apply_measured_width_tier` now returns whether it swapped the help text, and
  `_apply_size_tier` runs width tier → guidance gate → fit tier, deferring the
  fit tier one refresh when the help text changed. Added
  `ConcernVerticalFitTierTests` (16 tests), rewrote the two existing tests that
  pinned the defect, corrected the stale `_GUIDANCE_MIN_WIDTH` prose, and added a
  qualified sentence to `website/content/docs/tuis/minimonitor/how-to.md`.
  `_PICKER_NARROW_MIN_WIDTH`, the width tier's derivation guard and
  `ConcernPayloadEditModal` are untouched.

- **Deviations from plan:** Three, all forced by measurement.
  1. `on_mount` needed **no** `call_after_refresh`. The plan said to add one only
     if a probe confirmed it; the headline acceptance test asserts after mount
     with no resize and passes, so it was not added.
  2. The `call_after_refresh` negative control was **reframed**. The plan assumed
     skipping the hop would leave the settled state wrong; measured, it does not
     — swapping the help dirties the layout, which schedules another pass that
     self-corrects. Asserting otherwise would have been a false control. The test
     (`test_the_deferral_makes_the_first_decision_after_a_swap_correct`) now pins
     what the hop genuinely buys: every fit decision during a 30→31 resize is
     made from the settled height, whereas making the hop immediate produces at
     least one stale decision. The hop was kept — publishing a wrong tier for a
     frame is a real defect — but its value is stated honestly.
  3. `test_a_long_context_line_is_counted` was re-anchored from 60 to 80 columns:
     at 60 both the plain and round-suffixed context wrap to 2 rows, so that
     width could not detect a miscount. It now also pins the premise directly —
     the context measures ≥2 rows at 40 columns.

- **Issues encountered:**
  - The first plan draft derived a fixed `_PICKER_FIXED_CHROME_ROWS = 13` from a
    named decomposition. Review challenged it; measurement showed
    `#concern-context` is **3** rows at 40 columns, not the 1 the decomposition
    assumed — the constant had merely fitted the sampled geometries and would
    have understated the requirement for a longer context line or `stale_detail`.
    It was dropped for the measured-children sum, along with the Rich wrap model
    that supported it. **Do not reintroduce a chrome-rows constant.**
  - `ConcernGuidanceContractTests.test_negative_control_forcing_guidance_on_breaks_40x24`
    stopped discriminating: the fit tier now absorbs the forced-on guidance at
    40x24. Re-anchored to 40x20 (where no headroom remains even at full height)
    rather than deleted, per the plan's instruction.

- **Key decisions:** The tier changes `max-height` and nothing else. Dropping the
  buttons or compacting the help buys no additional concern row at 40x20
  (measured, markers = 1 either way), so the cap is the whole fix.

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_shared.py:3816 — ConcernPickerModal cannot
    seat its content at ~31–50 columns × 20 rows, nor at any width with BOTH the
    stale and unparsed banners composed in 20 rows; the keys stay evicted even at
    `max-height: 100%`. Pre-existing and verified against HEAD (31/32/35 × 20
    were already broken; this task fixes 31x24 and regresses nothing). Needs a
    precedence decision — which of banner / help / concern rows yields — not more
    CSS. Spawned as the "after" risk mitigation below.

## Verification performed

- `python3 -m pytest tests/test_concern_picker_modal.py tests/test_monitor_concern_action.py -q` — **263 passed**.
- `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
- Render-level sweep, vector-bearing and legacy blocks at 40x20 / 40x24 / 40x30 /
  30x24 / 24x20 (plus 60x20, 80x24, 80x24+stale, 100x30): every key token on the
  composited strips, `_clipped_rows` empty everywhere, and the `xshort` class
  consistent with `needed > available` at every geometry.
- Live, in a real 40x20 tmux pane on an isolated socket, before vs after:
  before, the help line was cut after `forward  [r] reject  [t] spin`; after, the
  full line renders (`[e] edit payload`, `[R] rejected list`, `[u] unparsed`,
  `[Enter/OK] confirm`, `[Esc] cancel`) with both borders intact.
