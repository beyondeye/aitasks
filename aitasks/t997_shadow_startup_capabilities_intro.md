---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_monitormini, claudeskills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-15 12:19
updated_at: 2026-06-15 12:51
---

## Goal

Improve the `aitask-shadow` skill's startup UX so the user immediately knows
what the shadow can do for them, knows they can ask it to re-read the followed
agent's screen as work progresses, and gets relevant capabilities surfaced
proactively as the followed agent's stage changes.

The shadow is **advisory-only** — this contract must be preserved by every
change here (no keystrokes/input into the followed agent's pane).

## Background

`/.claude/skills/aitask-shadow/SKILL.md` currently jumps straight to Step 1
(capture the followed agent's pane) and then waits for a free-form user ask.
Nothing tells the user what the shadow is capable of. The shadow's own
capability surface is well-defined and enumerable:

- **Inline capabilities:** explain the captured output / "what is the agent
  doing right now?"; help the user answer an `AskUserQuestion` shown by the
  followed agent.
- **Linked sub-procedures (the "linked procedures from the main skill"):**
  `plan-explain.md`, `plan-challenge.md`, `plan-socratic.md`,
  `plan-assumptions.md`.

Re-capture already exists as a *mechanism* (Step 1: "Re-run it any time you
need fresh state"), but it is an internal note — the user is never told they
can ask the shadow to refetch the followed agent's screen.

## Scope

Edit the shadow skill source only: `.claude/skills/aitask-shadow/SKILL.md`.

The Codex (`.agents/skills/aitask-shadow/SKILL.md`) and OpenCode
(`.opencode/skills/aitask-shadow/SKILL.md`, `.opencode/commands/aitask-shadow.md`)
versions are **thin wrappers that delegate to the Claude source** — they read and
follow `.claude/skills/aitask-shadow/SKILL.md` at runtime and do not duplicate
its body or sub-procedures (they carry only their own copied `description:`,
which this task does not change). **Verified.** The edits therefore propagate to
both ports automatically: no port-file edits and no separate port follow-up
tasks are needed. (This corrects the original assumption that the ports duplicate
the body; the AC below is updated to match.)

## Changes

1. **Startup capability greeting (plain text).**
   Add a startup step (before/around Step 1) that emits a short markdown intro
   to the user presenting the shadow's own capabilities. **The greeting derives
   the capability list at runtime from Step 3** (the single source of truth that
   maps each capability to its inline handling or `plan-*.md` sub-procedure) —
   it must NOT hardcode a second copy of the list, which would drift from
   Step 3. The capabilities are: explain the current output / what the agent is
   doing; help answer an `AskUserQuestion`; explain a plan to a non-expert
   (plan-explain); adversarially challenge a plan (plan-challenge); Socratic
   questioning of a plan (plan-socratic); surface a plan's assumptions
   (plan-assumptions).
   The greeting must also tell the user they can ask the shadow to **refetch**
   the followed agent's screen at any time (it re-runs
   `aitask_shadow_capture.sh`) so advice tracks the agent's latest state as it
   progresses. Keep it concise; presentation is plain text (not an
   AskUserQuestion menu). It should not add I/O latency before the greeting —
   the greeting itself is the first thing the user sees.

2. **Proactively surface stage-relevant capabilities.**
   Add an explicit instruction (in Step 3 / the serve-the-request flow) that
   when the followed agent's current captured state makes one of the shadow's
   capabilities especially relevant (e.g. the screen shows an
   `AskUserQuestion` -> offer to help decide; the screen shows a plan awaiting
   approval -> offer plan-explain/plan-challenge/plan-assumptions), the shadow
   should proactively present that capability to the user. Remain
   advisory-only and suggestion-only; never auto-run a sub-procedure without
   the user asking. NOTE: experimentally the shadow already appears to do this
   to some degree from the existing wording — verify whether the current
   instructions already produce this behavior, and if so make it explicit
   rather than rewriting; only add new wording where the behavior is not
   already guaranteed.

3. **Remove the deferred phase-autodetection note.**
   Delete the trailing `## Note - workflow-phase autodetection (deferred)`
   section (the t986_2 reference) from the shadow `SKILL.md`. The new
   stage-relevant surfacing in change #2 is a lightweight, advisory,
   non-gating behavior and is consistent with the "shadow is not phase-gated"
   design; the deferred-autodetection note is no longer the right framing to
   keep at the end of the skill.

## Acceptance criteria

- Launching `/aitask-shadow <pane_id>` presents a concise capability greeting
  + refetch reminder before waiting for the user's ask. The greeting derives its
  capability list from Step 3 (no hardcoded duplicate), with a visible
  maintainer guard in Step 0 against future hardcoding.
- The skill explicitly instructs proactive, advisory surfacing of
  stage-relevant capabilities (verified against current wording; explicit, not
  implicit).
- The `## Note - workflow-phase autodetection (deferred)` section is gone.
- Advisory-only guardrail is intact and unweakened.
- Codex and OpenCode ports are thin wrappers delegating to the Claude source —
  verified — so they require no edits; the change propagates automatically. No
  separate port follow-up tasks.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T09:51:09Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-15T09:51:11Z status=pass attempt=1 type=machine
