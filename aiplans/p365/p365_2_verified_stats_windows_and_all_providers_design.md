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

Verified-score storage currently tracks provider-specific all-time totals only (`verifiedstats[skill] = {runs, score_sum}`). This task extends the data model with month/week time windows and defines how readers should aggregate scores across providers for the same underlying LLM model. The backward-compatible `verified[skill]` field (all-time average) must remain unchanged for existing consumers (settings TUI, board).

## Key Files

- `.aitask-scripts/aitask_verified_update.sh` — the only writer of verifiedstats (modify `update_model_file()`)
- `tests/test_verified_update.sh` — extend with migration, rollover, multi-provider tests
- `website/content/docs/tuis/settings/reference.md` — document new schema
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — verify schema guidance (already handles `verifiedstats: {}`)

## Implementation Plan

### 1. Update `update_model_file()` in `aitask_verified_update.sh`

The jq filter (lines 150-167) needs to:

a) **Detect and migrate old format**: If `verifiedstats[skill]` has `runs` at top level (no `all_time` key), migrate:
   ```
   old: {"runs": N, "score_sum": S}
   new: {"all_time": {"runs": N, "score_sum": S}, "month": {"period": "<current>", "runs": 0, "score_sum": 0}, "week": {"period": "<current>", "runs": 0, "score_sum": 0}}
   ```
   Then apply the new score on top of the migrated structure.

b) **New update logic** (after migration or for new entries):
   - Always increment `all_time.runs` and `all_time.score_sum`
   - Check `month.period` against current `YYYY-MM`:
     - If matches: increment `month.runs` and `month.score_sum`
     - If differs: reset to `{"period": "<current>", "runs": 1, "score_sum": <score>}`
   - Check `week.period` against current `YYYY-Www` (ISO 8601 `%G-W%V`):
     - If matches: increment `week.runs` and `week.score_sum`
     - If differs: reset to `{"period": "<current>", "runs": 1, "score_sum": <score>}`
   - Recalculate `verified[skill]` from `all_time` values (unchanged behavior)

c) **Pass current date info to jq**: Add `--arg current_month "$(date +%Y-%m)"` and `--arg current_week "$(date +%G-W%V)"` to the jq invocation. For testability, accept an optional `--date` argument (format `YYYY-MM-DD`) that overrides `date` for deterministic tests.

### 2. Add `--date` CLI argument for testability

Add to `parse_args()`:
- `--date YYYY-MM-DD` — optional override for current date (used to derive month/week periods)
- Default: use system `date`
- Derive `CURRENT_MONTH` and `CURRENT_WEEK` from this date

### 3. Define `all_providers` aggregation contract

**No storage changes needed.** Add a documented normalization rule:

**Rule:** To compute `all_providers` stats for a given underlying LLM model:
1. For each model entry across all `models_*.json` files, extract the model portion from `cli_id` by stripping the `provider/` prefix (e.g., `openai/gpt-5.4` → `gpt-5.4`, `opencode/gpt-5.4` → `gpt-5.4`)
2. Group entries with identical normalized model IDs
3. For each skill, sum `all_time.runs` and `all_time.score_sum` across the group, then compute average
4. Same for `month` and `week` (only aggregate entries with matching `period` values)

This contract will be:
- Documented in `website/content/docs/tuis/settings/reference.md`
- Implemented by readers (t365_3 settings TUI, t365_4 stats) — NOT by this task

### 4. Extend tests in `tests/test_verified_update.sh`

Add test cases:

- **Test: Old schema migration** — Set up old-format `verifiedstats`, run update, verify new bucketed structure with migrated all_time data
- **Test: Repeated updates within same month/week** — Two updates with same `--date`, verify month/week accumulate
- **Test: Month rollover** — First update with `--date 2026-01-15`, second with `--date 2026-02-15`, verify month resets but all_time accumulates
- **Test: Week rollover** — First update with `--date 2026-03-09` (Mon W11), second with `--date 2026-03-16` (Mon W12), verify week resets
- **Test: New skill entry gets full structure** — Update a skill with no prior stats, verify all three buckets created

### 5. Update documentation

**`website/content/docs/tuis/settings/reference.md`:**
- Add `verifiedstats` schema documentation showing the new bucketed structure
- Document the `all_providers` normalization rule
- Add note about automatic migration from old format

### 6. Check refresh-code-models skill

The skill already preserves `verifiedstats: {}` during model refresh. Verify that it doesn't need changes since the richer nested structure is still valid JSON preserved by `jq` merges. Likely no changes needed — just confirm.

## Verification

1. `bash tests/test_verified_update.sh` — all existing + new tests pass
2. Manual test: run `aitask_verified_update.sh` against a model with old-format stats, verify migration
3. Verify `verified[skill]` (backward-compat field) still works correctly for settings TUI
4. `shellcheck .aitask-scripts/aitask_verified_update.sh`

## Final Implementation Notes

- **Actual work done:** Rewrote `update_model_file()` jq filter in `aitask_verified_update.sh` to use bucketed `{all_time, month, week}` verifiedstats structure. Added `--date YYYY-MM-DD` CLI argument with portable date resolution (`resolve_date_periods()`) for deterministic tests. Added old-format auto-migration (flat `{runs, score_sum}` → bucketed on first write). Updated `tests/test_verified_update.sh` with 4 new test scenarios (old schema migration, month rollover, week rollover, new skill structure) — 54 total assertions all passing. Documented the new schema and `all_providers` aggregation contract in `website/content/docs/tuis/settings/reference.md`. Confirmed `aitask-refresh-code-models` skill needs no changes (preserves nested JSON as-is).
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Used `%G-W%V` (ISO 8601) for week period keys. Made `--date` argument portable across GNU and BSD date with platform detection. Month/week buckets start fresh (runs=0) during migration since we can't retroactively assign historical scores to periods. The `all_providers` contract is read-time only (no storage duplication) — normalization strips `provider/` prefix from `cli_id`.
- **Notes for sibling tasks:** t365_3 (settings TUI) and t365_4 (ait stats) should use the `all_providers` normalization rule from the reference docs to group models. Read `verifiedstats[skill].month` and `.week` for recent performance display. The `verified[skill]` field is still the all-time backward-compat average. Existing live data (e.g., `openai_gpt_5_4` with old-format pick stats in `models_opencode.json`) will be auto-migrated on the next feedback vote — no manual data migration needed.
