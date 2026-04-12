---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board, codeagent]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-11 22:48
updated_at: 2026-04-12 09:22
---

we have several places in aitaks tuis where action triggered in tuis like task pick, review, explain, qa, etc. and we have a modal dialog with the actual command to run to spwan a codeagent. we would like to add the option in such dialog (that is ahared dialog in ait board, and ait codebrowser and potentially other tuis) to change the default codeagent and llm model to use for the action FOR that specific action: so basically we need to refactor the code in ait settings that we use to select the default codeagnet+llm model to use for some actions and reuse it to add the option to dynamiccally change this. this is a complex task that should be split in child tasks. ask me questions if you need clarifications
