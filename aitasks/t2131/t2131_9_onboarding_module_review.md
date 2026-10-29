---
priority: medium
effort: high
depends: [t2131_5]
issue_type: feature
status: Postponed
labels: [testmap, go_engine, testing, skills]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-24 23:23
---

## Context

Child 9 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 5 and 8.
- **Coarse plan:** `aiplans/p2131/p2131_9_onboarding_module_review.md`.
- **Wave:** F/G (with M6).

This child brings the inferred modules into onboarding and lets an **agent propose or correct** module boundaries. It is fully automated: there is no human gate, and agent output keeps `by: agent:<string>`.

**Scope:**
- **Onboarding output.** `onboard detect` / `classify` / `inventory` surface the inferred modules: a `MODULES:` summary line, and `MODULE_UNRESOLVED:` to-dos in the inventory.
- **Missing codemap.** When `aitasks/metadata/code_areas.yaml` is absent, the onboarding **skill** generates it on the framework side (`aitask_codemap.sh --write`). The engine never runs that script (Invariant 5).
- **Agent review.** The M6.5 skill's agent review writes:
  - `provider: agent` **proposals**. They are an inference provider (rank 2, below hand overrides, default 5), not overrides; a conflict is reported, not won. The intake is shaped like M6.4's `kind_proposals[]`, and `modules --scan` reads it;
    - code modules are flat (revised 2026-10-24, user decision; proposal component *Code modules*), so an agent row is a **glob module**: a name and its globs, with no nesting;
    - its name may not use the generated prefixes `codemap:`, `gradle:`, `go:`, `py:`;
    - the intake refuses two agent rows that overlap;
    - a hand module with the same name wins, and the conflict is reported;
  - `testmap:module` annotation lines, through a **key-aware rewriter planner** next to `PlanCovers`. Today `annot/rewrite.go` writes only `covers` lines: see `ownedBy` 304-313, `coverAt` 316-325, `PlanCovers` 490-521.
- **Rerunnable, not one-shot.** The agent review is not only a step of the first onboarding pass. It can be re-run on demand whenever the codebase has moved, for example when `MODULES_DRIFT` fires or `MODULE_UNRESOLVED:` findings accumulate. A re-run revises the existing agent proposals and keeps their `by:` provenance; hand overrides are never touched. User decision, 2026-10-23: agent-defined boundaries are where the tier's value lies, so they must be maintainable as the code evolves.
- **Reuse the agent review pass, do not build a second one.** The proposal already plans agent review machinery: the adoption model (seeds → verdicts → stamped) and *The Agent Review Pass* (packets, verdicts, calibration, budgets), owned by M6 and M7 (t1858). The boundary review should run through that machinery rather than a parallel proposal path. The Reality check decides how; if it needs an M7 work package, add that hold (below).
- **This child never writes `completion.mode: module`.** A test pins that. The enabling write is t2131_11, after module-mode support exists (t2131_8).

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M6.1** (`onboard detect` / `inventory` / `status` / `finish`; the `onboard.yaml` ledger), in t1857;
- **M6.4** (`onboard classify`, `kind_proposals[]`), in t1857;
- **M6.5** (the onboarding skill `.claude/skills/aitask-testmap-onboard/**`), in t1857.

Each provider parent's coarse pass adds the ids and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_5` (membership and `MODULE_UNRESOLVED:`). Keep it when wiring; `aitask_update.sh --deps` replaces the list.

A possible further hold on an **M7** work package (agent review verbs or pass, in t1858) is not recorded yet. It is decided at the Reality check below, not guessed now. t2131_12 depends on this task, so the retrospective measures agent-refined boundaries.

## Key Files to Modify (as M6 lands them)

- `goengines/internal/onboard/{detect,inventory,classify}.go` (M6.1 / M6.4): the module lines.
- `goengines/internal/testmap/modules/`: the agent-proposal intake read by `modules --scan` (the slot is reserved by t2131_3).
- `goengines/internal/testmap/annot/rewrite.go`: a key-aware ownership check plus a `PlanModule` planner.
- `.claude/skills/aitask-testmap-onboard/**` (M6.5): the review step. Port it to the other agent trees as separate tasks, per CLAUDE.md.

## Reference Files for Patterns

- Proposal *Onboarding verbs* (~3605-3690) and *Onboarding skill* (~3690), as amended by t2131_1.
- `annot/rewrite.go` (`Edit`, `PlanCovers`, `Placement`) and its placement goldens.

## Implementation Plan

1. **Step 0 — Reality check.** Read these as landed:
   - the M6.1 / M6.4 line classes;
   - the M6.5 skill and its `kind_proposals[]` intake;
   - the rewriter ownership checks for a non-`covers` key;
   - the landed M7 agent review pass (proposal *The Agent Review Pass*, ~1241; t1858): can module-boundary proposals travel as its packets and verdicts, with its calibration and budgets? If so, use it and add the M7 hold. If not, record why in the plan before building a proposal path of its own.

   **Stop if M6.1/M6.4/M6.5 have not landed.**
2. The onboarding lines.
3. The proposal intake, through the agent review pass where the Reality check says it fits.
4. The rewriter planner.
5. The skill review step, invocable on demand as well as from onboarding.
6. Tests and skill goldens.

## Verification Steps

- detect / classify / inventory lines on a fixture.
- An agent proposal is written with `by: agent:<string>` and reloaded.
- A conflict with a build provider is reported, not won.
- A re-run after the code moves revises the agent's own proposals, keeps their provenance, and leaves hand overrides untouched.
- `testmap:module` lines are placed by the planner (goldens).
- No write of `completion.mode`.
- No step requires a person.
- Skill goldens pass through `./.aitask-scripts/aitask_skill_verify.sh`.
- `ait engine test` is green.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:24:16Z.83666a38ca0759637c48dc8a from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:16Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
