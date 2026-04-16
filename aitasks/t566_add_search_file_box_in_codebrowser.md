---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-16 08:13
updated_at: 2026-04-16 10:01
---

currently the only way to select a file in codebrowser tui is manually drill down in the file tree widget. this is not optimal: add a sarch box at the top (make it selectable with tab, that is tab when cycling between, codebrowser panes will cycle also through the search box).
 align the search box at the start of the code detail pane. the search box should support fuzzy search. look at https://github.com/batrachianai/toad, specifically the file picker there. for this can be implemented in textual. ask me questions if you need clarifications. this is complex task probably, so split it in multiple child tasks if needed
 
