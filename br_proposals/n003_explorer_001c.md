<!-- section: overview -->
## Overview

The baseline task asks: the `aitask-shadow` skill works well, but it pulls the
workflow *against* the framework's core value of **steerability**. Two specific
failure modes are named:

1. **Delegation drift** — instead of using the shadow to help the *human* steer
   the followed agent, the user ends up handing whole decisions (e.g. "rewrite
   the execution plan") to the shadow. The human falls out of the design loop.
2. **Scope-creep ratchet** — the shadow's adversarial pass surfaces many
   secondary concerns. Not wanting to "lose" them, the user folds each one back
   into the plan and re-iterates until the plan is "complete" — but a complete,
   maximal plan is no longer something the human can *directly* steer.

This proposal turns the shadow from a free-form advisor into a **triage-and-defer
companion** built on two new ideas and one workflow:

- An **intent anchor** — a one-line human statement of *what this task is for* —
  becomes the yardstick the shadow measures every concern against.
- A **concern ledger + deferral helper** gives every surfaced concern a durable
  home *outside* the active plan, so "I don't want to lose it" stops forcing
  plan bloat. Out-of-scope concerns become real, dependency-linked aitasks; the
  active plan stays minimal and human-owned.

It differs from the baseline shadow in posture, not in its advisory-only
contract: the baseline *generates findings*; this version *routes each finding*
to STEER-NOW (drafted for the human to send), DEFER-TASK (spun off as a separate
aitask), or DROP — and continuously checks that the plan still matches the
human's stated intent. The human stays the sole steerer; the shadow stays
read-only with respect to the followed agent.
<!-- /section: overview -->

<!-- section: architecture -->
## Architecture

The existing pipeline (capture → context-fetch → skill) is preserved. The skill
gains a new orchestrating sub-procedure, `plan-triage.md`, and two new
persistence/automation components. Responsibilities:

- **Intent anchor (`component_intent_anchor`).** At the start of a plan-oriented
  shadow session, the shadow either asks the human for a one-line scope statement
  or proposes a draft anchor inferred from the task file's title + acceptance
  criteria (via `aitask_shadow_context.sh`) for the human to confirm/edit. The
  anchor text is stored at the top of the concern ledger. It is the *human's*
  intent, captured in the human's words — this is the structural fix for
  delegation drift: classification is anchored to something the human authored,
  not to the shadow's own judgement.

- **Triage router (`component_triage_router`).** After the adversarial pass
  produces findings (reusing `plan-challenge.md` unchanged as the finding
  source), the router presents each finding with a proposed disposition measured
  against the anchor: **STEER-NOW** (in-scope, must change the current plan),
  **DEFER-TASK** (real concern but out-of-scope for this task), or **DROP** (not
  worth tracking). The human confirms or overrides each — the decision is always
  the human's; the shadow only *recommends*.

- **Concern ledger (`component_concern_ledger`).** Every finding and its final
  disposition is appended to `.aitask-shadow/<task_id>/concerns.md`. This is the
  "nothing gets lost" guarantee that breaks the scope-creep ratchet: the human
  no longer has to fold a concern into the plan to avoid forgetting it, because
  the ledger already remembers it.

- **Deferral helper (`component_deferral_helper`).** For each DEFER-TASK item the
  shadow calls `aitask_shadow_defer.sh`, a thin whitelisted wrapper over
  `ait create --batch` that mints a backlog task carrying `depends: [<current
  task id>]` and a back-reference line, then writes a reciprocal pointer into the
  ledger (and, when the followed task file is writable on the data branch, a
  "deferred concerns" note). It returns a `LANDED t<N>: <title>` line so the
  human sees exactly what was created.

- **Steer-draft (`component_steer_draft`).** For STEER-NOW items the shadow
  composes a concrete, editable steering message ("Tighten step 3 to handle the
  empty-input case…") and hands it to the human to paste into the followed
  agent. It is never auto-sent — preserving the advisory-only contract while
  still making steering low-effort.

- **Scope-drift guard (`component_scope_drift_guard`).** The shadow tracks the
  running ratio of STEER-NOW (plan-expanding) vs DEFER-TASK dispositions across
  the session and warns the human when the plan is accreting scope ("4 of the
  last 5 concerns expanded the plan; does this still match your anchor: '…'?").
  This makes the ratchet *visible* instead of silent.

The four existing sub-procedures (`plan-explain`, `plan-challenge`,
`plan-socratic`, `plan-assumptions`) remain. `plan-triage.md` is additive and
composes `plan-challenge.md` as its first stage; the free-form inline
capabilities (explain output, help answer an AskUserQuestion) are untouched.
<!-- /section: architecture -->

<!-- section: data_flow -->
## Data Flow

1. **Session start.** Human invokes `/aitask-shadow <pane_id> [<task_id>]`
   (unchanged). When the request is plan-oriented, the shadow resolves the task
   via `aitask_shadow_context.sh`, proposes/records the **intent anchor** at the
   head of `.aitask-shadow/<task_id>/concerns.md`.

2. **Findings.** The shadow captures the plan (`aitask_shadow_capture.sh`),
   fetches the plan file if only a fragment is on screen, and runs
   `plan-challenge.md` to produce a prioritized, severity-tagged finding list.

3. **Triage loop.** For each finding the **triage router** proposes a disposition
   against the anchor and the human confirms/overrides:
   - **STEER-NOW →** shadow emits a drafted steering message
     (`component_steer_draft`); human edits + types it into the followed agent.
     Ledger row marked `STEER-NOW (sent by human)`.
   - **DEFER-TASK →** shadow calls `aitask_shadow_defer.sh` →
     `ait create --batch --name … --priority … --depends <task_id> --label
     deferred-from-shadow --commit`; helper returns `LANDED t<N>`; ledger row
     records the new task id (bidirectional link).
   - **DROP →** ledger row marked `DROP` with one-line reason; nothing else
     happens.

4. **Drift check.** After the loop (or every N findings) the **scope-drift
   guard** summarizes how many concerns expanded the plan vs were deferred and
   re-shows the anchor, prompting the human to confirm the plan still matches
   intent or to revise the anchor.

5. **Persistence.** The ledger lives under `.aitask-shadow/<task_id>/` and is
   pruned by `aitask_companion_cleanup.sh` when the followed agent's pane dies
   (same lifecycle hook that already cleans shadow panes). Deferred tasks persist
   independently in `aitasks/` on the data branch.

Failure handling: a `NOT_FOUND` task id degrades to "ledger-in-memory + no
deferral" (the shadow tells the human it can advise and draft but cannot mint
tasks). A `create` failure surfaces the error and leaves the concern as
`DEFER-TASK (pending)` in the ledger so it is not lost.
<!-- /section: data_flow -->

<!-- section: components -->
## Components

<!-- section: component_intent_anchor -->
### Intent Anchor

One human-authored line capturing the current task's intended scope/goal.
Captured at session start: the shadow proposes a draft built from the task
file's title and acceptance-criteria block (parsed from the `TASK_FILE:` path
returned by `aitask_shadow_context.sh`) and the human confirms or rewrites it.
Stored as the first line of `.aitask-shadow/<task_id>/concerns.md`
(`ANCHOR: <text>`). Editable mid-session via an explicit "revise anchor" step.
This is the load-bearing fix for delegation drift — every later classification is
measured against text the *human* owns, not the shadow's opinion.
<!-- /section: component_intent_anchor -->

<!-- section: component_triage_router -->
### Triage Router

The per-finding decision step. For each finding from `plan-challenge.md` it
proposes one of `STEER-NOW | DEFER-TASK | DROP` with a one-line rationale
referencing the anchor, then defers to the human's confirm/override. Implemented
as prose logic inside `plan-triage.md` plus a single multiSelect interaction
(group findings by proposed disposition so the human approves in one pass rather
than N prompts). DROP is the default for low-severity findings to keep friction
proportional to the number of *kept* concerns.
<!-- /section: component_triage_router -->

<!-- section: component_concern_ledger -->
### Concern Ledger

Durable markdown at `.aitask-shadow/<task_id>/concerns.md`. Schema:

```
ANCHOR: <one-line intent>
| # | severity | concern (one line) | disposition | ref            |
|---|----------|--------------------|-------------|----------------|
| 1 | high     | empty-input path   | STEER-NOW   | sent 07:55     |
| 2 | medium   | add metrics export | DEFER-TASK  | t1042          |
| 3 | low      | rename helper      | DROP        | cosmetic       |
```

It is the "nothing is lost" guarantee that lets the human keep the active plan
lean: a concern can be acknowledged and parked without being folded into the
plan. Co-located with the existing `.aitask-shadow/` capture scratch space;
pruned by `aitask_companion_cleanup.sh` on followed-agent death.
<!-- /section: component_concern_ledger -->

<!-- section: component_deferral_helper -->
### Deferral Helper (aitask_shadow_defer.sh)

A whitelisted helper script (per the framework convention that multi-command
skill bash lives in an `aitask_*.sh` helper with a unit test, not inlined in
skill markdown). Signature:

```
aitask_shadow_defer.sh --parent-task <id> --name "<title>" \
    [--priority low|medium|high] [--effort …] [--body-file <path>]
```

It wraps `ait create --batch` with `--depends <parent>`, a
`labels: [deferred-from-shadow]` tag, `boardcol: backlog`, and a body that
back-references the parent task and the originating concern. On success it prints
`LANDED t<N>: <title>` (a rich return, not a bare boolean) and the new id is
written back into the ledger row — a **bidirectional** link. A `--group` mode
folds several deferred concerns into one child task to avoid board clutter.
Covered by `tests/test_shadow_defer.sh` (construction-spy test: assert the
correct `ait create` argv is built and that nothing is created on a dry run /
invalid input, proving no side effect before validation).
<!-- /section: component_deferral_helper -->

<!-- section: component_steer_draft -->
### Steer Draft

For STEER-NOW findings the shadow composes a concrete, copy-pasteable steering
message addressed to the followed agent (specific to the finding: which step to
change and how). It is presented to the human, never sent — the advisory-only
guardrail is unchanged. This keeps the human *in* the steering loop while making
the act of steering cheap, directly countering the temptation to let the shadow
"just fix the plan itself".
<!-- /section: component_steer_draft -->

<!-- section: component_scope_drift_guard -->
### Scope-Drift Guard

A lightweight running tally of STEER-NOW (plan-expanding) vs DEFER-TASK
dispositions. When plan-expanding dispositions dominate (e.g. ≥3 of the last 4,
threshold tunable), the shadow re-displays the intent anchor and asks the human
whether the plan still matches it or whether the anchor itself should be revised.
Makes the scope-creep ratchet visible at the moment it happens rather than after
the plan has already bloated.
<!-- /section: component_scope_drift_guard -->

<!-- section: component_triage_subprocedure -->
### Triage Sub-procedure (plan-triage.md)

The new orchestrating sub-procedure under `.claude/skills/aitask-shadow/`. Flow:
establish/confirm anchor → run `plan-challenge.md` for findings → triage-router
loop (ledger + defer + steer-draft) → scope-drift check → summary
(`X steered, Y deferred → [t-ids], Z dropped`). Added to Step 3 of `SKILL.md` as
a new routed capability ("triage this plan", "help me keep this plan in scope");
because the greeting list is *derived* from Step 3, the new capability surfaces
automatically with no second hardcoded copy. The change is authored in the
Claude Code source first; Codex/OpenCode variants follow per the framework's
cross-agent porting rule (closures auto-render; only agent-specific surfaces
need a follow-up).
<!-- /section: component_triage_subprocedure -->
<!-- /section: components -->

<!-- section: assumptions -->
## Assumptions

All assumptions below are **new** (the baseline node carried no dimension
fields).

- **assumption_intent_anchor_available (new).** The user can articulate a
  one-line scope statement at session start, or accept/edit a draft the shadow
  infers from the task title + acceptance criteria. If neither is possible the
  triage flow degrades to plain `plan-challenge` with ledger-only capture.
- **assumption_batch_create_available (new).** `ait create --batch` exists and
  can mint a dependency-linked task, and the followed task id is known or
  resolvable. Without it, DEFER-TASK items remain `pending` in the ledger
  (advisory still works; automation is the only thing lost).
- **assumption_single_active_task (new).** Each shadow session follows exactly
  one task (guaranteed by the minimonitor pane/task binding), so "the plan",
  "the anchor", and the ledger path are unambiguous.
- **assumption_concern_volume (new).** A challenge pass yields a tractable number
  of findings (≈3–12), so interactive per-finding triage (batched into one
  multiSelect) is reasonable; a pass yielding dozens would need a paginated
  triage UI, which is out of scope.
<!-- /section: assumptions -->

<!-- section: tradeoffs -->
## Tradeoffs

All tradeoffs below are **new**.

- **tradeoff_friction_vs_discipline (new).** *Advantage:* scope discipline and a
  durable record. *Cost:* a triage decision per kept finding. *Mitigation:* group
  findings by proposed disposition into a single multiSelect confirm, and default
  low-severity findings to DROP, so interaction cost scales with kept concerns,
  not all of them.
- **tradeoff_ledger_persistence (new).** *Advantage:* "nothing is lost" without
  plan bloat. *Cost:* a new on-disk artifact needing lifecycle management.
  *Mitigation:* store under the existing `.aitask-shadow/` scratch space and
  prune in `aitask_companion_cleanup.sh` on followed-agent death (reuses the hook
  that already cleans shadow panes); never commit the ledger to git.
- **tradeoff_deferral_proliferation (new).** *Advantage:* the active plan stays
  minimal. *Cost:* aggressive deferral can spawn many tiny backlog tasks.
  *Mitigation:* a `--group` mode on `aitask_shadow_defer.sh` folds several
  concerns into one child task, and deferred tasks land in `boardcol: backlog`
  with `depends` on the parent so they neither block nor clutter the active lane.
- **tradeoff_intent_anchor_staleness (new).** *Advantage:* a stable yardstick for
  in/out-of-scope. *Cost:* if the human's intent legitimately shifts mid-task,
  the anchor mis-flags genuinely in-scope work. *Mitigation:* an explicit "revise
  anchor" affordance, and the scope-drift guard prompts an anchor re-confirm
  after any STEER-NOW that widens scope — so anchor revision is a deliberate,
  visible act, not silent drift.
<!-- /section: tradeoffs -->