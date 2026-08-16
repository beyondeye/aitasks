---
priority: medium
effort: medium
depends: [1509]
issue_type: manual_verification
status: Implementing
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
updated_at: 2026-08-16 09:34
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1509

## Verification Checklist

- [ ] Launch a Claude Code agent under `ait`, press `e` in minimonitor to spawn a shadow, and confirm the shadow pane runs Codex (not Claude) — this is the pairing t1509 exists to unblock.
- [ ] Press `L` to arm the auto-recheck loop with that Codex shadow. It must ARM (banner shows "auto-recheck ARMED"). Before t1509 this refused with "shadow agent 'node' has no readiness detection yet".
- [ ] Confirm the arm was NOT refused with "could not resolve the shadow's agent yet". If it is, press `L` again after a few seconds — resolution is retried on a backoff — and note how many attempts were needed.
- [ ] Let the followed Claude agent produce output and settle at a prompt. Observe ONE automatic recheck fire: the Codex shadow receives a single-line "refetch and recheck round N" prompt plus Enter.
- [ ] Confirm NOTHING is injected while the Codex shadow is mid-output (its "Working (Ns · esc to interrupt)" bullet is visible). Watch across at least one full shadow response.
- [ ] Confirm NOTHING is injected while the Codex shadow is parked at a permission dialog or a question widget. If convenient, get the shadow to ask for approval and leave it parked for ~30s.
- [ ] Confirm nothing is injected for at least SHADOW_SETTLE_SECONDS (2s) after you answer a Codex dialog in the shadow — the post-interaction settle latch.
- [ ] Answer a Codex dialog in the shadow in a way that produces NO follow-up work (e.g. "No, tell Codex what to do differently", or Esc). The loop must NOT wedge: it must become able to fire again once the settle deadline passes.
- [ ] Restart minimonitor with a non-default refresh (`ait minimonitor --interval 1`) and repeat the settle check — the hold is wall-clock, so it must last the same ~2s rather than shrinking with the faster tick.
- [ ] Confirm the followed pane NEVER receives any injected keys throughout (safety contract item 1).
- [ ] Negative control: switch the shadow to OpenCode and press `L`. Arming must REFUSE with a message naming 'opencode' and "no readiness detection yet".
- [ ] Kill the shadow pane while the loop is armed and confirm the loop auto-disarms visibly (verified absence), rather than hanging armed.
