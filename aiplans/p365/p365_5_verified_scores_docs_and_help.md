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

**File:** `website/content/docs/skills/verified-scores.md` (weight: 110)

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

## Post-Review Changes

### Change Request 1 (2026-03-15 22:30)
- **Requested by user:** Move verified-scores page to the bottom of the skills subpage list
- **Changes made:** Changed weight from 55 to 110 (highest existing was 100)
- **Files affected:** `website/content/docs/skills/verified-scores.md`

### Change Request 2 (2026-03-15 22:32)
- **Requested by user:** Execution profiles link in verified-scores page is broken (resolves to subpage of verified-scores instead of aitask-pick)
- **Changes made:** Changed relative link `aitask-pick/execution-profiles/` to Hugo relref `{{< relref "/docs/skills/aitask-pick/execution-profiles" >}}`. Also fixed `ait stats` link to use relref.
- **Files affected:** `website/content/docs/skills/verified-scores.md`

## Final Implementation Notes

- **Actual work done:** Created `website/content/docs/skills/verified-scores.md` as a dedicated reference page covering the full verified scores feature: score collection, scale, time windows, provider-specific vs all_providers, and where scores appear. Added cross-links from 6 existing docs (skills _index, aitask-pick, execution-profiles, aitask-stats, settings _index, settings reference). Fixed one terminology inconsistency in reference.md ("verification scores" → "verified scores").
- **Deviations from plan:** Changed page weight from 55 to 110 per user request to place it at the bottom of the skills list. Used Hugo `relref` shortcodes for all cross-page links instead of relative paths, which is more reliable. Did not add a link from the Notes section of execution-profiles.md as originally planned — the inline link on the `enableFeedbackQuestions` row is sufficient.
- **Issues encountered:** Initial relative link for execution profiles resolved incorrectly because Hugo treats leaf pages differently. Fixed by switching to absolute `relref`.
- **Key decisions:** The new page explains the user-facing concept without duplicating the technical schema (model entry, buckets) already documented in `reference.md`. Links to reference.md for the detailed JSON structure. All cross-links use Hugo `relref` for reliable resolution.
- **Notes for sibling tasks:** This is the last child task (t365_5). All verified-scores documentation is now cross-linked. The terminology standard is: `verified scores` (lowercase), `all_providers` (code-formatted), `provider-specific`.
