---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [task_workflow]
children_to_implement: [t401_1, t401_2, t401_3, t401_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-16 10:51
updated_at: 2026-03-16 11:21
---

I have noticed that many time claude code when running the model-self-detection procedure in the task workflow, it writes custom code to parse the models_claudecode.json, it fails,then retries, this is not efficient. I would like to make the procedure execution faster and without need to retry. once the procedure has been rewritten, add child tasks (to be run on opencode, geminicli, codex) also to check the new procedure to be sure that it work also in the other codeagents suported by the aitasks framework

here is an excerpt of claude code execution code when running the model-self-detecion procedure with the failure: ● Read(.claude/skills/task-workflow/model-self-detection.md)
