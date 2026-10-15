---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-16 00:04
updated_at: 2026-10-16 00:04
---

## Origin

Spawned from t2012 during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/deps/kotlin.go:226-241` — `annotationsAt` counts string-literal content as brackets: it switches on `toks[k].text` without checking `kind == 'o'`.
  - In `@[Foo("]") Inject] class C`, the `"]"` string lowers the depth, so the `)` that closes `Foo(` is read as the end of the list and `Inject` is never seen.
  - The file is therefore not marked `di` (fail OPEN).
  - Control: `@[Foo("x") Inject] class C` is marked `[di]`.
  - Measured by overlay probe on the t2012 tree.
- `goengines/internal/testmap/deps/kotlin.go:153-154` — inline properties get no opaque reason.
  - Neither `inline val x: Int get() = 1` nor `val x: Int inline get() = 1` is marked.
  - Their accessors are inlined into call sites exactly like an inline function's body, and that is the reason `inline-fun` exists. The dependency closure is under-approximated (fail OPEN).
  - Control: `inline fun f() = 1` is marked `[inline-fun]`.
  - Measured by overlay probe on the t2012 tree.

## Diagnostic context

t2012 made the `inline` / `const` opaque checks walk over interleaved annotations. It added `modifiersReach` / `skipAnnotation` / `skipBalanced` after `annotationsAt` in `kotlin.go`.

`skipBalanced` deliberately counts only operator tokens (`kind == 'o'`), because the lexer emits a plain string literal as a kind-`s` token whose text is the string's content. The row `inline-paren-in-string` in `TestKotlinAnnotationsBetweenModifiers` pins this, and a mutant without the kind check fails it. `annotationsAt` predates that and still switches on the raw text.

The two probes, both run through a `go test -overlay` probe file and exact on this tree:

```
@[Foo("x") Inject] class C         -> opaque [di]
@[Foo("]") Inject] class C         -> opaque []            (fail OPEN)
inline fun f() = 1                 -> opaque [inline-fun]
inline val x: Int get() = 1        -> opaque []            (fail OPEN)
val x: Int inline get() = 1        -> opaque []            (fail OPEN)
```

## Suggested fix

- **`annotationsAt`:** count brackets only on `kind == 'o'` tokens, matching `skipBalanced`. Add a `di` row with a bracket inside a string argument, plus the plain control.
- **Inline properties:** decide whether the closed opaque list should cover them, by the `inline-fun` rationale. If it should, either have the `inline` walk also reach `val` / `var`, or mark an `inline` that precedes `get` / `set` accessors. Possibly use a distinct reason; that is a design choice, because `opaqueReasons` is a closed, ordered list with a red-proof fixture per reason under `testdata/opaque/<reason>/`.
- Add exact-equality rows to `kotlin_test.go`, and bump the cache `schemaVersion` to HEAD + 1 at commit time.
