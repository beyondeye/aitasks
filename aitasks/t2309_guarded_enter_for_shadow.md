---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [sitrep, tui, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 22:31
updated_at: 2026-11-16 09:07
---

## Origin

Risk-mitigation ("after") follow-up for t2275, created at Step 8d after implementation landed.

## Risk addressed

code-health — two Enter transports; t2001 single-round-trip residual on the minimonitor

- The two Enter transports stay different behind one helper (`send_keys` vs guarded `if-shell`).
  The t2001 residual stays open on the minimonitor side · severity: low · → mitigation: guarded_enter_for_shadow

## Goal

Since t2275 both submit paths share `monitor/agent_submit.submit_typed_text`, but the
minimonitor's `send_enter` (in `minimonitor_app._submit_shadow_prompt`) still presses Enter with
a plain `monitor.send_keys(shadow_pane, "Enter")`, while the sitrep delivery uses the identity- and
mode-guarded, acked `monitor_core.guarded_send_key` (one `if-shell` whose condition is the run
identity + "not in a mode"). So a tmux mode entered in the one round trip between the pre-Enter
mode read and the keystroke is still not closed on the minimonitor side (the documented t2001
residual, `aidocs/framework/shadow_agent.md` item 9).

Give the minimonitor's `send_enter` (and possibly the prompt write in `_fire_shadow_recheck`) the
guarded dispatch through the helper's transport callable:
- read a shadow `RunIdentity` at fire time (`monitor_core.RUN_IDENTITY_FORMAT` /
  `parse_run_identity`) and measure its frozen-shadow semantics first;
- map `DISPATCH_SKIPPED` (in mode → the existing pre-Enter in-mode hold; identity changed → the
  shadow was replaced) and `DISPATCH_UNKNOWN` onto the loop's codes without breaking the
  t2001/t2009 supersession invariants pinned by `tests/test_submit_labels_pinned.py`;
- if the prompt write also moves to `guarded_paste_text`, re-run t1525's drain measurement
  (the write transport changes).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T07:07:37Z status=pass attempt=1 type=human
