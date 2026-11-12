---
title: "Reporting Work to Managers"
linkTitle: "Work Report"
weight: 86
description: "Draft a forward-looking status report from the board columns you already maintain"
depth: [intermediate]
---

The [`/aitask-work-report`]({{< relref "/docs/skills/aitask-work-report" >}}) skill drafts a manager-facing status report from your board, so you do not retype the board's priorities into a separate document that then drifts from it. You pick the board columns that represent your committed work, review which tasks belong in the report, and your coding agent drafts the summary from the task and plan records that already exist.

The draft is built from the board at the moment you ask for it, so it follows the board's current columns and their top-to-bottom order.

## Why Report from the Board

A work report covers what is being worked on now and what comes next. For what has already shipped, see [Releases]({{< relref "/docs/workflows/releases" >}}).

Board columns hold exactly that. Whatever your columns mean (a `now` / `next` / `backlog` split, or a set of named workstreams), membership is a deliberate decision you already made, and each column's order is the priority order you already maintain. The skill preserves both, so the report's structure mirrors the board a manager could look at directly.

Because the report is drafted from task descriptions, metadata, dependencies, and active plans, it describes intended outcomes and current status rather than implementation detail. Parent tasks with children are summarized at manager level, as in "3 of 5 subtasks complete", instead of listing each subtask.

## Walkthrough: Reporting from the Board

Suppose you maintain a project with `now`, `next`, and `backlog` columns, and your manager wants to know what this week looks like.

1. Open the board with `ait board` and move focus to any card in the `now` column, or to the column's placeholder if it is collapsed or empty.

2. Press `w`. The Work Report action is column-scoped, so it is available whenever the focused card or column placeholder belongs to a board column. It is hidden in the In-Flight, By-Topic and By-Trail views, which group tasks by their state, topic or trail instead of by board column.

   If you maintain an [implementation trail]({{< relref "/docs/workflows/implementation-trails" >}}) and want to report on a planned sequence, press `M` in the By-Trail view to move a whole wave into a column in wave order, and then report on that column. The trail affects a report only through that move, which you make yourself and can check on the board first.

3. Choose the columns. A picker opens with the focused column already checked. Check `next` as well if the report should cover upcoming work. **Space** toggles, **Enter** confirms, **Escape** cancels.

4. Review task membership. A second picker lists every task in the chosen columns, grouped by column and in board order, with all of them checked. Deselect anything that should not appear, such as a placeholder task or something a manager does not need to hear about. The list always shows the full contents of each selected column, regardless of any search text or view filter currently narrowing the board, so what you exclude here is the only thing that shrinks the report.

5. Launch the agent. The standard agent-command dialog opens, showing the exact command to be run, with the reviewed selection passed explicitly:

   ```
   /aitask-work-report --columns now,next --tasks 42,17,8
   ```

   You can change the agent, model, or execution profile for this run before launching, or edit the command directly.

6. Choose a horizon and review the draft. The agent asks what period the report covers: **Today**, **This week**, or a custom label such as a sprint name. The horizon labels the report only; it never changes which tasks are in it. The draft is then presented in the session for you to iterate on. Nothing is written to disk, so you decide whether the final text goes into an email, a chat message, or a planning document.

## Reporting Without the Board

The skill works standalone, which is useful over SSH or when scripting the same report repeatedly:

```
/aitask-work-report
```

Invoked bare, it discovers the reportable columns, asks which to include, and then walks the same membership review. Passing `--columns` (optionally with `--tasks`) skips straight to drafting, which is what the board does on your behalf.

## Reading the Projection

By default the report ends with observed throughput: recent completion rates with the sample size behind each figure. If you ask for a forecast, the skill adds a projected completion date for the selected work.

That date is an extrapolation from the count of completed tasks, so it knows nothing about task size, blockers, or who is available, and the report says so wherever the figure appears. It also holds back in two cases:

- Without enough completion history in the measurement window, the report says so instead of inventing a rate.
- Only a "Today" horizon gets a verdict on whether the work fits or exceeds it. For a week or a custom label, the report gives the projected date and leaves the judgement to you.

The measurement window defaults to the last 90 days and the estimator averages by weekday, which suits teams whose output varies across the week. For a single all-days average, add `--velocity-model flat` to the `/aitask-work-report` command; `--velocity-window <days>` changes the window. Both are listed on the [skill page]({{< relref "/docs/skills/aitask-work-report" >}}).

## Tips

- **Report the columns you commit to.** A report built from `now` and `next` reads as a plan. One built from every column, including the backlog, reads as a wish list.
- **Curate at the membership review.** Drop internal chores in the task multi-select. Editing them out of the draft afterwards loses the traceable task ids.
- **Reorder cards, not prose.** The report follows board order, so reorder cards before reporting instead of reordering the draft afterwards.
- **The selection is validated before drafting.** If the board has changed since a selection was made, the skill stops and offers to re-select instead of reporting a stale picture.
- **Set the agent default once.** Work reports are read-only summarization, so a lighter model is usually the right default. See the [`ait codeagent` reference]({{< relref "/docs/commands/codeagent" >}}).
