---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [aitask_monitor, shadow, tui, tmux_destructive]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-31 06:43
updated_at: 2026-07-31 06:43
---

## Origin

Risk-mitigation ("after") follow-up for t1216_4, created at Step 8d after
implementation landed.

## Risk addressed

`addresses:` mocked-only coverage of the spawn path, its cleanup-hook companion
argument, hook idempotence and focus retention.

Matching `## Risk` bullets from `aiplans/archived/p1216/p1216_4_monitor_shadow_spawn.md`:

### Code-health risk: medium
- The fixes for C2 and C5 change `agent_launch_utils` — a public dataclass field
  and the hook-install contract — which every agent launch in the framework goes
  through, not just the shadow path. Defaults preserve existing behaviour, but
  the blast radius is now framework-wide rather than monitor-local · severity:
  medium
- Retargeting patch sites in two minimonitor test files moves the
  characterization net that was t1216_1's proof the lift changed no behaviour; a
  missed `launch_in_tmux` retarget fails **silently** · severity: medium

### Goal-achievement risk: low
- Behaviour is specified by a working implementation and every acceptance item
  has a mocked unit test; the parts not provable in-task (live pane placement,
  real hook firing, focus retention) are covered manually by t1216_5 rather than
  automatically · severity: low

## Goal

Add an isolated-tmux smoke test (`require_isolated_tmux` from
`tests/lib/tmux_isolation.sh`) that **really** spawns a shadow from `ait monitor`
and asserts the contracts every current test can only assert through mocks —
making the PINNED companion-pane contract repeatable rather than human-checked.

It must assert, against a live throwaway tmux server:

1. **The `pane-died` hook's companion argument** is the newly created *shadow*
   pane, never the monitor's own `TMUX_PANE`. This is the PINNED contract of
   t1216_4: `aitask_companion_cleanup.sh` job 2 runs `kill-pane -t "$companion"`
   with no marker check, so a monitor pane passed here would be killed on the
   agent's exit, arbitrarily later.
2. **A pre-existing companion hook is not overwritten.** Arm an agent pane with a
   cleanup hook naming companion A, then spawn a shadow from the monitor and
   confirm the hook still names A and the new entry was appended at the next free
   `pane-died[N]` index — with an unrelated `pane-died[0]` hook surviving too.
3. **The client's active window does not change** across both placement branches
   (same-window split and `shadow_same_window: false`), i.e. `select_window=False`
   really reaches tmux as "no `select-window`" / "`new-window -d`".

## Notes

- **This task is `tmux_destructive`.** Same pick-time constraint as t1216_4: run
  it only from a shell whose tmux server carries no code agents worth keeping.
  `attach_shadow_cleanup_hook` installs persistent `remain-on-exit` +
  `pane-died` state on whatever pane it is given, and
  `aitask_companion_cleanup.sh` deliberately runs raw `tmux` with **no socket
  flag**, so `AITASKS_TMUX_SOCKET` cannot sandbox the cleanup script itself.
  Preflight with `tmux -L ait list-panes -a`.
- The mocked side is already covered by `tests/test_monitor_shadow_pick.py` (45
  tests) and `tests/lib/tmux_socket_containment.py`; this task adds the live leg
  those deliberately cannot provide, and is the automated counterpart to the
  human walkthrough owned by t1216_5.
