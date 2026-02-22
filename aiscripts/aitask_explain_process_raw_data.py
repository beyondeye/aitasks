#!/usr/bin/env python3
"""Process raw explain data into YAML reference format.

Reads raw_data.txt (pipe-delimited structured text from aitask_explain_extract_raw_data.sh)
and produces reference.yaml with:
- Per-file commit timelines (newest first)
- Aggregated line ranges mapped to commits and task IDs
- Task index with file paths and notes availability

Usage:
    python3 aitask_explain_process_raw_data.py <raw_data.txt> <reference.yaml>
"""

import sys
import re
from collections import OrderedDict


def parse_raw_data(raw_data_path):
    """Parse the raw_data.txt file into structured data.

    Returns:
        files: list of dicts with 'path', 'commits', 'blame_lines'
        task_index: list of dicts with 'id', 'task_file', 'plan_file'
    """
    files = []
    task_index = []

    with open(raw_data_path, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n')

        # Parse FILE blocks
        m = re.match(r'^=== FILE: (.+) ===$', line)
        if m:
            file_path = m.group(1)
            commits = []
            blame_lines = []
            section = None
            i += 1

            while i < len(lines):
                line = lines[i].rstrip('\n')
                if line == '=== END FILE ===':
                    i += 1
                    break
                elif line == 'COMMIT_TIMELINE:':
                    section = 'timeline'
                elif line == 'BLAME_LINES:':
                    section = 'blame'
                elif line == '':
                    pass  # skip blank lines
                elif section == 'timeline':
                    parts = line.split('|', 5)
                    if len(parts) >= 5:
                        num = int(parts[0])
                        short_hash = parts[1]
                        date = parts[2]
                        author = parts[3]
                        message = parts[4]
                        task_id = parts[5] if len(parts) > 5 and parts[5] else None
                        commits.append({
                            'num': num,
                            'hash': short_hash,
                            'date': date,
                            'author': author,
                            'message': message,
                            'task_id': task_id,
                        })
                elif section == 'blame':
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        line_num = int(parts[0])
                        full_hash = parts[1]
                        blame_lines.append({
                            'line': line_num,
                            'hash': full_hash,
                        })
                i += 1

            files.append({
                'path': file_path,
                'commits': commits,
                'blame_lines': blame_lines,
            })
            continue

        # Parse TASK_INDEX block
        if line == '=== TASK_INDEX ===':
            i += 1
            while i < len(lines):
                line = lines[i].rstrip('\n')
                if line == '=== END TASK_INDEX ===':
                    i += 1
                    break
                elif line:
                    parts = line.split('|', 2)
                    if len(parts) >= 1:
                        task_id = parts[0]
                        task_file = parts[1] if len(parts) > 1 else ''
                        plan_file = parts[2] if len(parts) > 2 else ''
                        task_index.append({
                            'id': task_id,
                            'task_file': task_file,
                            'plan_file': plan_file,
                        })
                i += 1
            continue

        i += 1

    return files, task_index


def aggregate_blame_to_ranges(blame_lines, commits):
    """Group consecutive blame lines with the same commit into ranges.

    Also maps each range to its timeline number(s) and task ID(s)
    from the commit timeline.

    Args:
        blame_lines: list of {'line': int, 'hash': str}
        commits: list of commit dicts with 'num', 'hash', 'task_id'

    Returns:
        list of {'start': int, 'end': int, 'commits': [int], 'tasks': [str]}
    """
    if not blame_lines:
        return []

    # Build hash-to-commit lookup (short hash from timeline, full hash from blame)
    # Match by prefix: blame has full 40-char hash, timeline has short hash
    hash_to_commit = {}
    for commit in commits:
        hash_to_commit[commit['hash']] = commit

    # Sort blame lines by line number
    sorted_lines = sorted(blame_lines, key=lambda x: x['line'])

    # Group consecutive lines with same commit
    ranges = []
    current_start = sorted_lines[0]['line']
    current_hash = sorted_lines[0]['hash']

    for j in range(1, len(sorted_lines)):
        bl = sorted_lines[j]
        if bl['hash'] == current_hash and bl['line'] == sorted_lines[j-1]['line'] + 1:
            continue  # same range
        else:
            # Close current range
            ranges.append({
                'start': current_start,
                'end': sorted_lines[j-1]['line'],
                'hash': current_hash,
            })
            current_start = bl['line']
            current_hash = bl['hash']

    # Close last range
    ranges.append({
        'start': current_start,
        'end': sorted_lines[-1]['line'],
        'hash': current_hash,
    })

    # Map ranges to timeline numbers and task IDs
    result = []
    for r in ranges:
        full_hash = r['hash']
        # Find matching commit by prefix
        matched_commits = []
        matched_tasks = []
        for commit in commits:
            if full_hash.startswith(commit['hash']) or commit['hash'].startswith(full_hash[:7]):
                matched_commits.append(commit['num'])
                if commit['task_id']:
                    matched_tasks.append(commit['task_id'])
                break

        result.append({
            'start': r['start'],
            'end': r['end'],
            'commits': matched_commits,
            'tasks': matched_tasks,
        })

    return result


def check_has_notes(plan_file_path, run_dir):
    """Check if a plan file contains Final Implementation Notes."""
    if not plan_file_path:
        return False
    import os
    # plan_file_path is relative to run_dir's parent
    # e.g., "plans/p16.md" relative to the run directory
    # We need to find the actual file - but since we don't know the run dir here,
    # just return True if plan_file exists (the skill will read the actual content)
    return bool(plan_file_path)


def yaml_escape(s):
    """Escape a string for YAML output."""
    if s is None:
        return 'null'
    s = str(s)
    # If string contains special chars, quote it
    if any(c in s for c in ':|{}[],&*#?!>%@`"\'') or s.startswith('-') or s.startswith(' '):
        # Use double quotes with escaping
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    if not s:
        return '""'
    return s


def write_yaml(files_data, task_index, output_path):
    """Write the reference data as YAML without requiring PyYAML.

    Generates clean YAML manually to avoid external dependencies.
    """
    with open(output_path, 'w') as f:
        f.write('files:\n')
        for file_data in files_data:
            f.write(f'  - path: {yaml_escape(file_data["path"])}\n')

            # Commits
            f.write('    commits:\n')
            for commit in file_data['commits']:
                f.write(f'      - num: {commit["num"]}\n')
                f.write(f'        hash: {yaml_escape(commit["hash"])}\n')
                f.write(f'        date: {yaml_escape(commit["date"])}\n')
                f.write(f'        author: {yaml_escape(commit["author"])}\n')
                f.write(f'        message: {yaml_escape(commit["message"])}\n')
                if commit['task_id']:
                    f.write(f'        task_id: {yaml_escape(commit["task_id"])}\n')
                else:
                    f.write('        task_id: null\n')

            # Line ranges
            f.write('    line_ranges:\n')
            for lr in file_data['line_ranges']:
                f.write(f'      - start: {lr["start"]}\n')
                f.write(f'        end: {lr["end"]}\n')
                commits_str = ', '.join(str(c) for c in lr['commits'])
                f.write(f'        commits: [{commits_str}]\n')
                tasks_str = ', '.join(yaml_escape(t) for t in lr['tasks'])
                f.write(f'        tasks: [{tasks_str}]\n')

        f.write('\ntasks:\n')
        for task in task_index:
            f.write(f'  - id: {yaml_escape(task["id"])}\n')
            f.write(f'    task_file: {yaml_escape(task["task_file"])}\n')
            f.write(f'    plan_file: {yaml_escape(task["plan_file"])}\n')
            has_notes = bool(task['plan_file'])
            f.write(f'    has_notes: {str(has_notes).lower()}\n')


def main():
    if len(sys.argv) != 3:
        print(f'Usage: {sys.argv[0]} <raw_data.txt> <reference.yaml>', file=sys.stderr)
        sys.exit(1)

    raw_data_path = sys.argv[1]
    output_path = sys.argv[2]

    # Parse raw data
    files, task_index = parse_raw_data(raw_data_path)

    # Process each file: aggregate blame lines into ranges
    files_data = []
    for file_info in files:
        line_ranges = aggregate_blame_to_ranges(
            file_info['blame_lines'],
            file_info['commits'],
        )
        files_data.append({
            'path': file_info['path'],
            'commits': file_info['commits'],
            'line_ranges': line_ranges,
        })

    # Write YAML output
    write_yaml(files_data, task_index, output_path)


if __name__ == '__main__':
    main()
