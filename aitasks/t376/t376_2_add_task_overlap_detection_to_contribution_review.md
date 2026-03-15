---
priority: medium
effort: medium
depends: [t376_1]
issue_type: feature
status: Implementing
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-12 22:41
updated_at: 2026-03-15 08:13
---

## Context

The `/aitask-contribution-review` skill (`.claude/skills/aitask-contribution-review/SKILL.md`) imports external contribution issues as aitasks. It checks for overlapping **contribution issues** (via fingerprint analysis), but does NOT check for overlapping **existing tasks** in the `aitasks/` directory. This means a contribution could duplicate work already tracked internally.

This task adds a new Step 5b that uses the shared Related Task Discovery Procedure (created in sibling task t376_1) to detect overlapping existing tasks and offer to fold them into the newly imported task.

## Key Files to Modify

- **Modify:** `.claude/skills/aitask-contribution-review/SKILL.md` — Add Step 5b between current Steps 5 (Present Proposal) and 6 (Execute Import)

## Reference Files for Patterns

- `.claude/skills/task-workflow/related-task-discovery.md` — Shared procedure (created by t376_1)
- `.claude/skills/aitask-explore/SKILL.md` — Shows how explore invokes the procedure and handles results
- `.aitask-scripts/aitask_update.sh` — Has `--folded-tasks`, `--status Folded`, `--folded-into` flags
- `.aitask-scripts/aitask_issue_import.sh` — Output format: `Created: <path>` (single) or via `success "Merged N issues into: <path>"` (merge)

## Implementation Plan

### Step 1: Add Step 5b to contribution-review SKILL.md

Insert between current Steps 5 and 6:

```markdown
### Step 5b: Check for Overlapping Existing Tasks

Execute the **Related Task Discovery Procedure** (see `.claude/skills/task-workflow/related-task-discovery.md`) with:
- **Matching context:** The contribution's description, areas, file paths, and change type from Step 1
- **Purpose:** "check if existing tasks already cover this contribution"

If no overlapping tasks found: proceed to Step 6 as normal.

If overlapping tasks found, present options via AskUserQuestion:
- "Fold existing task(s) into new imported task" — proceed with import (Step 6), then fold
- "Update existing task instead" — skip import, update existing (see Step 6b, added by t376_3)
- "Ignore overlap" — proceed with normal import (Step 6)
```

### Step 2: Add post-import fold handling

After Step 6 (Execute Import), if "Fold existing task(s)" was selected:

1. Parse the import output to get the created task file path
   - Single import: output contains `Created: <filepath>`
   - Merge import: output contains `Merged N issues into: <filepath>`
2. Extract the task number from the filename (e.g., `t42` from `aitasks/t42_foo.md`)
3. Read each folded task file, merge their content into the new task's body (append under a "## Folded Tasks" section)
4. Update the new task's frontmatter:
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <new_task_num> --folded-tasks "<id1>,<id2>"
   ```
5. Mark each overlapping task as Folded:
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <old_task_num> --status Folded --folded-into <new_task_num>
   ```
6. Commit the fold changes:
   ```bash
   ./ait git add aitasks/
   ./ait git commit -m "ait: Fold existing tasks into t<new_task_num>"
   ```

## Verification Steps

1. Read the updated SKILL.md and trace through the logic for: (a) no overlap case, (b) fold case, (c) ignore case
2. Verify import output parsing handles both single and merge formats
3. Verify aitask_update.sh flags are correct for fold frontmatter updates
4. Test mentally with a scenario: contribution about "sed portability" overlaps existing task about "portable sed helper" → should detect and offer fold
