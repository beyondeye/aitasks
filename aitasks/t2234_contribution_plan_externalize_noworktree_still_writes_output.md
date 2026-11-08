---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [contribution, worktree, workflow]
issue: https://github.com/beyondeye/aitasks/issues/15
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
created_at: 2026-11-08 09:30
updated_at: 2026-11-08 09:30
---

Issue created: 2026-08-14 00:47:52, last updated: 2026-08-14 00:48:04

## [Contribution] plan_externalize: --no-worktree still writes 'Output branch: main' into the plan header

## Contribution: plan_externalize: --no-worktree still writes 'Output branch: main' into the plan header

### Scope
bug_fix

### Motivation
Under a current-branch profile (create_worktree: false), planning.md Step 6 calls the helper with --no-worktree --profile <p>. The helper still writes 'Output branch: main' into the externalized plan's metadata header. task-workflow Step 9 and the Re-entry Routing both resolve the merge target from that header ('never from profile.output_branch'), so a resumed or Step-9 session aims at main even though the profile never asked for a worktree and the work is on another branch. In this project dev is the working branch and main is the production branch that gates deploys, so the wrong header points in-flight work at production. Observed with framework 0.32.0 on a fast-profile child task: the header had to be corrected by hand after every externalize. Expected: with --no-worktree the header should carry the current branch (or omit Output branch entirely), since the docs state --no-worktree 'clears any stale Output branch already present in a plan's frontmatter' - it clears, then writes main.

### Proposed Merge Approach
In the --no-worktree path, set Output branch to the resolved base/current branch rather than defaulting to main; or omit the field so Step 9's documented two-rung rule falls back explicitly rather than being handed a wrong value.

### Framework Version
0.32.0

### Changed Files

| File | Status |
|------|--------|
| `.aitask-scripts/aitask_plan_externalize.sh` | Modified |

### Code Changes


<!-- aitask-contribute-metadata
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
based_on_version: 0.32.0
fingerprint_version: 1
areas: scripts
file_paths: .aitask-scripts/aitask_plan_externalize.sh
file_dirs: .aitask-scripts
change_type: bug_fix
auto_labels: area:scripts,scope:bug_fix
-->
## Comments

**github-actions** (2026-08-14 00:48:04)

## Contribution Overlap Analysis

No overlapping contribution issues found for #15.

<!-- overlap-results overlap_check_version: 1 -->
