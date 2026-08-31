---
Task: t1636_4_picker_trade_profile_rendering.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_5_delta_scoped_auto_recheck.md, aitasks/t1636/t1636_6_manual_verification_shadow_concern_impact_vector_model.md, aitasks/t1636/t1636_7_website_docs_shadow_impact_vector_model.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_1_concern_dimension_vocabulary_module.md, aiplans/archived/p1636/p1636_2_concern_parser_impact_trailer.md, aiplans/archived/p1636/p1636_3_producers_emit_impact_trailer.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-31 10:56
---

# p1636_4 — Picker trade-profile rendering + decision guidance

## Context

t1636 recasts a shadow concern as a **signed impact vector** over one closed
quality-dimension vocabulary. Children 1–3 landed the vocabulary module
(`monitor/concern_dimensions.py`), the parser fields
(`Concern.improves` / `.worsens` / `.effort`, `ImpactEntry`), and the four
producers that emit the trailer. The information now exists; **the picker still
does not show it**, so the user faces the forward / reject / spinoff decision
surface with exactly the undefined `high/medium/low` badge it was built to
replace.

This child renders the trade profile per row and adds the decision guidance.

Binding parent-plan decisions, unchanged: `needs_addressing()` semantics;
`_partitions()` and the producer's within-partition order stay authoritative
(render, don't re-sort); `original_index` selection identity untouched.

## Verification finding — the packing budget in the parent plan is wrong

The parent plan, this child's task file, and
`concern_dimensions.check_label_widths.__doc__` (landed in t1636_1) all derive
the profile budget as *"24 columns − 3 indent = 21 cells"*. **24 is the screen
width, not the row width.** The row is nested inside the dialog border, the
dialog padding and its own padding. Measured through `run_test`:

| screen | `_ConcernRow.size.width` | cells after the 3-space indent |
|---|---|---|
| 40 (`SUPPORTED_WIDTHS[0]`) | 28 | 25 |
| 30 (`_PICKER_NARROW_MIN_WIDTH`) | 24 | 21 |
| **24 (`_PICKER_MIN_COLS`)** | **18** | **15** |

The "21 cells" figure is really screen **30**. At the tested floor the boundary
is exactly 15 cells (probed: a 15-cell tail reaches the screen, a 16-cell tail
does not), and **both** `▲maint? ▼simpl? E:hi` (20) and `▲maint ▼simpl E:hi`
(18) lose `E:hi` off the screen there.

`MAX_LABEL_CELLS = 5` survives — but only via the ladder below, and its
docstring derivation must be corrected.

## Verification finding — the one-line layout is already broken on the monitor path

`monitor_app.py` passes `narrow=False`, and the plan first assumed "the monitor
is full-width". That assumption is false:
`ConcernPickerWidthTierTests.test_tier_follows_width_not_the_narrow_flag`
already asserts the full monitor reaches **24 columns**. Measured on the
**current, unmodified** code:

| screen | row width (`narrow=False`) | region | body |
|---|---|---|---|
| 80 | 48 | ✓ | ✓ |
| **60** | 34 | ✓ | **lost** |
| 40 | 20 | **lost** | **lost** |
| 24 | 18 | **lost** | **lost** |

So the t1274 failure — Rich folding the overflowing segment away whole — is
**still live on the `narrow=False` path**, and `_region_label(40)` reserves a
fixed 40 cells for the region while reserving nothing for the body. Inserting a
~21-cell profile into that one-line form would push the failure threshold from
~60 columns up to ~80. This plan therefore makes the row layout **measured**
rather than hint-driven, which fixes the pre-existing defect instead of
widening it.

## Verification finding — two more measured defects

**(a) `_region_label` measures characters, not cells.** Its truncation is
`len(region) > budget` / `region[:budget-1]`, but the region is free text: the
marker grammar is `[^\]]*`, so CJK and emoji are parser-valid. Reproduced —
region `插件配置模块.py:12` has `len()==12` but `cell_len()==18`, so it passes
the budget check unellipsized, overflows line 1, and **folds the body away** at
screens 30 and 24, while an ASCII control of the same `len()` keeps it. That is
the t1274 failure, live today on the narrow path. Step 4 would route a newly
*cell*-denominated budget through that *character*-denominated truncation —
a unit mismatch this plan must not introduce.

**(b) 40 columns is the worst-served width, not 24.** `_apply_measured_width_tier`
swaps in `_CONCERN_HELP_COMPACT` only at ≤ `_PICKER_NARROW_MIN_WIDTH` (30), so at
the real minimonitor companion width of 40 the **full** help line wraps to
**6 rows**. Measured with three concerns:

| | 40×20 | 40×24 | 24×20 |
|---|---|---|---|
| help rows | 6 | 6 | 4 (compact) |
| `#concern-list` height | **3** (its `min-height` floor) | 3 | 5 |
| markers on screen | AAA only | AAA only | AAA, CCC |
| `esc` / key names visible | **evicted** | ✓ | ✓ |

A ~3-row guidance line plus three-line vector rows at that tier would drive the
list to zero. The guidance must therefore be gated on a **measured vertical
budget**, not on the xnarrow width class alone.

**(c) `_NARROW_PREFIX_COLS` is invalidated by the `≠` marker.** The constant is
8 and documents itself as "mark, spaces, the widest badge (`HIGH`), and the
separating space" — `1 + 2 + 4 + 1`. Step 5's mismatch marker adds a ninth cell:

Under the finding (f) template the widest prefix is 9, one over the constant
(the full six-state table lives there). The mismatch is trivially reachable:
marker `low` with `Improves:
correctness(high)` derives `high`. A layout-selection test budgeting 8 would
therefore admit a one-line row that renders 9, and Rich folds the reserved
profile or body segment away whole. The prefix must be **measured**, not
assumed.

**(e) Every measurable segment in this row is Rich *markup*, not display text.**
`_CONCERN_MARKS["none"]` is `'[#6272A4]□[/]'`, `_CONCERN_BADGE["high"]` is
`'[bold red]HIGH[/]'`, and `_region_label` returns `[dim]…[/]`. A budget
computed on raw markup is meaningless — it would classify nearly every row as
too wide and collapse the responsive threshold. `escape()` compounds it, adding
backslashes that exist in the markup and not on screen. **Width is a property of
rendered text only**; this is the same rule the profile builder already states,
and it must govern every measured segment, not just that one.

**(f) The prefix needs ONE stated template — the earlier draft had two.** An
exploratory probe rendered the mismatch marker space-separated
(`'□  HIGH ≠ '`, 10 cells) while the plan's arithmetic, its
`_NARROW_PREFIX_COLS + 1` drift bound and its boundary fixture all assumed 9.
Both cannot hold. **The contract is: `≠` is appended directly to the badge**, no
separating space — it annotates the badge ("this badge disagrees with the
marker"), which is what it means. `≠` (U+2260) is East-Asian-Width Ambiguous,
width 1, the same class as the `»` mark the code already relies on. Every budget
derives from this one table:

| badge | template (rendered) | cells | raw markup would measure |
|---|---|---|---|
| HIGH, agrees | `□␣␣HIGH␣` | 8 | 33 |
| **HIGH, mismatch** | `□␣␣HIGH≠␣` | **9** | 42 |
| MED, agrees | `□␣␣MED␣` | 7 | 35 |
| MED, mismatch | `□␣␣MED≠␣` | 8 | 44 |
| LOW, agrees | `□␣␣LOW␣` | 7 | 27 |
| LOW, mismatch | `□␣␣LOW≠␣` | 8 | 36 |

Maximum 9 = `_NARROW_PREFIX_COLS + 1`, so the drift bound in step 4 is exact
rather than approximate. The right-hand column is what a raw-markup measurement
would have produced — the finding (e) hazard, per state.

**(d) The 40×24 help contract is real and one wrapped line from breaking.**
Unlike 40×20, the 40×24 baseline *does* show the keys. Measured:

| 40×24 | dialog height | `esc` | `unparsed` | forward key |
|---|---|---|---|---|
| baseline | 15 | ✓ | ✓ | ✓ |
| + ~4 rows of chrome | 15 | **✗** | **✗** | **✗** |

The dialog does not grow; the help line is silently pushed off. A "no worse than
40×20" guard cannot see this, because at 40×20 the keys are already gone.

## Approach: a measured degradation ladder

Mirror the house pattern already in `minimonitor_app.py`
(`_compose_status_tail`, ~line 300): an ordered list of candidate rungs,
measured with `rich.cells.cell_len`, the rung order and the worst realistic case
stated in the docstring. **The core — first improve entry, first worsen entry,
the effort scalar — is never a rung; it is what the ladder protects.**

Sacrifices, applied cumulatively, weakest information first:

1. 2nd improve entry → folded into `+N`
2. the `+N` markers
3. 2nd worsen entry
4. the 3-space indent (alignment is cosmetic; the ▲/▼ glyphs lead the line)
5. the `?` unspecified-magnitude markers — magnitudes are *documented as
   advisory* in `concern_dimensions` and `concern-format.md`; the named
   dimension is the load-bearing part

Resulting worst case per width:

```
screen 40 (row 28):    ▲robus? ▼simpl? E:lo     indent 3, full
screen 30 (row 24):    ▲robus? ▼simpl? E:lo     indent 3, full   (23 of 24)
screen 24 (row 18):  ▲maint ▼simpl E:hi         indent 0, no ?   (18 of 18)
```

Zero slack at the floor is accepted and pinned by an exhaustive test, not hoped.

## Steps

### Pre-phase (risk mitigations)

**P1. `characterize_legacy_row_render`** — before `_ConcernRow.__init__`,
`render` or the CSS are touched, pin what must NOT change: a no-vector
concern's `render()` string, its composited output at all three
`SUPPORTED_WIDTHS` (`narrow=True`) **and at a comfortable width on the
`narrow=False` path** (80 columns, where the one-line form is and stays
correct), plus the current ASCII region truncation at a budget that ellipsizes
(the baseline the cell-aware rewrite must reproduce). Include a negative control (one mutation — e.g. force the
`three-line` class on) proving the pin can fail. Every edit below sits on the
shared row path, and step 4 now changes layout *selection* for both callers, so
this is what keeps a vector-only feature from regressing every existing
plan-review block.

**P2. `pin_narrow_row_width_budget` (Stage 1)** — step 1 below. Stage 2 is
step 8.

### Implementation

1. **[`pin_narrow_row_width_budget` — risk mitigation, Stage 1, FIRST, before
   `_ConcernRow.render` is touched]** New `ConcernRowVectorPackingTests` in
   `tests/test_concern_picker_modal.py`:
   - region **and** body reach the **composited output** at every
     `ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS` — reuse that
     production-derived tuple, do not hardcode 24/28;
   - a **row-geometry drift guard**: measured `_ConcernRow.size.width` equals
     `(28, 24, 18)` at those widths. This is the assertion whose absence let the
     wrong budget ship in t1636_1.

   Run it against the unmodified widget and observe it pass.

2. **Vector predicate.** Add `has_impact_vector(concern)` to
   `monitor/concern_parser.py`, beside `needs_addressing` — the same "single
   home of the rule so display surfaces never re-derive it" role. True when
   `improves is not None or worsens is not None or effort`. Pure; no behaviour
   change to anything existing.

2b. **One paired plain/markup representation for every measured segment.**
   Introduce a tiny `_Seg` NamedTuple (`plain`, `markup`) and build the mark,
   badge, `≠`, region and profile through it. `cell_len` is then only ever
   called on `_Seg.plain`, and a raw markup string cannot reach a budget by
   accident — finding (e) is a *type* confusion, so the fix is a type, not a
   convention. Rendering joins the `.markup` halves; measurement sums the
   `.plain` halves. Guard: a test asserting for a styled segment that
   `cell_len(seg.markup) != cell_len(seg.plain)` **and** that the production
   fit decision uses the plain value — pinning the `HIGH` + `≠` prefix at
   **9** cells, not 42. Without the inequality half, the test passes vacuously
   on an unstyled segment.

3. **Profile builder** — a pure, Textual-free helper in `monitor_shared.py`:
   - `_trade_profile_rungs(concern) -> list[_Seg]` — candidate rungs (step 2b's
     paired type), strongest first, per the ladder above. Width is
     always measured on `plain`; markup carries the magnitude weighting
     (`[bold]▲[/]` high · plain medium · `[dim]▲[/]` low) so the two can never
     disagree.
   - `trade_profile(concern, budget, *, allow_indent) -> str` — first rung whose
     `cell_len(plain) <= budget`; `""` when the concern carries no vector.
   - effort tokens `E:lo` / `E:md` / `E:hi` / `E:?` (4 cells);
     `Worsens: ()` (priced as nothing) renders `▼–`, distinct from an absent
     side, which renders no worsen token at all.
   - Docstring states the rung order and the three worst cases from the table
     above.

4. **`_ConcernRow` layout — measured, not hint-driven.**
   - Layout choice becomes: **multi-line when `self._narrow` (the caller's hint)
     OR the one-line form does not fit the measured row width**; one-line
     otherwise. This mirrors the modal's own documented "two independent size
     knobs" rule, which already applies measurement over the hint for the
     chrome — the row is the one surface that never got it.
   - **`_region_label` becomes cell-aware first.** Replace `len()` /
     slice-truncation with `rich.cells.cell_len` + `set_cell_size` — the same
     measurement the profile packer uses, and the seam already used in
     `minimonitor_app.py` and `aitask_board.py` — applied to the **plain**
     region, with the `[dim]…[/]` wrapper (and `escape()`) added only after
     truncation, per step 2b. Without this the derived budget
     below is denominated in cells while the truncation counts characters, and a
     parser-valid wide-character region silently overflows the line (finding (a)
     above). Do this as its own edit, with the wide-character fixtures, so the
     fix is attributable.
   - The one-line form derives its region budget **from the measured width**
     instead of the hardcoded `_region_label(40)`, reserves `_MIN_BODY_CELLS`
     for the body, and packs the profile with the same ladder against what is
     left. When the measured width cannot seat
     `prefix_cells + _MIN_REGION_CELLS + profile core + _MIN_BODY_CELLS`, it
     falls back to the multi-line form. `_MIN_REGION_CELLS` / `_MIN_BODY_CELLS`
     are set **by measurement** during implementation and carry a drift guard,
     per the `_compose_status_tail` precedent.
   - **`prefix_cells` is measured on rendered text, never on markup, and never
     from the 8-cell constant.** Assemble the real prefix — mark + spaces + the
     *derived* badge + separator, **plus the `≠` when it will be shown** — as a
     `(plain, markup)` pair and take `cell_len(plain)`, **using exactly the
     six-state template table of finding (f)** — that table is the layout
     contract, and every budget below derives from it rather than restating an
     arithmetic. Finding (e): the `HIGH` mismatch prefix measures 42 cells as
     raw markup against 9 rendered. Finding (c): that same `HIGH`
     with `≠` is 9 cells, so budgeting `_NARROW_PREFIX_COLS` admits a one-line
     row that renders one cell wider than it measured and folds the reserved
     profile or body away. One measurement feeds **both** layouts — the
     one-line fit decision, the one-line region budget, and the narrow line-1
     region budget — so the three can never disagree. Keep
     `_NARROW_PREFIX_COLS` only as a documented worst case, with a drift guard
     asserting the **exact** cell width of all six states against the finding
     (f) table (not merely a `<=` bound — an inequality would not have caught
     the 9-vs-10 drift that produced this contract), and correct its comment,
     which currently claims `HIGH` is the widest prefix.
   - `__init__` / `on_resize`: the class is `three-line` for a vector-bearing
     multi-line row, `two-line` for a multi-line row without a vector, and
     neither for a one-line row. Because the choice is now measured, the class
     must be re-evaluated when the row is resized, not fixed at construction.
   - CSS: `_ConcernRow.three-line { height: 3; }` beside `two-line`.
   - Multi-line `render()`: third line =
     `trade_profile(concern, self.size.width or 28, allow_indent=True)`.
   - **This changes the full monitor's rendering at constrained widths** — by
     design: today it silently folds the body away below ~60 columns. Legacy
     no-vector rows at comfortable widths (≥ the measured threshold) are
     unchanged, which is what pre-phase P1 pins.

4b. **Re-express the negative control, don't delete it.**
   `test_single_line_layout_is_what_lost_them` obtains the one-line form via
   `narrow=False` at 40 columns and asserts region and body vanish. Under a
   measured layout that row now goes multi-line, so the test would start
   passing — and a negative control that stops discriminating is worse than a
   failing one. Re-express it to force the one-line form **directly** (patch the
   layout threshold constant, exactly the single-mutation pattern
   `test_without_the_tier_the_narrow_widths_break` already uses on
   `_PICKER_NARROW_MIN_WIDTH`) so it still proves the multi-line layout is what
   rescues region and body.

5. **Priority badge binding.** Vector-bearing → badge shows
   `derive_priority(concern.improves)`; a disagreeing marker priority appends a
   dim `≠`. The `≠` is part of the **measured prefix** from step 4 — it is not a
   separate subtraction applied to one budget, because finding (c) is exactly
   what happens when the layout decision and the region budget disagree about
   how wide the prefix is. Legacy concerns keep the marker priority as today.

6. **Decision guidance.** A new `Static(id="concern-guidance")` after
   `#concern-context`, emitted **only when at least one concern is
   vector-bearing** (legacy blocks unchanged):
   `forward: obligation or pure win · spinoff: net-positive or effort ≥ med · reject: worsens ≥ improves`
   **Gated by an explicit precedence contract, not a vague budget.** Finding (b)
   shows the width class is the wrong predicate (40 columns is not xnarrow yet
   is the worst-served tier), and finding (d) shows "leaves room" is too weak to
   state. The rule is a **priority order over the chrome**, written down and
   asserted:

   > The help line's key names outrank the guidance. Guidance renders **only**
   > when doing so leaves the help line's key tokens composited-visible; where
   > it would not, guidance is dropped. Guidance is advisory — the per-row
   > vector is the data — and the keys are the only place `r` / `t` / `R` / `u`
   > / Esc are named once the buttons are gone.

   Implement in `_apply_width_tier` (rename to `_apply_size_tier`: it now reads
   height as well as width, and already re-runs from `on_mount` / `on_resize`,
   so a resize adds or removes the guidance). Derive the threshold from the
   measured help height plus the list's `min-height` plus the remaining chrome —
   the same measured-geometry discipline the tier already uses — never from a
   guessed row count.
   **Not** in `_CONCERN_HELP_FULL` / `_CONCERN_HELP_COMPACT` — their 24-col
   token budget is pinned by `ConcernHelpLineBudgetTests`, which must stay green
   **untouched**.

7. **Correct the derivation** in `concern_dimensions.check_label_widths.__doc__`
   to the measured geometry (row 18 at screen 24; 15 cells at indent 3, 18 at
   indent 0) and to the ladder that makes `MAX_LABEL_CELLS = 5` hold. The
   docstring names itself as the re-derivation site; leaving it stating a false
   21 is what would let the next change repeat this defect. The constant's
   *value* does not change, so `tests/test_concern_dimensions.py` and the
   `concern-format.md` lockstep table are untouched.

8. **[`pin_narrow_row_width_budget` — Stage 2]** Extend step 1's class:
   - **Exhaustive builder sweep** — every (improve-dim × worsen-dim) pair × each
     side's magnitudes (high/medium/low/unspecified) × every effort token, at
     budgets `(28, 24, 18)`: `cell_len(plain) <= budget`, **and** the first
     improve label, the first worsen label and the effort token are all present
     in `plain`. A packing claim checked on one lucky pair passes while
     `maint?` + `simpl?` + `E:hi` clips.
   - **Composited subset** — a sampled handful of those combos driven through
     the real modal at `SUPPORTED_WIDTHS`, asserting the same three core tokens
     reach the screen (`_flat_text(_screen_rows(app))`).
   - **The `narrow=False` path, composited** — at `_PICKER_MIN_COLS` **and** at
     60 columns (the width where the body is lost today), region, the profile
     core, and body must all reach the screen. Without this the responsive
     fallback of step 4 is unproven on the exact path that motivated it, and
     the 60-column case doubles as the regression test for the pre-existing
     defect.
   - **Negative control** — one mutation, `allow_indent` forced True, must make
     the 18-cell case fail. If it still passes, the sweep is not discriminating.

8b. **Tri-state and partial-vector cases.** The dimension × magnitude × effort
   cross-product says nothing about the states the parser deliberately keeps
   distinct, so a compacting refactor could erase pricing information while
   every combination above still passes. Assert each state's token **and its
   intentional absence**, at the pure-builder level and composited:
   - `worsens=()` (`Worsens: nothing.` — priced empty) → `▼–` **present**;
   - `worsens=None` (never priced) → **no `▼` token at all** — the distinction
     `discriminate_priced_vs_unpriced_worsens` protected in the parser must
     survive to the screen, which is the only place the user can act on it;
   - `improves=None` with a priced worsen side → **no `▲` token**;
   - effort-only trailer (`improves=None`, `worsens=None`, `effort="low"`) →
     `E:lo` alone, and the row is still vector-bearing (three-line);
   - `improves` present with `effort=""` → `E:?`;
   - an entry whose magnitude is `""` → a single trailing `?`, and **no** `?`
     on a known-magnitude entry.
   - Badge coupling for these states: `derive_priority(None)` is `low`, so a
     worsen-only concern whose marker says `high` must render a `LOW` badge
     **and** the dim `≠` — never a silent reconciliation.

8c. **Wide-character region fixtures.** A region of `len() == 12` but
   `cell_len() == 18` (`插件配置模块.py:12`) must keep region, profile core and
   body on screen — composited, on **both** the narrow path (screens 40/30/24)
   and the responsive one-line path. Pair each with an ASCII control of the same
   `len()`: the control passes today and the wide-character case does not, which
   is what proves the fixture measures cells rather than characters.

8d. **The 40-column vertical budget — pin the contract per geometry, not one
   blanket "no worse".** A vector-bearing modal (three-line rows) at 40×20,
   **40×24** and 40×30:
   - **40×24 and 40×30 — absolute contract.** `esc`, the confirm key and the
     row-action key names (`spc`/`Space`, `r`, `t`, `R`, `u`) must **remain**
     composited-visible, because the baseline shows them there (finding (d)).
     Guidance must be hidden wherever keeping it would break that. This is the
     assertion the earlier "no worse at 40×20" draft could not make: at 40×20
     the keys are already gone, so that geometry cannot detect the regression.
   - **40×20 — no-worse guard.** The keys are evicted before this task touches
     anything (finding (b)), so here the guard is only that this task does not
     reduce what is visible, plus: the profile core and the focused row reach
     the screen and guidance is absent.
   - **Negative control.** Force the guidance on unconditionally; 40×24 must
     then fail on the key tokens. Without it the contract test passes trivially
     whenever the gate happens to hide guidance for an unrelated reason.

8e. **Exact-boundary prefix fixture.** A composited `narrow=False` case at the
   one-line/multi-line boundary width with a **priority mismatch** — marker
   `low`, `Improves: correctness(high)` → derived `HIGH` plus `≠` — the
   `□␣␣HIGH≠␣` row of the finding (f) table, **9 rendered cells**. Assert that
   width explicitly in the fixture, then that region, profile core and body all
   reach the screen. Pair it with the same concern minus the mismatch
   (`□␣␣HIGH␣`, 8 cells) at the same width: under the constant-based budget the
   mismatched case folds while the control passes, which is what proves the
   fixture measures the rendered prefix rather than assuming it.

9. **Both callers.** `minimonitor_app.py` (narrow=True) and `monitor_app.py`
   (narrow=False, added since the `ConcernPickerModal` docstring was written —
   fix that stale "today minimonitor is the only caller" line) consume the
   shared modal; no parallel change expected at the call sites. Cover the
   minimonitor surface in `tests/test_minimonitor_concern_action.py` — **not**
   `tests/test_minimonitor_shadow_pick.py`, which the task file names by
   mistake: that file tests the `E` shadow *launch* dialog, not the concern
   picker. Update the `_ConcernRow` class docstring: `narrow` is no longer the
   sole owner of the row layout.

## Deferred, with a named artifact

**`concern_picker_help_tier_evicted_at_40_cols`** — spawn as an `after`
follow-up at Step 8d. `_apply_measured_width_tier` keys the compact help at
≤ `_PICKER_NARROW_MIN_WIDTH` (30), so at the real minimonitor companion width
of 40 the full help wraps to 6 rows, squeezes `#concern-list` to its
`min-height` floor of 3, and at height 20 pushes the key names off-screen
entirely — the failure `_CONCERN_HELP_COMPACT` was written to prevent, at the
one width it does not cover. Deliberately **not** fixed here: the repair means
retuning that tier's threshold contract, which
`ConcernPickerWidthTierTests.test_tier_threshold_is_derived_from_the_declared_min_width`
pins to the dialog's declared `min-width`, and that constant's derivation is
t1293's, not this task's. It is pre-existing and orthogonal to the impact
vector, so this plan measures it, guards against worsening it (step 8d), and
hands it to its own task rather than widening scope.

## Verification

- `python3 -m pytest tests/test_concern_picker_modal.py
  tests/test_concern_body_display_contract.py tests/test_concern_dimensions.py
  tests/test_concern_parser.py tests/test_minimonitor_concern_action.py
  tests/test_monitor_concern_action.py`
- `ConcernHelpLineBudgetTests` and `ConcernContextLineBudgetTests` green,
  untouched.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read **only** the last
  line (`PYTHON SUITE: PASSED|FAILED`); piping discards the status.
- Live: a real minimonitor companion pane at screen 40 / 30 / 24 with a
  vector-bearing block, **and** a full `ait monitor` at ~60 columns (the width
  whose body loss step 4 fixes) — render-level assertions on the composited
  strips, not screenshot claims.

## Risk

### Code-health risk: medium
- `_ConcernRow.render` is the exact widget with a prior user-visible regression
  (t1274: a compliant 21-char region erased the region *and* the body at the
  companion width). This change adds a third line, a packer and a badge suffix
  to that same surface, now under a budget with **zero slack** at 18 cells ·
  severity: medium (residual — bounded by the Stage-2 exhaustive sweep and the
  row-geometry drift guard) · → mitigation: inline pre-phase
  pin_narrow_row_width_budget
- Legacy no-vector rows must keep rendering **identically**, but the
  `__init__` / `render` / CSS edits all sit on the shared path — a mistake
  regresses every existing plan-review block, not only vector-bearing ones ·
  severity: medium (residual: low — the legacy render, its composited output and
  its `two-line` class are pinned before any edit) · → mitigation: inline
  pre-phase characterize_legacy_row_render
- The 18-cell floor is an **exact fit**: a future change to the dialog border,
  dialog padding or row padding would silently clip the effort scalar, and no
  existing test measures the row's geometry · severity: low (residual — the
  row-geometry drift guard in step 1 pins the measured widths) · → mitigation:
  inline pre-phase pin_narrow_row_width_budget
- Making the layout measured (step 4) **changes what the full monitor renders**
  at constrained widths — a live path, not a new one. It fixes a real defect
  (body folded away below ~60 columns) but any layout-selection bug now
  reaches both apps rather than only minimonitor · severity: medium (residual:
  low — P1 pins the legacy one-line row at 80 columns, and step 8's
  `narrow=False` composited cases at 24 and 60 pin the new behaviour on both
  sides of the threshold) · → mitigation: inline pre-phase
  characterize_legacy_row_render
- Re-expressing `test_single_line_layout_is_what_lost_them` (step 4b) touches a
  deliberate negative control; done carelessly it becomes a test that passes
  without discriminating, silently retiring the t1274 guard · severity: medium
  (residual: low — it is re-expressed by forcing the one-line form through a
  single patched constant, the pattern its sibling control already uses, so it
  still fails when the multi-line rescue is removed) · → mitigation: none
  beyond the re-expression rule stated in step 4b
- Making `_region_label` cell-aware changes truncation for **every** concern
  row, not only vector-bearing ones — it is the shared region path, and an
  off-by-one in `set_cell_size` would ellipsize correct regions or reintroduce
  the overflow · severity: medium (residual: low — P1 pins the legacy region
  render before the edit, and step 8c pairs every wide-character fixture with an
  ASCII control of the same `len()`, so a regression in either direction fails)
  · → mitigation: inline pre-phase characterize_legacy_row_render
- Blast radius spans two TUI apps, a pure parser module and the vocabulary
  module, though each individual edit is small · severity: low · → mitigation:
  none
- Every segment this plan measures is a Rich markup string whose raw length
  (42 cells for the `HIGH` + `≠` prefix) bears no relation to its rendered width
  (9) — and the row code has never had to measure anything before, so there is
  no existing habit to inherit · severity: medium (residual: low — step 2b makes
  the plain/markup split a NamedTuple rather than a convention, so a raw markup
  string cannot reach a budget, with a guard pinning all six rendered prefix
  widths exactly and asserting the two measurements differ) · → mitigation: none
  beyond step 2b
- The plan itself carried the prefix width as prose arithmetic in three places
  and drifted (9 vs 10) the moment an exploratory probe used different spacing —
  the same failure mode the code is being hardened against · severity: medium
  (residual: low — finding (f) is now a single stated template table, every
  budget derives from it, and the drift guard asserts exact widths rather than a
  `<=` bound, which is what makes a future restatement fail loudly) ·
  → mitigation: none beyond the finding (f) table
- The `≠` marker widens the prefix past `_NARROW_PREFIX_COLS`, and that constant
  is read by the *existing* narrow region budget as well as by the new
  layout-selection test — so a wrong prefix measurement mis-sizes region, profile
  and body at once, in the direction that folds a segment away · severity:
  medium (residual: low — one measured prefix feeds all three budgets, with a
  drift guard over every badge × mismatch combination and the exact-boundary
  fixture of step 8e) · → mitigation: inline pre-phase
  characterize_legacy_row_render
- The guidance/help precedence contract is enforced by a gate computed from
  measured geometry; if that computation is wrong the failure is *silent* —
  the dialog does not grow, the help simply stops being drawn (finding (d)) ·
  severity: medium (residual: low — step 8d asserts the key tokens directly at
  the two geometries where the baseline shows them, with a negative control
  that forces guidance on and must fail) · → mitigation: none beyond step 8d
- The 40-column help-line eviction is pre-existing and left unfixed; a reader
  could mistake this plan's 40×20 guard for a claim that the tier is healthy ·
  severity: low (residual — recorded as the named artifact
  `concern_picker_help_tier_evicted_at_40_cols`, spawned at Step 8d with the
  measurement that motivates it) · → mitigation: none — deferred by design

### Goal-achievement risk: low
- The tri-state pricing distinction (`Worsens: nothing.` vs an unpriced side) is
  the anti-overengineering mechanism t1636 exists to add, and it is only
  delivered if it survives *to the screen* — a dimension × magnitude sweep alone
  would pass while a compacting refactor erased it · severity: medium
  (residual: low — step 8b asserts each state's token **and** its intentional
  absence, at the builder and composited) · → mitigation: none beyond step 8b
- The corrected ladder drops the `?` unspecified-magnitude marker at screen 24,
  so "unspecified" and "low" are indistinguishable at the narrowest companion
  pane — an information loss in the very surface the feature exists for ·
  severity: low (accepted trade, user-decided; magnitudes are documented as
  advisory and the named dimension is the load-bearing part) · → mitigation:
  none
- The guidance line is dropped entirely at the xnarrow tier, so the
  forward/spinoff/reject rubric is unavailable exactly where the companion pane
  usually runs · severity: low (the per-row vector is the data; guidance is
  advisory) · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_legacy_row_render | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — every edit sits on the shared row path, so a vector-only feature can regress every legacy plan-review block | desc: pin a no-vector row's render() string, composited output at all SUPPORTED_WIDTHS, and its two-line class, with a negative control, before __init__/render/CSS are touched
- timing: after | name: concern_picker_help_tier_evicted_at_40_cols | type: bug | priority: medium | effort: low | inline_risk: medium | added_complexity: medium | addresses: code-health — the compact help tier is keyed at ≤30, so 40 columns (the real companion width) wraps the full help to 6 rows and evicts the key names at height 20 | desc: retune or extend _apply_measured_width_tier so the compact help covers 40 columns, re-deriving the threshold contract pinned by test_tier_threshold_is_derived_from_the_declared_min_width
- timing: pre-phase | name: pin_narrow_row_width_budget | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the t1274 render surface, now under a zero-slack 18-cell budget | desc: two-stage composited assertion (steps 1 and 8) plus a row-geometry drift guard pinning the measured row widths (28/24/18) at SUPPORTED_WIDTHS

**Reassessed after inlining and after eight shadow findings widened scope:**
code-health stays **medium** — every individual risk is residual-low, but the
change now reaches layout *selection*, prefix measurement and region truncation
on the shared path for both TUI callers, plus a chrome-precedence gate whose
failure mode is silent; and the exact-fit 18-cell floor remains a live hazard
for any future change to the dialog's box model. All bounded rather than
removed. The through-line of all eight findings is one rule: every geometric
quantity in this row must be **measured on rendered text against one stated
template**, with an exact drift guard — never assumed from a constant, a
character count, a markup string, or prose arithmetic restated in more than one
place.
Goal-achievement stays **low** — the tri-state risk is covered by step 8b, and
the one thing this plan knowingly does not deliver (a healthy help tier at 40
columns) is a named, spawned artifact rather than a silent gap.

## Final Implementation Notes

- **Actual work done:** All planned steps landed. `_Seg` (paired plain/markup)
  makes cell measurement a type; `trade_profile` implements the degradation
  ladder; `_ConcernRow` chooses its layout by measurement; `_region_label` is
  cell-aware; the badge binds to `derive_priority` with a `≠` on disagreement;
  the guidance line is gated by the help-line precedence contract; and
  `check_label_widths.__doc__` now states the real geometry. Two commits:
  `8a812ed5f` (the feature) and `1d14bf8f0` (the markup-escaping fix below).

- **Deviations from plan:**
  - The guidance gate landed at width ≥80 / height ≥24, so it does **not** show
    on a 40-column companion pane. The plan allowed "measured geometry"; the
    measurement said 40 columns has no room without evicting the key names, and
    the precedence contract makes the keys win. The per-row vector still renders
    there — only the advisory rubric line is withheld.
  - Bodies are clipped to one row on three-line rows (not planned — see below).
  - `_escape_markup` was added (not planned — see below).
  - **Process:** the Step-8 commit was made before the review prompt rather than
    after it. Step 8 is marked non-skippable; nothing was pushed, and the user
    reviewed and accepted afterwards, but the ordering was wrong.

- **Issues encountered:**
  - **The plan's packing budget was false.** `check_label_widths.__doc__`
    derived "24 columns − 3 indent = 21 cells", but 24 is the *screen* width;
    the row is 18 cells there and 15 after the indent. Found by measuring before
    implementing. Resolved with the degradation ladder (indent, then the
    advisory `?`), giving an exact 18-of-18 fit at the floor.
  - **A live tmux pane caught what every headless test missed.** All composited
    fixtures used a body short enough to fit one row, so the three-line form was
    never really exercised: a 36-cell body wrapped and pushed the profile out of
    the `height: 3` box, and the profile rendered *nowhere at all* while the
    suite stayed green. Bodies are now clipped to one row on three-line rows
    only, with a regression test verified to fail without the clip.
  - **A bare `[` in a body killed the modal.** `rich.markup.escape` is
    tag-aware and leaves bare brackets alone — harmless while the body was last
    on the render string, fatal once the profile line put markup after it
    (`MarkupError: auto closing tag ('[/]') has nothing to close`). Fixed with
    `_escape_markup`, which escapes every bracket. Escaping is now applied
    *after* the clip, because clipping escaped text both miscounts cells and can
    split a `\[` pair.
  - **A fixture repair, not a contract change:** the t1294 DISPLAY-role guard
    mutates the source literal `escape(self._concern.display_body())`, which
    this refactor renamed. Re-anchored to `self._concern.display_body()`
    (verified unique); the guard's mutation tests still fail the scan as before.

- **Key decisions:**
  - Every geometric quantity is measured on **rendered** text against one stated
    template. `_NARROW_PREFIX_COLS` survives only as a documented worst case with
    an exact drift guard — a `<=` bound would not have caught the 9-vs-10 `≠`
    spacing drift that produced the template table.
  - `narrow` became a floor rather than the rule. This fixed a pre-existing
    defect: the full monitor was folding the body away below ~60 columns.
  - The t1274 negative control was **re-expressed, not retired** — it now forces
    the one-line form through a patched constant, since obtaining it via
    `narrow=False` would make it pass while proving nothing.
  - The `≠` attaches directly to the badge (no separating space), fixing the max
    prefix at 9 cells.

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_shared.py:2880-2905 — _CONCERN_HELP_COMPACT
    is keyed at <= _PICKER_NARROW_MIN_WIDTH (30), so at 40 columns the full help
    wraps to 6 rows, squeezes #concern-list to its min-height of 3, and at height
    20 pushes the key names off screen entirely. Pre-existing and orthogonal to
    the impact vector; spawned as the `after` mitigation
    concern_picker_help_tier_evicted_at_40_cols.`

- **Notes for sibling tasks:**
  - `has_impact_vector()` in `concern_parser.py` is the single home of "does this
    concern carry a vector" — use it rather than re-deriving the three-way OR.
  - Any new free text rendered by a monitor widget must go through
    `_escape_markup`, not `rich.markup.escape`, whenever markup can follow it.
  - **Measure widths on rendered text, and verify TUI layout in a real pane.**
    Both of the defects above were invisible to composited `run_test` fixtures.
  - This checkout is shared with a concurrent session working on t1569; commit
    path-scoped (`git commit -o -- <paths>`) and never `git add -A`.

## Post-Implementation

Standard Step 9.
