---
Task: t433_5_v2_archive_scanners.md
Parent Task: aitasks/t433_refactor_task_archives.md
Sibling Tasks: aitasks/t433/t433_*_*.md
Worktree: (none — current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan: V2 Archive Scanners

### Goal

Create two libraries consolidating archive-scanning logic:
1. `.aitask-scripts/lib/archive_scan_v2.sh` -- bash scanner functions
2. `.aitask-scripts/lib/archive_iter_v2.py` -- Python iterator for `aitask_stats.py`

These replace the scattered tar.gz scanning in `aitask_claim_id.sh` (lines 60-66),
`aitask_query_files.sh` (lines 138-144), and `aitask_stats.py` (lines 599-612).

### Dependencies

- **t433_1** (archive_utils_v2.sh) must be complete -- provides `archive_bundle()`,
  `archive_dir()`, `archive_path_for_id()`, `_search_tar_gz_v2()`,
  `_extract_from_tar_gz_v2()`

### Step 1: Create shell library scaffold

**File:** `.aitask-scripts/lib/archive_scan_v2.sh`

```bash
#!/usr/bin/env bash
# archive_scan_v2.sh - Archive scanning functions for numbered archives
# Source this file from aitask scripts; do not execute directly.
#
# Provides:
#   scan_max_task_id_v2()       - find highest task ID across all locations
#   search_archived_task_v2()   - find a specific task in archives
#   iter_all_archived_files_v2() - iterate all files in all archives

# --- Guard against double-sourcing ---
[[ -n "${_AIT_ARCHIVE_SCAN_V2_LOADED:-}" ]] && return 0
_AIT_ARCHIVE_SCAN_V2_LOADED=1

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
# shellcheck source=archive_utils_v2.sh
source "${SCRIPT_DIR}/lib/archive_utils_v2.sh"
```

### Step 2: Implement scan_max_task_id_v2()

This replaces `scan_max_task_id()` from `aitask_claim_id.sh`. The key difference is
iterating all `_bN/oldM.tar.gz` files instead of a single `old.tar.gz`.

```bash
# Find the highest task number across all task locations.
# Args: $1=task_dir, $2=archived_dir
# Output: integer (max task ID, or 0 if no tasks found)
scan_max_task_id_v2() {
    local task_dir="$1"
    local archived_dir="$2"
    local max_num=0
    local num

    # Active tasks
    if ls "$task_dir"/t*_*.md &>/dev/null; then
        for f in "$task_dir"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Active child tasks
    if ls "$task_dir"/t*/t*_*.md &>/dev/null; then
        for f in "$task_dir"/t*/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Archived loose tasks (parents)
    if ls "$archived_dir"/t*_*.md &>/dev/null; then
        for f in "$archived_dir"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Archived loose tasks (children)
    if ls "$archived_dir"/t*/t*_*.md &>/dev/null; then
        for f in "$archived_dir"/t*/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Numbered archives (_bN/oldM.tar.gz)
    for archive in "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(tar -tzf "$archive" 2>/dev/null | grep -E 't[0-9]+')
    done

    # Legacy old.tar.gz fallback
    if [[ -f "$archived_dir/old.tar.gz" ]]; then
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(tar -tzf "$archived_dir/old.tar.gz" 2>/dev/null | grep -E 't[0-9]+')
    fi

    echo "$max_num"
}
```

**Design notes:**
- Accepts `task_dir` and `archived_dir` as parameters (not globals) for testability
- Scans child task directories too (`t*/t*_*.md`) since child task parent numbers may
  exceed any standalone parent task number
- The numbered archive glob `_b*/old*.tar.gz` naturally includes all bundles
- Legacy fallback is last to avoid double-counting files that exist in both

### Step 3: Implement search_archived_task_v2()

This replaces the tar.gz block in `cmd_archived_task()` from `aitask_query_files.sh`.

```bash
# Search for a specific task number in archives (numbered then legacy fallback).
# Uses O(1) lookup via archive_path_for_id when task number is known.
# Args: $1=task_num (numeric, e.g., "150"), $2=archived_dir
# Output: "ARCHIVED_TASK_TAR_GZ:<archive_path>:<match>" or "NOT_FOUND"
search_archived_task_v2() {
    local num="$1"
    local archived_dir="$2"
    local pattern="(^|/)t${num}_.*\.md$"

    # O(1) lookup: compute the exact archive for this task number
    local archive_path
    archive_path=$(archive_path_for_id "$num" "$archived_dir")
    if [[ -f "$archive_path" ]]; then
        local tar_match
        tar_match=$(_search_tar_gz_v2 "$archive_path" "$pattern")
        if [[ -n "$tar_match" ]]; then
            echo "ARCHIVED_TASK_TAR_GZ:${archive_path}:${tar_match}"
            return
        fi
    fi

    # Fallback: legacy old.tar.gz
    local legacy_path="${archived_dir}/old.tar.gz"
    if [[ -f "$legacy_path" ]]; then
        local tar_match
        tar_match=$(_search_tar_gz_v2 "$legacy_path" "$pattern")
        if [[ -n "$tar_match" ]]; then
            echo "ARCHIVED_TASK_TAR_GZ:${legacy_path}:${tar_match}"
            return
        fi
    fi

    echo "NOT_FOUND"
}
```

**Design notes:**
- Returns a structured string `ARCHIVED_TASK_TAR_GZ:<path>:<match>` matching the
  existing convention in `aitask_query_files.sh`
- Includes archive path in the output so the caller knows which archive to extract from
- The O(1) lookup means we check at most 2 archive files (numbered + legacy) instead
  of scanning all archives

### Step 4: Implement iter_all_archived_files_v2()

General-purpose iterator for completeness. Most callers will use the targeted functions above.

```bash
# Iterate all files across all numbered archives and legacy archive.
# Args: $1=archived_dir, $2=callback_cmd
#   callback_cmd is invoked as: $callback_cmd "$archive_path" "$filename_in_tar"
# Returns: 0 on success
iter_all_archived_files_v2() {
    local archived_dir="$1"
    local callback_cmd="$2"

    # Numbered archives (sorted for deterministic order)
    local archive
    for archive in $(ls "$archived_dir"/_b*/old*.tar.gz 2>/dev/null | sort); do
        [[ -f "$archive" ]] || continue
        while IFS= read -r entry; do
            [[ -z "$entry" || "$entry" == "." || "$entry" == "./" ]] && continue
            # Skip directory entries
            [[ "$entry" == */ ]] && continue
            "$callback_cmd" "$archive" "$entry"
        done < <(tar -tzf "$archive" 2>/dev/null)
    done

    # Legacy archive
    if [[ -f "$archived_dir/old.tar.gz" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" || "$entry" == "." || "$entry" == "./" ]] && continue
            [[ "$entry" == */ ]] && continue
            "$callback_cmd" "$archived_dir/old.tar.gz" "$entry"
        done < <(tar -tzf "$archived_dir/old.tar.gz" 2>/dev/null)
    fi
}
```

### Step 5: ShellCheck validation

```bash
shellcheck .aitask-scripts/lib/archive_scan_v2.sh
```

Common issues to fix:
- SC2155: split `local` and assignment (already handled in step 2-4 code above)
- SC2086: ensure all `$num`, `$archive`, `$entry` are double-quoted
- SC2013: the `for archive in $(ls ...)` in step 4 -- rewrite as glob if shellcheck
  complains (use `while IFS= read -r archive` with `find` or just glob directly)

### Step 6: Create Python library

**File:** `.aitask-scripts/lib/archive_iter_v2.py`

```python
"""archive_iter_v2.py - Python archive iteration for numbered archive scheme.

Provides iterator functions that yield (filename, text_content) tuples from
numbered _bN/oldM.tar.gz archives and legacy old.tar.gz.

Usage:
    from archive_iter_v2 import iter_all_archived_tar_files
    for name, content in iter_all_archived_tar_files(Path("aitasks/archived")):
        process(name, content)
"""

import os
import tarfile
from pathlib import Path
from typing import Iterable, Tuple


def archive_path_for_id(task_id: int, archived_dir: Path) -> Path:
    """Compute the numbered archive path for a given task ID."""
    bundle = task_id // 100
    dir_num = bundle // 10
    return archived_dir / f"_b{dir_num}" / f"old{bundle}.tar.gz"


def iter_numbered_archives(archived_dir: Path) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from all numbered archives."""
    for bdir in sorted(archived_dir.glob("_b*")):
        if not bdir.is_dir():
            continue
        for archive in sorted(bdir.glob("old*.tar.gz")):
            yield from _iter_single_archive(archive)


def iter_legacy_archive(archived_dir: Path) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from legacy old.tar.gz if it exists."""
    legacy = archived_dir / "old.tar.gz"
    if legacy.exists():
        yield from _iter_single_archive(legacy)


def iter_all_archived_tar_files(
    archived_dir: Path,
) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from all archives (numbered + legacy).

    This is the direct replacement for the ARCHIVE_TAR block in
    aitask_stats.py iter_archived_markdown_files().
    """
    yield from iter_numbered_archives(archived_dir)
    yield from iter_legacy_archive(archived_dir)


def _iter_single_archive(archive_path: Path) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) for .md files in a single tar.gz."""
    try:
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                if not member.isfile() or not member.name.endswith(".md"):
                    continue
                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                raw = extracted.read()
                text = raw.decode("utf-8", errors="replace")
                yield os.path.basename(member.name), text
    except (tarfile.TarError, OSError):
        return
```

### Step 7: Python module verification

```bash
cd /path/to/project
python -c "
import sys; sys.path.insert(0, '.aitask-scripts/lib')
from archive_iter_v2 import archive_path_for_id, iter_all_archived_tar_files
from pathlib import Path
# Test path computation
p = archive_path_for_id(150, Path('aitasks/archived'))
assert str(p) == 'aitasks/archived/_b0/old1.tar.gz', f'Got: {p}'
p = archive_path_for_id(1050, Path('aitasks/archived'))
assert str(p) == 'aitasks/archived/_b1/old10.tar.gz', f'Got: {p}'
print('Python module OK')
"
```

### Step 8: Manual integration test (shell)

```bash
# Create test environment
tmpdir=$(mktemp -d)
mkdir -p "$tmpdir/aitasks/archived/_b0"
mkdir -p "$tmpdir/aitasks"

# Create test task files
echo "task 50 content" > "$tmpdir/aitasks/t50_test.md"
staging=$(mktemp -d)
echo "task 150 archived" > "$staging/t150_archived.md"
tar -czf "$tmpdir/aitasks/archived/_b0/old1.tar.gz" -C "$staging" .
rm -rf "$staging"

# Test scan_max_task_id_v2
bash -c "
  SCRIPT_DIR=.aitask-scripts
  source .aitask-scripts/lib/archive_scan_v2.sh
  result=\$(scan_max_task_id_v2 '$tmpdir/aitasks' '$tmpdir/aitasks/archived')
  echo \"Max task ID: \$result\"
  [[ \"\$result\" == '150' ]] && echo PASS || echo FAIL
"

# Test search_archived_task_v2
bash -c "
  SCRIPT_DIR=.aitask-scripts
  source .aitask-scripts/lib/archive_scan_v2.sh
  result=\$(search_archived_task_v2 '150' '$tmpdir/aitasks/archived')
  echo \"Search result: \$result\"
  echo \"\$result\" | grep -q 'ARCHIVED_TASK_TAR_GZ' && echo PASS || echo FAIL
"

rm -rf "$tmpdir"
```

### Step 9: Final Implementation Notes

- **Actual files created/modified:**
  - `.aitask-scripts/lib/archive_scan_v2.sh` (~145 lines) — shell scanner library with guard variable, `scan_max_task_id_v2()`, `search_archived_task_v2()`, and `iter_all_archived_files_v2()`
  - `.aitask-scripts/lib/archive_iter_v2.py` (~65 lines) — Python iterator module with `archive_path_for_id()`, `iter_numbered_archives()`, `iter_legacy_archive()`, `iter_all_archived_tar_files()`, and `_iter_single_archive()`
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** None. ShellCheck clean (only SC1091 info for sourced files, same as all other project scripts). All manual integration tests pass. All 42 existing archive_utils_v2 tests pass.
- **ShellCheck result:** Clean (SC1091 info-level only, same as other scripts)
- **Key decisions:** Used explicit `task_dir` and `archived_dir` parameters (not globals) for testability. Shell glob iteration for numbered archives (`_b*/old*.tar.gz`) naturally sorts alphabetically. Python module uses `sorted()` on glob results for deterministic iteration.
- **Notes for sibling tasks:** Both libraries are ready. Shell: `source "${SCRIPT_DIR}/lib/archive_scan_v2.sh"` provides all scanner functions. Python: `from archive_iter_v2 import iter_all_archived_tar_files` is the drop-in replacement for the `ARCHIVE_TAR` block in `aitask_stats.py`. The `search_archived_task_v2()` output format (`ARCHIVED_TASK_TAR_GZ:<path>:<match>`) matches the convention in `aitask_query_files.sh`. For t433_6 (integration tests), the shell functions accept explicit directory parameters making them easy to test with temp directories. The correct `archive_path_for_id` argument order is `(task_id, archived_dir)` — consistent with t433_3's notes.
