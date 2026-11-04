---
Task: t2200_fix_codeagent_list_models_bucketed_stats.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t2200 — fix `ait codeagent list-models` STATS line for bucketed verifiedstats

## Context

`cmd_list_models` in `.aitask-scripts/aitask_codeagent.sh` (line ~337) builds the
`STATS:` line with a jq filter written for the old flat `verifiedstats.<op> =
{runs, score_sum}` shape. Every entry is now bucketed (`all_time`, `month`,
`prev_month`, `week`), so `.value.runs` is always null and every model prints
`runs 0, avg 0`. Found during t2194; the file is clean vs HEAD (checked).

No other code parses the `STATS:` line (grep over `.aitask-scripts`, skills,
website, tests: only the producer), so the output format can stay byte-identical
apart from the corrected numbers.

## Scope decision

Show **all-time** stats only (what `runs`/`avg` always meant). No recent window
is added — that would need the date-correct rule in
`lib/model_stats_windows.py` and is not required to fix the defect.

## Steps

1. **`.aitask-scripts/aitask_codeagent.sh` — `cmd_list_models` jq filter.**
   Resolve the bucket per op once, mirroring `lib/stats_data.py` (~l.561):
   `all_time` when present, else the flat object when it carries `runs`, else
   empty. Guard non-object values.

   ```jq
   ((.verifiedstats // {}) | to_entries
     | map(
         (.value | if type == "object"
                   then (if has("all_time") then (.all_time // {})
                         elif has("runs") then . else {} end)
                   else {} end) as $b
         | ($b.runs // 0) as $r
         | "\(.key)(runs \($r), avg \(if $r > 0 then (($b.score_sum // 0) / $r | round) else 0 end))")
     | join(",")) as $stats
   | if $stats == "" then "" else "\nSTATS:\($stats)" end
   ```
   Output format unchanged: `STATS:pick(runs N, avg M),…`.

2. **`tests/test_codeagent.sh` — new test (after Test 4, "Test 4b").**
   Build a second env via `setup_test_env`, overwrite its
   `aitasks/metadata/models_claudecode.json` with a synthetic fixture:
   - `bucketed` — `pick: {all_time:{runs:4,score_sum:380}, month:{period:"2026-11",runs:1,score_sum:100}}`
     → `pick(runs 4, avg 95)` (pins that `all_time`, not `month`, is read)
   - `flat` — `pick: {runs:2, score_sum:150}` → `pick(runs 2, avg 75)` (fallback)
   - `mixed` — `pick` bucketed + `wrap: {runs:1,score_sum:80}` flat → `STATS:pick(runs 4, avg 95),wrap(runs 1, avg 80)`
   - `nostats` — no `verifiedstats` → no STATS line after its MODEL line
   Assert the exact `STATS:` line following each `MODEL:` line (`grep -A1`),
   plus `assert_not_contains` for `runs 0` on the bucketed model. Clean up the env.
   The file has no `( … )`-subshell test bodies, so no counter opt-in is needed.

3. **Negative control:** run the new test against the pre-fix filter (temporarily,
   in the scratch copy only — never `git restore`/stash the tree) to confirm it
   fails with `runs 0`; record the result in Final Implementation Notes.

## Verification

- `bash tests/test_codeagent.sh` — all pass.
- `shellcheck .aitask-scripts/aitask_codeagent.sh`.
- `./ait codeagent list-models claudecode | grep STATS | head -3` shows non-zero
  runs for opus5_5 etc.

Step 9 (Post-Implementation): commit code + test, archive task/plan per workflow.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
