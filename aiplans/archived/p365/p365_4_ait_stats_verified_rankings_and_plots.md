---
Task: t365_4_ait_stats_verified_rankings_and_plots.md
Parent Task: aitasks/t365_verified_stats_for_same_model_different_providers.md
Sibling Tasks: aitasks/t365/t365_1_*.md, t365_2_*.md, t365_3_*.md, and t365_5_*.md
Archived Sibling Plans: aiplans/archived/p365/p365_1_opencode_runtime_provider_mapping_fix.md, aiplans/archived/p365/p365_2_verified_stats_windows_and_all_providers_design.md, aiplans/archived/p365/p365_3_settings_verified_score_discoverability.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

`ait stats` currently reports archived task completions only. After t365_2 added time-windowed `verifiedstats` buckets (all_time, month, week) to `models_*.json` and t365_3 implemented all_providers aggregation in settings TUI, there is no CLI report showing which models perform best per operation. This task adds verified score rankings (text + plots) to `aitask_stats.py`.

## Key Files

- `.aitask-scripts/aitask_stats.py` — primary file (970 lines)
- `tests/test_aitask_stats_py.py` — test suite (343 lines)
- `website/content/docs/skills/aitask-stats.md` — docs
- `.aitask-scripts/settings/settings_app.py` — reference for aggregation patterns (lines 332-413)

## Implementation Plan

### 1. Add data structures (after line 101 in aitask_stats.py)

- `VerifiedModelEntry` dataclass: cli_id, display_name, provider, score, runs
- `VerifiedRankingData` dataclass: by_provider dict, by_window dict, operations list
- `bucket_avg(runs, score_sum)` helper near line 185

### 2. Add `load_verified_rankings()` (after line 269)

- Iterate all 4 `models_*.json` files (same loop pattern as `load_model_cli_ids`)
- For each model with `verifiedstats`, extract entries per window (all_time/month/week)
- Store per-provider entries: `by_window[op][agent][window] = [entries]`
- All-providers aggregation: group by `canonical_model_id(cli_id)`, sum runs/score_sum across providers. For month/week only aggregate matching `period` values.
- Sort by score desc, display_name asc. Skip entries with 0 all_time runs.

### 3. Add `render_verified_rankings()` (after line 758)

- Main table: all_providers all_time top 5 models per operation
- "This month" column from all_providers month window
- Per-provider breakdown inline only when >1 provider has data
- Skip operations with 0 total all_time runs

### 4. Extract `show_chart()` to module level (line 837)

- Move nested function to module level with `plt` as first argument
- Update `run_plot_summary()` callers to pass `plt`

### 5. Add `run_verified_plots()` (after `run_plot_summary`)

- Bar chart per operation, top 5 all_providers all_time models
- Set `plt.ylim(0, 100)` for consistent scale

### 6. Update `main()` (line 939)

- Load `vdata = load_verified_rankings()` once
- Print `render_verified_rankings(vdata)` after existing report
- Call `run_verified_plots(vdata)` after existing plots when `--plot`

### 7. Add tests

- Extend fixtures with `verifiedstats` data + cross-provider model for aggregation testing
- Tests: load structure, all_providers aggregation, render sections, skip empty, bucket_avg, plot chart count

### 8. Update docs

- Add verified rankings to feature list in `aitask-stats.md`
- Update `--plot` description

## Verification

- `python -m unittest tests/test_aitask_stats_py.py`
- `python .aitask-scripts/aitask_stats.py`
- `python .aitask-scripts/aitask_stats.py --plot`

## Final Implementation Notes

- **Actual work done:** Added `VerifiedModelEntry` and `VerifiedRankingData` dataclasses, `bucket_avg()` helper, `load_verified_rankings()` function that reads all `models_*.json` verifiedstats and builds per-provider + all_providers aggregated rankings. Added `render_verified_rankings()` for text report output and `run_verified_plots()` for plotext bar charts. Extracted `show_chart()` from nested function to module-level for reuse. Added `_import_plotext()` helper to avoid duplication. Updated `main()` to integrate both text and plot output. Added 9 new tests covering loading, aggregation, rendering, empty data, bucket_avg, and plot chart count. Updated aitask-stats.md docs.
- **Deviations from plan:** Added old flat verifiedstats format handling (models with `{runs, score_sum}` directly under operation instead of `{all_time: {runs, score_sum}}`). This was discovered during testing when live `models_opencode.json` had GPT5.4 in old format. Simplified data structure: removed `by_provider` dict from `VerifiedRankingData` (only `by_window` needed since it contains per-provider data already).
- **Issues encountered:** Old flat verifiedstats format (pre-t365_2 migration) was not handled initially — fixed by detecting `runs` key without `all_time` wrapper and treating the bucket itself as the all_time data.
- **Key decisions:** Used `canonical_model_id()` (existing function) for all_providers normalization — more thorough than settings' `_normalize_model_id()` since it also strips `-preview` and date suffixes. Text output shows main table (all_providers all_time top 5) plus inline provider breakdown. Provider breakdown only shown when >1 provider has data. Month column uses `-` when no month data exists.
- **Notes for sibling tasks:** t365_5 (docs) should reference the "Verified Model Rankings" section format when documenting verified scores. The text output format includes per-operation tables with all_providers aggregate and optional per-provider breakdowns.
