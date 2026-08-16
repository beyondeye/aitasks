---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [dependencies, aitask_ls, aitask_monitormini, aitask_board, child_tasks]
gates: [risk_evaluated]
created_at: 2026-08-16 11:26
updated_at: 2026-08-16 11:26
---

Three surfaces independently resolve a task's `depends` field, with three
different policies. Give them one decision core, so `ait ls`, the minimonitor
task picker and the board can never disagree about whether a task is blocked.

## The divergence (verified on main, 2026-08-16)

| surface | site | unresolvable dep | gate-release (t635_3) |
|---|---|---|---|
| `ait ls` | `aitask_ls.sh:268` `is_task_uncompleted` | **fail-open** — "not in the active set ⇒ completed" | yes, via `aitask_gate.sh deps-unblock-batch` |
| minimonitor picker | `monitor_core.py:3555` `blocking_dependencies` | **fail-closed** — "a dangling id must be visible, never silently treated as satisfied" | **no — absent entirely** |
| board | `aitask_board.py:1752` `unresolved_local_deps` | **fail-open** — `if dep_task and ...` | yes, via in-process `gate_ledger.read_task_gate_state` |

Two distinct wrong answers follow, and they are independent of each other:

**1. Unresolvable deps.** Live case that motivated this task: `t1159_4` carried
`depends: [2, 3]` (a hand-written shorthand for siblings `t1159_2`/`t1159_3`
that no consumer supports — `normalize_task_ids` only upgrades `N_M` → `tN_M`).
Tasks 2 and 3 are early tasks living inside `aitasks/archived/_b0/old*.tar.zst`,
which `_resolve` deliberately never extracts, so neither resolves. `ait ls`
showed the task **Ready**; the minimonitor picker showed **"blocked by t2 t3"**.
The data was corrected in commit `6f78a3e05`, which is why this task is about
the resolvers, not that task file.

**2. Gate-released dependencies — the larger defect.** `blocking_dependencies`
tests only `dep_info.status != "Done"`. It never consults the gate ledger, so a
dependency sitting at `Implementing` with every required gate `SATISFIED`
unblocks its dependents in `ait ls` and on the board while the minimonitor
picker still reports it as blocking. This is the t635_3 rule ("completed for
dependency purposes ⇒ dependents unblock before archival") missing from one of
its three consumers, and it produces a wrong verdict on perfectly well-formed
data.

## The asymmetry that makes this tractable

The **cross-repo** half already does this correctly, in both surfaces that
implement it: `xdeps` resolution is fail-closed and renders an explicit
`(UNREACHABLE)` marker rather than a silent pass — `aitask_ls.sh:436-454` and
`aitask_board.py:1763` `cross_repo_dep_display`. Local deps simply never got the
same treatment. This task brings the local half up to the standard the
cross-repo half already sets; it does not invent a policy.

## Scope

1. **Pick one policy and state it.** The recommendation is the cross-repo one —
   **fail-closed with a distinguishable rendering**: an unresolvable dep blocks
   AND is displayed differently from a merely-not-Done one (e.g. `t2
   (UNRESOLVED)`), so a dangling id reads as a data error rather than as
   ordinary upstream work. Silently passing an id nobody can resolve is the
   behaviour that let `[2, 3]` survive in two task files for months.
   Note the tri-state this implies: *satisfied* / *blocking* / *unresolvable*
   are three outcomes, not two — do not collapse the third into either of the
   others.
2. **One decision core, reused — not three agreeing implementations.**
   `lib/gate_ledger.py` is already the canonical core for the gate-release half
   and is reachable from both Python surfaces in-process and from bash via
   `aitask_gate.sh deps-unblock[-batch]`; extend that seam rather than adding a
   fourth. Whatever shape is chosen, `monitor_core.blocking_dependencies` must
   end up consulting the same gate-release rule as the other two.
3. **Keep the performance work intact.** `aitask_ls.sh` batches the whole
   candidate list through one `deps-unblock-batch` subprocess on purpose —
   t1472 measured 190 per-file invocations at ~46ms costing 9.7s of an 18.9s
   `ait ls` in this repo. Any consolidation must preserve the batched call; do
   not regress it into per-dep subprocesses.
4. **Archived-dep handling must stay correct.** `monitor_core._resolve` searches
   `aitasks/archived/`, so archived deps resolve with `status: Done` and are
   correctly satisfied. The board's `find_task_by_id` reaches only loaded
   (active) tasks and gets the right answer for a different reason. Make the
   reason the same everywhere, and keep the documented non-goal: tasks bundled
   into `archived/_b0/old<N>.tar.zst` are NOT extracted, so they will always be
   unresolvable — that is exactly the case rule 1 has to render honestly.

## Verification

- A parity test that drives all three surfaces over the **same** fixture set and
  asserts identical verdicts — surface against surface, not each against a
  private expectation. Fixtures must include: a dep that is Done, one that is
  Ready, an archived dep, an unresolvable id, and a dep that is `Implementing`
  with all gates SATISFIED (the case that currently splits 2-to-1).
- A negative control: mutate one surface's policy and confirm the parity test
  fails, naming the surface.
- Render-level assertions for the `(UNRESOLVED)`-style marker in the minimonitor
  picker (~40 columns) and the board detail pane.
- `bash tests/run_all_python_tests.sh` and the relevant bash test files stay
  green.

## Related

- **t1528** — write-time validation of the `depends` notation, so a
  malformed id cannot be written in the first place. That task is the producer
  side of the same problem; this one is the consumer side. Settle the canonical
  accepted forms here, and let the validator enforce exactly those.
- `6f78a3e05` — the data fix for `t1159_4` and `t386_7` that this task
  generalizes. `t386_7` mixed both notations in one list
  (`[t386_6, t386_10, 1, 2, 3, 4, 5, 6]`, repeating 6 after t386_6), which is
  what confirmed the bare numbers were always meant as siblings.
