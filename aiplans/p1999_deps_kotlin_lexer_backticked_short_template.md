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

## Final Implementation Notes
- **Actual work done:** Implemented as planned. `deps/kotlinlex.go` `str()` reads
  `` $`name` `` (one or more chars, no newline, same line) as a short template and
  emits the unquoted name as an `n` token with `esc: true`. An empty, unclosed or
  newline-spanning name stays text. `deps/gradlelex.go` `str()` skips the same
  construct in kts mode only. Each lexer gained an `escapedEnd(i)` helper, which
  its existing code-path backtick case now also uses (behaviour unchanged).
  `cache.go` `schemaVersion` 9 → 10. Tests: 6 `TestKotlinLexer` rows, one
  `TestKotlinLexerMarksEscapedIdentifiers` case, the new
  `TestKotlinLexerShortTemplateBacktickedName` (the exact task probe plus a
  `p.Callee()` variant for `Refs`), and 3 `gradleLexCases` kts rows.
- **Deviations from plan:** The `ktLex` doc comment avoids a double backtick
  (`` `$`name`` ``), which gofmt rewrites to a curly quote, and says "the
  backticked name of $`name`" instead. The dump test records an `ERROR:` row
  instead of failing, so the pre-fix control could run on the same dump source.
  Rows are named rather than indexed.
- **Issues encountered:** Plan review (user) rejected an assertion that
  `Kt.Refs` contains `Callee` for the exact probe. `kotlin.go:192-198` admits only
  dotted chains with at least 2 segments and a lowercase first segment, so the
  test asserts tokens and decls for the probe, and `Refs` only for a
  `p.Callee()` variant.
- **Key decisions:** The kts blanker gap is fixed in this task, not deferred to
  t1992. Same construct, same package, one cache bump: fixing only one lexer
  would have left an interim state in which they disagree.
- **Red proof** (new tests against the unfixed `str()`, run before the fix in the
  live tree; no stash or restore was needed because the tests were written
  first):
  ```text
  --- FAIL: TestScanGradleStringAwareComments/kts-short-template-backticks: refs [], want [":lib"]
  --- FAIL: TestScanGradleStringAwareComments/kts-short-template-raw: refs [], want [":lib"]
  --- FAIL: TestKotlinLexer: lex "\"$`a\"b`\"": untokenizable
  --- FAIL: TestKotlinLexerMarksEscapedIdentifiers: ... s:$`fun`:false], want [... n:fun:true S::false]
  --- FAIL: TestKotlinLexerShortTemplateBacktickedName:
      names ["package" "p" "val" "q\"\"\"" "val" "s" "\"\"\" + \"\"\""] lack "f" / "Callee" / "t"
      decls ["q\"\"\"" "s"] lack "f" / "t"
      refs [] lack p.Callee at line 4
  ```
  `kts-short-template-unclosed` passed before the fix too, as intended: it
  guards against over-matching.
- **Real-lexer differential (plan step 6).** Lexer: `kotlin-compiler-embeddable-2.3.20.jar`
  from the Gradle 9.5.1 distribution. The dump test (deleted after use) and the
  Java probe are reproduced verbatim below. The control ran the identical dump
  source (`cmp`-verified) against an isolated scratch copy of `goengines/`
  whose `kotlinlex.go` / `gradlelex.go` were replaced by `git show HEAD:…`.

  Command:
  ```sh
  T1999_DUMP=$S/rows.tsv go test ./internal/testmap/deps/ -run TestZZDumpT1999 -count=1          # live (fixed)
  (cd $S/ctl/goengines && T1999_DUMP=$S/rows_ctl.tsv go test ./internal/testmap/deps/ -run TestZZDumpT1999 -count=1)  # pre-fix control
  L=$(ls -d ~/.gradle/wrapper/dists/gradle-9.5.1-bin/*/gradle-9.5.1/lib)
  java -cp "$L/kotlin-compiler-embeddable-2.3.20.jar:$L/kotlin-stdlib-2.3.20.jar" KtProbe.java rows.tsv
  java -cp "$L/kotlin-compiler-embeddable-2.3.20.jar:$L/kotlin-stdlib-2.3.20.jar" KtProbe.java rows_ctl.tsv
  ```

  Output, fixed lexers:
  ```text
MATCH    kt    templates
MATCH    kt    lone-dollar
MATCH    kt    st-plain
MATCH    kt    st-raw
MATCH    kt    st-run
MATCH    kt    st-newline
MATCH    kt    esc-keywords
MATCH    kt    probe-qualified
MATCH    kt    literals
MATCH    kt    raw-quote-run
MATCH    kt    comments
MATCH    kt    dollar-strings
MATCH    kt    dollar-run
MATCH    kt    st-unclosed
MATCH    kt    backticked
MATCH    kt    class-ref
MATCH    kt    use-site
MATCH    kt    st-empty
MATCH    kt    probe
MATCH    kts   glob-kts
MATCH    kts   kts-raw-string-backslash
MATCH    kts   kts-nested-comment
MATCH    kts   kts-backticked-name
MATCH    kts   kts-char-literals
SKIP     kts   kts-multi-dollar                 (our blanker fails closed)
SKIP     kts   kts-multi-dollar-single-line     (our blanker fails closed)
MATCH    kts   kts-short-template-backticks
MATCH    kts   kts-short-template-raw
MATCH    kts   kts-short-template-unclosed
TOTAL match=27 mismatch=0 skipped=2 lexer=2.3.20
  ```

  Output, pre-fix control (the oracle discriminates: 8 mismatches, all template rows):
  ```text
MATCH    kt    backticked
MATCH    kt    dollar-strings
MATCH    kt    dollar-run
MATCH    kt    st-newline
MATCH    kt    comments
MATCH    kt    literals
MATCH    kt    use-site
MATCH    kt    lone-dollar
MISMATCH kt    st-plain
    real: a"b
    ours: ERROR:untokenizable
    tokens: OPEN_QUOTE["] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`a"b`] CLOSING_QUOTE["]
MISMATCH kt    st-run
    real: x"
    ours: ERROR:untokenizable
    tokens: OPEN_QUOTE["] REGULAR_STRING_PART[$] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`x"`] CLOSING_QUOTE["]
MATCH    kt    st-empty
MATCH    kt    st-unclosed
MATCH    kt    class-ref
MISMATCH kt    esc-keywords
    real: fun | fun | interface | interface | fun
    ours: fun | fun | interface | interface
    tokens: IDENTIFIER[`fun`] WHITE_SPACE[ ] fun[fun] WHITE_SPACE[ ] IDENTIFIER[`interface`] WHITE_SPACE[ ] interface[interface] WHITE_SPACE[ ] OPEN_QUOTE["] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`fun`] CLOSING_QUOTE["]
MISMATCH kt    probe
    real: package | p | val | q""" | val | s | q""" | fun | f | Callee | val | t
    ours: package | p | val | q""" | val | s | """ + """
    tokens: package[package] WHITE_SPACE[ ] IDENTIFIER[p] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[`q"""`] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] INTEGER_LITERAL[1] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[s] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] OPEN_QUOTE["""] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`q"""`] CLOSING_QUOTE["""] WHITE_SPACE[ ] PLUS[+] WHITE_SPACE[ ] OPEN_QUOTE["""] REGULAR_STRING_PART[`/*] CLOSING_QUOTE["""] WHITE_SPACE[\n] fun[fun] WHITE_SPACE[ ] IDENTIFIER[f] LPAR[(] RPAR[)] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] IDENTIFIER[Callee] LPAR[(] RPAR[)] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[t] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] INTEGER_LITERAL[1] WHITE_SPACE[ ] EOL_COMMENT[// */] WHITE_SPACE[\n]
MISMATCH kt    probe-qualified
    real: package | p | val | q""" | val | s | q""" | fun | f | p | Callee | val | t
    ours: package | p | val | q""" | val | s | """ + """
    tokens: package[package] WHITE_SPACE[ ] IDENTIFIER[p] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[`q"""`] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] INTEGER_LITERAL[1] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[s] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] OPEN_QUOTE["""] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`q"""`] CLOSING_QUOTE["""] WHITE_SPACE[ ] PLUS[+] WHITE_SPACE[ ] OPEN_QUOTE["""] REGULAR_STRING_PART[`/*] CLOSING_QUOTE["""] WHITE_SPACE[\n] fun[fun] WHITE_SPACE[ ] IDENTIFIER[f] LPAR[(] RPAR[)] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] IDENTIFIER[p] DOT[.] IDENTIFIER[Callee] LPAR[(] RPAR[)] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[t] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] INTEGER_LITERAL[1] WHITE_SPACE[ ] EOL_COMMENT[// */] WHITE_SPACE[\n]
MATCH    kt    raw-quote-run
MISMATCH kt    st-raw
    real: q"""
    ours: ERROR:untokenizable
    tokens: OPEN_QUOTE["""] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`q"""`] CLOSING_QUOTE["""]
MATCH    kt    templates
MATCH    kts   glob-kts
MATCH    kts   kts-raw-string-backslash
MATCH    kts   kts-nested-comment
MATCH    kts   kts-backticked-name
MATCH    kts   kts-char-literals
SKIP     kts   kts-multi-dollar                 (our blanker fails closed)
SKIP     kts   kts-multi-dollar-single-line     (our blanker fails closed)
MISMATCH kts   kts-short-template-backticks
    real: val `q"` = 1\nval s = "$`q"`" + "`/*"\ndependencies { implementation(project(":lib")) }\nval t = 1      \n
    ours: val `q"` = 1\nval s = "$`q"`" + "`   \n                                                \n               \n
    tokens: val[val] WHITE_SPACE[ ] IDENTIFIER[`q"`] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] INTEGER_LITERAL[1] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[s] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] OPEN_QUOTE["] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`q"`] CLOSING_QUOTE["] WHITE_SPACE[ ] PLUS[+] WHITE_SPACE[ ] OPEN_QUOTE["] REGULAR_STRING_PART[`/*] CLOSING_QUOTE["] WHITE_SPACE[\n] IDENTIFIER[dependencies] WHITE_SPACE[ ] LBRACE[{] WHITE_SPACE[ ] IDENTIFIER[implementation] LPAR[(] IDENTIFIER[project] LPAR[(] OPEN_QUOTE["] REGULAR_STRING_PART[:lib] CLOSING_QUOTE["] RPAR[)] RPAR[)] WHITE_SPACE[ ] RBRACE[}] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[t] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] INTEGER_LITERAL[1] WHITE_SPACE[ ] EOL_COMMENT[// */] WHITE_SPACE[\n]
MISMATCH kts   kts-short-template-raw
    real: val r = """$`x"""`""" + """`/*"""\ndependencies { implementation(project(":lib")) }\nval t = 1      \n
    ours: val r = """$`x"""`""" + """`     \n                                                \n               \n
    tokens: val[val] WHITE_SPACE[ ] IDENTIFIER[r] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] OPEN_QUOTE["""] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`x"""`] CLOSING_QUOTE["""] WHITE_SPACE[ ] PLUS[+] WHITE_SPACE[ ] OPEN_QUOTE["""] REGULAR_STRING_PART[`/*] CLOSING_QUOTE["""] WHITE_SPACE[\n] IDENTIFIER[dependencies] WHITE_SPACE[ ] LBRACE[{] WHITE_SPACE[ ] IDENTIFIER[implementation] LPAR[(] IDENTIFIER[project] LPAR[(] OPEN_QUOTE["] REGULAR_STRING_PART[:lib] CLOSING_QUOTE["] RPAR[)] RPAR[)] WHITE_SPACE[ ] RBRACE[}] WHITE_SPACE[\n] val[val] WHITE_SPACE[ ] IDENTIFIER[t] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] INTEGER_LITERAL[1] WHITE_SPACE[ ] EOL_COMMENT[// */] WHITE_SPACE[\n]
MATCH    kts   kts-short-template-unclosed
TOTAL match=19 mismatch=8 skipped=2 lexer=2.3.20
  ```

  `zz_t1999_dump_test.go` (sha256 `6493c3928faa34f40aba9c2f2e854035110f03068b4615fe2f9343ae1e781dd7`):
  ````go
package deps

// zz_t1999_dump_test.go (t1999) - dumps ktLex names and kts blanking for the
// KotlinLexer differential. Deleted after use.

import (
	"encoding/base64"
	"os"
	"strings"
	"testing"
)

func TestZZDumpT1999(t *testing.T) {
	out := os.Getenv("T1999_DUMP")
	if out == "" {
		t.Skip("T1999_DUMP unset")
	}
	b64 := func(s string) string { return base64.StdEncoding.EncodeToString([]byte(s)) }
	var rows []string
	kt := map[string]string{
		"comments":       "a /* x /* y */ z */ b // c d\ne",
		"literals":       `f("com.x.Y", 'c', '\'')`,
		"templates":      `"$name and ${com.x.util.f()}"`,
		"raw-quote-run":  `"""a "b" """"`,
		"backticked":     "`odd name`.call()",
		"class-ref":      "x::class.java",
		"use-site":       "@field:Inject lateinit",
		"dollar-strings": `"a$" + "$$"`,
		"lone-dollar":    "$ x",
		"dollar-run":     "$$$ x",
		"st-plain":       "\"$`a\"b`\"",
		"st-raw":         "\"\"\"$`q\"\"\"`\"\"\"",
		"st-run":         "\"$$`x\"`\"",
		"st-empty":       "\"$``\"",
		"st-unclosed":    "\"$`x\"",
		"st-newline":     "\"\"\"$`a\nb`\"\"\"",
		"esc-keywords":   "`fun` fun `interface` interface \"$`fun`\"",
		"probe": lines("package p", "val `q\"\"\"` = 1",
			"val s = \"\"\"$`q\"\"\"`\"\"\" + \"\"\"`/*\"\"\"", "fun f() = Callee()", "val t = 1 // */"),
		"probe-qualified": lines("package p", "val `q\"\"\"` = 1",
			"val s = \"\"\"$`q\"\"\"`\"\"\" + \"\"\"`/*\"\"\"", "fun f() = p.Callee()", "val t = 1 // */"),
	}
	for name, src := range kt {
		toks, err := ktLex(src)
		if err != nil {
			rows = append(rows, strings.Join([]string{"kt", name, b64(src), b64("ERROR:" + err.Error())}, "\t"))
			continue
		}
		var names []string
		for _, k := range toks {
			if k.kind == 'n' {
				names = append(names, k.text)
			}
		}
		rows = append(rows, strings.Join([]string{"kt", name, b64(src), b64(strings.Join(names, "\x1f"))}, "\t"))
	}
	for _, c := range gradleLexCases {
		if !c.kts {
			continue
		}
		blanked, failAt := blankGradleComments(c.src, true)
		if failAt >= 0 {
			rows = append(rows, strings.Join([]string{"skip", c.name, b64(c.src), ""}, "\t"))
			continue
		}
		rows = append(rows, strings.Join([]string{"kts", c.name, b64(c.src), b64(blanked)}, "\t"))
	}
	if err := os.WriteFile(out, []byte(strings.Join(rows, "\n")+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
}
  ````

  `KtProbe.java` (sha256 `88382011758f49eb14f1efec17a561990c7bfd6ecbe7e0383927a9f21c9929ba`):
  ````java
// KtProbe.java (t1999) - KotlinLexer differential for deps' ktLex names and
// the kts comment blanker. Reads the rows dumped by zz_t1999_dump_test.go:
// mode \t name \t base64(src) \t base64(ours).
//   kt:  ours = ktLex 'n' texts joined by \x1f; real = IDENTIFIER (backticks
//        stripped) and keyword tokens, in order.
//   kts: ours = blankGradleComments(src, true); real = src with every comment
//        token blanked byte-for-byte (UTF-8), newlines kept.
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import org.jetbrains.kotlin.com.intellij.psi.tree.IElementType;
import org.jetbrains.kotlin.lexer.KotlinLexer;
import org.jetbrains.kotlin.lexer.KtKeywordToken;
import org.jetbrains.kotlin.lexer.KtTokens;

public class KtProbe {
  record Tok(IElementType type, int start, int end) {}

  static List<Tok> lex(String src) {
    List<Tok> toks = new ArrayList<>();
    KotlinLexer lx = new KotlinLexer();
    lx.start(src);
    while (lx.getTokenType() != null) {
      toks.add(new Tok(lx.getTokenType(), lx.getTokenStart(), lx.getTokenEnd()));
      lx.advance();
    }
    return toks;
  }

  static String names(String src, List<Tok> toks) {
    List<String> out = new ArrayList<>();
    for (Tok t : toks) {
      String text = src.substring(t.start, t.end);
      if (t.type == KtTokens.IDENTIFIER) {
        if (text.length() >= 2 && text.startsWith("`") && text.endsWith("`")) text = text.substring(1, text.length() - 1);
        out.add(text);
      } else if (t.type instanceof KtKeywordToken) {
        out.add(text);
      }
    }
    return String.join("\u001f", out);
  }

  static boolean isComment(IElementType t) {
    return t == KtTokens.EOL_COMMENT || t == KtTokens.BLOCK_COMMENT || t == KtTokens.DOC_COMMENT
        || t == KtTokens.SHEBANG_COMMENT;
  }

  static String blank(String src, List<Tok> toks) {
    boolean[] in = new boolean[src.length()];
    for (Tok t : toks) if (isComment(t.type)) for (int i = t.start; i < t.end; i++) in[i] = true;
    StringBuilder b = new StringBuilder();
    for (int i = 0; i < src.length(); i++) {
      char c = src.charAt(i);
      if (!in[i] || c == '\n') { b.append(c); continue; }
      int n = String.valueOf(c).getBytes(StandardCharsets.UTF_8).length;
      if (Character.isSurrogate(c)) n = 2; // a pair is 4 UTF-8 bytes
      b.append(" ".repeat(n));
    }
    return b.toString();
  }

  static String dump(String src, List<Tok> toks) {
    StringBuilder d = new StringBuilder("    tokens:");
    for (Tok t : toks) d.append(' ').append(t.type).append('[').append(src.substring(t.start, t.end).replace("\n", "\\n")).append(']');
    return d.toString();
  }

  public static void main(String[] args) throws Exception {
    int match = 0, mismatch = 0, skipped = 0;
    Base64.Decoder dec = Base64.getDecoder();
    for (String row : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
      if (row.isEmpty()) continue;
      String[] f = row.split("\t", -1);
      String mode = f[0], name = f[1], src = new String(dec.decode(f[2]), StandardCharsets.UTF_8);
      if (mode.equals("skip")) {
        System.out.printf("SKIP     %-5s %-32s (our blanker fails closed)%n", "kts", name);
        skipped++;
        continue;
      }
      String ours = new String(dec.decode(f[3]), StandardCharsets.UTF_8);
      List<Tok> toks = lex(src);
      String real = mode.equals("kt") ? names(src, toks) : blank(src, toks);
      boolean ok = real.equals(ours);
      System.out.printf("%-8s %-5s %s%n", ok ? "MATCH" : "MISMATCH", mode, name);
      if (ok) { match++; continue; }
      mismatch++;
      System.out.println("    real: " + real.replace("\u001f", " | ").replace("\n", "\\n"));
      System.out.println("    ours: " + ours.replace("\u001f", " | ").replace("\n", "\\n"));
      System.out.println(dump(src, toks));
    }
    System.out.printf("TOTAL match=%d mismatch=%d skipped=%d lexer=%s%n", match, mismatch, skipped,
        org.jetbrains.kotlin.config.KotlinCompilerVersion.VERSION);
  }
}
  ````
- **Upstream defects identified:** None
