---
priority: medium
effort: medium
depends: [886]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [886]
created_at: 2026-05-31 22:30
updated_at: 2026-05-31 22:30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t886

## Verification Checklist

- [ ] Open `ait board` on a task carrying >=2 cross-repo refs; focus the card and press `#` — picker shows >=2 refs plus a Cancel button
- [ ] Inside the picker, press Tab repeatedly — focus cycles ref -> ref -> Cancel -> ref within the popup and never jumps out to the board search box
- [ ] Press Enter on a focused non-first ref — it opens that cross-repo task
- [ ] Press Escape inside the picker — the picker closes (Escape-dismiss still works)
- [ ] On the base board (no modal open), press Tab — focus still moves to the search box (base behavior preserved)
