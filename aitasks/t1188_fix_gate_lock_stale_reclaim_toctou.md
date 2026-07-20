---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [gates]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-07-20 18:10
updated_at: 2026-07-20 18:10
boardidx: 30
---

## Origin

Spawned from t1183 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_gate.sh:80-88 — acquire_gate_lock stale-reclaim
  TOCTOU: if the lock dir vanishes between the -d check and stat, the
  stat-fail fallback (|| echo "0") computes age≈now, treats the lock as
  stale, and rmdirs a lock another process may have just re-acquired,
  permitting double-hold and a lost append; plausible-by-inspection
  (observed once, unreproduced in 150+ soak rounds); mirrored pattern in
  aitask_create.sh acquire_child_lock`
- `.aitask-scripts/lib/archive_utils.sh:53 — archive_path_for_id does
  arithmetic on a non-numeric task id; a t-prefixed id (e.g. t1183) crashes
  with "unbound variable" noise under set -u before resolve_task_file's
  friendly "No task file found" die`

## Diagnostic context

While building t1183's gate-lock characterization suite
(`tests/test_gate_lock_characterization.sh`), the very first run of the
4-concurrent-append serialization test produced 3/4 ledger blocks (one lost
append) with stderr discarded. The anomaly never reproduced: 0 recurrences in
150+ soak rounds with 4 and 8 contenders, and 0 rounds showed the
"Removing stale gate lock" warn. Code inspection of `acquire_gate_lock`
identified the stale-reclaim TOCTOU above as the only in-script path that can
remove a live lock: `stat -c %Y ... || echo "0"` maps a vanished dir to epoch
age, so a waiter that races the holder's release can classify a
just-re-acquired lock as stale (>120s) and rmdir it, after which two
processes hold the "lock" and the tmp-file+mv write path loses one block.
The characterization suite's tests 1 and 4b now capture and dump contender
stderr on anomaly, so any recurrence will show the reclaim warn if this path
fires.

The archive_utils defect surfaced when the suite pinned the t-prefixed
spelling: `aitask_gate.sh status t1183` prints
`archive_utils.sh: line 53: t1183: unbound variable` noise (from
`bundle=$(( task_id / 100 ))` treating the id as a variable name under
`set -u`) before dying with the intended "No task file found" message.

## Suggested fix

For the TOCTOU: treat a stat failure as "lock vanished — retry mkdir
immediately" instead of age≈∞ (e.g. `stat || continue`-shaped guard, or
re-check `-d` after stat fails), and consider an owner token so reclaim only
removes a provably-stale lock; apply the same fix to
`aitask_create.sh acquire_child_lock`. For archive_utils: validate the id is
numeric before arithmetic (or guard `_find_archive_for_task` against
non-numeric input) so non-numeric ids fail with only the friendly resolver
error. t1183's characterization tests 1/4b (serialization) and 6 (stale
reclaim) cover the lock behavior; extend test 3's t-spelling assertion to
require stderr free of "unbound variable" once fixed.
