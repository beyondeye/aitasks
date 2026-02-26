---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [bash_scripts, aitask_explain]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-26 11:15
updated_at: 2026-02-26 11:47
completed_at: 2026-02-26 11:47
---

Fix binary file detection in the aiexplains extraction and processing pipeline (producer side).

## Context

The aiexplains extraction pipeline (`aitask_explain_extract_raw_data.sh` + `aitask_explain_process_raw_data.py`) processes binary files (PNG, WEBP, etc.) as if they were code files. The shell script has a binary check in `expand_path()` at line 29 using `file -b --mime-encoding`, but it only applies when expanding **directories**. When individual file paths are passed (as the codebrowser does via `explain_manager.py:generate_explain_data()`), the `elif [[ -f "$path" ]]` branch has NO binary check.

This causes `git blame --porcelain` to generate thousands of meaningless "lines" for binary files, producing bloated raw_data.txt (~722KB for 8 image files) and reference.yaml with meaningless line_ranges.

Binary files should still have their commit timeline extracted (useful to know when an image was added/changed), but blame lines should be skipped.

## Key Files to Modify

1. **`aiscripts/aitask_explain_extract_raw_data.sh`** — Shell extraction script
   - Add `is_binary()` helper function (reusing `file -b --mime-encoding` approach from line 29)
   - Modify `process_file()` (lines 58-94): detect binary, emit `BINARY_FILE` marker, skip `git blame`

2. **`aiscripts/aitask_explain_process_raw_data.py`** — Python processing script
   - Update `parse_raw_data()` (lines 30-88): detect `BINARY_FILE` marker, set `binary: True`
   - Update main processing loop (lines 273-283): skip `aggregate_blame_to_ranges()` for binary files
   - Update `write_yaml()` (lines 219-258): emit `binary: true` in reference.yaml

3. **`tests/test_explain_binary.sh`** — New automated test file

## Reference Files for Patterns

- `tests/test_sed_compat.sh` — Test pattern: assert_eq/assert_contains helpers, PASS/FAIL summary, tmpdir setup/cleanup
- `aiscripts/aitask_explain_extract_raw_data.sh:29` — Existing binary detection pattern: `file -b --mime-encoding "$f" 2>/dev/null | grep -qv 'binary'`

## Implementation Plan

### Step 1: Add `is_binary()` helper to shell script

Insert after line 43 in `aitask_explain_extract_raw_data.sh`:
```bash
is_binary() {
    local filepath="$1"
    file -b --mime-encoding "$filepath" 2>/dev/null | grep -q 'binary'
}
```

### Step 2: Modify `process_file()` to detect binary and skip blame

In `process_file()`, after emitting `=== FILE: ... ===`:
- Check `is_binary "$filepath"`
- If binary: emit `BINARY_FILE` marker, still run commit timeline, skip blame section entirely
- If text: unchanged behavior

New raw_data.txt format for binary files:
```
=== FILE: imgs/logo.png ===

BINARY_FILE

COMMIT_TIMELINE:
1|9961ffe|2026-02-19|Author|chore: Add logo images|

=== END FILE ===
```

### Step 3: Update Python processor

- In `parse_raw_data()`: detect `BINARY_FILE` line, set `is_binary = True` on file dict
- In main loop: skip `aggregate_blame_to_ranges()` for binary files, use empty line_ranges
- In `write_yaml()`: emit `binary: true` field for binary files (omit for text to keep compact)

### Step 4: Write automated tests

Create `tests/test_explain_binary.sh` with 11 test cases covering:
- `is_binary` detection (PNG vs text)
- Shell extraction output for binary files (BINARY_FILE marker, no BLAME_LINES)
- Shell extraction output for text files (BLAME_LINES, no BINARY_FILE)
- Python processor output (binary: true in reference.yaml, empty line_ranges)
- Backward compatibility (old format raw_data.txt without BINARY_FILE marker)
- Mixed files in same extraction run

Test data: `imgs/aitasks_logo_dark_theme.png` (737KB git-tracked PNG)
Text reference: `aiscripts/lib/terminal_compat.sh` (known text file)
Use `AIEXPLAINS_DIR=$tmpdir` to avoid polluting `aiexplains/`

## Verification Steps

1. Run `bash tests/test_explain_binary.sh` — all tests should PASS
2. Manual: `./aiscripts/aitask_explain_extract_raw_data.sh --gather imgs/aitasks_logo_dark_theme.png` — check output format
3. Manual: run on mixed binary + text files, verify both handled correctly
