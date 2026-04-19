---
Task: t583_6_issue_type_manual_verification_and_unit_tests.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 15:05
---

# Plan: t583_6 — `manual_verification` Issue Type + Follow-up Helper Tests

## Context

Register the new `manual_verification` issue type in both the live and seed task_types lists, and add the remaining missing unit tests from the t583 family — tests for the `aitask_verification_followup.sh` helper delivered by t583_3.

**Scope reduction since the original task description (verified at plan time):**

- `tests/test_verification_parse.py` already exists (31 passing tests, delivered with t583_1). Per t583_1's Final Implementation Notes, t583_6 "should not duplicate parser-level tests." This plan drops that deliverable.
- `tests/test_verifies_field.sh` already exists (13 passing tests, delivered with t583_2). This plan drops that deliverable.
- Only `tests/test_verification_followup.sh` remains to write.
- The seed `task_types.txt` actually lives at `seed/task_types.txt` (flat under `seed/`), not at the `seed/aitasks/metadata/task_types.txt` path written in the task description.

## Files to modify / create

**Modify:**
- `aitasks/metadata/task_types.txt` — append `manual_verification`
- `seed/task_types.txt` — append `manual_verification` (mirror)

**New:**
- `tests/test_verification_followup.sh`

**Out of scope (already covered):**
- `tests/test_verification_parse.py` — covers `aitask_verification_parse.sh` (31 tests, t583_1)
- `tests/test_verifies_field.sh` — covers `verifies:` 3-layer propagation (13 tests, t583_2)

## Helper CLI surface (verified at plan time)

### `aitask_verification_followup.sh`

```
aitask_verification_followup.sh --from <task_id> --item <index> [--origin <feature_task_id>]
```

Structured output:
- `FOLLOWUP_CREATED:<new_id>:<path>` on success (exit 0)
- `ORIGIN_AMBIGUOUS:<csv>` when `--origin` omitted and `verifies:` has 2+ entries (exit 2)
- `ERROR:<message>` on failure (exit 1)

Behavior used in tests:
- Uses `verifies:` frontmatter on the `--from` task to resolve origin. If empty and no `--origin`, uses `--from` as origin.
- Resolves commits via `git log --oneline --grep "(t<origin>)"`; extracts touched files via `git show --name-only --format=`.
- Appends a back-reference line under the origin's archived plan's `## Final Implementation Notes` (creates section if missing).
- Creates the follow-up task with `issue_type: bug`, a `related: [<origin>]` field, and the failing item's prose copy-pasted into the description.

## Implementation

### 1. Register `manual_verification` issue type

Append a single line `manual_verification` to both:
- `aitasks/metadata/task_types.txt`
- `seed/task_types.txt`

No re-ordering. Other scripts read these files as a flat newline-separated list.

### 2. `tests/test_verification_followup.sh`

Follow the style of `tests/test_verifies_field.sh` and `tests/test_claim_id.sh`:

- `#!/usr/bin/env bash`, `set -e`, shared `assert_eq` / `assert_contains` helpers.
- `PASS`/`FAIL`/`TOTAL` counters; summary at the bottom.
- `setup_project()` creates a temp git repo, copies in the scripts this test touches (minimum: `.aitask-scripts/aitask_verification_followup.sh`, `aitask_verification_parse.sh`, `aitask_verification_parse.py`, `aitask_create.sh`, `aitask_update.sh`, `aitask_resolve_child.sh`, `lib/task_utils.sh`, `lib/terminal_compat.sh`, plus any others the followup script transitively calls). Check `test_verifies_field.sh` `setup_project()` for the current list; mirror it and add anything the followup helper pulls in via `source` / path refs.
- `trap teardown_all EXIT` with `CLEANUP_DIRS` array (same pattern as `test_verifies_field.sh`).
- `git config user.email` + `user.name` inside the temp repo so commits succeed.

**Test cases (aim for ~8-10 assertions across ~5 cases):**

1. **Happy path — single verifies, auto-resolve origin.**
   - Seed a feature task `t42_foo.md` with a commit `feature: do a thing (t42)` touching `src/foo.py`.
   - Create a manual-verification task `t99_manual.md` with `verifies: [42]`, `issue_type: manual_verification`, and a `## Verification Checklist` section containing one item, then `set <file> 1 fail --note "button broken"`.
   - Run `aitask_verification_followup.sh --from 99 --item 1`.
   - Assert: exit code 0; stdout contains `FOLLOWUP_CREATED:<new_id>:<path>`.
   - Read the newly-created bug task; assert it contains the failing item text, a `related: [42]` (or equivalent) frontmatter entry, and a reference to the `src/foo.py` touched file and/or the commit hash.

2. **Ambiguous origin — 2+ verifies, no `--origin`.**
   - Manual-verification task with `verifies: [42, 43]` and one failed item.
   - Run `aitask_verification_followup.sh --from 99 --item 1`.
   - Assert: exit code 2; stdout contains `ORIGIN_AMBIGUOUS:42,43` (order may vary — use `assert_contains` on each id).

3. **Explicit `--origin` resolves ambiguity.**
   - Same fixture as (2). Run `... --from 99 --item 1 --origin 42`.
   - Assert: exit code 0; `FOLLOWUP_CREATED:` present; follow-up task's `related:` references 42, not 43.

4. **Back-reference appended to archived plan.**
   - Create a minimal archived plan `aiplans/archived/p42_foo.md` with a `## Final Implementation Notes` section containing one placeholder line.
   - Run the happy-path followup.
   - After success, `cat` the archived plan and assert it now contains an extra line under `## Final Implementation Notes` mentioning the follow-up task id.

5. **Back-reference creates the section when missing.**
   - Same as (4) but the archived plan has no `## Final Implementation Notes` section.
   - After followup, the archived plan contains the section with the back-reference line.

**Skip (not required for this slice):** empty `verifies:` + no `--origin` → falls back to `--from` as origin. This is a degenerate case; if it proves trivial to cover alongside (1), include it as a short sixth case.

**Expected runtime:** <5s (all local fs + git, no network).

## Verification

```bash
bash tests/test_verification_followup.sh        # all PASS
shellcheck tests/test_verification_followup.sh  # no warnings
grep manual_verification aitasks/metadata/task_types.txt  # match
grep manual_verification seed/task_types.txt             # match
```

Also run the two already-passing siblings as regression checks (fixture overlap):

```bash
python3 -m unittest tests.test_verification_parse   # 31 tests, should still pass
bash tests/test_verifies_field.sh                    # 13 tests, should still pass
```

## Step 9 reminder

Commit (code + test files): `test: Add manual-verification followup tests and register issue type (t583_6)`.

Plan file commit (if revised here): `ait: Update plan for t583_6`.

## Final Implementation Notes

- **Actual work done:** Appended `manual_verification` to `aitasks/metadata/task_types.txt` and `seed/task_types.txt`. Wrote `tests/test_verification_followup.sh` exercising the followup helper across 5 cases + a syntax check — 28 assertions total, all passing. First-pass pass rate; no test fixture revisions needed.
- **Deviations from plan:** Bug task asserts use `depends: [N]` (the helper passes the origin via `--deps`, which lands in the `depends:` frontmatter) rather than the plan's speculative `related: [N]` — the helper does not emit a `related:` field. Back-reference heading-count check was added to case (4) to guard against accidental section duplication when Final Implementation Notes already exists. Seed path corrected from the stale task-description path (`seed/aitasks/metadata/task_types.txt`) to the actual flat `seed/task_types.txt` at plan time.
- **Issues encountered:** The `aitask_create.sh --commit` path used by the followup helper requires the atomic-ID counter branch (`aitask-ids`) to be initialized in the test env. Added `aitask_claim_id.sh --init` to `setup_project()` alongside copying `aitask_claim_id.sh` + `lib/archive_scan.sh` into the test repo. Without this the bug-task creation failed in batch mode with "Atomic ID counter failed".
- **Key decisions:**
  - Test env setup copies the minimal transitive script closure (`aitask_verification_followup.sh`, `aitask_verification_parse.{sh,py}`, `aitask_create.sh`, `aitask_update.sh`, `aitask_claim_id.sh`, `aitask_fold_mark.sh`, + `lib/{terminal_compat,task_utils,archive_utils,archive_scan}.sh`). Mirrors `test_verifies_field.sh` plus the claim_id chain needed for `--commit`.
  - Bare-remote + local-clone pattern (same as `test_verifies_field.sh` and `test_claim_id.sh`) so `task_push` / `git push` inside the helper don't fail noisily.
  - `./ait` is absent in the test env, so the helper's `./ait git add/commit` back-reference commit silently no-ops (`2>/dev/null || true`). The file mutation still happens, which is what the tests assert on.
- **Notes for sibling tasks:**
  - `tests/test_verification_parse.py` (31 tests, t583_1) and `tests/test_verifies_field.sh` (13 tests, t583_2) are the authoritative coverage for the parser and `verifies:` field; t583_6 does not duplicate them.
  - The followup helper stores the origin as a `depends:` entry on the new bug task (via `aitask_create.sh --deps`). If t583_7 or later adds a distinct `related:` concept, update both the helper and this test.
  - The bare-remote + claim-id init pattern used here is the canonical way to exercise `aitask_create.sh --commit` from a test. Reuse it when adding further integration tests against the create pipeline.
