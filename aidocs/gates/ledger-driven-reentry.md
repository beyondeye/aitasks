---
title: Ledger-Driven Re-entry
category: design
tags: [aitasks, gates, re-entry, resume, task-workflow, crash-recovery, ledger, deferred-archival]
sources: [aitask-gate-framework.md, integration-roadmap.md, gate-guarded-archival.md]
confidence: high
created: 2026-06-15
updated: 2026-08-03
---

# Ledger-Driven Re-entry

Phase 2 of the gate-framework roadmap ([[integration-roadmap]], decision
**D3** — re-entry is priority #1). This is the companion to
[[gate-guarded-archival]] (t635_4): that doc decides *when a gated task may
archive*; this one decides *where a re-entered in-flight task resumes*.

## Problem

A task left `Implementing` — a crash, a lost session, multi-day work, or
gate-guarded archival deferring at workflow end (t635_4) — should resume from
the first unmet checkpoint, skipping what is already done. Today re-entry state
lives only in the conversation: the crash-recovery path (task-workflow Step 4)
reclaims the lock, but the workflow then re-runs Step 6 (for child tasks,
re-verifies the plan) and Step 7 from the top. That is wasteful and lossy — the
durable record of "plan approved, code reviewed" exists in the ledger but is
not consulted.

## Criterion

Re-entry keys off the **recorded `## Gate Runs` checkpoints** (t635_2:
`plan_approved` → `review_approved`), **not** the declared `gates:` field. This
is the crucial contrast with [[gate-guarded-archival]]'s `archive_status`, which
reads declared gates: archival asks "is every *declared* gate pass?"; re-entry
asks "how far did the *recorded workflow* get?". The two derivations are
deliberately separate functions in `lib/gate_ledger.py` and must not be
conflated.

`resume_point(task_file)` derives a 3-state result via the same back-to-front
last-block-wins rule (decision **D6**, `derive_status`) — so a re-opened
checkpoint (`pass` → `fail`) correctly demotes the resume stage:

| Result | Condition | Resume target |
|--------|-----------|---------------|
| `PLAN` | `plan_approved` not `pass` (incl. empty ledger) | Plan from scratch (today's flow) |
| `IMPLEMENT` | `plan_approved` pass, `review_approved` not pass | Step 7 implementation body |
| `POSTIMPL` | `review_approved` pass | Step 9 (merge / build / archive) |

`risk_evaluated` (a quick post-approval write) and `build_verified` /
`merge_approved` (which live inside Step 9) are **not** re-entry boundaries —
the workflow cannot act on them as distinct resume points, so they collapse into
the three stages above.

Surfaced as `aitask_gate.sh resume-point <task-id>` (python-delegated, degrades
to `PLAN` if Python is absent — safe: plan from scratch as today).

## Re-entry flow (task-workflow)

1. **Step 3 Check 5** reads `status`; if `Implementing`, runs `resume-point`.
   `PLAN` → no-op (normal flow). `IMPLEMENT` / `POSTIMPL` → set the
   `resume_point` context variable and show a banner with the recorded state and
   resume target. It then **proceeds to Step 4** — ownership must be (re)claimed
   before any work resumes.
2. **Step 4** claims/reclaims ownership exactly as today (the crash-recovery
   reclaim prompt, now ledger-enriched, is the confirmation).
3. **Re-entry Routing** (end of Step 4) resolves the plan's branches from the
   plan header, then routes by `resume_point`: `IMPLEMENT` → Remote Drift Check
   → Step 7's implementation body; `POSTIMPL` → Merge-Target Sync Pre-flight →
   Step 9. See "Branch resolution on re-entry" and "Remote checks on re-entry"
   below.

### Routing is gated on `resume_point`, not on the reclaim branch

`aitask_pick_own.sh` emits a `RECLAIM_*` signal only when the task was already
`Implementing` **and** assigned to the same email. A force-unlock takeover of
someone else's in-flight task returns plain `OWNED` with no reclaim signal — so
binding the routing to crash-recovery's `reclaim` return would silently lose the
resume on that path. The Re-entry Routing gate therefore fires at the end of
Step 4 on **any** ownership-success path, keyed only on the `resume_point`
context variable.

### `IMPLEMENT` resumes at the implementation body, not Step 7's top

Step 7's pre-implementation gates include two **non-idempotent task creators** —
Cross-Repo Child Assignment and Risk-mitigation "before" creation — each of
which *ends the workflow* when it fires. A task that is still a normal
`Implementing` single task is therefore necessarily *past* them; re-running Step
7 from the top would double-create. So `IMPLEMENT` resumes at the "Follow the
approved plan" body, re-running only the idempotent ownership guard and Agent
Attribution (which re-records the resuming agent).

## Branch resolution on re-entry

A resumed session carries none of the Step 5 branch variables, and may run under
a **different profile** than the one that planned the task. Re-entry Routing
therefore resolves both branches **from the plan header only**, never from
`profile.base_branch` / `profile.output_branch` — the same rule Step 9 already
states for the merge target, and for the same reason.

The rule is two-rung and validated: `Base branch:` / `Output branch:` when
present, else `main`; the output branch **never** falls back to `Base branch:`
(a plan written before that field existed merged to `main`, so reading its base
would retroactively move in-flight work). Each value is bound to a shell
variable rather than substituted, and screened with
`grep -qE '^[A-Za-z0-9._/-]+$'` plus `git check-ref-format --branch`; an
`UNSAFE_BRANCH:` result **stops the resume** rather than defaulting, because an
unsafe header value means the plan is untrustworthy about where work lands.

## Remote checks on re-entry

Re-entry originally ran **no** remote check at all: the Remote Drift Check was
dispatched from `planning.md`'s Checkpoint, and Re-entry Routing bypasses Step 6
entirely. That inverted the risk — a resumed task is by construction the one
whose plan is *oldest* relative to `origin/<base>` and `origin/<output>`, and it
was the only one that got no check.

The two routes need different checks, because they are in different states:

| Route | Check | Why |
|---|---|---|
| `IMPLEMENT` | **Remote Drift Check Procedure** (`remote-drift-check.md`) | The plan is about to be followed, so drift in the files it targets is exactly what matters. Its "Stop and re-verify plan" branch — release, revert to `Ready`, pull and re-pick — is the right recovery before any code exists. |
| `POSTIMPL` | **Merge-Target Sync Pre-flight** (`merge-target-sync.md`) | The code is committed and reviewed; only the merge remains. |

**Why `POSTIMPL` is not just given the drift check.** Two reasons, one of which
also corrects a tempting-but-false exemption argument:

- *The base branch is irrelevant* at `POSTIMPL` — the plan is no longer being
  followed — and the drift check's only actionable branch reverts the task to
  `Ready`, which is wrong for work that is already reviewed and committed.
- *"Step 9's own merge surfaces the divergence" is false.* **Step 9 never
  fetches.** Its pre-flight checks only that `refs/heads/<output_branch>` exists
  locally and is not held by another worktree, and `git merge` is purely local.
  When `origin/<output_branch>` has advanced, the merge **succeeds cleanly**,
  the local branch quietly diverges, and the problem appears only at push time
  as a non-fast-forward rejection. So an exemption cannot rest on the merge; the
  pre-flight has to actually fetch.

The pre-flight reuses the same detector (`aitask_remote_drift_check.sh
--unsynced`) and swaps in post-implementation-appropriate recovery:
fast-forward-only sync (`git merge --ff-only`, refusing on real divergence —
never rebase, reset or force), continue-anyway with an explicit
push-will-be-rejected warning, or stop **without reverting** (the task stays
`Implementing` at `POSTIMPL` and re-picking resumes here).

**The stop→pull→re-pick loop terminates.** "Stop and re-verify plan" reverts the
task to `Ready`, so the re-pick fails Check 5's `Implementing` status gate,
never reaches Re-entry Routing, and runs the normal planning path — whose
Checkpoint runs the check once more against the now-pulled branches. The check
that sent the user away is not the one they land back on.

The same staleness affects the **non-resumed** Step 9 path. Wiring the pre-flight
in there unconditionally would add a network fetch and a possible prompt to every
task's merge — a behaviour change for every user, tracked separately rather than
folded in.

## "Approved and stopped" is not a routing signal

`planning.md`'s "Approve and stop here" and `remote-drift-check.md`'s "Stop and
re-verify plan" both record `plan_approved` `pass` — and both then revert the
task to `Ready`. Since Check 5 only consults the ledger for a task whose status
is `Implementing`, that recorded entry **cannot** drive routing, and prose
calling it "the resume signal" was simply wrong.

It is kept as an **audit record of the approval**, and the claim is corrected.
There are deliberately two different resume mechanisms:

| Task state on re-pick | What resumes it |
|---|---|
| `Implementing` (crashed / session lost / deferred archival) | Check 5 → `resume_point` → Re-entry Routing |
| `Ready` (approved and stopped) | §6.0's existing-plan preference (`plan_preference` / `plan_preference_child`) |

The second is the better path for an approved-and-stopped task, not a
consolation prize: it reaches the Checkpoint, so it re-runs the Remote Drift
Check — which is precisely what a task that stopped *because of* drift needs.

Both branches share one implementation, `plan-approved-stop.md`. That extraction
is the structural fix for the original defect: the sequence lived inline in
`planning.md` with the gate recording *above* its numbered list, and
`remote-drift-check.md` copied only the numbered steps — silently dropping the
recording. A reference cannot drop a step the way a copy can, and the shared
file uses bullets rather than a numbered list so nothing reads as optional
preamble.

## Abort demotes a recorded `plan_approved`

An abort rejects the plan, so `task-abort.md` re-opens any recorded approval by
appending `plan_approved` `fail` (`note=aborted`). Because the ledger derives
last-marker-wins, that demotes `resume_point` back to `PLAN`.

Previously nothing did this, and the safety was **incidental**: abort reverts
the status, so Check 5's status gate skipped the stale entry. That made the
protection an accident of the revert rather than an invariant — and it would
have evaporated the moment anyone relaxed Check 5's status condition, letting a
task aborted at Step 8 resume straight into implementation on the very plan the
abort rejected. (The plan-existence guard would not catch it either: abort
offers "Keep for future reference" for the plan file.)

The demotion is conditional on **ledger content** (`aitask_gate.sh
recorded-pass`), **not** on `record_gates`. A task recorded under `fast` can be
aborted under `default`, and a Jinja guard would render the demotion away in
exactly the case where a stale entry exists. Conditioning on the entry makes it
a no-op wherever nothing was ever recorded, so `record_gates: false` behaviour
is unchanged.

## Folds into the existing reclaim confirmation

Re-entry introduces **no new prompt**. The crash-recovery reclaim prompt already
asks "Reclaim and continue?" and surveys uncommitted changes; it is enriched to
show the resume target. This keeps the conservative-by-default posture: a stale
ledger cannot cause silent harm because `IMPLEMENT` lands at Step 7 (which
re-runs implementation anyway) and `POSTIMPL` lands at Step 9 (whose merge
approval is NON-SKIPPABLE).

## Live immediately (contrast with t635_4 dormancy)

Unlike gate-guarded archival — dormant until t635_14 populates the `gates:`
field — re-entry keys off the **recorded** ledger, which `record_gates: true`
already populates. So it goes **live immediately for the `fast` profile**: a
re-picked in-flight `fast` task with recorded checkpoints resumes from the first
unmet one. It stays inert where the ledger is empty (profiles without
`record_gates`, or a task that crashed before `plan_approved`): `resume-point`
returns `PLAN` and the flow is exactly today's. A plan-existence guard falls back
to `PLAN` if a checkpoint was recorded but no plan was externalized.

## Crash-recovery generalization

`crash-recovery.md` now treats the gate ledger as the **primary** progress
signal: its survey runs `aitask_gate.sh status` and reports the resume target,
with the old plan-file-marker heuristic kept as a fallback for empty ledgers.
Its `reclaim` / `decline` return contract is unchanged — routing is driven by the
`resume_point` context variable at the end of Step 4, so crash-recovery only
surveys and displays; it does not route.

## Rejected alternatives

- **A finer resume stage per recorded gate.** `risk_evaluated` /
  `build_verified` / `merge_approved` are not workflow re-entry boundaries
  (risk is a post-approval write; build/merge live inside Step 9), so per-gate
  stages add states the workflow cannot act on. The 3-state collapse is exact.
- **A separate "resume here?" AskUserQuestion.** Redundant with the reclaim
  prompt the user already answers; re-entry folds into it instead.
- **Gating the skill edits behind `record_gates` (Jinja).** Re-entry keys off
  ledger *presence*, not the recording profile key; an empty ledger already
  derives to `PLAN`, so the prose is profile-invariant and inert without a
  ledger (mirrors t635_4 Check 4).
- **Binding routing to crash-recovery's `reclaim` branch.** Loses the resume on
  the plain-`OWNED` takeover path (see above).
- **Re-running Step 7 from the top on `IMPLEMENT`.** Double-creates the
  non-idempotent post-approval tasks (see above).
- **Relaxing Check 5's `Implementing` status gate** so a `Ready` task carrying a
  recorded `plan_approved` routes to `IMPLEMENT`. It would make the recorded
  entry genuinely load-bearing, but it routes *around* the Step 6 Checkpoint and
  therefore around the Remote Drift Check — on exactly the path that needs it,
  since an approved-and-stopped task typically stopped *because of* drift. It
  would also make the abort demotion the sole barrier between an aborted task
  and resuming into a rejected plan. §6.0's existing-plan preference already
  resumes these tasks, and does so through the Checkpoint.

## See also

- [[integration-roadmap]] — Phase 2, decision D3 (re-entry priority #1).
- [[gate-guarded-archival]] — the companion archival-timing decision (t635_4);
  the deferred-`Implementing` state is exactly the in-flight resume signal this
  doc keys on.
- [[aitask-gate-framework]] — "Decision tree (re-entry)" and "Re-entry contract";
  the stateful re-entrant orchestrator (t635_11) reuses the same derivation.
