---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_review]
children_to_implement: [t259_1, t259_2, t259_3, t259_4, t259_5, t259_6, t259_7]
created_at: 2026-02-26 12:45
updated_at: 2026-02-26 18:44
boardidx: 40
---

currently the code review flow (in the aitask-review skill) is designed for interactive work: select file to work on interactively (or not), select the review type interactively, run the review and show proposed changes with priority, interactively choose desired fixes and create tasks for implementation. there are use cases where this workflow is not right. the problem is mainly when we want to process a large number of files of perhaps even whole repository using some selected guidelines, in such cases there several problems 1) we cannot rely on a single claude code session (problem with context size) 2)we cannot interactively choose what fixes to schedule in a task per file because it interrupts the batch processing flow. so the idea is allow a different mode of operations where a bash script drives multiple claude code session that are run in bathc mode, running a variation of the current aitask-review skill). the new bash script will incorporate the file selection \directory selection (fzf powered) it should also allow selection of files in directories outside of the current project repo. the claudes with the batch mode version of the aitask-review skill will need to write findings in some standard format for each file that can processed not only by claude by also by external programs, lets say a python tui to review the claude code review recommendation shown in a tree of files like the source repo, similar to what is done in the codebrowser tui. when a direcotry is clicked show a summary of all issues found for that directory divided by type, severity, etc and from which reviewguide the recommendations come. then in the tui we should implement the actual creation of actual aitasks based on the existing recommendation. the actual UX flow for this will defined later. I am just mentioning it in order to make it clear the requirement when design the file format (probably based on yaml) for writing the aitask-review findings in batch mode. this is a very complex tasks, that will spawn many child tasks. ask me questions if you need clarifications
