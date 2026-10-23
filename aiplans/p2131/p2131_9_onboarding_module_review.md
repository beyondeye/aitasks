---
Task: t2131_9_onboarding_module_review.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_8_*.md, aitasks/t2131/t2131_10_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_9 — Onboarding surfaces modules; agent review of boundaries (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It surfaces the inferred modules in onboarding and lets an
  agent propose or correct boundaries. It is fully automated.
- **Wave:** F/G (with M6).

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first.** No human gate. Agent output is written with
`by: agent:<string>`.

**Scope (defaults 5 and 8):**
- **Onboarding lines.** `onboard detect` / `classify` / `inventory` print a
  `MODULES:` summary and `MODULE_UNRESOLVED:` to-dos.
- **Missing codemap.** The onboarding **skill** generates it on the framework
  side (`aitask_codemap.sh --write`). The engine never runs it (Invariant 5).
- **Agent review.**
  - It writes `provider: agent` **proposals**. These are an inference
    provider (rank 2, below hand overrides), never overrides; a conflict is
    reported, not won. The intake is shaped like M6.4's `kind_proposals[]`,
    and `modules --scan` reads it.
  - It writes `testmap:module` lines through a key-aware rewriter planner next
    to `PlanCovers`.
- **Never `completion.mode: module`.** It never writes it, and a test pins
  that. The enabling write is t2131_11.

## Dependency hold

`Postponed` until the M6 coarse pass (t1857) wires ids for:
- **M6.1** (detect / inventory / status / finish; `onboard.yaml`);
- **M6.4** (classify, `kind_proposals[]`);
- **M6.5** (the onboarding skill).

In `depends:`: `t2131_5`. Keep it when wiring.

## Reading list

- Proposal *Onboarding verbs* (~3605-3690) and *Onboarding skill* (~3690),
  as amended by t2131_1.
- `annot/rewrite.go` (31-38, 162-169, 255-257, 304-325, 418-439, 490-521)
  and its placement goldens.
- t2131_3's reserved `provider: agent` slot.

## Owned files / provides / consumes

- **Owns:**
  - the module lines in `internal/onboard/{detect,inventory,classify}.go`;
  - the agent-proposal intake in `modules`;
  - the `PlanModule` planner and the key-aware ownership check in
    `annot/rewrite.go`;
  - the review step in `.claude/skills/aitask-testmap-onboard/**`.

  Ports to the other agent trees are separate follow-up tasks.
- **Provides:** agent-corrected boundaries, and the onboarding to-dos.
- **Consumes:** M6.1, M6.4 and M6.5 as landed; t2131_5.

## Step 0 — Reality check

1. Read the M6.1 / M6.4 line classes and the M6.5 skill structure as landed.
2. Read the `kind_proposals[]` intake shape.
3. Read the rewriter ownership checks (today `covers`-only).
4. **Stop if M6.1/M6.4/M6.5 have not landed.**
5. Record the outcome here.

## Implementation steps (coarse)

1. The onboarding lines.
2. The proposal intake read by `modules --scan`.
3. `PlanModule` and the key-aware ownership check.
4. The skill review step, including codemap generation when absent.
5. Tests and skill goldens.
6. **Commit.** `feature: … (t2131_9)`. Suggest the agent-port follow-ups.

## Verification / acceptance

- The detect / classify / inventory lines on a fixture.
- An agent proposal is written with `by: agent:<string>` and reloaded.
- A conflict is reported, not won.
- The planner places `testmap:module` lines correctly (goldens).
- No write of `completion.mode`.
- No step requires a person.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `ait engine test` is green.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
