---
Task: t1037_6_richer_concern_block_body_framing.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_3_*.md, aitasks/t1037/t1037_4_*.md, aitasks/t1037/t1037_5_*.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_1_*.md, aiplans/archived/p1037/p1037_2_*.md
Worktree: (none — current branch, profile 'fast')
Branch: current
Base branch: main
---

# Plan: Richer concern-block body framing (t1037_6)

## Context

Sibling t1037_2 (archived) shipped the **producer**: a Step 6 in the shadow
skill's `plan-challenge.md` and `plan-assumptions.md` that emits the structured
`===AITASK-CONCERNS===` block alongside the human-readable concern list, so the
user can tick a subset and forward them to the followed code-agent via
minimonitor's picker (t1037_3/_4) without retyping.

A live shadow run (gpt-5.5/Codex challenging the t1020 plan) proved the block
parses end-to-end (5/5 concerns, strict `has_concern_block` True). **But** the
user observed a real quality gap: the machine-block bodies came out
**compressed** relative to the prose list. The prose carries problem **+ why it
bites (the triggering scenario) + interpretive latitude**; the machine body kept
only the bare point. Load-bearing design intent: *the framing of a concern is as
important as the point itself* — a concern forwarded into the receiving agent
should state the problem, why it bites, and leave room for the agent to decide
how to address it.

Root cause: t1037_2's Step 6 wording called `body` the *"one-line problem (plus
why it bites)"* with a terse worked example, so the producing agent read
"one-line" as "compress" — reinforced by the parser's "one logical line" rule,
which is purely a **parser-mechanics** constraint (no literal newline
mid-concern), *not* a brevity constraint.

This is **instruction/example-only**. The parser
(`.aitask-scripts/monitor/concern_parser.py`, t1037_1) already space-joins
arbitrarily long soft-wrapped continuation lines into one body — the live t1020
capture proved multi-row rich bodies reassemble correctly. No parser/code logic
change.

## Files to modify

1. `.claude/skills/aitask-shadow/plan-challenge.md` — Step 6 (`body` rule +
   worked example).
2. `.claude/skills/aitask-shadow/plan-assumptions.md` — Step 6 (parallel `body`
   rule + worked example).
3. `tests/test_concern_parser.py` — add one round-trip test asserting a long,
   richly-framed multi-row body reassembles to exactly one `Concern` (full body
   intact) **and** `has_concern_block` is True (encodes the task's Verification
   bullet; guards the instruction's intent against parser regressions).

## Change detail

### Both `plan-challenge.md` and `plan-assumptions.md`, Step 6

**(a) Reword the `body` rule.** Replace the current terse rule
(`body` is the *"one-line problem … on one logical line — do not hard-wrap"`)
with a rule that makes the body carry the **full framing**:

- The body states the problem, **why it bites** (the triggering scenario), and
  enough context for the receiving agent to choose **how** to address it.
- It must **match the substance** of the corresponding prose item (Step 3) — do
  **not** compress to a bare one-liner.
- **"One logical line" is a parser constraint** (emit no literal newline
  mid-concern; let the terminal soft-wrap), **not** a brevity constraint — a
  rich, multi-sentence body that soft-wraps across several rows is correct and
  reassembles into one concern.

(`plan-assumptions.md` keeps its assumption-specific phrasing: assumption + *why
it is dangerous* + how the agent could confirm/harden it.)

**(b) Replace the terse worked example** in the fenced `===AITASK-CONCERNS===`
sample with **richly-framed** examples that model problem + why-it-bites +
interpretive latitude, mirroring prose-list quality — each concern still a
single physical line in the source (modelling "one logical line, no hard wrap").

## No port (cross-agent)

Claude-tree edits only. The Codex/OpenCode shadow trees are thin `SKILL.md`
wrappers redirecting to the Claude source (verified in t1037_2); they hold no
`plan-*.md`. The single Claude edit serves all three agents. The aidoc
`shadow_concern_format.md` stays unchanged — the wire format is unchanged; body
*richness* is a producer-prompt concern, and duplicating the guidance into the
format spec would split the source of truth.

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` passes (no golden/template drift —
   these are plain `.md` sub-procedures, not `.j2`).
2. `python3 -m pytest tests/test_concern_parser.py -v` (or
   `bash tests/run_all_python_tests.sh`) passes, including the new
   richly-framed round-trip test.
3. `grep -n '===AITASK-CONCERNS===' .claude/skills/aitask-shadow/plan-*.md` —
   confirm both examples updated and fences intact.
4. (Ideal, not blocking) a live shadow run now emits bodies carrying why-it-bites
   framing comparable in substance to the prose list.

## Risk

### Code-health risk: low
- Instruction/example-only edit to two prompt `.md` files plus one additive
  test; no parser/runtime logic touched, no behavioral code path changed.
  Contained blast radius. · severity: low · → mitigation: none needed
- Format/grammar unchanged (fences + `- [priority | region]` marker), so
  sibling t1037_3/_4 capture/auto-offer wiring is unaffected. · severity: low ·
  → mitigation: none needed

### Goal-achievement risk: low
- The reworded rule + richly-framed examples directly encode the user's stated
  intent (problem + why-it-bites + latitude); the new round-trip test guards
  that long rich bodies still parse to one concern. The only soft spot —
  whether the prompt *actually* produces richer live output — is inherent to
  prompt engineering and is covered by the task's "ideal" live-run check, not
  this task's hard ACs. · severity: low · → mitigation: none needed

## Step 9 (Post-Implementation)

Standard cleanup/archival per task-workflow Step 9 — current-branch profile, so
no worktree teardown; archive child via
`./.aitask-scripts/aitask_archive.sh 1037_6`.
