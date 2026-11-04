---
priority: medium
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [sitrep]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-04 19:21
updated_at: 2026-11-04 22:30
---

## Origin

Risk-mitigation ("after") follow-up for t2175_5, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — unit tests mock tmux and harvest

- Unit tests mock both tmux and the harvest; nothing proves the real gateway capture → real `harvest capture` → real guarded kill end to end, nor the if-shell condition against a real server · severity: medium · → mitigation: harvest_close_live_smoke

## Goal

Add an isolated-tmux live test of the monitor's `h` (harvest-and-close) flow end to end, through the real code paths rather than mocks:

- Isolation first: `require_clean_ait_server`, then `require_isolated_tmux` (tests/lib/tmux_isolation.sh; `tests/test_monitor_shadow_spawn_live.sh` is the reference caller); a scratch git repository (its own main worktree) and a scratch HOME / `AITASKS_AGENT_SESSIONS_FILE`, `AIT_PYTHON` pinned first, every seam exported before the private server starts (aidocs/framework/testing_conventions.md "Composed acceptance"). Never touch this repository's `.aitask-sitrep/` or the real `~/.config/aitasks` (take a before/after manifest, as t2175_4's smoke did).
- A pane in an `agent-pick-<n>` window prints a fixture workflow-end banner (Complete, with follow-ups and a trail handle). Drive `SitrepCloseMixin._harvest_for_close` (or the full `_harvest_close` with the dialog stubbed) with a real `TmuxMonitor` against that server: assert the real gateway capture, the real `aitask_sitrep_harvest.sh capture` writing items into the scratch store, `HarvestReport.ok`, then the confirm callback killing the pane via `kill_agent_run_guarded` (pane gone, window and a companion stand-in kept).
- A failing harvest (e.g. a scratch store made un-ignorable → `HARVEST_FAILED:…|store_not_ignorable`) keeps the pane and offers no close.
- An `agent-sitrep` window: nothing captured, nothing written to the store.
- A `respawn-pane -k` between the harvest and the confirm: the guarded kill reports `changed` and the new process stays running.
- `tests/test_kill_agent_run_guarded.sh` already proves the guard condition and the pane-only rule against a real server; reuse its fixture shape for the kill half.
