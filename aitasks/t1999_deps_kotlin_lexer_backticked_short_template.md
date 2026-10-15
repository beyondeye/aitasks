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
created_at: 2026-10-15 09:01
updated_at: 2026-10-15 10:10
---

## Origin

Spawned from t1990 during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/deps/kotlinlex.go:223-233` — `ktLexer.str()` does
  not model the `` $`name` `` short template (Kotlin.flex
  `SHORT_TEMPLATE_ENTRY` with an `ESCAPED_IDENTIFIER`). A backticked name
  holding quotes closes the string early. The probe:

  ```kotlin
  package p
  val `q"""` = 1
  val s = """$`q"""`""" + """`/*"""
  fun f() = Callee()
  val t = 1 // */
  ```

  makes `ktLex` return `err=nil` and silently drop the names `f`, `Callee` and
  `t`, which the 2.3.20 `KotlinLexer` keeps.

  Not checked:
  - whether kotlinc accepts a quote-bearing backticked name on JVM;
  - whether `gradlelex.go`'s kts mode has the same gap.

## Diagnostic context

t1990 modelled Kotlin 2.2 multi-dollar strings in `annot/lexctx.go`'s
`classifyKotlin` from the real lexer grammar (JetBrains/kotlin
`compiler/psi/parser/src/org/jetbrains/kotlin/lexer/Kotlin.flex`).

**The rule.** In `<STRING, RAW_STRING>`, `SHORT_TEMPLATE_ENTRY = \$+{IDENTIFIER}`.
`IDENTIFIER` includes `ESCAPED_IDENTIFIER = \`[^\`\n]+\``, so `` $`a"b` `` inside
a string is a template whose name spans the quote. The run threshold follows
the same `==`/`<`/`>` rule as `${`.

**Measured by the probe** (lexer from
`~/.gradle/wrapper/dists/gradle-9.5.1-bin/*/gradle-9.5.1/lib/kotlin-compiler-embeddable-2.3.20.jar`):
`OPEN_QUOTE["] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`x"/*`] CLOSING_QUOTE["]`.

**The annot fix.** `kotlinDollars` in `annot/lexctx.go` skips the backticked
name when the `$`-run reaches the string's prefix. It is pinned by the
`short-template-*` rows of `TestClassifyKotlin`.

**deps.** `deps/kotlinlex.go` fails closed on every multi-dollar string (t1980),
but its plain `str()` has no `` $` `` case: `$` falls through to `default`, and
the quote in the name closes the string.

## Suggested fix

In `str()`, when `c == '$'` and the next byte is a backtick with a closing
backtick on the same line (≥1 char between), skip past the closing backtick,
emitting the name as an `'n'` token as the `$ident` case does. Pin the probe
above as a regression: `f` and `Callee` must be present. Bump `cache.go`'s
`schemaVersion`. Check `gradlelex.go`'s kts mode for the same gap, and consider
it within the t1992 shared-core evaluation.
