---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
folded_tasks: [1017]
created_at: 2026-07-19 08:43
updated_at: 2026-08-02 07:59
boardidx: 70
boardcol: now
artifacts:
  - handle: art:trail-shadow-review-loop
    kind: implementation_trail
    name: "Shadow review-loop automation: landing order"
---

Design and build a specialized shadow review-loop that automates the plan-review and implementation-review feedback cycles between the shadow agent and the followed (main) agent, removing the manual juggling the current workflow requires. This likely needs a redesign of how the shadow agent works and how it interacts with minimonitor — brainstorm possible solutions at planning time.

## Current workflow (manual)

While `aitask-pick` runs on the main agent and a plan is on screen:
1. User asks the shadow to challenge the plan (`plan-challenge.md`); shadow emits a concern block.
2. Minimonitor auto-offers; user presses `c`, ticks concerns → clipboard.
3. User manually focuses the main agent pane, pastes the concerns, and waits for the plan rewrite.
4. User manually types "refetch and recheck" into the shadow pane.
5. Repeat until satisfied. The same loop (and the same friction) exists for implementation review via `impl-challenge.md`.

## Exploration findings (levers for automation)

- The advisory-only guardrail binds the **shadow** (it never drives the followed pane); it does not bind **minimonitor**, which already has `send_keys` machinery (e.g. sibling-pane Enter in `minimonitor_app.py`). Minimonitor can therefore legitimately (a) forward picked concerns directly into the followed pane (bracketed paste + Enter, after explicit user confirmation in the picker) and (b) send "refetch and recheck round N" into the shadow pane.
- The auto-recheck trigger already exists: the t1104 staleness machinery (`@aitask_shadow_analyzed_at` stamp in `aitask_shadow_capture.sh` vs `TmuxMonitor.get_last_change_wall`) detects "followed agent changed after the shadow's last read", and `awaiting_input` prompt detection (`prompt_patterns.py`) detects when the main agent has settled at a prompt again. Together: "plan rewritten and agent waiting" = time to re-challenge.
- The concern block (`concern-format.md`) carries no round number or review timestamp. The auto-offer dedups on the parsed payload (`_last_concern_block_payload`), so a round-2 review with identical concerns produces no new hint — round metadata fixes both the missing round/time display and the dedup suppression. The fence literals are exact (`===AITASK-CONCERNS===`), so metadata needs a parser-aware extension (producer sub-procedures + `concern_parser.py` + picker UI updated together).

## Candidate architectures (brainstorm at planning; assess trade-offs + rejected alternatives)

a. **Minimonitor-orchestrated loop mode** — a new keybinding starts a "review loop": minimonitor sends the challenge/recheck prompts into the shadow pane, watches for concern blocks, opens the picker, forwards picked concerns into the followed pane, and auto-triggers a recheck when the followed agent settles (staleness + awaiting_input). Shadow skill mostly unchanged, plus round/timestamp emission.
b. **Self-driving shadow variant** — a new sub-procedure (or specialized skill entry, e.g. a review-loop mode of `/aitask-shadow`) where the shadow itself runs the loop: challenge → emit block → block on a new `wait-for-change` helper (tmux-gateway-based, blocks until the followed pane settles with new content) → refetch → re-challenge, incrementing the round counter. The user still picks/forwards concerns via minimonitor.
c. **Hybrid** — the shadow owns re-review timing (wait helper + round/timestamp bookkeeping); minimonitor owns pick-and-forward injection into the followed pane.

The plan must include a safety contract for any pane injection (bracketed paste for multi-line payloads, explicit user confirmation, never inject while the followed agent is mid-output).

## Requirements

- Automate away the manual "refetch and recheck" typing.
- The concern block / review output carries the review round number and the time the review was done.
- Reduce or eliminate the manual paste of picked concerns into the main agent (direct forward after explicit user confirmation).
- The same loop works for plan review (`plan-challenge`) and implementation review (`impl-challenge`).
- Steerability (from folded t1017): the loop must keep the user in control — per-round concern triage should let the user route each concern to "address in plan now" vs "spin off as a separate task" (e.g. via `/aitask-explore` fix-task spawning, as `plan-diagnose-errors.md` already does) vs "dismiss", so plans don't bloat from absorbing every secondary concern across rounds.
- Preserve load-bearing contracts: the shadow advisory-only guardrail (the shadow never drives the followed pane — injection, if any, is done by minimonitor upon user confirmation), the concern-format parser contract, and staleness semantics (passive observation never refreshes stamps).

## Scope priority — the two directions are NOT equal (user clarification, 2026-08-05)

The loop has two automatable seams, and they carry very different value and
very different risk. Plan and sequence accordingly rather than treating them as
one symmetric feature:

- **Critical seam — followed agent → shadow (auto-recheck).** "The main agent
  has finished addressing the concerns" → automatically start the next shadow
  review round. This is where the time goes today (the manual "refetch and
  recheck round N" typing, plus the watching-for-completion that precedes it),
  and it is the direction that should be optimized first. It is also the *safe*
  direction: it drives the shadow, which is the advisory companion, not the
  agent doing the work.
- **Not on the critical path — shadow → followed agent (concern forwarding).**
  Direct injection of picked concerns into the followed pane is a convenience,
  not a bottleneck: **human review of what gets forwarded should be kept**
  deliberately, so this direction is not a time-optimization target. Treat
  automating it as optional/later, and do not let its safety contract (bracketed
  paste, mid-output detection, confirmation) dominate the design budget for the
  loop as a whole.

This re-weights the candidate architectures above: an option that automates the
recheck direction well and leaves forwarding as today's confirmed pick-and-paste
is a **complete** answer to the priority requirement, not a partial one. The
pane-injection safety contract is still required for whatever forwarding does
land, but it is no longer the gating design problem.

Relevant sources: `.claude/skills/aitask-shadow/` (`SKILL.md`, `plan-challenge.md`, `impl-challenge.md`, `concern-format.md`), `.aitask-scripts/aitask_shadow_capture.sh`, `.aitask-scripts/aitask_shadow_context.sh`, `.aitask-scripts/monitor/` (`minimonitor_app.py`, `monitor_shared.py`, `concern_parser.py`, `monitor_core.py`, `prompt_patterns.py`), `aidocs/framework/shadow_agent.md`, `aidocs/framework/tmux_gateway.md`.

Coordination note: t1420 (advisory workflow-phase signal for shadow mode
pre-selection) builds the *input* this loop needs to pick `plan-challenge` vs
`impl-challenge` per round without the user inspecting the followed pane. It is
deliberately independent (this task must not wait on it — a loop can be driven
with an explicit mode), but if t1420 lands first, consume its phase seam instead
of adding a second phase derivation here. Its shape is pinned advisory-only by
`aidocs/framework/shadow_agent.md:360-367`, which this loop must also respect:
the phase may pre-select a round's mode, never refuse one.

Coordination note: t1158 (shadow impl review modes/tiers from /code-review prompts) reworks `impl-challenge.md` review *content*; this task reworks loop *mechanics*. Keep them separate and coordinate whichever lands second.

Coordination note: t1311 (shadow impl-review gate premise + profile tier default) fixes the *entry conditions* of a single implementation review — it removes the "too early to review" abort/proceed gate that fires whenever the Final Implementation Notes are not yet written (the normal pre-commit state), and adds an execution-profile key supplying a default review tier. Both touch how a review round starts, so whichever lands second must re-check the other's assumptions about when a review may begin and which tier it runs at.

## Merged from t1017: shadow steerabiility


I am developing  a coding agent harness where an "shadow agent' follow and review the work of a main agent see the aitask-shadow skill in github repo beyondeye/aitasks. The skill is working very well. But what is happening tha instead of using the shadow agent to help me stir the main agent I find myself delegating completely to shadow agent decisions like change the the main agent execution plan also i am concerned about the fact with this shadow agent has become very easy to expand the original plan with a lot of secondary concerns that would be better addressed as separate tasks. but because i dont want to "lose" them i end up iterating multiple time on the plan until all concerns are addressed. this way i end up with a plan that is perhaps "complete" but it is not any more steerable directly by me. How can i address this problems with an updated aitask-shadow skill or with some structured workflow that I can follow when using the skill?

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1017** (`t1017_shadow_steerabiility.md`)
