---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: []
children_to_implement: [t221_6]
created_at: 2026-02-23 10:08
updated_at: 2026-02-23 13:03
boardidx: 70
---

Currently aitasks and aiplans directory are part of the main branch. this make running all skills and bash scripts that work with aitasks and aiplans data simpler. but this is causing several problems 1) when working on multiple PCs we need to call git pull to get the updated lists of aitasks, we possible merge conflicts and need to rebase when the changes to tasks are actually independent from changes to actual code 2) all the commits when updating tasks, creating tesks in the main branch are "noise" when trying to look at the actual code commits with implementation of tasks: we solved this but adding the ait: prefix to commit messages but still this is a little bit messy.

The synchronization of tasks between multiple pcs / client is probably the main issue. the question is: it would be possible to move aitasks/aiplans to a separate branch without significantly complicating claude code skills / bash scripts to work with them? or perhaps by encapsulating BETTER all the logic for working with task definitions, including querying tasks listsing tasks, also from the ait python board to shell script that encapsulate the actual branch when aitasks/aiplans are stored, it would be possible to separate code from task branches in  seamless way. this is a big rfactoring tasks, that require designing missing bash scripts for task and plans intereactions, rewriting all script that interact with tasks to work with data from a separate branch and rewrite all askill to do all task and plans interactions, and update documentation about this change
