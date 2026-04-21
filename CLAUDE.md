# CLAUDE.md

This file provides guidance when working with code in this repository.

## Project Overview

**aitasks**  is a file-based task management framework for AI coding agents. Tasks are markdown files with YAML frontmatter stored in git — no backend infrastructure required. The `ait` CLI dispatcher routes to shell scripts in `.aitask-scripts/`.


### Testing
Tests are bash scripts run individually: for example
```bash
bash tests/test_claim_id.sh
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

### Adding a New Helper Script

Any new script under `.aitask-scripts/` invoked by a skill must be whitelisted for every code agent's permission system — **both runtime configs (this project) AND seed configs (new projects bootstrapped via `ait setup`)**. Missing any touchpoint causes users of the corresponding agent to be prompted on every invocation, which is a recurring friction source.

| Touchpoint | Entry shape |
|-----------|------------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<name>.sh:*)"` in `permissions.allow` |
| `.gemini/policies/aitasks-whitelist.toml` | `[[rules]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"` |
| `seed/claude_settings.local.json` | mirror of `.claude/settings.local.json` entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of runtime Gemini policy |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/<name>.sh *": "allow"` |

**Codex exception:** `.codex/config.toml` and `seed/codex_config.seed.toml` use a prompt/forbidden-only permission model — no `allow` decision exists. Codex does not need a whitelist entry; it prompts by default.

When splitting a plan that introduces one or more new helper scripts, surface this 5-touchpoint checklist as an explicit deliverable per helper.

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

## Documentation Writing

User-facing docs (website, README-level content) describe the **current state only**.

- No "earlier versions of this page said…", "previously we recommended…", "this used to be wrong", "this corrects an earlier mistake".
- State correct behavior positively. Version history belongs in git and PR descriptions, not in doc bodies.
- Internal plan files (`aiplans/`) may still record deviations from earlier plans — the rule applies to user-facing content.
- **"Delete X, eventually integrate into Y" means redirect cross-refs now, defer content migration.** Read Y first. If Y already covers the essential content, "integrate" collapses to updating cross-references from X to Y — do not wholesale-migrate X's prose into Y in the same task. Defer the richer integration as a follow-up task and surface cross-reference redirects explicitly in Post-Review Changes (they break silently if missed).

## TUI (Textual) Conventions

- **`n` is the create-task key** across every aitasks TUI (board, codebrowser, minimonitor, monitor, brainstorm, TUI switcher modal). Do not default to `c` or other alternatives when adding a create-task binding to a new TUI. Related TUIs may bind `n` to "next" (monitor, logview, diffviewer) — those are read-oriented TUIs without a create-task action, so the conflict is only notional.
- **Priority bindings + `App.query_one` gotcha:** when an `App` and a pushed `Screen` define a binding with the same action name and `priority=True`, the App-level action runs first. If its "am I in the right screen?" guard uses `self.query_one(...)`, the query walks the entire screen stack and will match widgets from underlying screens — so the guard succeeds for the wrong screen, consumes the key, and the active screen's own binding never fires. Scope guards to `self.screen.query_one(...)`. On guard-miss, raise `textual.actions.SkipAction` so the next priority binding (the active screen's own action) gets a chance. Alternative: use distinct action names per screen.
- **No auto-commit/push of project-level config from runtime TUIs.** Runtime `save()` paths in config modules must write only the user-level (`*.local.json`, gitignored) layer. Project-level (`*.json`, tracked) files are read-only at runtime unless there is an explicit user-initiated "export / publish" action. Never call `git commit` or `./ait git push` from inside a TUI event handler for a config change. First-time ship of a project-level file is a one-time implementation commit; runtime saves after that must not touch it.
- **Contextual-footer ordering: keep uppercase sibling adjacent to its lowercase primary.** When a pane's footer includes both a lowercase primary action (e.g., `d` = toggle detail) and its uppercase sibling (e.g., `D` = expand detail), keep them adjacent in the footer — `d D …`, not `d c D …`. The uppercase-to-tail demotion rule applies only to uppercase keys whose primary is NOT itself in the pane's suffix. Example: in `detail_pane` the suffix should be `["d", "D", "c", "H"]` — `D` adjacent to `d`; `H` (whose `h` primary lives in `PRIMARY_ORDER`) at the tail.

## Model Attribution

When running the Model Self-Detection sub-procedure in Claude Code, scan the conversation for **mid-session `/model` switches before** falling back to the initial system message.

- The system message's "exact model ID" is frozen at session start. A `/model` command does **not** update it, so using the system-message value after a switch records the wrong model.
- Search for the most recent `<local-command-stdout>Set model to …</local-command-stdout>` line. If found, map the human-readable name (e.g., "Opus 4.7 (1M context)") to the cli_id via `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode --cli-id <id>`.
- Only fall back to the system-message model ID if no mid-session switch is visible.
- If the human name is ambiguous (e.g., "Opus 4.7" without the `1M` suffix), ask the user which variant.

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
- **Execution-profile keys vs. guard variables — pick the right lever.** Profile keys (e.g., `qa_mode: ask|never`, `post_plan_action`) are for letting users opt in/out of a procedure; they are the right fix when a step feels overreaching. Guard variables (e.g., `feedback_collected`) are set-once-consume-once flags that prevent DOUBLE execution when the same procedure can be invoked twice via different control-flow paths — they do NOT force a single execution, so they can't be used to "remind agents to fire a prompt." Rule of thumb: if the concern is "agents might forget to fire X", restructure control flow (extract X to its own file, reference explicitly from SKILL.md, make it a numbered step) and add a profile key for opt-out. If the concern is "X might fire twice via re-entry", add a guard variable to the SKILL.md context-variables table and check it at procedure entry — LLMs reading the instructions may not reliably distinguish imperative "execute this" from descriptive "this happens", so a variable is a programmatic guarantee regardless of interpretation.

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

## Planning Conventions

- **Refactor duplicates before adding to them.** When an implementation plan would edit the same list, set, or configuration in three or more separate files (e.g., adding one value to `DEFAULT_TUI_NAMES`, `_DEFAULT_TUI_NAMES`, `KNOWN_TUIS`, and `project_config.yaml`), propose a single-source-of-truth extraction before accepting the duplicated edit. Duplicated state is the mechanism that produces drift bugs (stale config masking new code defaults). Also evaluate replace-vs-merge semantics for config overrides over code defaults — merge/additive semantics prevent future drift when framework features are added.

## Project-Specific Notes

- **`diffviewer` TUI is transitional.** It will be integrated into the `brainstorm` TUI later; omit it from user-facing website docs and lists-of-TUIs (document: board, monitor, minimonitor, codebrowser, settings, brainstorm). Keep `diffviewer` in `KNOWN_TUIS` inside `.aitask-scripts/lib/tui_switcher.py` — it must remain switchable via `j` until the brainstorm integration lands.
- **Manual verification.** Tasks with `issue_type: manual_verification` dispatch through a dedicated Pass/Fail/Skip/Defer loop in `/aitask-pick` (Step 3 Check 3 → `.claude/skills/task-workflow/manual-verification.md`). Aggregate-sibling tasks are offered during parent-task planning when ≥2 children are created; single-task follow-ups are offered at Step 8c after "Commit changes". See `website/content/docs/workflows/manual-verification.md` for the end-to-end workflow.
