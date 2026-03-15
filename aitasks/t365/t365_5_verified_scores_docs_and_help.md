---
priority: medium
effort: medium
depends: [3, 4]
issue_type: documentation
status: Implementing
labels: [docs, verifiedstats]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-11 15:50
updated_at: 2026-03-15 22:24
---

## Context

This is child task 5 of t365 (verified stats for same model across different providers). It documents verified scores clearly across the website and settings help, including provider-specific versus `all_providers` views, recent-period buckets, and the end-of-skill feedback flow that updates the scores.

The investigation confirmed that verified scores are currently undocumented as a cohesive feature. Users can encounter the feedback question, see some score hints in settings, and still have no single place that explains what the numbers mean or how they are accumulated.

## Key Files to Modify

- `website/content/docs/skills/aitask-pick/_index.md`
- `website/content/docs/skills/aitask-pick/execution-profiles.md`
- `website/content/docs/skills/aitask-stats.md`
- `website/content/docs/tuis/settings/reference.md`
- `website/content/docs/tuis/settings/_index.md`
- new verified-scores documentation page under `website/content/docs/skills/`

## Reference Files for Patterns

- `website/content/docs/skills/aitask-pick/_index.md`
- `website/content/docs/skills/aitask-pick/execution-profiles.md`
- `website/content/docs/tuis/settings/reference.md`

## Implementation Plan

### 1. Create a single reference page for verified scores

- Add a dedicated documentation page that explains:
  - what verified scores are
  - how the end-of-skill rating updates them
  - provider-specific versus `all_providers` views
  - all-time versus month/week windows

### 2. Cross-link the main user entry points

- Add concise references from:
  - `/aitask-pick` docs
  - execution profile docs (`enableFeedbackQuestions`)
  - settings docs
  - `ait stats` docs

### 3. Align terminology across docs

- Use `provider-specific` and `all_providers` consistently.
- Avoid older ambiguous wording such as "canonical" in user-facing docs.

## Verification Steps

- `hugo build --gc --minify` in `website/`
- Review linked pages to confirm consistent terminology and no stale wording
