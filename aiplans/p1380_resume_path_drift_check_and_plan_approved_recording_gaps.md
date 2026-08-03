---
Task: t1380_resume_path_drift_check_and_plan_approved_recording_gaps.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1380 — Resume-path drift check and `plan_approved` recording gaps

## Context

An `/aitask-explore` investigation into "is `plan_approved` recorded so a
crashed task can resume after planning?" answered the question (yes, gated on
the profile key `record_gates`, independent of the declared `gates:` set) and
surfaced four concrete defects on that resume path:

1. `remote-drift-check.md`'s **"Stop and re-verify plan"** branch claims to run
   "the same release-and-revert sequence" as `planning.md`'s **"Approve and stop
   here"**, but reproduces only that branch's *numbered steps 1–5*. The Gate
   Recording call sits **above** the numbered list (unnumbered), so the copy
   silently dropped it — a user who reached the drift check by choosing "Start
   implementation" (i.e. the plan *was* approved) ends the session with an empty
   ledger.
2. The Remote Drift Check runs from exactly one place (`planning.md`'s
   Checkpoint). **Re-entry Routing bypasses Step 6 entirely**, so a resumed task
   — by construction the one whose plan is *oldest* relative to the remotes —
   is the only one that gets no drift check at all.
3. `planning.md:402` describes its `plan_approved` recording as "this is the
   resume signal", but the same branch reverts the task to `Ready`, and Check 5
   is gated on `status == Implementing`. The recorded entry can never drive
   routing.
4. `task-abort.md` never re-opens a previously recorded `plan_approved`. It is
   harmless today only *incidentally* — abort reverts status, so Check 5's gate
   skips the stale entry. The safety is an accident, not an invariant.

Intended outcome: the two stop branches become structurally incapable of
drifting apart, resumed tasks get the remote checks they most need, the
"approve-and-stop" resume story is made internally consistent, and abort's
interaction with a stale checkpoint becomes an explicit, tested invariant.

**Out of scope (recorded in the task):** flipping `record_gates` on for the
`default` profile. Everything gate-*recording* below is inert under `default` /
`remote` (neither sets the key), by design.

## Verified findings that shape the design

- **Step 9 never fetches.** `grep -n "git fetch\|git pull" .claude/skills/task-workflow/SKILL.md`
  returns nothing. Step 9's pre-flight checks only that `refs/heads/<output_branch>`
  exists locally and is not held by another worktree; `git merge` is purely
  local. So a **stale local output branch merges cleanly** and remote divergence
  surfaces only when the user later pushes (non-fast-forward). "The merge itself
  surfaces divergence" is false — a `POSTIMPL` exemption cannot rest on it.
- **Re-entry Routing has no branch-name extraction.** The plan-existence guard
  says only "read the plan and continue below". A resumed session carries none
  of `base_branch` / `output_branch`, and Step 9's own text already warns that a
  resumed session "may run under a different profile" — so the header, never the
  profile, must be the source.
- **`tests/test_remote_drift_check.sh` already has a real git-fixture harness**
  (`make_branch_mode_pair`, and "Test 8b: legacy mode, origin/dev ahead of local
  dev" asserting `AHEAD:1`) — the stale-local/advanced-origin case builds on it.
- **`aitask_gate.sh` and `aitask_gate_record.sh` are already permission-allowlisted**
  in `.claude/settings.local.json`, `seed/claude_settings.local.json`,
  `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`. Adding a
  *verb* to `aitask_gate.sh` needs no allowlist churn; a **new script would need
  edits in all four**. That is why the design below adds a verb, not a script.

## Design decisions (confirmed with the user)

- **Defect 3 → history-only.** Check 5 keeps its `status == Implementing` gate.
  A stop-branch `plan_approved` pass is an **audit record of approval**, not a
  routing signal: the branch reverts the task to `Ready`, so on re-pick §6.0's
  existing-plan preference is what resumes it — and that path *does* reach the
  Checkpoint, hence the drift check. `planning.md`'s inline claim is corrected.
- **Defect 2 → `IMPLEMENT` runs the drift check; `POSTIMPL` gets a merge-target
  sync pre-flight** (the exemption is *revised*, not kept — see above).
- **Step 5's missing worktree-reuse rule** (pre-existing; unreachable on every
  profile that records gates) is out of scope — standalone bug task at Step 8b.

## Changes

### A. New shared procedure — `.claude/skills/task-workflow/plan-approved-stop.md`

Per `skill_authoring_conventions.md` §"Extract new procedures to their own
file". This is the structural fix for Defect 1: both stop branches become
two-line references, so a partial copy is no longer possible.

**Name:** Approved-Plan Stop Sequence Procedure.
**Inputs:** `task_id`, `task_num`, `plan_file`, `stop_reason` (`deferred` |
`drift`), `revert_commit_message`, `closing_message`.

**Body:**

1. *(Jinja-guarded — `{% if profile.record_gates is defined and profile.record_gates %}`)*
   **Record the approval, once.**
   ```bash
   ./.aitask-scripts/aitask_gate.sh recorded-pass <task_id> plan_approved
   ```
   Exit **1** (not already `pass`) → **Gate Recording Procedure**
   (`gate-recording.md`) with `gate_name=plan_approved`, `status=pass`,
   `fields="type=human note=<stop_reason>"`. Exit **0** → skip (an earlier
   session already recorded it; re-appending only adds a redundant commit).
   Followed by the explicit statement that this is an **audit record of the
   approval, not a routing signal** — the task is about to become `Ready`, so
   Check 5's status gate skips it and §6.0's plan preference governs the resume.
2. Ensure the plan file is committed (idempotent) — verbatim from today's steps.
3. Release the task lock via the **Lock Release Procedure**.
4. `aitask_update.sh --batch <task_num> --status Ready --assigned-to ""`.
5. Commit + push the revert using `<revert_commit_message>`.
6. Display `<closing_message>`.
7. **Note:** the worktree and `aitask/<task_name>` branch are intentionally left
   in place (this is a stop, not an abort).

Jinja comment rulers per the inline `{# ---------- record_gates ---------- #}`
convention. The file is **profile-varying** (3 goldens).

### B. `planning.md` — "Approve and stop here"

Replace the `{%- if profile.record_gates … %}` block **and** numbered steps 1–5
with a single reference to the Approved-Plan Stop Sequence, passing
`stop_reason=deferred`,
`revert_commit_message="ait: Revert t<task_num> to Ready after plan approval"`,
and today's closing message. Keep the trailing "always available (not
profile-gated)" sentence. The `record_gates` guard disappears from
`planning.md` — it now lives once, in the shared file.

### C. `remote-drift-check.md` — "Stop and re-verify plan"

Replace numbered steps 1–5 with the same reference, `stop_reason=drift`,
`revert_commit_message="ait: Revert t<task_num> to Ready (remote drift)"`, and a
`closing_message` that names the drifted branch(es) (preserving today's
`LOCAL_BRANCH_MISSING` variant wording). **No Jinja is added** — the file must
stay profile-invariant or `test_skill_render_task_workflow.sh` Test 1b fails;
its `remote_drift_check: skip` conditional and Test 3/Test 4 literals are
untouched.

### D. New procedure — `.claude/skills/task-workflow/merge-target-sync.md`

**Merge-Target Sync Pre-flight Procedure.** Jinja-free (so: no golden, but it
does join the render closure and the three tracked `task-workflow-remote-`
trees). Fixes the invalid `POSTIMPL` exemption.

**Inputs:** `output_branch` (already resolved + validated by the caller),
`plan_file`, `task_id`.

**Body:**

1. ```bash
   ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced "$output_branch" "<plan_file>"
   ```
   (`--unsynced` is mandatory: the output branch is never checked out during
   implementation, so the legacy-mode "already pulled" premise does not hold.)
2. Act on the result:
   - `UP_TO_DATE` / `NO_REMOTE` / `LEGACY_MODE_SKIP` → return; no display.
   - `FETCH_FAILED` → return; **no display** (it is not evidence about the local
     branch — same cry-wolf rule the drift check already applies).
   - `LOCAL_BRANCH_MISSING` → display "Output branch `<b>` is not present
     locally — the Step 9 merge will fail." and return; Step 9's own pre-flight
     stops on it, and surfacing it here saves the user the merge-approval prompt.
   - `AHEAD:<n>` (± `OVERLAP:` lines) → display the count and any overlapping
     files, then **AskUserQuestion**, header "Merge target":
     - **"Sync `<output_branch>` now (Recommended)"** — fast-forward only:
       ```bash
       git checkout "$output_branch" --
       git symbolic-ref --short HEAD          # MUST print "$output_branch"; else STOP
       git merge --ff-only "origin/$output_branch"
       ```
       A non-zero `--ff-only` means the local branch holds commits `origin`
       lacks — a real divergence. **Stop and ask**; never rebase, reset, or
       force. On success, return so the caller proceeds to Step 9.
     - **"Continue anyway"** — return, having warned that the merge will be
       local-only and the eventual push may be rejected non-fast-forward.
     - **"Stop here"** — end the session **without merging**. Do **not** revert
       the task: it stays `Implementing` at `POSTIMPL` and is re-enterable,
       because the code is already committed and `review_approved` recorded.
       (The deliberate difference from the pre-implementation stop branch, which
       reverts to `Ready`.)

**Why a sync pre-flight rather than the drift check** — stated in the file: at
`POSTIMPL` the base branch is irrelevant (the plan is no longer being followed),
and the drift check's only actionable branch would revert reviewed, committed
work to `Ready`.

**Known gap, dispositioned:** the same staleness affects the *non-resumed* Step 9
path. Wiring this procedure into Step 9 unconditionally adds a network fetch and
a possible prompt to **every** task's merge — a behaviour change for every user,
in the same class as the `record_gates` flip this task explicitly carves out. A
standalone task is filed at Step 8b to make that call on its own merits.

### E. `SKILL.md` — Re-entry Routing (Defects 2 + the branch-resolution gap)

**E1 — new "Resolve the plan's branches" step**, inserted into Re-entry Routing
immediately after the plan-existence guard (it feeds both routes):

> The resumed session carries none of the Step 5 branch variables, and its
> profile may differ from the original's. Resolve both branches **from the plan
> header only** — never from `profile.base_branch` / `profile.output_branch`
> (the same rule Step 9 states for exactly this reason). Bind to variables; do
> not substitute the literals:
>
> ```bash
> base_branch=$(sed -n 's/^Base branch: //p' "<plan_file>" | head -n1)
> [ -n "$base_branch" ] || base_branch=main        # legacy plan, no field
> output_branch=$(sed -n 's/^Output branch: //p' "<plan_file>" | head -n1)
> [ -n "$output_branch" ] || output_branch=main    # two-rung rule; NEVER fall back to Base branch:
> for b in "$base_branch" "$output_branch"; do
>   printf '%s' "$b" | grep -qE '^[A-Za-z0-9._/-]+$' &&
>     git check-ref-format --branch "$b" >/dev/null 2>&1 || echo "UNSAFE_BRANCH:$b"
> done
> ```
>
> `UNSAFE_BRANCH:<b>` → **stop**: report it and resume nothing (fail closed).
> Record each value's provenance ("plan header" vs "legacy plan, no field") and
> name it in any prompt, exactly as Step 9 does.

**E2 — `IMPLEMENT` route**, after the worktree-reuse step and *before* the
implementation body:

> **Remote drift check (re-entry).** Execute the **Remote Drift Check
> Procedure** (`remote-drift-check.md`) with `base_branch` (from E1),
> `plan_file`, `task_id`, `task_num` and `active_profile`. Pass **no**
> `output_branch` value of your own — the procedure re-derives it from the same
> plan header (step 2), which is what keeps the base and output passes on one
> rule. A resumed task's plan is by construction the oldest relative to
> `origin/<base>` and `origin/<output>`, so this is the path that most needs the
> check. If the procedure ends the workflow ("Stop and re-verify plan" / "Abort
> task"), **stop** — do not resume implementation.
>
> **The loop terminates.** "Stop and re-verify plan" reverts the task to
> `Ready`; the re-pick therefore fails Check 5's `Implementing` status gate,
> never reaches Re-entry Routing, and runs the normal planning path — whose
> Checkpoint runs the check once more, now against the pulled branches. The
> check that sent the user away is not the one they land back on.

**E3 — `POSTIMPL` route**, before handing to Step 9:

> **Merge-target sync pre-flight.** Step 9 never fetches — its pre-flight only
> checks local ref existence and worktree conflicts, and `git merge` is purely
> local, so a stale local output branch merges cleanly and the divergence
> surfaces only at push time. Execute the **Merge-Target Sync Pre-flight
> Procedure** (`merge-target-sync.md`) with `output_branch` (from E1),
> `plan_file`, `task_id`. If it ends the session ("Stop here"), do not proceed
> to Step 9. The full pre-implementation drift check is deliberately **not** run
> here — see that file for why.

**E4** — add `plan-approved-stop.md` and `merge-target-sync.md` to SKILL.md's
**Procedures** list (unguarded entries; the `record_gates` guard lives inside
the first file).

### F. `task-abort.md` — demotion (Defect 4)

Insert between "Release task lock" and "Revert task status":

> - **Re-open a recorded plan approval (ledger-conditional, NOT profile-gated):**
>   ```bash
>   ./.aitask-scripts/aitask_gate.sh recorded-pass <task_id> plan_approved
>   ```
>   Exit **0** — a previous session recorded the plan as approved and this abort
>   rejects it. Append the demotion so the ledger stops claiming approval:
>   ```bash
>   ./.aitask-scripts/aitask_gate_record.sh <task_id> plan_approved fail type=human note=aborted
>   ```
>   Exit **1** — nothing recorded; skip. This is the common case, and the *only*
>   case on a project that has never run a recording profile.
>
>   **Why this is not wrapped in the `record_gates` guard:** a task recorded
>   under `fast` can be aborted under `default`, and a Jinja guard would render
>   the demotion away in exactly that case. Gating on **ledger content** instead
>   keeps it a no-op wherever no approval was ever recorded, so
>   `record_gates: false` behaviour is unchanged. (Same reasoning
>   `aidocs/gates/ledger-driven-reentry.md` already uses to reject Jinja-gating
>   the re-entry prose.)

`task-abort.md` stays Jinja-free and therefore golden-free.

### G. `aitask_gate.sh` — new decision verb `recorded-pass`

`recorded-pass <task-id> <gate>` — exit **0** iff the gate's **current derived**
status (last-marker-wins) is `pass`; exit **1** otherwise (absent, `fail`,
`skip`, `pending`, `running`, `error`).

- Pure **bash**, reusing the last-wins awk already in `cmd_status`: extract it
  into `_derive_gate_status <file> <gate>` that both call, so the two
  derivations cannot diverge. Existing bash↔python byte-parity coverage for
  `status` in `tests/test_gate_ledger.sh` characterizes that extraction.
- Established `AIT_GATES_BACKEND=python` delegation arm; matching
  `recorded-pass` arm in `lib/gate_ledger.py` (over `derive_gate_runs`).
- **Degrade → exit 1** ("not recorded"). Safe for both consumers: the stop
  sequence then records a harmless duplicate, and abort skips a demotion that
  cannot matter because `resume-point` also degrades to `PLAN`.
- Strict `== "pass"` deliberately mirrors `resume_point`'s predicate, **not** the
  module-wide `SATISFIED_STATUSES = {pass, skip}` used by `archive_status`.
- Add to the `--help` text and to `gate-cli.md`'s Decision-verbs table.

### H. Docs

- **`gate-recording.md`** — today it states every call site is wrapped in the
  `record_gates` guard. Add an explicit exception paragraph: the Gate Recording
  **Procedure** is `record_gates`-gated, but the **ledger-conditional plan-approval
  re-open** in `task-abort.md` calls `aitask_gate_record.sh` directly and must
  **not** acquire that guard — it invalidates a stale entry rather than
  recording a checkpoint, and is already conditional on the entry existing.
  Also state that recording is governed by `record_gates` **alone**, never by
  `plan_approved` appearing in `gates:` / `active_gates` (the misconception that
  seeded this task).
- **`aidocs/gates/ledger-driven-reentry.md`** — four new sections plus one
  rejected alternative:
  - *Branch resolution on re-entry* — header-only, two-rung, validated (E1).
  - *Remote checks on re-entry* — `IMPLEMENT` runs the drift check; `POSTIMPL`
    runs the merge-target sync pre-flight instead, **with the corrected
    rationale** (Step 9 never fetches) and the loop-termination argument.
  - *"Approved and stopped" is not a routing signal* — the two resume
    mechanisms (Check 5 for `Implementing`; §6.0 plan preference for `Ready`).
  - *Abort demotes a recorded `plan_approved`* — the explicit invariant and why
    it is ledger-conditional.
  - Rejected: *relaxing Check 5's status gate* (skips the Checkpoint and hence
    the drift check on exactly the Defect-2 path; makes the demotion the sole
    safety barrier).

## Tests

### New — `tests/test_gate_recorded_pass.sh`

Unit matrix in the established `TASK_DIR` fixture style: no ledger → 1; `pass` →
0; `pass`→`fail` → 1; `fail`→`pass` → 0; `skip` → 1; `pending` → 1; child id
resolves; missing args → nonzero + usage on stderr; bash↔python
(`AIT_GATES_BACKEND=python`) agreement on every row.

### New — `tests/test_gate_plan_approval_transitions.sh` (behavioural, answers concerns 3 & 4)

A **git-initialised** fixture repo (so `aitask_gate_record.sh`'s persistence runs
for real), driving the two documented command sequences as shell functions named
after the procedures, and asserting the **ledger transitions** — not strings:

1. *drift-stop on a task with no prior approval* → ledger gains `plan_approved`
   `pass` carrying `note=drift`; `resume-point` = `IMPLEMENT`.
2. *drift-stop on a task that already has the pass* → marker count for
   `plan_approved` is **unchanged** (the `recorded-pass` guard suppressed the
   duplicate).
3. *abort on that same task* → `plan_approved` current run is `fail` with
   `note=aborted`; `recorded-pass` now exits 1; `resume-point` = `PLAN`. Run
   with **no profile in scope at all** — which is exactly the "fast-recorded
   ledger handled under `default`" case, since both scripts are profile-agnostic.
4. *abort on a task with no ledger* → nothing appended and **no `## Gate Runs`
   section created** — the executable proof of AC "behaviour under
   `record_gates: false` is unchanged".

Bound to the prose by a companion assertion that the **rendered** `default`,
`fast` and `remote` copies of `task-abort.md` all contain the `recorded-pass …
plan_approved` and `aitask_gate_record.sh … plan_approved fail` lines — proving
no Jinja gate removes the demotion on any profile (concern 4's cross-profile
guard), and that the sequence the test executes is the sequence the agent is
told to run.

### New — `tests/test_task_workflow_reentry_drift.sh` (structural)

Predicates over source content (each also driving its negative control):

1. `planning.md` "Approve and stop here" references `plan-approved-stop.md` and
   no longer contains the inline `--status Ready --assigned-to ""` revert.
2. `remote-drift-check.md` "Stop and re-verify plan" likewise.
3. `plan-approved-stop.md` contains `gate_name=plan_approved`, `recorded-pass`,
   `note=<stop_reason>`.
4. Re-entry Routing: the branch-resolution block contains
   `sed -n 's/^Output branch: //p'`, `UNSAFE_BRANCH`, `check-ref-format`, and
   **not** `profile.output_branch`; the `IMPLEMENT` bullet references
   `remote-drift-check.md`; the `POSTIMPL` bullet references
   `merge-target-sync.md`.
5. `merge-target-sync.md` contains `--unsynced`, `merge --ff-only`,
   `symbolic-ref`, and **not** `--status Ready` (a POSTIMPL stop must never
   revert).
6. Render guards: `plan-approved-stop.md` at `default` contains **none** of
   `Gate Recording Procedure` / `aitask_gate_record.sh` / `gate_name=plan_approved`;
   at `fast` it contains all three.

**Negative controls** — for each guard, `sed`-mutate the real source file,
re-invoke *this script* as a subprocess with `AIT_NEGCTRL_CHILD=1` (which skips
the negctrl phase), assert the child exits **1** *and* that its output names the
expected assertion, then restore by reversing the mutation — never
`git checkout` (a concurrent session's edits must survive). `trap` on EXIT
restores on crash. One mutation per control.

### Extend — `tests/test_remote_drift_check.sh` (answers concern 1)

Reusing `make_branch_mode_pair`, a `dev` output branch whose `origin` advanced
while local is stale:

1. `--unsynced dev <plan>` reports `AHEAD:1` (the detection).
2. **The gap:** `git merge` of the task branch into the *stale local* `dev`
   succeeds and `git rev-list --count dev..origin/dev` is still `1` — i.e. the
   local merge demonstrably hides the divergence, which is what invalidates the
   "the merge surfaces it" exemption.
3. **The recovery:** `git merge --ff-only origin/dev` fast-forwards and the
   count drops to `0`.
4. **The refusal:** with a local-only commit on `dev` as well, `--ff-only`
   exits non-zero and leaves `dev` unmoved — pinning "never rebase, reset, or
   force".

### Extend — `tests/test_gate_reentry.sh`

- Abort-then-re-pick invariant: `plan_approved pass` → demotion → `resume-point`
  is `PLAN`, pinned **independently of** Check 5's status gate.
- Close the noted coverage gap: `plan_approved` `skip` → `PLAN`,
  `review_approved` `skip` → `IMPLEMENT`, pinning the deliberate divergence from
  `SATISFIED_STATUSES` that `recorded-pass` mirrors.

### Update — `tests/test_skill_render_task_workflow.sh`

- Add `plan-approved-stop.md` to `WRAPPED_FILES_VARYING` (3 new goldens).
  `merge-target-sync.md` is Jinja-free → no golden (like `task-abort.md`).
- Test 6: `gate_name=plan_approved` now asserted on `plan-approved-stop.md`
  instead of `planning.md`; add assertions that `planning.md` **and**
  `remote-drift-check.md` reference `plan-approved-stop.md`; extend the
  `default` zero-footprint check to the new file.
- Update the header comment's file/golden counts.

## Verification

```bash
cd /home/ddt/Work/aitasks

# 1. goldens (remote-drift-check keeps its single canonical -default golden)
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for f in SKILL planning plan-approved-stop; do for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/$f.md aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/procs/task-workflow/$f-$p.md
done; done
"$PYTHON" .aitask-scripts/lib/skill_template.py \
  .claude/skills/task-workflow/remote-drift-check.md \
  aitasks/metadata/profiles/default.yaml claude \
  > tests/golden/procs/task-workflow/remote-drift-check-default.md

# 2. refresh every rendered closure — ONE CALL PER PROFILE
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done

# 3. closure walk + stubs + committed-prerender freshness + wrapper parity
./.aitask-scripts/aitask_skill_verify.sh
shellcheck .aitask-scripts/aitask_gate.sh

# 4. tests
bash tests/test_gate_recorded_pass.sh
bash tests/test_gate_plan_approval_transitions.sh
bash tests/test_task_workflow_reentry_drift.sh
bash tests/test_remote_drift_check.sh
bash tests/test_gate_reentry.sh
bash tests/test_skill_render_task_workflow.sh
bash tests/test_gate_ledger.sh
bash tests/test_gate_guarded_archival.sh
bash tests/test_gate_active_gates.sh
bash tests/test_skill_parity_runtime_vs_rendered.sh
bash tests/test_gate_verifiers.sh
bash tests/test_parallel_cross_repo_planning_procedure.sh
bash tests/test_query_files_inflight.sh
bash tests/test_skill_template.sh
bash tests/test_skill_render_uniform.sh
bash tests/test_skill_rerender.sh
bash tests/test_skill_verify.sh
bash tests/test_skill_dispatch_contract.sh
for t in tests/test_skill_render_aitask_*.sh; do bash "$t"; done
bash tests/test_release_tarball.sh
bash tests/run_all_python_tests.sh    # read ONLY the last line for the verdict
```

**Review the golden diff, don't rubber-stamp it** — `SKILL.md`'s must be
confined to Re-entry Routing and the Procedures list; `planning.md`'s to the
"Approve and stop here" branch; `remote-drift-check.md`'s canonical golden must
change only in the stop branch and stay byte-identical across all three profiles.

**Commit together:** source `.md` files, `aitask_gate.sh`, `gate_ledger.py`,
goldens, the tests, `aidocs/gates/ledger-driven-reentry.md`, and the three
tracked `task-workflow-remote-` prerender trees (`.claude/`, `.agents/…-codex-`,
`.opencode/`).

**No cross-agent port task is warranted** — every edited/added file is
shared-closure prose with no `{% if agent %}` gate and no stub/agent-surface
change; codex and opencode variants auto-render from the Claude source. No new
script means **no permission-allowlist edits** in the four seed/settings files.

**Follow-up tasks filed at Step 8b:** (1) Step 5's missing worktree-reuse rule;
(2) wiring `merge-target-sync.md` into the non-resumed Step 9 path.

## Final Implementation Notes

- **Actual work done:** All four defects fixed as planned, plus the two
  design corrections the user's pre-approval review forced.
  - **Defect 1** — new shared `plan-approved-stop.md` (Approved-Plan Stop
    Sequence). `planning.md`'s "Approve and stop here" and
    `remote-drift-check.md`'s "Stop and re-verify plan" both reduce to a
    reference; the drift-stop branch now records `plan_approved` (once, guarded
    by the new `recorded-pass` verb). The shared file deliberately uses
    **bullets, not a numbered list** — an unnumbered step above a numbered list
    is precisely what the original partial copy dropped.
  - **Defect 2** — new "Resolve the plan's branches" step in Re-entry Routing
    (plan header only, two-rung, `check-ref-format`-validated, `UNSAFE_BRANCH`
    fails closed); `IMPLEMENT` runs the Remote Drift Check with a stated
    loop-termination argument; `POSTIMPL` runs the new `merge-target-sync.md`.
  - **Defect 3** — resolved as a *correction*: the recording is an audit record,
    not a routing signal; the two resume mechanisms (Check 5 for `Implementing`,
    §6.0 plan preference for `Ready`) are documented and the relaxation of Check
    5's status gate is recorded as a rejected alternative.
  - **Defect 4** — `task-abort.md` re-opens a stale `plan_approved`, gated on
    **ledger content** rather than `record_gates`, so a `fast`-recorded ledger
    aborted under `default` is still demoted.
  - New CLI: `aitask_gate.sh recorded-pass <task-id> <gate>` (pure bash + python
    parity arm), plus the extracted `_derive_gate_status`-style
    `_derive_gate_runs_table` shared with `status`.
- **Deviations from plan:** Two, both from the user's pre-approval review and
  both verified before acting.
  1. The planned `POSTIMPL` **exemption was invalid**. It rested on "Step 9's
     merge surfaces the divergence", but `grep -n "git fetch\|git pull"
     .claude/skills/task-workflow/SKILL.md` returns **nothing**: Step 9's
     pre-flight only checks local ref existence and worktree conflicts, and
     `git merge` is purely local, so a stale merge target merges cleanly and
     fails only at push. Replaced the exemption with a real pre-flight
     (`merge-target-sync.md`) with fast-forward-only recovery.
  2. Re-entry Routing had **no branch-name extraction at all** — the
     plan-existence guard only said "read the plan". Added the explicit
     header-only parse, since a resumed session carries no branch variables and
     may run under a different profile than the one that planned the task.
- **Issues encountered:**
  - `_derive_gate_runs_table` first used TAB as the field separator. Tab is IFS
    *whitespace*, so bash `read` collapses runs of it and the empty `attempt`
    field of a `skip`/`pending` run vanished, shifting the run id into its
    place — `status` stopped byte-matching the python backend. Switched to
    `\037` (US, non-whitespace) and pinned the empty-attempt shape in
    `test_gate_recorded_pass.sh`.
  - Drift-check test 12c's `git merge --ff-only origin/dev` "succeeded" while
    leaving `dev` stale, because the fixture leaves HEAD on the default branch —
    it fast-forwarded the *wrong* branch. That is exactly the failure
    `merge-target-sync.md`'s `checkout` + `symbolic-ref` assertion prevents; the
    test now runs the documented sequence verbatim and carries a negative
    control for the missing checkout.
  - 12b's local merge leaves `dev` genuinely diverged, so 12c cannot reuse that
    fixture (it would hit the refusal path). Each leg gets its own fixture,
    mirroring the procedure's own ordering: sync *before* Step 9 merges.
  - `set -e` aborts before `cmd; rc=$?` captures a deliberate failure; the new
    drift-check legs use `if (...); then rc=0; else rc=1; fi`.
- **Key decisions:**
  - Extraction over inline-plus-guard. Inlining the recording in
    `remote-drift-check.md` would have made that file profile-varying and broken
    `test_skill_render_task_workflow.sh` Test 1b's invariance assertion; the
    shared file localises the `record_gates` guard instead and satisfies the
    AC's "cannot drift apart again by partial copy" structurally.
  - A **verb** on the already-allowlisted `aitask_gate.sh`, not a new script: a
    new script would need permission-allowlist edits in four files
    (`.claude/settings.local.json`, `seed/claude_settings.local.json`,
    `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`).
  - Abort's demotion is ledger-conditional, never `record_gates`-guarded — the
    same reasoning `aidocs/gates/ledger-driven-reentry.md` already used to reject
    Jinja-gating the re-entry prose. A pure-`default` project never has a
    `plan_approved` pass, so the step is provably inert there.
  - `recorded-pass` degrades to exit 1 ("not recorded"): the stop sequence then
    writes a harmless duplicate, and abort skips a demotion that cannot matter
    because `resume-point` degrades to `PLAN` on the same failure.
- **Upstream defects identified:** None. (`tests/test_gate_guarded_archival.sh`
  fails in the live worktree, but that is a **concurrent in-flight session's**
  t1379 atomic-write refactor of `aitask_update.sh`, not a pre-existing defect
  and not this task's: the same test passes 31/31 against a pristine `HEAD`
  export with only this task's `aitask_gate.sh` + `gate_ledger.py` applied.)
- **Verification:** `test_gate_recorded_pass` 31/31, `test_gate_plan_approval_transitions`
  38/38, `test_task_workflow_reentry_drift` 57/57 (13 negative controls; sources
  restore byte-exactly), `test_remote_drift_check` 32/32, `test_gate_reentry`
  21/21, `test_skill_render_task_workflow` 180/180, all 13
  `test_skill_render_aitask_*`, `test_skill_verify` / `test_skill_rerender` /
  `test_skill_template` / `test_skill_render_uniform` /
  `test_skill_dispatch_contract` / `test_skill_parity_runtime_vs_rendered` /
  `test_gate_ledger` / `test_gate_active_gates` / `test_gate_verifiers` /
  `test_query_files_inflight` / `test_dependency_unblock` /
  `test_parallel_cross_repo_planning_procedure` green;
  `aitask_skill_verify.sh` OK; shellcheck unchanged from baseline (SC1091 only);
  Python suite `PASSED (runner=pytest, exit=0)`.
- **Follow-ups filed at Step 8b/8d:** (1) Step 5's missing worktree-reuse rule;
  (2) wiring `merge-target-sync.md` into the non-resumed Step 9 path;
  (3) `verify_reentry_drift_loop_terminates` (the confirmed risk mitigation).

## Post-Review Changes

### Change Request 1 (2026-08-03 13:45)

- **Requested by user:** `gate-recording.md` claimed every Gate Recording
  Procedure call site "in `SKILL.md`, `planning.md` and `plan-approved-stop.md`"
  is wrapped in the `record_gates` Jinja guard. After the extraction,
  `planning.md` delegates to the shared stop sequence **unguarded** and has no
  call site at all — so a maintainer could go looking for, or add, a guard that
  must not exist there.
- **Verified:** CONFIRMED. `grep -n "gate-recording.md\|record_gates"
  .claude/skills/task-workflow/planning.md` returns nothing; the only two
  call-site files are `SKILL.md` and `plan-approved-stop.md`.
- **Changes made:** Rewrote the paragraph in `gate-recording.md` to enumerate
  the two real call-site files and to state explicitly that `planning.md` and
  `remote-drift-check.md` do **not** call the procedure and must not carry a
  guard, with the reason (the shared sequence owns the guard once on their
  behalf — that is the point of the extraction). Fixed in place rather than
  deferred: it is a one-paragraph correction to text this task introduced.
- **Guarded against recurrence:** added four structural guards to
  `tests/test_task_workflow_reentry_drift.sh` —
  `planning-delegation-is-unguarded`, `drift-delegation-is-unguarded`,
  `gate-recording-names-stop-sequence-callsite`,
  `gate-recording-says-delegators-are-unguarded` — plus two new negative
  controls (one injects exactly the spurious `{% if profile.record_gates … %}`
  wrap at `planning.md`'s delegation, the mistake the concern predicts).
- **Files affected:** `.claude/skills/task-workflow/gate-recording.md`,
  `tests/test_task_workflow_reentry_drift.sh`,
  `tests/golden/procs/task-workflow/gate-recording-default.md`, and the three
  tracked `task-workflow-remote-` prerender trees (re-rendered).
- **Result:** `test_task_workflow_reentry_drift` 57/57 (13 negative controls),
  `aitask_skill_verify.sh` clean, `test_skill_render_task_workflow` 180/180.

## Risk

### Code-health risk: medium

- Adding two procedure files changes the **render closure**, which fans out to 3
  profiles × 3 agents and 3 git-tracked prerender trees. A missed
  `aitask_skill_rerender.sh remote` ships stale committed prerenders.
  · severity: medium · → mitigation: `aitask_skill_verify.sh`'s
  headless-prerender freshness check (`PRERENDER_FAIL`) catches exactly this
  regression (added for t888); it is in the verification list.
- Moving the `record_gates` guard out of `planning.md` breaks
  `test_skill_render_task_workflow.sh` Test 6's `planning.md` assertion. Intended
  and reviewed, but an unreviewed test edit could mask a real zero-footprint
  regression under `default`. · severity: medium · → mitigation: the replacement
  assertion is strictly stronger (checks the new file *and* that both call sites
  reference it) and the `default` zero-footprint check is extended, not moved.
- `merge-target-sync.md` introduces a **git-mutating** recovery
  (`checkout` + `merge --ff-only`) into the resume path. · severity: medium ·
  → mitigation: `--ff-only` can only fast-forward, is preceded by the same
  `symbolic-ref` assertion Step 9 uses, and refuses on real divergence — pinned
  by test case 4 in the extended drift-check suite.
- The new `recorded-pass` verb duplicates derivation already in `cmd_status`'s
  awk. · severity: low · → mitigation: extract a shared `_derive_gate_status`
  helper rather than copying; `test_gate_ledger.sh`'s existing bash↔python
  parity for `status` characterizes the extraction.
- Prose-only guards are grep-shaped and can rot into vacuous truths.
  · severity: low · → mitigation: every guard ships a negative control that
  re-runs the whole script as a subprocess and requires exit 1, and the ledger
  behaviour is additionally pinned by a real fixture test rather than strings.

### Goal-achievement risk: low

- Defect 3 is resolved by *correcting a claim* rather than adding behaviour, so
  "fixed" is only as good as the documentation being right. · severity: low ·
  → mitigation: pinned in three places (planning.md prose, the design doc's new
  section, the rejected-alternative entry), and the behaviour it describes is
  already exercised by `test_skill_parity_runtime_vs_rendered.sh`.
- The Defect-2 loop-termination argument depends on the stop branch continuing
  to revert to `Ready`, and is argued in prose — grep guards over skill markdown
  cannot prove the live loop terminates. · severity: low ·
  → mitigation: `verify_reentry_drift_loop_terminates` (the revert also now
  lives in exactly one shared file, with a structural guard asserting the
  reference from both call sites).

### Planned mitigations
- timing: after | name: verify_reentry_drift_loop_terminates | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement — loop termination is argued in prose only | desc: In a scratch repo, crash a fast-profile task after plan approval, push a drifting commit to origin, re-pick and confirm the re-entry drift check fires; then confirm "Stop and re-verify plan" → pull → re-pick lands in the planning path and terminates
