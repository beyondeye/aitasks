---
name: aitask-pickrem
description: Pick and implement a task in remote/non-interactive mode. All decisions from execution profile - no AskUserQuestion calls.
---

## Plan Mode Prerequisites

**BEFORE executing the workflow**, read **`.gemini/skills/geminicli_planmode_prereqs.md`**
and follow its guidance for plan mode phases.

## Source of Truth

This is a Gemini CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-pickrem/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Gemini CLI adaptations, read **`.gemini/skills/geminicli_tool_mapping.md`**.

## Arguments

Required task ID: `/aitask-pickrem 16` (parent) or `/aitask-pickrem 16_2` (child). Fully autonomous, no interactive prompts.
