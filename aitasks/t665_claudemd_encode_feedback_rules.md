---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [claudeskills, documentation, task_workflow]
created_at: 2026-04-27 11:40
updated_at: 2026-04-27 11:40
---

Encode 8 user-feedback rules and design invariants from auto-memory into
`CLAUDE.md` so future Claude Code sessions follow them without needing the
auto-memory files (which are being deleted by parent task t664).

## Origin

Spawned from t664 (review claude memories and transform into framework update
tasks). Each addition below corresponds to one auto-memory file; the original
memory text is reproduced so the rule, the *Why*, and the *How to apply* are
all preserved in the codebase.

## Additions to CLAUDE.md

### 1. TUI (Textual) Conventions section

Add four bullets:

#### a. Pane-internal cycling uses `←` / `→` (from memory: TUI pane-level navigation keys)

> For pane-level item cycling inside a Textual TUI (e.g. cycling operations in
> the stats verified-rankings pane), use ←/→ arrow keys, NOT `[` / `]` brackets.
>
> **Why:** User explicitly corrected the `[`/`]` proposal during planning of
> t603, asking for arrow keys instead. Arrows are more discoverable and
> ergonomic for left/right motion.
>
> **How to apply:** When designing a pane that needs prev/next cycling within a
> shared right-hand content area:
> - Use App-level bindings for `"left"` / `"right"` so the sidebar ListView
>   (which only consumes ↑/↓) doesn't interfere.
> - Ensure inner widgets don't consume left/right — e.g. set
>   `DataTable(cursor_type="row")` so the table's default cell-cursor bindings
>   are inactive.
> - Guard the action handler on the currently-visible pane id so arrows are a
>   no-op when viewing other panes.
> - Show `show=False` on the bindings to keep the footer uncluttered; surface
>   the hint in the pane's own header text instead.

#### b. Single tmux session per project (from memory: aitasks single tmux session per project invariant)

> The aitasks framework is designed to use exactly ONE tmux session per
> project. All TUIs, agents, monitor, minimonitor, brainstorm, and
> codebrowser of a given project live inside that one session (configured by
> `tmux.default_session` in `aitasks/metadata/project_config.yaml`).
>
> **Why:** Users routinely run multiple aitasks projects side-by-side
> (e.g., `aitasks` and `aitasks_mob`) in different terminals. Each project
> must stay fully isolated in its own tmux session so TUIs and singletons
> (lazygit, brainstorm, monitor) do not cross-contaminate between projects.
>
> **How to apply:**
> - Any tmux lookup that scans across sessions (e.g., `find_window_by_name`
>   iterating `get_tmux_sessions()`) is architecturally incorrect and must be
>   scoped to the current project's session.
> - Any `tmux -t <session>` target must use exact match (`-t =<session>`) —
>   tmux's default prefix match means a session named `aitasks` silently
>   resolves to `aitasks_mob` if that's the only running match, crossing
>   project boundaries.
> - When reviewing multi-project behavior, assume the user may have several
>   session names that share prefixes.

#### c. TUI switcher shortcuts act on selected session (from memory: TUI switcher shortcuts act on selected session)

> In the multi-session TUI switcher, shortcut keys (`b` board, `m` monitor,
> `c` codebrowser, `s` settings, `t` stats, `r` brainstorm, `g` git,
> `x` explore, `n` new task) act on the **selected** (Left/Right-browsed)
> session — identical to pressing Enter on that TUI's row in that session.
> Cross-session teleport (`switch-client`) fires automatically when the
> selected session differs from the attached one.
>
> **Why:** User correction during t634_3 planning (2026-04-24). The archived
> t634_3 task description and its parent t634 description prescribe
> "shortcuts stay on current/attached session"; the user explicitly reversed
> this — the desired behavior is shortcut-on-selected. The implemented plan
> (`aiplans/p634/p634_3_two_level_tui_switcher.md`) follows the user
> preference, not the task description.
>
> **How to apply:** Any future work on `.aitask-scripts/lib/tui_switcher.py`
> or related keybinding docs must preserve shortcut-on-selected semantics. If
> you see `self._session` being read in a shortcut handler, that is correct —
> `self._session` is the selected/operating session (mutated by Left/Right),
> NOT the attached one. The separate `self._attached_session` attribute is
> only for deciding whether to issue `switch-client`. Do not "fix" the
> asymmetry by adding a current-running-names set or routing shortcuts
> through the attached session. If reading the archived task file
> `t634/t634_3` later, treat its "Step 4 — Shortcut keys stay on current
> session" as superseded.

#### d. Companion pane auto-despawn (from memory: Companion pane auto-despawn)

> When spawning a companion pane (e.g., `minimonitor`) alongside a primary
> command in a new tmux window (git TUI / `ait create` / explore agents /
> similar), the companion must auto-despawn when the primary exits — **but
> only the companion pane, and only if no other sibling pane is still using
> the window**.
>
> **Why:** User correction during t622. First: do NOT blanket-kill the window
> (`; tmux kill-window`) — user-created panes (shells, notes) in the same
> window must survive. Second: if a codeagent or other "primary-like" pane
> shares the same companion, the minimonitor should persist until **every**
> primary-like pane is gone.
>
> **How to apply:**
> 1. Capture the primary pane id (`tmux new-window -P -F "#{pane_id}"`) and
>    companion pane id (same flags on `split-window`) at spawn time.
> 2. Attach a pane-scoped `pane-died` hook to the primary
>    (`tmux set-hook -p -t <primary> pane-died …`) with `remain-on-exit on`
>    so the hook fires.
> 3. The hook calls a cleanup script that lists panes in the window,
>    excluding primary + companion. If zero other panes → kill both. If ≥1 →
>    kill only the primary and leave the companion alive.
> 4. Do NOT use `tmux kill-window` — it tears down user-owned panes.
> 5. Do NOT use a global "kill companion on any pane-exit" approach — it
>    despawns prematurely when one of several primary-like siblings exits.
>    The per-primary hook + "any other sibling alive?" check is the right
>    shape.
>
> Canonical helper lives at `.aitask-scripts/aitask_companion_cleanup.sh`
> (shell script, called via `tmux run-shell`, not from a code-agent skill —
> no whitelisting touchpoints).

### 2. Skill / Workflow Authoring Conventions section

Add a bullet:

#### Context-variable pattern over template substitution (from memory: Prefer context-variable pattern over template substitution engines)

> When templates need per-instance values like `CREW_ID` / `AGENT_NAME` (or
> analogous variables), do NOT introduce a template-substitution engine that
> interpolates the values at template-write time (e.g., a sed/envsubst pass
> added to a helper). Instead, follow the "context-variable" pattern already
> used by `task-workflow`: declare the variables once in a known file the
> agent reads (e.g., `_instructions.md`, or a shared `_context_variables.md`
> include), reference them as `${VARNAME}` placeholders throughout the
> template, and let the agent substitute them at read time.
>
> **Why:** The pattern is already in use and working for execution profiles
> in `task-workflow` — `task_file`, `task_id`, `active_profile`, etc. are
> declared in the SKILL.md "Context Requirements" table and referenced
> throughout downstream procedures. Agents bind them from working memory
> rather than from text mangled at write time. Adding a new substitution
> engine duplicates the binding mechanism, introduces a second code path
> that can drift, and creates a fragile transformation step in the script
> pipeline.
>
> **How to apply:** When a template needs per-instance values:
> - First, check whether the agent already has the values available via a
>   known context source (e.g., its `_instructions.md` written by an
>   existing helper). If so, just reference the variables in the template
>   and tell the agent where the literal values live.
> - If a shared declaration is needed across multiple templates, add a small
>   include file (e.g., `_context_variables.md`) and inline it via the
>   existing `<!-- include: ... -->` mechanism — do NOT add a new
>   substitution pipeline.
> - Reserve write-time variable interpolation for cases where the agent
>   genuinely cannot read the literal values from any context file (rare).
>
> **Origin:** t650 (brainstorm-bug planning, 2026-04-26). User correction:
> "instead of using a template substitution engine the CREW_ID and
> AGENT_NAME as context variable, we use this technique for execution
> profiles in task-workflow and it is working".

### 3. Adding a New Helper Script section

Add a paragraph after the 5-touchpoint table:

#### Test the full install flow (from memory: Test the full install flow for ait setup helpers)

> When adding or modifying helpers in `.aitask-scripts/aitask_setup.sh` that
> touch `aitasks/metadata/project_config.yaml` (or any file expected to be
> in place by prior install steps), **the test harness must simulate the
> full `install.sh → ait setup` flow** in a scratch dir, not just feed a
> hand-crafted seed to the helper in isolation.
>
> **Why:** During t624 the agent tested setup helpers by dropping a copy of
> `seed/project_config.yaml` into a scratch dir and calling the helpers
> directly. They passed. But `install.sh` deletes `seed/` at the end of
> install and never has had an `install_seed_project_config()` function — so
> in the user's fresh install, `aitasks/metadata/project_config.yaml` was
> missing, the helpers printed "No project_config.yaml found" and returned.
> Unit tests passed, integration failed. Follow-up fix was t628.
>
> **How to apply:**
> - For any setup-flow change, run `bash install.sh --dir /tmp/scratchXY`
>   (or equivalent) into a fresh scratch dir, THEN run the new helper/flow,
>   THEN grep/cat the expected output file to confirm. Do not stop at
>   helper-level unit tests.
> - When adding a helper that reads from `aitasks/metadata/X`, grep
>   `install.sh` for `install_seed_X` or similar — if there isn't one, the
>   helper will fail on fresh installs even if it passes isolated tests.
> - `install.sh`'s deletion of `seed/` means any runtime script that still
>   reads from `$project_dir/seed/...` will silently fail in a fresh
>   install. Those paths only work in the source repo where `seed/` is
>   preserved.

### 4. CLI Conventions section (new H2 section, or sub-section under "Shell Conventions")

Add two sub-sections:

#### a. `ait setup` vs `ait upgrade` (from memory: ait setup vs ait upgrade in framework messages)

> In `ait` framework user-facing messages (`aitask_setup.sh`, docs, error
> hints), distinguish carefully:
>
> - **"Reinstall / repair / restore / populate-missing"** → say `ait setup`.
> - **"Move to a newer version"** → say `ait upgrade`.
>
> **Why:** `ait install` (the now-removed verb, later renamed to
> `ait upgrade`) was a misnomer. Maintainers historically wrote "Re-run 'ait
> install' to get X back" thinking it meant "reinstall/repair". But the
> command actually does a version upgrade: `ait upgrade latest`
> short-circuits with "Already up to date" when on latest, so it **cannot**
> repair a damaged install. The repair verb in aitasks is `ait setup` (which
> re-runs bootstrap and re-installs seed files into the current version).
>
> User surfaced this during t641 when reviewing a naive
> `ait install` → `ait upgrade` swap: four of five setup.sh hints had the
> wrong verb originally, and the agent carried the bug forward. Corrections
> are in commit `46b5a2ad` on main.
>
> **How to apply:** When editing any framework message that mentions
> reinstalling, repairing, or restoring missing files, verify the verb
> semantically. Use `ait setup`. Keep `ait upgrade` only for
> update-available hints or "move to v0.X.Y" flows.

#### b. CLI verb rename: clean removal preferred (from memory: Clean removal preferred for ait CLI verb renames)

> When renaming a user-facing `ait` subcommand, the default plan should
> remove the old verb entirely from the dispatcher — do not keep it as a
> deprecated alias that emits a warning and forwards.
>
> **Why:** During t641 the agent proposed keeping `ait install` as a
> deprecated alias that printed a yellow warning and forwarded to
> `aitask_upgrade.sh`. User rejected as too conservative and asked for
> complete removal. Rationale: clean break forces users to learn the new
> verb immediately; an alias just delays the migration and clutters the
> dispatcher.
>
> **How to apply:** When proposing a CLI rename in aitasks:
> - Remove the old case from the `ait` dispatcher `case "${1:-help}" in`
>   block.
> - Remove the old verb from any meta-command lists (e.g. the no-sync list
>   in `check_for_updates`).
> - Remove any "Previously named X" deprecation notes from docs — update in
>   place without mentioning the old name (aligns with CLAUDE.md docs rule:
>   "describe current state only").
> - Only propose an alias if the user explicitly asks for backward
>   compatibility.

## Implementation guidance

- All additions go into `/home/ddt/Work/aitasks/CLAUDE.md`.
- Place each addition in its existing section (TUI Conventions, Skill /
  Workflow Authoring Conventions, Adding a New Helper Script). The CLI
  Conventions section is new — add it as a new H2 section after "Shell
  Conventions" or as sub-sections under it.
- Keep formatting consistent with the existing CLAUDE.md style: short
  bullet headers, `**Why:**` and `**How to apply:**` lines for rules.
- Preserve the alphabetical or thematic grouping already used in each
  section.

## Verification

- `git diff CLAUDE.md` shows additions in the four targeted sections.
- No other files modified.
- The CLAUDE.md text reads naturally alongside existing content.
