---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [statistics, aitask_monitor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7
created_at: 2026-04-19 17:50
updated_at: 2026-04-19 18:17
---

## Context

First child of t597 (ait stats TUI). Foundation refactor: extract reusable stats data extraction from `aitask_stats.py` (1219 LOC) into a new `stats/stats_data.py` module so both the existing CLI (`ait stats`, `--csv`) and the upcoming TUI panes (t597_3) can consume the same `StatsData` without duplication.

Per parent plan: TUI panes reuse `collect_stats()` and friends. Goal of this task is the refactor only — no TUI work.

## Key Files to Modify

- `.aitask-scripts/aitask_stats.py` — strip extracted functions, re-import them from `stats.stats_data` so CLI behavior is unchanged.
- `.aitask-scripts/stats/__init__.py` — new package init (empty or version stub).
- `.aitask-scripts/stats/stats_data.py` — new module containing extracted code.
- `tests/test_stats_data.sh` — new test script.

## Reference Files for Patterns

- `.aitask-scripts/aitask_stats.py` lines 66–96 (`TaskRecord`, `StatsData` dataclasses), lines 234–584 (parsers), lines 621–734 (`collect_stats()`), lines 737–1020 (`sorted_weekly_keys`, `chart_totals`, `build_chart_title`, related helpers), lines 1066–1077 (`_import_plotext()` — leave in place for now; t597_5 removes it).
- `tests/test_*.sh` for existing test pattern (assert_eq / assert_contains, PASS/FAIL summary).

## Implementation Plan

1. Create `.aitask-scripts/stats/__init__.py` (empty file).
2. Create `.aitask-scripts/stats/stats_data.py` and move:
   - `TaskRecord`, `StatsData` dataclasses
   - `load_model_cli_ids()`, `load_verified_rankings()`
   - All task-archive parser helpers used by `collect_stats()`
   - `collect_stats()` itself
   - Pure data helpers reused by both CLI and plot: `sorted_weekly_keys()`, `chart_totals()`, `build_chart_title()`
3. In `aitask_stats.py`, replace removed code with `from stats.stats_data import (...)` imports. Keep `render_text_report()`, `--csv` writer, and `_import_plotext()`/`show_chart()`/`run_plot_summary()` in `aitask_stats.py` — t597_5 will deal with the plot path.
4. Verify the import path works: `aitask_stats.py` lives in `.aitask-scripts/`, the new package is `.aitask-scripts/stats/` — adjust `sys.path` if needed (mirror what `aitask_stats.sh` already does for the wrapper). If `aitask_stats.sh` does not already add `.aitask-scripts/` to `PYTHONPATH`, do so.
5. Write `tests/test_stats_data.sh` with at minimum:
   - Smoke test: run `python3 -c "from stats.stats_data import collect_stats; ..."` against a tiny fixture (build a few archived task files in a temp dir or use an existing snapshot)
   - Verify `StatsData` fields are populated for known counts

## Verification Steps

```bash
ait stats                                  # text report identical to before
ait stats --csv /tmp/stats.csv && diff <(...)  # CSV identical
ait stats --plot                           # still works (plotext path untouched here)
shellcheck .aitask-scripts/aitask_stats_tui.sh 2>/dev/null || true   # n/a yet
bash tests/test_stats_data.sh              # PASS
```

## Out of Scope

- Anything related to the TUI itself (t597_2, t597_3).
- Removing `--plot` (t597_5).
