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


def load_references(ref_pairs):
    """Load and return list of (data, run_dir) tuples."""
    refs = []
    for pair in ref_pairs:
        # Split on first colon only (run_dir path may contain colons)
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


def select_plans_for_file(contributions, max_plans):
    """Select top N plans by line contribution for a single file.

    Returns list of (task_id, line_count) tuples, sorted by line_count desc.
    """
    sorted_tasks = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    return sorted_tasks[:max_plans]


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


def strip_frontmatter(content):
    """Remove YAML frontmatter (--- ... ---) from markdown content."""
    if not content.startswith("---"):
        return content
    match = re.match(r"^---\s*\n.*?\n---\s*\n?", content, re.DOTALL)
    if match:
        return content[match.end():]
    return content


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


def format_output(plan_entries, total_selected, missing_ids):
    """Format the output markdown to stdout."""
    print("## Historical Architectural Context")
    print()

    for entry in plan_entries:
        task_id = entry["task_id"]
        files_str = ", ".join(entry["files"])

        # Extract title from first heading line of plan content
        title = f"t{task_id}"
        content = entry.get("content", "")
        if content:
            for line in content.splitlines():
                line_stripped = line.strip()
                if line_stripped.startswith("# "):
                    title = line_stripped.lstrip("# ").strip()
                    break

        print(f"### t{task_id}: {title}")
        print(f"**Historical context for:** {files_str}")
        print(f"**Staleness:** CURRENT")
        print()

        if content:
            print(content.strip())
        else:
            print("*(Plan content not available)*")

        print()
        print("---")
        print()

    # Context notes
    found_count = total_selected - len(missing_ids)
    print("### Context Notes")
    print("- Plans sorted by number of affected files (decreasing)")
    if missing_ids:
        missing_str = ", ".join(f"t{mid}" for mid in missing_ids)
        print(f"- {found_count} of {total_selected} plans found; "
              f"{len(missing_ids)} plan(s) missing ({missing_str})")
    else:
        print(f"- {found_count} of {total_selected} plans found")
    print("- Each plan appears once, listing all target files it provides context for")


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
        contributions, _source_ref = compute_line_contributions(refs, target_file)
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
        }
        if not found:
            missing_ids.append(plan_info["task_id"])
        plan_entries.append(entry)

    total_selected = len(sorted_plans)
    format_output(plan_entries, total_selected, missing_ids)


if __name__ == "__main__":
    main()
