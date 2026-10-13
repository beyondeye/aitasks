---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-10-13 15:52
updated_at: 2026-10-13 15:52
---

## Origin

Risk-mitigation ("after") follow-up for t1853_3, created at Step 8d after implementation landed (code commit 2c04a9639).

## Risk addressed

goal-achievement — Kotlin opaque contract / import walk / android-res unmeasured on a real tree

- **Kotlin untested against a real tree.** The Kotlin opaque contract, the import walk and android-res are designed against thinking_app (a sibling repository) but tested only on fixtures. Opaque frequency, `package-fallback` volume and missed constructs are unmeasured. · severity: medium · → mitigation: kotlin_target_probe

## Goal

Run the M2.3 dependency scanner (`deps.Scan` in `goengines/internal/testmap/deps`) over the thinking_app repository and measure it against the proposal's numbers. Resolve thinking_app by its logical project name through `ait projects resolve`, never by a sibling path.

How t1853_3 probed its own repository: a temporary, uncommitted `deps/probe_test.go`, gated on an env var, that calls `Scan(ctx, root, Options{CacheDir: t.TempDir()})` three times (cold, then warm) and logs per-language counts. It was deleted afterwards. Reuse that shape with `root` set to the resolved thinking_app path.

Measure and record:
- **Opaque files:** count per reason (`inline-fun`, `const-val`, `di`, `di-koin`, `reflection`, `untokenizable`, `generated`, `java-unscanned`, `dynamic-resource`, `gradle-dynamic`, …). Compare with the proposal's thinking_app figures: 42 main files declaring `const val` / `inline fun`, 63 carrying DI annotations.
- **Kotlin resolution volume:** `package-fallback` edges and the `Unresolved` list, sampled by hand to find constructs the import walk misses.
- **Gradle module graph:** module count, `gradle-dynamic` build files, and whether `ModuleOf` and the transitive `Deps` match the real project structure.
- **android-res** (with `symbol_scanners: [android-res]`): key counts per file, Java `*` files, and `ChangedKeys` over a real `values*/strings.xml` diff.
- **Timing:** cold and warm scan times against the 200 ms warm `select` budget and the 1.5 s cold budget.
- **`annotate --from-body`:** whether it maps real member blocks, including receiver-position extension calls, and what it misses.

File each defect found as its own task (bug, with a fixture reproducing it). Record the measurements in this task's plan.
