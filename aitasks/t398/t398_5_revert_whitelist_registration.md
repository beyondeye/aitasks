---
priority: medium
effort: medium
depends: [t398_4]
issue_type: chore
status: Implementing
labels: [aitask_revert]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-16 14:56
updated_at: 2026-03-17 10:04
---

Add `aitask_revert_analyze.sh` to permission/tool whitelists for Claude Code, OpenCode, and Gemini CLI — both in seed templates and local project settings files. (Codex CLI does not use whitelisting.)

Also add the `aitask-revert` skill to Gemini CLI's skill/command registration (both seed and local).

## Scope

### Script whitelist (`aitask_revert_analyze.sh`)
- `.claude/settings.local.json` — add `Bash(./.aitask-scripts/aitask_revert_analyze.sh:*)`
- `.opencode/` equivalent settings
- `.gemini/` equivalent settings
- `seed/` templates for Claude Code, OpenCode, and Gemini CLI

### Skill registration (`aitask-revert`)
- `.gemini/skills/` or `.gemini/commands/` — add Gemini CLI version of the revert skill (adapted from `.claude/skills/aitask-revert/SKILL.md`)
- `seed/` Gemini CLI templates
