---
title: "/aitask-pickrem"
linkTitle: "/aitask-pickrem"
weight: 11
description: "Pick and implement a task in remote/non-interactive mode — zero prompts, profile-driven"
---

A mostly autonomous version of [`/aitask-pick`](../aitask-pick/) designed for non-interactive environments. It combines task selection and implementation into a single workflow with **zero `AskUserQuestion` calls** — all decisions are driven by an execution profile. The only interactive step is **plan approval**, which still requires the user to review and confirm the implementation plan via `ExitPlanMode`.

> **Note:** This skill requires write access to the task data branch, so it is suited for local Claude Code or CI-like environments. For **Claude Code Web** (which cannot write to branches other than the code branch), use [`/aitask-pickweb`](../aitask-pickweb/) instead.

**Usage:**
```
/aitask-pickrem 42        # Parent task (no children)
/aitask-pickrem 42_2      # Child task
```

A task ID argument is **required** — there is no interactive task browsing.

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Key Differences from /aitask-pick

| Aspect | /aitask-pick | /aitask-pickrem |
|--------|-------------|-----------------|
| Task selection | Interactive browsing with pagination | Task ID is a required argument |
| User prompts | Multiple interactive decision points | Zero `AskUserQuestion` calls — plan approval still interactive |
| Worktree/branch | Optionally creates worktree on separate branch | Always works on current branch |
| Review loop | User reviews before committing | Auto-commits after implementation |
| Profile | Optional, user selects if multiple exist | Required, auto-selected |

## Workflow Overview

1. **Initialize data branch** — Ensures aitask-data worktree and symlinks are ready (required when `ait setup` hasn't been run). No-op for legacy repos
2. **Load execution profile** — Auto-selects a profile (prefers one named `remote`; falls back to first available). Profile is required — aborts if none found
3. **Resolve task file** — Validates the task ID argument, loads the task file. Parent tasks with children are rejected (must specify a child ID directly)
4. **Sync with remote** — Best-effort sync to pick up changes from other machines
5. **Task status checks** — Detects Done-but-unarchived tasks and orphaned parents. Handles them based on profile settings (`done_task_action`, `orphan_parent_action`)
6. **Assign task** — Non-interactive email resolution (from task metadata → userconfig → profile). Claims ownership and acquires lock. Stale locks can be auto-force-unlocked via `force_unlock_stale` profile setting
7. **Environment setup** — Always works on the current branch (no worktree/branch management)
8. **Create implementation plan** — Uses `EnterPlanMode`/`ExitPlanMode` for plan creation and **user approval** (plan approval is always interactive and cannot be skipped by profiles). Can verify existing plans or create new ones. Always implements as single task (no child creation in remote mode)
9. **Implement and auto-commit** — Follows the approved plan, runs tests and build verification, stages all changes, and commits with the standard `<issue_type>: <description> (t<task_id>)` format
10. **Archive and push** — Archives task and plan files, handles linked issues per profile setting, pushes to remote

### Abort Handling

If errors occur after claiming the task, the abort procedure releases the lock, reverts task status (configurable via `abort_revert_status`), and optionally deletes the plan file (`abort_plan_action`). No user interaction required.

## Execution Profiles

Remote mode **requires** a profile — without one, the skill aborts. The profile pre-answers every decision that `/aitask-pick` would ask interactively (except plan approval, which always requires user confirmation).

Profiles are YAML files stored in `aitasks/metadata/profiles/`. The `remote` profile ships by default:

```yaml
name: remote
description: Fully autonomous workflow - no interactive prompts except plan approval
skip_task_confirmation: true
default_email: userconfig
force_unlock_stale: true
plan_preference: use_current
post_plan_action: start_implementation
done_task_action: archive
orphan_parent_action: archive
complexity_action: single_task
review_action: commit
issue_action: close_with_notes
abort_plan_action: keep
abort_revert_status: Ready
```

### Standard Profile Fields

These fields are shared with `/aitask-pick` (see [Execution Profiles](../aitask-pick/#execution-profiles)):

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | string | (required) | Display name shown during profile load |
| `description` | string | (required) | Description shown during profile load |
| `default_email` | string | — | `"userconfig"`, `"first"`, or a literal email address |
| `plan_preference` | string | `use_current` | `"use_current"`, `"verify"`, or `"create_new"` |
| `post_plan_action` | string | `start_implementation` | `"start_implementation"` |

Fields from the standard schema that are **ignored** in remote mode: `run_location`, `create_worktree`, `base_branch`.

### Remote-Specific Profile Fields

These fields are only recognized by `/aitask-pickrem`:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `force_unlock_stale` | bool | `false` | Auto force-unlock stale task locks |
| `done_task_action` | string | `archive` | What to do with Done tasks: `"archive"` or `"skip"` |
| `orphan_parent_action` | string | `archive` | What to do with completed parent tasks: `"archive"` or `"skip"` |
| `complexity_action` | string | `single_task` | Always `"single_task"` (no child creation in remote mode) |
| `review_action` | string | `commit` | Auto-commit behavior: `"commit"` |
| `issue_action` | string | `close_with_notes` | Issue handling: `"close_with_notes"`, `"comment_only"`, `"close_silent"`, or `"skip"` |
| `abort_plan_action` | string | `keep` | Plan file on abort: `"keep"` or `"delete"` |
| `abort_revert_status` | string | `Ready` | Task status on abort: `"Ready"` or `"Editing"` |

All fields have sensible defaults — a profile only needs `name` and `description` to function, though providing all fields is recommended.

## Build Verification

The workflow can optionally verify the build after implementation. See [Build Verification](../aitask-pick/build-verification/) for configuration details.
