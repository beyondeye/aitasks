---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [gates, cli]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus5
created_at: 2026-07-27 23:27
updated_at: 2026-08-02 10:42
completed_at: 2026-08-02 10:42
boardidx: 220
---

## Problem

`ait gate pass <task-id> <gate>` is dispatched (`ait:320` → `aitask_gate_pass.sh`)
and is the HUMAN's tool for signing an async human gate (t635_15) — but it is
missing from the top-level `show_usage` "Gates:" list (`ait:51-58`), so
`ait --help` never advertises it. The neighbouring `gate append` / `gate fail` /
`gate log` are all listed.

Found while adding `gates sync-registry` to the same usage block (t635_34); left
unfixed there because it is unrelated to that task's surface.

## Fix

Add one line to the "Gates:" section of `show_usage` in `ait`, matching the
block's fixed 15-character verb padding:

```
  gate pass      Sign a human gate (writes the code-bound witness)
```

Place it with the other `gate ` verbs. Note `ait gate --help` (`ait:323`) DOES
already document `pass`; only the top-level usage omits it.

## Verification

- `./ait --help` lists `gate pass` under "Gates:".
- Column alignment matches the surrounding entries.
- `bash tests/test_gate_cli_wiring.sh` still passes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-02T07:33:57Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-02T07:40:03Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-02T07:42:31Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:b7c9a372470fd53d

> **✅ gate:risk_evaluated** run=2026-08-02T07:42:31Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1270/risk_evaluated_2026-08-02T07:42:31Z-risk_evaluated-a1.log`
