---
priority: medium
effort: high
depends: []
xdeps: [t77_4]
xdeprepo: aitasks_go
issue_type: feature
status: Postponed
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t77_4
in beyondeye/aitasks_go. This body is the framework half.

## Context

Child 7 of t2131 (test-map code-module tier), **framework half**.
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 7 and 10.
- **Coarse plan:** `aiplans/p2131/p2131_7_selector_module_widening.md`. Only its M5.1 bash-front steps are this task's; the selector, record and scoring steps moved to aitasks_go#t77_4.
- **Wave:** D (after M4.4), and after aitasks_go#t77_4.

The on-demand **widening tier** (user priority 1a) is `select --widen-modules`
and `test --widen-modules`, a plain flag with no level. The engine half,
aitasks_go#t77_4 in beyondeye/aitasks_go, implements the flag, the widening stage,
the output lines and the paired prediction record. This task makes the flag
reachable from the public `ait test` command.

**Automation-first:** no human step.

> **Revised 2026-10-24 (user decision): flat code modules, no submodules.** There is one widening behaviour and one spelling, `--widen-modules`, with no level anywhere in the flags, output or records. The contract is the proposal's component *Code modules*.

**What it adds:**
- **The public flag.** M5.1's bash front `aitask_test.sh` parses `ait test --widen-modules` and forwards it unchanged to the engine `test` composite, alone or with `--explain`. This is a named extension of M5.1's flag table. The front adds no widening logic, because a `WIDEN_FULL` outcome is already the composite's `--all` path.
- A fake-engine case in `tests/test_ait_test_entrypoint.sh` that pins the forwarding.

## Dependency hold

`Postponed` until both of these hold:

- **aitasks_go#t77_4** (the engine flag) is Done. This task holds it as `xdeps`
  (`xdeprepo: aitasks_go`), which unblocks only when the target is Done. The
  fake-engine test does not need the real engine, but the forward is only
  useful once the engine accepts the flag.
- **M5.1** (the `ait test` bash front `aitask_test.sh`, its flag parsing and the fake-engine `tests/test_ait_test_entrypoint.sh`), in t1856, has a child id. t1856's coarse pass adds that id to `depends:` and flips this task to `Ready` once nothing is left unresolved.

`depends:` is empty today (the library dependency moved with the engine half).
When wiring, keep the existing deps: `aitask_update.sh --deps` replaces the
list.

## Key Files to Modify (as M5.1 lands them)

- `.aitask-scripts/aitask_test.sh` (M5.1): parse `--widen-modules` and forward it to the engine `test` composite.
- `tests/test_ait_test_entrypoint.sh` (M5.1): the fake-engine invocation check.

## Reference Files for Patterns

- Proposal *Run Surface* steps 7-8 and the output contract (~1665-1693), as amended by t2131_1.
- M5.1's landed flag table in `aitask_test.sh`.

## Implementation Plan

1. **Step 0 — Reality check.** Read M5.1's landed flag parsing in `aitask_test.sh` and the fake engine in `tests/test_ait_test_entrypoint.sh`, and confirm from aitasks_go#t77_4's landed engine that `test` accepts `--widen-modules` alone and with `--explain`.

   **Stop if M5.1 or aitasks_go#t77_4 has not landed.**
2. Add the flag to the front's flag table and forward it unchanged.
3. Tests: the fake-engine cases below.

## Verification Steps

- `ait test --widen-modules`, and `ait test --explain --widen-modules`, reach the fake engine with the flag forwarded unchanged. A control run without the flag forwards none.
- The existing entrypoint tests stay green.

## Carried obligations (framework half)

- What it adds / "The public flag. M5.1's bash front `aitask_test.sh` parses … forwards it unchanged" — *What it adds* and *Implementation Plan* step 2.
- Dependency hold / M5.1 in t1856 "the public `--widen-modules` flag is parsed and forwarded there" — *Dependency hold*: M5.1 in t1856.
- Dependency hold / "Each provider parent's coarse pass adds the ids and flips this task to `Ready`" — this half flips on t1856's M5.1 id and on aitasks_go#t77_4 being Done; the engine half flips on aitasks_go#t61's M4.x ids.
- Implementation Plan / Step 0 M4.1/M4.4/M4.5 reality check — the M4.x part moved to aitasks_go#t77_4; the M5.1 `aitask_test.sh` / fake-engine reality check is *Implementation Plan* step 1 here.
- Implementation Plan / "Stop if M4.1/M4.4/M4.5 or M5.1 have not landed" — this half stops on M5.1 and on aitasks_go#t77_4; the M4.x stop is the engine half's.
- Implementation Plan / steps 2–3 (widening stage, paired record, scoring) — moved to aitasks_go#t77_4; step 4 Tests — the fake-engine cases here (step 3).
- Verification / "`ait test --widen-modules`, and `ait test --explain --widen-modules`, reach the fake engine … control run … forwards none" — *Verification*, first bullet.

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t77_4 and is quoted for reference only.

> - `--widen-modules` on engine `select` / `explain` / `test`; the widening stage after the graded walk (budget-exempt, never `DEFERRED`); reason token `module(<name>) <- <changed path>[ via <reached path>]`; `WIDENED:<modules_n>|<added_n>` line; `WIDEN_FULL:` passthrough; `WIDEN_FULL` under `test` runs the canonical `--all` path.
> - Paired prediction record (plain set + widen outcome + identity digests); `score` per-set false negatives (`WIDEN_SCORED:`, optional `widened {added_n, fn, full?}` row); readiness prediction-set rule; automatic widen recording under `completion.mode: module`; compatibility with records lacking the widened part.
> - Acceptance checks:
>   - exact `select --widen-modules` lines; `SELECTED:` shape unchanged; reasons appear in `explain`;
>   - `test --widen-modules` `WIDEN_FULL` → canonical `--all` (scoring, accounting); `select`/`explain` execute nothing but a task-scoped `select` still writes the record;
>   - readiness under `module` vs `auto` counts a widened catch differently; widened tests never `DEFERRED`;
>   - record carries plain + widen outcome + identity; `score` reports per-set FNs; a non-widened record scores byte-identically; newest-wins keeps the pair;
>   - `ait engine test` green.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:24:10Z.42b3fe7da8488b54a89cb927 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:10Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:31Z.69b198b31da01d990f47b26b from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:31Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t77_4. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
> | It now waits on aitasks_go#t77_4 through xdeps, which
> | unblocks only when that task is Done.

> **✉ note:t22_4** id=2026-10-30T10:16:49Z.e5370b17722e92138c8c95e2 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:16:49Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task was split: its engine part is aitasks_go#t77_4; this task
> |   keeps the framework part (body trimmed, see "Relocated to aitasks_go").
