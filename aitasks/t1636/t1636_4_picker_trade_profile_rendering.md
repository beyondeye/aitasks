---
priority: high
effort: high
depends: [t1636_3]
issue_type: enhancement
status: Implementing
labels: [shadow, aitask_monitormini, concern_format]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1636
created_at: 2026-08-30 14:54
updated_at: 2026-08-30 19:56
---

## Context

Part of t1636 (shadow concern impact-vector model). The concern picker gains a
compact per-row trade profile (`▲robus ▼simpl E:lo`) plus decision guidance, so
the user finally has the information the forward/reject/spinoff decision
surface was built for. Depends on t1636_2 (parser fields). Parent plan:
`aiplans/p1636_shadow_concern_impact_vector_model.md` — decisions 3 and 4 are
binding: `needs_addressing()` semantics unchanged; the partition and the
producer's within-partition order stay authoritative (render, don't re-sort);
`original_index` selection identity untouched.

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_shared.py`:
  - `_ConcernRow.render` (line 2781) — the trade profile, from
    `concern_dimensions` short labels.
  - `_ConcernRow` CSS (line 2667): new `three-line` class (`height: 3`)
    beside `two-line` (line 2671).
  - `_context_line()` (line 3521) or an own Static — the decision guidance
    (forward = obligation dims or pure-win + low effort; spinoff =
    net-positive non-obligated or effort ≥ medium; reject = worsens ≥
    improves). NOT in `_CONCERN_HELP_FULL`/`_CONCERN_HELP_COMPACT` (line
    2864): their token budget at `_PICKER_MIN_COLS = 24` is measured and
    pinned by `ConcernHelpLineBudgetTests`.
  - `_partitions()` (line 3501): UNTOUCHED.
- `tests/test_concern_picker_modal.py` (and siblings) — the new render tests.

## Layout (settled in the parent plan — follow exactly)

- NARROW (companion pane): a vector-bearing concern's row becomes THREE lines —
  line 1 mark+badge+region, line 2 body, line 3 `   ▲robus ▼simpl E:lo`.
  No-vector concerns stay two-line, so legacy blocks render exactly as today.
- WIDE: profile inserted between region and body on the one line.
- PACKING INVARIANT (before overflow policy): the mandatory core — first
  improve entry, first worsen entry, effort scalar — fits BY CONSTRUCTION,
  never by ellipsis: effort tokens are 4-cell `E:lo`/`E:md`/`E:hi` (`E:?`
  unspecified), short labels ≤5 cells (enforced in concern_dimensions),
  magnitude renders at most one trailing `?` — worst case
  `▲maint? ▼simpl? E:hi` = 20 ≤ 21 (budget = width −3 indent at 24 cols).
- OVERFLOW (optional tail only): ≤2 entries per side, rest collapse to `+N`;
  drop order under pressure: 2nd improve, then `+N` markers, then 2nd worsen —
  the worsen side's first entry and `E:` are core, never dropped.
- All marks single-width (`▲`/`▼` are East-Asian-Width Ambiguous, width 1
  outside CJK — same class as existing marks); `_NARROW_PREFIX_COLS = 8`
  (line 2634) stays valid.
- Priority badge for a vector-bearing concern renders
  `derive_priority(improves)`; a disagreeing marker priority gets a dim `≠`
  beside the badge — visible, never silently reconciled. Legacy concerns keep
  the marker priority as today.

## Reference Files for Patterns

- `monitor_shared.py:2637-2830` — `_ConcernRow` (two-layout render, region
  budget, t1274 lessons in the class docstring).
- `feedback_tui_render_level_verification` house rule: assert on
  `render().plain` / composited output, never on declared size.
- t1274 precedent: Rich's fold drops an overflowing segment WHOLE — this is
  why the packing invariant is proven, not hoped.

## Implementation Plan

1. FIRST (risk mitigation `pin_narrow_row_width_budget`, from the parent
   plan) — Stage 1, BEFORE touching `_ConcernRow.render`: a render-level
   assertion at both 24 and 28 columns that region AND body reach the
   composited output. Observe it pass against the unmodified widget.
2. Implement the layout above (render + CSS + badge/≠ + guidance line).
3. Stage 2 of the same test, once the profile lands: at the same widths,
   region, body, AND the vector core (first improve token, first worsen
   token, effort scalar) all reach the composited output — EXHAUSTIVELY over
   every (improve-dim × worsen-dim) pair × magnitudes (including
   unspecified-`?`) × effort tokens, measured in terminal cell widths. A
   packing claim checked on one lucky pair passes while
   `maint?`+`simpl?`+`E:hi` clips.
4. Decision-guidance line in the modal context area; assert it appears and
   that `ConcernHelpLineBudgetTests` stays green untouched.
5. `minimonitor_app.py` consumes the shared modal — no parallel change
   expected, but verify the narrow companion-pane surface at real width.

## Verification

- `python -m pytest tests/test_concern_picker_modal.py tests/test_concern_body_display_contract.py`
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
  line (`PYTHON SUITE: PASSED|FAILED`).
- Live: a real minimonitor companion pane at ~28 and 24 columns (render-level
  assertion, not a screenshot claim).
