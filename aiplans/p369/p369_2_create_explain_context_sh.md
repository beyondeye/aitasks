---
Task: t369_2_create_explain_context_sh.md
Parent Task: aitasks/t369_aitask_explain_for_aitask_pick.md
Sibling Tasks: aitasks/t369/t369_*_*.md
Archived Sibling Plans: aiplans/archived/p369/p369_*_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Create aitask_explain_context.sh (t369_2)

## Overview

Create a new shell script at `.aitask-scripts/aitask_explain_context.sh` that orchestrates historical context gathering for the planning phase. It groups input files by parent directory, manages the codebrowser cache (check/generate/regenerate), and calls the Python formatter (t369_1) to produce formatted markdown output.

**Dependency:** Requires `.aitask-scripts/aitask_explain_format_context.py` from t369_1 to be implemented first.

## Architecture

```
Agent (planning phase)
  └── .aitask-scripts/aitask_explain_context.sh --max-plans N file1 file2 ...
        ├── Groups files by parent directory
        ├── For each directory:
        │   ├── Computes dir_key (port of _dir_to_key)
        │   ├── Checks codebrowser cache (.aitask-explain/codebrowser/<key>__*)
        │   ├── Staleness check (git log timestamp vs run dir timestamp)
        │   └── If missing/stale: calls aitask_explain_extract_raw_data.sh
        └── Calls aitask_explain_format_context.py with collected ref:rundir pairs
              └── Output: formatted markdown to stdout
```

## Detailed Implementation Steps

### Step 1: Create script skeleton

**File:** `.aitask-scripts/aitask_explain_context.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# aitask_explain_context.sh - Gather historical architectural context for planning
# Orchestrates codebrowser cache and calls Python formatter for output.
#
# Usage: ./.aitask-scripts/aitask_explain_context.sh --max-plans N <file1> [file2...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Defaults ---
MAX_PLANS=0
INPUT_FILES=()
CODEBROWSER_DIR=".aitask-explain/codebrowser"
EXTRACT_SCRIPT="$SCRIPT_DIR/aitask_explain_extract_raw_data.sh"
FORMAT_SCRIPT="$SCRIPT_DIR/aitask_explain_format_context.py"
```

### Step 2: Implement argument parsing

```bash
show_help() {
    cat << 'EOF'
Usage: aitask_explain_context.sh --max-plans N <file1> [file2...]

Gather historical architectural context from aitask-explain data.

Options:
  --max-plans N    Maximum plans per file for greedy selection (required; 0 = no-op)
  --help, -h       Show help

Output:
  Formatted markdown to stdout with historical plan content.
  Progress messages go to stderr.

Examples:
  ./.aitask-scripts/aitask_explain_context.sh --max-plans 3 .aitask-scripts/aitask_archive.sh
  ./.aitask-scripts/aitask_explain_context.sh --max-plans 1 src/foo.py src/bar.py
EOF
}

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
            --)
                shift
                INPUT_FILES+=("$@")
                break
                ;;
            *)
                INPUT_FILES+=("$1")
                shift
                ;;
        esac
    done
}
```

### Step 3: Implement early exit for no-op

```bash
# After parse_args:
if [[ "$MAX_PLANS" -eq 0 ]]; then
    exit 0
fi

if [[ ${#INPUT_FILES[@]} -eq 0 ]]; then
    die "No input files specified. Usage: $0 --max-plans N <file1> [file2...]"
fi
```

### Step 4: Implement dir_to_key function

Port from `aitask_explain_extract_raw_data.sh` (line 79):

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

### Step 5: Implement find_run_dir function

Port from `explain_manager.py:_find_run_dir()` (line 47):

```bash
find_run_dir() {
    local dir_key="$1"
    # Glob for <dir_key>__YYYYMMDD_HHMMSS directories
    local pattern="${CODEBROWSER_DIR}/${dir_key}__"
    local latest=""
    for d in "${pattern}"[0-9]*; do
        [[ -d "$d" ]] || continue
        latest="$d"  # Sorted alphabetically, last one is newest
    done
    echo "$latest"
}
```

### Step 6: Implement parse_run_timestamp function

Port from `explain_manager.py:_parse_run_timestamp()` (line 258):

```bash
parse_run_timestamp() {
    local run_dir="$1"
    local dir_name
    dir_name=$(basename "$run_dir")

    # Timestamp is last 15 chars: YYYYMMDD_HHMMSS
    local ts_str="${dir_name: -15}"
    if [[ ${#ts_str} -ne 15 || "${ts_str:8:1}" != "_" ]]; then
        echo "0"
        return
    fi

    # Convert YYYYMMDD_HHMMSS to unix timestamp
    local year="${ts_str:0:4}"
    local month="${ts_str:4:2}"
    local day="${ts_str:6:2}"
    local hour="${ts_str:9:2}"
    local min="${ts_str:11:2}"
    local sec="${ts_str:13:2}"

    # Use date -d on Linux, date -j on macOS (portable)
    local ts
    if date --version &>/dev/null; then
        # GNU date (Linux)
        ts=$(date -d "${year}-${month}-${day} ${hour}:${min}:${sec}" +%s 2>/dev/null || echo "0")
    else
        # BSD date (macOS)
        ts=$(date -j -f "%Y%m%d_%H%M%S" "$ts_str" +%s 2>/dev/null || echo "0")
    fi
    echo "$ts"
}
```

### Step 7: Implement staleness check

Port from `explain_manager.py:_check_stale()` (line 298):

```bash
check_stale() {
    local dir_key="$1"
    local run_dir="$2"

    local run_ts
    run_ts=$(parse_run_timestamp "$run_dir")
    if [[ "$run_ts" -eq 0 ]]; then
        echo "false"
        return
    fi

    # Convert dir_key back to path
    local dir_path
    if [[ "$dir_key" == "_root_" ]]; then
        dir_path="."
    else
        dir_path="${dir_key//__//}"
    fi

    local git_ts
    git_ts=$(git log -1 --format=%ct -- "$dir_path" 2>/dev/null || echo "0")
    git_ts="${git_ts:-0}"

    if [[ "$git_ts" -gt "$run_ts" ]]; then
        echo "true"
    else
        echo "false"
    fi
}
```

### Step 8: Implement file grouping by parent directory

```bash
# Group input files by parent directory
# Use temp files to avoid associative array issues with spaces in paths
group_files() {
    declare -A dir_groups
    for f in "${INPUT_FILES[@]}"; do
        local dir
        dir=$(dirname "$f")
        local key
        key=$(dir_to_key "$dir")
        # Append file to group (newline-separated)
        dir_groups["$key"]="${dir_groups[$key]:-}${dir_groups[$key]:+$'\n'}$f"
    done

    # Output: key<TAB>file pairs, one per line
    for key in "${!dir_groups[@]}"; do
        echo "$key"
    done
}
```

### Step 9: Implement cache check and regeneration loop

This is the main logic. For each unique directory key:

```bash
process_directory() {
    local dir_key="$1"

    local run_dir
    run_dir=$(find_run_dir "$dir_key")

    if [[ -n "$run_dir" ]]; then
        # Check staleness
        local stale
        stale=$(check_stale "$dir_key" "$run_dir")
        if [[ "$stale" == "true" ]]; then
            info "Cache stale for $dir_key, regenerating..." >&2
            rm -rf "$run_dir"
            run_dir=""
        fi
    fi

    if [[ -z "$run_dir" ]]; then
        # Generate fresh data
        info "Generating explain data for $dir_key..." >&2

        # Convert dir_key back to path for the extract script
        local dir_path
        if [[ "$dir_key" == "_root_" ]]; then
            dir_path="."
        else
            dir_path="${dir_key//__//}"
        fi

        # Run the extract pipeline
        local extract_output
        extract_output=$(AITASK_EXPLAIN_DIR="$CODEBROWSER_DIR" \
            "$EXTRACT_SCRIPT" --no-recurse --gather \
            --source-key "$dir_key" "$dir_path" 2>&1) || {
            warn "Extract pipeline failed for $dir_key, skipping" >&2
            return 1
        }

        # Parse RUN_DIR from output
        run_dir=$(echo "$extract_output" | grep '^RUN_DIR: ' | sed 's/^RUN_DIR: //')
        if [[ -z "$run_dir" ]]; then
            warn "No RUN_DIR in extract output for $dir_key" >&2
            return 1
        fi
    fi

    # Verify reference.yaml exists
    local ref_yaml="${run_dir}/reference.yaml"
    if [[ ! -f "$ref_yaml" ]]; then
        warn "No reference.yaml in $run_dir" >&2
        return 1
    fi

    # Output ref:rundir pair
    echo "${ref_yaml}:${run_dir}"
}
```

### Step 10: Implement main function

```bash
main() {
    parse_args "$@"

    if [[ "$MAX_PLANS" -eq 0 ]]; then
        exit 0
    fi

    if [[ ${#INPUT_FILES[@]} -eq 0 ]]; then
        die "No input files specified"
    fi

    # Group files by directory
    declare -A dir_groups
    for f in "${INPUT_FILES[@]}"; do
        local dir
        dir=$(dirname "$f")
        local key
        key=$(dir_to_key "$dir")
        dir_groups["$key"]=1
    done

    # Process each directory and collect ref:rundir pairs
    local ref_pairs=()
    for dir_key in "${!dir_groups[@]}"; do
        local pair
        pair=$(process_directory "$dir_key" 2>&1 | tail -1) || continue
        # Only add if it looks like a valid ref:rundir pair
        if [[ "$pair" == *"/reference.yaml:"* ]]; then
            ref_pairs+=("$pair")
        fi
    done

    if [[ ${#ref_pairs[@]} -eq 0 ]]; then
        # No data available, graceful exit
        exit 0
    fi

    # Build --ref arguments for the Python formatter
    local ref_args=()
    for pair in "${ref_pairs[@]}"; do
        ref_args+=(--ref "$pair")
    done

    # Call the Python formatter
    python3 "$FORMAT_SCRIPT" \
        --max-plans "$MAX_PLANS" \
        "${ref_args[@]}" \
        -- "${INPUT_FILES[@]}"
}

main "$@"
```

**Important:** Progress/diagnostic messages MUST go to stderr (`>&2`) so that stdout is clean for the Python formatter's markdown output.

### Step 11: Make script executable

```bash
chmod +x .aitask-scripts/aitask_explain_context.sh
```

## Edge Cases to Handle

1. **No git history for files** -- New files that have never been committed. The extract pipeline will produce empty data; the formatter handles this gracefully (empty output).
2. **Extract pipeline failure** -- If `aitask_explain_extract_raw_data.sh` fails for a directory, warn and continue with remaining directories.
3. **All directories fail** -- If no reference.yaml files are collected, exit 0 silently.
4. **Binary files** -- The extract pipeline marks binary files. The formatter ignores them (no line ranges).
5. **Files in root directory** -- dir_key becomes `_root_`. Verify this works correctly.
6. **Concurrent execution** -- If two agents run simultaneously, the extract pipeline handles this via unique timestamps in run directory names.

## Testing

1. Run `shellcheck .aitask-scripts/aitask_explain_context.sh` -- verify clean
2. Run against a real file: `./.aitask-scripts/aitask_explain_context.sh --max-plans 2 .aitask-scripts/aitask_archive.sh`
3. Run with `--max-plans 0` -- verify immediate exit
4. Run against non-existent file -- verify graceful handling
5. Run against files from multiple directories

## Step 9: Post-Implementation

Follow `.claude/skills/task-workflow/SKILL.md` Step 9 for cleanup, archival, and merge.
