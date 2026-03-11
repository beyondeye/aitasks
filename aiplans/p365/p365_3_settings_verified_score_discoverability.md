---
Task: t365_3_settings_verified_score_discoverability.md
Parent Task: aitasks/t365_verified_stats_for_same_model_different_providers.md
Sibling Tasks: aitasks/t365/t365_1_*.md, t365_2_*.md, and t365_4_*.md through t365_5_*.md
Archived Sibling Plans: aiplans/archived/p365/p365_1_opencode_runtime_provider_mapping_fix.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

`ait settings` currently exposes verified information only through small score labels. Users cannot easily discover which models are best verified for a given operation, nor can they easily choose defaults from verified evidence. This task consumes the richer provider-specific and `all_providers` stats defined by t365_2.

## Implementation Plan

1. Add helper functions to `.aitask-scripts/settings/settings_app.py` for provider-specific summaries, `all_providers` summaries, and ranked model lists per operation/timeframe.
2. Update the Agent Defaults tab so current selections show richer verified context such as score, run count, and recent-period indicators.
3. Extend the picker flow to offer top-ranked verified models before the full provider/model browser, while preserving the existing fallback path.
4. Update the Models tab to surface provider-specific and `all_providers` summaries in a terminal-friendly format.
5. Refresh the settings docs in `website/content/docs/tuis/settings/_index.md` and `website/content/docs/tuis/settings/reference.md` to explain the new UI behavior.

## Verification

- Run `ait settings` and review the Agent Defaults and Models tabs interactively
- Confirm verified rankings remain understandable without overflowing the terminal layout
