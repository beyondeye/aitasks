---
Task: t448_7_fix_plan_retrieval_from_old_tar_gz.md
Parent Task: aitasks/t448_codebrowser_history_screen.md
Sibling Tasks: aitasks/t448/t448_5_*.md, aitasks/t448/t448_6_*.md
Archived Sibling Plans: aiplans/archived/p448/p448_*_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

When viewing completed tasks in the codebrowser history screen, toggling to plan view (`v`) shows "No plan file found" for tasks archived in tar.gz archives. Task content loads correctly from tar archives, but plan content does not — because `load_plan_content()` lacks tar archive fallback.

## Root Cause

`load_plan_content()` in `history_data.py:174-198` only checks loose files in `aiplans/archived/`. It has no tar fallback. `load_task_content()` (lines 139-171) correctly falls back to `iter_all_archived_markdown()` for tar scanning.

Plan archives exist at `aiplans/archived/_b0/old*.tar.gz` with `p`-prefixed filenames (e.g., `p97_foo.md`, `p99/p99_1_bar.md`).

## Implementation

### File to modify: `.aitask-scripts/codebrowser/history_data.py`

**1. Add tar archive fallback to `load_plan_content()`** (after the loose file checks):

```python
# Fall back to tar archives
for filename, content in iter_all_archived_markdown(archived_plans):
    m = re.match(r"p(\d+(?:_\d+)?)_", filename)
    if m and m.group(1) == task_id:
        return content
```

Note: `iter_all_archived_markdown` (from `archive_iter.py`) scans loose files with `t*_*.md` globs (which won't match plan `p*` files) then numbered tar archives (which yield ALL `.md` files by basename). So the tar entries will include plan files. The loose `t*` matches are harmless — they just won't match the `p`-prefix regex.

Alternatively, use `iter_all_archived_tar_files` directly to skip the redundant loose-file scan (since we already checked loose files above). This is cleaner:

```python
from archive_iter import iter_all_archived_markdown, iter_archived_frontmatter, iter_all_archived_tar_files

# In load_plan_content(), after loose file checks:
for filename, content in iter_all_archived_tar_files(archived_plans):
    m = re.match(r"p(\d+(?:_\d+)?)_", filename)
    if m and m.group(1) == task_id:
        return content
```

**Preferred approach:** Use `iter_all_archived_tar_files` — it only scans tar archives (numbered + legacy), avoiding redundant loose file iteration.

**2. Update import** (line 20): Add `iter_all_archived_tar_files` to the import.

## Verification

1. `ait codebrowser` → `h` → select an old task (low ID, archived in tar) → `v` to toggle plan view → should show plan content
2. Verify loose plan files still load correctly (select a recent task like t448_1)
3. Toggle back with `v` — task content still displays

## Final Implementation Notes
- **Actual work done:** Used `iter_all_archived_tar_files` (preferred approach) to add tar archive fallback to `load_plan_content()`. Added import and 5-line fallback block. Exactly as planned.
- **Deviations from plan:** None — implemented the preferred approach directly.
- **Issues encountered:** None.
- **Key decisions:** Used `iter_all_archived_tar_files` instead of `iter_all_archived_markdown` to avoid redundant loose-file scanning (loose files already checked above).
- **Notes for sibling tasks:** The `archive_iter.py` functions work with any `archived_dir` path, not just task archives. Plan archives follow the same `_bN/oldM.tar.gz` structure. When matching plan filenames from tar, use `p` prefix regex instead of `t`. User also reported an unrelated issue: the "load more" pseudo item in the task history list is not shown the first time the history screen is entered, only from the second time onward.
