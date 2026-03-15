---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [workflow, contribution]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-15 17:05
updated_at: 2026-03-15 22:48
completed_at: 2026-03-15 22:48
---

## Bug: Archive workflow only closes primary issue, ignores related_issues

When a merged contribution task (created via `aitask_issue_import.sh --merge-issues`) is archived, only the primary `issue:` field is processed. The `related_issues:` array (which holds URLs of all source issues merged into the task) is completely ignored during archival. This means secondary source issues are never offered for closing/commenting.

### Reproduction

1. Import multiple contribution issues into a single task with `--merge-issues`
2. Implement and archive the task
3. Only the primary `issue:` URL is offered for closing — all `related_issues:` URLs are silently skipped

### Root Cause (3 locations)

1. **`aitask_archive.sh` (~line 213)** — Uses `extract_issue_url()` from `task_utils.sh` which only reads the singular `issue:` field. Never reads `related_issues:`. Only emits one `ISSUE:<task_num>:<url>` line.

2. **Task workflow `procedures.md` (Issue Update Procedure)** — Only handles `ISSUE:` output lines from the archive script. No handling for related issues.

3. **Possible: `aitask_issue_import.sh` `inject_merge_frontmatter()`** — May silently fail to inject `related_issues` in some edge cases. Needs verification.

### Proposed Fix

1. **`task_utils.sh`** — Add `extract_related_issues()` function that reads the `related_issues:` YAML array from frontmatter and returns URLs one per line.

2. **`aitask_archive.sh`** — After emitting `ISSUE:` for the primary issue, also call `extract_related_issues()` and emit `RELATED_ISSUE:<task_num>:<url>` for each.

3. **Task workflow `SKILL.md`** — In Step 9 archive output parsing, add handling for `RELATED_ISSUE:` lines. Offer the same close/comment/skip options as for primary issues.

4. **`procedures.md`** — Update the Issue Update Procedure to document `RELATED_ISSUE:` handling.

5. **Verify** `inject_merge_frontmatter()` in `aitask_issue_import.sh` reliably writes `related_issues` for merged imports.

### Key Files

- `.aitask-scripts/aitask_archive.sh` — emit RELATED_ISSUE lines
- `.aitask-scripts/lib/task_utils.sh` — add extract_related_issues()
- `.claude/skills/task-workflow/SKILL.md` — handle RELATED_ISSUE in Step 9
- `.claude/skills/task-workflow/procedures.md` — document RELATED_ISSUE handling
- `.aitask-scripts/aitask_issue_import.sh` — verify inject_merge_frontmatter()

### Verification

- Create a test task with both `issue:` and `related_issues:` fields
- Run archive and confirm both `ISSUE:` and `RELATED_ISSUE:` lines are emitted
- Verify the workflow offers to close/comment on all linked issues
