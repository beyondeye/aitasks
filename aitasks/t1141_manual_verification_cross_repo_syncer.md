---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [tui, git-integration, project_groups, manual_verification]
assigned_to: dario-e@beyond-eye.com
anchor: 1138
created_at: 2026-07-09 10:33
updated_at: 2026-07-15 19:32
---

## Origin

Risk-mitigation ("after") follow-up for t1138, created at Step 8d after implementation landed.

## Risk addressed

Code-health risk (single-repo regression, live multi-repo TUI behavior, refresh scheduling):
- Syncer row-key model rework (composite keys, per-repo snapshots) could regress single-repo behavior or `check_action` gating.
- Concurrent refresh sources (interval tick, manual `r`, post-action) could interleave: a superseded local-only snapshot overwriting a newer fetched one, or accumulated background git passes.

## Goal

Drive the live syncer TUI in a multi-repo environment and verify the cross-repo behavior end-to-end.

## Verification Checklist

- [x] Launch `ait syncer` in a repo with ≥2 registered projects: table shows one row per repo × ref (`main`, `aitask-data`) with a Project column; the launch repo is listed first. — PASS 2026-07-15 19:21 auto: run_test — multi-repo (3 repos) renders Project column + 6 repo×ref rows, launch repo first, project cell='aitasks'
- [x] Least-recently-fetched scheduling: over successive automatic ticks (default 60s), exactly one repo's Fetched age resets per tick — PASS 2026-07-15 19:21 auto: run_test tick rotation covers every repo, <=1 fetch per settled tick; failed-fetch-no-starve via unit test_syncer_rows LeastRecentFetchKeyTests
- [x] Fetched age column ticks up smoothly between refreshes (5s display updates); `—` shows for never-fetched repos. — PASS 2026-07-15 19:21 auto: run_test — never-fetched cell='—', stamp→'7s'; AGE_TICK_SECONDS=5; format_age spot values
- [x] Manual `r` immediately refreshes the highlighted row's repo and defers it in the automatic rotation. — PASS 2026-07-15 19:21 auto: run_test — press r calls _request_refresh(selected.session_key, explicit=True); attempt-stamp records → defers in LRU
- [x] Per-row action gating: `s` footer hint/action only on `aitask-data` rows, `u`/`p` only on `main` rows — PASS 2026-07-15 19:21 auto: run_test — check_action gating follows cursor: main→pull/push, aitask-data→sync only
- [x] Run `s` (sync) and `u` (pull) against a NON-current repo: notifications are prefixed with that project's label, and (best-effort corroboration) that repo's `.git/FETCH_HEAD` mtime advances on `u` while the launch repo's does not. The primary targeting guarantee is the unit spy tests in `tests/test_sync_action_runner.py`. — PASS 2026-07-15 19:21 auto: run_test — sync/pull on NON-current repoB: subprocess cwd=repoB, notifications prefixed 'repoB:'; spy tests test_sync_action_runner pass. Live FETCH_HEAD mtime skipped (would mutate user repos)
- [x] Trigger a failure on a non-current repo (e.g. push with no permission) and confirm the failure modal names the project and the "Launch agent to resolve" flow roots the agent in THAT repo. — PASS 2026-07-15 19:21 auto: run_test — push failure on repoB captured with ref_name='repoB main', repo_root=repoB (agent rooting), modal title names project
- [x] Single-repo regression: with only one discovered repo (e.g. temporary empty registry + outside tmux), the table shows the legacy two rows, no Project column, last column is a wall-clock "Last refresh". — PASS 2026-07-15 19:21 auto: run_test — empty registry → single-repo: no Project column, legacy rows [main,aitask-data], 'Last refresh' header
- [x] `ait stats` still renders correct project labels after the `compact_root` promotion. — PASS 2026-07-15 19:21 auto: StatsApp real registry labels==project names + rendered items; colliding names disambiguated via compact_root ('repo (~/x/repo)')

## Related

Original task: t1138 (archived). Plan: `aiplans/archived/p1138_add_cross_repo_support_to_syncer_tui.md` after archival.

**Gate correction:** This task was created with an erroneous `gates: [risk_evaluated]`
(auto-injected from the `fast` profile's `default_gates` at creation). A
manual_verification task skips planning and can never satisfy `risk_evaluated`,
so the gate was removed here to unblock archival of the completed verification.
Root-cause fix tracked in **t1156**.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **🔄 gate:risk_evaluated** run=2026-07-15T16:26:02Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:c286714ec7c100d7

> **❌ gate:risk_evaluated** run=2026-07-15T16:26:02Z-risk_evaluated-a1 status=fail attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluation incomplete: plan has no '## Risk' section: aiplans/p1141_manual_verification_auto.md
> Log: `.aitask-gates/1141/risk_evaluated_2026-07-15T16:26:02Z-risk_evaluated-a1.log`
