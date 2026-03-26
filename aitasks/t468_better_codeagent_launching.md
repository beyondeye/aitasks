---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-26 09:34
updated_at: 2026-03-26 09:42
---

we have several places in aitasks TUIs (ait board, ait codebrowser) where we can trigger codeagent sessions (pick in ait board, explain and qa in codebrowser) We have recently improve the way we launch aitask-pick in board, with a modal dialog that shows the actual command that will be run and the prompt so the user can choose how to actually run the command. I want to refactor the code uses in ait board and use the same pattern also in codebrowser when launching qa and explain. this is a complex tasks that should be split in child tasks
