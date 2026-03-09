---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_contribute]
created_at: 2026-03-09 23:12
updated_at: 2026-03-09 23:12
---

when creating new issue with aitask-contribute, we don't actually check if the same issue was already addressed in another pr or contribution issue (generated with aitask-contribute skill). the repo mantainer need to run aitask-issue-import one by one for each issue and manually check if the changes are related or not. this is not ideal. also there is the risk of prompt injection in issues if there is no filter of the issues that are allowed to be imported to aitasks. a possibility. in order to reduce needed processing on the reviewer side, assuming that the contributor is honest, is to add in the aitask-contribute skill flow processing that extract a

a unified "signature" to the contribution, extracted to the aread/set of file type of fix etc. this auto generated "signatures" should be easy to compare to find "matches"m and perhaps we can add an automation flow that add labels based on this signatures when an issue is created, and the reviewer can filter issues by "signatures" or set of labels. I am not sure how feasible is this solution.

about the issue of prompt injection in created issues, this cannot be handled on the "contributor" side that can be hostile, it must handled on the "reviewer" side or with some kind of automated workflow. this should be probably left to a follow up tasks.

I need to brainstorm a few possible soultions at least the first part of the problem (classifying and grouping similar issues). by the way currently we can import a task only from a single issue, we cannot merge multiple issue into a single imported task. this should also be considered when trying to solve this problem.  this is a complex problem. at the first stage need to brainstorm severeal different possible solutions, at the second stage we will try to split the selected solutions into child tasks. ask me questions if you need clarifications
