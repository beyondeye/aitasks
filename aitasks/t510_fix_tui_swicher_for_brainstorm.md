---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [brainstorming, tui_switcher]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 11:20
updated_at: 2026-04-09 11:39
---

brainstorm integration with ait monitor tui and tui switcher is broken: first of all with have, in TUI switcher, in the list of available tui, brainstorm tui WITHOUT a task number: this must be removed. instead, if a brainstorm window tui is detected in the tmux session, and only it is detected show it in the list of TUI that can be switched to. currently it is shown in the "other" section in the tui switcher. anoter bug is that in the ait monitor tui in the panel with the list of code agents, also there the brainstorm window is shown in the "other" section. it should not shown there at all: this is a tui and we are going to support switching to it in the tui switcher dialog as explained above, it should not show in the ait monitor tui agent list panel. ask me questions if you need clarifications
