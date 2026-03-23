---
Task: t435_claude_struggle_with_task_create.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Refactor aitask_create.sh invocation into shared procedure

## Context

Claude Code frequently fails when creating tasks via `aitask_create.sh --batch` during workflow runs. The root cause is `planning.md` line 74 has an incomplete command reference, but the broader issue is that **7 skill files** each duplicate the same command template with slight variations, leading to drift and inconsistency.

## Approach

Create a shared **Batch Task Creation Procedure** (`.claude/skills/task-workflow/task-creation-batch.md`) that documents the canonical command templates. Update all calling skills to reference this procedure instead of duplicating the templates inline.

## Files to create/modify

### 1. CREATE: `.claude/skills/task-workflow/task-creation-batch.md`

New shared procedure file with:
- Input parameter table (mode, parent_num, name, description, priority, effort, type, labels, + optional flags)
- **Parent task creation** command template with heredoc
- **Child task creation** command template with heredoc
- **Post-creation read-back** pattern (`git log -1 --name-only`)
- Optional flags section (--no-sibling-dep, --issue, --pull-request, --contributor, --contributor-email)
- Notes on heredoc quoting (`<<'TASK_DESC'` to prevent shell expansion)

### 2. MODIFY: `.claude/skills/task-workflow/planning.md` (lines 74-75, 91-96)

**Line 74-75** — Replace incomplete command with procedure reference:
```
    - Use `aitask_create.sh --batch --parent <N>` to create each child
    - **IMPORTANT:** Each child task file MUST include detailed context (...)
```
becomes:
```
    - For each child task, execute the **Batch Task Creation Procedure** (see `task-creation-batch.md`) with mode `child`, the parent task number, an appropriate name, and the child task description content. The description MUST include detailed context (see Child Task Documentation Requirements below).
```

**Lines 91-96** — Fix combined commit to only handle plan files (child task files are already committed by `--commit`):
```bash
mkdir -p aiplans/p<parent>
./ait git add aiplans/p<parent>/
./ait git commit -m "ait: Add t<parent> child implementation plans"
```

### 3. MODIFY: `.claude/skills/aitask-qa/follow-up-task-creation.md` (lines 31-56)

Replace both inline templates (child + parent) with procedure references:
```
Execute the **Batch Task Creation Procedure** (see `../task-workflow/task-creation-batch.md`) with:
- mode: `child` (if is_child) or `parent` (if not)
- parent_num: <parent_id> (if child)
- no_sibling_dep: true (if child)
- name: "test_<short_description>" or "test_t<task_id>_<short_description>"
- type: test
- priority: medium
- effort: medium
- labels: "testing,qa"
- description: <composed description>
```

### 4. MODIFY: `.claude/skills/aitask-review/SKILL.md` (lines 194-229)

Replace all three inline templates (single task, parent, child) with procedure references.

### 5. MODIFY: `.claude/skills/aitask-explore/SKILL.md` (lines 161-165)

Replace inline template with procedure reference.

### 6. MODIFY: `.claude/skills/aitask-wrap/SKILL.md` (lines 212-222)

Replace inline template with procedure reference.

### 7. MODIFY: `.claude/skills/aitask-pr-import/SKILL.md` (lines 245-257)

Replace inline template with procedure reference, noting the extra `--pull-request`, `--contributor`, `--contributor-email` flags.

### 8. MODIFY: `.claude/skills/aitask-revert/SKILL.md` (lines 614-618)

Replace inline template with procedure reference.

### 9. MODIFY: `.claude/skills/aitask-create/SKILL.md` (Batch Mode section, lines 258-302)

Keep the Batch Mode section as-is (it's the full reference documentation for the interactive create skill), but add a cross-reference: "For the canonical batch creation templates used by other skills, see `.claude/skills/task-workflow/task-creation-batch.md`."

## Verification

1. Read all modified files to verify correct procedure references
2. Verify the new procedure file has complete, correct templates
3. Confirm no orphaned inline templates remain
4. Run `shellcheck .aitask-scripts/aitask_create.sh` to verify script is unchanged

## Final Implementation Notes

- **Actual work done:** Created `task-creation-batch.md` shared procedure and updated 9 skill files + `task-fold-content.md` to reference it. Also added the procedure to the SKILL.md procedures list.
- **Deviations from plan:** Also updated `task-fold-content.md` which references `aitask_create.sh` in its description of "incorporate during creation" callers. Not originally planned but discovered during implementation.
- **Issues encountered:** User feedback led to two revisions of `task-creation-batch.md`: (1) improved description of both modes (`--desc` vs `--desc-file -`), (2) clarified that `--desc-file -` uses stdin via heredoc (no temporary file needed) and is actually the recommended mode for AI agents since it avoids shell quoting issues.
- **Key decisions:** Recommended `--desc-file - <<'TASK_DESC'` as the primary mode for Claude Code because the single-quoted heredoc prevents all shell expansion — no escaping needed for quotes, `$`, backticks etc. in descriptions.

## Step 9: Post-Implementation

Archive task, push changes.
