---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask-create]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-03 22:12
updated_at: 2026-03-03 23:12
completed_at: 2026-03-03 23:12
---

when trying to use aitask-create in a git repository without a configured git remote ait create failed to finalize task id. this a quite a big issue. it is true that most of the time a git remote is available but why is that, are there any alternative solutions? we should have an alternative for assigning task ids when no git remote available: see attached error log

Shell ./aiscripts/aitask_create.sh --batch --finalize draft_2026… │    │                                                                      │
