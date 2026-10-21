---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-21 17:32
updated_at: 2026-10-21 17:41
artifacts:
  - handle: art:trail-crew-runner
    kind: implementation_trail
    name: Agent crew runner — fixes and improvements
---

## Origin

Risk-mitigation ("after") follow-up for t2029, created at Step 8d after implementation landed.

## Risk addressed

takeover duel (goal-achievement)

- Takeover duel: the runner's own identity fields win a two-sided change. If a peer runner on another host took over (rewrote `hostname`/`pid`), this runner would overwrite that claim, and both might keep running. This rule is specified by the task, and the situation already exists today on clean merges · severity: low (residual — the automatic resolution now defers on competing identities via inline post-phase runner_identity_guard; detecting and yielding on a duel that a *clean* merge produces is left to crew_runner_takeover_duel_detection) · → mitigation: inline post-phase runner_identity_guard; crew_runner_takeover_duel_detection

## Goal

Full takeover detection and a safe yield: when a pull (clean or conflicted) shows another live runner owns `_runner_alive.yaml`, log it and yield or hold rather than overwrite, and report the deferred competing-identity case to the operator.

Background from t2029:
- t2029 added `_resolve_runner_alive` to `.aitask-scripts/agentcrew/agentcrew_utils.py`. A conflict confined to `_runner_alive.yaml` is resolved field by field, and the runner-owned fields (`status`, `pid`, `hostname`, `started_at`, `last_heartbeat`, `next_check_at`, `interval`) always take the local side.
- Its guard, `_competing_runner_identity(base, ours, theirs)`, defers only the **conflicted** case. When theirs' `(hostname, pid)` differs from both the base and ours, the pull returns `deferred|merge_conflict: _runner_alive.yaml (competing runner identities: <theirs> vs <ours>)`. It repeats every iteration, and the runner only warns on stderr in non-batch mode.
- A **clean** merge (no adjacent-line overlap) still applies the peer's identity, and the runner then rewrites `last_heartbeat`/`next_check_at` under that other runner's `pid`/`hostname`. `update_runner_heartbeat` updates only those two fields. Nothing detects this.
- In `agentcrew_runner.py`, `run_loop` pulls before its heartbeat. `check_requested_action` runs after the pull, and the start-up takeover logic (`check_stale_runner`/remote-runner handling near the `taking over` log line) runs only at start-up.

What this follow-up should decide and implement:
1. After every pull (clean, merged or resolved), compare the committed `_runner_alive.yaml` identity with this process's `(hostname, pid)`. On a mismatch with a fresh heartbeat (another live runner), yield: stop launching agents and exit cleanly or hold, rather than rewrite the file. Pick and document the policy.
2. Surface the repeated `competing runner identities` deferral to the operator (a batch-mode line and/or a crew status field), so a stuck duel is visible.
3. Tests in `tests/test_crew_pull_no_autostash.sh`, reusing the `runner_takeover` peer fixture and the harness's `--interval` option: a clean-merge takeover (peer rewrites identity lines only, no local edit) and the conflicted case (cell 16d's fixture driven through `run_loop`).
