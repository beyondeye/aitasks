---
title: "Explain Utilities"
linkTitle: "Explain"
weight: 35
description: "ait explain-runs and ait explain-cleanup commands"
---

## ait explain-runs

Manage aiexplain run directories. The `/aitask-explain` skill generates reference data (git history analysis, task/plan mappings) in directories under `aiexplains/`. Over time these accumulate. Use `ait explain-runs` to list, inspect, and clean up old run data.

**Interactive mode** (default — requires fzf):

```bash
ait explain-runs
```

Presents a list of all existing runs (both top-level and codebrowser) with file counts and previews. Select a run to delete it, or choose "Delete ALL runs" to remove everything. Confirmation is required before deletion.

**Batch mode** (CLI flags):

```bash
ait explain-runs --list                                              # List all runs with their files
ait explain-runs --delete aiexplains/aiscripts__lib__20260226_155403  # Delete a specific run
ait explain-runs --delete-all                                         # Delete all runs
ait explain-runs --cleanup-stale                                      # Remove stale runs (keep newest per source)
```

| Option | Description |
|--------|-------------|
| `--list` | List all runs with their associated files (top-level and codebrowser sections) |
| `--delete RUN_DIR` | Delete a specific run directory (must be under `aiexplains/`) |
| `--delete-all` | Delete all run directories |
| `--cleanup-stale` | Remove stale runs, keeping only the newest per source directory (delegates to `ait explain-cleanup --all`) |
| (no flags) | Interactive mode using fzf |

**Run directory naming:**

Run directories use the format `<dir_key>__<timestamp>`, where `dir_key` identifies the source directory that was analyzed (e.g., `aiscripts__lib` for `aiscripts/lib/`) and `timestamp` is `YYYYMMDD_HHMMSS`. This naming allows the cleanup tools to identify which runs correspond to the same source directory and remove older duplicates.

**Run directory structure:**

Each run is stored as `aiexplains/<dir_key>__<timestamp>/` and contains:
- `files.txt` — list of files that were analyzed
- `reference.yaml` — structured line-to-commit-to-task mapping
- `tasks/` and `plans/` — extracted task and plan files for context

Codebrowser runs are stored under `aiexplains/codebrowser/<dir_key>__<timestamp>/` with the same structure.

**Safety:**
- The `--delete` option validates that the target path is under `aiexplains/` before removing
- The `aiexplains/` parent directory is automatically removed if empty after deletion
- Interactive mode requires explicit confirmation before any deletion

## ait explain-cleanup

Remove stale aiexplain run directories, keeping only the newest run per source directory key. This prevents disk usage from growing unboundedly as new analysis runs are generated.

Stale cleanup also happens automatically when the `/aitask-explain` skill generates new data and at codebrowser TUI startup — this command is for manual cleanup or automation.

```bash
ait explain-cleanup --all                                   # Clean both top-level and codebrowser runs
ait explain-cleanup --target aiexplains/codebrowser          # Clean only codebrowser runs
ait explain-cleanup --dry-run --all                          # Preview what would be removed
ait explain-cleanup --all --quiet                            # Silent mode for automation
```

| Option | Description |
|--------|-------------|
| `--target DIR` | Clean a specific directory (default: `aiexplains/`) |
| `--all` | Clean both `aiexplains/` (top-level) and `aiexplains/codebrowser/` |
| `--dry-run` | Show what would be removed without deleting |
| `--quiet` | Suppress informational output |

**How it works:**

The script groups run directories by their `dir_key` (the part before `__<timestamp>`). For each group, it keeps the newest run (highest timestamp) and removes all older ones. Directories without the expected naming pattern or without `files.txt`/`raw_data.txt` are skipped.
