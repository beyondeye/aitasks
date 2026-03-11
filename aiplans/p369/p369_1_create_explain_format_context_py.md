---
Task: t369_1_create_explain_format_context_py.md
Parent Task: aitasks/t369_aitask_explain_for_aitask_pick.md
Sibling Tasks: aitasks/t369/t369_*_*.md
Archived Sibling Plans: aiplans/archived/p369/p369_*_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Create aitask_explain_format_context.py (t369_1)

## Overview

Create a new Python script at `.aitask-scripts/aitask_explain_format_context.py` that reads reference.yaml files from the aitask-explain pipeline, identifies the most relevant historical plans for a set of target files using a per-file greedy selection algorithm, and outputs formatted markdown with full plan content.

This is the data-processing core of the historical context feature. The shell orchestrator (t369_2) handles cache management and pipeline orchestration, then delegates to this script for the actual data analysis and output formatting.

## Architecture

```
aitask_explain_context.sh (t369_2)
  └── aitask_explain_format_context.py (this script)
        ├── Reads reference.yaml files (YAML parsing)
        ├── Per-file greedy selection (rank plans by line count)
        ├── Cross-file deduplication (union + sort by coverage)
        ├── Plan content extraction (read <run_dir>/plans/p<id>.md)
        └── Formatted markdown output (stdout)
```

## Detailed Implementation Steps

### Step 1: Create the script file

**File:** `.aitask-scripts/aitask_explain_format_context.py`

```python
#!/usr/bin/env python3
"""Format historical context from aitask-explain data for planning.

Reads reference.yaml files from explain pipeline runs, ranks plans by
line contribution to target files, and outputs formatted markdown with
full plan content for agent consumption during planning.

Usage:
    python3 aitask_explain_format_context.py --max-plans N \\
        --ref <ref.yaml>:<run_dir> [--ref ...] \\
        -- <file1> [file2 ...]
"""
import argparse
import os
import re
import sys
from collections import defaultdict

import yaml
```

### Step 2: Implement argument parsing

```python
def parse_args():
    parser = argparse.ArgumentParser(
        description="Format historical context from aitask-explain data"
    )
    parser.add_argument(
        "--max-plans", type=int, required=True,
        help="Maximum number of plans to select per file"
    )
    parser.add_argument(
        "--ref", action="append", required=True,
        help="reference.yaml:run_dir pair (repeatable)"
    )
    parser.add_argument(
        "files", nargs="+",
        help="Target files to get context for"
    )
    return parser.parse_args()
```

Parse each `--ref` value by splitting on `:`. Handle the case where the run_dir path itself contains `:` by splitting only on the first `:`.

### Step 3: Implement reference.yaml loading

```python
def load_references(ref_pairs):
    """Load and return list of (data, run_dir) tuples."""
    refs = []
    for pair in ref_pairs:
        # Split on first colon only
        parts = pair.split(":", 1)
        if len(parts) != 2:
            print(f"Warning: Invalid --ref format: {pair}", file=sys.stderr)
            continue
        ref_path, run_dir = parts
        if not os.path.isfile(ref_path):
            print(f"Warning: reference.yaml not found: {ref_path}", file=sys.stderr)
            continue
        with open(ref_path) as f:
            data = yaml.safe_load(f)
        if data and "files" in data:
            refs.append((data, run_dir))
    return refs
```

### Step 4: Implement per-file line contribution counting

For each target file, find it in the loaded reference data and compute task_id -> line_count:

```python
def compute_line_contributions(refs, target_file):
    """Compute task_id -> total_line_count for a target file across all refs.

    Returns:
        contributions: dict of task_id -> line_count
        source_ref: (data, run_dir) tuple that contains the file, or None
    """
    contributions = defaultdict(int)
    source_ref = None

    for data, run_dir in refs:
        for file_entry in data["files"]:
            if file_entry["path"] == target_file:
                source_ref = (data, run_dir)
                for lr in file_entry.get("line_ranges", []):
                    line_count = lr["end"] - lr["start"] + 1
                    for task_id in lr.get("tasks", []):
                        contributions[str(task_id)] += line_count
                break  # Found in this ref, no need to check others

    return contributions, source_ref
```

### Step 5: Implement greedy plan selection per file

```python
def select_plans_for_file(contributions, max_plans):
    """Select top N plans by line contribution for a single file.

    Returns list of (task_id, line_count) tuples, sorted by line_count desc.
    """
    sorted_tasks = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    return sorted_tasks[:max_plans]
```

### Step 6: Implement cross-file deduplication and sorting

```python
def deduplicate_and_sort(per_file_selections):
    """Combine selections across all files, deduplicate, sort by coverage.

    Args:
        per_file_selections: dict of target_file -> list of (task_id, line_count)

    Returns:
        List of dicts: [{task_id, files: [file1, file2], total_lines}, ...]
        sorted by len(files) desc, then total_lines desc
    """
    task_info = defaultdict(lambda: {"files": [], "total_lines": 0})

    for target_file, selections in per_file_selections.items():
        for task_id, line_count in selections:
            task_info[task_id]["files"].append(target_file)
            task_info[task_id]["total_lines"] += line_count

    result = []
    for task_id, info in task_info.items():
        result.append({
            "task_id": task_id,
            "files": info["files"],
            "total_lines": info["total_lines"],
        })

    result.sort(key=lambda x: (len(x["files"]), x["total_lines"]), reverse=True)
    return result
```

### Step 7: Implement frontmatter stripping

Port from `explain_manager.py:_strip_frontmatter()`:

```python
def strip_frontmatter(content):
    """Remove YAML frontmatter (--- ... ---) from markdown content."""
    if not content.startswith("---"):
        return content
    match = re.match(r"^---\s*\n.*?\n---\s*\n?", content, re.DOTALL)
    if match:
        return content[match.end():]
    return content
```

### Step 8: Implement plan content extraction

```python
def extract_plan_content(task_id, refs):
    """Find and read plan content for a task_id from the run directory.

    Returns:
        (content_str, found_bool)
    """
    for data, run_dir in refs:
        for task_entry in data.get("tasks", []):
            if str(task_entry.get("id", "")) == str(task_id):
                plan_rel = task_entry.get("plan_file", "")
                if plan_rel:
                    plan_path = os.path.join(run_dir, plan_rel)
                    if os.path.isfile(plan_path):
                        with open(plan_path) as f:
                            raw = f.read()
                        return strip_frontmatter(raw), True
                return "", False
    return "", False
```

### Step 9: Implement staleness check

```python
def check_staleness(run_dir):
    """Check if run dir data might be stale based on dir name timestamp.

    Returns "CURRENT" or "STALE (data may be outdated)"
    """
    dir_name = os.path.basename(run_dir)
    # Timestamp is last 15 chars: YYYYMMDD_HHMMSS
    if len(dir_name) >= 15:
        ts_str = dir_name[-15:]
        if len(ts_str) == 15 and ts_str[8] == "_":
            # The shell orchestrator already handles staleness detection
            # and regeneration. If we got here, the data should be current.
            return "CURRENT"
    return "CURRENT"
```

Note: The shell orchestrator (t369_2) handles staleness detection and auto-regenerates stale data before calling this script. So by the time we run, data should be current. Still include a basic check for reporting purposes.

### Step 10: Implement markdown output formatting

```python
def format_output(plan_entries, total_selected, missing_ids):
    """Format the output markdown to stdout."""
    print("## Historical Architectural Context")
    print()

    for entry in plan_entries:
        task_id = entry["task_id"]
        files_str = ", ".join(entry["files"])
        staleness = entry.get("staleness", "CURRENT")

        # Extract title from first heading line of plan content
        title = f"t{task_id}"
        content = entry.get("content", "")
        if content:
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("# "):
                    title = line.lstrip("# ").strip()
                    break

        print(f"### t{task_id}: {title}")
        print(f"**Historical context for:** {files_str}")
        print(f"**Staleness:** {staleness}")
        print()

        if content:
            print(content.strip())
        else:
            print("*(Plan content not available)*")

        print()
        print("---")
        print()

    # Context notes
    found_count = len(plan_entries) - len(missing_ids)
    print("### Context Notes")
    print(f"- Plans sorted by number of affected files (decreasing)")
    if missing_ids:
        missing_str = ", ".join(f"t{mid}" for mid in missing_ids)
        print(f"- {found_count} of {total_selected} plans found; "
              f"{len(missing_ids)} plan(s) missing ({missing_str})")
    else:
        print(f"- {found_count} of {total_selected} plans found")
    print("- Each plan appears once, listing all target files it provides context for")
```

### Step 11: Wire everything together in main()

```python
def main():
    args = parse_args()

    if args.max_plans <= 0:
        sys.exit(0)

    refs = load_references(args.ref)
    if not refs:
        sys.exit(0)

    # Per-file selection
    per_file_selections = {}
    for target_file in args.files:
        contributions, source_ref = compute_line_contributions(refs, target_file)
        if contributions:
            selected = select_plans_for_file(contributions, args.max_plans)
            per_file_selections[target_file] = selected

    if not per_file_selections:
        sys.exit(0)  # No relevant data

    # Deduplicate and sort
    sorted_plans = deduplicate_and_sort(per_file_selections)

    # Extract plan content
    plan_entries = []
    missing_ids = []
    for plan_info in sorted_plans:
        content, found = extract_plan_content(plan_info["task_id"], refs)
        entry = {
            "task_id": plan_info["task_id"],
            "files": plan_info["files"],
            "total_lines": plan_info["total_lines"],
            "content": content,
            "staleness": "CURRENT",
        }
        if not found:
            missing_ids.append(plan_info["task_id"])
        plan_entries.append(entry)

    total_selected = len(sorted_plans)
    format_output(plan_entries, total_selected, missing_ids)
```

### Step 12: Make the script executable

```bash
chmod +x .aitask-scripts/aitask_explain_format_context.py
```

## Testing

1. Create synthetic reference.yaml in a temp dir and run:
   ```bash
   python3 .aitask-scripts/aitask_explain_format_context.py \
       --max-plans 2 --ref /tmp/test/reference.yaml:/tmp/test \
       -- src/foo.py src/bar.py
   ```
2. Verify output format matches the expected markdown structure
3. Test with `--max-plans 1` and verify limiting
4. Test with non-existent files and verify graceful exit

## Step 9: Post-Implementation

Follow `.claude/skills/task-workflow/SKILL.md` Step 9 for cleanup, archival, and merge.
