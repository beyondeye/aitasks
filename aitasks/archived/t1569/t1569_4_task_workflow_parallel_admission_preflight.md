---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t1569_3]
issue_type: feature
status: Done
labels: [workflow, scheduling, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1569
implemented_with: claudecode/opus5
created_at: 2026-08-27 11:28
updated_at: 2026-09-02 15:07
completed_at: 2026-09-02 15:07
---

Wire the shared parallel-admission checker into `task-workflow` as a **required
preflight**. Slice 4 of 6 for t1569 — read the parent task and
`aiplans/p1569_background_work_roadmap_trail_for_followup_backlog.md` first.

Depends on t1569_3 (the checker). Consumer #1 of two; t1569_5 is consumer #2 and
runs in parallel with this.

## Context

```
Roadmap estimate -> candidate selected -> plan written
                                  |
                       Remote-drift check          (exists today)
                                  |
                  Parallel-admission preflight     (this task)
                                  |
                  proceed / confirm / stop (user choice)
```

> **SUPERSEDED 2026-09-02 — the preflight ships ADVISORY-ONLY.** By explicit user
> decision during plan verification, **no verdict stops the workflow on its own**;
> every stop is a choice the user makes at the prompt, and the profile knob is
> `parallel_admission: confirm | warn | off` with **no `block` value**. The
> reason: the checker's evidence is regex-extracted from plan prose, so a path a
> plan merely *runs* inside a fenced command is indistinguishable from one it
> edits — a false `CONFLICT` was measured live (it flagged
> `aitask_audit_wrappers.sh`, which neither task edits, while demoting the five
> files both genuinely edit to hub caveats). Making a mandatory stop safe would
> have required a shell/Markdown parser plus a provenance channel plus a consumer
> layer; that machinery was rejected as disproportionate. A hard-stop mode is
> gated on **t1343**'s structured per-task declaration of intended edits, not on
> this knob. Measurements below are kept as **superseded evidence** for t1343; the
> conclusions drawn from them no longer hold.


The framework already prevents two sessions claiming the same task (ownership
locks), compares the approved plan's paths against commits on the base/output
branch (remote-drift check), and protects worktree/branch reuse and merge safety.
What it does **not** provide is a dedicated, authoritative check against other
active tasks. This adds it — using the same checker the roadmap uses, so there is
one definition of "safe".

## Scope

New procedure `.claude/skills/task-workflow/parallel-admission.md`, modelled on
`remote-drift-check.md`, wired in at **two** call sites:

1. **After** the Remote Drift Check returns "Continue anyway" at the planning
   Checkpoint, **before** Step 7 implementation.
2. **Again on implementation re-entry** — `SKILL.md` Re-entry Routing, the
   `IMPLEMENT` route, after its drift check. The world may have changed since the
   plan was approved.

Order is load-bearing: the drift check can pull the base branch, which changes
what is in flight. The preflight must run **after** it, never before.

### Dispositions

- **CLEAR** -> proceed, stating **"no known conflict at check time"**. Never
  "safe to run in parallel" — the checker observes, it does not reserve, and
  overlapping work can begin the instant after it passes. State that residual in
  the procedure text.
- **CLEAR_CAVEATED** -> **require explicit confirmation under `confirm`**, naming
  the unverified source (e.g. "t259 holds a lock but is not `Implementing`, and
  its holder's liveness cannot be established"). Under `warn`, a visible note.
  Rendered **distinctly from CLEAR** in both modes.
- **CONFLICT** -> **advisory**: name the overlapping task(s) and file(s), then
  require explicit confirmation to continue. Continuing is listed first; stopping
  is offered, never imposed.
- **UNCHECKABLE** -> **require explicit user confirmation**, naming *why* the
  evidence was insufficient. Never auto-proceed.

### Invocation rules

- Call with `--lock-freshness require-fresh`. A cached lock ref would hide a lock
  another agent took seconds ago — a false CLEAR at exactly the admission point.
- **Exclude the candidate.** `task-workflow` set it `Implementing` and locked it
  back at **Step 4**, long before the plan existed. Verified live: t1569 was in
  `ait lock --list` while its own plan was being written. Without exclusion the
  candidate overlaps 100% of its own plan and every pick is a CONFLICT.
- Re-read **live** state at call time. Never reuse the roadmap's snapshot, which
  is by construction older.

### Operator recovery path — printed with every UNCHECKABLE

Keyed to the named `UNCHECKABLE_CAUSE:`:

- in-flight task with no plan -> plan it, or release its lock
  (`ait lock --unlock <id>`), or override for that task;
- all-phantom plan -> the plan is stale; refresh or release it;
- unavailable locks -> check the network, or re-run.

A prompt with no remedy is what trains users to dismiss a guard.

### Profile knob

`parallel_admission: confirm | warn | off` in `aitasks/metadata/profiles/*.yaml`
plus the `seed/` mirrors, mirroring `remote_drift_check: warn|strong-only`.

**RETRACTED (see the SUPERSEDED note above).** This paragraph previously read
"CONFLICT's disposition is stop-and-replan in both `block` and `warn` — that is
the design and it does not change". It is no longer the design: no verdict stops
the workflow on its own, and there is no `block` value. `warn` is the default
because the signal is heuristic, not as a step toward something stricter.

**Superseded evidence (2026-08-27):** the projection against that day's in-flight
population was UNCHECKABLE on 100% of picks (2 of 4 non-candidate `Implementing`
tasks had no plan; t259's plan was all-phantom). Re-measured 2026-09-01: 13
in-flight tasks, 3 `no_plan`, verdict CONFLICT — and that CONFLICT was a false
positive. Kept for t1343; no promotion criterion is derived from it.

## Key files to modify

- New `.claude/skills/task-workflow/parallel-admission.md`.
- `.claude/skills/task-workflow/SKILL.md` — Re-entry Routing (`IMPLEMENT` route).
- `.claude/skills/task-workflow/planning.md` — the Checkpoint, after the drift
  check.
- `aitasks/metadata/profiles/{default,fast,remote}.yaml` + `seed/` mirrors.
- `tests/golden/procs/task-workflow/` — regenerate in the **same commit**.

**No Codex / OpenCode port task is needed.** `parallel-admission.md` is
shared-closure content with no `{% if agent %}` gates, and Claude is the single
source (`SOURCE_AGENT_ROOT = ".claude/skills"` in `lib/skill_template.py`), so
`.agents/skills/task-workflow-*-codex-/` and `.opencode/skills/task-workflow-*/`
auto-render from it — verified identical modulo digits for an existing procedure.
CLAUDE.md's port guidance targets agent-specific surfaces only.

The **helper whitelist is** such a surface and still needs entries:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_parallel_admission
```

Five touchpoints (`.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`) — **verify them against
`aidocs/framework/aitasks_extension_points.md:286-318` before editing.**

## Reference files for patterns

- `.claude/skills/task-workflow/remote-drift-check.md` — the procedure shape this
  mirrors, including its `warn` / `strong-only` profile semantics.
- `aidocs/framework/skill_authoring_conventions.md` — goldens regeneration.
- `aidocs/framework/manual_verification_staleness.md` — why this is a procedure
  step and **not a gate** (`MANUAL_VERIFICATION_REACHABLE_GATES` is an allowlist
  and `filter_gates_for_issue_type()` would silently strip a new gate; the
  precedent is plan-verification staleness, a step in `planning.md`).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests` (last line only)
- Golden diffs are empty after regeneration.

Required tests:

1. A bash test driving the **real** helper through a synthetic repo for each of
   CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE.
2. A **self-exclusion end-to-end test**: claim a task exactly as Step 4 does
   (`aitask_pick_own.sh`), then assert the preflight returns CLEAR rather than
   conflicting with the candidate's own plan.
3. A workflow-contract test pinning that the preflight sits **after** the drift
   check at **both** call sites.
4. Live CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE rates recorded in the
   Final Implementation Notes — calibration evidence handed to **t1343**, which
   owns any future structured-declaration basis for a hard conflict. Not a
   promotion criterion: there is nothing to promote to.

## Coordination — threshold sensitivity (t1643)

t1643 re-measured the threshold and **supersedes t1569_3's rates**. There is no
longer a `warn` → `block` decision for them to feed (see the SUPERSEDED note at
the top); what follows is retained as **superseded evidence** for t1343. The numbers, the method and their
caveats are in `aiplans/archived/p1643_threshold_sensitivity_replay.md`
(Final Implementation Notes); re-run them with:

```bash
./.aitask-scripts/aitask_parallel_admission.sh sweep --thresholds 8,10,20,50
./.aitask-scripts/aitask_parallel_admission.sh replay --candidates auto \
    --from plan --lock-freshness require-fresh --thresholds 8,10,20,50 --exclude-no-plan
```

**t1643 deliberately made no threshold decision — it is this task's.** What it
established:

- **Recall of `CONFLICT ∪ CLEAR_CAVEATED` is invariant in the hub threshold.** A
  wrong threshold cannot cost recall, only grading. So the entry criterion above
  should not be written in terms of recall.
- **Grading moves with the threshold — but the premise this bullet rested on is
  gone.** It assumed `CONFLICT` stops while `CLEAR_CAVEATED` merely confirms, so
  the threshold decided which of the two a real collision got. **Both now
  confirm**, so the hub threshold selects only prompt wording. The measurements
  stand and are kept as superseded evidence for t1343: at the shipped
  `HUB_THRESHOLD = 10` about **32%** of true collisions land on `CONFLICT` (59%
  downgrade); at 20 it is ~67% (23%), costing ~20pp of precision. No criterion is
  derived from them here.
- **The availability rate is not yet decidable.** The live population is still
  ~96% UNCHECKABLE, driven entirely by tasks claimed but not yet planned. The
  excluded figures t1643 reports are a **counterfactual** ("what if nobody were
  mid-claim"), not an availability measurement — do not use them as one. t1643
  spawned an `availability_timeseries` follow-up to sample the real distribution.

Nothing here asks this task to change its plan; it replaces the stale reference
to t1569_3's rates in the "Deviation, with evidence" note above.

## Coordination — resource admission (t1597)

t1597 landed a **second, different** admission check at the same boundary: a
project-pluggable `resource_admission_command` (project_config.yaml) consulted
in `SKILL.md` **Step 7**, between the pre-implementation ownership guard and the
deferred worktree fork. Procedure: `.claude/skills/task-workflow/resource-admission.md`;
helper: `.aitask-scripts/aitask_resource_admission.sh`.

Nothing here asks this task to change its plan. What it fixes is the vocabulary
and the ordering, so the two checks cannot be confused for one:

- **They are distinct and separately named.** *Parallel* admission asks whether
  other in-flight tasks collide with this one (profile knob
  `parallel_admission: confirm|warn|off`, `aitask_parallel_admission.sh`,
  `parallel-admission.md`). *Resource* admission asks whether the host can
  afford the phase (project key, one command, no profile knob). Neither may be
  folded into the other, and neither may claim the bare name "admission".
- **Ordering, if both are wired: correctness before capacity.** The parallel
  preflight — which is advisory and never stops on its own — runs first; the
  resource hook runs last, immediately before the fork. This task's own call sites already satisfy
  that: the planning Checkpoint precedes Step 7.
- **Their dispositions differ on purpose.** A CONFLICT only *asks*; a
  resource refusal **parks with the plan intact**
  (`stop_reason=resource_admission`, which shares the `deferred` stop's marker
  stamp in `plan-approved-stop.md`).
- **`plan-approved-stop.md`'s `stop_reason` vocabulary is now closed at four**
  (`deferred`, `drift`, `resource_admission`, `parallel_admission`) with an
  exhaustiveness guard and a contract test pinning which side of the marker
  disposition each one selects. The preflight's **user-elected** "Stop and
  re-plan" reuses that sequence, so `parallel_admission` is registered on the
  **clearing** side — the guard refuses an unlisted reason rather than guessing.

## Coordination — t1343 (declared claims)

t1569_4 ships the advisory preflight at the same planning→implementation boundary
`t1343_parallel_agent_file_conflict_advisory.md` targets, and t1343 is itself
specified as *"An **advisory** (never blocking, never auto-acting) signal"*.

**When t1343's structured per-task declaration of intended edits exists, it — not
regex-scraped plan prose — becomes the only admissible basis for a hard
conflict**, and an absent or unclear declaration must require confirmation rather
than a guess. The live verdict rates and the false-CONFLICT observation in this
task's Final Implementation Notes are calibration evidence for that decision.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-02T09:11:02Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-02T12:06:09Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-02T12:07:15Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:56c57926abc7db60

> **✅ gate:risk_evaluated** run=2026-09-02T12:07:15Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1569_4/risk_evaluated_2026-09-02T12:07:15Z-risk_evaluated-a1.log`
