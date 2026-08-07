---
description: Procedure-backed verifier for the `docs_updated` gate — inspects a task's change, updates the project's documentation per the configured doc-update spec (confirming with the user), and records the gate result. Run by the attended agent (task-workflow / aitask-resume), not the headless engine.
---

@.opencode/skills/opencode_tool_mapping.md

Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping above.

Arguments: $ARGUMENTS

@.claude/skills/aitask-gate-docs-updated/SKILL.md
