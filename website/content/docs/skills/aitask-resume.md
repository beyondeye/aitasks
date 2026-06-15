---
title: "/aitask-resume"
linkTitle: "/aitask-resume"
weight: 14
description: "Resume an in-flight task from its gate-ledger checkpoint — the programmatic re-entry surface"
maturity: [experimental]
depth: [intermediate]
---

`/aitask-resume <task-id>` re-enters a task that was left **in-flight**
(`Implementing`) — after a crash, a lost session, or multi-day work — and resumes
it from the **first unmet recorded checkpoint** instead of restarting at
planning. It is the **programmatic** re-entry surface: a direct "resume this
specific task" entry without the [`/aitask-pick`](../aitask-pick/) browsing
funnel, intended for re-entry testing, TUI/board In-Flight launches, and any
surface that already knows the task id.

> **Most users want [`/aitask-pick <id>`](../aitask-pick/) instead.** Picking an
> in-flight task already re-enters it through the same engine. Reach for
> `/aitask-resume` when you want the direct, funnel-free entry point.

**Usage:**
```
/aitask-resume 42          # Parent task
/aitask-resume 42_2        # Child task
/aitask-resume 42_2 --gate review_approved   # also report a gate's state
```

A task ID is **required**. A parent that has children is rejected — resume is
single-task scoped, so pass a specific child id.

> **Note:** Must be run from the project root directory. See
> [Skills overview](..) for details.

## How it resumes

`/aitask-resume` does not contain its own resume logic — it resolves the task and
hands off to the shared task workflow, which reads the task's **gate ledger** and
derives a three-state resume point:

| Resume point | Condition | Resumes at |
|--------------|-----------|------------|
| **Plan** | no plan checkpoint recorded (empty ledger) | plan from scratch (same as a fresh pick) |
| **Implement** | plan approved, review not yet recorded | the implementation step |
| **Post-implementation** | review recorded | the merge / build / archive step |

Ownership is always (re)claimed before any work resumes; the reclaim prompt shows
the resume target. If the task is **not** in-flight (or nothing was recorded
yet), resuming behaves exactly like a fresh `/aitask-pick` and plans from scratch.

Resume state is recorded only for execution profiles that enable gate recording
(the `fast` profile does by default). A task with an empty ledger always derives
to *Plan*, so profiles that record nothing are unchanged.

## The `--gate` argument

`--gate <name>` reports the current recorded state of a single gate from the
ledger. Automated per-gate verifier execution is handled by the gate
orchestrator; until that ships, `--gate` reports state only and runs no verifier.
To record a human-gate sign-off, use `ait gate pass <task-id> <name>`.

## Execution Profiles

`/aitask-resume` honors the same execution profiles as `/aitask-pick` (resolved
from `userconfig` / `project_config`, or overridden with `--profile <name>`). The
profile governs how the downstream workflow behaves once the task is resumed. See
[Execution Profiles](../aitask-pick/execution-profiles/).
