---
title: "Explain Utilities"
linkTitle: "Explain"
weight: 35
description: "ait explain-runs command"
---

## ait explain-runs

Manage aiexplain run directories. The `/aitask-explain` skill generates reference data (git history analysis, task/plan mappings) in timestamped directories under `aiexplains/`. Over time these accumulate. Use `ait explain-runs` to list, inspect, and clean up old run data.

**Interactive mode** (default — requires fzf):

```bash
ait explain-runs
```

Presents a list of all existing runs with file counts and previews. Select a run to delete it, or choose "Delete ALL runs" to remove everything. Confirmation is required before deletion.

**Batch mode** (CLI flags):

```bash
ait explain-runs --list                              # List all runs with their files
ait explain-runs --delete aiexplains/20260221_143052  # Delete a specific run
ait explain-runs --delete-all                         # Delete all runs
```

| Option | Description |
|--------|-------------|
| `--list` | List all runs with their associated files |
| `--delete RUN_DIR` | Delete a specific run directory (must be under `aiexplains/`) |
| `--delete-all` | Delete all run directories |
| (no flags) | Interactive mode using fzf |

**Run directory structure:**

Each run is stored as `aiexplains/<timestamp>/` and contains:
- `files.txt` — list of files that were analyzed
- `reference.yaml` — structured line-to-commit-to-task mapping
- `tasks/` and `plans/` — extracted task and plan files for context

**Safety:**
- The `--delete` option validates that the target path is under `aiexplains/` before removing
- The `aiexplains/` parent directory is automatically removed if empty after deletion
- Interactive mode requires explicit confirmation before any deletion
