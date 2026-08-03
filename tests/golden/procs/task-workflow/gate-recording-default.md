# Gate Recording Procedure

Records a workflow checkpoint into the task's **gate ledger** (the append-only
`## Gate Runs` section in the task file) and persists it so the gate state is
visible from every PC. This is the attended-mode seed of the gate framework:
the existing interactive approval (ExitPlanMode / AskUserQuestion) is unchanged
— its outcome IS the gate signal, and this procedure just *witnesses* it.

Invoked only when the active profile sets `record_gates: true` — every call-site
of **this procedure** is wrapped in that Jinja guard, so it never runs for
profiles that have not opted in. There are exactly two files with such call
sites:

- `SKILL.md` — Step 7 (`plan_approved`, and the conditional `risk_evaluated`),
  Step 8 (`review_approved`), Step 9 (`build_verified`, `merge_approved`).
- `plan-approved-stop.md` — the deferred `plan_approved` shared by both
  approved-plan stop branches.

**`planning.md` and `remote-drift-check.md` do NOT call this procedure and must
not carry a guard.** Their "Approve and stop here" / "Stop and re-verify plan"
branches delegate, unguarded, to the **Approved-Plan Stop Sequence**
(`plan-approved-stop.md`), which owns the guard once on their behalf. That
delegation is the whole point of the extraction (t1380): the recording lives in
exactly one place, so neither branch can drop it or double-guard it. Do not add
a `record_gates` conditional at either reference.

> **Recording is gated on `record_gates` ALONE.** It is *not* gated on the gate
> name appearing in the task's `gates:` / `active_gates` set. A task that
> declares no gates at all still gets `plan_approved` / `review_approved` /
> `merge_approved` recorded under a recording profile — the ledger is a record
> of what the workflow witnessed, which is why `resume_point()` can key off it
> without consulting the declared set. (The one exception is the conditional
> `risk_evaluated` self-record described below, which is about avoiding a
> *double*-record, not about eligibility.)

> **One deliberate non-guarded path (t1380).** `task-abort.md` re-opens a
> previously recorded `plan_approved` by calling `aitask_gate_record.sh`
> **directly**, conditioned on `aitask_gate.sh recorded-pass` rather than on
> `record_gates`. Do **not** "fix" that by routing it through this procedure or
> wrapping it in the Jinja guard: a task recorded under `fast` can be aborted
> under `default`, and the guard would render the demotion away in exactly the
> case where a stale approval exists. It invalidates an existing entry rather
> than recording a new checkpoint, and being conditional on that entry existing
> already makes it a no-op wherever nothing was ever recorded.

> **`risk_evaluated` is conditional (t635_14).** The Step-7 `risk_evaluated`
> self-record additionally fires **only when the task does not literally declare
> the gate** (checked via `aitask_gate.sh should-self-record <task_id>
> risk_evaluated`). For a task that *declares* `risk_evaluated` in `gates:`, the
> Step-9 gate orchestrator records it instead — self-recording here too would
> double-record. The other checkpoints (`plan_approved`, `review_approved`,
> `merge_approved`) are human gates the orchestrator never records, so they have
> no such guard.
>
> **Dual transport (t635_15).** `review_approved` / `merge_approved` carry an
> async `signal: file-touch` transport in `gates.yaml`. In an **attended**
> session this procedure records the pass directly from the interactive approval
> (the transport is unused). In the **headless/remote** lane the same gate pends
> until a human signs via `ait gate pass <task-id> <gate>` and the orchestrator
> observes it. One gate definition, two transports — attended recording here is
> unchanged.

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
