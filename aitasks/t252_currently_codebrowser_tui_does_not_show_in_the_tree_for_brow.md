---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-26 08:34
updated_at: 2026-02-26 16:48
boardcol: now
boardidx: 10
---

currently codebrowser tui does not show in the tree for browsing repository files the .claude directory even though it is under source control. need to understand why it is filtered out. this is not desirable behavior. need to check if there are source contrrolled filed that are currently excluded in the codebrowser and why. check also how source cntrolled binary files are handled: obviously no text content for them should be shown but still we can show which commits are associated to them (i.e. task plan files) this can still be usefull information
