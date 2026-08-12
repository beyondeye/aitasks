---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1159_2, t1159_3, t1159_4, t1159_5, t1159_6]
folded_tasks: [1017]
artifacts:
  - handle: art:trail-shadow-review-loop
    kind: implementation_trail
    name: "Shadow review-loop automation: landing order"
created_at: 2026-07-19 08:43
updated_at: 2026-08-12 17:14
boardcol: now
boardidx: 70
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
  - **Correction (2026-08-10): the second half of this was false when written, and is only true now because of t1420 and t1474.** t1420's pre-phase measurement drove four real Claude Code 2.1.226 widgets through the monitor's own `capture-pane -p -e` + `strip_ansi` path and found that `AskUserQuestion` was matched by **nothing** and the ExitPlanMode dialog was matched by **nothing** — so an agent parked at either (the two moments this loop most wants to fire on) read as **IDLE** in both monitor TUIs. `claude_proceed`, whose comment claimed to cover both, matched no current dialog at all. t1420 added `claude_askuserquestion` and `claude_plan_approval` (the latter bottom-anchored on the dialog's footer/option wording, because `classify_content` matches only the last 6 lines while the question renders ~7 lines up); t1474 then retired the dead `claude_proceed`, added `claude_trust_folder`, and extended `strip_ansi` to drop OSC 8 sequences that were polluting `compare_value` and idle detection. **Do not re-derive this lever — read the current `prompt_patterns.py` and `ansi_utils.py`.** Note also that the currency rule guarding against a stale, already-answered prompt still sitting in scrollback is structural, not a distance bound: `current_question_block()` locates the widget's header chip (`☐ <Header>`) and requires the anchor to sit below it.
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

Relevant sources: `.claude/skills/aitask-shadow/` (`SKILL.md`, `plan-challenge.md`, `impl-challenge.md`, `concern-format.md`), `.aitask-scripts/aitask_shadow_capture.sh`, `.aitask-scripts/aitask_shadow_context.sh`, `.aitask-scripts/monitor/` (`minimonitor_app.py`, `monitor_shared.py`, `concern_parser.py`, `monitor_core.py`, `prompt_patterns.py`, `ansi_utils.py`), `aidocs/framework/shadow_agent.md`, `aidocs/framework/tmux_gateway.md`.

Added by the landed predecessors (2026-08-09/10) — read these too:
`.aitask-scripts/lib/workflow_phase.py`, `.aitask-scripts/aitask_shadow_rejected.sh`,
`.aitask-scripts/lib/registry_lock.sh`, and the `workflow-phase` verb in
`.aitask-scripts/aitask_gate.sh`.

**Read the landed code, not the descriptions above.** Three predecessors
deviated from their approved plans during implementation — t1420 in three
documented ways — and one shipped a helper whose own header comment contradicted
its emitter (fixed as t1464, found only because t1427_4 re-derived the format
from the `printf` rather than the comment). Re-derive the store's machine format,
the phase seam's API and the picker's dismiss contract from the emitters.
Sequencing context for all of this is recorded in the implementation trail
`art:trail-shadow-review-loop` (`ait artifact get art:trail-shadow-review-loop`).

Coordination note: **t1420 (advisory workflow-phase signal) — LANDED
2026-08-10.** The conditional in this note fired: consume its phase seam, do not
add a second phase derivation here. What shipped, to read rather than re-derive:

- `.aitask-scripts/lib/workflow_phase.py` — stdlib-only, beside `gate_ledger.py`,
  returning a frozen `PhaseSignal(phase, waiting, source, consulted, recording,
  detail)`. `phase` and `waiting` are **separate** states and "I cannot tell" is
  its own value on both axes (`UNKNOWN`), never folded into a negative — under
  every profile except `fast` the gate ledger stays empty, so a consumer that
  treats an empty ledger as `PLAN` reports "planning" forever. `SOURCES` is
  tier-named (`workflow-prompt` / `native-prompt` / `ledger` / `none`) so a
  consumer can tell which tier produced the answer.
- CLI verb `./.aitask-scripts/aitask_gate.sh workflow-phase <id>`, mirroring
  `resume-point`; and `aitask_shadow_capture.sh --phase` for the shadow side.
- Transport to the shadow is the **`@aitask_shadow_phase` pane option, not
  argv** — chosen precisely because argv freezes at spawn while the shadow skill
  re-evaluates on every refetch. It is stamped inside `spawn_shadow` *before*
  `schedule_refresh` and re-stamped every tick from **both** TUIs via the shared
  `refresh_shadow_phase_stamp`. A re-evaluating loop is exactly the workload that
  reasoning was chosen for; do not reopen the channel question.
- Mode resolution follows `explicit user wording > detected phase > ask`, and the
  shadow announces what it resolved and from what evidence.
- Phase is rendered on the full-monitor agent cards, the minimonitor list rows,
  and the docked followed-agent panel (whose deliberately-static contract from
  t1133/t1322 was formally amended to admit it).

Its shape is pinned advisory-only by `aidocs/framework/shadow_agent.md`, which
this loop must also respect: the phase may pre-select a round's mode, never
refuse one. t1420 shipped a negative control that forces a *wrong* phase and
asserts nothing is refused — a loop that gates on phase would break it.

**Caveat before building on it:** its own manual verification (t1475) has not
run, so the above is what the implementation reports, not what has been
confirmed. Two defects were caught late in its own review and are worth knowing:
a broad `except Exception` in `refresh_shadow_phase_stamp` swallowed a
`NameError` and left the feature dead with every test green, and `spawn_shadow`
initially did not stamp at spawn — the same race class t1319 fixed for
`@aitask_shadow_target`.

Coordination note: **t1427 (reject shadow concerns, suppress next round) —
LANDED 2026-08-09, all five children plus an aggregate manual verification.**
It built the substrate for this task's "dismiss" triage arm, and the division
of labour stands: t1427 owns *where per-round concern state lives*, this task
owns *when a round starts and how it is driven*. This loop consumes it; do not
re-implement rejection and do not duplicate its store layout. What shipped:

- `.aitask-scripts/aitask_shadow_rejected.sh` — `add` / `list` / `remove` /
  `prune`, over a store at `.aitask-shadow/<task_id>/rejected.md` mirroring
  `.aitask-gates/`, git-ignored, written through `lib/registry_lock.sh` plus
  atomic write (appending is a read-modify-write two TUIs can race), pruned at
  archive time. Its machine-format line is `REJECTED:r<id>|<ts>|<producer>|
  <marker line>` — **note the `r` prefix**; the helper's own header comment said
  otherwise and was wrong until t1464 fixed it. Re-derive from the emitter, not
  the comment.
- Picker tri-state: `_ConcernRow` now renders `☐` / `☑` / `✗` in place of the old
  boolean `_selected`, and the `a` / `A` bulk shortcuts were **removed entirely**
  — per-row state made them meaningless. Any keybinding work here starts from
  that, not from the pre-t1427 picker.
- `ConcernPickResult(forwarded, rejected, unrejected)` replaces the bare list on
  modal dismiss. This is the contract the triage routing plugs into.
- `RejectedStoreModal`, reachable with `R`, giving a reversible un-reject path
  (TUI-only).
- A producer-side suppression rule inlined in **all four** concern producers
  (inlined per producer because shadow Step 2 is optional, so a
  context-fetch-only rule would have an unreachable trigger). It matches
  semantically, reports `Suppressed N previously-rejected concern(s).` rather
  than filtering silently, and is **fail-open** — anything it is unsure about is
  kept.

The reciprocal obligation now falls on this task: **this task's round-number
requirement is the natural key-space for scoping suppression per round**, and
t1427 landed first, so that key-space is designed-for and currently unused.
Decide explicitly at planning time whether round number scopes suppression, and
re-check that decision against the shipped store rather than against this note.

Coordination note: **t1158 (shadow impl review modes/tiers from /code-review
prompts) — ARCHIVED.** It reworked `impl-challenge.md` review *content*; this
task reworks loop *mechanics*. The constraint is discharged, but this task is
the one landing second, so read the *landed* review entry conditions and tier
behaviour in `impl-challenge.md` rather than t1158's task text.

Coordination note: **t1311 (shadow impl-review gate premise + profile tier
default) — ARCHIVED.** It removed the "too early to review" abort/proceed gate
that fired whenever the Final Implementation Notes were not yet written (the
normal pre-commit state), and added an execution-profile key supplying a default
review tier. Discharged as a coordination obligation, but load-bearing as a
precedent: t1420 cites that removed gate as the scar defining the advisory-only
shape constraint — a signal about the followed agent's state may change a
*default*, never change what is *permitted*. A review loop that refuses to start
a round because it inferred the wrong phase would reintroduce exactly what t1311
removed.

Coordination note: **t1474 (fix stale Claude prompt patterns) — LANDED
2026-08-10**, spawned from t1420's review. It hardened the same detection surface
this loop's completion trigger reads: retired the dead `claude_proceed`, added
`claude_trust_folder` for the first-run workspace-trust dialog (previously read
as idle), and extended `strip_ansi` to drop OSC sequences alongside CSI. See the
correction under "Exploration findings" above. Its own follow-up t1477 (verify
the trust dialog against a real widget) is unrun, but the trust dialog is not a
state this loop encounters.

Coordination note: **t1467 (cross-agent phase prompt detection, `depends:
[1420]`, Ready)** — a scope constraint on this task, not a blocker. t1420's
Tier A workflow-prompt anchors are agent-neutral, but its **currency detection is
not**: both `awaiting_input` and the current-prompt-block index come from
`prompt_patterns.PROMPT_PATTERNS_BY_AGENT`, whose `opencode` list is empty and
whose `codex` Tier B row is an explicit placeholder. An OpenCode followed pane
therefore establishes neither, degrades to ledger-only, and **this loop's
auto-recheck trigger can never fire for it** until t1467 lands. Decide explicitly
at planning time whether the loop ships Claude-first or degrades visibly for
other agents — and consume t1420's `live_tiers_available()` predicate rather than
assuming coverage. Do not let the loop appear to support an agent whose trigger
cannot fire.

Coordination note: **t1448 (shadow concern badge currency) — a downstream
consumer, `depends: [1159, 1420]`.** t1420 has landed, so this task is its last
remaining blocker. It is chartered to key its "freshness" notion off **the round
metadata this task adds to the concern block**, so what this task puts in that
block is a live constraint on it, not a speculative one. It also cross-references
t1427 ("check whether a fully-rejected block should also clear the badge; do not
duplicate its store"). No obligation to build for it, but the round-metadata
format should be designed as something a second consumer can read.

## Merged from t1017: shadow steerabiility


I am developing  a coding agent harness where an "shadow agent' follow and review the work of a main agent see the aitask-shadow skill in github repo beyondeye/aitasks. The skill is working very well. But what is happening tha instead of using the shadow agent to help me stir the main agent I find myself delegating completely to shadow agent decisions like change the the main agent execution plan also i am concerned about the fact with this shadow agent has become very easy to expand the original plan with a lot of secondary concerns that would be better addressed as separate tasks. but because i dont want to "lose" them i end up iterating multiple time on the plan until all concerns are addressed. this way i end up with a plan that is perhaps "complete" but it is not any more steerable directly by me. How can i address this problems with an updated aitask-shadow skill or with some structured workflow that I can follow when using the skill?

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1017** (`t1017_shadow_steerabiility.md`)
