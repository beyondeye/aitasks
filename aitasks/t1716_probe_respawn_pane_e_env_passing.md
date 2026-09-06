---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [tmux, test_infrastructure, session_persistence, codeagent]
anchor: 1705
created_at: 2026-09-06 13:15
updated_at: 2026-09-06 13:15
---

## Summary

Add **Case 3b** to `tests/test_frozen_standin_spike.sh`, proving that tmux's
native `respawn-pane -e VAR=value` delivers an environment variable to the
respawned process **and** keeps `#{pane_pid}` equal to that process.

The t1705_1 spike's Case 3 validated only the `env VAR=… cmd` prefix. That left
t1705_5 (restore / re-pick flows) choosing its env-passing mechanism on
assumption: `respawn-pane` has accepted `-e environment` since well before the
tmux 3.6a this was measured on, and it is the more direct mechanism, but nothing
had exercised it here.

## What the case does

A deliberate **one-variable parallel** to Case 3 — same fixture, same two
assertions, only the delivery mechanism differs. Running both is what makes the
comparison meaningful: a single passing mechanism proves nothing about the
alternative.

The `#{pane_pid}` assertion is the load-bearing half for either mechanism.
`launch_in_tmux`'s contract is that the pane's pid **is** the agent process,
because a wrapper that *outlives* the agent would make a dead agent's lock keep
reading as alive (t1465). A mechanism that broke that would be unusable for
restore no matter how cleanly it delivered the variable.

The process self-reports its pid and environment to a path only that run knows
(`fake_agent.sh --report-env`), for the reason Case 3 records: macOS has no
`/proc` and `ps eww` / `ps -E` return nothing under SIP, so a foreign process's
environment cannot be read at all; and a `pgrep -f` pattern could match the
wrong process and pass while inspecting it.

The absent-report path records `UNKNOWN` plus `tmux -V` as an explicit finding
rather than passing silently, so a tmux build without `-e` support is visible
instead of skipped.

## Result (tmux 3.6a, macOS 15.7.3)

Both mechanisms work. `-e` is preferred for t1705_5: tmux sets the variable in
the spawned process's environment itself, so the command string carries no
wrapper at all and nothing has to exec through `env`. The prefix stays proven
and usable as a fallback for a build without `-e`.

Suite: 31/31 (was 29/29 — this adds 2 assertions).

## Verification

```bash
bash tests/test_frozen_standin_spike.sh   # ~8s, no agent binaries needed
```

Recorded in the `## Spike findings (t1705_1) — PINNED` block of
`aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md`, which is the
cross-child contract children 2-5 read.
