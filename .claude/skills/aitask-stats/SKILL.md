---
name: aitask-stats
description: Calculate and display statistics of AI task completions (daily, global, per-label).
---

## Usage

Run the statistics script:

```bash
./.aitask-scripts/aitask_stats.sh [OPTIONS]
```

### Options

- `-d, --days N` - Show daily breakdown for last N days (default: 7)
- `-w, --week-start DAY` - First day of week: mon, sun, tue, etc. (default: Monday)
- `-v, --verbose` - Show individual task IDs in daily breakdown
- `--csv [FILE]` - Export raw data to CSV (default: aitask_stats.csv)
- `--backlog-weeks N` - Weeks of backlog history to render (default: 8, max: 99)
- `--csv-backlog [FILE]` - Export the weekly backlog series to CSV (default: aitask_backlog.csv)
- `-h, --help` - Show usage information

### Examples

Basic statistics (last 7 days):
```bash
./.aitask-scripts/aitask_stats.sh
```

Extended daily view (14 days):
```bash
./.aitask-scripts/aitask_stats.sh --days 14
```

Verbose output with task names:
```bash
./.aitask-scripts/aitask_stats.sh -v
```

Export to CSV for graphing in LibreOffice:
```bash
./.aitask-scripts/aitask_stats.sh --csv
```

## Statistics Provided

1. **Summary** - Total completions, 7-day and 30-day counts
2. **Backlog Level** - Weekly count of open tasks per category, with follow-up / genuine subtotals, `TOTAL OPEN`, and a parent/child split
3. **Backlog Net Flow** - Weekly arrivals minus departures per category, with ARRIVALS / DEPARTURES / NET rows
4. **Daily Breakdown** - Completions per day with optional task IDs
5. **Day of Week Stats** - Current week counts + 30d/all-time averages per weekday
6. **Pipeline Timing** - Average time in the implement and review/merge phases, for gated tasks
7. **Label Weekly Trends** - Per-label completions for last 4 weeks (W-3, W-2, W-1, This Week)
8. **Label Day-of-Week Breakdown** - Per-label averages by day of week
9. **Task Type Weekly Trends** - Parent/child and feature/bug trends for last 4 weeks
10. **Features/Bugs by Label Trends** - Combined label + issue type weekly trends
11. **Code Agent Weekly Trends** - Weekly completions split by code agent
12. **LLM Model Weekly Trends** - Weekly completions split by normalized LLM model
13. **Verified Model Rankings** - Model scores per skill, aggregated across providers

The backlog sections cover the last 8 weeks by default (`--backlog-weeks` changes
the horizon). Their columns run chronologically with the current week last; in the
net-flow table that final column is a partial week, marked `Now*`.

## Export Format

**CSV Export (`--csv`):** one row per *completed* task, with columns:
- date, day_of_week, week_offset, task_id, labels, issue_type, task_type, implemented_with, codeagent, llm_model, created_at, category

**Backlog Export (`--csv-backlog`):** the weekly backlog series, with columns:
- week_ending, category, open, arrived, departed, net

One row per category per week, oldest week first, zero cells included. `category`
holds raw namespaced keys (`type:feature`, `kind:manual_verification`) and only real
categories -- no subtotal or `TOTAL OPEN` rows for a pivot to double-count. Open
tasks are not rows in the `--csv` table, so the backlog level is not reproducible
from it.

Open in LibreOffice Calc to create custom charts and pivot tables for trend analysis.

### Importing CSV in LibreOffice Calc

1. Open LibreOffice Calc
2. File -> Open -> Select the CSV file
3. In the import dialog:
   - Character set: UTF-8
   - Separator: Comma
   - Check "Quoted field as text"
4. Click OK

### Creating Charts

1. Select the data range
2. Insert -> Chart
3. Choose chart type (Line, Bar, or XY Scatter for trends)
4. Follow the wizard to customize

### Pivot Tables for Analysis

1. Select all data
2. Insert -> Pivot Table
3. Drag fields:
   - Row: `week_offset` or `day_of_week`
   - Column: `labels` or `issue_type`
   - Data: Count of `task_id`
4. Creates summary table for trends
