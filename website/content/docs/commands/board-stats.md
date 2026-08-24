---
title: "Board, Code Browser & Stats"
linkTitle: "Board, Browser & Stats"
weight: 30
description: "ait board, ait codebrowser, and ait stats commands"
depth: [intermediate]
---

## ait board

Open the kanban-style TUI board for visual task management.

```bash
ait board
```

Launches a Python-based terminal UI (built with [Textual](https://textual.textualize.io/)) that displays tasks in a kanban-style column layout. All arguments are forwarded to the Python board application.

For full usage documentation — including tutorials, keyboard shortcuts, how-to guides, and configuration — see the [Kanban Board documentation](../../tuis/board/).

**Requirements:**
- Python venv at `~/.aitask/venv/` with packages: `textual`, `pyyaml`, `linkify-it-py`
- Falls back to system `python3` if venv not found (warns about missing packages)
- Checks terminal capabilities and warns on legacy terminals (e.g., WSL default console)

---

## ait codebrowser

Open the code browser TUI for file exploration with task annotations.

```bash
ait codebrowser
```

Launches a Python-based terminal UI (built with [Textual](https://textual.textualize.io/)) that provides a file tree, syntax-highlighted code viewer, and annotation gutter showing which aitasks contributed to each section of code. All arguments are forwarded to the Python codebrowser application.

For full usage documentation — including tutorials, keyboard shortcuts, how-to guides, and annotation details — see the [Code Browser documentation](../../tuis/codebrowser/).

**Requirements:**
- Python venv at `~/.aitask/venv/` with packages: `textual`, `pyyaml`
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
ait stats --backlog-weeks 26   # Longer backlog history
ait stats --csv-backlog        # Export the weekly backlog series
```

| Option | Description |
|--------|-------------|
| `-d, --days N` | Show daily breakdown for last N days (default: 7) |
| `-w, --week-start DAY` | First day of week: mon, sun, tue, etc. (default: Monday) |
| `-v, --verbose` | Show individual task IDs in daily breakdown |
| `--csv [FILE]` | Export raw data to CSV (default: aitask_stats.csv) |
| `--backlog-weeks N` | Weeks of backlog history to render (default: 8, max: 99). The table widens by 7 characters per week |
| `--csv-backlog [FILE]` | Export the weekly backlog series to CSV (default: aitask_backlog.csv) |

**Statistics provided:**

1. **Summary** — Total completions, 7-day and 30-day counts
2. **Backlog level** — Weekly count of *open* tasks per category, with follow-up and genuine-work subtotals, a `TOTAL OPEN` row, and its parent / child partition
3. **Backlog net flow** — Weekly arrivals minus departures per category, with `ARRIVALS` / `DEPARTURES` / `NET` summary rows, explaining why the level moves
4. **Daily breakdown** — Completions per day (with task IDs in verbose mode)
5. **Day of week averages** — This week counts + 30-day and all-time averages per weekday
6. **Pipeline timing** — Average time in the implement and review/merge phases, for gated tasks
7. **Label weekly trends** — Per-label completions for last 4 weeks
8. **Label day-of-week** — Per-label averages by day of week (last 30 days)
9. **Task type trends** — Parent/child and issue type (feature/bug/refactor) weekly trends
10. **Label + type trends** — Issue types by label, weekly for last 4 weeks
11. **Code agent trends** — Weekly completion split by code agent for last 4 weeks
12. **LLM model trends** — Weekly completion split by normalized LLM model for last 4 weeks
13. **Verified model rankings** — Model scores per skill, aggregated across providers

The two backlog sections cover the last 8 weeks by default; `--backlog-weeks` changes the horizon. In both tables the columns run chronologically with the current week last, and in the net-flow table that final column is a partial week (marked `Now*`, with the dates it covers given below the table).

**Data sources:** The completion sections scan archived parent tasks (`aitasks/archived/t*_*.md`), archived child tasks (`aitasks/archived/t*/`), and compressed archives (numbered `_bN/oldM.tar.gz` bundles). They use the `completed_at` field, falling back to `updated_at` for tasks with `status: Done`, and prefer the `merge_approved` / `review_approved` gate-ledger stamps where a task has them.

The two backlog sections need open tasks as well, so they scan your **active** tasks alongside the archive, and they use a different clock: `completed_at`, falling back to `updated_at` for tasks with `status: Done` or `Completed` — never the gate-ledger stamps, which on a live task mean "in flight", not "finished". The two clocks agree on *whether* a task completed and can disagree on *which week* it landed in, so a small number of tasks are bucketed one week apart between the backlog sections and the completion sections.

Backlog population rules: a task counts as **open** from its `created_at` week until the week it departs, so **Postponed** tasks count as open; a `Done` task that has not been archived yet counts as departed; **Folded** tasks are excluded entirely, as are tasks with no frontmatter, no `created_at`, or a future date. The report footnotes how many tasks were excluded and why.

**CSV export format:** `--csv` writes one row per *completed* task: `date, day_of_week, week_offset, task_id, labels, issue_type, task_type, implemented_with, codeagent, llm_model, created_at, category`. Open in LibreOffice Calc for custom charts and pivot tables.

Open tasks are **not** rows in that table, so the backlog level cannot be reproduced from it — `created_at` there supports lead-time analysis, not backlog. The backlog series has its own export: `--csv-backlog` writes `week_ending, category, open, arrived, departed, net`, one row per category per week, oldest week first, including zero cells so the grid is dense and plottable. Its `category` values are raw namespaced keys (`type:feature`, `kind:manual_verification`) rather than the display labels the report prints, so they are safe to join on, and it contains only real categories — no subtotal or `TOTAL OPEN` rows for a pivot to double-count. `--backlog-weeks` sets its horizon too.

**Interactive charts:**

For interactive terminal charts (daily completions, weekday averages, top labels, issue types, code agents, LLM models, backlog level and net flow), use [`ait stats-tui`]({{< relref "/docs/tuis/stats" >}}). The TUI is launched directly or switched into from any other aitasks TUI (`j` in the TUI switcher). It uses the `plotext` package, installed and version-pinned by `ait setup`.

---

**Next:** [Explain Utilities]({{< relref "/docs/commands/explain" >}})
