---
name: aitask-reviewguide-classify
description: Classify a review guide file by assigning metadata and finding similar existing guides.
---

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-reviewguide-classify/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Accepts an optional fuzzy pattern: `$aitask-reviewguide-classify security`. Without argument, runs batch mode.
