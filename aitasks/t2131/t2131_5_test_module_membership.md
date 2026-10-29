---
priority: medium
effort: high
depends: [t2131_3]
issue_type: feature
status: Ready
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-24 23:23
---

## Context

Child 5 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 8 and 9.
- **Coarse plan:** `aiplans/p2131/p2131_5_test_module_membership.md`.
- **Wave:** C (M2.7). Depends on t2131_3.
- **Archived providers:** M2.2 (t1853_2, grammar v3), M2.5 (t1853_5, areas) and M2.6 (t1853_6, adoption tables).

This child answers "which tests belong to which module" (test → module membership) and lets areas reference modules. Its consumers:
- the reach/widening library (t2131_6) uses membership to widen;
- onboarding (t2131_9) surfaces the unresolved tests.

**Automation-first:** no human step.

> **Revised 2026-10-24 (user decision): flat code modules, no submodules.** Membership has one kind only (nothing is inherited). The codemap-import change below is **removed**: `areas --import-codemap` stays as landed. The contract is the proposal's component *Code modules*.

**Design defaults (parent plan):**
- **(8) Membership** is computed at load, inside `registry`, and never persisted.
  - **Base membership.** A test belongs to the modules that path containment gives it, **plus** the modules of its covered sources. Covered sources come from `_scanned.yaml` covers and from hand, adopted and seeded edges (the selector walks seeds). Covered-source modules count even when path membership exists, so flat test dirs work: in this repo `tests/` holds tests whose sources live in `.aitask-scripts/`.
  - **Annotation.** `testmap:module <name>…` is a new grammar key, allowed on **any** kind (unlike `area`). It reaches the loader through a new optional `ScannedRow` field, byte-identical when empty (like `axis`; `_scanned.yaml` is `KnownFields(true)`).
    - It replaces **only the path-derived part**; covered-source modules always stay, so the map fails toward running more.
    - An annotation that would drop one is a finding.
  - **Unresolved.** A test with no membership is a `MODULE_UNRESOLVED:` check finding (Info, counted). It is never guessed.
- **(9) Areas reference modules.**
  - An area may list `modules: [<name>…]`. The list expands at load to those modules' **effective** paths. An unknown name, or one absent from the effective table, is `DEAD_SCOPE:<file>|areas|<area>|module:<name>`.
  - **`areas --import-codemap` is unchanged.** It keeps copying `<path>/**` globs and never writes module references, so an imported area's breadth never depends on the modules table or an override. There is no M2.5 deviation.

## Key Files to Modify

- **Grammar:** `goengines/internal/testmap/annot/grammar.go` (`Unit` field 48-65, the `line()` switch 413-533, `File.Annotated()` 80-89, `single()` if needed). Update the `annot/testdata/parse/*` goldens and `conformance_test.go` `confRecords` (485).
- **Bridge to the registry:**
  - `goengines/internal/testmap/registry/inputs.go` `UnitAnnotation` (33-63);
  - `annot/source.go:toRegistry` (141-199);
  - `registry/scan.go` `ScannedRow` (29-36) and its render, plus `SCAN_DRIFT`.
- **Registry side:**
  - `registry/modules.go`: membership and `ModulesOf` (from t2131_3);
  - `registry/rules_modules.go`: `MODULE_UNRESOLVED`, unknown-id and annotation-drop findings;
  - `registry/scoped.go`: area module refs (`areas_import.go` stays as landed).
- **CLI:** `goengines/cmd/ait-testmap/modules.go`, adding `modules --explain <test-id>` (membership with its sources).

## Reference Files for Patterns

- How M2.4 added the `axis` key: `scan.go` comment 25-28 (optional, byte-identical when empty) and `axes/axes.go` post-load validation.
- `registry/scoped.go:669-672` (the unit-kind refusal for `area`, which does **not** apply to `module`) and `validateRow`.
- `registry/areas_import.go` (`ReadCodemap`, `renderAreasAppend`, `AREA_IMPORT:` lines).

## Implementation Plan

1. **Step 0 — Reality check.**
   - Which effective-edge sources exist at load.
   - How unknown `testmap:area` names are treated, mirrored for module ids.
   - That `areas --import-codemap` still writes `<path>/**` globs and needs no change.
2. Grammar key → `UnitAnnotation` → `ScannedRow` field → render and drift.
3. Membership computation and the findings.
4. Area `modules:` references.
5. `modules --explain <test-id>`.

## Verification Steps

`ait engine test` is green, plus:
- parse goldens and `TestParseErrors` cases for `testmap:module`;
- a `ScannedRow` round trip, byte-identical when empty;
- the flat-`tests/` fixture (a test outside the module dir covering a source inside it) gets that membership;
- the annotation replaces only path membership, and an attempted drop is a finding;
- `MODULE_UNRESOLVED:` is counted, not failing;
- an area module ref expands to effective paths, and an unknown or dropped ref is refused;
- the proposal's worked example 3: `tests/test_board.sh`, which covers sources in `board` and `lib`, belongs to both;
- `areas --import-codemap` still writes `<path>/**` globs. With a codemap entry `api` at `services/api/` and a hand module `api` over `services/api/public/**`, the imported area `api` stays `services/api/**`, so `services/api/internal/x.go` still reaches its broad tests.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2131_3** id=2026-10-25T08:10:29Z.5831c2f52b5a1641ab116b4e from=t2131_3 from_verified=yes at=2026-10-25T08:10:29Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_3 (landed in commit eb6baa4c9), for membership:
> | - Path → module: `registry.ModulesOf(reg).OwnerOf(path)` needs no universe and returns "" for unmapped. Two hand modules (or two agent rows) on one path come back as an `*InvalidError` (REGISTRY_INVALID).
> | - Effective table: `ModulesOf(reg).Resolve(files)` with the complete universe from `deps.Universe(ctx, root, cfg)`, never the deps graph's scanned `Files()`.
> | - `modules --explain` currently accepts paths only: a test id fails `registry.CheckPath` and exits 64 (cmd/ait-testmap/modules.go). Widening it to `<path|test-id>` is yours.
> | - `MODULE_CONFLICT` / `MODULES_DRIFT` run in `check` only when a table is declared (a committed `_modules.yaml` or a hand `modules:` block). The same gate may suit `MODULE_UNRESOLVED`.
> | - A hand module declaration accepts `paths` only (any other key is REGISTRY_INVALID).

> **✉ note:t15** id=2026-10-25T08:54:59Z.5b931751bd7ef662fb56f952 from=aitasks_go#t15 at=2026-10-25T08:54:58Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t22_3** id=2026-10-29T22:24:04Z.04cff782982be525eab8b231 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:04Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
