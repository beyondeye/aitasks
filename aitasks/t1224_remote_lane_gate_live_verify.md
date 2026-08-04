---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [gates, task_workflow, execution_profiles]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-23 18:37
updated_at: 2026-08-04 12:28
boardidx: 31744
---

## Origin

Risk-mitigation ("after") follow-up for t635_35, created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement: the full remote/web lane cannot be exercised end-to-end in automated tests (needs a live Claude Web session / headless pickrem run); the web handoff chain is unit-tested via the helper seam, but the live lane remains manual.

## Goal

Live remote-lane verification of the t635_35 active-gates materialization.

## Verification Checklist

- [ ] Run `/aitask-pickrem <id>` on a throwaway task with a literal `gates: [risk_evaluated]` declaration; confirm Step 5 materializes `active_gates: []` at claim (status line `MATERIALIZED:(empty)`), the `active_gates_profile` stamp is `remote`, and the task archives at Step 10 without any manual gate append.
- [ ] Produce (or hand-craft on a branch) a pickweb completion marker carrying `"profile": "remote"` and `"profile_filename": "remote.yaml"`; run `aitask-web-merge` and confirm the Step 5 materialization sub-step runs `aitask_web_merge.sh materialize`, reports `WEBMAT_OK:MATERIALIZED:(empty)` (or NOOP on re-run), and archival proceeds cleanly.
- [ ] Sanity-check the failure stop: point a marker at a nonexistent profile file and confirm web-merge surfaces `WEBMAT_INVALID:profile-not-found` and stops before archival with the Retry / Abort-branch prompt.
