---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: test
status: Done
labels: [scheduling, planning]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1649]
assigned_to: dario-e@beyond-eye.com
anchor: 1569
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-08-30 19:44
updated_at: 2026-08-31 12:50
completed_at: 2026-08-31 12:50
---

## Origin

Risk-mitigation ("after") follow-up for t1569_3, created at Step 8d after implementation landed.

## Risk addressed

From `aiplans/archived/p1569/p1569_3_*.md` `## Risk` → Goal-achievement risk:

- The demotion model and its threshold rest on one corpus snapshot. Demotion
  makes a wrong threshold cost verdict *grading* rather than recall, which bounds
  the damage — but the grading is what t1569_4 blocks on. · severity: medium
- The checker can be entirely correct and still measure ~100% UNCHECKABLE,
  because the in-flight side has no fallback and a task claimed but not yet
  planned blocks every candidate. A reviewer reading the headline rate alone
  will reasonably conclude the design failed; only `CAUSE_RATE:` distinguishes
  the two. · severity: medium

## Goal

Re-run `aitask_parallel_admission.sh replay` at hub thresholds 8/10/20/50 over
the live corpus and record, per threshold:

- the verdict rates (`RATES:`),
- **recall of `CONFLICT ∪ CLEAR_CAVEATED`** — the governing metric, since the
  failure mode of this guard is *letting two agents collide*, not a spurious stop,
- precision of `CONFLICT`,
- the `CAUSE_RATE:` histogram.

Ground truth for recall is the same oracle t1569_3 used: over archived tasks
that have both a plan surface and landed files (`TASKFILES:` from
`aitask_revert_analyze.sh --batch-map`), did the two tasks' actually-landed file
sets intersect?

**Why this is a separate task.** t1569_3 measured one snapshot; the in-flight
population moved twice during that single session (CLEAR 48% → 58% with no code
change), so a single reading cannot settle the threshold. This task establishes
whether 10 is stable or should move, and produces the numbers t1569_4 needs to
decide whether `parallel_admission` can default to `block` instead of `warn`.

Record the result in this task's Final Implementation Notes and reference it from
t1569_4.

## Reference

- `.aitask-scripts/lib/parallel_admission.py` — `HUB_THRESHOLD`, `MAX_CLAIM_AGE_S`
- `aiplans/archived/p1569/p1569_3_shared_parallel_admission_checker.md` — the
  original measurement, its method, and the volatility warning

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-31T08:37:44Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-31T09:33:02Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-31T09:50:31Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:d1cbe24a26fe0f68

> **✅ gate:risk_evaluated** run=2026-08-31T09:50:31Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1643/risk_evaluated_2026-08-31T09:50:31Z-risk_evaluated-a1.log`
