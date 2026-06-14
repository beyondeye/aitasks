---
priority: high
effort: medium
depends: [t635_1]
issue_type: feature
status: Ready
labels: [gates, task_workflow]
created_at: 2026-06-10 18:52
updated_at: 2026-06-14 11:40
---

## Context

Phase 1 of `aidocs/gates/integration-roadmap.md` (decision D1/D2 seed).
task-workflow starts RECORDING its existing checkpoints as gate-run blocks
in the task file — purely additive appends, zero behavior change to the
interactive prompts. In attended mode the AskUserQuestion / ExitPlanMode
outcome IS the signal (hybrid-by-mode, decision D2).

## Scope

- Record as gate-run blocks (via `./.aitask-scripts/aitask_gate.sh append`
  from t635_1 — see Coordination below; there is intentionally no `ait gate`
  dispatcher entry yet): plan approved (Step 6 checkpoint), review approved
  (Step 8), merge approved (Step 9), build verified (Step 9 `verify_build`),
  risk evaluated (when `risk_evaluation: true`).
- **Design call to make here (roadmap "open problem 2"):** record-by-default
  vs opt-in. Proposal to evaluate: `gate_ledger` profile flag, default on
  for the core checkpoints, so Phase 2 re-entry (t635_5) works for every
  task — this deliberately bends the framework doc's "no `gates:` field =
  exactly like today" stance and must be decided explicitly at planning time.
- Regenerate goldens + `./.aitask-scripts/aitask_skill_verify.sh` in the
  same commit (task-workflow closure edits auto-render to other agents).

## Out of scope

Resume logic (t635_5), archival changes (t635_4), any gate that *drives*
a decision — this child only witnesses decisions already made.

## Coordination (from t635_1, landed)

The ledger substrate is available:
- **Invocation:** `./.aitask-scripts/aitask_gate.sh append <task-id> <gate>
  <status> [k=v ...]` — **full path**, not `ait gate append`. The user-facing
  `ait gate` / `ait gates` dispatcher surface was intentionally deferred to the
  phase with the first real human command (e.g. `ait gate pass`, t635_15), per
  `aitasks_extension_points.md` "the dispatcher is user-facing only".
- **Append keys:** marker line = `run` / `attempt` / `duration` / `type`;
  body lines = `verifier` / `result` / `log` / `note`. `run` defaults to now
  (ISO-8601-Z); `attempt` auto-increments for pass/fail.
- **Status / derivation:** `aitask_gate.sh status <id>` (last run per gate wins).
- **Registry:** `aitasks/metadata/gates.yaml` already seeds the 5 checkpoint
  gates this task records against — `plan_approved`, `risk_evaluated`,
  `build_verified`, `review_approved`, `merge_approved`.
- **Whitelist:** `aitask_gate.sh` is already allowlisted across all 5 touchpoints
  (runtime claude/codex + 3 seed files) — no permission work needed here.
- **Python parser:** derivation logic lives in `lib/gate_ledger.py`
  (`parse_gate_runs` / `derive_status`) — reuse it; t635_8 extends it.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 1, open problem 2)
- `.claude/skills/task-workflow/SKILL.md` Steps 6/8/9
