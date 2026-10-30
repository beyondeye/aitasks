---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, concurrency]
gates: [risk_evaluated]
followup_kind: upstream_defect
created_at: 2026-10-30 12:32
updated_at: 2026-10-30 12:32
---

## Origin

Spawned from aitasks_go#t22_4 (the testmap cutover) during its Step 8b
review. t22_4 rewrote 39 aitasks task files while other sessions could append
notes, and had to work around both defects below with a wrapper that holds the
ledger locks itself.

## Upstream defects

- `.aitask-scripts/aitask_gate.sh:310` (also `:992`, `:1253`):
  `local key="${task_id//\//_}"` keys the gate lock on the caller's spelling of
  the id. `aitask_gate.sh append 1854_14 …` locks `gate_1854_14`, while
  `aitask_gate.sh append t1854_14 …` locks `gate_t1854_14`, so two gate
  writers using different spellings do not exclude each other. `aitask_note.sh`
  already normalizes (`note_id_normalize`, `${1#t}`); the gate key should too.
- `.aitask-scripts/aitask_update.sh`: `--desc-file` replaces the whole
  description, including the `## Inbox` and `## Gate Runs` ledger sections,
  and the script takes **no** ledger lock. Even a status-only update rewrites
  the file from a body it read at start. A note (`aitask_note.sh`, which holds
  the per-task `note_<id>` lock) or a gate run appended between that read and
  the write is silently lost. Callers that replace a body must know to splice
  the ledgers back themselves.

## Diagnostic context

- `lib/ledger_block.sh` keeps a single `_AIT_LEDGER_LOCK_DIR`/`_TOKEN` pair per
  shell, so a caller that needs both the note and the gate lock must nest
  subshells (one lock per scope, each with its own EXIT trap). A second
  acquisition in the same shell overwrites the first ownership record and
  leaks the first lock (verified by a mutation probe in t22_4).
- `stale_lock.sh` reclaims locks whose recorded PID is dead, which hides such
  leaks from a later reacquire. Cleanup has to be asserted by checking that
  the lock directory is absent.

## Suggested fix

- Normalize the gate lock key (`${task_id#t}`) in all three `aitask_gate.sh`
  sites.
- Make `aitask_update.sh` hold the task's note and gate locks around its
  read-modify-write, in nested scopes, and preserve the ledger sections when
  `--desc`/`--desc-file` is given, unless an explicit flag opts out.
- Add a test that appends a note concurrently with an update.
