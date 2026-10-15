---
priority: medium
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
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 22:52
updated_at: 2026-10-15 23:54
---

## Origin

Spawned from t2002 during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/deps/kotlin.go:153-163`: the `inline` and `const` opaque checks fail OPEN when an annotation sits between modifiers.
  - The `inline` modifier walk only continues over kind-`n` tokens, so it stops at `@` (kind `o`).
  - The `const` check only looks at the very next token.
  - As a result, `inline @JvmSynthetic fun f()` and `const @Ann val y` are never marked `inline-fun` / `const-val`, while `@JvmSynthetic inline fun` is.
  - This is valid Kotlin: the grammar's `modifiers: (annotation | modifier)+` lets annotations interleave with modifiers.
  - Measured by overlay probe on the t2002 tree. It is present on HEAD independently of t2002, because these are unescaped tokens.

## Diagnostic context

t2002 made the keyword gates in `scanKotlin` escape-aware (`!t.esc`), including the `inline` modifier walk and the `const` + `val` check. While probing those checks, an overlay test showed this (opaque reasons listed):

```
package x\ninline @JvmSynthetic fun f() = 1\n   -> decls [fun:f] opaque []            (fail OPEN)
package x\n@JvmSynthetic inline fun f() = 1\n   -> decls [fun:f] opaque [inline-fun]  (correct)
package x\nconst @Ann val y = 1\n               -> decls [val:y] opaque []            (fail OPEN)
```

`inline-fun` and `const-val` are opaque reasons because the compiler copies the body or value into call sites. Missing them under-approximates the dependency closure, which is the unsafe direction for the opaque contract (`assumption_kotlin_scanner_fail_closed`).

## Suggested fix

- In the `inline` walk, skip whole annotations: `@`, an optional use-site target, the dotted name, and an optional balanced `(...)` or `[...]` argument list. Then keep looking for `fun`.
- Apply the same skip between `const` and `val`. Keep the walk bounded, and keep `!esc` on modifiers and on `fun` / `val`.
- Add exact-equality rows to `kotlin_test.go` next to `TestKotlinEscapedKeywordsAreIdentifiers`. Include an annotation with arguments, e.g. `inline @JvmName("x") fun f()`, and controls for the annotation-first order.
- Bump the cache `schemaVersion` to HEAD + 1 at commit time.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T20:54:48Z status=pass attempt=1 type=human
