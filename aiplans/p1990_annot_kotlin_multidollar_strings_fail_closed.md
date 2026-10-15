---
Task: t1990_annot_kotlin_multidollar_strings_fail_closed.md
Branch: main
Base branch: main
Output branch: main
---

# t1990 — annot Kotlin classifier: model Kotlin 2.2 multi-dollar strings

## Context

t1954_4's research corpus found that `classifyKotlin`
(`goengines/internal/testmap/annot/lexctx.go:787`) does not model the Kotlin 2.2
interpolation prefix (`$$"…"`, `$$"""…"""`). In such a string only a `$`-run at
least as long as the prefix starts a template, so a lone `${` is literal text.
The classifier pushes a template frame on every `${`, mis-places every later
string/comment boundary, and on the valid file `kotlin/multidollar_comment_desync.kt`
classes line 9 (inside a raw string) as Comment — `Apply` then writes into the
string's content. Exposure today is zero (no `$$"` in any registered repo), but
any target adopting the syntax is exposed.

**Decision: model the prefix exactly (not fail closed).** The task allows either.
Failing closed is far costlier here than in `deps` (t1980): an Uncertain context
makes `ParseFile` return a `SyntaxError` for any file carrying `testmap:`, and
`ScanAnnotations` (`annot/source.go:54-60`) returns that error, so **one annotated
Kotlin test file using `$$"` would fail the whole scan**. The model is small and is
pinned to the real lexer grammar below, the four corpus fixtures all expect
`certain` (kotlinc 2.4.21 oracle), and modelling lets t1991's conformance gate
take them as passes instead of pinned known failures.

### Grammar (JetBrains/kotlin `compiler/psi/parser/src/org/jetbrains/kotlin/lexer/Kotlin.flex`)

- `{INTERPOLATION}?\"` (code and `LONG_TEMPLATE_ENTRY`, i.e. inside `${…}`):
  `pushInterpolationPrefix(Math.max(yylength()-1, 1))` → a `$`-run of length r
  before the opening quote gives the string prefix `n = max(r, 1)`; then
  `STRING_PREFIX` picks `"""` (RAW_STRING) or `"` (STRING).
- `<STRING, RAW_STRING> LONG_TEMPLATE_ENTRY_START = \$+\{`: count = dollars.
  `== n` → template; `< n` → literal (`{` pushed back); `> n` → pushback(n+1):
  leading dollars literal, the last n + `{` re-lexed as a template. ⇒ **template
  iff count ≥ n.**
- `<STRING, RAW_STRING> SHORT_TEMPLATE_ENTRY = \$+{IDENTIFIER}`, IDENTIFIER
  includes `ESCAPED_IDENTIFIER = \`[^\`\n]+\``: same `==`/`<`/`>` rule. Only the
  backticked form moves a boundary (it can contain `"`, `{`, `/*`); a plain
  identifier cannot.
- `<STRING, RAW_STRING> LONELY_DOLLAR = \$+` → literal; inside strings a `$`-run
  before `"` is literal dollars followed by the closing quote (the prefix rule is
  not active in the exclusive string states).
- `pushState`/`popState` save and restore `requiredInterpolationPrefix` — each
  string frame keeps its own n; a template inside resets to code.

### Boundary-moving forms (Kotlin), modelled-or-fail

| form | status |
|---|---|
| `$`ʳ`"` / `$`ʳ`"""` in code or a template, r ≥ 0 → prefix max(r,1) | **modelled (new)** |
| in a string: `$`-run ≥ n + `{` → template | **modelled (new; was: any `${`)** |
| in a string: `$`-run ≥ n + `` `name` `` → short template, name skipped | **modelled (new)** |
| in a string: `$`-run < n, or before anything else → literal | **modelled (new)** |
| `"` closes STRING; `\` escapes one char (also in `$$"…"`) | modelled (unchanged) |
| `"""` + extra quotes closes RAW_STRING (last three close) | modelled (unchanged) |
| newline in STRING (DANGLING_NEWLINE) | fails closed: Uncertain (unchanged) |
| `${ … }` brace depth, nested strings/comments inside | modelled (unchanged) |
| `/* … */` nesting, `//`, char literals, backticked names in code | modelled (unchanged) |

## Implementation

All production changes are in `goengines/internal/testmap/annot/lexctx.go`
(Kotlin section only).

1. **`kframe`** — add `dollars int` (`'s'`/`'r'`: the interpolation prefix, i.e.
   the `$`-run a template needs) and update the type comment.
2. **`classifyKotlin` code context** — replace the `"""` and `"` cases with one
   case on `c == '"' || c == '$'`: measure the `$`-run r at `j`; if `"""` follows,
   push `'r'` with `dollars: max(r, 1)` and advance r+3; if `"` follows, push
   `'s'` likewise (r+1); otherwise advance past the run (dollars before no quote
   are ordinary code bytes, as today). Comment cites `{INTERPOLATION}?\"`.
3. **`'s'` and `'r'` cases** — replace `strings.HasPrefix(rest, "${")` with a
   `c == '$'` case calling a new helper; keep `\\` (s), `"` (s) and `"""` (r)
   exactly as they are:
   ```go
   // kotlinDollars reads the $-run at ln[j] in a string whose interpolation
   // prefix is n (Kotlin.flex: LONG_TEMPLATE_ENTRY_START, SHORT_TEMPLATE_ENTRY,
   // LONELY_DOLLAR). A run of at least n dollars before '{' opens a template —
   // its last n dollars start it, any before them are text; one before a
   // backticked name is a short template, whose name may hold quotes. A
   // shorter run, or one before anything else, is text.
   func kotlinDollars(ln string, j, n int) (next int, template bool) {
       k := j
       for k < len(ln) && ln[k] == '$' { k++ }
       if k-j < n || k == len(ln) { return k, false }
       switch ln[k] {
       case '{':
           return k + 1, true
       case '`':
           if e := strings.IndexByte(ln[k+1:], '`'); e > 0 {
               return k + e + 2, false
           }
       }
       return k, false
   }
   ```
   On `template` push `'t'` (as today) and continue at `next`. For n = 1 this is
   byte-for-byte today's behaviour except the backticked short template, which
   now matches the real lexer.
4. **Tests — `lexctx_test.go` `TestClassifyKotlin`**: add rows (classes pinned,
   `uncertain` 0) for
   - the four corpus fixtures, inlined from
     `aidocs/testing_engine/t1954_parser_research/corpus/kotlin/multidollar_*.kt.in`
     with a comment naming them (the `bomDoc` precedent):
     `comment_desync` → `cc#cc#ccLLc#`, `interpolation` → `ccccc#c`,
     `literal_brace` → `cccLLc#c`, `quote_boundary` → `ccccLLcL#c`;
   - prefix 3 (`$$$"""$${/*"""` then `// real`);
   - excess dollars open a template (`$$"""$$${"""` / look-alike / `"""}"""` /
     `// real` → `cLL#`);
   - a dollar run before the closing quote (`$$"""a$$"""`);
   - nested frames restore the outer prefix (`"${ $$"${" }"`, and a plain
     `"${x}"` inside a `$$"""$${ … }"""` template);
   - a backticked short template holding a quote, plain and multi-dollar
     (`"$\`x"/*\`"`, `$$"$$\`x"/*\`"`), and its sub-threshold literal form.
   Every `want` string is confirmed against the real lexer in step 6.
5. **Tests — reads and writes through the real path**: add a
   `TestKotlinMultiDollar` (in `rewrite_test.go`, next to `TestByteOrderMark`)
   that, for each of the four fixtures, runs `ParseFile` and checks the covers
   records equal the fixture's `.expect` `read:` list (desync: line 3
   `app/real.kt`; interpolation: 6; literal_brace: 7; quote_boundary: 9; nothing
   else), and add the `.edits` case to `TestApplyRefusesNonComments`:
   `Replace` line 9 of the desync fixture (`Want` = `// testmap:covers
   app/fake.kt`, `New` = `… @2026-02-02/bbbbbbbbbb`) → `ErrNotComment`, file
   unchanged.
6. **Red proof + real-lexer differential.**
   - Run the new tests before the `lexctx.go` change:
     `cd goengines && go test ./internal/testmap/annot/ -run 'TestClassifyKotlin|TestKotlinMultiDollar|TestApplyRefusesNonComments'`
     must fail (desync Apply applies; classes differ; interpolation is
     Uncertain). Record output.
   - **Real-lexer differential through an explicit adapter.** A scratchpad
     probe drives `org.jetbrains.kotlin.lexer.KotlinLexer` from
     `~/.gradle/wrapper/dists/gradle-9.5.1-bin/*/gradle-9.5.1/lib/kotlin-compiler-embeddable-2.3.20.jar`
     + `kotlin-stdlib-2.3.20.jar` (that classpath alone loads the lexer —
     checked in planning). A raw token dump does not match `TestClassifyKotlin`'s
     contract, so the probe has an adapter that reproduces `runLex`'s
     contract. Both gaps were checked against this jar during planning: the
     BOM comes back as `BAD_CHARACTER` before `EOL_COMMENT`, and an
     unterminated raw string reaches EOF with no error token. The adapter
     (Java, one `adapt(src) → (classes, uncertainLine)` function):
     - **Input:** the row's `src`, LF-only (refuse a `\r`). Strip one leading
       U+FEFF before lexing, as `bomLen(Kotlin, …)` and kotlinc do; line
       numbers are unchanged. Every other `BAD_CHARACTER` is listed as a note
       and does not affect classes.
     - **Frames:** a stack fed by `OPEN_QUOTE` (push string, its line; an
       `INTERPOLATION_PREFIX` before it changes nothing) / `CLOSING_QUOTE` (pop),
       `LONG_TEMPLATE_ENTRY_START` (push template) / `LONG_TEMPLATE_ENTRY_END`
       (pop). `SHORT_TEMPLATE_ENTRY_START` pushes nothing: its `IDENTIFIER`
       token follows.
     - **Unclosed, tracked explicitly** (the lexer gives no error token):
       `DANGLING_NEWLINE` → uncertain at the innermost string's line, and stop.
       A `BLOCK_COMMENT`/`DOC_COMMENT` token is closed only if a nesting scan
       of its text (`/*` +1, `*/` −1) returns to 0 at its last byte. This
       catches `/* a /* b */` running to EOF. At EOF, an open frame or an
       unclosed comment → uncertain at the **outermost** open construct's line,
       mirroring `stack[1].line`.
     - **Classes (only when certain):** for line k ≥ 2, take the token holding
       the preceding `\n`. A `REGULAR_STRING_PART` or `BLOCK_COMMENT`/`DOC_COMMENT`
       gives `L`. A `WHITE_SPACE` with a template on top gives `c`; inside a
       template the classifier classes a `//` line as Code. A `WHITE_SPACE` with
       an empty stack gives `#` when the line's first non-`WHITE_SPACE` token is
       `EOL_COMMENT`, else `c`. Line 1 uses the empty-stack rule.
     - **Comparison mirrors `runLex`:** a row with `uncertain ≠ 0` compares
       only the uncertain line. A certain row needs a certain adapter result
       and equal class strings. The two are reported separately.
     - **Triage before any change.** Classify every disagreement first:
       (a) an **adapter gap** — a rule above fails to mirror the classifier's
       documented contract (BOM, EOF, the template-line policy, CR). Fix the
       adapter; never touch the model or the row for it. (b) A **classifier
       defect** — the token dump shows a different boundary. Fix the model.
       (c) A **wrong pin in a new row** — fix the row, citing the token dump.
       Existing rows keep their expectations unless (b) is proven with a
       token dump. That includes `bom-comment` → `#c` and `unterminated-raw`
       → uncertain line 1.
     - Run it over every `TestClassifyKotlin` row, old and new. Adapter source,
       command and output go verbatim into Final Implementation Notes.
7. Then apply steps 1–3 and re-run: `go vet ./internal/testmap/annot/ && go test
   ./internal/testmap/annot/ ./internal/testmap/deps/ ./cmd/ait-testmap/`
   all green; `gofmt -l` clean.

### Post-phase (risk mitigations)

1. [kotlin_realrepo_class_parity] Write a throwaway
   `goengines/internal/testmap/annot/zz_parity_test.go` holding HEAD's Kotlin
   classifier renamed (`git show HEAD:goengines/internal/testmap/annot/lexctx.go`,
   Kotlin section only: `kframe`→`kframeOld`, `classifyKotlin`→`classifyKotlinOld`)
   and a test, gated on an env var listing files, that runs both classifiers on
   every `.kt`/`.kts` file of every repository in `ait projects list` (git
   `ls-files`, so ignored/build trees are skipped) and prints one line per file
   whose class string or Uncertain differs, plus the totals. Expected: 0
   differences (no `$$"` in any repo; a backticked short template in a string is
   the only other changed form). Any difference must be traced to one of the two
   modelled forms and the real lexer, or it is a regression to fix. Delete the
   file afterwards (`git status` shows no trace); copy its source and output
   verbatim into Final Implementation Notes.

## Verification

- Red proof (step 6) fails pre-fix; post-fix the same command passes.
- The KotlinLexer adapter agrees with every `TestClassifyKotlin` row: class
  strings for the certain rows, the uncertain line for the uncertain rows.
  Any disagreement is triaged as adapter gap, classifier defect or wrong pin,
  and resolved, before the review.
- `go test ./...` in `goengines` green (the classifier feeds deps and the CLI).
- Optional (task's last bullet, informational): the research matrix rerun is not
  required — the inlined fixtures plus the differential cover the same cases.

## Risk

### Code-health risk: low
- The `$` handling is shared by every Kotlin string: a slip in the n = 1 path (or in the new code-context `$`-run case) would shift classes across all Kotlin files, not just multi-dollar ones · severity: low (residual — addressed by inline post-phase kotlin_realrepo_class_parity; plain-string rows of `TestClassifyKotlin` stay pinned) · → mitigation: inline post-phase kotlin_realrepo_class_parity

### Goal-achievement risk: low
- The model is read from Kotlin.flex on master; the lexer a target compiles with may differ in detail · severity: low · → mitigation: none (plan step 6 diffs every row against the 2.3.20 `KotlinLexer`, and the corpus `.expect` files were checked by kotlinc 2.4.21)

### Planned mitigations
- timing: post-phase | name: kotlin_realrepo_class_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a regression on plain (n = 1) Kotlin strings | desc: old-vs-new classifier parity over every .kt/.kts file in the registered repositories; zero unexplained differences

## Step 9 reference

Current-branch workflow: after Step 8 review and commit, Step 9 runs
`ait gates run` / build verification, then `aitask_archive.sh 1990`.
