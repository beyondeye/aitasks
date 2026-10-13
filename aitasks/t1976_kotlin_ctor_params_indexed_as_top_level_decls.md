---
priority: medium
risk_code_health: low
risk_goal_achievement: low
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
implemented_with: claudecode/opus5_5
created_at: 2026-10-13 17:39
updated_at: 2026-10-13 23:31
---

## Origin

Found by t1973 (Kotlin target probe: `deps.Scan` over thinking_app at `1dc7b958926f`). Measurements in `aiplans/p1973_kotlin_target_probe.md`.

## Defect

`scanKotlin` (`goengines/internal/testmap/deps/kotlin.go`) records a declaration whenever
a `class|interface|object|fun|val|var|typealias` keyword appears at brace depth 0. Depth
counts only `{` / `}`, so **primary-constructor `val`/`var` parameters**
(`data class LoginState(val email: String)`, `class X(private val repo: Repo)`,
`enum class E(val label: String)`) are at depth 0 too. They are indexed as top-level
declarations of the file's package.

On thinking_app this affects **697 spurious symbols in 224 of 784 Kotlin files**:
- 626 constructor `val`s and 71 constructor `var`s;
- they include common names such as `email`, `context`, `password`, `inProgress`,
  `mapper` and `analytics`.

An independent oracle, plus a hand-checked sample of 14 files, agreed on every other
declaration.

Consequences:
- **`annotate --from-body` writes wrong covers.** `resolveSimple` resolves a bare name
  against the package's top-level declarations. A member body in the same package that
  says `email` (a local val, a named argument) gets a ref, and so a `testmap:covers`
  stamp, to every file whose constructor has an `email` parameter. `--from-body` writes
  by default.
- **Symbol facts are wrong** for the review packets.
- The import index is polluted (`ix.decls`), so `pkg.someParam` lookups can resolve. This
  is rare, but it is the wrong direction for `Static()` seeds.

## Reproducing fixture

Confirmed red against the scanner at commit `822fc6f47`:

```go
func TestCtorParamsAreNotTopLevel(t *testing.T) {
	r := repo(t, map[string]string{
		"aitestmap/.keep":      "",
		"src/a/LoginState.kt":  "package com.x.a\n\ndata class LoginState(val email: String, var busy: Boolean = false)\n",
		"tests/a/LoginTest.kt": "package com.x.a\n\n// testmap:unit M\nfun m() {\n    val email = \"x\"\n    println(email)\n}\n",
	})
	g := scanRepo(t, r)
	// want Symbols(src/a/LoginState.kt) == [LoginState]; got [LoginState busy email]
	refused, refs, _, _ := FromBody(bg, r.Dir, registry.ID{Path: "tests/a/LoginTest.kt", Member: "M"},
		Options{Config: registry.Defaults(), Uncached: true})
	// want no ref; got [{Source:src/a/LoginState.kt Symbol:email Line:5}]
	_ = refused; _ = refs
}
```

## Fix direction

Track parenthesis (and angle-bracket) nesting alongside brace depth, so that only
declarations at depth 0 *outside* parentheses are top-level. Keep the class name itself
(`class X(` is still a declaration). Add a fixture per form:
- `data class` constructor `val`/`var`;
- `enum class` constructor;
- `class X @Inject constructor(private val …)`;
- a multi-line constructor parameter list.

Bump the cache `schemaVersion`, because the raw Kotlin extraction changes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-13T20:31:02Z status=pass attempt=1 type=human
