---
Task: t85_2_create_ait_dispatcher.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_3_*.md, aitasks/t85/t85_4_*.md, etc.
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_2 - Create `ait` Dispatcher Script

## Context

The `ait` dispatcher is the single CLI entry point for the aitask framework. It lives at the root of `~/Work/aitasks/` and forwards subcommands to scripts in `aiscripts/`. The placeholder file already exists (empty, created in t85_1).

## Key Correction from t85_1

The task spec maps `import` → `aitask_import.sh`, but per t85_1's implementation notes, the file was renamed to `aitask_issue_import.sh`. The dispatcher will map `issue-import` → `aitask_issue_import.sh`.

## Implementation

### File: `~/Work/aitasks/ait`

Write the full dispatcher script with these components:

1. **Shebang + strict mode**: `#!/usr/bin/env bash` + `set -euo pipefail`
2. **AIT_DIR resolution**: `$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` then `cd "$AIT_DIR"`
3. **SCRIPTS_DIR**: `"$AIT_DIR/aiscripts"`
4. **`show_version()`**: reads `$AIT_DIR/VERSION`, prints `ait version <ver>` or `ait version unknown`
5. **`show_usage()`**: prints help text listing all subcommands
6. **`case` dispatch**: uses `exec` for clean process replacement

Subcommand mapping:
| Subcommand | Script |
|---|---|
| `create` | `aitask_create.sh` |
| `ls` | `aitask_ls.sh` |
| `update` | `aitask_update.sh` |
| `issue-import` | `aitask_issue_import.sh` |
| `board` | `aitask_board.sh` |
| `stats` | `aitask_stats.sh` |
| `clear-old` | `aitask_clear_old.sh` |
| `issue-update` | `aitask_issue_update.sh` |
| `setup` | `aitask_setup.sh` |
| `help` / `--help` / `-h` | `show_usage` |
| `--version` / `-v` | `show_version` |
| (no args) | `show_usage` |
| (unknown) | error message + usage hint |

Then `chmod +x ~/Work/aitasks/ait`.

## Verification

1. `cd ~/Work/aitasks && ./ait --version` → prints `ait version 0.1.0`
2. `./ait help` → prints usage with all subcommands
3. `./ait unknowncmd` → prints error and suggests `ait help`
4. `./ait` (no args) → prints usage

## Final Implementation Notes
- **Actual work done:** Created the `ait` dispatcher script (58 lines) at `~/Work/aitasks/ait`. Implements all 9 subcommand dispatches via `exec`, plus `help`, `--version`, and unknown command handling. Made executable with `chmod +x`.
- **Deviations from plan:** Changed `import` subcommand to `issue-import` per user request, mapping to `aitask_issue_import.sh`. This better reflects the actual script name and avoids confusion.
- **Issues encountered:** None.
- **Key decisions:** Used `issue-import` (not `import`) as the subcommand name to match the script name `aitask_issue_import.sh`.
- **Notes for sibling tasks:** The `ait` dispatcher uses `cd "$AIT_DIR"` to ensure all scripts can use relative paths like `TASK_DIR="aitasks"`. The `exec` pattern replaces the shell process cleanly. The subcommand `issue-import` (not `import`) maps to `aitask_issue_import.sh` — sibling tasks referencing import functionality should use this name.

## Post-Implementation (Step 9)

Archive child task and plan, update parent's `children_to_implement`.
