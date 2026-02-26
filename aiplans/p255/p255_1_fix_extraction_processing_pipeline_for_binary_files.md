---
Task: t255_1_fix_extraction_processing_pipeline_for_binary_files.md
Parent Task: aitasks/t255_support_for_binary_files_in_aiexplains.md
Sibling Tasks: aitasks/t255/t255_2_update_codebrowser_and_skill_for_binary_files.md
Archived Sibling Plans: (none yet)
Worktree: (working on current branch)
Branch: (current branch)
Base branch: main
---

## Plan: Fix extraction + processing pipeline for binary files

### Step 1: Add `is_binary()` helper to shell script

**File:** `aiscripts/aitask_explain_extract_raw_data.sh`

Insert after line 43 (after `expand_path()` function, before `extract_task_id_from_message()`):

```bash
# Check if a file is binary using MIME encoding detection
# Returns 0 (true) if binary, 1 (false) if text
is_binary() {
    local filepath="$1"
    file -b --mime-encoding "$filepath" 2>/dev/null | grep -q 'binary'
}
```

### Step 2: Modify `process_file()` for binary detection

**File:** `aiscripts/aitask_explain_extract_raw_data.sh`

Replace `process_file()` (lines 58-94). Key changes:
- After emitting `=== FILE: ... ===`, check `is_binary "$filepath"`
- If binary: emit `BINARY_FILE` marker line
- Commit timeline section: always run (unchanged)
- Blame lines section: wrap in `if [[ "$file_is_binary" == "false" ]]` — skip entirely for binary

```bash
process_file() {
    local filepath="$1"
    local raw_data_file="$2"

    echo "=== FILE: ${filepath} ===" >> "$raw_data_file"
    echo "" >> "$raw_data_file"

    # Detect binary file
    local file_is_binary=false
    if is_binary "$filepath"; then
        file_is_binary=true
        echo "BINARY_FILE" >> "$raw_data_file"
        echo "" >> "$raw_data_file"
    fi

    # --- Commit Timeline (newest first) --- always extracted
    echo "COMMIT_TIMELINE:" >> "$raw_data_file"
    local timeline_num=0
    while IFS='|' read -r full_hash short_hash date author message; do
        [[ -z "$full_hash" ]] && continue
        timeline_num=$((timeline_num + 1))
        local task_id
        task_id=$(extract_task_id_from_message "$message")
        echo "${timeline_num}|${short_hash}|${date}|${author}|${message}|${task_id}" >> "$raw_data_file"
    done < <(git log --follow --format="%H|%h|%as|%an|%s" --max-count="$MAX_COMMITS" -- "$filepath" 2>/dev/null || true)

    echo "" >> "$raw_data_file"

    # --- Blame Lines (skipped for binary files) ---
    if [[ "$file_is_binary" == "false" ]]; then
        echo "BLAME_LINES:" >> "$raw_data_file"
        local current_hash=""
        while IFS= read -r blame_line; do
            if [[ "$blame_line" =~ ^([0-9a-f]{40})[[:space:]]([0-9]+)[[:space:]]([0-9]+) ]]; then
                current_hash="${BASH_REMATCH[1]}"
                local final_line="${BASH_REMATCH[3]}"
                echo "${final_line}|${current_hash}" >> "$raw_data_file"
            fi
        done < <(git blame --porcelain "$filepath" 2>/dev/null || true)
        echo "" >> "$raw_data_file"
    fi

    echo "=== END FILE ===" >> "$raw_data_file"
    echo "" >> "$raw_data_file"
}
```

### Step 3: Update Python processor — parse_raw_data()

**File:** `aiscripts/aitask_explain_process_raw_data.py`

In the FILE block parsing loop (inside `parse_raw_data()`):
- Initialize `is_binary = False` alongside other variables
- Add `elif line == 'BINARY_FILE': is_binary = True` in the section detection
- Include `'binary': is_binary` in the appended file dict

### Step 4: Update Python processor — main loop

**File:** `aiscripts/aitask_explain_process_raw_data.py`

In the `main()` function's processing loop:
```python
if file_info.get('binary', False):
    line_ranges = []
else:
    line_ranges = aggregate_blame_to_ranges(
        file_info['blame_lines'],
        file_info['commits'],
    )
files_data.append({
    'path': file_info['path'],
    'commits': file_info['commits'],
    'line_ranges': line_ranges,
    'binary': file_info.get('binary', False),
})
```

### Step 5: Update Python processor — write_yaml()

**File:** `aiscripts/aitask_explain_process_raw_data.py`

After writing `path:` line, add binary flag:
```python
if file_data.get('binary', False):
    f.write('    binary: true\n')
```

### Step 6: Write automated tests

**File:** `tests/test_explain_binary.sh` (new)

Test cases using `imgs/aitasks_logo_dark_theme.png` as binary test data and `aiscripts/lib/terminal_compat.sh` as text reference. Use `AIEXPLAINS_DIR=$tmpdir` for isolation.

11 test cases covering:
1. `is_binary` detection for PNG
2. `is_binary` detection for text file (should NOT be binary)
3. Binary file → raw_data.txt contains `BINARY_FILE` marker
4. Binary file → raw_data.txt contains `COMMIT_TIMELINE:`
5. Binary file → raw_data.txt does NOT contain `BLAME_LINES:`
6. Text file → raw_data.txt contains `BLAME_LINES:`
7. Text file → raw_data.txt does NOT contain `BINARY_FILE`
8. Binary file → reference.yaml contains `binary: true`
9. Binary file → reference.yaml has no line_range entries after `line_ranges:`
10. Backward compat: old format raw_data.txt → valid reference.yaml without `binary:`
11. Mixed binary + text in same run → correct markers for each

### Step 7: Run tests and verify

```bash
bash tests/test_explain_binary.sh
```

All 11 tests should PASS.

## Final Implementation Notes

- **Actual work done:** Implemented all 7 steps as planned. Added `is_binary()` helper to shell script, modified `process_file()` to emit `BINARY_FILE` marker and skip blame for binary files, updated Python processor (`parse_raw_data()`, main loop, `write_yaml()`) to handle binary flag, and wrote comprehensive tests.
- **Deviations from plan:** Test file ended up with 15 assertions instead of the planned 11, due to some tests covering multiple assertions (e.g., mixed mode tests assert both binary and text properties). Also needed `grep -qF --` (with `--` separator) in test helpers to handle patterns starting with `-`.
- **Issues encountered:** Initial test sourced the shell script which triggered `main()` execution — fixed by defining `is_binary()` directly in the test. Also hit `grep` interpreting `"- start:"` as an option flag — fixed by adding `--` before the pattern.
- **Key decisions:** Binary files still get their full `COMMIT_TIMELINE` extracted (useful for knowing when images were added/changed). Only `BLAME_LINES` section is skipped. The `binary: true` field is only emitted for binary files (not `binary: false` for text) to keep YAML compact and backward-compatible.
- **Notes for sibling tasks (t255_2):** The `binary: true` field appears right after `path:` in reference.yaml. When `binary: true`, `line_ranges:` section is empty (no entries). `commits:` section is always populated. The `FileExplainData` consumer should check for this field and skip annotation building. Old reference.yaml files (without `binary:` field) are backward-compatible — all files default to non-binary.

## Post-implementation

Refer to Step 9 of the task-workflow (archival, merge, cleanup).
