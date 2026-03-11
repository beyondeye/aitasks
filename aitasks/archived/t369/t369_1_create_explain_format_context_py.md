---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitask_explain, aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-11 18:33
updated_at: 2026-03-12 00:01
completed_at: 2026-03-12 00:01
---

Create aitask_explain_format_context.py - Python helper that reads reference.yaml files, performs per-file greedy plan selection, deduplicates across files, and outputs formatted markdown with full plan content.

## Context

The parent task t369 integrates the aitask-explain data (which maps code lines to tasks/plans via git blame) into the aitask-pick workflow. When an agent picks a task, it currently lacks historical context about WHY existing code was designed the way it is. The aitask-explain system already maps `file lines -> commits -> tasks -> plans` via git blame, but this data is only accessible through the codebrowser TUI or the manual `/aitask-explain` skill.

This child task creates the Python component that reads the existing `reference.yaml` data format (produced by the explain pipeline), identifies which historical plans are most relevant to a set of target files, and outputs formatted markdown containing those plans. This is the data-processing core that the shell orchestrator (t369_2) will call.

## Key Files to Modify

- **`.aitask-scripts/aitask_explain_format_context.py`** (NEW) — The main deliverable. Python script that reads reference.yaml, ranks plans by line contribution, and outputs formatted markdown.

## Reference Files for Patterns

- **`.aitask-scripts/aitask_explain_process_raw_data.py`** — Shows the existing pattern for Python scripts in this project: stdlib-only (no PyYAML for writing, custom `yaml_escape()`), reads structured data, produces output. Uses `sys.argv` for CLI args. Note: this script avoids PyYAML for writing but the new script CAN use PyYAML for reading since it is already a dependency of the codebrowser.
- **`.aitask-scripts/codebrowser/explain_manager.py`** — Contains `parse_reference_yaml()` (line 146) showing the exact YAML structure: `files[].path`, `files[].line_ranges[].start/end/tasks[]`, `tasks[].id/task_file/plan_file`. Also contains `_strip_frontmatter()` (line 374) for removing YAML frontmatter from plan markdown.
- **`.aitask-scripts/aitask_explain_extract_raw_data.sh`** — Shows how run directories are structured: `<run_dir>/reference.yaml`, `<run_dir>/plans/p<id>.md`, `<run_dir>/tasks/t<id>.md`.

## Implementation Plan

### Step 1: Create the script file with shebang and docstring

Create `.aitask-scripts/aitask_explain_format_context.py` with:
```python
#!/usr/bin/env python3
"""Format historical context from aitask-explain data for planning.

Reads reference.yaml files from explain pipeline runs, ranks plans by
line contribution to target files, and outputs formatted markdown with
full plan content for agent consumption during planning.

Usage:
    python3 aitask_explain_format_context.py --max-plans N \
        --ref <ref.yaml>:<run_dir> [--ref <ref.yaml>:<run_dir> ...] \
        -- <file1> [file2 ...]
"""
```

### Step 2: Implement YAML parsing

Use PyYAML (`yaml.safe_load`) to read reference.yaml files. Parse the structure:
- `data["files"]` — list of file entries with `path`, `line_ranges`
- `data["tasks"]` — task index with `id`, `plan_file`, `task_file`

For each file entry, extract:
- `file_entry["path"]` — the file path
- `file_entry["line_ranges"]` — list of `{start, end, tasks: [task_id, ...]}`

### Step 3: Implement per-file line contribution counting

For each target file provided on the command line:
1. Find matching file entry in reference.yaml (by path)
2. For each `line_range` in that file, compute `line_count = end - start + 1`
3. Distribute that line count to each `task_id` in the range's `tasks` list
4. Sum across all ranges to get `task_id -> total_lines_contributed` for this file

### Step 4: Implement per-file greedy plan selection

For each target file:
1. Sort task_ids by `total_lines_contributed` descending
2. Take the top N (from `--max-plans`)
3. Store as `{task_id: lines_contributed}` per file

### Step 5: Implement cross-file deduplication and sorting

1. Union all selected task_ids across all target files
2. For each task_id: record which target files selected it and total line count across all files
3. Sort by: number of affected target files (descending), then by total line count (descending)

### Step 6: Implement plan content extraction

For each selected task_id (in sorted order):
1. Look up `plan_file` from the tasks index in reference.yaml
2. Construct path: `<run_dir>/<plan_file>` (e.g., `<run_dir>/plans/p166.md`)
3. Read the file, strip YAML frontmatter (reuse the `_strip_frontmatter` pattern from explain_manager.py: match `^---\s*\n.*?\n---\s*\n?` with re.DOTALL)
4. Track missing plans (plan_file empty or file not found)

### Step 7: Implement staleness indicator

For each selected plan:
- Read the commit dates from `reference.yaml`'s commit timeline for the relevant files
- Compare the most recent commit date against the run directory timestamp (parsed from dir name)
- Mark as `CURRENT` or `STALE (newer commits exist)`

### Step 8: Implement markdown output formatting

Output to stdout in this format:
```markdown
## Historical Architectural Context

### t166: <task title from first line of plan or task_id>
**Historical context for:** file1.py, file2.py
**Staleness:** CURRENT

<full plan content, frontmatter stripped>

---

### t209: <task title>
**Historical context for:** file1.py
**Staleness:** CURRENT

<full plan content>

---

### Context Notes
- Plans sorted by number of affected files (decreasing)
- N of M plans found; K plan(s) missing (list missing IDs)
- Each plan appears once, listing all target files it provides context for
```

### Step 9: Implement CLI argument parsing

Use `argparse` with:
- `--max-plans N` (required, int) — max plans per file for greedy selection
- `--ref REF_YAML:RUN_DIR` (required, repeatable) — colon-separated reference.yaml path and run directory
- Positional `files` — target files after `--`

### Step 10: Wire everything together in `main()`

1. Parse args
2. For each `--ref` pair, load reference.yaml
3. For each target file, find its reference.yaml (by checking which ref contains the file's path)
4. Run per-file selection, deduplication, plan extraction
5. Output formatted markdown
6. Exit 0 on success, exit 1 on fatal errors, exit 0 with empty output if no relevant data

## Verification Steps

1. **Unit test with synthetic data**: Create a temporary reference.yaml with known structure, run the script, verify output contains expected plan headers and content
2. **Test with real codebrowser data**: If `.aitask-explain/codebrowser/` has cached data, run against real files and verify output is well-formed markdown
3. **Test --max-plans limiting**: Verify that `--max-plans 1` produces at most 1 plan per file (may produce more total if different files select different plans)
4. **Test missing plans**: Verify graceful handling when plan files referenced in reference.yaml don't exist
5. **Test no matching files**: Verify empty output (no error) when target files aren't found in any reference.yaml
6. **Shellcheck-adjacent**: Verify the script runs with `python3` and requires only stdlib + PyYAML
