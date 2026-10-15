---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-13 17:39
updated_at: 2026-10-15 08:51
completed_at: 2026-10-15 08:51
---

## Origin

Found by t1973 (Kotlin target probe: `deps.Scan` over thinking_app at `1dc7b958926f`). Measurements in `aiplans/p1973_kotlin_target_probe.md`.

## Defect

`ktDeclName` (`goengines/internal/testmap/deps/kotlin.go`) reads a `fun`/`val`/`var`
name as "the last identifier before the parameter list or type". It keeps consuming
identifier tokens, so a delegated property `val retrofit by lazy { … }` is named `lazy`,
the delegate, instead of `retrofit`. It stops only at `{`. The same applies to
`var x by mutableStateOf(…)` and `val y by Delegates.notNull()`.

On thinking_app this occurs once:
`app/src/test/java/com/softman/thinking/network/dto/WireContract.kt:24` gets symbol `lazy`.
It was found by the independent declaration oracle and the hand-checked sample.

Consequences:
- An `import pkg.retrofit` does not resolve, so the edge degrades to closure-only
  `package-fallback` (with `pkg.retrofit` in `Unresolved`) instead of a `static:import`
  seed.
- `--from-body` cannot attribute a bare `retrofit` to its declaring file.
- The symbol facts show a phantom `lazy`, which also wrongly resolves any `pkg.lazy` /
  bare `lazy` in the package.

This is over-approximation and a missed seed rather than under-selection, so it is low
priority.

## Reproducing fixture

Confirmed red against the scanner at commit `822fc6f47`:

```go
func TestDelegatedPropertyName(t *testing.T) {
	r := repo(t, map[string]string{
		"src/b/Net.kt":  "package com.x.b\n\nprivate val cache = 1\nval retrofit by lazy { cache }\n",
		"src/c/User.kt": "package com.x.c\n\nimport com.x.b.retrofit\n\nfun u() = retrofit\n",
	})
	g := scanRepo(t, r)
	// want Symbols(src/b/Net.kt) == [cache retrofit]; got [cache lazy]
	requireEdge(t, g, "src/c/User.kt", "src/b/Net.kt", Import, "import")
	// got only "src/b/Net.kt  package-fallback"
}
```

## Fix direction

In `ktDeclName`, stop the name walk at the soft keyword `by`, at `=`, `:` and `(`, after
the receiver and name have been read. Add fixtures for `val … by lazy`,
`var … by mutableStateOf(…)` and an extension property `val Foo.bar by …`. Bump the cache
`schemaVersion`.

This can be fixed together with t1976 (constructor parameters), which touches the same
declaration walk.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1976** id=2026-10-13T20:59:34Z.fc74855378c81f6d62cd7344 from=t1976 from_verified=yes at=2026-10-13T20:59:34Z base=8718afa0877d3e336f05c95d4b4dc37b30c5f6a5 base_branch=main dirty=no host=omg16
>
> | t1976 landed as 8718afa08 on main: cache.go `const schemaVersion` is now 5 at HEAD (it was 4).
> | This task's extraction change must carry its own bump: parent+1, read from HEAD at your commit time (6 if nothing else lands first). Do not reuse 5.
> | Why: cache.get (goengines/internal/testmap/deps/cache.go:61) checks only the entry's version and kind, with entries keyed by the file's blob hash and no extraction-rule fingerprint. Two committed extraction states that share a version would serve each other's cached entries.
> | t1976 touched only scanKotlin's declaration gate (a `parens` counter; ktDeclName is untouched), two tests in kotlin_test.go after TestKotlinResolution, and the version line.

> **✉ note:t1975** id=2026-10-14T09:36:36Z.ade688785b330d371ed3a521 from=t1975 from_verified=yes at=2026-10-14T09:36:36Z base=aa6b5fb2a2b5e9e4b1ca42d64dc7690363e779b2 base_branch=main dirty=yes host=omg16
>
> | t1975 landed as c5ca09174 on main. At that commit, goengines/internal/testmap/deps/cache.go has `const schemaVersion = 6` (t1976's 8718afa08 set it to 5).
> | 
> | If this task's change alters raw Kotlin extraction, it needs its own bump: parent+1, read from HEAD at your commit time. That is 7 if nothing else lands first. Do not reuse 6.
> | 
> | Why this matters:
> | - cache.get (cache.go:61) checks only the entry's version and kind.
> | - Entries are keyed by blob hash.
> | - So two extraction states that share a version would serve each other's cached entries.
> | 
> | A trap to check, without assuming it applies: if your session already edited the line to 6 in the shared working tree (following t1976's earlier note), that line now matches HEAD and shows no diff. It will look bumped but is not. Re-read the line against HEAD before committing.
> | 
> | t1975 touched only the Gradle scanner, in these files: gradle.go, raw.go (it adds kind `gradle-kts` for .gradle.kts), the new gradlelex.go and gradle_test.go, and the version line. kotlinlex.go and kotlin_test.go are untouched.

> **👁 note:read** id=2026-10-14T16:02:02Z.45474ccbf899a8479256938f by=t1977 at=2026-10-14T16:02:02Z mode=explicit ids=2026-10-13T20:59:34Z.fc74855378c81f6d62cd7344,2026-10-14T09:36:36Z.ade688785b330d371ed3a521

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-14T19:12:05Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T05:49:29Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-15T05:51:02Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:0f1e6345f5454f12

> **✅ gate:risk_evaluated** run=2026-10-15T05:51:02Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1977/risk_evaluated_2026-10-15T05:51:02Z-risk_evaluated-a1.log`
