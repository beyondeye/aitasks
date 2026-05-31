---
Task: t890_fix_pr_contributor_test_fixture_cross_repo_reexec.md
Base branch: main
plan_verified: []
---

## Context

`bash tests/test_pr_contributor_metadata.sh` fails (28 passed, 2 failed, exit 1) — reproduced deterministically. Both failing subtests are inside "Test 10: ls -v shows PR and contributor".

**Root cause:** Test 10 runs `bash .aitask-scripts/aitask_ls.sh -v 99`, but `aitask_ls.sh:7` does `source "$SCRIPT_DIR/lib/cross_repo_reexec.sh"` and `:15` calls `cross_repo_reexec_or_continue`. The fake repo the test builds never receives `cross_repo_reexec.sh`:
- `setup_fake_aitask_repo()` (`tests/lib/test_scaffold.sh:13`) copies only `aitask_path.sh`, `terminal_compat.sh`, `python_resolve.sh`, `yaml_utils.sh`.
- the test's own cp block (`tests/test_pr_contributor_metadata.sh:72-78`) adds `aitask_create/claim_id/update/ls.sh` + `task_utils.sh`, `archive_utils.sh`, `archive_scan.sh` — but not `cross_repo_reexec.sh`.

So `source` fails, `cross_repo_reexec_or_continue` is "command not found", `aitask_ls.sh` prints its usage/help instead of the task list, and the two `assert_contains` checks (PR / Contributor) fail. This is the exact missing-fixture-lib failure class CLAUDE.md's Shell Conventions note warns about (same class as t883).

**Blast-radius findings (why the baseline fix is the right home):**
- `cross_repo_reexec.sh` is a **startup-chain system lib**, sourced unconditionally by 3 command scripts: `aitask_ls.sh`, `aitask_query_files.sh`, `aitask_find_by_file.sh`.
- Its **only** dependency is `terminal_compat.sh`, which is *already* in the scaffold baseline → adding it to the baseline cannot introduce a new missing-dep.
- CLAUDE.md Shell Conventions explicitly mandates that libs added to `ait`'s source-on-startup chain also be added to `setup_fake_aitask_repo()`. `cross_repo_reexec.sh` qualifies but was never added.

## Recommended approach: fix the scaffold baseline (root-cause, prevents drift)

`test_pr_contributor_metadata.sh:70` already calls `setup_fake_aitask_repo "$PWD"`, so adding the lib to the baseline fixes this test **and** closes the same latent gap for every other scaffolded test that copies `aitask_ls.sh` / `aitask_query_files.sh` / `aitask_find_by_file.sh`, and stops the lib list drifting again.

### Change 1 — `tests/lib/test_scaffold.sh`
In `setup_fake_aitask_repo()`, after the `yaml_utils.sh` copy (line 21), add:
```bash
# cross_repo_reexec.sh is sourced at startup by aitask_ls.sh,
# aitask_query_files.sh, and aitask_find_by_file.sh; its only dep
# (terminal_compat.sh) is already copied above.
cp "$PROJECT_DIR/.aitask-scripts/lib/cross_repo_reexec.sh" "$repo_dir/.aitask-scripts/lib/"
```

### Change 2 — `CLAUDE.md` (Shell Conventions, baseline note)
Update the "Current baseline:" line so the doc matches reality. It currently reads `aitask_path.sh, terminal_compat.sh, python_resolve.sh` but omits the already-present `yaml_utils.sh`. Update to: `aitask_path.sh`, `terminal_compat.sh`, `python_resolve.sh`, `yaml_utils.sh`, `cross_repo_reexec.sh`.

**Do NOT** modify `aitask_ls.sh` — sourcing `cross_repo_reexec.sh` there is correct (t832_1).

## Alternative considered (rejected)
Add the `cp` only to `test_pr_contributor_metadata.sh`'s own cp block (the task's primary suggestion). Rejected as the sole fix because it is narrower: it patches one test but leaves the same latent gap in other scaffolded tests and does nothing to prevent recurrence. Since `cross_repo_reexec.sh` is a startup-chain system lib (not a test-specific helper) and its only dep is already in the baseline, the baseline is its correct home per CLAUDE.md.

## Verification
1. `bash tests/test_pr_contributor_metadata.sh` → expect `30 passed, 0 failed` (was 28/2).
2. Regression sweep of other scaffolded tests touching the source-chain scripts:
   `bash tests/test_query_files_cross_repo.sh`, `bash tests/test_xdeps_blocking.sh`, `bash tests/test_xdeps_parser.sh`, `bash tests/test_draft_finalize.sh`, `bash tests/test_create_silent_stdout.sh` → all PASS.
3. `shellcheck tests/lib/test_scaffold.sh` → clean.

## Step 9 (Post-Implementation)
Single-task fix on the current branch. After commit + review approval, archive via `./.aitask-scripts/aitask_archive.sh 890` and `./ait git push`.
