---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [workflows, aitask_contribute]
created_at: 2026-03-12 17:04
updated_at: 2026-03-12 17:04
---

in the aitask-contribution-review skill we scan issues for comments that contains information of possible overlaps between issues, this information is created by an automated workflow. because of a bug, there are issues with multiple (duplicated) comments of this type. this was a bug, but it is probably a good idea to make the skill robust agains this case and when multiple comments of this type are found the last one (most recent shuld be used). for example of this problem, in order to debug code needed to parse them, see issue 6 and 7
