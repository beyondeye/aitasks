---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [sitrep, tmux]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-27 01:28
updated_at: 2026-11-27 01:39
---

## Origin

Spawned from t2349 during Step 8b review (upstream defect). It also carries the
t2338 note's wider blast radius that t2349 left out of scope ("keep
`switch_to_pane_anywhere`'s other callers unchanged").

## Upstream defect

- `.aitask-scripts/lib/agent_launch_utils.py:2116` — `switch_to_pane_anywhere`
  makes three separate calls: a lookup, then `switch-client`, `select-window`
  and `select-pane`.
  - **Half move.** When the destination pane dies (or moves) after its lookup
    but its session and window survive, `switch-client -t =<session>`
    succeeds and `select-pane` then fails. The function returns False, but
    the client is left in the destination session on another pane. Measured
    on tmux 3.8 in t2349; see the t2349 archived plan's live case 9dX.
  - **Implicit client.** Without `client=`, the switch lets tmux pick the
    client, so when the caller's own client has gone, whichever client tmux
    finds is moved. This was reproduced for the cold path in t2338's live
    case 5X.

## Callers to fix

- `.aitask-scripts/monitor/monitor_core.py:6001`: the `spawn_sitrep`
  `focused` branch, `switch_to_pane_anywhere(agent)`.
- `.aitask-scripts/monitor/monitor_core.py:6116`: the `spawn_sitrep` repair
  branches, `switch_to_pane_anywhere(agent)`.

  Both can read the launch-time `_SitrepClient` (`_sitrep_launch_client`,
  caller-pane targeted, control clients refused) and use the guarded
  `switch_client_to_pane` that t2349 added. Pin each with
  `tests/test_sitrep_window_select_live.sh` style cases.
- `.aitask-scripts/monitor/monitor_core.py:4590`: the monitor's own jump to a
  pane. It needs its own client source; the monitor runs over a control
  client in its helper session (t2051), so "the current client" is the
  control client.

## Diagnostic context (from t2349)

- `switch_client_to_pane(pane_id, *, client, client_pid)`
  (`lib/agent_launch_utils.py`) performs the name+pid check and ONE
  `switch-client -c <name> -t $S:@W.%P` in a single `if-shell -F` dispatch.
  - The full target makes tmux refuse a dead or moved pane before anything
    moves. Measured on 3.8 and on a real 3.3a.
  - Its stage A is the `#{L:}` client loop (tmux 3.4 and newer), with an
    exact `#{==:…,1}` match. On 3.3a the unknown `L:` expands to a truthy
    literal, so a truthiness guard is unsafe there.
  - Its stage B is the client tmux resolves for the dispatching process's
    context (`TMUX`/`TMUX_PANE`). Its outcomes are `moved`, `absent`,
    `skipped` and `failed`.
- `tests/test_sitrep_window_select_live.sh` has `AIT_LIVE_TMUX_BIN=<tmux>`,
  which runs the whole file against another tmux, e.g. the Debian 3.3a binary
  the user extracted for t2349.

## Suggested fix

- Give `switch_to_pane_anywhere` the single full-target switch
  (`switch-client [-c <c>] -t $S:@W.%P`), which removes the half move for
  every caller.
- Move the two `spawn_sitrep` branches to `switch_client_to_pane` with the
  launch-time client.
- Decide separately what client source the monitor jump should use.

Keep `tests/test_multi_session_primitives.sh` Tier 1b
(`switch_to_pane_anywhere` call order) in step with any change to its call
shape.
