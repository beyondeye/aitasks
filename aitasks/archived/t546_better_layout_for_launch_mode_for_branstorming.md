---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-14 13:04
updated_at: 2026-04-14 14:20
completed_at: 2026-04-14 14:20
---

in ait settings tui in the agent defaults tab we have the list of default code agents for brainstorming: for each we have two settings: codeagent+llm to use and launch mode. is is not clear from the label (launch_mode, same label for all (brainstorm-explorer, brainstorm-synthetizer, etc.) to which specific agent it refer: to possible fixes (perhaps do both). add some padding at start of the launch_mode label so it is clearer that this is a subsetting for the previous line that is the codeagent for some brainstorm op. 2) change the launch_mode label to be specific to the brainstorm codeagent setting it refer to: that is change "launch_mode" to "brainstorm-explorer launch_mode".  ask me questions if you need clarifications
