---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [statistics, aitask_monitor]
children_to_implement: [t597_1, t597_2, t597_3, t597_4, t597_5]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 17:22
updated_at: 2026-04-19 17:52
---

I would like to create a new TUI that integrates with the other existing TUIs (ait board ait codebrowser, settings etc). the new TUI should integrate with tmux via the TUI switcher dialog (a new entry in the TUI switcher for the new stats tui, and integrate of the new tui switcher in the stats tui itself). the new stats tui should show several panes with meaningful stats extracted from running ait stats bash script. the current ait stats bash script has already a --plot mode to generate stats, some of the code there could be reused to for the new stats tui. I not sure if to use the python graph library we used in the ait stats --plot or instead get ideas from https://github.com/charles-001/dolphie project. about the stats pane to show. this is should be configurable in a modal dialog, and the configiration stored between runs. there should be standard combinations, and also allow the user generate a custom comnbination of panes (also stored in the tui preferences, peristed between reloeads). ask me questions if you need clarificatiosn. this is complex task that need to be split in child tasks
