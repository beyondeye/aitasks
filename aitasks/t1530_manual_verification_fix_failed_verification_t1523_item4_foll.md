---
priority: medium
effort: medium
depends: [1525]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1525]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-16 18:27
updated_at: 2026-08-16 18:30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1525

## Verification Checklist

- [ ] Re-run t1523 item #4 verbatim: launch a Claude agent under `ait`, press `e` for a Codex shadow, press `L` to arm, let the followed agent settle at a prompt, and observe ONE automatic recheck fire — the Codex shadow must receive the single-line "refetch and recheck round N" prompt AND have it SUBMITTED (the composer clears and Codex starts working), not left sitting as typed text. This is the exact item that failed and created t1525.
- [ ] After that fire, confirm the loop RE-ARMS: the shadow's re-read re-stamps its analysis, staleness clears, and the banner returns to "auto-recheck ARMED" rather than staying on "recheck #1 sent — waiting for shadow" forever. The old bug's signature was a permanent hold here.
- [ ] Confirm the banner never sits on "⟳ auto-recheck: delivering…" for more than a couple of seconds during a normal fire (the drain plus two verification captures should be well under 2s on a healthy tmux).
- [ ] Repeat one fire with an OpenCode shadow (press `E` to switch the shadow agent) and confirm delivery submits there too — the drain is unconditional and was measured for all three agents, but only Codex's failure was ever reported.
- [ ] Repeat one fire with a Claude shadow and confirm no regression: this pairing worked before t1525 and must still work.
- [ ] Negative control — nothing is injected while the Codex shadow is mid-output: with the loop armed, confirm no keys arrive while the shadow's "Working (Ns · esc to interrupt)" bullet is visible.
- [ ] Negative control — press `L` to DISARM during a delivery (immediately after you see "delivering…"). No Enter may be injected afterwards; if the prompt text is left in the shadow composer, the loop must say so with the "recheck text left in the shadow composer" toast rather than going quiet.
- [ ] Observe whether the "recheck sent, but submission could not be verified" warning ever appears in normal use, and how often. Measurement predicted ~2% (OpenCode only, from a transcript line matching a dialog pattern). If it fires frequently, that is a usability finding for t1524, not a reason to weaken the check — note the shadow agent and what was on screen.
- [ ] Confirm the followed pane NEVER receives any injected keys throughout (safety contract item 1).
