---
priority: medium
effort: medium
depends: [t2131_7, t1859_4, t1859_5]
xdeps: [t77_5]
xdeprepo: aitasks_go
issue_type: feature
status: Postponed
labels: [testmap, go_engine, testing, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t77_5
in beyondeye/aitasks_go. This body is the framework half.

## Context

Child 8 of t2131 (test-map code-module tier), **framework half**.
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 11.
- **Coarse plan:** `aiplans/p2131/p2131_8_module_completion_mode.md`. Only its `aitask_test.sh` `POLICY` hook arm and the `module` matrix in `tests/test_ait_test_entrypoint.sh` are this task's; the config enum, `policy` verb, `cadence.go`, readiness lines and the supported-modes probe moved to aitasks_go#t77_5.
- **Wave:** G (with M8.5), and after aitasks_go#t77_5.

The **`module` completion-policy mode** (user priority 1b) is
`completion.mode: full|selected|module|auto`, with no `completion.widen`. The
engine half, aitasks_go#t77_5 in beyondeye/aitasks_go, owns the decision order
(readiness, approval, demotion, cadence, `widen_full:<reason>`,
`module|next_full_in:<n>`) and the supported-modes probe. This task makes the
`ait test` completion run **execute** the engine's decision under `module`.

**Automation-first:** no human step.

**What it adds:**
- The `module` arm of the `POLICY` hook in `.aitask-scripts/aitask_test.sh` (M5.1 / M8.4):
  - on `POLICY:module|…|next_full_in:<n>` (decision-order step 5), run engine `test --widen-modules`;
  - on every full outcome the engine announces (`POLICY:module|full|…`, `POLICY_DEMOTED:`, `cadence:<trigger>`, `widen_full:<reason>`), run the canonical full-run path, exactly as the existing arms do;
  - no policy logic in the front: the engine decides, the hook executes.
- The `module` matrix in `tests/test_ait_test_entrypoint.sh`, against a fake engine.
- **Conditional:** if aitasks_go#t77_5's Step 0 finds that the `result=` carrier is
  assembled in the hook (per how t1859_4 landed), the `MODE:module|…` text and
  its 200-character check land here as well. aitasks_go#t77_5 sends a note if so.

`mode: module` is written by onboarding only once the engine supports it
(t2131_11), or by the project. This task never writes it.

## Dependency hold

`Postponed` until all of these hold:

- **aitasks_go#t77_5** (the engine `module` arm) is Done. This task holds it as
  `xdeps` (`xdeprepo: aitasks_go`), which unblocks only when the target is
  Done.
- `depends: [t2131_7, t1859_4, t1859_5]` are Done: t2131_7 (the front's
  `--widen-modules` forwarding, which this arm uses), t1859_4 (M8.4 framework
  half: the `POLICY` hook in `aitask_test.sh`) and t1859_5 (M8.5 framework
  half). Each of those waits on its own engine half in aitasks_go. Keep these
  when wiring; `aitask_update.sh --deps` replaces the list.

## Key Files to Modify (as M8.4 lands them)

- `.aitask-scripts/aitask_test.sh` (M5.1 / M8.4): the `module` arm of the `POLICY` hook, which passes `--widen-modules` to `test`.
- `tests/test_ait_test_entrypoint.sh`: the `module` matrix.

## Reference Files for Patterns

- Proposal *Completion policy* (~1940-1960, ~3847-3879) and *Auto completion policy and cadence* (~3882-3920), as amended by t2131_1.
- The landed `full|selected|auto` arms of the `POLICY` hook (t1859_4, t1859_5).

## Implementation Plan

1. **Step 0 — Reality check.** Read these as landed:
   - M8.4's `POLICY` hook and its existing arms;
   - where the `result=` carrier is assembled (hook or engine; see aitasks_go#t77_5);
   - the lines aitasks_go#t77_5's engine emits under `module`.

   **Stop if t1859_4, t1859_5, t2131_7 or aitasks_go#t77_5 have not landed.**
2. Add the `module` arm in the `POLICY` hook.
3. The fake-engine matrix tests.

## Verification Steps

- **Fake-engine `module` matrix:**
  - `POLICY:module|…|next_full_in:<n>` → `test --widen-modules`;
  - `POLICY:module|full|…`, `POLICY_DEMOTED:`, `cadence:<trigger>` and `widen_full:<reason>` → the canonical full path (counters are the engine's);
  - `engine_absent` (the front-side case);
  - empty selection (the hook follows the engine's outcome).
- If the hook assembles `result=`: `result=` is at most 200 characters.
- The existing `full|selected|auto` arms are unchanged.

## Carried obligations (framework half)

- Default 11 / step 4 "A reach fallback → full, with `widen_full:<reason>`, run through the canonical full-run path" — the hook runs the canonical full path on `widen_full:<reason>` (*What it adds*; matrix).
- Default 11 / step 5 "`module|next_full_in:<n>`" — the hook runs `test --widen-modules` (*What it adds*; matrix first row).
- Default 11 / Approval and output: human `approved_by` optional; `result=` `MODE:module|…` ≤ 200 chars; `POLICY:module|…` — engine-side in aitasks_go#t77_5; lands here only if the carrier is assembled in the hook (*What it adds*, conditional).
- Default 11 / "Who enables it … written by onboarding only once the engine supports it (t2131_11)" — stated in *What it adds*; the write is t2131_11's.
- Dependency hold / depends `t2131_7` — `depends` t2131_7 (the front's `--widen-modules` forward); the engine flag is aitasks_go#t77_4, reached through aitasks_go#t77_5.
- Dependency hold / `t1859_4` "the `POLICY` hook in `aitask_test.sh`, the `policy` verb, the `result=` carrier" — `depends` t1859_4 for the hook; the verb and carrier are aitasks_go#t65_1, reached through aitasks_go#t77_5.
- Key Files / `registry/config.go` enum → E; `feedback/policy/`, `feedback/cadence.go` → E; `aitask_test.sh` POLICY hook → F; `tests/test_ait_test_entrypoint.sh` `module` matrix → F — *Key Files* (the hook and the matrix); the engine files moved to aitasks_go#t77_5.
- Plan Step 0 (M8.4 hook / carrier / readiness; M8.5 cadence; config enum) — *Implementation Plan* step 1 (the hook and carrier location); the rest moved to aitasks_go#t77_5.
- Plan Step 0 "Stop if t1859_4, t1859_5 or M4.4 have not landed" — this half stops on t1859_4, t1859_5, t2131_7 and aitasks_go#t77_5 (which itself waits on M4.4).
- Plan step 2 config enum → E; step 3 "the `module` arm in the `policy` verb, `cadence.go` and the bash front" → both; step 4 readiness lines → E; step 5 matrix tests → both — the bash-front arm is step 2 here and the fake-engine matrix is step 3; the enum, verb, `cadence.go` and readiness moved to aitasks_go#t77_5.
- Verification / matrix: not approved + NOT_YET → E; … `widen_full:<reason>` canonical full run, counters reset → both; … `engine_absent` → F; empty selection → both — *Verification*: the fake-engine `widen_full`, `engine_absent` and empty-selection rows.
- Verification / "`result=` is at most 200 characters" — only if the hook assembles the carrier (*Verification*, conditional row).

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t77_5 and is quoted for reference only.

> - `completion.mode` enum gains `module` (no new key, no `completion.widen`); `cadence_declared` required for `module`; the `module` decision order (not approved → NOT_YET/ADMISSIBLE engine approval `approved_by: engine:readiness@<run>` with `mode: module`; approved → demote on unmet criterion clearing `approved_by`; cadence triggers incl. `selection_ratio_above` on the widened estimate; `widen_full:<reason>`; else `module|next_full_in:<n>`), reusing M8.5's `cadence.go` and `policy` verb.
> - Readiness under `module` judges widened sets; counters reset/increment; `result=` `MODE:module|…` within 200 chars; `POLICY:module|…|next_full_in:<n>`; `auto` never lands on `module`.
> - The supported-modes capability probe (config validation or a `policy` capability line) that t2131_11 calls, if the landed engine has none.
> - Acceptance checks:
>   - the engine side of the `module` matrix (each admission branch, each cadence trigger, counters, `cadence_declared` unmet, per-criterion demotion, `widen_full`, `mode: auto` approval not admitting `module`, empty selection);
>   - `result=` ≤ 200 chars; readiness `POLICY:module|…`;
>   - cadence code is M8.5's, not a copy (grep);
>   - a probe reports `module` as supported;
>   - `ait engine test` green.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:24:13Z.86e79f709e49527a3c984fbb from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:13Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:33Z.c25f4cb23d535b9e846aaf1c from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:33Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t77_5. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
> | It now waits on aitasks_go#t77_5 through xdeps, which
> | unblocks only when that task is Done.

> **✉ note:t22_4** id=2026-10-30T10:16:52Z.8fcb476eb9f87b3b56c0f1cb from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:16:52Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task was split: its engine part is aitasks_go#t77_5; this task
> |   keeps the framework part (body trimmed, see "Relocated to aitasks_go").

> **✉ note:t77_5** id=2026-11-27T08:29:03Z.62ebf5809255148db1563267 from=aitasks_go#t77_5 from_verified=yes at=2026-11-27T08:29:03Z base=7516a41b4b09216a75454e215f620cb90cc4fc3f base_branch=main dirty=yes host=omg16
>
> | Advisory from aitasks_go#t77_5 (engine half of the `module` completion mode). It landed in aitasks_go commit c41db71 on main, not pushed as of this moment. Verify against goengines/README.md (`policy decide` / `policy record` / `policy modes` rows) and goengines/internal/testmap/feedback/policy/policy.go.
> | 
> | Carrier: the engine assembles no gate result carrier. `result=`, its `MODE:module|…` text and the <=200-character check are therefore the hook's (this task's), as t77_5's own rule says.
> | 
> | What `policy decide` emits under `completion.mode: module`. It is the auto arm (same ledger, CAS, confirmation), running the module widening. The hook picks its path from POLICY field 3 alone:
> | - `POLICY_FLIPPED:module->module|engine:readiness@<run>` (gate form wrote the flip), then the cadence step.
> | - `POLICY_DEMOTED:module->full|<criterion>` (+ `POLICY_WRITE:aitestmap/costs/policy.yaml`), approval cleared.
> | - `POLICY:module|module|next_full_in:<n>` → run `test --changes - --widen-modules --task <t> --run <id>`.
> | - `POLICY:module|full|<reason>[|<detail>]` → the canonical full path (`test --all --run full-<id>`, no --task), for each of:
> |   - `not_yet:<criterion>`
> |   - `cadence:<tasks|days|selection_ratio>|<detail>`
> |   - `widen_full:<reason>` (the widening's WIDEN_FULL fallback; no detail field)
> |   - `superseded` (also a stale demotion that would clear another mode's live approval)
> | 
> | Precedence: tasks, then days, then the widening (computed lazily, at most once, only with --changes). A fallback → widen_full, with the ratio not judged; otherwise the ratio is judged on the widened estimate. A due tasks/days trigger therefore wins over a would-be fallback. Without --changes (readiness's POLICY line) neither the widening nor the ratio is judged.
> | 
> | Record: a module run records as `POLICY_RECORDED:selected|…`; the kind names the counter, not the mode. `test --widen-modules` can still self-promote (`RUN_PROMOTED:<id>|full-<id>|widen_full`) if the tree moved between decide and run. Pass the effective id to `policy record`, which then records a full-run reset.
> | 
> | Empty selection: the engine still decides `module|next_full_in:<n>` (estimate 0) when tasks/days are not due and the host class has a positive full-suite p95. `test --widen-modules` then exits 2 with `RESULT:skip|0|0|0|0` and no RUN: line. `on_empty_selection` stays yours.
> | 
> | Config boundary:
> | - An out-of-range schedule (negative tasks/days, ratio outside [0,1]) is exit 3 `REGISTRY_INVALID` for every verb, the full run included. It is not a policy outcome.
> | - Under module an omitted, null or partial `full_run_every` is `cadence_declared|unmet|missing:<key>` → full.
