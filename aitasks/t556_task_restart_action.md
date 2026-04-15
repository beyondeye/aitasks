---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-15 10:10
updated_at: 2026-04-15 10:28
---

in ait monitor tui we have an action "n" (pick) next sibling that simplify pick workflow for sibling/child tasks. we want something similar for the task itself, that is a commnad to restart a task: the comamnd should be active only if the associated terminal is currently idle, and when the command is run it should ask for confirmation and warn if the task is not currently in the "ready" status. when approved the command should 1) kill the current agent session 2) run pick again for the selected task (use the usual dialog for spawning pick in all aitasks tui). ask me questions if you need clarifications

note: the kill command for existing codeagent should be sent only after confirmation for running the pick command in the agent spaan dialog
