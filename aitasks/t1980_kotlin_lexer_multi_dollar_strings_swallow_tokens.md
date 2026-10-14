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
created_at: 2026-10-14 12:06
updated_at: 2026-10-14 15:20
---

## Origin

Spawned from t1975 during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/deps/kotlinlex.go:187` — `ktLexer.str` (with `code`'s `$` handling) treats a Kotlin 2.2 multi-dollar string (`$$"""…"""`) as an ordinary string and recurses into a literal `${`, so `val s = $$"""${/*}"""` swallows every token up to a later `*/` with err=nil (measured: `fun f() = Callee()` lost) — silent under-read of .kt sources

## Diagnostic context

t1975 made the Gradle build-script comment blanker string-aware
(`goengines/internal/testmap/deps/gradlelex.go`, commit c5ca09174). Plan review
found that Kotlin 2.2 **multi-dollar interpolation** strings (`$$"…"`,
`$$"""…"""`) need N dollars to interpolate. A single `${` inside them is literal
text. A lexer that does not model the prefix recurses into that `${` as template
code and mis-places every later boundary.

t1975's Gradle lexer detects the form and fails closed (`untokenizable`). The
`.kt` source lexer `ktLexer` (`kotlinlex.go`) has the same blind spot, and there
it is **silent**. A throwaway probe at HEAD c5ca09174 showed it:

```go
src := "package p\n\nval s = $$\"\"\"${/*}\"\"\"\nfun f() = Callee()\nval t = \"\"\"*/}\"\"\"\n"
toks, err := ktLex(src)  // err=<nil>, 'n' tokens = ["package" "p" "val" "s"]
```

Why it happens:

- `code()` emits a lone `$` as an operator token.
- `str()` then lexes the raw string as an ordinary one.
- `str()` recurses into the literal `${` via `code(true)`.
- The `/*` inside it opens a block comment that runs to the next `*/` in a later
  string.

The result: `fun f() = Callee()` disappears from the token stream. The file's
imports and references go missing (under-selection), and no `untokenizable`
opaque reason is raised.

## Suggested fix

Pick one:

- **Fail closed, like `gradlelex.go`:** a run of `$` immediately followed by `"`
  in code returns `errUntokenizable`.
- **Model the interpolation threshold:** with an N-dollar prefix, only a run of
  at least N `$` before `{` or an identifier starts a template.

Either way, pin `val s = $$"""${/*}"""` … `*/` as a regression in
`kotlinlex_test.go`, and bump `schemaVersion` in `cache.go` to HEAD+1 at commit
time.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-14T12:20:17Z status=pass attempt=1 type=human
