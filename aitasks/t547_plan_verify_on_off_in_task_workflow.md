---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [aitask_pick, task_workflow]
children_to_implement: [t547_1]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 14:08
updated_at: 2026-04-14 16:11
---

recent changes to claude code has dramatically increased token usage for planning. plan quality has also improved. the problem is that now, after planning phase, llm context is almost full already, this causes us to reach llm context usage level that require compact for completing the task. this is very bad, both because of delays because of compacting and also loss of context and potential break down of the requested workflow. as a work around to this issue, we need to rethink how automatic plan verification work in task workflow. we need to be able to run aitask-pick allowing the user to skip plan verification. But running plan verification at least once is very good practice: almost always this produce better plans, with gotchas detected before implementation. note that this a claude code specific issue, and specific to the current claude code 200k token window, that can expand in the future. codex has already a much larger context window, and worse planning phase by the way. Note also that plan_verification (to run it or not) is part of execution profile settings (plan_preference and plan_preference_child) ; for faat execution profile it is 1)verify for child, use current for normal task.

we want to add some metadata to the plan so we know if the plan has already been verified and when by which codeagent: allow for multiple entries for the this new plan_verified metadata, to allow to record multiple verifications. then change workflow to update this metadata each time a plan is verified and updated. then chnage the execution_profile settings to add more settings: add a time parameter that define after how much time a plan verification is considered stale (default to one day) 2) keep existing autoverify execution profile options but extend them to have the number of required verifications. if required verification are done the skip verification, unless verification are stale: if verification are stale then report verification status and ASK if we want additional verificaiton. 3) if the llm has access to current context usage, and at the end of plan verification llm context usage is over 70% suggest to stop after plan verification and approval, and not continue to implementation. ask me questions if you need clarificattons. please analyze my proposal and check if it make sense or you would suggest something different
this is a complex task that must be split in child tasks
