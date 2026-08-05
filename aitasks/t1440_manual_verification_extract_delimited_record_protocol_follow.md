---
priority: medium
effort: medium
depends: [1433]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1433]
created_at: 2026-08-05 18:20
updated_at: 2026-08-05 18:20
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1433

## Verification Checklist

- [ ] [t1433] `ait board` boots and renders its columns — t1433 put lib/record_protocol.py on the board's module-scope startup path via board_columns.py. Automated tests prove the import resolves and returns the stock three columns; they never launch the TUI.
- [ ] [t1433] Column titles and colours render correctly on the board, including any title containing a `|`.
- [ ] [t1433] `ait work-report` end-to-end, including the board's `w` flow — work_report_gather.py had 10 call sites renamed; its protocol bytes are pinned but the rendered report is not.
- [ ] [t1433] `ait minimonitor` column move via the headless seam (aitask_board_column.sh move) — shares the edited module; only list-columns output changed, so this is a regression check.
