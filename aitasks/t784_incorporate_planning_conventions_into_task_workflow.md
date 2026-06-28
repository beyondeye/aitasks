---
priority: medium
effort: medium
depends: [783]
issue_type: refactor
status: Ready
labels: [agents_md]
created_at: 2026-05-18 12:30
updated_at: 2026-05-20 12:25
boardidx: 400
---

## Context

t783 compacted CLAUDE.md by externalising specialist rules into focused aidocs files. Among those, `aidocs/planning_conventions.md` was extracted but the rules really belong inside the planning procedure that the task-workflow skill runs (`.claude/skills/task-workflow/planning.md`) — that way they fire at plan-authoring time instead of relying on the agent to remember to read a separate doc.

## Goal

Move the six planning rules from `aidocs/planning_conventions.md` into `.claude/skills/task-workflow/planning.md` (or co-located helper file referenced from it), then trim the aidoc accordingly.

## Rules to incorporate

From `aidocs/planning_conventions.md`:
1. **Refactor duplicates before adding to them** — fires when a plan would edit the same list/config in 3+ files. Best surfaced as a step in 6.1 (Planning) right after "Create a detailed, step-by-step implementation plan".
2. **Plan split: in-scope sibling children, not deferred follow-ups** — fires during complexity assessment / child-task creation. Already partly aligned with the existing Step 6.1 "If creating child tasks" branch.
3. **Dead code goes into the sibling refactor task — never a vague follow-up** — fires during child-task plan authoring.
4. **Gate plans on in-flight related tasks instead of forking ahead** — fires during exploration. Could become a check in 6.1 before drafting.
5. **No fallback-read workarounds for sync/desync root causes** — design-time rule; could become a "Anti-patterns to avoid" callout in the plan template.
6. **Audit-only tasks with zero findings produce audit-only plans** — design-time rule; could become an "Audit task pattern" note.

## Approach

- Audit each rule against the current `.claude/skills/task-workflow/planning.md` structure.
- For rules that map cleanly to a numbered step, inline them at that step (terse — one short paragraph each).
- For rules that are design-time anti-patterns rather than per-step actions, add a brief "Planning Anti-patterns" section near the top of `planning.md` (or extract to a sibling `planning-anti-patterns.md` if it grows).
- Mirror the changes into the sibling agent trees (`.agents/skills/task-workflow/`, `.gemini/skills/task-workflow/`, `.opencode/skills/task-workflow/`) per the skills-source-of-truth convention in CLAUDE.md.
- Once content is incorporated:
  - **If all rules land in planning.md**: delete `aidocs/planning_conventions.md` and remove its pointer from CLAUDE.md.
  - **If some rules remain too detailed for inlining** (e.g., the refactor-duplicates rule has a longer worked example): trim `aidocs/planning_conventions.md` to just the remaining rules and update the CLAUDE.md pointer to reflect what's left.

## Files to touch

- `.claude/skills/task-workflow/planning.md` (primary edit)
- `aidocs/planning_conventions.md` (trim or delete)
- `CLAUDE.md` (update or remove planning-conventions pointer)
- Mirrors in `.agents/`, `.gemini/`, `.opencode/` skill trees

## Dependencies

Depends on t783 (where these aidocs files were first created).

## Verification

- `./ait skill verify` passes after planning.md edits.
- Spot-check a real plan-authoring run via `/aitask-pick` on a small task; confirm the relocated rules surface at the right step.
- Confirm CLAUDE.md still resolves all its `aidocs/...` pointers (or that the removed pointer has no dangling references).
