---
Task: t149_run_zip_old_after_new_release.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Task t149 requests updating the release process documentation to include running `/aitask-zipold` after creating a new release. This archives old completed task and plan files to keep the repository clean.

## Plan

Add a third step to the Release Process section in `docs/development.md` (line 135).

### File to modify

- `docs/development.md` — Add step 3 after existing step 2

### Verification

- Read the updated file to confirm the new step is properly formatted

## Final Implementation Notes
- **Actual work done:** Added step 3 (`/aitask-zipold`) to the Release Process section in `docs/development.md`, exactly as planned
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Placed the zip-old step after `create_new_release.sh` since archiving old files is a cleanup step best done after the release is created
