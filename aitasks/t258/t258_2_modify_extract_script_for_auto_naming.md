---
priority: medium
effort: medium
depends: [t258_1]
issue_type: feature
status: Ready
labels: [codebrowser]
created_at: 2026-02-26 15:01
updated_at: 2026-02-26 15:01
---

## Context

The `aitask_explain_extract_raw_data.sh` script creates run directories with bare timestamps (e.g., `20260225_234611`). The codebrowser's Python manager renames them post-hoc to include the source directory key. This child task moves the naming logic into the shell script itself and integrates automatic cleanup.

## Task

Modify `aiscripts/aitask_explain_extract_raw_data.sh` to:
1. Support a `--source-key KEY` flag for explicit key specification
2. Auto-derive a dir_key from input paths when `--source-key` is not given
3. Rename the run directory to `<dir_key>__<timestamp>` format before outputting `RUN_DIR:`
4. Call the cleanup script at the end of `gather()` to prune stale runs

## Key Files to Modify

- `aiscripts/aitask_explain_extract_raw_data.sh` — main changes

## Reference Files

- `aiscripts/codebrowser/explain_manager.py:29-34` — `_dir_to_key()` Python implementation to mirror in bash
- `aiscripts/aitask_explain_cleanup.sh` — cleanup script to call (created in t258_1)

## Implementation Details

**New functions to add:**

1. `dir_to_key()` — mirror Python `_dir_to_key()`: `.` or empty → `_root_`, otherwise replace `/` with `__`

2. `compute_common_parent()` — given `INPUT_PATHS` array, compute common parent directory:
   - If path is a directory, use as-is
   - If path is a file, use its dirname
   - Find common prefix across all paths by splitting on `/` and comparing segments
   - Return `.` if no common prefix

**Changes to `gather()` function (after line 195, before the `echo "RUN_DIR:"`):**

```bash
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
```

**Cleanup integration (at end of gather()):**
```bash
if [[ -x "$SCRIPT_DIR/aitask_explain_cleanup.sh" ]]; then
    "$SCRIPT_DIR/aitask_explain_cleanup.sh" --quiet --target "$AIEXPLAINS_DIR" 2>/dev/null || true
fi
```

**Argument parsing:** Add `SOURCE_KEY=""` variable and `--source-key)` case in `parse_args()`.

**Update `--help`:** Document `--source-key` option.

## Verification

1. `shellcheck aiscripts/aitask_explain_extract_raw_data.sh`
2. Run `AIEXPLAINS_DIR=aiexplains ./aiscripts/aitask_explain_extract_raw_data.sh --gather aiscripts/lib/task_utils.sh` — verify output dir is named `aiscripts__lib__<timestamp>` (not bare timestamp)
3. Run with `--source-key test_key` — verify dir is named `test_key__<timestamp>`
4. Run twice for same files — verify only 1 dir remains (cleanup prunes the older one)
