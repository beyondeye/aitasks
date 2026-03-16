---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitask_revert]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-16 10:23
updated_at: 2026-03-16 14:44
completed_at: 2026-03-16 14:44
---

Create .aitask-scripts/aitask_revert_analyze.sh — the backend data layer for all revert operations.

## Context
This is child 1 of t398 (aitask-revert). The parent task creates a feature to revert changes associated with specific aitasks. This child creates the core analysis script that the skill (child 2) will call.

## Key Files to Create
- `.aitask-scripts/aitask_revert_analyze.sh` — Main analysis script

## Key Files to Modify
- `ait` — Add `revert-analyze` dispatcher entry

## Reference Files for Patterns
- `.aitask-scripts/aitask_review_commits.sh` — Commit parsing, ait: filtering, paginated output
- `.aitask-scripts/aitask_explain_extract_raw_data.sh` lines 69-76 — `extract_task_id_from_message()` for `(tN)` pattern
- `.aitask-scripts/lib/terminal_compat.sh` — Portable utilities (die, warn, info, sed_inplace)
- `.aitask-scripts/lib/task_utils.sh` — resolve_task_file(), resolve_plan_file()

## Implementation Plan

### Subcommands to implement:

1. **`--recent-tasks [--limit N]`** — List recently completed tasks from git log
   - Parse commit messages for `(tNN)` pattern using grep/sed
   - Filter out `ait:` administrative commits
   - Deduplicate by task ID, count commits per task
   - Output: `TASK|<id>|<title>|<date>|<commit_count>`
   - Default limit: 20

2. **`--task-commits <task_id>`** — Find all commits associated with a task
   - Search git log for commits matching `(t<id>)` in message
   - **For parent tasks:** also search for all child task commits. Use `aitask_query_files.sh all-children <id>` to discover child IDs, then search for `(t<id>_1)`, `(t<id>_2)`, etc.
   - Include diff stats (insertions/deletions) per commit
   - Output: `COMMIT|<hash>|<date>|<message>|<insertions>|<deletions>|<task_id>`
   - Last field indicates which task/child the commit belongs to

3. **`--task-areas <task_id>`** — Group changed files by directory
   - Uses commits from `--task-commits` logic (including children for parents)
   - Group files by their parent directory (component/area)
   - Aggregate stats per area
   - Output: `AREA|<area_path>|<file_count>|<insertions>|<deletions>|<file1,file2,...>`

4. **`--task-files <task_id>`** — Flat file list
   - Same commit scope as above
   - Output: `FILE|<path>|<insertions>|<deletions>`

### Script structure:
- `#!/usr/bin/env bash`, `set -euo pipefail`
- Source `terminal_compat.sh` + `task_utils.sh`
- `show_help()` + `parse_args()` + `main()` pattern
- Helper functions: `find_task_commits()`, `get_child_ids()`, `group_by_area()`

### Portability notes:
- No `grep -P` (use `grep -oE` for extended regex)
- Use `sed_inplace()` if needed
- `wc -l | tr -d ' '` for string comparisons

## Verification Steps
- `shellcheck .aitask-scripts/aitask_revert_analyze.sh` passes
- `./ait revert-analyze --recent-tasks` lists recently implemented tasks
- `./ait revert-analyze --task-commits <known_parent_id>` returns commits for parent AND all children
- `./ait revert-analyze --task-commits <known_child_id>` returns commits for just that child
- `./ait revert-analyze --task-areas <known_id>` groups files by area
- `./ait revert-analyze --task-files <known_id>` lists all changed files
- `./ait revert-analyze --help` shows usage
