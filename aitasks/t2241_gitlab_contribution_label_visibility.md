---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git-integration, contribution]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2235
followup_kind: risk_mitigation
created_at: 2026-11-08 15:24
updated_at: 2026-11-08 15:39
---

## Origin

Risk-mitigation ("after") follow-up for t2235, created at Step 8d after implementation landed.

## Risk addressed

GitLab may silently drop non-member labels too.

> GitLab may drop labels from non-members in the same silent way, and its listing still filters on the label · severity: medium · → mitigation: gitlab_contribution_label_visibility

## Goal

Verify GitLab label-drop behaviour for non-members and, if confirmed, make the GitLab listing and CI job identify contribution issues by metadata.

t2235 fixed this on GitHub. GitHub drops labels supplied by authors without push access; `github_list_contribution_issues` now runs a paginated scan of all open issues and keeps those with the `contribution` label OR the `<!-- aitask-contribute-metadata` block, limiting after filtering. The GitHub workflow also runs on `issues.opened`.

On GitLab the same gap probably exists but is unverified:
- `gitlab_create_issue` (`.aitask-scripts/aitask_contribute.sh`) requests the label at creation. Check whether GitLab silently ignores it when the author lacks the role needed to set labels (non-members / Guest on public projects).
- `gitlab_list_contribution_issues` (`.aitask-scripts/aitask_contribution_check.sh`) uses `glab issue list --label contribution` / `labels=contribution` on the REST path, so unlabeled contribution issues would be invisible to the overlap check and `aitask_contribution_review.sh list-issues`.
- The scheduled scan in `.aitask-scripts/ci_templates/gitlab/contribution-check-job.yml` queries `labels=contribution`, so it would never check them.

Steps:
1. Confirm the behaviour against GitLab documentation or a test project. Record the evidence in the plan.
2. If confirmed, mirror the t2235 GitHub design: list all open issues (paginated), keep label OR metadata header, and limit after filtering. Drop the label filter from the CI job's scheduled scan. Make `gitlab_create_issue` read the label back and warn, as `_github_verify_contribution_label` does.
3. Tests: reuse the stub pattern in `tests/lib/gh_contribution_stub.sh` (a glab/curl analogue), with crowding and label-dropped cases and pre-fix controls.
4. If not confirmed, record the evidence and close the task.
