# CLAUDE.md

This file is the always-loaded context for working on this repository.
Specialist rules live in `aidocs/` and are read on demand — pointers appear
inline below.

## Project Overview

**aitasks** is a file-based task management framework for AI coding agents.
Tasks are markdown files with YAML frontmatter stored in git — no backend
infrastructure required. The `ait` CLI dispatcher routes to shell scripts in
`.aitask-scripts/`.

### Testing
Tests are bash scripts run individually:
```bash
bash tests/test_claim_id.sh
```
No test runner — each file is self-contained with `assert_eq`/`assert_contains`
helpers and prints PASS/FAIL summary.

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
`ait` (bash dispatcher) → `.aitask-scripts/aitask_*.sh` (command scripts) →
`.aitask-scripts/lib/task_utils.sh` + `terminal_compat.sh` (shared utilities)

All scripts `cd` to the repo root via `ait` before running. Directory variables
default to: `TASK_DIR=aitasks`, `PLAN_DIR=aiplans`,
`ARCHIVED_DIR=aitasks/archived`, `ARCHIVED_PLAN_DIR=aiplans/archived`.

### Key Directories
- `.aitask-scripts/` — Shell scripts implementing all CLI commands
- `.aitask-scripts/board/aitask_board.py` — Python TUI board (Textual)
- `aitasks/` — Active task files (`t<N>.md`, child tasks in `t<N>/t<N>_M_*.md`)
- `aitasks/archived/` — Completed tasks (may include `old.tar.zst` bundles)
- `aitasks/metadata/` — Config: `task_types.txt`, `labels.txt`,
  `board_config.json`, `project_config.yaml`, `profiles/`
- `aiplans/` — Implementation plan files (`p<N>.md`)
- `aireviewguides/` — Code review guides organized by language subdirectory
- `.claude/skills/` — Claude Code skill definitions (each a dir with `SKILL.md`)
- `website/` — Hugo/Docsy documentation site
- `seed/` — Template files for `ait setup` bootstrapping into new projects

### Task File Format
```yaml
---
priority: high|medium|low
effort: high|medium|low
depends: [1, 3]
issue_type: bug|feature|enhancement|chore|documentation|performance|refactor|style|test
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
Parent: `aitasks/t130_feature_name.md` → Children: `aitasks/t130/t130_1_subtask.md`,
`t130_2_subtask.md`. Children auto-depend on siblings.

### Folded Task Semantics
Folded tasks are **merged** into the primary task — not superseded or
replaced. At fold time the folded content is incorporated into the primary
task's description (see `## Merged from t<N>` headers). The folded file
remains on disk only as a reference for post-implementation cleanup; it is
deleted during archival. Always use "merged" / "incorporated" language in
code, procedures, and docs — never "superseded" / "replaced".

### Script Modes
Most scripts support both **interactive** (uses `fzf`) and **batch** (CLI
flags for automation) modes. Example: `aitask_create.sh --batch --name "task"
--priority high --commit`.

> **Read `aidocs/aitasks_extension_points.md`** when adding a new
> frontmatter field, adding a new helper script under `.aitask-scripts/`,
> editing `aitask_setup.sh` or anything in the install flow, fixing an
> OS-specific bug, or touching framework PATH / binary shimming.

## Shell Conventions

- **Shebang:** Always `#!/usr/bin/env bash`, never `#!/bin/bash`. macOS system
  bash is 3.2; `env bash` picks up brew-installed bash 5.x from PATH.
- All scripts use `set -euo pipefail`.
- Error helpers: `die()` (fatal), `warn()`, `info()` from `terminal_compat.sh`.
- Guard against double-sourcing with `_AIT_*_LOADED` variables.
- Platform detection: `detect_platform()` returns `github|gitlab|bitbucket`
  from git remote URL.
- Task/plan resolution functions live in `task_utils.sh`.
- **Platform-specific CLIs (gh/glab/bitbucket):** encapsulate in bash scripts
  that route via `detect_platform()`. `SKILL.md` must call a script
  subcommand, never `gh`, `glab`, or the Bitbucket API directly.
- **Archive format details (tar.gz/tar.zst/zstd):** encapsulate in bash
  scripts. `SKILL.md` must call a script subcommand — never raw archive
  tooling. Format migrations then happen in one place.
- Use `sed_inplace()` from `terminal_compat.sh` — never `sed -i`.
- **System libs added to `./ait`'s source-on-startup chain must also be added
  to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same PR.**
  43 tests scaffold a fake `.aitask-scripts/lib/` via that helper; a missing
  entry crashes every one of them with `No such file or directory` the next
  time `./ait` (or a helper that learns to source the new lib) is invoked
  from the fake repo. Current baseline: `aitask_path.sh`, `terminal_compat.sh`,
  `python_resolve.sh`.

> **macOS portability quirks** (BSD sed vs GNU sed, `grep -P` unavailable,
> `wc -l` padding, `mktemp --suffix`, `base64 -D` vs `-d`): see
> `aidocs/sed_macos_issues.md`.

## CLI Conventions

**`ait setup` vs `ait upgrade` — pick the verb by intent, not by habit.** In
user-facing messages (`aitask_setup.sh`, docs, error hints):
- **"Reinstall / repair / restore / populate-missing"** → `ait setup`.
- **"Move to a newer version"** → `ait upgrade`.

When editing any framework message that mentions reinstalling, repairing, or
restoring missing files, verify the verb semantically. Keep `ait upgrade` only
for update-available hints or "move to v0.X.Y" flows.

## Commit Message Format

```
<type>: <description> (tNN)
```

Types match `issue_type` values: `bug`, `feature`, `enhancement`, `chore`,
`documentation`, `performance`, `refactor`, `style`, `test`. Also `ait` for
framework-internal changes.

## Git Operations on Task/Plan Files

When committing changes to files in `aitasks/` or `aiplans/`, use `./ait git`
instead of plain `git`. This ensures correct branch targeting when task data
lives on a separate branch.
- `./ait git add aitasks/t42_foo.md`
- `./ait git commit -m "ait: Update task t42"`
- `./ait git push`

In legacy mode (no separate branch), `ait git` passes through to plain `git`.

## Documentation Writing

User-facing docs (website, README-level content) describe the **current state
only**.

- No "earlier versions of this page said…", "previously we recommended…",
  "this used to be wrong", "this corrects an earlier mistake".
- State correct behavior positively. Version history belongs in git and PR
  descriptions, not in doc bodies.
- Internal plan files (`aiplans/`) may still record deviations from earlier
  plans — the rule applies to user-facing content.
- **"Delete X, eventually integrate into Y" means redirect cross-refs now,
  defer content migration.** Read Y first. If Y already covers the essential
  content, "integrate" collapses to updating cross-references from X to Y —
  do not wholesale-migrate X's prose into Y in the same task. Defer the
  richer integration as a follow-up task and surface cross-reference
  redirects explicitly in Post-Review Changes (they break silently if
  missed).

> **Read `aidocs/documentation_conventions.md`** when writing user-facing doc
> prose — especially manual-verification auto-mode descriptions (say
> "autonomous", not "auto-execution") or any passage that names the supported
> coding agents (genericize the list).

## Model Attribution

When running the Model Self-Detection sub-procedure in Claude Code, scan the
conversation for **mid-session `/model` switches before** falling back to the
initial system message.

- The system message's "exact model ID" is frozen at session start. A
  `/model` command does **not** update it, so using the system-message value
  after a switch records the wrong model.
- Search for the most recent `<local-command-stdout>Set model to
  …</local-command-stdout>` line. If found, map the human-readable name (e.g.,
  "Opus 4.7 (1M context)") to the cli_id via
  `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode
  --cli-id <id>`.
- Only fall back to the system-message model ID if no mid-session switch is
  visible.
- **When you do fall back to the system-message exact ID, pass it verbatim.**
  The 1M-context Opus variant's exact ID carries a bracketed `[1m]` suffix
  (e.g. `claude-opus-4-7[1m]`); stripping it resolves to the non-1M entry
  (`claudecode/opus4_7` instead of `claudecode/opus4_7_1m`) and mis-attributes
  the model. See `aidocs/model_reference_locations.md`.
- If the human name is ambiguous (e.g., "Opus 4.7" without the `1M` suffix),
  ask the user which variant.

## Working on Skills / Custom Commands

The **source of truth** for skills and custom commands is the Claude Code
implementation in `.claude/skills/`.

The framework also supports Codex CLI and OpenCode:
- **Codex CLI:** `.agents/skills/` (shared with future `agy` agent — see
  "Skill templating and per-profile dispatch" below); `.codex/` holds
  only `config.toml` and `instructions.md`
- **OpenCode:** `.opencode/skills/<name>/SKILL.md` and `.opencode/commands/`

Adapt from the Claude Code version when porting; each agent uses a similar
markdown-based skill format.

Run `./.aitask-scripts/aitask_skill_verify.sh` before committing any `.j2`
template or stub-surface change. After editing any `.md.j2` or closure
procedure, regenerate the affected goldens in the same commit — see
"Regenerate goldens after any `.md.j2` or closure edit" in
`aidocs/skill_authoring_conventions.md`.

**IMPORTANT:** Skill/custom command changes, if not specified otherwise,
should be done in the Claude Code version first. When such changes take
place, suggest separate aitasks to update the corresponding skills/commands
in the other supported coding agents.

> **Read `aidocs/skill_authoring_conventions.md`** when editing anything
> under `.claude/skills/`, `.agents/skills/`, `.opencode/skills/`, or
> `.opencode/commands/` — or when designing a new skill, procedure, or
> per-profile variant.
>
> **Read `aidocs/stub-skill-pattern.md`** when authoring or modifying a
> profile-aware skill's stub surface or `.md.j2` authoring template.
>
> **Read `aidocs/adding_a_new_codeagent.md`** when adding a new code agent
> to the framework (skill discovery / rendering, shared-root semantics,
> rerender driver, headless variants, goldens regeneration).

### Skill templating and per-profile dispatch

Profile-aware skills are authored as `.claude/skills/<skill>/SKILL.md.j2` (Claude
is the single source of truth). Each agent has a thin profile-agnostic **stub**
at its discovery surface. At invocation time the stub resolves the active
profile (default OR `--profile <name>` override on `ARGUMENTS`), runs
`./.aitask-scripts/aitask_skill_render.sh`, then Read-and-follows the rendered
variant. Rendered files are autogenerated; never edit them by hand.

Per-agent stub surface and rendered-variant location:

| Agent | Stub location | Rendered variant location |
|-------|---------------|---------------------------|
| Claude | `.claude/skills/<skill>/SKILL.md` | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| Codex | `.agents/skills/<skill>/SKILL.md` | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
| OpenCode | `.opencode/commands/<skill>.md` | `.opencode/skills/<skill>-<profile>-/SKILL.md` |

Rendered dir names end with a hyphen so each agent root has a single `*-/`
`.gitignore` glob. Authoring dir names MUST NOT end with `-`. Shared roots
(currently `.agents/skills/` for codex; +`agy` later) carry an extra
`-<agent>-` segment to prevent collisions — the predicate is declared in
`agent_skill_root` / `agent_shared_skills_root` in
`.aitask-scripts/lib/agent_skills_paths.sh` (Python mirror:
`AGENT_SHARED_SKILLS_ROOT` in `lib/skill_template.py`).

Invocation paths:
- From inside an agent session: `/aitask-pick --profile fast 42`.
- From the shell: `ait skillrun pick --profile fast 42`
  (honors `--profile-override <yaml|->` for ad-hoc YAML merges, `--dry-run`
  to preview the launch command).

Jinja conditional patterns inside `.md.j2` and closure procedures:
- `{% if profile.<key> %}` — branch on profile keys
  (`default_email`, `create_worktree`, `plan_preference`, …).
- `{% if agent == "<name>" %}` — gate per-agent content
  (currently `aitask-wrap` Step 1b; remaining call-sites tracked in
  `aidocs/agent_runtime_guards_audit.md`).
- `{% raw %} … {% endraw %}` for literal `{{` / `{%` that must not be
  evaluated.

`./.aitask-scripts/aitask_skill_verify.sh` (referenced above) enforces stub
markers, dep-closure render cleanliness, and headless prerender freshness.
After **any** `.md.j2` or closure-`.md` edit, regenerate the affected goldens
under `tests/golden/skills/<skill>/` and `tests/golden/procs/<scope>/` in the
same commit — see "Regenerate goldens after any `.md.j2` or closure edit"
in `aidocs/skill_authoring_conventions.md`.

> **Read `aidocs/agent_runtime_guards_audit.md`** when introducing a new
> `{% if agent %}` gate or moving an existing "If running in Claude Code"
> runtime guard into a Jinja gate — the audit catalogs the cross-skill
> cascade impact (Test 1b agent-invariance) before any such move.

## TUI Development

> **Read `aidocs/tui_conventions.md`** when editing any Textual TUI under
> `.aitask-scripts/` (board, monitor, minimonitor, codebrowser, brainstorm,
> settings, syncer, stats-tui, diffviewer, TUI switcher) or its launcher
> `.sh`, when adding keybindings to an existing TUI, or when spawning tmux
> panes / windows from framework code.
>
> **Read `aidocs/python_tui_performance.md`** when re-evaluating a TUI's
> Python runtime (CPython vs PyPy) choice. The framework currently routes
> only `ait board` through the PyPy fast path; the document records the
> empirical evidence for that scoping decision and the criteria for
> reconsidering other TUIs.
>
> **Read `aidocs/monitor_idle_and_prompt_detection.md`** when `ait monitor`
> / `ait minimonitor` fails to flag an agent that is visibly waiting on
> user input, when adding a new code-agent CLI, or when changing how idle
> vs. "awaiting user input" is detected. The patterns live in
> `.aitask-scripts/monitor/prompt_patterns.py` and are edited in-place when
> a new agent's prompt wording shows up.

## Planning / Testing / Code Conventions

> **Read `aidocs/planning_conventions.md`** when writing or reviewing an
> implementation plan — especially before splitting a complex task into
> children, deferring follow-ups, or proposing edits to a list/config that
> appears in 3+ files. (These rules are a candidate for future promotion
> into the task-workflow planning procedure.)
>
> **Read `aidocs/testing_conventions.md`** when designing tests for a
> threading / asyncio migration or any other concurrency primitive.
>
> **Read `aidocs/code_conventions.md`** when adding a constant or dict that
> holds user-facing help text condensed from another canonical file
> (language-agnostic — bash, Python, etc.). Shell-specific portability
> quirks live in `aidocs/sed_macos_issues.md`; general shell style stays in
> the Shell Conventions section above.

## Reusable Helpers

**`aitask_explain_context.sh` is the canonical "source files → related plans
/ tasks" scanner.** For any requirement of the form "given a list of source
files, find the aitasks/aiplans that touched them and surface their plan
content as context", call directly:

```bash
./.aitask-scripts/aitask_explain_context.sh --max-plans N <file1> [file2...]
```

Outputs formatted markdown with historical plan content. Internally
orchestrates a cache at `.aitask-explain/codebrowser/` (shared with
codebrowser — don't write a parallel cache). Family:
`aitask_explain_context.sh` (orchestrator),
`aitask_explain_extract_raw_data.sh`, `aitask_explain_format_context.py`,
`aitask_explain_process_raw_data.py`, `aitask_explain_runs.sh`,
`aitask_explain_cleanup.sh`.

Do NOT cite or reinvent codebrowser's Python internals (`history_data.py` /
`explain_manager.py`) for new features — those are codebrowser-internal; the
bash helpers are the supported public interface. Only build new tooling if
the helper genuinely cannot fit (different output shape); prefer extending
the existing helper (add a flag) over forking the scan logic.

## Project-Specific Notes

- **`diffviewer` TUI is transitional.** It will be integrated into the
  `brainstorm` TUI later; omit it from user-facing website docs and
  lists-of-TUIs (document: board, monitor, minimonitor, codebrowser,
  settings, brainstorm). Keep `diffviewer` in `KNOWN_TUIS` inside
  `.aitask-scripts/lib/tui_switcher.py` — it must remain switchable via `j`
  until the brainstorm integration lands.
- **Manual verification.** Tasks with `issue_type: manual_verification`
  dispatch through a dedicated Pass/Fail/Skip/Defer loop in `/aitask-pick`
  (Step 3 Check 3 → `.claude/skills/task-workflow/manual-verification.md`).
  Aggregate-sibling tasks are offered during parent-task planning when ≥2
  children are created; single-task follow-ups are offered at Step 8c after
  "Commit changes". See `website/content/docs/workflows/manual-verification.md`
  for the end-to-end workflow.
- **Cross-repo coordination.** When a task / plan / commit needs to
  reach into a sibling aitasks project, reference it by logical name —
  never by sibling-directory path (`../aitasks/`). The `ait projects`
  subcommand (`list` / `add` / `resolve` / `exec`) and `ait create
  --batch --project <name>` resolve names against the per-user registry
  at `~/.config/aitasks/projects.yaml`. Cross-repo task IDs use the
  `aitasks#835_3` notation (preferred without `t`; accepted with `t`).
  See `aidocs/cross_repo_references.md` for the registry schema,
  resolver semantics, and notation regex.

## Mobile Companion

`ait applink` is the TUI that bridges a local `ait` workspace to a mobile
companion app (developed in the sibling repo `../aitasks_mobile`, Kotlin
Multiplatform) over a paired, QR-bootstrapped LAN WebSocket. The wire
protocol, pairing flow, connection state machine, and permission profiles
are documented under `aidocs/applink/` — see
`aidocs/applink/protocol.md` and `aidocs/applink/permissions.md`. The
canonical command-verb inventory and `ait monitor` port design live in
`aidocs/applink/monitor_port_design.md` (authored separately).
