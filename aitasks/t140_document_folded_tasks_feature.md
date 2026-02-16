---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [aitasks_explore]
folded_tasks: [138]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-16 17:00
updated_at: 2026-02-16 17:01
---

## Context

The `/aitask-explore` skill's "folded tasks" feature (Steps 2b and 3 in SKILL.md) and the parallel exploration workflow are both fully implemented but under-documented in user-facing documentation.

## What Needs Documenting

### 1. Folded Tasks Feature

The folded tasks mechanism allows explore to discover existing pending tasks that overlap with a new task being created, and "fold" them in — incorporating their content into the new task and marking them for cleanup after implementation.

**Current state:**
- Fully specified in `.claude/skills/aitask-explore/SKILL.md` (Steps 2b and 3)
- `aitask_update.sh --folded-tasks` flag exists for setting the frontmatter field
- Cleanup logic exists in `.claude/skills/task-workflow/SKILL.md` (Step 9)
- **Not mentioned** in `docs/skills.md` (the `/aitask-explore` section, lines 117-147)
- **Not documented** in `docs/task-format.md` (the `folded_tasks` frontmatter field is missing from the schema)
- No examples of when/how folded tasks work in practice

**What to add:**
- Add `folded_tasks` field to the task frontmatter schema in `docs/task-format.md`
- Add a "Folded Tasks" subsection to the `/aitask-explore` section in `docs/skills.md` explaining:
  - What folded tasks are and when they appear during exploration
  - How the user is prompted to select tasks to fold in
  - What happens to folded tasks (content incorporated, originals deleted after implementation)
- Add a brief example scenario showing the folded tasks workflow

### 2. Parallel Exploration Workflow

Running `/aitask-explore` while waiting for other AI task work to complete is a natural and safe use case. The explore flow does not modify source files, so it can run in parallel with another task being implemented (similar to how running `ait board` or `ait create` can be done alongside active implementation).

**What to add:**
- Document this parallel workflow pattern in `docs/workflows.md` or `docs/skills.md`
- Explain that explore is read-only (no source modifications) and safe to run alongside implementation work
- Suggest this as a productivity pattern: explore while waiting for builds, tests, or other task implementations

## Key Files to Modify

1. **`docs/task-format.md`** — Add `folded_tasks` frontmatter field to the schema
2. **`docs/skills.md`** — Add folded tasks subsection and parallel workflow note to the `/aitask-explore` section
3. **`docs/workflows.md`** (optional) — Add parallel exploration workflow pattern

## Reference Files

- `.claude/skills/aitask-explore/SKILL.md` — Steps 2b and 3 for folded tasks implementation
- `.claude/skills/task-workflow/SKILL.md` — Step 9 for folded tasks cleanup
- `aiscripts/aitask_update.sh` — `--folded-tasks` flag implementation

## Verification Steps

1. Verify `folded_tasks` field is accurately documented in task-format.md
2. Cross-reference docs/skills.md additions with actual SKILL.md behavior
3. Ensure no existing content was accidentally removed or modified
4. Check that markdown formatting and heading nesting are correct

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t138** (`t138_aitaks_explore_workflow.md`)
