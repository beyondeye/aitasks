---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitask_pick, aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-11 09:35
updated_at: 2026-03-11 15:04
completed_at: 2026-03-11 15:04
---

currently in ait board TUI we have the option when a task detail is selected to press on the pick button that open a new shell launching the current configured preference (see ait settings) for code agent+ llm model to execute the task pick skill. the issue is that when working with multiplexed terminal with multiple tab/panes, the new opened terminal will be a separate windows, not integrated with the terminal multiplexer the user use. so we want to change what happens when the user press pick. instead of direclty issueing the command to open a new terminal instead show a dialog where we show the command that would be run (for the specific code agent, i.e. the code agemt tool name + line args that configure the prompt, and two buttons to the right one for copying the the full command and one only for copying the prompt that will be issued i.e. /aitask-pick <task number>. or perhaps better show two line with one clickable button tot he right for copying the text one linm for the full command, a second linke only for the prompt, plus two button at the bottom of the dialog: run in new terminal, and cancel. add also keyboard shortcuts for each of the buttons in the dialog
