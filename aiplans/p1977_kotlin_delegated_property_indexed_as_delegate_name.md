---
Task: t1977_kotlin_delegated_property_indexed_as_delegate_name.md
Base branch: main
Output branch: main
---

# t1977 — Name a delegated Kotlin property after itself, not its delegate

## Context

`ktDeclName` (`goengines/internal/testmap/deps/kotlin.go:262`) names a top-level
`fun`/`val`/`var` by walking every following identifier and keeping the **last**
one. It stops only at a token it does not recognise. So `val retrofit by lazy { … }`
walks `retrofit`, then `by`, then `lazy`, and records `lazy`. On thinking_app
(t1973's probe) this hits `app/src/test/java/com/softman/thinking/network/dto/WireContract.kt:24`.
As a result, `import pkg.retrofit` degrades to a closure-only `package-fallback`
edge, `--from-body` cannot attribute a bare `retrofit`, and a phantom `lazy`
symbol resolves `pkg.lazy`.

The same walk mis-names related forms:
- `val y by Delegates.notNull()` → `notNull`, and it is also marked as an
  extension because of the dot.
- `val x get() = 1` (accessor, no type) → `get`.
- `fun List<*>.f()` → `List`: `*` is not in the skip list, so the walk stops on
  the receiver.

State at planning time:
- t1976 (8718afa08) added a `parens` gate in `scanKotlin`, but `ktDeclName` is
  unchanged since t1853_3.
- `schemaVersion` at HEAD is **7**: t1976 set 5, t1975 set 6, t1980 set 7.

## Approach

Replace the "keep the last identifier" loop with the declaration grammar:
optional receiver type, then the name. An identifier continues the receiver only
when a `.` follows it, optionally after type arguments `<…>` and one or more
nullable `?` markers. The old loop skipped `?` repeatedly, and Kotlin's
`nullableType` is `quest+`, so `String??.` must stay a receiver.
Any other identifier is the name and ends the walk. Whatever comes after the name
(`(` `:` `=` `{`, the soft keyword `by`, an accessor's `get`/`set`) is therefore
never read. This is the task's fix direction, "stop … after the receiver and name
have been read", expressed as a structural rule rather than a stop-word list. So
`get`/`set` and the dotted delegate `Delegates.notNull` are covered without
naming them.

### Step 1 — `goengines/internal/testmap/deps/kotlin.go`

1. Add a helper next to `ktDeclName`, shared by the type-parameter prefix and the
   receiver's type arguments:
   ```go
   // skipTypeArgs returns the index after the '>' closing the '<' at toks[j]
   // (len(toks) when it never closes). A function type's '->' does not close.
   func skipTypeArgs(toks []ktok, j int) int {
   	d := 0
   	for ; j < len(toks); j++ {
   		switch {
   		case toks[j].text == "<":
   			d++
   		case toks[j].text == ">" && toks[j-1].text != "-":
   			if d--; d == 0 {
   				return j + 1
   			}
   		}
   	}
   	return j
   }
   ```
   The lexer emits `>>` as two `>` tokens and `->` as `-` `>`
   (`kotlinlex.go`, single-char default branch), so counting single tokens is
   exact.
2. Replace the inline generics loop at the top of `ktDeclName` with
   `if j < len(toks) && toks[j].text == "<" { j = skipTypeArgs(toks, j) }`.
   The result is the same, plus `->` inside a bound.
3. Replace the fun/val/var loop with:
   ```go
   for j < len(toks) && toks[j].kind == 'n' {
   	name, line = toks[j].text, toks[j].line
   	j++
   	if j < len(toks) && toks[j].text == "<" {
   		j = skipTypeArgs(toks, j)
   	}
   	for j < len(toks) && toks[j].text == "?" { // `Foo?.`, and the legal (redundant) `Foo??.`
   		j++
   	}
   	if j >= len(toks) || toks[j].text != "." {
   		break
   	}
   	ext = true
   	j++
   }
   return name, line, ext
   ```
4. Rewrite the doc comment: for fun/val/var the name is the identifier after the
   optional receiver type (`a.B<T>?.`). An identifier continues the receiver only
   when a `.` follows it, so a delegate (`by lazy`), an accessor (`get()`), the
   parameter list, the type and the initializer all end the walk.

Unchanged forms (they must keep their current names). Each is pinned by a test:
- `fun topFun()`, `fun String.ext()` and `typealias` are pinned by the existing
  `TestKotlinResolution` symbol list. `class`/`object`/`interface` take the
  untouched early-return branch.
- `fun <T> T.f()`, `fun Foo?.f()`, `fun String??.f()`, `fun a.b.C.f()` and
  `fun (A).f()` (still `""`, so no declaration) are pinned by the new control
  rows in Step 2, with both name and extension-list assertions.

### Step 2 — `goengines/internal/testmap/deps/kotlin_test.go`

Add after `TestKotlinFromBodyIgnoresCtorParams`, in the existing style (`lines()`,
`scanKotlin(...).Symbols` → `kind:name`):

- `TestKotlinDeclNameStopsAfterName`: a table compares both the `kind:name` list
  and `scanKotlin(...).Kt.Exts`. Every row's source is `package x` plus one
  declaration:

  | row | source | want |
  |---|---|---|
  | lazy | `val retrofit by lazy { cache }` | `val:retrofit`, exts `[]` |
  | mutable-state | `var counter by mutableStateOf(0)` | `var:counter`, exts `[]` |
  | dotted-delegate | `val y by Delegates.notNull<Int>()` | `val:y`, exts `[]` (the old walk gave `notNull`, ext) |
  | ext-delegate | `val Foo.bar by lazy { 1 }` | `val:bar`, exts `[bar]` |
  | accessor | `val isEmpty get() = true` | `val:isEmpty` |
  | star-receiver | `fun List<*>.firstOrBlank() = ""` | `fun:firstOrBlank`, exts `[firstOrBlank]` |
  | nested-args | `fun Map<String, List<Int>>.total() = 0` | `fun:total`, ext |
  | arrow-arg | `fun Box<(Int) -> Unit>.run() = 0` | `fun:run`, ext |
  | nullable-generic | `fun <T> List<T>?.orEmpty2() = 0` | `fun:orEmpty2`, exts `[orEmpty2]` |

  Control rows. These are unchanged forms that the old walk already named
  correctly, so they pass before and after the fix and pin the new walk to the
  old behaviour:

  | row | source | want |
  |---|---|---|
  | typed | `val plain: Int = 1` | `val:plain`, exts `[]` |
  | type-param-receiver | `fun <T> T.also2() = 0` | `fun:also2`, exts `[also2]` |
  | nullable-receiver | `fun Foo?.orDefault() = 0` | `fun:orDefault`, exts `[orDefault]` |
  | double-nullable | `fun String??.f() = 1` | `fun:f`, exts `[f]` (legal `quest+`; a single-`?` walk would give `String`) |
  | qualified-receiver | `fun a.b.C.helper() = 0` | `fun:helper`, exts `[helper]` |
  | paren-receiver | `fun (A).f() = 0` + `val after = 1` | `val:after` only, exts `[]` |

- `TestKotlinDelegatedPropertyImport`: the task's reproducing fixture, end to end:
  - `src/b/Net.kt` is `private val cache = 1` + `val retrofit by lazy { cache }`;
  - `src/c/User.kt` has `import com.x.b.retrofit` + `fun u() = retrofit`;
  - asserts `Symbols(src/b/Net.kt) == [val:cache val:retrofit]`;
  - asserts `requireEdge(t, g, "src/c/User.kt", "src/b/Net.kt", Import, "import")`;
  - asserts that `Unresolved` of `User.kt` does not contain `com.x.b.retrofit`.

**Red first:** write both tests and run them before Step 1. The `lazy`,
`mutable-state`, `dotted-delegate`, `ext-delegate`, `accessor`, `star-receiver`
and `arrow-arg` rows, and the e2e test, must fail against the current walk. Every
control row must **pass** against it, which proves each control pins existing
behaviour. `nested-args` and `nullable-generic` also pass before the fix. They
are there to exercise the new `skipTypeArgs` path, not to prove the defect. Then
apply Step 1, after which everything is green.

### Step 3 — `goengines/internal/testmap/deps/cache.go`

Bump `const schemaVersion` to **HEAD's value + 1**, read at commit time with
`git show HEAD:goengines/internal/testmap/deps/cache.go | grep 'schemaVersion ='`.
That gives 8 if nothing else lands first. Before committing, confirm that
`git diff HEAD -- …/cache.go` shows the bump. A line that already equals HEAD's
value shows no diff (the trap t1975's note warns about). The raw Kotlin
extraction changes, and `cache.get` keys only on blob, kind and version.

## Verification

1. `cd goengines && go test ./internal/testmap/deps/`: the new tests pass, and
   the existing Kotlin, Gradle and ctor tests still pass.
2. `ait engine test` (go vet + go test over all of `goengines/`).
3. **Real-target diff (thinking_app).** This is the regression check for the
   rewritten walk on real code.
   - Snapshot thinking_app HEAD with `git archive <sha> | tar -x` into the
     scratchpad and record the SHA. This scans a committed tree, never the live
     one.
   - Add a temporary, env-gated `deps/probe_t1977_test.go` that walks every
     `*.kt` file, runs `scanKotlin` and prints sorted
     `path\tkind:name:line[:ext]` lines.
   - Capture the baseline **before Step 1** (after the red tests, with the walk
     unchanged), then capture again after Step 1, and `diff` the two.
   - Expected diff: `WireContract.kt:24` `val:lazy` → `val:retrofit`. **Every
     other changed line must be explained** by one of the forms above. An
     unexplained change is a regression to fix before committing.
   - Delete the probe afterwards: `git status --short goengines/` must show only
     the three intended files. Its source and the diff go verbatim into Final
     Implementation Notes.
4. `shellcheck` is not relevant, since no shell changes.

## Step 9 reference

Post-implementation follows task-workflow Step 9: current-branch mode (no
worktree or merge), commit `bug: … (t1977)` naming only the three Go paths (the
shared tree has foreign dirty brainstorm files), then archive the task and plan.

## Risk

### Code-health risk: low
- The rewritten walk could change the name of a declaration form the old walk
  got right. The change is limited to one function plus a helper, and all
  consumers read `Decls`/`Exts`. · severity: low · → mitigation: already in plan.
  - The Step 2 control rows each assert name and extension list, and pass both
    before and after the fix. They cover `<T> T.`, `Foo?.`, `String??.`,
    `a.b.C.` and `(A).`.
  - The existing `TestKotlinResolution` symbol list covers the rest.
  - Verification step 3 (an exhaustive thinking_app before/after diff) covers
    real-code forms beyond the rows.

### Goal-achievement risk: low
None identified. The task's fixture, its three requested fixture forms and the
schemaVersion bump are all covered directly.
