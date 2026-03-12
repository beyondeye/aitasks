---
Task: t376_1_extract_related_task_discovery_procedure.md
Parent Task: aitasks/t376_check_for_existing_tasks_in_aitaskcontribute.md
Sibling Tasks: aitasks/t376/t376_2_*.md, aitasks/t376/t376_3_*.md, aitasks/t376/t376_4_*.md
Worktree: (none - current branch)
Branch: (current branch)
Base branch: main
---

## Goal

Extract the duplicated "Related Task Discovery" logic from aitask-explore (Step 2b) and aitask-fold (Step 1) into a shared procedure file at `.claude/skills/task-workflow/related-task-discovery.md`.

## Steps

### 1. Create `.claude/skills/task-workflow/related-task-discovery.md`

The shared procedure must be parameterized for three callers. Structure:

```markdown
# Related Task Discovery Procedure

## Parameters

| Parameter | Description |
|-----------|-------------|
| matching_context | What to compare against (exploration findings, task description, contribution metadata) |
| purpose_text | Displayed in the AskUserQuestion (e.g., "fold into the new task", "fold together") |
| min_eligible | Minimum eligible tasks required (1 for explore/contribution-review, 2 for fold) |
| selection_mode | "ai_filtered" (explore/contribution-review: AI pre-selects relevant tasks) or "all" (fold: show all eligible) |

## Procedure

### Step 1: List Pending Tasks
[aitask_ls.sh command]

### Step 2: Filter Eligible Tasks
[filtering rules]

### Step 3: Assess Relevance (if selection_mode = "ai_filtered")
[AI semantic matching against matching_context]

### Step 4: Present Results
[AskUserQuestion with multiSelect, pagination]

### Step 5: Return
[Return selected task IDs or empty list]
```

**Key logic to preserve from aitask-explore Step 2b:**
- `aitask_ls.sh -v --status all --all-levels 99 2>/dev/null`
- Filter: status `Ready` or `Editing`, no children, no child tasks, standalone parent-level only
- Semantic matching: read title + first ~5 lines of body, AI comparison
- MultiSelect AskUserQuestion with "None — no tasks to fold in" option

**Key logic to preserve from aitask-fold Step 1:**
- Same listing and filtering
- Additional: needs ≥2 eligible tasks or abort
- Step 1b: identify related tasks by labels + semantic similarity
- Step 1c: multiSelect with pagination (page_size=3 + "Show more")
- Returns selected task IDs (minimum 2 for fold)

**Parameterized differences:**
- `min_eligible`: fold=2, explore/contribution-review=1
- `selection_mode`: fold="all" (show all eligible), explore/contribution-review="ai_filtered" (AI pre-filters)
- `purpose_text`: varies per caller
- Pagination: always use it (consistent across callers)

### 2. Update `.claude/skills/aitask-explore/SKILL.md`

Replace Step 2b (lines ~129-157) with a compact reference:

```markdown
### Step 2b: Related Task Discovery

Before creating a new task, check for existing pending tasks that overlap.

Execute the **Related Task Discovery Procedure** (see `.claude/skills/task-workflow/related-task-discovery.md`) with:
- **Matching context:** The exploration findings gathered in Step 2
- **Purpose text:** "will be fully covered by the new task (they will be folded in and deleted after implementation)"
- **Min eligible:** 1
- **Selection mode:** ai_filtered

If the procedure returns task IDs, store them as `folded_tasks` for Step 3. Read the full description of each selected task — their content will be incorporated into the new task description in Step 3.

**Scope rule:** Only standalone parent-level tasks without children may be folded in.
```

### 3. Update `.claude/skills/aitask-fold/SKILL.md`

Replace Step 1a-1c (lines ~78-130) with a reference:

```markdown
### Step 1: Task Discovery

Execute the **Related Task Discovery Procedure** (see `.claude/skills/task-workflow/related-task-discovery.md`) with:
- **Matching context:** (not needed — fold uses "all" mode)
- **Purpose text:** "fold together into a single task (minimum 2)"
- **Min eligible:** 2
- **Selection mode:** all

If the procedure returns fewer than 2 task IDs, inform user "Need at least 2 tasks to fold." and abort.

Store the selected task IDs for Step 2 (Primary Task Selection).
```

Keep Step 1 validation logic for argument-provided task IDs (Step 0b) — that's separate from the discovery flow.

## Verification

1. Read new `related-task-discovery.md` — verify all logic from both sources is captured
2. Read updated `aitask-explore/SKILL.md` — verify Step 2b is functionally equivalent
3. Read updated `aitask-fold/SKILL.md` — verify Step 1 discovery is functionally equivalent
4. Verify fold-specific features preserved: ≥2 task requirement, "all" selection mode, pagination

## Step 9: Post-Implementation

Archive child task, proceed to sibling t376_2.
