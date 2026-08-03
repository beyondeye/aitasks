---
priority: medium
effort: medium
depends: [1251]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1251]
created_at: 2026-07-28 17:48
updated_at: 2026-07-28 17:48
boardidx: 68608
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1251

## Verification Checklist

- [ ] Run `ait codebrowser` in a real terminal and resize across the ~120 boundary: the left sidebar must step between 35 (>=120 cols) and 28 (80-119 cols) with no flicker or stale width.
- [ ] Resize `ait codebrowser` across the ~80 boundary: the left sidebar must step between 28 (>=80) and 22 (<80), and the annotation gutter must narrow from 12 to 10 cells.
- [ ] Open a file with annotations in `ait codebrowser` below 80 columns and confirm the annotation gutter is readable and not clipped at the narrow width (the narrow arm had zero test coverage before t1251).
- [ ] Confirm the codebrowser detail pane (`d`) still opens, resizes, and auto-hides at the same terminal widths as before the refactor - the code pane must keep priority over the detail pane.
- [ ] Run `ait board` and resize across its filter-row reflow threshold (~120 cols): the search box must move below the filter row and back, unchanged by t1251 (the board was deliberately not migrated).
- [ ] Verify in a real terminal, not only via Textual `run_test`: the t1251 suite asserts widget geometry headlessly, which does not prove what a user actually sees rendered in a tmux pane.
