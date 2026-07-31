---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: test
status: Done
labels: [aitask_monitor, shadow, tui, tmux_destructive]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus5
created_at: 2026-07-31 06:43
updated_at: 2026-07-31 10:04
completed_at: 2026-07-31 10:04
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
   Assert it **behaviourally**, not only lexically: let the hook fire (kill the
   agent's process), then confirm the shadow died and a monitor stand-in pane in
   another window survived.
2. **A pre-existing `pane-died` hook is not overwritten.** This splits into the
   two distinct branches of `attach_shadow_cleanup_hook` — the original single
   acceptance item merged them, but they are mutually exclusive in the shipped
   code, which returns `"existing"` and appends **nothing** when a cleanup hook
   is already present:
   - **2a** — the pre-existing hook **is** a cleanup hook naming companion A:
     after a monitor-side spawn it still names A, and **no second cleanup entry**
     is appended (the shadow is still cleaned up because job 1 is marker-driven).
   - **2b** — the pre-existing `pane-died[0]` hook is **unrelated**: it survives,
     and the cleanup hook is appended at `pane-died[1]`. Both entries must be
     asserted — checking only "our hook is present" passes even when the
     unrelated one was destroyed.
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
  The preflight is no longer manual: `require_clean_ait_server`
  (`tests/lib/tmux_isolation.sh`) refuses with exit 2 when `$TMUX` is set or the
  `-L ait` server is alive, overridable with `AIT_LIVE_TMUX_TEST_FORCE=1`. It
  must be called **before** `require_isolated_tmux`, which unsets `$TMUX` and
  repoints `$TMUX_TMPDIR`.
- **Every positive assertion needs a paired control.** The suite spawns with
  `select_window=True` (minimonitor's policy) to show the active window really
  does move, and arms a deliberately wrong companion to show that pane really is
  killed — otherwise items 1 and 3 could pass merely because nothing happened.
- The mocked side is already covered by `tests/test_monitor_shadow_pick.py` (45
  tests) and `tests/lib/tmux_socket_containment.py`; this task adds the live leg
  those deliberately cannot provide, and is the automated counterpart to the
  human walkthrough owned by t1216_5.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-31T04:53:01Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-31T07:02:24Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-31T07:04:14Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:669728c1dcd3b373

> **✅ gate:risk_evaluated** run=2026-07-31T07:04:14Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1353/risk_evaluated_2026-07-31T07:04:14Z-risk_evaluated-a1.log`
