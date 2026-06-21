---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [shadow, claudeskills]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 14:38
updated_at: 2026-06-21 18:09
---

## Context

Follow-up to t1037_2 (archived), which shipped the **producer**: a new Step 6 in
`.claude/skills/aitask-shadow/plan-challenge.md` and `plan-assumptions.md` that
emits the structured `===AITASK-CONCERNS===` block alongside the human-readable
concern list.

Live testing (a gpt-5.5 / Codex shadow agent challenging the t1020 plan in
`agent-pick-1020`) confirmed the block format parses correctly end-to-end
(5/5 concerns, strict `has_concern_block` True — and notably proved the
cross-agent wrapper redirect works). **But** the user observed a real quality
gap: the machine-block bodies are **compressed** relative to the prose list. The
prose carries the problem **+ why it bites (the triggering scenario) + suggested
latitude** ("I would ask the agent to add a focused app-level test…"); the
machine body keeps only the bare point.

User feedback (load-bearing design intent): **the framing of a concern is as
important as the point itself.** A concern forwarded to the receiving coding
agent (via `build_clipboard_payload`) should state the problem, why it bites, and
leave the agent room to decide how to address it. Compressing to a one-liner
strips exactly the context that lets the downstream agent interpret and act well.

Root cause: t1037_2's Step 6 wording said `body` is the **"one-line problem
(plus why it bites)"** with a terse worked example — the producing agent read
"one-line" as "compress," reinforced by the parser's "one logical line" rule
(which is purely a *parser-mechanics* constraint: no literal newline mid-concern).

## Key files to modify

- `.claude/skills/aitask-shadow/plan-challenge.md` — Step 6 (the block-emit
  instruction added by t1037_2).
- `.claude/skills/aitask-shadow/plan-assumptions.md` — Step 6 (parallel
  instruction).

## Change

1. Reword the `body` rule in **both** Step 6 blocks so the body carries the
   **full framing** — the problem, *why it bites* (the triggering scenario), and
   enough context for the receiving agent to choose how to address it. Explicitly
   state: do **not** compress to a bare one-liner; the machine body should match
   the **substance** of the corresponding prose item. Clarify that **"one logical
   line"** is a *parser constraint* (no literal newline mid-concern; let the
   terminal soft-wrap) — **not** a brevity constraint.
2. Replace the terse worked examples in both files with **richly-framed**
   examples that model problem + why-it-bites + interpretive latitude (mirroring
   the prose-list quality), so the producing agent has the right template.

## No parser / code change

The parser (`.aitask-scripts/monitor/concern_parser.py`, t1037_1) already
space-joins arbitrarily long soft-wrapped continuation lines into one body — the
live t1020 capture proved multi-row rich bodies reassemble correctly. This task
is **instruction/example-only**.

## Cross-agent reach (NO port)

Claude-tree edits only. The Codex/OpenCode shadow trees are thin `SKILL.md`
wrappers that redirect to the Claude source (verified in t1037_2); they hold no
`plan-*.md`. The single Claude edit serves all three agents. Do **not** port.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- Round-trip a long, richly-framed multi-row body through
  `concern_parser.parse_concerns` and assert it still yields exactly **one**
  `Concern` with the full body reassembled (no splitting, motivation intact),
  and `has_concern_block` True.
- Ideally, a live shadow run (or pasted plan) now emits a block whose bodies
  carry the why-it-bites framing, comparable in substance to the prose list.

## Notes for sibling tasks

- No sentinel/grammar change — fences and `- [priority | region]` marker are
  unchanged, so t1037_4's auto-offer / capture wiring is unaffected.
- Richer bodies directly improve what `build_clipboard_payload` forwards into the
  followed pane — this is the payoff the picker (t1037_3/_4) delivers.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-21T15:09:49Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-21T15:09:50Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-21T15:14:39Z status=pass attempt=1 type=human
