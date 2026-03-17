---
Task: t399_3_document_redesign_workflows.md
Parent Task: aitasks/t399_aitaskredesign.md
Sibling Tasks: aitasks/t399/t399_1_redesign_workflow_spec.md, aitasks/t399/t399_2_implement_redesign_skill.md
Archived Sibling Plans: aiplans/archived/p399/p399_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t399_3 - Document Redesign Workflows

## Goal

Document the finished `/aitask-redesign` behavior clearly enough that users can
understand when to use it, what it creates, and how it relates to
`/aitask-revert`.

## Files

- `website/content/docs/skills/aitask-redesign.md`
- `website/content/docs/workflows/task-redesign.md`
- `website/content/docs/skills/_index.md`
- `docs/README.md`
- `website/content/docs/skills/verified-scores.md` if needed

## Steps

1. Read the final implemented workflow from child `t399_2`.
2. Write the skill reference page.
3. Write the workflow guide with redesign and brainstorm examples.
4. Update the skill index and docs inventory.
5. Update verified-scores docs if the skill collects feedback.
6. Run `hugo build --gc --minify` and fix any issues.
7. Update this plan with final documentation notes.

## Verification

- the docs explain both supported v1 modes
- the docs explain the relationship to `/aitask-revert`
- the website builds successfully

## Step 9 Note

When this child is completed, archive it normally so the final docs history is
captured in the archived plan.
