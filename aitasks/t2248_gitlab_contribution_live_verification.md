---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [git-integration, contribution]
anchor: 2235
followup_kind: risk_mitigation
created_at: 2026-11-08 18:20
updated_at: 2026-11-08 18:20
---

## Origin

Risk-mitigation ("after") follow-up for t2241, created at Step 8d after implementation landed.

## Risk addressed

The drop and the glab --paginate/:id behaviour were not tested on a live GitLab.

> The drop was proved from GitLab source and docs but not on a live GitLab. The output of glab's `:id` placeholder and `--paginate` is taken from `glab api --help` (1.126) and the stubs, not from a real server · severity: medium · → mitigation: gitlab_contribution_live_verification

> The CI job's runtime is Alpine with BusyBox ash and BusyBox date, not the test host. The inherited `date -d '6 hours ago'` cutoff fails there, which is now fixed with jq. A BusyBox-modelling `date` stub, a POSIX-shell run and a pre-fix control cover this on the host. Only the live run proves it in the real image · severity: medium · → mitigation: gitlab_contribution_live_verification

## Goal

Confirm on a real GitLab project and the real `alpine:latest` runtime what t2241 proved from GitLab source and host-side stubs. Use a test project where you are a maintainer, plus a second account that is **not** a member of it.

## Verification Checklist

- [ ] As the non-member account, run `/aitask-contribute` against the test project: the issue is created, GitLab drops the `contribution` label, and `aitask-contribute` prints the "GitLab did not apply the 'contribution' label … not members … silently dropped" warning
- [ ] As a member (Guest or higher), create a contribution issue: the label is kept and no warning is printed
- [ ] In a checkout of the test project with `glab` authenticated (no `--repo`), `./.aitask-scripts/aitask_contribution_review.sh list-issues` lists the unlabeled contribution with `HAS_METADATA:true`, which confirms that `glab api --paginate projects/:id/issues` resolves `:id` and that its output parses
- [ ] With `GITLAB_TOKEN` set and `--repo <group/project>` (curl path), `./.aitask-scripts/aitask_contribution_check.sh <iid> --platform gitlab --repo <group/project> --dry-run` scores the unlabeled contribution against other contributions
- [ ] Run `docker run --rm alpine:latest sh -c 'apk add -q jq && jq -nr "now - 21600 | strftime(\"%Y-%m-%dT%H:%M:%SZ\")"'`: it prints a UTC timestamp 6 hours in the past
- [ ] Install the job from `.aitask-scripts/ci_templates/gitlab/contribution-check-job.yml` in the test project and trigger a scheduled pipeline: the log shows `--- Checking issue #<iid> ---` for the unlabeled contribution, no ordinary issue is checked, and no `date` error appears
