---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [monitor, minimonitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-09 16:22
updated_at: 2026-11-09 23:16
completed_at: 2026-11-09 23:16
---

## Origin

Spawned from t2256 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/status_server.py:1238` — `ait monitor --restart-server --version V`
  (`_cmd_restart`) retires V's server and then calls `ensure_server(version=V)`, which
  spawns **this checkout's** `SERVER_SCRIPT` (`status_server.py:134`, argv built at
  `:323`) under V's socket key with `--version V`. Clients of version V accept it,
  because the handshake only compares the version string. They are then served by a
  different release's producer code (prompt patterns, idle detection), which defeats
  the "one server per (tmux server, `VERSION`)" rule. That rule exists precisely
  because prompt patterns change between releases
  (`aidocs/framework/monitor_status_protocol.md` "Scope").

## Diagnostic context

While writing the t2256 troubleshooting docs, the `--version V` advice was traced
through `_cmd_restart` → `ensure_server(version=…)` → `_spawn_server`. The spawned
argv is `[sys.executable, SERVER_SCRIPT, "serve", …, "--version", V, …]`, where
`SERVER_SCRIPT = Path(__file__).resolve()`, i.e. the invoking checkout, whatever its
own `VERSION`. t2256's how-to therefore advises running `ait monitor --restart-server`
**from a project on that version** instead of passing `--version`. The options table in
`website/content/docs/tuis/monitor/reference.md` still advertises "Add `--version V` to
restart the server of another framework version" (text from t2246).

An `ensure` started by a reconnecting client never hits this: it always uses its own
`VERSION`. Only the explicit operator verb can mislabel a server.

## Suggested fix

Either refuse `--version V` when V differs from this checkout's `VERSION` after
retiring nothing (point at running the verb from a project on V), or make it
retire-only for a foreign version: stop V's server and let V's own clients respawn
it from their own files. Then update the reference row and the protocol doc's
"Entry points" table, with a test that a foreign `--version` never spawns this
tree's script under V's key.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-09T20:36:26Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-09T21:13:05Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-09T21:16:23Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:c30241012c6f2e61

> **✅ gate:risk_evaluated** run=2026-11-09T21:16:23Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2262/risk_evaluated_2026-11-09T21:16:23Z-risk_evaluated-a1.log`
