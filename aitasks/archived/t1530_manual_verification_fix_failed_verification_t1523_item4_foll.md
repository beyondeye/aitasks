---
priority: medium
effort: medium
depends: [1525]
issue_type: manual_verification
status: Done
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
updated_at: 2026-08-16 19:02
completed_at: 2026-08-16 19:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1525

## Verification Checklist

- [x] Re-run t1523 item #4 verbatim: launch a Claude agent under `ait`, press `e` for a Codex shadow, press `L` to arm, let the followed agent settle at a prompt, and observe ONE automatic recheck fire — the Codex shadow must receive the single-line "refetch and recheck round N" prompt AND have it SUBMITTED (the composer clears and Codex starts working), not left sitting as typed text. This is the exact item that failed and created t1525. — PASS 2026-08-16 19:00 auto: live end-to-end -- real claude followed pane + real Codex shadow bound via @aitask_shadow_target, armed through the real action_toggle_review_loop, serviced through the real _service_review_loop; ONE fire, 2 keys to the shadow, prompt SUBMITTED (echoed into the transcript, composer clean, Codex working). 3/3 in the isolated delivery probe too. Negative control at COMPOSER_DRAIN_SECONDS=0 reproduces the t1523 failure.
- [x] After that fire, confirm the loop RE-ARMS: the shadow's re-read re-stamps its analysis, staleness clears, and the banner returns to "auto-recheck ARMED" rather than staying on "recheck #1 sent — waiting for shadow" forever. The old bug's signature was a permanent hold here. — PASS 2026-08-16 19:00 auto: two-sided through real code -- stale read holds FIRED on 'recheck #1 sent' (the old permanent-hold signature), fresh read returns to WAITING with the 'auto-recheck ARMED' banner; reproduced for all 3 shadow agents. Re-stamp leg proven separately: the real aitask_shadow_capture.sh in a real bound shadow pane writes @aitask_shadow_analyzed_at.
- [x] Confirm the banner never sits on "⟳ auto-recheck: delivering…" for more than a couple of seconds during a normal fire (the drain plus two verification captures should be well under 2s on a healthy tmux). — PASS 2026-08-16 19:00 auto: delivery wall-clock 1.009-1.015s across 23 live deliveries (max 1.015s) = 2x COMPOSER_DRAIN_SECONDS plus two captures. Well under the 2s budget.
- [x] Repeat one fire with an OpenCode shadow (press `E` to switch the shadow agent) and confirm delivery submits there too — the drain is unconditional and was measured for all three agents, but only Codex's failure was ever reported. — PASS 2026-08-16 19:01 auto: OpenCode 1.18.18 -- 13 live deliveries (3 + 10) plus a full end-to-end loop fire; all 'sent' with 2 keys and independently confirmed submitted.
- [x] Repeat one fire with a Claude shadow and confirm no regression: this pairing worked before t1525 and must still work. — PASS 2026-08-16 19:01 auto: Claude 2.1.233 -- 3 live deliveries plus a full end-to-end loop fire; all submitted. No regression.
- [x] Negative control — nothing is injected while the Codex shadow is mid-output: with the loop armed, confirm no keys arrive while the shadow's "Working (Ns · esc to interrupt)" bullet is visible. — PASS 2026-08-16 19:01 auto: two live runs -- 6 ticks with the Codex shadow classified working and 17 ticks holding on 'waiting for shadow to settle' injected ZERO keys; each run then fired exactly once when the shadow settled (positive control in the same run).
- [x] Negative control — press `L` to DISARM during a delivery (immediately after you see "delivering…"). No Enter may be injected afterwards; if the prompt text is left in the shadow composer, the loop must say so with the "recheck text left in the shadow composer" toast rather than going quiet. — PASS 2026-08-16 19:01 auto: L pressed 0.35s into the delivery (after the prompt write, inside the drain) -> exactly 1 loop send, NO Enter, and the warning toast 'Auto-recheck loop disarmed: recheck text left in the shadow composer - submit or clear it there manually'. Not silent.
- [x] Observe whether the "recheck sent, but submission could not be verified" warning ever appears in normal use, and how often. Measurement predicted ~2% (OpenCode only, from a transcript line matching a dialog pattern). If it fires frequently, that is a usability finding for t1524, not a reason to weaken the check — note the shadow agent and what was on screen. — PASS 2026-08-16 19:01 auto: 1 warning in 23 live successful deliveries (~4%); OpenCode-only 1/14. The one case read 'dialog' and was GENUINE - the shadow raised a real permission dialog right after a submit that did land. Consistent with the t1525 prediction and mechanism; scratch-sandbox permission prompts inflate it. Data point for t1524; no weakening indicated.
- [x] Confirm the followed pane NEVER receives any injected keys throughout (safety contract item 1). — PASS 2026-08-16 19:01 auto: every send_keys call recorded and tagged loop-vs-user across all 5 end-to-end runs; the loop's send targets were exclusively the shadow pane, followed_got_loop_keys False in every run.
