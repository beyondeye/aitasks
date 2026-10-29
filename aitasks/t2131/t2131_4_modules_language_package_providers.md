---
priority: medium
effort: medium
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

Child 4 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 5.
- **Coarse plan:** `aiplans/p2131/p2131_4_modules_language_package_providers.md`.
- **Wave:** C (M2.7). Depends on t2131_3 (table, driver and verb).

The dependency graph knows Go and Python packages only during resolution, then **discards** them:
- `goResult` is dropped (`deps/golist.go:80-85`);
- `pyPackage` / `pyModel` are dropped (`deps/python.go:1511-1523,1756-1763`);
- `goRaw.Package` is dropped (`resolve.go:12`).

So `deps.Graph` exposes no package facts. This child exposes those facts and adds the two providers:
- **Go:** every package under a `go.mod` is one module, `go:<dir>`;
- **Python:** every package (a regular package or a namespace portion) is one module, `py:<dir>`.

Revised 2026-10-24 (user decision): code modules are flat, with no submodules. These are **package providers**:
- a package module owns **only that package's own source files** directly in its directory (`*.go` with test files, or `*.py` / `*.pyi`);
- it never owns a subtree, so a subpackage is just another module and no package claims the unrelated files beside it;
- the name writes `/` as `:` and the repository root directory as `.`. A root package is `go:.` / `py:.`. It is legitimate and bounded, because it owns only its own files;
- a package directory whose name contains `:` or another character the name rule refuses is `MODULE_REFUSED:<provider>|<dir>|unnameable`, and its files stay unmapped.

The contract is the proposal's component *Code modules*.

Both rank below hand, agent, codemap and Gradle (default 5). Overlaps are reported as `MODULE_CONFLICT:`.

**Why a separate child:** it carries the immutability and cache-key risk, so it should not block the table work in t2131_3.

**Automation-first:** no human step.

## Key Files to Modify

- `goengines/internal/testmap/deps/graph.go`: new copy-returning accessors (e.g. `GoPackages()`, `PyPackages()`), keeping `Graph` immutable.
- `goengines/internal/testmap/deps/scan.go`, `golist.go`, `python.go` and `resolve.go`: retain the facts on the graph.
- The deps cache: its key must cover every newly retained input (memory `feedback_cache_keys_cover_every_consumed_input`).
- `goengines/internal/testmap/modules/`: the `golang` and `python` providers.

## Reference Files for Patterns

- `deps/graph.go`: `Modules()` returns a sorted copy (119-125).
- `deps/kotlin_test.go:523-604`: the copy-immutability test for `Modules()`.
- `deps/helpers_test.go` (`repo`, `scanRepo`, `requireEdge`) and `internal/testmap/fixture/fixture.go` (real git fixtures).

## Implementation Plan

1. **Step 0 — Reality check.**
   - Read what the cache stores and keys on.
   - Run `deps.Scan` on this repo and on fixtures to see which package facts exist.
   - Confirm that the t2131_3 provider interface is as landed.
2. Retain the Go module and package facts on the graph, plus the Python package and namespace-portion facts, with copy-returning accessors.
3. Extend the cache key. Add a test that changing a package fact changes the key.
4. Add the two providers in `modules`, with precedence and conflicts per t2131_3.

## Verification Steps

`ait engine test` is green, plus:
- a Go module and package fixture;
- Python packages, including a namespace portion;
- accessors return copies;
- the cache key changes when package facts change;
- a Go/Python vs codemap overlap reported as `MODULE_CONFLICT:`;
- the proposal's worked example 6:
  - `go.mod` sits at the root of `example.com/tool`, so `go:.` owns `main.go` and `main_test.go`, `go:tool` owns `tool/*.go`, and `README.md` is unmapped;
  - a change to `tool/parse.go` reached from `main.go` affects {`go:tool`, `go:.`};
  - a change to `README.md` is `WIDEN_FULL:unmapped_path`;
- name safety: `a/b/` gives `go:a:b` and `a.b/` gives `go:a.b` (distinct), while `a:b/` is refused (`MODULE_REFUSED:go|a:b|unnameable`);
- run on this repo's own `deps.Scan`, with the result recorded in the plan.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2131_3** id=2026-10-25T08:10:26Z.6b5f7d74d715c878fee9ed15 from=t2131_3 from_verified=yes at=2026-10-25T08:10:26Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_3 (landed in commit eb6baa4c9): the Go/Python providers plug in without registry changes.
> | - Register with `modules.RegisterProvider(modules.Provider{Name, Rows})` (internal/testmap/modules/modules.go). Rows must pass `registry.ValidateModuleRow`; `modules.Infer` rejects an invalid row.
> | - The registry already implements package-kind ownership: a `go`/`python` row owns only `*.go` / `*.py`+`*.pyi` files directly in `root`; `root: .` is allowed for packages only. Names come from `registry.GeneratedName(provider, root, "")` → `go:<dir>` / `py:<dir>` (`/`→`:`), and roots must pass `registry.ValidRoot` (the directory rule, independent of the name).
> | - Ownership is judged over `Graph.Universe()` (every file, scanned or not), never `Graph.Files()`.
> | - Each row's `deps:` are recomputed by the driver (agent rows included). Providers emit none.

> **✉ note:t15** id=2026-10-25T08:54:56Z.2a7d7897e93788b35bd10d04 from=aitasks_go#t15 at=2026-10-25T08:54:56Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:24:01Z.28562e64de2e7a3d604493b7 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:01Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
