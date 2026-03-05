---
name: aitask-pickrem
description: Pick and implement a task in remote/non-interactive mode. All decisions from execution profile - no AskUserQuestion calls.
---

## Prerequisites

**BEFORE anything else**, read **`.agents/skills/codex_interactive_prereqs.md`**
and follow its requirements. Do not proceed until prerequisites are satisfied.

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-pickrem/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Required task ID: `$aitask-pickrem 16` (parent) or `$aitask-pickrem 16_2` (child). Fully autonomous, no interactive prompts.
