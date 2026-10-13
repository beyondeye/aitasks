---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
created_at: 2026-10-13 17:39
updated_at: 2026-10-13 18:44
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
