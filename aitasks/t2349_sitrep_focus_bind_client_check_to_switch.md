---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [sitrep, tmux]
gates: [risk_evaluated]
anchor: 2175
followup_kind: review_finding
created_at: 2026-11-22 19:20
updated_at: 2026-11-22 19:20
---

## Origin

Review finding on t2338 (disposition: follow-up hardening, verified in a private
tmux test by the reviewer).

## Problem

`monitor_core.spawn_sitrep`'s cold cross-session jump (t2338) reads the
initiating client at launch (`_sitrep_launch_client`: `#{client_name}`,
`#{client_pid}`, `#{client_session}`), re-checks after the companion spawn that
the same (name, pid) is still attached (`_sitrep_client_still_attached`,
`list-clients`), then switches it with
`switch_to_pane_anywhere(agent, client=<name>)` (`switch-client -c <name>`).

A narrow race remains between the `list-clients` re-check and the later
`switch-client`: if the initiator closes in that window and a new terminal is
attached on the same freed `/dev/pts/N` name, the replacement is moved. The
reviewer reproduced it by pausing after `list-clients` returned. The window is
about one tmux round trip (the startup-long window was closed in t2338).

## Goal

Bind the identity check and the switch together so no other client can be moved,
e.g. one tmux invocation that checks and switches atomically (a `;`-chained
command list or `if-shell -F` on `#{client_pid}` evaluated against the target
client), or another server-side construct; measure what tmux offers before
choosing. Keep `switch_to_pane_anywhere`'s other callers unchanged.

## Tests

`tests/test_sitrep_window_select_live.sh` case 6 already models pty reuse
during startup; add a case that replaces the client between the re-check and
the switch (a seam between the two calls), with a mutant control.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2338** id=2026-11-23T07:48:20Z.1e67941997ab3c84d1d275f9 from=t2338 from_verified=yes at=2026-11-23T07:48:20Z base=adf6bfe52c2632e86648de3a5501d599bceab73f base_branch=main dirty=yes host=omg16
>
> | Advisory (t2338, tree-relative claims as of adf6bfe52): a wider blast radius than
> | this task's body records. Besides the cold-spawn jump (which already names its
> | client and re-checks name+pid), three other callers of
> | agent_launch_utils.switch_to_pane_anywhere still let tmux pick the client
> | (no `client=`, so `switch-client` without `-c`):
> | - .aitask-scripts/monitor/monitor_core.py:4589 — the monitor's jump to a pane
> | - .aitask-scripts/monitor/monitor_core.py:6016 — spawn_sitrep `focused` branch
> | - .aitask-scripts/monitor/monitor_core.py:6125 — spawn_sitrep repair branches
> | If the caller's own client has gone, tmux moves whichever client it finds
> | (reproduced for the cold path in t2338's live case 5X). spawn_sitrep can pass the
> | launch-time `_SitrepClient` (caller_pane-targeted read, control clients refused)
> | to those branches too; the monitor jump would need its own client source.
> | Pinned behaviour to keep: tests/test_sitrep_window_select_live.sh cases 1-7.
