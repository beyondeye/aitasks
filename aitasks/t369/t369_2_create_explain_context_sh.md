---
priority: medium
effort: medium
depends: [t369_1]
issue_type: feature
status: Ready
labels: [aitask_explain, aitask_pick]
created_at: 2026-03-11 18:33
updated_at: 2026-03-11 18:33
---

Create aitask_explain_context.sh - Shell script orchestrating context gathering: groups files by directory, checks/generates codebrowser cache with auto-staleness detection and regeneration, calls Python formatter.

## Context

This is the shell orchestrator for the historical context feature (parent task t369). When an agent identifies files it plans to modify during the planning phase, it calls this script to get historical architectural context. The script handles all the file system operations, git commands, cache management, and pipeline orchestration, then delegates to the Python formatter (t369_1) for data aggregation and output formatting.

The key design principle is that unlike the codebrowser TUI (which only flags staleness for manual refresh), this script auto-regenerates stale data because it runs non-interactively during the planning phase.

## Key Files to Modify

- **`.aitask-scripts/aitask_explain_context.sh`** (NEW) — The main deliverable. Shell script that groups files by directory, manages codebrowser cache, calls existing extract pipeline when needed, and calls the Python formatter.

## Reference Files for Patterns

- **`.aitask-scripts/aitask_explain_extract_raw_data.sh`** — The existing extract pipeline this script will invoke. Key functions to understand:
  - `dir_to_key()` (line 79) — converts directory path to cache key (replace `/` with `__`, `.` becomes `_root_`)
  - `gather()` (line 173) — the main extraction function showing how run directories are created
  - Shows how `AITASK_EXPLAIN_DIR` env var controls output location
  - Shows the `--no-recurse --gather --source-key` invocation pattern for directory-based extraction
- **`.aitask-scripts/codebrowser/explain_manager.py`** — Contains the staleness check logic to port:
  - `_dir_to_key()` (line 40) — Python version of dir_to_key
  - `_find_run_dir()` (line 47) — glob pattern `<dir_key>__[0-9]*` sorted, take last
  - `_check_stale()` (line 298) — compare run dir timestamp vs `git log -1 --format=%ct -- <dir>`
  - `_parse_run_timestamp()` (line 258) — extract timestamp from dir name suffix (last 15 chars: `YYYYMMDD_HHMMSS`)
  - `refresh_data()` (line 211) — delete old run dir, regenerate
- **`.aitask-scripts/lib/task_utils.sh`** — Shared utility functions (die, warn, info, etc.)
- **`.aitask-scripts/lib/terminal_compat.sh`** — Platform detection and portable helpers

## Implementation Plan

### Step 1: Create the script skeleton

Create `.aitask-scripts/aitask_explain_context.sh` with:
```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
```

Add defaults:
```bash
MAX_PLANS=0
INPUT_FILES=()
CODEBROWSER_DIR=".aitask-explain/codebrowser"
```

### Step 2: Implement argument parsing

Parse `--max-plans N <file1> [file2...]`:
```bash
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --max-plans)
                [[ $# -ge 2 ]] || die "--max-plans requires a number"
                MAX_PLANS="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                INPUT_FILES+=("$1")
                shift
                ;;
        esac
    done

    if [[ "$MAX_PLANS" -eq 0 ]]; then
        exit 0  # No-op when disabled
    fi

    if [[ ${#INPUT_FILES[@]} -eq 0 ]]; then
        die "No input files specified"
    fi
}
```

### Step 3: Implement `dir_to_key()` function

Port from `aitask_explain_extract_raw_data.sh` line 79 (already exists there, but we need a local copy since this is a standalone script):
```bash
dir_to_key() {
    local dir="$1"
    if [[ "$dir" == "." || -z "$dir" ]]; then
        echo "_root_"
    else
        local trimmed="${dir%/}"
        echo "${trimmed//\//__}"
    fi
}
```

### Step 4: Implement `find_run_dir()` function

Port the logic from `explain_manager.py:_find_run_dir()`:
```bash
find_run_dir() {
    local dir_key="$1"
    local pattern="${CODEBROWSER_DIR}/${dir_key}__[0-9]*"
    local matches
    matches=$(ls -d $pattern 2>/dev/null | sort | tail -1)
    echo "$matches"
}
```

### Step 5: Implement `parse_run_timestamp()` function

Extract unix timestamp from run directory name. Port from `explain_manager.py:_parse_run_timestamp()`:
- Extract last 15 chars of dir name (YYYYMMDD_HHMMSS)
- Convert to unix timestamp using `date` (use portable syntax)

### Step 6: Implement staleness check

Port from `explain_manager.py:_check_stale()`:
```bash
check_stale() {
    local dir_key="$1"
    local run_dir="$2"

    local run_ts
    run_ts=$(parse_run_timestamp "$run_dir")
    [[ "$run_ts" -eq 0 ]] && echo "false" && return

    # Convert dir_key back to path
    local dir_path
    if [[ "$dir_key" == "_root_" ]]; then
        dir_path="."
    else
        dir_path="${dir_key//__//}"
    fi

    local git_ts
    git_ts=$(git log -1 --format=%ct -- "$dir_path" 2>/dev/null || echo "0")
    [[ -z "$git_ts" ]] && git_ts=0

    if [[ "$git_ts" -gt "$run_ts" ]]; then
        echo "true"
    else
        echo "false"
    fi
}
```

### Step 7: Implement file grouping by parent directory

Group input files by their parent directory:
```bash
# Use associative array: dir_key -> space-separated file list
declare -A dir_files
for f in "${INPUT_FILES[@]}"; do
    local dir
    dir=$(dirname "$f")
    local key
    key=$(dir_to_key "$dir")
    dir_files["$key"]="${dir_files[$key]:-} $f"
done
```

### Step 8: Implement cache check and regeneration loop

For each unique directory:
1. Find existing run_dir
2. If found, check staleness
3. If stale: delete run_dir, regenerate
4. If missing: generate fresh
5. Collect `reference.yaml:run_dir` pairs

Regeneration uses the existing extract pipeline:
```bash
AITASK_EXPLAIN_DIR="$CODEBROWSER_DIR" \
    "$SCRIPT_DIR/aitask_explain_extract_raw_data.sh" \
    --no-recurse --gather --source-key "$dir_key" "$dir_path"
```

### Step 9: Call the Python formatter

After collecting all ref:rundir pairs:
```bash
local ref_args=()
for pair in "${ref_pairs[@]}"; do
    ref_args+=(--ref "$pair")
done

python3 "$SCRIPT_DIR/aitask_explain_format_context.py" \
    --max-plans "$MAX_PLANS" \
    "${ref_args[@]}" \
    -- "${INPUT_FILES[@]}"
```

### Step 10: Handle edge cases

- If no explain data can be generated (new files with no git history), exit 0 silently
- If the extract pipeline fails for a directory, warn but continue with remaining directories
- If no reference.yaml files are collected (all directories failed), exit 0 silently
- Use `info` for progress messages (sent to stderr so stdout is clean for the formatter output)

## Verification Steps

1. **Manual test with real files**: Run against known files in the project:
   ```bash
   ./.aitask-scripts/aitask_explain_context.sh --max-plans 3 .aitask-scripts/aitask_archive.sh
   ```
   Verify output is well-formed markdown with plan content.

2. **Cache reuse test**: Run twice against the same file; second run should be faster (uses cached data).

3. **Staleness detection**: Modify a tracked file, commit, then run the script; verify it detects staleness and regenerates.

4. **No-op test**: Run with `--max-plans 0` and verify immediate clean exit.

5. **New file test**: Run against a file with no git history and verify graceful no-op.

6. **Shellcheck**: Run `shellcheck .aitask-scripts/aitask_explain_context.sh` and verify clean output.

7. **Multiple directories**: Run against files from different directories and verify all are handled:
   ```bash
   ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 \
       .aitask-scripts/aitask_archive.sh \
       .aitask-scripts/lib/task_utils.sh
   ```
