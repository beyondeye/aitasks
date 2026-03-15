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

### 1. Create dedicated verified-scores page

**File:** `website/content/docs/skills/verified-scores.md` (weight: 55)

Content sections:
- What are verified scores — 1-5 rating at end of skill runs, mapped to 20-100 scale
- How scores are collected — satisfaction feedback prompt, list of supporting skills, `enableFeedbackQuestions` profile field
- Score scale — 0 = untested, 1-49 = partial, 50-79 = verified, 80-100 = highly verified
- Time windows — all_time, month (YYYY-MM), week (YYYY-Www)
- Provider-specific vs all_providers — aggregation by stripping provider prefix, read-time only
- Where scores appear — `ait settings` tabs, `ait stats` rankings/plots
- Controlling feedback — `enableFeedbackQuestions` in execution profiles

### 2. Add cross-links from existing docs

- `website/content/docs/skills/_index.md` — add to Configuration & Reporting table
- `website/content/docs/skills/aitask-pick/_index.md` — add Verified Scores section after Commit Attribution
- `website/content/docs/skills/aitask-pick/execution-profiles.md` — link from enableFeedbackQuestions and Notes
- `website/content/docs/skills/aitask-stats.md` — link after verified rankings bullet
- `website/content/docs/tuis/settings/_index.md` — link from Agent Defaults verified score context
- `website/content/docs/tuis/settings/reference.md` — links from Verified Stats Buckets and All-Providers sections

### 3. Terminology consistency

Use consistently: `all_providers`, `provider-specific`, `verified scores` (lowercase except titles)

## Verification

- `hugo build --gc --minify` in `website/`
- Review updated docs for consistent terminology and clear cross-linking
- Verify all relative links resolve correctly
