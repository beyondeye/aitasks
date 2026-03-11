---
priority: high
effort: high
depends: [1]
issue_type: feature
status: Implementing
labels: [verifiedstats, opencode]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-11 15:50
updated_at: 2026-03-11 19:01
---

## Context

This is child task 2 of t365 (verified stats for same model across different providers). It redesigns the verified-score data model so stats remain available per provider/model entry while also supporting `all_providers` aggregation for the same underlying LLM model, plus current month and current week tracking.

Current `verifiedstats` data is provider-specific and all-time only. The task investigation also confirmed that `ait settings` and `ait stats` will need richer data than the current flat `{runs, score_sum}` shape. This task establishes the storage and migration rules that the later UI and reporting tasks depend on.

## Key Files to Modify

- `.aitask-scripts/aitask_verified_update.sh`
- `tests/test_verified_update.sh`
- `website/content/docs/tuis/settings/reference.md`
- `.claude/skills/aitask-refresh-code-models/SKILL.md` (if schema guidance needs updating)

## Reference Files for Patterns

- `.aitask-scripts/aitask_verified_update.sh` - current verifiedstats update flow
- `tests/test_verified_update.sh` - schema/update test structure
- `aitasks/metadata/models_opencode.json` - current model metadata shape

## Implementation Plan

### 1. Define the new provider-specific storage shape

- Replace the flat per-skill stats object with a richer provider-specific structure:

```json
{
  "all_time": {"runs": 0, "score_sum": 0},
  "month": {"period": "YYYY-MM", "runs": 0, "score_sum": 0},
  "week": {"period": "YYYY-Www", "runs": 0, "score_sum": 0}
}
```

- Keep `verified.<skill>` as the provider-specific all-time average for backward compatibility.

### 2. Implement migration and update rules

- Update `.aitask-scripts/aitask_verified_update.sh` so existing flat stats are upgraded automatically on first write.
- On every update:
  - increment `all_time`
  - reset/restart `month` when the calendar month changes
  - reset/restart `week` when the calendar week changes
  - recalculate provider-specific `verified.<skill>` from all-time values

### 3. Define `all_providers` aggregation contract

- Do not store duplicate aggregate values in each model entry.
- Instead, define how readers group provider-specific entries into the same underlying LLM model for `all_providers` calculations.
- Document the normalization rule clearly so UI and stats tasks can reuse it without inventing separate logic.

### 4. Add regression and migration tests

- Extend `tests/test_verified_update.sh` with cases for:
  - old-schema migration
  - repeated updates within same month/week
  - month rollover
  - week rollover
  - input data later used for same-model/all-providers aggregation

## Verification Steps

- `bash tests/test_verified_update.sh`
- provider-specific `verified.<skill>` values still update correctly
- new `verifiedstats` entries contain all-time, month, and week buckets
