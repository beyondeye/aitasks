---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-15 23:08
updated_at: 2026-10-15 23:11
---

## Origin

Risk-mitigation ("after") follow-up for t2008, created at Step 8d after implementation landed.

## Risk addressed

code-health bullet 2 (runner pull never converges when an incoming commit touches _runner_alive.yaml)

- The runner merge pull no longer stashes, and that pull is not guaranteed to
  converge. `run_loop` (`agentcrew_runner.py`, ~L870–878) calls
  `update_runner_heartbeat()`, which rewrites `_runner_alive.yaml`, right before
  every `git_pull()`. If an incoming commit touches that file, the merge refuses on
  **every** iteration. Pushes then stay non-fast-forward, and a remote
  `requested_action: stop` (read by `check_requested_action()` from that same
  file) is never seen. This already happens under git's default config. For
  `merge.autoStash` users, stash → merge → pop could sometimes get through, so
  this change removes an accidental recovery path for them. Cell 6 pins the
  refusal; nothing here claims recovery. · severity: medium · → mitigation:
  crew_runner_pull_refusal_recovery

## Goal

Make the crew runner's per-iteration pull converge when an incoming commit touches a file the runner dirtied before pulling. Today `run_loop` in `.aitask-scripts/agentcrew/agentcrew_runner.py` writes the `_runner_alive.yaml` heartbeat (`update_runner_heartbeat()`) immediately before `git_pull()`. If any incoming commit touches that file, the merge refuses on every iteration, pushes stay non-fast-forward, and a remote `requested_action: stop` is never seen.

Fix direction (decide in planning):
- pull before writing the heartbeat, or commit the heartbeat before pulling, so the runner's own file is never dirty at the pull;
- consider the other files the worktree routinely holds uncommitted: agents' `<agent>_alive.yaml`, non-terminal `<agent>_status.yaml`, `_crew_status.yaml`, and queued `<agent>_commands.yaml`. An incoming commit touching any of those blocks the merge the same way;
- keep t2008's `--no-autostash`: recovery must not stash or rewrite another process's uncommitted file.

Pinning: `tests/test_crew_pull_no_autostash.sh` Test 6 pins today's clean refusal (no stash, no rewrite, HEAD unchanged, no MERGE_HEAD) for the overlapping `_runner_alive.yaml` case. Update that cell to assert convergence once the fix lands, and keep its no-stash / no-rewrite assertions.

Reachability: crew branches currently get an upstream only under `push.autoSetupRemote` or a manual `push -u` (see t2016). If t2016 makes crew branches publish by default, this gap becomes reachable for every user. Sequence the two accordingly.
