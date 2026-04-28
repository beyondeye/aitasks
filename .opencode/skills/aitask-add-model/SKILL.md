---
name: aitask-add-model
description: Register a known code-agent model in models_<agent>.json, optionally promote it to default across config/seed/DEFAULT_AGENT_STRING.
---

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-add-model/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
OpenCode adaptations, read **`.opencode/skills/opencode_tool_mapping.md`**.

## Arguments

Accepts optional flags: `--agent <name>`, `--name <id>`, `--cli-id <str>`, `--notes <text>`, `--promote`, `--promote-ops <csv>`, `--dry-run`. Without arguments, prompts for missing inputs interactively. Example: `/aitask-add-model --agent claudecode --name opus4_7_1m --cli-id 'claude-opus-4-7[1m]' --promote`.
