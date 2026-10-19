---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-16 08:01
updated_at: 2026-10-19 08:02
---

## Origin

Risk-mitigation ("after") follow-up for t2024, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — crew-branch deletion pushes stay unbounded

- The crew-branch deletion pushes (`ait crew cleanup`, brainstorm delete, brainstorm reopen) stay unbounded · severity: low · → mitigation: crew_branch_delete_push_timeout

## Goal

t2024 bounded every crew WRITE to origin (init, addwork, setmode, the runner, `ait crew status set`) through `lib/bounded_run.py`: a hard bound of `AIT_CREW_GIT_TIMEOUT` seconds (default 10), process-group kill, and a non-interactive environment (no controlling terminal, no askpass, no display). The branch-deletion pushes were out of its scope and can still stall until the TCP timeout against an origin that is routable but never answers:

- `.aitask-scripts/aitask_crew_cleanup.sh` — `git push origin --delete "$branch_name" 2>/dev/null || true`
- `.aitask-scripts/aitask_brainstorm_delete.sh` — `git push origin --delete "crew-${CREW_ID}" 2>/dev/null || true`
- `.aitask-scripts/brainstorm/brainstorm_app.py` (reopen path, around the stale-crew delete) — `subprocess.run(["git", "push", "origin", "--delete", crew_branch], …)`

Route the shell calls through `_crew_git_bounded` (`lib/agentcrew_utils.sh`; check whether those scripts already source it) and the Python call through `agentcrew_utils.git_cmd(…, timeout=crew_git_timeout())`. Keep each call's best-effort semantics and messages: a timed-out delete is a failed delete. In the brainstorm TUI, make sure the call runs off the UI thread or stays bounded, so the reopen flow cannot freeze.

Tests: follow the hang-fixture pattern in `tests/test_crew_publish_upstream.sh` (Tests 9–15: an ssh origin whose `core.sshCommand` stub ignores SIGTERM and sleeps; assert the bound, reaping, and that the local cleanup still completes).
