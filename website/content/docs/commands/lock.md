---
title: "Lock"
linkTitle: "Lock"
weight: 36
description: "ait lock command for atomic task locking to prevent concurrent work"
---

## ait lock

Lock and unlock tasks to prevent two users or agents from working on the same task simultaneously. Uses atomic git operations on a separate `aitask-locks` branch.

```bash
ait lock 42                        # Lock task t42 (auto-detects email)
ait lock 42 --email user@co.com    # Lock with explicit email
ait lock --unlock 42               # Release lock on t42
ait lock --check 42                # Check if t42 is locked
ait lock --list                    # Show all active locks
```

| Command | Description |
|---------|-------------|
| `<task_id>` | Lock a task. Auto-detects email from `userconfig.yaml`, falling back to `emails.txt` |
| `--lock <task_id> [--email EMAIL]` | Explicit lock syntax (same as bare task ID) |
| `--unlock <task_id>` | Release a task lock. Idempotent (succeeds even if not locked) |
| `--check <task_id>` | Check lock status. Exit 0 = locked (prints lock info), exit 1 = free |
| `--list` | List all currently locked tasks |
| `--init` | Initialize the `aitask-locks` branch on the remote (usually done by `ait setup`) |
| `--cleanup` | Remove stale locks for tasks that have been archived |

| Option | Description |
|--------|-------------|
| `--email EMAIL` | Override email for locking (default: auto-detect) |
| `--debug` | Enable verbose debug output |

### Email Auto-Detection

When locking a task without `--email`, the command resolves the email in this order:

1. `aitasks/metadata/userconfig.yaml` -- the `email:` field
2. `aitasks/metadata/emails.txt` -- the first line

This matches the behavior of the [board TUI](../../tuis/board/) lock button.

### How It Works

Locks are stored as YAML files (`t<N>_lock.yaml`) on a separate orphan git branch (`aitask-locks`) that exists only on the remote. Atomicity is achieved via git's push rejection on non-fast-forward updates -- if two users try to lock the same task simultaneously, only one push succeeds and the other retries (up to 5 attempts).

Each lock file contains:

```yaml
task_id: 42
locked_by: user@example.com
locked_at: 2026-02-24 14:30
hostname: my-laptop
```

**Locking does not change task metadata.** The task's `status` and `assigned_to` fields are not modified -- locking is purely a reservation mechanism. The status changes to `Implementing` later when the task is actually picked for implementation (via `/aitask-pick` or similar).

### When to Use `ait lock`

**You do not need to call `ait lock` before `/aitask-pick`.** The `/aitask-pick` and `/aitask-pickrem` skills automatically handle locking as part of their workflow -- they acquire the lock, set the task status to Implementing, and update `assigned_to` all in one step.

`ait lock` is a **manual pre-reservation tool** for signaling to other users or agents that you intend to work on a task. Common use cases:

- **Before `/aitask-pickweb`** -- Claude Code Web cannot acquire locks (it lacks push access to the `aitask-locks` branch), so pre-locking from your local machine prevents another agent from picking the same task. Even without pre-locking, `/aitask-pickweb` will still work -- it just won't have lock protection against concurrent work.
- **Reserving tasks for later** -- Lock a task now to signal intent, then start `/aitask-pick` later when ready.
- **Multi-agent coordination** -- When multiple agents are running simultaneously, pre-locking helps avoid duplicate work.

### Locking vs Ownership

| Concept | Command | What it does |
|---------|---------|--------------|
| **Lock** | `ait lock` | Reserves a task to signal intent. Lightweight -- no metadata changes |
| **Ownership** | (automatic) | Performed by `/aitask-pick` skills: locks + sets status to Implementing + sets `assigned_to` |

### Pre-Locking for Claude Code Web

When using [`/aitask-pickweb`](../../skills/aitask-pickweb/) on Claude Code Web, the Web environment cannot acquire locks (it lacks push access to the `aitask-locks` branch). Pre-locking from your local machine is recommended but not required -- `/aitask-pickweb` will work either way, but without a lock another agent could pick the same task concurrently.

```
Local machine          Claude Code Web           Local machine
---------------        ---------------           ---------------
1. ait lock 42         2. /aitask-pickweb 42     3. /aitask-web-merge
   (lock task)            (implement + commit)      (merge + archive)
```

### Setup

The `aitask-locks` branch is created during `ait setup`. If you see an error about missing lock infrastructure, run:

```bash
ait setup        # Interactive -- includes lock branch initialization
ait lock --init  # Direct initialization
```
