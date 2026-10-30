---
priority: medium
effort: high
depends: []
issue_type: feature
status: Postponed
labels: [testing, testmap, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-19 15:43
updated_at: 2026-10-19 15:43
---

## Context

Child of t1859 (test-map **M8 — Completion policy and gates**), submodule
**M8.3 — `testmap_fresh` procedure gate** (the base, without the seeds step),
wave **E**. This procedure-backed gate keeps coverage annotations on a task's
changed sources fresh before the Step-8 commit. Task-workflow Step 8 already
dispatches `kind: procedure` gates generically (`procedure-gates` →
`begin-procedure` → Read-and-follow the skill), so no workflow edit is needed.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
the `#### M8` row, components *Gates*, *Freshness*, *Staleness tool* and
*Skills*, *The in-gate site (Step 8)*, and the invariants. The parent plan
`aiplans/p1859_testmap_m8_completion_policy_and_gates.md` lists the cut fixes
in *Deviations*: Dev 5, 6, 9, 10 and 14.

This coarse plan records what the proposal fixes for M8.3. It does not design
internals against providers that do not exist yet; the Reality check does that
when this child is picked. The seeds step is a separate sibling, `t1859_6`.

**Automation-first:** no branch requires a person. The autonomous lane never
confirms `STALE` and never writes a first stamp.
- `STALE` rows are left and counted, with a `pass`.
- `UNSTAMPED` rows are left and counted. During bootstrap or without
  `require_stamp`, the gate passes. Under `require_stamp` past
  `bootstrap_until`, it fails with a machine-readable handoff to the repair
  coordinator t1853_7.
- The only stamp the gate writes is `--confirm-evidenced`, which re-stamps an
  existing claim and is never a first stamp.

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M4.2** (`stale --task`, `--confirm*`, `--retarget`)
- **M4.3** (the evidence join), both in t1855.

t1855's coarse pass adds the ids and flips this task to `Ready` once nothing
is left unresolved. Never depend on a whole provider parent.

**External, soft:** t635_29 (headless procedure-gate dispatch). Until it
lands, autonomous lanes defer this gate as `needs agent`. The skill still
ships its non-interactive branch.

## Key Files to Modify

- **New** `.claude/skills/aitask-gate-testmap-fresh/SKILL.md` (and its
  profile-aware stub/`.j2` surfaces, if that is the convention for gate
  skills; check `aitask-gate-docs-updated`). The workflow:
  - `stale --task` → `git diff` per `STALE` row with unevidenced variants;
  - retarget `STALE_PATH`; re-stamp `EVIDENCED`; resolve `check`'s
    structural rows;
  - attended: prompt on `UNSTAMPED` past bootstrap; autonomous: as above;
  - never guess `UNKNOWN`;
  - read the `adopted(… by <who>)` context;
  - append the terminal block via `append --only-if-running <run-id>`;
  - attended and non-interactive branches.
- `.aitask-scripts/gates_reference.yaml`: the `testmap_fresh` entry (machine,
  `kind: procedure`, verifier `aitask-gate-testmap-fresh`,
  `blocks_dependents: false`, no `unlocks`), synced to the live registry.
- `tests/test_gates_reference_drift.sh`: the expected gate set (rebase onto
  `t1859_2`'s edit if it landed first).
- The five allowlist touchpoints for `./ait testmap` /
  `aitask_testmap.sh`. This is the first skill that calls the shim:
  `.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`.
- Goldens; `aitask_skill_verify.sh`; wrapper surfaces via
  `aitask_audit_wrappers.sh` (Codex/OpenCode ports are M9.5's).

## Reference Files for Patterns

- `.claude/skills/aitask-gate-docs-updated/SKILL.md` (procedure-gate
  precedent, including its non-interactive branch).
- `aidocs/gates/aitask-gate-framework.md`.
- `aidocs/framework/skill_authoring_conventions.md`.

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome).** Stop if
   M4.2 or M4.3 has not landed.
1. Write the skill.
2. Add the registry entry and drift test update.
3. Add the allowlist entries.
4. Regenerate goldens and run the verify script.

## Verification Steps

A fixture run of each branch:
- STALE left and counted, `pass`;
- UNSTAMPED `pass`+count in bootstrap, and `fail`+handoff past bootstrap
  under `require_stamp`;
- EVIDENCED re-stamped;
- STALE_PATH retargeted;
- UNKNOWN never guessed;
- no stamp ever invented.

Also: the five allowlist entries are present; the drift test is green;
`aitask_skill_verify.sh` is green.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:22:57Z.6f0e1d872735c85b275c9398 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:57Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:15:38Z.ae33b2fd920eebc3e9b5a924 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:15:38Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here unchanged.
