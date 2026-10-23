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
updated_at: 2026-10-23 11:51
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
  - `testmap:module` annotation lines, through a **key-aware rewriter planner** next to `PlanCovers`. Today `annot/rewrite.go` writes only `covers` lines: see `ownedBy` 304-313, `coverAt` 316-325, `PlanCovers` 490-521.
- **This child never writes `completion.mode: module`.** A test pins that. The enabling write is t2131_11, after module-mode support exists (t2131_8).

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M6.1** (`onboard detect` / `inventory` / `status` / `finish`; the `onboard.yaml` ledger), in t1857;
- **M6.4** (`onboard classify`, `kind_proposals[]`), in t1857;
- **M6.5** (the onboarding skill `.claude/skills/aitask-testmap-onboard/**`), in t1857.

Each provider parent's coarse pass adds the ids and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_5` (membership and `MODULE_UNRESOLVED:`). Keep it when wiring; `aitask_update.sh --deps` replaces the list.

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
   - the rewriter ownership checks for a non-`covers` key.

   **Stop if M6.1/M6.4/M6.5 have not landed.**
2. The onboarding lines.
3. The proposal intake.
4. The rewriter planner.
5. The skill review step.
6. Tests and skill goldens.

## Verification Steps

- detect / classify / inventory lines on a fixture.
- An agent proposal is written with `by: agent:<string>` and reloaded.
- A conflict with a build provider is reported, not won.
- `testmap:module` lines are placed by the planner (goldens).
- No write of `completion.mode`.
- No step requires a person.
- Skill goldens pass through `./.aitask-scripts/aitask_skill_verify.sh`.
- `ait engine test` is green.
