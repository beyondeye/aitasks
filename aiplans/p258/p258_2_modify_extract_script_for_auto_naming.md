---
Task: t258_2_modify_extract_script_for_auto_naming.md
Parent Task: aitasks/t258_automatic_clean_up_of_aiexplains_for_code_browser.md
Sibling Tasks: aitasks/t258/t258_1_*.md, aitasks/t258/t258_3_*.md, aitasks/t258/t258_4_*.md, aitasks/t258/t258_5_*.md
Archived Sibling Plans: aiplans/archived/p258/p258_1_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Plan: Modify extract script for auto-naming

### Step 1: Add helper functions

Add to `aiscripts/aitask_explain_extract_raw_data.sh` after the existing functions section (~line 63):

**`dir_to_key()`** — mirrors Python `_dir_to_key()`:
```bash
dir_to_key() {
    local dir="$1"
    if [[ "$dir" == "." || -z "$dir" ]]; then
        echo "_root_"
    else
        # Remove trailing slash, replace / with __
        echo "${dir%/}" | tr '/' '_' | sed 's/_/__/g'
        # Actually simpler: just replace / with __
        echo "${dir%/}" | sed 's|/|__|g'
    fi
}
```
Note: Be careful with the replacement — `tr '/' '__'` won't work (tr does char-by-char). Use `sed 's|/|__|g'`.

**`compute_common_parent()`** — derives dir_key from input paths:
```bash
compute_common_parent() {
    local first_dir="" common=""
    for path in "${INPUT_PATHS[@]}"; do
        local dir
        if [[ -d "$path" ]]; then
            dir="${path%/}"
        elif [[ -f "$path" ]]; then
            dir=$(dirname "$path")
        else
            continue
        fi
        if [[ -z "$common" ]]; then
            common="$dir"
        else
            # Find common prefix by comparing path segments
            IFS='/' read -ra parts_a <<< "$common"
            IFS='/' read -ra parts_b <<< "$dir"
            local result="" i=0
            while [[ $i -lt ${#parts_a[@]} && $i -lt ${#parts_b[@]} ]]; do
                if [[ "${parts_a[$i]}" == "${parts_b[$i]}" ]]; then
                    result="${result:+$result/}${parts_a[$i]}"
                else
                    break
                fi
                i=$((i + 1))
            done
            common="$result"
        fi
    done
    echo "${common:-.}"
}
```

### Step 2: Add `--source-key` flag

Add `SOURCE_KEY=""` variable at the top (near `MODE=""` line).

In `parse_args()`, add:
```bash
--source-key)
    [[ $# -ge 2 ]] || die "--source-key requires a key argument"
    SOURCE_KEY="$2"
    shift 2
    ;;
```

### Step 3: Modify `gather()` to rename and cleanup

At the end of `gather()`, before the `echo "RUN_DIR:"` line (~line 197):

```bash
# Compute directory key for naming
local dir_key
if [[ -n "$SOURCE_KEY" ]]; then
    dir_key="$SOURCE_KEY"
else
    local common_parent
    common_parent=$(compute_common_parent)
    dir_key=$(dir_to_key "$common_parent")
fi

# Rename run directory to include dir_key
local named_dir="${AIEXPLAINS_DIR}/${dir_key}__${run_id}"
if [[ "$run_dir" != "$named_dir" ]]; then
    mv "$run_dir" "$named_dir"
    run_dir="$named_dir"
fi

# Auto-cleanup stale runs for this AIEXPLAINS_DIR
if [[ -x "$SCRIPT_DIR/aitask_explain_cleanup.sh" ]]; then
    "$SCRIPT_DIR/aitask_explain_cleanup.sh" --quiet --target "$AIEXPLAINS_DIR" 2>/dev/null || true
fi
```

### Step 4: Update help text

Add `--source-key KEY` to the options section and examples.

### Step 5: Verify

1. `shellcheck aiscripts/aitask_explain_extract_raw_data.sh`
2. Test with single file: `./aiscripts/aitask_explain_extract_raw_data.sh --gather aiscripts/lib/task_utils.sh`
   - Expected dir: `aiexplains/aiscripts__lib__<timestamp>/`
3. Test with `--source-key`: `./aiscripts/aitask_explain_extract_raw_data.sh --gather --source-key mykey aiscripts/lib/task_utils.sh`
   - Expected dir: `aiexplains/mykey__<timestamp>/`
4. Test duplicate cleanup: run twice for same files, verify only 1 dir remains

### Step 9: Post-Implementation

Archive task following the standard workflow.

## Final Implementation Notes

- **Actual work done:** All planned steps implemented: `dir_to_key()` and `compute_common_parent()` helper functions, `--source-key` flag in argument parsing, auto-rename of run directories before `RUN_DIR:` output, cleanup integration at end of `gather()`, updated help text with new option and examples. Additionally created `tests/test_extract_auto_naming.sh` with 18 tests (unit + integration).
- **Deviations from plan:** Used bash parameter expansion `${trimmed//\//__}` instead of `sed 's|/|__|g'` for `dir_to_key()` — shellcheck SC2001 recommended this. The plan's draft had two conflicting `echo` lines in `dir_to_key()` (one using `tr` incorrectly, one using `sed`); only the correct approach was implemented. Removed unused `first_dir` variable from `compute_common_parent()`.
- **Issues encountered:** Cleanup integration doesn't work when `AIEXPLAINS_DIR` points outside the default `aiexplains/` directory because `aitask_explain_cleanup.sh` has a hardcoded safety check against `AIEXPLAINS_DIR="aiexplains"`. This is by design (safety) and only affects non-standard configurations — production use with default or `aiexplains/codebrowser` paths works correctly.
- **Key decisions:** Placed the rename and cleanup AFTER Python processing (`reference.yaml` generation) so all data is complete before the directory is renamed. This ensures the Python script operates on a stable directory path.
- **Notes for sibling tasks:** The auto-naming produces directories like `aiscripts__lib__20260226_155403` which matches the `<key>__<YYYYMMDD_HHMMSS>` pattern expected by `aitask_explain_cleanup.sh`. The `dir_to_key()` bash function mirrors `explain_manager.py:_dir_to_key()` exactly. Sibling t258_3 (update explain_manager.py) can now simplify its `_find_run_dir()` since the shell script handles naming — the Python manager no longer needs to rename directories post-hoc.
