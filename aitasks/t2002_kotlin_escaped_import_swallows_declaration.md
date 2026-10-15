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
created_at: 2026-10-15 10:06
updated_at: 2026-10-15 22:32
---

## Origin

Spawned from t1997 during Step 8b review.

## Upstream defect

- goengines/internal/testmap/deps/kotlin.go:128 — the escape-blind `import` branch reads a backticked `` `import` `` identifier at depth 0 as an import directive. `` val x = `import` `` followed by `fun f() = 1` yields imports `[fun]` and decls `[val:x]`: the next token is consumed as the import path, so the real `fun f()` declaration is lost. Measured on the t1997 tree via an overlay probe; the control `val x = y` keeps `fun:f`. Fix: add `!t.esc` to the `package` / `import` cases (and to the keyword-text opaque checks), using the `esc` flag t1997 added to the lexer.

## Diagnostic context

t1997 fixed `fun interface X` being recorded twice in `scanKotlin`. The lexer emits a backticked identifier as kind `n` with its backticks stripped, so `` `fun` `` looked exactly like the keyword. t1997 therefore added `ktok.esc` (set for backticked identifiers, `kotlinlex.go`) and an `!t.esc` check on the **declaration** gate only. That removed the escaped-keyword phantom declarations (`fun:Y`, `object:fun`).

The other keyword-text branches in the same `scanKotlin` loop are still blind to escapes. The worst one is `case t.text == "import" && depth == 0 && !prevDot`. It runs `chainAt(toks, i+1)` and then `i = j - 1`, so an escaped `` `import` `` at top level does two things:
- it records a phantom import (`fun` in the probe; any identifier chain in general);
- it **skips** the tokens it consumed. If the next token is a declaration keyword, that declaration is lost from `Decls` / `Facts(path).Symbols` and from the resolution index (`buildKtIndex`).

Probe (overlay test, t1997 tree at `6ed14e3a3`):

```
package x\n\nval x = `import`\nfun f() = 1\n -> decls [val:x] imports [fun]
package x\n\nval x = y\nfun f() = 1\n        -> decls [val:x fun:f] imports []
```

The `package` case has the same shape. It is gated on `!seenDecl && k.Package == ""`, so it only fires before the first declaration. The keyword-text opaque checks (`inline` + `fun`, `const` + `val`) can only over-mark a file opaque, which fails closed. Still, check whether `` `inline` fun `` should count.

## Suggested fix

Add `!t.esc` to the `package` and `import` cases in `scanKotlin`. Decide per opaque check whether an escaped token should trigger it. Add exact-equality fixture rows to `kotlin_test.go`, in the same shape as t1997's `TestKotlinFunInterfaceDeclaredOnce`: an escaped `import` / `package` followed by a declaration must keep that declaration and add no import. Add controls for real `import` / `package` directives. Bump the cache `schemaVersion` to HEAD + 1 at commit time.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T19:32:47Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T19:50:00Z status=pass attempt=1 type=human
