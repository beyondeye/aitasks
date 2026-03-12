---
Task: t365_3_settings_verified_score_discoverability.md
Parent Task: aitasks/t365_verified_stats_for_same_model_different_providers.md
Sibling Tasks: aitasks/t365/t365_1_*.md, t365_2_*.md, and t365_4_*.md through t365_5_*.md
Archived Sibling Plans: aiplans/archived/p365/p365_1_opencode_runtime_provider_mapping_fix.md, aiplans/archived/p365/p365_2_verified_stats_windows_and_all_providers_design.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

`ait settings` currently exposes verified information only through small `[score: 80]` labels using only the flat `verified` dict. After t365_2 added time-windowed `verifiedstats` buckets (all_time, month, week) and defined the all_providers aggregation contract, users cannot discover which models perform best for a given operation, how many runs back a score, or cross-provider scores for the same underlying LLM.

## Implementation Plan

### 1. Add verified-score helper functions (settings_app.py, ~line 1527)

Add helpers to `SettingsApp`:

- `_normalize_model_id(cli_id)` — strip `provider/` prefix for all_providers grouping
- `_get_all_providers_stats(model_cli_id)` — aggregate verifiedstats across all providers for same normalized model ID
- `_format_verified_detail(verifiedstats, operation, include_time=True)` — format score with run count and recency

### 2. Enhance `_get_verified_label()` (line 1527)

- Show `[80 (5 runs, 2 this month)]` instead of `[score: 80]`
- Read from `verifiedstats` buckets when available, fall back to flat `verified`

### 3. Update Agent Defaults tab (`_populate_agent_tab`, line 1544)

- Show enhanced verified labels from step 2
- Add all_providers hint when stats differ from provider-specific

### 4. Add ranked model selection to picker (`AgentModelPickerScreen`, line 700)

- New Step 0: "Top Verified Models" — up to 5 models ranked by verified score for the operation
- "Browse all models" option falls back to existing agent→model flow
- Enhance Step 2 model descriptions with verifiedstats detail
- Sort models with verified scores first

### 5. Update Models tab (`_populate_models_tab`, line 1825)

- Replace flat `verified: pick:80` with `pick: 96 (9 runs, 2 this month) | explain: 80 (2 runs)`
- Add all_providers summary line when model is shared across providers

### 6. Update documentation

- `website/content/docs/tuis/settings/_index.md` — mention richer verified context, Top Verified picker, all_providers
- `website/content/docs/tuis/settings/reference.md` — note that `ait settings` now implements all_providers aggregation

## Verification

- Run `ait settings` — check Agent Defaults, picker, and Models tabs
- Verify terminal layout doesn't overflow
- Test graceful degradation with empty verifiedstats
- Test all_providers aggregation with multi-provider models

## Final Implementation Notes

- **Actual work done:** Added 4 module-level helper functions (`_normalize_model_id`, `_bucket_avg`, `_aggregate_verifiedstats`, `_format_op_stats`) to `settings_app.py`. Enhanced `_get_verified_label()` to read from `verifiedstats` buckets with compact display (`[96 (9 runs, 2 this mo)]`). Added `_get_all_providers_label()` for cross-provider aggregated hints in Agent Defaults. Redesigned `AgentModelPickerScreen` with a new Step 0 showing Top Verified models ranked by score before the full agent→model browser, plus sort-by-score in Step 2. Updated `_populate_models_tab()` to show rich verifiedstats per operation and all-providers summary rows. Updated both settings docs to explain new UI behavior and added a note in reference.md that `ait settings` implements the all_providers aggregation contract.
- **Deviations from plan:** Implemented helpers as module-level functions rather than instance methods since they don't need `self` access (cleaner separation). Renamed `_format_verified_detail` to `_format_op_stats` for clarity. Named the aggregation function `_aggregate_verifiedstats` instead of `_get_all_providers_stats`.
- **Issues encountered:** None.
- **Key decisions:** Used compact `"mo"` abbreviation for month in Agent Defaults labels (space-constrained) vs full `"month"` in Models tab. Top Verified picker shows up to 5 candidates across all providers, sorted by all_time average score. When no verified models exist for an operation, Step 0 is skipped entirely and the picker starts at Step 1 (agent selection) as before. All-providers summary in Models tab only appears when aggregate runs exceed provider-specific runs (i.e., there's actually cross-provider data).
- **Notes for sibling tasks:** t365_4 (ait stats) can reuse the same `_normalize_model_id` pattern and `_aggregate_verifiedstats` logic for its rankings/plots. The `_format_op_stats` helper demonstrates the compact vs full display format. The all_providers contract is now fully implemented by `ait settings` as a reference consumer.
