---
Task: t321_6_contribute_multiplatform_support.md
Parent Task: aitasks/t321_removeautoupdatefromdocsorimplement.md
Sibling Tasks: aitasks/t321/t321_1_*.md .. t321_5_*.md (all archived)
Archived Sibling Plans: aiplans/archived/p321/p321_*_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t321_6 — Contribute Multi-Platform Support

## Context

The aitask-contribute skill and `aitask_contribute.sh` script currently only support GitHub (via `gh` CLI) for creating contribution issues. The aitasks framework already has established multi-platform patterns (GitHub, GitLab, Bitbucket) in `aitask_issue_update.sh`, `aitask_pr_import.sh`, and `aitask_issue_import.sh` with platform backend functions, dispatcher functions, and auto-detection. This task extends `aitask_contribute.sh` to follow the same patterns.

## Steps

### 1. Add platform backend functions to `aitask_contribute.sh`

Add a `PLATFORM BACKENDS` section (following `aitask_issue_update.sh` pattern) with:

**CLI checks:** `github_check_cli()`, `gitlab_check_cli()`, `bitbucket_check_cli()`
**Issue creation:** `github_create_issue()`, `gitlab_create_issue()`, `bitbucket_create_issue()`
**Contributor resolution:** `github_resolve_contributor()`, `gitlab_resolve_contributor()`, `bitbucket_resolve_contributor()`
**Upstream URL construction:** `github_upstream_url()`, `gitlab_upstream_url()`, `bitbucket_upstream_url()`

### 2. Add dispatcher functions

`source_check_cli()`, `source_create_issue()`, `source_resolve_contributor()`, `source_upstream_url()` — all dispatch on `CONTRIBUTE_PLATFORM`.

### 3. Add `--source` flag and platform detection

- Add `ARG_SOURCE=""` and `--source` to `parse_args()` with validation
- Platform resolved in `main()`: `--source` value → default `github`

### 4. Update existing functions

- `fetch_upstream_file()`: use `source_upstream_url()` instead of hardcoded GitHub URL
- `create_issue()`: use `source_create_issue()` dispatcher
- `resolve_contributor()`: use `source_resolve_contributor()` with git config fallback
- CLI check in `main()`: `source_check_cli()` replaces `command -v gh`

### 5. Update SKILL.md

- Description, Step 1 prereqs, Notes section — all platform-neutral

### 6. Update documentation

- `website/content/docs/skills/aitask-contribute.md` — multi-platform mentions
- `website/content/docs/workflows/contribute-and-manage.md` — platform-neutral references

### 7. Update tests

5 new tests (Tests 12-16), 14 new assertions, totaling 16 tests / 45 assertions.

## Key Files

- `.aitask-scripts/aitask_contribute.sh`
- `.claude/skills/aitask-contribute/SKILL.md`
- `tests/test_contribute.sh`
- `website/content/docs/skills/aitask-contribute.md`
- `website/content/docs/workflows/contribute-and-manage.md`

## Final Implementation Notes

- **Actual work done:** Added 12 platform backend functions (4 operations x 3 platforms), 4 dispatcher functions, `--source` flag with validation, and updated 5 files. Tests expanded from 11/31 to 16/45.
- **Deviations from plan:** The success message in `main()` was kept as-is (platform-neutral wording was already acceptable). The `--source` short flag `-S` was added (matching `aitask_issue_update.sh` pattern). The CLI check was moved after `--dry-run` exit so dry-runs don't require platform CLI tools.
- **Issues encountered:** None. The existing `AITASK_CONTRIBUTE_UPSTREAM_DIR` mock in tests allowed all platform dry-run tests to work offline without `glab`/`bkt`.
- **Key decisions:** Platform defaults to `github` when `--source` is not specified (since the primary upstream is GitHub). Bitbucket contributor resolution always falls back to git config (no simple user API). CLI check runs only when actually creating issues (not for `--dry-run`, `--list-areas`, `--list-changes`).
- **Notes for sibling tasks:** This is the final child task (t321_6) — no subsequent siblings.

## Step 9 Reference
Post-implementation: archive task via task-workflow Step 9.
