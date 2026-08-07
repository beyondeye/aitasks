---
priority: medium
effort: medium
depends: [1159, 1420]
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini, tui]
gates: [risk_evaluated]
anchor: 1159
created_at: 2026-08-07 10:39
updated_at: 2026-08-07 10:39
---

## Goal

Make the shadow-concern badge (`!` appended to the shadow `◆`) reflect whether
the concerns are *still relevant*, and render it in `ait minimonitor` as well as
`ait monitor`.

Two separable defects, one shared root: the badge's only clearing edge is "the
user opened the picker".

## Findings (verified against `main` — do not re-derive)

**The glyph and its two call sites**

- `monitor_shared.py:135` — `SHADOW_CONCERN_GLYPH = "!"`, appended to
  `SHADOW_GLYPH` (`◆`) inside `format_shadow_glyph(shadow_snap, *,
  has_concerns=False)` at `:138-159`. It shares the shadow's state colour rather
  than adding a span (one marker, one style run).
- It is **not** a completion marker. Completion is signalled by *colour*
  (`bold dodger_blue1`) via `_state_color` on the `●` dot and the status text,
  and t1322 explicitly forbids `format_shadow_glyph` from ever taking a
  `completed` parameter — a shadow is advisory and has no task of its own.
- `monitor_app.py:1540-1542` passes
  `has_concerns=self._has_fresh_concerns(snap.pane.pane_id)`.
  `minimonitor_app.py:740-742` omits the keyword, so minimonitor can never show
  `!`. This asymmetry was deliberate at the time (`p1216_3` Context: *"minimonitor
  has exactly one followed agent … The monitor shows N agents, so the badge must
  be free for all of them"*) — minimonitor got the proactive
  `_maybe_offer_concerns` toast instead.
- Minimonitor's own width comment at `minimonitor_app.py:744-748` already budgets
  the name column for the worst-case row `● ◆! ≈ <name>  PROMPT 123s` — the
  comment anticipates a `!` the code never renders.

**Defect 1 — the badge is derived but never goes stale**

`monitor_app._has_fresh_concerns` (`:2052-2064`) returns
`sig in _concern_sig_latest AND sig NOT IN _concern_sig_offered`. `_offered` is
written only by `_mark_concern_sig` on the picker path. Consequence: once the
shadow has emitted a concern block, the badge stays lit through plan approval,
implementation, commit and archival, unless the user opens the picker purely to
silence it. The concern block also stays on the shadow's scrollback, so
`_concern_sig_latest` keeps re-deriving the same signature every tick.

**Defect 2 — minimonitor has the staleness signal but no badge; monitor has the
badge but does not use staleness**

Both halves already exist and are simply not joined:

- `monitor_core.compute_shadow_staleness(monitor, shadow_pane, followed_pane,
  eps)` (`:498-550`) compares the shadow's `@aitask_shadow_analyzed_at` pane
  stamp against the followed pane's last change. It returns a **tri-state**:
  `None` means *"preserve whatever the caller was showing"* (unreadable stamp,
  malformed stamp, followed pane not yet observed); only an explicit `False`
  clears a standing warning. Callers own `eps` (one refresh tick).
- Monitor already calls it twice — `monitor_app.py:1118` (the "(⚠ STALE — agent
  moved on)" toast marker) and `:2924` (the picker's red "may be stale" banner) —
  but **never for the row badge**.
- Minimonitor calls it at `:1899` to drive its `⚠ shadow feedback is stale —
  agent moved on (analyzed Ns ago)` banner (`_set_shadow_stale_banner`, `:1871`),
  but has no badge to modify.

**The right clearing signal is phase, not elapsed time.** "The plan was accepted"
and "the implementation was committed" are workflow-phase transitions, not
timeouts. `gate_ledger.resume_point(task_file)` (`lib/gate_ledger.py:1547`, pure
helper `_resume_point_from_state` at `:1570`) already returns `PLAN` /
`IMPLEMENT` / `POSTIMPL` derived back-to-front from the recorded `## Gate Runs`
ledger, and correctly demotes when a checkpoint is re-opened. It is exposed as
`./.aitask-scripts/aitask_gate.sh resume-point <id>` and already consumed by the
board (`board/aitask_board.py:1422`, `:1431`). **t1420** is chartered to surface
exactly this as an advisory signal for the shadow — this task should consume
t1420's signal rather than reach into `gate_ledger` on its own.

## Why this is sequenced behind t1159 and t1420

Declared in `depends` and load-bearing, not merely polite:

- **t1159** (`shadow_review_loop_automation`, high/high, board `now`, trail
  `art:trail-shadow-review-loop`) explicitly adds a **round number and review
  timestamp** to the concern block, and notes that the current auto-offer dedups
  on the parsed payload so an identical round-2 block produces no new hint.
  Round metadata changes what "fresh" *means* and what the badge's identity key
  should be — building a currency rule on today's payload signature would be
  rework.
- **t1420** (`advisory_workflow_phase_signal_for_shadow`, anchor 1159) delivers
  the phase signal this task needs, under a hard shape constraint from
  `aidocs/framework/shadow_agent.md:360-367`: the signal is **advisory-only** —
  a hint that changes a *default*, never a check that changes what is
  *permitted*. That constraint binds this task too: a wrong or unavailable
  phase must at most leave the badge as it is today, never hide a real concern.

Re-verify both landed designs before planning; the anchors above are as of
task creation.

## Requirements

- The badge stops signalling concerns that the followed agent has demonstrably
  moved past. At minimum, a `plan_approved` pass (for plan-round concerns) and a
  `review_approved` pass / task archival must clear it without the user opening
  the picker to silence it.
- Adopt the tri-state discipline of `compute_shadow_staleness`: "cannot tell"
  is its own state and must **preserve** the current badge, never clear it. A
  concern that might still matter is worth a false positive; silently dropping
  one is not.
- Decide, with rationale, between *clearing* the badge and *demoting* it (e.g. a
  dimmed or differently-shaped marker for "concerns exist but predate the
  current phase") — clearing loses the information that unaddressed concerns
  were raised; a second shape costs a column that `minimonitor` may not have.
- Render the badge in minimonitor's `_agent_card_text` (`minimonitor_app.py:740`)
  by passing `has_concerns=`, sourced from whatever per-tick derivation the
  monitor ends up using. Keep the non-shadowed row byte-identical (the flag is
  applied inside the `None` guard in `format_shadow_glyph` — preserve that).
- Respect the N-agent cost constraint from `p1216_3`: the monitor's badge
  derivation must stay free for N agents (no per-agent subprocess capture per
  tick). Minimonitor may afford more, but the derivation should stay shared.

## Cross-references

- **`t1351_minimonitor_row_width_audit`** (low/low, anchor 1326) — the
  minimonitor agent row already overflows at ~38 usable columns, verified by a
  40-column tmux capture. Adding `!` costs one more column on the worst-case
  row, and `minimonitor_app.py:747` already assumes that cost. Coordinate: either
  land t1351 first or fold its width budget into this task's verification.
- **`t1427_reject_shadow_concerns_suppress_next_round`** (has children) — the
  rejection store (`aitask_shadow_rejected.sh`, `ShadowRejectionsMixin` at
  `monitor_shared.py:538`) is an adjacent disposition mechanism. Check whether a
  fully-rejected block should also clear the badge; do not duplicate its store.

## Out of scope

- Changing the concern-block format or its parser contract (that is t1159).
- Making the phase signal a gate or a prerequisite on anything (barred by
  `aidocs/framework/shadow_agent.md`).
- The docked followed-agent panel in minimonitor (`_own_agent_identity_text`),
  which is static by design and renders no live glyphs (t1133).
