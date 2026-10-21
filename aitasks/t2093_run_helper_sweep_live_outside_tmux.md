---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [aitask_monitormini, tmux, scratchpad]
anchor: 2073
followup_kind: risk_mitigation
created_at: 2026-10-21 10:15
updated_at: 2026-10-21 10:15
---

## Origin

Risk-mitigation ("after") follow-up for t2088, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — live case D flip and case G cannot run inside this tmux session

- The live flip (case D) and the new live case G cannot run in this session: it is inside tmux with the `-L ait` server alive, and `require_clean_ait_server` refuses. So the end-to-end proof that no `pane-died` is needed would land unrun · severity: medium · → mitigation: run_helper_sweep_live_outside_tmux

## Goal

Run the live tests t2088 could not run, from a terminal that is NOT inside tmux and with no `-L ait` server alive (both refuse otherwise):

- [ ] `bash tests/test_scratchpad_spawn_live.sh` — all cases pass, in particular:
  - [ ] D: dropping a frozen record (kill-pane branch, real sibling keeps the window) kills the stand-in, its scratchpad and a shadow placed in another window; the sibling and a pad bound to the sibling survive, still bound
  - [ ] G: `kill_agent_pane_smart`'s pane branch (driver `kill` mode) prints `KILL:True:False`, kills the agent, its pad and its other-window shadow; the sibling, its pad and the minimonitor companion survive
- [ ] `bash tests/test_cleanup_rule_parity.sh` passes (the cleanup script itself was not changed by t2088; this confirms the rule tables still agree)

If a case fails, record the output and spawn a bug follow-up against the t2088 sweep (`lib/helper_panes.kill_bound_helpers`, `monitor_core.TmuxMonitor.kill_agent_pane_smart`, `lib/agent_freeze.drop_record`).
