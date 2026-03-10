---
Task: t359_missing_plot_title_in_ait_stats_plots.md
Worktree: /home/ddt/Work/aitasks
Branch: main
Base branch: main
---

# Implementation Plan

1. Inspect the existing plotting flow in `.aitask-scripts/aitask_stats.py`, especially `run_plot_summary()` and `show_chart()`, to keep title handling centralized and avoid changing chart rendering behavior beyond title text.
2. Add a small helper near the plotting code to build consistent, self-contained chart titles. The helper should accept the chart subject, the reporting window, and optionally the configured week start so charts that depend on weekly grouping can explain that context directly in the title.
3. Update all `show_chart()` call sites in `.aitask-scripts/aitask_stats.py` so each generated chart has a descriptive title:
   - daily completions chart includes the day window
   - weekday average chart includes that it is based on the last 30 days and the configured week start
   - label chart explains it is all-time top labels
   - issue type chart explains it is for the current week and includes week start context
   - code agent and model charts explain whether they cover the last 4 weeks or this week, with week start context where relevant
4. Add a unit test in `tests/test_aitask_stats_py.py` that patches in a fake `plotext` implementation, runs `run_plot_summary()`, records each `title()` call, and asserts that all expected charts are produced with the new descriptive wording.
5. Run `python3 -m unittest tests/test_aitask_stats_py.py` to verify the updated titles and ensure no existing stats behavior regresses.
6. After implementation, update this plan file with final implementation notes covering the actual title wording, any deviations, and verification results.
7. Step 9 reminder: after review/commit, complete cleanup and archival with the standard task-workflow post-implementation steps.

## Post-Review Changes

### Change Request 1 (2026-03-10 15:11)
- **Requested by user:** Reduce chart height so plot titles are visible, and add extra blank lines between charts.
- **Changes made:** Added terminal-aware plot sizing and printed two blank lines after each chart.
- **Files affected:** `.aitask-scripts/aitask_stats.py`, `tests/test_aitask_stats_py.py`

### Change Request 2 (2026-03-10 15:12)
- **Requested by user:** Reduce graph height by two more lines.
- **Changes made:** Lowered the computed chart height from `terminal_lines - 2` to `terminal_lines - 4`.
- **Files affected:** `.aitask-scripts/aitask_stats.py`, `tests/test_aitask_stats_py.py`

### Change Request 3 (2026-03-10 15:13)
- **Requested by user:** Reduce graph height by one more line.
- **Changes made:** Lowered the computed chart height again to `terminal_lines - 5`.
- **Files affected:** `.aitask-scripts/aitask_stats.py`, `tests/test_aitask_stats_py.py`

## Final Implementation Notes
- **Actual work done:** Added shared chart-title helpers so every `ait stats --plot` chart uses self-contained wording, introduced terminal-aware plot sizing, and inserted blank-line spacing between charts for readability.
- **Deviations from plan:** The original task description focused on missing titles, but review showed titles already existed; the final implementation kept the title improvements and additionally fixed the real rendering issue by shrinking chart height and separating charts visually.
- **Issues encountered:** The exact chart-height adjustment needed iterative tuning during review. The final sizing uses terminal height minus 5 lines, clamped to a minimum height of 12.
- **Key decisions:** Kept title generation centralized via helpers, used `shutil.get_terminal_size()` for predictable plot sizing, and covered both title content and spacing/size behavior with the plot test.
