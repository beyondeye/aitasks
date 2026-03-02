---
Task: t288_complex_task_planning_workflow.md
Worktree: (current directory)
Branch: main
Base branch: main
---

# Plan: Document Complex Task Planning Workflow (t288)

## Context

Document a parallel-safe workflow where you run only the planning and child decomposition phase of a complex task — no code changes, just design work. This is a subpage of the existing "Parallel Development" workflow documentation.

## Implementation

Create a new Hugo documentation page at `website/content/docs/workflows/parallel-planning.md` covering:

1. The idea — front-load design work while other implementations run in parallel
2. Why it's safe — pure design work, no source code changes; plans verified at implementation time (double verification)
3. When to use it — complex features, preparing parallel workloads, design sessions
4. How it works — brief walkthrough from parent task creation through decomposition to later implementation
5. What you get — child tasks, implementation plans, auto-archiving parent

Also add a cross-reference from the existing parallel-development.md page.

## Final Implementation Notes

- **Actual work done:** Created `website/content/docs/workflows/parallel-planning.md` with high-level workflow documentation (no technical deep dives into skill internals). Added a "Parallel Planning" section to `website/content/docs/workflows/parallel-development.md` as a cross-reference.
- **Deviations from plan:** Initial plan was too technically detailed; revised per user feedback to focus on essential concepts: (1) it's design work that doesn't touch source code, (2) plans are double-verified (at decomposition and at implementation time). Removed mention of separate git branches/directories as a safety mechanism per user guidance.
- **Issues encountered:** None.
- **Key decisions:** Weight set to 45 (between parallel-development at 40 and other workflow pages). Included tip to add "this is a complex task that requires decomposition into child tasks" in parent task descriptions to trigger decomposition.
