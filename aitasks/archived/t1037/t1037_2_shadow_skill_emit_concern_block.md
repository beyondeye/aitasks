---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t1037_1]
issue_type: feature
status: Done
labels: [shadow, claudeskills]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 11:42
updated_at: 2026-06-21 14:00
completed_at: 2026-06-21 14:00
---

## Context

Producer side of t1037. The shadow agent's plan-review sub-procedures already
emit prioritized, severity-tagged concern lists — but as free prose. This task
makes them emit the **structured concern block** defined by sibling t1037_1
(`aidocs/framework/shadow_concern_format.md`), so minimonitor's parser
(t1037_1) and modal (t1037_3/_4) can extract concerns reliably.

Depends on t1037_1 (the format spec must exist and be final). Read that spec
and the parent t1037 before starting.

## Key files to modify

- `.claude/skills/aitask-shadow/plan-challenge.md` — its Step 3 produces "a
  prioritized list of concrete weaknesses ... severity (high/medium/low)".
  Add an instruction: after presenting the human-readable list, ALSO emit the
  structured `===AITASK-CONCERNS===` block (one `- [priority | region]` item
  per concern, body verbatim) so the user can pick-and-forward via minimonitor.
  The `region` maps to the plan section/axis the concern targets.
- `.claude/skills/aitask-shadow/plan-assumptions.md` — also emits a
  concern-like list (load-bearing-and-unverified assumptions first). Decide
  whether it should emit the block too; if yes, mirror the instruction. (Keep
  `plan-socratic.md` / `plan-explain.md` out — they ask questions / teach, they
  don't produce a concern list.)
- `.claude/skills/aitask-shadow/SKILL.md` — the Step 0 greeting is *derived*
  from Step 3 (maintainer note forbids hardcoding). Confirm no greeting edit is
  needed; if the structured-emit changes a capability phrasing, update Step 3
  only.
- Preserve the **advisory-only guardrail** — the block is for the user to copy;
  the shadow still never drives the followed pane.

## Cross-agent reach (NO port needed — wrapper model, corrected during impl)

**Original AC was wrong.** It claimed the shadow skill is "replicated per agent"
and required porting the edited prose to `.agents/` and `.opencode/`. Verified
against the tree (and the t988 Codex / t989 OpenCode port commits): the Codex
and OpenCode shadow trees contain **only a thin `SKILL.md` wrapper** that
redirects to the Claude source (`.claude/skills/aitask-shadow/SKILL.md`). They
hold **no** `plan-*.md` sub-procedures — when their wrapper follows the Claude
SKILL.md's Step 3 (`read and follow plan-challenge.md`), the relative path
resolves into the Claude tree.

Therefore editing the Claude `plan-challenge.md` / `plan-assumptions.md`
**automatically serves all three agents**; there is nothing to port and nothing
to keep byte-identical (only one copy exists). This is a wrapper redirect, not a
Jinja-rendered closure, but the effect is the same: single source, all agents.

## Reference files for patterns

- `aidocs/framework/shadow_agent.md` — the shadow pipeline + skill contract.
- `aidocs/framework/skill_authoring_conventions.md` — read before editing any
  skill file.
- Sibling spec `aidocs/framework/shadow_concern_format.md` (from t1037_1) — the
  exact fence + grammar to emit.

## Implementation plan

1. Read the final format spec from t1037_1.
2. Edit `plan-challenge.md` to append the structured block after the prose
   list, with a concrete worked example matching the spec.
3. Decide + apply the same for `plan-assumptions.md`.
4. No cross-agent port — the Codex/OpenCode trees are wrappers that redirect to
   the Claude source (see "Cross-agent reach" above). The single Claude edit
   serves all three agents.
5. Run `./.aitask-scripts/aitask_skill_verify.sh` (skill/template integrity).
6. Behavioral check: do a sample shadow run (or paste a representative plan)
   and confirm the emitted block parses cleanly via t1037_1's
   `parse_concerns` — this is the producer↔parser round-trip the parent calls
   "verify with a sample run".

## Verification steps

- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- A sample emitted block feeds `concern_parser.parse_concerns` and yields the
  expected `Concern` items (closes the producer→consumer loop end-to-end with
  t1037_1).

## Notes for sibling tasks

- Record the exact emit wording so t1037_4's auto-offer (detecting a fresh
  block) keys off the same sentinel. Note any deviation from the spec back to
  t1037_1's Final Implementation Notes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-21T10:51:25Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-21T10:51:27Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-21T11:00:29Z status=pass attempt=1 type=human
