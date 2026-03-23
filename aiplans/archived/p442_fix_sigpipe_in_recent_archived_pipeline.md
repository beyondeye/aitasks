---
Task: t442_fix_sigpipe_in_recent_archived_pipeline.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

## Context

`aitask_query_files.sh recent-archived 15` crashes with exit code 141 (SIGPIPE) when there are more archived tasks than the limit parameter. This blocks `/aitask-qa` interactive task selection. The bug was introduced in t428_1 when `cmd_recent_archived` was added. With 186 archived tasks and a limit of 15, the `sort | head` pipeline triggers SIGPIPE under `set -eo pipefail`.

## Plan

### Step 1: Fix the main `sort | head` SIGPIPE (line 408)

**File:** `.aitask-scripts/aitask_query_files.sh`

Add `|| true` after the pipeline to suppress SIGPIPE, consistent with the t389 fix pattern:

```bash
# Before:
sorted=$(printf '%s\n' "${entries[@]}" | sort -t'|' -k1 -r | head -n "$limit")

# After:
sorted=$(printf '%s\n' "${entries[@]}" | sort -t'|' -k1 -r | head -n "$limit") || true
```

### Step 2: Fix the per-file `grep | sed | head` pipelines (lines 382, 384, 394, 396)

Same file. These pipelines could SIGPIPE if any archived task file has multiple matching frontmatter lines. Add `|| true` to each:

```bash
# Before (4 instances):
completed_at=$({ grep ... || true; } | sed '...' | head -n 1)

# After:
completed_at=$({ grep ... || true; } | sed '...' | head -n 1) || true
```

Lines to fix: 382, 384, 394, 396.

## Verification

1. Run the fixed command and confirm it succeeds:
   ```bash
   ./.aitask-scripts/aitask_query_files.sh recent-archived 15
   ```
   Should output 15 `RECENT_ARCHIVED:` lines with exit code 0.

2. Run with a limit larger than total entries to confirm no regression:
   ```bash
   ./.aitask-scripts/aitask_query_files.sh recent-archived 999
   ```

3. Run shellcheck:
   ```bash
   shellcheck .aitask-scripts/aitask_query_files.sh
   ```

4. Reference Step 9 (Post-Implementation) for archival and cleanup.

## Final Implementation Notes
- **Actual work done:** Added `|| true` to 5 pipelines in `cmd_recent_archived()` — the main `sort | head` pipeline and 4 per-file `grep | sed | head` pipelines. Exactly as planned.
- **Deviations from plan:** None.
- **Issues encountered:** None — the fix was straightforward and consistent with the t389 pattern.
- **Key decisions:** Used `|| true` (same as t389 fix) rather than restructuring the pipelines, since it's simpler and the SIGPIPE is the only benign failure mode.
