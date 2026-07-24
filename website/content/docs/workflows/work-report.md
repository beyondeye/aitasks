---
title: "Reporting Work to Managers"
linkTitle: "Work Report"
weight: 86
description: "Draft a forward-looking status report from the board columns you already maintain"
depth: [intermediate]
---

Status reporting is usually a second bookkeeping system: the real priorities live on the board, and then somebody retypes them into a document for a manager, where they immediately start drifting. The [`/aitask-work-report`](../../skills/aitask-work-report/) skill removes the retyping step. You pick the board columns that represent your committed work, review which tasks belong in the report, and your coding agent drafts a manager-facing summary from the task and plan records that already exist.

**The key insight: the board's column membership and top-to-bottom ordering already encode your priorities. A report generated from them is correct by construction; a hand-written one is a copy that starts going stale the moment it is saved.**

## Why Report from the Board

A work report answers a different question than a changelog. [Releases](../releases/) look backward at what shipped; a work report looks forward at what is being worked on now and next.

Board columns are the natural source for that. Whatever your columns mean — a `now` / `next` / `backlog` split, or a set of named workstreams — membership is a deliberate decision you already made, and each column's order is the priority order you already maintain. The skill preserves both, so the report's structure mirrors the board a manager could look at directly.

Because the report is drafted from task descriptions, metadata, dependencies, and active plans, it describes intended outcomes and current status rather than implementation detail. Parent tasks with children are summarized at manager level — "3 of 5 subtasks complete" — instead of exposing the subtask breakdown.

## Walkthrough: Reporting from the Board

Suppose you maintain a project with `now`, `next`, and `backlog` columns, and your manager wants to know what this week looks like.

**1. Focus the column you want to report on**

Open the board and move focus to any card in the `now` column — or to the column's placeholder if it is collapsed or empty.

```bash
ait board
```

**2. Press `w`**

The Work Report action is column-scoped, so it is available in the persistent kanban views whenever a focused card or column placeholder identifies a column. It is hidden in the In-Flight and By-Topic views, which render derived lanes rather than columns.

**3. Choose the columns**

A picker opens with the focused column already checked. Check `next` as well if the report should cover upcoming work. Space toggles, Enter confirms, Escape cancels.

**4. Review task membership**

A second picker lists every task in the chosen columns, grouped by column and in board order, with all of them checked. This is an *exclusion* review — deselect anything that should not appear, such as a placeholder task or something a manager does not need to hear about.

> **Note:** This list always shows the full contents of each selected column, regardless of any search text or view filter currently narrowing the board. What you exclude here is the only thing that shrinks the report.

**5. Launch the agent**

The standard agent-command dialog opens, showing the exact command to be run, with the reviewed selection passed explicitly:

```
/aitask-work-report --columns now,next --tasks 42,17,8
```

You can change the agent, model, or execution profile for this run before launching, or edit the command directly.

**6. Choose a horizon and review the draft**

The agent asks what period the report covers — **Today**, **This week**, or a custom label such as a sprint name. This labels the report only; it never changes which tasks are in it. The draft is then presented in the session for you to iterate on. Nothing is written to disk, so you decide whether the final text goes into an email, a chat message, or a planning document.

## Reporting Without the Board

The skill works standalone, which is useful over SSH or when scripting the same report repeatedly:

```
/aitask-work-report
```

Invoked bare, it discovers the reportable columns, asks which to include, and then walks the same exclusion review. Passing `--columns` (optionally with `--tasks`) skips straight to drafting — this is exactly what the board does on your behalf.

## Reading the Projection

By default the report ends with observed throughput: recent completion rates with the sample size behind each figure. If you ask for a forecast, the skill adds a projected completion date for the selected work.

Treat that date as an extrapolation, not a plan. It is derived by counting completed tasks, so it knows nothing about task size, blockers, or who is available — and the report says so wherever the figure appears. Two guardrails keep it honest:

- **It refuses to guess.** Without enough completion history in the measurement window, the report states that plainly instead of inventing a rate.
- **It only judges the horizon it can.** For a "Today" horizon the report says whether the work fits or exceeds it. For a week or a custom label, it gives you the projected date and leaves the judgement to you.

The measurement window defaults to the last 90 days and the estimator averages by weekday, which suits teams whose output varies across the week. A flat all-days average is available when that fits better.

## Tips

- **Report the columns you commit to, not everything** — A report built from `now` and `next` reads as a plan. One built from every column, including the backlog, reads as a wish list.
- **Curate at the exclusion step** — The task multi-select is the right place to drop internal chores. Editing them out of the draft afterwards loses the traceable task ids.
- **Board order is priority order** — Reorder cards before reporting rather than reordering prose afterwards; the report follows the board.
- **The selection is validated before drafting** — If the board moved on since a selection was made, the skill stops and offers to re-select rather than reporting a stale picture.
- **Set the agent default once** — Work reports are read-only summarization, so a lighter model is usually the right default. See the [`ait codeagent` reference]({{< relref "/docs/commands/codeagent" >}}).
