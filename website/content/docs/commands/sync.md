---
title: "Sync"
linkTitle: "Sync"
weight: 35
description: "ait sync command for bidirectional task data synchronization"
---

## ait sync

Sync task data with a remote repository: auto-commit local changes, fetch, pull with rebase, and push. Designed for multi-machine workflows where task files may be edited on different PCs.

```bash
ait sync                    # Interactive mode with colored progress
ait sync --batch            # Structured output for scripting/automation
```

| Option | Description |
|--------|-------------|
| `--batch` | Structured single-line output for scripting (no colors, no interactive prompts) |
| `--help, -h` | Show usage help |

### Interactive Mode

In interactive mode, `ait sync` displays colored progress messages as it works through each step:

1. Checks for uncommitted task file changes and auto-commits them
2. Fetches from the remote with a 10-second timeout
3. Pulls new commits using rebase (to keep history linear)
4. Pushes local commits to the remote

If merge conflicts occur during rebase, the script opens each conflicted file in `$EDITOR` (default: `nano`) for manual resolution. After editing, the file is staged and the rebase continues. You can abort the rebase at any point by exiting the editor without saving.

### Batch Output Protocol

In batch mode (`--batch`), the script outputs a single structured line on stdout:

| Output | Meaning |
|--------|---------|
| `SYNCED` | Both push and pull completed successfully |
| `PUSHED` | Local changes pushed, nothing to pull |
| `PULLED` | Remote changes pulled, nothing to push |
| `NOTHING` | Already up-to-date, no action needed |
| `CONFLICT:<file1>,<file2>` | Merge conflicts detected (rebase aborted) |
| `NO_NETWORK` | Fetch or push timed out or failed (no connectivity) |
| `NO_REMOTE` | No git remote configured for the repository |
| `ERROR:<message>` | Unexpected error with details |

This protocol is used by the [board TUI](../../board/) for background sync integration.

### How It Works

The sync flow follows these steps:

1. **Mode detection** — Determines whether task data lives on a separate `aitask-data` branch (via `.aitask-data/` worktree) or on the current branch (legacy mode)
2. **Remote check** — Verifies a git remote exists; outputs `NO_REMOTE` if not
3. **Auto-commit** — If there are uncommitted changes to `aitasks/` or `aiplans/`, stages and commits them automatically
4. **Fetch** — Fetches from the remote with a 10-second network timeout; outputs `NO_NETWORK` on failure
5. **Pull with rebase** — If the remote has new commits, pulls them using `git pull --rebase` to maintain linear history
6. **Push** — If there are local commits to push, pushes them to the remote (retries once on rejection, in case the remote advanced during rebase)
7. **Output result** — Reports the final status

### Network Handling

All network operations use a 10-second timeout to prevent the script from hanging when there is no connectivity. On systems with the `timeout` command (standard on Linux), it is used directly. On systems without it (e.g., macOS without coreutils), a portable bash-based watchdog fallback is used.

If any network operation times out, the script outputs `NO_NETWORK` and exits cleanly — no partial state is left behind.

### Data Branch Mode

When the repository uses a separate `aitask-data` branch for task files (set up via `ait setup`), all git operations target the data branch worktree automatically. In legacy mode (tasks on the main branch), sync operates on the current branch. The behavior is transparent — the same `ait sync` command works in both modes.
