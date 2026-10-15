---
Task: t2002_kotlin_escaped_import_swallows_declaration.md
Base branch: main
Output branch: main
---

# t2002 — Escaped `import` / `package` must not open a Kotlin directive

## Context

t1997 added `ktok.esc` (set only for backticked identifiers, `kotlinlex.go:79`
and `:245`) and made the **declaration** gate in `scanKotlin` escape-aware.
The other keyword-text gates in the same loop
(`goengines/internal/testmap/deps/kotlin.go`) still read a backticked name as
the keyword. Worst case: the `import` case runs `chainAt` and skips past
the tokens it consumed, so `` val x = `import` `` followed by `fun f() = 1`
records the phantom import `fun` and **loses `fun:f`** from `Decls`,
`Facts(path).Symbols` and the resolution index (`buildKtIndex`). Downstream,
`frombody.go`'s `resolveSimple` reads the same `Imports`.

Overlay probe on the current tree (HEAD `159437cd1`). The rows marked * change
with the fix below; every control row is identical before and after:

| source | before | after |
|---|---|---|
| *`` val x = `import` `` / `fun f() = 1` | decls `[val:x]` imports `[fun]` | `[val:x fun:f]`, `[]` |
| *`import a.b.C` / `` val x = `import` `` / `object O` | `[val:x]`, `[a.b.C object]` | `[val:x object:O]`, `[a.b.C]` |
| *`` val p = `import` to 1 `` / `class K` | imports `[to]` | `[]` |
| *`` @file:Ann(`package` to 1) `` / `package com.x` | **pkg `to`** | pkg `com.x` |
| *`` @file:Ann(`import` to 1) `` / `package com.x` | imports `[to]` | `[]` |
| *`` val x = `inline` `` / `fun f() = 1` | opaque `[inline-fun]` | `[]` |
| *`val a = inline` / `` `fun`() `` (in a body) | `[inline-fun]` | `[]` |
| *`val a = inline` / `` `suspend` `` / `fun h()` (in a body) | `[inline-fun]` | `[]` |
| *`` val x = `const` `` / `val y = 1` | `[const-val]` | `[]` |
| *`val a = const` / `` `val`() `` (in a body) | `[const-val]` | `[]` |
| *`` val y = `typealias` `` / `Wire = javax.inject.Inject` / `@Wire class C` | `[di]` | `[]` |
| real directives, `` import a.b.`import` ``, `` package `import`.b `` | unchanged | unchanged |
| `public inline suspend fun`, `const val`, `typealias Wire = …Inject` + `@Wire` | opaque kept | kept |
| `` `Class`.forName("a") `` | `[reflection]` | `[reflection]` |

**Per-check decision** (the task asks for one per opaque check):
- **Keyword** gates (`package`, `import`, `inline` and its modifier/`fun` walk,
  `const` + `val`, `typealias`) require `!esc`: in Kotlin a backticked token is
  always an identifier. It is never a modifier, so `` `inline` `` / `` `const` ``
  can never make an inline function or a const val. Dropping these over-marks
  loses no real construct.
- **Identifier** matches (`Class.forName`, `getIdentifier`, `R.string|plurals.x`)
  stay escape-neutral: `` `Class` `` and `Class` name the same identifier.
- `::class.java`: unchanged. `` x::`class` `` is still a callable reference
  (reflection), so the over-mark stays fail-closed.

## Implementation

### 1. `goengines/internal/testmap/deps/kotlin.go` — `scanKotlin`

- L123: `case t.text == "package" && !t.esc && !seenDecl && …`
- L128: `case t.text == "import" && !t.esc && depth == 0 && !prevDot:`
- L149: `case t.text == "inline" && !t.esc:` and the walk condition at L150 becomes
  `… && toks[j].kind == 'n' && !toks[j].esc; j++ {`. An escaped `fun` is not
  the keyword, and an escaped modifier is not a modifier, so either one ends the walk.
- L159: `case t.text == "const" && !t.esc && i+1 < len(toks) && toks[i+1].text == "val" && !toks[i+1].esc:`
- L188: `if t.text == "typealias" && !t.esc && !prevDot && …`
- Add one comment above the `switch` saying that keyword cases require `!t.esc`
  and identifier matches are escape-neutral. Match the existing comment density.

### 2. `goengines/internal/testmap/deps/kotlin_test.go`

Follow the shape of `TestKotlinFunInterfaceDeclaredOnce`. Every row compares
exactly, using `slices.Equal`:

- `TestKotlinEscapedKeywordsAreIdentifiers` is a table with
  `{src, pkg, decls, imports(paths), opaque}`, one row per starred line above.
  It also has controls:
  - real `package` / `import` / `import a.b.*` / `import a.b.D as E` → pkg
    `com.x`, imports `[a.b.C a.b a.b.D]`;
  - `` import a.b.`import` `` → `[a.b.import]`;
  - `` package `import`.b `` → pkg `import.b`;
  - `public inline suspend fun f()` → `[inline-fun]`;
  - `const val y` → `[const-val]`;
  - `typealias Wire = javax.inject.Inject` + `@Wire class C` → `[di]`;
  - `` `Class`.forName("a") `` → `[reflection]`.

  Each `!esc` condition has at least one row that fails without it.
- `TestKotlinEscapedImportKeepsDeclaration` is an end-to-end test in the style of
  `TestKotlinDelegatedPropertyImport`:
  - `src/b/Lib.kt` contains ``package com.x.b`` / `` val tag = `import` `` / `fun helper() = 1`.
  - `src/c/User.kt` imports `com.x.b.helper`.
  - Assert Lib symbols are exactly `[val:tag fun:helper]`.
  - Assert `requireEdge(User → Lib, Import, "import")`.
  - Assert `com.x.b.helper` is not in `User.Unresolved`.

  Before the fix, `helper` is lost, so the edge is a closure-only package fallback.

### 3. `goengines/internal/testmap/deps/cache.go`

`schemaVersion` 10 → 11 (an extraction rule changed). At commit time,
re-check `git show HEAD:goengines/internal/testmap/deps/cache.go`. If a
concurrent commit already bumped it, use HEAD + 1.

## Verification

1. `cd goengines && go test -count=1 ./internal/testmap/deps/`: all pass.
2. **Red proof:** run the new tests against the pre-fix `kotlin.go` through a
   `go test -overlay` from the scratchpad, never by editing the tree. Both new
   tests must fail on the starred rows and the E2E edge.
3. **Mutants:** for each of the 7 added `!esc` conditions, an overlay copy of
   `kotlin.go` with only that condition removed must make
   `TestKotlinEscapedKeywordsAreIdentifiers` fail.
4. `./ait engine test` (go vet + go test over `goengines/`).

## Out of scope (candidate follow-up at Step 8b)

There is a pre-existing **fail-open** gap, and it is not escape-related.
`inline @JvmSynthetic fun f()` and `const @Ann val y` are **not** marked
opaque. The modifier walk stops at `@` (kind `o`), while
`@JvmSynthetic inline fun` is marked. Annotations can sit between modifiers in
valid Kotlin (`modifiers: (annotation | modifier)+`). Offer it as an
`upstream_defect` follow-up; do not fix it here.

## Step 9

Post-implementation: commit the code (`bug: … (t2002)`), then archive via
`aitask_archive.sh` per task-workflow Step 9. Current-branch mode, so there is
no merge.

## Risk

### Code-health risk: low
- Removing escaped-token opaque over-marks narrows a fail-closed path. A real
  `inline fun` / `const val` would be missed only if `esc` were ever set on a
  non-backticked token, and it is set at exactly two backtick sites
  (`kotlinlex.go`). · severity: low · → mitigation: none (pinned in-plan by the
  real-`inline`/`const`/`typealias` control rows and the per-condition mutants)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned. In `scanKotlin` (`goengines/internal/testmap/deps/kotlin.go`), the `package` / `import` / `inline` / `const` / `typealias` keyword gates now require `!t.esc`. The `inline` modifier walk also stops at an escaped token (`!toks[j].esc`), and `const` requires an unescaped following `val`. One comment above the `switch` records the rule: keywords are escape-aware, identifier matches are escape-neutral. `cache.go` `schemaVersion` 10 → 11; at commit time HEAD was still 10, since no concurrent `goengines/` commit landed after `159437cd1`. `kotlin_test.go` has two new tests. `TestKotlinEscapedKeywordsAreIdentifiers` has 11 defect rows and 7 controls, each comparing package/decls/imports/opaque exactly. `TestKotlinEscapedImportKeepsDeclaration` is the end-to-end test: symbols, the `static:import` edge, and no unresolved import.
- **Deviations from plan:** None.
- **Issues encountered:** None. Verification as planned:
  - `go test ./internal/testmap/deps/` and `./ait engine test` both green.
  - Red proof: overlaying HEAD's `kotlin.go`, every one of the 11 defect rows fails, and so does every assertion of the end-to-end test. All 7 controls pass on HEAD.
  - Mutants: an overlay with any single `!esc` condition removed fails exactly its own row(s).
- **Key decisions:**
  - Each opaque check was decided separately. Keyword gates (`inline`, `const`, `typealias`, and the `fun` / modifier walk) ignore escaped tokens, because a backticked token is never a Kotlin keyword or modifier. Identifier matches (`Class.forName`, `getIdentifier`, `R.string|plurals`) stay escape-neutral.
  - `::class.java` is unchanged: `` x::`class` `` is still a callable reference, so the over-mark stays fail-closed.
  - The realistic `package` failure is a file annotation, `` @file:Ann(`package` to 1) ``. It previously set the file's package to `to` and made the real `package` directive be ignored.
- **Upstream defects identified:**
  - `goengines/internal/testmap/deps/kotlin.go:153-163` — the `inline` / `const` opaque checks fail OPEN when an annotation sits between modifiers. The modifier walk stops at `@` (kind `o`), and `const` only looks at the very next token. So `inline @JvmSynthetic fun f()` and `const @Ann val y` are never marked `inline-fun` / `const-val`, while `@JvmSynthetic inline fun` is. This is valid Kotlin (`modifiers: (annotation | modifier)+`). It was measured by overlay probe and is present on HEAD independently of this task (unescaped tokens).
