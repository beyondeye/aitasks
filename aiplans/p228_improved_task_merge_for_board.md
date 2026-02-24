---
Task: t228_improved_task_merge_for_board.md
Branch: (current branch - no worktree)
Base branch: main
---

# Implementation Plan: t228 — Improved Task Merge for ait sync

## Overview

This is a parent task split into 5 child tasks. See each child's plan in `aiplans/p228/` for details.

## Child Tasks

1. **t228_1** — Extract shared YAML utilities into `task_yaml.py` (refactor, low effort)
2. **t228_2** — Create Python auto-merge script (feature, high effort)
3. **t228_3** — Integrate merge into `ait sync` (feature, medium effort)
4. **t228_4** — Update board TUI integration (feature, low effort)
5. **t228_5** — Tests and documentation (test, medium effort)

## Auto-Merge Rules

| Field(s) | Rule |
|-----------|------|
| `boardcol`, `boardidx` | Keep LOCAL |
| `updated_at` | Keep LATEST timestamp |
| `labels` | Union (dedup) |
| `depends` | Union (dedup) |
| `priority`, `effort` | Keep REMOTE (batch) / Ask user (interactive) |
| `status` | If either side is `Implementing` → keep `Implementing`. Otherwise → manual |
| Field in one side only | Keep it (no conflict) |
| Body or other fields | Manual resolution with "newest" hint |

## Step 9 (Post-Implementation)

After all child tasks complete: archive child tasks, archive parent t228, push.
