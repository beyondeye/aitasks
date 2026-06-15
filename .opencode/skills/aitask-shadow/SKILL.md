---
name: aitask-shadow
description: Shadow companion for a followed coding agent — reads its captured terminal output and, in one instruction-driven flow, explains it, helps answer an AskUserQuestion, or critically interrogates a plan. Advisory-only. Spawned by minimonitor; not a task-implementation command.
---

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-shadow/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
OpenCode adaptations, read **`.opencode/skills/opencode_tool_mapping.md`**.

## Arguments

/aitask-shadow <followed_pane_id> [<source_task_id>]
