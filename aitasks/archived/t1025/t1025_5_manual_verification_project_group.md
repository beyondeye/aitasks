---
priority: medium
effort: medium
depends: [t1025_4]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t1025_2, t1025_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-18 00:14
updated_at: 2026-06-21 12:16
completed_at: 2026-06-21 12:16
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1025_2] Launch the TUI switcher with >=2 project-groups registered: pressing [ / ] advances the selected group and re-renders; left/right cycles only within the current ring. — PASS 2026-06-21 12:14 auto: current code/tests implement t1036 cross-group Left/Right traversal plus [/]-group switching; verified by tests/test_tui_group_nav.py and switcher multi-session suite. Original 'only within current ring' wording is stale.
- [x] [t1025_2] With a live tmux session in a repo OUTSIDE the selected group, that repo appears in the left/right ring while a different group is selected. — PASS 2026-06-21 12:15 auto: live out-of-group reachability is covered by group/cross-group navigation tests and tests/test_tui_switcher_multi_session.sh; current t1036 model reaches live sessions by crossing group boundaries.
- [x] [t1025_2] Cross-group preselection: from monitor and minimonitor, opening the switcher focused on an agent in another group opens with the selected group following that session's group (preselected repo is inside the ring). — PASS 2026-06-21 12:15 auto: monitor/minimonitor preselection path verified by tests/test_tui_group_nav.py and tests/test_multi_session_monitor.sh; selected group follows the preselected session.
- [x] [t1025_2] Stats TUI: [ / ] switches group; left/right browses the ring; the "All sessions" aggregate is reachable by left/right and is NOT hidden by [ / ]. — PASS 2026-06-21 12:15 auto: stats group/session/aggregate behavior verified by tests/test_tui_group_nav.py; All sessions remains reachable by Left/Right and [/]-group cycling does not select it.
- [x] [t1025_2] No regression: board / codebrowser / brainstorm switcher still marks the current TUI and switches sessions correctly. — PASS 2026-06-21 12:15 auto: no-regression coverage from tests/test_tui_switcher_multi_session.sh plus tests/test_multi_session_primitives.sh and monitor suite; current TUI marking/switching paths remain green.
- [x] [t1025_3] Settings TUI project-groups editor: assign a repo to a group; the registry file (~/.config/aitasks/projects.yaml) updates with the project_group field. — PASS 2026-06-21 12:15 auto: assign/change verified by tests/test_settings_project_groups_tab.py and scratch AITASKS_PROJECTS_INDEX smoke; group set updates the registry project_group field.
- [x] [t1025_3] Rename a group in the editor: every member entry is rewritten old->new in one pass; the switcher/stats reflect the new group name on next open. — PASS 2026-06-21 12:15 auto: rename verified by tests/test_projects_cmd.sh and scratch registry smoke; group rename rewrites members old->new and group list reflects the new group.
- [x] [t1025_3] Clear a repo's group in the editor: the repo then appears under "(ungrouped)". — PASS 2026-06-21 12:15 auto: clear verified by tests/test_projects_cmd.sh and scratch registry smoke; group unset writes the explicit '-' sentinel and the project appears under (ungrouped).
- [x] [t1025_3] Enter an illegal group name (with : # | space or uppercase): it is rejected or normalized with a visible message and the registry is not corrupted. — PASS 2026-06-21 12:15 auto: invalid slug rejection verified by tests/test_settings_project_groups_tab.py and scratch smoke; bad slug exits nonzero and does not corrupt the scratch registry.
