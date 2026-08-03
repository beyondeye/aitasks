---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [aitask_monitor, aitask_monitormini, tui, tmux]
gates: [risk_evaluated]
anchor: 1326
created_at: 2026-07-30 10:34
updated_at: 2026-07-30 10:34
boardidx: 103424
---

## Context

Risk-mitigation "after" task for **t1326** (cross-repo prioritized-agent marks),
addressing its identified goal-achievement risk: the fail-closed liveness rule is
the part most likely to be subtly wrong, and no existing harness sets up several
genuine repos and tmux sessions.

t1326 ships strong unit coverage of the policy, plus a real-discovery test that
drives `_parse_list_panes` with only an excluded companion pane. What it does not
have is a Tier-2 test against a **real tmux server** with two real project roots.

## Goal

Add a Tier-2 real-tmux harness, modelled on the existing Tier-2 half of
`tests/test_multi_session_monitor.sh` (isolated socket via
`tests/lib/tmux_isolation.sh`, fake project roots holding
`aitasks/metadata/project_config.yaml`, PID-scoped session names, `SKIP` when
tmux is unavailable).

## Acceptance criteria

- [ ] Two fake repos with two tmux sessions on an isolated socket; a mark set for
      an agent window in repo A is visible when reading the store as repo B
- [ ] Killing repo B's **session** never drops repo B's marks (the fail-closed
      direction — an unobservable session is not evidence an agent departed)
- [ ] Killing only the **agent window** while its session stays up DOES reap that
      mark on the next purge (the prompt-reap direction)
- [ ] A session reduced to only the excluded companion pane is still enumerated,
      exercised end-to-end rather than through a stubbed `_parse_list_panes`
- [ ] Degrades to `SKIP` (not failure) when tmux is absent or a session cannot start
- [ ] Cleans up its server, sessions and temp roots via a single `trap ... EXIT`

## Reference

- `tests/test_multi_session_monitor.sh` — Tier 2 block at the end
- `tests/test_agent_marks_generation.py` — the unit-level equivalents
- `.aitask-scripts/lib/agent_marks.py` — `sweep_liveness` and the observation TSV
