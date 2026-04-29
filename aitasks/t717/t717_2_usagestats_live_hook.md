---
priority: medium
effort: medium
depends: [t717_1]
issue_type: feature
status: Ready
labels: [verifiedstats, statistics]
created_at: 2026-04-30 00:18
updated_at: 2026-04-30 00:18
---

## Context

Second child of t717. Adds a parallel `usagestats[skill]` block that tracks plain run counts (no 1-5 score) for each agent/model/skill combination. The hook fires unconditionally at the satisfaction-feedback procedure entry — so codex (which skips every `AskUserQuestion` after `ExitPlanMode`) still gets counted, even though it never reaches the verified-score prompt.

User-confirmed schema (parallel to verifiedstats added by t717_1):

```
"usagestats": {
  "<skill>": {
    "all_time":   { "runs": N },
    "prev_month": { "period": "YYYY-MM", "runs": N },
    "month":      { "period": "YYYY-MM", "runs": N },
    "week":       { "period": "YYYY-Www", "runs": N }
  }
}
```

Rollover rule is identical to verifiedstats (see t717_1 archived plan): on month change, copy `month` → `prev_month`; if multi-month skip, zero `prev_month` first. No `score_sum` field anywhere.

## Key Files to Modify

- **NEW:** `.aitask-scripts/aitask_usage_update.sh` — mirror of `aitask_verified_update.sh` minus `--score` and minus `score_sum` everywhere. Same CLI surface (`--agent-string` or `--agent --cli-id`, `--skill`, `--date`, `--silent`).
- **NEW:** `.aitask-scripts/lib/verified_update_lib.sh` — sourced helper extracted from existing verified_update.sh, holding the remote-aware commit-and-push retry logic. Both update scripts source it.
- `.aitask-scripts/aitask_verified_update.sh` — refactor to source the new lib (no behavior change).
- `.claude/skills/task-workflow/satisfaction-feedback.md` — add a new first step ("Step 0 — record usage") that calls `aitask_usage_update.sh` BEFORE the verified-score `AskUserQuestion`. Guard with a fresh `usage_collected` context variable (separate from existing `feedback_collected`) to ensure once-per-workflow execution. Must run regardless of `enableFeedbackQuestions` profile setting.
- `.claude/skills/task-workflow/SKILL.md` — add `usage_collected` to the Context Requirements table (initialized to `false`, semantics: "guard flag — set to `true` after the usage bump fires").
- 5-touchpoint helper-script whitelist for the new `aitask_usage_update.sh`:
  - `.claude/settings.local.json` → `permissions.allow`
  - `.gemini/policies/aitasks-whitelist.toml` → new `[[rules]]` block
  - `seed/claude_settings.local.json`
  - `seed/geminicli_policies/aitasks-whitelist.toml`
  - `seed/opencode_config.seed.json`
- **NEW:** `tests/test_usage_update.sh` — fixture-based tests for the new script.

## Reference Files for Patterns

- `.aitask-scripts/aitask_verified_update.sh` — source of the script structure to mirror. The new lib will hold:
  - `has_remote_tracking()`, `current_task_branch()`, `current_task_remote()`, `configure_clone_identity()`, `run_before_push_hook()`, `is_retryable_push_error()`, `sync_current_repo_from_remote()`, `commit_and_push_from_remote_clone()` (parameterized by an `update_model_file_fn` callback), `commit_metadata_update_local()`, `commit_metadata_update()`, `MAX_REMOTE_RETRIES`. The callback indirection lets each script pass its own `update_model_file` while sharing the remote/retry shell.
- `previous_calendar_month()` helper added in t717_1 (see archived `aiplans/archived/p717/p717_1_*.md`) — reuse verbatim in `aitask_usage_update.sh`. If t717_1 placed it inline rather than in a sourced lib, move it into `verified_update_lib.sh` here.
- `tests/test_verified_update.sh` (extended in t717_1) — same fixture pattern: temp dir, fake `aitasks/metadata/models_<agent>.json`, run script, jq-assert.
- `.claude/skills/task-workflow/satisfaction-feedback.md` — the existing `feedback_collected` guard at procedure entry is the model for `usage_collected`.

## Implementation Plan

1. **Extract shared lib first.**
   - Create `.aitask-scripts/lib/verified_update_lib.sh` with the remote-aware push/retry block. Use a callback variable `_AIT_UPDATE_MODEL_FILE_FN` that the caller sets to the name of its own `update_model_file` function before invoking `commit_metadata_update`.
   - Modify `aitask_verified_update.sh` to `source` the lib and assign `_AIT_UPDATE_MODEL_FILE_FN=update_model_file`. Verify all existing tests still pass (no regression).
   - Lib must guard against double-source via `_AIT_VERIFIED_UPDATE_LIB_LOADED` (per CLAUDE.md shell convention).

2. **Create `aitask_usage_update.sh`.**
   - Header / shebang / sourcing matches verified_update.sh.
   - Args: `--agent-string`, `--agent`, `--cli-id`, `--skill`, `--date`, `--silent`. NO `--score`.
   - Globals: `AGENT_STRING`, `CLI_AGENT`, `CLI_ID`, `SKILL_NAME`, `SILENT`, `DATE_OVERRIDE`, `PARSED_AGENT`, `PARSED_MODEL`, `CURRENT_MONTH`, `CURRENT_WEEK`, `PREV_MONTH`.
   - `update_model_file()`: jq pipeline that mutates `usagestats[$skill]`. Rollover identical to verifiedstats (see t717_1) but no score_sum. The flat `verified[$skill]` aggregate should NOT be touched — usage is a separate concept. Print the new `month.runs` value as the success line.
   - `_AIT_UPDATE_MODEL_FILE_FN=update_model_file` before calling `commit_metadata_update`.
   - Commit message: `ait: Update usage count for ${agent_string} ${skill_name}`.
   - Final stdout line on success: `UPDATED:${AGENT_STRING}:${SKILL_NAME}:${month_runs}` (parallel to verified_update's `UPDATED:...`).

3. **Wire the satisfaction-feedback hook.**
   - In `.claude/skills/task-workflow/satisfaction-feedback.md`, add new Step 0 BEFORE the existing "skip if enableFeedbackQuestions=false" early-out and BEFORE the existing `feedback_collected` guard:
     - Step 0 has its own guard: `if usage_collected == true: skip`.
     - Step 0 reuses the same agent string detection that Step 1 already does (delegate to the Model Self-Detection Sub-Procedure if `detected_agent_string` is null — same as the existing flow).
     - Step 0 calls `./.aitask-scripts/aitask_usage_update.sh --agent-string <agent_string> --skill <skill_name> --silent`.
     - On success: set `usage_collected=true`. On failure: warn and continue (do NOT abort the workflow — usage is best-effort).
   - The order is intentional: usage bumps unconditionally; verified bump is gated on the score `AskUserQuestion` answer.
   - Update SKILL.md Context Requirements table.

4. **Whitelist touchpoints (5).** For each, follow the pattern of an existing helper script (e.g. `aitask_verified_update.sh`):
   - `.claude/settings.local.json`: append `"Bash(./.aitask-scripts/aitask_usage_update.sh:*)"` to `permissions.allow`.
   - `.gemini/policies/aitasks-whitelist.toml`: add `[[rules]]` block with `commandPrefix = "./.aitask-scripts/aitask_usage_update.sh"` and `decision = "allow"`.
   - `seed/claude_settings.local.json`: mirror runtime entry.
   - `seed/geminicli_policies/aitasks-whitelist.toml`: mirror runtime entry.
   - `seed/opencode_config.seed.json`: add `"./.aitask-scripts/aitask_usage_update.sh *": "allow"` under permissions.

5. **Tests.** `tests/test_usage_update.sh`:
   - Fresh model with no `usagestats` key → adds full block, all buckets at runs=1.
   - Existing `usagestats[pick].month` with same period → runs increments, prev_month untouched.
   - Existing `usagestats[pick].month` with prior period (one-month skip) → prev_month copies old month, month resets.
   - Multi-month skip → prev_month zeroed, month resets.
   - Two skills in sequence → both blocks present, independent runs.
   - Agent-not-found → exits non-zero with sensible error.
   - Verified data on the same model is NOT touched (assert verifiedstats and verified blocks unchanged).

## Verification Steps

1. `bash tests/test_verified_update.sh` — must still pass (lib extraction is no-op).
2. `bash tests/test_usage_update.sh` — new tests pass.
3. `shellcheck .aitask-scripts/aitask_usage_update.sh .aitask-scripts/lib/verified_update_lib.sh .aitask-scripts/aitask_verified_update.sh` — clean.
4. Manual end-to-end: simulate a satisfaction-feedback flow where the user picks "Skip" on the score prompt — confirm `usagestats[pick].month.runs` incremented but `verifiedstats[pick].month.runs` unchanged.
5. Confirm whitelist coverage: in a fresh shell, run `./.aitask-scripts/aitask_usage_update.sh --help` via Claude Code and confirm no permission prompt is triggered.

## Notes for sibling tasks (t717_3 / t717_4)

- The `usagestats[skill][bucket].runs` field is the data source for t717_3's `_build_top_usage` and t717_4's `load_usage_rankings`. Both will sum `month.runs + prev_month.runs` for the "recent" window.
- The `verified_update_lib.sh` extraction may also be useful if future tasks add more model-file mutators (e.g., a separate "agent feedback notes" updater).
