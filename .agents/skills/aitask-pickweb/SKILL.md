---
name: aitask-pickweb
description: Pick and implement a task on Claude Code Web. Zero interactive prompts. No cross-branch operations — stores task data locally in .aitask-data-updated/.
---

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-pickweb/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Required task ID: `$aitask-pickweb 16`. Zero interactive prompts. Stores data in `.aitask-data-updated/`.
