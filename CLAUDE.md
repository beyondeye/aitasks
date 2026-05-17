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
| `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"`, `decision = "allow"`, `priority = 100` |
| `seed/claude_settings.local.json` | mirror of `.claude/settings.local.json` entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of runtime Gemini policy |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/<name>.sh *": "allow"` |

**Codex exception:** `.codex/config.toml` and `seed/codex_config.seed.toml` use a prompt/forbidden-only permission model — no `allow` decision exists. Codex does not need a whitelist entry; it prompts by default.

When splitting a plan that introduces one or more new helper scripts, surface this 5-touchpoint checklist as an explicit deliverable per helper.

#### Test the full install flow for setup helpers

When adding or modifying helpers in `.aitask-scripts/aitask_setup.sh` that touch `aitasks/metadata/project_config.yaml` (or any file expected to be in place by prior install steps), the test harness must simulate the full `install.sh → ait setup` flow in a scratch dir, not just feed a hand-crafted seed to the helper in isolation.

**Why:** During t624 the agent tested setup helpers by dropping a copy of `seed/project_config.yaml` into a scratch dir and calling the helpers directly. They passed. But `install.sh` deletes `seed/` at the end of install and never had an `install_seed_project_config()` function — so in a fresh user install, `aitasks/metadata/project_config.yaml` was missing, the helpers printed "No project_config.yaml found" and returned. Unit tests passed, integration failed. Follow-up fix was t628.

**How to apply:**
- For any setup-flow change, run `bash install.sh --dir /tmp/scratchXY` (or equivalent) into a fresh scratch dir, THEN run the new helper/flow, THEN grep/cat the expected output file to confirm. Do not stop at helper-level unit tests.
- When adding a helper that reads from `aitasks/metadata/X`, grep `install.sh` for `install_seed_X` or similar — if there isn't one, the helper will fail on fresh installs even if it passes isolated tests.
- `install.sh`'s deletion of `seed/` means any runtime script that still reads from `$project_dir/seed/...` will silently fail in a fresh install. Those paths only work in the source repo where `seed/` is preserved.

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
- **No global PATH override for framework-internal binaries.** Do NOT append framework-internal directories (e.g., `~/.aitask/bin`) to the user's interactive shell rc (`~/.zshrc` / `~/.bashrc` / `~/.profile`). That globally overrides system tools (like `python3`) for every program the user runs, not just aitasks subprocesses, and risks silent breakage of the user's unrelated workflows. Instead, ship a sourced lib (e.g., `.aitask-scripts/lib/aitask_path.sh`) that exports `PATH="$HOME/.aitask/bin:$PATH"` idempotently, and source it from the `ait` dispatcher and from every `.aitask-scripts/aitask_*.sh` that may invoke the framework binary (covers skill-direct calls bypassing the dispatcher). The exception is `~/.local/bin` — `ensure_path_in_profile()` correctly manages only that directory because the global `ait` entry-point shim is meant to be user-invocable.
- **Cross-platform audit for platform-specific bugs.** When fixing a bug on one OS branch (e.g., a Linux-only `_install_pypy_linux` failure), audit the parallel function on the other platform (`_install_pypy_macos`) for the same bug class before finalizing the task scope: hardcoded literals where a constant exists, missing layout symmetry, same single-source-of-truth violations. If the symmetric path has same-family issues, fold them into the same task (a single coherent fix is better than two staggered ones); name a manual-verification follow-up for the platform you can't test from your dev box. Skip this only when the bug is genuinely OS-specific (kernel API quirk, sandbox restriction) with no analog on the other platform.

## CLI Conventions

- **`ait setup` vs `ait upgrade` — pick the verb by intent, not by habit.** In `ait` framework user-facing messages (`aitask_setup.sh`, docs, error hints), distinguish carefully:
  - **"Reinstall / repair / restore / populate-missing"** → say `ait setup`.
  - **"Move to a newer version"** → say `ait upgrade`.

  **How to apply:** When editing any framework message that mentions reinstalling, repairing, or restoring missing files, verify the verb semantically. Use `ait setup`. Keep `ait upgrade` only for update-available hints or "move to v0.X.Y" flows.

## Commit Message Format
```
<type>: <description> (tNN)
```
Types match `issue_type` values: `bug`, `feature`, `enhancement`, `chore`, `documentation`, `performance`, `refactor`, `style`, `test`. Also `ait` for framework-internal changes.

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

- **New long-running Textual TUI launchers call `require_ait_python_fast`, not `require_ait_python`.** When introducing a new launcher .sh under `.aitask-scripts/` for a long-running Textual TUI (board-class, multi-screen, interactive), use `PYTHON="$(require_ait_python_fast)"` at the top of the script. Short-lived CLIs (one-shot helpers, `ait create`, status reporters) keep `require_ait_python` to avoid the ~150-300 ms PyPy warmup penalty.

  **Why:** `require_ait_python_fast` auto-routes to PyPy when the user has run `ait setup --with-pypy` (and falls through to CPython otherwise — zero behavior change for non-PyPy users). Forgetting to use the fast variant means new TUIs silently miss out on the PyPy speedup forever, until someone notices and ports them. This drift was the motivating finding of t718_2 (where `aitask_syncer.sh` had been added on `require_ait_python` after the parent task t718 was planned).

  **How to apply:** Default any new long-running Textual TUI launcher to `require_ait_python_fast`. Codebrowser is an exception (empirically verified by t718_6: PyPy ~17% slower at steady state, ~2× slower cold-start — see `aidocs/python_tui_performance.md`). Monitor / minimonitor are exceptions (empirically verified by t718_5; PyPy loses on both the legacy fork+exec fallback and the post-t719_2 control-mode path). Diffviewer is also an exception until its brainstorm integration lands. Stats TUI is also an exception (it depends on `plotext`, which is installed only in the CPython venv; its browse-and-exit interaction profile does not justify mirroring plotext into the PyPy venv). Do NOT retroactively switch existing launchers without an aitask covering the change.

- **`AIT_USE_PYPY` precedence (runtime override).** When PyPy has been installed via `ait setup --with-pypy`, the four fast-path TUIs (board, settings, brainstorm, syncer) auto-route through `~/.aitask/pypy_venv`. The `AIT_USE_PYPY` env var overrides per invocation:

  | `AIT_USE_PYPY` | PyPy installed? | Result |
  |----------------|-----------------|--------|
  | `1`            | Yes             | PyPy (forced) |
  | `1`            | No              | error: install with `ait setup --with-pypy` |
  | `0`            | (any)           | CPython (override) |
  | unset          | Yes             | PyPy (default once installed) |
  | unset          | No              | CPython (current behavior preserved) |

  Codebrowser / monitor / minimonitor / stats-tui stay on CPython regardless of `AIT_USE_PYPY` — codebrowser empirically loses on PyPy (t718_6); monitor/minimonitor empirically lose on PyPy (t718_5); stats-tui depends on `plotext` (CPython-only). Full analysis: `aidocs/python_tui_performance.md`.

- **`n` is the create-task key** across every aitasks TUI (board, codebrowser, minimonitor, monitor, brainstorm, TUI switcher modal). Do not default to `c` or other alternatives when adding a create-task binding to a new TUI. Related TUIs may bind `n` to "next" (monitor, logview, diffviewer) — those are read-oriented TUIs without a create-task action, so the conflict is only notional.
- **Priority bindings + `App.query_one` gotcha:** when an `App` and a pushed `Screen` define a binding with the same action name and `priority=True`, the App-level action runs first. If its "am I in the right screen?" guard uses `self.query_one(...)`, the query walks the entire screen stack and will match widgets from underlying screens — so the guard succeeds for the wrong screen, consumes the key, and the active screen's own binding never fires. Scope guards to `self.screen.query_one(...)`. On guard-miss, raise `textual.actions.SkipAction` so the next priority binding (the active screen's own action) gets a chance. Alternative: use distinct action names per screen.
- **No auto-commit/push of project-level config from runtime TUIs.** Runtime `save()` paths in config modules must write only the user-level (`*.local.json`, gitignored) layer. Project-level (`*.json`, tracked) files are read-only at runtime unless there is an explicit user-initiated "export / publish" action. Never call `git commit` or `./ait git push` from inside a TUI event handler for a config change. First-time ship of a project-level file is a one-time implementation commit; runtime saves after that must not touch it.
- **Contextual-footer ordering: keep uppercase sibling adjacent to its lowercase primary.** When a pane's footer includes both a lowercase primary action (e.g., `d` = toggle detail) and its uppercase sibling (e.g., `D` = expand detail), keep them adjacent in the footer — `d D …`, not `d c D …`. The uppercase-to-tail demotion rule applies only to uppercase keys whose primary is NOT itself in the pane's suffix. Example: in `detail_pane` the suffix should be `["d", "D", "c", "H"]` — `D` adjacent to `d`; `H` (whose `h` primary lives in `PRIMARY_ORDER`) at the tail.
- **Pane-internal cycling uses `←` / `→`** (not `[` / `]` brackets). For pane-level item cycling inside a Textual TUI (e.g., cycling operations in the stats verified-rankings pane), use ←/→ arrow keys.

  **Why:** Arrows are more discoverable and ergonomic for left/right motion than bracket keys.

  **How to apply:** When designing a pane that needs prev/next cycling within a shared right-hand content area:
  - Use App-level bindings for `"left"` / `"right"` so the sidebar `ListView` (which only consumes ↑/↓) doesn't interfere.
  - Ensure inner widgets don't consume left/right — e.g., set `DataTable(cursor_type="row")` so the table's default cell-cursor bindings are inactive.
  - Guard the action handler on the currently-visible pane id so arrows are a no-op when viewing other panes.
  - Keep `show=False` on the bindings to avoid cluttering the footer; surface the hint in the pane's own header text instead.
- **TUI switcher shortcuts act on the *selected* session, not the attached one.** In the multi-session TUI switcher, shortcut keys (`b` board, `m` monitor, `c` codebrowser, `s` settings, `t` stats, `r` brainstorm, `g` git, `x` explore, `n` new task) act on the selected (Left/Right-browsed) session — identical to pressing Enter on that TUI's row in that session. Cross-session teleport (`switch-client`) fires automatically when the selected session differs from the attached one.

  **Why:** Earlier task-description language ("shortcuts stay on current/attached session") was reversed by user direction during planning; the implemented plan in `aiplans/p634/p634_3_two_level_tui_switcher.md` follows the user preference, not the original task description.

  **How to apply:** Future work on `.aitask-scripts/lib/tui_switcher.py` and related keybinding docs must preserve shortcut-on-selected semantics. `self._session` in a shortcut handler is the *selected/operating* session (mutated by Left/Right) — that read is correct. The separate `self._attached_session` attribute exists only to decide whether to issue `switch-client`. Do not "fix" the asymmetry by routing shortcuts through the attached session or by adding a current-running-names set. If reading the archived task file `t634/t634_3` later, treat its "Step 4 — Shortcut keys stay on current session" as superseded.
- **Single tmux session per project.** The aitasks framework is designed to use exactly ONE tmux session per project. All TUIs, agents, monitor, minimonitor, brainstorm, and codebrowser of a given project live inside that one session (configured by `tmux.default_session` in `aitasks/metadata/project_config.yaml`).

  **Why:** Users routinely run multiple aitasks projects side-by-side (e.g., `aitasks` and `aitasks_mob`) in different terminals. Each project must stay fully isolated in its own tmux session so TUIs and singletons (lazygit, brainstorm, monitor) do not cross-contaminate between projects.

  **How to apply:**
  - Any tmux lookup that scans across sessions (e.g., `find_window_by_name` iterating `get_tmux_sessions()`) is architecturally incorrect and must be scoped to the current project's session.
  - Any `tmux -t <session>` target must use exact match (`-t =<session>`) — tmux's default prefix match means a session named `aitasks` silently resolves to `aitasks_mob` if that's the only running match, crossing project boundaries.
  - When reviewing multi-project behavior, assume the user may have several session names that share prefixes.
- **Companion pane auto-despawn — kill the companion only, never the window.** When spawning a companion pane (e.g., `minimonitor`) alongside a primary command in a new tmux window (git TUI / `ait create` / explore agents / similar), the companion must auto-despawn when the primary exits — but only the companion pane, and only if no other sibling pane is still using the window.

  **Why:** Two failure modes to avoid: (1) blanket-killing the window (`tmux kill-window`) tears down user-created panes (shells, notes); (2) a global "kill companion on any pane-exit" approach despawns prematurely when one of several primary-like siblings exits. The companion should persist until *every* primary-like pane is gone.

  **How to apply:**
  1. Capture the primary pane id (`tmux new-window -P -F "#{pane_id}"`) and companion pane id (same flags on `split-window`) at spawn time.
  2. Attach a pane-scoped `pane-died` hook to the primary (`tmux set-hook -p -t <primary> pane-died …`) with `remain-on-exit on` so the hook fires.
  3. The hook calls a cleanup script that lists panes in the window, excluding primary + companion. If zero other panes → kill both. If ≥1 → kill only the primary and leave the companion alive.
  4. Do NOT use `tmux kill-window`.
  5. Do NOT use a global "kill companion on any pane-exit" approach.

  Canonical helper lives at `.aitask-scripts/aitask_companion_cleanup.sh` (shell script, called via `tmux run-shell`, not from a code-agent skill — no whitelisting touchpoints).

- **TUI footer must surface every operation on the affected tab/screen — existing AND new.** When a plan adds keybindings to a Textual TUI tab/screen, the same plan must also flip pre-existing `show=False` bindings and `on_key`-only handlers (no `Binding` declared) on that tab/screen to footer-visible `Binding` declarations. Partial coverage is worse than none because it misleads users into thinking the visible set is complete.

  **How to apply:** When planning a TUI change that touches keybindings:
  - Audit every existing binding on the affected widget/screen. Convert `on_key`-only handlers to proper `Binding` declarations with `action_*` methods.
  - Default new bindings to `show=True` with a short, user-friendly label.
  - For pre-existing `show=False` bindings, propose flipping them to `show=True` (or justify keeping them hidden — e.g., internal navigation that would clutter the footer) in the same plan.
  - Arrow-key bindings can be footer-visible if they are part of the primary interaction model (e.g., 2D graph navigation); don't reflexively hide them just because Textual examples often do.
  - Surface this as an explicit deliverable in the child task that introduces the new operations.

- **Tmux-stress tasks: implement outside the user's main aitasks tmux.** For tasks whose tests/verification destructively manipulate tmux (`kill -KILL` of `tmux -C attach` children, `tmux kill-session`, `tmux kill-server`, `tmux pause-pane`, etc. — typical surface: `.aitask-scripts/monitor/`, `tmux_control.py`, `agent_launch_utils.py`, resilience test suites), the implementation must NOT run from inside the user's active aitasks tmux session. Even with per-case `TMUX_TMPDIR` sockets, a wrong test or an embedded helper bug can blast the user's real session and take all running code agents down.

  **How to apply:**
  - Flag the risk before drafting the verification section. Recommend the user pick the task from a shell that is **not** inside their main aitasks tmux. The plan can still be written from inside; only implement + verify need the outside-tmux precaution.
  - If the user is mid-pick when the risk surfaces, offer "abort + revert to Ready, keep the plan" as the default action — do not push through implementation.
  - If only a subset of test cases need a sandboxed tmux, split them into a separate runner script the user invokes from a clean shell.

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
- **Gemini CLI**: `.gemini/commands/` and `.agents/skills/` (skills consolidated with Codex)
- **Codex CLI**: `.agents/skills/` (`.codex/` holds only `config.toml` and `instructions.md` — no per-skill prompts directory)
- **OpenCode**: `.opencode/skills/<name>/SKILL.md` and `.opencode/commands/`

> **Read the sections below only if you need to implement or update skills/commands for a specific tool.**

### Verifying `.j2` Templates Before Commit

When you add or modify a `.j2` authoring template (`.claude/skills/<skill>/SKILL.md.j2`) or any per-agent stub surface (`.claude/skills/<skill>/SKILL.md`, `.agents/skills/<skill>/SKILL.md`, `.gemini/commands/<skill>.toml`, `.opencode/commands/<skill>.md`), run `ait skill verify` before committing:

```bash
./ait skill verify
```

This renders every `.j2` against `default.yaml` for all 4 supported agents (claude, codex, gemini, opencode) and asserts each stub surface contains the canonical markers from `.claude/skills/task-workflow/stub-skill-pattern.md` (resolver call, render call, trailing-hyphen Read path). The script exits non-zero on any render error or stub-pattern violation; address every failure before committing.

If no `.j2` templates exist yet, the command prints `ait skill verify: no .j2 templates found — nothing to verify.` and exits 0. That is the expected state until the first authoring template lands.

`ait skill verify` writes nothing to disk (it renders through `lib/skill_template.py` to stdout). It is safe to run anytime.

### Skill / Workflow Authoring Conventions

- **Extract new procedures to their own file.** Any new procedure added to an aitasks skill (task-workflow or sibling) goes in its own file (`.claude/skills/<skill>/<name>.md`); the calling `SKILL.md` / `planning.md` carries only a thin "Execute the **\<Procedure Name\>** (see `<name>.md`) with: \<context vars\>" reference. No inlined procedure bodies; no "either inline or extract" alternatives in plans. The agent-specific case (e.g., Claude Code's internal plan-file externalization) is one instance of this rule — wrap the reference in a conditional like "If running in Claude Code, execute …. Other agents skip this step because \<reason\>." Inlined bodies in shared files duplicate when the procedure fires from multiple call-sites, drift silently when the tree is ported to `.opencode/` / `.gemini/` / `.agents/`, and create conflict surface when multiple aitasks touch the same SKILL.md region.
- **Execution-profile keys vs. guard variables — pick the right lever.** Profile keys (e.g., `qa_mode: ask|never`, `post_plan_action`) are for letting users opt in/out of a procedure; they are the right fix when a step feels overreaching. Guard variables (e.g., `feedback_collected`) are set-once-consume-once flags that prevent DOUBLE execution when the same procedure can be invoked twice via different control-flow paths — they do NOT force a single execution, so they can't be used to "remind agents to fire a prompt." Rule of thumb: if the concern is "agents might forget to fire X", restructure control flow (extract X to its own file, reference explicitly from SKILL.md, make it a numbered step) and add a profile key for opt-out. If the concern is "X might fire twice via re-entry", add a guard variable to the SKILL.md context-variables table and check it at procedure entry — LLMs reading the instructions may not reliably distinguish imperative "execute this" from descriptive "this happens", so a variable is a programmatic guarantee regardless of interpretation.
- **Context-variable pattern over template substitution engines.** When templates need per-instance values like `CREW_ID` / `AGENT_NAME` (or analogous variables), do NOT introduce a template-substitution engine that interpolates the values at template-write time (e.g., a sed/envsubst pass added to a helper). Instead, follow the "context-variable" pattern already used by `task-workflow`: declare the variables once in a known file the agent reads (e.g., `_instructions.md`, or a shared `_context_variables.md` include), reference them as `${VARNAME}` placeholders throughout the template, and let the agent substitute them at read time.

  **Why:** The pattern is already in use and working for execution profiles in `task-workflow` — `task_file`, `task_id`, `active_profile`, etc. are declared in the SKILL.md "Context Requirements" table and referenced throughout downstream procedures. Agents bind them from working memory rather than from text mangled at write time. Adding a new substitution engine duplicates the binding mechanism, introduces a second code path that can drift, and creates a fragile transformation step in the script pipeline.

  **How to apply:** When a template needs per-instance values:
  - First, check whether the agent already has the values available via a known context source (e.g., its `_instructions.md` written by an existing helper). If so, just reference the variables in the template and tell the agent where the literal values live.
  - If a shared declaration is needed across multiple templates, add a small include file (e.g., `_context_variables.md`) and inline it via the existing `<!-- include: ... -->` mechanism — do NOT add a new substitution pipeline.
  - Reserve write-time variable interpolation for cases where the agent genuinely cannot read the literal values from any context file (rare).

- **SKILL.md files are re-read during execution — never overwrite an in-use one.** Skill definitions on disk (`.claude/skills/<name>/SKILL.md`, `.agents/skills/<name>/SKILL.md`, `.gemini/skills/<name>/SKILL.md`, `.opencode/skills/<name>/SKILL.md`) are read MULTIPLE times by the agent during a skill's execution, not just once at slash-command expansion. Any design that mutates an in-use `SKILL.md` mid-session produces torn reads and inconsistent behavior.

  **How to apply:**
  - Use per-profile subdirectories (each with its own stable `SKILL.md`) so different (skill, profile) combinations live in different files. For dynamic profile-driven content, render ONCE atomically (mv from tempfile) into a per-profile path, then dispatch via a profile-suffixed slash command (e.g. `/aitask-pick-fast`). The committed no-suffix `/aitask-pick` becomes a thin stub that resolves the active profile and dispatches.
  - Skills must also be invokable from INSIDE a live agent session (typing `/aitask-pick 42` in Claude), where no external wrapper can intercept. Stub-dispatch from the skill itself is the canonical solution: the stub runs `ait skill render …` (bash), then invokes `/skill-<profile>`.
  - Atomic mv from tempfile is essential for any render that lands in a skill discovery path.

- **Use recognizable name-suffix conventions for generated artifact dirs, not per-variant gitignore globs.** When a feature generates rendered artifact directories alongside authoring ones (e.g., per-profile rendered SKILL.md variants), encode "generated" into the directory NAME with a single recognizable suffix/prefix marker so the gitignore is one glob per agent root. Convention for aitasks framework rendered SKILL.md dirs: **trailing hyphen** (e.g., `aitask-pick-fast-/`); gitignore is `.claude/skills/*-/` (and same for `.agents/skills/`, `.gemini/skills/`, `.opencode/skills/`). Per-variant globs (`*-fast/`, `*-default/`, …) require maintenance every time a new variant lands; the suffix convention does not. Authoring dir names must NOT end with the marker — verify at design time.

- **Do not route skill invocation through `claude -p "<inlined prompt>"`.** `claude -p` is billed at a higher per-token rate than slash-command invocations against an existing session. Inlining a rendered SKILL.md (often 200–400 lines) into the prompt every invocation multiplies that cost. The wrapper's job is to render → atomically place the rendered file at the agent's discovery path → exec the agent with the natural slash command (`claude '/skill-name <args>'` or invocation inside an existing session). Never pipe rendered SKILL.md content via `-p`. The constraint applies to all four agents (Claude, Codex, Gemini, OpenCode); the rate-difference rationale is documented specifically for Claude.

- **Post-implementation follow-up offers: cross-step state lives in the plan file, not in context variables.** When a Step 8X-style follow-up procedure (8b upstream-defect, 8c manual-verification, future siblings) needs cross-step state — e.g., "did diagnosis surface an upstream defect?" — record it in a dedicated bullet of the plan file's `## Final Implementation Notes` section, and have the follow-up procedure read from that subsection. Use `None` (verbatim) as the positive-assertion sentinel when nothing was found. Do NOT add new entries to SKILL.md's "Context Requirements" table for this kind of state. Plan-file persistence survives context resumes, stays auditable in archived plans, and keeps the recorded finding visible even if the user declines the follow-up offer.

### Claude Code (source of truth)
- Skills: `.claude/skills/<name>/SKILL.md`
- Settings: `.claude/settings.local.json`

### Gemini CLI
- Custom commands: `.gemini/commands/`
- Skills: `.gemini/skills/`
- Adapt from the Claude Code version; Gemini CLI uses a similar markdown-based skill format.

### Codex CLI
- Skills: `.agents/skills/` (shared with Gemini CLI — unified Codex/Gemini wrapper layout)
- Config: `.codex/config.toml` and `.codex/instructions.md` (no per-skill prompts directory)
- Adapt from the Claude Code version; Codex CLI uses its own prompt/agent structure.

### OpenCode
- Skills: `.opencode/skills/<name>/SKILL.md`
- Commands: `.opencode/commands/`
- Adapt from the Claude Code version; OpenCode follows a similar `SKILL.md` convention.

**IMPORTANT**: Skill/custom command changes and development, if not specified otherwise, should be done in the Claude Code version first. When such changes take place, suggest to the user to create separate aitasks to update the corresponding skills/commands in their codex cli / gemini cli / opencode versions.

## Planning Conventions

- **Refactor duplicates before adding to them.** When an implementation plan would edit the same list, set, or configuration in three or more separate files (e.g., adding one value to `DEFAULT_TUI_NAMES`, `_DEFAULT_TUI_NAMES`, `KNOWN_TUIS`, and `project_config.yaml`), propose a single-source-of-truth extraction before accepting the duplicated edit. Duplicated state is the mechanism that produces drift bugs (stale config masking new code defaults). Also evaluate replace-vs-merge semantics for config overrides over code defaults — merge/additive semantics prevent future drift when framework features are added.

- **Plan split: in-scope sibling children, not deferred follow-ups.** When splitting a complex parent task into children, default to all phases as siblings (in scope), plus a trailing retrospective-evaluation child that depends on the others. Do NOT mark later phases as "out-of-scope follow-up tasks" when the parent has scoped them. When committing to a design choice under partial information ("we'll know if this is the right shape once we benchmark"), proactively propose the retrospective-evaluation child — it documents outcomes and files standalone follow-ups only if the collected data justifies them. The retrospective child is bounded by the parent (a *child*, not a deferred top-level task), even though its outputs may include new top-level tasks. Applies to both architectural refactors and exploratory work whose right-next-step depends on what the first step shows.

- **Dead code goes into the sibling refactor task — never a vague follow-up.** When a child-task plan would leave a function / global / branch / file unreachable after the change lands, do NOT write "leave it for a future cleanup" or "follow-up child" without naming the actual sibling. Identify the right sibling task (whose explicit scope is `cleanup / refactor / migrate / remove`) and drop a one-line note into that sibling's task file under `## Notes for sibling tasks` (include file path + line range, so the future implementer doesn't re-trace). If no sibling fits, surface a NEW task creation as part of the current plan. Do not bury cleanup intent in a `# DEPRECATED` comment alone — the load-bearing signal is the task-file note that surfaces in `aitask_ls.sh`-driven workflows.

- **Gate plans on in-flight related tasks instead of forking ahead.** When a planned task **mirrors, clones, or extends** rendering / data presented by another task that is currently `Implementing` or `Editing`, do NOT propose implementing the new task in parallel. Add a "Sequencing — wait for tN to land" section to the plan, mark the new task `depends: [N]` (or `Postponed`), externalize and commit the plan now (so the design isn't lost), but exit via the "Approve and stop here" Step 6 checkpoint. Forking ahead produces diverging UI / data — the new task ships an extension that doesn't include the in-flight task's new fields. During planning, scan `aitasks/t<id>_*.md` for `status: Implementing` and check for meaningful overlap (mirrors / clones / extends, not just file proximity).

- **No fallback-read workarounds for sync/desync root causes.** For local-vs-remote desync symptoms, do NOT extend resolver helpers like `resolve_task_file` / `resolve_plan_file` with `git show <remote_ref>:...` fallback tiers. Such tiers hide the desync, bloat resolver chains, and silently mask stale local state. The right fix is to make desync **visible and resolvable** — best-effort `warn` at script entry points (telling the user "you are out of sync"), and integration with the dedicated syncer TUI + monitor / minimonitor / switcher surfaces. Workarounds that read from `origin` behind the user's back are not acceptable as "deeper fixes."

- **Audit-only tasks with zero findings produce audit-only plans — not speculative regression tests.** When a follow-up audit task ("grep the codebase for the same class of bug") finds zero additional occurrences beyond the single known case, do NOT propose a regression-prevention test, AST scanner, or lint rule as the durable deliverable. The audit itself is the deliverable: document method + findings + "no code changes." A one-off bug with a known mechanism is not evidence of an ongoing pattern. If a second occurrence ever appears, reconsider then — note this trigger in "Out of scope", don't pre-build the infrastructure. (Aligned with the system-prompt rule "Don't add features, refactor, or introduce abstractions beyond what the task requires.")

## Testing Conventions

- **Threading / asyncio migrations require thorough automated coverage — smoke + manual verification is not enough.** When a plan introduces a background thread, dedicated asyncio loop, `run_coroutine_threadsafe` bridge, or any other concurrency primitive, the test plan must enumerate concrete cases across each axis below. Threading bugs hide in race windows that manual smoke cannot reach; skipping any axis is a planning gap, not a "stretch."

  Walk this checklist explicitly in the plan body before exiting plan mode:
  1. **Lifecycle:** start idempotency, start-after-stop, stop idempotency, stop with pending work.
  2. **Concurrency:** N concurrent callers from multiple threads — bump N to 50+ to flush latent ordering bugs.
  3. **Mixed contexts:** sync caller invoked from inside a running asyncio loop on a different thread (the load-bearing test that proves the architecture solves the deadlock the migration was meant to address).
  4. **Failure recovery:** transport failure (e.g., server killed externally), then next request returns a dead-client sentinel cleanly without raising.
  5. **Resource boundaries:** binary not on PATH / config missing — start fails cleanly, fallback engages, no thread leaks.
  6. **Resource cleanup:** after stop, assert thread joined within timeout AND `threading.enumerate()` no longer lists the worker.
  7. **Behavior parity:** for every operation with a new code path, run new vs old and assert identical results (exact rc; exact stdout when rc==0). Document the contract explicitly when error-path stdout diverges (e.g., control-mode `%error` body vs subprocess stderr) so future maintainers don't tighten the assertion incorrectly.

  If a planned case is flaky on timing (e.g., sub-ms timeout assertions on a fast IPC), DROP the case rather than weakening it with sleeps / retries — note the dropped case in Final Implementation Notes and rely on adjacent cases that exercise the same semantics deterministically.

## Code Conventions

- **Source-trace comments for help text condensed from other files.** When a constant or dict holds user-facing help/summary text **condensed** from another canonical file (agent prompt templates, JSON schemas, external docs), include source-code comments at the data site naming the canonical origin (file path + relevant section/heading) for each entry. Archived plans and tasks are not surfaced when a future contributor opens the source file; the "where did this description come from?" answer must live in the code so the next person editing the help text can verify and re-derive it without spelunking through git history or `aitasks/`.

  Example:
  ```python
  # Source: .aitask-scripts/brainstorm/templates/explorer.md
  # I/O contract from "## Input" + "## Output" sections.
  "explore": { ... }
  ```

  If the dict/constant as a whole derives from a single canonical file or directory, add a top-of-block comment naming that location plus per-entry comments naming the section backing each entry. Apply only when the help/summary is a condensation of authoritative content elsewhere — not for inline help written from scratch.

## Reusable Helpers

- **`aitask_explain_context.sh` is the canonical "source files → related plans / tasks" scanner.** For any requirement of the form "given a list of source files, find the aitasks/aiplans that touched them and surface their plan content as context", call the t369 helper family directly:

  ```bash
  ./.aitask-scripts/aitask_explain_context.sh --max-plans N <file1> [file2...]
  ```

  Outputs formatted markdown with historical plan content. Internally orchestrates a cache at `.aitask-explain/codebrowser/` (shared with codebrowser — don't write a parallel cache). Family members built in t369: `aitask_explain_context.sh` (orchestrator), `aitask_explain_extract_raw_data.sh`, `aitask_explain_format_context.py`, `aitask_explain_process_raw_data.py`, `aitask_explain_runs.sh`, `aitask_explain_cleanup.sh`.

  Do NOT cite or reinvent codebrowser's Python internals (`history_data.py` / `explain_manager.py`) for new features — those are codebrowser-internal; the bash helpers are the supported public interface. Only build new tooling if the helper genuinely cannot fit (different output shape); prefer extending the existing helper (add a flag) over forking the scan logic.

## Project-Specific Notes

- **`diffviewer` TUI is transitional.** It will be integrated into the `brainstorm` TUI later; omit it from user-facing website docs and lists-of-TUIs (document: board, monitor, minimonitor, codebrowser, settings, brainstorm). Keep `diffviewer` in `KNOWN_TUIS` inside `.aitask-scripts/lib/tui_switcher.py` — it must remain switchable via `j` until the brainstorm integration lands.
- **Manual verification.** Tasks with `issue_type: manual_verification` dispatch through a dedicated Pass/Fail/Skip/Defer loop in `/aitask-pick` (Step 3 Check 3 → `.claude/skills/task-workflow/manual-verification.md`). Aggregate-sibling tasks are offered during parent-task planning when ≥2 children are created; single-task follow-ups are offered at Step 8c after "Commit changes". See `website/content/docs/workflows/manual-verification.md` for the end-to-end workflow.
- **`monitor` / `minimonitor` stay on CPython — empirically verified.** PyPy is *strictly worse* for these two TUIs on both the legacy fork+exec fallback path (3-7× slower; more panes → worse) AND the production `tmux -C` control-mode path that `t719_2` already integrated (76-90% slower at 3 and 8 panes; ties around 15). Cold-start also regresses ~2× (159 ms → 325 ms). Measured by t718_5 (2026-05-17) under PyPy 7.3.21 / Python 3.11.15 vs CPython 3.14.4 on Linux. Root cause is not "fork+exec dominates" (t719_2 removed that — see `aidocs/python_tui_performance.md`); on the control-mode path it's PyPy's heavier per-coroutine + cross-thread `run_coroutine_threadsafe` overhead combined with too little user Python work per tick for JIT to amortize. Full tables and methodology: `aidocs/python_tui_performance.md`. Do not re-attempt the PyPy fast-path swap for these two launchers; only re-evaluate if t719_4 (pipe-pane push) lands and reshapes the per-tick work toward Python-side parsing.
- **`codebrowser` stays on CPython — empirically verified.** PyPy is ~17% *slower* on the Pilot workload at steady state (CPython 4067 ms median vs PyPy 4740 ms median over 8 reps after 5-rep warmup) and ~2× slower at cold-start (173 ms vs 341 ms, 5 reps each). Workload: open codebrowser on a 5200-LOC Python file via `--focus`, then 10× pagedown + 10× pageup + end + home. Measured by t718_6 (2026-05-17) under PyPy 7.3.21 / Python 3.11.15 vs CPython 3.14.4 on Linux. Root cause is plausibly that codebrowser's per-keystroke work is small, fragmented Rich/Textual render code dispatched through C-accelerated layers — too little hot Python work for JIT to amortize while paying its fixed per-frame overhead. By contrast, `board` *keeps* PyPy because its `refresh_board()` pass exercises heavy frontmatter parsing per workload iteration (13.6% faster on PyPy after warmup). Full tables and rationale: `aidocs/python_tui_performance.md`. Do not re-attempt the PyPy fast-path swap for codebrowser; only re-evaluate if the codebrowser hot path is reshaped toward heavy interpreted Python (e.g., live multi-file re-indexing) or a future PyPy release closes the C-extension call-site overhead gap.
