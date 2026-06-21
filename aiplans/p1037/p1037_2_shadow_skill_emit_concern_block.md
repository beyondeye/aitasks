---
Task: t1037_2_shadow_skill_emit_concern_block.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_3_concern_picker_modal.md, aitasks/t1037/t1037_4_minimonitor_trigger_capture_wiring.md, aitasks/t1037/t1037_5_manual_verification_minimonitor_shadow_concern_picker.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_1_concern_format_spec_and_parser.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-21 13:50
---

# Plan: Shadow skill emits structured concern block (t1037_2) — verified

Producer side of the t1037 concern-picker feature. Make the shadow agent's
plan-review sub-procedures emit the structured `===AITASK-CONCERNS===` block
defined by sibling t1037_1, so minimonitor's parser/modal can extract concerns
for selective forward-to-followed-agent.

## Context

The shadow agent already produces prioritized, severity-tagged concern lists,
but as free prose. Sibling **t1037_1 (landed/archived)** shipped the format spec
(`aidocs/framework/shadow_concern_format.md`) and a pure parser
(`.aitask-scripts/monitor/concern_parser.py`). This task adds the **producer**:
the shadow's plan-review sub-procedures must *additionally* emit the
machine-parseable block so the user can tick a subset and forward them via
minimonitor's picker (t1037_3/_4) instead of retyping.

### ⚠️ Verification finding — task/old-plan assumption is WRONG (scope correction)

The task definition and the pre-existing plan both assert the shadow skill is
**"replicated per agent"** and demand a **REQUIRED cross-agent port** of the
edited prose to `.agents/skills/aitask-shadow/plan-challenge.md` and
`.opencode/skills/aitask-shadow/plan-challenge.md`.

**That is factually false against the current tree.** Verified directly:

- `.agents/skills/aitask-shadow/` and `.opencode/skills/aitask-shadow/` contain
  **only `SKILL.md`** — thin **wrappers** that say *"The authoritative skill
  definition is `.claude/skills/aitask-shadow/SKILL.md`. Read that file and
  follow its complete workflow."* There are **no** `plan-*.md` files there
  (`find .agents .opencode -name 'plan-*.md' -path '*shadow*'` → none).
- The Codex port (t988, `4fa30abe5`) and OpenCode port (t989, `7b8b66ed2`)
  deliberately created wrapper-only `SKILL.md` (Codex) / `SKILL.md` + command
  (OpenCode) — they did **not** replicate the sub-procedures.
- Consequence: when a Codex/OpenCode shadow agent runs and Step 3 says
  *"read and follow `plan-challenge.md`"*, that relative path resolves into the
  **Claude** tree (the wrapper redirected there). All three agents already
  share the single Claude copy.

**Therefore the cross-agent port is a NO-OP.** Editing the Claude
`plan-challenge.md` / `plan-assumptions.md` automatically serves Codex and
OpenCode via the wrapper redirect. The old plan's §4 ("Cross-agent port
REQUIRED") and its "three trees byte-identical" verification step are obsolete
and are dropped. This is surfaced explicitly (no silent AC deviation) — see the
checkpoint note; the task AC will be corrected as part of the scope decision.

*(Distinct from the auto-render closure model — this is a wrapper redirect, not
Jinja rendering — but the practical effect is the same: one source, all agents.)*

## Scope

- **Edit (Claude source only):**
  - `.claude/skills/aitask-shadow/plan-challenge.md`
  - `.claude/skills/aitask-shadow/plan-assumptions.md`
- **No edit:** `SKILL.md` (greeting is *derived* from Step 3; block emission is
  internal to the sub-procedures and adds no capability — the one-phrase
  descriptions "Adversarially challenge a plan" / "Surface a plan's assumptions"
  are unchanged). Confirmed no Step 3 capability phrasing changes.
- **No cross-agent port** (wrapper model — see finding above).
- **Untouched:** `plan-socratic.md` / `plan-explain.md` (they question / teach;
  they don't produce a concern list).

## Implementation

### 1. `.claude/skills/aitask-shadow/plan-challenge.md` — append a new Step 6

After Step 5 ("Stay honest"), add a step that emits the structured block as an
**additive** copy of the same prioritized concerns. Exact rules, matching the
locked grammar in `shadow_concern_format.md` and `concern_parser.py`:

- Fences `===AITASK-CONCERNS===` … `===END-CONCERNS===` (ASCII).
- One concern per line: `- [priority | region] body`.
- Leading `- ` (dash + space) **MANDATORY** on every concern line (wrap-collision
  guard).
- `priority` ∈ {high, medium, low} — reuse the Step 3 severity.
- `region` = the plan section / axis the concern targets (a step name,
  `verification`, `blast radius`, …).
- `body` = the one-line problem (+ why it bites) on **one logical line** (don't
  hard-wrap; let the terminal soft-wrap — the parser space-joins continuations).
- Order by severity (matches the prose list).
- **Always emit the closing fence** (minimonitor's strict auto-offer requires it).
- Emit the block **only when ≥1 concern**; if the plan is genuinely clean (Step
  5), omit the block.
- Reaffirm **advisory-only**: the block is for the user to copy; never drive the
  followed pane.

Include a concrete worked example (2 items, high/medium) verbatim in the spec
shape so the producing agent has a template.

### 2. `.claude/skills/aitask-shadow/plan-assumptions.md` — append a new Step 6

Same block, same grammar/rules (keep the instruction prose parallel to
plan-challenge for maintainability). Mapping for this sub-procedure:

- One item per **dangerous** assumption (load-bearing AND unverified), which are
  already ordered first by Step 4. Optionally include lesser ones.
- `priority`: load-bearing + unverified → `high`; load-bearing + verified, or
  peripheral + unverified → `medium`; peripheral → `low`.
- `region` = the assumption category (environment/tooling, data/inputs, behavior
  of other code, sequencing/dependencies, intent/scope) or a named plan region.
- `body` = the assumption statement + why it's dangerous.
- Same closing-fence / mandatory-dash / advisory-only / omit-when-empty rules.

### 3. SKILL.md — confirm-only, no edit

Re-read Step 0 (derived greeting) and Step 3; confirm the new internal emission
does not change any capability one-phrase. No edit.

### 4. Correct the task AC (user-approved scope decision)

Edit `aitasks/t1037/t1037_2_shadow_skill_emit_concern_block.md` to replace the
false "replicated per agent / REQUIRED cross-agent port" content with the
verified wrapper-model reality:

- Rewrite the `## Cross-agent port (REQUIRED — shadow is a replicated static
  skill)` section → a note that the Codex/OpenCode shadow skills are thin
  wrappers redirecting to the Claude source, so the single Claude-tree edit
  serves all three agents (no port; nothing to replicate).
- Drop the verification bullet asserting "the three agent trees' plan-challenge.md
  … are byte-identical" (there is only one copy).
- Keep the round-trip / `aitask_skill_verify.sh` verification bullets.

Commit the task-file edit separately with `./ait git` (task data may live on a
separate branch); stage only this task file's path (concurrent-writer safety).
This honors "no silent AC deviation" — the dropped requirement is corrected in
the AC, not quietly skipped.

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` passes (skill/template integrity).
2. **Producer → parser round-trip** (the parent's "verify with a sample run"):
   feed the exact worked-example block from the new instruction through the
   t1037_1 parser and assert it yields the expected `Concern` items:
   ```bash
   python3 - <<'PY'
   import sys; sys.path.insert(0, ".aitask-scripts/monitor")
   from concern_parser import parse_concerns, has_concern_block
   block = open("/tmp/t1037_2_example.txt").read()   # the emitted example
   cs = parse_concerns(block)
   assert has_concern_block(block) and len(cs) == 2, cs
   assert cs[0].priority == "high" and cs[1].priority == "medium", cs
   print("ROUND-TRIP OK", cs)
   PY
   ```
   Confirms the closing fence is present (strict `has_concern_block` True),
   the mandatory dash parses, and priorities/regions/bodies extract correctly —
   closing the producer→consumer loop with t1037_1.
3. No `plan-*.md` exists in `.agents`/`.opencode` shadow trees → nothing to port;
   re-confirm the wrappers still redirect to the Claude source.

## Notes for sibling tasks (record at completion)

Record the exact emitted sentinel/wording so t1037_4's auto-offer keys off the
same `===AITASK-CONCERNS===` / `===END-CONCERNS===` fences. No deviation from the
t1037_1 spec is intended; note any in the plan's Final Implementation Notes.

See parent t1037 and **Step 9 (Post-Implementation)** for archival/merge.

## Risk

### Code-health risk: low
- Edits are confined to two advisory-only skill **markdown** sub-procedures; no
  executable code path changes. The block is additive (prose list retained) and
  the advisory-only guardrail is reaffirmed, not weakened · severity: low · →
  mitigation: none needed.
- Drift risk: the emitted grammar must stay in lockstep with
  `shadow_concern_format.md` / `concern_parser.py`. Mitigated in-task by the
  round-trip verification against the real parser (step 2 above) · severity: low
  · → mitigation: covered by verification, no separate task.

### Goal-achievement risk: low
- The cross-agent-port assumption in the task/old-plan was wrong; correcting it
  (wrapper model → single Claude edit serves all agents) is the convergent,
  verified path, so the goal ("all three agents emit the block") is met by one
  edit · severity: low · → mitigation: explicit scope correction surfaced at the
  approval checkpoint; task AC to be updated.
- Producer↔parser contract is locked by t1037_1 and re-validated here by a live
  round-trip, so a format mismatch cannot pass silently · severity: low · →
  mitigation: covered by verification.

## Final Implementation Notes

- **Actual work done:** Added a new **Step 6** to
  `.claude/skills/aitask-shadow/plan-challenge.md` and to
  `.claude/skills/aitask-shadow/plan-assumptions.md`, instructing the shadow
  agent to emit the structured `===AITASK-CONCERNS===` … `===END-CONCERNS===`
  block (additive to the existing prose list) using the locked t1037_1 grammar:
  mandatory leading `- `, `[priority | region] body`, one-logical-line bodies,
  severity-ordered, always-closed fence, omit-when-empty, advisory-only. Each
  step carries a 2-item worked example. `plan-assumptions.md` adds the
  load-bearing/unverified → priority mapping. `SKILL.md` was confirmed
  unchanged (its greeting derives from Step 3, whose capability one-phrases did
  not change). The task AC was corrected (see Deviations).
- **Deviations from plan:** The task & original plan's **"Cross-agent port
  (REQUIRED)"** rested on a false premise ("shadow is replicated per agent").
  Verified the Codex (`.agents/`) and OpenCode (`.opencode/`) shadow trees hold
  **only a wrapper `SKILL.md`** that redirects to the Claude source — no
  `plan-*.md` files (ports t988/t989 were wrapper-only). So the single Claude
  edit serves all three agents via the wrapper redirect; **no port was done**.
  Surfaced to the user (chose "Drop port + fix task AC"); the task file's
  Cross-agent section, implementation-plan step 4, and the "three trees
  byte-identical" verification bullet were corrected to match reality.
- **Issues encountered:** None. The task file was concurrently rewritten by the
  workflow's own metadata/gate writes mid-edit (expected — re-read and retried).
- **Key decisions:** Kept the emit-instruction prose parallel between the two
  sub-procedures for maintainability; made plan-assumptions map
  load-bearing+unverified → high so the most dangerous assumptions forward first.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** The exact sentinel fences t1037_4's auto-offer
  must key off are `===AITASK-CONCERNS===` (open) and `===END-CONCERNS===`
  (close); producers always emit the closing fence (strict `has_concern_block`
  depends on it). No deviation from the t1037_1 spec/grammar. Verified the
  producer→parser round-trip: both worked examples (extracted from the edited
  skill files) parse via `concern_parser.parse_concerns` to 2 `Concern`s with
  correct priorities and a passing strict `has_concern_block`. The wrapper-model
  finding applies to **all** shadow `plan-*.md` sub-procedures — future shadow
  sub-procedure edits are Claude-tree-only too (no cross-agent port).
