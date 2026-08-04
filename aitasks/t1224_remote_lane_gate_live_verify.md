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
updated_at: 2026-08-04 12:35
boardidx: 31744
---

## Origin

Risk-mitigation ("after") follow-up for t635_35, created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement: the full remote/web lane cannot be exercised end-to-end in automated tests (needs a live Claude Web session / headless pickrem run); the web handoff chain is unit-tested via the helper seam, but the live lane remains manual.

## Goal

Live remote-lane verification of the t635_35 active-gates materialization.

## Verification Checklist

- [x] Run `/aitask-pickrem <id>` on a throwaway task with a literal `gates: [risk_evaluated]` declaration; confirm Step 5 materializes `active_gates: []` at claim (status line `MATERIALIZED:(empty)`), the `active_gates_profile` stamp is `remote`, and the task archives at Step 10 without any manual gate append. — PASS 2026-08-04 12:35 auto: probe t1406 (gates: [risk_evaluated]); pickrem Step 5 command materialize-active --profile remote.yaml => MATERIALIZED:(empty); wrote active_gates: [], active_gates_filtered: [risk_evaluated], active_gates_profile: remote; bash+python 'active' readers both exit 1; archived exit 0 with no gate append. Negative control: pre-materialize archive-ready = BLOCKED:risk_evaluated. Step 5/Step 10 wiring source-verified; live pickrem agent loop not driven.
- [x] Produce (or hand-craft on a branch) a pickweb completion marker carrying `"profile": "remote"` and `"profile_filename": "remote.yaml"`; run `aitask-web-merge` and confirm the Step 5 materialization sub-step runs `aitask_web_merge.sh materialize`, reports `WEBMAT_OK:MATERIALIZED:(empty)` (or NOOP on re-run), and archival proceeds cleanly. — PASS 2026-08-04 12:35 auto: probe t1407 + hand-crafted marker (profile=remote, profile_filename=remote.yaml); aitask_web_merge.sh materialize => WEBMAT_OK:MATERIALIZED:(empty), re-run => WEBMAT_OK:NOOP:unchanged; tuple FRESH / ACTIVE empty / PROFILE remote; archive-ready NO_GATES; attribution + archive exit 0.
- [x] Sanity-check the failure stop: point a marker at a nonexistent profile file and confirm web-merge surfaces `WEBMAT_INVALID:profile-not-found` and stops before archival with the Retry / Abort-branch prompt. — PASS 2026-08-04 12:35 auto: same probe t1407, marker pointed at no_such_profile.yaml => WEBMAT_INVALID:profile-not-found exit 1; tuple left ABSENT, archive-ready still BLOCKED:risk_evaluated, and aitask_archive.sh refused with GATE_PENDING:risk_evaluated exit 2 (genuinely stops before archival). Retry/Abort-branch prompt is agent-side, source-verified in materialize-gates.md.
