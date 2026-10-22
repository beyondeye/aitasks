---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [minimonitor, gates, ui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-22 22:57
updated_at: 2026-10-22 22:59
---

## Goal

In `ait minimonitor`, each agent card in the agent list has a detail row carrying
the task's advisory **workflow phase** (PLAN, IMPLEMENT, POSTIMPL, `unknown (…)`)
merged with its gate counts, e.g. `IMPLEMENT ⏸ · 1/4 1p`. Today the whole row is
dim, so the phase does not stand out. Make the phase easier to recognize at a
glance:

1. Give each phase value its **own color**.
2. Put a **leading symbol/glyph** in front of the phase, one per phase value.

The phase stays advisory (it never gates anything); this is a display-only change.

## Where it lives (exploration findings)

- **Phase vocabulary:** `.aitask-scripts/lib/workflow_phase.py` — `PHASES`
  (PLAN / IMPLEMENT / POSTIMPL / UNKNOWN), the trailing ` ⏸` waiting glyph,
  `_UNKNOWN_TEXT` (narrow variants like `unknown (rec off)`, `unknown (ledger)`,
  `unknown ⏸`) and `_RESOLUTION_SUFFIX` (`?` / `~`). Rendered label-free for
  narrow surfaces by `render_phase_narrow` (via `_phase_body`). Per the module's
  rule, cite the constants rather than re-listing the members — a phase→style map
  should be keyed off `PHASES` / `UNKNOWN_PHASE` and have a drift guard test that
  every member has an entry.
- **List rows:** `.aitask-scripts/monitor/minimonitor_app.py`
  - `format_gate_phase_row(phase, gates, budget)` (~line 384) joins phase and gate
    summary into ONE plain string, with a shed ladder when it exceeds the budget:
    abbreviate the gate tail → clip the phase → drop the phase → clip the summary.
  - `_agent_card_text` (~line 2506-2519) wraps the whole result as
    `"\n  [dim]{merged}[/]"`.
- **Pinned own-agent card:** `_own_phase_text` (~line 2810) returns the same
  narrow phase; `_own_card_text` (~line 2737) renders it as `[dim]{phase}[/]`.
  Apply the same color + glyph there so the phase reads identically on both
  surfaces of the pane (that consistency is a documented intent of t1479).
- **Frozen / parked rows** deliberately render no phase — keep it that way.

## Design constraints

- **Row budget.** The detail row has `_detail_budget(target_width)` cells (~36 at
  the default 40-col pane); see the budget block at the top of
  `minimonitor_app.py`. The glyph's cells MUST be counted before the shed ladder
  decides what fits, otherwise the row wraps (costing a whole extra row per agent).
  Prefer **1-cell glyphs** (or measure with `rich.cells.cell_len`); true emoji are
  2 cells and render inconsistently inside tmux — if one is chosen, budget for 2
  cells and verify on a composited screen. Note the module already records the
  assumption that East-Asian-Ambiguous glyphs count as one cell.
- **Styling vs. budgeting.** `format_gate_phase_row` currently returns plain text,
  and the caller dims it. Coloring the phase means the row must be built as styled
  pieces AFTER the plain-text budgeting: decide what fits on plain text (glyph
  included), then wrap only the phase segment in its color and keep the gate
  counts dim. A clipped phase (rung 2) keeps its color; a dropped phase (rung 3)
  drops its glyph too. Phase text is framework-controlled, but keep markup safety
  in mind (see the `markup_literal` notes, t2017) and note `_title_row` leaves an
  open `[dim]` span that the next row must not assume is closed.
- **Colors** should be distinguishable in both light and dark terminal themes and
  not collide with colors that already mean something in this pane (state dot,
  shadow glyph, session divider cyan, own-panel header dim). `unknown (…)` should
  stay muted (it is "cannot tell", not a phase). Whether the ` ⏸` waiting glyph
  gets its own emphasis is a design choice to settle in planning.
- **Full monitor (`ait monitor`, `monitor_app.py` ~line 1863) is out of scope**
  unless the plan decides to share the phase→style map; if it does, keep the
  labelled `render_phase` output unchanged for any consumer that parses it.

## Tests and docs to update

- `tests/test_minimonitor_gate_phase_row.py` — pins `format_gate_phase_row` rungs
  in cells and the card's line structure on a composited 40-col screen; extend it
  so the glyph is counted and every rung still fits the budget, and that the phase
  segment carries its style.
- `tests/test_workflow_phase.py`, `tests/test_minimonitor_top_chrome_render.py`
  — check for pinned phase strings.
- Add a drift guard: every member of `PHASES` (and the UNKNOWN variants) has a
  glyph + style.
- Docs: `website/content/docs/tuis/minimonitor/how-to.md` (phase table, the
  `IMPLEMENT ⏸ · 1/4 1p 1f` example, the shed-order paragraph, pinned-card text)
  and `website/content/docs/tuis/minimonitor/_index.md` (comparison table). Run
  `python3 check_links.py --build` in `website/` after editing.

## Related (not folded)

- t2007 `budget_actual_pane_width` and t1481 `validate_minimonitor_configured_width`
  touch the same row-budget arithmetic; coordinate if either is in flight.
