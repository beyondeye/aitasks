---
Task: t365_2_verified_stats_windows_and_all_providers_design.md
Parent Task: aitasks/t365_verified_stats_for_same_model_different_providers.md
Sibling Tasks: aitasks/t365/t365_1_*.md and t365_3_*.md through t365_5_*.md
Archived Sibling Plans: aiplans/archived/p365/p365_1_opencode_runtime_provider_mapping_fix.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Verified-score storage currently tracks provider-specific all-time totals only. The feature now needs to support recent-period reporting and `all_providers` grouping for the same underlying LLM model, while keeping existing provider-specific `verified.<skill>` values usable.

## Implementation Plan

1. Define the new provider-specific `verifiedstats.<skill>` shape with `all_time`, `month`, and `week` buckets, including period keys for rollover detection.
2. Update `.aitask-scripts/aitask_verified_update.sh` to migrate old flat stats automatically and to update all three buckets on each rating.
3. Preserve `verified.<skill>` as the provider-specific all-time average so existing UI behavior remains backward compatible.
4. Define the normalization/grouping contract used later to compute `all_providers` rankings without duplicating aggregate values into every model entry.
5. Extend `tests/test_verified_update.sh` with migration, month rollover, week rollover, and multi-provider input scenarios.
6. Update schema documentation in `website/content/docs/tuis/settings/reference.md`, and update `.claude/skills/aitask-refresh-code-models/SKILL.md` if refresh instructions need to preserve the richer structure explicitly.

## Verification

- `bash tests/test_verified_update.sh`
- Manual inspection of updated model metadata confirms new bucketed stats and unchanged provider-specific `verified.<skill>` compatibility
