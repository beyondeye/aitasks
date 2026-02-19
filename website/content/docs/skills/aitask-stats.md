---
title: "/aitask-stats"
linkTitle: "/aitask-stats"
weight: 50
description: "View task completion statistics via Claude Code"
---

View task completion statistics via Claude Code.

**Usage:**
```
/aitask-stats
```

Runs `./aiscripts/aitask_stats.sh` and displays the results. Provides the same 7 types of statistics as `ait stats`:

- Summary counts (7-day, 30-day, all-time)
- Daily breakdown with optional task IDs
- Day-of-week averages
- Per-label weekly trends (4 weeks)
- Label day-of-week breakdown (30 days)
- Task type weekly trends
- Label + issue type trends

Supports all command-line options (`-d`, `-v`, `--csv`, `-w`). For CSV export, provides guidance on opening the file in LibreOffice Calc with pivot tables and charts.
