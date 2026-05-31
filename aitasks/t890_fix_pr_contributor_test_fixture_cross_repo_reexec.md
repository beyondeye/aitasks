---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, python]
created_at: 2026-05-31 22:34
updated_at: 2026-05-31 22:34
---

## Origin

Surfaced during the t883 audit (test-fixture lib-copy drift). While checking whether other tests shared test_desync_state.py's missing-`python_resolve.sh` omission, `tests/test_pr_contributor_metadata.sh` was found to fail for a DIFFERENT missing fixture lib.

## Upstream defect

- tests/test_pr_contributor_metadata.sh:72-78 (cp block); setup_fake_aitask_repo called at tests/test_pr_contributor_metadata.sh:70 — the test's fake `.aitask-scripts/lib/` omits `.aitask-scripts/lib/cross_repo_reexec.sh`, which `aitask_ls.sh` sources.

Root cause: The test DOES fail (real exit code 1; the prior "exit 0" was the trailing echo's status, not the script's). aitask_ls.sh line 7 `source "$SCRIPT_DIR/lib/cross_repo_reexec.sh"` and line 15 `cross_repo_reexec_or_continue "aitask_ls.sh" "$@"`. The fake repo built by the test never gets cross_repo_reexec.sh: the explicit cp block (lines 72-78) copies aitask_create/claim_id/update/ls.sh plus task_utils.sh, archive_utils.sh, archive_scan.sh but NOT cross_repo_reexec.sh, and setup_fake_aitask_repo in tests/lib/test_scaffold.sh only copies aitask_path.sh, terminal_compat.sh, python_resolve.sh, yaml_utils.sh (baseline) — also not cross_repo_reexec.sh. So when Test 10 runs `bash .aitask-scripts/aitask_ls.sh -v 99`, line 7 fails with "No such file or directory", line 15 fails with "cross_repo_reexec_or_continue: command not found", aitask_ls prints its usage/help instead of the task list, and the two assert_contains checks (PR / Contributor) fail. The lib exists in the real repo (.aitask-scripts/lib/cross_repo_reexec.sh, 3255 bytes) — it is simply never copied into the fixture. Reproduced deterministically across 4 runs (not flaky). This is the exact missing-lib failure mode warned about in CLAUDE.md's Shell Conventions note. Note: cross_repo_reexec.sh is NOT (yet) in the test_scaffold baseline list, so the fix belongs in this test's own cp block (and arguably the scaffold baseline).

## Diagnostic context

Failing subtests: 2 failing subtests, both inside "Test 10: ls -v shows PR and contributor": (1) "FAIL: ls shows PR (expected output containing 'PR: https://github.com/o/r/pull/77', ...)" and (2) "FAIL: ls shows Contributor (expected output containing 'Contributor: visible_user', ...)". Script summary: "Results: 28 passed, 2 failed, 30 total / SOME TESTS FAILED". Test exit code: 1. Uses setup_fake_aitask_repo: true.

Output tail:
```
                other flag/argument.
  -h, --help    Show this help message.

METADATA FORMAT:
  The file uses YAML front matter (lines between --- markers).
  Missing properties default to 'Medium'.

    ---
    priority: high|medium|low
    effort: high|medium|low
    depends: [1, 3, 5]
    issue_type: bug|chore|documentation|enhancement|feature|performance|refactor|style|test
    status: Editing|Implementing|Postponed|Ready|Done|Folded
    labels: [ui, backend]
    assigned_to: email@example.com
    created_at: 2026-02-01 14:30
    updated_at: 2026-02-01 15:45
    ---')
--- Test 11: ls -v hides PR fields when not set ---
warning: You appear to have cloned an empty repository.
--- Test 12: Syntax check ---

===============================
Results: 28 passed, 2 failed, 30 total
SOME TESTS FAILED
```

## Suggested fix

Copy the missing lib into the fake repo. Add to the cp block in tests/test_pr_contributor_metadata.sh (after line 78): `cp "$PROJECT_DIR/.aitask-scripts/lib/cross_repo_reexec.sh" .aitask-scripts/lib/`. (Optionally also add cross_repo_reexec.sh to the baseline copy list in tests/lib/test_scaffold.sh::setup_fake_aitask_repo so every scaffolded test that invokes ./ait or aitask_ls.sh gets it, consistent with the CLAUDE.md Shell Conventions note about libs added to ait's source-on-startup chain.) Do NOT modify aitask_ls.sh — sourcing cross_repo_reexec.sh there is correct (t832_1).

(Same fixture-drift class as t883. Consider routing the fixture through `setup_fake_aitask_repo` in tests/lib/test_scaffold.sh so the lib list cannot drift again. Verify with `bash tests/test_pr_contributor_metadata.sh`.)
