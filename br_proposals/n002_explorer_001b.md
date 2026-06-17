<!-- section: overview -->
## Overview

The baseline shadow is an **advisory companion** that reads a followed agent's
screen and, on a free-form ask, explains output, helps answer an
`AskUserQuestion`, or runs one of four structured plan analyses
(explain / challenge / socratic / assumptions). It is read-only with respect to
the followed agent and never types into its pane.

That contract stops the shadow from *acting* on the followed agent, but it does
nothing to stop two **steerability** failures the developer actually hits:

1. **Decision delegation drift.** The skill's "help answer an `AskUserQuestion`"
   capability *suggests an answer with reasoning*. In practice the developer
   adopts the suggestion wholesale and stops forming their own intent — the
   shadow becomes the designer, the human becomes a relay. Advisory-only prevents
   keystrokes, not authorship transfer.

2. **Scope accretion into an unsteerable plan.** `plan-challenge.md` surfaces
   secondary concerns and even "separates fatal from fixable follow-ups" — but
   nothing *captures* those follow-ups. The developer, unwilling to lose them,
   folds each one back into the current plan and re-iterates until the plan is
   "complete." A complete plan that addresses twelve concerns is no longer a
   small unit the human can steer by intent — which is the exact opposite of the
   framework's decompose-into-small-tasks philosophy.

This approach reframes the shadow as a **steerability-preserving instrument**.
It changes the *default posture* (decision-withholding: elicit the developer's
intent before recommending) and adds a **concern-spillover pipeline** that gives
secondary concerns a durable home *as separate tasks* instead of as plan bloat.
The advisory-only guarantee is preserved and extended: even creating a deferred
task is a draft the developer runs, never an automatic write.

It differs from the baseline along three concrete seams: a tightened guardrail,
a new `plan-triage.md` sub-procedure, and a new `aitask_shadow_spillover.sh`
helper that bridges deferred concerns to `ait create`.
<!-- /section: overview -->

<!-- section: architecture -->
## Architecture

The shadow keeps its three-piece pipeline (capture → context-fetch → skill) and
adds a fourth seam — **spillover** — plus a posture change in the skill flow.

```
followed agent pane
   │  capture (unchanged)
   ▼
aitask_shadow_capture.sh ──► current screen text
   │
   ├─ context-fetch (aitask_shadow_context.sh) ──► TASK_FILE (with AC/intent) + PLAN_FILE
   │
   ▼
SKILL.md flow  ── routes the ask, default posture = decision-withholding
   │
   ├─(plan analysis: challenge/assumptions/socratic/explain) ─► concerns surfaced
   │                                                              │
   │                                                              ▼
   │                                              plan-triage.md  (per concern: IN_SCOPE | DEFER)
   │                                                              │ DEFER
   │                                                              ▼
   │                                              aitask_shadow_spillover.sh  ── append ──►  ledger
   │                                                              │  on developer command
   │                                                              ▼
   │                                              defer-to-task bridge ──► drafted `ait create --batch ...` stubs
   │
   └─(AskUserQuestion help) ─► decision-withholding guardrail: lay out space → elicit intent → (opt-in) recommend

scope-drift meter: compares PLAN_FILE against TASK_FILE AC → flags concerns that exceed the task's stated intent
```

**Component responsibilities:**

- **component_skill_flow** owns routing and the new default posture. It is still
  one instruction-driven flow with no mode selector. The change is in *how* it
  serves two existing capabilities (AskUserQuestion help; plan analyses) and in
  exposing a new triage capability in Step 3.
- **component_capture** / **component_context_fetch** are unchanged in interface.
  Context-fetch's existing task-file output becomes load-bearing because the
  scope-drift meter reads the task's AC from it.
- **component_decision_withholding_guardrail** extends the load-bearing guardrail
  from "don't type into the pane" to "don't author the developer's decisions
  either, unless asked."
- **component_triage_subprocedure** (`plan-triage.md`) is the classifier that
  every plan analysis funnels its findings through.
- **component_spillover_ledger** (`aitask_shadow_spillover.sh`) is the durable
  store and the only sanctioned writer/reader of the ledger.
- **component_defer_to_task_bridge** turns ledger entries into `ait create
  --batch` drafts (with `depends:` on the current task), shown for the developer
  to run.
- **component_scope_drift_meter** is an advisory comparison surfaced on request
  (or proactively when a plan is on screen), never an automatic action.
<!-- /section: architecture -->

<!-- section: data_flow -->
## Data Flow

1. **Capture.** `aitask_shadow_capture.sh <pane_id>` returns the followed agent's
   current screen (re-run on demand). Unchanged.

2. **Context-fetch.** When the ask needs source, `aitask_shadow_context.sh
   <task_id>` returns `TASK_FILE:<path>` and `PLAN_FILE:<path>`. The skill reads
   the task file's description/AC — this is the **original intent baseline** the
   scope-drift meter measures against.

3. **Analysis → concern stream.** A plan analysis (e.g. `plan-challenge.md`)
   produces a list of concerns, each a `{title, why_it_bites, severity}` record.

4. **Triage.** `plan-triage.md` classifies each concern against the task AC:
   - `IN_SCOPE` — traceable to the current task's stated intent → keep in the
     plan discussion; the developer steers it directly.
   - `DEFER` — a distinct concern the developer doesn't want to lose but that
     would bloat the current plan → routed to the ledger.

5. **Ledger append.** `aitask_shadow_spillover.sh append --task <task_id>` writes
   each DEFER concern as one block to
   `.aitask-shadow/spillover/<task_id>.md`. Schema per entry:
   ```
   - title: <one line>
     severity: high|medium|low
     why: <scenario that triggers it>
     source: <challenge|assumptions|socratic|explain|manual>
     verbatim: |
       <the concern's full original text, for faithful task creation>
   ```

6. **Defer-to-task bridge.** On the developer's command
   (`aitask_shadow_spillover.sh stubs --task <task_id>`), each ledger entry is
   rendered to a runnable draft:
   ```bash
   ait create --batch --name "<title>" --issue-type <inferred> \
     --priority <severity→priority> --depends <task_id> \
     --description-file <tmp-with-verbatim-body>
   ```
   The drafts are **printed for the developer to review/edit/run** — the helper
   does not execute them (assumption_no_auto_apply). After the developer
   confirms the tasks exist, `aitask_shadow_spillover.sh clear --task <task_id>`
   empties the ledger.

7. **Scope-drift meter.** `aitask_shadow_spillover.sh drift --task <task_id>
   --plan <plan_path>` (or inline reasoning in the skill) compares the plan's
   addressed items against the AC and reports counts: "N plan items, M not
   traceable to the task's AC — defer these?" The M items are *offered* for
   triage; nothing is auto-deferred.

8. **AskUserQuestion path (no ledger).** When the screen shows an
   `AskUserQuestion`, the decision-withholding guardrail governs: the shadow lays
   out each option and its trade-offs, then **asks the developer for their
   leaning/intent** before offering a recommendation. The developer can short-cut
   with "just recommend one" — an explicit per-request opt-out.
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

<!-- section: component_skill_flow [dimensions: component_skill_flow] -->
### Skill flow (SKILL.md)

Still a single instruction-driven flow (Steps 0–3, no mode selector). Two edits:

- **Step 3 routing** gains a triage/spillover capability ("park this for later",
  "what should be a separate task?", "what's creeping out of scope?") that
  reads-and-follows `plan-triage.md`.
- The **AskUserQuestion-help** bullet is rewritten to the decision-withholding
  posture (see guardrail). The capability list in Step 0 stays derived from
  Step 3, so the new capability appears in the greeting automatically — no
  hardcoded second copy (existing maintainer rule).
<!-- /section: component_skill_flow -->

<!-- section: component_triage_subprocedure [dimensions: component_triage_subprocedure] -->
### Triage sub-procedure (plan-triage.md)

New read-and-follow file. Input: a concern list (from a prior analysis or the
developer's own words) + the fetched task AC. Procedure: for each concern,
decide IN_SCOPE vs DEFER with a one-line justification tied to the AC; present
the split to the developer for confirmation (the developer can move items either
way); on confirm, append DEFER items via the spillover helper. It never decides
unilaterally and never edits the plan.
<!-- /section: component_triage_subprocedure -->

<!-- section: component_spillover_ledger [dimensions: component_spillover_ledger] -->
### Spillover ledger (aitask_shadow_spillover.sh)

New whitelisted helper following shell conventions (`#!/usr/bin/env bash`,
`set -euo pipefail`, source-on-startup test scaffold). Subcommands: `append`,
`list`, `stubs`, `drift`, `clear`. Ledger lives at
`.aitask-shadow/spillover/<task_id>.md` (the `.aitask-shadow/` scratch root,
gitignored). One markdown file per task; entries are append-only blocks. A unit
test (`tests/test_shadow_spillover.sh`) covers append→list→clear round-trip and
stub rendering, per the "encapsulate workflow bash in a tested helper" rule.
<!-- /section: component_spillover_ledger -->

<!-- section: component_defer_to_task_bridge [dimensions: component_defer_to_task_bridge] -->
### Defer-to-task bridge (stubs subcommand)

Renders ledger entries to `ait create --batch` invocations with
`--depends <current_task>` so each deferred concern becomes a tracked follow-up
linked back to its origin. Severity maps to priority (high→high, medium→medium,
low→low); issue_type is inferred from the concern wording (bug/enhancement/etc.)
and shown for the developer to correct. Output is text the developer runs — the
bridge never calls `aitask_create.sh` itself.
<!-- /section: component_defer_to_task_bridge -->

<!-- section: component_decision_withholding_guardrail [dimensions: component_decision_withholding_guardrail] -->
### Decision-withholding guardrail (SKILL.md)

Extends the existing advisory-only guardrail. New load-bearing clause: the
shadow's default is to **present the decision space and elicit the developer's
intent**, not to hand over a decision. It may recommend only when (a) the
developer explicitly asks ("you pick", "recommend one") or (b) after the
developer has stated their own leaning, to confirm/refine it. This applies to
`AskUserQuestion` help and to any "what should I do here?" ask. The pane-write
prohibition is unchanged and absolute.
<!-- /section: component_decision_withholding_guardrail -->

<!-- section: component_scope_drift_meter [dimensions: component_scope_drift_meter] -->
### Scope-drift meter

Compares the on-screen / fetched plan against the task's AC and reports how many
plan items are *not* traceable to the original intent. Offered proactively when a
plan is visible (one suggestion, take-or-ignore — same posture as the existing
proactive-capability glance) and on demand. Flagged items are offered to
`plan-triage.md`; the meter itself defers nothing automatically.
<!-- /section: component_scope_drift_meter -->

<!-- section: component_capture [dimensions: component_capture] -->
### Capture (aitask_shadow_capture.sh)

Inherited unchanged. Reads the followed agent's current screen via the tmux
gateway; re-run on demand.
<!-- /section: component_capture -->

<!-- section: component_context_fetch [dimensions: component_context_fetch] -->
### Context-fetch (aitask_shadow_context.sh)

Inherited interface. Its task-file output now feeds the scope-drift meter (the
AC is the drift baseline) in addition to its existing role of supplying plan
context for analyses.
<!-- /section: component_context_fetch -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

- **assumption_followed_agent_pane** (inherited from the shadow pattern): a
  resolvable tmux pane id for the followed agent; capture works as today.
- **assumption_context_fetch_has_ac** (NEW, load-bearing): the fetched task file
  contains the original intent / acceptance criteria the scope-drift meter and
  triage measure against. If the task body is terse, drift detection degrades to
  "ask the developer" rather than failing.
- **assumption_create_batch_available** (NEW): `ait create --batch` can mint a
  follow-up task non-interactively with `--depends` on the current task id. (The
  framework already supports `--batch` task creation.)
- **assumption_developer_owns_decisions** (NEW, the steerability premise): the
  developer *wants* to author intent. Full delegation is supported only as an
  explicit per-request opt-out, never the default.
- **assumption_no_auto_apply** (NEW): rendering an `ait create` stub does not run
  it; the developer runs it. This keeps task creation inside the advisory-only
  boundary.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

- **tradeoff_advisory_purity_preserved** — *Advantage:* the defer-to-task bridge
  only drafts commands, so the shadow never writes the developer's repo or drives
  the followed agent — the advisory contract holds even for task creation.
  *Cost:* the developer must take one explicit action per deferred task; if they
  ignore the drafts the concern still evaporates. *Mitigation:* the ledger
  persists across the session, so "run the stubs later" is viable; `list` shows
  outstanding deferrals.
- **tradeoff_decision_withholding_friction** — *Advantage:* keeps the human as
  decision author, the core fix for delegation drift. *Cost:* adds a round-trip
  (elicit intent before recommending). *Mitigation:* explicit "you pick / just
  recommend" opt-out per request bypasses the round-trip when the developer
  genuinely wants a recommendation.
- **tradeoff_ledger_overhead** — *Cost:* one more artifact per task.
  *Mitigation:* store under gitignored `.aitask-shadow/spillover/<task_id>.md`,
  one file per task, cleared via `clear` once stubs are run; never committed.
- **tradeoff_scope_meter_false_drift** — *Risk:* terse ACs cause legitimately
  in-scope items to be flagged as drift. *Mitigation:* drift is always presented
  as a question the developer answers ("is this part of the task?"), never an
  automatic defer; the developer can move items back to IN_SCOPE in triage.
- **tradeoff_create_stub_accuracy** — *Risk:* an auto-drafted stub captures a
  concern imperfectly (wrong issue_type, lossy title). *Mitigation:* the full
  draft is shown for edit-before-run, and the concern's verbatim text is carried
  into the task body so nothing is lost in summarization.
<!-- /section: tradeoffs -->