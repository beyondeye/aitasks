---
Task: t2022_kotlin_annotations_at_string_brackets_and_inline_properties.md
Base branch: main
Output branch: main
---

# t2022 — String-literal content read as syntax, and inline properties not marked opaque (Kotlin deps scanner)

## Context

The Kotlin dependency scanner (`goengines/internal/testmap/deps/kotlin.go`) fails
**open** in two reported places (t2012 Step 8b), plus one more instance of the same
mistake found while planning. It was folded in at the user's request (planning
Q&A, "Fold into t2022"):

1. **`annotationsAt`** (kotlin.go:226-241) counts brackets on the raw token text. The
   lexer emits a plain string literal as a kind-`s` token whose text is its content,
   so in `@[Foo("]") Inject] class C` the `"]"` closes the list early, `Inject` is
   never seen, and the file is not marked `di`. `skipBalanced` already counts only
   `kind == 'o'` tokens; `annotationsAt` predates that check.
2. **Inline properties** get no opaque reason. Neither `inline val x: Int get() = 1`
   nor `val x: Int inline get() = 1` is marked, but their accessors are inlined into
   call sites exactly like an `inline fun` body. That inlining is why `inline-fun`
   exists.
3. **Folded sibling, same mistake:** `prevDot` (kotlin.go:121) and the receiver/`?`
   checks in `frombody.go:92,99` compare `toks[i-1].text` without checking the kind.
   A string literal `"."`, `"::"` or `"?"` right before a keyword or name hides it.
   For example, `const val SEP = "."` followed by `class After` drops `After`'s
   declaration. A `typealias Wire = javax.inject.Inject` after such a string is never
   aliased, so `@Wire` loses `di` (fail open). In a `--from-body` unit,
   `val sep = "."` followed by `LoginState(sep)` resolves `LoginState` as an extension
   receiver and drops the ref. `skipTypeArgs` (kotlin.go:395-408) has the same raw-text
   `<`/`>` problem: `fun Box<@Ann(">") Int>.render()` is indexed as `fun:Box`. It gets
   the same one-token fix.

Decisions made with the user:
- Inline properties **reuse `inline-fun`**. An inline accessor is an inline function
  (`get()` / `set()`), so the label stays accurate. The closed `opaqueReasons` list,
  its `testdata/opaque/<reason>/` red-proof fixtures and the reason vocabulary in
  `aidocs/testing_engine/n014_explorer_006_proposal.md` stay unchanged.
- The `prevDot` / frombody / `skipTypeArgs` fix is folded in, so all of this shares a
  single cache `schemaVersion` bump.

## Implementation steps

### 1. `annotationsAt` — brackets only on operator tokens (kotlin.go:225-242)

Guard the bracket `switch` with `toks[k].kind == 'o'`, the same check `skipBalanced` uses:

```go
for k := j; k < len(toks); k++ {
    if toks[k].kind == 'o' {
        switch toks[k].text {
        case "[", "(":
            depth++
        case "]", ")":
            depth--
            if depth == 0 {
                return out
            }
        }
    }
    if depth == 1 && toks[k].kind == 'n' && toks[k-1].text != "." {
```

Extend the doc comment with one sentence: "Only operator tokens count as brackets: a
string literal's content is never one (as in skipBalanced)."

### 2. Inline properties → `inline-fun` (kotlin.go:153, 251-277)

- Make `modifiersReach` variadic: `func modifiersReach(toks []ktok, i int, kws ...string) bool`,
  and change `case t.text == kw:` to `case slices.Contains(kws, t.text):`. The ordering
  stays as it is: an escaped or non-identifier token still returns false before the
  keyword match, so a backticked `` `get` `` or `` `val` `` never counts. Update the doc
  comment to say "reaches one of the keywords kws".
- Line 153: `case t.text == "inline" && !t.esc && modifiersReach(toks, i, "fun", "val", "var", "get", "set"):`
  with a comment. `inline` on a `val`/`var` makes both accessors inline. `inline`
  before `get`/`set` makes that accessor inline. In both cases the accessor body is
  inlined into call sites, as an `inline fun` body is. `inline class` (the old
  value-class syntax) still does not match.
- Line 155 (`const` → `"val"`) is unchanged.
- `opaque.go` header comment: "inline functions and `const val` (inlined into
  callers)" becomes "inline functions and inline property accessors, and `const val`
  (inlined into callers)".

### 3. Token-kind checks for `prevDot`, frombody and `skipTypeArgs`

- kotlin.go:121:
  `prevDot := i > 0 && toks[i-1].kind == 'o' && (toks[i-1].text == "." || toks[i-1].text == "::" || toks[i-1].text == "?")`
  Add a one-line comment saying a string literal's content (`"."`) is not an operator.
- frombody.go:92: `if i > 0 && toks[i-1].kind == 'o' && (toks[i-1].text == "." || toks[i-1].text == "::") {`
- frombody.go:99: `if i > 0 && toks[i-1].kind == 'o' && toks[i-1].text == "?" {`
- kotlin.go:399/401 (`skipTypeArgs`): `case toks[j].kind == 'o' && toks[j].text == "<":` and
  `case toks[j].kind == 'o' && toks[j].text == ">" && !(…existing '-' check…):`.
  Extend the doc comment: "only operator tokens count; a string argument of a type
  annotation is never a bracket".
- The other raw-text look-ahead checks (kotlin.go:105, 111, 135, 157, 161, 184 and
  ktDeclName's `.`/`?`) can only match a string token in invalid Kotlin, so they stay
  as they are.

### 4. Cache schema bump (cache.go:17)

`schemaVersion = 12` → **HEAD + 1**. Re-read cache.go at commit time; it is 13 unless
a concurrent session has bumped it already. Every change above alters cached
`rawFile` facts (Opaque, Decls, Refs).

### 5. Tests — exact equality (kotlin_test.go)

**New `TestKotlinInlineProperties`.** Each row compares `decls` and `opaque` exactly,
in the same shape as `TestKotlinAnnotationsBetweenModifiers`:
- `inline-val`: `inline val x: Int get() = 1` → `[val:x]`, `[inline-fun]`
- `inline-var`: `inline var x: Int` / `    get() = 1` / `    set(v) {}` → `[var:x]`, `[inline-fun]`
- `inline-getter`: `val x: Int inline get() = 1` → `[val:x]`, `[inline-fun]`
- `inline-setter`: `var x: Int` / `    get() = 1` / `    inline set(v) {}` → `[var:x]`, `[inline-fun]`
- `inline-private-setter`: `var x: Int` / `    get() = 1` / `    private inline set(v) {}` → `[var:x]`, `[inline-fun]`
- `inline-ext-val`: `inline val String.size2: Int get() = length` → `[val:size2]`, `[inline-fun]`
- `inline-annotation-val`: `inline @JvmSynthetic val x: Int get() = 1` → `[val:x]`, `[inline-fun]`
- `annotation-inline-getter`: `val x: Int @JvmName("a") inline get() = 1` → `[val:x]`, `[inline-fun]`
- `member-inline-val`: `class C {` / `    inline val x: Int get() = 1` / `}` → `[class:C]`, `[inline-fun]`
- Controls:
  - `plain-getter`: `val x: Int get() = 1` → `[val:x]`, nil
  - `inline-escaped-get`: `fun g() {` / `    val a = inline` / ``    `get`()`` / `}` → `[fun:g]`, nil
  - `inline-escaped-val`: same shape with ``    `val`()`` → `[fun:g]`, nil
  - `inline-dot-get`: `val a = inline.get()` → `[val:a]`, nil
  - `inline-class`: `inline class V(val v: Int)` → `[class:V]`, nil

**New `TestKotlinStringContentIsNotSyntax`.** Every row compares `decls`, the `Refs`
chains and `opaque` exactly:
- annotationsAt:
  - `@[Foo("]") Inject] class C` → `[class:C]`, `[di]`
  - `@[Foo(")") Inject] class C` → `[class:C]`, `[di]`
  - `@[Foo("[") Inject] class C` → `[class:C]`, `[di]`
  - `@[Foo("(") Inject] class C` → `[class:C]`, `[di]`
  - `@[Foo("${"]"}") Inject] class C` (a template's code tokens stay tokens) → `[class:C]`, `[di]`
  - Controls: `@[Foo("x") Inject] class C` → `[di]`; `@[Foo("]") Bar] class C` → nil
- prevDot:
  - `const val SEP = "."` / `class After` → `[val:SEP, class:After]`, `[const-val]`
  - `val s = "::"` / `fun after() = 1` → `[val:s, fun:after]`
  - `val q = "?"` / `object After` → `[val:q, object:After]`
  - `val s = "."` / `typealias Wire = javax.inject.Inject` / `@Wire class C` → `[val:s, typealias:Wire, class:C]`, `[di]`
  - `fun f() {` / `    val s = "."` / `    com.x.util.helper()` / `}` → `[fun:f]`, refs `[com.x.util.helper]`
  - Controls: `val s = "a"` / `class After` → `[val:s, class:After]`; `a.b.c.d()`-style body ref unchanged
- skipTypeArgs: add rows to `TestKotlinDeclNameStopsAfterName`:
  - `fun Box<@Ann(">") Int>.render() = 0` → `[fun:render]`, exts `[render]`
  - `fun Box<@Ann("<") Int>.render() = 0` → same

**New `TestKotlinFromBodyStringBeforeName`.** End-to-end through `FromBody`, in the
same shape as `TestKotlinFromBodyIgnoresCtorParams`, with one sub-case per string:
- `val sep = "."` / `LoginState(sep)` → want `[{src/a/LoginState.kt, LoginState, <line>}]`
- `val q = "?"` / `LoginState(q)` → same
Before the fix the first resolves as an extension receiver (no ref, `no-symbols`) and
the second is skipped.

## Verification

1. `cd goengines && gofmt -l internal/testmap/deps` (empty) and
   `go test ./internal/testmap/deps/ -count=1`; then `./ait engine test` (go vet + go
   test over goengines).
2. **Red proofs via overlay.** Never stash or restore in the shared worktree. Write
   mutant copies of the fixed `kotlin.go` / `frombody.go` into the scratchpad, each
   with exactly one fix reverted, and run
   `go test -overlay <json> ./internal/testmap/deps/ -run 'TestKotlin' -count=1`:
   - annotationsAt reverted: only the annotationsAt string-bracket rows fail; the controls pass.
   - modifiersReach call reverted to `"fun"`: only the inline-property positive rows fail.
   - prevDot reverted: only the prevDot rows fail.
   - skipTypeArgs reverted: only the two type-arg rows fail.
   - frombody reverted: only the `TestKotlinFromBodyStringBeforeName` sub-cases fail.
   Record each mutant's exact failing-row list in Final Implementation Notes.
3. Confirm `TestOpaqueBranchesRedProved` / `TestOpaqueFixturesCoverEveryReason` still
   pass with the reason list unchanged.

## Step 9 reference

After review and commit (Step 8: code commit `bug: … (t2022)` naming only the code
paths; plan commit via `aitask_task_commit.sh`), run Step 9 post-implementation:
gate orchestration (`risk_evaluated`) and archival. Current-branch mode, so there is
nothing to merge.

## Risk

### Code-health risk: low
- Inline-property detection marks more files opaque, and an identifier named `inline` followed by `val`/`var`/`get`/`set` (for example `val a = inline` then `val b = 1`) over-marks. That is the fail-closed direction `inline … fun` already accepts, and `inline` as an identifier is rare · severity: low · → mitigation: none (deliberate over-approximation)
- The `prevDot` / `skipTypeArgs` kind checks change extraction only when a kind-`s` token's content is exactly `.`, `::`, `?`, `<` or `>`. Templated (`S`), char (`S`) and number (`d`) tokens never carry those texts, so no previously correct answer changes. Exact-equality controls pin that · severity: low · → mitigation: none
- The schemaVersion bump causes a one-time cache rescan · severity: low · → mitigation: none

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Implemented as planned, in `goengines/internal/testmap/deps/`:
  - `kotlin.go`: `annotationsAt` counts `[ ( ] )` only on `kind == 'o'` tokens; `modifiersReach` takes variadic `kws` and the `inline` rule reaches `fun`/`val`/`var`/`get`/`set` (reason stays `inline-fun`); `prevDot` requires `kind == 'o'`; `skipTypeArgs` counts `<`/`>` only on operator tokens.
  - `frombody.go:92,99`: the receiver (`.`/`::`) and `?` checks require `kind == 'o'`.
  - `opaque.go`: header comment names inline property accessors. The reason list is unchanged.
  - `cache.go`: `schemaVersion` 12 → 13 (HEAD was still 12 at commit time).
  - `kotlin_test.go`: new `TestKotlinInlineProperties` (9 positive + 5 control rows), `TestKotlinStringContentIsNotSyntax` (10 positive + 4 control rows), `TestKotlinFromBodyStringBeforeName` (`"."`, `"::"`, `"?"` sub-cases), and 2 rows (`string-gt-arg`, `string-lt-arg`) in `TestKotlinDeclNameStopsAfterName`. Every row is compared exactly.
- **Deviations from plan:** None. The planned "`a.b.c.d()`-style body ref unchanged" control was written as `plain-before-ref` (the same body with `"a"` in place of `"."`).
- **Issues encountered:** None. `gofmt -l` is clean; `go test ./internal/testmap/deps/` passes; `./ait engine test` (go vet + go test over goengines) exits 0 with every package `ok`.
- **Key decisions:** Inline properties reuse `inline-fun` (user's choice: an inline accessor is an inline function), so no new fixture and no change to the reason vocabulary. The `prevDot` / frombody / `skipTypeArgs` kind checks were folded in (user's choice) so the one `schemaVersion` bump covers everything. The other raw-text look-ahead checks in kotlin.go (lines 105, 111, 135, 157, 161, 184 and ktDeclName's `.`/`?`) were left alone: only invalid Kotlin can place a string token there.
- **Red proofs (overlay mutants, one fix reverted each; the shared worktree was never touched).** Mutants were generated by a scratch Python script, each a copy of the fixed file with exactly one hunk undone, and run with `go test -overlay <json> ./internal/testmap/deps/ -count=1`. Each mutant failed exactly the rows below, and every control row passed under all five:
  - annotationsAt guard removed → `TestKotlinStringContentIsNotSyntax`: `multi-close-bracket`, `multi-close-paren`, `multi-open-bracket`, `multi-open-paren`, `multi-template-bracket` (opaque `[]`, want `[di]`).
  - `modifiersReach(toks, i, "fun")` restored → `TestKotlinInlineProperties`: all 9 positive rows (`inline-val`, `inline-var`, `inline-getter`, `inline-setter`, `inline-private-setter`, `inline-ext-val`, `inline-annotation-val`, `annotation-inline-getter`, `member-inline-val`), opaque `[]`.
  - `prevDot` kind check removed → `TestKotlinStringContentIsNotSyntax`: `dot-before-class` (`[val:SEP]`), `scope-before-fun` (`[val:s]`), `quest-before-object` (`[val:q]`), `dot-before-typealias` (`[val:s class:C]`, opaque `[]`), `dot-before-ref` (refs `[]`).
  - `skipTypeArgs` kind checks removed → `TestKotlinDeclNameStopsAfterName`: `string-gt-arg`, `string-lt-arg` (`[fun:Box]`, exts `[]`).
  - frombody kind checks removed → `TestKotlinFromBodyStringBeforeName`: `dot`, `scope`, `quest` (refused `no-symbols`).
- **Upstream defects identified:** None

### Red-proof mutant generator (verbatim)

Run as `python3 -I mk.py <deps dir> <scratch dir>`. Then, per mutant, `go test -overlay <scratch>/<name>.json ./internal/testmap/deps/ -count=1` from `goengines/`.

```python
import json, sys
D, S = sys.argv[1], sys.argv[2]
kt = open(f"{D}/kotlin.go").read()
fb = open(f"{D}/frombody.go").read()
def rep(src, old, new, count):
    assert src.count(old) == count, (old, src.count(old))
    return src.replace(old, new)
annot_old = """		if toks[k].kind == 'o' {
			switch toks[k].text {
			case "[", "(":
				depth++
			case "]", ")":
				depth--
				if depth == 0 {
					return out
				}
			}
		}
"""
annot_new = """		switch toks[k].text {
		case "[", "(":
			depth++
		case "]", ")":
			depth--
			if depth == 0 {
				return out
			}
		}
"""
mut = {
  "annot": ("kotlin.go", rep(kt, annot_old, annot_new, 1)),
  "inlineprop": ("kotlin.go", rep(kt, 'modifiersReach(toks, i, "fun", "val", "var", "get", "set")', 'modifiersReach(toks, i, "fun")', 1)),
  "prevdot": ("kotlin.go", rep(kt, "prevDot := i > 0 && toks[i-1].kind == 'o' && (", "prevDot := i > 0 && (", 1)),
  "typeargs": ("kotlin.go", rep(kt, "case toks[j].kind == 'o' && toks[j].text == \"<\":", "case toks[j].text == \"<\":", 1).replace("case toks[j].kind == 'o' && toks[j].text == \">\" &&", "case toks[j].text == \">\" &&")),
  "frombody": ("frombody.go", rep(fb, "toks[i-1].kind == 'o' && ", "", 2)),
}
assert mut["typeargs"][1].count("case toks[j].text == \">\" &&") == 1
for name, (f, src) in mut.items():
    p = f"{S}/{name}_{f}"
    open(p, "w").write(src)
    json.dump({"Replace": {f"{D}/{f}": p}}, open(f"{S}/{name}.json", "w"))
    print(name, p)
```
