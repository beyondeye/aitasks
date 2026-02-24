---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitakspickrem, remote]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 16:52
updated_at: 2026-02-24 18:56
completed_at: 2026-02-24 18:56
---

Create a stripped-down, fully autonomous task implementation skill for Claude Code Web at `.claude/skills/aitask-pickweb/SKILL.md`. Zero interactive prompts. No cross-branch operations (no locking, no status updates to aitask-data, no archival).

## Context

Claude Code Web is sandboxed to a single branch with no push access to `aitask-locks`, `aitask-data`, or `main`. The existing `aitask-pickrem` skill assumes full branch access and aborts on lock failure. This new skill strips out all cross-branch operations and stores task data locally in `.aitask-data-updated/` on the working branch.

## Key Files to Create
- `.claude/skills/aitask-pickweb/SKILL.md` -- new skill definition
- Update `.claude/settings.local.json` -- register the new skill

## Reference Files
- `.claude/skills/aitask-pickrem/SKILL.md` -- base to adapt from
- `aiscripts/aitask_lock.sh` -- `check_lock()` function at line 221 (read-only check)
- `aiscripts/aitask_init_data.sh` -- data branch initialization

## Workflow Summary

1. Init data branch read-only via `aitask_init_data.sh` (fetch + local worktree + symlinks)
2. Load execution profile (same as pickrem)
3. Resolve task file from `aitasks/` (via symlinks)
4. Read-only lock check via `aitask_lock.sh --check` (informational only, no lock acquisition)
5. NO status update -- task status stays as-is
6. Create implementation plan at `.aitask-data-updated/plan_t<task_id>.md`
7. Implement the code
8. Write completion marker `.aitask-data-updated/completed_t<task_id>.json` with task metadata (task_id, task_file, plan_file, is_child, parent_id, issue_type, completed_at, branch). This marker is how `aitask-web-merge` detects completed branches.
9. Commit all changes (code + `.aitask-data-updated/` files) to current branch
10. NO archival, NO `./ait git push`

Abort procedure: simply display error and stop (nothing was modified on aitask-data).

## Verification
- Review SKILL.md for completeness
- Verify NO calls to: `aitask_own.sh`, `aitask_update.sh`, `aitask_archive.sh`, `./ait git`
- Verify it DOES contain: `aitask_init_data.sh`, `aitask_lock.sh --check`, `.aitask-data-updated/` plan and marker creation
