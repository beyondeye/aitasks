---
Task: t140_document_folded_tasks_feature.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The folded tasks feature and parallel exploration workflow are fully implemented in the aitask-explore skill but under-documented in user-facing docs. This task adds the missing documentation so users can discover and understand these features.

## Plan

### 1. Add `folded_tasks` field to `docs/task-format.md`

**File:** `docs/task-format.md` (line ~50, after `boardidx` row)

Add one row to the frontmatter table:

```
| `folded_tasks` | `[138, 129_5]` | Task IDs folded into this task by `/aitask-explore` (deleted on archival) |
```

### 2. Add Folded Tasks subsection to `/aitask-explore` in `docs/skills.md`

**File:** `docs/skills.md` (after line 145, before the `---` separator at line 147)

Add a new subsection after the "Profile key" line:

```markdown
**Folded tasks:**

During task creation, `/aitask-explore` scans pending tasks (`Ready`/`Editing` status) for overlap with the new task. If related tasks are found, you're prompted to select which ones to "fold in" — their content is incorporated into the new task's description, and the originals are automatically deleted when the new task is archived after implementation.

Only standalone parent tasks (no children) can be folded. The `folded_tasks` frontmatter field tracks which tasks were folded in. During planning, there's no need to re-read the original folded task files — all relevant content is already in the new task.
```

### 3. Add Parallel Exploration section to `docs/workflows.md`

**File:** `docs/workflows.md` (after line 101, before the `---` separator at line 102)

Add a new subsection within the existing "Parallel Development" section:

```markdown
**Parallel exploration:**

`/aitask-explore` is read-only — it searches and reads code but never modifies source files. This makes it safe to run in a separate terminal tab while another Claude Code instance implements a task. Use this pattern to stay productive: explore and create new tasks while waiting for builds, tests, or ongoing implementations to complete.
```

## Verification

1. Check markdown renders correctly (heading nesting, table alignment)
2. Cross-reference the `folded_tasks` documentation against actual behavior in `.claude/skills/aitask-explore/SKILL.md` Steps 2b/3 and `.claude/skills/task-workflow/SKILL.md` Step 9
3. Verify no existing content was accidentally removed

## Final Implementation Notes
- **Actual work done:** Added `folded_tasks` frontmatter field to docs/task-format.md, folded tasks subsection to /aitask-explore in docs/skills.md, and parallel exploration note to docs/workflows.md. All three additions match the plan exactly.
- **Deviations from plan:** None.
- **Issues encountered:** None — straightforward documentation additions.
- **Key decisions:** Kept the parallel exploration note within the existing "Parallel Development" section rather than creating a separate section, as it fits naturally there.

## Post-Review Changes

### Change Request 1 (2026-02-16 20:00)
- **Requested by user:** Reference the upcoming `/aitask-fold` skill (t143) in the folded tasks documentation
- **Changes made:** Added cross-reference to `/aitask-fold` in docs/skills.md folded tasks subsection; updated docs/task-format.md `folded_tasks` field description to mention both `/aitask-explore` and `/aitask-fold`
- **Files affected:** `docs/skills.md`, `docs/task-format.md`
