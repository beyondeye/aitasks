---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [aitask_pick]
children_to_implement: [t777_1, t777_2, t777_3, t777_4, t777_5, t777_6, t777_7, t777_8, t777_9, t777_10]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-17 09:44
updated_at: 2026-05-17 12:00
---

I want to redesign the way execution profiles in the aitasks framework control the actul procedure executed in skills like aitask-pick. Currently how execution profiles work: they define "variables" whose value control the actual execution flow of skill like aitask-pick. There are several issue with that: first we rely on the fact that the LLM does not loose focus the actual values passed for the execution profile and for this purpose we even "reread" the execution profile to "refresh" the llm mameory. Another issue is that a possible value for execution profile variable is ASK, but many coding agent (like codexcli) does not support askuserquestion prompts in skills if we are outside of plan mode. An additional problem is the overhead of resolving the current execution profile or asking for it. Another problem that the skill execution flow can become non linear becasue of possible execution profile parameters choice. In order to solve all these issues and allow for better agent skills flexibility and expandability, I would like to introduce an alternative mechanism: dynamically building the actual skill executed (for example for aitask-pick) based on execution profile variables BEFORE the skills is executed: rewrite the skills using some templating library (in python) that allow to assemble the actual skill executed from blocks according to the current execution profile choice for that skill. also add to agent run dialog that we use to trigger the skill additional ui to change the execution profile variables "per" run. in other words, refactore the code in ait settings where we can edit the execution profile variable in common code that can be used to edit execution profile variable for a specific run. ask me questions if you need clarifications. the initial target for this redesign is specifically the aitask-pick skill. this is a complex tasks that should be split in child tasks
