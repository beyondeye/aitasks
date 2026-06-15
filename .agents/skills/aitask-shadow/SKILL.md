---
name: aitask-shadow
description: Shadow companion for a followed coding agent - reads its captured terminal output and, in one instruction-driven flow, explains it, helps answer an AskUserQuestion, or critically interrogates a plan. Advisory-only. Spawned by minimonitor; not a task-implementation command.
---

## Source of Truth

This is a Codex CLI skill wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-shadow/SKILL.md`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Use the source skill's arguments:

```text
$aitask-shadow <followed_pane_id> [<source_task_id>]
```
