---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [aitask_fold, task_workflow]
children_to_implement: [t522_1]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-12 08:08
updated_at: 2026-04-12 09:53
---

Several folding procedures (task-fold-content.md, task-fold-marking.md, the new ad-hoc fold procedure in planning.md, and the validation logic in aitask-fold/SKILL.md Step 0b) currently express their logic as step-by-step instructions for Claude Code. This means each caller has to execute several shell commands in sequence and parse their outputs.

Investigate whether some of this logic can be off-loaded into new helper bash scripts (or by extending existing scripts) to reduce instruction complexity, improve consistency, and minimize the chance of misexecution by Claude Code.

## Areas to investigate

1. **Fold candidate validation** — Currently each caller must:
   - Resolve task file (different command for parent vs child IDs)
   - Read frontmatter and check status
   - Check for children
   - Skip ineligible tasks with warnings

   Could be a single script: `./.aitask-scripts/aitask_fold_validate.sh <id1> <id2> ...` that returns `VALID:<id>:<path>`/`INVALID:<id>:<reason>` lines.

2. **Build merged description** — task-fold-content.md is a markdown procedure for constructing the merged description body. Could be a script: `./.aitask-scripts/aitask_fold_content.sh <primary_file> <folded_file1> <folded_file2> ...` that prints the merged description to stdout.

3. **Full fold execution** — The combination of content merge + marking + commit could be a single script: `./.aitask-scripts/aitask_fold_apply.sh <primary_id> <folded_id1> <folded_id2> ...` that executes the entire fold sequence including transitive handling and commit. This would replace the dual procedure invocation in callers.

4. **Parent cleanup for child tasks** — The new Step 4b in task-fold-marking.md (and the safety-net in handle_folded_tasks) does parent cleanup. This logic should ideally live in one place — likely the script if we create one.

## Goals

- Reduce instruction complexity in skill markdown files
- Make folding behavior consistent across all callers (aitask-fold, aitask-explore, aitask-pr-import, ad-hoc planning fold, etc.)
- Ensure scripts handle macOS portability concerns (sed, grep, wc, mktemp — see CLAUDE.md)
- Maintain backwards compatibility — existing callers should continue to work or be updated atomically
- Add tests for new scripts following the existing test patterns in tests/

## Reference

This task was created as a follow-up to t520 (better folding support), which added ad-hoc folding during planning and enabled folding of child tasks. See aiplans/archived/p520_better_folding_support.md once t520 is archived.
