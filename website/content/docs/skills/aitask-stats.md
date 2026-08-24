---
title: "/aitask-stats"
linkTitle: "/aitask-stats"
weight: 50
description: "View task completion statistics via a code agent"
maturity: [stable]
depth: [intermediate]
---

View task completion statistics via a code agent.

**Usage:**
```
/aitask-stats
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

Runs `./.aitask-scripts/aitask_stats.sh` and displays the results. Provides the same statistics as `ait stats`, including:

- Summary counts (7-day, 30-day, all-time)
- Backlog level — weekly count of open tasks per category, with follow-up / genuine subtotals and a parent-child split
- Backlog net flow — weekly arrivals minus departures per category, with `ARRIVALS` / `DEPARTURES` / `NET` totals
- Daily breakdown with optional task IDs
- Day-of-week averages
- Pipeline timing for gated tasks (time in the implement and review/merge phases)
- Per-label weekly trends (4 weeks)
- Label day-of-week breakdown (30 days)
- Task type weekly trends
- Label + issue type trends
- Code agent weekly trends (last 4 weeks)
- LLM model weekly trends (last 4 weeks)
- Verified model score rankings per skill (pick, explain, batch-review) -- see [Verified Scores](../verified-scores/) for how scores are accumulated
  - All-providers aggregated view with per-provider breakdowns
  - Time-windowed display (all-time, this month)

Supports all command-line options (`-d`, `-v`, `--csv`, `-w`, `--backlog-weeks`,
`--csv-backlog`). For interactive terminal charts (including code agent / LLM model
histograms, verified score ranking bar charts per skill, and the backlog panes), run
[`ait stats-tui`]({{< relref "/docs/tuis/stats" >}})
or switch into it from any other aitasks TUI via the TUI switcher.
For CSV export, provides guidance on opening the file in LibreOffice Calc with pivot tables and charts.
