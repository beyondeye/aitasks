---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [tmux, test_infrastructure]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1689
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 14:48
updated_at: 2026-10-26 15:36
---

## Origin

Risk-mitigation ("after") follow-up for t2146, created at Step 8d after implementation landed.

## Risk addressed

macOS live features stay degraded (weak ps token ⇒ unknown).

> On macOS the PID→pane correlation, the agent check and the `live_lock` stderr naming stay unexercised (explicit SKIPs). The suites go green, but macOS live delivery is still degraded in the product. This was accepted by design; the product fix is separate. · severity: low

## Goal

Add a strong macOS identity token kind to `.aitask-scripts/lib/pid_anchor.sh`, so that `lock_holder_liveness` can return `alive` on macOS and the live-holder features work there:
- `ait note --with-live` → `LIVE_PANE`
- sync `live_lock` pane naming
- the `LOCK_LIVE_HOLDER` acquire gate

Background (measured in t2146 on Darwin 24.6):
- Without /proc, the only token today is `ps -o lstart`, which has one-second resolution. `lock_holder_liveness` deliberately refuses to call it `alive`, because a PID can be reused within the same second.
- `sysctl kern.proc.pid.<n>` is an unknown oid in the CLI on Darwin, so there is no pure-shell route.
- `proc_pidinfo(pid, PROC_PIDTBSDINFO=3, 0, buf, 136)` through ctypes (`libproc`) returns `pbi_start_tvsec` / `pbi_start_tvusec` at offset 120 (two uint64), which is microsecond start time. Probed working with the framework venv python.

Design points to settle:
- the new kind name (e.g. `bsdinfo`), recorded as `pid_starttime_kind` next to the token, with the reader re-deriving from the SAME source (the existing rule)
- interpreter cost on the hot path (claim, sync, note) versus a small compiled helper
- backward compatibility with locks already written with `ps` tokens
- the `get_pid_starttime_kind` preference order
- extending `tests/lib/proc_fixtures.sh` `liveness_token_class` with the new strong kind

Then remove the weak-token SKIP branches t2146 added. The new kind would take the strong branch on macOS. Affected: `test_lock_anchor_tmux_live`, `test_live_endpoint_tmux_live`, `test_note_with_live_composition`, `test_sync_holder_pane_live`, `test_lock_live_holder_gate`, `test_sync_protect_paths` (live_lock), `test_crash_recovery_pid_anchor` Test 15.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-26T13:36:43Z status=pass attempt=1 type=human
