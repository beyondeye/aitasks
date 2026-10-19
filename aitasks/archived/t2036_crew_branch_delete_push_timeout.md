---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 08:01
updated_at: 2026-10-19 16:38
completed_at: 2026-10-19 16:38
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2035** id=2026-10-19T09:54:15Z.8518911df547d7aa113e3074 from=t2035 from_verified=yes at=2026-10-19T09:54:15Z base=245754abee80860da3e66b62a3b955fb27a7fb92 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2035 (commit 245754abe). This changes how lib/bounded_run.py isolates the command it runs, so it may affect pushes you route through it.
> | 
> | - Before: bounded_run always used a new session (start_new_session).
> | - Now (`_child_isolation()`): it uses a new session ONLY when the runner itself has a controlling terminal. Otherwise the child leads its own process group (`process_group=0` on Python 3.11+, or `os.setpgrp` while single-threaded) INSIDE the caller's session. The group kill and the "no controlling terminal / no prompt channel" guarantee are unchanged.
> | - `run_bounded(..., cancelled=...)` now also reaps the group when a stop was requested but the leader exited first (the CLI always passes `cancelled`).
> | 
> | What this may mean for you: a test asserting that git ran in a separate session (`os.getsid(child) == child pid`) now passes or fails depending on whether the test run has a controlling terminal. `tests/test_bounded_run.py::TestChildIsolation` shows how to pin either mode by patching `bounded_run._has_controlling_terminal`. Kill and timeout semantics (124, TERM → CONT → grace → KILL) are unchanged. Line references are as of 245754abe.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T13:26:54Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-19T13:37:43Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-19T13:38:18Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:d16a0fb1658d028f

> **✅ gate:risk_evaluated** run=2026-10-19T13:38:18Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2036/risk_evaluated_2026-10-19T13:38:18Z-risk_evaluated-a1.log`
