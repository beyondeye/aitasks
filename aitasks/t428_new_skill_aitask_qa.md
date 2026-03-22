---
priority: medium
effort: high
depends: []
issue_type: test
status: Ready
labels: [testing, qa]
children_to_implement: [t428_3, t428_4, t428_5, t428_6, t428_7]
created_at: 2026-03-22 10:40
updated_at: 2026-03-22 12:40
---

currently support for tests and quality assurance in aitasks frameworks is not not structured enough. we currently have the the test-followup-task procedure integrated in task-workflow. but I think that a separate aitask-qa skill would be better (separation of concern). so what I want to do is to remove the integration of the test-follouup procedure from task-workflow and create, on the basis of that procedure, a separate skill to create followup tasks to add and run tests to some existing or archived task. the skill should take a task argument, and if no task argument is passed, it should interactively allow to select a task from recently archived tasks. it should work similarly to the test followup-procedure. for additional inspiration of what can integrated in this skill look also at https://github.com/garrytan/gstack/blob/main/.agents/skills/gstack-qa/SKILL.md https://github.com/garrytan/gstack/blob/main/.agents/skills/gstack-plan-eng-review/SKILL.md  https://github.com/garrytan/gstack/blob/main/.agents/skills/gstack-qa-only/SKILL.md. https://github.com/obra/superpowers/tree/main/skills/test-driven-development  https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md NOTE that the links I provided are thought for integrating in different frameworks. you should extract from there what is relevant to the aitasks frameworks and contextualize what is there so that analyze chnages introucdeb by the target tasks and propose the most appropriate test plan to add. this is a complex task that should be split into child tasks. including basic implementation, possible extensions (based on referenced links), website documentations update (new skill+update of exisiting skils docs if the reference the test-followup-task.md procedure), whitelisting of skills for geminicli and skill/command wrappers for codex/gemini/opencode. ask me questions if you need clarifications
