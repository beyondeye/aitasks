---
priority: high
effort: medium
depends: [t1705_1]
issue_type: feature
status: Ready
labels: [session_persistence, codeagent, agent_marks, python, concurrency, testing]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:02
updated_at: 2026-09-04 16:02
---

## Context

Second child of t1705 (frozen code agents). Introduces the **framework
session store**: one machine-wide record per code agent across every aitasks
tmux session / project, with the lifecycle state machine that the freeze
engine (t1705_4), the restore coordinator (t1705_5), the viewer (t1705_6) and
the monitors (t1705_7) all drive. Nothing here touches tmux or a TUI; it is a
pure store + locked writer + lock-free reader, mirrored 1:1 on the shipped
`agent_marks` pair. Read the parent plan's §A (**PINNED**) before writing a
line — the schema, the `(root, window, window_slot)` identity, the conflict
policy, the operation lease, the state machine and every verb's wire format
are decided there and reproduced in this child's plan
(`aiplans/p1705/p1705_2_framework_session_store.md`). If t1705_1's
`## Spike findings` block in the parent plan changed a contract, the plan
here carries the amended text.

## Key files

- **New** `.aitask-scripts/lib/agent_sessions.py` — lock-free primitive:
  schema v1, `load()` (raises `MalformedSessionsError`) / `load_safe()`,
  `dump()` via `lib/atomic_write.py`, `SessionRecord` dataclass, the
  conflict-policy resolver, every transition as a pure function
  `(store, args) -> (store', wire_line)` raising typed errors
  (`TransitionRefused`, `NonceMismatch`, `SessionMismatch`, `LeaseHeld`),
  `standin_command(record_id)`, `SessionsView` (mtime+size+**inode** gated),
  observation-file reader (`ROOT`/`WINDOW`/`PANE`/`INCOMPLETE`), purge
  policy, CLI entry (`python3 agent_sessions.py [--file PATH] <verb> …`).
- **New** `.aitask-scripts/aitask_agent_sessions.sh` — the **sole writer**:
  resolves `AITASKS_AGENT_SESSIONS_FILE`, derives `<file>.lockd`, holds
  `lib/registry_lock.sh` around every mutating verb (2 s keypress timeout,
  10 s for `purge`), `list`/`show` take **no** lock, merges stderr into
  stdout, exit codes `0/2/3 LOCK_BUSY/4 ERROR/5 TRANSITION_REFUSED/6
  NONCE_MISMATCH/7 RESTORE_SESSION_MISMATCH/8 LEASE_HELD`.
- **New** `.aitask-scripts/lib/agent_sessions.sh` — shell mirror of the
  option-name constants (`RECORD_OPTION`, `FROZEN_OPTION`,
  `STANDIN_READY_OPTION`, `AGENT_SESSION_OPTION`) and the capture-dir
  resolver (`AITASKS_FROZEN_DIR`, default `~/.config/aitasks/frozen`).
- **Edit** `.aitask-scripts/lib/agent_marks.py` `_read_observed` (:623-654)
  — skip `PANE` rows so one observation file serves both purges.
- **New** `tests/test_agent_sessions.py`, `tests/test_agent_sessions_identity.py`,
  `tests/test_agent_sessions_transitions.py`, `tests/test_agent_sessions_lease.py`,
  `tests/test_agent_sessions_observation.py`, `tests/test_agent_sessions_liveness.py`,
  `tests/test_agent_sessions_concurrency.sh`.
- **Edit** `aitasks/t1389_stamped_agent_and_task_pane_identity.md` — the
  reverse coordination link is written by the parent at decomposition; this
  child's task file carries the forward one (below).

## Reference patterns (read before writing)

- `.aitask-scripts/lib/agent_marks.py` — the whole file is the template:
  `_target_mode` / `dump` (:308-362), `_parse` strictness (:209-270),
  `load` vs `load_safe` (:273-305), `mark_key` realpath-both-sides (:176-184),
  `sweep_liveness` fail-closed rules (:440-478), `MarksView` inode gating
  (:506-581), `_read_observed` (:623-654), CLI (:658-684).
- `.aitask-scripts/aitask_agent_marks.sh` — lock dir derived from the
  resolved file (:55-59), `marks_lock_or_busy` (:82-92), `cmd_list` takes no
  lock (:127-139), exit-code contract (:38-43).
- `.aitask-scripts/lib/registry_lock.sh` — `registry_lock_acquire <dir>
  [timeout] [label]` returns 1 on busy and prints nothing.
- `.aitask-scripts/lib/atomic_write.py` — `atomic_write_text`, `target_mode`.
- `.aitask-scripts/aitask_shadow_rejected.sh` — the second store with the
  same exit-code contract.
- `tests/test_agent_marks.py`, `tests/test_agent_marks_liveness.py`,
  `tests/test_agent_marks_concurrency.sh` — test shapes to mirror (N
  background writers + `wait`, assert both total count and each payload once).

## Implementation plan (summary — the child plan is normative)

1. Schema + dataclass + parse/dump with the marks strictness rules; unknown
   `state` is corruption.
2. Identity + conflict policy (`upsert`), including `window_slot` allocation
   and the fail-closed multi-candidate rule.
3. Lease (`op_nonce`/`op_owner_pid`/`op_started_at`), `lease-take`, nonce
   checks on every leased mutation.
4. Transitions: `freeze-begin/commit/abort`, `restore-begin/launched/confirm/abort`,
   `standin-respawned`, `drop`, with `last_error` persistence on session
   mismatch and the "captures deleted only on `ack=hook`" rule.
5. Observation reader (`PANE` rows) + purge (`dead_window`, `dead_pane`
   with `ESRCH`-only pid death, `capture_missing`); `agent_marks._read_observed`
   learns to skip `PANE`.
6. `SessionsView`, `standin_command` (+ `AITASKS_FROZEN_STANDIN_CMD` test seam).
7. Locked shell wrapper; `list`/`show` unlocked.
8. Tests, including the concurrency suite and a negative control per
   fail-closed rule.

## Coordination

- **t1389** (`stamped_agent_and_task_pane_identity`): this store keys on
  `(root, window, window_slot)` and joins panes via `@aitask_record`; when
  t1389 stamps `@aitask_agent` / `@aitask_task_id`, it must sweep
  `lib/agent_sessions.py`, `lib/agent_freeze.py`, `aitask_session_hook.sh`
  and the frozen discovery branch in `monitor_core.py`. The parent wrote the
  reverse note under t1389's `## Notes for sibling tasks`.
- No `ait` dispatcher entry and no skill allow-list entries: callers are
  Python TUIs, sibling scripts and the SessionStart hook
  (`aidocs/framework/aitasks_extension_points.md` §"Adding a new helper script").

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests -k agent_sessions   # or the individual files
bash tests/test_agent_sessions_concurrency.sh
bash tests/test_agent_marks.py-equivalents still green: bash tests/run_all_python_tests.sh
shellcheck .aitask-scripts/aitask_agent_sessions.sh .aitask-scripts/lib/agent_sessions.sh
AITASKS_AGENT_SESSIONS_FILE=/tmp/x.json ./.aitask-scripts/aitask_agent_sessions.sh upsert --root "$PWD" --window agent-pick-1 --pane %9 --pane-pid $$   # UPSERTED:<id>|created
```
No tmux involvement — safe to implement from any shell.
