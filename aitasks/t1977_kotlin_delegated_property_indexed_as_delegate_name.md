---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-13 17:39
updated_at: 2026-10-13 17:39
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

This can be fixed together with the constructor-parameter task, which touches the same
declaration walk.
