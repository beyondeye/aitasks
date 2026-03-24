---
Task: t448_1_consolidate_archive_iter_and_history_data_layer.md
Parent Task: aitasks/t448_archived_tasks_in_board.md
Sibling Tasks: aitasks/t448/t448_2_*.md, aitasks/t448/t448_3_*.md
Worktree: (none)
Branch: main
Base branch: main
---

# Plan: Consolidate archive iteration + history data layer

## Part A: Consolidate `archive_iter.py`

### Step 1: Add `iter_all_archived_markdown()` to `archive_iter.py`

File: `.aitask-scripts/lib/archive_iter.py`

Add a new function after the existing ones:

```python
def iter_all_archived_markdown(
    archived_dir: Path,
) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from loose files + numbered archives.

    Scans in order: loose parent files, loose child files (in subdirs),
    then numbered tar.gz archives. Does NOT scan legacy old.tar.gz.
    """
    if archived_dir.exists():
        # Loose parent tasks
        for path in sorted(archived_dir.glob("t*_*.md")):
            # Skip child-pattern files at top level (shouldn't exist, but guard)
            if _is_child_filename(path.name):
                continue
            try:
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        # Loose child tasks in subdirectories
        for path in sorted(archived_dir.glob("t*/t*_*_*.md")):
            try:
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    # Numbered archives only (no legacy)
    yield from iter_numbered_archives(archived_dir)


def _is_child_filename(name: str) -> bool:
    """Check if filename matches child task pattern t<N>_<M>_*.md."""
    import re
    return bool(re.match(r't\d+_\d+_', name))
```

### Step 2: Add `iter_archived_frontmatter()` to `archive_iter.py`

```python
def iter_archived_frontmatter(
    archived_dir: Path,
    parse_fn,
) -> Iterable[Tuple[str, dict]]:
    """Yield (filename, metadata_dict) using parse_fn on frontmatter only.

    parse_fn should accept a string (full file text) and return a dict
    of metadata (the YAML frontmatter). This avoids loading full body content.
    """
    for name, text in iter_all_archived_markdown(archived_dir):
        try:
            metadata = parse_fn(text)
            if metadata is not None:
                yield name, metadata
        except Exception:
            continue
```

### Step 3: Refactor `aitask_stats.py`

File: `.aitask-scripts/aitask_stats.py`

Replace lines 588-606:
```python
def iter_archived_markdown_files() -> Iterable[Tuple[str, str]]:
    return iter_all_archived_markdown(ARCHIVE_DIR)
```

Ensure the import at the top includes `iter_all_archived_markdown`:
```python
from archive_iter import iter_all_archived_tar_files, iter_all_archived_markdown
```

### Step 4: Verify `ait stats` still works

Run `ait stats` and compare output before/after the refactor.

---

## Part B: History Data Layer

### Step 5: Create `history_data.py`

File: `.aitask-scripts/codebrowser/history_data.py`

**Imports and path setup:**
```python
import os, sys, re, subprocess, json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Import from sibling directories
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'board'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from task_yaml import parse_frontmatter
from archive_iter import (
    iter_all_archived_markdown,
    iter_archived_frontmatter,
    archive_path_for_id,
)
```

**Dataclasses:**
```python
@dataclass
class CompletedTask:
    task_id: str          # e.g. "219" or "401_1"
    name: str             # e.g. "rename_aitaskpickremote"
    issue_type: str
    labels: list
    priority: str
    effort: str
    commit_date: str      # ISO format from git log
    commit_hash: str      # short hash of most recent commit
    file_source: str      # "loose" or "tar"
    metadata: dict        # full frontmatter dict

@dataclass
class TaskCommitInfo:
    hash: str
    message: str
    date: str
    affected_files: list  # list of file paths

@dataclass
class PlatformInfo:
    platform: str         # "github", "gitlab", "bitbucket"
    base_url: str         # e.g. "https://github.com/owner/repo"
    commit_url_template: str  # e.g. "https://github.com/owner/repo/commit/{hash}"
```

**`load_task_index(project_root)`:**
1. Run `git log --all --grep='(t' --format='%H %aI %s'`
2. Parse each line: extract hash, date, and task_id via regex `\(t(\d+(?:_\d+)?)\)`
3. Build dict: `{task_id: (most_recent_hash, most_recent_date)}` (keep only most recent commit per task)
4. Scan archived frontmatter via `iter_archived_frontmatter(archived_dir, _extract_metadata)`
5. Build `_extract_metadata(text)` helper that calls `parse_frontmatter(text)[0]` to get just the dict
6. Merge: for each task_id in git log that has archived metadata, create `CompletedTask`
7. Sort by commit_date desc
8. Return list

**`load_task_content(project_root, task_id)`:**
- Parse task_id to determine parent/child pattern
- Check loose files first: `aitasks/archived/t{id}_*.md` or `aitasks/archived/t{parent}/t{id}_*.md`
- If not found, search numbered archives via `archive_path_for_id()`
- Return full text content or None

**`load_plan_content(project_root, task_id)`:**
- Same pattern but in `aiplans/archived/`: `p{id}_*.md` or `p{parent}/p{id}_*.md`
- Return full text content or None

**`load_completed_tasks_chunk(task_index, offset, limit=10)`:**
- Simple slice: `task_index[offset:offset+limit]`
- Return `(chunk, offset + limit < len(task_index))`

**`find_commits_for_task(task_id, project_root)`:**
- Run `git log --all --grep='(t{task_id})' --format='%H %aI %s'`
- For each commit, run `git diff-tree --no-commit-id --name-only -r {hash}`
- Return list of `TaskCommitInfo`

**`find_child_tasks(parent_id, task_index)`:**
- Filter index: `[t for t in task_index if t.task_id.startswith(f"{parent_id}_")]`

**`find_sibling_tasks(task_id, task_index)`:**
- Extract parent: `task_id.split("_")[0]`
- Return `find_child_tasks(parent, task_index)` excluding self

**`detect_platform_info(project_root)`:**
- Run `git remote get-url origin`
- Parse URL for github.com, gitlab.com, bitbucket.org
- Extract owner/repo from URL patterns (SSH and HTTPS)
- Return PlatformInfo with appropriate commit URL template

---

## Step 9: Post-Implementation

Archive child task, update plan, push.
