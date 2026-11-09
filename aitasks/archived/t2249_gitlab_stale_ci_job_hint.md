---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [git-integration, contribution]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2235
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-11-08 18:20
updated_at: 2026-11-09 15:41
completed_at: 2026-11-09 15:41
---

## Origin

Risk-mitigation ("after") follow-up for t2241, created at Step 8d after implementation landed.

## Risk addressed

Existing installs keep the label-filtered scheduled scan.

> Existing GitLab installs keep their copied `.gitlab-ci.yml` job, which `ait setup` never edits, so their scheduled scan still filters on the label until the job is copied again · severity: medium · → mitigation: gitlab_stale_ci_job_hint

## Goal

`ait setup` (`_install_contribution_ci_workflow` in `.aitask-scripts/aitask_setup.sh`, gitlab branch) writes `.aitask-scripts/ci_templates/gitlab/contribution-check-job.yml` only when no `.gitlab-ci.yml` exists, and it never edits an existing file. A project that copied the job before t2241 therefore still has a broken scheduled scan:
- it queries `labels=contribution`, which misses contributions from non-members, whose labels GitLab silently drops;
- its cutoff comes from `date -d '6 hours ago'` / `date -v-6H`, which BusyBox date on `alpine:latest` rejects.

When an existing `.gitlab-ci.yml` contains a `contribution-check:` job whose scheduled scan still carries either marker (`labels=contribution&updated_after`, or `date -u -d '6 hours ago'`), setup should print a warning. The warning should say that the job predates the current template, name both effects, and point to the template path and the Manual Setup section of `website/content/docs/workflows/contribute-and-manage/contribution-flow.md`. Setup must still never modify the file.

Tests in `tests/test_setup_contribution_workflow.sh`:
- an existing file with the old job warns;
- an existing file with the current template job does not;
- an unrelated `.gitlab-ci.yml` does not;
- the file is byte-identical after setup in all three cases.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-09T08:47:38Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-09T13:33:23Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-09T13:41:17Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:92489ece7981d1ab

> **✅ gate:risk_evaluated** run=2026-11-09T13:41:17Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2249/risk_evaluated_2026-11-09T13:41:17Z-risk_evaluated-a1.log`
