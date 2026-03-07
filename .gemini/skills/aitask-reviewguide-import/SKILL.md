---
name: aitask-reviewguide-import
description: Import external content (file, URL, or repository directory) as a reviewguide with proper metadata.
---

## Source of Truth

This is a Gemini CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-reviewguide-import/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Gemini CLI adaptations, read **`.gemini/skills/geminicli_tool_mapping.md`**.

## Arguments

Accepts an optional source: `/aitask-reviewguide-import https://...` or `/aitask-reviewguide-import path/to/file.md`. Without argument, prompts for source.
