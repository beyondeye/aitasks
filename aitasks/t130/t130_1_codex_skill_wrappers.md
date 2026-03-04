---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitasks, codexcli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-04 10:46
updated_at: 2026-03-04 10:54
---

## Context

This is child task 1 of t130 (Codex CLI support). It creates the 14 Codex CLI skill wrapper files in `.agents/skills/` plus seed config and instructions files.

The aitasks framework uses Claude Code skills (`.claude/skills/`) as the source of truth. Codex CLI wrappers are thin SKILL.md files that reference the Claude Code skills and provide a tool mapping table for Codex CLI equivalents.

Users invoke Codex skills with `$skill-name` (equivalent to Claude Code's `/skill-name`). Skills in `.agents/skills/` are auto-discovered by Codex CLI.

## Key Files to Create

### 14 Skill Wrappers in `.agents/skills/<name>/SKILL.md`

Each wrapper follows a consistent template structure:

```yaml
---
name: <skill-name>
description: <same description as corresponding Claude Code skill>
---
```

Followed by:
1. **Source of Truth** section — points to `.claude/skills/<name>/SKILL.md`
2. **Arguments** section — skill-specific argument documentation
3. **Tool Mapping** table — Claude Code tools to Codex CLI equivalents
4. **Codex CLI Adaptations** — shared adaptations section

Skills to wrap (all user-invocable Claude Code skills):
- aitask-pick (optional: task ID like `16` or `16_2`)
- aitask-create (no args, interactive)
- aitask-explore (no args, interactive)
- aitask-fold (optional: comma/space-separated task IDs)
- aitask-review (no args, interactive)
- aitask-stats (optional: `--days N`, `--csv`, `-v`)
- aitask-changelog (no args)
- aitask-wrap (no args)
- aitask-explain (optional: file paths, supports `path:start-end`)
- aitask-pr-import (optional: PR URL or number)
- aitask-reviewguide-classify (optional: fuzzy pattern)
- aitask-reviewguide-import (optional: file/URL/repo path)
- aitask-reviewguide-merge (optional: 0-2 patterns)
- aitask-refresh-code-models (no args)

Internal skills (task-workflow, user-file-select, ait-git, etc.) do NOT get wrappers.

### Tool Mapping Table (shared across all wrappers)

| Claude Code | Codex CLI | Notes |
|---|---|---|
| AskUserQuestion | request_user_input | Max 3 questions, 3 options. Suggest mode only. |
| Bash | exec_command | Direct equivalent |
| Read | exec_command("cat file") | |
| Write/Edit | apply_patch | |
| Glob | exec_command("find ...") | |
| Grep | exec_command("grep ...") | |
| EnterPlanMode | _(n/a)_ | Plan inline |
| ExitPlanMode | _(n/a)_ | Plan inline |
| Agent | _(n/a)_ | Execute steps directly |
| WebFetch/WebSearch | web.run | |
| Skill(name) | Read referenced SKILL.md | |

### Seed Files

**`seed/codex_config.seed.toml`** — aitask-specific Codex config for merging during setup:
- `sandbox_mode = "workspace-write"` with `network_access = true`
- Protective `prefix_rules` for dangerous commands (rm -rf, git push --force to main, etc.)
- Comments explaining each setting
- NOTE: Codex prefix_rules only support `prompt` or `forbidden` decisions, NOT `allow`

**`seed/codex_instructions.seed.md`** — Codex system prompt template:
- References CLAUDE.md/AGENTS.md for project docs
- Documents `$skill-name` invocation pattern
- Agent identification: `codex/<model_name>` from `models_codex.json`

### aitasks-project-specific files

**`.codex/config.toml`** — Full Codex config for the aitasks repo itself (includes seed settings plus project-specific settings). NOT distributed to other projects.

**`.codex/instructions.md`** — Codex instructions for the aitasks repo itself. NOT distributed.

## Reference Files for Patterns

- `.claude/skills/aitask-pick/SKILL.md` — Most complex skill, good reference for wrapper
- `.claude/skills/aitask-stats/SKILL.md` — Simple skill, good reference for minimal wrapper
- `aidocs/codexcli_tools.md` — Codex CLI tools reference (tool namespaces, arguments)
- `seed/claude_settings.local.json` — Pattern for seed file structure

## Implementation Steps

1. Create `.agents/skills/` directory
2. For each of the 14 skills: create `<name>/SKILL.md` with the wrapper template
3. Read each Claude Code skill's frontmatter to get exact name/description
4. Customize the Arguments section for each skill
5. Create `seed/codex_config.seed.toml` with aitask-specific settings
6. Create `seed/codex_instructions.seed.md` with system prompt template
7. Create `.codex/config.toml` for the aitasks repo
8. Create `.codex/instructions.md` for the aitasks repo

## Verification

1. Verify all 14 `.agents/skills/<name>/SKILL.md` files exist
2. Verify each wrapper's name matches the corresponding Claude skill
3. Verify each wrapper's description matches the Claude skill
4. Verify argument documentation is correct for each skill
5. Verify `seed/codex_config.seed.toml` is valid TOML: `python3 -c "import tomllib; tomllib.load(open('seed/codex_config.seed.toml','rb'))"`
6. Verify `seed/codex_instructions.seed.md` exists and references CLAUDE.md
