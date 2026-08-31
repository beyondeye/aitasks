---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [scheduling, planning]
gates: [risk_evaluated]
anchor: 1569
followup_kind: risk_mitigation
created_at: 2026-08-31 12:49
updated_at: 2026-08-31 12:49
---

## Origin

Risk-mitigation ("after") follow-up for t1643, created at Step 8d after implementation landed.

## Risk addressed

Addresses: one snapshot of the UNCHECKABLE rate cannot support promoting
`parallel_admission` to `block`.

From `aiplans/archived/p1643_threshold_sensitivity_replay.md` `## Risk` →
Goal-achievement risk:

- **The live half stays degenerate.** The excluded run is a counterfactual, not
  an observation: it reports what the checker *would* say if no agent were
  mid-claim. On a busy box the real answer stays `UNCHECKABLE`, which is a fact
  about the fleet, not the threshold. If t1569_4 reads the excluded number as its
  availability figure it will ship `block` on a rate that never occurs.
  · severity: medium

## Goal

Produce a **distribution** of the parallel-admission availability rate as agents
actually experience it, rather than the single reading t1643 recorded.

t1643 measured 113 of 118 candidates `UNCHECKABLE` — driven **entirely** by tasks
claimed but not yet planned (`CAUSE_RATE:no_plan`). Its `--exclude-no-plan`
column is a *counterfactual* ("what if nobody were mid-claim"), deliberately
labelled as such by the paired `RATES_AT:` / `RATES_AT_EXCL:` output. Neither
number answers the question t1569_4 must answer before defaulting
`parallel_admission` to `block`: **how often is a real pick actually decidable?**

That depends on how many agents are mid-claim at the moment of the pick, which
varies through the day and with how many sessions the operator runs. One reading
taken while 2-3 agents were mid-claim cannot characterise it.

Sample repeatedly over days and report the distribution:

```bash
./.aitask-scripts/aitask_parallel_admission.sh replay --candidates auto \
    --from plan --lock-freshness require-fresh --thresholds 10 --exclude-no-plan
```

Each run already emits `SNAPSHOT:<epoch>|<n_inflight>`, `CANDIDATES:<n>|auto`
and `EXCLUDED:<ids>`, so a sample is self-describing and needs no extra
instrumentation — the sampler only has to persist the lines and aggregate them.

Record per sample: the wall-clock time, `n_inflight`, the number of `no_plan`
blockers, and the four verdict counts. Report at minimum the median and the
tail (how often the rate is *worse* than the median), since a guard that is
undecidable a quarter of the time is a very different proposition from one that
is undecidable once a week.

**Deliberately not decided here:** whether the resulting availability justifies
`block`. That remains t1569_4's call — this task supplies the distribution it
needs.

## Reference

- `aiplans/archived/p1643_threshold_sensitivity_replay.md` — the single-snapshot
  measurement, its `## Risk` section, and why the excluded column is a
  counterfactual
- `.aitask-scripts/lib/parallel_admission_collect.py` — `no_plan_claims`,
  the `replay` sweep and its line protocol
- `aitasks/t1569/t1569_4_task_workflow_parallel_admission_preflight.md` —
  `## Coordination — threshold sensitivity (t1643)`
