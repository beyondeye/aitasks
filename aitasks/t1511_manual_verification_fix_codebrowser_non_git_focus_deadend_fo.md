---
priority: medium
effort: medium
depends: [1500]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1500]
anchor: 1449
followup_kind: manual_verification
created_at: 2026-08-13 15:45
updated_at: 2026-08-13 15:45
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1500

## Verification Checklist

- [ ] Launch `ait codebrowser` from a directory that is NOT a git repo: the sidebar shows "Error: not inside a git repository" and NO "Search files..." box is drawn anywhere in the code pane.
- [ ] In that same non-git pane, press Tab several times: focus never leaves the code viewer and no hidden widget takes the keyboard (no cursor appears in a search field).
- [ ] In that same non-git pane, press a bare `q`: the codebrowser exits back to the shell (the keystroke is not swallowed).
- [ ] Launch `ait codebrowser` inside a real git repo: the "Search files..." box IS present, and typing a partial filename shows matching results immediately on the first keystroke (this proves the boot seeding reached the widget, not just its internal list).
- [ ] In that git-repo pane, pick a search result with Enter: the file opens in the code viewer (the open path still resolves against the project root).
- [ ] In that git-repo pane, press `R` to refresh the file tree, then search for a file added since launch: it appears in the results (proves the TrackedFilesRefreshed path re-seeds the index end-to-end).
- [ ] In that git-repo pane, Tab from the recent-files row: focus goes recent_files -> file_tree -> search box -> code viewer, i.e. the full cycle is unchanged by this task.
