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
updated_at: 2026-07-19 08:43
boardidx: 140
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

Relevant sources: `.claude/skills/aitask-shadow/` (`SKILL.md`, `plan-challenge.md`, `impl-challenge.md`, `concern-format.md`), `.aitask-scripts/aitask_shadow_capture.sh`, `.aitask-scripts/aitask_shadow_context.sh`, `.aitask-scripts/monitor/` (`minimonitor_app.py`, `monitor_shared.py`, `concern_parser.py`, `monitor_core.py`, `prompt_patterns.py`), `aidocs/framework/shadow_agent.md`, `aidocs/framework/tmux_gateway.md`.

Coordination note: t1158 (shadow impl review modes/tiers from /code-review prompts) reworks `impl-challenge.md` review *content*; this task reworks loop *mechanics*. Keep them separate and coordinate whichever lands second.

## Merged from t1017: shadow steerabiility


I am developing  a coding agent harness where an "shadow agent' follow and review the work of a main agent see the aitask-shadow skill in github repo beyondeye/aitasks. The skill is working very well. But what is happening tha instead of using the shadow agent to help me stir the main agent I find myself delegating completely to shadow agent decisions like change the the main agent execution plan also i am concerned about the fact with this shadow agent has become very easy to expand the original plan with a lot of secondary concerns that would be better addressed as separate tasks. but because i dont want to "lose" them i end up iterating multiple time on the plan until all concerns are addressed. this way i end up with a plan that is perhaps "complete" but it is not any more steerable directly by me. How can i address this problems with an updated aitask-shadow skill or with some structured workflow that I can follow when using the skill?

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1017** (`t1017_shadow_steerabiility.md`)
