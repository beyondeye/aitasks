---
Task: t1997_kotlin_fun_interface_recorded_twice.md
Base branch: main
Output branch: main
---

# t1997 — Record `fun interface X` once in the Kotlin scanner

## Context

`scanKotlin` (`goengines/internal/testmap/deps/kotlin.go`) records every
top-level declaration by matching a declaration keyword at brace/paren depth 0
and calling `ktDeclName`. For `fun interface Listener { … }` the `fun` match
already declares `Listener` — `ktDeclName` skips the `interface` token for
keyword `fun` — but the loop then visits that `interface` token as its own
keyword and declares `Listener` a second time. Measured on HEAD (4940de5dc) via
a `go test -overlay` probe (no tree edits):

```
fun interface Listener { fun on() }          -> [fun:Listener:3 interface:Listener:3]
public fun interface P<T> { fun on(t: T) }   -> [fun:P:3 interface:P:3]
fun⏎interface Q                              -> [fun:Q:4 interface:Q:4]
interface Foo                                -> [interface:Foo:3]
val a = obj.`fun`⏎interface Y                -> [val:a:3 interface:Y:4]
val a = `fun`⏎interface Y                    -> [val:a:3 fun:Y:4 interface:Y:4]
```

Resolution is unaffected (`buildKtIndex` dedups per file), but
`Facts(path).Symbols` — consumed by the review packets — carries a duplicate
entry. `Symbol.Kind` is read by no Kotlin resolution path (only bash.go keys on
Kind, for bash symbols), so keeping `fun:Listener` — the entry listed first
today — as the survivor changes nothing but the duplicate.

### Escaped identifiers are not keywords

`ktLex` emits a backticked identifier as kind `n` with the backticks stripped
(`kotlinlex.go:72-81`), so `` `fun` `` / `` `interface` `` are
indistinguishable from the keywords after lexing. Every partial fix that leaves
the decl gate blind to escapes produces a wrong symbol on some escaped input:

- "previous token is `fun`" (the task's literal suggestion): drops the real
  `interface:Y` after `` obj.`fun` ``.
- skip tied to the consuming `fun` match, no escape awareness: for
  ``val a = `fun` `` + `interface Y` the escaped `fun` passes the gate and
  suppresses the correct `interface:Y`, leaving only the false `fun:Y`.
- escape-aware `fun interface` predicate, gate still blind: the escaped `fun`
  still enters `ktDeclName`, which (no longer skipping) takes the `interface`
  keyword as the function's name — a new phantom `fun:interface` (reproduced by
  review via an overlay: `[val:a fun:interface interface:Y]`).

So the lexer marks escaped identifiers, and the declaration gate refuses them:
an escaped identifier never opens a declaration. That also removes the
pre-existing false `fun:Y` (and any other escaped-keyword phantom such as
``val b = `object` `` + `fun g()` → `object:fun`), which every partial variant
above kept or mutated.

## Implementation

### 1. `goengines/internal/testmap/deps/kotlinlex.go` — mark escaped identifiers

- `ktok` gains `esc bool // a backticked identifier: never a keyword`.
- `emit` switches to a keyed literal (`ktok{kind: kind, text: text, line: line}`)
  — the positional `ktok{kind, text, line}` no longer compiles with the new
  field.
- The backtick case appends `ktok{kind: 'n', text: l.src[l.i+1:j], line: l.line, esc: true}`
  instead of calling `emit`. Kind and text are unchanged, so every existing
  consumer (chainAt, annotationsAt, frombody.go's token walk, the lexer test's
  `kind:text` rendering) sees exactly what it saw before.

`ktok` is never cached (the cache stores `rawFile`), so the field adds no
cache-shape change of its own.

### 2. `goengines/internal/testmap/deps/kotlin.go`

**One definition of the `fun interface` form**, beside `ktDeclName`, used by it
and by the scanner so the skip and the consumption cannot drift:

```go
// isFunInterface reports whether toks[i] is the `fun` of `fun interface X`:
// ktDeclName reads X past the `interface` token, which therefore opens no
// declaration of its own. Backticked `fun` / `interface` are identifiers,
// not the keyword pair.
func isFunInterface(toks []ktok, i int) bool {
	return toks[i].text == "fun" && !toks[i].esc && i+1 < len(toks) &&
		toks[i+1].kind == 'n' && toks[i+1].text == "interface" && !toks[i+1].esc
}
```

In `ktDeclName`, replace
`if kw == "fun" && j < len(toks) && toks[j].text == "interface" { j++ }`
with `if isFunInterface(toks, i) { j++ }`.

**The declaration gate.** In `scanKotlin`, add `funIface := -1` beside the
other loop state (comment: the `interface` token a `fun interface`'s `fun`
already declared), and change the gate to:

```go
// Only an unescaped keyword outside every brace and parenthesis declares
// in the package: `class X(val a: A)` declares X, not a, and a backticked
// `fun` is an identifier. The `interface` of `fun interface X` belongs to
// its `fun`'s declaration, not a second one.
if depth == 0 && parens == 0 && !prevDot && !t.esc && i != funIface && slices.Contains(declKeywordsKt, t.text) {
	if isFunInterface(toks, i) {
		funIface = i + 1
	}
	if name, line, ext := ktDeclName(toks, i); name != "" { … unchanged … }
}
```

`ktDeclName` has no other caller, so after this an escaped token never reaches
declaration parsing. `funIface` is set only inside the gate — exactly when
`ktDeclName` consumed the `interface`. Nothing else in the loop changes (the
`package` / `import` / opaque / typealias-alias / ref-chain branches keep their
current escape-blind behaviour; none of them declares a symbol).

### 3. Tests

`kotlinlex_test.go` — `TestKotlinLexerMarksEscapedIdentifiers`:
``ktLex("`fun` fun `interface` interface")`` → kinds all `n`, texts
`fun fun interface interface`, `esc` `[true false true false]`.

`kotlin_test.go` — `TestKotlinFunInterfaceDeclaredOnce`, same shape as
`TestKotlinDeclNameStopsAfterName` (each `src` prefixed with `package x` via
`lines`, **exact** comparison of `Kind:Name` lists from
`scanKotlin(...).Symbols` for every row, so any unexpected declaration fails):

| row | src | want | pre-fix result |
|---|---|---|---|
| fun-interface | `fun interface Listener { fun on() }` | `[fun:Listener]` | `[fun:Listener interface:Listener]` |
| modified-generic | `public fun interface P<T> { fun on(t: T) }` | `[fun:P]` | `[fun:P interface:P]` |
| split-lines | `fun` / `interface Q` | `[fun:Q]` | `[fun:Q interface:Q]` |
| escaped-fun | ``val a = `fun` `` / `interface Y` | `[val:a interface:Y]` | `[val:a fun:Y interface:Y]` |
| escaped-object | ``val b = `object` `` / `fun g() = 1` | `[val:b fun:g]` | `[val:b object:fun fun:g]` |
| escaped-interface-name | ``fun `interface`() = 1`` | `[fun:interface]` | `[]` |
| control: plain-interface | `interface Foo` | `[interface:Foo]` | same |
| control: fun-then-interface | `fun f() = 1` / `interface I` | `[fun:f interface:I]` | same |
| control: dotted-escaped-fun | ``val a = obj.`fun` `` / `interface Y` | `[val:a interface:Y]` | same |
| control: escaped-val-name | ``val `fun` = 1`` | `[val:fun]` | same |

The "pre-fix result" column is re-measured in the red run (step 1 below), not
assumed. `escaped-val-name` pins that an escaped *name* after a real keyword
is still read as the name.

### 4. `goengines/internal/testmap/deps/cache.go` — cache schema

Raw Kotlin extraction changes, so bump `schemaVersion` to HEAD + 1 (currently
8 → 9). Re-read HEAD's value immediately before committing (other sessions bump
it too) and use HEAD + 1 against that value.

## Verification

1. **Red first:** land the lexer field and both tests before the scanner change;
   `go test -run 'TestKotlinLexerMarksEscapedIdentifiers|TestKotlinFunInterfaceDeclaredOnce' -count=1 ./internal/testmap/deps/`
   (from `goengines/`): the lexer test passes; the decl test fails on exactly
   the six non-control rows with the pre-fix results in the table; every
   control passes.
2. **Mutants** (scratchpad copies of kotlin.go via `go test -overlay` — never
   editing the shared tree); each must fail the named row:
   - naive "previous token is `fun`" rule → `control: dotted-escaped-fun`;
   - gate without `!t.esc` (predicate escape-aware) → `escaped-fun` with
     `[val:a fun:interface interface:Y]`, and `escaped-object`;
   - predicate without the `toks[i+1].esc` check → `escaped-interface-name`
     (`[]`).
3. **Green:** after the fix the new tests pass; then the whole package:
   `go test -count=1 ./internal/testmap/deps/`, `go vet ./internal/testmap/deps/`,
   `gofmt -l internal/testmap/deps/`, and `go build ./...`. (Not `ait engine
   test` over the whole module: another session has uncommitted work in
   `annot/` and `runner/` that is not this task's.)
4. Commit only the five named files (`git commit -- <paths>`).

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no merge; archive the task and plan per
Step 9 after the Step 8 review and commit.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
