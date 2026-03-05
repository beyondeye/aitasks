---
name: aitask-pick
description: Select the next AI task for implementation from the `aitasks/` directory.
---

## Prerequisites

**BEFORE anything else**, read **`.agents/skills/codex_interactive_prereqs.md`**
and follow its requirements. Do not proceed until prerequisites are satisfied.

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-pick/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Accepts an optional task ID: `$aitask-pick 16` (parent) or `$aitask-pick 16_2` (child). Without argument, follows interactive selection.
