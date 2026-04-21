---
Task: t605_archive_carryover_missing_desc.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
---

# Plan: t605 — Regression tests for carry-over archival + silent-mode stdout

## Context

Two related bugs were hotfixed during t597_6 archival (commit `b63a8502`):

1. **`aitask_archive.sh` missed `--desc`.** `create_carryover_task()` invoked `aitask_create.sh --batch --commit --silent` without a description; the batch validator rejects that.
2. **`aitask_create.sh --silent` leaked git commit summary to stdout.** Three `task_git commit` calls fired on the `--batch --commit` path ran without `--quiet`, so git's `[branch hash] subject\n N files changed…` output polluted stdout. A caller that did `$(aitask_create.sh --silent …)` captured a multi-line blob instead of the created filename.

The fixes are in. What's missing is regression coverage: both `tests/test_archive_carryover.sh` and `tests/test_create_silent_stdout.sh` are named in t605's acceptance criteria but don't exist.

Surprise to flag in the plan: `tests/test_archive_verification_gate.sh:375-423` already has a carry-over test (Test 6), but its stub `aitask_create.sh` accepts any args via `*) shift ;;`, so it would **not** have caught the missing `--desc`. The new test must be strict in a way the existing one isn't.

## Approach

Write two small, hermetic bash tests that follow the existing `tests/*.sh` conventions (`#!/usr/bin/env bash`, `set -e`, local `PASS/FAIL/TOTAL` + `assert_*` helpers, bare-remote + local-clone scaffolding, `run_all_tests.sh` compatible).

### Test 1 — `tests/test_archive_carryover.sh`

**Goal:** Would have caught the missing `--desc` bug. Also guards against future removals of `--desc`.

**Pattern:** reuse the setup from `tests/test_archive_verification_gate.sh:151-197` (`setup_archive_project`), but swap in a **strict** stub `aitask_create.sh` that:
- Parses `--desc` / `--desc-file` explicitly.
- **Exits 1** with a clear message if neither is present.
- Logs all received args to a tempfile so the test can introspect them.
- On success, synthesises a minimal task file and writes the path to stdout.

**Test cases:**
1. `archive --with-deferred-carryover <id>` against a manual-verification task with one deferred + one terminal item → archive succeeds (`CARRYOVER_CREATED:` emitted), stub was called with a non-empty `--desc` value.
2. Regression assertion: introspect the stub's arg-log file and `assert_contains "--desc"` — the specific bug check.
3. Carry-over seeding is preserved from the existing gate test: the deferred item appears in the new task's checklist, the terminal item doesn't. Keep this to avoid coverage loss vs. Test 6 of the gate test.

Nothing else — `test_archive_verification_gate.sh` still owns the broad gate-behavior coverage.

### Test 2 — `tests/test_create_silent_stdout.sh`

**Goal:** Would have caught the stdout leak.

**Pattern:** reuse `tests/test_draft_finalize.sh:76-154` (`setup_draft_project`) verbatim — it already provides a bare remote + local clone + `aitask_claim_id.sh --init`, which is everything `aitask_create.sh --batch --commit` needs.

**Test cases:**

1. **Silent + commit:**
   ```bash
   stdout=$(./.aitask-scripts/aitask_create.sh --batch --commit --silent \
       --name "silent_smoke" --desc "Silent smoke test" 2>/dev/null)
   ```
   Assertions:
   - Exit code 0.
   - `stdout` is exactly one line (`wc -l` says `1`, with portable trim per CLAUDE.md `wc -l` note).
   - `[[ -f "$stdout" ]]` — the single line is a real file path.
   - `grep -q "silent_smoke" "$stdout"` — sanity.

2. **Silent + commit + child:**
   Same assertions but with `--parent 1` (t1 is already seeded by `setup_draft_project`). Guards the sibling code path in `aitask_create.sh` that was also patched (child-task commit around line 1571).

3. **Non-silent control:**
   Same create without `--silent` — just asserts exit 0 and a non-empty stdout; deliberately does NOT assert one line (non-silent mode is free to print whatever). This pins the behavior difference between modes.

No draft-mode / finalize coverage — `test_draft_finalize.sh` already owns that.

## Files to create

- `tests/test_archive_carryover.sh`
- `tests/test_create_silent_stdout.sh`

Both scripts are self-contained (no edits to existing test infrastructure).

## Files to reference (do not modify)

- `tests/test_archive_verification_gate.sh` — copy the `setup_archive_project` + `assert_*` scaffolding (lines 28-197).
- `tests/test_draft_finalize.sh` — copy the `setup_draft_project` scaffolding (lines 76-154).
- `.aitask-scripts/aitask_archive.sh:549-601` — the function under test (carry-over).
- `.aitask-scripts/aitask_create.sh` around lines 1571 and 1607 — the silent-guarded commits.

## Out of scope (explicit)

- **No changes to `run_all_tests.sh`.** The existing runner auto-picks up anything matching `tests/test_*.sh`.
- **No changes to the production scripts.** The fixes are already committed; this task is tests only.
- **No tests for `--silent` without `--commit` (draft mode).** That path doesn't do a git commit, so it can't exhibit the bug; testing it would be cargo-cult coverage.

## Verification

Run the two new tests directly:

```bash
bash tests/test_archive_carryover.sh
bash tests/test_create_silent_stdout.sh
```

Both should print "All tests PASSED" and exit 0.

Then sanity-check the full suite hasn't regressed (only the two new files should have been added; nothing else was touched):

```bash
bash tests/test_archive_verification_gate.sh
bash tests/test_draft_finalize.sh
```

No regressions expected.

### Regression proof-test (one-time, discard after)

Before the commit message lands, temporarily revert `.aitask-scripts/aitask_archive.sh` to the pre-fix version locally and confirm `tests/test_archive_carryover.sh` **fails** with a clear message. Then temporarily revert `.aitask-scripts/aitask_create.sh` and confirm `tests/test_create_silent_stdout.sh` **fails** with a one-line vs. multi-line assertion mismatch. Restore both files. This is the "would have caught it" check — the single most important property of a regression test.

## Step 9 — Post-Implementation

Follow the shared task-workflow Step 9: commit the two new test files with `test: Add regression tests for carry-over + silent stdout (t605)` and let the archive script run. No branch/worktree cleanup (profile `fast` → working on main). No follow-up tasks expected.

## Final Implementation Notes

- **Actual work done:**
  - Added `tests/test_archive_carryover.sh` with 2 test groups / 13 assertions. The strict stub `aitask_create.sh` exits 1 when `--desc` / `--desc-file` is absent and writes every received argv line to `$STUB_ARG_LOG`, so the test both exercises the happy path and introspects the arg log for the specific `--desc` regression.
  - Added `tests/test_create_silent_stdout.sh` with 3 test groups / 10 assertions, driving the real `aitask_create.sh --batch --commit --silent` against a bare-remote + `aitask_claim_id.sh --init` scaffold cloned from `tests/test_draft_finalize.sh`. Asserts stdout is exactly one line (portable `wc -l`-free counter via `grep -c ''`), that the line is an existing file path, and that it contains the `--name` slug. Test 3 is a non-silent control that pins `exit 0 + non-empty` without over-constraining the non-silent contract.
  - **Bonus fix that Test 2 caught:** `update_parent_children_to_implement()` in `.aitask-scripts/aitask_create.sh:315` invoked `aitask_update.sh --batch <parent> --add-child <child>` without routing its `Updated: <file>` stdout anywhere. In `--silent` callers, that line landed in the captured stdout ahead of the real filename. Patched to `>&2 2>/dev/null` so stdout goes to stderr (still visible to humans) while pre-existing stderr suppression is preserved.

- **Deviations from plan:**
  - Plan called for 2 test files; delivered 2. Plan did not anticipate a third stdout leak site. Fixed it inline rather than punt to another task — the fix is a 1-line hygiene patch in the same file and is provably caught by the existing test, so deferring would have left `tests/test_create_silent_stdout.sh` permanently failing or over-relaxed.

- **Issues encountered:**
  - `>&2 2>/dev/null` ordering matters: `>&2` aliases fd1 to the pre-redirection fd2 (original stderr), then `2>/dev/null` points fd2 at `/dev/null`. Net: stdout → real stderr (visible), stderr → sink. That is the intent.
  - `wc -l` is portable-unsafe on macOS (leading spaces). Used `printf '%s' "$stdout" | grep -c '' | tr -d ' '` per CLAUDE.md `wc -l` note.

- **Key decisions:**
  - Kept the strict stub inside the new test file instead of extending `test_archive_verification_gate.sh`'s Test 6. The two tests have different contracts (behavioural gate vs. bug-specific regression) and merging them would dilute each.
  - Did not add a test for `--silent` without `--commit` (draft mode) — that path does no git commit, so it can't exhibit the bug; adding a test would be cargo-cult coverage.

- **Regression proof:** Verified interactively. Reverting the archive `--desc` fix → test_archive_carryover fails 8/13. Reverting all three `task_git commit` silent guards → test_create_silent_stdout fails 4/10. Restoring → both green again.
