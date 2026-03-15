---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [contribution]
folded_tasks: [380]
assigned_to: dario-e@beyond-eye.com
issue: https://github.com/beyondeye/aitasks/issues/9
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-15 14:09
updated_at: 2026-03-15 14:30
completed_at: 2026-03-15 14:30
---

Issue created: 2026-03-14 21:59:18, last updated: 2026-03-14 21:59:31

## [Contribution] Fix Node.js 20 deprecation warning in contribution-check workflow

## Contribution: Fix Node.js 20 deprecation warning in contribution-check workflow

### Scope
bug_fix

### Motivation
GitHub deprecated Node.js 20 runners (Sept 2025). Starting March 2026, workflows using actions/checkout@v4 show deprecation warnings. This upgrades to v5 (Node 24) and syncs the missing jq install step from the seed template.

### Proposed Merge Approach
clean merge

### Framework Version
0.10.0

### Changed Files

| File | Status |
|------|--------|
| `.github/workflows/contribution-check.yml` | Modified |
| `seed/ci/github/contribution-check.yml` | Modified |

### Code Changes

#### `.github/workflows/contribution-check.yml`

```diff
--- c/.github/workflows/contribution-check.yml
+++ w/.github/workflows/contribution-check.yml
@@ -13,7 +13,10 @@ jobs:
     if: github.event.label.name == 'contribution'
     runs-on: ubuntu-latest
     steps:
-      - uses: actions/checkout@v4
+      - uses: actions/checkout@v5
+
+      - name: Install jq
+        run: command -v jq >/dev/null 2>&1 || sudo apt-get install -y jq
 
       - name: Check for overlapping contributions
         run: |
```

#### `seed/ci/github/contribution-check.yml`

```diff
--- c/seed/ci/github/contribution-check.yml
+++ w/seed/ci/github/contribution-check.yml
@@ -18,7 +18,7 @@ jobs:
     if: github.event.label.name == 'contribution'
     runs-on: ubuntu-latest
     steps:
-      - uses: actions/checkout@v4
+      - uses: actions/checkout@v5
 
       - name: Install jq
         run: command -v jq >/dev/null 2>&1 || sudo apt-get install -y jq
```


<!-- aitask-contribute-metadata
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
based_on_version: 0.10.0
fingerprint_version: 1
areas: unknown
file_paths: .github/workflows/contribution-check.yml,seed/ci/github/contribution-check.yml
file_dirs: .github/workflows,seed/ci/github
change_type: bug_fix
auto_labels: area:unknown,scope:bug_fix
-->
## Comments

**github-actions** (2026-03-14 21:59:31)

## Contribution Overlap Analysis

| Issue | Score | Overlap | Detail |
|-------|-------|---------|--------|
| [#7](https://github.com/beyondeye/aitasks/issues/7) | 1 (low) | [Contribution] Add missing satisfaction rating in aitask-explore 'Save for later' path | change_type- bug_fix (+1) |
| [#6](https://github.com/beyondeye/aitasks/issues/6) | 1 (low) | [Contribution] Fix incorrect skill name in contribute workflow output | change_type- bug_fix (+1) |

<!-- overlap-results top_overlaps: 7:1,6:1 overlap_check_version: 1 -->

## Merged from t380: nodejs warning when running contribution check

currently we have a github action contribution-check.ynl that trigger a warning:

fix this warning, and after the fix, update the copy of the contribution check workflow is seed/ci/github

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t380** (`t380_nodejs_warning_when_running_contribution_check.md`)
