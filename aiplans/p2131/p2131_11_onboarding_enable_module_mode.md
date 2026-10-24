---
Task: t2131_11_onboarding_enable_module_mode.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_10_*.md, aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_11 — Onboarding's enabling write for `module` mode (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It is the onboarding skill's enabling write for `module`
  mode. It is kept separate so that onboarding can never write an unsupported
  mode before its consumer exists (t2131_8).
- **Wave:** G (after M8.5).

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first.** No human gate. The write carries agent provenance.

**What it writes:** `completion.mode: module` and a valid `full_run_every`
(all three triggers). There is no `completion.widen` (revised 2026-10-24,
user decision: code modules are flat).

**When it writes:** only when all of these hold:
- the engine reports `module` as **supported** (a capability probe, never a
  version guess);
- the modules table resolves;
- no `MODULE_UNRESOLVED:` blocks readiness.

## Dependency hold

`Postponed` until the M6 coarse pass (t1857) wires the id for:
- **M6.5** (the onboarding skill and its `enable` phase).

In `depends:`: `t2131_8` and `t2131_9`. Keep these when wiring.

## Reading list

- Proposal *Onboarding skill* (~3690) and *Completion policy* (~1940,
  ~3847), as amended by t2131_1.
- How the `--policy selected` re-entry writes `completion.mode` (proposal
  ~423, ~3850).
- t2131_8's plan: the capability probe.

## Owned files / provides / consumes

- **Owns:** the guarded write in `.claude/skills/aitask-testmap-onboard/**`.
  Ports are separate tasks.
- **Provides:** an automated route into `module` mode.
- **Consumes:** t2131_8 (support and the probe); t2131_9 (module review); M6.5.

## Step 0 — Reality check

1. How the landed engine reports supported completion modes. If it does not,
   coordinate with t2131_8's owner via a note.
2. The M6.5 `enable` phase's config writes.
3. **Stop if t2131_8 or M6.5 have not landed.**
4. Record the outcome here.

## Implementation steps (coarse)

1. The capability probe call.
2. The guarded write.
3. Tests and skill goldens.
4. **Commit.** `feature: … (t2131_11)`.

## Verification / acceptance

- With a fake engine that lacks `module` support: no write, and the reason is
  reported.
- With the real engine: the write lands with agent provenance, loads, and
  readiness reports `cadence_declared|met`.
- An unresolved table blocks the write.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
