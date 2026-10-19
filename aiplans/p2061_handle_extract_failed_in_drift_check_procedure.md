---
Task: t2061_handle_extract_failed_in_drift_check_procedure.md
Base branch: main
Output branch: main
---

# t2061 — Handle `EXTRACT_FAILED` and incomplete runs in the Remote Drift Check Procedure

## Context

`aitask_remote_drift_check.sh` emits `EXTRACT_FAILED` with **exit 3** in two
places (`.aitask-scripts/aitask_remote_drift_check.sh`):

- ~line 196 — no usable Python (preflight, checked **before** the fetch, so it is
  never reported as `FETCH_FAILED`; added by t2035) → stdout is `EXTRACT_FAILED`;
- ~line 291 — the plan reference scan failed (unreadable plan, broken symlink,
  `lib/plan_paths.py` unreachable). Printed **after** `AHEAD:<n>` → stdout is
  `AHEAD:<n>` then `EXTRACT_FAILED`.

The verdict section (lines ~299-320) prints `OVERLAP:*` then `WEAK_OVERLAP:*`
then `NO_OVERLAP` only when there was no `OVERLAP`, then `exit 0`.

The consuming procedure `.claude/skills/task-workflow/remote-drift-check.md`
step 3 has no rule for `EXTRACT_FAILED`, for a non-zero exit, or for an
**incomplete** run (e.g. a helper killed after printing `AHEAD:<n>` — the
output is recognisable but carries no verdict). Steps 4-5 also assume every
prompt is about proven drift: the "Stop and re-verify plan" description says
"pull the drifted branch(es)", the closing message asserts remote drift, and the
stop records `stop_reason=drift` — all wrong when the check merely failed
(pulling does not fix an unusable Python or an unreadable plan).

The helper's `--help` also says "Output (always exit 0; …)", contradicting its
header and its own `EXTRACT_FAILED (exit 3)` entry.

Other agent trees have no independent source for this procedure — `.agents/`
and `.opencode/` carry only rendered `task-workflow-*-` dirs (the `-remote-`
ones committed). Re-rendering ports the change; no porting task needed.

## Implementation

### 1. `.claude/skills/task-workflow/remote-drift-check.md`

**Step 2 — make the exit status part of what is read.** Append
`; echo "DRIFT_RC:$?"` to both helper invocations (base pass and `--unsynced`
output pass). One sentence: the trailing `DRIFT_RC:<rc>` line is the run's exit
status, not a protocol token.

**Step 3 — classify each run before reading its tokens.** New lead-in:

> A run is accepted only as one of these **complete outcomes** (protocol shape
> *and* exit status):
> - `DRIFT_RC:0`, exactly one of `LEGACY_MODE_SKIP` / `LOCAL_BRANCH_MISSING` /
>   `NO_REMOTE` / `FETCH_FAILED` / `UP_TO_DATE`;
> - `DRIFT_RC:0`, `AHEAD:<n>` then zero or more `OVERLAP:` lines then zero or
>   more `WEAK_OVERLAP:` lines, **ending in a verdict**: `NO_OVERLAP` when there
>   is no `OVERLAP` line, otherwise at least one `OVERLAP` line;
> - `DRIFT_RC:3` with `EXTRACT_FAILED` as the last token (alone, or after
>   `AHEAD:<n>`) — a complete *failure* outcome.
>
> Anything else is an **incomplete run**: any other non-zero exit (2 = usage
> error, 128+n = killed), exit 3 without `EXTRACT_FAILED`, `EXTRACT_FAILED`
> with exit 0, `AHEAD:<n>` with no verdict after it, empty stdout, or an
> unrecognised line. Never read an incomplete run as any of the silent outcomes.

The existing token bullets stay (they apply to complete outcomes, so the
documented silent outcomes stay silent). Add two bullets:

- **`EXTRACT_FAILED` (exit 3), either pass** — the overlap scan could not run
  (unreadable plan, `lib/plan_paths.py` unreachable, or no usable Python —
  checked before the fetch, so not a network problem). Display "Remote drift
  check for `<branch>` could not run its overlap scan (EXTRACT_FAILED) — check
  that the plan file is readable; `ait setup` repairs a broken install."; when
  `AHEAD:<n>` preceded it, prefix "Remote `<branch>` is ahead by `<n>`
  commit(s), but …". Not a verdict: `strong-only` does not suppress it. Proceed
  to the question.
- **Incomplete run, either pass** — display "Remote drift check for `<branch>`
  did not complete (exit `<rc>`) — no drift verdict for this branch." with the
  helper's stderr. Proceed to the question.

Then define, for steps 4-5, the two facts the collected passes establish:
- **proven drift** — a pass whose complete outcome carries `AHEAD:<n>` (with a
  verdict, or with `EXTRACT_FAILED`), or the output pass's `LOCAL_BRANCH_MISSING`;
- **check failure** — a pass that was `EXTRACT_FAILED` or incomplete.

The existing "collect both passes, ask exactly once" rule is unchanged.

**Step 4 — option descriptions by case** (labels unchanged):
- "Stop and re-verify plan":
  - proven drift only → current text ("… pull the drifted branch(es) then re-pick the task");
  - check failure only → "Release the lock, revert task to Ready, and end the workflow — repair the failed check (see above), then re-pick the task";
  - both → "… pull the drifted branch(es) and repair the failed check, then re-pick the task".
- "Continue anyway": when there is a check failure, "Proceed to implementation without a drift verdict for `<branch(es)>`"; otherwise current text.

**Step 5 — "Stop and re-verify plan"** keeps the single reference to
`plan-approved-stop.md`; only the arguments vary:
- `stop_reason=drift` when any proven drift; `stop_reason=drift_check_failed`
  when only check failures.
- `closing_message`: drift-only → current text; failure-only → "Plan saved.
  Task t<task_id> reverted to Ready — the remote drift check could not run for
  <branch(es)> (<EXTRACT_FAILED | exit rc>). Repair it (`ait setup` for a broken
  install; make the plan readable), then re-pick with /aitask-pick <task_id>.";
  both → name the drifted branch(es) to pull **and** the failed check to repair,
  separately. The existing `LOCAL_BRANCH_MISSING` variant stays.

**Notes** — rewrite the "Always best-effort" bullet: network failures, missing
remote and legacy mode stay silent (`FETCH_FAILED` included); surfaced
exceptions are the output pass's `LOCAL_BRANCH_MISSING`, `EXTRACT_FAILED`, and an
incomplete run — local certainties, not network flakiness.

### 2. `.claude/skills/task-workflow/plan-approved-stop.md` — a complete fifth case

The sequence dispatches on `stop_reason` in three places and rejects anything
unlisted, so the new reason must be wired into each — otherwise a failure-only
stop hits the "stop and report" rejection *after* the lock release, leaving the
task `Implementing` with no lock.

- **Call-site list** (top): `remote-drift-check.md` step 5 →
  `stop_reason=drift`, or `stop_reason=drift_check_failed` when the check could
  not run on any pass that would otherwise have proven drift.
- **Input context table**: add `drift_check_failed` (the remote drift check
  could not run — the plan was neither verified nor shown stale).
- **Marker disposition table**: new row `drift_check_failed` | "must pass a
  drift check that actually runs before it can be implemented" | **clear**.
  Rationale: the plan was not verified against the remote, so advertising it as
  implementation-ready would be the same false signal the `drift` row avoids.
  Update the "two **clear** rows" prose to "the **clear** rows".
- **Command dispatch**: add `drift_check_failed` to the clearing bullet
  ("If `stop_reason` is `drift` … **or `drift_check_failed`** (the drift check's
  "Stop and re-verify plan" when the check could not run) **or
  `parallel_admission`** …").
- **Exhaustiveness sentence**: "There is no sixth case: … exactly `deferred`,
  `drift`, `drift_check_failed`, `resource_admission` or `parallel_admission`."
- **Stopped banner reason**: `drift_check_failed` → "remote drift check could
  not run — repair it, then re-plan".

`aidocs/gates/ledger-driven-reentry.md` (marker lifecycle table, ~line 219):
add the `drift_check_failed` row (**cleared**) — and the missing
`parallel_admission` row (**cleared**) — and replace the stale "closed at
exactly those three" with a pointer to `plan-approved-stop.md`'s exhaustiveness
sentence as the owner of the vocabulary.

### 3. `.aitask-scripts/aitask_remote_drift_check.sh` — help text only

`Output (always exit 0; structured stdout):` →
`Output (structured stdout; exit 0 except EXTRACT_FAILED, which exits 3):`.
(No test pins the old string.)

### 4. Guards — `tests/test_task_workflow_reentry_drift.sh`

New `guards_drift_protocol_coverage`, wired into `run_all_guards`; Coverage
header gets item 7:

- `drift-protocol-tokens-extracted` — token vocabulary parsed from the helper's
  header comment (between `# Output protocol` and `# Exit code:`), ≥ 10 tokens.
- `drift-procedure-handles-<TOKEN>` — each token appears backtick-prefixed in
  the step-3 slice (`slice_between … '3. **Parse each run' '4. **AskUserQuestion'`
  — anchor adjusted to the new wording).
- Focused fallback-contract guards (token presence alone cannot catch these):
  - `drift-procedure-captures-exit-status` — step 2 carries `DRIFT_RC:$?` on
    both invocations (count == 2);
  - `drift-procedure-ahead-without-verdict-is-incomplete` — step 3 states
    `AHEAD:<n>` with no verdict is an incomplete run;
  - `drift-procedure-incomplete-run-prompts` — the incomplete-run bullet routes
    to the question;
  - `drift-procedure-failure-stop-reason` — step 5 passes
    `stop_reason=drift_check_failed`.
- Negative controls (existing `negctrl` machinery, exact inverses), one each for
  `drift-procedure-handles-EXTRACT_FAILED`,
  `drift-procedure-ahead-without-verdict-is-incomplete`,
  `drift-procedure-captures-exit-status`, `drift-procedure-failure-stop-reason`.

**Dispatch guard — `tests/test_plan_approved_marker_contract.sh`.** Its
derived loop already reads the reason set from the exhaustiveness sentence and
requires each reason to sit in exactly one command region, so adding
`drift_check_failed` to the sentence makes the loop check that it is dispatched
(a name only listed in the table would fail "selects exactly one side"). Add the
side pin alongside the existing `resource_admission` one:
`'drift_check_failed' is on the clearing side`. Plus a banner pin: the
"Display `<closing_message>`" bullet maps `drift_check_failed` to a reason.
Negative control (manual, during implementation): drop
`drift_check_failed` from the clearing bullet only → the loop must FAIL; restore.

### 5. Re-render + goldens (same commit)

- `./.aitask-scripts/aitask_skill_rerender.sh remote` (committed
  `task-workflow-remote-` copies in `.claude/`, `.agents/` codex, `.opencode/`),
  plus `fast` / `default` for local use.
- Regenerate `tests/golden/procs/task-workflow/remote-drift-check-default.md`
  and `plan-approved-stop-{default,fast,remote}.md` via the loop in
  `tests/test_skill_render_task_workflow.sh`; review each diff equals the edit.

## Verification

- `bash tests/test_task_workflow_reentry_drift.sh` (new guards + negctrls)
- `bash tests/test_skill_render_task_workflow.sh`
- `bash tests/test_skill_parity_runtime_vs_rendered.sh`
- `bash tests/test_workflow_end_banner_contract.sh`
- `bash tests/test_plan_approved_marker_contract.sh`,
  `bash tests/test_plan_approved_marker_drift.sh`,
  `bash tests/test_resource_admission_stop.sh`,
  `bash tests/test_gate_plan_approval_transitions.sh`
- `bash tests/test_remote_drift_check.sh`, `bash tests/test_plan_paths_seam.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `shellcheck .aitask-scripts/aitask_remote_drift_check.sh`
- `git diff --stat` limited to: the two source procedures, helper help text,
  `aidocs/gates/ledger-driven-reentry.md`, the two tests, goldens, committed
  `task-workflow-remote-*` renders.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): commit code (`bug: … (t2061)`) and plan
separately by path, then archive via `aitask_archive.sh 2061`.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
