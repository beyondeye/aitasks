---
title: "Lock"
linkTitle: "Lock"
weight: 36
description: "ait lock command for atomic task locking to prevent concurrent work"
depth: [intermediate]
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
| `<task_id>` | Lock a task. Auto-detects email from `userconfig.yaml`, falling back to `emails.txt`. Exit 0 = locked, 1 = held by another owner, 13 = held by another **live** session of yours on this host, 14 = held by a session of yours whose liveness could not be established (see [Locks]({{< relref "/docs/concepts/locks" >}})) |
| `--lock <task_id> [--email EMAIL]` | Explicit lock syntax (same as bare task ID) |
| `--unlock <task_id>` | Release a task lock. Idempotent (succeeds even if not locked) |
| `--check <task_id>` | Check lock status. Exit 0 = locked (prints lock info), exit 1 = free |
| `--list` | List all currently locked tasks |
| `--init` | Initialize the `aitask-locks` branch on the remote (usually done by `ait setup`) |
| `--cleanup` | Remove stale locks for tasks that have been archived. Exit 0 = completed, 11 = lock branch unreadable, 12 = removal push rejected (see [Stale Lock Cleanup](#stale-lock-cleanup)) |

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

### Stale Lock Cleanup

`ait lock --cleanup` sweeps the `aitask-locks` branch for locks belonging to tasks that have already been archived. The pick workflow runs it automatically before selecting a task, so it is what keeps a finished session's lock from blocking the next one.

It reports its outcome through the exit status:

| Exit | Meaning |
|------|---------|
| `0` | Completed -- no remote, no lock branch, nothing stale, or every stale lock removed |
| `11` | The lock branch could not be read (unreachable remote, auth failure). No locks were removed |
| `12` | The branch was readable, but the removal push was rejected on every retry. The stale locks are still there |

Both failure codes warn on stderr, naming how many stale locks were left in place and how to recover. Successful sweeps and sweeps with nothing to do are silent.

**A failed sweep never blocks a pick.** `/aitask-pick` and the other skills that sync first still proceed; they surface the warning and continue. This matters because the failure is self-perpetuating if unreported: stale locks that are never swept accumulate, and a later pick reports the task as locked by someone who is no longer working on it. If you see that warning, run `ait lock --list` to inspect the branch and `ait lock --unlock <task_id>` to clear a specific lock.

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

---

**Next:** [Issue Integration & Utilities]({{< relref "/docs/commands/issue-integration" >}})
