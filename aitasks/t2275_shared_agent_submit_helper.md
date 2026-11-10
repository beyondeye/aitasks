---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [sitrep, tui, tmux]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-10 12:42
updated_at: 2026-11-10 13:19
---

## Origin

Risk-mitigation ("after") follow-up for t2211_4, created at Step 8d after implementation landed.

## Risk addressed

code-health — duplicated pre-Enter/mode-gate/retry loop in minimonitor and the sitrep delivery can drift

- Two implementations of the same pre-Enter / mode-gate / bounded-retry loop
  (`minimonitor_app._submit_shadow_prompt` and `deliver_sitrep_request`) can drift; a fix to
  one (e.g. a new t2001-style hazard) silently misses the other · severity: medium ·
  → mitigation: shared_agent_submit_helper

## Goal

Extract ONE shared submit helper and use it from both callers:
- `.aitask-scripts/monitor/minimonitor_app.py` `_submit_shadow_prompt` (L6011-6170, with
  `_fire_shadow_recheck` L5910-6009 writing the prompt);
- `.aitask-scripts/monitor/agent_request_delivery.py` `deliver_sitrep_request`, the
  phase-3 loop (committed in t2211_4, e16e440e4).

The helper owns the shared sequence: drain, the pre-Enter proof, the pane-mode read as
the last await before every Enter, the Enter, the post-Enter verification, and the bounded
retry with `SHADOW_SUBMIT_RETRIES`.

Keep each caller's result labels. The minimonitor returns `('sent' | 'not_ready' |
'failed', HOLD_*/DISARM_* code)` and checks its delivery token after every await; the
sitrep delivery returns `DeliveryResult` codes. Pin every caller's labels against
pre-refactor behaviour (the "dedupe keeps each caller's labels" rule).

Mind the difference between the two Enter transports. The minimonitor uses
`send_keys(..., "Enter")`, while the sitrep path uses the identity-guarded, acked
`guarded_send_key`. Decide whether the minimonitor should adopt the guarded dispatch too.

Coordinate with t2274 (minimonitor recheck Enter needs the composer payload proof).
t2211_4's per-Enter proof (`review_loop.composer_payload` + `payload_matches`) is what the
minimonitor lacks. Whichever task lands first should carry the proof into the shared
helper, and the other should consume it.
