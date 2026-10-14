# Multi-language annotation parsers for testmap: research report (t1954)

| | |
|---|---|
| task | t1954 (children t1954_1–4), topic t1852, trail `art:trail-testmap-feature` |
| date | 2026-10-14 (final run); the child runs ran 2026-10-12 – 2026-10-13 |
| scope | how `ait test` / testmap should find `testmap:` annotations, and where to write them, in more languages than it supports today |
| harness, corpus, results | `aidocs/testing_engine/t1954_parser_research/` (here `R/`): `R/README.md` holds every rerun command |
| final evidence | `R/results/t4/` at annot `3d1a2b628`, on a 240-fixture corpus |
| raw evidence | artifact `art:t1954-researchevidence` (owner t1954, kind `research_evidence`) |

This report keeps four kinds of statement apart, as the child findings do:
- **observations** (O): measured here, each citing a committed result file;
- **documentation claims** (D): what upstream says, not verified here;
- **assumptions** (A): taken without proof;
- **unknowns** (U).

Every number cites the file that holds it.

## 1. Summary and decision

**Decision: keep the landed M2.2 readers for bash, Python, Go and Kotlin.**

The readers are go/scanner for Go and the hand-written classifiers in `goengines/internal/testmap/annot/lexctx.go` for the other three. The decision has three parts:

1. **Fix the one remaining measured defect, and put a conformance gate on the readers.** The defect is Kotlin 2.2 multi-dollar strings (§4.1).
2. **Close language expansion until a provider passes the onboarding contract in §9.** No candidate yet qualifies for a fifth language.
3. **Do not adopt sidecar-only annotations.** They stay recorded as the product option for languages without a qualifying reader.

Why this, in one paragraph. Twelve alternatives were scored through the real `ParseFile → PlanCovers → Apply` path, on the same 240-fixture corpus and on six real repositories. No alternative matches the landed readers on all four constraints that bind a production reader together:
- **safety:** no write into data, and no silent certainty on malformed input;
- **the shipped artifact:** one static `CGO_ENABLED=0` binary for four targets, with no runtime;
- **the 300 ms scan budget;**
- **the dependency allowlist:** `yaml.v3`, `doublestar/v4`, `x/sync`.

Each alternative fails at least one. The exception is go/scanner, which already *is* the landed Go reader:
- the language-native tools that are safe need a runtime the release does not ship: CPython, Node.js or a JVM;
- the pure-Go families are either unsafe (regex highlighters, ANTLR lexers, mvdan/sh on heredocs) or over the budget, and also over the dependency policy (every Tree-sitter runtime, 1.3–3.4× the budget);
- no language server returns comment ranges together with certainty.

The table in §3 has the numbers.

**What changes for the four supported languages:**
- **A conformance gate.** The research corpus, which already found two real reader defects, becomes a hermetic `go test` gate inside goengines (follow-up t1991).
- **The Kotlin defect.** The Kotlin reader must model Kotlin 2.2 multi-dollar strings or fail closed on them. Today a valid file can make it read, and let `Apply` write, a look-alike inside a raw string (follow-up t1990).
- **A language-version clause (§8.3).** Each reader names the syntax it models and fails closed beyond it.
- **A shared Kotlin-family lexer, under evaluation.** The same blind spot appeared independently in three hand lexers: annot, `deps/kotlinlex.go` and `deps/gradlelex.go`. Whether they should share one lexical core is follow-up t1992.

**What changes for other languages:** nothing ships.
- gotreesitter is the leading candidate for TS/JS, Java and Rust: 0 safety failures on the corpus in those languages. Its gaps are measured and named (§7).
- The compiler front ends (`tsnative`, `ktpsi`) and the native oracles are the reference tools any onboarding must be checked against.

**The user's concern.** The user did not accept "an expanding collection of custom readers" as an *unexamined* strategy. The readers are now examined:
- every alternative was measured against them, and the result is in this report;
- their two measured defects are fixed (t1969) or filed (t1990);
- a regression will fail `go test` (t1991);
- a fifth reader cannot be added without passing a written contract (§9).

The collection does not expand by default. It expands only through that gate.

## 2. Method

**Seam.** `R/baseline/seam.patch` adds two nil-by-default hooks to an immutable snapshot of `annot`, extracted from a commit (`git archive`), never from the working tree:
- `ClassifyHook` in `Classify`;
- `LangHook` in `LangOf`.

A provider replaces only the lexical layer. The landed grammar, placement and rewriter (`ParseFile`, `PlanCovers`, `Apply`, with Apply's ownership, snapshot and before/after checks) run unchanged on its output. The guard builds the baseline matrix from the unpatched snapshot and from the patched-but-unhooked one; they must be identical. They are, at both pins (O: `R/results/guard.md`, `R/results/t4/guard.md`; negative control in `R/findings_t1954_1.md` item 1).

**Corpus: 240 fixtures** (O: `R/results/t4/oracle_check.md`).

| language | fixtures | of which |
|---|---|---|
| bash | 69 | M2.2's own adversarial tables and placement goldens, imported from the pinned commit, plus hand oracles |
| Python | 67 | ditto, plus the docstring-value table |
| Go | 22 | |
| Kotlin | 31 | |
| TS / TSX / JS | 19 | |
| Java | 11 | |
| Rust | 10 | |
| Swift | 11 | |

- t1954_1 built 213 fixtures.
- t1954_3 added 16: non-ASCII positions and TS/JS anchors.
- t1954_4 added 6 language-version fixtures:
  - Kotlin 2.2 multi-dollar strings ×4;
  - Python 3.14 t-strings;
  - bash 5.3 `${ …; }` substitutions.
- The pin move re-imported M2.2's tables at `3d1a2b628`, which adds t1969's 5 BOM cases.
- Every fixture has a hand `.expect` that keeps four things apart: read records, writable lines, read-only lines and look-alikes. Edit fixtures add an `.edits` file with the full expected record list after each operation.
- Native tools cross-check the hand oracle: 240 fixtures, 0 disagreements (O: `R/results/t4/oracle_check.md`; the tools are in §8.1).

**Metrics** (per subject × language × case):
- **safety** (must be 0):
  - FP-writable: a look-alike or read-only line classed Comment, or accepted by `Apply`;
  - Docstring-write;
  - Silent-uncertain: a malformed file reported certain;
  - Record-corruption: any record other than the intended one changes after an applied edit.
- **recall and cost:** missed-writable, missed-comment, read-mismatch, over-refusal, placement.
- **fidelity** on every applied edit: bytes, CRLF, final newline, BOM, file mode.
- **range checks** where a provider exposes byte ranges.
- **behaviour:** controlled fixtures executed before and after each applied edit.

**Subjects (13)** — the landed baseline; three language-native tools; two compiler front ends; three Tree-sitter runtimes; ANTLR; three highlighters:

| subject | what it is |
|---|---|
| `baseline` | the landed readers |
| `goscanner` | go/scanner |
| `pytokenize` | CPython `tokenize` + `ast` |
| `shfmt` | mvdan.cc/sh/v3 |
| `tsnative` | the TypeScript compiler's parser |
| `ktpsi` | the Kotlin compiler's PSI |
| `gotreesitter` | pure-Go Tree-sitter |
| `tscgo` | official go-tree-sitter, cgo |
| `tswasm` | the same C runtime as WASI under wazero |
| `antlr` | ANTLR4 Go runtime + grammars-v4 lexers |
| `chroma` | regex highlighter (Go) |
| `pygments` | regex highlighter (Python) |
| `textmate` | vscode-textmate + oniguruma |

LSP servers and sidecar-only annotations are separate experiments (§4.7, §4.8).

**Two pins, both reproduced.**
- **Research pin `f096db065`** (t1853_2's commit). t1954_1–3 ran at this pin. Rerunning their guard, every matrix, the oracle check and the local-error policy from the **committed** inputs reproduced the committed files **byte for byte** (O: `R/results/t4/README.md`).
- **Final pin `3d1a2b628`.** This was the then-current `annot` commit. After the pin it carries:
  - t1969's BOM fix;
  - t1853_3's scanners and `annotate` arms;
  - t1854_1's runner keys.
- **Pin comparison.** On the same 240-fixture corpus, at both pins, **five cases differ, all in the baseline and all BOM cases that t1969 fixed**:
  - `python/bom_doc.py`;
  - t1969's own four BOM test cases.

  The other 12 subjects are identical across the pins (O: `R/results/t4/pin_compare.md`; §4.1).

**Real repositories** (O: `R/results/t4/inputs.md`). The six registered repositories (aitasks, aitasks_go, aitasks_mobile, thinking_app, thinking_backend, timexchange) were walked read-only. Each walk read a **temporary checkout of a recorded commit**, never a live working tree, so every input can be rebuilt from its commit. The child-era walks read live trees, so their inputs cannot be rebuilt (`R/results/t4/inputs.md`).

**Performance.**
- The budget-comparable operation is the end-to-end `registry.Scan` over M2.2's bench shape: 420 annotated tests, a quarter of them Python.
- Each subject enters through `ClassifyHook` for its languages.
- Measurement: `taskset -c 0`, fastest of 3 fresh processes; cold includes provider and runtime start-up; warm is a separate process.
- Lexical-only timings are labelled "not budget-comparable".

Footprint comes from `CGO_ENABLED=0 -trimpath` probes for linux/darwin × amd64/arm64.

**Environment:** `R/results/t4/environment.md` (linux/amd64, Intel Core Ultra 9 275HX, 24 CPUs, go1.27.1).

## 3. Candidate matrix

### 3.1 Safety (final run)

O: `R/results/t4/matrix.md`. Each cell is **FP-writable / Docstring-write / Silent-uncertain / Record-corruption**; "—" means the subject does not support that language; † means the subject has no error model, so Silent-uncertain cannot be measured.

| subject | bash (69) | python (67) | go (22) | kotlin (31) | TS/TSX/JS (19) | java (11) | rust (10) | swift (11) |
|---|---|---|---|---|---|---|---|---|
| baseline | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 3/0/0/1 | — | — | — | — |
| goscanner | — | — | 0/0/0/0 | — | — | — | — | — |
| pytokenize | — | 0/0/0/0 | — | — | — | — | — | — |
| shfmt | 2/0/1/0 | — | — | — | — | — | — | — |
| ktpsi | — | — | — | 0/0/0/0 | — | — | — | — |
| tsnative | — | — | — | — | 0/0/0/0 | — | — | — |
| gotreesitter | 4/0/0/0 | 0/0/0/0 | 0/0/0/0 | 2/0/2/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 2/0/1/0 |
| tscgo | 4/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/1/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 2/0/1/0 |
| tswasm | 4/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/1/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 2/0/1/0 |
| antlr | — | — | — | 2/0/3/0 | — | 2/0/1/0 | 2/0/1/0 | — |
| chroma | 22/0/8/3 | 1/0/3/0 | 2/0/1/0 | 10/0/3/0 | 2/0/1/0 | 2/0/2/0 | 0/0/2/0 | 2/0/2/0 |
| pygments | 22/0/8/3 | 1/0/3/0 | 2/0/1/0 | 8/0/3/0 | 2/0/1/0 | 2/0/2/0 | 0/0/2/0 | 0/0/2/0 |
| textmate | 12/0/0†/0 | 4/0/0†/0 | 0/0/0†/0 | 14/0/0†/0 | 0/0/0†/0 | 2/0/0†/0 | 0/0/0†/0 | 0/0/0†/0 |

The fixture count per language is in the header row. TS/TSX/JS is one corpus directory.

Read across a row and the pattern is plain:
- **0 on every safety column in every language they support:**
  - the landed readers, in bash, Python and Go;
  - the native tools, goscanner and pytokenize;
  - the two compiler front ends, ktpsi and tsnative.
- **Unsafe in bash, Kotlin or Swift:** every Tree-sitter runtime.
- **Unsafe in most languages they support:** ANTLR, Chroma and Pygments.
- **TextMate** is 0 in several languages but has no error model, so it cannot authorise any write.

The baseline's Kotlin cells come from one fixture, `kotlin/multidollar_comment_desync.kt` (§4.1).

### 3.2 Deployment and cost

| subject | runtime the host must provide | static `CGO_ENABLED=0` binary, 4 targets | binary Δ (linux/amd64) | end-to-end scan vs the 300 ms budget | real Kotlin files refused where the baseline is certain |
|---|---|---|---|---|---|
| baseline (landed) | none | yes | `annot` +2.37 MB (already shipped) | 24.7 ms cold / 26.9 ms warm: **0.1×** | — (reference) |
| goscanner | none | yes | +0.55 MB | — (it is the landed Go reader) | — |
| shfmt | none | yes | +1.01 MB | 45.5 ms: 0.2× (bash via shfmt) | — |
| pytokenize | CPython | n/a (subprocess) | — | 120.4 ms: 0.4× (Python via subprocess) | — |
| native composite (shfmt + pytokenize + goscanner) | CPython | — | — | 138.3 ms: 0.5× | — |
| ktpsi | a JVM (JDK 352.5 MB + 63.6 MB of jars) | n/a (subprocess) | — | **not informative**: the bench shape has no Kotlin, so the cold 402 ms is JVM start-up | 21 (1.0%) |
| tsnative | Node.js (123.8 MB + typescript 23.6 MB) | n/a (subprocess) | — | **not informative**: no TS/JS in the shape | — |
| gotreesitter | none | yes | +14.99 MB (10 grammars); +33.0 MB (all) | 433 ms cold / 397 ms warm: **OVER 1.4×** | 495 (24.6%) |
| tscgo | a C toolchain (cgo) | **no** | +17.6 MB (host cgo build) | 525 ms / 590 ms: **OVER 1.8×** | 126 (6.3%) |
| tswasm | none | yes | +22.3 MB | 1,008 ms cold / 438 ms warm: **OVER 3.4×**; peak RSS 364 MiB | 126 (6.3%) |
| antlr | none | yes | +1.32 MB | **not informative**: no Kotlin, Java or Rust in the shape | 1 (0.05%) |
| chroma | none | yes | +6.39 MB (every lexer; no subset) | **cannot run**: it fails closed on the first Python test (`unsupported:DocLiterals`) | 168 (8.3%) |
| pygments | CPython (+20.6 MB library) | n/a (subprocess) | — | **cannot run** (same) | 75 (3.7%) |
| textmate | Node.js (+13.4 MB) | n/a (subprocess) | — | **cannot run** (same) | 0, because it has no error model and never refuses |

Sources:
- `R/results/t4/bench.md` (end-to-end scan: the M2.2 bench shape, whose 420 tests are bash and Python; `taskset -c 0`, fastest of 3);
- `R/results/t4/footprint*.md`;
- `R/results/t4/realrepo_totals.md` (Kotlin refusals).

The current `ait-testmap` built from the final pin is 8,092,059 bytes. The landed `annot` package costs +2.37 MB of it (O: `R/results/t4/footprint.md`).

### 3.3 Families not run through the seam

| family | why it is not a seam provider | evidence |
|---|---|---|
| LSP servers (gopls, pyright, typescript-language-server, kotlin-lsp) | no server returns comment ranges and certainty in one answer: gopls tokens cannot tell a `//` line inside `/* … */` from a real comment; pyright advertises neither feature; the TS server and kotlin-lsp emit no comment tokens even for a block-comment control; certainty is asynchronous `publishDiagnostics` at best | O: `R/results/t4/lsp.md` (rerun), `R/findings_t1954_3.md` item 17 |
| sidecar-only annotations | a product alternative, not a reader: registry-compatible except the 735 covers-edge `line:` fields; needs an orphan check to fail closed on a moved test | O: `R/results/t4/sidecar.md` (rerun), item 18 |
| highlight.js, Prism, scc, tokei, ctags, linguist/go-enry, semgrep, srcML, difftastic, tree-sitter-language-pack, typescript-go, swift-syntax, JavaParser, `syn`, gpython | eliminated by evidence or by class (§5) | `R/findings_t1954_3.md` items 16, 24, 26 |

## 4. Per-family evaluation

### 4.1 The landed readers (baseline)

**Observations**
- **Bash, Python and Go: 0 on every safety column** at the final pin (`R/results/t4/matrix.md`).
  - Python and Go are 0 on every recall, cost, placement, fidelity and behaviour column too.
  - Bash has 3 over-refusals and 2 read-mismatches, all fail-closed costs:
    - a `$((`-ambiguous subshell;
    - an ANSI-C heredoc delimiter;
    - a multi-line heredoc inside backticks.
  
  Bash 5.3 execution shows these files are valid (`R/findings_t1954_1.md` item 10).
- **Python's UTF-8 BOM defect is fixed.**
  - Before t1969, a BOM-prefixed module lost its docstring record, and a fresh insertion landed above the BOM, which broke the module. At `f096db065`: Record-corruption 3, fidelity 1, behaviour 2.
  - At `3d1a2b628` every column is 0. The BOM cases are the only cases that changed between the pins in any subject (`R/results/t4/pin_compare.md`).
  - t1969's five BOM test cases (now corpus fixtures) are 0 everywhere.
- **Kotlin: one defect, Kotlin 2.2 multi-dollar strings** (`kotlin/multidollar_comment_desync.kt`; FP-writable 3, Record-corruption 1).
  - Mechanism: in `$$"""…"""`, only a `$$` run starts a template, so a lone `${` is literal text. The reader takes it for a template.
  - With `${/*` inside such a string, the reader opens a block comment, leaves it at a later `// */` line comment, and ends up outside the raw string that the next look-alike line is really inside.
  - It reads that line as a real annotation, and **`Apply` applies a write into the string's content** (want `refused:not-comment`).
  - kotlinc 2.4.21 compiles the fixture (`R/results/t4/oracle_check.md`).
  - The other three multi-dollar fixtures are safe; one is over-refused.
  - The defect is identical at both pins: it is pre-existing, not a regression.
  - ktpsi, gotreesitter, tscgo and tswasm are safe on all four (`R/results/t4/matrix_*.md`).
  - Exposure on 2026-10-14: no `.kt`/`.kts` file in the six snapshots contains `$$"`.
  - The same blind spot was found in the same week in `deps/kotlinlex.go` (t1980) and in the Gradle blanker (t1975). Both were made to fail closed.
- **Language-version probes** (t1954_4 fixtures `python/tstrings_314.py`, `bash/funsub_53.sh`): 0 on every column.
  - The Python reader handles 3.14 t-strings with PEP 701 quote reuse. A comment inside a field is classed as data, per the M2.2 policy, exactly as `tokenize`+`ast` do.
  - The bash reader handles 5.3 `${ …; }` / `${| …; }`, including a heredoc inside one, exactly as shfmt and bash execution do.
- **Real repositories:** 7,866 files of the six snapshots were walked: bash 1,630, Python 1,842, Go 359, Kotlin 2,014, plus 21 files in the research languages. The baseline is **never uncertain** on any of them, and no candidate differs from it in any **annotation record** on any file (`R/results/t4/realrepo_totals.md`).
- **Speed:** 24.7 ms cold and 26.9 ms warm on the budget-comparable scan, 0.1× the 300 ms budget. Lexical-only: 6.0 ms for the 420 bench-shape test files, and 60.5 ms for aitasks' 855 test files (`R/results/t4/bench.md`).
- **Size:** `annot` costs +2.37 MB (`R/results/t4/footprint.md`).
- **Implementation size:** `annot/lexctx.go` is 928 lines for bash, Python, Go and Kotlin (Go delegates to go/scanner). The `deps` package adds `kotlinlex.go` (247 non-comment lines) and `gradlelex.go` (299) for dependency scanning (`git ls-tree` at `7f1d0614a`).

**Assumptions**
- The M2.2 policy is the right product rule for every language: an annotation lives only on a standalone line comment, outside strings, heredocs, block comments, backtick substitutions, continuation lines and interpolation fields. It is what the hand oracles encode.

**Unknowns**
- Syntax newer than the corpus. The multi-dollar defect shows this class is real (§8.3).
- Behaviour on darwin and arm64: the runs were linux/amd64 only.

### 4.2 Language-native tools (go/scanner, Python tokenize + ast, mvdan/sh)

**Observations**
- **goscanner:** 0 on every column, and range checks pass (`R/results/t4/matrix_goscanner.md`). It agrees with the baseline on every Go file of the snapshots (359 files; 0 comment-class differences, `R/results/t4/realrepo_totals.md`). The baseline Go reader *is* go/scanner, so this is partly self-consistency.
- **pytokenize:** 0 on every safety column. It has 2 over-refusals: lexically valid files with grammar errors, which `ast` rejects by construction. Real repositories: 1,842 files, 0 comment-class differences and 0 record differences against the baseline (`R/results/t4/realrepo_totals.md`).
  - It is the only complete Python docstring model among the subjects: content bounds, raw flags and the statement end.
  - It needs a CPython subprocess (`R/results/t4/footprint_t3.md`). The release ships no interpreter.
- **shfmt (mvdan/sh v3.14.1): unsafe on bash heredocs.**
  - FP-writable 2: in an unquoted `<<-` heredoc it matches the delimiter before joining a backslash-newline, so heredoc **data** reads as an annotation. Bash execution confirms the hand oracle.
  - Silent-uncertain 1: an unterminated heredoc inside backticks.
  - Over-refusal 8 (`R/results/t4/matrix_shfmt.md`; mechanism in `R/findings_t1954_1.md` item 14).
  - It is pure Go, +1.01 MB.

**Documentation claims:** none relied on.

**Assumptions:** none beyond §4.1.

**Unknowns**
- A maintained pure-Go Python tokenizer with 3.12 f-string support was not found.
- gpython v0.2.0 emits no comment tokens (`R/results/t3_probes.md`).

### 4.3 Tree-sitter (gotreesitter, tscgo, tswasm)

**Observations**
- **One shared mapping** (`R/provider/tsmap.go`) serves all three runtimes, so their rows differ only by runtime.
  - tswasm equals tscgo in every matrix cell.
  - The runtime differential covers 6,106 inputs: the 240 fixtures plus the files of the six snapshots. It has 0 runtime failures. tswasm and tscgo trees are identical on all 6,106. gotreesitter and tscgo give identical mapped Results on 5,646, and the differences concentrate in Kotlin and bash (`R/results/t4/ts_differential.md`).
  - Safety: 0 in Python, Go, TS/JS, Java and Rust in all three runtimes.
  - Failures, with heuristic cause indicators pointing at the grammars' external scanners (`R/findings_t1954_2.md` items 11 and 21):
    - **bash FP-writable 4:** heredoc data after a backslash continuation;
    - **Kotlin:** gotreesitter has FP-writable 2 and Silent-uncertain 2; tscgo and tswasm have Silent-uncertain 1;
    - **Swift:** FP-writable 2 and Silent-uncertain 1 on a nested comment parsed as an operator.
  
  Source: `R/results/t4/matrix.md`.
- **Over-refusal**, mostly ERROR nodes on syntax the grammars do not cover:
  - gotreesitter: bash 13, Python 2;
  - tscgo and tswasm: bash 11, Python 2;
  - every runtime: 1 each in Go, Kotlin, Java and Swift.

  New in t1954_4: bash 5.3 `${ …; }` is an ERROR in every runtime (`R/results/t4/matrix.md`).
- **Real files refused where the baseline is certain** (`R/results/t4/realrepo_totals.md`):
  - Kotlin: gotreesitter 495 of 2,014 (24.6%); tscgo and tswasm 126 (6.3%);
  - bash: gotreesitter 82 of 1,630; tscgo and tswasm 61.

  On the files both sides read as certain there is no comment-class and no record difference. These are the child era's figures too, although the child era read live trees (`R/findings_t1954_2.md` item 17).
- **Local refusal is unsafe.** Refusing only ±1 line around a diagnostic makes one look-alike writable in every runtime (`R/results/t4/ts_local_error_policy.md`). Whole-file refusal stays.
- **Every runtime is over the 300 ms scan budget** (end-to-end scan, cold / warm: gotreesitter 433 / 397 ms (1.4× / 1.3×), tscgo 525 / 590 ms (1.8× / 2.0×), tswasm 1,008 / 438 ms (3.4× / 1.5×; peak RSS 364 MiB, the cold figure includes compiling the 16.6 MB wasm module). Lexical-only on the 420 bench-shape files: 397–933 ms against 6.0 ms for the landed readers. Sources: `R/results/t4/bench.md`, `R/findings_t1954_2.md` item 20).
- **Footprint** (`R/results/t4/footprint_ts.md`):
  - gotreesitter: +14.99 MB for the 10-grammar subset, +33.0 MB for all ~206 grammars;
  - tswasm: +22.3 MB;
  - tscgo: does not build with `CGO_ENABLED=0` on any target; a darwin cross build needs a macOS SDK sysroot.

**Documentation claims**
- gotreesitter's README: 206 grammars, "error-free trees on smoke samples". The research corpus is harder and shows silent recoveries.
- Its C-parity boards (2026-09-08) were not run here.

**Assumptions**
- The cause indicators in the attribution pass are triage hints, not attributions.

**Unknowns**
- gotreesitter's 370 gotreesitter-only uncertain Kotlin files have not been attributed to the runtime or the scanner port (child era).
- Whether newer grammar versions fix the shared C-runtime failures.
- A per-language subset footprint (for example TS/JS alone) was not measured.

### 4.4 Regex highlighters (Chroma, Pygments, TextMate)

**Observations**
- **Chroma and Pygments have a non-zero safety cell in every language** (`R/results/t4/matrix.md`):
  - bash FP-writable 22: their shared heredoc rule `<<-?\s*('?)\\?(\w+)[\w\W]+?\2` ends a heredoc at the first occurrence of the delimiter word anywhere;
  - Silent-uncertain 22 across the languages: an `Error` token fires only on a character no rule matches, so an unterminated construct ends the input without any diagnostic (`R/findings_t1954_3.md` item 5).
- **TextMate has no error model**, so every write is `unsupported:Errors`. It also reads look-alikes as comments in bash (12), Kotlin (14, including the multi-dollar fixtures), Python (4) and Java (2).
- **No docstring model.** Pygments' `String.Doc` covers 15 of 35 module docstrings, so Python writes are unsupported (`R/results/t3_probes.md`).
- **The lexical step alone is 3–6× the whole scan budget** on the 420 bench-shape files (Chroma 855 ms, Pygments 976 ms, TextMate 1,826 ms, against 6.0 ms for the landed readers. Their end-to-end scan cannot run at all: without a docstring model they fail closed on the first Python test (`R/results/t4/bench.md`)).
- **Byte fidelity holds when the tools are driven correctly.** Chroma needs explicit `TokeniseOptions`; Pygments needs `get_tokens_unprocessed` and ensurenl emulation (`R/findings_t1954_3.md` item 6).

**Documentation claims**
- highlight.js and Prism are the same mechanism with less output; they were eliminated by class, not run.

### 4.5 Compiler front ends (tsnative, ktpsi)

**Observations**
- **tsnative:** 0 on every safety column and Placement 0 in TS/TSX/JS (`R/results/t4/matrix_tsnative.md`).
  - Its range agreement is **self-consistency**: it shares `oracle/ts_oracle.js` with the `ts-parser` oracle.
  - Its independent evidence is the hand oracle, the non-ASCII and anchor fixtures, and the oracle's self-test with a naive-scanner negative control.
  - It over-refuses 1 file: Annex B HTML comments in `.js`.
- **ktpsi:** 0 on every safety column in Kotlin, including all four multi-dollar fixtures (`R/results/t4/matrix_ktpsi.md`).
  - It over-refuses 2 files: an `import` inside a class, and a `.kts` script parsed as `.kt`, because a provider sees the language, not the path.
  - Real Kotlin files: on all 2,014 Kotlin files of the snapshots, **0 comment-class and 0 record differences** against the landed Kotlin reader; it refuses 21 files (1.0%) that the baseline reads as certain (`R/results/t4/realrepo_totals.md`).
- **Cost:** a runtime the release does not ship (`R/results/t4/footprint_t3.md`):
  - Node.js 123.8 MB plus typescript 23.6 MB;
  - a JDK 352.5 MB plus 63.6 MB of compiler jars.
  
  JVM start-up dominates ktpsi's cold time (932 ms cold against 182 ms warm on aitasks_mobile's 37 Kotlin test files; 2,724 ms cold on thinking_app's 396 (`R/results/t4/bench.md`)).

**Documentation claims**
- ktlint and detekt build on the same PSI (their build files), so they are redundant with ktpsi.

### 4.6 ANTLR4 + grammars-v4 lexers (Kotlin, Java, Rust)

**Observations**
- **Silent on malformed input that the grammar can still tokenise** (`R/results/t4/matrix_antlr.md`):
  - Silent-uncertain: Kotlin 3, Java 1, Rust 1;
  - FP-writable 2 in each language, from unterminated block comments;
  - token recognition errors on valid files: Java text blocks and `\u` escapes; Kotlin 2.2 `$$` strings.
- **Per-language code, not just a grammar file:**
  - Rust needs a Go base class;
  - TypeScript has no Go target base at all;
  - 252 KB of generated Go for 3 lexers.
- **Maintenance:** the Go runtime was last released 2024-05, with 2 contributors (`R/findings_t1954_3.md` item 25).
- **Footprint:** +1.32 MB (`R/results/t4/footprint_t3.md`).

### 4.7 LSP servers

**Observations** (`R/results/t4/lsp.md`)
- One protocol-correct experiment per server, each with independent per-feature controls:
  - **gopls v0.23.0** emits `comment` semantic tokens, but cannot tell a `//` line inside `/* … */` from a real line comment: look-alike lines read like annotation lines.
  - **pyright 1.1.414** advertises neither semantic tokens nor folding ranges.
  - **typescript-language-server 6.0.2** has no `comment` token type.
  - **kotlin-lsp v263.6379.0** lists `comment` in its legend but emits none, even for the control's block comment.
- Comment folds cover look-alike lines.
- Certainty is asynchronous `publishDiagnostics` at best.
- Deployment: one server per language, a project per server, a runtime, and readiness waits.

**Unknowns**
- Other servers and configurations, for example basedpyright, which serves semantic tokens.

### 4.8 Sidecar-only annotations (product alternative)

**Observations** (`R/results/t4/sidecar.md`)
- All 735 records of the bench shape were moved into per-file YAML sidecars. The real `registry` yields identical units, edges and variants: 420 / 735 / 0.
- The rendered `_scanned.yaml` is byte-identical **once the 735 `line:` fields are removed**.
- A path-keyed sidecar orphaned by a moved test file **succeeds on a stale record** unless an orphan check fails closed.
- Consumer impact:
  - M4.2's `stale --confirm` would need its own stamp-write path;
  - the repair loop would need a second writer;
  - M6.3 adoption and M7.4 author annotation already write sidecar-shaped registry rows.

**Assumptions**
- The prototype keys records by path and member and carries no line hints. That is the simplest compatible design, not the only one.

### 4.9 Other approaches (eliminated)

See §5.

## 5. Rejected alternatives

| alternative | decisive evidence | file |
|---|---|---|
| mvdan/sh as the bash reader | FP-writable 2 (heredoc data after a continuation in `<<-`), Silent-uncertain 1 | `R/results/t4/matrix_shfmt.md` |
| Python tokenize + ast as the production reader | safe, but needs CPython at run time; the release ships one static binary | `R/results/t4/footprint.md` |
| gotreesitter (pure Go) for the supported four | bash FP-writable 4, Kotlin FP-writable 2 / Silent-uncertain 2; over the budget; +15–33 MB; a dependency-policy change; refuses 24.6% of real Kotlin files (child era) | §4.3 |
| official go-tree-sitter (cgo) | cannot build with `CGO_ENABLED=0`; darwin cross builds need an SDK sysroot; over the budget | `R/results/t4/footprint_ts.md` |
| Tree-sitter as WASM under wazero | identical results to cgo; +22.3 MB; cold scan 3.4× the budget, including the wasm compile; peak RSS 364 MiB | `R/results/t4/bench.md` |
| Chroma / Pygments | unsafe in every language; no docstring model; lexical step 3–6× the budget | §4.4 |
| TextMate (vscode-textmate; also stands for highlight.js and Prism) | no error model, so no write can be authorised; Kotlin, Python and Java look-alikes read as comments | `R/results/t4/matrix_textmate.md` |
| ANTLR4 + grammars-v4 | silent on malformed input that still tokenises; unmaintained Go runtime; per-language base classes | §4.6 |
| TypeScript compiler (`tsnative`), Kotlin PSI (`ktpsi`) as production readers | safe, but each needs a runtime (Node.js, a JVM) that the release does not ship; kept as **dev-time oracles** | §4.5 |
| LSP servers | no comment ranges plus certainty in one response | §4.7 |
| pure-Go Python tokenizers (gpython) | emits no comment tokens; would be a custom reader by another route | `R/results/t3_probes.md` |
| ktlint, detekt, kotlinx.ast | the same PSI, or ANTLR's Kotlin grammar on a JVM | `R/findings_t1954_3.md` item 26 |
| scc, tokei | count-only, no positions | `R/results/t3_probes.md` |
| universal-ctags, linguist/go-enry, semgrep, srcML, difftastic | symbols, file classification, rule matches, C-family only, a diff UI: none exposes comment ranges (documentation claims) | `R/findings_t1954_3.md` item 24 |
| tree-sitter-language-pack | cgo plus a download on first use (not offline) | ditto |
| typescript-go | its parser is under `internal/` and cannot be imported (layout evidence) | ditto |
| swift-syntax, JavaParser, Rust `syn` | one more runtime each; `syn` drops ordinary comments (documentation claims) | ditto |
| local (±1 line) refusal around a diagnostic | makes a look-alike writable in every Tree-sitter runtime | `R/results/t4/ts_local_error_policy.md` |
| sidecar-only annotations as the default | loses the line anchor and co-location; needs an orphan check and a second writer; not needed for the four supported languages | §4.8 |

## 6. Dependency, licensing and maintenance

| component | role | license | dependency-policy impact | maintenance signal (12 months to 2026-10-13) |
|---|---|---|---|---|
| go/scanner (std) | Go reader (landed) | BSD-3 (Go) | none | Go toolchain |
| `annot` hand readers | bash, Python, Kotlin (landed) | repository | none | in-repo; three edits since the research pin |
| mvdan.cc/sh/v3 | candidate | BSD-3 | a new module | v3.14.1 (2026-09); 473 commits; 111 contributors |
| gotreesitter | candidate | MIT, plus 206 bundled grammar licenses (`licenses/grammars.json`) | a new module; +15–33 MB | v0.55.1 (2026-09-26); 23 contributors; a bundle that pins all grammars together |
| go-tree-sitter + C grammars | reference | MIT | cgo, which breaks the release build | no GitHub releases; 6 contributors |
| wazero | WASM runtime | Apache-2.0 | a new module; +22 MB | v1.12.0 (2026-05); 86 contributors |
| grammars (bash, Python, Go, JS, TS, Java, Rust; Kotlin and Swift from community repositories) | Tree-sitter | MIT | — | none archived; Kotlin's last release is 2024-08 with commits to 2026-08, so pin commits, not tags (`R/results/ts_grammars.md`) |
| Chroma v2 | candidate | MIT | a new module; +6.4 MB (all lexers, no subset) | 221 commits; v3 is alpha |
| Pygments | candidate | BSD-2 | CPython at run time | 2.21.0 (2026-08) |
| vscode-textmate, tm-grammars | candidate | MIT | Node.js at run time | 9.3.2; 1.32.22 |
| TypeScript 5.9.3 | oracle and tsnative | Apache-2.0 | Node.js at run time | 7.x is the Go-native line; its parser is `internal/` |
| Kotlin compiler 2.4.21 (PSI) | oracle and ktpsi | Apache-2.0 | a JVM at run time | 14,529 commits |
| ANTLR4 Go runtime | candidate | BSD-3 | a new module; +1.3 MB | last release 2024-05; 2 contributors |
| grammars-v4 | ANTLR lexers | per grammar (Apache-2.0, BSD, MIT) | — | no releases; pinned commit |

Sources: `R/findings_t1954_3.md` item 25 and `R/results/ts_grammars.md`. Licenses were read from LICENSE/COPYING files, and every activity number is moment-relative.

**The allowlist** (goengines `yaml.v3`, `doublestar/v4`, `x/sync`, enforced by `guards_test.go`) admits **none** of the candidate modules. Every pure-Go alternative is a dependency-policy change on top of its measured gaps. The landed readers need none.

## 7. Recommendation

1. **Keep the landed readers as the production providers** for bash, Python, Go and Kotlin. They are the only configuration that meets all of these:
   - 0 safety failures in bash, Python and Go;
   - no shipped runtime and no new dependency;
   - ≈0.1× the scan budget.
   
   Kotlin also qualifies once t1990 makes the reader model or refuse multi-dollar strings.
2. **Gate them.** Make the bash, Python, Go and Kotlin part of this corpus a hermetic `go test` conformance suite in `annot` (t1991). The research harness has found two reader defects that `annot`'s own tests missed: the BOM, and multi-dollar strings.
3. **Fix the Kotlin multi-dollar defect** (t1990, advisory). Exposure today is nil, and the fix is the same modelled-or-fail rule that t1975 and t1980 applied to the `deps` lexers.
4. **Evaluate one shared Kotlin-family lexical core** for `annot` and `deps` (t1992, advisory after F2). The same construct broke three independent hand lexers in one week.
5. **No candidate yet for a fifth language.**
   - None of the five M10 target repositories needs one: they are bash, Python, Go and Kotlin, and aitasks_mobile's 2 Swift files are not test files.
   - When a target does need one, onboarding follows §9.
   - **gotreesitter** is the leading candidate for TS/JS, Java and Rust: 0 safety failures in those languages on the corpus, pure Go, and an AST that gives the placement anchors. Its gaps must be closed first:
     - the footprint of a per-language subset;
     - the budget for that language's share of a scan (or a cache);
     - the dependency-policy change;
     - real-file evidence. The six repositories hold almost no TS/JS, Java or Rust.
   - Swift has no qualifying candidate (every Tree-sitter runtime: FP-writable 2).
6. **Keep the compiler front ends and native tools as dev-time oracles**, never as runtime providers:
   - tokenize + ast (Python);
   - go/scanner;
   - the TypeScript parser;
   - the Kotlin PSI.
   
   Run them against the corpus and against target repositories (read-only snapshots) when a reader or a language version changes.
7. **Sidecar-only annotations stay a recorded option, not adopted.** If a target ever needs annotations in a language with no qualifying reader, decide this as a product question, with the costs in §4.8: the orphan check, the line field, a second writer.

## 8. Language policy

### 8.1 Oracle coverage

This is what checks the hand oracle independently. It is separate from support status.

| language | comment-range oracle | provenance | validity / execution |
|---|---|---|---|
| bash | shfmt (mvdan/sh) comment lines, plus bash execution of the controlled heredoc fixtures | shfmt has its own documented defects (FP heredoc continuation, silent heredoc-in-backticks), so the hand oracle plus execution decide | `bash -n`, bash 5.3 execution |
| Python | `tokenize` + `ast` | independent of the baseline | CPython 3.14 |
| Go | go/scanner | **partly self-consistency**: the baseline Go reader *is* go/scanner | `go/parser`, gofmt, `go run` |
| TS / TSX / JS | the parser-aware TypeScript extractor `ts-parser` (TypeScript 5.9.3; `--selftest` with a naive-scanner negative control; hand comment agreement 17/17) | `tsnative` wraps the same extractor, so its range agreement is **self-consistency, not validation** | the TS parser, node execution |
| Kotlin | none in `oraclecheck`. Independent evidence comes from the `ktpsi` provider (compiler PSI): corpus safety 0, and 0 comment-class and 0 record differences against the baseline on all 2,014 real Kotlin files (`R/results/t4/realrepo_totals.md`) | ktpsi is a provider under test, not a self-tested oracle | kotlinc 2.4.21 |
| Java, Rust, Swift | none | — | javac 21, rustc 1.98.1, swiftc 6.2.4 (validity and execution only) |

O: `R/results/t4/oracle_check.md`: 240 fixtures, 0 disagreements; no language is `native: none`.

### 8.2 Production support status

| status | languages | meaning | evidence |
|---|---|---|---|
| **supported** | bash, Python, Go, Kotlin | inline annotations read and written through the landed readers; a file the reader cannot prove is refused whole (`ErrUncertainContext`, or `ErrByteOrderMark` for a BOM with no slot) | §4.1; the oracle coverage above. Kotlin carries the open multi-dollar defect until t1990 |
| **unsupported** | every other language, including TS/JS/TSX, Java, Rust and Swift | no inline annotation is read or written; adoption reports the file explicitly (`ADOPT_SKIP …\|no-leader`, from `annot.ErrNoLeader`) | §7 item 5 |
| experimental | none in production | — | — |

For TS/JS/TSX, "unsupported" is **not** a claim that no oracle exists. The `ts-parser` oracle is available for a future onboarding. What is missing is a production reader that meets §9: tsnative needs Node.js, and gotreesitter has open gaps. Java, Rust and Swift additionally have no comment-range oracle.

### 8.3 Language-version clause

Each supported reader names the lexical syntax it models, and **fails closed** on syntax newer than that. Fail closed means the file is Uncertain and refused whole, never read with a guessed boundary.

| language | modelled | known unmodelled (must fail closed) |
|---|---|---|
| bash | bash 5.3, including `${ …; }` / `${| …; }` (t1954_4 fixture) | — measured |
| Python | the CPython 3.14 tokenizer, including PEP 701 f-strings and PEP 750 t-strings (t1954_4 fixture) | — measured |
| Go | whatever go/scanner of the build toolchain accepts | — (the toolchain moves with the engine) |
| Kotlin | Kotlin lexical syntax up to 2.1 | **2.2 multi-dollar interpolation strings**: today **not** failed closed (t1990) |

**The trigger.** A language release that adds a string, comment, template or heredoc form. When one appears:
- add fixtures to the conformance suite;
- run the dev-time oracle for that language (§7 item 6) over the corpus and over the target repositories' read-only snapshots.

### 8.4 Onboarding trigger

A new language is considered when a target repository needs inline annotations in it. A wish to support "more languages" is not a trigger. The candidate then has to pass §9.

## 9. Provider/adapter contract (bounded)

The research ran every candidate through one interface (`R/provider/provider.go`). That interface held unchanged for every family. This section is the subset any production reader must satisfy. It is a contract for **what a reader returns**. The rewriter, grammar and placement stay `annot`'s.

1. **Trustworthy comment locations.**
   - Byte offsets are offsets of the **original source**. Converting rune, UTF-16 and line/column positions is the adapter's job (`R/provider/offsets.go`), tested with 2-, 3- and 4-byte characters.
   - **Layer 1:** every token's text equals `src[start:end]`; tokens are in bounds, sorted and non-overlapping. A gap is attributed to a diagnostic, a skip rule or a BOM. An unexplained gap is an adapter failure (`R/provider/tokencheck.go`).
   - **Layer 2:** fragments are coalesced into construct-level spans, without ever absorbing a token the tool itself called a comment (`R/provider/coalesce.go`).
   - Every adapter defect the research found was caught by these checks, not by the safety columns (`R/findings_t1954_3.md` item 4).
2. **Uncertainty.**
   - Any diagnostic makes the **whole file** uncertain and unwritable. Local refusal is unsafe (§5).
   - A provider error means "unsupported", never "no comments".
   - A provider that cannot report errors cannot authorise writes: `Errors` is required for every write.
   - Syntax the reader does not model fails closed (§8.3).
3. **Capabilities declared, enforced per operation.**
   - `TokenRanges`, `FullCover`, `Errors`, `DocLiterals` and `Anchors` are declared honestly, and an undeclared anchor is *unknown*, never "none".
   - `ToContext` enforces them per operation (`R/provider/adapter.go`):
     - every write needs `Errors` (and `DocLiterals` for Python);
     - only a fresh file-level insertion needs the per-language anchors.
4. **Safe placement.** Placement stays `annot`'s (`PlanCovers` / `Placement`).
   - A new language needs a file-level rule computed from declared anchors. The corpus records *proposed* rules:
     - TS/JS: after the imports and any directive prologue;
     - Java: after the imports, else the package;
     - Rust: after inner attributes and the `use` block;
     - Swift: after the imports.
   - A rule stays *proposed* until its fixtures pass through the real `Apply`.
5. **Policy.** The reader encodes the M2.2 policy (§4.1 assumption) for the new language: which tokens are comments, data, or interpolation. That table is the per-language cost, and it is where every research adapter defect lived.
6. **Onboarding gate** (all required):
   - corpus fixtures for the language: every class — ordinary, difficult, malformed, embedded, unsupported constructs, non-ASCII, the edit set, and the language's newest string and comment forms;
   - 0 on every safety column through the real `Apply`;
   - a dev-time native oracle, self-tested with a negative control, agreeing with the hand oracle;
   - read-only real-repository walks on recorded-commit snapshots, with no record difference against the oracle;
   - the end-to-end scan measured against the 300 ms budget, with that language's realistic share;
   - binary-size delta and dependency-policy review;
   - a fixture-backed placement rule;
   - a named owner for grammar or lexer updates.
7. **Conformance fixtures.** These use the research format: `.in` / `.expect` / `.edits`, documented in `R/README.md` "Adding fixtures". They run hermetically inside goengines (t1991).

## 10. Migration sketch and complexity comparison

No schedules. "Shared-engine" is work done once; "per language" recurs for each language.

| route | new dependencies | binary Δ | budget fit | shared-engine work | per-language work | measured safety |
|---|---|---|---|---|---|---|
| **A. Status quo + gate + fix** (recommended) | none | 0 | ≈0.1× | conformance suite (F1); Kotlin fix (F2); shared-lexer evaluation (F3) | none (no new language) | bash, Python, Go 0; Kotlin 0 after F2 |
| B. Promote the seam to a production provider interface | none | ≈0 | unchanged for the four | an `annot` provider registry with capability declarations and whole-file refusal (the seam already shows the shape: two hooks) | — | unchanged |
| C. B plus one gotreesitter-backed language | gotreesitter (a policy change) | +15 MB with 10 grammars; the subset size per language is unknown | **unknown** for a TS-heavy repository; ≈0.95 ms per file lexical-only (397 ms for the 420 bench-shape files; `R/results/t4/bench.md`) | a mapping layer (`tsmap.go`: 447 lines in research) | a kind table, the policy encoding, a placement rule, fixtures and real-file evidence | 0 on TS/JS, Java, Rust (corpus); Swift fails |
| D. Sidecar-only for unsupported languages | none | small | within (no lexing) | a second `AnnotationSource`, an orphan check, `git mv`-aware repair, a stamp writer for sidecars, a conflict rule for files with both | none per language | no reader safety question; a stale-record risk without the orphan check |
| E. Subprocess providers (tsnative, ktpsi, pytokenize) | a runtime on every host | 0 in the binary, plus 20–400 MB on the host | Python only within; JVM start-up dominates | process management (`subproc.go`) | one helper per tool | 0 (safe), **rejected** for the shipped-artifact constraint |

Landing order, advisory: A first (F1, F2; F3 after F2). B only when a fifth language is actually triggered (§8.4). C on top of B for that language. D only as a product decision.

## 11. Impact on the rewriter and the flows

Every provider in this research ran through the **unchanged** `ParseFile → PlanCovers → Apply`. A reader change touches only the lexical layer (`Classify` / `LangOf`). The impact follows from that:

| concern | impact |
|---|---|
| centralized rewriter | `Apply` stays the only writer. Its before/after checks (comment-only edits, the class of every other line, ownership, snapshot) were the last line of defence in every experiment. They did **not** catch the multi-dollar case, because the reader's classes were wrong on both sides. That is why the reader itself must fail closed. |
| conflicts | unchanged: `*ConflictError` / `REWRITE_CONFLICT:<path>\|<line>`, exit 75 |
| root confinement / no-follow | unchanged: providers only read bytes that `annot` already read through `os.Root` |
| stamp / provenance | unchanged; the stamp format and the restamp hook (M2.6) do not depend on the reader |
| annotate / verify | unchanged; they act on what the reader proves, and an unsupported language is `ErrNoLeader` |
| stale confirmation (M4.2) | unchanged; it re-stamps through `annot`, and an unsupported-language test has no annotation to confirm |
| adoption (M6.3) | placement unchanged; unsupported-language files surface as `ADOPT_SKIP …\|no-leader`; uncertain files are never written |
| author annotation (M7.4) | `annotate --author` writes through `PlanCovers` + `Apply`; it must refuse explicitly on `ErrNoLeader`, `ErrUncertainContext` and `ErrByteOrderMark` |
| repair loop (t1853_7) | reuses the sole rewriter; unsupported-language, uncertain and BOM-without-slot files are terminal, classified failures, never repair targets; no second writer while sidecars are not adopted |

## 12. Consumer evaluation

| consumer | verdict | reason |
|---|---|---|
| t1853_2 M2.2 (archived) | context | its readers are retained as the production providers; the BOM defect is fixed (t1969); the Kotlin defect is filed (t1990) |
| t1853_3 M2.3 (archived) | context | the dependency scanners carry their own hand lexers (`deps/kotlinlex.go`, `deps/gradlelex.go`), which showed the same multi-dollar blind spot (t1980, t1975); the shared-lexer evaluation (t1992) covers them |
| t1855 M4 | context | `stale --confirm` re-stamps through the unchanged `annot`; no provider change |
| t1857 M6 | **action** | adoption and onboarding must surface unsupported-language test files explicitly (`ADOPT_SKIP …\|no-leader`), and the onboarding docs must state the four-language policy; placement is unchanged |
| t1858 M7 | **action** (one check) | `annotate --author` must refuse explicitly on an unsupported-language, uncertain or BOM-without-slot file |
| t1853_7 repair loop | **action** | the rule-to-repair matrix classes unsupported-language, uncertain and BOM-without-slot files as terminal failures; no second writer |
| t1860 M9 | **action** | document the language policy and the annotation-line rules (a standalone line comment; never in heredocs, strings, backtick substitutions, continuation lines or interpolation fields; docstrings are read-only) |
| t1861 M10 | context | every target is in the supported four; re-run the read-only real-repository walk for each target at rollout time, at the then-current `annot`, and check Kotlin targets for `$$"` until t1990 lands |
| t1863 cross-linking | **action** | the research-result handoff is resolved: link this report, the evidence artifact and t1991/t1990/t1992 |

Nothing here is a hard prerequisite of current four-language work.

## 13. Follow-ups and notes

Follow-up tasks, all with anchor 1852 and no hard dependencies. Their order is advisory and recorded in the trail.

| task | type | what | why |
|---|---|---|---|
| **t1990** `annot_kotlin_multidollar_strings_fail_closed` | bug (upstream defect) | the Kotlin reader models the multi-dollar prefix exactly, or classes the file Uncertain | §4.1: FP-writable plus record corruption on valid Kotlin 2.2 |
| **t1991** `annot_conformance_suite_from_t1954_corpus` | test | the bash, Python, Go and Kotlin corpus as a hermetic `go test` gate in `annot`, with safety at 0, read records, fidelity, and known costs pinned | §7 item 2: the readers are retained, so their regressions must fail tests |
| **t1992** `kotlin_family_shared_lexical_core_evaluation` | chore | decide whether `annot` and `deps` share one Kotlin-family lexical core | §7 item 4: one construct broke three independent hand lexers |

**Advisory order:** t1990 and t1991 in either order; t1992 after t1990. None blocks M2–M10 work.

**Not created: the parent plan's `native_oracle_gap_followup`.** Its trigger was a language whose fixtures are still `native: none`. No language is (`R/results/t4/oracle_check.md`). The policy in §8 claims nothing beyond the named evidence, and Java, Rust and Swift, which have no comment-range oracle, stay unsupported.

**Advisory notes** go with `./ait note --from 1954_4` to the existing consumers in §12: t1855, t1857, t1858, t1853_7, t1860, t1861 and t1863. Each carries that consumer's verdict and a link to this report. A note is context for its task; it never replaces a follow-up task.

## 14. Residual risks

- **Hand readers carry language-version risk.** A language release can add syntax that a reader mis-tokenises. The multi-dollar case shows it is real. It is mitigated by the §8.3 clause, the conformance gate and the dev-time oracles, not eliminated.
- **Kotlin stays exposed until t1990 lands.** Exposure today is nil (no `$$"` in the six repositories). A target that adopts Kotlin 2.2 multi-dollar strings before the fix can get a write into a string literal.
- **Bash has no fully independent comment oracle.** shfmt is itself unsafe on heredocs. Bash evidence rests on the hand oracle plus execution of the controlled fixtures.
- **Thin real-world evidence for the unsupported languages.** TS/JS, Java, Rust and Swift files are near-absent from the six repositories, so any candidate evidence there rests on the corpus.
- **Moment-relative maintenance data.** Every activity number in §6 is a reading at one date.
- **Host noise in timings.** The bench host ran concurrent agent sessions; the ratios are robust and the absolute times are not (The 1-minute load was 3.65 before the bench and 4.43 after. The same-run baseline control read 24.7 ms, within 4% of t1954_1/2's 23.8 ms).

## 15. Unknowns

- Darwin and arm64 latency and memory: every measurement ran on linux/amd64.
- The per-language subset footprint and budget share of gotreesitter for a single new language.
- Whether newer grammar or highlighter releases fix the measured failures. Only the pinned versions were measured.
- LSP servers beyond the four that were run.
- How each candidate behaves on future language versions. §8.3 makes the readers fail closed instead of predicting this.

## 16. Evidence index

| what | path or handle |
|---|---|
| this report | `aidocs/testing_engine/t1954_annotation_parser_research.md` |
| harness, corpus, README (rerun commands) | `aidocs/testing_engine/t1954_parser_research/` |
| final run (pin `3d1a2b628`, 240 fixtures) | `R/results/t4/`: `README.md`, `inputs.md`, `guard.md`, `matrix.md` + `matrix_<subject>.md`, `oracle_check.md`, `pin_compare.md`, `ts_local_error_policy.md`, `realrepo_<repo>.md`, `realrepo_totals.md`, `ts_differential.md`, `bench.md`, `footprint.md`, `footprint_ts.md`, `footprint_t3.md`, `lsp.md`, `sidecar.md`, `environment.md` |
| child-era results (pin `f096db065`, 229 fixtures; live-tree walks) | `R/results/` (top level), `R/results/ts/`, `R/results/t3/` |
| child findings | `R/findings_t1954_1.md`, `R/findings_t1954_2.md`, `R/findings_t1954_3.md` |
| raw logs, the old-pin final-corpus matrices, the reproduction outputs | artifact `art:t1954-researchevidence` |
| plans | the parent plan `p1954_research_multilanguage_annotation_parsers.md` and the child plans `p1954_<n>_*.md`, archived with t1954 under `aiplans/archived/` and `aiplans/archived/p1954/` |
| trail | `art:trail-testmap-feature` |
