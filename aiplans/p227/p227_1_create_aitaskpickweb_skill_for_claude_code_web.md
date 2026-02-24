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

Claude Code Web is sandboxed to a single branch. This skill strips out all cross-branch operations from `aitask-pickrem` and stores task data locally in `.task-data-updated/`.

## Implementation Steps

### Step 1: Create skill directory and SKILL.md
- Create `.claude/skills/aitask-pickweb/SKILL.md`
- Base on `.claude/skills/aitask-pickrem/SKILL.md` (456 lines)
- Strip out: Steps 3 (sync), 5 (assign/lock), 9 (auto-commit to ait git), 10 (archive)
- Replace with: read-only lock check, `.task-data-updated/` plan storage, completion marker

### Step 2: Define the workflow
Key differences from pickrem:
1. Step 0: `aitask_init_data.sh` — same as pickrem (read-only)
2. Step 1: Load profile — same as pickrem
3. Step 2: Resolve task — same as pickrem
4. Step 3: Read-only lock check via `aitask_lock.sh --check` (informational only)
5. Step 4: Task status checks — same as pickrem (handle Done/orphaned tasks per profile)
6. **NO Step 5** (no assign/lock/status update)
7. Step 6: Create plan at `.task-data-updated/plan_t<task_id>.md`
8. Step 7: Implement
9. Step 8: Write completion marker `.task-data-updated/completed_t<task_id>.json`
10. Step 9: Commit all changes to current branch (regular `git`, not `./ait git`)
11. **NO Step 10** (no archive, no ait git push)

### Step 3: Define completion marker format
```json
{
  "task_id": "42",
  "task_file": "aitasks/t42_implement_auth.md",
  "plan_file": ".task-data-updated/plan_t42.md",
  "is_child": false,
  "parent_id": null,
  "issue_type": "feature",
  "completed_at": "2026-02-24 15:30",
  "branch": "claude-web/t42"
}
```

### Step 4: Register skill
- Update `.claude/settings.local.json` to include `aitask-pickweb` skill

### Step 5: Abort procedure
- Simply display error and stop
- No status revert, no lock release (nothing was modified on aitask-data)

## Key Files
- **Create:** `.claude/skills/aitask-pickweb/SKILL.md`
- **Modify:** `.claude/settings.local.json`
- **Reference:** `.claude/skills/aitask-pickrem/SKILL.md`, `aiscripts/aitask_lock.sh` (line 221), `aiscripts/aitask_init_data.sh`

## Verification
- Review SKILL.md for completeness
- Verify NO calls to: `aitask_own.sh`, `aitask_update.sh`, `aitask_archive.sh`, `./ait git`
- Verify it DOES contain: `aitask_init_data.sh`, `aitask_lock.sh --check`, `.task-data-updated/` plan and completion marker

## Post-Implementation (Step 9)
Archive this child task. If all children complete, parent t227 auto-archives.
