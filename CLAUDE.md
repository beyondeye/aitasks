# CLAUDE.md

always-loaded context for working on this repository.
Specialist rules live in `aidocs/` and are read on demand — pointers appear
inline below.

## Project Overview

**aitasks** is a file-based task management framework for AI coding agents.
Tasks are markdown files with YAML frontmatter stored in git.
The `ait` CLI dispatcher routes to shell scripts in
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
anchor: 130               # topic-group key = root task id (absent ⇒ task is its own root)
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

> **Read `aidocs/framework/aitasks_extension_points.md`** when adding a new
> frontmatter field, adding a new helper script under `.aitask-scripts/`,
> editing `aitask_setup.sh` or anything in the install flow, fixing an
> OS-specific bug, or touching framework PATH / binary shimming.

> **Read `aidocs/framework/shell_conventions.md`** when writing or editing any
> shell script under `.aitask-scripts/` — shebang (`#!/usr/bin/env bash`),
> `set -euo pipefail`, error helpers, `sed_inplace()`, platform/archive CLI
> encapsulation, the source-on-startup ↔ test-scaffold rule, and the
> `claude -p` headless-mode caveat. macOS portability quirks (BSD vs GNU sed,
> `grep -P`, etc.) live in `aidocs/framework/sed_macos_issues.md`.

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

> **Read `aidocs/framework/documentation_conventions.md`** when writing user-facing
> doc prose — the current-state-only rule (no version history in doc bodies),
> the "delete X / integrate into Y means redirect cross-refs now" rule,
> manual-verification auto-mode descriptions (say "autonomous", not
> "auto-execution"), and genericizing any passage that names the supported
> coding agents.

## Working on Skills / Custom Commands

The **source of truth** for skills and custom commands is the Claude Code
implementation in `.claude/skills/`.

The framework also supports Codex CLI and OpenCode:
- **Codex CLI:** `.agents/skills/` (shared root with the future `agy` agent —
  see `aidocs/framework/skill_authoring_conventions.md`); `.codex/` holds
  only `config.toml` and `instructions.md`
- **OpenCode:** `.opencode/skills/<name>/SKILL.md` and `.opencode/commands/`

Adapt from the Claude Code version when porting; each agent uses a similar
markdown-based skill format.

Run `./.aitask-scripts/aitask_skill_verify.sh` before committing any `.j2`
template or stub-surface change. After editing any `.md.j2` or closure
procedure, regenerate the affected goldens in the same commit — see
"Regenerate goldens after any `.md.j2` or closure edit" in
`aidocs/framework/skill_authoring_conventions.md`.

**IMPORTANT:** Skill/custom command changes, if not specified otherwise,
should be done in the Claude Code version first. When such changes take
place, suggest separate aitasks to update the corresponding skills/commands
in the other supported coding agents.

> **Read `aidocs/framework/skill_authoring_conventions.md`** when editing anything
> under `.claude/skills/`, `.agents/skills/`, `.opencode/skills/`, or
> `.opencode/commands/` — or when designing a new skill, procedure, or
> per-profile variant.
>
> **Read `aidocs/framework/stub-skill-pattern.md`** when authoring or modifying a
> profile-aware skill's stub surface or `.md.j2` authoring template.
>
> **Read `aidocs/framework/adding_a_new_codeagent.md`** when adding a new code agent
> to the framework (skill discovery / rendering, shared-root semantics,
> rerender driver, headless variants, goldens regeneration).

> **Read `aidocs/framework/agent_runtime_guards_audit.md`** when introducing a new
> `{% if agent %}` gate or moving an existing "If running in Claude Code"
> runtime guard into a Jinja gate — the audit catalogs the cross-skill
> cascade impact (Test 1b agent-invariance) before any such move.

The per-profile dispatch model (stub + `.md.j2` pair, per-agent surface table,
rendered-variant naming, invocation paths, Jinja patterns, goldens) is
documented in full in `aidocs/framework/skill_authoring_conventions.md` and
`aidocs/framework/stub-skill-pattern.md` — read those when actually editing
skill files.

## TUI Development

> **Read `aidocs/framework/tui_conventions.md`** when editing any Textual TUI under
> `.aitask-scripts/` (board, monitor, minimonitor, codebrowser, brainstorm,
> settings, syncer, stats-tui, diffviewer, TUI switcher) or its launcher
> `.sh`, or when adding keybindings to an existing TUI. (For *spawning or
> commanding* tmux from framework code, see `tmux_gateway.md` below.)
>
> **Read `aidocs/framework/tmux_gateway.md`** when writing or editing any code
> (shell or Python) that spawns or commands `tmux` — panes, windows, sessions,
> sockets, capture / send-keys — anywhere under `.aitask-scripts/`, not only in
> TUIs. The two gateways (`lib/tmux_exec.py` / `lib/tmux_exec.sh`) are the only
> sanctioned raw-`tmux` call sites; `tests/test_no_raw_tmux.sh` enforces it.
>
> **Read `aidocs/framework/python_tui_performance.md`** when re-evaluating a TUI's
> Python runtime (CPython vs PyPy) choice. The framework currently routes
> only `ait board` through the PyPy fast path; the document records the
> empirical evidence for that scoping decision and the criteria for
> reconsidering other TUIs.
>
> **Read `aidocs/framework/monitor_idle_and_prompt_detection.md`** when `ait monitor`
> / `ait minimonitor` fails to flag an agent that is visibly waiting on
> user input, when adding a new code-agent CLI, or when changing how idle
> vs. "awaiting user input" is detected. The patterns live in
> `.aitask-scripts/monitor/prompt_patterns.py` and are edited in-place when
> a new agent's prompt wording shows up.
>
> **Read `aidocs/framework/shadow_agent.md`** when editing the `aitask-shadow`
> skill, its capture / context helpers (`aitask_shadow_capture.sh`,
> `aitask_shadow_context.sh`), the minimonitor `e` trigger, or any code that
> classifies or cleans up shadow panes. The shadow is an advisory-only companion
> agent (capture → context-fetch → skill) spawned beside a followed agent and
> bound to it via the `@aitask_shadow_target` pane option.

## Planning / Testing / Code Conventions

> **Read `aidocs/framework/planning_conventions.md`** when writing or reviewing an
> implementation plan — especially before splitting a complex task into
> children, deferring follow-ups, or proposing edits to a list/config that
> appears in 3+ files. (These rules are a candidate for future promotion
> into the task-workflow planning procedure.)
>
> **Read `aidocs/framework/testing_conventions.md`** when designing tests for a
> threading / asyncio migration or any other concurrency primitive.
>
> **Read `aidocs/framework/code_conventions.md`** when adding a constant or dict that
> holds user-facing help text condensed from another canonical file
> (language-agnostic — bash, Python, etc.). Shell-specific portability
> quirks live in `aidocs/framework/sed_macos_issues.md`; general shell style lives in
> `aidocs/framework/shell_conventions.md`.

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
- **Cross-repo coordination.** When a task / plan / commit needs to
  reach into a sibling aitasks project, reference it by logical name —
  never by sibling-directory path (`../aitasks/`). The `ait projects`
  subcommand (`list` / `add` / `resolve` / `exec`) and `ait create
  --batch --project <name>` resolve names against the per-user registry
  at `~/.config/aitasks/projects.yaml`. Cross-repo task IDs use the
  `aitasks#835_3` notation (preferred without `t`; accepted with `t`).
  See `aidocs/framework/cross_repo_references.md` for the registry schema,
  resolver semantics, and notation regex.

## Mobile Companion

`ait applink` is the TUI that bridges a local `ait` workspace to a mobile
companion app (developed in the sibling repo `../aitasks_mobile`, Kotlin
Multiplatform) over a paired, QR-bootstrapped LAN WebSocket. The wire
protocol, pairing flow, connection state machine, and permission profiles
are documented under `aidocs/applink/` — see
`aidocs/applink/protocol.md` and `aidocs/applink/permissions.md`. The security
posture (TLS, token/bearer model, at-rest permissions, input validation, DoS
limits, audit logging) lives in `aidocs/applink/security.md`.
`aidocs/applink/wish_ssh_evaluation.md` evaluates SSH-based serving
(charmbracelet/wish) as a complementary terminal-client / hosted-deployment
access path alongside the native-mobile transport.
