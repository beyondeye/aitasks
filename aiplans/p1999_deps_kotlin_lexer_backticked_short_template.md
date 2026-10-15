---
Task: t1999_deps_kotlin_lexer_backticked_short_template.md
Base branch: main
Output branch: main
---

# t1999 — Model the `` $`name` `` short template in the deps Kotlin lexers

## Context

Kotlin.flex: in `<STRING, RAW_STRING>`, `SHORT_TEMPLATE_ENTRY = \$+{IDENTIFIER}`.
`IDENTIFIER` includes `` ESCAPED_IDENTIFIER = `[^`\n]+` ``. So inside a string,
`` $`a"b` `` is a template, and its name runs past the quote. t1990 modelled this in
`annot/lexctx.go` (`kotlinDollars`). The two lexers in `deps/` did not:

- `deps/kotlinlex.go` `ktLexer.str()` (`.kt` dependency scanner): `$` before a
  backtick falls to `default`, and the quote in the name closes the string. The
  task's probe then opens a `/*` and silently drops `f`, `Callee` and `t`, with
  `err=nil`.
- `deps/gradlelex.go` `gradleLexer.str()` in kts mode (`.gradle.kts` comment
  blanker). This is the same gap, traced by hand. Adapted probe:
  ```kotlin
  val `q"` = 1
  val s = "$`q"`" + "`/*"
  dependencies { implementation(project(":lib")) }
  val t = 1 // */
  ```
  The string closes at the `"` after `q`. The code-path backtick case then
  consumes `` `" + "` ``, and `/*` blanks everything up to line 4's `*/`. That
  hides `project(":lib")`, the over-blanking hazard that `blankGradleComments`'
  own docblock warns about. Groovy mode is unaffected: a GString `$name` cannot
  be backticked.

Both lexers fix the same construct in the same package, under one cache-schema
bump, so they are fixed together. Separate fixes would leave an interim state
in which the two lexers disagree.

The `$`-run rule needs nothing extra. deps fails closed on every multi-dollar
string (t1980/t1975), so only one-dollar strings reach `str()`. There, a run
`$$`x``'s last `$` starts the template. A per-character scan gets this for free:
the first `$` falls through as text, and the second sees the backtick.

## Implementation

### 1. `goengines/internal/testmap/deps/kotlinlex.go`

- Add a helper next to `ident`:
  ```go
  // escapedEnd returns the index of the backtick closing the one at i on its
  // line, or -1.
  func (l *ktLexer) escapedEnd(i int) int
  ```
- `code()`'s `` case c == '`' `` uses it (same behaviour: unclosed → `errUntokenizable`;
  emits `ktok{kind: 'n', text: unquoted, esc: true}`).
- `str()`: new case **before** the `$ident` case:
  ```go
  case c == '$' && l.peek(1) == '`':
      // $`name` is a short template (Kotlin.flex SHORT_TEMPLATE_ENTRY): its
      // escaped name — one or more chars, no newline — may hold quotes.
      if j := l.escapedEnd(l.i + 1); j > l.i+2 {
          plain = false
          l.toks = append(l.toks, ktok{kind: 'n', text: l.src[l.i+2 : j], line: l.line, esc: true})
          l.i = j + 1
      } else {
          l.i++ // a lone $: text
      }
  ```
  The token is `esc: true`, as in the code path (t1997: a backticked name is
  never a keyword). An empty `` $`` `` or an unclosed `` $`x `` stays text.
- Update `ktLex`'s doc comment: template code `` `${…}`, `$ident`, `$`name` ``.

### 2. `goengines/internal/testmap/deps/gradlelex.go`

- Add `func (l *gradleLexer) escapedEnd(i int) int`, the same contract over
  `l.b`. Use it in `code()`'s `` l.kts && c == '`' `` case (fail behaviour
  unchanged).
- `str()`: new case right after the `${` case:
  ```go
  case l.kts && q == '"' && c == '$' && l.at(1) == '`':
      // $`name` is a short template whose escaped name may hold quotes.
      if j := l.escapedEnd(l.i + 1); j > l.i+2 {
          l.i = j + 1
      } else {
          l.i++
      }
  ```
  It sits after the backslash case, so a `\$` escape in a plain string is still
  consumed first. In a kts raw string `\` is literal text, which matches Kotlin.
- Extend `str()`'s doc comment by one clause.

### 3. `goengines/internal/testmap/deps/cache.go`

`schemaVersion` 9 → 10. Cached `kotlin` and `gradle-kts` raw facts change, so
stale blobs must be rescanned.

### 4. Tests: `deps/kotlinlex_test.go`

- `TestKotlinLexer` good rows (Go-escaped in the file):
  - `"$`a"b`"` → `n:a"b S:`
  - `"""$`q"""`"""` → `n:q""" S:`
  - `"$$`x"`"` → `n:x" S:` (the run's last `$` starts the template)
  - `"$``"` → ``s:$`` `` (an empty name is text)
  - `"$`x"` → `` s:$`x `` (an unclosed name is text, and the quote closes the string)
  - raw `"""$`a⏎b`"""` → text (a name never spans a newline)
- `TestKotlinLexerMarksEscapedIdentifiers`: append `"$`fun`"` and expect `n:fun:true`,
  then `S::false`.
- New `TestKotlinLexerShortTemplateBacktickedName`, with two sources:
  - **The task's exact probe.** It asserts that `ktLex` returns `err == nil`,
    that the `n` tokens include `f`, `Callee` and `t`, and that
    `scanKotlin(...).Kt.Decls` names include `f` and `t`. It makes **no** `Refs`
    assertion: `scanKotlin` records only dotted chains of at least two segments
    with a lowercase-leading first segment (`kotlin.go:192-198`), so the bare
    `Callee()` can never be a ref, lexer fix or not.
  - **A qualified-call variant.** Identical, except line 4 reads
    `fun f() = p.Callee()`. It asserts that `Refs` include the `p.Callee` chain
    (line 4), which the pre-fix lexer swallows along with `f`. This covers
    reference extraction without widening the ref rule.

  The doc comment states the pre-fix failure.

### 5. Tests: `deps/gradle_test.go` (`gradleLexCases`)

- `kts-short-template-backticks`: the adapted probe above, with `refs: [":lib"]`.
- `kts-short-template-raw`: the raw-string form,
  ``val r = """$`x"""`""" + """`/*"""``, then the deps line, then `val t = 1 // */`,
  with `refs: [":lib"]`.
- `kts-short-template-unclosed`: ``val s = "$`x"; val u = "https://x"; dependencies { implementation(project(":lib")) }``
  with `refs: [":lib"]`. An unclosed name is text: the string still closes at its quote.

### 6. Differential against the real lexer

This step checks the model against the lexer, not only against my reading of
Kotlin.flex. Jars:
`~/.gradle/wrapper/dists/gradle-9.5.1-bin/*/gradle-9.5.1/lib/kotlin-{compiler-embeddable,stdlib}-2.3.20.jar`.

- A temporary `deps/zz_t1999_dump_test.go` dumps every successful `TestKotlinLexer`
  good row, the new rows and the probe, as `kt` rows: name, base64(src), and the
  `n`-token texts. It also dumps every `gradleLexCases` kts row whose blanking
  succeeds, plus the new kts rows, as `kts` rows: name, base64(src), and
  base64(`blankGradleComments(src, true)`). The dump goes to the scratchpad.
- `KtProbe.java` in the scratchpad lexes each row with
  `org.jetbrains.kotlin.lexer.KotlinLexer`:
  - **kt rows:** it maps `IDENTIFIER` (backticks stripped) and every
    `KtKeywordToken` to their text, ignores all other tokens, and compares the
    sequence with ours.
  - **kts rows:** it blanks every `EOL_COMMENT` / `BLOCK_COMMENT` /
    `DOC_COMMENT` / `SHEBANG_COMMENT` range (keeping newlines) and compares the
    result with our blanked output.
- Every new row must match. A pre-existing row that does not match is triaged:
  either explained, or recorded as an upstream defect. It is never filtered out.
- Delete the zz file afterwards. Record both sources, the command and the full
  output verbatim in the plan's Final Implementation Notes (as t1990 did).

## Verification

```bash
cd goengines && go vet ./internal/testmap/deps/ && go test ./internal/testmap/deps/ ./internal/testmap/annot/
ait engine test     # go vet + go test over goengines/
```

- Red proof: before the fix, the new probe test (both sources) and the
  `kts-short-template-backticks` row fail, and they pass after it. Check this by
  running the tests against the unfixed `str()` cases in an isolated copy, with
  no stash and no restore in this shared worktree.
- The differential in step 6 shows every row matching.

## Post-implementation

- Step 8e: offer a note to **t1992**, which is in flight (the Kotlin-family
  shared-core evaluation). With this change, all three lexers model the
  `` $`name` `` short template, and the kts blanker had the gap too. Its
  inventory should list the construct as modelled everywhere.
- Step 9: archival, on the current branch (no merge).

## Risk

### Code-health risk: low
- Two additive `str()` cases plus a shared helper per lexer. They change
  behaviour only for a `$` directly before a backtick that closes on the same
  line. The cache bump forces a rescan of stale blobs · severity: low · → mitigation: none (covered by steps 3–5)

### Goal-achievement risk: low
- The model comes from Kotlin.flex and t1990's measurement. Edge forms (an
  empty name, a newline, a `$`-run) could still differ from the shipped lexer ·
  severity: low · → mitigation: none (step 6 diffs every row against the 2.3.20 `KotlinLexer`)
