---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tests]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-30 11:56
updated_at: 2026-04-30 14:31
boardidx: 80
---

## Origin

Spawned from t723 during Step 8b review.

## Upstream defect

`tests/test_archive_verification_gate.sh` and `tests/test_archive_carryover.sh` — these tests exercise `aitask_verification_parse.sh` (and `aitask_archive.sh` which calls it), but their `setup_paired_repos()` helpers do not copy the following framework lib files into the test fixture:

- `.aitask-scripts/lib/aitask_path.sh`
- `.aitask-scripts/lib/python_resolve.sh`

`aitask_verification_parse.sh:5` sources both. The tests die with `lib/aitask_path.sh: No such file or directory`, producing 15 failures in `test_archive_verification_gate.sh` and 4 in `test_archive_carryover.sh`. They were failing before t723 too — surfaced incidentally during t723's regression sweep.

## Diagnostic context

t723 added a new sourced helper (`lib/pid_anchor.sh`) and had to update 9 test setup files to copy it. While doing that, I noticed two test files that were ALREADY failing for the same class of reason — a previously-added lib helper sourced by `aitask_verification_parse.sh` had never been added to those test setups. Pattern is: any new lib helper sourced by a script needs to be added to the copy-list of every test that exercises that script. Easy to miss; happened at least twice in the codebase.

## Suggested fix

1. Add the two missing `cp` lines to `setup_paired_repos()` in both failing tests:
   ```bash
   cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" .aitask-scripts/lib/
   cp "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" .aitask-scripts/lib/
   ```
2. Audit all `tests/test_*.sh` files: for each `cp` of a script, ensure all `source` lines in that script are matched by a corresponding lib `cp`. A small linter could automate this — for each test file, parse `cp` lines for scripts, transitively follow `source` lines, and emit a warning if any sourced lib isn't copied.
3. Consider extracting a shared `_copy_framework_files()` helper that pulls in the canonical set of lib files in one call, so adding a new lib helper only touches one place.
