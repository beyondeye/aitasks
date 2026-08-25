---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [reporting, tui, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1544
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-24 22:51
updated_at: 2026-08-25 11:04
completed_at: 2026-08-25 11:04
---

## Origin

Spawned from t1544_6 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_stats.py:471 — the backlog footnote prints "~0.3%" as a hardcoded literal, a frozen t1544_3 sample with no maintained metric behind it; stats/panes/backlog.py mirrors the line verbatim and t1544_5's CLI-parity test pins the pair, so changing it is a coupled code+test edit. Out of scope for a docs task. t1544_8 (retrospective) carries the same figure.`
- `aitasks/metadata/stats_config.json — pins five of the seven presets (sessions and backlog are absent). Harmless today because deep_merge merges the presets dict per key, so the code-only presets still appear; but the parent task's scope asked for both sites to be updated, and t1544_5 deliberately left the JSON alone (its Deliverable 3 required no config change). Recorded because the divergence is now documented behaviour rather than a silent inconsistency.`

## Diagnostic context

t1544_6 documented the two completion clocks the backlog sections use. The task
text asked the docs to state that the clocks "can name a different week for
~0.3% of tasks". Verification showed that figure is **not** computed: it is a
literal in the footnote string at `aitask_stats.py:471`, taken from a one-time
t1544_3 measurement (26 of ~1828 archived tasks differ by a day, 6 by a week
bucket — the 0.3% is the by-week figure). It drifts with every task added or
metadata repair, and nothing recomputes or guards it.

The docs therefore deliberately omit the percentage and state the behavioural
invariant instead (the two clocks agree on *whether* a task completed and can
disagree on *which week*). That leaves the rendered CLI and TUI output as the
only surfaces still asserting a stale number to users.

The second defect was found while correcting the claim that presets are defined
in `aitasks/metadata/stats_config.json`. They are defined in
`.aitask-scripts/stats/stats_config.py::DEFAULT_PRESETS`; the JSON is an
override layer that currently pins five of the seven presets.

## Suggested fix

For the footnote: either drop the percentage from the rendered string (keeping
the invariant sentence, matching what the docs now say), or compute it from the
data already collected. Note the coupling — `stats/panes/backlog.py`'s
diagnostic line is asserted equal to the CLI footnote by a t1544_5 parity test,
so both sites and the test move together.

For `stats_config.json`: decide whether the shipped JSON should mirror
`DEFAULT_PRESETS` at all. Since `deep_merge` merges the `presets` dict per key,
the file is only needed to *override*; shipping a partial copy of the code
defaults invites exactly this drift. Removing the redundant entries may be
better than completing them.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T07:16:30Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-25T07:26:25Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-25T08:04:08Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:d2b61113fbd5202d

> **✅ gate:risk_evaluated** run=2026-08-25T08:04:08Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1590/risk_evaluated_2026-08-25T08:04:08Z-risk_evaluated-a1.log`
