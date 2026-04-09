---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 11:10
updated_at: 2026-04-09 11:25
---

int ait monitor tui we have support for enter keyboard shortcut that send an "enter" key to the currently selected codeagent in the list. there is an issue that when doing this, still the agent window "preview" is not refreshed immediatly so that it is not clear that the enter action has been actually sent or not. the fix should change the next refresh to be done after 300 ms from when the enter key was sent. I don't knww what would be better, if to queue a separate delayed refrhesh from he standard periodical refresh, or to integrate with the existing refresh mechanism. the additional effort of integrating with the existing refresh mechanish could be worthwhile if possible so that we can dinamically adjust the time to the next refresh if needed, or something similar please explore the option and evaluate complexity of different implementations
