---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [sitrep, tui, tmux]
gates: [risk_evaluated]
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-16 09:38
updated_at: 2026-11-16 09:38
---

## Origin

Risk-mitigation ("after") follow-up for t2309, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — write-side one-round-trip mode residual left open by scope

- The write-side one-round-trip mode residual stays open by scope decision. Closing it needs the paste transport plus t1525's live drain sweep. · severity: low · → mitigation: guarded_prompt_write_for_shadow

## Goal

t2309 made the minimonitor shadow recheck's **Enter** a guarded, acked dispatch
(`monitor_core.guarded_send_key`, bound to the shadow `RunIdentity` that
`_fire_shadow_recheck` now reads before the write). The literal **prompt write** is
still a plain `monitor.send_keys(shadow_pane, prompt, literal=True)`, so a tmux mode
entered in the one round trip between the pre-write `query_pane_mode` read and that
write is still not closed (`aidocs/framework/shadow_agent.md` item 9, "Accepted
residual (the write only)").

- Move the write in `_fire_shadow_recheck` (`.aitask-scripts/monitor/minimonitor_app.py`)
  to `monitor_core.guarded_paste_text(monitor, identity, prompt, nonce)`. This is the
  sitrep path's phase-2 transport: the text goes via stdin into a named buffer, and one
  `if-shell` with the identity + not-in-mode condition does the paste, acked by a nonce.
  Map its answers onto the loop's codes the way t2309 mapped the Enter:
  `skipped:in_mode` → `HOLD_SHADOW_IN_MODE` (nothing written);
  `skipped:identity_changed` → a disarm; `unknown` → decide (the paste may have landed);
  `failed` → `DISARM_PROMPT_WRITE_FAILED`.
- **Re-run t1525's live drain sweep.** `review_loop.COMPOSER_DRAIN_SECONDS` was measured
  against `send-keys -l` followed by Enter, over every agent in `SHADOW_READY_DETECTORS`
  (claude, codex, opencode). `paste-buffer` delivers differently: codex in particular
  coalesces input bursts. Re-measure that the Enter after a paste is not consumed as text,
  and that `composer_payload` / `payload_matches` still prove a pasted prompt at shadow
  widths 60 and 44. Record the measurements.
- Update `tests/test_submit_labels_pinned.py`, `tests/test_minimonitor_concern_action.py`
  (the `_LoopFakeMon` literal-write model), the live smoke in
  `tests/test_minimonitor_concern_smoke.py`, and `shadow_agent.md` items 7 and 9.
