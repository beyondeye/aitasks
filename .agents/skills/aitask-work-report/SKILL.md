---
name: aitask-work-report
description: Draft a manager-facing work report from selected board columns.
---

## Source of Truth

This is a Codex CLI skill wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-work-report/SKILL.md`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **`.agents/skills/codex_tool_mapping.md`**. `request_user_input` has no multi-select mode — for the interactive column/task selection, use the source skill's "Agents without native multi-select" fallback (one free-text comma-separated id list, gatherer-validated).

## Arguments

Optional: `--columns <csv>`, `--tasks <csv>` (requires `--columns`),
`--velocity-model <id>`, `--velocity-window <days>`. See source skill
documentation.
