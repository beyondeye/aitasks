---
Task: t1357_2_instrument_helpers_gate_duration.md
Parent Task: aitasks/t1357_task_workflow_step_stats_and_drift.md
Sibling Tasks: aitasks/t1357/t1357_1_*.md … t1357_7_*.md
Archived Sibling Plans: aiplans/archived/p1357/p1357_*_*.md
Worktree: aiwork/t1357_2_instrument_helpers_gate_duration
Branch: aitask/t1357_2_instrument_helpers_gate_duration
Base branch: main
Output branch: main
---

# Plan: t1357_2 — Instrument deterministic helpers + emit gate `duration=`

Task file lists the six helper edits and the two gate-duration sites — that
list is the scope. Every stamp call: `./.aitask-scripts/aitask_stats_step.sh
… || true` (defense in depth over the helper's own exit-0 contract).

## Implementation steps

1. **Read first:** `aidocs/framework/shell_conventions.md`; t1357_1's landed
   helper (verb signatures may have evolved — the archived plan
   `aiplans/archived/p1357/p1357_1_*.md` records deviations).
2. Locate the exact stamp points:
   - `aitask_pick_own.sh`: where `OWNED:` is printed → `begin-run` + `claim` point.
   - `aitask_gate_record.sh`: after successful append → `gates` point with
     `gate=<name> status=<status>`.
   - `aitask_plan_externalize.sh`: on `EXTERNALIZED:`/`OVERWRITTEN:` →
     `planning point --sub externalize`.
   - `aitask_archive.sh`: after archive move commits → `archive` point.
   - `aitask_usage_update.sh`: new optional `--task-id <id>`; when present →
     `feedback` point + `capture <id> --outcome done --sweep-orphans`.
     Without the flag: behavior byte-identical to today.
   - `aitask_update.sh`: in the `--status` write path → `status` point with
     `status=<S>`.
3. **Gate duration:**
   - `lib/gate_verifier_lib.sh` `run_command_gate()`: `start=$(date +%s)` …
     `duration="$(( $(date +%s) - start ))s"`; add `duration=$duration` to the
     existing `aitask_gate.sh append` argv (marker key order is fixed:
     run,status,attempt,duration,type — the append path handles ordering).
   - `lib/gate_orchestrator.py`: wall-time around `_spawn_verifier` (~308);
     thread the measured seconds into `reconcile_terminal()`'s append kwargs.
4. **Tests** `tests/test_stats_instrumentation.sh`: scratch repo; invoke each
   instrumented helper; assert expected spool line (step/ev/src). Negative
   control: rename `aitask_stats_step.sh` away → helpers still succeed.
   Gate duration: run a command gate; assert marker contains `duration=<N>s`;
   parse with `python3 -c 'from lib.gate_ledger import …'` (run from
   `.aitask-scripts/`). Check existing tests for each touched script still
   pass (grep tests/ for the script names; run those files).
5. `shellcheck` all touched `aitask_*.sh` + the two libs.

## Verification

Per task file: existing helper tests green; new instrumentation test PASS;
negctrl proves non-fatality; `duration=` present and parseable in both the
bash and orchestrator paths.

## Step 9

Standard Step 9. Note for t1357_3: the `--task-id` flag added here is what
the Step 9b skill hook passes.
