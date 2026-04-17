# CLAUDE.md

This file provides guidance when working with code in this repository.

## Project Overview

**aitasks**  is a file-based task management framework for AI coding agents, primarily Claude Code. Tasks are markdown files with YAML frontmatter stored in git — no backend infrastructure required. The `ait` CLI dispatcher routes to shell scripts in `.aitask-scripts/`.


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
bash tests/test_resolve_tar_zst.sh
bash tests/test_t167_integration.sh
bash tests/test_global_shim.sh
bash tests/test_sed_compat.sh
bash tests/test_resolve_detected_agent.sh
bash tests/test_verified_update_flags.sh
bash tests/test_archive_scan.sh
bash tests/test_archive_utils.sh
bash tests/test_crew_setmode.sh
bash tests/test_archive_no_overbroad_add.sh
bash tests/test_plan_externalize.sh
```
No test runner — each file is self-contained with `assert_eq`/`assert_contains` helpers and prints PASS/FAIL summary.

### Linting
```bash
shellcheck .aitask-scripts/aitask_*.sh
```

### Website (Hugo/Docsy)
```bash
cd website && npm install && ./serve.sh    # Local dev server
hugo build --gc --minify                   # Production build (in website/)
```
Requires: Hugo extended (>=0.155.3), Go (>=1.23), Dart Sass, Node.js (18+).

## Architecture

### Core Flow
`ait` (bash dispatcher) → `.aitask-scripts/aitask_*.sh` (command scripts) → `.aitask-scripts/lib/task_utils.sh` + `terminal_compat.sh` (shared utilities)

All scripts `cd` to the repo root via `ait` before running. Directory variables default to: `TASK_DIR=aitasks`, `PLAN_DIR=aiplans`, `ARCHIVED_DIR=aitasks/archived`, `ARCHIVED_PLAN_DIR=aiplans/archived`.

### Key Directories
- `.aitask-scripts/` — Shell scripts implementing all CLI commands (~18 scripts + 2 lib files)
- `.aitask-scripts/board/aitask_board.py` — Python TUI board (Textual framework, ~2400 LOC)
- `aitasks/` — Active task files (`t<N>.md`, child tasks in `t<N>/t<N>_M_*.md`)
- `aitasks/archived/` — Completed tasks (may include `old.tar.zst` numbered bundles for space)
- `aitasks/metadata/` — Config: `task_types.txt`, `labels.txt`, `board_config.json`, `project_config.yaml`, `profiles/`
- `aiplans/` — Implementation plan files (`p<N>.md`)
- `aireviewguides/` — Code review guides organized by language subdirectory
- `.claude/skills/` — 21 Claude Code skill definitions (each a dir with `SKILL.md`)
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

### Folded Task Semantics
Folded tasks are **merged** into the primary task — not superseded or replaced. At fold time the folded content is incorporated into the primary task's description (see `## Merged from t<N>` headers). The folded file remains on disk only as a reference for post-implementation cleanup; it is deleted during archival. Always use "merged" / "incorporated" language in code, procedures, and docs — never "superseded" / "replaced".

### Adding a New Frontmatter Field
A new task frontmatter field must touch three layers, or the board silently drops it:

1. **Write path:** `aitask_create.sh` (batch flags + interactive flow + `create_task_file` serialization) and `aitask_update.sh` (mirroring add/remove flags).
2. **Fold machinery:** `aitask_fold_mark.sh` — union folded tasks' values into the primary if the field is a list. `aitask_fold_content.sh` only merges body text; frontmatter lists are lost unless `fold_mark` is extended.
3. **Board TUI:** `aitask_board.py` `TaskDetailScreen.compose()` renders per-field widgets keyed on field name. Add a `<FieldName>Field` class mirroring `DependsField` / `ChildrenField`, wire it into `compose()`, and have it shell out to `aitask_update.sh --batch ... --<flag>`.

When splitting a plan that introduces a new field, surface any missing layer as its own child task.

### Script Modes
Most scripts support both **interactive** (uses `fzf`) and **batch** (CLI flags for automation) modes. Example: `aitask_create.sh --batch --name "task" --priority high --commit`.

## Shell Conventions

- **Shebang:** Always use `#!/usr/bin/env bash`, never `#!/bin/bash`. macOS system bash is 3.2 which lacks features like `declare -A` and `${var^}`; `env bash` picks up the brew-installed bash 5.x from PATH.
- All scripts use `set -euo pipefail`
- Error helpers: `die()` (fatal), `warn()`, `info()` from `terminal_compat.sh`
- Guard against double-sourcing with `_AIT_*_LOADED` variables
- Platform detection: `detect_platform()` returns `github|gitlab|bitbucket` from git remote URL
- Task/plan resolution functions live in `task_utils.sh` (resolves task IDs to file paths, extracts frontmatter)
- **Platform-specific CLIs (gh/glab/bitbucket):** encapsulate in bash scripts that route to the correct backend via `detect_platform()`. `SKILL.md` must call a script subcommand, never `gh`, `glab`, or the Bitbucket API directly.
- **Archive format details (tar.gz/tar.zst/zstd):** encapsulate in bash scripts. `SKILL.md` must call a script subcommand — never raw archive tooling. Format migrations then happen in one place.
- **sed portability:** macOS ships BSD sed, not GNU sed. Use `sed_inplace()` from `terminal_compat.sh` instead of `sed -i`. Avoid GNU-only features (`\U`, `/pattern/a text`). See `aidocs/sed_macos_issues.md` for details.
- **grep portability:** macOS `grep` does not support `-P` (PCRE). Avoid `grep -oP`, `\K`, and lookahead/lookbehind `(?=...)`. Use `grep -o 'pattern' | sed 's/...//'` or `grep -oE` (extended regex) instead. See `aidocs/sed_macos_issues.md` for related portability notes.
- **wc -l portability:** macOS `wc -l` pads output with leading spaces (`"       1"` vs `"1"`). This is safe in arithmetic contexts (`-gt`, `-le`, `$(())`), but breaks exact string comparisons (`== "1"`). Strip with `| tr -d ' '` when comparing as strings. See `aidocs/sed_macos_issues.md` for details.
- **mktemp portability:** macOS BSD `mktemp` does not support `--suffix`. Use template patterns instead: `mktemp "${TMPDIR:-/tmp}/prefix_XXXXXX.ext"`. See `aidocs/sed_macos_issues.md` for details.
- **base64 portability:** macOS uses `base64 -D` for decoding, Linux uses `base64 -d`. The long form `--decode` is not portable across both. In skill files, document both flags. In scripts, use a conditional or avoid `base64` if possible.

## Commit Message Format
```
<type>: <description> (tNN)
```
Types match `issue_type` values: `bug`, `feature`, `chore`, `documentation`, `performance`, `refactor`, `style`, `test`. Also `ait` for framework-internal changes.

## Git Operations on Task/Plan Files

When committing changes to files in `aitasks/` or `aiplans/`, use `./ait git`
instead of plain `git`. This ensures correct branch targeting when task data
lives on a separate branch.
- `./ait git add aitasks/t42_foo.md`
- `./ait git commit -m "ait: Update task t42"`
- `./ait git push`

In legacy mode (no separate branch), `ait git` passes through to plain `git`.

## Debugging Conventions

When a command fails, debug **that exact command** — do not spend cycles reproducing the symptom by testing its components in isolation.

- First action: run the failing command under tracing (`bash -x`, `2>/tmp/log`, `tee`). Do not run a simplified version.
- For commands that take over the terminal (`exec tmux`, `exec $EDITOR`), wrap in a log-keeping shell so fd 2 stays redirected through the exec.
- When isolated components all pass but the composed command fails, the fault is in composition (env vars, shim state, PATH resolution, caller context). Stop re-testing components.
- When symptoms vary by invocation path (`./ait ide` vs `ait ide`, direct vs wrapper), compare the paths systematically — the delta is usually the cause.

## Documentation Writing

User-facing docs (website, README-level content) describe the **current state only**.

- No "earlier versions of this page said…", "previously we recommended…", "this used to be wrong", "this corrects an earlier mistake".
- State correct behavior positively. Version history belongs in git and PR descriptions, not in doc bodies.
- Internal plan files (`aiplans/`) may still record deviations from earlier plans — the rule applies to user-facing content.

## UI & Dialog Conventions

Destructive-action confirmations (delete, archive, cascade) must make each affected item's fate explicit.

- Group affected items under labelled sections: `Will be ARCHIVED (moved to …)`, `Will be DELETED`, `Will be UPDATED`, `Blocking (must be handled first)`.
- Annotate each row with useful status metadata (e.g., `[Ready]`, `[Implementing]`, `[parent — status: …]`).
- Include every section even when an action is refused, so the user sees what *would* have happened.
- Centralize the formatting in one helper so every dialog variant stays consistent.
- Never collapse multi-fate operations into a single opaque "N files affected" list.

Applies to Textual `ModalScreen` dialogs in `ait board`, AskUserQuestion prompts, bash confirm prompts — anywhere an action touches more than one item or more than one fate.

## TUI (Textual) Conventions

- **`n` is the create-task key** across every aitasks TUI (board, codebrowser, minimonitor, monitor, brainstorm, TUI switcher modal). Do not default to `c` or other alternatives when adding a create-task binding to a new TUI. Related TUIs may bind `n` to "next" (monitor, logview, diffviewer) — those are read-oriented TUIs without a create-task action, so the conflict is only notional.
- **Priority bindings + `App.query_one` gotcha:** when an `App` and a pushed `Screen` define a binding with the same action name and `priority=True`, the App-level action runs first. If its "am I in the right screen?" guard uses `self.query_one(...)`, the query walks the entire screen stack and will match widgets from underlying screens — so the guard succeeds for the wrong screen, consumes the key, and the active screen's own binding never fires. Scope guards to `self.screen.query_one(...)`. On guard-miss, raise `textual.actions.SkipAction` so the next priority binding (the active screen's own action) gets a chance. Alternative: use distinct action names per screen.

## Model Attribution

When running the Model Self-Detection sub-procedure in Claude Code, scan the conversation for **mid-session `/model` switches before** falling back to the initial system message.

- The system message's "exact model ID" is frozen at session start. A `/model` command does **not** update it, so using the system-message value after a switch records the wrong model.
- Search for the most recent `<local-command-stdout>Set model to …</local-command-stdout>` line. If found, map the human-readable name (e.g., "Opus 4.7 (1M context)") to the cli_id via `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode --cli-id <id>`.
- Only fall back to the system-message model ID if no mid-session switch is visible.
- If the human name is ambiguous (e.g., "Opus 4.7" without the `1M` suffix), ask the user which variant.

## QA Workflow

After committing implementation changes, run `/aitask-qa <task_id>` for test coverage analysis and test plan generation. The embedded Step 8b "test-followup-task" procedure is deprecated — `/aitask-qa` supersedes it and provides better separation from the workflow. Profile keys `qa_mode` and `qa_run_tests` control automation level.

## WORKING ON SKILLS / CUSTOM COMMANDS

The **source of truth** for skills and custom commands is the Claude Code implementation
as found in `.claude/skills/`.

The framework also supports opencode, codex cli and gemini cli, which have their own slightly modified versions
of skills and commands:
- **Gemini CLI**: `.gemini/commands/` and `.gemini/skills/`
- **Codex CLI**: `.agents/skills/` and `.codex/prompts/`
- **OpenCode**: `.opencode/skills/<name>/SKILL.md` and `.opencode/commands/`

> **Read the sections below only if you need to implement or update skills/commands for a specific tool.**

### Skill / Workflow Authoring Conventions

- **Agent-specific steps live in their own procedure file.** If a workflow step applies only to one code agent (e.g., Claude Code's internal plan file externalization), put the procedure — commands, output parsing, error handling — in its own `.claude/skills/task-workflow/<name>.md`. Reference it from `SKILL.md` / `planning.md` with a short conditional wrapper: "If running in Claude Code, execute the \<Procedure Name\> (see `<name>.md`). Other agents skip this step because \<reason\>." Never inline agent-specific steps into shared files — when the tree is ported to `.opencode/`, `.gemini/`, `.agents/`, the porter either copies irrelevant steps or silently drops them.
- **Use guard variables, not prose.** When a procedure could be triggered from multiple code paths, add an explicit guard boolean (e.g., `feedback_collected`) to the SKILL.md context-variables table and check it at procedure entry. LLMs reading the instructions may not reliably distinguish imperative "execute this" from descriptive "this happens" — a variable is a programmatic guarantee regardless of interpretation.

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

## Project-Specific Notes

- **`diffviewer` TUI is transitional.** It will be integrated into the `brainstorm` TUI later; omit it from user-facing website docs and lists-of-TUIs (document: board, monitor, minimonitor, codebrowser, settings, brainstorm). Keep `diffviewer` in `KNOWN_TUIS` inside `.aitask-scripts/lib/tui_switcher.py` — it must remain switchable via `j` until the brainstorm integration lands.
