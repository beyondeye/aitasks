---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [t1794_1, t1794_2, t1794_3, t1794_4, t1794_5, t1794_6, t1794_7, t1794_8, t1794_9, t1794_10, t1794_11]
anchor: 1794
followup_kind: carry_over
created_at: 2026-09-23 16:35
updated_at: 2026-09-23 16:35
---

Carry-over of deferred manual-verification items from t1794_12. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t1794_4] Manual: edit a task in `ait board` (updated_at written); move a card. — DEFER 2026-09-23 16:34
- [ ] [t1794_5] Manual: `ait board` → `z` → `s r d R v enter M S` as before; `T` hidden in By-Trail, live on a card in the normal view. — DEFER 2026-09-23 16:34
- [ ] [t1794_6] Manual: `ait trails` boots; `j`→`i` from the board and `j`→`b` back; `ait monitor` classifies the window as a TUI; no minimonitor auto-spawn; Settings → Shortcuts lists trail actions once under `board`. — DEFER 2026-09-23 16:34
- [ ] [t1794_7] Manual: `enter` on a card; edit every field type; `?` lists `board.detail`; Settings → Shortcuts still lists `board.detail`. — DEFER 2026-09-23 16:34
- [ ] [t1794_8] Manual — column manage (`e`): add, rename, recolour (colour swatch focus + Enter/space select), shift+↑/↓ reorder, delete — each with its **cancel** path too. — DEFER 2026-09-23 16:34
- [ ] [t1794_8] Manual — **merge** flow end to end (`ColumnMultiSelectScreen` + `MergeColumnsConfirmScreen` both moved): Merge → multi-select sources (space toggles, Enter confirms) → pick destination → confirm; then the same flow cancelled at each of the three steps. Merging into `Unsorted / Inbox` must report that title, not the raw `unordered` id. — DEFER 2026-09-23 16:34
- [ ] [t1794_8] Manual — **Esc-with-changes dismiss result**: make a change in column manage (reorder or merge), then close with **Esc** rather than a button. The board must recompose and show the change immediately (`ColumnManageScreen.handle_escape` returns the `_changed` flag; a `None` here silently leaves a removed column rendered until the next manual refresh). — DEFER 2026-09-23 16:34
- [ ] [t1794_8] Manual: `m` move a card to a chosen column; `M` in By-Trail moves a wave. — DEFER 2026-09-23 16:34
- [ ] [t1794_10] Manual: `./serve.sh` and read the new page set, index, board reference. — DEFER 2026-09-23 16:34
