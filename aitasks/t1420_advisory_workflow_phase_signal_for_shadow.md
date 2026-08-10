---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [shadow, aitask_monitormini, gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-05 10:42
updated_at: 2026-08-10 14:55
---

## Goal

Give the framework an **advisory** signal for "which task-workflow phase is the
followed agent in right now", and use it to **pre-select** the shadow's review
mode (plan-level challenge vs implementation verification) instead of the user
reading the screen and typing the right instruction every time.

Today the user manually inspects the followed agent's pane to decide whether to
ask the shadow for `plan-challenge` or `impl-challenge`. That judgement is
mechanical and repeatable, and most of its inputs already exist on disk.

## Non-negotiable shape constraint (read this first)

`aidocs/framework/shadow_agent.md:360-367` **already deferred this feature with
a written contract**:

> Detecting the followed agent's *workflow phase* … was scoped out: the shadow's
> value is to spawn fast, be immediately available, and answer any question
> without needing to know the phase. Phase autodetection remains a possible
> future advisory-only enhancement; **it must never become a flow step, a
> prerequisite, or a gate on what the user can ask.**

The same document (`:369-384`) records the scar from violating that rule:
`impl-challenge`'s "too early to review" gate inspected the followed agent's
state to decide whether the user could proceed, fired on the normal path, and
was removed in t1311. **This task implements the deferred enhancement in its
sanctioned shape only:** a hint that changes a *default*, never a check that
changes what is *permitted*. A wrong or unavailable phase must cost the user at
most one extra keystroke.

This task must also **update that deferred section** — once implemented, it is
no longer deferred, and the doc must describe the shipped signal and restate the
advisory-only rule as a live constraint.

## Existing signals (verified — do not re-derive)

The strongest signal already exists and is already parsed at every relevant call
site; it is simply discarded.

- **`gate_ledger.resume_point(task_file)`** (`lib/gate_ledger.py:1547`, pure
  helper `_resume_point_from_state` at `:1570`) returns `PLAN` /
  `IMPLEMENT` / `POSTIMPL`, derived back-to-front from the recorded
  `## Gate Runs` ledger (`plan_approved` pass ⇒ past planning; `review_approved`
  pass ⇒ past implementation). Re-opening a checkpoint correctly demotes it.
- Exposed on the CLI as `./.aitask-scripts/aitask_gate.sh resume-point <id>`
  (`aitask_gate.sh:539 cmd_resume_point`), and consumed by the board already
  (`board/aitask_board.py:1422`, `:1431`).
- **The monitor already computes it and throws it away.** `GateSummaryCache`
  (`monitor/monitor_core.py:2855-2910`) calls
  `gate_ledger.read_task_gate_state(info.task_file_abs)` at `:2905` — whose
  `TaskGateState` carries `resume_point` (`gate_ledger.py:148`, populated at
  `:1640`) — then keeps only `compact_gate_summary(state)`. This is structurally
  the same "already parsed, then discarded" finding as t1323.
- **Pane → task binding already exists**: `TaskInfoCache.get_task_id_for_pane`
  (`monitor_core.py:3013-3028`) via `task_id_from_window_name`
  (`:2786`, regex `_TASK_ID_RE` at `:2783`). Minimonitor already uses it when
  spawning the shadow (`minimonitor_app.py:1513`, `:1556`).
- Corroborating post-approval-only frontmatter writes (task-workflow Step 7,
  i.e. *after* the plan checkpoint): `implemented_with:`
  (`task-workflow/SKILL.md:373`) and `risk_code_health:` /
  `risk_goal_achievement:` (`:386-391`, explicitly not written during Step 6
  because planning runs read-only). Plan-file existence
  (`aitask_plan_externalize.sh`, written at `planning.md:357`) is a further
  coarse marker.

## Blind spots the design MUST handle (do not paper over)

1. **Empty ledger reads as `PLAN`, not as "unknown".** `_resume_point_from_state`
   returns `PLAN` when nothing is recorded (`gate_ledger.py:1575-1576`), and
   recording is gated on the profile key `record_gates`
   (`task-workflow/gate-recording.md:9-12`), which is set **only in the `fast`
   profile** (`aitasks/metadata/profiles/fast.yaml:17`, `seed/profiles/fast.yaml:14`).
   Under `default` / `remote` the ledger stays empty and a naive consumer would
   confidently report "planning" for every task, forever. The phase signal must
   therefore emit an explicit **`UNKNOWN`** distinct from `PLAN`, derived from
   "is there a ledger at all" (`gate_ledger.has_gate_markers`) plus the recording
   profile — not silently inherit `resume_point`'s re-entry default. `PLAN` and
   "I cannot tell" are different states and every consumer must render them
   differently.
2. **The two moments the shadow is most useful leave no durable trace.**
   "Plan on screen awaiting approval" (Step 6 checkpoint / `ExitPlanMode`) and
   "parked at the Step 8 review prompt" are pure in-conversation
   `AskUserQuestion`s; the gate is recorded only *after* the human answers
   (`gate-recording.md:5-7` — "the existing interactive approval … is unchanged
   — its outcome IS the gate signal, and this procedure just *witnesses* it").
   The durable ledger therefore tells you which **span** you are in, never
   whether the agent is **waiting on you inside it**. The live half of the
   signal has to come from the pane: `classify_content` /
   `awaiting_input` and the captured screen.
3. **The live half is weak today.** `monitor/prompt_patterns.py` carries very few
   patterns, and its own comment at `:27` states the plan-mode and
   tool-permission confirmations are indistinguishable
   (`claude_proceed` = `Do you want to proceed\?`). Sharpening it enough to
   separate "approve this plan" from "allow this tool call" is in scope — but see
   the t1116 coordination note.
4. **The shadow has no mode argument, by construction.** The whole argv surface
   is `/aitask-shadow <followed_pane_id> [<source_task_id>]`
   (`.claude/skills/aitask-shadow/SKILL.md.j2:22-35`), and
   `aitask_codeagent.sh:426-437` rejects empty/whitespace-bearing args — so a
   free-text instruction can never be smuggled in as argv. Passing a phase hint
   needs either a new **bare token** argument or a different channel (a pane
   option in the `@aitask_shadow_*` family, read by
   `aitask_shadow_capture.sh` like `@aitask_shadow_target` /
   `@aitask_shadow_analyzed_at`). Choose one at planning time and justify it;
   both have precedent.

## Reuse this resolution ladder (precedent exists)

Do not invent a new precedence scheme. `impl-challenge.md:152-186` already
resolves the review **tier** as: **explicit user wording > profile key
(`shadow_impl_review_tier`) > ask**. Phase-driven mode selection should mirror it
exactly: **explicit user wording > detected phase > ask**, and when the detected
phase drives the choice the shadow must *announce* what it resolved and from
what evidence (the tier branch already announces; copy that behaviour). An
`UNKNOWN` phase falls through to the existing ask — which is today's behaviour,
so the feature can only ever remove keystrokes, never add a blocked path.

## Deliverables

1. A phase-derivation seam returning a **rich result, not a bare enum**: phase
   (`PLAN` / `IMPLEMENT` / `POSTIMPL` / `UNKNOWN`), plus provenance (which
   signals were consulted and which produced the answer) and whether the agent
   appears to be *waiting* inside that phase. Live under `lib/` next to
   `gate_ledger.py` so board / monitor / minimonitor / shell can all reach it,
   with a CLI verb for shell callers (mirror `aitask_gate.sh resume-point`).
2. Wire minimonitor / monitor to stop discarding `TaskGateState.resume_point`
   (`monitor_core.py:2905`) and surface the phase on the followed-agent card.
3. Pass the phase to the shadow at spawn time (bare-token argv or pane option —
   decided at planning) and consume it in the shadow's mode resolution as the
   middle rung of the ladder above.
4. Sharpen the shadow's existing proactive offer (`SKILL.md.j2:138-149`, which
   today is explicitly "a lightweight look at what is *visibly* on screen, not a
   workflow-phase classifier") so it can additionally cite the phase — while
   keeping the same non-gating character.
5. Update `aidocs/framework/shadow_agent.md` "Phase detection (deferred)"
   (`:360-367`) to document the shipped signal and keep the advisory-only rule
   as a live, testable constraint.

## Explicit non-goals

- No loop automation, no auto-rechecking, no injection of anything into the
  followed pane. That is t1159's scope (see below).
- No new gate, no change to `resume_point`'s three-state re-entry contract
  (`aidocs/gates/ledger-driven-reentry.md:50-53` deliberately excludes
  risk/build/merge as re-entry boundaries — the phase signal may be finer-grained
  than re-entry, but must not redefine re-entry).
- The phase must never block, abort, or prompt-for-confirmation before doing what
  the user asked.

## Verification

A structural/behavioural guard is required for the advisory-only contract: prove
that every phase value — including `UNKNOWN` and a *wrong* phase — still reaches
every shadow capability the user can ask for. A negative control that forces a
wrong phase and asserts nothing is refused is the discriminating test; a test
that only checks the happy-path default would pass even if the hint had become a
gate. Also prove the `UNKNOWN`-vs-`PLAN` split at its weakest surface: a task
with no `## Gate Runs` section under a non-`record_gates` profile must not report
`PLAN`.

## Coordination

- **t1159 (shadow review-loop automation)** — this task is the *input* its loop
  will consume: knowing the phase is what lets a loop pick `plan-challenge` vs
  `impl-challenge` per round. Deliberately kept **separate and independent**:
  t1159 is high-effort with its own four-wave predecessor trail
  (`art:trail-shadow-review-loop`), and this signal is useful on its own (card
  display, sharper proactive offer) with or without the loop. Whichever lands
  second re-checks the other's assumptions about how a review round selects its
  mode. This task is anchored to t1159's topic root.
- **t1311** — removed the impl-review premise gate; its rationale is the shape
  constraint above. Do not reintroduce state-inspection-as-permission.
- **t1116 (Postponed)** — stale minimonitor instances mis-report prompt state.
  Any work sharpening `prompt_patterns.py` must account for the fact that a
  long-running minimonitor predating the change keeps the old patterns.
- **t1323** — same "gate detail already parsed then discarded at
  `monitor_core.py:2905`" seam. Whichever lands second should extend the cache's
  return rather than adding a second parse of the same file.
- **t1357 (+ 8 children)** — proposes a live per-step event spool
  (`.aitask-stats/runs/t<id>/`) stamping `planning[plan_mode]` / `implement` /
  `review[iteration]` begin+end. That would be a strictly finer-grained phase
  source than the ledger, including the currently-invisible "awaiting approval"
  spans. It is stats-motivated and unbuilt; this task must **not** wait on it,
  but the seam in deliverable 1 should be able to take an additional provenance
  source later without changing its callers.
- **t1389** — moves pane→task binding from window-name regex to stamped pane
  options. The phase signal depends on that binding; it should read it through
  the existing `get_task_id_for_pane` accessor so t1389 remains a drop-in change.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-10T11:56:05Z status=pass attempt=1 type=human
