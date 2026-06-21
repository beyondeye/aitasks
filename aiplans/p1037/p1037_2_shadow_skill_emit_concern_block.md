---
Task: t1037_2_shadow_skill_emit_concern_block.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_1_*.md, aitasks/t1037/t1037_3_*.md, aitasks/t1037/t1037_4_*.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_*_*.md
Worktree: (current branch — fast profile)
Branch: (current branch)
Base branch: main
---

# Plan: Shadow skill emits structured concern block (t1037_2)

Producer side. Make the shadow plan-review sub-procedures emit the structured
block defined by t1037_1, across all three agent trees.

## 0. Prerequisite

Read the FINAL spec `aidocs/framework/shadow_concern_format.md` (from t1037_1) —
the exact sentinel and item grammar to emit.

## 1. plan-challenge.md (Claude Code source first)

`.claude/skills/aitask-shadow/plan-challenge.md` Step 3 already yields a
prioritized list with one-line problem + why-it-bites + severity. Append an
instruction (new step / sub-bullet): after presenting the human-readable list,
ALSO emit the machine-parseable block:

```
===AITASK-CONCERNS===
- [<severity> | <plan region/axis>] <the one-line problem + why it bites>
...
===END-CONCERNS===
```

- `region` = the axis/section the concern targets (regressions, edge case,
  blast-radius, etc., or a named plan section).
- One item per concern, ordered by severity (matches the existing ordering).
- **MANDATORY leading `- ` on every concern line** and **always emit the
  closing `===END-CONCERNS===` fence** — both are load-bearing for the parser
  (t1037_1): the dash is the wrap-join collision guard, and the closing fence is
  what makes minimonitor's strict `has_concern_block` auto-offer fire. Match the
  exact marker grammar recorded in t1037_1's Final Implementation Notes.
- Keep the prose list too — the block is additive, for pick-and-forward.
- Reaffirm the advisory-only guardrail (the block is for the user to copy; the
  shadow never drives the followed pane).

## 2. plan-assumptions.md

`.claude/skills/aitask-shadow/plan-assumptions.md` also emits a concern-like
list. Decide (recommend yes) to emit the same block, mapping each
load-bearing-and-unverified assumption to an item (priority by load-bearingness).
Mirror the instruction. Leave `plan-socratic.md` / `plan-explain.md` untouched
(they don't produce concern lists).

## 3. SKILL.md greeting

Step 0 greeting is *derived* from Step 3 (maintainer note forbids a hardcoded
copy). Confirm no greeting edit is needed. Only touch Step 3 if a capability
phrasing changes.

## 4. Cross-agent port (REQUIRED)

Shadow is a replicated static skill, not an auto-rendered closure. Port the
identical prose to:
- `.agents/skills/aitask-shadow/plan-challenge.md` (+ plan-assumptions.md)
- `.opencode/skills/aitask-shadow/plan-challenge.md` (+ plan-assumptions.md)

Keep the three trees byte-identical in the new block instruction. (If a
same-commit port is truly impractical, file explicit follow-ups per CLAUDE.md —
but the diff is small and identical, so port here.)

## 5. Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- Diff the three trees: new instruction identical across Claude/Codex/OpenCode.
- **Producer→parser round-trip:** craft a representative emitted block, feed it
  to `concern_parser.parse_concerns` (t1037_1), assert the expected `Concern`
  items. This is the "verify with a sample run" the parent calls for.
- Read `aidocs/framework/skill_authoring_conventions.md` before editing.

## 6. Final Implementation Notes (fill at completion)

Record the exact emit wording so t1037_4's auto-offer keys off the same
sentinel. Note any spec deviation back to t1037_1.

See parent t1037 and **Step 9 (Post-Implementation)** for archival/merge.
