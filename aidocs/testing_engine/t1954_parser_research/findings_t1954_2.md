# Findings — t1954_2 (the Tree-sitter family)

- Research date: 2026-10-13.
- Baseline: `annot` at `f096db065a72`, via `baseline/PIN`, unchanged from
  t1954_1. Host and toolchain: `results/environment.md`; the harness
  ran on go1.27.1.
- Candidates and versions:
  - **gotreesitter** v0.55.1 (pure Go; MIT);
  - **tscgo**: official `github.com/tree-sitter/go-tree-sitter` v0.25.0,
    with its vendored C runtime (cgo; MIT);
  - **tswasm**: that same C runtime compiled to one WASI reactor with zig
    0.17.0 (sha256-verified release tarball), run by wazero v1.12.0
    (Apache-2.0).
- Grammars: the 10 research grammars at the commits in `tsref/LOCK`, which
  are gotreesitter v0.55.1's `languages.lock`. Swift's parser was generated
  with tree-sitter CLI 0.26.9. `ts.wasm` sha256 `8368eeb5…` (16,618,675
  bytes).
- Every number below comes from a committed result file, which is named,
  and can be rerun with the commands in `README.md`.

As in t1954_1, the file keeps **observations** (measured here),
**documentation claims** (upstream's word, not verified), **assumptions**
and **unknowns** apart.

## Observations

### Harness changes (shared with t1954_3/4), all behaviour-neutral for the existing subjects

1. **`tsx` became its own research Lang.** A provider sees only the Lang,
   never the path (`Analyze(lang, src)`, `ClassifyHook(Lang, data)`). Yet
   TypeScript and TSX are different grammars: `<T>x` is a type assertion in
   `.ts` and a JSX element in `.tsx`. Matrix rows stay grouped by corpus
   directory.
2. **A refusal-reason mismatch no longer counts as record corruption.**
   An op that expected `refused:not-comment` and got `refused:uncertain`
   wrote nothing, but it fell through to the corruption default.
   - Regression test: `TestRefusalReasonMismatchIsNotCorruption`, with a
     negative control (it fails with the fix reverted).
   - No committed matrix hit that branch.
3. **`bench` and `footprint` gained flags** so the new rows are measured
   into their own files (`bench_ts.md`, `footprint_ts.md`) instead of
   re-measuring t1954_1's moment-relative rows: `--subjects`,
   `--lex-subjects`, `--labels`, `--excluded`, `--title`, `--rerun`, `--ts`,
   `--ts-only`, `--ts-out`, `--zig`.
4. **Neutrality check:** after these changes the regenerated
   `matrix_{baseline,goscanner,pytokenize,shfmt}.md`, `oracle_check.md` and
   `guard.md` are byte-identical to the committed files. `matrix.md` only
   gained rows. `realrepo` will show a `tsx | 0` row when t1954_1's reports
   are next regenerated.
5. **New verbs:** `tsdiff` (`-tags t1954cgo`) and `localpolicy`.

### One shared mapping for three runtimes — `provider/tsmap.go`

6. All three providers flatten their tree into `[]TSNode` and call
   `MapTree`, so their rows differ only by runtime. The per-language
   adapter is one kind table per grammar:
   - comment kinds;
   - data kinds (strings, templates, chars, regex, JSX text);
   - heredocs;
   - anchor kinds;
   - plus the Python docstring rule.

   `TestTSKindsExistInGrammars` fails if any listed kind is missing from
   the grammar. A bogus kind was caught (negative control).
7. **The mapping encodes the M2.2 policy**, not just the trees:
   - a data node is data over its whole range, interpolation fields
     included (an f-string field or `${…}` holding a comment is never an
     annotation line, as in pytokenize and the hand oracles);
   - bash `$( … )` inside double quotes stays code (as in M2.2 and shfmt);
   - backtick substitutions are data;
   - a comment that opens a bash continuation line is not a comment line.
     This last rule was found by the attribution pass (item 21): the tree
     was right and the mapping was wrong. Fixed, with a test and a negative
     control.
8. **`FullCover` is false, by measurement.** Tree-sitter does not
   materialise hidden tokens and extras as leaves, so leaves leave
   non-whitespace gaps. Seen in the first run: Kotlin string delimiters and
   `.`, Rust doc-comment text and raw-string openers, Python string contents
   in some shapes, bash line continuations, a leading BOM, Swift shebang and
   regex bodies. Declaring a partition would have been false, so the
   capability is not declared and range checks cover spans only.
9. **Python `expression_statement` is a supertype** at the pinned
   tree-sitter-python commit (26855eab). Neither the C runtime nor
   gotreesitter materialises it; the docstring value sits directly under
   `module`. A first reading took this for a gotreesitter divergence; a
   C-runtime dump disproved that. The mapping accepts both shapes.

### The WASM route — `tswasm/`

10a. **It builds and runs.** `tswasm/build.sh` compiles each translation
    unit separately: the C runtime (go-tree-sitter v0.25.0's `src/lib.c`,
    the same runtime tscgo links), each grammar's `parser.c`/`scanner.c`
    with its own include path, and `shim.c`. zig 0.17.0 does it with
    `--target=wasm32-wasi-musl -O2` and go-tree-sitter's own CFLAGS
    (`-std=c11 -D_POSIX_C_SOURCE=200112L -D_DEFAULT_SOURCE`), plus
    `-DHAVE_ENDIAN_H`, which the runtime's portable `endian.h` needs to
    find wasi-libc's `<endian.h>`. The result is linked as a WASI reactor:
    16,618,675 bytes, built in ≈1 min.
    - Node handles: `TSNode` is a struct passed by value, which does not
      cross the wasm boundary cleanly. So the shim walks the tree inside
      the guest and returns one flat preorder buffer per file: symbol,
      start, end, parent and flags. Each symbol name is looked up once and
      cached.
    - The only published wrapper (malivvan/tree-sitter v0.0.1) bundles
      C/C++ only (t1954_1 feasibility). Its recipe (zig, WASI reactor) was
      reused with our grammars.

### Matrices — `results/matrix_{gotreesitter,tscgo,tswasm}.md`

10. **tswasm equals tscgo in every cell**, and their trees are identical on
    every one of 6,007 inputs (`ts_differential.md`). The same C runtime
    and C scanners compiled to wasm reproduce the native trees exactly.
11. **Safety cells, gotreesitter / tscgo** (every other safety cell is 0 in
    all 8 corpus languages):

    | lang | FP-writable | Silent-uncertain | fixtures |
    |---|---|---|---|
    | bash | 4 / 4 | 0 / 0 | `lex_heredoc_body_continuation`, `lex_heredoc_strip_continuation`: heredoc **data** read as a comment annotation |
    | kotlin | 2 / 0 | 2 / 1 | `malformed_unterminated_string` (gotreesitter only), `malformed_unterminated_block` (both) |
    | swift | 2 / 2 | 1 / 1 | `malformed_nested` (both) |

    Docstring-write and Record-corruption are 0 everywhere. Python, Go,
    TS/JS, Java and Rust have no safety failure in either runtime.
12. **Recall/cost** (gotreesitter / tscgo):
    - over-refusal: bash 12 / 10, python 2 / 2, go 1 / 1, kotlin 1 / 1,
      java 1 / 1, swift 1 / 1;
    - read-mismatch: bash 7 / 7, kotlin 3 / 1, swift 3 / 3 (these come from
      the refusals and the failures above);
    - missed-comment: bash 2 / 2 (`$'…'` / `$"…"` heredoc delimiters, which
      the scanner does not decode, so the heredoc runs on);
    - missed-writable and placement: 0 in all languages;
    - fidelity and behaviour: 0 on every applied edit.

    Most over-refusals are ERROR nodes on syntax the grammar does not
    cover:
    - bash `$((`-ambiguous subshells and literal braces in expansions;
    - Python's backslash continuation followed by a comment line;
    - Kotlin `import` inside a class body;
    - Swift bare `/…/` regex literals;
    - Java unicode-escaped comment leaders.
13. **Range evidence vs the native oracles** (all three runtimes): spans pass
    in all Kotlin, Java, Rust and Swift fixtures. Where they disagree it is
    on malformed input:
    - recovery puts comments where the native tool stops;
    - JS Annex B `<!--`/`-->` comments, which the tree-sitter JS grammar
      recognises and the TypeScript parser does not;
    - a comment after a BOM, which shfmt does not report.

### The C-vs-Go differential — `results/ts_differential.md`

Inputs: the corpus plus every git-visible file of the six read-only
repositories, 6,007 files in all. Runtime failures: 0 in every runtime.

14. Mapped Results agree on 5,548 of 6,007 inputs. By grammar
    (`results/ts_scanners.md`):
    - **Python 1,895 / 1,895** agree;
    - **Go 323 / 324**;
    - **bash 1,615 / 1,689**;
    - **Kotlin 1,657 / 2,039**;
    - the TS/JS/Java/Rust/Swift files agree except 1 Rust and 1 Swift
      corpus file.

    Python's 14 tree differences, Java's 1 and JavaScript's 1 never reach
    the mapped Result.
15. **Kotlin is where the runtimes part.** On the 2,014 real Kotlin files,
    gotreesitter alone reports 370 as uncertain; the C runtime alone reports 1
    (plus 1 corpus fixture).
    - Kotlin is a *mirror* grammar: gotreesitter's tables are ts2go-extracted
      from the same `parser.c`. So this is not an owned-table difference,
      but it is still not attributed (item 21).
    - Indicators: table-or-runtime 136, recovery 105, scanner 11,
      unknown 130.
16. **bash** (corpus and real files): gotreesitter alone uncertain on 37
    files, C alone on 14.
    Indicators: scanner 55, unknown 15, recovery 3, table-or-runtime 1.

### Real repositories against the baseline — `results/ts/realrepo_*.md`

17. On **files both sides read as certain, there is no comment-class
    difference and no record difference**, for any of the three runtimes,
    across bash, Python, Go and Kotlin in all six repositories (5,775
    files). The baseline is never uncertain where a tree-sitter runtime is
    certain. **Every disagreement is a refusal the baseline does not
    make:**

    | runtime | bash refused (of 1,623) | python | go | kotlin refused (of 2,014) |
    |---|---|---|---|---|
    | gotreesitter | 82 | 0 | 0 | 495 (24.6 %) |
    | tscgo / tswasm | 61 | 0 | 0 | 126 (6.3 %) |

    Java (15 files) and Swift (2 files) are research languages, unsupported
    by the baseline, and have no reference here.

### Local-error refusal — `results/ts_local_error_policy.md`

18. Refusing only the lines around a diagnostic (±1 line) instead of the
    whole file would make **one look-alike line writable** in all three
    tree-sitter runtimes: `bash/lex_two_heredocs.sh` line 4. It recovers
    1–2 writable lines in total. Whole-file refusal (M2.2 D9) stays the
    safe default.

### Performance and footprint — `results/bench_ts.md`, `results/footprint_ts.md`

19. Footprint, from `CGO_ENABLED=0 -trimpath` probes. Each one parses with
    all 10 grammars; Δ is against the 2,021,164-byte no-op on linux/amd64:

    | probe | linux/amd64 | Δ | other targets |
    |---|---|---|---|
    | gotreesitter `grammar_subset` (10 grammars) | 17,009,379 | +14.99 MB | all four build |
    | gotreesitter, all ~206 grammars | 35,051,168 | +33.03 MB | all four build |
    | tswasm (wazero + embedded 16.6 MB wasm) | 24,345,615 | +22.32 MB | all four build |
    | tscgo | — | — | **fails under `CGO_ENABLED=0`** on every target (build constraints exclude all Go files); host cgo 19,614,464 bytes. With zig 0.17.0 as `CC`, the linux/arm64 cross build succeeds but darwin/amd64 and darwin/arm64 fail at link time (`unable to find dynamic system library "resolv"`): a macOS SDK sysroot is needed. |

    For comparison, the current `ait-testmap` is 6,329,964 bytes
    (`results/footprint.md`).

20. **Every tree-sitter runtime is OVER the 300 ms scan budget**
    (`results/bench_ts.md`). This is the budget-comparable end-to-end
    `registry.Scan` over the M2.2 shape, with bash and Python going through
    the subject; `taskset -c 0`, fastest of 3 fresh processes; host load
    1.9–2.0 on 24 CPUs before and after the run:

    | subject | cold | warm | peak RSS KiB (process) | vs budget |
    |---|---|---|---|---|
    | baseline (same-run control) | 23.8 ms | 24.7 ms | 36,824 | within (0.1×), identical to t1954_1's 23.8 ms, so the host is comparable |
    | gotreesitter | 384.5 ms | 366.8 ms | 90,916 | **OVER** (cold 1.3×, warm 1.2×) |
    | tscgo (host-only) | 497.7 ms | 495.6 ms | 36,528 | **OVER** (1.7×) |
    | tswasm | 907.0 ms | 402.2 ms | 363,364 | **OVER** (cold 3.0×, warm 1.3×); the cold number includes 412.8 ms of wazero compile for the 16.6 MB module |

    The tree-sitter parse dominates. The lexical-only rows (not
    budget-comparable) show the same per-file cost on the M2.2 shape's 420
    test files: 366.9 ms gotreesitter, 466.7 ms tscgo and 897.1 ms cold /
    378.2 ms warm tswasm, against 5.4 ms for the landed lexers. It is
    ≈50–90× the landed lexers on bash/Python test files, and gotreesitter
    is not slower than the C binding on them. On Kotlin-heavy sets
    gotreesitter is 2× slower than C (thinking_app: 2.0 s vs 0.95 s for
    397 test files).

### Attribution pass (inline post-phase `failure_attribution_pass`)

21. Every non-zero gotreesitter safety or recall cell was compared with
    tscgo on the same fixture, with both trees dumped. The cause is
    definitive only where the evidence isolates one component.

    | fixture (cell) | gotreesitter / C | tree | cause |
    |---|---|---|---|
    | bash `lex_continuation_line_is_code` (read-mismatch, policy divergence) | both | correct (a real bash comment) | **mapping — definitive**: the continuation-line policy was missing from `tsmap`; fixed (item 7) |
    | bash `lex_heredoc_body_continuation`, `lex_heredoc_strip_continuation` (FP-writable) | both | wrong: `heredoc_end` sits on the joined `prefix\`+`EOF` line, but bash joins the backslash-newline and ends the heredoc later | heuristic:scanner. The boundary is an external token in both the C scanner and its Go port. Not isolated: the scanner was not swapped. |
    | bash `lex_heredoc_ansi_c_delimiter`, `lex_heredoc_locale_delimiter` (missed-comment) | both | the heredoc runs past the real end (the delimiter is not decoded) | heuristic:scanner |
    | kotlin `malformed_unterminated_block` (silent-uncertain) | both | an EOF-terminated `multiline_comment`, no error | heuristic:scanner (`multiline_comment` is an external token in Kotlin) |
    | kotlin `malformed_unterminated_string` (FP-writable, silent-uncertain) | **gotreesitter only** | C: `ERROR [8,14)`; gotreesitter: a 1-byte `string_literal`, then identifiers, no error | heuristic:scanner-or-runtime. The tables are the same `parser.c` (mirror) and string delimiters are external tokens; the Go port vs the Go runtime is not isolated. |
    | swift `malformed_nested` (FP-writable, silent-uncertain) | both | `/* outer` parsed as the custom operator `/*`, no error | heuristic:scanner (`multiline_comment` is external) |
    | the over-refusals listed in item 12 | mostly both (bash: 3 gotreesitter-only, 1 C-only) | ERROR nodes on syntax the grammar does not cover | unknown: grammar coverage; not isolated |

    No mapping fix came out of this pass beyond item 7. The `FullCover`
    and docstring corrections (items 8 and 9) came earlier, from the first
    matrix run.

## Documentation claims (not verified here)

- gotreesitter's README: 206 grammars, "error-free trees on smoke samples".
  The research corpus, the 10 grammars and the real repositories measured
  here are a different, harder sample. They show silent recoveries
  (item 11) and, for Kotlin, many spurious ERRORs (items 15 and 17).
- gotreesitter `docs/c-parity-boards.md` (counts dated 2026-09-08): recovery
  78 cases, 36 agree on the default route; query semantics 103 cases, 101
  agree. The `cgo_harness/` that produces them is not in the published
  module and was not run here.
- wazero: the compiler backend serves amd64 and arm64 on linux and darwin
  (documentation). The per-target engine was not checked.
- The C runtime's ABI support (13–15) covers every pinned grammar
  (ABI 14 or 15).

## Assumptions

- The M2.2 policy (t1954_1's assumption) holds unchanged, and the mapping
  encodes it (item 7). A production adapter would have to encode the same
  policy for every new language. That policy is the per-language cost next
  to the kind table.
- The heuristic cause indicators are hints for triage. None is an
  attribution.
- The bench workload (the M2.2 shape) stands for real scan cost, as in
  t1954_1.

- `tree-sitter build --wasm` emits emscripten SIDE_MODULEs for
  web-tree-sitter's dynamic loader, which wazero has no linker for. That
  sub-route was not attempted; the zig/WASI reactor route above replaced it.

## Unknowns

- **Kotlin's 370 gotreesitter-only uncertain files** (item 15): runtime vs
  Go scanner port is not isolated. The grammar is a mirror, so the tables
  are excluded only to the extent that the extraction is faithful.
- Whether the shared C-runtime failures (bash heredoc continuation, Kotlin
  and Swift unterminated comments) are fixed in newer grammar versions:
  only the `languages.lock` pins were measured.
- Real-world evidence for TS/JS, Java, Rust and Swift is thin:
  - TS/JS, Rust: no files in the six repositories;
  - Java: 15 files in timexchange (25 counting the corpus);
  - Swift: 2 files in aitasks_mobile (12 counting the corpus).

  Their agreement rests mainly on the corpus.
- Peak RSS and latency on darwin and arm64: not measured. The bench ran on
  linux/amd64 only.
- The aitasks real-repository walk read a shared working tree (other
  sessions' uncommitted edits included), so it is moment-relative. The five
  sibling repositories were read as they stood.
