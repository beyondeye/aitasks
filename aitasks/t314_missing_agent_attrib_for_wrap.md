---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codeagent, codexcli]
created_at: 2026-03-05 12:58
updated_at: 2026-03-05 12:58
---

I have  just run an aitask_wrap with codex codeagent and I noticed that the executing coding agent metadata was not added to the wrapped task. this is not actually a big issue, since the wrap skill does not actually implement anything but still it would be nice to have this information the wrap skill. in general need it would be better to extract the instructions to identify the current executing codeagent and llmmodel (as currently defined in the task-workflow, that also set the task metadata field to all skills where this can be relevant that we missed out
