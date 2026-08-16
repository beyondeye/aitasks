---
priority: medium
effort: medium
depends: [1509]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1509]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-14 16:21
updated_at: 2026-08-16 10:25
completed_at: 2026-08-16 10:25
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1509

## Verification Checklist

- [x] Launch a Claude Code agent under `ait`, press `e` in minimonitor to spawn a shadow, and confirm the shadow pane runs Codex (not Claude) — this is the pairing t1509 exists to unblock. — PASS 2026-08-16 10:24
- [x] Press `L` to arm the auto-recheck loop with that Codex shadow. It must ARM (banner shows "auto-recheck ARMED"). Before t1509 this refused with "shadow agent 'node' has no readiness detection yet". — PASS 2026-08-16 10:21 auto: real action_toggle_review_loop against a LIVE codex pane (pane_current_command='node', pid 222316) -- ARMED, banner '⟳ auto-recheck ARMED', no refusal
- [x] Confirm the arm was NOT refused with "could not resolve the shadow's agent yet". If it is, press `L` again after a few seconds — resolution is retried on a backoff — and note how many attempts were needed. — PASS 2026-08-16 10:21 auto: fresh-launch measurement -- codex child visible to pgrep at +0.13s; real agent_key_from_pane resolved 'codex' on attempt #1; no 'could not resolve' refusal
- [fail] Let the followed Claude agent produce output and settle at a prompt. Observe ONE automatic recheck fire: the Codex shadow receives a single-line "refetch and recheck round N" prompt plus Enter. — FAIL 2026-08-16 10:21 follow-up t1525
- [x] Confirm NOTHING is injected while the Codex shadow is mid-output (its "Working (Ns · esc to interrupt)" bullet is visible). Watch across at least one full shadow response. — PASS 2026-08-16 10:21 auto: 28 consecutive live WORKING captures over a full 7.1s codex response replayed through the real controller -- 0 keys sent; positive control (settled tail) fires, so the probe discriminates
- [x] Confirm NOTHING is injected while the Codex shadow is parked at a permission dialog or a question widget. If convenient, get the shadow to ask for approval and leave it parked for ~30s. — PASS 2026-08-16 10:21 auto: parked at a REAL codex permission dialog for 40.6s (161 captures) -- shadow_state=dialog every tick, 0 keys sent
- [x] Confirm nothing is injected for at least SHADOW_SETTLE_SECONDS (2s) after you answer a Codex dialog in the shadow — the post-interaction settle latch. — PASS 2026-08-16 10:21 auto: after answering a live codex dialog, raw readiness returned at +0.51s but the latch held injection until +2.03s (hold 2.04s >= SHADOW_SETTLE_SECONDS 2.0) -- latch demonstrably load-bearing
- [x] Answer a Codex dialog in the shadow in a way that produces NO follow-up work (e.g. "No, tell Codex what to do differently", or Esc). The loop must NOT wedge: it must become able to fire again once the settle deadline passes. — PASS 2026-08-16 10:21 auto: Esc answer produced no follow-up work (conversation interrupted, no WORKING state after) yet the latch released at +2.03s and the loop became fireable again -- no wedge
- [x] Restart minimonitor with a non-default refresh (`ait minimonitor --interval 1`) and repeat the settle check — the hold is wall-clock, so it must last the same ~2s rather than shrinking with the faster tick. — PASS 2026-08-16 10:21 auto: same live captures replayed at the evidence cadence of each refresh -- hold 2.04s at --interval 1 (1.0s cadence) and 3.05s at default (1.5s cadence); never below 2.0s. Method: cadence replay, not a literal TUI restart
- [x] Confirm the followed pane NEVER receives any injected keys throughout (safety contract item 1). — PASS 2026-08-16 10:21 auto: across arm/fire/hold/disarm probes the followed pane %1 never appears in any send_keys call; the single fire delivered both keys to the shadow pane only
- [x] Negative control: switch the shadow to OpenCode and press `L`. Arming must REFUSE with a message naming 'opencode' and "no readiness detection yet". — PASS 2026-08-16 10:21 auto: LIVE opencode pane (pane_current_command='opencode') -- arm REFUSED with "Auto-recheck unavailable: shadow agent 'opencode' has no readiness detection yet"; armed=False
- [x] Kill the shadow pane while the loop is armed and confirm the loop auto-disarms visibly (verified absence), rather than hanging armed. — PASS 2026-08-16 10:21 auto: armed against a live codex pane bound via @aitask_shadow_target, killed the pane, next tick auto-disarmed visibly -- banner cleared + warning toast 'Auto-recheck loop disarmed: followed agent or shadow pane is gone'
