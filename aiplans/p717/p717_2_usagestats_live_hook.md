---
Task: t717_2_usagestats_live_hook.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Sibling Tasks: aitasks/t717/t717_1_verifiedstats_prev_month_schema.md, aitasks/t717/t717_3_agent_picker_recent_modes.md, aitasks/t717/t717_4_stats_tui_window_selector_usage_pane.md
Archived Sibling Plans: aiplans/archived/p717/p717_*_*.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
---

# t717_2 — usagestats: live hook + new aitask_usage_update.sh

## Goal

Track per-model run counts independently of whether a 1-5 score was collected. Add a parallel `usagestats[skill]` block (same shape as verifiedstats minus `score_sum`), bumped at the satisfaction-feedback procedure entry — unconditionally — so codex (which skips every `AskUserQuestion` after `ExitPlanMode`) is now visible in usage rankings.

## Pre-requisites

- t717_1 archived. The verifiedstats `prev_month` rollover logic + `previous_calendar_month()` helper are the canonical patterns this task mirrors.

## Schema after this task

```json
"usagestats": {
  "<skill>": {
    "all_time":   { "runs": N },
    "prev_month": { "period": "YYYY-MM", "runs": N },
    "month":      { "period": "YYYY-MM", "runs": N },
    "week":       { "period": "YYYY-Www", "runs": N }
  }
}
```

No `score_sum`. Rollover identical to verifiedstats from t717_1.

## Implementation

### 1. Extract shared lib `verified_update_lib.sh`

Create `.aitask-scripts/lib/verified_update_lib.sh`:

- Shebang `#!/usr/bin/env bash`, `set -euo pipefail` not used in libs (caller decides), but guard against double-source:
  ```bash
  [[ -n "${_AIT_VERIFIED_UPDATE_LIB_LOADED:-}" ]] && return 0
  _AIT_VERIFIED_UPDATE_LIB_LOADED=1
  ```
- Move from `aitask_verified_update.sh`:
  - `MAX_REMOTE_RETRIES=5` constant
  - `previous_calendar_month()` (added in t717_1)
  - `has_remote_tracking()`
  - `current_task_branch()`
  - `current_task_remote()`
  - `configure_clone_identity()`
  - `run_before_push_hook()`
  - `is_retryable_push_error()`
  - `sync_current_repo_from_remote()`
  - `commit_metadata_update_local()`
  - `commit_and_push_from_remote_clone()` — generalized: parameterize the per-script update via a callback variable. The lib reads `_AIT_UPDATE_MODEL_FILE_FN` (function name) and `_AIT_COMMIT_PREFIX` (commit message prefix, e.g. `"ait: Update verified score"` vs `"ait: Update usage count"`). Caller assigns these before invoking.
  - `commit_metadata_update()` — the dispatcher between local-only and remote retrying.

The `update_model_file` function itself remains in each caller script (the jq logic differs).

### 2. Refactor `aitask_verified_update.sh`

- `source "$SCRIPT_DIR/lib/verified_update_lib.sh"` after the existing `terminal_compat.sh` / `task_utils.sh` sources.
- Remove the moved helpers from the script body.
- Before calling `commit_metadata_update`, set:
  ```bash
  _AIT_UPDATE_MODEL_FILE_FN=update_model_file
  _AIT_COMMIT_PREFIX="ait: Update verified score"
  ```
- Verify all existing tests still pass — refactor is no-op.

### 3. Create `.aitask-scripts/aitask_usage_update.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"
source "$SCRIPT_DIR/lib/verified_update_lib.sh"

SUPPORTED_AGENTS=(claudecode geminicli codex opencode)

AGENT_STRING=""
CLI_AGENT=""
CLI_ID=""
SKILL_NAME=""
SILENT=false
DATE_OVERRIDE=""

PARSED_AGENT=""
PARSED_MODEL=""
CURRENT_MONTH=""
CURRENT_WEEK=""
PREV_MONTH=""

show_help() { ... }   # adapt — no --score

require_jq()  { ... }
log_info()    { ... }
run_git_quiet() { ... }

parse_agent_string() { ... }   # identical to verified_update.sh

resolve_date_periods() { ... } # identical
                                # then: PREV_MONTH="$(previous_calendar_month "$CURRENT_MONTH")"

parse_args() {
    # accept --agent-string OR --agent + --cli-id, --skill, --date, --silent
    # No --score parsing.
    # Validate --skill non-empty.
    ...
}

models_file_for_agent() { ... }
ensure_model_exists()   { ... }

update_model_file() {
    local models_file="$1"
    local model_name="$2"
    local skill_name="$3"

    local tmp_file
    tmp_file="$(mktemp "${TMPDIR:-/tmp}/aitask_usage_update.XXXXXX")"

    jq \
        --arg model "$model_name" \
        --arg skill "$skill_name" \
        --arg current_month "$CURRENT_MONTH" \
        --arg current_week "$CURRENT_WEEK" \
        --arg prev_month_target "$PREV_MONTH" '
        .models |= map(
            if .name == $model then
                .usagestats = (.usagestats // {}) |
                (
                    .usagestats[$skill] as $existing |
                    (
                        if ($existing | type) == "object" and ($existing | has("all_time")) then
                            $existing | (.prev_month //= {"period": "", "runs": 0})
                        else
                            {
                                "all_time":   {"runs": 0},
                                "prev_month": {"period": "", "runs": 0},
                                "month":      {"period": $current_month, "runs": 0},
                                "week":       {"period": $current_week,  "runs": 0}
                            }
                        end
                    ) as $base |
                    ($base.all_time.runs + 1) as $at_runs |
                    (if $base.month.period == $current_month then
                        $base.prev_month
                     elif $base.month.period == $prev_month_target then
                        $base.month
                     else
                        {"period": "", "runs": 0}
                     end) as $pm |
                    (if $base.month.period == $current_month then ($base.month.runs + 1) else 1 end) as $m_runs |
                    (if $base.week.period  == $current_week  then ($base.week.runs + 1)  else 1 end) as $w_runs |
                    .usagestats[$skill] = {
                        "all_time":   {"runs": $at_runs},
                        "prev_month": $pm,
                        "month":      {"period": $current_month, "runs": $m_runs},
                        "week":       {"period": $current_week,  "runs": $w_runs}
                    }
                )
            else
                .
            end
        )
        ' "$models_file" > "$tmp_file"

    mv "$tmp_file" "$models_file"

    jq -r --arg model "$model_name" --arg skill "$skill_name" '
        .models[] | select(.name == $model) | .usagestats[$skill].month.runs
    ' "$models_file"
}

main() {
    require_jq
    parse_args "$@"
    resolve_date_periods
    PREV_MONTH="$(previous_calendar_month "$CURRENT_MONTH")"

    local models_file
    models_file="$(models_file_for_agent "$PARSED_AGENT")"
    [[ -f "$models_file" ]] || die "Model config not found: $models_file"

    ensure_model_exists "$models_file" "$PARSED_MODEL"

    _AIT_UPDATE_MODEL_FILE_FN=update_model_file
    _AIT_COMMIT_PREFIX="ait: Update usage count"

    local new_runs
    if has_remote_tracking; then
        new_runs="$(commit_metadata_update "$models_file" "$AGENT_STRING" "$SKILL_NAME" "$PARSED_MODEL")"
    else
        if [[ "$SILENT" == "false" ]]; then
            warn "No remote configured for task data; using local-only usage update without concurrency protection."
        fi
        new_runs="$(update_model_file "$models_file" "$PARSED_MODEL" "$SKILL_NAME")"
        commit_metadata_update_local "$models_file" "$AGENT_STRING" "$SKILL_NAME"
    fi

    if [[ "$SILENT" == "false" ]]; then
        success "Updated ${AGENT_STRING} ${SKILL_NAME} usage count to ${new_runs}"
    fi
    echo "UPDATED:${AGENT_STRING}:${SKILL_NAME}:${new_runs}"
}

main "$@"
```

The `commit_and_push_from_remote_clone` in the lib calls `"$_AIT_UPDATE_MODEL_FILE_FN"` indirectly. Adjust its signature so the score is passed positionally only when present — easiest is to pass the score (or empty string for usage) as an extra arg that the verified callback consumes and the usage callback ignores. Practical sketch:

```bash
# in lib:
"$_AIT_UPDATE_MODEL_FILE_FN" "$clone_dir/$models_file" "$model_name" "$skill_name" "${5:-}"
# verified callback signature: update_model_file(models_file, model_name, skill_name, raw_score)
# usage    callback signature: update_model_file(models_file, model_name, skill_name) — ignore $4
```

Verify that `commit_metadata_update` signature is preserved for backward compat.

### 4. Wire the satisfaction-feedback hook

Edit `.claude/skills/task-workflow/satisfaction-feedback.md`. Add a new `## Step 0 — Record usage` section BEFORE the existing first step. Critical placement details:

- Step 0 runs BEFORE the early-out for `enableFeedbackQuestions=false` (usage is unconditional).
- Step 0 has its own guard: `if usage_collected: skip`. Otherwise proceed.
- Step 0 reuses `detected_agent_string` if already set; else calls the Model Self-Detection Sub-Procedure (same as the existing Step 1 flow).
- Step 0 invokes:
  ```
  ./.aitask-scripts/aitask_usage_update.sh \
    --agent-string "<agent_string>" \
    --skill "<skill_name>" \
    --silent
  ```
- On success: set `usage_collected=true`. Any non-zero exit: warn, set `usage_collected=true` anyway (to avoid double-attempt on retry), continue.
- Step 0 must NOT short-circuit Step 1 — both are independent.

Add the `usage_collected` variable to `.claude/skills/task-workflow/SKILL.md` Context Requirements table:

```
| `usage_collected` | boolean | Guard flag — initialized to `false`. Set to `true` after the usage bump fires. Prevents double execution. |
```

### 5. 5-touchpoint whitelist

For each touchpoint, add an entry mirroring `aitask_verified_update.sh`'s existing entry:

- `.claude/settings.local.json`: append `"Bash(./.aitask-scripts/aitask_usage_update.sh:*)"` to `permissions.allow`.
- `.gemini/policies/aitasks-whitelist.toml`: add new `[[rules]]` block with `decision = "allow"` and `commandPrefix = "./.aitask-scripts/aitask_usage_update.sh"`.
- `seed/claude_settings.local.json`: same as runtime claude settings.
- `seed/geminicli_policies/aitasks-whitelist.toml`: same as runtime gemini policy.
- `seed/opencode_config.seed.json`: add `"./.aitask-scripts/aitask_usage_update.sh *": "allow"` under permissions.

Codex (`.codex/config.toml`, `seed/codex_config.seed.toml`) does not need a whitelist entry per CLAUDE.md.

### 6. Tests — `tests/test_usage_update.sh`

Fixture pattern (mirror `tests/test_verified_update.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail

# helpers: assert_eq, assert_contains, mk_fake_models_file
# fixtures use a temp dir with fake aitasks/metadata/models_<agent>.json
```

Test cases:

1. **Fresh model — no usagestats key.** Run script. Assert `usagestats.pick = {all_time:{runs:1}, prev_month:{period:"", runs:0}, month:{period:CURRENT, runs:1}, week:{period:CURRENT, runs:1}}`.
2. **Existing same-month bump.** Pre-seed `usagestats.pick.month = {period:current, runs:3}`. Run with same date. Assert month.runs=4.
3. **One-month rollover.** Pre-seed `month.period=2026-04, runs=5`. Run `--date 2026-05-01`. Assert prev_month=`{period:"2026-04", runs:5}`, month=`{period:"2026-05", runs:1}`.
4. **Multi-month skip.** Pre-seed `month.period=2026-02, runs=3, prev_month={period:"2026-01", runs:1}`. Run `--date 2026-05-01`. Assert prev_month=`{period:"", runs:0}`, month=`{period:"2026-05", runs:1}`.
5. **Two skills accumulate independently.** Run `--skill pick`, then `--skill explore`. Assert both blocks present, neither clobbers the other.
6. **Verified data untouched.** Pre-seed `verifiedstats.pick={...}` and `verified={pick:80}`. Run usage script. Assert verifiedstats unchanged byte-for-byte, verified unchanged.
7. **Agent-not-found error.** Run with `--agent-string fake/whatever`. Assert non-zero exit and helpful error.
8. **Model-not-found error.** Run with `--agent-string claudecode/nonexistent`. Assert non-zero exit.

## Verify

```bash
bash tests/test_verified_update.sh    # still passes (lib extraction is no-op)
bash tests/test_usage_update.sh        # new tests pass
shellcheck .aitask-scripts/aitask_verified_update.sh \
           .aitask-scripts/aitask_usage_update.sh \
           .aitask-scripts/lib/verified_update_lib.sh
```

End-to-end manual:
- Pick a small skill (e.g. an existing simple completed task), run /aitask-pick on it. After Step 8 commits, the satisfaction-feedback procedure runs:
  - Step 0 fires `aitask_usage_update.sh` — observe `models_*.json` updated with usagestats[skill].
  - Step 1 fires the score AskUserQuestion. If user picks a score, verifiedstats also bumps. If user picks "Skip", verifiedstats does not bump but usagestats stays.

## Notes for sibling tasks (t717_3, t717_4)

- `usagestats[skill][bucket].runs` is the data source for picker `_build_top_usage` and stats TUI `load_usage_rankings`.
- The recent window = `month.runs + prev_month.runs`. Same convention used by t717_3 and t717_4.
- The shared `verified_update_lib.sh` is also a useful integration point if a future feature needs another model-file mutator.
