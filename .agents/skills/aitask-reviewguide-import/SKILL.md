---
name: aitask-reviewguide-import
description: Import external content (file, URL, or repository directory) as a reviewguide with proper metadata.
---

## Prerequisites

**BEFORE anything else**, read **`.agents/skills/codex_interactive_prereqs.md`**
and follow its requirements. Do not proceed until prerequisites are satisfied.

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-reviewguide-import/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Accepts an optional source: `$aitask-reviewguide-import https://...` or `$aitask-reviewguide-import path/to/file.md`. Without argument, prompts for source.
