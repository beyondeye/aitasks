---
name: aitask-note
description: Send a durable note to an existing aitask — context that task needs which is not itself work. Use when you learn something a task that already exists depends on, such as a stale assumption in its body, a wider blast radius, or a decision that changes its approach.
---

## Source of Truth

This is a Codex CLI skill wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-note/SKILL.md`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Optional. `<target-task-id>` names the recipient directly (e.g. `357`, or
`1657_6` for a child); omit it and the skill routes through Related Task
Discovery to choose one. `--from <id>` names the sending task, defaulting to
the task this session is implementing. `--text "..."` supplies a single-line
body.
