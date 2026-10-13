# Findings — t1954_3 (tokenizers, language parsers, LSP, alternatives)

- Research date: 2026-10-13.
- Baseline: `annot` at `f096db065a72`, via `baseline/PIN`, unchanged since
  t1954_1. Host and toolchain: `results/environment.md` (its "t1954_3 tools"
  section lists every scratch install with its version and source).
- Corpus: **229 fixtures** (213 from t1954_1; t1954_3 added 16, see item 1).
- Candidates prototyped through the seam (all 8 corpus directories, every
  level; `results/matrix_<p>.md`, combined in `results/matrix.md`):

  | provider | what | version | license | runtime |
  |---|---|---|---|---|
  | `chroma` | regex highlighter (Pygments port), pure Go | chroma/v2 v2.27.0 (v3 is alpha) | MIT | none (in-process) |
  | `pygments` | regex highlighter | Pygments 2.21.0 | BSD-2-Clause | CPython subprocess |
  | `textmate` | TextMate grammars (VS Code, shiki) | vscode-textmate 9.3.2, vscode-oniguruma 2.0.1, tm-grammars 1.32.22 | MIT | Node.js subprocess |
  | `tsnative` | the TypeScript compiler's parser | typescript 5.9.3 | Apache-2.0 | Node.js subprocess |
  | `ktpsi` | the Kotlin compiler's PSI | kotlinc 2.4.21 (`kotlin-compiler.jar`) | Apache-2.0 | JVM subprocess |
  | `antlr` | ANTLR4 Go runtime + grammars-v4 lexers (Kotlin, Java, Rust) | runtime v4.13.1, tool 4.13.1, grammars-v4 `89fd3648` | BSD-3 (runtime); grammars Apache-2.0 / BSD / MIT | none (in-process) |

  Already measured by t1954_1 and analysed here: `shfmt` (mvdan.cc/sh/v3
  v3.14.1) and `pytokenize` (CPython tokenize + ast).
- Experiments that are not seam providers (reasons in the items): LSP
  (`results/lsp.md`), sidecar-only annotations (`results/sidecar.md`), scc,
  gpython and the Pygments design checks (`results/t3_probes.md`).
- Every number below comes from a committed result file, which is named and
  can be rerun with the commands in `README.md`.

## Observations

### Harness changes (shared with t1954_4)

1. **16 fixtures added, nothing else in the corpus moved.**
   - 8 `nonascii.*` fixtures, one per corpus directory plus `.tsx` and `.js`.
     Each puts a 2-byte (`é`), 3-byte (`€`, `漢`) and 4-byte (`😀`, a UTF-16
     surrogate pair) character before a real comment, before a look-alike in
     a string, and on the lines above every edit target.
   - `nonascii_doc.py` (a docstring after non-ASCII bytes) and
     `latin1_member.py` (PEP 263 Latin-1, one byte per character).
   - 4 TS/JS anchor fixtures with hand-written placements:
     `fresh_noimports.ts`, `fresh_imports_only.ts`,
     `fresh_strict_imports.js`, `fresh_comment_between.tsx`.
   - `gen_corpus.py` only added files. `oraclecheck`: 229 fixtures, 0
     disagreements (`results/oracle_check.md`). kotlinc, swiftc (docker),
     javac, rustc, node, bash, go and Python accept the new ones.
   - **Every pre-existing subject's 213 old per-case rows and notes are
     byte-identical** after the regeneration (baseline, goscanner,
     pytokenize, shfmt, gotreesitter, tscgo, tswasm). Only the per-language
     totals grew. The new fixtures expose no defect in any of those seven
     subjects: placement included, all their new rows are 0 on every column.
   - `guard`: PASS on the grown corpus. `ts_local_error_policy.md`
     regenerates byte-identical. `ts_differential.md` was **not**
     regenerated: it also walks the live sibling repositories, so a rerun
     would mix repository drift into t1954_2's evidence. It stays measured on
     the 213-fixture corpus.
2. **The adapter contract every t1954_3 provider follows** (`provider/`):
   - `offsets.go`: rune, UTF-16 and LSP line/character positions → byte
     offsets of the ORIGINAL source. Hand-computed tests cover 2-, 3- and
     4-byte characters (`offsets_test.go`).
   - Layer 1, `tokencheck.go`: every emitted token's text must equal
     `src[start:end]`, in bounds, sorted and non-overlapping. Gaps are
     attributed to a diagnostic (ANTLR's `Recover`), a grammar `skip` rule
     or a BOM; an unexplained gap, or any gap from a total tokeniser, is an
     **adapter failure**, never a candidate deficiency.
   - Layer 2, `coalesce.go`: fragments become construct-level spans.
     Pygments splits `"""a\n# no\nb"""` at each newline, so the continuation
     line begins exactly on a fragment boundary, which `ToContext`'s strict
     `s.Start < off` check would class Code. `coalesce_test.go` reproduces
     that with the recorded Pygments stream and a negative control.
     Coalescing never absorbs a token the tool itself called a comment.
   - `ToContext` is unchanged.
   - Runner: `provider.SharedOracle` labels a provider that wraps the
     oracle's own extraction as *self-consistency* (`range.go`,
     `shared_oracle_test.go`, with an independent-provider negative control).
     A FullCover provider that reports Diags and no partition gets "full
     cover not checked" instead of a false range failure. No pre-existing
     subject declares either, which item 1's identity check confirms.
3. **New verbs and modes:**
   - `lsp`, `sidecar`, `footprint-t3`, `env --t3`;
   - `ts_oracle.js` gained a `provider` mode; the oracle mode is unchanged
     and `--selftest` still passes with its negative control;
   - `antlr/gen.sh [--check]` regenerates the committed lexers
     byte-identically from `antlr/LOCK`.

### Adapter failures the harness caught (fixed; listed apart from the candidates)

4. **None survives in the final runs**: no `error:provider: adapter-conversion`
   row in any matrix or real-repository report. On the non-ASCII fixtures
   every new provider's comment ranges equal the native oracle's byte for
   byte (shfmt, goscanner, pytokenize, ts-parser). The one exception is a
   classification, not an offset: Chroma and Pygments read `nonascii.tsx`'s
   JSX text as a comment (item 8). These four defects
   were found during development by the harness's own checks:
   - **ktpsi** walked past string templates without descending, so the
     compiler's `Expecting '"'` (a `PsiErrorElement` inside the template)
     was never collected. Two Silent-uncertain rows
     (`malformed_unterminated_string.kt`, `lex_unterminated_raw.kt`) were
     adapter artefacts. The fix records only the outermost template but
     still descends.
   - **chroma / pygments** classed a comment token by its text when its type
     was `Comment.Multiline`. A fragment such as ` outer ` inside
     `/* outer /* inner */ … */` became a "line comment". Rust FP-writable
     4 → 0 for both. The range metric caught it ("line comment does not start
     with `//`").
   - **pygments** with `ensurenl` forced off: the Bash lexer's comment rule
     needs the final newline, so the last line of `nonl_edit.sh` (no final
     newline) was not a comment and an applied edit corrupted the records.
     Pygments documents `ensurenl` as "required for some lexers that consume
     input linewise". The helper now lexes with the newline and trims that
     one appended character. Bash record corruption 4 → 3, missed-writable
     1 → 0.
   - **runner accounting**: ANTLR's FullCover was failed on uncertain inputs
     whose recovery gaps the adapter had already attributed (item 2).

### Regex highlighters — Chroma and Pygments (`results/matrix_{chroma,pygments}.md`)

5. **Safety fails in every language, worst in bash:**

   | | bash | python | go | kotlin | ts/tsx/js | java | rust | swift |
   |---|---|---|---|---|---|---|---|---|
   | FP-writable chroma / pygments | 22 / 22 | 1 / 1 | 2 / 2 | 10 / 8 | 2 / 2 | 2 / 2 | 0 / 0 | 2 / 0 |
   | Silent-uncertain chroma / pygments | 8 / 8 | 3 / 3 | 1 / 1 | 3 / 3 | 1 / 1 | 2 / 2 | 2 / 2 | 2 / 2 |
   | Record-corruption chroma / pygments | 3 / 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

   - Both report **22 of the 25 malformed fixtures as certain**. Their
     `Error` token fires only on a character no rule matches, and an
     unterminated construct ends the input in some state without any token
     saying so. `Errors` is declared (the plan's rule), so the gap is
     measured, not hidden.
   - Bash heredocs: both use the same rule
     (`chroma …/embedded/bash.xml:193`, `pygments/lexers/shell.py:73`):
     `<<-?\s*('?)\\?(\w+)[\w\W]+?\2`. It ends a heredoc at the **first
     occurrence of the delimiter word anywhere**, not on a line of its own,
     and accepts only `\w+` delimiters. That is the 22 FP-writable (heredoc
     continuations, two heredocs on a line, ANSI-C and locale delimiters,
     partly quoted delimiters).
   - Swift: Chroma's lexer enters a string only on `"` (`swift.xml:133`),
     with no `"""` or `#"…"#` rule. This is the feasibility smoke's 21
     phantom comments. Pygments has `"""` but no extended delimiters.
   - Python records: neither can supply `DocInfo` (item 7), so every Python
     write is `unsupported:DocLiterals` (40 / 43 ops).
6. **Byte fidelity holds when they are driven correctly.**
   - Both are total tokenisers. Layer 1's exact partition holds on every
     corpus and real-repository input.
   - Chroma: `TokeniseOptions` must be passed explicitly, because the
     default `EnsureLF` rewrites CRLF. The TypeScript, JavaScript and Rust
     lexers' `EnsureNL` appends one `\n`, which the adapter trims.
   - Pygments: `get_tokens()` always rewrites CRLF/CR to LF. It fails to
     reproduce exactly the 9 CRLF fixtures, plus `nonl_edit.sh` with the
     default options (`results/t3_probes.md`). The provider path
     (`get_tokens_unprocessed` + ensurenl emulation) reproduces all 228
     decodable fixtures.
   - Encodings: Chroma lexes runes, so non-UTF-8 input is
     `unsupported:UTF-8-input` (3 Latin-1 fixtures). Pygments decodes Python
     by its PEP 263 cookie (both Latin-1 Python fixtures pass) and refuses
     the Latin-1 bash file.
7. **Pygments `String.Doc` is not a docstring model** (`--doccheck` in
   `results/t3_probes.md`). Over 59 parseable Python fixtures with 35 module
   docstrings:
   - a `String.Doc` token covers only 15 of them;
   - 20 docstrings have none (implicit concatenation, parenthesised forms,
     prefixes);
   - 3 `String.Doc` tokens are not the module docstring (any triple-quoted
     string at a line start);
   - the statement end differs in 2.

   `DocLiterals` is therefore not declared.
8. **TSX:** Chroma has no TSX lexer (its TypeScript lexer claims `*.tsx`).
   Pygments has one. Both read the JSX text `// testmap:…` as a comment
   (`jsx_text.tsx`: FP-writable 2).

### TextMate (`results/matrix_textmate.md`)

9. **No error model, so every write is `unsupported:Errors`.** Silent-uncertain
   is reported as "n/a: no error reporting" (25 malformed fixtures).
   - Lexical classing is closer to the oracles than the regex lexers' in
     bash (FP-writable 12 vs 22) and Swift (0), but it reads look-alikes as
     comments in Kotlin (8: nested and unterminated block comments), Python
     (4: triple strings, raw triples) and Java (2: `\u` escapes).
   - It stands for the regex-state class: highlight.js and Prism are the
     same mechanism with less output (item 24).

### The TypeScript compiler's parser — `tsnative` (`results/matrix_tsnative.md`)

10. **0 on every safety column, Placement 0** (19 fixtures, 16 applied
    edits).
    - Its anchors (`ImportEnd`, `Prologue`, from the AST) were checked
      against independently hand-written placements: the four new anchor
      fixtures plus `prologue.js` and `imports.ts`.
    - **Its range column is self-consistency, not validation**: it shares
      `oracle/ts_oracle.js` with the `ts-parser` oracle, and every row says
      so. Its independent evidence is the hand `.expect` records, look-alikes
      and placements, the non-ASCII fixtures, and `ts_oracle.js --selftest`
      (PASS, with the naive-scan negative control, typescript 5.9.3).
    - Over-refusal 1: `html_comments.js` (Annex B `<!--` comments, which the
      TypeScript parser rejects and JS engines accept).
    - Cost: Node.js + typescript (item 22).

### The Kotlin compiler's PSI — `ktpsi` (`results/matrix_ktpsi.md`)

11. **0 on every safety column** (26 fixtures, 11 applied edits). The PSI
    flags all 3 malformed Kotlin fixtures: `Unclosed comment`, `Expecting
    '"'`.
    - Its `Package` / `ImportEnd` anchors are measured (fresh-file inserts
      applied).
    - Over-refusal 2:
      - `lex_anchors.kt`: `import x` inside a class is a grammar error to
        the PSI, while the hand oracle (lexically valid) says certain;
      - `script.kts`: the provider sees the Lang, never the path, so a
        script is parsed as a `.kt` file. A production adapter would need
        the file kind.
    - ktlint (`kotlin-compiler-embeddable`) and detekt (`kotlin-compiler`)
      are built on this same PSI (their `gradle/libs.versions.toml`), so
      they add rule engines, not a different lexer: eliminated as redundant
      with this row.
    - Cost: a JVM per process plus 63.6 MB of jars (`kotlin-compiler.jar` 60.2 MB, stdlib, coroutines; item 22).

### ANTLR4 + grammars-v4 lexers (`results/matrix_antlr.md`)

12. **Lexers diagnose only what their grammar cannot tokenise.**
    - Silent-uncertain: Kotlin 3/3, Java 1/2, Rust 1/2.
    - FP-writable 2 in each language. These come from unterminated block
      comments: `COMMENT: '/*' .*? '*/'` simply fails to match, and `/`,
      `*` and identifiers then tokenise the opener without any recognition
      error. `MalformedComment.java` behaves exactly as predicted from the
      grammar.
    - The diagnostics that ARE emitted reach the refusal scoring: Java
      `TextBlocks.java` and `UnicodeEscape.java` are over-refusals (token
      recognition errors on valid files: an escaped quote in a text block,
      `\u` escapes the lexer does not translate). They are never
      `unsupported`.
    - The runtime keeps its mode stack unexported, so an unclosed string
      mode at EOF is invisible. No diagnostic is invented for it.
13. **Positions:** the runtime indexes runes. Converted through
    `RuneOffsets`, all ranges agree on the non-ASCII fixtures (Layer 1 holds
    everywhere). Kotlin's grammar has `-> skip` rules (whitespace), so it
    declares no FullCover. Java and Rust do.
14. **Per-language maintenance is real code, not just a grammar file:**
    - the Rust lexer needs grammars-v4's Go base class and a
      `this.`→`p.`/`l.` transform; the copied base also needed one
      unreachable statement removed for `go vet`;
    - **TypeScript has no Go target base class at all**, so it was not
      generated;
    - generated Go is 252 KB for 3 lexers (`provider/antlrgen/`);
    - grammar churn over 24 months: KotlinLexer.g4 3 commits (last
      2026-07-05), JavaLexer.g4 2 (2025-08-13), RustLexer.g4 1 (2025-11-21),
      TypeScriptLexer.g4 0 (2024-02-25);
    - open issues titled with the language: Kotlin 8, Java 29, Rust 4,
      TypeScript 13;
    - the Go runtime module `antlr4-go/antlr` was last pushed 2024-06 (2
      contributors), and the ANTLR tool's last release is 4.13.2
      (2024-08).

### mvdan/sh and pytokenize (t1954_1 rows, read for production cost)

15. Measured by t1954_1 (`findings_t1954_1.md` items 13–14). On the grown
    corpus their old rows are unchanged and the new fixtures add nothing.
    - shfmt: 2 FP-writable on bash's hardest heredoc continuation, 1
      Silent-uncertain (an unterminated heredoc in backticks), 10 of 1,620
      real bash files refused.
    - pytokenize: 0 on safety and the only full Python docstring model. It
      is a CPython subprocess: the release artefact ships none (item 22).

### Pure-Go Python tokenizers (`results/t3_probes.md`)

16. **gpython v0.2.0** (last release 2023-06-28; 4 commits in 12 months)
    lexes 60 of 61 valid Python fixtures (it rejects `bom_doc.py`). But **its
    lexer emits no comment token**: it skips comment-only lines and stops a
    line at `#` (`parser/lexer.go`). It cannot report comment locations
    without being modified, which makes it a custom reader by another route.
    No maintained pure-Go Python tokenizer with 3.12 f-string support was
    found (pkg.go.dev / GitHub search; gotreesitter's Python grammar is
    t1954_2's).

### LSP / compiler servers (`results/lsp.md`)

17. **No server gives comment ranges plus certainty in one response.** One
    experiment per server, each in its own scratch project, through a
    protocol-correct lifecycle with independent per-feature controls. Every
    control and readiness check passed.
    - **gopls v0.23.0** (`semanticTokens` enabled through its settings)
      exposes `comment` tokens: 19 of 21 Go fixtures, exact line-comment
      ranges equal to go/scanner in 13 of 21.
      - Its tokens cannot tell a `//` line *inside* a `/* … */` block from a
        real line comment: 5 look-alike lines read exactly like annotation
        lines (`lex_block.go`, `lookalikes.go`, `cgo_preamble.go`, …).
      - Comment folds cover the same 4 blocks.
      - Certainty exists only as asynchronous `publishDiagnostics` (5 files),
        never with the tokens.
    - **pyright 1.1.414** advertises neither semantic tokens nor folding
      ranges: `not advertised`, so no comment evidence at all.
    - **typescript-language-server 6.0.2** (typescript 5.9.3) has no
      `comment` type in its semantic-token legend: 0 comment tokens, even for
      the control file's 4-line block comment, with the control passing.
      Folding exposes comment blocks only (2 fixtures).
    - **kotlin-lsp v263.6379.0** lists `comment` in its legend but emits
      **none**, even for the control's block comment: a measured absence
      with the semantic-token and folding controls both passing. Comment
      folds (5 fixtures) cover look-alike lines 6 times (nested and
      unterminated block comments).
    - Deployment burden:
      - a project or workspace per server;
      - 2.2 s of readiness wait before the first answer;
      - a runtime (Node.js, a JVM; kotlin-lsp ships a 1.2 GB bundle with its
        own JBR);
      - one server per language.

      LSP therefore stayed an experiment, not a seam provider.
    - fwcd/kotlin-language-server was not run: deprecated by its own README.

### Product alternative: sidecar-only annotations (`results/sidecar.md`)

18. **The registry is source-agnostic, except for lines.**
    - All 735 records of the M2.2 bench shape (420 test files) moved into
      per-file YAML sidecars. The real `registry` code yields identical
      units, edges and variants (420 / 735 / 0).
    - The rendered `_scanned.yaml` is byte-identical **once the 735 `line:`
      fields are removed**. The registry records each covers edge's line,
      and a sidecar has no line to give. M2.1's `AnnotationSource` interface
      itself needed no change.
    - Scan (dry run, fastest of 5 in one process, not the pinned bench
      method): inline 21.4 ms, sidecar 11.5 ms. No
      lexing is needed.
    - **A moved test file**: inline records travel with the file. A path-keyed
      sidecar is orphaned. Without an orphan check the scan **succeeds on a
      stale record** (420 / 735 still reported, the moved file unannotated);
      with one it fails closed. A production sidecar needs that check, plus a
      `git mv`-aware repair.
    - **Consumers** (task files as they stand; none has landed: t1855 M4,
      t1857 M6 and t1858 M7 are Ready, t1853_7 is Postponed):
      - M4.2 `stale` reports "line classes and encodings" and `--confirm`
        rewrites stamps through M2.2's rewriter, so a sidecar would need its
        own stamp-write path and loses the line it reports.
      - M6.3 adoption and M7.4 author annotation already write registry rows
        (`adopted.yaml`, origin `agent:author`) next to annotations, so
        their records are sidecar-shaped today.
      - The repair loop (t1853_7) reuses "M2.2's sole annotation rewriter"
        and would need a second writer.
    - What inline buys and a sidecar loses: co-location (the record moves,
      renames and is reviewed with the test), review visibility in diffs of
      the test file, and the line anchor.
    - What the inline requirement costs: a trustworthy comment reader per
      language, which is everything else in this report.
    - Mixed sources fit the interface: two `AnnotationSource`s concatenated,
      with a conflict rule for a file that has both. Not built here.

### Real repositories (`results/t3/realrepo_*.md`, read-only)

19. **Six repositories, read-only, against the baseline** (`results/t3/`).
    The totals are: **no annotation record differs for any provider in any
    language** (records-differ 0), and 0 provider errors.
    - Highlighters differ from the landed lexers in line classes where the
      corpus predicted:
      - bash (Chroma and Pygments 17 files, TextMate 18): heredocs;
      - Python (Chroma and Pygments 217 of 1,840 files, TextMate 3):
        triple-quoted strings at a line start.

      No testmap line is affected.
    - **Refusal cost on valid Kotlin** (2,014 files), uncertain where the
      baseline is certain:

      | provider | files refused |
      |---|---|
      | ktpsi | 21 (1.0%) |
      | antlr | 1 (0.05%) |
      | Pygments | 75 (3.7%) |
      | Chroma | 168 (8.3%, spurious `Error` tokens) |

      For comparison (t1954_2): gotreesitter 24.6%, tscgo 6.3%.
    - The ANTLR figure is low because a lexer tokenises almost anything
      (item 12); it is not evidence of certainty.
    - Bash refusals: Chroma and Pygments 2 of 1,626. TS/JS (3 files), Java
      (16) and Swift (2) are too few to weigh (t1954_2's unknown stands).

### Performance and footprint (`results/bench_t3.md`, `results/footprint_t3.md`)

20. **Speed** (`results/bench_t3.md`; the t1954_1 method: `taskset -c 0`,
    fastest of 3 fresh processes, cold includes provider and runtime
    start-up).
    - The host's 1-minute load rose from 2.6 to 4.7 during the run. The
      same-run baseline control read 28.5 ms, against 23.8 ms in t1954_2's
      run, so absolute figures carry roughly 20% host noise; the ratios are
      what matter.
    - **End-to-end scan (budget-comparable): not measurable for Chroma,
      Pygments and TextMate.** The M2.2 workload is a quarter Python, and
      without DocLiterals the scan fails closed on the first Python test
      (`unsupported:DocLiterals`). A highlighter could only serve the scan as
      a hybrid with a Python docstring model, a configuration not built
      here.
    - **Lexical-only (not budget-comparable), on the 420 M2.2 test files:**

      | subject | cold |
      |---|---|
      | landed lexers | 6.1 ms |
      | Chroma | 866 ms |
      | Pygments | 909 ms |
      | TextMate | 1,883 ms |

      Even the lexical step alone exceeds the whole 300 ms scan budget by 3–6×.
      On aitasks' 839 test files: 8.4–13.2 s against 54 ms.
    - **ktpsi:** JVM start-up dominates. Cold 541–923 ms against warm
      15.6–195 ms on the sibling Kotlin sets (20–37 files); 2.7 s cold / 1.3 s
      warm on thinking_app's 396 Kotlin test files.
    - **antlr:** 259 ms cold on those 396 files, against 11 ms for the landed
      Kotlin lexer.
    - **tsnative:** not measured. The lexical sets contain no TS/JS test files
      and the scan workload has none.
21. **Footprint** (`results/footprint_t3.md`; probes built `CGO_ENABLED=0`
    for the four release targets, all of which build):
    - Chroma adds **+6.4 MB** to a static binary: the `lexers` registry
      embeds every lexer, with no per-language subset.
    - The ANTLR runtime plus the three generated lexers add **+1.3 MB**.
    - For comparison (t1954_2): gotreesitter's curated subset adds +14.8 MB.
22. **Subprocess runtimes are outside the release artefact** (one static Go
    binary, no runtime):

    | provider | runtime the host must provide | library |
    |---|---|---|
    | Pygments, pytokenize | CPython | 20.6 MB (Pygments) |
    | tsnative | Node.js (a 123.8 MB `node` binary here) | 23.6 MB (typescript) |
    | TextMate | Node.js | 13.4 MB |
    | ktpsi | a JDK/JRE (352.5 MB JDK here) | 63.6 MB of compiler jars |
    | kotlin-lsp | its own bundled JBR | 1.2 GB |

    Each also needs a per-process start-up and, for a long-lived helper, the
    process management this harness does in `subproc.go`. Shipping any of
    them makes the engine's language support depend on what the user's host
    has installed.

### Shared adapter cost

23. Non-blank, non-comment lines (approximate; `grep -cv` of comment
    leaders) of each provider's glue:

    | provider | Go adapter | helper | notes |
    |---|---|---|---|
    | goscanner (t1954_1) | 83 | — | |
    | shfmt (t1954_1) | 55 | — | |
    | pytokenize (t1954_1) | 122 | 140 (`py_oracle.py`) | |
    | tree-sitter (t1954_2) | 83 / 94 / 157 (gotreesitter / tscgo / tswasm) | 447 shared (`tsmap.go`) + per-grammar kind tables | |
    | chroma | 71 | — | + 46 shared highlighter mapping |
    | pygments | 83 | 180 (`pygments_oracle.py`, incl. the two checks) | + 46 shared |
    | textmate | 72 | 117 (`textmate_oracle.js`) | + 46 shared |
    | tsnative | 78 | +50 in `ts_oracle.js` (provider mode) | |
    | ktpsi | 86 | 168 (`KtPsiOracle.java`) + 10 (build) | |
    | antlr | 152 | 52 (`gen.sh`) + ~250 KB generated + the Rust Go base | |
    | shared contract | `offsets.go` 94, `tokencheck.go` 95, `coalesce.go` 117, `subproc.go` 85 | | |

    - The interface held for every family without change. Capability
      declarations decided which cells are `unsupported`:
      - TextMate: no Errors, so writes are unsupported;
      - Pygments and Chroma: no DocLiterals, so Python writes are
        unsupported;
      - every lexer-only provider (Chroma, Pygments, TextMate, ANTLR): no
        anchors, so fresh file-level inserts are unsupported.
    - The real per-language cost sits in the mapping:
      - which token types are comments, literals or interpolation
        delimiters;
      - the encoding of each tool's positions;
      - how each tool fragments a construct.

      Every item-4 adapter defect lived there.

### Other approaches — evidence-backed eliminations

24. Each with what it is, why it cannot supply comment locations with
    certainty for safe edits, and the evidence:
    - **highlight.js 11.12.0 (BSD-3), Prism 1.30.0 (MIT):** regex
      highlighters emitting HTML (highlight.js) or nested token trees without
      offsets (Prism), with no error model. They are the same class as the
      measured TextMate, Chroma and Pygments rows (items 5–9), which
      measure that class's failure modes. Eliminated by class (documentation
      claim; not prototyped).
    - **scc 4.1.0 (MIT), tokei 15.0.0:** count-only line classifiers.
      - scc's per-file JSON carries counts and no line or byte positions.
      - Its comment count matches the hand line-comment count in 139/229
        fixtures (a coarse indicator; the definitions differ).
      - tokei reports the same counts (its README: "code, comments, and
        blanks").
      - Measured for scc (`results/t3_probes.md`); a documentation claim for
        tokei.
    - **universal-ctags 6.2.1 (GPL-2.0):** emits definition tags (symbols),
      not comment ranges. Documentation claim.
    - **linguist (MIT) / go-enry (Apache-2.0):** file-level language
      detection and vendored/generated classification. They expose no
      tokens. Documentation claim.
    - **semgrep 1.180.0 (LGPL-2.1):** a rule-matching engine. Its output is
      rule matches, and no API returns a file's lexical comment ranges; an
      OCaml binary. Documentation claim; footprint not measured.
    - **srcML 1.1.0 (GPL-3.0):** supports C, C++, C# and Java only (README),
      so no coverage of bash, Python, Kotlin, TS, Rust or Swift.
    - **difftastic 0.71.0 (MIT):** vendors tree-sitter parsers into a Rust
      binary (README). It is the t1954_2 family behind a diff UI, with no
      comment-range API.
    - **tree-sitter-language-pack 1.22.1 (MIT):**
      - a grammar bundle over the C tree-sitter runtime;
      - its Go binding is cgo linking a Rust FFI library
        (`packages/go/binding.go`: `#cgo … -lts_pack_core_ffi`);
      - parsers are "fetched on first use" (README).

      So it is not CGO-free and not offline; as a runtime it is t1954_2's
      `tscgo`.
    - **typescript-go (microsoft/typescript-go, Apache-2.0):** the Go port of
      the TypeScript compiler, discovered here; TypeScript's latest release
      line is 7.x. Its parser lives under `internal/`, which Go's import rule
      makes unimportable from another module. Documentation and layout
      evidence; not prototyped.
    - **swift-syntax, JavaParser, Rust `syn`:** each a per-language native
      parser on a third runtime (a Swift toolchain, a JVM, a Rust build).
      They are the `ktpsi` / `tsnative` pattern, with one more runtime each.
      `syn` takes `proc-macro2` token streams, where ordinary comments do
      not exist (doc comments become attributes). Documentation claims; not
      prototyped.
    - **fwcd/kotlin-language-server:** its README declares it deprecated in
      favour of Kotlin/kotlin-lsp, which was measured instead (item 17).

### Maintenance and licenses (read-only `gh api`, 2026-10-13)

25. Commits are counted over the 12 months to 2026-10-13. Licenses come
     from the LICENSE / COPYING file where the API reports NOASSERTION.

     | project | used as | latest release | commits (12 mo) | contributors | open issues | license |
     |---|---|---|---|---|---|---|
     | alecthomas/chroma | chroma | v2.27.0 (v3.0.0-alpha.5, 2026-07-08) | 221 | 344 | 37 | MIT (COPYING) |
     | pygments/pygments | pygments | 2.21.0 (2026-08-17) | 214 | 950 | 720 | BSD-2-Clause |
     | microsoft/vscode-textmate | textmate | v9.3.2 (2026-01-22) | 61 | 29 | 67 | MIT |
     | shikijs/textmate-grammars-themes | tm-grammars | 1.32.22 (npm) | 136 | 78 | 37 | MIT |
     | microsoft/TypeScript | tsnative (5.9.3) | v7.0.2 (2026-08-20, the Go-native line) | 1,829 | 1,079 | 5,131 | Apache-2.0 |
     | JetBrains/kotlin | ktpsi | v2.4.21 (2026-10-08) | 14,529 | 1,258 | 471 | Apache-2.0 |
     | antlr4-go/antlr | antlr runtime | v4.13.1 (2024-05-15) | ≤1 | 2 | 0 | BSD-3-Clause |
     | antlr/antlr4 | ANTLR tool | 4.13.2 (2024-08-03) | 5 | 427 | 1,098 | BSD-3-Clause |
     | antlr/grammars-v4 | grammars | no releases (pinned commit) | 261 | 675 | 686 | per grammar: Kotlin Apache-2.0, Java BSD, Rust MIT |
     | mvdan/sh | shfmt (t1954_1) | v3.14.1 (2026-09-06) | 473 | 111 | 86 | BSD-3-Clause |
     | golang/tools | gopls | gopls/v0.23.0 (2026-07-09) | 859 | 592 | 120 | BSD-3-Clause |
     | microsoft/pyright | pyright | 1.1.414 (2026-09-09) | 261 | 168 | 345 | MIT |
     | typescript-language-server | tsls | v6.0.2 (2026-10-09) | 102 | 57 | 21 | Apache-2.0 / MIT parts |
     | Kotlin/kotlin-lsp | kotlin-lsp | v263.6379.0 (2026-10-03, alpha) | 1,427 | 104 | 172 | Apache-2.0 (partially closed-source per README) |
     | boyter/scc | scc probe | v4.1.0 (2026-09-07) | 164 | 149 | 29 | MIT |
     | go-python/gpython | gpython probe | v0.2.0 (2023-06-28) | 4 | 24 | 59 | BSD-3-Clause |

     - The ANTLR Go runtime is the outlier: effectively unmaintained since
       2024, with two contributors.
     - The TypeScript compiler's current release line is the Go-native 7.x
       (item 24); the oracle and `tsnative` stay on 5.9.3, t1954_1's pin.

### Candidate ledger (post-phase `candidate_coverage_audit`)

26. Every candidate named in the task (lists 1–7) and in the parent's
    "Candidate approaches" (1–6), each ticked against its evidence:

    | candidate | source | disposition | evidence |
    |---|---|---|---|
    | Tree-sitter family (gotreesitter, official cgo binding, WASM) | parent 1 | prototyped by t1954_2 | `matrix_{gotreesitter,tscgo,tswasm}.md`, `findings_t1954_2.md` (regenerated on the grown corpus, item 1) |
    | Chroma | task 1, parent 2 | prototyped | `matrix_chroma.md`, items 5–8 |
    | Pygments | task 2, parent 2 | prototyped | `matrix_pygments.md`, `t3_probes.md`, items 5–8 |
    | mvdan.cc/sh/v3 | task 3, parent 3 | prototyped (t1954_1), cost analysis | `matrix_shfmt.md`, item 15 |
    | Python tokenize/ast via subprocess | task 3, parent 3 | prototyped (t1954_1), cost analysis | `matrix_pytokenize.md`, items 15, 22 |
    | pure-Go Python tokenizers (gpython; none other maintained found) | task 3 | eliminated (measured) | `t3_probes.md`, item 16 |
    | Kotlin compiler PSI | task 3, parent 3 | prototyped (`ktpsi`) | `matrix_ktpsi.md`, item 11 |
    | ktlint, detekt | task 3 | eliminated: the same PSI (build files) | item 11 |
    | kotlinx tooling (kotlinx.ast) | task 3 | eliminated: ANTLR's Kotlin grammar on the JVM (= the `antlr` Kotlin row + a JVM); last pushed 2024-08 | its README; item 12 |
    | parsers for additional target languages | parent 3 | TypeScript prototyped (`tsnative`); Java/Rust/Swift natives eliminated by runtime (item 24) | `matrix_tsnative.md`, item 10 |
    | shared adapter interface cost | task 3, parent 3 | measured | item 23 |
    | Go scanner / current custom readers | parent 3, 5 | baseline (t1954_1) | `matrix_{baseline,goscanner}.md` |
    | ANTLR4 Go runtime + grammars-v4 (Kotlin, Java, Rust) | task 4 | prototyped | `matrix_antlr.md`, items 12–14 |
    | ANTLR TypeScript lexer | task 4 | eliminated: no Go target base in grammars-v4 | item 14 |
    | gopls | task 5, parent 4 | measured | `lsp.md`, item 17 |
    | pyright | task 5, parent 4 | measured | `lsp.md`, item 17 |
    | typescript-language-server | task 5, parent 4 | measured | `lsp.md`, item 17 |
    | kotlin-language-server (fwcd, deprecated) → Kotlin/kotlin-lsp | task 5, parent 4 | kotlin-lsp measured; fwcd eliminated (deprecated) | `lsp.md`, items 17, 24 |
    | TextMate grammars (vscode-textmate / shiki) | task 6 | prototyped | `matrix_textmate.md`, item 9 |
    | ctags | task 6 | eliminated (definition tags only) | item 24 |
    | linguist / go-enry | task 6 | eliminated (file classification only) | item 24 |
    | tokei / scc | task 6 | eliminated (count-only; scc measured) | `t3_probes.md`, item 24 |
    | semgrep | task 6 | eliminated (rule matches, no comment API) | item 24 |
    | srcML | task 6 | eliminated (C/C++/C#/Java only) | item 24 |
    | difftastic | task 6 | eliminated (tree-sitter behind a diff UI) | item 24 |
    | tree-sitter-language-pack | task 6 | eliminated (cgo + download-on-first-use) | item 24 |
    | highlight.js / Prism | task 6 | eliminated by class (TextMate/Chroma/Pygments measured) | items 5–9, 24 |
    | typescript-go (discovered) | task 6 | eliminated (parser under `internal/`) | item 24 |
    | swift-syntax, JavaParser, syn (discovered) | task 6 | eliminated by runtime, `syn` drops comments | item 24 |
    | hybrid providers and refusal / fallback | parent 5 | measured by t1954_1 (`native` composite) and t1954_2 (`ts_local_error_policy.md`); recommendation inputs below | Notes for t1954_4 |
    | registry / sidecar-only annotations | task 7, parent 5 | prototyped against the real registry | `sidecar.md`, item 18 |

## Documentation claims (not verified here)

- Pygments: `ensurenl` "is required for some lexers that consume input
  linewise" (its lexer documentation). The ensurenl emulation rests on this
  claim. Measured consequence: `nonl_edit.sh` (item 4).
- kotlin-lsp: "partially closed-source", alpha (its README). Its folding and
  semantic-token behaviour is version-specific (v263.6379.0).
- tree-sitter-language-pack: "Parsers are fetched on first use and cached
  locally" (README); the download path was not exercised.
- highlight.js / Prism: output formats (HTML / token trees without offsets)
  from their documentation; not run.
- semgrep, ctags, linguist, tokei, srcML, difftastic, swift-syntax,
  JavaParser, `syn` / `proc-macro2`: capabilities as their READMEs and docs
  describe them; not run.
- typescript-go: the parser is in `internal/` (repository layout, read via
  `gh api`). No public Go API was found; a future one would change item 24.

## Assumptions

- The M2.2 policy (t1954_1's assumption) holds unchanged. Every new
  provider's mapping encodes it through the shared Layer 2 rules (data
  across a literal's whole range, interpolations included; bash `$( … )`
  inside double quotes stays an island because the highlighters type it as
  code).
- Declaring `Errors` for the highlighters (their error token) is the plan's
  rule. It lets the matrix measure how often that mechanism stays silent
  (item 5). It is not a claim that they establish certainty.
- The LSP readiness control (documentSymbol names a known function) stands
  for "the project is loaded". A server that answers documentSymbol before
  its semantic index is complete would be under-measured; each feature's own
  control guards against reading that as absence.
- The sidecar prototype keys records by test path and member name, with no
  lines. That is the simplest compatible design, not the only one (a
  sidecar could carry line hints, which would then go stale on every edit).

## Unknowns

- Whether newer releases fix the measured failures: Chroma v3 (alpha), a
  later Pygments, or grammars-v4 head. Only the pinned versions were
  measured.
- `ktpsi` on `.kts` scripts as scripts: the provider sees no path. A
  production adapter would pass the file kind (item 11). Not measured.
- LSP servers other than the four, and other configurations (gopls with
  `noSemanticString`, pyright vs basedpyright, which does serve semantic
  tokens): not measured.
- Darwin/arm64 behaviour and latency of the subprocess runtimes: linux/amd64
  only.
- Real-world evidence for TS/JS, Java, Rust and Swift remains thin in the
  six repositories (t1954_2's unknown); their results rest mainly on the
  corpus.
- The aitasks real-repository walk read a shared working tree (other
  sessions' uncommitted edits included), so it is moment-relative.

## Notes for t1954_4

- **Recommendation inputs:**
  - **Highlighters (Chroma, Pygments, TextMate) cannot authorise writes.**
    They are silent on 22 of 25 malformed fixtures (TextMate has no error
    model), and their bash heredoc rule fails by construction (items 5, 9).
    At most they are lexical hints, never certainty.
  - **The compilers' own front ends are the only candidates at 0 on every
    safety column** in their languages: `tsnative` (TS/TSX/JS) and `ktpsi`
    (Kotlin), next to t1954_1's `goscanner` and `pytokenize`. Each costs a
    runtime the release artefact does not ship: Node.js, a JVM, CPython
    (items 10, 11, 22). The budget fit is in item 20.
  - **ANTLR lexers inherit their grammar's tolerance.** Malformed input
    that the grammar can still tokenise is silent, and the Go target needs
    per-language base classes (TypeScript has none) (items 12–14).
  - **LSP:** item 17.
  - **Sidecar-only annotations are registry-compatible except for edge
    lines,** and they need an orphan check to fail closed on a moved test
    file (item 18).
- **Adapter contract to carry into any production provider:**
  - byte offsets of the original source;
  - Layer 1 per-token text validation, with gaps attributed;
  - Layer 2 construct coalescing that never absorbs the tool's comments;
  - a strict codec or a refusal;
  - a shared-provenance label whenever a provider wraps an oracle.

  Every adapter defect found here (item 4) was caught by these checks, not
  by the safety columns.
- **Rerun from one binary:** `go build -tags 't1954cgo t1954wasm'`, with
  the env vars of README "t1954_3". This session's runs used exactly that,
  and the committed matrices came from it.
- `ts_differential.md` is still measured on the 213-fixture corpus
  (item 1); a full rerun regenerates it with the then-current sibling
  repositories.
