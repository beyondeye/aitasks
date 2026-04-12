---
name: aitask-contribution-review
description: Analyze a contribution issue, find related issues, and import as grouped or single task.
---

## Prerequisites

**If you are Codex CLI:** Read **`.agents/skills/codex_interactive_prereqs.md`** BEFORE proceeding.

**If you are Gemini CLI:** Read **`.agents/skills/geminicli_planmode_prereqs.md`** BEFORE proceeding.

## Source of Truth

This is a unified skill wrapper for Codex CLI and Gemini CLI. The authoritative skill definition is:

**`.claude/skills/aitask-contribution-review/SKILL.md`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

**If you are Gemini CLI:** For tool mapping and adaptations, read **`.agents/skills/geminicli_tool_mapping.md`**.

## Arguments

Accepts an optional issue number: `/aitask-contribution-review 42`. Without arguments, lists open contribution issues interactively for selection.
