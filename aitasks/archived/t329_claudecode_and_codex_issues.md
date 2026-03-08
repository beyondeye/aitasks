---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Done
labels: [codexcli, claudecode]
assigned_to: dario-e@beyond-eye.com
implemented_with: opencode/openai_gpt_5_3_codex
created_at: 2026-03-08 07:51
updated_at: 2026-03-08 08:08
completed_at: 2026-03-08 08:08
---

this is a task to add a new subpage to the Installation page in the website, to document known issues for the aitasks framework with currently two sections: 1) Claude Code: don't use claude code with models with MEDIUM EFFORT they fail to follow workflow instructions, and generally give poor results. 2) Codex Cli: although openai models are very capable, the codexcli has several issues when using it with the aitasks framework. codex cli is limited to use interactive user questions only in plan mode and this break several workflow, especially workflow like aitask-pick based. also codexcli has no support fow allow-lists for calls to bash scripts. all this makes using the user expeience when working with codexcli and aitasks not very good. it is basically working but it  is often best using openai llm models through opencode (that support connecting directly connecting to your plus/pro plans.

this the general idea for the text to write, please write better and also try to add references to opencode and codex documentation that document the issue reported
