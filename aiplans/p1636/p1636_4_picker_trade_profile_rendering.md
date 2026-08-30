---
Task: t1636_4_picker_trade_profile_rendering.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_1_concern_dimension_vocabulary_module.md, aitasks/t1636/t1636_2_concern_parser_impact_trailer.md, aitasks/t1636/t1636_3_producers_emit_impact_trailer.md, aitasks/t1636/t1636_5_delta_scoped_auto_recheck.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_*_*.md
Branch: main
Base branch: main
Output branch: main
---

# p1636_4 — Picker trade-profile rendering + decision guidance

The concern picker (`ConcernPickerModal` / `_ConcernRow` in
`.aitask-scripts/monitor/monitor_shared.py`) renders each vector-bearing
concern's trade profile and shows decision guidance. Depends on t1636_2
(parser fields). Binding parent-plan decisions: `needs_addressing()` unchanged;
partition and producer order authoritative (render, don't re-sort);
`original_index` untouched.

## Steps

1. **[pin_narrow_row_width_budget — risk mitigation, Stage 1, FIRST, before
   touching `_ConcernRow.render`]** Add a render-level test (pattern:
   `tests/test_concern_picker_modal.py` narrow-layout tests) asserting at BOTH
   24 and 28 columns that the region text AND the body text reach the
   **composited output** (`render()`/pilot screen text — never the widget's
   declared size; Rich's fold drops an overflowing segment whole, the t1274
   shape). Observe it pass against the unmodified widget.

2. **Vector line — narrow layout.** In `_ConcernRow`:
   - constructor: detect a vector-bearing concern (`improves is not None or
     worsens is not None or effort`); narrow + vector → add new `three-line`
     class (CSS `height: 3` beside `two-line`, line ~2671); no-vector rows
     stay exactly as today (legacy blocks render unchanged);
   - `render()` narrow: third line `   <profile>`; wide: profile inserted
     between region and body.

3. **Profile builder** (a small pure helper in `monitor_shared.py`, unit-
   testable without Textual): from `improves`/`worsens`/`effort` build e.g.
   `▲robus ▼simpl E:lo` using `concern_dimensions.label_for`:
   - effort tokens 4-cell: `E:lo` / `E:md` / `E:hi` / `E:?`;
   - magnitude suffix: nothing for `high|medium|low`? No — magnitude is shown
     only as the unspecified marker: a known magnitude colors/weights the
     glyph (e.g. `[bold]▲[/]` for high, plain for medium, `[dim]` for low),
     an unspecified one renders a single trailing `?` (`▲robus?`). This keeps
     the core within the packing bound (labels carry no magnitude cells
     beyond the one `?`);
   - `Worsens: ()` (priced as nothing) renders `▼–` (single-width dash) —
     distinct from no vector at all;
   - **packing invariant** (budget = width −3 indent = 21 cells at 24 cols):
     mandatory core = first improve entry + first worsen entry + effort —
     worst case `▲maint? ▼simpl? E:hi` = 2·(1+5+1) + 2 + 4 = 20 ≤ 21, holds
     by construction (labels ≤5 asserted in `concern_dimensions`);
   - overflow (optional tail only): ≤2 entries/side, rest `+N`; drop order
     under pressure: 2nd improve → `+N` markers → 2nd worsen; the worsen
     side's first entry and `E:` are never dropped;
   - all glyphs single-width (`▲`/`▼` East-Asian-Width Ambiguous — same class
     as existing marks; `_NARROW_PREFIX_COLS = 8` stays valid).

4. **Priority badge binding** (parent decision 2): vector-bearing concern →
   badge shows `derive_priority(improves)`; if the marker priority disagrees,
   append a dim `≠` beside the badge (visible, never silently reconciled).
   Legacy concerns keep the marker priority exactly as today.

5. **Decision guidance**: one dim line in the modal (extend `_context_line()`
   at ~3521 or a dedicated Static above the list):
   `forward: obligation/pure-win · spinoff: net-positive+effort · reject: worsens ≥ improves`
   — NOT in `_CONCERN_HELP_FULL`/`_CONCERN_HELP_COMPACT` (their 24-col token
   budget is pinned by `ConcernHelpLineBudgetTests`, which must stay green
   untouched). At the xnarrow tier the guidance line may be dropped entirely
   (guidance is advisory; the vector per row is the data).

6. **[pin_narrow_row_width_budget — Stage 2]** Extend step 1's test: at 24 and
   28 columns, region, body, AND the vector's mandatory core (first improve
   token, first worsen token, effort scalar) all reach the composited output —
   **exhaustively** over every (improve-dim × worsen-dim) pair × magnitudes
   (high/medium/low/unspecified-`?`) × effort tokens, measured in terminal
   cell widths. One lucky pair passing while `maint?`+`simpl?`+`E:hi` clips is
   exactly the failure this stage exists to catch. (The pure profile builder
   makes the exhaustive sweep cheap: assert builder output width ≤ budget for
   all combos, plus a sampled composited-screen subset through the real modal.)

7. **Minimonitor surface**: `minimonitor_app.py` consumes the shared modal —
   no parallel change expected; verify the narrow companion-pane render via
   the existing minimonitor picker tests (`tests/test_minimonitor_shadow_pick.py`)
   with a vector-bearing block fixture.

## Verification

- `python -m pytest tests/test_concern_picker_modal.py tests/test_minimonitor_shadow_pick.py tests/test_concern_body_display_contract.py`
- `ConcernHelpLineBudgetTests` green untouched.
- `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last
  line.
- Live: real minimonitor companion pane at ~28 and 24 columns (render-level
  assertion).

## Post-Implementation

Standard Step 9.
