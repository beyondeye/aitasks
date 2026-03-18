# Aitask Redesign v1 Spec

## Problem Statement

`/aitask-redesign` exists for a common gap in the current workflow:

- a task or plan still captures valuable user intent, constraints, and pain
  points
- but the original design or implementation direction is no longer the right one

This happens after a full or partial revert, after infrastructure changes, after
technology choices change, or when the team wants to brainstorm alternatives
before implementation starts.

Today the repository has adjacent skills, but none of them solve this directly:

- `/aitask-revert` can undo implementation history, but it does not create a new
  design successor
- `/aitask-explore` starts from a vague idea, not from a task plus preserved
  task/plan history
- `/aitask-fold` merges overlapping tasks, but it is not a redesign workflow and
  does not preserve alternative designs side by side

`/aitask-redesign` should bridge that gap: start from an existing task/plan,
preserve the stable intent, replace the stale design, and produce a new task and
plan ready for later implementation.

## Goals

1. Preserve the useful intent from an existing task and plan.
2. Let the user adapt the design when requirements, infrastructure, or tools
   change.
3. Support both classical redesign and guided brainstorming of alternatives.
4. Produce artifacts that fit the existing aitasks lifecycle:
   - a new task in `aitasks/`
   - a new plan in `aiplans/`
5. Reuse the existing helper scripts and workflow patterns wherever possible.

## Non-Goals For v1

1. Do not edit the original task in place.
2. Do not redesign child tasks directly.
3. Do not automate AgentCrew-powered deep brainstorming.
4. Do not automatically close, fold, or mutate the original task after the new
   redesign task is created.

The original task remains a historical reference in v1. Any cleanup or
follow-up state changes happen later and explicitly.

## Why v1 Creates A New Task Instead Of Editing The Original

This is the central design decision for v1.

Creating a new redesign task is better than mutating the original task because
it preserves:

- the original design and task history for auditability
- the old implementation/revert chain without mixing it with the new design
- side-by-side comparison of alternative designs during brainstorming
- clear commit/changelog traceability for the redesigned implementation

Editing the original task in place would blur the line between the old design
and the new one, especially after a revert or partial revert.

## Supported Source Tasks In v1

### Supported

- active standalone parent tasks
- active parent tasks with children
- archived/completed standalone parent tasks
- archived/completed parent tasks with children
- deep-archived parent tasks after extraction

### Not Supported

- direct redesign of child tasks like `42_1`

If child-task redesign becomes important later, it should be added as a follow-up
after the parent-level workflow is stable.

## Output Model

`/aitask-redesign` creates two artifacts after user approval:

1. **A new redesign task** in `aitasks/`
2. **A matching redesign plan** in `aiplans/`

The new task is standalone in v1. It references the original task and plan, but
it does not fold them and does not replace them automatically.

### Naming Convention

Use this pattern for the new task name:

- `redesign_t<source_id>_<focus>`

Examples:

- `t420_redesign_t259_batch_reviews_for_agentcrew.md`
- `t421_redesign_t180_settings_ui_alternative.md`

The matching plan follows the normal `t -> p` conversion:

- `aiplans/p420_redesign_t259_batch_reviews_for_agentcrew.md`

## User-Facing Modes

`/aitask-redesign` supports two modes in v1.

### 1. Redesign Existing Task

Use when the old design is no longer valid because:

- requirements changed
- the implementation direction was wrong
- a revert removed the previous implementation
- infrastructure or technology choices changed

### 2. Brainstorm Alternatives

Use when the source task and plan still exist, but the user wants to explore
alternative designs before implementation starts or resumes.

This mode still ends by selecting one approved direction and creating a new
redesign task and plan. It does not leave the redesign as an unstructured chat.

## Workflow

### Step 0: Select Execution Profile

Reuse the normal execution profile selection procedure.

The main profile key reused in v1 is `explore_auto_continue`, controlling
whether the new redesign task should immediately continue into implementation.

### Step 1: Source Task Discovery

#### Direct argument path

Accept `42` or `t42`.

- First try active resolution:
  - `./.aitask-scripts/aitask_query_files.sh resolve <id>`
- Then resolve archived/deep-archived storage:
  - `./.aitask-scripts/aitask_revert_analyze.sh --find-task <id>`
- If the task lives in deep archive, unpack it before reading.

#### Interactive path

If no argument is supplied, present three discovery options:

1. `Browse active pending tasks`
   - use `./.aitask-scripts/aitask_ls.sh -v 15`
2. `Browse completed or archived tasks`
   - use `./.aitask-scripts/aitask_revert_analyze.sh --recent-tasks --limit 20`
3. `Enter task ID`

This split is important because redesign is valid both before and after
implementation.

### Step 2: Load Source Context

Once the source task is selected:

1. Read the source task file.
2. Read the source plan file if one exists.
3. If the source task is a parent task with children:
   - prefer archived child plans from `aiplans/archived/p<id>/`
   - otherwise use pending child plans from `aiplans/p<id>/`
   - use child task files only as secondary context

The redesign workflow should extract stable intent, not copy stale details
blindly.

### Step 3: Capture The Redesign Trigger

Offer explicit trigger choices:

- `Post-revert redesign`
- `Changed requirements`
- `Changed infrastructure or tech`
- `Brainstorm alternatives`
- `Other`

The selected trigger shapes the wording of the new redesign task and plan.

### Step 4: Clarify Constraints One Question At A Time

Inspired by the superpowers brainstorming skill, v1 should ask focused,
sequential questions rather than batching many questions together.

Key topics to clarify:

- what must still be preserved from the original task
- what is now obsolete
- what changed technically or product-wise
- what success looks like for the redesign

### Step 5: Propose 2-3 Approaches

Before any file creation, the skill should present 2-3 candidate redesign
approaches with trade-offs and a recommendation.

This is the main brainstorming value of the skill. The user should not be forced
into a single inferred solution.

### Step 6: Approval Gate

Do not create any task or plan until the user approves one redesign direction.

If the user wants changes, loop back through clarification and approach updates.

### Step 7: Create The New Redesign Task

Create a new standalone task with `aitask_create.sh --batch --commit`.

The description must preserve the source context but be written as a forward
looking task, not as a retrospective note.

### Step 8: Write The Matching Redesign Plan

Immediately create a matching plan file in `aiplans/` so the redesign output is
ready for `/aitask-pick <newid>` later.

The plan should be detailed enough that a later implementation run can reuse it
directly.

### Step 9: Continue Now Or Save For Later

After the redesign task and plan are created:

- `Continue to implementation` -> hand off the new task to the shared
  task-workflow
- `Save for later` -> end cleanly and collect satisfaction feedback

## Redesign Task Template

The new redesign task body should follow this structure:

```md
## Source Context
- Original task: t<N>
- Original plan: aiplans/p<N>_...
- Trigger: <selected trigger>

## Stable Intent To Preserve
- <user goal>
- <important pain points>
- <constraints that still matter>

## What Changed Since The Original Design
- <requirement change>
- <infrastructure change>
- <revert outcome or obsolete assumptions>

## Candidate Directions Considered
1. <option A>
2. <option B>
3. <option C>

## Selected Direction
- <approved redesign>
- <why it was selected>

## Implementation Constraints
- <files/modules likely affected>
- <key interfaces or risks>

## Traceability Notes
- Original task remains unchanged in v1
- If a revert task exists, reference it here
```

## Redesign Plan Template

The redesign plan should follow the normal metadata header and include:

```md
---
Task: t<newid>_redesign_t<sourceid>_<focus>.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t<newid> - Redesign <source>

## Source References
- Original task: ...
- Original plan: ...
- Trigger: ...

## Stable Intent To Preserve
- ...

## Recommended Direction
- ...

## Implementation Steps
1. ...
2. ...
3. ...

## Verification
- ...

## Step 9 Note
- archive normally after implementation
```

## Why AgentCrew Deep Brainstorming Is Deferred In v1

The repository now has AgentCrew infrastructure, but a fully automated deep
brainstorming mode is still the wrong scope for v1.

Three open problems remain:

1. **User-in-the-loop checkpoints**
   - the redesign workflow depends on explicit user approval after the approach
     comparison stage
   - a DAG of background agents makes that checkpoint harder to model cleanly
2. **Synthesis ownership**
   - multiple brainstorming agents can produce conflicting alternatives
   - v1 still needs one clear place where the approved direction is distilled
     into a single redesign task and plan
3. **Operational complexity**
   - cost control, interruption, and partial-result reuse are still separate
     design questions

For v1, the safer path is:

- keep the redesign workflow single-agent and interactive
- borrow the *question cadence* and *approach comparison* ideas from the
  superpowers brainstorming skill
- leave AgentCrew integration for a dedicated follow-up once the approval and
  synthesis model is clearer

## Follow-Up Scope For A Future Deep-Brainstorm Skill

If the project later adds deep brainstorming, it should likely become either:

- a dedicated advanced mode of `/aitask-redesign`, or
- a separate `/aitask-brainstorm` skill

That follow-up should solve:

- how to pause for user approval between agent rounds
- how to merge multi-agent outputs into one approved redesign
- how to store intermediate brainstorming artifacts without polluting the main
  task history

## Acceptance Criteria For Child Tasks

### For `t399_2`

- implement the exact two-mode workflow above
- create a new redesign task and plan after approval
- do not edit the original task in place
- do not add new shell helpers unless there is a documented gap

### For `t399_3`

- document both supported v1 modes
- document the relationship between `/aitask-redesign` and `/aitask-revert`
- explain that v1 deep brainstorming is deferred

## Summary

The v1 contract for `/aitask-redesign` is:

- start from an existing parent/standalone task and its plan history
- preserve the stable intent
- replace the stale design through guided redesign or guided brainstorming
- require approval before creating files
- produce a new redesign task and a new redesign plan
- leave AgentCrew-powered deep brainstorming for later
