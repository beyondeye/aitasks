---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitor, tui]
children_to_implement: [t475_1, t475_2, t475_3, t475_4, t475_5, t475_6]
created_at: 2026-03-29 09:08
updated_at: 2026-03-29 10:58
boardidx: 10
---

We are going to integrate the aitasks framework deeply with tmux. tmux has features that allow to monitor execution of multiple claude coe instances much better than any terminal emulateor that support multiple tabs. tmux can monitor if a controlled terminal session is "idle" that its output did not update for a certain time, and tmux can also programmatically send input to a terminal. this can be used to create a ait monitor tui (to be added to existing tuis, like ait board) that shows all active code agent windows/pane in some tmux session, and which is idle, and what it is its last output: if it is idle it probly need user input, so add tui option to automatically send enten to confirm claude code security question (show the last part of claude output so the user know what is confirming) or the option to swich to that window/pane so the user can direclty interact with it. this is a complex tasks that need to be splitted in child tasks, need also to add documentation in the aitasks website for the new tui. ask me questions if you need clarifications
