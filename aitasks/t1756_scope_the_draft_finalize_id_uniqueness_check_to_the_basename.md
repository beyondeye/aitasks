---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [bash_scripts]
file_references: [tests/test_draft_finalize.sh:282-284]
created_at: 2026-09-09 09:51
updated_at: 2026-09-09 09:51
---

## Problem

`tests/test_draft_finalize.sh:282` derives task ids by grepping **full paths**:

    ids7=$(ls "$TMPDIR_7/local/aitasks"/t*_*.md 2>/dev/null | grep -oE 't[0-9]+' | sort -u | wc -l)
    total_tasks7=$(ls "$TMPDIR_7/local/aitasks"/t*_*.md 2>/dev/null | wc -l)
    assert_eq_trim "All task IDs are unique" "$total_tasks7" "$ids7"

`mktemp -d` names are random, so when the temporary directory's own name happens
to contain `t` followed by digits, that substring is counted as an extra unique
"id" and the assertion fails with a count one higher than the number of files.

Observed 2026-09-08: `FAIL: All task IDs are unique (expected '5', got '6')`,
with three consecutive re-runs green afterwards. It is a **flaky test**, not a
product defect — nothing in `aitask_create.sh` misbehaved.

## Goal

Make the check independent of where the fixture happens to live, so a run's
verdict does not depend on `mktemp`'s random name.

Extract ids from the **basename** rather than the full path, and anchor the
pattern to the start of the name — e.g. iterate the files and strip with
`${f##*/}` before matching `^t[0-9]+`, or pipe through `basename -a`. Anchoring
matters as much as the basename: an unanchored `t[0-9]+` would still match inside
a task *name* such as `t3_fix_t42_regression`.

## Verification

- The existing Test 7 assertions still pass.
- Add a deterministic control: run the same extraction against a fixture path
  that deliberately contains `t123` (e.g. build the repo under a directory named
  `t123_fixture`) and assert the uniqueness check still passes. Without the fix
  that control fails, which is what makes it a real regression guard rather than
  a re-run of the flaky case.

## Context

Found while implementing **t1725_2**; recorded in that task's plan under "Issues
encountered". Unrelated to the guard work — the failure was observed once during
its regression sweep and did not reproduce.
