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
  - timing: <before|after|pre-phase|post-phase> | name: <snake_name> | type: <issue_type> | priority: <p> | effort: <e> | inline_risk: <l> | added_complexity: <l> | addresses: <which risk> | desc: <one-line description> [| created: t<id>]
  ```
- **Formally define `created: t<id>`** (today it exists only in live plans and t1331's prose): an **optional, spawned-only** trailing field. Absent at design time (Part 1 never writes it); appended by the Part 2 / Part 3 back-fill step (step 4) when the task is actually created, as the creation witness t1331's idempotency guard will key on. Inline (`pre-phase`/`post-phase`) lines **never** receive it — nothing is created for them. Any future normalization of a `### Planned mitigations` block MUST preserve an existing `created:` field verbatim.
- Document the `→ mitigation:` cross-reference forms. **Identity is the stable mitigation `name`, never a step position** (positions drift when a plan is later re-verified or phases are added/dropped): inline entries use `→ mitigation: inline pre-phase <name>` / `inline post-phase <name>`; spawned entries keep the planned `name`, back-filled to `t<id>` at creation.

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
- Spawned confirmations: unchanged (write `before`/`after` lines, fill `→ mitigation:` with the planned name; `created:` is back-filled later by Parts 2/3).
- Inline confirmations: write the `pre-phase`/`post-phase` line AND edit the plan's implementation steps. **Canonical placement:** the `### Pre-phase (risk mitigations)` block is inserted immediately **before the first numbered step of the plan's main implementation body**; the `### Post-phase (risk mitigations)` block immediately **after its last numbered step** (before any trailing `## Verification` / `## Risk` sections). Each block's steps have their own numbering and each step is **labeled with its mitigation `name`** (e.g. `1. [characterize_board_sort] <instruction>`), so the name-based `→ mitigation: inline pre-phase <name>` cross-reference resolves regardless of later reordering. Existing plan step numbers are untouched. Each phase step must be a concrete, verifiable instruction (same detail bar as normal plan steps).
- `risk_mitigations_confirmed = true` if ≥1 mitigation confirmed with any disposition.

**Part 1, new step 4 (post-inline reassessment — single pass, no recursion):** If ≥1 mitigation was confirmed **inline**, the plan the user will approve is no longer the plan the risk levels were assessed against. Re-run the Risk Evaluation Procedure's Steps 1–2 **once** against the final augmented plan (implementation body + inline phases) and update the `## Risk` subsection level headings in place if a level changed. **Bullet update rules — linked bullets are durable provenance:**
  - A bullet with a `→ mitigation:` link is never deleted and never collapsed into `None identified.` — it is the record of why its mitigation (inline phase or spawned task) exists. Update it in place to describe residual state, e.g. `<description> · severity: low (residual — addressed by inline pre-phase <name>) · → mitigation: inline pre-phase <name>`, keeping its identity and link verbatim.
  - Genuinely **new** risks introduced by the augmented plan are added as separate new bullets (link `TBD`/`none`) — never by rewriting an existing linked bullet.
  - The reassessment MUST NOT reopen mitigation selection: `### Planned mitigations` lines and dispositions are preserved verbatim, and no new mitigation proposals are made (one pass, terminates).

  Thread the possibly-updated `risk_level_code_health` / `risk_level_goal_achievement` back into the workflow context — SKILL.md Step 7's post-approval field write then records the levels of the plan as approved, not the pre-insertion ones. Skip this step entirely when no inline disposition was confirmed.

**Part 2, step 1 / Part 3, step 1:** change "keep only `timing: before` lines" → "keep only `timing: before` lines (`pre-phase`/`post-phase` lines are inline plan phases, never spawn candidates — skip them)"; same for `after` in Part 3.

### 2. `.claude/skills/task-workflow/risk-evaluation.md`

Step 3 (`## Risk` section format): document the two accepted `→ mitigation:` link forms — a task reference (spawned) or `inline pre-phase <name>` / `inline post-phase <name>` (inline phase, name-based identity), filled by the follow-up procedure. Add a note that when inline mitigations are confirmed, the follow-up procedure re-runs this evaluation's Steps 1–2 once against the augmented plan (see Part 1 step 4 above) so the levels Step 7 writes describe the approved plan.

### 3. `.claude/skills/task-workflow/planning.md`

§6.1 "Risk-mitigation design (end of planning)" bullet (~line 322): "proposes before/after mitigation tasks" → "proposes mitigations as spawned before/after tasks **or as inline pre-/post-phases of this plan** (per-mitigation propose-and-confirm with decision metrics)". Keep the rest (creates nothing; Step 7/8d create the spawned ones).

### 4. `.aitask-scripts/skill_templates/_planning_plan_contract.md`

Append one bullet: confirmed inline risk mitigations appear as explicit `### Pre-phase (risk mitigations)` / `### Post-phase (risk mitigations)` step blocks — the pre-phase block immediately before the first numbered implementation step, the post-phase block immediately after the last — with name-labeled steps cross-referenced from the `## Risk` bullets by mitigation name. These two headings are the canonical insertion anchors (single sourced here and in `risk-mitigation-followup.md`).

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

- `aitask_gate_risk.sh`, `aitask_risk_mitigation_landed.sh`, Step 6.0a force-reverify, `risk_mitigation_tasks` frontmatter semantics (spawned-only), Step 7/8d dispatch conditions. The `created: t<id>` annotation's *semantics* are unchanged (creation witness, back-filled at spawn time) — this task only documents it formally in the line contract, exactly the shape t1331's guard expects to key on.

## Verification

1. `bash tests/test_skill_render_task_workflow.sh` — all goldens green (diff reviewed as the audit signal, per conventions).
2. **Fixture walk covering all four timings** (scratchpad): a fixture plan whose `### Planned mitigations` has one `before`, one `after`, one `pre-phase`, and one `post-phase` line (the `before`/`after` lines carrying `created: t<id>` back-fill examples). Assert with executable greps against the fixture: Part 2's stated filter (`timing: before`) matches exactly 1 line; Part 3's (`timing: after`) exactly 1; the two inline lines match neither; an inline-only variant of the fixture matches zero `before` lines (→ `risk_before_created` stays false → no Step 7 session stop).
3. **Semantic assertions on rendered procedures**: grep each rendered `risk-mitigation-followup` variant (all 3 profiles × rendered dirs) for the four-timing enum, both metric names, the spawned-only `created:` definition, the name-based `inline pre-phase <name>` link form, and the durable-provenance bullet rule (linked bullets never collapsed to `None identified.`) — asserting the contract survives rendering in every profile.
4. `aitask_gate_risk.sh` still passes a plan containing the extended line format + phase blocks (run the verifier against a fixture task/plan pair in the scratchpad — it only greps section headings).
5. `shellcheck` not applicable (no script edits); `./.aitask-scripts/aitask_skill_verify.sh` passes.
6. **Accepted as unverified at implementation time:** the live >4-mitigation prompt-batching behavior (order preservation across batched `AskUserQuestion` calls) is agent-interpreted prose that only a live walk of a 5-mitigation risk-gated task can exercise; the user declined a follow-up verification task for it. Record this explicitly in Final Implementation Notes.
7. Step 9 (Post-Implementation) per task-workflow: merge approval, gates run (`risk_evaluated` gate must pass), archival.

## Risk

### Code-health risk: low
- None identified. (Procedure-markdown + docs + goldens only; renders are pinned by `tests/test_skill_render_task_workflow.sh`; no executable code or verifier changes.)

### Goal-achievement risk: low
- The new per-mitigation prompt flow is agent-interpreted prose; ambiguity under many (>4) mitigations could degrade the live UX. The batching behavior itself is accepted as unverified (user declined a live-walk follow-up); the timing filters and record schema are covered by the fixture walk and rendered-procedure assertions · severity: low · → mitigation: none (user declined)

## Post-Review Changes

### Change Request 1 (2026-08-05 08:55)
- **Requested by user:** Four review findings: (1) `created:` witness documented but never consumed — Parts 2/3 could duplicate mitigations on re-entry, and the batch back-fill was not interruption-safe; (2) decision data lived only in pre-prompt prose, which the agent UI can hide — move it into the AskUserQuestion payload; (3) the per-mitigation disposition prompts lacked a NON-SKIPPABLE banner; (4) `risk-evaluation.md`'s `risk_mitigations_planned` return contract still described only before/after tasks.
- **Changes made:** Parts 2/3 step 1 now skip lines whose `created: t<id>` names an existing (active or archived) task; step 2 persists the witness per item immediately after each creation; Part 2 step 5 sets `risk_before_created` only for this run's creations. Part 1 step 2 rewritten: NON-SKIPPABLE banner (auto mode/profiles/"don't ask" do not cover the disposition prompts), candidate summaries required inside the question text, per-mitigation questions carry full decision context, option descriptions state concrete outcomes. Return contract updated for both dispositions. Goldens regenerated; variants rerendered.
- **Files affected:** `.claude/skills/task-workflow/risk-mitigation-followup.md`, `.claude/skills/task-workflow/risk-evaluation.md`, `tests/golden/procs/task-workflow/risk-mitigation-followup-default.md`, `tests/golden/procs/task-workflow/risk-evaluation-default.md`, tracked `-remote-` rendered variants.
- **Coordination note:** the witness-consumption guard implements t1331's item (2) design verbatim (skip witnessed lines whose task exists; `risk_before_created` only for actual creations). t1331's item (1) — Step 6.0a force-reverify inert under `use_current` — remains open there.

### Change Request 2 (2026-08-05 09:05)
- **Requested by user:** Four findings on the review-round changes: (1) witnessed lines were skipped outright, so a crash between witness-write and wiring left `depends:`/`risk_mitigation_tasks`/links permanently unrepaired; (2) creation and witness persistence were non-atomic with the plan commit deferred to step 4 — a crash in the gap duplicates on retry; (3) a stale `created: t<old>` (task gone) would get a second `created:` field appended, breaking the singular-field contract; (4) t1331/t1419 coordination statements still advertised the idempotency work as future/separate.
- **Changes made:** Parts 2/3 restructured to a reconcile-converge model: step 1 partitions lines into `to_create` / `witnessed_*_ids` (reconciliation inputs — excluded from creation, included in wiring/link convergence) with an explicit stale-witness branch (AskUserQuestion: re-create with replace-in-place, or mark `created: dropped`; never a second field); step 2 adds an adoption probe (reconcile-before-create via Origin-grep) and commits each witness immediately per item; steps 3/4 converge the union (append only missing IDs, repair name-form links, skip when converged). Plan record format paragraph updated (singular field, dropped marker, reconciliation-input semantics). t1331 annotated with a Scope update section (item 2 landed here; item 1 + fixture verification remain); t1419's Coordination section updated to match.
- **Files affected:** `.claude/skills/task-workflow/risk-mitigation-followup.md`, `tests/golden/procs/task-workflow/risk-mitigation-followup-default.md`, tracked `-remote-` rendered variants, `aitasks/t1331_guard_risk_mitigation_reentry.md`, `aitasks/t1419_inline_risk_mitigations_as_plan_phases.md`.

### Change Request 3 (2026-08-05 09:20)
- **Requested by user:** Six findings: (1) `risk_before_created` counted only this-run creations, so a recovery run could proceed into implementation with a witnessed-but-unfinished before-dependency; (2) the stale-witness prompt header "Stale witness" exceeds the documented 12-char AskUserQuestion header cap; (3) the adoption probe's filename-substring match could adopt `foo_extended` for a missing `foo`; (4) the new recovery prompts lacked a NON-SKIPPABLE banner; (5) `created: dropped` left the line and its risk link claiming a mitigation that will never execute, and the schema admitted only `created: t<id>`; (6) inline-phase placement had no defined anchor for plans without numbered main steps.
- **Changes made:** (1) Return signal renamed to `risk_before_blocking` — true when any before-mitigation (created, adopted, or witnessed) is unfinished; false only when all landed; SKILL.md Step 7 dispatch/stop text updated to name the unfinished tasks; t1419's AC bullet updated for the rename. (2) Header renamed to "Witness"; new Test 7 in `tests/test_skill_render_task_workflow.sh` pins all headers in this file to ≤12 chars (negative-controlled: re-adding a 13-char header is detected). (3) Adoption probe now requires the exact filename stem `t<id>_<name>` AND the anchored Origin provenance line; ambiguity asks the user ("Adopt task" prompt). (4) Part 2 procedure now opens with a NON-SKIPPABLE recovery-prompts banner (also governing Part 3). (5) Drop disposition rewrites the risk link to `→ mitigation: dropped (was <name>)` in the same commit; line shape formalized as `[| created: <t<id> | dropped>]`; partitions skip dropped lines explicitly. (6) Deterministic fallback anchors defined in both the plan contract and Part 1 step 3: pre-phase at top of plan body after the metadata header, post-phase before the first of `## Verification`/`## Risk` (end of file if neither).
- **Files affected:** `.claude/skills/task-workflow/risk-mitigation-followup.md`, `.claude/skills/task-workflow/SKILL.md`, `.aitask-scripts/skill_templates/_planning_plan_contract.md`, `tests/test_skill_render_task_workflow.sh`, regenerated goldens (`risk-mitigation-followup-default`, `SKILL-fast`, `planning-{default,fast,remote}`), tracked `-remote-` rendered variants, `aitasks/t1419_...md` (AC wording).
- **Note:** two pre-existing 13-char headers elsewhere ("Related tasks" in related-task-discovery.md, "Manual verify" in planning.md) exceed the documented cap — recorded as upstream defects for Step 8b.

### Change Request 4 (2026-08-05 09:28)
- **Requested by user:** (1) the adoption probe's "anchored" Origin match could be read as full-line and would then miss the real heredoc line (which continues ", created at ..."), re-creating duplicates; (2) adopted tasks were labeled unfinished by definition, so adopting an already-landed archived mitigation would wrongly stop the session again.
- **Changes made:** Probe contract now specifies the comma-delimited provenance prefix `Risk-mitigation ("before") for t<task_id>,` (comma delimits the id; end-of-line explicitly NOT anchored) — mirrored for Part 3's "after" prefix. Step 5 evaluates adopted tasks exactly like witnessed ones (landed vs unfinished), so only genuinely unfinished mitigations block.
- **Files affected:** `.claude/skills/task-workflow/risk-mitigation-followup.md`, regenerated golden, tracked `-remote-` rendered variants.
