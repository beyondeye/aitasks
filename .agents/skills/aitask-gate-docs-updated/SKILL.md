---
name: aitask-gate-docs-updated
description: Procedure-backed verifier for the `docs_updated` gate — inspects a task's change, updates the project's documentation per the configured doc-update spec (confirming with the user), and records the gate result. Run by the attended agent (task-workflow / aitask-resume), not the headless engine.
---

## Source of Truth

This is a Codex CLI skill wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-gate-docs-updated/SKILL.md`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

See source skill documentation.
