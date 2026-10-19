---
Task: t1859_3_m8_3_testmap_fresh_gate.md
Parent Task: aitasks/t1859_testmap_m8_completion_policy_and_gates.md
Sibling Tasks: aitasks/t1859/t1859_1_*.md, aitasks/t1859/t1859_2_*.md, aitasks/t1859/t1859_4_*.md, aitasks/t1859/t1859_5_*.md, aitasks/t1859/t1859_6_*.md
Archived Sibling Plans: aiplans/archived/p1859/p1859_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1859_3 — M8.3 `testmap_fresh` procedure gate, base (coarse)

## Context

Parent t1859 (M8); Module Map row **M8.3**, the base without the seeds step
(which is `t1859_6`); wave **E**. This child is the procedure-backed gate that
keeps the coverage annotations on a task's changed sources fresh before the
Step-8 commit. Task-workflow Step 8 already dispatches `kind: procedure` gates
generically, so no workflow edit is needed.

This coarse plan records what the proposal fixes for M8.3. It does not design internals against providers that do not exist yet; the Reality check below
does that when this child is picked.

**Automation-first:** no branch requires a person. The autonomous lane never
confirms `STALE` and never writes a first stamp.

- `STALE` rows are left and counted, with a gate `pass`.
- `UNSTAMPED` rows are left and counted. The gate passes during bootstrap or
  without `require_stamp`. Under `require_stamp` past `bootstrap_until` it
  records a `fail` with a machine-readable handoff to the repair coordinator
  t1853_7.
- The only stamp the gate writes is `--confirm-evidenced`, which re-stamps an
  *existing* claim.

**Dependency hold:** `Postponed` until M4.2 and M4.3 (t1855) have child ids in
`depends:`. External and soft: t635_29 (headless procedure-gate dispatch).

## Proposal reading list

- The `#### M8` row (M8.3).
- Components *Gates*, *Freshness*, *Staleness tool*, *Evidence join*,
  *Skills*.
- *The in-gate site (Step 8)*; *Adoption Model → The autonomous floor*.
- Invariants 1, 2, 3, 6 and 7.
- Parent plan Deviations 5, 6, 9, 10 and 14.
- Precedents: `.claude/skills/aitask-gate-docs-updated/SKILL.md`,
  `aidocs/gates/aitask-gate-framework.md`,
  `aidocs/framework/skill_authoring_conventions.md`.

## Owned files / provides / consumes

- **Owns:**
  - `.claude/skills/aitask-gate-testmap-fresh/**` and its goldens;
  - the `testmap_fresh` entry in `gates_reference.yaml`, synced to the live
    registry;
  - its expected name in the drift test;
  - the five `./ait testmap` / `aitask_testmap.sh` allowlist entries, since
    this is the first skill that calls the shim.
- **Provides:** the before-commit freshness step and the `UNSTAMPED` handoff.
  Consumers: M6.5, M9.5, M10.x, t1853_7, `t1859_6`.
- **Consumes:**
  - held: M4.2 (`stale --task`, `--confirm`, `--confirm-source`,
    `--confirm-evidenced`, `--retarget`, `adopted(…)` DISPLAY) and M4.3 (the
    evidence join);
  - `aitask_change_surface.sh`;
  - t635_29 (soft).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

1. Re-read the M8.3 row, the components, and the interface rows for the
   `stale` report and the adoption transitions.
2. Inspect the actual state, naming the task and commit for each:
   - M4.2 and M4.3 as landed, including their line classes and confirmation
     verbs;
   - how `check` reports `UNSTAMPED` (`registry/rules_core.go`
     `checkUnstamped`);
   - the docs-gate skill's structure and its non-interactive branch;
   - t635_29's status and its non-interactive contract;
   - the gate-skill stub/`.j2` convention;
   - whether `t1859_2` has already edited `gates_reference.yaml` and the
     drift test (if so, rebase).
3. Tabulate *proposal* / *coarse plan* / *repository*.
4. Decide each difference and record it. **Stop if M4.2 or M4.3 has not
   landed.**
5. Send notes to `t1859_6`, t1853_7, t1857 (M6.5) and t1860 (M9.5) where an
   assumption breaks, hedged.
6. Re-confirm ownership.

## Implementation steps (coarse)

1. Write the skill:
   - `stale --task` (change-surface intake) → `git diff` per `STALE` row with
     unevidenced variants;
   - retarget `STALE_PATH`; re-stamp `EVIDENCED`; resolve `check`'s
     structural rows;
   - `UNSTAMPED`: attended → prompt; autonomous → as described in *Context*;
   - never guess `UNKNOWN`;
   - read the `adopted(… by <who>)` context;
   - append the terminal block via `append --only-if-running <run-id>`;
   - attended and non-interactive branches.
2. Add the registry entry: `type: machine`, `kind: procedure`, verifier
   `aitask-gate-testmap-fresh`, `blocks_dependents: false`, no `unlocks`.
   Sync it and update the drift test.
3. Add the allowlist entries.
4. Regenerate goldens and run `aitask_skill_verify.sh`. Note the Codex and
   OpenCode ports for M9.5.

## Verification / acceptance

- A fixture run of each branch:
  - STALE left and counted, `pass`;
  - UNSTAMPED `pass`+count in bootstrap, and `fail`+handoff under
    `require_stamp` past bootstrap;
  - EVIDENCED re-stamped;
  - STALE_PATH retargeted;
  - UNKNOWN never guessed;
  - no stamp ever invented.
- The five allowlist entries are present.
- The drift test is green with the procedure entry.
- The skill goldens are green.
- No path requires a human action.

## Step 9 reference

The shared post-implementation flow: current branch, no merge.
