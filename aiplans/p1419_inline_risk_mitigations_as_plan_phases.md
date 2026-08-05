---
Task: t1419_inline_risk_mitigations_as_plan_phases.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1419 — Inline risk mitigations as plan phases

## Context

The risk machinery (`risk-evaluation.md` + `risk-mitigation-followup.md`) offers exactly one disposition for a confirmed mitigation: spawn a separate task (`timing: before` blocks and ends the session; `timing: after` spawns a follow-up at Step 8d). That is the right shape for heavyweight or plan-invalidating mitigations, but costly for small ones: a "before"-blocked task is easy to forget, sibling prioritization gets awkward, and a spawned task is invisible to the shadow-agent review rounds that an inline plan phase gets for free. This task adds a per-mitigation choice at Part-1 (design-in-planning) time to **inline a mitigation into the plan as a pre- or post-phase**, with two decision metrics (`inline_risk`, `added_complexity`) and a derived recommendation. The spawn path stays fully available and remains the recommendation whenever inlining is not clearly safe.

Verified during exploration:
- `aitask_gate_risk.sh` only greps `## Risk` + the two `###` subsections → **no script/verifier changes needed**.
- `risk-mitigation-followup.md` and `risk-evaluation.md` are **profile-invariant** wrapped files (single `-default` golden + invariance assertion); `planning.md` and `SKILL.md` are profile-varying (3 goldens each) — see `tests/test_skill_render_task_workflow.sh`.
- t1331 (open) will add a Part-2 idempotency guard keyed on the `created: t<id>` annotation — this task must not change that annotation's semantics.

## Changes

### 1. `.claude/skills/task-workflow/risk-mitigation-followup.md` (core change)

**Intro (parts list):** note that Part 1 can now also dispose a mitigation *inline* (pre-/post-phase of the current plan), in which case Parts 2/3 skip it.

**"Plan record format" section:**
- Extend the timing enum: `timing: before | after | pre-phase | post-phase`. `pre-phase`/`post-phase` mean the mitigation is **incorporated into this plan's implementation steps** — no task is ever created for it; Parts 2/3 filter on `before`/`after` only and naturally skip inline lines.
- Add two agent-estimated decision metrics to the line format (recorded on every confirmed line, whatever the disposition, as provenance for the choice):
  - `inline_risk: low|medium|high` — risk of incorporating the mitigation into the main task. Estimated from separability: an independently-verifiable bounded addition (e.g. a characterization test) is low; work that could invalidate/reshape the plan (e.g. an approach spike) is high.
  - `added_complexity: low|medium|high` — how much the mitigation grows the task, **relative to the plan's own scope**.
- New line shape:
  ```
  - timing: <before|after|pre-phase|post-phase> | name: <snake_name> | type: <issue_type> | priority: <p> | effort: <e> | inline_risk: <l> | added_complexity: <l> | addresses: <which risk> | desc: <one-line description>
  ```
- Document the `→ mitigation:` cross-reference form for inline entries: `→ mitigation: inline pre-phase step <N>` / `inline post-phase step <N>` (spawned entries keep the planned name / back-filled `t<id>`; the `created: t<id>` annotation semantics are untouched — t1331 compatibility).

**Part 1, step 2 (propose):**
- Each proposed candidate carries: timing (before/after), both metrics, and a **recommended disposition** derived from them: both metrics `low` → recommend inline (pre-phase for before-timed, post-phase for after-timed); any metric `high` → recommend spawn; otherwise (any `medium`, none high) → judgement call, lean spawn. Cite the quality argument in the guidance: an inline phase automatically gets shadow-agent review coverage (plan-challenge / impl-challenge see the plan; a spawned task is invisible to them).
- Numbered plain-text list before the prompt now shows: timing · name · metrics · recommended disposition · what it does · which risk it addresses.
- First `AskUserQuestion` options become:
  - "No mitigations" (unchanged)
  - "Apply recommended dispositions" (replaces "Create all proposed" — confirms every proposal with its recommended disposition)
  - "Let me choose per mitigation" (replaces the multiSelect subset pick)
- **"Let me choose per mitigation"**: ask one question per mitigation (batch up to 4 per `AskUserQuestion` call, in proposal order). Options per question, recommended option first with "(Recommended)":
  - before-timed: "Spawn as 'before' task" / "Inline as pre-phase" / "Drop"
  - after-timed: "Spawn as 'after' task" / "Inline as post-phase" / "Drop"
  (The user can flip timing via the built-in "Other" free text.) All dropped → treat as "No mitigations".

**Part 1, step 3 (record):**
- Spawned confirmations: unchanged (write `before`/`after` lines, fill `→ mitigation:` with the planned name).
- Inline confirmations: write the `pre-phase`/`post-phase` line AND edit the plan's implementation steps — prepend a `### Pre-phase (risk mitigations)` block before step 1 / append a `### Post-phase (risk mitigations)` block after the last step, each with its own step numbering (`pre-phase step 1..N`), so existing plan step numbers are untouched and the `→ mitigation: inline pre-phase step <N>` cross-reference is unambiguous. Each phase step must be a concrete, verifiable instruction (same detail bar as normal plan steps).
- `risk_mitigations_confirmed = true` if ≥1 mitigation confirmed with any disposition.

**Part 2, step 1 / Part 3, step 1:** change "keep only `timing: before` lines" → "keep only `timing: before` lines (`pre-phase`/`post-phase` lines are inline plan phases, never spawn candidates — skip them)"; same for `after` in Part 3.

### 2. `.claude/skills/task-workflow/risk-evaluation.md`

Step 3 (`## Risk` section format): document the two accepted `→ mitigation:` link forms — a task reference (spawned) or `inline pre-phase step <N>` / `inline post-phase step <N>` (inline phase), filled by the follow-up procedure.

### 3. `.claude/skills/task-workflow/planning.md`

§6.1 "Risk-mitigation design (end of planning)" bullet (~line 322): "proposes before/after mitigation tasks" → "proposes mitigations as spawned before/after tasks **or as inline pre-/post-phases of this plan** (per-mitigation propose-and-confirm with decision metrics)". Keep the rest (creates nothing; Step 7/8d create the spawned ones).

### 4. `.aitask-scripts/skill_templates/_planning_plan_contract.md`

Append one bullet: confirmed inline risk mitigations appear as explicit `### Pre-phase (risk mitigations)` / `### Post-phase (risk mitigations)` step blocks in the implementation plan, cross-referenced from the `## Risk` bullets.

### 5. `.claude/skills/task-workflow/SKILL.md`

Doc-only parentheticals at the two dispatch sites (no dispatch-condition change):
- Step 7 "Risk-mitigation 'before' creation": note inline `pre-phase`/`post-phase` lines are not spawn candidates — a plan with only inline mitigations has no `before` lines, so `risk_before_created` stays false and the session-stop branch never fires.
- Step 8d: same note for `after` lines.

### 6. Website docs

- `website/content/docs/workflows/risk-evaluation.md` — extend "Risk-Mitigation Follow-ups": the four dispositions (spawn before/after, inline pre-/post-phase), the two metrics with the recommendation rule, and when inlining is recommended — citing the shadow-review-coverage argument. Note inline mitigations land with the task itself (no `risk_mitigation_tasks` entry, no force re-verification involvement).
- `website/content/docs/workflows/follow-up-tasks.md` (~line 75) — one sentence: small mitigations can instead be inlined as pre-/post-phases of the plan.
- `website/content/docs/workflows/_index.md` (line 44, manually-maintained list) — "offers before/after mitigation follow-ups" → "offers spawned or inline mitigation follow-ups".

### 7. Goldens + rerender (same commit)

Regenerate with `skill_template.py` (pattern from `tests/test_skill_render_task_workflow.sh`):
- Profile-invariant (default golden only): `risk-mitigation-followup-default.md`, `risk-evaluation-default.md`
- Profile-varying (×3: default/fast/remote): `planning-{p}.md`, `SKILL-{p}.md`

Then refresh live rendered variants: `./.aitask-scripts/aitask_skill_rerender.sh <profile>` once per profile (default, fast, remote), and run `./.aitask-scripts/aitask_skill_verify.sh`.

## Not changed

- `aitask_gate_risk.sh`, `aitask_risk_mitigation_landed.sh`, Step 6.0a force-reverify, `risk_mitigation_tasks` frontmatter semantics (spawned-only), the `created: t<id>` annotation (t1331 lands compatibly), Step 7/8d dispatch conditions.

## Verification

1. `bash tests/test_skill_render_task_workflow.sh` — all goldens green (diff reviewed as the audit signal, per conventions).
2. Fixture walk (scratchpad): a fixture plan whose `### Planned mitigations` has one `before`, one `pre-phase`, one `post-phase` line — confirm by reading the updated procedure that: Part 2 selects only the `before` line; Part 3 selects nothing; Step 7's dispatch (`≥1 before line`) still fires for the spawned one; a plan with only inline lines has zero `before` lines → `risk_before_created` stays false → no session stop.
3. `aitask_gate_risk.sh` still passes a plan containing the extended line format + phase blocks (run the verifier against a fixture task/plan pair in the scratchpad — it only greps section headings).
4. `shellcheck` not applicable (no script edits); `./.aitask-scripts/aitask_skill_verify.sh` passes.
5. Step 9 (Post-Implementation) per task-workflow: merge approval, gates run (`risk_evaluated` gate must pass), archival.

## Risk

### Code-health risk: low
- None identified. (Procedure-markdown + docs + goldens only; renders are pinned by `tests/test_skill_render_task_workflow.sh`; no executable code or verifier changes.)

### Goal-achievement risk: low
- The new per-mitigation prompt flow is agent-interpreted prose; ambiguity under many (>4) mitigations could degrade the live UX · severity: low · → mitigation: none (user declined — covered by the in-plan fixture walk)
