---
priority: low
effort: medium
depends: []
issue_type: test
status: Ready
labels: [testing]
anchor: 1794
followup_kind: risk_mitigation
created_at: 2026-09-17 22:47
updated_at: 2026-09-17 22:47
---

## Origin

Risk-mitigation ("after") follow-up for t1826, created at Step 8d after implementation landed.

## Risk addressed

- The `t1_alpha.md` truncation stays unexplained. Transcripts, reflog and code search rule out a Claude-run test and any other writer in `tests/`, but not a git rewrite inside `.aitask-data` or a non-Claude agent · severity: medium
- The audit covers bash tests only. A Python test that `os.chdir`s into the repo and fails a fixture step is outside the lint (none found today) · severity: low

## Goal

Give the live task tree a tripwire that fires when a test run changes it.

t1826 closed the bash side: every `cd`/`pushd` in `tests/*.sh` is exit-guarded
(`tests/lib/cd_guard_scan.py`, enforced by `tests/test_cd_guard_lint.sh`), and
cwd-changing tests start in an empty read-only dir
(`tests/lib/scratch_cwd.sh`). Neither covers the Python suite, and neither
explains the 2026-09-02 09:09:18 truncation of `aitasks/t1_alpha.md`, which
happened after the t1631 guards landed and has no writer anywhere in `tests/`
or `.aitask-scripts/`.

Snapshot the live `aitasks/` (and `aiplans/`) — names, sizes, mtimes — before
and after `bash tests/run_all_python_tests.sh`, and fail loudly, naming the
paths, when a run changed it. Decide where the check belongs (inside the runner
vs a wrapper a developer opts into) and whether it should be advisory or a hard
failure; a false positive must not block a suite run, because concurrent agent
sessions legitimately write task files while tests run. That concurrency is the
main design problem: distinguish "this suite run wrote it" from "another
session committed a task update at the same moment" — e.g. by restricting the
tripwire to fixture-shaped names (`t<N>_alpha`, `t<N>_sample`, `t<N>_test_task`,
0-byte task files) or by comparing against `./ait git status` rather than
mtimes alone.

Verification bar: a negative control. Make a throwaway test write a fixture task
file into the live tree (in a scratch copy of the repo, never the real one) and
show the tripwire fires and names it; show a clean run stays silent, including
while an unrelated task-file commit lands mid-run.
