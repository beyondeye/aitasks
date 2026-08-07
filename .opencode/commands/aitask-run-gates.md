---
description: Run a task's declared gates — the conversational front of the headless gate orchestrator engine. Dispatches unlocked machine-gate verifiers within their retry budgets, observes human gates without self-signalling, and reports.
---

@.opencode/skills/opencode_tool_mapping.md

Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping above.

Arguments: $ARGUMENTS

@.claude/skills/aitask-run-gates/SKILL.md
