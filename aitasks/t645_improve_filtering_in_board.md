---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_board]
created_at: 2026-04-26 10:03
updated_at: 2026-04-26 10:03
---

in ait board tui, we aleady support task filter (all/git/impl) I would like to add an additional filter view that is filter by issue type, when the issue. when the issue type view is selected, a dialog open to select the issue type to show (one or more types), and the selected type is afterward shown in the tui in the filter widget region. the current value of the filter is memory persistent, that is when we again select the issue type filter the dialog open with the previous choice of issue types to show. the dialog should have keyboard shorcuts: space to toggle issue type selection, enter to confirm selection, esc cancel. I think there is a native textual widget to show selectable items, but also check if already have ui patterns in existing tuis. ask me questions if you need clarifications
