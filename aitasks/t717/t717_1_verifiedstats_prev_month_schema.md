---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [verifiedstats, statistics]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-30 00:17
updated_at: 2026-04-30 10:01
---

## Context

Foundation child of t717. Today `verifiedstats[skill]` has buckets `all_time`, `month`, `week`. The `month` bucket is overwritten when the calendar rolls over, losing the previous month's data and making it impossible to display a stable "current + last calendar month" recent window. This task adds a `prev_month` bucket and a rollover rule that copies `month` → `prev_month` before reset. All downstream children of t717 (usage hook, agent picker, stats TUI) depend on this layout.

User-confirmed schema (no further design needed — see parent plan in aiplans/p717_codeagent_usage_stats_improvements.md):

```
"verifiedstats": {
  "<skill>": {
    "all_time":   { "runs": N, "score_sum": S },
    "prev_month": { "period": "YYYY-MM", "runs": N, "score_sum": S },  // NEW
    "month":      { "period": "YYYY-MM", "runs": N, "score_sum": S },
    "week":       { "period": "YYYY-Www", "runs": N, "score_sum": S }
  }
}
```

## Key Files to Modify

- `.aitask-scripts/aitask_verified_update.sh` — extend `update_model_file()` jq pipeline:
  - On read of existing `verifiedstats[skill]`, treat missing `prev_month` as `{period: "", runs: 0, score_sum: 0}`.
  - Before incrementing `month`, if `month.period != $current_month`: assign `prev_month = month` (preserving `month.period`), reset `month = {period: $current_month, runs: 0, score_sum: 0}`.
  - If existing `prev_month.period` is older than `(current_month - 1 calendar month)` (e.g., user skipped 2+ months), zero out `prev_month` before the copy.
  - All-time and week behavior unchanged.
- `tests/test_verified_update.sh` — extend with new test cases (see Verification Steps).

## Reference Files for Patterns

- Existing `update_model_file()` jq logic in `.aitask-scripts/aitask_verified_update.sh:197-254` — the `if/elif/else` ladder for bucket migration is the model. Extend the inner `as $base` resolution and the trailing `verifiedstats[$skill] = {...}` assignment.
- `resolve_date_periods()` in same file (line 96) — already computes `CURRENT_MONTH`. Add a small bash helper `previous_calendar_month()` that returns `YYYY-MM` of the month before `CURRENT_MONTH`. Use `date -d "$CURRENT_MONTH-01 -1 month" "+%Y-%m"` (GNU) or `date -j -v-1m -f "%Y-%m-%d" "$CURRENT_MONTH-01" "+%Y-%m"` (BSD).
- Existing tests in `tests/test_verified_update.sh` — follow the same fixture pattern (temp models JSON, run script, jq-assert the result).

## Implementation Plan

1. Add a `previous_calendar_month()` helper near `resolve_date_periods()` for portable previous-month computation. Set a new global `PREV_MONTH` after `resolve_date_periods()` runs.
2. Modify the jq pipeline in `update_model_file()`:
   - Pass a new `--arg prev_month_target "$PREV_MONTH"`.
   - In the `as $base` resolution, ensure `prev_month` is always present in the output (default `{period: "", runs: 0, score_sum: 0}` when reading old format).
   - Compute `$pm` (the new prev_month value) as:
     - If `$base.month.period == $current_month` → `$base.prev_month` unchanged.
     - Else (rolling over): use `$base.month` as the new `prev_month` IF its period equals `$prev_month_target` (one-month rollover); otherwise reset `prev_month` to `{period: "", runs: 0, score_sum: 0}` (multi-month skip).
   - Compute `$m_runs` / `$m_sum` as before — the rollover side effect on `prev_month` is independent.
   - Emit the final 4-bucket dict.
3. Migration safety: the `if .verifiedstats[$skill] | has("all_time") and has("prev_month") | not` migration condition needs to handle three legacy shapes:
   a. Pre-bucketed flat `{runs, score_sum}` (already handled — extend to also seed prev_month).
   b. Bucketed but missing prev_month (new — seed prev_month).
   c. Fresh skill (no key) — already handled.
4. Confirm `verified[$skill]` (the flat aggregate) still updates from `all_time` (no change to its semantics).
5. Update consumers that read `verifiedstats[skill]`:
   - `.aitask-scripts/lib/agent_model_picker.py` `_format_op_stats()` — defensive `.get("prev_month", {})` only; do NOT change displayed string yet (t717_3 owns picker UX). Leaving this read-only consumer untouched is acceptable as long as nothing crashes.
   - `.aitask-scripts/stats/stats_data.py` `load_verified_rankings()` — defensive read only; do NOT add new windows yet (t717_4 owns stats UI).

## Verification Steps

Run `bash tests/test_verified_update.sh` (extended). Add test cases:

1. **Same-month bump:** start with `month.period=2026-04, runs=2, score_sum=180`, run `--date 2026-04-29 --score 5` → `month.runs=3, month.score_sum=280`, prev_month untouched.
2. **One-month rollover:** start with `month.period=2026-04, runs=5, score_sum=480` and no prev_month, run `--date 2026-05-01 --score 4` → `prev_month={period:"2026-04", runs:5, score_sum:480}`, `month={period:"2026-05", runs:1, score_sum:80}`.
3. **Multi-month skip:** start with `month.period=2026-02, runs=3, score_sum=240`, run `--date 2026-05-01 --score 5` → `prev_month={period:"", runs:0, score_sum:0}` (because Feb is older than April = current-1), `month={period:"2026-05", runs:1, score_sum:100}`.
4. **Migration from pre-bucketed flat:** start with `verifiedstats.pick={runs:10, score_sum:920}` (legacy), run any bump → `all_time={runs:11, score_sum:920+map_score}`, `prev_month={period:"", runs:0, score_sum:0}`, `month={period:current, runs:1, score_sum:map_score}`, `week={period:current, runs:1, score_sum:map_score}`.
5. **Migration from bucketed-but-no-prev_month:** start with `verifiedstats.pick={all_time, month, week}` (current bucketed but pre-prev_month), run a same-month bump → output gains `prev_month={period:"", runs:0, score_sum:0}` in addition to incrementing month/all_time/week.

Also run:
- `shellcheck .aitask-scripts/aitask_verified_update.sh` — must be clean.
- Manual: `cp aitasks/metadata/models_claudecode.json /tmp/backup.json`, run a script invocation with a back-dated `--date`, then `git diff` the file and confirm prev_month is well-formed.

## Notes for sibling tasks (t717_2 / 3 / 4)

- `previous_calendar_month()` helper is reusable — t717_2's `aitask_usage_update.sh` will need the exact same logic. Recommend extracting it to a sourced helper in t717_2 (which is the right time, since two callers exist).
- The jq rollover ladder for `prev_month` is the **canonical pattern** for t717_2's usagestats rollover — same conditions, just no `score_sum`. Keep the verified jq readable so t717_2 can adapt it.
- No schema changes elsewhere in this task — t717_2 owns the parallel `usagestats` field.
