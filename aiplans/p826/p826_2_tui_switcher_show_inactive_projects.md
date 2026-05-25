---
Task: t826_2_tui_switcher_show_inactive_projects.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_1_registry_resolver_projects_cmd_and_create_flag.md, aitasks/t826/t826_3_website_docs_multi_project_workflow.md
Archived Sibling Plans: aiplans/archived/p826/p826_*_*.md (especially p826_1 — the registry schema and resolver semantics it ships are required reading)
Worktree: (profile 'fast' — works on current branch, no worktree)
Branch: (profile 'fast' — current branch)
Base branch: main
---

# Plan: TUI switcher surfaces registered-but-inactive projects (t826_2)

## Context

Second sibling under t826. Consumes the per-user registry shipped by t826_1
(`~/.config/aitasks/projects.yaml`) to make registered-but-not-currently-running
projects visible in the `ait` IDE TUI switcher. Selecting an inactive project
spawns its tmux session via the same path `ait ide` uses and teleports.

**Scope note (locked in parent brainstorm):** `ait monitor` is intentionally
**out of scope**. Only the TUI switcher gains inactive-project visibility in
this round. Monitor's multi-project view stays scoped to live tmux sessions.

## Plan

The full step-by-step implementation plan, file paths, reference patterns,
and verification steps are inlined into the task description at
`aitasks/t826/t826_2_tui_switcher_show_inactive_projects.md`.

Before picking up this task, read the archived plan from sibling t826_1
(`aiplans/archived/p826/p826_1_*.md`) for the canonical registry schema and
the resolver's invocation contract — do not redesign those here.

## Key design decisions

| Decision | Value |
|---|---|
| Default-off flag on `discover_aitasks_sessions` | `include_registered=False` — preserves identical behavior for existing callers (notably `ait monitor`) |
| Inactive entry shape | `AitasksSession(session=None, project_root, project_name)` with `is_live` property |
| Switcher visual indicator | None — activity is implied by switch-vs-spawn on selection (user explicitly said "probably not needed") |
| Bootstrap reuse | Extract `aitask_ide.sh`'s session-bootstrap into shared helper (`lib/tmux_bootstrap.sh` or similar); single source of truth for tmux session creation |
| `ait monitor` changes | None — explicit out-of-scope |
| Regression test required | Yes — `discover_aitasks_sessions()` default call must yield identical entries to pre-change behavior |

## Out of scope

- `ait monitor` multi-project view
- Visual indicators for inactive entries in the switcher
- Bootstrap differences between `ait ide` and switcher-triggered spawn (use the same path)

## Step 9 reference

After implementation and review, follow the shared workflow's Step 9. No
worktree to clean (profile `fast` works on the current branch).
