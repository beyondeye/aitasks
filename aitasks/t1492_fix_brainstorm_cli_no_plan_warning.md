---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tests, bash_scripts]
gates: [risk_evaluated]
anchor: 1468
followup_kind: upstream_defect
created_at: 2026-08-12 10:15
updated_at: 2026-08-12 10:15
---

## Origin

Spawned from t1488 during Step 8b review.

## Upstream defect

- `tests/test_brainstorm_cli.sh — "archive outputs NO_PLAN warning" fails on
  main; brainstorm archive prints only "Finalizing brainstorm session for task
  999..." without the expected NO_PLAN warning`

`tests/test_brainstorm_cli.sh` is **red on `main`**. Its final assertion is:

```
FAIL: archive outputs NO_PLAN warning (expected output containing (ci) 'NO_PLAN',
got '[0;34mFinalizing brainstorm session for task 999...[0m
```

The file reports `PASS: 29 / FAIL: 1 / TOTAL: 30` and exits non-zero. Unlike the
t1488 defect this one is *visible* — it prints a named FAIL line and a summary —
so it is a straightforward assertion failure rather than a silent abort.

## Diagnostic context

Found during the t1488 regression sweep over all 69 consumers of
`tests/lib/test_scaffold.sh` (68 pass, this one fails).

It is **proven pre-existing and unrelated to t1488**. t1488 modified three
shared files (`tests/lib/test_scaffold.sh`, `tests/lib/asserts.sh`,
`tests/test_boardcol_update.sh`). With all three reverted to their `HEAD`
versions and the test re-run, the failure reproduces byte-identically — same
assertion, same captured output, same 29/1/30 tally. A name-collision check also
confirmed `test_brainstorm_cli.sh` references none of the identifiers t1488
added.

(A `git worktree` control was attempted first but could not run: task data lives
on the separate `aitask-data` branch, so a detached worktree has no
`aitasks/metadata/codeagent_config.json` and the brainstorm scaffold aborts
during setup. The revert-in-place control was used instead.)

## Suggested fix

Determine whether the regression is in the brainstorm archive path (the
`NO_PLAN` warning is no longer emitted when a session has no plan) or in the
test's expectation (the warning moved, was reworded, or now goes to a different
stream than the assertion captures). Check whether the assertion captures
stderr — a warning written to stderr while the test captures only stdout would
produce exactly this symptom.
