---
priority: medium
effort: high
depends: []
xdeps: [t77_6]
xdeprepo: aitasks_go
issue_type: feature
status: Postponed
labels: [testmap, go_engine, testing, skills]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t77_6
in beyondeye/aitasks_go. This body is the framework half.

## Context

Child 9 of t2131 (test-map code-module tier), **framework half**.
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 5 and 8.
- **Coarse plan:** `aiplans/p2131/p2131_9_onboarding_module_review.md`. Only its skill steps are this task's; the onboard lines, the agent-proposal intake and the `PlanModule` planner moved to aitasks_go#t77_6.
- **Wave:** F/G (with M6), and after aitasks_go#t77_6.

This child lets an **agent propose or correct** module boundaries during
onboarding, through the onboarding skill. The engine half, aitasks_go#t77_6 in
beyondeye/aitasks_go, surfaces the inferred modules in `onboard detect` /
`classify` / `inventory` (`MODULES:`, `MODULE_UNRESOLVED:`), and provides the
`provider: agent` proposal intake read by `modules --scan` and the key-aware
`PlanModule` rewriter planner for `testmap:module` lines. It is fully
automated: there is no human gate, and agent output keeps `by: agent:<string>`.

**Scope:**
- **Missing codemap.** When `aitasks/metadata/code_areas.yaml` is absent, the onboarding **skill** generates it on the framework side (`aitask_codemap.sh --write`). The engine never runs that script (Invariant 5).
- **Agent review step.** The M6.5 skill `.claude/skills/aitask-testmap-onboard/**` gains a boundary-review step that writes:
  - `provider: agent` **proposals** through the engine's intake (an inference provider, rank 2, below hand overrides; a conflict is reported, not won; glob modules only, with no nesting and no generated prefixes; the intake's rules are aitasks_go#t77_6's);
  - `testmap:module` annotation lines, through the engine's `PlanModule` planner (never by hand-editing).
- **Rerunnable, not one-shot.** The review step can be invoked on demand whenever the codebase has moved, for example when `MODULES_DRIFT` fires or `MODULE_UNRESOLVED:` findings accumulate, as well as from the first onboarding pass. A re-run revises the existing agent proposals and keeps their `by:` provenance; hand overrides are never touched (the engine enforces this). User decision, 2026-10-23: agent-defined boundaries are where the tier's value lies, so they must be maintainable as the code evolves.
- **Reuse the agent review pass, do not build a second one.** The proposal already plans agent review machinery: the adoption model (seeds → verdicts → stamped) and *The Agent Review Pass* (packets, verdicts, calibration, budgets), owned by M6 and M7 (t1858; the M7 engine verbs are in aitasks_go#t64, not yet decomposed). The skill drives the packets and verdicts. aitasks_go#t77_6's Reality check decides how, together with this task.
- **This child never writes `completion.mode: module`.** The skill must not write it; a skill golden pins that. The enabling write is t2131_11, after module-mode support exists (aitasks_go#t77_5).
- Ports of the review step to the other agent skill trees are separate tasks, per CLAUDE.md.

## Dependency hold

`Postponed` until both of these hold:

- **aitasks_go#t77_6** (the intake and the planner) is Done. This task holds it
  as `xdeps` (`xdeprepo: aitasks_go`), which unblocks only when the target is
  Done.
- **M6.5** (the onboarding skill `.claude/skills/aitask-testmap-onboard/**`), in t1857, has a child id. t1857's coarse pass adds that id to `depends:` and flips this task to `Ready` once nothing is left unresolved.

`depends:` is empty today (the membership dependency moved with the engine
half). Keep the existing deps when wiring; `aitask_update.sh --deps` replaces
the list.

A possible further hold on an **M7** work package (agent review verbs or
pass, in t1858 / aitasks_go#t64) is decided at aitasks_go#t77_6's Reality check. If the
review must run through a framework-side M7 skill, add that hold here.
t2131_12 depends on this task, so the retrospective measures agent-refined
boundaries.

## Key Files to Modify (as M6.5 lands it)

- `.claude/skills/aitask-testmap-onboard/**` (M6.5): the review step and the codemap generation. Port it to the other agent trees as separate tasks, per CLAUDE.md.

## Reference Files for Patterns

- Proposal *Onboarding verbs* (~3605-3690) and *Onboarding skill* (~3690), as amended by t2131_1.
- aitasks_go#t77_6's landed intake format and `PlanModule` interface.

## Implementation Plan

1. **Step 0 — Reality check.** Read these as landed:
   - the M6.5 skill and its `kind_proposals[]` intake;
   - aitasks_go#t77_6's intake and planner;
   - the M7 agent review pass decision recorded in aitasks_go#t77_6's plan.

   **Stop if M6.5 or aitasks_go#t77_6 has not landed.**
2. The skill review step, invocable on demand as well as from onboarding, including codemap generation when it is missing.
3. Skill goldens.
4. Create the port follow-ups for the other agent trees.

## Verification Steps

- Skill goldens pass through `./.aitask-scripts/aitask_skill_verify.sh`.
- The skill never writes `completion.mode` (golden).
- No step requires a person.
- Port follow-ups exist for the other agent trees.

## Carried obligations (framework half)

- Scope / Missing codemap "the onboarding **skill** generates it on the framework side (`aitask_codemap.sh --write`). The engine never runs that script" — *Scope → Missing codemap*; step 2.
- Scope / Agent review "writes `provider: agent` proposals … intake shaped like M6.4's `kind_proposals[]`, and `modules --scan` reads it" — the skill writes them (*Scope → Agent review step*); the intake is aitasks_go#t77_6.
- Scope / "`testmap:module` annotation lines, through a key-aware rewriter planner next to `PlanCovers`" — the skill invokes the planner (*Agent review step*); the planner is aitasks_go#t77_6.
- Scope / Rerunnable "can be re-run on demand … revises the existing agent proposals and keeps their `by:` provenance; hand overrides are never touched" — the on-demand skill entry (*Scope → Rerunnable*; step 2); revise semantics are aitasks_go#t77_6.
- Scope / "Reuse the agent review pass … owned by M6 and M7 (t1858)" — the skill drives the packets and verdicts (*Scope*; Step 0); the M7 verbs are aitasks_go#t64.
- Scope / "This child never writes `completion.mode: module`. A test pins that" — the skill golden in *Verification*; the engine test is aitasks_go#t77_6's.
- Dependency hold / M6.1, M6.4 in t1857 → E; M6.5 skill in t1857 → F — *Dependency hold*: M6.5 in t1857; M6.1/M6.4 hold aitasks_go#t77_6.
- Dependency hold / "t2131_12 depends on this task" — *Dependency hold* (kept; t2131_12 also waits on aitasks_go#t77).
- Key Files / `internal/onboard/{detect,inventory,classify}.go` → E; `internal/testmap/modules/` intake → E; `annot/rewrite.go` `PlanModule` → E; `.claude/skills/aitask-testmap-onboard/**` review step + ports → F — *Key Files* (the skill) and step 4 (ports); the engine files moved to aitasks_go#t77_6.
- Plan Step 0 (M6.1/M6.4 line classes, rewriter checks, M7 pass) → E; (M6.5 skill and its `kind_proposals[]` intake) → F — *Implementation Plan* step 1 (the M6.5 part); the rest is aitasks_go#t77_6's Step 0.
- Plan Step 0 "Stop if M6.1/M6.4/M6.5 have not landed" — this half stops on M6.5 and aitasks_go#t77_6 (which itself stops on M6.1/M6.4).
- Plan steps 2 onboarding lines → E; 3 proposal intake → E; 4 rewriter planner → E; 5 skill review step → F; 6 tests and skill goldens → both — the skill review step is step 2 and skill goldens step 3; the rest moved to aitasks_go#t77_6.
- Verification / "No write of `completion.mode`" — *Verification*, second bullet (skill side).
- Verification / "No step requires a person" — *Verification*.
- Verification / "Skill goldens pass through `./.aitask-scripts/aitask_skill_verify.sh`" — *Verification*, first bullet.

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t77_6 and is quoted for reference only.

> - `onboard detect` / `classify` / `inventory` surface a `MODULES:` summary line and `MODULE_UNRESOLVED:` to-dos.
> - `provider: agent` proposal intake read by `modules --scan` (rank 2, below hand; glob modules only; reserved prefixes `codemap:`/`gradle:`/`go:`/`py:` refused; overlapping agent rows refused; same-name hand wins with conflict reported), shaped like M6.4's `kind_proposals[]`, and routed through M7's agent-review pass where it fits; re-runs revise agent rows and keep `by:` provenance, never touching hand overrides.
> - Key-aware rewriter ownership check plus a `PlanModule` planner for `testmap:module` lines.
> - Never writes `completion.mode` (pinned by a test).
> - Acceptance checks:
>   - detect/classify/inventory lines on a fixture;
>   - an agent proposal with `by: agent:<string>` round-trips;
>   - a build-provider conflict is reported, not won;
>   - a re-run revises agent rows, keeps provenance, leaves hand overrides;
>   - `testmap:module` placement goldens;
>   - no write of `completion.mode`;
>   - `ait engine test` green.


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

> **✉ note:t22_4** id=2026-10-30T10:12:36Z.4332aa7b61bf3a68c8131464 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:36Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t77_6. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
> | It now waits on aitasks_go#t77_6 through xdeps, which
> | unblocks only when that task is Done.
