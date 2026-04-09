---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [brainstorming, tui_switcher]
folded_tasks: [498]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-09 11:20
updated_at: 2026-04-09 15:31
completed_at: 2026-04-09 15:31
---

brainstorm integration with ait monitor tui and tui switcher is broken: first of all with have, in TUI switcher, in the list of available tui, brainstorm tui WITHOUT a task number: this must be removed. instead, if a brainstorm window tui is detected in the tmux session, and only it is detected show it in the list of TUI that can be switched to. currently it is shown in the "other" section in the tui switcher. anoter bug is that in the ait monitor tui in the panel with the list of code agents, also there the brainstorm window is shown in the "other" section. it should not shown there at all: this is a tui and we are going to support switching to it in the tui switcher dialog as explained above, it should not show in the ait monitor tui agent list panel. ask me questions if you need clarifications

## Folded from t498: Brainstorming Session Switcher for Monitor

Add support in the TUI switcher (in ait monitor and minimonitor) for opening the brainstorm TUI for EXISTING brainstorm sessions: a brainstorm session is always associated to a specific task and creates an ad-hoc branch for the brainstorm. When brainstorm branches are detected, add corresponding actions in the TUI switcher dialog to switch to or open the ait brainstorm TUI for those detected sessions. Show them like normal TUIs with an indicator if the TUI is already active or not. Remove the current brainstorm item in the TUI switcher that is not linked to any existing brainstorm session.
