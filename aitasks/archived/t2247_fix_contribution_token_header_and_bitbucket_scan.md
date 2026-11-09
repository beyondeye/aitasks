---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [git-integration, contribution]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2235
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-08 18:16
updated_at: 2026-11-09 11:05
completed_at: 2026-11-09 11:05
---

## Origin

Spawned from t2241 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_contribution_check.sh:185-215 — every remaining GitLab curl call (fetch_issue, post_comment, add_label, list_repo_labels, has_overlap_comment) still passes "$(_gitlab_token_header)" inline, so a missing GITLAB_TOKEN sends an empty header instead of failing (die only exits the command substitution)`
- `.aitask-scripts/ci_templates/bitbucket/contribution-check-pipeline.yml:30-33 — scheduled scan fetches one unpaginated page (pagelen=50) of open issues and runs the check script on every one, so non-contribution issues get a "no fingerprint" comment and older contributions beyond 50 are missed`

## Diagnostic context

From t2241's pre-fix control in a baseline worktree of HEAD: with `GITLAB_TOKEN` unset, the old curl listing path returned exit 0 and a list. `_gitlab_token_header` calls `die`, but inside `curl --header "$(_gitlab_token_header)"` that only exits the command substitution. curl therefore runs with an empty header, and the request fails as unauthenticated, or, on a public project, succeeds anonymously, with no clear error. t2241 fixed only the listing: the new `_gitlab_rest_all_pages` computes the header once with `hdr=$(_gitlab_token_header) || return 1`. `gitlab_fetch_issue`, `gitlab_post_comment`, `gitlab_add_label`, `gitlab_list_repo_labels` and `gitlab_has_overlap_comment`, plus the same pattern in `aitask_contribution_review.sh` `review_gitlab_fetch_comments`, still use the inline form. The Bitbucket `_bitbucket_auth` uses the same pattern.

Separately, the check script posts a "no fingerprint" overlap comment on any issue it is pointed at (`main()`, the empty `target_fp_version` branch). The Bitbucket scheduled pipeline runs it on every open issue from a single `pagelen=50` request, so ordinary issues get spammed with comments, and contributions beyond the first 50 are never checked. `bitbucket_list_contribution_issues` is unpaginated too, with `pagelen=$ARG_LIMIT`. t2241 fixed the equivalent GitLab job: it now paginates with a page cap and a repeated-page check, and selects only label-or-metadata issues.

## Suggested fix

Compute each auth header once into a local with `|| return 1` before calling curl. For Bitbucket, paginate through `next` links with a page cap, filter on the `<!-- aitask-contribute-metadata` marker before invoking the check script, and add stub-based tests modelled on `tests/lib/glab_contribution_stub.sh` and `tests/test_gitlab_contribution_job.py`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T20:03:34Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-09T08:21:07Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-09T09:05:32Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:86a6f79bdfb04942

> **✅ gate:risk_evaluated** run=2026-11-09T09:05:32Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2247/risk_evaluated_2026-11-09T09:05:32Z-risk_evaluated-a1.log`
