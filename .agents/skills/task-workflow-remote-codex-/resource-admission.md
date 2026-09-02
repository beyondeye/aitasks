# Resource Admission Procedure

Consults the project's **resource-admission hook** immediately before
implementation starts, and parks the task on its approved plan when the host
cannot afford the phase. Invoked from `SKILL.md` **Step 7** — after the
pre-implementation ownership guard, before the deferred worktree fork — on both
routes that reach it: a fresh pick (the Checkpoint approved the plan and the
Remote Drift Check returned "Continue anyway") and **Re-entry Routing**'s
`IMPLEMENT` resume. Control returns to Step 7 only on an admit.

Planning is cheap; implementation and verification are memory-bound. This is the
one place the workflow asks "can this host afford to start now?" — and it asks
the *project*, which is the only party that knows what "afford" means for it.

**Unset ⇒ nothing happens.** A project that has not configured
`resource_admission_command` in `aitasks/metadata/project_config.yaml` sees no
prompt, no stop, no display and no file: the helper reports `none_configured`
and returns without creating a log.

## Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The task being admitted (`16` or `16_2`). |
| `task_num` | Numeric id for `aitask_update.sh` — the task's **own** id; for a child that is the child id (`16_2`), never the parent's. |
| `plan_file` | Path to the externalized plan (e.g. `aiplans/p16_add_auth.md`). |

## Procedure

1. **Run the helper.** Capture stdout with the `if`-form — a bare
   `out="$(…)"; rc=$?` dies under `set -e` before `rc` is read:

   ```bash
   if out="$(./.aitask-scripts/aitask_resource_admission.sh --task-id <task_id> --plan <plan_file>)"; then
     rc=0
   else
     rc=$?
   fi
   ```

   **Never merge stderr into stdout.** Every line this procedure acts on is a
   `KEY:value` line — `VERDICT:`, `REASON:`, `DETAIL:`, `LOG:` and, on exit 3,
   `DIAG:`. Merging stderr would corrupt that parse, which is precisely why the
   helper puts a sanitized diagnostic on stdout instead of leaving it on stderr.

2. **Exit 0 with `REASON:none_configured`** → **display nothing at all** and
   return to Step 7. A project that never enabled this must not learn about it
   from a line in every pick.

3. **Exit 0 otherwise** → display "Resource admission: admitted (\<`DETAIL`\>)"
   and return to Step 7.

   Say **admitted**, never "safe": the hook observes, it does not reserve. Another
   agent can claim the memory the instant after it answers, and this procedure
   makes no promise about that.

4. **Any non-zero exit** → **park the task.** Never treat a non-zero as an admit,
   and never re-run the hook hoping for a better answer. Execute the
   **Approved-Plan Stop Sequence** (see `plan-approved-stop.md`) with `task_id`,
   `task_num`, `plan_file`, `stop_reason=resource_admission`,
   `revert_commit_message="ait: Revert t<task_num> to Ready (resource admission)"`,
   and a `closing_message` built from the verdict:

   - **`VERDICT:refuse` (exit 1)** — the hook decided. Name its reason
     (`DETAIL`), the log (`LOG`), and the remedy: "Task t\<task_id\> parked with
     its approved plan. Free the resource and re-pick with `/aitask-pick
     <task_id>` — planning is skipped (`ait ls --plan-approved` lists it)."

   - **`VERDICT:error` (exit 2)** — the hook ran and could **not** decide
     (unparseable command, or an exit code that is neither admit nor refuse).
     Say so: "The resource-admission hook could not be evaluated: \<`DETAIL`\>.
     See \<`LOG`\>." Then the same park message, plus the second remedy: fix or
     unset `resource_admission_command` in `aitasks/metadata/project_config.yaml`.
     This is fail-closed on purpose — a host that cannot be probed is exactly the
     one that runs out of memory mid-verification — and a broken hook must never
     read as a shortage.

   - **no `VERDICT:` line (helper exit 3)** — the helper could not evaluate at
     all (a bad argument, a list-valued key, an unwritable log). Report `DIAG:`,
     the bounded sanitized diagnostic the helper guarantees on this exit, as a
     **wiring error** — naming `LOG:` when it is not `(none)` — and then park
     through the same **Approved-Plan Stop Sequence** with
     `stop_reason=resource_admission`. A missing verdict is not an escape from
     the park. Never quote raw stderr in its place: it is not captured here, and
     it is neither bounded nor sanitized.

   The three read differently on purpose. A refusal and a broken hook route the
   same way but must never look the same — "refused" and "never actually asked"
   are different facts about the host.

## Notes

- **Not a gate.** This is an admission decision at a workflow seam. Nothing is
  appended to the gate ledger — the `plan_approved` recording inside the stop
  sequence is pre-existing and unchanged — so `archive-ready`, `resume-point`
  and `workflow-phase` see no new state, and a parked task is indistinguishable
  from any other approved-and-stopped task on every surface that reads them.
- **The park is a defer, never a failure.** The plan stays approved and
  committed, the task returns to `Ready` with `plan_approved_at` stamped, and no
  branch or worktree is left behind: this procedure runs *before* Step 7's
  deferred fork, exactly like the other two stop call sites.
- **No profile knob.** An unset key is already the opt-out, and whether a host
  can afford a phase must not vary with how chatty a profile is. Every profile
  renders this identically.
- **Distinct from the parallel-admission preflight.** That check
  (`parallel_admission` profile knob, `aitask_parallel_admission.sh`) asks
  whether *other tasks* collide with this one; this one asks whether the *host*
  can afford it. Where both are wired, correctness runs before capacity: the
  parallel preflight sits at the planning Checkpoint, this hook last, immediately
  before the fork. Neither may be folded into the other. Their dispositions also
  differ: the parallel preflight is **advisory** and never stops on its own,
  while a refusal here parks the task.
- **Availability is structural, not statistical.** The hook is opt-in and runs
  one local command, so a project that configures it gets an answer every time or
  a named error. There is no "cannot decide" population to measure — unlike a
  checker that reads shared state it does not control, which is exactly why the
  parallel preflight is advisory and this hook can park.
