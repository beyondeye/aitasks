---
priority: medium
effort: medium
depends: [975]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [975]
created_at: 2026-06-11 12:57
updated_at: 2026-06-11 12:57
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t975

## Verification Checklist

- [ ] Open `ait codebrowser` -> press `H`; once loading completes, confirm recent CHILD tasks (e.g. t891_3, t952_4) appear interleaved by commit date in Completed Tasks (not just parents)
- [ ] Scroll the Completed Tasks list and click/activate "Load more" repeatedly; confirm no index entry is ever skipped and there are no duplicate rows
- [ ] While the History screen is open in one session, archive a task from another tmux window; toggle the History screen off (`h`/`esc`) and back on; confirm the newly archived task appears WITHOUT pressing `r` (and a brief "History updated" notice shows)
- [ ] Quick-toggle the History screen off and on within ~5s; confirm it does NOT re-scan (debounce) and the view is stable
- [ ] Confirm preserved behaviors: label filter (`l`), scroll-position restore on reopen, Recently Opened list, the `[+N children]` parent badge, and manual `r` refresh all still work
- [ ] Watch the list during the initial progressive load; confirm no visible flicker and that keyboard focus / selection is not lost when later chunks arrive
