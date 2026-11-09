---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git-integration, contribution]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2235
followup_kind: upstream_defect
created_at: 2026-11-09 22:33
updated_at: 2026-11-09 22:55
---

## Origin

Spawned from t2252 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_contribution_check.sh:181 — github_list_repo_labels reads only the first 200 repository labels (gh label list --limit 200); an auto-applicable area:/scope: label past them is never applied (no duplicate risk)`

## Diagnostic context

t2252 made the GitLab side of the contribution check read every page of
repository labels. `gitlab_list_repo_labels` now uses
`glab api --paginate "projects/:id/labels?per_page=100"` on the glab path
(`glab label list` printed only one page of 30) and `_gitlab_rest_all_pages` on
REST. The GitHub counterpart, `github_list_repo_labels`, still caps at
`gh label list --limit 200`.

`main()` applies a contribution's `auto_labels` only when the label already
exists in the repository. It checks this against that list, so in a repository
with more than 200 labels an `area:`/`scope:` label that sorts past the cap is
silently not applied. The worst case is a missing auto-label, never a duplicate
comment. That is why t2252 kept it out of scope.

## Suggested fix

Read every label, for example with
`gh api --hostname <host> --paginate "repos/<nwo>/labels?per_page=100"` (resolve
host/nwo the way `github_list_contribution_issues` does, for GitHub
Enterprise). Read the pages with `jq -s 'add // [] | .[].name'`, and keep the
caller's all-or-nothing behaviour. Extend `tests/lib/gh_contribution_stub.sh`
with a >200-label fixture, and add a pre-fix control showing the label past the
cap is missed today.
