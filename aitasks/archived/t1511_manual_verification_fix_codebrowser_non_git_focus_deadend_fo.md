---
priority: medium
effort: medium
depends: [1500]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1500]
assigned_to: dario-e@beyond-eye.com
anchor: 1449
followup_kind: manual_verification
created_at: 2026-08-13 15:45
updated_at: 2026-08-13 20:59
completed_at: 2026-08-13 20:59
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1500

## Verification Checklist

- [x] Launch `ait codebrowser` from a directory that is NOT a git repo: the sidebar shows "Error: not inside a git repository" and NO "Search files..." box is drawn anywhere in the code pane. — PASS 2026-08-13 20:58 auto: live tmux pane, non-git fixture; sidebar shows 'Error: not inside a git repository' and 'Search files...' absent from the whole capture
- [x] In that same non-git pane, press Tab several times: focus never leaves the code viewer and no hidden widget takes the keyboard (no cursor appears in a search field). — PASS 2026-08-13 20:58 auto: 6x Tab left the capture byte-identical (clock aside), no search field appeared, and a bare '?' still fired the Keys binding - no text input held the keyboard
- [x] In that same non-git pane, press a bare `q`: the codebrowser exits back to the shell (the keystroke is not swallowed). — PASS 2026-08-13 20:58 auto: bare 'q' returned pane_current_command python->bash in 0.3s and the app screen left the pane
- [x] Launch `ait codebrowser` inside a real git repo: the "Search files..." box IS present, and typing a partial filename shows matching results immediately on the first keystroke (this proves the boot seeding reached the widget, not just its internal list). — PASS 2026-08-13 20:58 auto: git fixture shows the 'Search files...' box; a SINGLE keystroke 'z' listed docs/zeppelin.md - boot seeding reached the widget
- [x] In that git-repo pane, pick a search result with Enter: the file opens in the code viewer (the open path still resolves against the project root). — PASS 2026-08-13 20:58 auto: Enter on the result opened docs/zeppelin.md (info bar 'zeppelin.md - 1 lines', content rendered), search cleared, path resolved against the project root
- [x] In that git-repo pane, press `R` to refresh the file tree, then search for a file added since launch: it appears in the results (proves the TrackedFilesRefreshed path re-seeds the index end-to-end). — PASS 2026-08-13 20:58 auto: negative control first - searching 'gamma' before R gave no results; after R, src/gamma_newfile.py appeared in results and in the tree
- [x] In that git-repo pane, Tab from the recent-files row: focus goes recent_files -> file_tree -> search box -> code viewer, i.e. the full cycle is unchanged by this task. — PASS 2026-08-13 20:58 auto: probed each stop - recent row (accent border+bg) -> file_tree (Down moved tree cursor) -> search (typing filtered) -> code_viewer (Down set 'Line 3/8') -> back to recent row
