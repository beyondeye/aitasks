---
priority: medium
effort: medium
depends: [1247]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1247]
created_at: 2026-07-26 11:46
updated_at: 2026-07-26 11:46
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1247

## Verification Checklist

- [ ] Open `ait board` at a normal terminal width — confirm all six base filters (All, Locked, Free, In-Flight, By-Topic, By-Trail) plus `g Git` and `t Type` are fully visible, with nothing cut off at the right edge.
- [ ] Confirm the search box sits beside the filter row and does not visually overlap or clip any filter segment.
- [ ] Narrow the terminal below ~120 columns — confirm the search box reflows onto its own line rather than consuming the filter segments.
- [ ] Drag the terminal width slowly across the ~120-column threshold — confirm the transition is not visually glitchy, flickering, or leaving artifacts.
- [ ] Widen back above 120 columns — confirm the layout returns to side-by-side with the search box beside the filters.
- [ ] Click each filter segment (All / Locked / Free / In-Flight / By-Topic / By-Trail, then Git and Type) in BOTH the wide and reflowed layouts — confirm the correct filter activates each time.
- [ ] Enable the Type filter with many types selected — confirm the long `types: ...` summary wraps below the filters and does not distort the filter-row width.
- [ ] Rebind a base-filter key via the `?` shortcut editor to a non-first-letter key — confirm the filter row still fits without truncation and the search placeholder hint shows the new key.
- [ ] TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux (interactive surface touched by this task).
