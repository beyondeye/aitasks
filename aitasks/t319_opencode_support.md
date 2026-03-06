---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [opencode, codeagent]
children_to_implement: [t319_3, t319_4]
created_at: 2026-03-05 23:48
updated_at: 2026-03-06 11:00
boardidx: 10
---

we have recently added support for codexcli (task t130 mainly) in the aitasks framework. now we want to add support for opencode. review what was done for adding support for codex and follow the same architecture to add support for opencode. we want also to refresh the list of supported llm model for opencode to allow to connect to open ai models via /connect (see https://x.com/thdxr/status/2009803906461905202). we need to find a better way to update the list of supported models in opencode: perhaps we should find a way to query opencode itself, launching opencode in batch models and explore available models (according to current authentications, this will require updating the current skill . this task should also include the updating of the website documentation about the support for opencode (see also latest tasks run where we update website docs for codex support). this is a complex tasks taht should be split in child tasks
