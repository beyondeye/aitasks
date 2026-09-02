# Parallel-Admission Preflight Procedure

Asks the shared parallel-admission checker whether any **other** in-flight task
collides with this one, and surfaces the answer before implementation starts. It
is **advisory**: no verdict ever ends the workflow on its own. Every stop is a
choice the user makes at the prompt.

Invoked from two places, both immediately after the **Remote Drift Check
Procedure** (see `remote-drift-check.md`) returned "Continue anyway":
`planning.md`'s Checkpoint, and `SKILL.md`'s **Re-entry Routing** on the
`IMPLEMENT` route. That order is load-bearing — the drift check can pull the base
branch, which changes what is in flight, so a preflight that ran first would be
reasoning about a stale world. It is deliberately **not** on the `POSTIMPL`
route: the code is already committed there, and nothing this procedure could say
would be actionable.

Control returns to the caller unless the user chose to stop or abort.

## Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The task being admitted (`16` or `16_2`). |
| `task_num` | Numeric id for `aitask_update.sh` — the task's **own** id; for a child that is the child id (`16_2`), never the parent's. |
| `plan_file` | Path to the externalized plan (e.g. `aiplans/p16_add_auth.md`). |
| `active_profile` | Loaded execution profile (or null). |

## Procedure

**Profile 'remote' sets `parallel_admission: off`** — this procedure
is a **no-op**. Do not invoke the checker, do not display anything, and return to
the caller immediately. Nothing below applies.


## Notes

- **`CLEAR` means "no known conflict at check time", never "safe to run in
  parallel".** The checker observes; it does not reserve. Overlapping work can
  begin the instant after it passes, and this procedure makes no promise about
  that. The residual closes only when t1343's declared-claims backend lands.
- **Advisory by design, not by omission.** No value of `parallel_admission` stops
  the workflow. The evidence is regex-extracted from plan prose — a path a plan
  merely *runs* inside a fenced command is indistinguishable from one it declares
  it will edit — and a measured false `CONFLICT` is on record. A heuristic of that
  shape may inform a decision; it may not make one. Any future hard-stop mode is
  gated on t1343's structured per-task declaration, not on this knob.
- **Not a gate, deliberately.** `MANUAL_VERIFICATION_REACHABLE_GATES` in
  `lib/task_utils.sh` is an allowlist and `filter_gates_for_issue_type()` would
  silently strip a new gate. The precedent is plan-verification staleness — a
  step in `planning.md`, not a gate — and the structural twin is
  `remote-drift-check.md`, which this mirrors. See
  `aidocs/framework/manual_verification_staleness.md` ("Why not a gate").
- **Distinct from resource admission, and neither may be folded into the other.**
  This asks whether *other tasks* collide with this one; `resource-admission.md`
  asks whether the *host* can afford the phase. Where both are wired, correctness
  runs before capacity: this preflight sits at the planning Checkpoint, that hook
  last, immediately before the fork.
- **No worktree exists at the planning-Checkpoint call site** — the fork is
  deferred to `SKILL.md` Step 7 — so a stop there strands nothing. On the
  `IMPLEMENT` re-entry route a worktree from the earlier session may already
  exist; it is left in place, and the next pick reuses it.
- For child tasks, `task_num` is the **child** id (e.g. `16_2`). The parent's
  status is untouched.
