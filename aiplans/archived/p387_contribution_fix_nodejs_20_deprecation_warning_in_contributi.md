---
Task: t387_contribution_fix_nodejs_20_deprecation_warning_in_contributi.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

GitHub deprecated Node.js 20 runners (Sept 2025). Starting March 2026, workflows using `actions/checkout@v4` show deprecation warnings. This task upgrades to v5 (Node 24) and syncs the missing jq install step from the seed template.

Contributed by @beyondeye (issue #9). Also merges existing task t380 which described the same fix.

## Plan

### 1. Update `.github/workflows/contribution-check.yml`

Two changes:
- **Line 16:** Change `actions/checkout@v4` → `actions/checkout@v5`
- **After line 16:** Add jq install step (syncing from seed template):
  ```yaml
      - name: Install jq
        run: command -v jq >/dev/null 2>&1 || sudo apt-get install -y jq
  ```

### 2. Update `seed/ci/github/contribution-check.yml`

One change:
- **Line 21:** Change `actions/checkout@v4` → `actions/checkout@v5`

(Seed template already has the jq install step.)

## Verification

- Confirm both files have `actions/checkout@v5`
- Confirm `.github/workflows/contribution-check.yml` now has the jq install step matching the seed template
- Compare both files to ensure they're structurally aligned (aside from seed header comments)

## Final Implementation Notes

- **Actual work done:** Exactly as planned — upgraded actions/checkout v4→v5 in both files and added missing jq install step to the live workflow (already present in seed template).
- **Deviations from plan:** None.
- **Issues encountered:** None — straightforward two-file edit.
- **Key decisions:** None — the contribution provided the exact diff to apply.
