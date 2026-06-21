---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [brainstorming, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
anchor: 1020
created_at: 2026-06-21 14:53
updated_at: 2026-06-21 18:32
---

## Origin

Spawned from t1020 during Step 8b review — split out per the explicit scope
decision recorded in t1020 AC #4.

## Upstream defect

`.aitask-scripts/brainstorm/brainstorm_cli.py:134` — the crew-aggregate
`_crew_status.yaml` roll-up stays stale: it can read `Running` / `80` while the
only agent in the crew is `Completed` / `100`. It is written by the crew runner
and `cmd_archive` (which only flips it to `Completed` at archive time), a
separate subsystem from the brainstorm **operation** lifecycle that t1020 fixed
(`br_groups.yaml` group status). The staleness affects all operation types, not
just comparators.

## Diagnostic context

Observed live in `crew-brainstorm-1017` while diagnosing t1020: with the sole
comparator agent at `Completed` / `100`, `_crew_status.yaml` remained
`Running` / `80`. t1020 fixed the operation-group `Waiting → Completed`
transition (the TUI never polled the comparator) but deliberately did NOT touch
the crew-aggregate roll-up — the task framed the runner "stopping" as a red
herring for the operation-level bug. See t1020 / `p1020` Final Implementation
Notes ("Upstream defects identified").

## Suggested fix

Investigate where the crew runner writes `_crew_status.yaml` (progress/status
aggregate) and ensure the aggregate recomputes to `Completed` / `100` once every
member agent has reached a terminal `Completed` state, rather than only being
finalized by `cmd_archive`. Decide whether the roll-up should be derived
on-read from member `*_status.yaml` files instead of separately persisted.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-21T15:32:55Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-21T15:32:57Z status=pass attempt=1 type=machine
