---
priority: medium
effort: high
depends: []
issue_type: feature
status: Done
labels: [aitasks, statistics, claudeskills]
created_at: 2026-02-04 12:07
updated_at: 2026-02-04 14:21
completed_at: 2026-02-04 14:21
---

Add a new Claude skill called: aitasks-stats, that calculates statistics of number of tasks completed daily, globally, and per label.

## Completed

Created:
- `aitask_stats.sh` - Bash script for collecting and calculating task completion statistics
- `.claude/skills/aitask-stats/SKILL.md` - Skill definition file

### Features Implemented:
1. **Summary** - Total completions, 7-day and 30-day counts
2. **Daily Breakdown** - Completions per day with optional task IDs (-v flag)
3. **Day of Week Stats** - Current week counts + 30d/all-time averages per weekday
4. **Label Weekly Trends** - Per-label completions for last 4 weeks (W-3, W-2, W-1, This Week)
5. **Label Day-of-Week Breakdown** - Per-label averages by day of week (last 30 days)
6. **Task Type Weekly Trends** - Parent/child and feature/bug trends for last 4 weeks
7. **Features/Bugs by Label Trends** - Combined label + issue type weekly trends
8. **CSV Export** - Raw data export with LibreOffice Calc import instructions

### Usage:
```bash
./aitask_stats.sh              # Basic stats (last 7 days)
./aitask_stats.sh -d 14        # Extended daily view (14 days)
./aitask_stats.sh -v           # Verbose with task IDs
./aitask_stats.sh --csv        # Export to CSV for graphing
```
