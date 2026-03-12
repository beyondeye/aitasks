---
priority: medium
effort: high
depends: [2]
issue_type: feature
status: Done
labels: [ait_settings, verifiedstats]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-11 15:50
updated_at: 2026-03-12 08:29
completed_at: 2026-03-12 08:29
---

## Context

This is child task 3 of t365 (verified stats for same model across different providers). It improves `ait settings` so verified-score information is easy to discover in both the `Models` tab and the `Agent Defaults` tab.

The current settings UI only exposes flat `verified` values in a few small labels, which makes it hard to understand which models are performing well and hard to choose defaults from verified evidence. This task builds on the richer stats schema from t365_2.

## Key Files to Modify

- `.aitask-scripts/settings/settings_app.py`
- `website/content/docs/tuis/settings/_index.md`
- `website/content/docs/tuis/settings/reference.md`

## Reference Files for Patterns

- `.aitask-scripts/settings/settings_app.py` - model picker, Agent Defaults tab, Models tab
- `website/content/docs/tuis/settings/reference.md` - settings behavior reference

## Implementation Plan

### 1. Add verified-score helper functions

- In `settings_app.py`, add helpers to compute:
  - provider-specific score summaries
  - `all_providers` score summaries
  - ranked models for a selected operation and timeframe

### 2. Improve Agent Defaults discoverability

- Update the Agent Defaults tab so saved defaults show more than a single `[score: X]` badge.
- Include score, run count, and recent-period context when available.
- Reorder or annotate picker results so the most verified models for the selected operation are obvious.

### 3. Add a ranked model selection path

- Extend the model picker flow so users can choose from a top-ranked verified list before falling back to the full provider/model browser.
- Keep the existing two-stage agent/model flow available as the complete fallback path.

### 4. Improve the Models tab summaries

- Show provider-specific verified information directly in model rows.
- Also expose `all_providers` summaries for the same LLM model where applicable.
- Keep the row text compact enough for terminal display.

## Verification Steps

- Run `ait settings`
- Confirm Agent Defaults shows richer verified context for existing defaults
- Confirm the picker exposes ranked models for the selected skill
- Confirm the Models tab shows both provider-specific and `all_providers` information when available
