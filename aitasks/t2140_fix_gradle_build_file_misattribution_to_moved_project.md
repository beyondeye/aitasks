---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-25 10:09
updated_at: 2026-10-25 10:09
---

## Origin
Spawned from t2131_3 during Step 8b review.

## Upstream defect
- `goengines/internal/testmap/deps/gradle.go:209-215` — a build file whose directory maps by `moduleNameOf` onto an existing project name with a different `projectDir` (e.g. `include(":api")` moved to `services/api` plus a stray `api/build.gradle.kts`) is attached to that project as its `BuildFile` through `addModule`'s by-name return; this also feeds `sourceEdges` (the module-build closure edges of every Kotlin / Java source of the project).

## Diagnostic context
In `buildGradle`, the build-file loop looks a build file's directory up in `byDir`; on a miss it calls `addModule(moduleNameOf(d), d)`. `addModule` returns the existing module **by name** when one exists, so a build file in `api/` resolves to the `:api` project even though settings moved `:api` to `services/api/`. If `api/build.gradle.kts` sorts before `services/api/build.gradle.kts` (it does), it becomes `:api`'s `BuildFile` (`if m.BuildFile == ""`), and the project's real build file is never attached. t2131_3's Gradle modules provider guards against it (`build:` evidence only when the build file lies under the project's directory), but the deps graph itself — `GradleModule.BuildFile`, the module-build closure edges and the build-file opacity/dynamic attribution — still carries the wrong file.

## Suggested fix
In the build-file loop, when `byDir[d]` misses, only reuse a by-name module whose `Dir == d`; otherwise create a distinct record (or skip it — it is a build directory no settings file includes, `Declared: false`). Add a regression test in `deps/gradle_test.go` with the moved project plus the stray build file, asserting `:api`'s `BuildFile` is `services/api/build.gradle.kts` and its sources' `module-build` edge targets it.
