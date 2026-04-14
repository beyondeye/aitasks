---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 16:25
updated_at: 2026-04-14 16:27
---

in ait codebrowser we have recently (task 541) improved the feature of being able to switch between tui panes using tab: in code browser main screen there are supposed to be 4 switchable panes: 1) opened file history 2) file tree 3) file content 4) detai pane.  pressing tab should cycle focus between these panes (the detail pane only if visible). this not what is happening: there one more additional pane that get focus with tab, I am not shure if this is the title pane or the footer, or something else, anyway there is something else that get focus that shouldnnt. another bug is that when the last opened file pane is focused, tab move focus to the next entry in the last opened files, instead of moving focus to the next pane.    There is a related bug in the history screen (with the history of completed tasks) again in the ait codebrowser tui: the task detail pane does not appear to get focused when we toggle focus between pane with tabs: or perhaps it get focus but no widget in it get focus so it does not appear to be focused? What i see is that when toggling fuocus with tab in the history screen I see this order: 1) completed tasks 2) recently opened tasks 3) something else that when focus does not react to me pressing up/down arrow to move between focused widget: since the task detail pane has focusable widget I assum that this "something" that get focused is not the task detail pane, but I can be wrong. ask me questions if you need clarifications
