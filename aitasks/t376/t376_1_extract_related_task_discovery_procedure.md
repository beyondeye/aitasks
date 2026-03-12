---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [aitask_fold, aitask_contribute]
created_at: 2026-03-12 22:34
updated_at: 2026-03-12 22:34
---

## Context

The "Related Task Discovery" logic — listing pending tasks, filtering eligible ones, performing AI semantic matching, and presenting overlapping tasks for folding — is currently duplicated in two skills:

1. **aitask-explore** Step 2b (`.claude/skills/aitask-explore/SKILL.md`, lines 129-157)
2. **aitask-fold** Step 1 (`.claude/skills/aitask-fold/SKILL.md`, lines 78-112)

A third copy is needed for `/aitask-contribution-review` (t376). To avoid tripling the duplication, this task extracts the shared logic into a reusable procedure.

## Key Files to Modify

- **Create:** `.claude/skills/task-workflow/related-task-discovery.md` — New shared procedure file (alongside existing `procedures.md` and `planning.md`)
- **Modify:** `.claude/skills/aitask-explore/SKILL.md` — Replace Step 2b inline logic with reference to shared procedure
- **Modify:** `.claude/skills/aitask-fold/SKILL.md` — Replace Step 1 inline logic with reference to shared procedure

## Reference Files for Patterns

- `.claude/skills/task-workflow/procedures.md` — Existing procedure file pattern (called "Execute the X Procedure" from SKILL.md)
- `.claude/skills/task-workflow/planning.md` — Another shared procedure file example
- `.claude/skills/aitask-explore/SKILL.md` Step 2b (lines 129-157) — Primary source for the discovery logic
- `.claude/skills/aitask-fold/SKILL.md` Step 1 (lines 78-112) — Alternative source with slight differences

## Implementation Plan

### Step 1: Create the shared procedure file

Create `.claude/skills/task-workflow/related-task-discovery.md` containing:

1. **List pending tasks:**
   ```bash
   ./.aitask-scripts/aitask_ls.sh -v --status all --all-levels 99 2>/dev/null
   ```

2. **Filter eligible tasks:** Status `Ready` or `Editing` only. Exclude:
   - Tasks with children ("Has children")
   - Child tasks (filename pattern `t<parent>_<child>_*.md`)
   - Status `Implementing`, `Postponed`, `Done`, `Folded`

3. **Assess relevance:** Read title + first ~5 lines of body text for each eligible task. Use AI semantic analysis to match against the provided **matching context** (parameterized — the calling skill provides what to match against).

4. **Present results:** If related tasks found, present via `AskUserQuestion` with multiSelect. Include "None — no tasks to fold in" option.

5. **Return:** List of selected task IDs as `folded_tasks`, or empty if none selected.

**Parameterize differences between callers:**
- **Matching context:** What to compare against (exploration findings for explore, task description for fold, contribution metadata for contribution-review)
- **Question text:** Slightly different wording per caller
- **Minimum count:** Fold requires ≥2 eligible tasks; explore/contribution-review require ≥1

### Step 2: Update aitask-explore SKILL.md

Replace Step 2b inline logic (lines 129-157) with:
```markdown
### Step 2b: Related Task Discovery

Execute the **Related Task Discovery Procedure** (see `.claude/skills/task-workflow/related-task-discovery.md`) with:
- **Matching context:** The exploration findings gathered in Step 2
- **Purpose:** "fold into the new task being created"

If the procedure returns folded task IDs, store them as `folded_tasks` for Step 3.
```

Keep the existing notes about "Scope rule: Only standalone parent-level tasks..." as they're already in the shared procedure.

### Step 3: Update aitask-fold SKILL.md

Replace Step 1 inline logic (lines 78-112) with a reference to the shared procedure. Note that fold has a key difference: it needs ≥2 eligible tasks and presents all tasks for selection (not just "related" ones). The procedure must handle this variant.

For fold's Step 1a-1c, replace with a call to the procedure with fold-specific parameters:
- **Minimum eligible:** 2
- **Selection mode:** All eligible tasks shown (not pre-filtered by AI relevance)
- **Question text:** "Select tasks to fold together"

## Verification Steps

1. Read the new `related-task-discovery.md` and verify it captures all the logic from both sources
2. Read updated `aitask-explore/SKILL.md` and verify Step 2b references the procedure correctly
3. Read updated `aitask-fold/SKILL.md` and verify Step 1 references the procedure correctly
4. Verify no logic is lost in the refactoring — the procedure must be functionally equivalent
5. Run `shellcheck .aitask-scripts/aitask_*.sh` to ensure no script changes broke anything (though this task is skill-doc-only)
