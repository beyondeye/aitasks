---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1159
followup_kind: risk_mitigation
created_at: 2026-08-16 18:28
updated_at: 2026-08-16 18:28
---

## Origin

Risk-mitigation ("after") follow-up for t1525, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement risk 1 (a drain constant tuned to one Codex build will rot):

> `COMPOSER_DRAIN_SECONDS = 0.5` is tuned against codex-cli 0.146.0 at n=2. A UI
> or input-handling change in a later Codex makes it wrong again — the same class
> of failure this task is fixing. The verifier converts that from a silent hold
> into a visible auto-disarm, but the constant itself remains the load-bearing
> part.

(The shipped constant was ultimately sized by a 150-repetition sweep across all
three shadow agents — see `## Measurement` in
`aiplans/archived/p1525_fix_failed_verification_t1523_item4.md` — but the point
of the risk stands: it is a wall-clock constant pinned to one release of each
CLI, and it will rot.)

## Goal

Deliver the recheck prompt as a **bracketed paste** instead of a literal
keystroke burst followed by a timed Enter, so the Enter becomes structurally
incapable of being read as text and the timed drain stops being the load-bearing
mechanism.

Sketch: `tmux set-buffer -b <name> -- <text>` then
`paste-buffer -b <name> -d -p -t <pane>`. With `-p`, tmux wraps the payload in
`ESC[200~ … ESC[201~` **only if the pane's application has enabled DECSET 2004**
— which crossterm/ratatui apps (Codex) do, since that is how they handle
multi-line pastes. The app then receives a paste *event* rather than keys, after
which a separate `send-keys Enter` is unambiguous. If the app has not enabled
bracketed paste, tmux sends the payload raw, i.e. it degrades to exactly today's
behaviour rather than breaking.

## Required work

1. Add the paste path behind the existing delivery seam in
   `minimonitor_app._submit_shadow_prompt`; go through the tmux gateway
   (`lib/tmux_exec.py`), never raw `tmux` — `tests/test_no_raw_tmux.sh` enforces
   this. The repo already shells out to a buffer verb (`load-buffer -w -`), so
   the pattern exists.
2. **Measure it per shadow agent**, reusing t1525's harness
   (`measure_drain.py`, method and acceptance criterion recorded in that plan's
   `## Measurement`): does the paste submit reliably at drain 0, and — the
   specific risk — does Codex collapse a bracketed paste into a
   `[Pasted N chars]` chip? A chip changes what the composer *displays*, which
   would break the `SHADOW_BUSY` pre-Enter gate that t1525's delivery
   authorises on, even though the agent receives the right text.
3. Decide from that measurement whether the drain can be reduced/retired or must
   stay as the fallback for agents without DECSET 2004.

## Non-goals

Do not weaken t1525's post-Enter verification. The verifier is what makes a
future rot *visible*; this task changes the delivery mechanism, not the check.

## Related

- t1525 (the fix this mitigates), t1530 (its manual verification)
- t1524 (surface a never-settling shadow — the other half of "make rot visible")
- Safety contract items 7 and 9 in `aidocs/framework/shadow_agent.md`
