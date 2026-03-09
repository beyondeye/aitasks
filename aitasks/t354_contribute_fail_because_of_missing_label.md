---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_contribute]
created_at: 2026-03-09 22:14
updated_at: 2026-03-09 22:14
---

I have just tried to run the aitask_contribute skill and at the end of the workflow, the issue creation failed bacause the label "contribution" was undefined as available label for issues. what follows is the log the claude code session with the failore and the fix

● Bash(./.aitask-scripts/aitask_contribute.sh --area-path ".claude/" \

to fix the issue claude code created the label with gh. here the problem is two-fold 1) all interaction with the repo should be encapsulated in aitask_contribute that handle different remote types automatically (github, gitlab, bitbucked) 2) is creating a label an operation that any user is allowed? contributions are supposed to come from any authenticated github/gitlab/bitbucket user. in this case I am the owner of the repo with full access, but what about a "normal" user. we cannot rely on similar "hacks" by the code agent to solve this kind of problems
