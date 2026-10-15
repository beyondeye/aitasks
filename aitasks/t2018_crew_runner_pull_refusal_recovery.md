---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 23:08
updated_at: 2026-10-16 00:21
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2016** id=2026-10-15T21:30:21Z.891b23545bf0ce83c76c62ec from=t2016 from_verified=yes at=2026-10-15T21:30:21Z base=32d1bb16eb5cbdd21e79158ed2a799b8952aba1b base_branch=main dirty=yes host=omg16
>
> | t2016 (crew branch never gets upstream) landed in commit 8019565ea. Advisory context for t2018's runner pull-refusal work:
> | 
> | 1. Reachability: crew branches now publish to origin with `git push --quiet -u origin HEAD` whenever an `origin` remote exists — crew init/addwork/setmode via `crew_push` in .aitask-scripts/lib/agentcrew_utils.sh, the runner and `ait crew status set` via the new `git_push()` in .aitask-scripts/agentcrew/agentcrew_utils.py. Your task body's condition "if t2016 makes crew branches publish by default, this gap becomes reachable for every user" now holds whenever a second writer pushes to the crew branch (no shipped path attaches a second machine, so in practice that still needs a manual clone).
> | 
> | 2. Edit overlap: as of 8019565ea, t2016 inserted `git_push()` between `git_pull()` and `git_commit_push_if_changes()` in agentcrew/agentcrew_utils.py, and `git_commit_push_if_changes` now calls it. `git_pull()` itself was deliberately left untouched for you. If you edit that file, rebase onto 8019565ea.
> | 
> | 3. Pre-existing, unchanged by t2016 (from code reading, not a run): in a repo with no origin, `git_pull()` still prints "git pull warning: ... no tracking information" on every non-batch runner iteration, whereas `git_push()` now returns silently when `git remote get-url origin` fails. You own git_pull — you may want the same guard for consistency. Your call.
> | 
> | 4. tests/test_crew_pull_no_autostash.sh setup_crew_remote_fixture comment "No upstream exists yet, so the seeding addwork's own pull and push fail quietly" is slightly stale: origin is added only after seeding, so the pull still fails quietly but the push is now skipped silently (no origin). The fixture's later manual `push -u` stays valid; t2016 did not edit that file.

> **👁 note:read** id=2026-10-15T21:48:18Z.de48fe20c2f23ac3303e50f9 by=t2018 at=2026-10-15T21:48:18Z mode=explicit ids=2026-10-15T21:30:21Z.891b23545bf0ce83c76c62ec

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T21:21:47Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T22:04:19Z status=pass attempt=1 type=human
