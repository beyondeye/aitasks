---
Task: t398_1_revert_analyze_script.md
Parent Task: aitasks/t398_aitask_revert.md
Sibling Tasks: aitasks/t398/t398_2_revert_skill.md, aitasks/t398/t398_3_post_revert_integration.md, aitasks/t398/t398_4_website_documentation.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t398_1 — Backend Analysis Script (`aitask_revert_analyze.sh`)

## Overview

Create `.aitask-scripts/aitask_revert_analyze.sh` with 4 subcommands for analyzing task-related commits and changes. Also register it in the `ait` dispatcher.

## Steps

### Step 1: Create the script file

Create `.aitask-scripts/aitask_revert_analyze.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"
```

### Step 2: Implement `show_help()` and `parse_args()`

Standard pattern. Arguments:
- `--recent-tasks` — set `MODE=recent_tasks`
- `--task-commits <id>` — set `MODE=task_commits`, `TASK_ID=<id>`
- `--task-areas <id>` — set `MODE=task_areas`, `TASK_ID=<id>`
- `--task-files <id>` — set `MODE=task_files`, `TASK_ID=<id>`
- `--limit N` — set `LIMIT=N` (default 20)
- `--help|-h` — show help

### Step 3: Implement `extract_task_id()` helper

Parse task IDs from commit messages matching `(tN)` or `(tN_M)` pattern:
```bash
extract_task_id() {
    local msg="$1"
    echo "$msg" | grep -oE '\(t[0-9]+(_[0-9]+)?\)' | sed 's/[()]//g' | sed 's/^t//'
}
```

### Step 4: Implement `get_child_ids()` helper

For parent tasks, discover all child task IDs:
```bash
get_child_ids() {
    local task_id="$1"
    local output
    output=$("$SCRIPT_DIR/aitask_query_files.sh" all-children "$task_id" 2>/dev/null) || return 0
    # Parse CHILD: and ARCHIVED_CHILD: lines, extract child number from filename
    echo "$output" | grep -E '^(CHILD|ARCHIVED_CHILD):' | \
        grep -oE 't[0-9]+_[0-9]+' | sed 's/^t//' | sort -u
}
```

### Step 5: Implement `find_task_commits()` core function

Given a task ID, find all commits. For parents, also search children.
```bash
find_task_commits() {
    local task_id="$1"
    local search_ids=("$task_id")

    # Check for children
    local children
    children=$(get_child_ids "$task_id")
    if [[ -n "$children" ]]; then
        while IFS= read -r child_id; do
            search_ids+=("$child_id")
        done <<< "$children"
    fi

    for sid in "${search_ids[@]}"; do
        local pattern="(t${sid})"
        git log --all --oneline --format="%H|%as|%s" --grep="$pattern" -- | while IFS='|' read -r hash date msg; do
            # Get diff stats
            local stats
            stats=$(git diff --shortstat "${hash}^..${hash}" 2>/dev/null || echo "")
            local ins=0 del=0
            ins=$(echo "$stats" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo 0)
            del=$(echo "$stats" | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo 0)
            echo "COMMIT|${hash:0:12}|${date}|${msg}|${ins}|${del}|${sid}"
        done
    done
}
```

### Step 6: Implement `--recent-tasks` mode

Parse git log, extract task IDs, deduplicate, count:
```bash
cmd_recent_tasks() {
    local limit="${LIMIT:-20}"
    # Get recent non-ait: commits with task IDs
    git log --all --oneline --format="%as|%s" -500 | \
        grep -v '^[^|]*|ait:' | while IFS='|' read -r date msg; do
            local tid
            tid=$(extract_task_id "$msg")
            [[ -n "$tid" ]] && echo "${tid}|${date}|${msg}"
        done | \
        awk -F'|' '!seen[$1]++ { count[$1]=1; date[$1]=$2; title[$1]=$3; next } { count[$1]++ }
            END { for (id in date) print "TASK|" id "|" title[id] "|" date[id] "|" count[id] }' | \
        head -n "$limit"
}
```

### Step 7: Implement `--task-areas` mode

Group files from commits by parent directory:
```bash
cmd_task_areas() {
    local task_id="$1"
    # Collect all changed files from task commits
    # ... (use find_task_commits to get commit hashes, then git diff-tree for each)
    # Group by directory, aggregate stats
}
```

### Step 8: Implement `--task-files` mode

Flat file listing from all task commits:
```bash
cmd_task_files() {
    local task_id="$1"
    # Collect unique files with aggregate stats
}
```

### Step 9: Implement `main()` dispatch

```bash
main() {
    parse_args "$@"
    case "$MODE" in
        recent_tasks) cmd_recent_tasks ;;
        task_commits) find_task_commits "$TASK_ID" ;;
        task_areas)   cmd_task_areas "$TASK_ID" ;;
        task_files)   cmd_task_files "$TASK_ID" ;;
        *) show_help; exit 1 ;;
    esac
}
main "$@"
```

### Step 10: Register in `ait` dispatcher

Add to the `ait` file's case statement:
```bash
revert-analyze) shift; exec "$SCRIPTS_DIR/aitask_revert_analyze.sh" "$@" ;;
```

### Step 11: Make executable and verify

```bash
chmod +x .aitask-scripts/aitask_revert_analyze.sh
shellcheck .aitask-scripts/aitask_revert_analyze.sh
./ait revert-analyze --help
./ait revert-analyze --recent-tasks
./ait revert-analyze --task-commits <known_task_id>
```

## Final Implementation Notes

- **Actual work done:** Created `aitask_revert_analyze.sh` with 4 subcommands (`--recent-tasks`, `--task-commits`, `--task-areas`, `--task-files`) plus 27 automated tests. Script is internal (not registered in `ait` dispatcher).
- **Deviations from plan:**
  - No `ait` dispatcher entry — this is an internal script called by the revert skill (t398_2), not user-facing
  - Added `|| true` to `get_child_ids()` grep pipeline to prevent `pipefail` failures when a task has no children
  - Used an `order` array instead of re-iterating git log for `cmd_recent_tasks()` output ordering (simpler, single-pass)
  - Added `build_search_ids()` and `collect_commit_hashes()` helper functions to share search logic between `find_task_commits`, `cmd_task_areas`, and `cmd_task_files`
  - Used `--fixed-strings` flag with `git log --grep` to match literal parentheses in `(tN)` patterns
  - Used process substitution (`< <(git log ...)`) instead of piping to avoid subshell issues with `git diff` stats collection
- **Issues encountered:** `set -euo pipefail` caused `get_child_ids()` to fail when grep found no matches in the pipeline; fixed with `|| true`
- **Key decisions:** Reused `parse_shortstat()` pattern from `aitask_review_commits.sh` and `extract_task_id()` pattern from `aitask_explain_extract_raw_data.sh` (inlined, not sourced)
- **Notes for sibling tasks:**
  - The script is invoked directly with `bash .aitask-scripts/aitask_revert_analyze.sh <subcommand>`, not via `./ait`
  - Output uses pipe-delimited structured format: `TASK|`, `COMMIT|`, `AREA|`, `FILE|` prefixes
  - The `--task-commits` subcommand automatically discovers and includes child task commits when given a parent task ID
  - The `collect_commit_hashes()` function is useful for any subcommand that needs all commit hashes for a task
