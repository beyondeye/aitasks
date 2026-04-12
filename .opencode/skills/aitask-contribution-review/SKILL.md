---
name: aitask-contribution-review
description: Analyze a contribution issue, find related issues, and import as grouped or single task.
---

## Plan Mode Prerequisites

**BEFORE executing the workflow**, read **`.opencode/skills/opencode_planmode_prereqs.md`**
and follow its guidance for plan mode phases.

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-contribution-review/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
OpenCode adaptations, read **`.opencode/skills/opencode_tool_mapping.md`**.

## Arguments

Accepts an optional issue number: `/aitask-contribution-review 42`. Without arguments, lists open contribution issues interactively for selection.
