---
Task: t504_confusing_panel_highlight.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Plan

Add a persistent base border to `#pane-list` in the monitor TUI CSS so the border always renders (just changes color on focus), matching the pattern already used by `#content-section`.

### Change

**File:** `.aitask-scripts/monitor/monitor_app.py` (CSS block, line ~200)

- Add `border: solid $primary-darken-2;` to `#pane-list` base style
- The `.zone-active` override already sets `border: solid $accent;` — no change needed there

### Verification

- Run `./ait monitor`
- Tab between agent list and preview panels
- Border should stay visible, only changing color (not appearing/disappearing)
- Text should not shift position on focus change

## Final Implementation Notes
- **Actual work done:** Added `border: solid $primary-darken-2;` to the `#pane-list` CSS rule in `monitor_app.py`. This ensures the border is always rendered with a subdued color when inactive, and changes to `$accent` when active via the existing `.zone-active` override.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Used `$primary-darken-2` for the inactive border color to match the pattern already established by `#content-section`'s inactive `border-top`.
