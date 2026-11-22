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
