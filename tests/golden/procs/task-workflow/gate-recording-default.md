# Gate Recording Procedure

Records a workflow checkpoint into the task's **gate ledger** (the append-only
`## Gate Runs` section in the task file) and persists it so the gate state is
visible from every PC. This is the attended-mode seed of the gate framework:
the existing interactive approval (ExitPlanMode / AskUserQuestion) is unchanged
— its outcome IS the gate signal, and this procedure just *witnesses* it.

Invoked only when the active profile sets `record_gates: true` — every call-site
in `SKILL.md` / `planning.md` is wrapped in that Jinja guard, so this procedure
never runs for profiles that have not opted in.

## Inputs (from the calling context)

| Variable | Description |
|----------|-------------|
| `task_id` | The task being worked (`16` or `16_2`). |
| `gate_name` | One of the registered checkpoint gates: `plan_approved`, `risk_evaluated`, `build_verified`, `review_approved`, `merge_approved`. |
| `status` | The checkpoint outcome: `pass` \| `fail` \| `skip`. |
| `fields` | Optional extra `k=v` fields. `type=human` for approvals (plan/review/merge), `type=machine` for verifications (risk/build); `verifier=<cmd>` and `note=<text>` where useful. |

## Procedure

Run (best-effort — a recording failure must never block the workflow):

```bash
./.aitask-scripts/aitask_gate_record.sh <task_id> <gate_name> <status> [k=v ...]
```

The script appends the gate-run block via `aitask_gate.sh`, commits the single
task file **path-scoped** (`ait: Record <gate_name> gate for t<task_id>`), and
best-effort pushes to the data branch. It always exits 0. Do **not** add a
separate commit for the recording — the script handles persistence.
