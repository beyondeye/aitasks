---
priority: high
effort: high
depends: []
issue_type: bug
status: Ready
labels: [git-integration]
created_at: 2026-03-02 16:10
updated_at: 2026-03-02 16:10
---

in task t277 we tested the full taskfrompullrequest flow, of creating a task from a pull request, executing the task, and updating back the pull request after task exection, verify proper contributor attribution as define in the taskfrompullrequest flow (see task t260). hit this task we want the same verificaiton for github remote. we can use the aitasks repository itself, there is alraeady a test pull request available. this is a complex tasks, with probably user interaction and collaboration for the tests that need to be split in child tasks like t277. ask me questions if you need clarificaions
