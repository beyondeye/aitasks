---
Task: t717_1_verifiedstats_prev_month_schema.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Sibling Tasks: aitasks/t717/t717_2_usagestats_live_hook.md, aitasks/t717/t717_3_agent_picker_recent_modes.md, aitasks/t717/t717_4_stats_tui_window_selector_usage_pane.md
Archived Sibling Plans: aiplans/archived/p717/p717_*_*.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 10:21
---

# t717_1 — verifiedstats: add prev_month bucket + rollover

## Context

Today `verifiedstats[skill]` has buckets `all_time`, `month`, `week`. The `month` bucket is overwritten when the calendar rolls over, losing the previous month's data and making it impossible to display a stable "current + last calendar month" recent window. Sibling tasks t717_3 (agent picker recent-mode) and t717_4 (stats TUI window selector) need that recent window. This task adds a `prev_month` bucket and a rollover rule that copies `month` → `prev_month` before reset, so the previous calendar month's totals are preserved.

This is the foundational schema change — t717_2 (usagestats) mirrors the same rollover logic on a parallel block; t717_3 and t717_4 consume the new bucket downstream.

## Verification result (verify path, 2026-04-30)

The pre-existing plan in `aiplans/p717/p717_1_verifiedstats_prev_month_schema.md` was checked against the current codebase:

- `.aitask-scripts/aitask_verified_update.sh` — `update_model_file()` jq pipeline at lines 197-254 matches the plan's reference exactly (3-bucket: all_time, month, week, with the existing migration ladder). `resolve_date_periods()` at line 96 confirmed.
- `tests/test_verified_update.sh` — 13 existing tests; plan's 5 new test cases extend cleanly without duplication. Existing Test 11 ("Month rollover resets month but keeps all-time") asserts month is reset but does NOT assert prev_month behavior — that gap is what t717_1 fills.
- `agent_model_picker.py:68` `_format_op_stats()` — uses defensive `.get(...)` for `month`; tolerates missing `prev_month`. No changes needed in this task.
- `stats/stats_data.py:234` `load_verified_rankings()` — uses defensive `.get(...)` for `month`/`week`; no changes needed in this task.

Conclusion: plan is sound, no updates required. Implementation proceeds per the canonical plan.

## Schema after this task

```json
"verifiedstats": {
  "<skill>": {
    "all_time":   { "runs": N, "score_sum": S },
    "prev_month": { "period": "YYYY-MM", "runs": N, "score_sum": S },
    "month":      { "period": "YYYY-MM", "runs": N, "score_sum": S },
    "week":       { "period": "YYYY-Www", "runs": N, "score_sum": S }
  }
}
```

## Implementation

### 1. `previous_calendar_month()` helper

Add a portable bash helper near `resolve_date_periods()` in `.aitask-scripts/aitask_verified_update.sh`:

```bash
previous_calendar_month() {
    local current_month="$1"  # YYYY-MM
    if date --version >/dev/null 2>&1; then
        date -d "${current_month}-01 -1 month" "+%Y-%m"
    else
        date -j -v-1m -f "%Y-%m-%d" "${current_month}-01" "+%Y-%m"
    fi
}
```

Set a new global `PREV_MONTH` after `resolve_date_periods()` returns:

```bash
PREV_MONTH="$(previous_calendar_month "$CURRENT_MONTH")"
```

### 2. Extend `update_model_file()` jq pipeline

Pass the new period as an arg:

```bash
jq \
    --arg model "$model_name" \
    --arg skill "$skill_name" \
    --argjson mapped_score "$mapped_score" \
    --arg current_month "$CURRENT_MONTH" \
    --arg current_week "$CURRENT_WEEK" \
    --arg prev_month_target "$PREV_MONTH" \
    '
```

Replace the inner bucket-resolution `if/elif/else` ladder with one that always materializes a 4-bucket base:

```jq
.verifiedstats[$skill] as $existing |
(
    if ($existing | type) == "object" and ($existing | has("runs")) and ($existing | has("all_time") | not) then
        # Legacy flat — migrate
        {
            "all_time":   {"runs": $existing.runs, "score_sum": $existing.score_sum},
            "prev_month": {"period": "", "runs": 0, "score_sum": 0},
            "month":      {"period": $current_month, "runs": 0, "score_sum": 0},
            "week":       {"period": $current_week,  "runs": 0, "score_sum": 0}
        }
    elif ($existing | type) == "object" and ($existing | has("all_time")) then
        # Bucketed — ensure prev_month exists
        $existing
        | (.prev_month //= {"period": "", "runs": 0, "score_sum": 0})
    else
        # Fresh
        {
            "all_time":   {"runs": 0, "score_sum": 0},
            "prev_month": {"period": "", "runs": 0, "score_sum": 0},
            "month":      {"period": $current_month, "runs": 0, "score_sum": 0},
            "week":       {"period": $current_week,  "runs": 0, "score_sum": 0}
        }
    end
) as $base |
```

Then the increment + rollover. Compute the new prev_month conditionally:

```jq
($base.all_time.runs + 1) as $at_runs |
($base.all_time.score_sum + $mapped_score) as $at_sum |

# Month rollover decision
(if $base.month.period == $current_month then
    # No rollover — prev_month untouched
    $base.prev_month
 elif $base.month.period == $prev_month_target then
    # One-month rollover — old month becomes prev_month
    $base.month
 else
    # Multi-month skip OR fresh month bucket — zero prev_month
    {"period": "", "runs": 0, "score_sum": 0}
 end) as $pm |

(if $base.month.period == $current_month then ($base.month.runs + 1) else 1 end) as $m_runs |
(if $base.month.period == $current_month then ($base.month.score_sum + $mapped_score) else $mapped_score end) as $m_sum |
(if $base.week.period  == $current_week  then ($base.week.runs + 1)  else 1 end) as $w_runs |
(if $base.week.period  == $current_week  then ($base.week.score_sum + $mapped_score) else $mapped_score end) as $w_sum |

.verifiedstats[$skill] = {
    "all_time":   {"runs": $at_runs, "score_sum": $at_sum},
    "prev_month": $pm,
    "month":      {"period": $current_month, "runs": $m_runs, "score_sum": $m_sum},
    "week":       {"period": $current_week,  "runs": $w_runs, "score_sum": $w_sum}
} |
.verified[$skill] = (($at_sum / $at_runs) | round)
```

The flat `verified[$skill]` aggregate continues to update from `all_time` — unchanged semantics.

### 3. Tests

Extend `tests/test_verified_update.sh` with these new test cases (numbered 14-18, after existing Test 13):

- **Same-month bump with existing prev_month:** seed `month.period=2026-04, runs=2, score_sum=180, prev_month={period:"2026-03", runs:5, score_sum:480}`. Run `--date 2026-04-29 --score 5` → month becomes `{period:"2026-04", runs:3, score_sum:280}`, prev_month untouched.
- **One-month rollover:** seed `month.period=2026-04, runs=5, score_sum=480` and no prev_month (or `prev_month.period=""`). Run `--date 2026-05-01 --score 4` → prev_month becomes `{period:"2026-04", runs:5, score_sum:480}`, month becomes `{period:"2026-05", runs:1, score_sum:80}`.
- **Multi-month skip:** seed `month.period=2026-02, runs=3, score_sum=240, prev_month={period:"2026-01", runs:2, score_sum:160}`. Run `--date 2026-05-01 --score 5` → prev_month becomes `{period:"", runs:0, score_sum:0}` (because Feb is older than April = current-1), month becomes `{period:"2026-05", runs:1, score_sum:100}`.
- **Migration from flat:** seed `verifiedstats.pick={runs:10, score_sum:920}`. Run any bump → all_time captures original 10+1, prev_month is `{period:"", runs:0, score_sum:0}`, month/week reflect the new bump only.
- **Migration from bucketed-but-no-prev_month:** seed `verifiedstats.pick={all_time:{...}, month:{...}, week:{...}}` (current bucketed but pre-prev_month). Same-month bump → output gains `prev_month={period:"", runs:0, score_sum:0}` and increments all/month/week as expected.

### 4. Verify

```bash
bash tests/test_verified_update.sh                         # all pass (13 existing + 5 new)
shellcheck .aitask-scripts/aitask_verified_update.sh       # clean
```

Manual smoke:
```bash
cp aitasks/metadata/models_claudecode.json /tmp/before.json
./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-05-01 --silent
diff <(jq '.models[] | select(.name=="opus4_6") | .verifiedstats.pick' /tmp/before.json) <(jq '.models[] | select(.name=="opus4_6") | .verifiedstats.pick' aitasks/metadata/models_claudecode.json)
# Restore: ./ait git checkout aitasks/metadata/models_claudecode.json
```

## Out of scope (other children)

- `usagestats` block, the live satisfaction-feedback hook, and the new `aitask_usage_update.sh` script live in t717_2.
- Picker UX changes (new mode, recent-window aggregation) live in t717_3.
- Stats TUI window selector + usage pane lives in t717_4.
- Defensive read-only consumers (`agent_model_picker.py` `_format_op_stats`, `stats_data.py` `load_verified_rankings`) need NO changes here — they use `.get(...)` already and tolerate missing prev_month.

## Notes for sibling tasks

- **`previous_calendar_month()` helper is reusable.** t717_2 needs the exact same logic. Recommend in t717_2 to extract it (and the remote-aware commit/push block) into `.aitask-scripts/lib/verified_update_lib.sh` and source from both scripts. This is the natural moment for the extraction since two callers will exist.
- **The jq rollover ladder is the canonical pattern for usagestats rollover** in t717_2 — same conditions, just remove every reference to `score_sum`.
- **Schema visibility for downstream:** after t717_1 lands and any verified-update fires once, `models_*.json` contains `prev_month`. t717_3 / t717_4 can rely on the field being present; their read paths should still default-handle missing `prev_month` for cold-start models.
