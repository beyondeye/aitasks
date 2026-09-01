---
Task: t1561_generalize_task_staleness_detection.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1561 — Generalize task staleness detection (design + task tree)

## Context

Tasks can sit Ready for months while the codebase moves under them. The framework has three isolated freshness mechanisms — t1555's manual-verification pre-check (helper landed, 0/481 live coverage, procedure wiring still pending in t1555_3), the plan-review freshness flow in planning.md §6.0, and t1569_5's `lib/roadmap_premise.py` (whose docstring declares itself a temporary stand-in: *"t1561 generalizes task staleness for every task type; when it lands, the roadmap drops this module"*, with t1655 already filed as the adoption task). t1561 is the exploration task that must produce (a) a decision record in `aidocs/framework/` and (b) a separately planned implementation task tree. **No general mechanism is implemented in this task** — the deliverable is the design + the tree.

User decisions taken (AskUserQuestion, this session):
- **Coverage:** derived origin baseline for legacy follow-ups (roadmap_premise's landing-commit model) — broad day-one coverage, one evidence-backed prompt at first pick, quiet after dismissal advances the stored baseline. New tasks additionally seeded at creation.
- **Surfaces:** v1 = task-workflow Step 3 advisory check only; `ait ls -v` / board surfacing deferred with a named disposition in the tree's retrospective child.

## The selected design (invariants the decision record will fix)

1. **Accept the generalization** (not reject): `roadmap_premise.py` + t1655 already commit the framework to it, and the substitution surface is pinned by `tests/test_roadmap_premise.py::PublicSurfaceTests`.
2. **New frontmatter field `premise_baseline: <sha> @ <YYYY-MM-DD HH:MM>`** — the commit at which the task's premise was last known valid. Same grammar as `verification_baseline:`, which is NOT reused (it is issue_type-scoped to MV checklist validity; t1561's own constraint forbids widening it). Merge rule: `_BASE_AWARE_FIELDS` with `deletion_aware=True`; this is the third user of `_normalize_opaque_scalar`, whose own comment says the third user promotes the helper.
3. **Scope derivation, tiered (v1) — scope and baseline are orthogonal axes:**
   - Tier A (curated scope): `file_references:` when present — any issue type.
   - Tier B (derived scope): follow-up origin via `lib/followup_origin.py`, quality `exact` only; scope = files the origin's landing commits touched outside the task-data prefixes. **Derived scope is a v1 permanent** — it is what makes a seeded follow-up (stored baseline, no curated refs) checkable at all, so it survives the pre-phase no-go unchanged.
   - Neither → silent `SKIP`. Manual-verification tasks never reach the check (Step 3 Check 3 routes them away first) — no double-prompt with t1555's seam.
4. **Baseline resolution (the axis the go/no-go gates):** stored `premise_baseline` wins; else (follow-ups) **computed** origin last **landing** commit (`baseline_for` semantics — a commit naming the origin AND touching a path outside `aitasks/`, `aiplans/`, `.aitask-gates/`; 35/1615 tagged ids have a metadata-only newest commit, so "newest tagged" is wrong); else `SKIP`. The computed-baseline source is what produces the one-time legacy prompt — it, and only it, is what a pre-phase **no-go** removes from v1 (see Pre-phase). History rewrite (stored baseline unreachable via `git merge-base --is-ancestor`) → `SKIP`.
5. **Verdict engine:** tri-state `FRESH / ASK_STALE / SKIP`, line protocol modeled on `aitask_verification_stale.sh` (`BASELINE / CHECKED / FILES / CHANGED / DELETED / UNKNOWN / DISPLAY / DECISION`), always exit 0 for content states, die on CLI misuse. The new `CHECKED:<sha>` line records the exact revision the evidence was evaluated against (HEAD at check time); **every later baseline advance writes that recorded sha, never write-time HEAD** — the check result and the lock-and-write transaction are separated by Step 4, and HEAD may move in between; advancing to write-time HEAD would silently cover commits the user was never shown. Commits after the checked revision stay uncovered and surface at the next pick. Framework law preserved: **UNKNOWN drives the verdict** (one evidence list), **empty scope → SKIP not FRESH**, `%`-then-`|` injective encoding, `:(literal)` pathspec guard, probes against committed trees (dirty worktree invisible by construction).
6. **Architecture (the t1655 contract):** pure core `lib/task_premise.py` — generalizes `roadmap_premise.baseline_for` + `check`, keeps purity (`PURE_MODULES`), keeps `metadata_only` ≠ `unknown_history` — plus an impure git-facing producer `aitask_premise_stale.sh check <task_file>`. The producer may restore the two narrowings roadmap_premise accepted (a `DELETED:` record via `cat-file -e` probes; the `:(literal)` guard) since it runs git; the pure core stays text-in/text-out.
7. **Interaction:** new **Step 3 Check 6** in task-workflow (fires on every entry path: pick, board launch, explore; Ready tasks only — resume paths skip it). `FRESH`/`SKIP` → silent. `ASK_STALE` → one NON-SKIPPABLE AskUserQuestion with the evidence inside the widget text, four options:
   - *Proceed — premise still valid*: advance `premise_baseline` to the **checked revision** (the `CHECKED:` sha, not write-time HEAD); write deferred until after the Step 4 lock claim; transaction: decide → write → advance baseline **last** → commit.
   - *Review & replan with this evidence*: continue the workflow with the drift evidence threaded into planning context (§6.1 reads it; for a task with an existing/deferred-approved plan it forces the §6.0 verify path, mirroring §6.0a's `force_verify`). The baseline is **not** advanced at dismissal — it advances (to the checked revision) only after the renewed plan is approved, at the Step 7 post-approval write site, confirming the premise was actually re-validated.
   - *Postpone task*: status → Postponed, end.
   - *Pick a different task*: return to the calling skill's selection.
   **Advancing on dismissal is load-bearing** — the same evidence never re-prompts — but advancement always requires an explicit premise confirmation (dismissal or approved replan), never a mere workflow transit. No new profile key in v1 (cheap check + advance-on-dismissal already bounds noise; recorded as deferred).
8. **Seeding:** `aitask_create.sh` stamps `premise_baseline` = HEAD at creation when the new task has a derivable scope (`--followup-of` or `--file-ref` given). Carry-over tasks inherit the origin task's baseline (t1555's carryover rule generalized).
9. **Stated limits (in the record):** measures change, not behavior (both error directions persist); product/purpose drift remains human judgment — the mechanism never claims it; a silent-skip precondition can mask a broken implementation — the tree must include an end-to-end exercise (seed → change file → prompt fires → dismiss → no re-fire).
10. **Deferred, each with a named disposition:** heuristic body-path extraction tier (blocked on the six defects in `plan_path_reference_extraction_findings.md`), task-graph evidence axis (deps/status digests — `trail_gather.py` precedent), `ls -v` marker + board badge, topic-quality origins, cross-repo scopes, profile key.

## Steps (t1561 implementation, post-approval)

### Pre-phase (risk mitigations)

- **sample_live_backlog_prompt_rate** — Before finalizing the decision record's coverage section, run the existing roadmap tooling (`./.aitask-scripts/aitask_backlog_origin_facts.sh` + `lib/roadmap_premise.py`'s `baseline_for`/`check`, fed by the same commit-index rows the roadmap uses) over this repo's actual Ready follow-up tasks. Record (dated, in the decision record): (a) the fraction that would read `ASK_STALE` at first pick, (b) an actionability audit of 5 sampled `ASK_STALE` evidence sets — an evidence set is **actionable** when it names concrete drift sources the user can realistically inspect (identified tasks/commits over the origin surface, ≤10 of them), not undifferentiated churn.
  **Go/no-go rule (binding on the tree's design):**
  - **Go** (derived tier ships in v1 as planned) requires ≥3/5 sampled evidence sets actionable; and if the measured first-pick `ASK_STALE` rate exceeds 90% (a near-constant verdict discriminates nothing — the roadmap's own finding), the bar rises to 5/5: a near-universal prompt must be near-universally informative.
  - **No-go** (either bar missed): v1 narrows to **stored-baseline-only** — precisely: the **computed-baseline source** (implicit origin-landing baseline for legacy follow-ups) moves to the deferred list carrying the "behind profile key" disposition. **Derived origin scope (Tier B) and creation-time seeding remain in v1**: a seeded follow-up carries a stored baseline and derives its scope from its origin, so new follow-ups stay fully checkable — without this split the fallback would have no coverage at all (stored baseline + no scope = silent SKIP). Legacy follow-ups without a stored baseline then SKIP silently. The decision record documents the measurement that forced the narrowing, and child 1's tests assert the no-go shape if taken: stored-baseline + derived-scope → verdict; no stored baseline → SKIP.
  **Sampling method (deterministic, recorded):** the candidate pool is every Ready follow-up with an `exact`-quality origin whose check reads `ASK_STALE`, sorted by canonical task id ascending (id order ≈ creation order, so this stratifies by age). Select 5 by even stride: indices `floor(i·N/5)` for `i = 0..4`. Record the sampled task ids and each per-sample actionability verdict in the decision record alongside the rates — the go/no-go outcome must be reproducible from the record alone.
  The outcome (go or no-go, with numbers and sampled ids) is surfaced at the Step 8 review before the tree is created.

1. **Write the decision record** `aidocs/framework/task_premise_staleness.md`:
   - Structure mirrors `manual_verification_staleness.md`: what staleness means here (detectable evidence vs heuristic signal vs human judgment — consuming `plan_path_reference_extraction_findings.md` for the evidence/heuristic line); the selected model (items 1–8 above); baseline lifecycle table; measured facts (dated 2026-08-31/09-01: 481 active tasks, 234 follow-ups, 0 baseline carriers, 153/169 ASK_STALE against origin baselines, 61/1714 metadata-only tagged commits); rejected alternatives (reuse of `verification_baseline`, `created_at`-anchored baselines — false-stale on "before" risk mitigations, time-based verdicts — zero information at 20-day median age); limits; deferred items with dispositions; the t1655 substitution contract.
   - Add a one-line cross-reference from `aidocs/framework/manual_verification_staleness.md` (Related section) to the new record.
2. **Create the implementation parent task + sequential children** (via the Batch Task Creation Procedure, `--followup-of 1561` so anchor resolves to root 1538). Children auto-depend on siblings; each description self-contained per Child Task Documentation Requirements:
   1. **Core engine**: `lib/task_premise.py` (pure; generalized `baseline_for`/`check`; `PURE_MODULES` entry) + `aitask_premise_stale.sh` producer + protocol tests. **Owns these verification cases, each with its pinned expected outcome**: clean → `FRESH`; changed scope → `ASK_STALE` with `CHANGED:`; uncheckable path → `UNKNOWN:` drives `ASK_STALE`; metadata absent (no baseline, no scope) → silent `SKIP`; metadata present in every tier combination (stored/computed baseline × curated/derived scope); **history rewrite** — stored baseline unreachable from the checked revision (`merge-base --is-ancestor` fails, and the unresolvable-rev 128 case) → `SKIP`, never an error; **dirty worktree** — an uncommitted edit to a scope file produces no `CHANGED:` and flips no verdict (probes read committed trees only; mirrors `test_dirty_worktree_is_not_a_change`); negative controls (forced-failure per scope tier); and the no-go shape if the pre-phase takes it (stored baseline + derived scope → verdict; no stored baseline → `SKIP`).
   2. **`premise_baseline` field end-to-end**: `aitask_update.sh --premise-baseline` (update-only, like `plan_approved_at`), merge rule + `_normalize_opaque_scalar` promotion, extension-points 5-layer sweep, contract test pinning write/clear sites (à la `test_plan_approved_marker_contract.sh`), doc surfaces (`task-format.md`, seed instructions, CLAUDE.md). **Owns the concurrent-metadata-merge cases** in `board/aitask_merge.py` tests, expected outcomes pinned: base-aware + `deletion_aware=True` — a baseline cleared on one side is not resurrected by presence on the other; an unrelated field edit (e.g. `--status`) with newer `updated_at` does not win a baseline it never touched; divergent advances resolve without silent loss (conflict surfaces as PARTIAL rather than a guessed winner).
   3. **Creation-time seeding + carryover inheritance** in `aitask_create.sh` / `aitask_archive.sh` — tests: seeded value is creation-time HEAD; carryover inherits the origin task's baseline (never re-stamps); a task with no derivable scope is not seeded.
   4. **Workflow integration**: Step 3 Check 6 + new procedure file `.claude/skills/task-workflow/premise-staleness.md` (one-line caller per authoring conventions), NON-SKIPPABLE prompt marking, `aitask_skill_verify.sh` + per-profile rerender + goldens in the same commit. **Owns the UI/workflow verification**: the end-to-end exercise (seed → change a scope file → prompt fires → dismiss → baseline advanced → no re-fire); the TOCTOU pin (commit landing between check and write — advanced baseline equals the `CHECKED:` sha, not the newer HEAD); the replan path (baseline unchanged at dismissal, advanced only after plan approval).
   5. **Website docs child**: `website/content/docs/workflows/` page section for the advisory check (docs are a first-class child per planning conventions).
   6. **Retrospective evaluation child** (depends on all): measure real prompt rates and noise post-rollout; owns the deferred-surface dispositions (`ls -v`, board badge) and files follow-ups only if data justifies.
3. **Rewire t1655**: add the new parent to `t1655`'s `depends:` (it needs the mechanism landed, not just this record) via `aitask_update.sh --batch 1655 --deps "1561,t1569_5,<new_parent>"` — preserving existing entries.
4. **Commits**: decision record + cross-ref as a docs commit (`documentation: … (t1561)` on the code branch); task files via `./ait git` (batch-creation procedure handles its own commits).

## Files touched by t1561 itself

- `aidocs/framework/task_premise_staleness.md` (new)
- `aidocs/framework/manual_verification_staleness.md` (one-line cross-ref)
- `aitasks/` — new parent + 6 children, t1655 depends update (via helpers, `./ait git`)

No source code, skills, or tests change in this task — all mechanism work lives in the created tree.

## Verification

- Decision record covers all six "Explore and decide" items and every constraint in t1561's body; deferred items each carry a disposition; limits stated (no false all-clear).
- `./.aitask-scripts/aitask_ls.sh -v 15` lists the new parent as "Has children"; each child description names its files, contracts, and verification steps without needing this session's context.
- `t1655` frontmatter shows the added dependency; `./.aitask-scripts/aitask_ls.sh -v` shows t1655 blocked on it.
- `roadmap_premise.py` untouched (its deletion belongs to t1655); t1555_2/3/4 untouched (MV seam stays narrow, per constraint).

## Risk

### Code-health risk: low
- None identified. (t1561 writes one new aidocs file, a one-line cross-ref, and task metadata via existing helpers — no runtime code, skills, or tests change in this task.)

### Goal-achievement risk: medium
- Prompt-noise miscalibration: the derived-origin tier fires on nearly every legacy follow-up's first pick (153/169 measured ASK_STALE on the roadmap corpus); if perceived as noise, users learn to click through and the mechanism fails its purpose · severity: medium · → mitigation: inline pre-phase sample_live_backlog_prompt_rate
- t1655 substitution-contract mismatch: if the generalized lib's shape diverges from the four pinned properties (landing-commit baseline, UNKNOWN-drives-verdict, silent SKIP with distinct reasons, purity), the roadmap cannot drop `roadmap_premise.py` · severity: low · → mitigation: pinned explicitly in the decision record's substitution-contract section and in child 1's description (in-plan)
- Child self-containment: the tree's children are planned in fresh contexts and could lose design context · severity: low · → mitigation: the decision record is the durable context anchor, referenced from every child description (in-plan)

### Planned mitigations
- timing: pre-phase | name: sample_live_backlog_prompt_rate | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: prompt-noise miscalibration (goal-achievement) | desc: measure live Ready-follow-up ASK_STALE rate and evidence quality with existing roadmap tooling before finalizing the record's coverage decision
