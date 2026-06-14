---
Task: t983_2_node_selection_model.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_2_node_selection_model
Branch: aitask/t983_2_node_selection_model
Base branch: main
---

# p983_2 — Pure `NodeSelection` model

Child of t983. **Testability-first centerpiece:** land the headless selection
model + exhaustive unit tests BEFORE any UI consumer. Purely additive — the old
single-selection `_current_focused_node_id`
(`.aitask-scripts/brainstorm/brainstorm_app.py:3453`) keeps working until t983_3
wires this in.

## Goal
Replace single-node selection with a model supporting `space`-marking (single OR
multi) and a `cardinality` the Operations dialog (t983_4) greys ops by.

## Steps
1. `class NodeSelection` (no Textual/I/O): `marked: set[str]`, `primary: str|None`
   (cursor); `mark`/`unmark`/`toggle(node_id)`, `clear()`, `set_primary(node_id)`,
   property `cardinality`.
2. Document semantics: single-node ops act on `primary`/cursor; multi-node ops on
   the `marked` set; `cardinality` = effective selection size (primary-only = 1).
3. Keep import-light and side-effect-free; do NOT wire into UI (that is t983_3).

## Verification
- New `tests/test_brainstorm_node_selection.py` — fully headless, exhaustive over
  mark/unmark/toggle/clear/set_primary and `cardinality` transitions (empty,
  primary-only, single-marked, multi-marked). Model on
  `tests/test_brainstorm_wizard_steps.py` (pure, zero-Textual).
- Suite `tests/test_brainstorm*.py` green (additive change).

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_2`.
