---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codeagent]
gates: [risk_evaluated]
anchor: 1171
created_at: 2026-07-21 18:02
updated_at: 2026-07-21 18:02
---

## Origin

Spawned from t1196 during Step 8b review.

## Upstream defect

`tests/test_crew_runner.sh:762 — footer reads a file-backed COUNTER_FILE that no
assertion writes, so the suite prints "FAIL:" lines and still exits 0; all 19
tests are unenforced in CI.`

Scope is wider than that one file. **11 test files** pair a `COUNTER_FILE`
footer with the shared `tests/lib/asserts.sh` helpers and under-report to
varying degrees:

| File | Assertions in file | Reported total |
|---|---|---|
| `tests/test_crew_groups.sh` | 23 | **0** |
| `tests/test_crew_init.sh` | 22 | 3 |
| `tests/test_crew_status.sh` | 52 | 5 |
| `tests/test_crew_runner.sh` | 19 tests | 2 |

Also affected (same pattern, counts not individually measured):
`test_crew_report.sh`, `test_crew_setmode.sh`,
`test_crew_addwork_output_instructions.sh`, `test_crew_template_includes.sh`,
`test_agentcrew_pythonpath.sh`, `test_brainstorm_cli.sh`,
`test_launch_mode_field.sh`.

## Diagnostic context

Root cause: these files predate t923 (the migration that consolidated ~136
files' inline assertion helpers into `tests/lib/asserts.sh`). They implement
their own file-backed counters (`COUNTER_FILE` + `_inc_pass` / `_inc_fail`)
specifically so counts survive the `( … )` **subshells** their tests run in.
The shared `asserts.sh` helpers instead mutate shell-global `PASS` / `FAIL` /
`TOTAL`. After the migration:

- assertions bump the shell globals, which are then discarded at subshell exit;
- `_inc_pass` / `_inc_fail` became dead code, so `COUNTER_FILE` stays at its
  initial value;
- the footer reads `COUNTER_FILE` and the exit guard tests that value.

Net effect: **a failing assertion prints `FAIL:` and the suite still exits 0.**
Reproduced directly on `tests/test_crew_runner.sh` at HEAD by breaking an
assertion deliberately — `FAIL:` printed, exit code 0.

This was found while adding a content contract for t1196: the new check was
initially placed in `tests/test_crew_runner.sh`, where it would not have been
enforced. t1196 worked around it by putting the checks in a new harness
(`tests/test_crew_runner_config_delivery.sh`) with a working
`[[ $FAIL -eq 0 ]]` footer — the underlying defect was left for this task.

## Suggested fix

Pick ONE mechanism per file and make the footer read what the assertions
actually write. Two viable directions:

1. **Drop the subshells** where practical, so the shared `asserts.sh` globals
   propagate, and delete the `COUNTER_FILE` scaffolding. Cleanest, but some
   tests rely on subshells for `cd` isolation.
2. **Keep subshells, make counting subshell-safe** — e.g. have each subshell
   block flush its `PASS`/`FAIL` deltas to the counter file on exit, or restrict
   subshells to command substitution (capture output, assert at top level, as
   `tests/test_crew_runner_config_delivery.sh` does).

Whichever is chosen, verification MUST include a negative control per touched
file: deliberately break one assertion and confirm the suite now exits non-zero.
A fix that only corrects the printed totals without fixing the exit code leaves
the CI blind spot in place.
