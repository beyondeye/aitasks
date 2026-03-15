---
title: "/aitask-stats"
linkTitle: "/aitask-stats"
weight: 50
description: "View task completion statistics via a code agent"
---

View task completion statistics via a code agent.

**Usage:**
```
/aitask-stats
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

Runs `./.aitask-scripts/aitask_stats.sh` and displays the results. Provides the same statistics as `ait stats`, including:

- Summary counts (7-day, 30-day, all-time)
- Daily breakdown with optional task IDs
- Day-of-week averages
- Per-label weekly trends (4 weeks)
- Label day-of-week breakdown (30 days)
- Task type weekly trends
- Label + issue type trends
- Code agent weekly trends (last 4 weeks)
- LLM model weekly trends (last 4 weeks)
- Verified model score rankings per skill (pick, explain, batch-review) -- see [Verified Scores](../verified-scores/) for how scores are accumulated
  - All-providers aggregated view with per-provider breakdowns
  - Time-windowed display (all-time, this month)

Supports all command-line options (`-d`, `-v`, `--csv`, `-w`, `--plot`).
`--plot` shows interactive terminal charts when optional `plotext` is installed
(can be enabled via `ait setup`), including the code agent and LLM model
histograms and verified score ranking bar charts per skill.
For CSV export, provides guidance on opening the file in LibreOffice Calc with pivot tables and charts.
