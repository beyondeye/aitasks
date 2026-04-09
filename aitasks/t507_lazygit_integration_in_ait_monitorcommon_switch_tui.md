---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor]
children_to_implement: [t507_1, t507_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 10:36
updated_at: 2026-04-09 12:51
---

currently in ait monitor and all other tui with a tui switcher dialog that allow to switch between aitasks native tuis like board, settings, codebroser, monitor. I would like to suport like a "pseudo" native tui also lazygit to see current changes and git history. the actual git tui that is launched should be configurable in ait settings tui. in ait setup we should detect if lazygit is installed or any other similar common tuis and ask the user which one to use by default (default to lazygit if installed) in the settings tui allow to select among detected installed git management tuis. only one instance of lazygit (or similar) should be acive in a tmux session (similar handling as is currently done for native aitasks tuis). in ait setup there should be also an option to ask the user if he want to install lazygit, if no git management tui is detected as installed. this is a complex task that should be splitted in child tasks
