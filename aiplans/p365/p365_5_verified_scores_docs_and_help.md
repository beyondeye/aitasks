---
Task: t365_5_verified_scores_docs_and_help.md
Parent Task: aitasks/t365_verified_stats_for_same_model_different_providers.md
Sibling Tasks: aitasks/t365/t365_1_*.md through t365_4_*.md
Archived Sibling Plans: aiplans/archived/p365/p365_1_opencode_runtime_provider_mapping_fix.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Verified scores are currently visible in several places but not explained as a cohesive feature. Users need one clear reference that explains the feedback flow, score meaning, provider-specific versus `all_providers` views, and recent-period buckets.

## Implementation Plan

1. Create a dedicated verified-scores documentation page under `website/content/docs/skills/`.
2. Explain the end-of-skill feedback flow and how `enableFeedbackQuestions` affects score collection.
3. Explain the difference between provider-specific and `all_providers` views, plus all-time/month/week periods.
4. Add concise cross-links from `/aitask-pick`, execution profiles, settings docs, and `ait stats` docs.
5. Review terminology across the updated docs so `all_providers` is used consistently and older ambiguous wording is removed.

## Verification

- `hugo build --gc --minify` in `website/`
- Review updated docs for consistent terminology and clear cross-linking
