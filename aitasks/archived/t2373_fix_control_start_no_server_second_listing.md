---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [monitor]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-27 01:43
updated_at: 2026-11-27 14:39
completed_at: 2026-11-27 14:39
---

## Origin

Spawned from aitasks_go#t134 (the Go port of the `_ait_control` helper-session
attach into `goengines/tmux`) during its Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py` `TmuxControlClient._start_pass` /
  `_server_is_gone`: after a failed start listing, "no server" is established
  by a SECOND `list-sessions` (`_server_is_gone` runs `run_checked` again). A
  tmux server that comes back between the two calls erases the first call's
  no-server observation, so `lost_project` stays empty after a real outage and
  the supervisor raises no `exit_seen`.

## Diagnostic context

The Go port first mirrored this two-call shape. The t134 reviewer showed it
with a seam: the first subprocess answered "no server", the second returned a
session listing, and the start reported an empty loss reason despite the
observed outage. The Go port now classifies the ONE listing that failed
(`RunChecked`: `Outcome == no_server`) and asks nothing a second time. The
Python side was not reproduced directly; this is the same structure, by
inspection, as of aitasks main 46b34ee2f.

## Suggested fix

Make `_inspect` use `run_checked` and return the no-server outcome alongside
the rows, then drop the second probe in `_server_is_gone` (keep the
"transport is not absence" rule: only tmux's own no-server answer counts).
Add a test with a gateway stub whose first listing says no server and whose
second would succeed.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-27T12:16:30Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-27T12:38:17Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-27T12:39:24Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:17b86ac8929e0f5a

> **✅ gate:risk_evaluated** run=2026-11-27T12:39:24Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2373/risk_evaluated_2026-11-27T12:39:24Z-risk_evaluated-a1.log`
