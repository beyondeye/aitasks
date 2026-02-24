---
title: "Claude Code Web"
linkTitle: "Claude Code Web"
weight: 50
description: "Running tasks on Claude Code Web with sandboxed branch access"
---

Claude Code Web is a browser-based Claude Code environment that operates with restricted git permissions — it can only push to its own implementation branch. It cannot access `aitask-locks`, `aitask-data`, or `main` branches directly. This guide covers the end-to-end workflow for running aitasks on Claude Code Web.

## Standard vs Claude Web Workflow

| Step | Standard (local) | Claude Code Web |
|------|-----------------|-----------------|
| 1. Lock task | Automatic (during `/aitask-pick`) | Manual pre-lock from local machine |
| 2. Implement | `/aitask-pick` — full branch access | `/aitask-pickweb` — current branch only |
| 3. Archive | Automatic (during `/aitask-pick`) | `/aitask-web-merge` — run locally after |

**Standard workflow** handles everything in one session: lock → implement → commit → archive → push.

**Claude Web workflow** splits into three stages across two environments:

```
Local machine          Claude Code Web           Local machine
─────────────          ───────────────           ─────────────
1. ait lock 42         2. /aitask-pickweb 42     3. /aitask-web-merge
   (lock task)            (implement + commit)      (merge + archive)
```

## Step-by-Step Guide

### Step 1: Pre-Lock the Task (Local)

Before starting a Claude Web session, lock the task from your local machine to prevent another developer or agent from picking it concurrently.

**Option A — Using the board TUI:**
```bash
ait board
```
Open the task details and click the Lock button (🔒). The board prompts for your email and acquires the lock.

**Option B — Using the CLI:**
```bash
ait lock <task_id>
```

Pre-locking is recommended but not required. If you skip it, `/aitask-pickweb` will display an informational warning if the task is locked by someone else, but will proceed regardless.

### Step 2: Implement on Claude Code Web

Start a Claude Code Web session on a branch for the task, then run:

```
/aitask-pickweb <task_id>
```

For child tasks, use the parent_child format:
```
/aitask-pickweb 42_2
```

The skill handles everything autonomously with zero interactive prompts (except plan approval via `ExitPlanMode`):
1. Loads the `remote` execution profile
2. Resolves and reads the task file
3. Performs a read-only lock check (informational only)
4. Creates or verifies the implementation plan
5. Implements the approved plan
6. Auto-commits all changes
7. Writes a completion marker to `.aitask-data-updated/`

See [`/aitask-pickweb`](../../skills/aitask-pickweb/) for the full skill reference.

### Step 3: Merge and Archive (Local)

After the Claude Web session completes and the branch is pushed, run locally:

```
/aitask-web-merge
```

This skill:
1. Scans remote branches for completion markers (`.aitask-data-updated/completed_t*.json`)
2. Merges the implementation branch to main (excluding `.aitask-data-updated/`)
3. Copies the plan file to `aiplans/` on the aitask-data branch
4. Archives the task (and parent if all children are complete)
5. Pushes main and aitask-data
6. Deletes the remote implementation branch

If multiple completed branches exist, the skill offers to process them sequentially.

See [`/aitask-web-merge`](../../skills/aitask-web-merge/) for the full skill reference.

## The `.aitask-data-updated/` Directory

Since Claude Web cannot write to the `aitask-data` branch, `/aitask-pickweb` stores task metadata in a `.aitask-data-updated/` directory on the implementation branch. This directory contains:

| File | Purpose |
|------|---------|
| `plan_t<task_id>.md` | Implementation plan (normally stored in `aiplans/`) |
| `completed_t<task_id>.json` | Completion marker — signals to `/aitask-web-merge` that the branch is ready |

The completion marker JSON includes:
```json
{
  "task_id": "42",
  "task_file": "aitasks/t42_implement_auth.md",
  "plan_file": ".aitask-data-updated/plan_t42.md",
  "is_child": false,
  "parent_id": null,
  "issue_type": "feature",
  "completed_at": "2026-02-24 15:30",
  "branch": "claude-web/t42"
}
```

During `/aitask-web-merge`, the plan file is copied to `aiplans/` and the entire `.aitask-data-updated/` directory is excluded from the merge to main via `git rm -rf`.

## Execution Profile

`/aitask-pickweb` requires an execution profile from `aitasks/metadata/profiles/`. It auto-selects a profile named `remote` if one exists, falling back to the first available profile alphabetically.

The default `remote.yaml` profile works for both `/aitask-pickrem` and `/aitask-pickweb` — pickweb simply ignores fields it doesn't recognize (lock, archival, review settings). Only these fields are used by pickweb:

| Key | Default | Description |
|-----|---------|-------------|
| `plan_preference` | `use_current` | How to handle existing plans: `use_current`, `verify`, or `create_new` |
| `post_plan_action` | `start_implementation` | Action after plan approval |

See [`/aitask-pickweb` Execution Profiles](../../skills/aitask-pickweb/#execution-profiles) for details.

## Troubleshooting

### Branch not detected by `/aitask-web-merge`

- Ensure the Claude Web session pushed the branch to the remote
- Run `git fetch --all` and check if the branch appears in `git branch -r`
- Verify the branch contains `.aitask-data-updated/completed_t*.json`

### Merge conflicts during `/aitask-web-merge`

The skill uses `git merge --no-ff --no-commit` and will prompt you to resolve conflicts interactively. You can also abort the merge and handle it manually.

### Task already locked by someone else

`/aitask-pickweb` performs a read-only lock check — it warns but always proceeds. If you want to prevent concurrent work, pre-lock the task from your local machine before starting the Web session.

### "Web workflow requires an execution profile"

Create a profile at `aitasks/metadata/profiles/remote.yaml`. The default `ait setup` creates one automatically. Minimal content:

```yaml
name: remote
description: Fully autonomous workflow - no interactive prompts
plan_preference: use_current
post_plan_action: start_implementation
```

## See Also

- [`/aitask-pickweb`](../../skills/aitask-pickweb/) — Web-side skill reference
- [`/aitask-web-merge`](../../skills/aitask-web-merge/) — Local merge skill reference
- [`/aitask-pickrem`](../../skills/aitask-pickrem/) — Remote skill with full branch access
- [Parallel Development](../parallel-development/) — Concurrency safety and locking
