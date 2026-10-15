---
Task: t2012_kotlin_opaque_modifiers_skip_interleaved_annotations.md
Base branch: main
Output branch: main
---

# t2012 — Kotlin `inline` / `const` opaque checks must walk over interleaved annotations

## Context

`scanKotlin` (`goengines/internal/testmap/deps/kotlin.go:153-164`) marks a file
opaque with `inline-fun` / `const-val`, because the compiler copies an inline
function body or a const value into its call sites. Both checks fail OPEN when
an annotation sits inside the modifier list, which Kotlin allows
(`modifiers: (annotation | modifier)+`):

- The `inline` walk continues only over kind-`n` tokens, so it stops at `@`
  (kind `o`). Result: `inline @JvmSynthetic fun f()` is not marked, while
  `@JvmSynthetic inline fun f()` is.
- The `const` check looks only at the very next token. Result: `const @Ann val y`
  is not marked, and neither is `const internal val y`.
- The walk is also bounded at 7 **tokens** (`j < i+8`). Once annotations are
  skipped, a token bound fails open again on any long argument list, such as
  `inline @Suppress("a", "b", "c", "d") fun`.

This was measured by an overlay probe on the t2002 tree and is present on HEAD.
Missing these reasons under-approximates the dependency closure, which is the
unsafe direction for `assumption_kotlin_scanner_fail_closed`.

## Implementation

### 1. `goengines/internal/testmap/deps/kotlin.go`

**a. One shared walk for both checks.** Replace the `inline` case body
(L153-162) and the `const` case (L163-164) with:

```go
case t.text == "inline" && !t.esc && modifiersReach(toks, i, "fun"):
	add("inline-fun")
case t.text == "const" && !t.esc && modifiersReach(toks, i, "val"):
	add("const-val")
```

When a condition is false, the switch falls through to the later cases
(`Class`, `getIdentifier`, `R`). None of them can match the text `inline` or
`const`, so behaviour is unchanged.

**b. New helpers**, placed after `annotationsAt`:

```go
// ktModifierWalk bounds the modifier list modifiersReach reads, in
// modifiers and annotations — not tokens, so a long annotation argument
// list never ends it early.
const ktModifierWalk = 32

// modifiersReach reports whether the modifier list after the modifier
// toks[i] reaches the keyword kw: it walks over unescaped modifiers and
// whole annotations (`modifiers: (annotation | modifier)+`), so
// `inline @JvmName("x") suspend fun` reaches fun. A list that runs past
// ktModifierWalk entries reports true: fail closed.
func modifiersReach(toks []ktok, i int, kw string) bool {
	j := i + 1
	for n := 0; n < ktModifierWalk; n++ {
		if j >= len(toks) {
			return false
		}
		t := toks[j]
		switch {
		case t.kind == 'o' && t.text == "@":
			j = skipAnnotation(toks, j)
		case t.kind != 'n' || t.esc:
			return false
		case t.text == kw:
			return true
		case slices.Contains(ktModifiers, t.text):
			j++
		default:
			return false
		}
	}
	return true
}

// skipAnnotation returns the index after the annotation at the '@'
// toks[i]: an optional use-site target, then a multi-annotation `[…]`, or
// a dotted name with optional type arguments and a balanced `(…)`.
func skipAnnotation(toks []ktok, i int) int {
	j := i + 1
	if j+1 < len(toks) && toks[j].kind == 'n' && toks[j+1].text == ":" && toks[j+1].kind == 'o' {
		j += 2
	}
	if j < len(toks) && toks[j].kind == 'o' && toks[j].text == "[" {
		return skipBalanced(toks, j)
	}
	_, j = chainAt(toks, j)
	if j < len(toks) && toks[j].kind == 'o' && toks[j].text == "<" {
		j = skipTypeArgs(toks, j)
	}
	if j < len(toks) && toks[j].kind == 'o' && toks[j].text == "(" {
		j = skipBalanced(toks, j)
	}
	return j
}

// skipBalanced returns the index after the bracket closing the '(' or '['
// at toks[j] (len(toks) when it never closes). Only operator tokens count:
// a string literal's content is never a bracket.
func skipBalanced(toks []ktok, j int) int { … d over "(" "[" / ")" "]", kind 'o' only … }
```

The use-site-target test is the same one `annotationsAt` uses (L223). Each unit
advances `j` by at least 1, so the walk always terminates.

**c. Tolerances relative to the old code:**
- Everything the old `inline` walk marked is still marked. The same unescaped
  kind-`n` modifiers continue the walk, and the same unescaped `fun` stops it.
  The new bound (32 units) is never smaller than the old one (7 tokens).
- `!esc` stays on the modifiers and on `fun` / `val`. Annotation names stay
  escape-neutral, because `` @`My Ann` `` is a name, not a keyword.
- **Deliberate widening, all in the safe (over-mark) direction:**
  - `const <modifiers> val` is now marked.
  - An identifier `inline` / `const` followed on the next line by an annotated
    declaration over-marks. The lexer has no newlines, and the existing walk
    already over-marks the same way with modifiers.
  - A list that runs past the bound is marked.
- `const` now requires a kind-`n` `val`. A string literal `"val"` is never the
  keyword.

### 2. `goengines/internal/testmap/deps/kotlin_test.go`

Add `TestKotlinAnnotationsBetweenModifiers` directly after
`TestKotlinEscapedKeywordsAreIdentifiers`, with the same table shape:
`{src, decls, opaque}`, each row comparing exactly with `slices.Equal`. Every
source starts with `package x`.

Defect rows. Each fails on HEAD:

| row | source | decls | opaque |
|---|---|---|---|
| inline-annotation | `inline @JvmSynthetic fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| inline-annotation-args | `inline @JvmName("x") fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| inline-annotation-modifier | `public inline @JvmSynthetic suspend fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| inline-dotted-nested-args | `inline @kotlin.Deprecated("x", ReplaceWith("y")) fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| inline-long-args (beats a token bound) | `inline @Suppress("a", "b", "c", "d") fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| inline-paren-in-string | `inline @Ann(")") fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| inline-multi-annotation | `inline @[JvmSynthetic Ann("x")] fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| inline-use-site | `inline @receiver:Ann fun String.f() = 1` | `[fun:f]` | `[inline-fun]` |
| inline-type-args | `inline @Ann<Int>(1) fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| const-annotation | `const @Ann val y = 1` | `[val:y]` | `[const-val]` |
| const-annotation-args | `const @Ann("x") val y = 1` | `[val:y]` | `[const-val]` |
| const-modifier | `const internal val y = 1` | `[val:y]` | `[const-val]` |
| long-list-reaches-fun | `inline ` + (ktModifierWalk−1)×`@A ` + `fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| exhaustion-fails-closed | `inline ` + ktModifierWalk×`@A ` + `class C` | `[class:C]` | `[inline-fun]` |

Control rows. Each gives the same result on HEAD and after the fix:

| row | source | decls | opaque |
|---|---|---|---|
| annotation-first | `@JvmSynthetic inline fun f() = 1` | `[fun:f]` | `[inline-fun]` |
| annotation-first-const | `@Ann const val y = 1` | `[val:y]` | `[const-val]` |
| inline-annotation-class | `inline @Ann class C` | `[class:C]` | `[]` |
| under-bound-not-a-fun | `inline ` + (ktModifierWalk−1)×`@A ` + `class C` | `[class:C]` | `[]` |
| inline-annotation-escaped-fun | `fun g() {` / `val a = inline` / ``@Ann `fun`()`` / `}` | `[fun:g]` | `[]` |
| inline-annotation-escaped-modifier | `fun g() {` / `val a = inline` / ``@Ann `suspend` `` / `fun h() = 1` / `}` | `[fun:g]` | `[]` |
| const-annotation-escaped-val | `fun g() {` / `val a = const` / ``@Ann `val`()`` / `}` | `[fun:g]` | `[]` |

The repeated rows are built with `strings.Repeat`, tied to the constant.

### 3. `goengines/internal/testmap/deps/cache.go`

Bump `schemaVersion` 11 → 12, because an extraction rule changed. At commit
time, re-read `git show HEAD:goengines/internal/testmap/deps/cache.go` and use
HEAD + 1.

`goengines/README.md` states only the bump rule, with no number in it, so it is
not touched. It also carries another session's uncommitted edits.

## Verification

1. `cd goengines && go vet ./internal/testmap/deps/ && go test -count=1 ./internal/testmap/deps/`
   must be green.
2. **Red proof:** build a `go test -overlay` from the scratchpad that maps
   `kotlin.go` to HEAD's version. Never edit the tree for this. Every defect row
   must fail and every control row must pass.
3. **Mutants:** run each as an overlay copy of the fixed `kotlin.go`. Each must
   fail its own row(s):
   - drop the `@` branch
   - put `const` back on the next-token check
   - remove the `kind=='o'` check from `skipBalanced`
   - use a token bound `j < i+8` instead of the unit bound
   - return false on exhaustion
   - drop `!esc` on the `kw` match
   - drop `!esc` on modifiers
   - drop the type-args skip
   - drop the use-site-target skip
   - drop the `[` branch
4. `./ait engine test`. Other sessions have uncommitted changes under
   `goengines/internal/testmap/runner/`. A failure there is checked against
   those files before it is attributed to this change.

## Out of scope (record under "Upstream defects identified" if the probe confirms)

- `annotationsAt` counts the content of string literals as brackets. It matches
  on `toks[k].text` without checking the token kind, so `@[A("]") Inject]` stops
  early and misses `Inject`. The likely result is a `di` fail-open. Confirm it
  by probe during implementation.
- Inline properties (`inline val x get() = …`, `val x inline get() = …`) get no
  opaque reason, although their accessors are inlined the same way an inline
  function's body is. Confirm by probe.

## Step 9

This is current-branch mode, so there is no merge. Commit the code as
`bug: … (t2012)`, then archive with `aitask_archive.sh 2012`. Write the risk
fields at Step 7, after approval: the t2002 slip must not repeat.

## Risk

### Code-health risk: low
- The deliberate widening adds new over-marks: `const <modifier> val`, an
  identifier `inline` / `const` followed by an annotated declaration, and
  exhaustion of the bound. All of them go in the fail-closed direction and are
  contained to two `scanKotlin` cases plus three new helpers in one file.
  · severity: low · → mitigation: none (each one is pinned by its own row, and
  the per-condition mutants are in-plan)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned.
  - In `scanKotlin` (`goengines/internal/testmap/deps/kotlin.go`), the `inline` and `const` cases now share one walk, `modifiersReach(toks, i, kw)`. It walks over unescaped modifiers and over whole annotations, then reaches an unescaped kind-`n` `fun` / `val`. It is bounded by `ktModifierWalk = 32` units (modifiers and annotations, not tokens), and running past the bound reports true, so it fails closed.
  - `skipAnnotation` handles an optional use-site target, then either a `@[…]` multi-annotation, or a dotted name with optional `<…>` type arguments and an optional balanced `(…)`.
  - `skipBalanced` counts only operator tokens, so a string literal's content is never treated as a bracket.
  - `cache.go`: `schemaVersion` 11 → 12. HEAD was still 11 at commit time.
  - `kotlin_test.go`: new `TestKotlinAnnotationsBetweenModifiers`, 14 defect rows and 7 controls. Every row compares symbols and opaque exactly.
- **Deviations from plan:** None.
- **Issues encountered:** None. Verification was run as planned, and all of it was green:
  - `gofmt -l` is clean.
  - `go vet` and `go test ./internal/testmap/deps/` pass, and `./ait engine test` passes for every package.
  - **Red proof:** an overlay with HEAD's `kotlin.go` (plus the `ktModifierWalk` constant, so the test compiles). Exactly the 14 defect rows fail. All 7 controls pass, and so does every row of `TestKotlinEscapedKeywordsAreIdentifiers`.
  - **Mutants:** each of the 10 overlay mutants fails exactly its own rows:
    - drop `@` branch → all 13 annotation rows
    - const next-token → the 3 const rows
    - `skipBalanced` without kind check → `inline-paren-in-string`
    - token bound `j<i+8` → long-args, nested-args, multi, type-args, long-list, exhaustion
    - exhaustion returns false → `exhaustion-fails-closed`
    - kw without `!esc` → both escaped-fun/val controls, plus the t2002 `inline-escaped-fun` / `const-escaped-val`
    - modifier without `!esc` → both escaped-modifier rows
    - drop type-args → `inline-type-args`
    - drop use-site → `inline-use-site`
    - drop `[` branch → `inline-multi-annotation`
- **Key decisions:**
  - The bound counts units, not tokens. With a token bound, any long annotation argument list would fail open again.
  - Exhausting the bound marks the file (fail closed), and the `exhaustion-fails-closed` / `under-bound-not-a-fun` pair pins the boundary.
  - Sharing one walk deliberately widens `const`: `const <modifier> val` is now marked. The new over-marks are an identifier `inline` / `const` followed by an annotated declaration, and exhaustion. Both are in the safe direction.
  - `const` now requires a kind-`n` `val`. A string `"val"` is never the keyword.
- **Upstream defects identified:**
  - `goengines/internal/testmap/deps/kotlin.go:226-241` — `annotationsAt` counts string-literal content as brackets: it switches on `toks[k].text` without checking `kind == 'o'`. As a result, in `@[Foo("]") Inject] class C` the `"]"` string drops the depth, so the `)` that closes `Foo(` is read as the end of the list and `Inject` is never seen, so the file is not marked `di` (fail OPEN). The control `@[Foo("x") Inject] class C` is marked `[di]`. Measured by overlay probe on this tree.
  - `goengines/internal/testmap/deps/kotlin.go:153-154` — inline properties get no opaque reason: neither `inline val x: Int get() = 1` nor `val x: Int inline get() = 1` is marked. Their accessors are inlined into call sites exactly like an inline function's body, which is the rationale for `inline-fun`, so the closure is under-approximated (fail OPEN). The control `inline fun f() = 1` is marked `[inline-fun]`. Measured by overlay probe on this tree.
