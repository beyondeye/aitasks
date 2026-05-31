---
priority: high
effort: low
depends: [t873_2]
issue_type: bug
status: Ready
labels: [brainstorming, ait_brainstorm, ui]
created_at: 2026-05-31 13:13
updated_at: 2026-05-31 13:13
---

Fix defect #3 of parent t873: long dimension descriptions are truncated in the node detail pane with no way to read the full text.

## Context
`DimensionRow` (`.aitask-scripts/brainstorm/brainstorm_app.py:1699-1756`) sets CSS `height: 1` (:1713) and `render()` (:1746) concatenates the full (multi-sentence) dimension value into that single clipped row. The intended "read the full description" escape hatch is the proposal jump on Enter — but per defects #1/#2 (t873_1/t873_2) that link is often missing or mis-targeted, so there is effectively **no reliable way to read the full dimension description** from the detail pane. Real values in session `crew-brainstorm-635` are long (the node YAMLs carry 23–45 dimension keys with paragraph-length values).

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `DimensionRow` class (:1699-1756): its `DEFAULT_CSS` (:1711-1724), `render()` (:1741-1746), and `on_key`/`on_click` handlers (:1748-1755).

## Reference Files for Patterns
- Existing `DimensionRow.on_key` already binds `enter` → `Activated` (section jump). The expand toggle must use a **different** key so it does not collide.
- `aidocs/tui_conventions.md` — "TUI footer must surface every operation on the affected tab/screen": the new expand binding must be discoverable (footer-visible `Binding` and/or a hint), not an undocumented `on_key` branch. Also note the shortcut-manifest rule (`register_app_bindings`/`_shortcuts_scope`) if the binding is made customizable — but a simple per-row toggle following the existing `on_key` style may be acceptable; justify the choice.
- `_show_brief_in_detail` (`brainstorm_app.py:5063-5075`) shows how the pane already does a truncate-with-marker pattern — a model for a "full text" affordance.

## Implementation Plan
1. Add an `expanded` reactive (or plain bool) to `DimensionRow`, default `False`.
2. Bind a distinct key (e.g. `space`) in `on_key` to toggle `expanded`; on toggle, update the row's `styles.height` to `"auto"` (expanded) vs `1` (collapsed) and `refresh()`.
3. In `render()`, when collapsed show the current single-line `  {badge} {suffix}: {value}` (clipped); when expanded, render the full value wrapped over multiple lines (Textual wraps automatically when height is auto and the markup contains the full text). Keep the `[N §]` badge.
4. Surface the toggle: add/update a footer or pane hint (e.g. include "space: expand" in the detail-pane help line), per tui_conventions.
5. Alternative if inline expand proves fiddly in Textual: push a small `ModalScreen` showing the full value (mirror the `SectionViewerScreen` push pattern) on the toggle key. Pick whichever is cleaner and document the decision in the plan's Final Implementation Notes.

## Verification Steps
- `bash tests/run_all_python_tests.sh` (no regression; DimensionRow has no dedicated unit test — add a light one if feasible, else rely on manual).
- Manual (no regeneration): `ait brainstorm` → session 635 → focus a node with long dimension values → a clipped row, on the toggle key, expands to show the complete description and collapses again. Confirm Enter still performs the proposal jump (no key collision), and the toggle is visible in the footer/hint.
