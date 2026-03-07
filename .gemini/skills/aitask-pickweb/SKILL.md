---
name: aitask-pickweb
description: Pick and implement a task on Claude Code Web. Zero interactive prompts. No cross-branch operations — stores task data locally in .aitask-data-updated/.
---

## Plan Mode Prerequisites

**BEFORE executing the workflow**, read **`.gemini/skills/geminicli_planmode_prereqs.md`**
and follow its guidance for plan mode phases.

## Source of Truth

This is a Gemini CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-pickweb/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Gemini CLI adaptations, read **`.gemini/skills/geminicli_tool_mapping.md`**.

## Arguments

Required task ID: `/aitask-pickweb 16`. Zero interactive prompts. Stores data in `.aitask-data-updated/`.
