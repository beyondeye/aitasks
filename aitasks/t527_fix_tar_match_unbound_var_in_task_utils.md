---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait, shell]
created_at: 2026-04-12 12:13
updated_at: 2026-04-12 12:13
---

## Context

During archival of t521_3 on 2026-04-12, `aitask_archive.sh 521_3` aborted
mid-flow with:

```
/home/ddt/Work/aitasks/.aitask-scripts/lib/task_utils.sh: line 358: tar_match: unbound variable
```

The script had already moved both the child task/plan files and the parent
task file to `archived/` (parent auto-archival worked), but it crashed
before committing the renames, leaving a dirty working tree that had to
be staged and committed manually. Any task archival that hits the "Tier 3
numbered archives" fallback path for a parent plan will trip the same bug.

## Root Cause

`.aitask-scripts/lib/task_utils.sh` around line 353:

```bash
# Tier 3: numbered archives (computed path, then legacy fallback)
if [[ -z "$files" ]]; then
    local archive_path tar_match
    archive_path=$(_find_archive_for_task "$task_id" "$ARCHIVED_PLAN_DIR")
    if [[ -n "$archive_path" ]]; then
        tar_match=$(_search_archive "$archive_path" "(^|/)p${task_id}_.*\.md$")
    fi
    if [[ -z "$tar_match" ]]; then
        ...
```

`local archive_path tar_match` declares both variables but only initializes
`archive_path` (via the command substitution on the next line). If
`_find_archive_for_task` returns an empty string, the inner `if` block is
skipped and `tar_match` stays unset. The subsequent `[[ -z "$tar_match" ]]`
read under `set -u` (nounset) raises "unbound variable" and the script
exits.

Same pattern likely exists in the sibling Tier 3 branch for active task
resolution — grep the file for `local.*tar_match` to find all occurrences.

## Fix

One-liner: initialize both variables at declaration.

```bash
local archive_path="" tar_match=""
```

Apply to every `local archive_path tar_match` line in
`.aitask-scripts/lib/task_utils.sh` (expected: 1–2 sites covering the
parent-plan and child-task Tier 3 fallbacks).

## Verification

1. `shellcheck .aitask-scripts/lib/task_utils.sh` (should stay clean).
2. Manual repro: archive a task whose plan lives in a numbered archive
   bundle (`aiplans/archived/old*.tar.zst`). Before the fix, the archive
   aborts with "unbound variable". After the fix, it completes cleanly.
3. Alternatively: force `_find_archive_for_task` to return empty and
   confirm `resolve_plan_for_task` / the archival flow no longer aborts.

## Files to Modify

- `.aitask-scripts/lib/task_utils.sh` (line ~353 and any other
  `local archive_path tar_match` occurrences).
