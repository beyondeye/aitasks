---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [brainstorming, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-25 12:53
updated_at: 2026-03-25 13:21
---

in task 464 we have introduced top/down arrow navigation for various options/commands in most of the codeborwser tui. we want to improve this in two ways 1) currently if no option/ command is focused (when a specific tab is selected) up/down arrows do not work: we need frist to focus one of the command/ options (i.e. with the mouse click) and the up/down arrows start to work, to move focus. 2) second isue is actually feature but is related to issue 1: that is we want up arrow to move focus to the tab line itself, that is in currently the topmost available widget/ text is focused and we press the up arrow again what get focused is the tab itself , so that buy prssing left /right arrow now we can move between tabs.

ask me questions if you need more clarifications
