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

## Implementation Evidence

Steps 1-7 and the post-phase are done. Every throwaway was created, run and
deleted in this session; its source and output are recorded below.

### Red proof (step 6, before the `lexctx.go` change)

`cd goengines && go test ./internal/testmap/annot/ -run 'TestClassifyKotlin|TestKotlinMultiDollar|TestApplyRefusesNonComments'`
exited 1. Pre-fix, `Apply` **wrote** line 9 of the desync fixture, `ParseFile`
read line 9 as a record, and the interpolation fixture was refused as Uncertain:

````text
--- FAIL: TestClassifyKotlin (0.00s)
    lexctx_test.go:195: kotlin/multidollar-comment-desync: classes "cc#ccLcL#cLL" uncertain <nil>, want "cc#cc#ccLLc#" uncertain line 0
    lexctx_test.go:195: kotlin/multidollar-interpolation: classes "cccccLL" uncertain &{Line:5 Construct:unterminated string}, want "ccccc#c" uncertain line 0
    lexctx_test.go:195: kotlin/multidollar-literal-brace: classes "cccccc#c" uncertain <nil>, want "cccLLc#c" uncertain line 0
    lexctx_test.go:195: kotlin/multidollar-quote-boundary: classes "cccLccLc#c" uncertain <nil>, want "ccccLLcL#c" uncertain line 0
    lexctx_test.go:195: kotlin/dollar-prefix-3: classes "cL" uncertain &{Line:1 Construct:raw string}, want "c#" uncertain line 0
    lexctx_test.go:195: kotlin/dollar-inside-template: classes "cc" uncertain &{Line:1 Construct:string}, want "c#" uncertain line 0
    lexctx_test.go:195: kotlin/dollar-prefix-restored: classes "cL" uncertain &{Line:1 Construct:raw string}, want "c#" uncertain line 0
    lexctx_test.go:195: kotlin/short-template-backticks: classes "cL" uncertain &{Line:1 Construct:block comment}, want "c#" uncertain line 0
    lexctx_test.go:195: kotlin/short-template-backticks-dollar: classes "cL" uncertain &{Line:1 Construct:block comment}, want "c#" uncertain line 0
--- FAIL: TestApplyRefusesNonComments (0.00s)
    rewrite_test.go:289: tests/dollar.kt line 9: got <nil>, want not a comment annotation line
    rewrite_test.go:292: tests/dollar.kt written
--- FAIL: TestKotlinMultiDollar (0.00s)
    rewrite_test.go:325: multidollar_comment_desync: records ["line=3 member= value=app/real.kt stamped=false docstring=false" "line=9 member= value=app/fake.kt stamped=false docstring=false"], want ["line=3 member= value=app/real.kt stamped=false docstring=false"]
    rewrite_test.go:313: multidollar_interpolation: tests/multidollar_interpolation.kt:5: cannot determine comment context: unterminated string
FAIL
FAIL	github.com/beyondeye/aitasks/goengines/internal/testmap/annot	0.002s
FAIL
````

Post-fix the same command passes. Four new rows (`dollar-run-longer`,
`dollar-run-before-close`, `short-template-below-prefix`,
`short-template-unclosed-backtick`) already passed pre-fix. That is expected:
they guard against *wrong* models, such as one that treats a short run as a
template or skips a backticked name below the prefix.

### Real-lexer differential (step 6)

**Rows:** read from the test source itself, not retyped. A throwaway
`goengines/internal/testmap/annot/zz_lexdump_test.go` (sha256
`2839bdaed4da3362e611ca91241e128ef6c200f4cb4f0b1ecec2df9c2faaeffa`) parses
`lexctx_test.go` with go/parser and evaluates every `TestClassifyKotlin` row
(string literals, `+`, `kl`, the `ktDollar*` constants). It writes
`name \t base64(src) \t want \t uncertain`:

````go
package annot

// THROWAWAY (t1990): dumps every TestClassifyKotlin row, read from the test
// source itself, for the KotlinLexer differential. Deleted after use.

import (
	"encoding/base64"
	"fmt"
	"go/ast"
	goparser "go/parser"
	"go/token"
	"os"
	"strconv"
	"strings"
	"testing"
)

func TestZZDumpKotlinRows(t *testing.T) {
	out := os.Getenv("T1990_DUMP")
	if out == "" {
		t.Skip("T1990_DUMP unset")
	}
	vals := map[string]string{
		"kl":                    strings.Replace(look, "#", "//", 1),
		"look":                  look,
		"ktDollarDesync":        ktDollarDesync,
		"ktDollarInterpolation": ktDollarInterpolation,
		"ktDollarLiteralBrace":  ktDollarLiteralBrace,
		"ktDollarQuoteBoundary": ktDollarQuoteBoundary,
	}
	var eval func(e ast.Expr) string
	eval = func(e ast.Expr) string {
		switch x := e.(type) {
		case *ast.BasicLit:
			s, err := strconv.Unquote(x.Value)
			if err != nil {
				t.Fatal(err)
			}
			return s
		case *ast.Ident:
			v, ok := vals[x.Name]
			if !ok {
				t.Fatalf("unknown identifier %s", x.Name)
			}
			return v
		case *ast.BinaryExpr:
			if x.Op != token.ADD {
				t.Fatalf("operator %s", x.Op)
			}
			return eval(x.X) + eval(x.Y)
		case *ast.ParenExpr:
			return eval(x.X)
		}
		t.Fatalf("unsupported %T", e)
		return ""
	}
	f, err := goparser.ParseFile(token.NewFileSet(), "lexctx_test.go", nil, 0)
	if err != nil {
		t.Fatal(err)
	}
	var b strings.Builder
	n := 0
	for _, d := range f.Decls {
		fd, ok := d.(*ast.FuncDecl)
		if !ok || fd.Name.Name != "TestClassifyKotlin" {
			continue
		}
		ast.Inspect(fd, func(nd ast.Node) bool {
			cl, ok := nd.(*ast.CompositeLit)
			if !ok {
				return true
			}
			at, ok := cl.Type.(*ast.ArrayType)
			if !ok || fmt.Sprint(at.Elt) != "lexCase" {
				return true
			}
			for _, el := range cl.Elts {
				r := el.(*ast.CompositeLit).Elts
				name, src, want := eval(r[0]), eval(r[1]), eval(r[2])
				unc := r[3].(*ast.BasicLit).Value
				fmt.Fprintf(&b, "%s\t%s\t%s\t%s\n", name,
					base64.StdEncoding.EncodeToString([]byte(src)), want, unc)
				n++
			}
			return false
		})
	}
	if err := os.WriteFile(out, []byte(b.String()), 0o644); err != nil {
		t.Fatal(err)
	}
	t.Logf("dumped %d rows", n)
}
````

**Adapter:** `KtAdapter.java` (sha256
`3cc23e50453ac82bdb11ca2a0686ec218aac8cc5e852e53ab43f9c0937a8cc04`) implements
the step-6 contract:
- BOM stripped;
- unclosed strings, templates and comments tracked;
- uncertainty compared separately from class strings.

````java
// KtAdapter.java (t1990) - KotlinLexer differential for TestClassifyKotlin.
// Reads the rows dumped by zz_lexdump_test.go (name \t base64(src) \t want \t
// uncertain) and adapts the real lexer's tokens to runLex's contract:
// classes c/#/L per line when certain, else the uncertain line.
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Deque;
import java.util.List;
import org.jetbrains.kotlin.com.intellij.psi.tree.IElementType;
import org.jetbrains.kotlin.lexer.KotlinLexer;
import org.jetbrains.kotlin.lexer.KtTokens;

public class KtAdapter {
  record Tok(IElementType type, int start, int end) {}
  record Frame(char kind, int line) {}
  record Result(String classes, int uncertain, List<String> notes, List<Tok> toks) {}

  static int[] starts; // 0-based offset of each line

  static int lineOf(int off) { // 1-based
    int lo = 0, hi = starts.length - 1;
    while (lo < hi) {
      int mid = (lo + hi + 1) / 2;
      if (starts[mid] <= off) lo = mid; else hi = mid - 1;
    }
    return lo + 1;
  }

  // closed reports a block/doc comment token whose own nesting returns to 0.
  static boolean closed(String t) {
    int depth = 0;
    for (int i = 0; i < t.length(); ) {
      if (t.startsWith("/*", i)) { depth++; i += 2; }
      else if (t.startsWith("*/", i) && depth > 0) { depth--; i += 2; if (depth == 0) return i == t.length(); }
      else i++;
    }
    return false;
  }

  static Result adapt(String src) {
    if (src.indexOf('\r') >= 0) throw new IllegalArgumentException("CR in input");
    if (src.startsWith("﻿")) src = src.substring(1); // as bomLen(Kotlin) and kotlinc
    String body = src.endsWith("\n") ? src.substring(0, src.length() - 1) : src;
    String[] lines = src.isEmpty() ? new String[0] : body.split("\n", -1);
    starts = new int[lines.length];
    for (int i = 1, off = 0; i < lines.length; i++) { off += lines[i - 1].length() + 1; starts[i] = off; }
    List<Tok> toks = new ArrayList<>();
    KotlinLexer lx = new KotlinLexer();
    lx.start(src);
    while (lx.getTokenType() != null) { toks.add(new Tok(lx.getTokenType(), lx.getTokenStart(), lx.getTokenEnd())); lx.advance(); }

    char[] start = new char[lines.length]; // L, c (template), E (empty stack: # or c)
    IElementType[] first = new IElementType[lines.length];
    List<String> notes = new ArrayList<>();
    Deque<Frame> stack = new ArrayDeque<>(); // push/peek at the head = innermost
    int unclosedComment = 0;
    if (lines.length > 0) start[0] = 'E';
    for (Tok t : toks) {
      int ln = lineOf(t.start);
      if (t.type != KtTokens.WHITE_SPACE && first[ln - 1] == null && t.start >= starts[ln - 1]) first[ln - 1] = t.type;
      if (t.type.toString().equals("BAD_CHARACTER")) notes.add("BAD_CHARACTER@" + ln + ":" + src.substring(t.start, t.end));
      if (t.type == KtTokens.DANGLING_NEWLINE) {
        return new Result(null, stack.peek().line, notes, toks); // innermost string's line
      }
      if ((t.type == KtTokens.BLOCK_COMMENT || t.type == KtTokens.DOC_COMMENT) && !closed(src.substring(t.start, t.end))) {
        unclosedComment = ln;
      }
      for (int o = t.start; o < t.end; o++) {
        if (src.charAt(o) != '\n') continue;
        int next = lineOf(o + 1);
        if (o + 1 >= src.length() || starts[next - 1] != o + 1) continue; // final newline
        char s;
        if (t.type == KtTokens.REGULAR_STRING_PART || t.type == KtTokens.BLOCK_COMMENT || t.type == KtTokens.DOC_COMMENT) s = 'L';
        else if (t.type == KtTokens.WHITE_SPACE) s = stack.isEmpty() ? 'E' : (stack.peek().kind == 't' ? 'c' : '?');
        else { s = '?'; notes.add("newline in " + t.type + "@" + next); }
        start[next - 1] = s;
      }
      if (t.type == KtTokens.OPEN_QUOTE) stack.push(new Frame('s', ln));
      else if (t.type == KtTokens.LONG_TEMPLATE_ENTRY_START) stack.push(new Frame('t', ln));
      else if (t.type == KtTokens.CLOSING_QUOTE || t.type == KtTokens.LONG_TEMPLATE_ENTRY_END) {
        char want = t.type == KtTokens.CLOSING_QUOTE ? 's' : 't';
        if (stack.isEmpty() || stack.peek().kind != want) notes.add("unbalanced " + t.type + "@" + ln);
        else stack.pop();
      }
    }
    if (!stack.isEmpty()) return new Result(null, stack.peekLast().line, notes, toks); // outermost
    if (unclosedComment != 0) return new Result(null, unclosedComment, notes, toks);
    StringBuilder b = new StringBuilder();
    for (int i = 0; i < lines.length; i++) {
      char s = start[i];
      if (s == 'E') s = first[i] == KtTokens.EOL_COMMENT ? '#' : 'c';
      b.append(s);
    }
    return new Result(b.toString(), 0, notes, toks);
  }

  public static void main(String[] args) throws Exception {
    int match = 0, mismatch = 0;
    for (String row : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
      String[] f = row.split("\t", -1);
      String name = f[0], src = new String(Base64.getDecoder().decode(f[1]), StandardCharsets.UTF_8), want = f[2];
      int wantU = Integer.parseInt(f[3]);
      Result r = adapt(src);
      boolean ok = wantU != 0 ? r.uncertain == wantU : (r.uncertain == 0 && want.equals(r.classes));
      String got = r.uncertain != 0 ? "uncertain line " + r.uncertain : "classes " + r.classes;
      String exp = wantU != 0 ? "uncertain line " + wantU : "classes " + want;
      System.out.printf("%-8s %-34s got %-22s want %s%s%n", ok ? "MATCH" : "MISMATCH", name, got, exp,
          r.notes.isEmpty() ? "" : "  notes=" + r.notes);
      if (ok) match++; else {
        mismatch++;
        StringBuilder d = new StringBuilder("    tokens:");
        String lexed = src.startsWith("\uFEFF") ? src.substring(1) : src;
        for (Tok t : r.toks) d.append(' ').append(t.type).append('[').append(lexed.substring(t.start, t.end).replace("\n", "\\n")).append(']');
        System.out.println(d);
      }
    }
    System.out.printf("TOTAL match=%d mismatch=%d lexer=%s%n", match, mismatch,
        org.jetbrains.kotlin.config.KotlinCompilerVersion.VERSION);
  }
}
````

**Command:**

````sh
T1990_DUMP=$S/rows.tsv go test ./internal/testmap/annot/ -run TestZZDumpKotlinRows -v
L=$(ls -d ~/.gradle/wrapper/dists/gradle-9.5.1-bin/*/gradle-9.5.1/lib)
java -cp "$L/kotlin-compiler-embeddable-2.3.20.jar:$L/kotlin-stdlib-2.3.20.jar" KtAdapter.java rows.tsv
````

**Result:** all 20 rows match. That covers the 7 existing rows, including
`bom-comment` → `#c` and `unterminated-raw` → uncertain line 1, and the 13
new ones. There was no disagreement, so nothing to triage.

````text
MATCH    plain                              got classes cc#c           want classes cc#c
MATCH    raw                                got classes cLLL#          want classes cLLL#
MATCH    block-nested                       got classes cLL#           want classes cLL#
MATCH    slashes-in-string                  got classes c#             want classes c#
MATCH    template-string                    got classes c#             want classes c#
MATCH    unterminated-raw                   got uncertain line 1       want uncertain line 1
MATCH    bom-comment                        got classes #c             want classes #c
MATCH    multidollar-comment-desync         got classes cc#cc#ccLLc#   want classes cc#cc#ccLLc#
MATCH    multidollar-interpolation          got classes ccccc#c        want classes ccccc#c
MATCH    multidollar-literal-brace          got classes cccLLc#c       want classes cccLLc#c
MATCH    multidollar-quote-boundary         got classes ccccLLcL#c     want classes ccccLLcL#c
MATCH    dollar-prefix-3                    got classes c#             want classes c#
MATCH    dollar-run-longer                  got classes cLL#           want classes cLL#
MATCH    dollar-run-before-close            got classes c#             want classes c#
MATCH    dollar-inside-template             got classes c#             want classes c#
MATCH    dollar-prefix-restored             got classes c#             want classes c#
MATCH    short-template-backticks           got classes c#             want classes c#
MATCH    short-template-backticks-dollar    got classes c#             want classes c#
MATCH    short-template-below-prefix        got classes c#             want classes c#
MATCH    short-template-unclosed-backtick   got classes c#             want classes c#
TOTAL match=20 mismatch=0 lexer=2.3.20
````

**Negative control.** Two rows were fed with the pre-fix classifier's output
as their `want` (desync `cc#ccLcL#cLL`, backticks `cL`). The adapter rejects
both:

````text
MISMATCH multidollar-comment-desync         got classes cc#cc#ccLLc#   want classes cc#ccLcL#cLL
    tokens: package[package] WHITE_SPACE[ ] IDENTIFIER[app] WHITE_SPACE[\n\n] EOL_COMMENT[// testmap:covers app/real.kt] WHITE_SPACE[\n] fun[fun] WHITE_SPACE[ ] IDENTIFIER[f] LPAR[(] RPAR[)] WHITE_SPA
MISMATCH short-template-backticks           got classes c#             want classes cL
    tokens: val[val] WHITE_SPACE[ ] IDENTIFIER[s] WHITE_SPACE[ ] EQ[=] WHITE_SPACE[ ] OPEN_QUOTE["] SHORT_TEMPLATE_ENTRY_START[$] IDENTIFIER[`x"/*`] CLOSING_QUOTE["] WHITE_SPACE[\n] EOL_COMMENT[// rea
TOTAL match=0 mismatch=2 lexer=2.3.20
````

### Post-phase [kotlin_realrepo_class_parity]

**Inputs:** the Kotlin files of every registered repository, archived at its
HEAD commit (`git ls-tree` + `git archive`, so a commit snapshot and not the
live tree): 2051 `.kt`/`.kts` files.

````text
aitasks_go e0e3862be98a0fc2d8d977f4dfa42db20104660f kt=0
timexchange c60e7e05a46550034197b0051ae851eb193a1764 kt=970
teamim 18a4679d1c108eee54063c3b40a6867c55168760 kt=37
thinking_app 33b7fcd4923df066b4f7d7753dafbd4d22900cd8 kt=784
thinking_backend cba7d8aab541d2dd595cc3b6526f13c95ae3bb56 kt=0
aitasks 4940de5dc18ff776087154a4a3f10827f7f08bc4 kt=0
aitasks_mobile 75f4543fb70e90baa8661404505017887d3602c1 kt=260
animeless 75365c1fec1e9cd7fb27d6d5a8ce983173298d02 kt=0
````

**Harness:** a throwaway `zz_parity_test.go` (sha256
`5fa273be88fb677e0328373adea5e848b5f9527221ff38302682a3972c45e84d`). Its test
function, verbatim:

````go
package annot

// THROWAWAY (t1990): HEAD's Kotlin classifier, renamed, vs the current one over
// the files listed in $T1990_PARITY. Deleted after use.

import (
	"fmt"
	"os"
	"strings"
	"testing"
)

func TestZZKotlinParity(t *testing.T) {
	list := os.Getenv("T1990_PARITY")
	if list == "" {
		t.Skip("T1990_PARITY unset")
	}
	data, err := os.ReadFile(list)
	if err != nil {
		t.Fatal(err)
	}
	files, diff, uncertain := 0, 0, 0
	for _, p := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		src, err := os.ReadFile(p)
		if err != nil {
			t.Fatal(err)
		}
		lines := splitLines(src)
		o, n := classifyKotlinOld(lines), classifyKotlin(lines)
		files++
		if n.Uncertain != nil {
			uncertain++
		}
		ou, nu := "", ""
		if o.Uncertain != nil {
			ou = fmt.Sprintf("%s@%d", o.Uncertain.Construct, o.Uncertain.Line)
		}
		if n.Uncertain != nil {
			nu = fmt.Sprintf("%s@%d", n.Uncertain.Construct, n.Uncertain.Line)
		}
		if classes(o) != classes(n) || ou != nu || o.Package != n.Package || o.Import != n.Import {
			diff++
			t.Logf("DIFF %s: old %q %q pkg %d imp %d / new %q %q pkg %d imp %d", p, classes(o), ou, o.Package, o.Import, classes(n), nu, n.Package, n.Import)
		}
	}
	t.Logf("PARITY files=%d differing=%d uncertain_new=%d", files, diff, uncertain)
}

````

The rest of the file is HEAD's Kotlin section with three names changed. It was
generated by:

````sh
git show HEAD:goengines/internal/testmap/annot/lexctx.go | sed -n '/^\/\/ -* Kotlin$/,$p' \
  | sed 's/\bkframe\b/kframeOld/g; s/\bclassifyKotlin\b/classifyKotlinOld/g; s/\bskipKotlinChar\b/skipKotlinCharOld/g'
````

That section is byte-identical to the generator's output: both hash to
`a5856a6a5db5fa17efdfe81225167b65d4632259f9ee83b9b6fd363fdd447895`. Its source
is the last commit to `lexctx.go`, `5d54b9170fadf970465ead0957a470ec805c4a41`;
HEAD was `4940de5dc` at the time.

**Result:** 0 differences.

````text
    zz_parity_test.go:46: PARITY files=2051 differing=0 uncertain_new=0
--- PASS: TestZZKotlinParity (0.09s)
PASS
ok  	github.com/beyondeye/aitasks/goengines/internal/testmap/annot	0.093s
````

**Negative control.** Run on the four corpus fixtures plus
`` val s = "$`x"/*`" ``, the harness reports all five:

````text
    zz_parity_test.go:43: DIFF ctrl/backtick.kt: old "cL" "block comment@1" pkg 0 imp 0 / new "c#" "" pkg 0 imp 0
    zz_parity_test.go:43: DIFF ctrl/multidollar_comment_desync.kt: old "cc#ccLcL#cLL" "" pkg 1 imp 0 / new "cc#cc#ccLLc#" "" pkg 1 imp 0
    zz_parity_test.go:43: DIFF ctrl/multidollar_interpolation.kt: old "cccccLL" "unterminated string@5" pkg 1 imp 0 / new "ccccc#c" "" pkg 1 imp 0
    zz_parity_test.go:43: DIFF ctrl/multidollar_literal_brace.kt: old "cccccc#c" "" pkg 1 imp 0 / new "cccLLc#c" "" pkg 1 imp 0
    zz_parity_test.go:43: DIFF ctrl/multidollar_quote_boundary.kt: old "cccLccLc#c" "" pkg 1 imp 0 / new "ccccLLcL#c" "" pkg 1 imp 0
    zz_parity_test.go:46: PARITY files=5 differing=5 uncertain_new=0
````

Both throwaway `_test.go` files were deleted. `git status` shows only
`lexctx.go`, `lexctx_test.go` and `rewrite_test.go` as this task's changes.

### Suite

`go vet` is clean for annot, deps and cmd/ait-testmap. `go test -count=1 ./...`
in `goengines` passes, and `gofmt -l` is clean.

## Final Implementation Notes
- **Actual work done:** `classifyKotlin` (`annot/lexctx.go`) now models Kotlin 2.2
  multi-dollar strings exactly, per Kotlin.flex:
  - a `$`-run before an opening `"`/`"""` in code or in a template sets the
    frame's `dollars` prefix to `max(run, 1)`;
  - inside `'s'`/`'r'` frames, the new `kotlinDollars` opens a template only on a
    `$`-run ≥ prefix followed by `{`. The last n dollars start it and any
    excess before them is text;
  - it skips a backticked short-template name (`` $`name` ``) when the run is
    ≥ prefix, because the name may hold quotes;
  - a shorter run, or one before anything else, is text.

  `kframe` gained `dollars`. Tests:
  - `TestClassifyKotlin` +13 rows: the 4 corpus fixtures as `ktDollar*`
    constants, prefix 3, a longer run, a run before the close, prefix
    restoration across nested frames, and the backticked short-template forms;
  - new `TestKotlinMultiDollar`: the `.expect` read lists through `ParseFile`,
    comparing the full record (line, member, value, stamped, docstring);
  - `TestApplyRefusesNonComments` + the corpus `.edits` case (Replace line 9
    → `ErrNotComment`, file unchanged).
- **Deviations from plan:** two cosmetic ones.
  - The desync fixture's key in `TestApplyRefusesNonComments` is
    `tests/multi.kt`, not the `tests/dollar.kt` shown in the red-proof output.
    The 15-character key made gofmt re-pad the whole existing map (15 lines of
    churn); the 14-character key keeps the diff additive.
  - The optional research matrix rerun was not done. The inlined fixtures, the
    real-lexer differential and the parity check cover the same cases.
- **Issues encountered:** plan review found that a raw `KotlinLexer` token dump
  does not match the `runLex` contract:
  - the BOM is lexed as `BAD_CHARACTER`;
  - an unterminated raw string reaches EOF with no error token;
  - an unclosed nested comment ends in `*/`.

  The adapter in the evidence section handles all three. All 20 rows matched
  on the first run, so nothing needed triage.
- **Key decisions:** model rather than fail closed. An Uncertain context makes
  `ParseFile` return a `SyntaxError` for any file carrying `testmap:`, and
  `ScanAnnotations` (`annot/source.go:54-60`) propagates it. Failing closed
  would therefore fail the **whole scan** as soon as one annotated Kotlin test
  file used `$$"`. That is far costlier than `deps`' per-file opaque reason
  (t1980). The backticked short template is part of the same
  `SHORT_TEMPLATE_ENTRY` rule, so it is modelled too. For ordinary (n = 1)
  strings this is the only behaviour change, and parity over 2051 real files
  shows no file affected.
- **Upstream defects identified:**
  - `goengines/internal/testmap/deps/kotlinlex.go:223-233` — `ktLexer.str()` does
    not model the `` $`name` `` short template (Kotlin.flex
    `SHORT_TEMPLATE_ENTRY` with an `ESCAPED_IDENTIFIER`). A backticked name holding
    quotes closes the string early. The probe
    ``val `q"""` = 1`` / ``val s = """$`q"""`""" + """`/*"""`` /
    `fun f() = Callee()` / `val t = 1 // */` makes `ktLex` return `err=nil` and
    silently drop the names `f`, `Callee` and `t`, which the 2.3.20 `KotlinLexer`
    keeps. Not checked:
    - whether kotlinc accepts a quote-bearing backticked name on JVM;
    - whether `gradlelex.go`'s kts mode has the same gap.
