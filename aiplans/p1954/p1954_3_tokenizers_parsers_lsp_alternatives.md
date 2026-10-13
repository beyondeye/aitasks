---
Task: t1954_3_tokenizers_parsers_lsp_alternatives.md
Parent Task: aitasks/t1954_research_multilanguage_annotation_parsers.md
Sibling Tasks: aitasks/t1954/t1954_1_*.md, aitasks/t1954/t1954_2_*.md, aitasks/t1954/t1954_4_*.md
Archived Sibling Plans: aiplans/archived/p1954/p1954_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-13 22:44
---

# Plan: t1954_3 — Tokenizers, language parsers, external providers, alternatives

## Context

Third child of t1954. It evaluates every candidate family that is not Tree-sitter
on the landed harness (`R = aidocs/testing_engine/t1954_parser_research/`). The
shared design in `aiplans/p1954_research_multilanguage_annotation_parsers.md` is
authoritative. Results feed t1954_4's report and recommendation. Engine
constraints: CGO-free on 4 targets, offline, a dependency allowlist, and `scan`
under 300 ms. A provider that needs a runtime the engine does not ship is
evaluated **and costed**, not assumed out.

## Verification of this plan (2026-10-13, at pick time)

Checked against the landed harness (t1954_1 at 5e730b0fb, t1954_2 at a2395c309),
both archived plans, `R/results/feasibility.md` and the 4 inbox notes
(acknowledged). The plan stands with these corrections, folded into the steps:

- **mvdan/sh and pytokenize are already full providers** (t1954_1:
  `provider/shfmt.go`, `provider/pytokenize.go`, `matrix_shfmt.md`,
  `matrix_pytokenize.md`, bench and footprint rows). Step 3 does not rebuild
  them. It cites and analyses them in the findings: the bash-dialect limits
  (10/1,620 real files refused, the FP-writable `<<-` continuation case, the
  unterminated heredoc in backticks) and the subprocess cost of pytokenize.
- **The harness extension points exist:** `register()` in `provider/registry.go`;
  `bench --subjects/--lex-subjects/--title/--out`; `extraVerbs`; and `realrepo
  --provider … --out <dir>`. `footprintProbes` is still a hardcoded list (step 10
  adds a filter). `matrix` writes the combined `matrix.md` only for `--provider
  all`, which needs the full-tag tree-sitter build (zig, `.tswasm`). Because
  step 2 grows the corpus, step 10 regenerates every subject's matrix, including
  `matrix.md`, from one full-tag binary. If that build cannot be produced, it
  falls back to a separate, labelled combined table.
- **The `tsx` Lang exists** (`provider/langs.go`). Every multi-language provider
  lists and handles `tsx`.
- **Versions (read-only `gh api`, today):**
  - Chroma: v2.27.0 is the latest v2. v3.0.0-alpha.5 is a pre-release on a new
    module path, recorded but not used.
  - Pygments: latest 2.21.0; the framework venv has 2.19.2.
  - ANTLR tool: 4.13.2. The Go runtime `antlr4-go/antlr` is v4.13.1, last pushed
    2024-06, so the tool is pinned to **4.13.1** to match the runtime.
  - The rest:
    - mvdan/sh v3.14.1; shiki 4.5.0; vscode-textmate 9.3.2;
    - pyright 1.1.414; typescript-language-server 6.0.2;
    - universal-ctags 6.2.1; difftastic 0.71.0; scc 4.1.0; tokei 15.0.0;
      semgrep 1.180.0;
    - srcML 1.1.0; tree-sitter-language-pack 1.22.1;
    - highlight.js 11.12.0; Prism 1.30.0;
    - ktlint 1.8.0; detekt 1.23.8; gpython v0.2.0 (2023).
- **Kotlin LSP:** fwcd/kotlin-language-server's README declares it deprecated in
  favour of the official **Kotlin/kotlin-lsp** (Apache-2.0, v263.6379.0,
  2026-10-03). The experiment runs kotlin-lsp. fwcd is documented, not run.
- **grammars-v4 Go targets:**
  - `kotlin/kotlin` has a target-neutral lexer (no base class).
  - `java/java` has a target-neutral lexer; only the parser has a Go base.
  - `rust` ships a Go `RustLexerBase`.
  - **`javascript/typescript` has no Go target** (only CSharp/Cpp/Java/TypeScript
    bases). Generating a TypeScript lexer would therefore mean writing a
    hand-written Go base class, which is itself a finding about per-language
    maintenance.
  - ANTLR prototypes: **Kotlin, Java, Rust**.
- **Most new providers report positions in something other than bytes, and the
  corpus cannot catch a wrong conversion today** (user plan review, verified):
  - The seam needs original-source **byte** offsets, but:
    - ANTLR's Go runtime indexes runes;
    - Pygments' `get_tokens_unprocessed` gives `str` (code-point) indices
      (probe: a comment after `é` is at character 7, byte 8);
    - the Kotlin PSI and LSP default to UTF-16 code units, as do vscode-textmate
      (per line) and the JVM generally;
    - `ts_oracle.js` already converts UTF-16 → bytes.
  - Only `corpus/python/` has non-ASCII `.in` files (4; the go/bash BOM cases
    aside). Kotlin, Java, Rust, Swift and TypeScript have **none**, so every
    range check would pass on ASCII alone while a conversion bug went unseen.
  - Fixed by step 2 (new fixtures) and by the per-provider conversion contract
    under Steps.
- **A `tsnative` provider would be scored against itself** (user plan review,
  verified):
  - `internal/oracle/oracle.go` already serves the TS/TSX/JS reference from
    `oracle/ts_oracle.js` under the name `ts-parser`.
  - `internal/runner/range.go:61` labels "provider is the oracle" only when
    `name == s.Name`.
  - So a provider wrapping the same extraction would be reported as an
    independent "vs ts-parser" pass.
  - Fixed in step 5 (a shared-provenance label, plus independent hand-checked
    expectations for its anchors).
- **An LSP experiment can mistake setup failure for "no comment support"**
  (user plan review, verified against the servers' documentation):
  - gopls serves semantic tokens only when its `semanticTokens` setting is on
    (default off);
  - every server needs `initialized` and answers to its own requests
    (`workspace/configuration`, `client/registerCapability`,
    `window/workDoneProgress/create`);
  - a bare directory of copied fixtures is not a loaded project.
  - Fixed in step 7 (protocol lifecycle, negotiation, per-server project,
    per-feature controls, a separate outcome vocabulary).
- **Adding fixtures invalidates the committed matrices of the existing
  subjects.** Step 10 therefore regenerates every subject's matrix from one
  binary over the new corpus, including the full-tag tree-sitter subjects when
  their toolchain (C compiler, zig, `.tsref`) is available, and `matrix.md` with
  `--provider all`. A subject that cannot be rebuilt keeps its old file,
  labelled with the corpus size it was measured on.
- **Local tools:**
  - present: go 1.27, java/javac 21, node 25/npm, docker, gh, tree-sitter CLI,
    and python3 (the framework venv, with pygments 2.19.2);
  - absent: gopls, pyright, ts-language-server, kotlin-lsp, ctags, semgrep,
    difft, scc, tokei, srcml, zig.
  - Every external tool is installed into the session scratch dir, never
    system-wide. A tool that cannot be obtained is reported "not measured".
- **The sidecar alternative can be measured cheaply.** `registry.AnnotationSource`
  (`.baseline/goengines/internal/testmap/registry/inputs.go`) is a one-method
  interface returning `[]FileAnnotations{Path, Units{Member, Line, Covers}}`. A
  sidecar-backed implementation can drive the real `registry.Scan` at the pinned
  snapshot.
- **The existing `oracle/ts_oracle.js` already returns parser-aware comment
  ranges and `getSyntacticDiagnostics`.** That makes a native TS/JS provider
  (`tsnative`) cheap. It covers "established parsers for additional target
  languages" on the same footing as pytokenize.

## Steps

Every provider: `provider/<name>.go` + `register`, `Langs()` listing exactly what
it serves (including `tsx` where applicable), honest `Capabilities`, and
`Analyze` returning an error (→ `unsupported`) when its runtime is absent. A
subprocess provider follows the `pytokenize` pattern: one long-lived process,
JSON lines, base64 source, and an `io.Closer`.

**Position-conversion contract (every new adapter):**
- Every `Span`, `Diag` and `DocLiteral` offset handed to `ToContext` is a byte
  offset into the **original** `src`. The conversion happens once, in the
  provider (or in its helper before JSON), from the unit the tool reports:

  | tool | reports | conversion |
  |---|---|---|
  | ANTLR Go | runes | rune index → byte, via a prefix table over `src` |
  | Pygments | `str` code points of the decoded text | code point → byte under the **same codec** the helper decoded with (UTF-8, BOM-stripped, or a PEP 263 cookie such as Latin-1) |
  | Kotlin PSI (JVM) | UTF-16 code units | UTF-16 → byte |
  | vscode-textmate | per-line UTF-16 | per line, UTF-16 → byte |
  | LSP | the negotiated `positionEncoding` (`utf-8` preferred, else UTF-16) | line/character → byte |
  | Chroma | token value strings | accumulate `len(value)` |

- A helper that decodes bytes into text records the codec it used. Bytes that
  do not decode make the analysis fail, so the result is `unsupported`; it never
  guesses.
- One shared Go helper (`provider/offsets.go`: rune / UTF-16 / line-column →
  byte) has a unit test on hand-computed offsets for 2-, 3- and 4-byte
  characters, the last including a surrogate pair. Helpers outside Go (Python,
  JS, Java) convert with the same rule and are checked by the step 2 fixtures.
- **Two layers: raw tokens are validated, construct-level spans go to the
  seam** (user plan review, verified):
  - The first finding was the fragment case. Highlighter and lexer tokens are
    often legitimate fragments: Pygments splits `x = "abc"` into `"`, `abc`,
    `"`.
  - The second finding is the one that breaks classing. Pygments splits
    `x = """a\n# no\nb"""` at every newline, so the continuation line `# no`
    starts exactly at a fragment boundary (offset 9), and
    `provider/adapter.go:154` `insideData` (strict `s.Start < off` for String
    spans) would class it Code.
  - `ToContext` is **not** changed, because that would alter every t1954_1/2
    result.
  - **Layer 1, raw-token validation** (`provider/tokencheck.go`, shared). Every
    helper returns each token's text as **original-codec bytes** (base64;
    Pygments re-encodes with the codec it decoded with). For **every emitted
    token**, independently of completeness, the check requires:
    - `src[start:end] == text`;
    - in bounds;
    - sorted and non-overlapping.

    A violation is an **adapter conversion failure**: the analysis fails, the
    failure is listed apart in the findings, and it is never scored as a
    candidate deficiency.
  - **Completeness is conditional, and gaps are explained, not failed:**
    - **Total tokenisers** (Chroma, Pygments, TextMate) document that every
      input byte becomes a token, an unmatched character included (as an
      `Error` token). For them, a gap is an adapter failure.
    - **ANTLR:** `BaseLexer.safeMatch` (v4.13.1 `lexer.go:166-177`) reports a
      recognition error, calls `Recover` and returns `LexerSkip`, so the
      offending character yields no token. A grammar `-> skip` rule also omits
      tokens. Every gap is therefore classified:
      - a gap starting at a recorded recognition error → **a Diag**, kept, so
        that the row is scored as uncertain/refused (refusal evidence
        preserved, never turned into `unsupported`);
      - a gap in a grammar that declares skip rules, with no Diag →
        **documented omission** (a candidate coverage limitation, noted);
      - any other gap → adapter failure.

      A full partition is required only when `FullCover` is declared (a
      grammar with no skip rules) **and** the input produced no Diags.
  - **Layer 2, construct-level spans for the seam** (`provider/coalesce.go`,
    shared). Validated raw tokens are normalised into the representation
    `ToContext` expects, one span per construct:
    - **Literal runs:** a maximal run of contiguous String-family tokens is one
      String (or Heredoc) span. Interpolations are absorbed, following
      t1954_2's "data across the whole range, interpolations included":
      - Chroma and Pygments: an Interpol token ending in an opener (`${`, `#{`,
        `\(`, `{`) opens a nesting count, a closing Interpol token closes it,
        and the tokens in between belong to the run;
      - TextMate: a token is literal when any scope in its stack starts with
        `string.`, which covers template expressions natively;
      - ANTLR: a per-grammar table of opener and closer token types (Kotlin
        `QUOTE_OPEN`/`TRIPLE_QUOTE_OPEN` … `QUOTE_CLOSE`/`TRIPLE_QUOTE_CLOSE`,
        names from the pinned `.g4`). Java and Rust literals are single tokens.
    - **Block comments:** contiguous `Comment.Multiline`/`Special`/`Preproc`
      fragments are merged into one BlockComment.
    - **Line comments:** contiguous line-comment fragments are merged, never
      across a newline.
    - A genuine construct start is unaffected: a literal that opens at a line
      start still has `Start == lineStart` and keeps that line's class.
  - **Delimiter and leader shape is not an adapter check.** It stays the
    runner's existing range metric ("a line-comment span starts with the
    leader and ends at end of line"). That metric applies to construct-level
    comment spans, and a failure there is a **candidate classification
    defect**, scored in the matrix.

**Capability-declaration rule for highlighters (Chroma, Pygments, TextMate):**
- `Errors` is declared only when the library has an error-token mechanism that
  the provider maps to `Diags` (Chroma `Error`, Pygments `Token.Error`). The
  matrix's Silent-uncertain column then measures how often that mechanism stays
  silent on malformed input.
- TextMate has no error model (`invalid.*` scopes are grammar-optional), so it
  declares no `Errors` and its writes score `unsupported:Errors`.
- No highlighter declares `Anchors` or `DocLiterals` unless it really
  determines them.
- `FullCover` is declared only when the provider is a documented total tokeniser
  and the Layer 1 partition holds over the whole corpus; otherwise the failure is recorded as a finding. `Leaves` carries the raw validated tokens, `Spans` the Layer 2 constructs.

### Pre-phase (risk mitigations)

1. [toolchain_fetch_smoke] Before writing any provider code, install every
   external runtime into the session scratch dir and run one smoke call against
   a corpus fixture with each:
   - a Pygments 2.21.0 venv (`lex` one file);
   - `antlr-4.13.1-complete.jar`, checked against its sha256, plus the pinned
     grammars-v4 files (generate the Kotlin lexer once);
   - the kotlinc 2.4.21 zip, with a trivial `KtPsiFactory` parse compiled
     against `lib/kotlin-compiler.jar`;
   - gopls, pyright 1.1.414, typescript-language-server 6.0.2 + typescript
     5.9.3, and kotlin-lsp v263.6379.0 (`initialize` round trip each);
   - vscode-textmate + vscode-oniguruma + tm-grammars (tokenise one line);
   - scc v4.1.0;
   - for the full-tag matrix rerun (step 10): `tsref/fetch.sh`, the zig 0.17.0
     tarball and `tswasm/build.sh`, plus `go build -tags 't1954cgo t1954wasm'
     ./...` with the local gcc.

   Record each version, source URL, size and pass/fail in a "t1954_3 tools"
   section of `results/environment.md`. A tool that fails is re-scoped
   immediately to "not measured", with the error recorded, and the dependent
   step documents rather than prototypes.

1. **Step 0: reality check**
   - Run `baseline/fetch.sh && baseline/fetch.sh --unpatched`, `go vet ./...`,
     `go test ./...` and `go run ./cmd/t1954 guard`. The committed baseline
     matrix must reproduce byte-identically except for the header.
   - Extend the `env` verb with the t1954_3 tools, so `results/environment.md`
     records their versions.

2. **Non-ASCII position fixtures** (before any provider, so that every adapter
   is tested on them from its first run)
   - Add small, hand-checked fixtures to `corpus/gen/hand_<lang>.py` for **all
     8 corpus languages**, `tsx` included. Each fixture puts the following
     **before a real comment, before a look-alike inside a string, and on lines
     above an edit target**:
     - a 2-byte character (`é`);
     - a 3-byte character (`€` or CJK `漢`);
     - a supplementary-plane character (`😀`: 4 bytes in UTF-8, a surrogate
       pair in UTF-16).

     Minimum per language: one fixture with one writable annotation after such
     a character on the same line's prefix or a preceding line, plus `.edits`
     (an insertion and a restamp after the non-ASCII lines). Python adds a
     variant whose module docstring follows a non-ASCII comment, and a
     PEP 263 Latin-1 case beside the existing `latin1_cookie.py`.
   - Expectations are written by hand. Byte offsets are hand-computed and
     double-checked with `python3 -c 'len(s[:i].encode())'`. Native tools
     cross-check them through `oraclecheck`, which must report 0 new
     disagreements.
   - Run `corpus/gen/gen_corpus.py` and confirm with `git diff --stat corpus/`
     that it only **adds** files (existing fixtures byte-identical). Update the
     fixture count in the README.

3. **Chroma** (`provider/chroma.go`, `github.com/alecthomas/chroma/v2` v2.27.0,
   pure Go; added to `go.mod`, then `go.unpatched.mod/sum` regenerated as the
   README prescribes)
   - Lexers:
     - bash, python, go, kotlin, typescript, javascript, java, rust and swift,
       by name;
     - tsx: Chroma's TSX lexer if one exists. Otherwise tsx is `unsupported`
       and that is recorded.
   - Tokenise with `EnsureLF` off. Map the token types:
     - `Comment.Single` / `Comment.Hashbang` → LineComment;
     - `Comment.Multiline` / `Comment.Preproc*` / `Comment.Special` → BlockComment;
     - `LiteralString*` (incl. `Heredoc`, `Doc`, `Backtick`) → String or Heredoc;
     - `Error` → Diag.
   - Byte offsets accumulate `len(value)`. A token-text or partition mismatch
     fails the analysis as an adapter/library failure (see the contract), and
     any normalisation Chroma applies is recorded as a FullCover finding. Spans are the Layer 2 coalesced constructs.
   - Record which lexers are regex state machines that cannot express heredoc
     delimiters, nesting or raw-string hash counts, citing the lexer source
     files (e.g. the swift `#"""` case from feasibility).

4. **Pygments** (`oracle/pygments_oracle.py` + `provider/pygments.go`, subprocess)
   - Interpreter: `T1954_PYGMENTS_PYTHON`, a scratch venv with
     `pygments==2.21.0`; otherwise `T1954_PYTHON`/`python3`. The helper reports
     the version it imported.
   - Decoding:
     - The helper decodes the bytes exactly as the language would: Python via
       `tokenize.detect_encoding` (BOM, PEP 263 cookie); every other language as
       strict UTF-8 with any BOM stripped.
     - It converts every `get_tokens_unprocessed` index from code points to
       original bytes under that codec, adding the BOM length, before
       answering.
     - A decode failure is an error, so the result is `unsupported`.
   - Lexer options are forced to `stripnl=False, ensurenl=False, tabsize=0`.
     The default normalisation is recorded by running both settings over the
     corpus and counting reconstruction differences.
   - Token mapping as for Chroma, with Layer 2 coalescing (the `"""a\n# no\nb"""` boundary case comes from this lexer); `Token.Error` → Diag.
   - `String.Doc` vs `DocInfo`: test whether the Python lexer's `String.Doc`
     token can yield content bounds and the statement end on the docstring
     fixtures. It has no statement model, so the expectation is `DocLiterals:
     unsupported` and the Python docstring rows score `unsupported:DocLiterals`.
     The test is recorded either way.
   - Cost: interpreter startup per process, per-file latency (bench), venv size,
     and the shipping implication (no release artefact carries Python).

5. **Language-specific parsers**
   - **mvdan/sh, pytokenize:** already measured (see Verification). The findings
     add the dialect/cost analysis and say how a production provider would treat
     those failures. Both are rerun over the new fixtures in step 10.
   - **`tsnative`** (`provider/tsnative.go`, wrapping `oracle/ts_oracle.js
     --serve` under `T1954_TS_NODE_MODULES`, typescript 5.9.3) for typescript,
     tsx and javascript:
     - spans from the parser-aware extraction, already converted UTF-16 → bytes;
     - Diags from `getSyntacticDiagnostics`;
     - the oracle is extended to also emit Anchors `ImportEnd` and `Prologue`
       from the AST (last import declaration; the directive prologue), with
       UTF-16 → line conversion.
     - **Shared provenance is labelled, never presented as independent
       validation:**
       - Add an optional interface `provider.SharedOracle{ SharesOracle()
         string }`; `tsnative` returns `"ts-parser"`.
       - `internal/runner/range.go` treats `name == s.Name ||
         sharesOracle(s.P) == name` as "self-consistency: shares the
         ts-parser extraction (`oracle/ts_oracle.js`), not independent
         validation" and counts no independent pass. A runner test with a
         fake provider pins this.
       - `tsnative`'s independent evidence is stated as such in its matrix
         notes and in the findings: the hand-checked `.expect` record,
         look-alike and placement expectations; the step 2 fixtures; and the
         existing `ts_oracle.js --selftest` with its naive-scan negative
         control (rerun and cited).
       - The new anchors are checked against **independently hand-written**
         expected placements. Add hand fixtures (typescript, tsx and
         javascript) covering: no imports; imports only; a `"use strict"`
         prologue followed by imports; and a comment between imports and code.
         Each gets a hand `placement: file=N` and a fresh file-level insert in
         `.edits`.
   - **Pure-Go Python tokenizers:** search pkg.go.dev and GitHub, then probe
     gpython's lexer (`go-python/gpython/parser`, v0.2.0, Python 3.4 grammar) in
     scratch over the Python corpus: count rejections and the PEP 701 f-string
     cases. Record an exclusion, or prototype a tokenizer if a maintained one
     with 3.12 support exists.
   - **Kotlin compiler PSI: `ktpsi`**
     - Files:
       - `oracle/KtPsiOracle.java`, a long-lived JVM helper with JSON lines,
         compiled against `$T1954_KOTLINC/lib/kotlin-compiler.jar` (kotlinc
         2.4.21, as t1954_1 used) by `oracle/ktpsi_build.sh <scratch>` into a
         git-ignored `.ktpsi/`;
       - `provider/ktpsi.go`.
     - The helper decodes strict UTF-8, BOM-aware, and converts PSI UTF-16
       offsets to original bytes before answering.
     - Spans: `KotlinLexer` comment tokens (EOL/BLOCK/DOC/SHEBANG) and the
       string-template token ranges.
     - Diags: `PsiErrorElement`s and `BAD_CHARACTER`.
     - Anchors `Package` / `ImportEnd` come from `KtFile`'s package directive and
       import list.
     - Fallback: if PSI environment setup fails, run lexer-only without
       Anchors and record the setup failure.
     - Cost: JVM cold start, jar and JRE size, offline packaging.
   - **ktlint / detekt / kotlinx tooling:** eliminate them with build-file
     evidence that they sit on the same kotlin-compiler-embeddable PSI. Any
     kotlinx-ast-style library gets its maintenance status recorded.
   - **Shared adapter cost:** a table of glue lines per provider (`wc` of each
     provider file and its oracle helper), declared capabilities, and the
     capability gaps that force `unsupported` cells.

6. **ANTLR4** (`github.com/antlr4-go/antlr/v4` v4.13.1)
   - Regeneration: `antlr/gen.sh <scratch>` downloads `antlr-4.13.1-complete.jar`
     (sha256 pinned in `antlr/LOCK`) and the grammars-v4 files at a pinned commit
     (sha256 per file in `antlr/LOCK`). It generates Go lexers into
     `provider/antlrgen/{kotlin,java,rust}/`. Rust also gets grammars-v4's Go
     `RustLexerBase`, copied with its MIT attribution.
   - **The generated Go is committed**, so the default build reruns offline, and
     `gen.sh --check` proves regeneration is byte-identical.
   - Provider `antlr` (`provider/antlr.go`), langs kotlin, java, rust:
     - every token on every channel is walked;
     - hidden-channel comment rules → LineComment/BlockComment;
     - string and text-block token ranges → String (Kotlin string modes are
       data across their whole range, interpolations included, matching
       t1954_2's policy);
     - rune indices → bytes through `provider/offsets.go`;
     - the input is decoded as strict UTF-8 after the BOM, and invalid UTF-8
       is an error, so the result is `unsupported`;
     - a custom error listener turns token-recognition errors into Diags at
       their offsets; the gap `Recover` leaves behind is explained by that Diag
       (see Layer 1), never treated as an adapter failure;
     - Errors is declared;
     - an unclosed lexer mode at EOF becomes a Diag where the runtime exposes
       the mode stack, otherwise it is recorded as a gap;
     - Layer 2 coalescing uses the Kotlin opener/closer token-type table;
     - no Anchors (lexer only);
     - `FullCover` is declared per grammar only when the grammar has no
       `-> skip` rules (each of Kotlin, Java and Rust is checked in the pinned
       `.g4`). The partition is then required only for inputs with no Diags.
     - **Diagnostic preservation, not a predetermined outcome:**
       - When the lexer **actually emits** a recognition error on a fixture,
         that Diag must survive conversion and reach refusal scoring. The row
         is then uncertain or refused, never `unsupported` merely because
         recovery left a gap.
       - When the lexer emits **no** diagnostic, the row stays a measured
         candidate failure: Silent-uncertain, or FP-writable / missed comments
         as the runner scores them. Nothing is invented, no extra parsing is
         added, and nothing is excluded from scoring.
       - Expected example, to be confirmed against the pinned grammar:
         `corpus/java/MalformedComment.java.in`. `JavaLexer.g4`'s
         `COMMENT: '/*' .*? '*/'` needs the closer, but `DIV '/'`, `MUL '*'`
         and identifiers can tokenize an unclosed opener without any
         recognition error, which would be a Silent-uncertain finding for
         ANTLR.
       - The findings report, per malformed fixture: emitted Diag (yes/no) and
         the resulting matrix outcome.
   - Maintenance: read-only `gh api` commit history of each used grammar file
     (last change, commit count over 24 months), plus open issues mentioning
     each grammar. The missing TypeScript Go target is recorded as a cost
     (per-language target base classes).

7. **LSP / compiler providers** (verb `lsp`, `cmd/t1954/lsp.go`, writing
   `results/lsp.md`)
   - Servers, all installed in scratch:
     - gopls (`GOBIN=<scratch> go install golang.org/x/tools/gopls@<pinned
       latest>`);
     - pyright 1.1.414 (`pyright-langserver --stdio`);
     - typescript-language-server 6.0.2 with typescript 5.9.3;
     - kotlin-lsp v263.6379.0 (the release zip, on the local JDK 21).
   - **Protocol-correct lifecycle** (a stdio JSON-RPC client with
     `Content-Length` framing and one reader goroutine that demultiplexes
     responses, notifications and server→client requests):
     1. `initialize`, with:
        - `processId`, `rootUri`, `workspaceFolders`;
        - `general.positionEncodings: ["utf-8","utf-16"]`;
        - `textDocument.semanticTokens`: `requests.full: true`, the full
          standard `tokenTypes` list including `comment`, `tokenModifiers`,
          `formats: ["relative"]`, `multilineTokenSupport: true`;
        - `textDocument.foldingRange`: `lineFoldingOnly: false`,
          `foldingRangeKind.valueSet: [comment, imports, region]`;
        - `workspace.configuration: true`;
        - `window.workDoneProgress: true`;
        - per-server `initializationOptions`, e.g. gopls
          `{"semanticTokens": true}`.

        Record the negotiated `positionEncoding` (default UTF-16) and the
        advertised `semanticTokensProvider` legend and `foldingRangeProvider`.
     2. Send `initialized`.
     3. Answer every server→client request:
        - `workspace/configuration`: per-item settings, gopls
          `semanticTokens: true`, else `null`;
        - `client/registerCapability`, `window/workDoneProgress/create` and
          `window/showMessageRequest`: `null`;
        - anything else: a `MethodNotFound` error, logged.
     4. Wait for readiness: `$/progress` `end` for any started token, or a
        quiet period. All bounded: 120 s for initialisation, 30 s per request.
     5. **Controls.** They run on a known-good control file in the project,
        which holds a multi-line block comment, a function body spanning
        several lines, and at least one identifier.
        - **Project readiness (shared):** a request the server advertises
          returns a non-empty result, e.g. `textDocument/documentSymbol` naming
          the known function. If this fails, both features are `inconclusive`
          for that server.
        - **`semanticTokens/full`**, only when advertised: the control's
          response decodes to at least one token at a known identifier
          position.
        - **`foldingRange`**, only when advertised: the control's response
          contains the known function-body fold.
        - The two feature controls are **independent**. The absence or
          failure of one never invalidates evidence from the other.
     6. `didOpen` each fixture (`languageId`, version 1), request each
        advertised feature separately, then `didClose`.
     7. `shutdown` then `exit`.

     Positions are decoded with the negotiated encoding into original bytes.
   - **Valid per-server project** in scratch:
     - gopls: `go.mod`, with each fixture in its own package directory so that
       package clauses and malformed files cannot break their neighbours;
     - pyright: `pyrightconfig.json`;
     - typescript-language-server: `tsconfig.json` with `allowJs` and
       `jsx: preserve`;
     - kotlin-lsp: a minimal project in a form it documents (a Gradle/Maven
       file, or its light JSON workspace if documented); an import failure is
       recorded.
   - **Outcome vocabulary, kept per server × feature (`semanticTokens`,
     `foldingRange`) × fixture:**
     - `measured: comments exposed` (with line agreement against `comments:`,
       and exact range agreement against the native oracle where one exists);
     - `measured: no comment tokens` / `measured: no comment folds`, only when
       that feature's own control passed;
     - `not advertised` (that capability is absent);
     - `inconclusive` (that feature's control failed, a timeout, an error
       response, or the shared readiness control failed);
     - `setup failed` (no server, project import failed);
     - `not measured` (not obtainable).

     Only `measured:*` rows count as evidence about comment support, and each
     feature's evidence stands on its own control.
   - Also recorded: whether errors exist only asynchronously
     (`publishDiagnostics`), initialisation and first-response times, install
     size, runtime and workspace requirement.
   - LSP stays an experiment rather than a seam provider (one server per
     language, a project required, asynchronous certainty). The findings state
     that rationale with the measured numbers.

8. **Other approaches**
   - **TextMate** (provider `textmate`, `oracle/textmate_oracle.js` +
     `provider/textmate.go`, under `T1954_TM_NODE_MODULES`): vscode-textmate
     9.3.2, vscode-oniguruma, and the grammars from shiki's `tm-grammars` package
     (version pinned).
     - Scopes `comment.line*` / `comment.block*` / `string.*` become spans.
     - Per-line UTF-16 indices are converted to original bytes in the helper.
     - No Errors (see the rule above).
     - Lexical rows are measured; write rows score `unsupported:Errors`.
   - **scc** (`go install github.com/boyter/scc/v3@v4.1.0` into scratch): compare
     per-file comment-line counts on the corpus with the oracle `comments:`
     counts. scc is count-only and has no positions, which is the exclusion
     evidence, with its state-machine source cited.
   - **Evidence-backed exclusions** (source, docs or a cheap measurement, each
     with version and license):
     - universal-ctags: definition tags, not comment ranges;
     - linguist / go-enry: file classification only;
     - tokei: counts only, the same class as scc;
     - semgrep: its generic AST drops comments, it is a large OCaml binary and
       LGPL;
     - srcML: C/C++/C#/Java only, GPL-3.0;
     - difftastic: tree-sitter grammars vendored into a Rust binary, so already
       covered by t1954_2's family results;
     - tree-sitter-language-pack: a grammar bundle over the same runtime as
       tscgo. Check which bindings it ships; a Go binding would be cgo;
     - highlight.js / Prism: regex highlighters emitting HTML or token trees,
       without offsets or errors. This is cited, and the TextMate measurement
       stands in for the regex-state class;
     - anything else discovered on the way, e.g. swift-syntax, JavaParser and
       Rust `syn` as further per-language native parsers, each costed by its
       runtime.

9. **Product alternative: registry/sidecar-only annotations**
   - Experiment: verb `sidecar` (`cmd/t1954/sidecar.go`, writing
     `results/sidecar.md`).
     - A research `registry.AnnotationSource` reads one YAML sidecar per test
       file under a scratch `aitestmap/annotations/`.
     - Over the M2.2 bench shape (`writeM22Shape`), all annotations are moved
       into sidecars.
     - The real `registry.Scan` runs at the pinned snapshot. The output is
       compared with the inline baseline: scan output diff and timing.
     - Member identity is keyed by member name. Rename and move cases are
       demonstrated as stale or orphaned records.
   - Design evaluation in the findings:
     - compatibility with M2.1 `AnnotationSource` and mixing with inline sources;
     - stamp/provenance (M2.2);
     - stale confirmation (M4/t1855), adoption (M6/t1857), author annotation
       (M7.4/t1858) and the repair loop (t1853_7). Each is read from the actual
       task/plan files as they exist then, distinguishing landed from proposed
       work;
     - what is lost compared with inline annotations: co-location and review
       visibility;
     - the cost of the inline requirement.

10. **Runs**
    - The corpus grew (step 2), so **every** subject's matrix is regenerated
      from one binary:
      - `go run -tags 't1954cgo t1954wasm' ./cmd/t1954 matrix` (`--provider
        all`) writes every `matrix_<p>.md` and the combined `matrix.md`.
        Subjects: baseline, goscanner, pytokenize, shfmt, gotreesitter, tscgo,
        tswasm, and the new chroma, pygments, tsnative, ktpsi, antlr and
        textmate.
      - This needs `tsref/fetch.sh` and `tswasm/build.sh <zig>`; the zig
        tarball goes into scratch, as t1954_2 did.
      - If the full-tag build cannot be produced, the default-build subjects
        are regenerated. The tagged subjects' files are left as they are, with
        a line stating the 213-fixture corpus they were measured on. The
        combined table is then written with a new `matrix --combined <file>`
        flag to `results/matrix_t1954_3.md`.
    - `guard` and `oraclecheck` are rerun on the new corpus.
    - `realrepo --provider chroma,pygments,tsnative,ktpsi,antlr,textmate --out
      results/t3` over the 6 repos (read-only).
    - `bench --title t1954_3 --subjects baseline,<new providers> --lex-subjects
      … --out results/bench_t3.md` on an idle host. Cold time includes
      interpreter or JVM startup.
    - `footprint`:
      - add probe entries for chroma and antlr, each using its library on real
        input;
      - add a filter flag `--only <names> --out results/footprint_t3.md`;
      - cost the subprocess runtimes as runtime + library size (`du` of the
        venv, node_modules, JRE + jars) in the same file.

11. **Findings** `R/findings_t1954_3.md`, in the t1954_1/2 format:
    - Observations (numbered, with result-file links), documentation claims,
      assumptions and unknowns, kept separate.
    - An **evidence-provenance column**: independent oracle, self-consistency
      (shared extraction), or hand oracle only.
    - Adapter failures (offset conversion, decoding) listed apart from
      candidate deficiencies.
    - A candidate ledger: every family and candidate named in the task, with a
      prototype or an elimination, the evidence path, version/commit, license,
      maintenance data and footprint.
    - Notes for t1954_4.
    - The README gets the new rerun commands, environment variables, provider
      list and fixture count.

### Post-phase (risk mitigations)

1. [candidate_coverage_audit] Before committing, build a checklist from the
   candidates named in the task body (lists 1–7) and in the parent task's
   "Candidate approaches" 1–6. Tick each against the findings ledger. Every
   entry must carry one of:
   - a prototype with its result-file link (`matrix_<p>.md`, `lsp.md`,
     `sidecar.md`, `bench_t3.md`, `footprint_t3.md`);
   - an elimination citing source, docs or a measurement, with version and
     license.

   Fill any gap before the commit, and include the ticked checklist as the
   ledger's closing table.

## Verification

- `CGO_ENABLED=0 go build ./... && go vet ./... && go test ./...` in `R` (the
  default build includes chroma, antlr and the subprocess providers).
- The `guard` verb still passes after the `go.mod` change, with
  `go.unpatched.*` regenerated.
- Rerunning each README command reproduces every new `results/matrix_<p>.md`;
  two consecutive runs are byte-identical.
- With the runtime env var unset, a subprocess provider reports `unsupported`
  cleanly, with nothing empty and no panic (checked once per provider).
- `antlr/gen.sh --check` regenerates byte-identical Go.
- `go test ./provider/` includes `offsets.go`'s hand-computed 2-, 3- and 4-byte
  (surrogate) cases.
- A runner test shows that a `SharedOracle` provider gets the self-consistency
  label and no independent pass, while the existing subjects' labels are
  unchanged.
- `gen_corpus.py` only adds files: existing fixtures are byte-identical
  (`git diff --stat corpus/`). `oraclecheck` reports 0 new disagreements on the
  step 2 fixtures.
- Every new provider's range column passes on the step 2 fixtures, or each
  failure is attributed as either an adapter failure or a candidate
  deficiency.
- `results/lsp.md` shows, per server and feature, the readiness control and that
  feature's own control. No `measured:*` row exists without both passing, and a
  feature's outcome never depends on the other feature's control.
- `go test ./provider/` covers the two layers:
  - `tokencheck_test.go`:
    - a fragment stream (`x = "abc"` as 3 tokens) passes;
    - a text mismatch fails as an adapter failure;
    - a gap at a recorded recognition-error Diag is accepted and the Diag is
      kept;
    - a gap is accepted as a documented omission only when the grammar
      declares skip rules;
    - an unexplained gap fails;
    - a total tokeniser's gap fails.
  - `coalesce_test.go`, using the recorded Pygments stream for
    `x = """a\n# no\nb"""\ny = 1  # c\n` (a newline fragment ends at 9 and a
    String fragment starts at 9) and running it through the real `ToContext`:
    - lines 2 and 3 are Literal and line 4 Comment-capable;
    - negative control: the raw, uncoalesced fragments give line 2 Code, which
      demonstrates the boundary bug;
    - a literal that genuinely opens at a line start keeps its pre-existing
      class;
    - an interpolation case (Kotlin `"""…${x}…"""`) yields one span.
- Over the whole corpus, every new provider's Layer 1 checks pass. Any failure
  is listed as an adapter failure, not scored.
- Every candidate in the task's lists 1–7 appears in the findings ledger with a
  prototype or an evidence-backed elimination.
- `git status` shows changes only under `R`. Commits name their paths
  explicitly; `goengines/` is untouched.

## Step 9 reference

A `chore: … (t1954_3)` commit of the `R` paths only, then the standard child
archival. Send t1954_4 a note (`./ait note 1954_4 --from 1954_3`) with the
result headline and file paths.

## Risk

### Code-health risk: low
- `go.mod` gains chroma and antlr4-go, and a large committed body of generated
  ANTLR Go lands under `R`. The module is isolated: it is not shipped, CI does
  not run it, and test discovery does not reach it (README isolation evidence).
  `gen.sh --check` and the guard's `go.unpatched.*` regeneration keep it
  reproducible. · severity: low · → mitigation: in-plan (steps 3, 6; Verification)
- The shared worktree holds other sessions' uncommitted work (`.aitask-scripts/lib`,
  `tests/`), so a broad add or commit would absorb it. · severity: low ·
  → mitigation: in-plan (path-scoped commits of `R` only)
- New verb flags (`matrix --combined`, `footprint --only`, `env` additions) could
  alter t1954_1/2's committed outputs. Verb defaults stay unchanged. The
  regeneration of t1954_1/2's matrices on the grown corpus is deliberate and
  complete (step 10), never partial or silent. A subject that cannot be rebuilt
  is labelled with its corpus size. · severity: low · → mitigation: in-plan
  (step 10)
- The runner change for shared provenance (`range.go`) touches scoring for
  every subject. It only adds a label branch for a provider that declares
  `SharedOracle`, and a runner test (with the existing review tests) pins
  behaviour for all other subjects. · severity: low · → mitigation: in-plan
  (step 5; Verification)

### Goal-achievement risk: medium
- Breadth: 6 new providers, 4 LSP servers, the sidecar experiment and about 10
  eliminations. Some candidates could end up with shallow or missing evidence,
  which would fail the "every family evaluated" acceptance criterion. ·
  severity: low (residual — addressed by inline post-phase candidate_coverage_audit) ·
  → mitigation: inline post-phase candidate_coverage_audit
- External runtimes may fail late, after the provider code is written: kotlinc
  PSI environment setup, kotlin-lsp, pyright, gopls, the tm-grammars and
  Pygments venvs, the ANTLR jar or the grammars. · severity: low (residual —
  addressed by inline pre-phase toolchain_fetch_smoke) ·
  → mitigation: inline pre-phase toolchain_fetch_smoke
- A highlighter declaring `Errors` on the strength of rare error tokens could
  make writes look supported. Mitigated by the stated declaration rule: the
  Silent-uncertain column measures the gap, and it is reported in the
  findings. · severity: low · → mitigation: in-plan (capability rule)
- Adapter position bugs: ANTLR runes, Pygments code points, PSI/TextMate/LSP
  UTF-16, and a decoding codec mismatch. Any of these could misplace spans, and
  ASCII-only fixtures would hide them, misreporting an adapter mistake as a
  candidate deficiency. · severity: medium (user plan review) → low (residual —
  addressed by the position-conversion contract, `provider/offsets.go` with
  hand-computed tests, Layer 1 per-token text/bounds/order validation with
  conditional, gap-explaining completeness, and the step 2 non-ASCII fixtures
  in every language; adapter failures are listed apart in the findings) ·
  → mitigation: in-plan (review amendments; steps 2–8)
- Fragmented tokens reaching the seam unnormalised would class literal
  continuation lines as Code (`insideData`'s strict start check). And a
  completeness check that ignores ANTLR recovery or skip rules would turn
  lexical-error refusals into `unsupported`. · severity: medium (user plan
  review) → low (residual — addressed by Layer 2 construct coalescing with a
  `ToContext` boundary test and its negative control, and by Layer 1 gap
  attribution that keeps any recognition-error Diag the lexer actually emits.
  Malformed inputs the lexer does not diagnose stay measured candidate
  failures, e.g. Silent-uncertain) · → mitigation: in-plan (review amendments;
  contract, step 6)
- LSP setup failures (incomplete handshake, missing configuration such as
  gopls `semanticTokens`, an unloaded project) could be read as "no comment
  support". · severity: medium (user plan review) → low (residual — addressed
  by the protocol lifecycle, capability negotiation, server→client request
  handling, a per-server project, independent per-feature controls and a separate
  inconclusive/setup-failed vocabulary) · → mitigation: in-plan (review
  amendment; step 7)
- `tsnative` shares `ts_oracle.js` with the `ts-parser` reference, so its range
  check would look like independent validation. · severity: medium (user plan
  review) → low (residual — addressed by the `SharedOracle` label in
  `range.go`, the provenance column in the findings, and independent hand
  expectations for its anchors plus the retained selftest negative control) ·
  → mitigation: in-plan (review amendment; step 5)
- Concurrent agents on the host can contend the bench. Mitigated by the
  idle-host rule with the load recorded, and a discard-and-rerun precedent
  (t1954_2). · severity: low · → mitigation: in-plan (step 10)

Reassessed with both inline phases: code-health stays **low**. Goal-achievement
stays **medium**. The two medium risks are now bounded, but a tool that proves
unobtainable still leaves that candidate with documentation-only evidence
("not measured"), and t1954_4 must weigh that.

### Planned mitigations
- timing: pre-phase | name: toolchain_fetch_smoke | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: external runtimes failing late | desc: install every external runtime into scratch and smoke-call it before any provider code; re-scope failures to "not measured" up front
- timing: post-phase | name: candidate_coverage_audit | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: breadth — shallow or missing evidence | desc: tick every candidate from the task and parent lists against the findings ledger (prototype link or cited elimination); fill gaps before commit
