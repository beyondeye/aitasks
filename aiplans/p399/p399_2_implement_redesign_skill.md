---
Task: t399_2_implement_redesign_skill.md
Parent Task: aitasks/t399_aitaskredesign.md
Sibling Tasks: aitasks/t399/t399_1_redesign_workflow_spec.md, aitasks/t399/t399_3_document_redesign_workflows.md
Archived Sibling Plans: aiplans/archived/p399/p399_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t399_2 - Implement Redesign Skill

## Goal

Implement the approved `/aitask-redesign` workflow in the Claude source skill
and expose it through the existing wrapper conventions.

## Files

- `.claude/skills/aitask-redesign/SKILL.md`
- optional helper markdowns under `.claude/skills/aitask-redesign/`
- `.agents/skills/aitask-redesign/SKILL.md`
- `.opencode/skills/aitask-redesign/SKILL.md`
- `.opencode/commands/aitask-redesign.md`

## Steps

1. Read `aidocs/brainstorming/aitask_redesign_spec.md` from child `t399_1`.
2. Create the Claude source skill skeleton with frontmatter, arguments, and
   execution-profile handling.
3. Implement source-task discovery and context loading using existing helpers.
4. Implement redesign-trigger selection plus the guided question flow.
5. Implement the 2-3 approach comparison and approval checkpoint.
6. Implement redesign task creation.
7. Implement matching redesign plan creation.
8. Implement continue-now vs save-for-later behavior and feedback handling.
9. Add OpenCode and unified Codex/Gemini wrappers.
10. Update this plan with final notes, especially if any new helper script was
    needed.

## Verification

- the workflow has a coherent direct-id path
- wrapper files match existing repository conventions
- task and plan outputs use the expected naming and traceability structure

## Step 9 Note

When this child is completed, archive it normally so the archived plan becomes
the primary reference for the documentation child.
