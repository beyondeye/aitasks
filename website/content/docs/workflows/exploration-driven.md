---
title: "Exploration-Driven Development"
linkTitle: "Exploration-Driven"
weight: 75
description: "Start with codebase exploration, create tasks from findings"
---

Sometimes you don't know what the task should be. You have a vague symptom, an unfamiliar module to understand, or a hunch that something could be improved — but you can't write a task description yet because you haven't explored enough to know what needs doing. The [`/aitask-explore`](../../skills/aitask-explore/) skill is designed for exactly this situation.

**The philosophy: explore first, define the task from what you find.**

This inverts the normal aitasks flow. Instead of *define task → pick task → implement*, you follow *explore → discover → define task → implement*. The exploration phase is interactive and iterative — you direct Claude's investigation, review findings after each round, and decide when you've learned enough to crystallize a task.

## When to Use Exploration-Driven Development

- **Debugging a vague symptom** — "Something is slow" or "users report occasional errors" — you need to investigate before you can define a fix
- **Understanding unfamiliar code** — Onboarding to a new module or reviewing code you haven't touched in months
- **Looking for improvement opportunities** — You suspect there's technical debt or duplication but need to map it out first
- **Scoping a feature idea** — You have a rough idea but need to discover which files, modules, and patterns are involved before estimating effort
- **Documentation gaps** — You want to find where docs are missing or outdated but don't know the full scope yet

## Walkthrough: Investigating a Performance Issue

A user reports that "the task listing feels slow." You don't know where the bottleneck is, so you start with exploration.

**1. Launch the skill**

```
/aitask-explore
```

Select "Investigate a problem" when prompted. Describe the symptom: "Task listing via aitask_ls.sh feels slow with large task directories."

**2. First exploration round**

Claude traces the data flow in `aitask_ls.sh` — how tasks are read, sorted, and filtered. Findings: the script reads every task file to extract frontmatter, even when filtering by label. With 200+ task files, this adds up.

You're shown a summary and asked how to proceed. Select "Continue exploring" and redirect: "Check if there's any caching or if the frontmatter parsing could be optimized."

**3. Second exploration round**

Claude examines the frontmatter parsing function, finds it spawns a subshell per file, and identifies that `grep` + `sed` could replace the current `awk` approach. Also discovers that archived tasks are excluded early (good) but the sort happens after all files are read (potential improvement: sort during read).

The findings are clear enough. Select "Create a task."

**4. Task creation**

Claude summarizes the exploration:
- Focus: Performance of `aitask_ls.sh` with large task sets
- Key findings: per-file subshell overhead, sequential read-then-sort pattern
- Suggested task: "Optimize aitask_ls.sh frontmatter parsing for large directories"

The task is created with metadata pre-filled from the exploration type (`issue_type: bug`, `priority: high`). You confirm and select "Continue to implementation" to hand off to the standard [`/aitask-pick`](../../skills/aitask-pick/) workflow.

## The Four Exploration Modes

Each mode sets a different investigation strategy and task defaults:

| Mode | Best for | Default task type |
|------|----------|-------------------|
| **Investigate a problem** | Bugs, performance issues, error tracing | `bug` (high priority) |
| **Explore codebase area** | Understanding modules, mapping dependencies | `feature` (medium priority) |
| **Scope an idea** | Estimating blast radius of a proposed change | `feature` (medium priority) |
| **Explore documentation** | Finding doc gaps, outdated content, missing help text | `documentation` (medium priority) |

## Consolidating Related Work

During task creation, `/aitask-explore` scans pending tasks for overlap with your findings. If it finds existing tasks that your new task would fully cover, you can **fold them in** — their content is incorporated into the new task description, and the originals are cleaned up after implementation.

This prevents duplicate tasks from accumulating when multiple exploration sessions or different team members discover the same issues. For folding tasks outside of the explore workflow, use [`/aitask-fold`](../../skills/aitask-fold/).

## Tips

- **Redirect freely** — After each exploration round, you can shift focus. Start broad, then narrow in on what matters
- **Don't over-explore** — Two or three rounds is usually enough. Create the task when you have a clear picture, even if some details remain — the planning phase will fill in the rest
- **Use profiles** — The `explore_auto_continue` profile key controls whether you're prompted to continue to implementation or save the task for later. Set it to `true` in your profile if you always want to implement immediately
