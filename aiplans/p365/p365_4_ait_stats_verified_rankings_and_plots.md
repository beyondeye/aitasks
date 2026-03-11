---
Task: t365_4_ait_stats_verified_rankings_and_plots.md
Parent Task: aitasks/t365_verified_stats_for_same_model_different_providers.md
Sibling Tasks: aitasks/t365/t365_1_*.md, t365_2_*.md, t365_3_*.md, and t365_5_*.md
Archived Sibling Plans: aiplans/archived/p365/p365_1_opencode_runtime_provider_mapping_fix.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

`ait stats` currently reports archived task completions only. It does not load model verification metadata, so there is no CLI or plot report for provider-specific or `all_providers` verified rankings by skill.

## Implementation Plan

1. Extend `.aitask-scripts/aitask_stats.py` to read `models_*.json` verification data alongside archived task data.
2. Add ranking helpers for provider-specific and `all_providers` views using the grouping rules introduced in t365_2.
3. Add compact text sections for top verified models per skill and timeframe (all-time, month, week).
4. Extend `--plot` output with readable verified-ranking charts using `plotext`.
5. Expand `tests/test_aitask_stats_py.py` with fixtures and assertions for verified metadata loading, ranking, and rendered output.
6. Update `website/content/docs/skills/aitask-stats.md` to document the new reporting behavior.

## Verification

- `python -m unittest tests/test_aitask_stats_py.py`
- `python .aitask-scripts/aitask_stats.py`
- `python .aitask-scripts/aitask_stats.py --plot`
