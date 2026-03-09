---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codexcli, task_workflow]
created_at: 2026-03-09 10:45
updated_at: 2026-03-09 10:45
---

the codex cli does properly return the name of the current llm model in use, it return a generic GPT-5 id, this create problems for the agent coauthor attribution procedure: here is an example of the lof of the conversation where the error occurred

• Ran test -f aitasks/metadata/project_config.yaml && sed -n '1,120p' aitasks/metadata/project_config.yaml || true

in the end codex succeeded in obtaining the correct modelid but we should find a solution of the root problem. apparently even though codex does not directly answered the question about the current model in use directly but in the end decided that GPT5_4 was the model in use and this was actually correct. this makes me think that there is probably a way to obtain the crrect llm model id in use.  I propose to desgin a plan for testing multiple interactive questions to code and chcking the results or bettere trying to run codex in batch mode with multiple prompts and model configuration (from the command linke) and find out what will work, and when this is found update the codeagent identification procedure in task-workflow skill or related skills
