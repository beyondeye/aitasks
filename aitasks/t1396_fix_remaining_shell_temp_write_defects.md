---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [script-performance]
followup_kind: upstream_defect
created_at: 2026-08-03 22:36
updated_at: 2026-08-13 23:07
boardidx: 1024
---

## Origin

Spawned from t1379 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_archive.sh:158,163` — task-file rewrite uses a FIXED temp name (`"$file_path.tmp"`) instead of `mktemp`, so two concurrent archives of the same task collide, and the temp is visible to a `*.md.tmp` glob.
- `.aitask-scripts/aitask_gate.sh:280` — ledger temp name is PID-derived with no `O_EXCL` (same defect class as `gate_ledger.py:357`, which t1281 owns).
- `.aitask-scripts/aitask_update.sh:6` — `set -e` only, no `-u`/`pipefail`, contrary to `aidocs/framework/shell_conventions.md`; same at `aitask_issue_import.sh:6`.

## Diagnostic context

Found while sweeping `.aitask-scripts/` for truncate-then-write and
cross-device-`mv` file writers during t1379.

The first two sites were **cleared** by that sweep for the defect t1379 was
fixing: both already stage their temp in the destination directory, so their
renames are same-filesystem and atomic. What they get wrong is the temp *name*,
which is a different (and much narrower) failure mode — collision between two
concurrent writers rather than a torn read. `aitask_archive.sh` is the worse of
the two: a fixed `.tmp` suffix collides whenever two archives of the same task
run at once, whereas `aitask_gate.sh`'s PID-derived name only collides between
threads of one process, which bash does not have.

The third item is a convention violation noted while converting those two
scripts to `lib/atomic_write.sh`. t1379 deliberately did NOT bundle it: enabling
`-u` in `aitask_update.sh` is a large change on its own (`write_task_file` takes
30 positional parameters with `${N:-}` defaults precisely because `-u` is off),
and t1379's prepare/commit split was chosen so that no conversion depends on
`pipefail`.

## Suggested fix

For the two temp-name sites, use the same shape `lib/atomic_write.sh` now
provides: `ait_atomic_render` (or `ait_atomic_tmp` + `ait_atomic_commit`), which
mktemps a dot-prefixed sibling in the destination directory and cleans up on
failure. Note the renderer contract in that file's header — renderers must not
rely on `set -e`, which the calling context disables.

The `set -euo pipefail` item is independent and larger; consider splitting it
out if the temp-name fixes land first.
