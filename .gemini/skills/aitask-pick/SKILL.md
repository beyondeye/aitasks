---
name: aitask-pick
description: Select the next AI task for implementation from the `aitasks/` directory.
---

## Plan Mode Prerequisites

**BEFORE executing the workflow**, read **`.gemini/skills/geminicli_planmode_prereqs.md`**
and follow its guidance for plan mode phases.

## Source of Truth

This is a Gemini CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-pick/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Gemini CLI adaptations, read **`.gemini/skills/geminicli_tool_mapping.md`**.

## Arguments

Accepts an optional task ID: `/aitask-pick 16` (parent) or `/aitask-pick 16_2` (child). Without argument, follows interactive selection.
