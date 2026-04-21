---
Task: t619_fix_manual_verification_wrapper_double_seed.md
Base branch: main
plan_verified: []
---

# Plan: t619 — Fix manual-verification wrapper double-seed bug

## Context

`.aitask-scripts/aitask_create_manual_verification.sh` always fails at its
final seed step. The wrapper pre-writes the literal `## Verification
Checklist` header into the task description, then calls
`aitask_verification_parse.sh seed`, which refuses to run because a
checklist section already exists. Result: the task file gets created and
committed with an empty checklist, and the wrapper exits 1. Recovering
requires manually deleting the stub header and re-seeding.

The bug was introduced in commit `aae0a65d` (t583_7). No test covers this
wrapper, which is why the regression went latent.

Observed in the wild on 2026-04-21 during `/aitask-pick 617`, when the
wrapper created `t618` then errored. Since the wrapper is called from
both `planning.md` (aggregate-sibling mode, `--parent`) and
`manual-verification-followup.md` (follow-up mode, `--related`), both
code paths are broken.

## Root cause (confirmed in code)

`.aitask-scripts/aitask_create_manual_verification.sh:106`:

```bash
printf '## Verification Checklist\n'     # ← bug
```

is inside the description body that gets passed to `aitask_create.sh`
via `--desc-file`. The subsequent seed call at line 154 invokes
`cmd_seed` in `.aitask-scripts/aitask_verification_parse.py:254–258`:

```python
if _locate_section(body) is not None:
    _die("verification checklist section already exists")
```

`cmd_seed` itself appends the `## Verification Checklist` header plus a
surrounding blank line (lines 272–276), so the wrapper's pre-staged
header is redundant **and** fatal.

## Fix

Remove the single offending line from the wrapper. The seed call will
then find no existing section, append the header, and append the items.

**File:** `.aitask-scripts/aitask_create_manual_verification.sh`

**Change:** Delete line 106 (`printf '## Verification Checklist\n'`).

No trailing-whitespace cleanup is required: `cmd_seed` strips trailing
empty lines from the body before appending (python lines 270–271).

No other callers or scripts change. The behaviour after the fix matches
what the wrapper was always intended to produce.

## Regression test

Add `tests/test_create_manual_verification.sh` modelled on
`tests/test_verification_followup.sh` (same fixtures, same `setup_project`
shape, same assert helpers). Cases:

1. **Happy path (`--related`):** Run the wrapper with a 2-item items
   file against an existing seeded task. Assert:
   - Exit 0.
   - stdout ends with `MANUAL_VERIFICATION_CREATED:<id>:<path>`.
   - Task file exists.
   - Task body contains exactly **one** `## Verification Checklist`
     heading.
   - Task body contains one `- [ ] <item>` line per input bullet, with
     matching text.
   - Task frontmatter has `issue_type: manual_verification`.
2. **Empty items file:** Run the wrapper with an items file containing
   only blank lines. Assert:
   - Non-zero exit.
   - stdout contains `ERROR:aitask_verification_parse.sh seed failed`
     (the wrapper's own error prefix — `cmd_seed` emits
     `items file is empty (after skipping blank lines)` which gets
     discarded to `/dev/null 2>&1` at line 154, so the wrapper's
     fallback error message is what the user sees).

Minimum scripts/libs to copy into the temp project (mirrors
`test_verification_followup.sh` list):

- `.aitask-scripts/aitask_create_manual_verification.sh` (the subject)
- `.aitask-scripts/aitask_create.sh`
- `.aitask-scripts/aitask_update.sh`
- `.aitask-scripts/aitask_claim_id.sh`
- `.aitask-scripts/aitask_fold_mark.sh`
- `.aitask-scripts/aitask_verification_parse.sh`
- `.aitask-scripts/aitask_verification_parse.py`
- `.aitask-scripts/lib/terminal_compat.sh`
- `.aitask-scripts/lib/task_utils.sh`
- `.aitask-scripts/lib/archive_utils.sh`
- `.aitask-scripts/lib/archive_scan.sh`
- Metadata: `task_types.txt` (must include `manual_verification`),
  empty `labels.txt`
- Initialise the atomic id counter via
  `./.aitask-scripts/aitask_claim_id.sh --init`

The `--related` mode is used in tests because it avoids needing a real
parent task file — `aitask_create.sh --deps` just records the dep
number in frontmatter without validating its existence.

## Files to touch

- `.aitask-scripts/aitask_create_manual_verification.sh` — remove 1 line
- `tests/test_create_manual_verification.sh` — new test file

## Verification

1. Before the fix, confirm the failure repro:
   ```bash
   # inside a scratch project (skip — we have the in-the-wild repro)
   ```
2. After the fix:
   - `bash -n .aitask-scripts/aitask_create_manual_verification.sh`
     (syntax check).
   - `bash tests/test_create_manual_verification.sh` — all assertions
     pass.
   - `shellcheck .aitask-scripts/aitask_create_manual_verification.sh
     tests/test_create_manual_verification.sh` — clean.
3. Manual smoke (optional, since covered by the new test): in a
   throwaway checkout, run the wrapper with a small items file under
   `--related <existing_task>` and confirm the created task file has
   one checklist section with the expected items.

## Post-implementation

Follow task-workflow Step 8 (review + commit) and Step 9 (archival,
push). Commit subject: `bug: Fix manual-verification wrapper double-seed
(t619)`. Plan file commit: `ait: Update plan for t619`.

## Final Implementation Notes

- **Actual work done:**
  - Removed the offending `printf '## Verification Checklist\n'` line
    from `.aitask-scripts/aitask_create_manual_verification.sh` (the
    single line in the description-body heredoc that pre-staged the
    checklist section). The seed call downstream now finds no existing
    section and appends header + items as designed.
  - Added `tests/test_create_manual_verification.sh` with three tests:
    happy-path (`--related` mode, 2 items — asserts exit 0,
    `MANUAL_VERIFICATION_CREATED:` on stdout, exactly one `## Verification
    Checklist` heading, both items present as `- [ ]` lines, correct
    frontmatter), empty-items-file (asserts non-zero exit + `ERROR:`
    prefix), and a syntax check. 12/12 assertions pass.
- **Deviations from plan:** None. Scope matched the plan exactly.
- **Issues encountered:**
  - First run of the test had 2 failures from the `assert_contains`
    helper: `grep -qF "- [ ] ..."` interprets the leading `-` as an
    option flag. Fixed by changing `grep -qF` to `grep -qF --` in both
    `assert_contains` and `assert_not_contains`. This bug was in the
    test harness, not in the wrapper fix.
  - The wrapper calls `./ait git add/commit` after seeding; the test
    fixture doesn't have the full `ait` dispatcher, so the test stubs
    `./ait` with a tiny pass-through script that forwards `git
    <args>` to plain `git` (the wrapper already redirects these calls
    to `/dev/null` so any output is discarded).
- **Key decisions:**
  - Chose `--related` mode in tests instead of `--parent` because it
    avoids needing a real parent task file in the fixture — `aitask_create.sh
    --deps` records the dep number without validating existence.
  - Did not remove the blank line before the deleted `printf`. Python
    `cmd_seed` (`aitask_verification_parse.py:270–271`) strips trailing
    empty lines from the body before appending its header, so any
    residual whitespace is harmless. Confirmed in the test output
    (clean task file, no double blank lines).
- **Shellcheck:** The only warning after the fix is a pre-existing
  `SC1091` info on `source "$SCRIPT_DIR/lib/terminal_compat.sh"`, which
  is present on every script in `.aitask-scripts/` and is unrelated to
  this change.
