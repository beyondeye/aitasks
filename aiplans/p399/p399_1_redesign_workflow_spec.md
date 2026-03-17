---
Task: t399_1_redesign_workflow_spec.md
Parent Task: aitasks/t399_aitaskredesign.md
Sibling Tasks: aitasks/t399/t399_2_implement_redesign_skill.md, aitasks/t399/t399_3_document_redesign_workflows.md
Archived Sibling Plans: aiplans/archived/p399/p399_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t399_1 - Redesign Workflow Spec

## Goal

Produce a clear design note that fixes the v1 behavior of `/aitask-redesign`
before any implementation work starts.

## Files

- `aidocs/aitask_redesign_spec.md` (new)

## Steps

1. Review the parent task and all reference workflows.
2. Define the v1 problem statement and non-goals.
3. Define the exact input model and the exact output model.
4. Define the supported redesign modes and the approval checkpoints.
5. Define the task-template and plan-template text child `t399_2` will write.
6. Document the AgentCrew/deep-brainstorming decision as deferred scope.
7. Update this plan with final implementation notes once the spec is complete.

## Verification

- the spec can be handed directly to child `t399_2` without ambiguity
- the spec answers the new-task-vs-edit-in-place question
- the spec clearly marks deep brainstorming as follow-up scope

## Step 9 Note

When this child is completed, archive it normally so later sibling tasks can use
its archived plan as the primary reference.
