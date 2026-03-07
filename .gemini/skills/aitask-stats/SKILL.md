---
name: aitask-stats
description: Calculate and display statistics of AI task completions (daily, global, per-label).
---

## Source of Truth

This is a Gemini CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-stats/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Gemini CLI adaptations, read **`.gemini/skills/geminicli_tool_mapping.md`**.

## Arguments

Accepts optional flags: `--days N`, `--verbose`/`-v`, `--csv [FILE]`. Example: `/aitask-stats --days 14 --verbose`.
