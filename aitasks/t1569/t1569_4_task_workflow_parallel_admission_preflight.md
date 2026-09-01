---
priority: high
effort: medium
depends: [t1569_3]
issue_type: feature
status: Implementing
labels: [workflow, scheduling, skills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1569
created_at: 2026-08-27 11:28
updated_at: 2026-09-01 18:03
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
                  proceed / confirm / stop-and-replan
```

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
- **CLEAR_CAVEATED** -> **require explicit confirmation under `block`**, naming
  the unverified source (e.g. "t259 holds a lock but is not `Implementing`, and
  its holder's liveness cannot be established"). Under `warn`, a visible note.
  Rendered **distinctly from CLEAR** in both modes.
- **CONFLICT** -> **stop-and-replan by default**, naming the overlapping task(s)
  and file(s); an explicit user override is the alternative.
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

`parallel_admission: block | warn | off` in `aitasks/metadata/profiles/*.yaml`
plus the `seed/` mirrors, mirroring `remote_drift_check: warn|strong-only`.

**CONFLICT's disposition is stop-and-replan in both `block` and `warn`** — that
is the design and it does not change.

**Deviation, with evidence:** the knob **ships defaulting to `warn`**, not
`block`. The measured projection against today's in-flight population is
UNCHECKABLE on **100% of picks** (2 of 4 non-candidate `Implementing` tasks have
no plan; t259's plan is all-phantom). Promoting the default to `block` is a
separate, explicitly gated step whose entry criterion is t1569_3's measured
UNCHECKABLE and false-CONFLICT rates falling to an agreed level. In `warn`,
UNCHECKABLE still prompts for explicit confirmation — only the hard stop is
deferred.

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
   Final Implementation Notes — they are the evidence for any later promotion of
   the default to `block`.

## Coordination — threshold sensitivity (t1643)

t1643 re-measured the threshold and **supersedes t1569_3's rates** as the input
to this task's `warn` → `block` decision. The numbers, the method and their
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
- **Grading is what moves, and this task is the reason it matters.** Because
  `CONFLICT` stops and `CLEAR_CAVEATED` merely confirms, the threshold decides
  which of the two a real collision gets. At the shipped `HUB_THRESHOLD = 10`
  only **~32%** of true collisions hard-stop (59% downgrade); at 20 it is ~67%
  (23%), costing ~20pp of precision. Any `block` criterion has to name an
  acceptable point on that curve.
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
  `parallel_admission: block|warn|off`, `aitask_parallel_admission.sh`,
  `parallel-admission.md`). *Resource* admission asks whether the host can
  afford the phase (project key, one command, no profile knob). Neither may be
  folded into the other, and neither may claim the bare name "admission".
- **Ordering, if both are wired: correctness before capacity.** The parallel
  preflight — which can stop-and-replan — runs first; the resource hook runs
  last, immediately before the fork. This task's own call sites already satisfy
  that: the planning Checkpoint precedes Step 7.
- **Their dispositions differ on purpose.** A CONFLICT stops and replans; a
  resource refusal **parks with the plan intact**
  (`stop_reason=resource_admission`, which shares the `deferred` stop's marker
  stamp in `plan-approved-stop.md`).
- **`plan-approved-stop.md`'s `stop_reason` vocabulary is now closed at three**
  (`deferred`, `drift`, `resource_admission`) with an exhaustiveness guard and a
  contract test pinning which side of the marker disposition each one selects.
  If the parallel preflight's stop-and-replan reuses that sequence, it must add
  its reason to the table and say which side it belongs on — the guard refuses
  an unlisted reason rather than guessing.
