---
priority: medium
effort: medium
depends: [t1859_3]
issue_type: feature
status: Postponed
labels: [testing, testmap, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-19 15:43
updated_at: 2026-10-19 15:44
---

## Context

Child of t1859 (test-map **M8 — Completion policy and gates**), the **seeds
step of M8.3** (`aitask-gate-testmap-fresh`), wave **G**. It is split from the
base gate (`t1859_3`, wave E) because it needs the packet writer and the
verdict intake (M7.1, M7.2). Through it, a map migrates a few files per task in
ordinary work: when a task touches a test file that has rows in `seeded.yaml`,
the gate reads the engine-cut packets and adopts the pairs, or parks them, on
verdicts.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
*The Agent Review Pass → The in-gate site (Step 8)*, components *Freshness*,
*Skills* and *Agent review verbs*, *Data Flow → Level 1*, and Invariants 2 /
3. Parent plan: `aiplans/p1859_testmap_m8_completion_policy_and_gates.md`
(Dev 6).

This coarse plan records what the proposal fixes for the M8.3 seeds step. It
does not design internals against providers that do not exist yet; the
Reality check does that when this child is picked.

**Automation-first:** autonomous runs adopt through `onboard adopt
--agent-verdicts -`, where `verifies` adopts and the rest are parked and keep
selecting. The attended confirm / override / trust-batch steps are UX, never a
precondition.

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M7.1** (packets) and **M7.2** (verdict intake), in t1858.

t1858's coarse pass adds the ids and flips this task to `Ready` once nothing
is left unresolved. In `depends:`: the base gate `t1859_3`. Never depend on a
whole provider parent.

## Key Files to Modify

- `.claude/skills/aitask-gate-testmap-fresh/**` (M8.3's skill, extended): the
  seeds step. For each `COMMITTED:` / `TASK:` test file with seeds, run
  `onboard review --ids <rows>` and read the packets.
  - Attended: the agent's verdict is pre-filled per row with its rationale;
    the person confirms (`by: human`), overrides, or trusts the batch
    (`by: agent`).
  - Autonomous: `onboard adopt --agent-verdicts - --by <agent-string> --run
    <gate-run-id>`.
  - Either way, the stamps ride the `(t<id>)` commit.
- Goldens; `aitask_skill_verify.sh`.

## Reference Files for Patterns

- The base skill from `t1859_3`.
- M6.5's `review.md` (the same reading flow), once landed.

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome).** Stop if
   M7.1 or M7.2 has not landed.
1. Add the seeds step.
2. Regenerate goldens.
3. Write the fixture tests.

## Verification Steps

- Autonomous `--agent-verdicts` adoption riding the commit; parked rows left.
- Attended pre-fill / override / trust-batch recording `by: human` /
  `by: agent`.
- No stamp without a `verifies` verdict.
- `aitask_skill_verify.sh` green.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:23:07Z.f57ad2899f221e5facf2d7d1 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:07Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:15:46Z.6d3b6638f7a32c26e9473cff from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:15:46Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here unchanged.
