---
Task: t873_3_expandable_dimension_descriptions_detail_pane.md
Parent Task: aitasks/t873_fix_brainstorm_dimension_proposal_linking_and_compare.md
Sibling Tasks: aitasks/t873/t873_*.md
Archived Sibling Plans: aiplans/archived/p873/p873_*_*.md
Worktree: aiwork/t873_3_expandable_dimension_descriptions_detail_pane
Branch: aitask/t873_3_expandable_dimension_descriptions_detail_pane
Base branch: main
---

# Plan: t873_3 — Expandable / full-text dimension descriptions in detail pane

Give the node detail pane a reliable way to read a full (long) dimension
description, independent of the proposal-jump escape hatch (which is unreliable
per t873_1/t873_2).

## Root cause
`DimensionRow` (`.aitask-scripts/brainstorm/brainstorm_app.py:1699-1756`) sets CSS
`height: 1` (:1713) and `render()` (:1746) concatenates the full multi-sentence
value into that single clipped row. Enter is already bound to the proposal jump,
so there is no in-pane way to see the full text.

## Steps
1. Add `expanded` state to `DimensionRow` (reactive bool, default `False`).
2. In `on_key` (:1752), bind a **distinct** key (Enter is taken) — use `space`:
   toggle `expanded`, set `self.styles.height = "auto" if expanded else 1`, then
   `self.refresh()`. `event.stop()`.
3. `render()`: collapsed → current `  {badge} {suffix}: {value}` (clipped);
   expanded → full value wrapped (Textual wraps when height is `auto`). Keep the
   `[N §]` badge.
4. Surface the toggle per `aidocs/tui_conventions.md` ("footer must surface every
   operation"): add "space: expand" to the detail-pane hint/footer. If the row's
   key is made customizable, register via `_shortcuts_scope`/
   `register_app_bindings`; if following the existing lightweight `on_key` style,
   justify it in Final Implementation Notes.
5. **Fallback** if inline auto-height proves fiddly: push a small `ModalScreen`
   with the full value on the toggle key (mirror the `SectionViewerScreen` push
   in `on_dimension_row_activated`). Document the chosen approach.

## Verification
- `bash tests/run_all_python_tests.sh` (add a light DimensionRow test if feasible).
- Manual (no regeneration): `ait brainstorm` → session `crew-brainstorm-635` →
  node with long dimension values → toggle key expands a clipped row to the full
  wrapped description and collapses again; Enter still jumps to the proposal (no
  key collision); the toggle is discoverable in the footer/hint.

## Post-implementation
Follow task-workflow Step 8 (review/commit) and Step 9 (archival/merge). Record
any related upstream defect in the plan's Final Implementation Notes.
