---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [shadow, concern_format, skills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-20 09:21
updated_at: 2026-10-20 09:22
---

## Problem

When many agents run in parallel, the user loses track of whether the last
concern block (`===AITASK-CONCERNS===` … `===END-CONCERNS===`) in an
`aitask-shadow` pane came from a **plan review** or an **implementation
review**. Today the only hint is a one-liner at the start of the round (and
only when the phase signal picked the default sub-procedure — see
`SKILL.md.j2` "Phase-driven default"), which is usually far above the block,
so the user scrolls up the shadow pane hunting for it.

## Requested change

On the line **immediately before** the opening `===AITASK-CONCERNS===` fence,
the shadow emits a short fixed phrase naming the review it is running. Keep it
simple — **no task number, no round number** (the user explicitly asked for
this; the round already lives in the `Round:` header inside the block).

Suggested wording (one per producer; finalize during planning):

| producer | label line |
|---|---|
| `plan-challenge.md` (`>pc`) | `Review: plan challenge` |
| `plan-assumptions.md` (`>pa`) | `Review: plan assumptions` |
| `plan-diagnose-errors.md` (`>d`) | `Review: error diagnosis` |
| `impl-challenge.md` (`>i`, `>i1`–`>i4`) | `Review: implementation` |

The label must appear on every block a producer emits, including
zero-concern (metadata-only, clean-round) blocks and `>r` / `>r<code>`
recheck rounds (and minimonitor's injected `refetch and recheck round N`).

## Exploration findings

- **Producers.** Four sub-procedures under `.claude/skills/aitask-shadow/`
  emit the block, each with its own near-identical "Emit a block delimited
  by…" rules section: `plan-challenge.md` (~l.151), `plan-assumptions.md`
  (~l.160), `plan-diagnose-errors.md` (~l.136), `impl-challenge.md`
  (~l.607). `concern-format.md` is the format's single source of truth.
- **Parser safety.** `concern_parser._last_block_region` scopes all
  detection to the **last** opening fence (`text.rfind(_OPEN)`), so a prose
  line just above the fence is never seen by `parse_concerns` /
  `has_concern_block` / `parse_block_meta` — same as the existing
  `In plain words:` lines and the "Where this is heading" preamble, which
  `concern-format.md` §"Prose around the block that is not parsed" already
  documents as pre-block prose.
- **Constraints on the label line:**
  - must never begin with `- [` (or `• [`) — keep it plain text;
  - must be markdown-free: Codex and OpenCode renderers rewrite markdown
    before tmux capture (`concern-format.md`, marker-glyph section; OpenCode
    strips bracket spans), so no `**bold**`, backticks, or brackets;
  - must sit directly above the opening fence (not inside the fences —
    the first line inside is reserved for `Round: <N> @ <ts>`).
- **t1123 hazard:** `concern-format.md` is read by the shadow at runtime; do
  not add a contiguous `label → open fence → items → close fence` example to
  it (it could be captured into the pane and mis-forwarded by the picker).
  Name the fences inline as the doc already does.

## Implementation outline

1. `concern-format.md`: document the label line in "Prose around the block
   that is not parsed" (placement, fixed wording per producer, not parsed).
2. Add the rule to each of the four producers' emission sections (and its
   "Rules" bullet list), with the producer's exact phrase.
3. Test: in `tests/test_concern_parser.py`, pin that a capture with the label
   line before the opening fence parses byte-identically to the same capture
   without it (`parse_concerns`, `parse_block_meta`, `has_concern_block`,
   `is_metadata_only_block`). Consider a contract test (e.g. extend
   `tests/test_shadow_seam.py` or a shell contract test) asserting each
   producer names its label.
4. Regenerate goldens for the affected `.md` procedures
   (`tests/golden/procs/aitask-shadow/` — plan-challenge/plan-assumptions/
   plan-diagnose-errors opencode goldens and the impl-challenge goldens) and
   rerender the Codex (`.agents/skills/aitask-shadow-*-codex-/`) and OpenCode
   (`.opencode/skills/aitask-shadow-*-/`) trees; run
   `./.aitask-scripts/aitask_skill_verify.sh` before committing (see
   `aidocs/framework/skill_authoring_conventions.md`).
5. `aidocs/framework/shadow_agent.md`: mention the label if it describes the
   block's on-screen shape.

## Out of scope

- Having minimonitor / monitor parse or display the review kind (the picker
  context line could show it later — separate task if wanted).
