---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [board, framework]
gates: [risk_evaluated]
anchor: 1312
followup_kind: upstream_defect
created_at: 2026-07-29 18:36
updated_at: 2026-08-13 23:06
boardidx: 93184
---

## Origin

Spawned from t1312 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:7259-7261` — `action_work_report`
  silently drops any column task whose filename has no numeric id
  (`task_num, task_name = TaskCard._parse_filename(...)` then
  `if not task_num: continue`), while `manager.get_column_tasks(col_id)` still
  counts it. The task vanishes from the work report with no warning.
- `aitasks/t_refresh_codeagent_suite_default_model_expectations.md` — a live
  task file with **no numeric id** at all (created 2026-07-29 alongside t1311's
  risk-mitigation flow, committed in `ait: Revert t1311 to Ready (risk
  mitigation pending)`). Whatever produced it wrote a task file that never
  claimed an ID; that creation path needs finding too.

## Diagnostic context

Surfaced while running the full python suite for t1312. The suite failed with
exactly one failure, reproducible across two independent runs:

    FAIL: test_board_work_report.WorkReportFullColumnUnderSearchTests.test_hidden_cards_still_listed
    AssertionError: 137 != 138

`test_hidden_cards_still_listed` runs the real `KanbanApp` against the **live**
repo tree and asserts `sl.option_count == len(col_tasks)` — i.e. that every task
in a board column reaches the work-report SelectionList. A live probe pinned the
cause precisely:

    col=unordered tasks=138 entries=137
    unparsed=['t_refresh_codeagent_suite_default_model_expectations.md'] dupes=[]

So the failure is not flaky and not a board regression: one live task file has
no parseable id, and the two sides of the assertion disagree about whether to
count it. The failure is unrelated to t1312 (which touched only the label
vocabulary seam) and was left unfixed there.

## Suggested fix

Two independent halves — decide each on its own merits:

1. **Board:** make the skip visible rather than silent — surface a notification
   naming the unparseable filename(s), or include the task with a degraded
   label, so a work report can never quietly omit a task.
2. **Creation path:** find what wrote an id-less task file and make that
   impossible (the id claim should be a precondition of writing the file).
   Then decide whether the existing file is renamed to a claimed id or removed.

Note the test itself encodes the assumption "every task file in a column parses
to a task number". If the board is fixed to count consistently, the test passes;
if instead malformed files are made impossible, it also passes. Fixing only one
half is sufficient to green the suite, but both are worth doing.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1755** id=2026-09-09T10:41:23Z.7daa90cf37a955de11e37c42 from=t1755 from_verified=yes at=2026-09-09T10:41:23Z base=ec9641e79d0bc203ff54aeca4e3f0783d9da6f61 base_branch=main dirty=yes host=omg16
>
> | The id-less-filename **producer** is now closed. Your "Upstream defect" bullet 2
> | ends "Whatever produced it wrote a task file that never claimed an ID; that
> | creation path needs finding too." — t1755 found and fixed it.
> | 
> | What was wrong (reproduced end-to-end in a scratch fixture, twice):
> | `aitask_create.sh` could write `aitasks/t_<name>.md`, **commit** it, and exit **0**.
> | Two defects combined — an unchecked `mktemp` whose empty path made
> | `2>"$claim_stderr"` an ambiguous redirect, and a lost exit status, because bash
> | DROPS `errexit` inside every command-substitution subshell, so the `die()` in
> | `claim_parent_id_once` exited only its own subshell and the caller continued with an
> | empty id.
> | 
> | Fixed in `ec9641e79` (checked `mktemp`, status absorbed with `|| rc=$?`, and a
> | `^[0-9]+$` validation in `claim_unique_parent_id` as the single choke point).
> | Regression coverage: `tests/test_create_id_claim_abort.sh`.
> | 
> | **What I did NOT prove:** that your specific artifact
> | `aitasks/t_refresh_codeagent_suite_default_model_expectations.md` came from this
> | path. I have no evidence tying that file to a failed claim. t1721 has since
> | renumbered it to t1730, so no id-less file is on disk as of this note.
> | 
> | **What this may change for you, and what it does not:** bullet 2's "creation path
> | needs finding" is answered, so what remains is bullet 1 — `action_work_report`
> | silently dropping a column task whose filename has no numeric id
> | (`aitask_board.py:7259-7261`) while `get_column_tasks` still counts it. That is
> | now a backstop for legacy/pre-existing files rather than a guard against newly
> | created ones, which may affect priority — but it does not make the task moot: the
> | silent drop and the count mismatch are still real.
