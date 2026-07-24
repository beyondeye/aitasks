---
title: "/aitask-work-report"
linkTitle: "/aitask-work-report"
weight: 62
description: "Draft a manager-facing work report from selected board columns"
maturity: [stable]
depth: [intermediate]
---

Draft a first-person, manager-facing report of what you are working on, built from the tasks in the board columns you select. Membership and ordering come from the board itself, so the report reflects the priorities you actually maintain rather than a hand-written list.

**Usage:**
```
/aitask-work-report
/aitask-work-report --columns now,next
/aitask-work-report --columns now,next --tasks 42,17,8
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Arguments

All arguments are optional. Invoked bare, the skill selects columns and tasks interactively.

| Argument | Description |
|----------|-------------|
| `--columns <csv>` | Column ids to report on. Skips the interactive column picker. |
| `--tasks <csv>` | Task ids, order significant. Requires `--columns`. A leading `t` is accepted and normalized. |
| `--velocity-model <id>` | Throughput estimator: `dow` (per-weekday averages, the default) or `flat` (a single all-days average). |
| `--velocity-window <days>` | How far back to look when measuring throughput. Defaults to 90 days. |

## Step-by-Step

1. **Select columns** — With `--columns`, the given selection is used as-is. Without it, the skill discovers the reportable columns and asks which to include. The dynamic Unsorted column is offered whenever it currently holds tasks.
2. **Review task membership** — Every task in the chosen columns starts included; you select any you want to *exclude*. Ordering follows each column's board order and is preserved throughout.
3. **Choose a horizon** — Asked on every run: **Today**, **This week**, or a custom label you type (a sprint or milestone name). The horizon labels the report; it never changes which tasks are in it.
4. **Gather context** — For each selected task the skill reads the description, metadata, dependencies, the active plan when one exists, and child-task progress. Child work is summarized at manager level as "N of M subtasks complete" rather than listed.
5. **Draft the report** — Produces the Markdown described below.
6. **Review and iterate** — The draft is presented in-session for editing. When you are satisfied, the complete report is re-rendered as one consolidated block.

## Report Structure

- **Focus summary** — Two or three sentences on the overall thrust of the selected work under the chosen horizon.
- **Column-grouped priorities** — In board order, each task's intended outcome and current status, with its `tNN` id for traceability.
- **Observed throughput** — Recent completion rates per bucket, with the observed sample size quoted alongside each average so the reader can judge confidence.
- **Completion projection** — Included only on request; see below.
- **Blockers and manager-asks** — Real blockers drawn from task dependencies and content.

The report contains exactly the selected tasks. Dates, estimates, progress, commitments, dependencies, and blockers are never invented, and implementation-level file or symbol detail is left out.

## Completion Projection

The projection is **opt-in** — ask for a forecast and the skill computes one; otherwise the report ends at observed throughput.

A projection is an extrapolation of past throughput, never a commitment or a delivery estimate: it counts tasks, so it ignores task size, blockers, and capacity. That caveat is always surfaced alongside the figure.

- A projection requires at least 10 completions inside the measurement window. Below that, the report states that there is insufficient completion history for a projection rather than fabricating a rate.
- For the **Today** horizon the report says plainly whether the work fits within the horizon or exceeds it. For **This week** and custom labels it reports the projected date and days-ahead figure without inferring a fits-or-exceeds judgement.
- If nothing remains to complete in the selection, the projection is omitted and the selection is reported as effectively complete.

## Key Features

- Membership and ordering come from a single deterministic source, so the report matches the board exactly.
- Selection is validated before drafting. If a column or task no longer matches the board — renamed, moved, or reordered since it was chosen — the skill stops, shows the diagnostics, and offers to re-select or abort. It never drafts from a partially valid selection or silently corrects one.
- The throughput estimator is selectable, and the measurement window is configurable.
- **No report file is written.** The draft lives in the session only, so you decide where it goes.

## Configuring the Agent

The `work-report` operation defaults to a lightweight model class. To change it, edit `defaults."work-report"` in `aitasks/metadata/codeagent_config.json` (shared with the project) or `codeagent_config.local.json` (your personal override, which wins) — or use the Agent Defaults tab in `ait settings`. You can also override the agent and model for a single run from the launch dialog. See the [`ait codeagent` reference]({{< relref "/docs/commands/codeagent" >}}).

## Workflows

For the end-to-end guide, including the board flow, see [Work Reporting](../../workflows/work-report/).
