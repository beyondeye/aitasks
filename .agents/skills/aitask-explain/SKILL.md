---
name: aitask-explain
description: "Explain files in the project: functionality, usage examples, and code evolution history traced through aitasks."
---

## Prerequisites

**BEFORE anything else**, read **`.agents/skills/codex_interactive_prereqs.md`**
and follow its requirements. Do not proceed until prerequisites are satisfied.

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-explain/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Accepts optional file/directory paths: `$aitask-explain src/app.py` or `$aitask-explain src/lib/`. Supports line ranges: `path:start-end`.
