---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask-redesign, brainstorming]
created_at: 2026-03-17 18:51
updated_at: 2026-03-17 18:51
---

## Redesign Workflow Spec

### Context

Parent task `t399` needs a new `/aitask-redesign` skill that preserves the
useful user intent from an existing task/plan while allowing the concrete design
to change. The source research for this child must draw from the current
workflow building blocks already present in the repository:

- `.claude/skills/aitask-revert/SKILL.md`
- `.claude/skills/aitask-explore/SKILL.md`
- `.claude/skills/aitask-fold/SKILL.md`
- `.claude/skills/task-workflow/planning.md`
- `aidocs/agentcrew_architecture.md`
- `aidocs/agentcrew_work2do_guide.md`
- the external `superpowers` brainstorming skill referenced in the parent task

The expected output of this child is a source-of-truth spec at
`aidocs/aitask_redesign_spec.md` that makes the later implementation mostly
mechanical.

### Key Files To Modify

- `aidocs/aitask_redesign_spec.md` - new design note defining the v1 workflow
- `aiplans/p399/p399_1_redesign_workflow_spec.md` - update with final notes once
  the design decisions are locked

### Reference Files For Patterns

- `.claude/skills/aitask-revert/SKILL.md` - task discovery and traceability
- `.claude/skills/aitask-explore/SKILL.md` - create-a-task workflow and guided
  exploration style
- `.claude/skills/aitask-fold/SKILL.md` - related task treatment and save vs
  continue handoff pattern
- `.claude/skills/task-workflow/satisfaction-feedback.md` - standalone feedback
  collection behavior

### Implementation Plan

1. Re-read the parent task and the reference skills/docs listed above.
2. Write a short problem statement explaining what `/aitask-redesign` adds that
   `/aitask-revert`, `/aitask-explore`, and `/aitask-fold` do not already do.
3. Define the exact v1 input model:
   - direct task-id invocation
   - interactive task discovery when no id is passed
   - source task states supported in v1 (active, archived, deep archived)
   - source task types supported in v1 (parent/standalone only)
4. Define the exact v1 output model:
   - create a **new** redesign task in `aitasks/`
   - create a matching redesign plan in `aiplans/`
   - leave the original task untouched in v1
5. Define the two supported modes:
   - redesign after changed constraints or after a revert
   - brainstorm alternative designs from an existing task/plan
6. Define the exact user flow:
   - resolve source task and plan
   - capture redesign trigger
   - ask one clarifying question at a time
   - propose 2-3 approaches with trade-offs
   - present the recommended redesign and require approval
   - create the redesign task and plan
   - offer continue-now vs save-for-later
7. Write the exact task and plan templates child 2 must implement.
8. Add a clear scope decision for AgentCrew deep brainstorming:
   explain why it is deferred in v1, and describe what a future follow-up would
   need to solve before it becomes safe to automate.

### Verification Steps

- `aidocs/aitask_redesign_spec.md` explicitly defines both redesign and
  brainstorm modes
- the spec explains why v1 creates a new task instead of editing the old task
- the spec names the exact files child 2 and child 3 are expected to create
- the spec documents deep brainstorming as deferred scope rather than leaving it
  ambiguous
