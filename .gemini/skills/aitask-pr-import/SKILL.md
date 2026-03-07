---
name: aitask-pr-import
description: Create an aitask from a pull request by analyzing PR data and generating a structured task with implementation plan.
---

## Plan Mode Prerequisites

**BEFORE executing the workflow**, read **`.gemini/skills/geminicli_planmode_prereqs.md`**
and follow its guidance for plan mode phases.

## Source of Truth

This is a Gemini CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-pr-import/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Gemini CLI adaptations, read **`.gemini/skills/geminicli_tool_mapping.md`**.

## Arguments

Accepts a PR URL or number: `/aitask-pr-import 42` or `/aitask-pr-import https://github.com/org/repo/pull/42`.
