---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [codebrowser]
created_at: 2026-03-24 23:07
updated_at: 2026-03-24 23:07
---

currently in ait codebrowser tui, in history screen, we show the full history of tasks in reverse implementation time order. I would like also filtering of tasks by labels (that is in the currently loaded tasks, when the label filter button, options is activated (add also keyboard shortcut) collect label counts for currently loaded tasks, then show all existing labels (see labels.txt in aitasks/metadata) with usage count for current loaded tasks and allow to multiselect labels in a modal dialog (with fuzzy search and by scrolling up down with up down arrow, enter to select/unselct, and and somewhere in the dialog the full list of selected labels and total selected tasks (from loaded) with ok/cancel and also with a reset button to reset label filter. when a new chunk of files. when loading a new chunk of tasks, we currently load chunks of 10 tasks. for making the UX better wehn we have a label filter, if no tasks we the current selected label is found in the 10 loaded tasks, then load 10 more, and again with a maximum of 30 tasks per click/ select to the load more item. BY THE WAY we should show the current selected labels filter somewhere (probably at the top of the task history list columen
