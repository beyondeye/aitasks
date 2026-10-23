---
priority: medium
effort: low
depends: [t2131_8, t2131_9]
issue_type: feature
status: Postponed
labels: [testmap, go_engine, testing, skills]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:52
updated_at: 2026-10-23 11:52
---

## Context

Child 11 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 11 ("who enables it").
- **Coarse plan:** `aiplans/p2131/p2131_11_onboarding_enable_module_mode.md`.
- **Wave:** G (after M8.5).

This is the onboarding skill's **enabling write** for `module` mode, kept separate from t2131_9 so that onboarding can never write an unsupported mode before its consumer (t2131_8) exists.

**What it writes:** `completion.mode: module` with `completion.widen` and a valid `full_run_every` (all three triggers), with agent provenance.

**When it writes:** only when all of these hold:
- the engine reports `module` as a **supported** mode. This is a capability probe of the landed config validation or `policy` verb, never a version guess;
- the modules table resolves;
- no `MODULE_UNRESOLVED:` finding blocks readiness.

**Automation-first:** no human gate.

## Dependency hold

`Postponed` only because a provider has no child id yet:

- **M6.5** (the onboarding skill and its `enable` phase config writes), in t1857.

The provider parent's coarse pass adds the id and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_8` (module-mode support) and `t2131_9` (module review in onboarding). Keep them when wiring; `aitask_update.sh --deps` replaces the list.

## Key Files to Modify (as M6.5 lands them)

- `.claude/skills/aitask-testmap-onboard/**`: the enable-phase write, behind the capability probe. Port it to other agent trees as separate tasks.
- The engine probe: `config.go` validation, or a `policy` capability line. If neither reports supported modes, add the probe to t2131_8's verb (coordinate via a note).

## Reference Files for Patterns

- Proposal *Onboarding skill* (~3690) and *Completion policy* (~1940, ~3847), as amended by t2131_1.
- How the `--policy selected` re-entry writes `completion.mode` (proposal ~423, ~3850).

## Implementation Plan

1. **Step 0 — Reality check.**
   - How the landed engine reports supported completion modes.
   - The M6.5 `enable` phase's config writes.

   **Stop if t2131_8 or M6.5 have not landed.**
2. Add the probe and the guarded write.
3. Tests and skill goldens.

## Verification Steps

- With a fake engine that lacks `module` support: no write, and the reason is reported.
- With the real engine: the write lands with agent provenance, loads, and readiness reports `cadence_declared|met`.
- An unresolved table blocks the write.
- Skill goldens pass (`./.aitask-scripts/aitask_skill_verify.sh`).
