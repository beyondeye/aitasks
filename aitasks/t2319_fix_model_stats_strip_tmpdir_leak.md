---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
created_at: 2026-11-16 18:06
updated_at: 2026-11-16 18:17
---

## Origin

Spawned from t2316 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_model_stats_strip.sh:96 — mktemp -d "${TMPDIR:-/tmp}/ait_stats_strip.XXXXXX" work dir leaked into the Python suite's per-run TMPDIR (guard reported "TMPDIR LEFTOVERS (1): ait_stats_strip.r9J2h3" on the final full-suite run); cleanup at :64/:146 apparently misses some exit path — leaking path not yet identified`

## Diagnostic context

- Seen on a full `bash tests/run_all_python_tests.sh` run on 2026-11-16, after
  t2316 had removed every Chromium leftover from the same report. The guard
  (`tests/lib/tmpdir_guard.sh`) printed `TMPDIR LEFTOVERS (1):
  ait_stats_strip.r9J2h3` (warn-only; suite PASSED).
- Earlier runs that day did not report it, so it is path- or timing-dependent
  (not every run). t2316 did not touch this script.
- The script creates `WORK_DIR` at line 96 and removes it at line 64 (an error
  helper) and line 146; an exit route that bypasses both (e.g. a
  `strip_deferred` / early-return path, a signal, or a subshell `exit`) would
  leave it. Which Python test drives it was not identified — start with
  `grep -rln aitask_model_stats_strip tests/`.

## Suggested fix

Install `trap 'rm -rf "$WORK_DIR"' EXIT` right after the `mktemp -d` (or route
every exit through one cleanup), then add a test that runs each exit route
under a private TMPDIR and asserts it is empty
(`bash tests/run_shell_test.sh` shows leftovers for shell tests).
