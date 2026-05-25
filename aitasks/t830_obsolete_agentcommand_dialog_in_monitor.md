---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor]
created_at: 2026-05-25 18:23
updated_at: 2026-05-25 18:23
---

in ait monitor with the "n" shortcut we can "pick" a new sibling task. it uses the agentcommand dialog that is also used in ait board (and other tuis?) to choose the actual agent to run aitask-pick. we recently in ait board added the option in the agentcommand dialog there to edit the execution profile to use. but this change was not propagated to other tuis that use the agentcommand dialog? why the full agentcommand dialog code is not shared (for example in codebrowser for spawning explain on in ait monitor as reported)?
aitasks/archived/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md
