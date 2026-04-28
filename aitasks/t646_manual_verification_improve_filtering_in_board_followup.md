---
priority: medium
effort: medium
depends: [645]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [645]
created_at: 2026-04-26 10:23
updated_at: 2026-04-26 10:23
boardidx: 150
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t645

## Verification Checklist

- [ ] Launch the board (`./ait board`) and confirm the new `t Type` segment appears in the top filter selector alongside `a All | g Git | i Impl`, with the summary line hidden initially.
- [ ] First-time `t` press with no persisted selection: dialog opens immediately; toggling items with space, then pressing Enter applies the filter and the summary line below the selector reads `types: <comma-joined sorted types>`.
- [ ] Re-press `t` while in Type mode: dialog re-opens with the current selection pre-checked.
- [ ] Esc in the dialog cancels: the active view and persisted selection are unchanged.
- [ ] Confirm dialog with zero items selected: view reverts to All and the summary line is hidden.
- [ ] Switching to another mode (`a`, `g`, `i`) while in Type mode hides the summary line; switching back to Type via `t` shows it again populated from persisted selection.
- [ ] Quit the board (`q`), relaunch, press `t`: the persisted selection from the previous session drives the filter (no dialog this time); pressing `t` again opens the dialog with the prior picks pre-checked.
- [ ] Click hit-test: clicking each visible segment of the selector text (`a All`, `g Git`, `i Impl`, `t Type`) switches modes; clicking `t Type` follows the same dialog-open semantics as the keyboard shortcut.
- [ ] Search box interacts with the type filter: typing in the search box while in Type mode further narrows the visible cards (intersection of both filters).
- [ ] TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux
