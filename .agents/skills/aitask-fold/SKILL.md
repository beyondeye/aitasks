---
name: aitask-fold
description: Identify and merge related tasks into a single task, then optionally execute it.
---

## Prerequisites

**BEFORE anything else**, read **`.agents/skills/codex_interactive_prereqs.md`**
and follow its requirements. Do not proceed until prerequisites are satisfied.

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-fold/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Accepts optional task IDs: `$aitask-fold 106,108,112` or `$aitask-fold 106 108`. Without arguments, follows interactive discovery.
