---
Task: t130_1_codex_skill_wrappers.md
Parent Task: aitasks/t130_codecli_support.md
Sibling Tasks: aitasks/t130/t130_2_codex_setup_install.md, aitasks/t130/t130_3_codex_docs_update.md
Worktree: n/a (working on current branch)
Branch: main
Base branch: main
---

# Plan: Create Codex CLI Skill Wrappers (t130_1)

## Overview

Create 14 Codex CLI wrapper SKILL.md files in `.agents/skills/`, plus seed config and instructions files. Each wrapper is a thin file (~70 lines) that references the authoritative Claude Code skill and provides a Codex-specific tool mapping.

## Step 1: Create wrapper SKILL.md files

For each of the 14 user-invocable skills, create `.agents/skills/<name>/SKILL.md`.

### Wrapper template

```markdown
---
name: <skill-name>
description: <exact description from Claude Code skill's frontmatter>
---

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/<skill-name>/SKILL.md`**

Read that file and follow its complete workflow. The instructions below
explain how to adapt Claude Code tool references for Codex CLI.

## Arguments

<skill-specific argument documentation>

## Tool Mapping (Claude Code → Codex CLI)

When the source skill references Claude Code tools, use these Codex CLI equivalents:

| Claude Code Tool | Codex CLI Equivalent | Notes |
|---|---|---|
| `AskUserQuestion` | `functions.request_user_input` | Max 3 questions per call, max 3 options per question. Only works in Suggest mode. |
| `Bash(command)` | `functions.exec_command(command)` | Direct equivalent |
| `Read(file)` | `functions.exec_command("cat <file>")` | Use cat for file reading |
| `Write(file, content)` | `functions.apply_patch(...)` | Use Add File patch for new files |
| `Edit(file, ...)` | `functions.apply_patch(...)` | Use Update File patch for edits |
| `Glob(pattern)` | `functions.exec_command("find . -name '<pattern>'")` | Use find for file discovery |
| `Grep(pattern)` | `functions.exec_command("grep -rn '<pattern>' .")` | Use grep/rg for content search |
| `WebFetch(url)` | `web.run` with `open` | Web content fetching |
| `WebSearch(query)` | `web.run` with `search_query` | Web search |
| `EnterPlanMode` | _(not available)_ | Plan inline within the conversation |
| `ExitPlanMode` | _(not available)_ | Plan inline within the conversation |
| `Agent(...)` | _(not available)_ | Execute the sub-steps directly |
| `Skill(name)` | Read the referenced SKILL.md file directly | No sub-skill invocation mechanism |

## Codex CLI Adaptations

### AskUserQuestion Limits

Codex CLI's `request_user_input` supports max 3 options per question (Claude
allows 4) and max 3 questions per call (Claude allows 4). When the source
skill presents 4 options:

1. Combine the two least critical options into one if semantically possible
2. Or split into two sequential prompts
3. Or drop the least essential option

`request_user_input` only works in **Suggest mode**. If running in a mode
where user input is not available, use execution profiles or reasonable defaults.

### Plan Mode

Codex CLI has no separate `EnterPlanMode`/`ExitPlanMode`. When the source
skill references plan mode, plan inline: describe your approach as part of
the conversation output before executing.

### Sub-Skill References

When the source skill says "read and follow `.claude/skills/<name>/SKILL.md`",
read that file directly and follow its instructions. There is no sub-agent
or sub-skill invocation mechanism.

### Agent String

When recording `implemented_with` in task metadata, identify as
`codex/<model_name>`. Read `aitasks/metadata/models_codex.json` to find the
matching `name` for your model ID. Construct as `codex/<name>`.
```

### Skill-specific Arguments sections

| Skill | Arguments text |
|---|---|
| aitask-pick | `Accepts an optional task ID: $aitask-pick 16 (parent) or $aitask-pick 16_2 (child). Without argument, follows interactive selection.` |
| aitask-create | `No arguments. Follows interactive task creation workflow.` |
| aitask-explore | `No arguments. Follows interactive codebase exploration workflow.` |
| aitask-fold | `Accepts optional task IDs: $aitask-fold 106,108,112 or $aitask-fold 106 108. Without arguments, follows interactive discovery.` |
| aitask-review | `No arguments. Follows interactive code review workflow.` |
| aitask-stats | `Accepts optional flags: --days N, --verbose/-v, --csv [FILE]. Example: $aitask-stats --days 14 --verbose` |
| aitask-changelog | `No arguments. Analyzes commits and archived plans since last release.` |
| aitask-wrap | `No arguments. Analyzes uncommitted changes and wraps into a task.` |
| aitask-explain | `Accepts optional file/directory paths: $aitask-explain src/app.py or $aitask-explain src/lib/. Supports line ranges: path:start-end` |
| aitask-pr-import | `Accepts a PR URL or number: $aitask-pr-import 42 or $aitask-pr-import https://github.com/org/repo/pull/42` |
| aitask-reviewguide-classify | `Accepts an optional fuzzy pattern: $aitask-reviewguide-classify security. Without argument, runs batch mode.` |
| aitask-reviewguide-import | `Accepts an optional source: $aitask-reviewguide-import https://... or $aitask-reviewguide-import path/to/file.md. Without argument, prompts for source.` |
| aitask-reviewguide-merge | `Accepts 0-2 fuzzy patterns: $aitask-reviewguide-merge security error. Without arguments, runs batch discovery.` |
| aitask-refresh-code-models | `No arguments. Researches latest models via web and updates configuration.` |

### How to get exact descriptions

Read each `.claude/skills/<name>/SKILL.md` first 5 lines to extract the `description:` field from frontmatter.

## Step 2: Create seed/codex_config.seed.toml

```toml
# aitask framework — Codex CLI configuration seed
# This file is merged into .codex/config.toml during `ait setup`
# Only aitask-specific settings are included here

# Sandbox: allow writes to workspace + network access (needed for git push, web search)
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true

# Protective rules for destructive commands
# NOTE: Codex prefix_rules only support "prompt" or "forbidden" decisions
# There is no "allow" decision — commands cannot be pre-approved like in Claude Code

[[rules.prefix_rules]]
pattern = [{ token = "rm" }, { any_of = ["-rf", "-r", "-fr"] }]
decision = "prompt"
justification = "Recursive deletion requires approval"

[[rules.prefix_rules]]
pattern = [{ token = "git" }, { token = "push" }, { token = "--force" }]
decision = "prompt"
justification = "Force push requires approval"

[[rules.prefix_rules]]
pattern = [{ token = "git" }, { token = "reset" }, { token = "--hard" }]
decision = "prompt"
justification = "Hard reset requires approval"
```

## Step 3: Create seed/codex_instructions.seed.md

```markdown
# Codex CLI Instructions for aitasks

This project uses the **aitasks** framework for file-based task management.
See `CLAUDE.md` (or `AGENTS.md`) for full project documentation including
conventions, architecture, and commit message format.

## Skills

aitasks skills are available in `.agents/skills/`. Each skill is a wrapper
that references the authoritative Claude Code skill in `.claude/skills/`.
Read the wrapper for tool mapping guidance.

Invoke skills with `$skill-name` syntax (e.g., `$aitask-pick 16`).

## Key Conventions

- Tasks are markdown files in `aitasks/` with YAML frontmatter
- Plans go in `aiplans/`
- Use `./ait git` (not plain `git`) for task/plan file operations
- Commit format: `<type>: <description> (tNN)`
- Shell scripts use `#!/usr/bin/env bash` and `set -euo pipefail`
- Follow portability notes in CLAUDE.md (sed, grep, wc, mktemp, base64)

## Agent Identification

When recording `implemented_with` in task metadata, identify as
`codex/<model_name>` using `aitasks/metadata/models_codex.json` for
model name resolution.
```

## Step 4: Create .codex/config.toml (aitasks-project-specific)

Same content as seed plus aitasks-project-specific settings (if any). For now, the seed content is sufficient.

## Step 5: Create .codex/instructions.md (aitasks-project-specific)

Same as seed instructions, since this IS the aitasks project.

## Verification

- [ ] All 14 `.agents/skills/<name>/SKILL.md` files exist
- [ ] Each wrapper name/description matches Claude Code skill
- [ ] `seed/codex_config.seed.toml` is valid TOML
- [ ] `seed/codex_instructions.seed.md` references CLAUDE.md
- [ ] `.codex/config.toml` and `.codex/instructions.md` exist

## Step 9 Reference

After implementation, follow task-workflow Step 9 for archival and cleanup.
