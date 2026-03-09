---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [codexcli]
children_to_implement: [t339_5]
created_at: 2026-03-08 17:29
updated_at: 2026-03-09 14:08
---

currently when in aitask-pick code for a task is commited to git it is marked as coauthored by me (beyondeye) and claude, when aitask-pick is run in claude-code. we should a similar feature when running aitask-pick (or other skills that use the task-workflow) so that we also indicate as coauthor the appropriate code agent (not the llm model). analyze how claude do it and make sure that when running the task workflow on codex, opencode, geminiclu we also set the coauthor. look also to the current commits in github aitask repo for commit formats. this tasks should be probably decomposed in child tasks, with one child task for support of coauthored commits for each supported code agent in aitasks framework (easier to debug)
