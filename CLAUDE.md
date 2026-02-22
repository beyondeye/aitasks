# CLAUDE.md/AGENTS.md

This file provides guidance when working with code in this repository.

## Project Overview

**aitasks**  is a file-based task management framework for AI coding agents, primarily Claude Code. Tasks are markdown files with YAML frontmatter stored in git — no backend infrastructure required. The `ait` CLI dispatcher routes to shell scripts in `aiscripts/`.


### Testing
Tests are bash scripts run individually:
```bash
bash tests/test_claim_id.sh
bash tests/test_detect_env.sh
bash tests/test_draft_finalize.sh
bash tests/test_task_lock.sh
bash tests/test_terminal_compat.sh
bash tests/test_zip_old.sh
bash tests/test_setup_git.sh
bash tests/test_resolve_tar_gz.sh
bash tests/test_t167_integration.sh
bash tests/test_global_shim.sh
```
No test runner — each file is self-contained with `assert_eq`/`assert_contains` helpers and prints PASS/FAIL summary.

### Linting
```bash
shellcheck aiscripts/aitask_*.sh
```

### Website (Hugo/Docsy)
```bash
cd website && npm install && ./serve.sh    # Local dev server
hugo build --gc --minify                   # Production build (in website/)
```
Requires: Hugo extended (>=0.155.3), Go (>=1.23), Dart Sass, Node.js (18+).

## Architecture

### Core Flow
`ait` (bash dispatcher) → `aiscripts/aitask_*.sh` (command scripts) → `aiscripts/lib/task_utils.sh` + `terminal_compat.sh` (shared utilities)

All scripts `cd` to the repo root via `ait` before running. Directory variables default to: `TASK_DIR=aitasks`, `PLAN_DIR=aiplans`, `ARCHIVED_DIR=aitasks/archived`, `ARCHIVED_PLAN_DIR=aiplans/archived`.

### Key Directories
- `aiscripts/` — Shell scripts implementing all CLI commands (~18 scripts + 2 lib files)
- `aiscripts/board/aitask_board.py` — Python TUI board (Textual framework, ~2400 LOC)
- `aitasks/` — Active task files (`t<N>.md`, child tasks in `t<N>/t<N>_M_*.md`)
- `aitasks/archived/` — Completed tasks (may include `old.tar.gz` for space)
- `aitasks/metadata/` — Config: `task_types.txt`, `labels.txt`, `board_config.json`, `profiles/`
- `aiplans/` — Implementation plan files (`p<N>.md`)
- `aireviewguides/` — Code review guides organized by language subdirectory
- `.claude/skills/` — 13 Claude Code skill definitions (each a dir with `SKILL.md`)
- `website/` — Hugo/Docsy documentation site
- `seed/` — Template files for `ait setup` bootstrapping into new projects

### Task File Format
Task files use YAML frontmatter with these fields:
```yaml
---
priority: high|medium|low
effort: high|medium|low
depends: [1, 3]
issue_type: bug|feature|chore|documentation|performance|refactor|style|test
status: Ready|Editing|Implementing|Postponed|Done|Folded
labels: [ui, backend]
assigned_to: email
boardcol: now|next|backlog
boardidx: 50
folded_tasks: [2, 4]     # merged child tasks
folded_into: 1            # parent task ID if folded
issue: https://...        # linked issue tracker URL
---
```

### Task Hierarchy
Parent: `aitasks/t130_feature_name.md` → Children: `aitasks/t130/t130_1_subtask.md`, `t130_2_subtask.md`. Children auto-depend on siblings.

### Script Modes
Most scripts support both **interactive** (uses `fzf`) and **batch** (CLI flags for automation) modes. Example: `aitask_create.sh --batch --name "task" --priority high --commit`.

## Shell Conventions

- All scripts use `set -euo pipefail`
- Error helpers: `die()` (fatal), `warn()`, `info()` from `terminal_compat.sh`
- Guard against double-sourcing with `_AIT_*_LOADED` variables
- Platform detection: `detect_platform()` returns `github|gitlab|bitbucket` from git remote URL
- Task/plan resolution functions live in `task_utils.sh` (resolves task IDs to file paths, extracts frontmatter)

## Commit Message Format
```
<type>: <description> (tNN)
```
Types match `issue_type` values: `bug`, `feature`, `chore`, `documentation`, `performance`, `refactor`, `style`, `test`. Also `ait` for framework-internal changes.


## WORKING ON SKILLS / CUSTOM COMMANDS

The **source of truth** for skills and custom commands is the Claude Code implementation
as found in `.claude/skills/`.

The framework also supports opencode, codex cli and gemini cli, which have their own slightly modified versions
of skills and commands:
- **Gemini CLI**: `.gemini/commands/` and `.gemini/skills/`
- **Codex CLI**: `.agents/skills/` and `.codex/prompts/`
- **OpenCode**: `.opencode/skills/<name>/SKILL.md` and `.opencode/commands/`

> **Read the sections below only if you need to implement or update skills/commands for a specific tool.**

### Claude Code (source of truth)
- Skills: `.claude/skills/<name>/SKILL.md`
- Settings: `.claude/settings.local.json`

### Gemini CLI
- Custom commands: `.gemini/commands/`
- Skills: `.gemini/skills/`
- Adapt from the Claude Code version; Gemini CLI uses a similar markdown-based skill format.

### Codex CLI
- Skills: `.agents/skills/`
- Prompts: `.codex/prompts/`
- Adapt from the Claude Code version; Codex CLI uses its own prompt/agent structure.

### OpenCode
- Skills: `.opencode/skills/<name>/SKILL.md`
- Commands: `.opencode/commands/`
- Adapt from the Claude Code version; OpenCode follows a similar `SKILL.md` convention.

**IMPORTANT**: Skill/custom command changes and development, if not specified otherwise, should be done in the Claude Code version first. When such changes take place, suggest to the user to create separate aitasks to update the corresponding skills/commands in their codex cli / gemini cli / opencode versions.
