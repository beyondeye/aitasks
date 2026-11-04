---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [model_selection, verifiedstats, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2194
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-04 16:06
updated_at: 2026-11-04 18:52
completed_at: 2026-11-04 18:52
---

## Origin

Spawned from t2194 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_codeagent.sh:337` — `ait codeagent list-models` STATS line reads `.value.runs` / `.value.score_sum` (the pre-bucket flat format) instead of `.value.all_time.*`, so every model prints `runs 0, avg 0`.

## Diagnostic context

While t2194 inventoried every reader of the `verifiedstats` buckets (to make the
month / prev_month / week / recent windows date-correct), `cmd_list_models` in
`aitask_codeagent.sh` turned out to read the stats with a jq filter written for
the old flat `{runs, score_sum}` shape:

```
((.verifiedstats // {}) | to_entries | map("\(.key)(runs \(.value.runs // 0), avg …)")
```

Every `verifiedstats.<skill>` entry is now bucketed (`all_time`, `month`,
`prev_month`, `week`), so `.value.runs` is always null. Observed 2026-11-04:

```
MODEL:opus5_5 … VERIFIED:pick=100,changelog=100,wrap=100,explore=100
STATS:pick(runs 0, avg 0),changelog(runs 0, avg 0),wrap(runs 0, avg 0),explore(runs 0, avg 0)
```

t2194 left the file alone: it was out of scope, and at the time another
session held uncommitted hunks in `aitask_codeagent.sh`. Re-check the file is
clean vs HEAD (`git diff --quiet HEAD -- .aitask-scripts/aitask_codeagent.sh`)
before editing.

## Suggested fix

Read `.value.all_time.runs` / `.value.all_time.score_sum`, keeping the flat
`.value.runs` as a fallback for unmigrated entries (stats_data also accepts the
old flat format). If the STATS line should show a recent window too, compute it
date-correctly — the rule lives in `.aitask-scripts/lib/model_stats_windows.py`
(t2194); do not compare slot names. Add a `tests/test_codeagent.sh` case that
pins the STATS line for a bucketed fixture. Note t1912 plans to move these
counters to a plumbing branch and lists this jq reader among the ones its shared
read path must replace.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T16:11:25Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-04T16:50:23Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-04T16:52:46Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:0728baeb8c7151df

> **✅ gate:risk_evaluated** run=2026-11-04T16:52:46Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2200/risk_evaluated_2026-11-04T16:52:46Z-risk_evaluated-a1.log`
