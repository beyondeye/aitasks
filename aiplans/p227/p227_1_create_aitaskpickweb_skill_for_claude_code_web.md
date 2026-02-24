---
Task: t227_1_create_aitaskpickweb_skill_for_claude_code_web.md
Parent Task: aitasks/t227_aitask_own_failure_in_cluade_web.md
Sibling Tasks: aitasks/t227/t227_2_*.md, aitasks/t227/t227_3_*.md, aitasks/t227/t227_4_*.md, aitasks/t227/t227_5_*.md, aitasks/t227/t227_6_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: t227_1 — Create aitask-pickweb skill for Claude Code Web

## Context

Claude Code Web is sandboxed to a single branch. This skill strips out all cross-branch operations from `aitask-pickrem` and stores task data locally in `.aitask-data-updated/`.

## Implementation Steps

### Step 0: Rename `.task-data-updated/` → `.aitask-data-updated/` in siblings [DONE]
- Updated all references in t227_1, t227_2, t227_6 task files and their plan files
- Committed: `ait: Rename .task-data-updated to .aitask-data-updated in t227 siblings`

### Step 1: Create skill directory and SKILL.md [DONE]
- Created `.claude/skills/aitask-pickweb/SKILL.md`
- Based on `.claude/skills/aitask-pickrem/SKILL.md` (464 lines)
- Stripped: Steps 3 (sync), 5 (assign/lock), 9 (auto-commit via ait git), 10 (archive)
- Replaced with: read-only lock check, `.aitask-data-updated/` plan storage, completion marker

### Step 2: Define the workflow [DONE]
Key differences from pickrem:
1. Step 0: `aitask_init_data.sh` — same as pickrem (read-only)
2. Step 1: Load profile — same as pickrem
3. Step 2: Resolve task — same as pickrem
4. Step 3: Read-only lock check via `aitask_lock.sh --check` (informational only)
5. Step 4: Task status checks — simplified (abort instead of archive for Done/orphaned)
6. **NO assign/lock/status update step**
7. Step 5: Create plan at `.aitask-data-updated/plan_t<task_id>.md`
8. Step 6: Implement
9. Step 7: Auto-commit with regular `git` (not `./ait git`)
10. Step 8: Write completion marker `.aitask-data-updated/completed_t<task_id>.json`
11. **NO archive, NO push**

### Step 3: Define completion marker format [DONE]
```json
{
  "task_id": "42",
  "task_file": "aitasks/t42_implement_auth.md",
  "plan_file": ".aitask-data-updated/plan_t42.md",
  "is_child": false,
  "parent_id": null,
  "issue_type": "feature",
  "completed_at": "2026-02-24 15:30",
  "branch": "claude-web/t42"
}
```

### Step 4: Register skill [DONE]
- Skill auto-discovered by Claude Code (no settings.local.json change needed)

### Step 5: Abort procedure [DONE]
- Simply display error and stop
- No status revert, no lock release (nothing was modified on aitask-data)
- Optionally clean up `.aitask-data-updated/` files

## Key Files
- **Created:** `.claude/skills/aitask-pickweb/SKILL.md`
- **Modified:** 3 task files + 3 plan files (rename `.task-data-updated/` → `.aitask-data-updated/`)
- **Reference:** `.claude/skills/aitask-pickrem/SKILL.md`, `aiscripts/aitask_lock.sh` (line 221), `aiscripts/aitask_init_data.sh`

## Verification
- Review SKILL.md for completeness
- Verify NO calls to: `aitask_own.sh`, `aitask_update.sh`, `aitask_archive.sh`, `./ait git`
- Verify it DOES contain: `aitask_init_data.sh`, `aitask_lock.sh --check`, `.aitask-data-updated/` plan and completion marker
- Grep siblings to confirm no remaining `.task-data-updated/` references

## Final Implementation Notes
- **Actual work done:** Created `.claude/skills/aitask-pickweb/SKILL.md` (a ~350-line skill definition) by adapting `aitask-pickrem`. Renamed `.task-data-updated/` to `.aitask-data-updated/` across all sibling task files (t227_1, t227_2, t227_6) and their plan files (p227_1, p227_2, p227_6).
- **Deviations from plan:** Added Step 0 to rename the directory across siblings before creating the skill. Task status checks (Step 4) were simplified to abort instead of archive for Done/orphaned tasks, since archival requires cross-branch access. The step numbering was reorganized: pickrem Steps 5-10 became pickweb Steps 3-8 with the removal of assign/lock and archive steps.
- **Issues encountered:** None.
- **Key decisions:** The skill recognizes only `plan_preference` and `post_plan_action` profile fields. All lock/ownership/archive-related profile fields are documented as ignored. Done/orphaned tasks abort with a message pointing to `aitask-web-merge` for local handling.
- **Notes for sibling tasks:** The `.aitask-data-updated/` directory is the contract between pickweb and web-merge (t227_2). The completion marker format at `.aitask-data-updated/completed_t<task_id>.json` is what web-merge scans for. The plan file at `.aitask-data-updated/plan_t<task_id>.md` must be copied to `aiplans/` by web-merge before archival.

## Post-Implementation (Step 9)
Archive this child task. If all children complete, parent t227 auto-archives.
