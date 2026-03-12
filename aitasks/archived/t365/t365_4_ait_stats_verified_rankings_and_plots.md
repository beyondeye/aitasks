---
priority: medium
effort: high
depends: [2]
issue_type: feature
status: Done
labels: [verifiedstats, python]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-11 15:50
updated_at: 2026-03-12 11:57
completed_at: 2026-03-12 11:57
---

## Context

This is child task 4 of t365 (verified stats for same model across different providers). It extends `ait stats` so verified-score rankings and plots are available from the command line, including recent-period views and `all_providers` aggregation.

Current `ait stats` only reports archived task-completion history. It does not read model verification metadata at all, so there is no CLI report showing which models are performing best for `pick`, `explain`, or other supported operations.

## Key Files to Modify

- `.aitask-scripts/aitask_stats.py`
- `tests/test_aitask_stats_py.py`
- `website/content/docs/skills/aitask-stats.md`

## Reference Files for Patterns

- `.aitask-scripts/aitask_stats.py` - current text and plot reporting flow
- `tests/test_aitask_stats_py.py` - Python unit-test pattern for stats rendering

## Implementation Plan

### 1. Load verified-score metadata into `ait stats`

- Extend `aitask_stats.py` to read `models_*.json` verified and `verifiedstats` data in addition to archived task history.
- Add shared ranking helpers that can group by provider-specific model entry and by `all_providers` LLM model.

### 2. Add text reports for verified rankings

- For each supported skill, render compact top-model sections for:
  - provider-specific all-time / month / week
  - `all_providers` all-time / month / week
- Keep the output concise enough to remain usable in the terminal.

### 3. Add plot support

- Extend `--plot` so verified rankings can be visualized with `plotext`.
- Choose a chart order that stays readable even when multiple skills/timeframes are shown sequentially.

### 4. Add unit tests

- Extend `tests/test_aitask_stats_py.py` with fixtures and assertions covering:
  - verified metadata loading
  - provider-specific ranking
  - `all_providers` ranking
  - text-report rendering for the new sections

## Verification Steps

- `python -m unittest tests/test_aitask_stats_py.py`
- `python .aitask-scripts/aitask_stats.py`
- `python .aitask-scripts/aitask_stats.py --plot`
