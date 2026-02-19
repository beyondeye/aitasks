---
title: "Board & Stats"
linkTitle: "Board & Stats"
weight: 30
description: "ait board and ait stats commands"
---

## ait board

Open the kanban-style TUI board for visual task management.

```bash
ait board
```

Launches a Python-based terminal UI (built with [Textual](https://textual.textualize.io/)) that displays tasks in a kanban-style column layout. All arguments are forwarded to the Python board application.

For full usage documentation — including tutorials, keyboard shortcuts, how-to guides, and configuration — see the [Kanban Board documentation](../../board/).

**Requirements:**
- Python venv at `~/.aitask/venv/` with packages: `textual`, `pyyaml`, `linkify-it-py`
- Falls back to system `python3` if venv not found (warns about missing packages)
- Checks terminal capabilities and warns on legacy terminals (e.g., WSL default console)

---

## ait stats

Display task completion statistics and trends.

```bash
ait stats                  # Basic stats (last 7 days)
ait stats -d 14            # Extended daily view
ait stats -v               # Verbose with task IDs
ait stats --csv            # Export to CSV
ait stats -w sun           # Week starts on Sunday
```

| Option | Description |
|--------|-------------|
| `-d, --days N` | Show daily breakdown for last N days (default: 7) |
| `-w, --week-start DAY` | First day of week: mon, sun, tue, etc. (default: Monday) |
| `-v, --verbose` | Show individual task IDs in daily breakdown |
| `--csv [FILE]` | Export raw data to CSV (default: aitask_stats.csv) |

**Statistics provided:**

1. **Summary** — Total completions, 7-day and 30-day counts
2. **Daily breakdown** — Completions per day (with task IDs in verbose mode)
3. **Day of week averages** — This week counts + 30-day and all-time averages per weekday
4. **Label weekly trends** — Per-label completions for last 4 weeks
5. **Label day-of-week** — Per-label averages by day of week (last 30 days)
6. **Task type trends** — Parent/child and issue type (feature/bug/refactor) weekly trends
7. **Label + type trends** — Issue types by label, weekly for last 4 weeks

**Data sources:** Scans archived parent tasks (`aitasks/archived/t*_*.md`), archived child tasks (`aitasks/archived/t*/`), and compressed archives (`old.tar.gz`). Uses `completed_at` field, falling back to `updated_at` for tasks with `status: Done`.

**CSV export format:** `date, day_of_week, week_offset, task_id, labels, issue_type, task_type`. Open in LibreOffice Calc for custom charts and pivot tables.
