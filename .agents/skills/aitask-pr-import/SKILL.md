---
name: aitask-pr-import
description: Create an aitask from a pull request by analyzing PR data and generating a structured task with implementation plan.
---

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-pr-import/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Accepts a PR URL or number: `$aitask-pr-import 42` or `$aitask-pr-import https://github.com/org/repo/pull/42`.
