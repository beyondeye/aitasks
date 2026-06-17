---
priority: medium
effort: medium
depends: [t1025_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1025_2, 1025_3]
created_at: 2026-06-18 00:14
updated_at: 2026-06-18 00:14
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1025_2] Launch the TUI switcher with >=2 project-groups registered: pressing [ / ] advances the selected group and re-renders; left/right cycles only within the current ring.
- [ ] [t1025_2] With a live tmux session in a repo OUTSIDE the selected group, that repo appears in the left/right ring while a different group is selected.
- [ ] [t1025_2] Cross-group preselection: from monitor and minimonitor, opening the switcher focused on an agent in another group opens with the selected group following that session's group (preselected repo is inside the ring).
- [ ] [t1025_2] Stats TUI: [ / ] switches group; left/right browses the ring; the "All sessions" aggregate is reachable by left/right and is NOT hidden by [ / ].
- [ ] [t1025_2] No regression: board / codebrowser / brainstorm switcher still marks the current TUI and switches sessions correctly.
- [ ] [t1025_3] Settings TUI project-groups editor: assign a repo to a group; the registry file (~/.config/aitasks/projects.yaml) updates with the project_group field.
- [ ] [t1025_3] Rename a group in the editor: every member entry is rewritten old->new in one pass; the switcher/stats reflect the new group name on next open.
- [ ] [t1025_3] Clear a repo's group in the editor: the repo then appears under "(ungrouped)".
- [ ] [t1025_3] Enter an illegal group name (with : # | space or uppercase): it is rejected or normalized with a visible message and the registry is not corrupted.
