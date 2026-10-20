---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [aitask_monitormini, tmux, scratchpad]
anchor: 2073
followup_kind: carry_over
created_at: 2026-10-20 16:57
updated_at: 2026-10-20 16:57
---

## Context

Carry-over from t2073_3 (bound-helper pane rule, folded t1388). t2073_3 changed
the "is this pane a helper?" rule in both the Python side
(`monitor_core.classify_window_panes`, discovery, the occupancy check, minimonitor
rung 2) and the bash side (`aitask_companion_cleanup.sh` jobs 1 and 2), and
extended the tmux-stress tests that drive both against a real tmux server. Those
tests were **not run** during t2073_3, by the user's explicit choice: the
implementing session ran inside tmux on the live `-L ait` server, and the tests'
`require_clean_ait_server` guard (correctly) refuses that. The guard must not be
bypassed and the live server must not be stopped for this.

So the bash/Python cleanup parity for scratchpad panes is **unverified**. The
Python halves are covered by unit tests that did run (`tests/test_helper_panes.py`,
`tests/test_minimonitor_sibling_fallback.py`, the arity and companion-filter
tests). Only the live-tmux runs below are outstanding.

## What to run

In an environment with **no access to the host's tmux sockets** (a container or
VM), or on the host when no aitasks session is running: not inside tmux, `-L ait`
stopped. No `AIT_LIVE_TMUX_TEST_FORCE`.

```bash
bash tests/test_cleanup_rule_parity.sh
bash tests/test_frozenagent_standin_stamp.sh
bash tests/test_monitor_shadow_spawn_live.sh
bash tests/test_frozen_standin_spike.sh
```

`test_cleanup_rule_parity.sh` carries the new t2073_3 coverage:
- roles `scratchpad` (bound to `$first`) and `frozen_scratch` (`@aitask_frozen` +
  `@aitask_scratchpad_target=$first`);
- rows `agent + scratchpad + companion` → window,
  `agent + agent + scratchpad + companion` (unbound agent dies) → pane,
  `agent + frozen(scratch) + companion` → pane;
- a job-1 block: the scratchpad bound to the survivor is NOT killed when a sibling
  dies, IS killed when its target dies, and a frozen stand-in carrying a retained
  scratchpad target is never reaped by job 1.

## Acceptance

- [ ] All four tests run to their own PASS summary (read the summary line; the
      parity file uses file-backed counters, so its exit status is meaningful).
- [ ] Any failure is diagnosed. A bash/Python disagreement is a real defect in
      `aitask_companion_cleanup.sh` or `monitor_core.classify_window_panes`. Fix
      it under its own task, or here if it is small.
- [ ] Record the run (environment, commit SHA, per-test summary lines) in this
      task's plan before archival.
