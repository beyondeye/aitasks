---
Task: t2030_kotlin_shebang_line_hides_deps.md
Base branch: main
Output branch: main
---

# t2030 — Model Kotlin's SHEBANG_COMMENT in ktLex and classifyKotlin

## Context

Kotlin.flex lexes a `#!` line at the start of a file as one `SHEBANG_COMMENT`
token. Of the three Kotlin-family lexers only the kts blanker models it
(`gradleLexer.shebang`, `deps/gradlelex.go`). `ktLex` (`deps/kotlinlex.go`) and
`classifyKotlin` (`annot/lexctx.go`) read the line as code. So a `{` in a
shebang silently hides the package and every declaration from `scanKotlin`, a
`(` silently hides every declaration, and a `/*` refuses the file in both. In
annot it can fail a whole `ScanAnnotations` run with a `SyntaxError`. Found by
t1992; exposure today is 0 files, but every `*.main.kts` script is a target.

### Probed rule

The real `KotlinLexer` (kotlin-compiler-embeddable 2.3.20) was probed via
jshell during planning:

| input | real lexer |
|---|---|
| `#!/usr/bin/env kotlin\npackage p\n` | `SHEBANG_COMMENT@0-21`, then `\n` whitespace |
| ` #!…` (leading space) | `WHITE_SPACE HASH EXCL …`: **offset 0 only** |
| `package p\n#!x\n` | `HASH EXCL …`: a later line is code |
| `#!a\n#!b\n` | the first line is a SHEBANG_COMMENT, the second is `HASH EXCL …`: **one line only** |
| `#!a {` (EOF, no newline), `#!a`, `#!` | `HASH EXCL …`: **a `\n` must end the line** |
| `#!\nx` | `SHEBANG_COMMENT@0-2`: an empty shebang counts |
| `#!a {\r\n…`, `#!a\fb\n`, `#!a b\n` | the token runs to the `\n` |
| `﻿#!…` (raw BOM in the lexer text) | `BAD_CHARACTER HASH …` |

Two facts sit at the compiler level, and the user's local K2JVMCompiler 2.3.20
probes confirmed both:
- kotlinc strips a leading BOM before lexing, so **a shebang after a BOM is
  honoured**.
- kotlinc normalises a lone CR to `\n`, so a lone CR ends the shebang line.

### The lone-CR boundary (review finding, verified)

None of the three Kotlin-family lexers models lone-CR line semantics:
- `ktLexer.code` and `gradleLexer.code` end a `//` comment only at `\n`, and
  ktLex counts lines only at `\n`;
- `annot.splitLines` splits only at `\n`, and the rewriter writes lines back
  joined by `\n`.

So in `// note\rpackage p\rclass Actual\r` ktLex already swallows the package
and the declaration as one comment, **with no opaque reason**. That holds with
or without a shebang. The shebang fix would only move the problem.

Modelling CR line semantics would change annot's line model and its writer,
which today would rewrite CRs as LFs. Exposure is **0 of the 2051** tracked
`.kt`/`.kts` files in the 8 registered repositories (`git ls-files` +
`grep -lzP '\r(?!\n)'`; the pattern's control: `a\rb` matches, `a\r\nb` does
not). So the supported boundary is: **a lone CR anywhere (a `\r` not
immediately followed by `\n`, including a final `\r`) fails closed in all
three Kotlin-family lexers**:
- ktLex refuses the file (`untokenizable`, so `scanKotlin` reports it opaque);
- the kts blanker returns `failAt >= 0` (the scanner over-reads);
- annot sets `Uncertain{Construct: "lone carriage return"}` (a `SyntaxError`
  for a file carrying `testmap:`, `ErrUncertainContext` for rewrites).

CRLF stays fully supported. With lone CRs refused up front, the shebang
terminator is just `\n`, which matches the lexer. Under CRLF the `\r` is part
of the shebang line, as the probe shows.

## Implementation

### 1. Record the compiler-level evidence (scratchpad only)

Re-run the two K2JVMCompiler probes the user ran, and record the commands and
outputs verbatim in Final Implementation Notes as durable evidence. Use the
`gradle-9.5.1` `lib/` jars, compile into `$SCRATCH/kshebang/out_<n>`, and check
for `p/<Class>.class`:
- `bom.kt` = `EF BB BF` + `#!/x {\npackage p\nclass A\n`;
- `cr.kt` = `#!/x {\rpackage p\rclass B\r`;
- control `ok.kt` = `#!/x {\npackage p\nclass C\n`.

If a result contradicts the user's probes, stop and report before coding.

### 2. Red tests first (negative control)

Write all the tests below against the current lexers, run them, and record
which fail. Every one of the new behaviour tests must fail; the controls pass.

**`deps/kotlinfamily_test.go`**
- Flip `shebang_plain`, `shebang_slash_star`, `shebang_brace` and
  `shebang_paren` to `{modelled, modelled, modelled}`. Their truth fields
  already hold the real lexer's reading and stay unchanged.
- Add rows that pin the probed rule. Their truth fields (`open`, `classes`,
  `anchors`, `tokens`, `comments`) come **from a real-lexer jshell dump**, in
  the existing rows' ktLex vocabulary, never from our lexers' output:
  - `shebang_unterminated`: `#!/usr/bin/env kotlin` with no newline. It stays
    code.
  - `shebang_indented`: ` #!/usr/bin/env kotlin\n// probe: a real comment\nval probe = 1\n`.
    Line 1 is code.
  - `shebang_second_line`: `#!/usr/bin/env kotlin\n#!x {\npackage p\nclass Actual\n// probe: a real comment\nval probe = 1\n`.
    Only line 1 is the header, and line 2's `{` is code.
  - `shebang_bom`: `﻿#!/usr/bin/env -S kotlin -J-Dtag={\npackage p\nclass Actual\n// probe: a real comment\nval probe = 1\n`.
    Its truth is the real lexer over the BOM-stripped text with offsets +3, as
    t1992's `KtFamily` builds the BOM row.

  `want` for all of them: `modelled` ×3.
- No lone-CR row. t1992's truth harness excludes lone CR (kotlinc normalises
  it), and the table cannot express "the compiler accepts it, every lexer
  refuses". The per-lexer tests below pin it instead.

**`deps/kotlin_test.go`**: new `TestKotlinShebang`, table-driven like
`TestKotlinStringContentIsNotSyntax`. Through `scanKotlin` it checks
`raw.Package`, the symbols and `Opaque`:
- the brace, paren and `/*` shebangs, then `package p\nclass Actual\n`: `p`,
  `[class:Actual]`, no opaque;
- BOM + brace shebang: the same;
- CRLF control `#!/x {\r\n// note\r\npackage p\r\nclass Actual\r\n`: the same,
  and the token lines are right (via `ktLex`: `package` on line 3, `Actual` on
  line 4);
- lone CR, fail closed: `#!/x {\r// note\rpackage p\rclass Actual\r`,
  `// note\rpackage p\rclass Actual\r` (no shebang: the pre-existing silent
  hide) and `package p\nclass Actual\r` (final lone CR): `Opaque` is
  `[untokenizable]` in each;
- controls: no shebang at all; and an unterminated `#!a {`, which stays code
  (no symbols, no opaque).

`deps/kotlinlex_test.go` `TestKotlinLexer`: add the lone-CR sources to the
`bad` list.

**`deps` kts blanker** (in the existing Gradle blanker test file):
`blankGradleComments(src, true)` returns `failAt >= 0` for the three lone-CR
sources, and `-1` for the CRLF control. The BOM and unterminated cases are
covered by the family rows. A Groovy-mode control (`kts=false`) checks that
`#!a\n#!b\n` still blanks both lines.

**`annot/lexctx_test.go` `TestClassifyKotlin`**: add `runLex` rows:
- `shebang-brace`: `#!/x {\npackage a\nimport b.C\n// real\nclass T\n`,
  classes `ccc#c`;
- `shebang-slash-star`: `#!/x -cp lib/*\n// real\n`, classes `c#`, certain
  (Uncertain today);
- `shebang-bom`: `﻿#!/x {\n// real\n`, classes `c#`;
- `shebang-crlf`: `#!/x {\r\n// note\r\npackage p\r\nclass T\r\n`, classes
  `c#cc`;
- `lone-cr`: `#!/x {\r// note\rpackage p\r`, Uncertain on line 1;
- `lone-cr-final`: `package p\n// note\r`, Uncertain on line 2.

Then add anchor asserts: the brace shebang gives `Package == 2`, `Import == 3`;
the `/*` shebang with a package line gives `Package == 2` and
`Uncertain == nil`; BOM + brace + package gives `Package == 2`; the CRLF row
gives `Package == 3`.

**`annot` ParseFile / annotation reading**, in `rewrite_test.go` or
`grammar_test.go`, wherever Kotlin `ParseFile` is exercised:
- `tests/S.kts` = `#!/usr/bin/env -S kotlin -cp lib/*\npackage p\nimport q.R\n// testmap:covers src/a.kt\nclass T\n`
  parses without error (a `SyntaxError` today), and its covers line is read;
- its CRLF twin parses and reads the same covers line;
- the lone-CR twin `…\r// testmap:covers src/a.kt\r…` returns a `SyntaxError`
  naming "lone carriage return", and it is never read as an annotation.

**`annot/testdata/placement/`**: new goldens, picked up automatically by
`TestPlacementGoldens` and `TestPlacementDiffIsCommentsOnly`, and so also by
`TestKotlinFamilyCorpus`. Each golden is hand-written from the rule, not
produced by `-update`:
- `kotlin_shebang.kts.in` = `#!/usr/bin/env -S kotlin -J-Dtag={\npackage app\n\nimport a.B\n\nclass T\n`.
  The golden inserts `// testmap:covers src/new @2026-10-12/aaaaaaaaaa` after
  `import a.B` (today it would go after line 1, since the `{` hides the
  anchors).
- `kotlin_shebang_bom.kts.in` = `﻿#!/x {\nprintln(1)\n` (no package, no
  import). The golden is `﻿#!/x {\n// testmap:covers src/new @2026-10-12/aaaaaaaaaa\nprintln(1)\n`:
  the BOM and the header are kept, and the block goes after the header. Today
  this is `ErrByteOrderMark`, because `fixedPosition` misses the header after
  the BOM.

### 3. Fix

**3a. `deps/kotlinlex.go`**
- In `ktLex`, check for a lone CR first: if one is found, return
  `nil, errUntokenizable`.
- Then call a new `l.shebang()` before `l.code(false)`:

```go
// shebang skips the script header: Kotlin.flex's SHEBANG_COMMENT is a #!
// line at offset 0, after the byte-order mark kotlinc strips, that a newline
// ends (one without a newline is code). The newline stays for code to count.
func (l *ktLexer) shebang() {
	i := len(l.src) - len(strings.TrimPrefix(l.src, "﻿"))
	if !strings.HasPrefix(l.src[i:], "#!") {
		return
	}
	if j := strings.IndexByte(l.src[i:], '\n'); j >= 0 {
		l.i = i + j
	}
}
```

- Put the lone-CR scan in one small `loneCR(s string) int` helper in `deps`. It
  returns the index or -1, and both `ktLex` and the kts blanker use it. Add
  `strings` to the imports.
- Extend the `ktLex` doc comment: the shebang is skipped, and a lone CR is
  refused because kotlinc reads it as a newline and no line rule here does.

**3b. `deps/gradlelex.go`, kts mode only**
- In `blankGradleComments`, `if kts`: a lone CR → `return src, at`.
- In `shebang()`, kts branch: skip a leading BOM first, and blank only when a
  `\n` ends the line, i.e. the same rule as ktLex. The Groovy path
  (`!l.kts`) stays byte-for-byte unchanged.

**3c. `annot/lexctx.go`**
- `Classify` passes `data` to `classifyKotlin`, as `classifyGo` gets it.
- At the start of `classifyKotlin`: if `data` holds a lone CR, return a Context
  with all lines `Literal` (`markRest` from 0) and
  `Uncertain{Line: <1 + '\n' count before it>, Construct: "lone carriage return"}`.
- Shebang: line 1 is the header when `ln[skip:]` starts with `#!` and its
  terminator exists, meaning `len(lines) > 1` or `data` ends in `\n`. In that
  case line 1's `from` becomes `len(ln)`, so nothing in the header reaches the
  brace, comment or string state. Its class stays `Code`: never `Comment`, so
  never an annotation. The package/import anchors cannot match it.
- Update the `kframe` / `classifyKotlin` comment.

**3d. `annot/rewrite.go` `fixedPosition`, Kotlin branch**: recognise the header
after the BOM. Use `strings.HasPrefix(f.Lines[0][bomLen(f.Lang, f.Lines):], "#!")`
instead of the raw `f.Lines[0]` prefix. Then a BOM + shebang file without
package/import places after line 1, and the `after == 0 && bomLen > 0`
`ErrByteOrderMark` guard no longer fires for it, while it still guards a BOM
file whose line 1 is code. The generic `leading` helper (bash/Python) is
unchanged: there a `#!` line is already a `Comment`-class line after the BOM.

**3e. `deps/cache.go`**: `schemaVersion` 13 → 14, because the ktLex and kts
output changed.

### 4. Green

The Step 2 tests all pass, the existing suites stay green, and the Groovy
control is unchanged.

## Verification

- `cd goengines && go vet ./... && go test ./internal/testmap/...`, then
  `ait engine test`.
- Negative control: the Step 2 failure list (recorded before Step 3) covers
  every new behaviour test.
- `TestKotlinFamilyCorpus` passes with the two new placement fixtures in its
  walk. `TestClassifyFingerprint` (bash only) is unaffected.
- Step 9 (Post-Implementation): commit the code (`bug: … (t2030)`), commit the
  plan via `aitask_task_commit.sh`, archive.

## Risk

### Code-health risk: low
- The kts change touches `gradleLexer.shebang` and `blankGradleComments`, which Groovy shares · severity: low · → mitigation: none (in-plan: the change is confined to `l.kts` / `kts` branches, and a Groovy control is added in Step 2)
- Lone-CR refusal is new behaviour outside the shebang (any lone-CR Kotlin file becomes opaque or Uncertain) · severity: low · → mitigation: none (it replaces a silent hide with fail-closed; exposure measured at 0/2051)
- `schemaVersion` bump: every cached entry is rescanned once · severity: low · → mitigation: none (required by the cache contract)

### Goal-achievement risk: low
- New-row truths derived from our own lexers would make the table circular · severity: low · → mitigation: none (in-plan: Step 2 takes every truth from a real-lexer dump, and the goldens are hand-written)
- BOM and lone-CR behaviour rests on compiler-level facts the lexer probe cannot show · severity: low · → mitigation: none (in-plan: Step 1 re-measures them and stops on a contradiction)
