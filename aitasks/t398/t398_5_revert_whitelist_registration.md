---
priority: medium
effort: medium
depends: [t398_4]
issue_type: chore
status: Ready
labels: [aitask_revert]
created_at: 2026-03-16 14:56
updated_at: 2026-03-16 14:56
---

Add `aitask_revert_analyze.sh` to permission/tool whitelists for all agents — Claude Code, OpenCode, Codex CLI, and Gemini CLI — both in seed templates and local project settings files.

Also add the `aitask-revert` skill to Gemini CLI's skill/command registration (both seed and local).

## Scope

### Script whitelist (`aitask_revert_analyze.sh`)
- `.claude/settings.local.json` — add `Bash(./.aitask-scripts/aitask_revert_analyze.sh:*)`
- `.opencode/` equivalent settings
- `.codex/` equivalent settings
- `.gemini/` equivalent settings
- `seed/` templates for all four agents

### Skill registration (`aitask-revert`)
- `.gemini/skills/` or `.gemini/commands/` — add Gemini CLI version of the revert skill (adapted from `.claude/skills/aitask-revert/SKILL.md`)
- `seed/` Gemini CLI templates
