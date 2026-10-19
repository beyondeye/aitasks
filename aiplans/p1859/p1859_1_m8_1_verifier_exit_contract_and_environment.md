---
Task: t1859_1_m8_1_verifier_exit_contract_and_environment.md
Parent Task: aitasks/t1859_testmap_m8_completion_policy_and_gates.md
Sibling Tasks: aitasks/t1859/t1859_2_*.md, aitasks/t1859/t1859_3_*.md, aitasks/t1859/t1859_4_*.md, aitasks/t1859/t1859_5_*.md, aitasks/t1859/t1859_6_*.md
Archived Sibling Plans: aiplans/archived/p1859/p1859_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1859_1 — M8.1 Verifier exit contract and environment (coarse)

## Context

Parent t1859 (M8 — Completion policy and gates); Module Map row **M8.1**; wave
**A**. This child sets the contract `./ait test --gate` speaks to the gate
machinery:

- exit 75 (host refused resources) and exit 3 (framework could not run) become
  a verifier **error** for opted-in keys;
- the error is retried within budget, and is never a code failure or a skip;
- two variables tell the command which task and gate run it serves;
- a carrier lets the command put one line into the gate block's `result=`.

This coarse plan records what the proposal fixes for M8.1. It does not design internals against providers that do not exist yet; the Reality check below
does that when this child is picked.

**Automation-first:** no path may require a human action. A human-only step met
in the proposal is reported to its owning parent and never encoded.

## Proposal reading list

- The Module Map `#### M8` row (M8.1).
- Component *Gates* (the M8.1 sentences).
- *Run Surface → Output and exit contract*, *The two environment variables*.
- *Workflow Seam → The concrete edits* (the lib and helper rows), *Gates*.
- `assumption_gate_exit_contract_reused`; Invariants 8 and 9; Open question 4
  (the default is that any `test_command` sees the variable).
- Parent plan `aiplans/p1859_testmap_m8_completion_policy_and_gates.md`:
  Deviations 1 (64 stays a fail) and 2 (the result carrier), and the *M8.1
  helper contract* note.

## Owned files / provides / consumes

- **Owns:**
  - the two rows, the exports and the carrier in
    `.aitask-scripts/lib/gate_verifier_lib.sh`;
  - the export and the verdict contract in
    `.aitask-scripts/aitask_run_project_command.sh`;
  - the new `tests/test_gate_verifiers.sh` cases.
- **Provides:** the contract `./ait test --gate` speaks, `AIT_GATE_TASK_ID`,
  `AIT_GATE_RUN_ID` and `AIT_GATE_RESULT_FILE`. Consumers are M5.1 (mode),
  M8.4 / M8.5 (writing `result=`), M9.1 (`build-verification.md` branch) and
  M9.2.
- **Consumes:** no test-map module. It uses existing framework files only:
  `lib/gate_orchestrator.py` (`map_exit`, `reconcile_terminal`),
  `lib/gate_ledger.py` (`error` in `VALID_STATUSES`), and
  `aitask_gate.sh append`.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

1. Re-read the M8.1 row, the component sentences, and the interface row "the
   verifier exit contract and the two environment variables" (as amended by
   the parent's Deviation 2: plus the carrier).
2. Inspect the current state of each file this child touches, and name the
   task and commit that last landed it: `run_project_command_key` /
   `run_command_gate` (t1610 `3ee86c5ca`, t1729 `ce3a10af3` at coarse time),
   the helper's header and outputs, the orchestrator's `map_exit` and
   `reconcile_terminal`, and the ledger's status vocabulary.
3. Tabulate the differences in three columns: *proposal says* / *coarse plan
   says* / *repository has*.
4. Decide each difference: adapt, revise this plan, or revise the proposal.
   Record the decision and the reason. Child-specific questions:
   - Does an appended `error` block followed by exit 3 reconcile as a no-op?
   - Is the `result=` value rendered as a `> Result:` line, so that CR/LF is
     what must be sanitized?
   - The helper's `VERDICT:` header contract for the new verdict: emit
     `VERDICT:error` plus a reason with exit 3, or keep exit 3 verdict-less?
     Either way, `build-verification.md`'s capture form must still classify
     the result as infrastructure until M9.1 lands.
   - The carrier with a list of commands: truncate per command, and keep the
     value from the command that decided the verdict.
5. Send notes (`/aitask-note`) to every downstream child or parent whose
   assumptions a difference breaks (M5.1 in t1856, M9.1/M9.2 in t1860, M8.4
   `t1859_4`), hedging what the tree cannot prove.
6. Re-confirm that every touched file is owned by this submodule.

## Implementation steps (coarse)

1. In `run_project_command_key`, opted-in keys only:
   - exit 75 → `PROJECT_CMD_STATUS=error`, `CODE=3`,
     `REASON=command_refused`;
   - exit 3 → `error` / 3 / `command_errored`;
   - 64 and every other non-zero code stay `fail`; 2 stays the opt-in skip.

   Update the docblock table, which is the single canonical statement.
2. In `run_command_gate`:
   - export `AIT_GATE_TASK_ID`, `AIT_GATE_RUN_ID` and
     `AIT_GATE_RESULT_FILE=.aitask-gates/<task>/<gate>_<run>.result` around
     the command;
   - append the `error` block with its reason, and return 3;
   - read the carrier: first line, CR/LF stripped, length-capped. Use it as
     `result=`, keeping the reason prefix. Absent or empty keeps today's text.
3. In `aitask_run_project_command.sh`, make `--task-id` also export
   `AIT_GATE_TASK_ID`. Restate the header contract for the `error` verdict.
4. Write the tests.

## Verification / acceptance

In `tests/test_gate_verifiers.sh` (with the file-backed counters if bodies run
in subshells):

- Opted-in exit 75 → an `error` block with `command_refused` and return 3.
  Opted-in exit 3 → `error` with `command_errored` and return 3.
- Not opted in: 75 → fail, 3 → fail.
- 64 → fail. 2 → skip, unchanged.
- The command sees `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID`, and
  `aitask_run_project_command.sh --task-id` exports the former.
- The carrier:
  - present → `result=` carries it;
  - absent or empty → today's text;
  - multi-line → first line only;
  - a list of commands → the deciding command's value.
- A negative control proves that each new row is the one that fires.
- `shellcheck` is clean.
- No path requires a human action.

## Step 9 reference

The shared post-implementation flow (task-workflow Step 9): current branch, no
merge, archival via the workflow.
