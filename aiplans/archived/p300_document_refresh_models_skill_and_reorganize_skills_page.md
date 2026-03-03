---
Task: t300_document_refresh_models_skill_and_reorganize_skills_page.md
Worktree: (current directory)
Branch: main
Base branch: main
---

## Context

Task t300: The `/aitask-refresh-code-models` skill has no website documentation page and is missing from the skills overview table. Additionally, `/aitask-web-merge` is documented but missing from the overview table. The overview page lists 15 skills in a flat table that should be reorganized into grouped sections for better navigation. Also, `/aitask-pr-review` should be renamed to `/aitask-pr-import` everywhere since it imports PRs as tasks (not reviews them), and moved to the Task Management group.

## Plan

### 1. Rename `/aitask-pr-review` → `/aitask-pr-import` everywhere

Rename the skill across all references. This is a semantic correction: the skill imports PRs as tasks, it doesn't review them.

**Directory rename:**
- `.claude/skills/aitask-pr-review/` → `.claude/skills/aitask-pr-import/`
  - Update `name:` field in SKILL.md frontmatter

**File rename:**
- `website/content/docs/skills/aitask-pr-review.md` → `website/content/docs/skills/aitask-pr-import.md`
  - Update frontmatter: title, linkTitle
  - Update usage block and any self-references

**String replacements (in-place edits):**
- `website/content/docs/commands/pr-import.md` — 3 references to `/aitask-pr-review` and links
- `website/content/docs/workflows/pr-workflow.md` — ~8 references to `/aitask-pr-review` and links
- `aiscripts/aitask_pr_import.sh` — 4 user-facing string references in `info`/fzf messages

### 2. Create `/aitask-refresh-code-models` documentation page

**Create:** `website/content/docs/skills/aitask-refresh-code-models.md`

### 3. Reorganize skills overview into grouped sections

**Modify:** `website/content/docs/skills/_index.md`

### 4. Add cross-reference in `ait codeagent` doc page

**Modify:** `website/content/docs/commands/codeagent.md`

## Post-Review Changes

### Change Request 1 (2026-03-03)
- **Requested by user:** Rename "Workflow" heading to "Step-by-Step" in refresh-code-models skill page
- **Changes made:** Changed `## Workflow` to `## Step-by-Step` for consistency with other skill pages
- **Files affected:** `website/content/docs/skills/aitask-refresh-code-models.md`

### Change Request 2 (2026-03-03)
- **Requested by user:** Add Settings TUI note to codeagent doc's TUI Integration section
- **Changes made:** Added bullet point for Settings TUI (`ait settings`) describing the Code Agent tab for editing operation-to-agent bindings
- **Files affected:** `website/content/docs/commands/codeagent.md`

## Final Implementation Notes
- **Actual work done:** All 4 planned steps implemented plus 2 post-review changes. Renamed `/aitask-pr-review` → `/aitask-pr-import` across 7 files (1 directory rename, 1 file rename, 5 in-place edits). Created new skill doc page. Reorganized skills overview into 4 grouped sections. Enhanced codeagent doc with "Updating Models" subsection and Settings TUI reference.
- **Deviations from plan:** Added Settings TUI mention to codeagent doc (user request). Used 4 groups instead of 5 (merged "Code Understanding" and "Review Guides" into "Code Review").
- **Issues encountered:** Pre-existing uncommitted changes in the repo (task-workflow/SKILL.md, aitask_archive.sh, aitask_board.py, imgs/) — carefully excluded from commit.
- **Key decisions:** Hugo link paths `../../skills/aitask-pr-import/` work correctly after file rename since Hugo resolves by directory structure.
