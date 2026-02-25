---
title: "/aitask-pickweb"
linkTitle: "/aitask-pickweb"
weight: 12
description: "Pick and implement a task on Claude Code Web — sandboxed skill with local metadata storage"
---

A sandboxed version of [`/aitask-pickrem`](../aitask-pickrem/) designed specifically for **Claude Code Web**, where the environment has no push access to `aitask-locks`, `aitask-data`, or `main` branches. It combines task selection and implementation into a single flow with **zero `AskUserQuestion` calls** — all decisions are driven by an execution profile. The only interactive step is **plan approval**, which still requires the user to review and confirm the implementation plan via `ExitPlanMode`.

All task metadata (plans, completion markers) is stored in `.aitask-data-updated/` on the current working branch. After the Claude Web session completes, run [`/aitask-web-merge`](../aitask-web-merge/) locally to merge code to main and archive the task.

> **Claude Code Web branch restrictions:** Claude Web can only push to the implementation branch — not to `aitask-locks`, `aitask-data`, or `main`. This means task locking, status updates, and archival cannot happen during the Web session. It is recommended (but not required) to pre-lock the task from your local machine using `ait board` or `ait lock <task_id>` before starting a Claude Web session, to prevent another agent from picking the same task.

**Usage:**
```
/aitask-pickweb 42        # Parent task (no children)
/aitask-pickweb 42_2      # Child task
```

A task ID argument is **required** — there is no interactive task browsing.

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Key Differences from /aitask-pickrem

| Aspect | /aitask-pickrem | /aitask-pickweb |
|--------|-----------------|-----------------|
| Lock handling | Acquires lock via `aitask_own.sh` | Read-only lock check only (informational) |
| Status updates | Updates task status to Implementing | No status changes |
| Archival | Full archival via `aitask_archive.sh` | Writes completion marker instead |
| Git operations | Uses `./ait git` (cross-branch) | Uses regular `git` (current branch only) |
| Plan storage | `aiplans/` directory | `.aitask-data-updated/` directory |
| Issue handling | Updates/closes linked issues | Deferred to `/aitask-web-merge` |
| Post-completion | Done — task archived and pushed | Requires follow-up with `/aitask-web-merge` |

## Key Differences from /aitask-pick

| Aspect | /aitask-pick | /aitask-pickweb |
|--------|-------------|-----------------|
| Task selection | Interactive browsing with pagination | Task ID is a required argument |
| User prompts | Multiple interactive decision points | Zero `AskUserQuestion` calls — plan approval still interactive |
| Worktree/branch | Optionally creates worktree on separate branch | Always works on current branch |
| Review loop | User reviews before committing | Auto-commits after implementation |
| Profile | Optional, user selects if multiple exist | Required, auto-selected |
| Branch access | Full access to all branches | Implementation branch only |
| Archival | Full archival process | Completion marker + `/aitask-web-merge` |

## Step-by-Step

1. **Initialize data branch** — Ensures aitask-data worktree and symlinks are ready (required when `ait setup` hasn't been run). No-op for legacy repos
2. **Load execution profile** — Auto-selects a profile (prefers one named `remote`; falls back to first available). Profile is required — aborts if none found
3. **Resolve task file** — Validates the task ID argument, loads the task file. Parent tasks with children are rejected (must specify a child ID directly). For child tasks, gathers sibling context from archived plan files
4. **Read-only lock check** — Informational only. Reports if another user has the task locked, but always proceeds regardless. Does not acquire or modify locks
5. **Task status checks** — Detects Done-but-unarchived tasks and orphaned parents. Unlike `/aitask-pickrem`, these cases abort with a message to use `/aitask-web-merge` locally (since archival requires cross-branch operations)
6. **Create implementation plan** — Uses `EnterPlanMode`/`ExitPlanMode` for plan creation and **user approval** (plan approval is always interactive and cannot be skipped). Plan is saved to `.aitask-data-updated/plan_t<task_id>.md`. Always implements as single task (no child creation in web mode)
7. **Implement** — Follows the approved plan, runs tests and build verification if configured
8. **Auto-commit** — Stages all changes (including `.aitask-data-updated/` files), commits with the standard `<issue_type>: <description> (t<task_id>)` format
9. **Write completion marker** — Creates `.aitask-data-updated/completed_t<task_id>.json` as the signal for `/aitask-web-merge` to detect and process this branch

### Abort Handling

Since no cross-branch operations are performed during the Web session, abort is simple: display the error, optionally clean up `.aitask-data-updated/` files, and stop. No status revert or lock release is needed.

## Completion and Merging

When `/aitask-pickweb` finishes, it writes a **completion marker** at `.aitask-data-updated/completed_t<task_id>.json` containing the task ID, file paths, issue type, and branch name. This marker is the signal for the follow-up step.

After the Claude Web session completes, run [`/aitask-web-merge`](../aitask-web-merge/) on your local machine to:
- Merge the implementation branch to main
- Move the plan file from `.aitask-data-updated/` to `aiplans/`
- Archive the task and plan
- Update/close linked issues
- Clean up the `.aitask-data-updated/` directory

## Suggested Workflow

```
Local machine          Claude Code Web           Local machine
─────────────          ───────────────           ─────────────
1. ait lock 42         2. /aitask-pickweb 42     3. /aitask-web-merge
   (lock task)            (implement + commit)      (merge + archive)
```

1. **(Recommended)** Pre-lock the task from your local machine using `ait board` or `ait lock <task_id>` to prevent concurrent work
2. Run `/aitask-pickweb <task_id>` in Claude Code Web to implement the task
3. After the Web session completes, run `/aitask-web-merge` locally to merge code to main and archive the task

## Execution Profiles

Web mode uses the same profile format as `/aitask-pickrem` from `aitasks/metadata/profiles/`, but only recognizes a subset of fields:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | string | (required) | Display name shown during profile load |
| `description` | string | (required) | Description shown during profile load |
| `plan_preference` | string | `use_current` | `"use_current"`, `"verify"`, or `"create_new"` |
| `post_plan_action` | string | `start_implementation` | `"start_implementation"` |

**Fields from `/aitask-pickrem` that are ignored** (not applicable in web mode): `default_email`, `force_unlock_stale`, `done_task_action`, `orphan_parent_action`, `review_action`, `issue_action`, `abort_plan_action`, `abort_revert_status`, `create_worktree`, `base_branch`.

See [`/aitask-pick` Execution Profiles](../aitask-pick/#execution-profiles) for the full profile reference.

## Build Verification

The skill can optionally verify the build after implementation. See [Build Verification](../aitask-pick/build-verification/) for configuration details.

## Workflows

For the full end-to-end workflow guide, see [Claude Code Web](../../workflows/claude-web/).
