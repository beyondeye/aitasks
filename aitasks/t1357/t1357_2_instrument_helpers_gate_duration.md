---
priority: medium
effort: medium
depends: [t1357_1]
issue_type: feature
status: Ready
labels: [task_workflow, gates]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:57
updated_at: 2026-07-31 10:57
---

## Context

Second child of t1357. With the stamp helper from t1357_1 in place, add
guarded stamp calls to the deterministic helpers that already fire at
workflow step boundaries — covering claim→plan→approve→review→merge→archive
without touching any skill text — and emit the gate ledger's never-used
`duration=` key.

Parent plan: `aiplans/p1357_task_workflow_step_stats_and_drift.md`
(Architecture + child t1357_2 section). Depends on t1357_1
(`aitask_stats_step.sh` must exist).

## Key files to modify

Every stamp call is guarded: `./.aitask-scripts/aitask_stats_step.sh ... || true`
(defense in depth on top of the helper's own exit-0 contract).

1. `.aitask-scripts/aitask_pick_own.sh` — at the point that prints `OWNED:`:
   `begin-run <id> --skill "${AIT_STATS_SKILL:-pick}"` + `stamp <id> claim point`.
2. `.aitask-scripts/aitask_gate_record.sh` — after a successful append:
   `stamp <id> gates point gate=<gate> status=<status>`.
3. `.aitask-scripts/aitask_plan_externalize.sh` — on EXTERNALIZED/OVERWRITTEN:
   `stamp <id> planning point --sub externalize`.
4. `.aitask-scripts/aitask_archive.sh` — after successful archive:
   `stamp <id> archive point`.
5. `.aitask-scripts/aitask_usage_update.sh` — `stamp <task?> feedback point`
   is NOT possible (no task id in scope — it is keyed by agent/skill).
   Instead: add `--task-id <id>` optional flag; when present, stamp feedback
   AND run `capture <id> --outcome done --sweep-orphans` as the deterministic
   end-of-run backstop. (Skill text passes --task-id in t1357_3; without the
   flag behavior is unchanged.)
6. `.aitask-scripts/aitask_update.sh` — on `--status <S>` writes: `stamp <id>
   status point status=<S>` (cheap lifecycle points; status values map to
   step transitions at report time).
7. **Gate duration emission:**
   - `.aitask-scripts/lib/gate_verifier_lib.sh` `run_command_gate()` — time
     the command block (`SECONDS` or `date +%s` delta) and pass
     `duration=<N>s` to the existing `aitask_gate.sh append` call (marker
     slot already parsed by bash + `lib/gate_ledger.py`; order run,status,
     attempt,duration,type).
   - `.aitask-scripts/lib/gate_orchestrator.py` — measure wall time around
     `_spawn_verifier` (line ~308/384-391) and include `duration=` in the
     terminal `reconcile_terminal()` append.

## Reference files for patterns

- Marker key order + parsing: `lib/gate_ledger.py` (`MARKER_KEYS` ~line 78).
- Existing tests to keep green: `tests/` files covering pick_own, gate
  record/ledger, archive, update (grep `tests/ -l` for each script name).
- `aidocs/framework/shell_conventions.md` before editing any script.

## Verification

- Each instrumented helper's existing test file still passes.
- New `bash tests/test_stats_instrumentation.sh`: run each helper in a
  scratch repo and assert the expected spool line appears (step + ev + src).
- **Negative control:** replace `aitask_stats_step.sh` with a script that
  exits 1 / is absent → every instrumented helper still succeeds.
- Gate duration: run a command gate via `run_command_gate` in a scratch repo;
  assert the ledger marker contains `duration=<N>s` and that
  `lib/gate_ledger.py` parses it (python one-liner). Same for an
  orchestrator-driven machine gate if a cheap fixture exists
  (see tests/test_gate_orchestrator*.sh for the harness).
- `shellcheck` on all touched `aitask_*.sh`.
