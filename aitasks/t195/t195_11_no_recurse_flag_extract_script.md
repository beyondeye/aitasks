---
priority: low
effort: low
depends: [t195_4]
issue_type: feature
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:19
updated_at: 2026-03-01 11:15
---

## Context

This is child task 11 of t195 (Python Code Browser TUI) — a risk mitigation follow-up for Risk 4 (non-recursive directory listing). The initial implementation (t195_4) filters `git ls-files` output on the Python side to get only direct children of a directory. This task moves that logic into the shell script where it belongs by adding a `--no-recurse` flag to `aitask_explain_extract_raw_data.sh`.

## Key Files to Modify

- **`aiscripts/aitask_explain_extract_raw_data.sh`** (MODIFY):
  - Add `--no-recurse` flag to the argument parser
  - When set, modify `expand_path()` to only return direct children of a directory (not files in subdirectories)
  - Handle edge case: root directory (empty path) → list only top-level tracked files
  - Handle edge case: directory with no direct files (only subdirectories) → produce empty run or skip gracefully
- **`aiscripts/codebrowser/explain_manager.py`** (MODIFY):
  - Update `generate_explain_data()` to use `--no-recurse` flag instead of Python-side filtering
  - Remove the Python-side `os.path.dirname(f) == str(directory)` filter
  - Simplify: just pass the directory path + `--no-recurse` to the script

## Reference Files for Patterns

- `aiscripts/aitask_explain_extract_raw_data.sh` (lines 23-42): Current `expand_path()` function — uses `git ls-files "$path"` which is recursive
- `aiscripts/aitask_explain_extract_raw_data.sh` (lines 62-90): Argument parsing section where `--no-recurse` should be added

## Implementation Plan

1. Add `--no-recurse` flag to argument parser:
   - Add `NO_RECURSE=false` default
   - Add case: `--no-recurse) NO_RECURSE=true; shift ;;`

2. Modify `expand_path()`:
   - After `git ls-files "$path"`, if `$NO_RECURSE` is true:
     - Strip the directory prefix from each path
     - Filter out paths containing `/` (these are in subdirectories)
     - Re-prepend the directory prefix
   - Implementation:
     ```bash
     if [[ "$NO_RECURSE" == "true" ]]; then
         git ls-files "$path" | while IFS= read -r f; do
             # Get path relative to the directory
             local rel="${f#"$path"/}"
             # Skip if still contains / (means it's in a subdirectory)
             [[ "$rel" == */* ]] && continue
             # Binary check
             if file -b --mime-encoding "$f" 2>/dev/null | grep -qv 'binary'; then
                 echo "$f"
             fi
         done
     else
         # existing recursive behavior
         ...
     fi
     ```

3. Handle edge cases:
   - Root directory (path is `.` or empty):
     - `git ls-files .` lists everything; with no-recurse, filter to files with no `/` in path
   - Directory with no direct files:
     - `expand_path()` returns nothing → `all_files` array is empty → script warns and exits cleanly (existing behavior)

4. Update `explain_manager.py`:
   - In `generate_explain_data()`: pass `["--no-recurse", "--gather", str(directory)]` instead of individual file paths
   - Remove Python-side filtering logic
   - Simplify the method

5. Test backward compatibility:
   - Without `--no-recurse`: behavior unchanged (recursive)
   - With `--no-recurse`: only direct children

## Verification Steps

1. Run extract script with `--no-recurse` on `aiscripts/` directory:
   - Should only get `.sh` files directly in `aiscripts/`, not files in `aiscripts/board/` or `aiscripts/lib/`
2. Run without `--no-recurse` on same directory:
   - Should get all files recursively (unchanged behavior)
3. Run with `--no-recurse` on root directory (`.`):
   - Should get only top-level files (ait, CLAUDE.md, etc.)
4. Run with `--no-recurse` on a directory with only subdirectories (no direct files):
   - Should produce empty result, no errors
5. Codebrowser uses `--no-recurse` and still generates correct explain data per directory
6. Verify `reference.yaml` only contains files from the target directory, not subdirectories
