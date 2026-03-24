---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_board, task-archive]
created_at: 2026-03-24 08:57
updated_at: 2026-03-24 08:57
---

## Context

This is child task 1 of t448 (Completed Tasks History View in Codebrowser). It establishes the data foundation that all subsequent child tasks depend on.

The codebrowser TUI needs to access archived task data, but the archive iteration logic is currently fragmented:
- `archive_iter.py` handles only tar.gz iteration (numbered + legacy)
- `aitask_stats.py` (lines 588-606) has its own `iter_archived_markdown_files()` combining loose file globbing with tar iteration

This task consolidates the iteration logic and creates the history-specific data layer.

## Part A: Consolidate `archive_iter.py`

### Key Files to Modify
- `.aitask-scripts/lib/archive_iter.py` — add consolidated iteration functions
- `.aitask-scripts/aitask_stats.py` — refactor to use the new consolidated functions

### Implementation

1. Add to `archive_iter.py`:
   - `iter_all_archived_markdown(archived_dir)` — yields `(filename, text_content)` from loose files + numbered tar.gz (no legacy `old.tar.gz`). Must handle:
     - Parent tasks: `archived_dir/t*_*.md` (loose)
     - Child tasks: `archived_dir/t*/t*_*_*.md` (loose, in subdirs)
     - Numbered tar: `archived_dir/_b*/old*.tar.gz` (via existing `iter_numbered_archives`)
   - `iter_archived_frontmatter(archived_dir, parse_fn)` — yields `(filename, metadata_dict)`. Calls `parse_fn(text_content)` which should return only the frontmatter dict (not the body). This is for fast index building without loading full content.

2. Refactor `aitask_stats.py`:
   - Replace lines 588-606 (`iter_archived_markdown_files()`) body with a call to `archive_iter.iter_all_archived_markdown(ARCHIVE_DIR)`
   - Ensure `aitask_stats.py` still works identically (same output, same stats)

### Reference Files
- `.aitask-scripts/lib/archive_iter.py` — current tar-only iteration (68 lines)
- `.aitask-scripts/aitask_stats.py` lines 588-606 — pattern to consolidate
- `.aitask-scripts/board/task_yaml.py` — `parse_frontmatter()` function that returns `(metadata, body, key_order)`

## Part B: History Data Layer (`history_data.py`)

### Key Files to Create
- `.aitask-scripts/codebrowser/history_data.py`

### Implementation

Create a Python module with these dataclasses and functions:

**Dataclasses:**
- `CompletedTask` — task_id (str), name (str), issue_type (str), labels (list), priority (str), effort (str), commit_date (str), commit_hash (str), file_source (str: "loose" or "tar"), metadata (dict)
- `TaskCommitInfo` — hash (str), message (str), date (str), affected_files (list of str)
- `PlatformInfo` — platform (str: "github"|"gitlab"|"bitbucket"), base_url (str), commit_url_template (str)

**Functions:**
- `load_task_index(project_root)`:
  1. Run `git log --oneline --all --grep='(t' --format='%H %aI %s'` to get all task-related commits
  2. Parse task IDs from commit messages (regex `\(t(\d+(?:_\d+)?)\)`)
  3. For each unique task ID, resolve metadata from archived files via `archive_iter.iter_archived_frontmatter()`
  4. Sort by most recent commit date desc
  5. Return list of `CompletedTask` objects

- `load_task_content(project_root, task_id)` — load full markdown content for a single task. Check loose files first, then tar.gz via `archive_iter`.

- `load_plan_content(project_root, task_id)` — load associated plan file from `aiplans/archived/`. Uses same loose + tar.gz pattern for `p<N>` files. Returns None if no plan found.

- `load_completed_tasks_chunk(task_index, offset, limit=10)` — returns `(tasks_chunk, has_more)` slice of the index.

- `find_commits_for_task(task_id, project_root)` — `git log --grep='(tN)' --format='%H %aI %s'`, then for each commit run `git diff-tree --no-commit-id --name-only -r <hash>`. Returns list of `TaskCommitInfo`.

- `find_child_tasks(parent_id, task_index)` — filter index for tasks with IDs matching `parent_id_*` pattern.

- `find_sibling_tasks(task_id, task_index)` — extract parent from task_id (e.g., "16" from "16_2"), then find all children of that parent.

- `detect_platform_info(project_root)` — run `git remote get-url origin`, parse for github.com/gitlab.com/bitbucket.org, extract owner/repo, return `PlatformInfo` with URL template. Templates:
  - GitHub: `https://github.com/{owner}/{repo}/commit/{hash}`
  - GitLab: `https://gitlab.com/{owner}/{repo}/-/commit/{hash}`
  - Bitbucket: `https://bitbucket.org/{owner}/{repo}/commits/{hash}`

**Import strategy:** Use `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'board'))` and `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))` (same pattern as `diffviewer/plan_loader.py`).

## Verification

1. Run `ait stats` — verify output is identical before/after the `archive_iter.py` consolidation
2. Write a test script that imports `history_data` and:
   - Calls `load_task_index()` and verifies tasks are sorted by commit date desc
   - Calls `find_commits_for_task()` for a known archived task
   - Calls `detect_platform_info()` and verifies platform detection
   - Calls `load_plan_content()` for a known task with an archived plan
