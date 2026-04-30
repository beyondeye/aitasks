---
Task: t717_2_usagestats_live_hook.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Sibling Tasks: aitasks/t717/t717_3_agent_picker_recent_modes.md, aitasks/t717/t717_4_stats_tui_window_selector_usage_pane.md, aitasks/t717/t717_5_manual_verification_codeagent_usage_stats.md, aitasks/t717/t717_6_dedupe_verify_path_model_detection.md
Archived Sibling Plans: aiplans/archived/p717/p717_1_verifiedstats_prev_month_schema.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 10:46
---

# t717_2 — usagestats: live hook + new aitask_usage_update.sh

## Context

Verified models like codex skip every `AskUserQuestion` after `ExitPlanMode`, so they never reach the satisfaction-feedback score prompt and are invisible in `verifiedstats`. This task adds a parallel `usagestats[skill]` block (same shape as `verifiedstats` minus `score_sum`) that is bumped unconditionally at the satisfaction-feedback procedure entry, before any user prompt. Downstream siblings t717_3 (agent-picker recent modes) and t717_4 (stats TUI usage pane) consume this data.

Foundation from sibling t717_1 (now archived): `verifiedstats` already has the 4-bucket shape with `prev_month` and the rollover ladder. `previous_calendar_month()` helper, `PREV_MONTH` global, and the rollover jq pattern are reusable. The natural moment to extract the remote-aware push/retry block into a shared lib is now (two callers will exist).

## Verification result (verify path, 2026-04-30)

The pre-existing plan in `aiplans/p717/p717_2_usagestats_live_hook.md` was checked against the current codebase. Findings:

- `.aitask-scripts/aitask_verified_update.sh` — all helpers the plan proposes to extract still exist as standalone functions (`MAX_REMOTE_RETRIES` line 11, `previous_calendar_month` 97-104, `has_remote_tracking` 300-303, `current_task_branch` 305-312, `current_task_remote` 314-316, `configure_clone_identity` 318-332, `run_before_push_hook` 334-345, `is_retryable_push_error` 347-350, `sync_current_repo_from_remote` 352-354, `commit_metadata_update_local` 286-298, `commit_and_push_from_remote_clone` 356-408, `commit_metadata_update` 410-441). `update_model_file` signature is `(models_file, model_name, skill_name, raw_score)` — 4 positional args. Called from `commit_and_push_from_remote_clone` at line 377 with `"$SCORE"` as the 4th arg.
- `tests/test_verified_update.sh` — 18 tests; tests 14-18 cover prev_month migration/rollover (from t717_1). Fixture pattern: `setup_repo()` lines 58-74 with `mktemp -d`, fake `ait` wrapper, fake `aitasks/metadata/models_claudecode.json`. `json_get()` jq helper.
- `.aitask-scripts/lib/` — `verified_update_lib.sh` does NOT yet exist. Other libs: `terminal_compat.sh`, `task_utils.sh`, `archive_utils.sh`, plus Python utils.
- `.claude/skills/task-workflow/satisfaction-feedback.md` — starts with Step 1 (no Step 0). `feedback_collected` guard pattern at line 10 is the model: "If `feedback_collected` is `true`, skip this procedure entirely. Otherwise, set `feedback_collected` to `true` before proceeding."
- `.claude/skills/task-workflow/SKILL.md` — Context Requirements table contains `feedback_collected` (line 24) and `detected_agent_string` (line 25). `usage_collected` does NOT exist.
- Whitelist files — entries for `aitask_verified_update.sh` exist in all 5 touchpoints. **CLAUDE.md docs are wrong:** the gemini whitelist table at line 89 says `[[rules]]` block, but the actual files (`.gemini/policies/aitasks-whitelist.toml` line 351, `seed/geminicli_policies/aitasks-whitelist.toml` line 325) use `[[rule]]` (singular). The runtime is correct; the doc is wrong. Fix CLAUDE.md as part of this task (Step 5b below).
- `aitasks/metadata/models_claudecode.json` — verified pick block now shows `all_time / prev_month / month / week` post-t717_1.

Conclusion: plan is sound. Implementation proceeds per the canonical plan below. The only adjustment is being explicit about the callback signature (the lib forwards a 5th positional arg through the call chain for the verified-only score; usage caller passes empty string).

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

### 1. Extract shared lib `.aitask-scripts/lib/verified_update_lib.sh`

- Header:
  ```bash
  #!/usr/bin/env bash
  [[ -n "${_AIT_VERIFIED_UPDATE_LIB_LOADED:-}" ]] && return 0
  _AIT_VERIFIED_UPDATE_LIB_LOADED=1
  ```
  No `set -euo pipefail` (caller decides).
- Move from `aitask_verified_update.sh` into the lib (and delete from caller):
  - `MAX_REMOTE_RETRIES=5`
  - `previous_calendar_month()`
  - `has_remote_tracking()`
  - `current_task_branch()`
  - `current_task_remote()`
  - `configure_clone_identity()`
  - `run_before_push_hook()`
  - `is_retryable_push_error()`
  - `sync_current_repo_from_remote()`
  - `commit_metadata_update_local()`
  - `commit_and_push_from_remote_clone()` — generalized: replace the literal `update_model_file ... "$SCORE"` call with an indirect callback. The lib reads `_AIT_UPDATE_MODEL_FILE_FN` (function name) and the caller-supplied "extra" arg.
  - `commit_metadata_update()` — extended signature: `commit_metadata_update <models_file> <agent_string> <skill_name> <parsed_model> [extra]` where `[extra]` is forwarded to the callback as `$4`. Verified caller passes `$SCORE`; usage caller passes empty string (or omits).
  - Commit message inside `commit_metadata_update_local` and `commit_and_push_from_remote_clone` reads `_AIT_COMMIT_PREFIX` (caller sets, e.g. `"ait: Update verified score"` or `"ait: Update usage count"`). Message template: `${_AIT_COMMIT_PREFIX} for ${agent_string} ${skill_name}`.
- The lib does NOT contain `update_model_file` — that is jq logic specific to each caller and stays in the caller script.

### 2. Refactor `aitask_verified_update.sh` (no behavior change)

- After existing `terminal_compat.sh` / `task_utils.sh` sources, add:
  ```bash
  source "$SCRIPT_DIR/lib/verified_update_lib.sh"
  ```
- Delete the moved helpers from the script body.
- Before invoking `commit_metadata_update`, set:
  ```bash
  _AIT_UPDATE_MODEL_FILE_FN=update_model_file
  _AIT_COMMIT_PREFIX="ait: Update verified score"
  ```
- Update the call site to pass the extra arg explicitly:
  ```bash
  new_score="$(commit_metadata_update "$models_file" "$AGENT_STRING" "$SKILL_NAME" "$PARSED_MODEL" "$SCORE")"
  ```
  (Previously `$SCORE` was a global read by the lambda; now it is forwarded explicitly so the lib can run without script-globals.)
- The local-only branch (when no remote) also needs to forward `$SCORE` to `update_model_file` directly — that call site already passes 4 args, no change.
- Run `bash tests/test_verified_update.sh` to confirm all 18 tests still pass (refactor is a no-op).

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

# show_help / require_jq / log_info / run_git_quiet / parse_agent_string /
# resolve_date_periods / parse_args / models_file_for_agent / ensure_model_exists
# — copy from aitask_verified_update.sh and strip every reference to --score / SCORE.

update_model_file() {
    # Caller signature from the lib forwards 4 args; we ignore $4 (raw_score) here.
    local models_file="$1"
    local model_name="$2"
    local skill_name="$3"
    # $4 is unused (passed by the lib for the verified-update callback).

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
    resolve_date_periods   # already sets PREV_MONTH inside (per t717_1)

    local models_file
    models_file="$(models_file_for_agent "$PARSED_AGENT")"
    [[ -f "$models_file" ]] || die "Model config not found: $models_file"

    ensure_model_exists "$models_file" "$PARSED_MODEL"

    _AIT_UPDATE_MODEL_FILE_FN=update_model_file
    _AIT_COMMIT_PREFIX="ait: Update usage count"

    local new_runs
    if has_remote_tracking; then
        new_runs="$(commit_metadata_update "$models_file" "$AGENT_STRING" "$SKILL_NAME" "$PARSED_MODEL" "")"
    else
        if [[ "$SILENT" == "false" ]]; then
            warn "No remote configured for task data; using local-only usage update without concurrency protection."
        fi
        new_runs="$(update_model_file "$models_file" "$PARSED_MODEL" "$SKILL_NAME" "")"
        commit_metadata_update_local "$models_file" "$AGENT_STRING" "$SKILL_NAME"
    fi

    if [[ "$SILENT" == "false" ]]; then
        success "Updated ${AGENT_STRING} ${SKILL_NAME} usage count to ${new_runs}"
    fi
    echo "UPDATED:${AGENT_STRING}:${SKILL_NAME}:${new_runs}"
}

main "$@"
```

CLI surface: `--agent-string`, `--agent`, `--cli-id`, `--skill`, `--date`, `--silent`. **No `--score`** flag, even for compatibility — fail with a usage error if seen.

### 4. Wire the satisfaction-feedback hook

Edit `.claude/skills/task-workflow/satisfaction-feedback.md`:

- Insert a new `## Step 0 — Record usage` section BEFORE the existing `## Step 1` (and before the existing early-out for `enableFeedbackQuestions=false`). Critical placement: usage is unconditional — must run regardless of `enableFeedbackQuestions`. The existing `feedback_collected` guard remains for Step 1+ unchanged.
- Step 0 body:
  - Guard: if `usage_collected` is `true`, skip Step 0. Otherwise set `usage_collected = true` before proceeding (set-before-call so a failure mid-procedure does not cause a retry double-bump).
  - Resolve agent string: if `detected_agent_string` is non-null, reuse it. Else execute the **Model Self-Detection Sub-Procedure** (`model-self-detection.md`) and store the result in `detected_agent_string`.
  - Invoke:
    ```bash
    ./.aitask-scripts/aitask_usage_update.sh \
        --agent-string "<agent_string>" \
        --skill "<skill_name>" \
        --silent
    ```
  - On success (`UPDATED:...` line): continue.
  - On failure: warn the user "usage update failed: <error>" and continue. Do NOT abort the workflow — usage tracking is best-effort.
- Add `usage_collected` to `.claude/skills/task-workflow/SKILL.md` Context Requirements table, between `feedback_collected` and `detected_agent_string`:
  ```
  | `usage_collected` | boolean | Guard flag — initialized to `false`. Set to `true` before the usage bump fires. Prevents double execution across workflow paths. |
  ```

### 5. 5-touchpoint whitelist

Mirror the existing `aitask_verified_update.sh` entries. Use the in-file convention (gemini files use `[[rule]]` singular).

- `.claude/settings.local.json` — append to `permissions.allow`:
  ```json
  "Bash(./.aitask-scripts/aitask_usage_update.sh:*)"
  ```
- `.gemini/policies/aitasks-whitelist.toml` — append a new block (mirror format on lines 351-357):
  ```toml
  [[rule]]
  toolName = "run_shell_command"
  commandPrefix = "./.aitask-scripts/aitask_usage_update.sh"
  decision = "allow"
  priority = 100
  ```
- `seed/claude_settings.local.json` — same `Bash(...)` permission entry.
- `seed/geminicli_policies/aitasks-whitelist.toml` — same `[[rule]]` block.
- `seed/opencode_config.seed.json` — append:
  ```json
  "./.aitask-scripts/aitask_usage_update.sh *": "allow"
  ```

Codex (`.codex/config.toml`, `seed/codex_config.seed.toml`) is excluded per CLAUDE.md (prompt/forbidden-only model).

### 5b. Fix CLAUDE.md gemini whitelist doc

In `CLAUDE.md` "Adding a New Helper Script" section (around line 89), the gemini row in the touchpoint table is wrong: it says `[[rules]]` but the actual TOML files use `[[rule]]`. Update both gemini rows to match runtime:

```diff
- | `.gemini/policies/aitasks-whitelist.toml` | `[[rules]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"` |
+ | `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"`, `decision = "allow"`, `priority = 100` |
```

(The seed row reads "mirror of runtime Gemini policy" — no change needed since it just refers to the runtime row, but the runtime row above is now correct.)

### 6. Tests — `tests/test_usage_update.sh`

Mirror the fixture pattern from `tests/test_verified_update.sh`'s `setup_repo()`:
- mktemp dir, `git init --quiet`, fake `ait` wrapper, copy script + libs, seed `aitasks/metadata/models_claudecode.json`.
- `json_get()` jq helper.

Test cases:

1. **Fresh model, no usagestats key** — Run `--agent-string claudecode/opus4_7 --skill pick`. Assert: `usagestats.pick = { all_time:{runs:1}, prev_month:{period:"", runs:0}, month:{period:CURRENT, runs:1}, week:{period:CURRENT, runs:1} }`.
2. **Same-month bump** — Pre-seed `usagestats.pick.month = {period:CURRENT, runs:3, ... full block}`. Run with same date. Assert `month.runs=4`, `prev_month` untouched.
3. **One-month rollover** — Pre-seed `month.period=2026-04, runs=5`, `prev_month.period=""`. Run `--date 2026-05-01`. Assert `prev_month={period:"2026-04", runs:5}`, `month={period:"2026-05", runs:1}`.
4. **Multi-month skip** — Pre-seed `month.period=2026-02, runs=3`, `prev_month={period:"2026-01", runs:1}`. Run `--date 2026-05-01`. Assert `prev_month={period:"", runs:0}`, `month={period:"2026-05", runs:1}`.
5. **Two skills accumulate independently** — Run `--skill pick`, then `--skill explore`. Assert both blocks present, each with runs=1, neither clobbers the other.
6. **Verified data untouched** — Pre-seed `verifiedstats.pick={...}` and flat `verified.pick=80`. Run usage script. Assert `verifiedstats` byte-equal before/after; `verified.pick` unchanged.
7. **Agent-not-found** — Run with `--agent-string fake/whatever`. Assert non-zero exit and helpful error.
8. **Model-not-found** — Run with `--agent-string claudecode/nonexistent`. Assert non-zero exit.
9. **--score flag rejected** — Run with `--score 5`. Assert non-zero exit (no silent acceptance).

### 7. Sanity: existing verified tests still pass

After step 1+2, run `bash tests/test_verified_update.sh` — all 18 tests must pass (lib extraction is no-op).

## Verification

```bash
bash tests/test_verified_update.sh         # 18/18 pass
bash tests/test_usage_update.sh            # new tests pass
shellcheck .aitask-scripts/aitask_verified_update.sh \
           .aitask-scripts/aitask_usage_update.sh \
           .aitask-scripts/lib/verified_update_lib.sh
```

End-to-end smoke: pick a small task, exit cleanly through Step 8 → satisfaction-feedback. Confirm:
- `models_claudecode.json` `usagestats.pick.month.runs` incremented.
- If user picks "Skip" on the score prompt, `verifiedstats.pick.month.runs` unchanged but `usagestats` still incremented.
- If user picks a score, both bumped.

Whitelist confirm: from a fresh shell, run `./.aitask-scripts/aitask_usage_update.sh --help` via Claude Code — no permission prompt.

## Out of scope

- Picker UX changes (recent-window aggregation) — t717_3.
- Stats TUI window selector + usage pane — t717_4.
- Manual verification — t717_5.
- Verify-path model-detection dedup — t717_6.

## Notes for sibling tasks

- `usagestats[skill][bucket].runs` is the data source for picker `_build_top_usage` (t717_3) and stats TUI `load_usage_rankings` (t717_4). Both will sum `month.runs + prev_month.runs` for the recent window.
- `verified_update_lib.sh` is a useful integration point for any future model-file mutator (e.g., separate "agent feedback notes" updater). Keep its callback signature stable: `(models_file, model_name, skill_name, extra)`.
- The CLAUDE.md gemini-row doc fix is folded into this task (see Step 5b) — no need to surface as a separate defect.

## Step 9: Post-Implementation

Standard archival via `./.aitask-scripts/aitask_archive.sh 717_2`. Folded tasks: none.
