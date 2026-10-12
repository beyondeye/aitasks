---
Task: t1954_research_multilanguage_annotation_parsers.md
Base branch: main
Output branch: main
---

# Plan: t1954 — Research multi-language annotation parsers (decomposed)

## Context

`ait test` / testmap reads and writes `testmap:` annotations only on lines a
lexer proves are real comments (M2.2 D9, Invariant 6). t1853_2 (M2.2) **landed**
in `f096db065`, with its contract recorded in the proposal at `7229dee86`. It
ships Go via `go/scanner` and handwritten readers for bash, Python and Kotlin
(`goengines/internal/testmap/annot/lexctx.go`). The user
accepts that for now but will not accept a growing set of custom readers as the
unexamined long-term strategy. This task compares every credible approach with
reproducible experiments and ends in a recommendation, a language policy, a
provider contract, and a migration sequence placed in `art:trail-testmap-feature`.
It never blocks t1853_2.

Hard constraints found during exploration (they decide most eliminations):
- Engine builds with `CGO_ENABLED=0 -trimpath` for linux/darwin × amd64/arm64
  (`goengines/build.sh`), offline, prebuilt binaries only.
- Dependency allowlist: `yaml.v3`, `doublestar/v4`, `x/sync` only
  (`goengines/README.md`, `guards_test.go`); any new dep is a policy change.
- Budget: `scan` / `check` / `stale --task` < 300 ms (proposal *Engine binary
  identity and budget*); M2.2 bench shape ≈420 annotated tests, ≈600 sources,
  ≈1,000 other files (`aiplans/p1853/p1853_2_…md` step 9).
- Target repos (surveyed): aitasks (sh 647, py 631, go 45), aitasks_go (go/py/sh),
  aitasks_mobile (kt 252, 2 swift), thinking_app (kt 777), thinking_backend
  (py/sh), timexchange (kt 957, java 15). Only bash/Python/Go/Kotlin are in real
  use today; Java/Swift appear at the margin.
- Local tools: go 1.27.0, gcc/clang, python 3.14 + Pygments 2.19.2, node 25,
  rustc, java/javac 21, tree-sitter CLI 0.26.9, docker. Missing: kotlinc,
  swiftc, LSP servers (obtainable into the scratch dir, never system-wide).

Baseline as landed (`annot`, from the archived plan
`aiplans/archived/p1853/p1853_2_m2_2_annotation_grammar_rewriter.md`, *Final
Implementation Notes*):
- API: `Classify(Lang, []byte) Context` (`Class []LineClass` Code/Comment/Literal,
  `Docs []DocSpan` for the Python docstring, `Uncertain *Unclosed`),
  `LangOf`, `ParseFile`, `(*File).Placement` / `PlanCovers`, `RestampLine`, and
  `Apply(root, EditSet)`. `Apply` is the only writer. It checks comment-only edits
  before and after, the class of every other line, ownership and the snapshot,
  and writes atomically with the original mode, CRLF and final newline kept.
- Fixtures to reuse (copied, never imported): `annot/testdata/parse/*.in`
  (look-alikes per language, docstring, CRLF, members) and
  `annot/testdata/placement/*.in` (with goldens), plus the cases in
  `annot/lexctx_test.go`.
- Recorded evidence:
  - `annot.BenchmarkScan` ≈21 ms against `budget=300ms`; `Source` over the whole
    aitasks repo ≈130 ms.
  - Python vs `tokenize` / `ast` (631 files) and bash vs shfmt v3 (647 files):
    0 mismatches. 3 files shfmt cannot parse.
  - One real bash lexer defect (`$(( cd … ) | …)`) and one panic were found by
    the repository probe and fixed. No Kotlin sources in aitasks.
  - So mvdan/sh and Python tokenize/ast have already served as oracles; this
    research turns them (and the rest) into candidate **providers**.

User decisions (this planning session): split into children; the harness is a
separate Go module under `aidocs/` (never built/shipped by goengines); sibling
repos may be scanned **read-only** (counts and paths only, nothing executed);
additional languages = TypeScript/JavaScript, Java, Rust, Swift.

## Decomposition

Four sequential children (default sibling chain; 2 and 3 both extend the shared
harness, so they are not parallel). Child 4 is the bounded synthesis /
retrospective that owns every deliverable the task names after the experiments.

| child | name | scope |
|---|---|---|
| t1954_1 | corpus_harness_baseline | research dir, corpus + oracle, harness + provider interface, baseline (custom readers) and native oracles, real-repo + perf + footprint commands |
| t1954_2 | treesitter_family | gotreesitter (pure Go), official go-tree-sitter (cgo, as reference + cost), WASM/wazero; grammar pinning, external scanners, ERROR/MISSING, licensing |
| t1954_3 | tokenizers_parsers_lsp_alternatives | Chroma, Pygments, mvdan/sh, Python tokenize, Kotlin tooling, ANTLR4 Go + grammars-v4, LSP/compiler providers, TextMate-class and other discovered approaches, sidecar/registry-only product alternative |
| t1954_4 | report_recommendation_trail | final rerun, report, provider contract + migration sketch, language policy, trail refresh (deep), consumer evaluation, follow-ups, notes |

The parent is reverted to Ready with children; each child is picked in a fresh
context.

## Shared design (every child follows it)

### Location and layout

`aidocs/testing_engine/t1954_parser_research/`:
- `README.md` — environment, pinned versions, exact rerun commands.
- `go.mod` / `go.sum` — module `github.com/beyondeye/aitasks/goengines/t1954research`
  (Go's internal rule is import-path based, so this path may import
  `internal/testmap/annot`) with
  `replace github.com/beyondeye/aitasks/goengines => ./.baseline/goengines`.
  It **never** points at the live checkout (see *Immutable baseline*).
- `baseline/PIN` — committed: the baseline commit, `git rev-parse <commit>:goengines`
  tree id, and the sha256 of `baseline/seam.patch`.
  `baseline/fetch.sh` — `git archive <commit> goengines` into `.baseline/`,
  applies `seam.patch`, writes `.baseline/IDENTITY`. `baseline/seam.patch` — see
  *Evaluation seam*. `.baseline/` is ignored by a research-dir `.gitignore`.
- `provider/` — the experimental interface, the shared adapter, one file per
  provider.
- `cmd/t1954/` — subcommands `matrix`, `edit`, `realrepo`, `bench`, `footprint`.
  Every run first checks that `.baseline/IDENTITY` matches `baseline/PIN`; on a
  mismatch it refuses to run (exit non-zero) and never falls back to the
  checkout. It prints the identity at the top of every result file.
- `oracle/` — native-tool helpers (Python `tokenize`/`ast`, Pygments, the
  parser-aware TypeScript comment extractor) invoked as subprocesses. A
  native tool overrides a hand `.expect` only after passing a self-test on
  that language's hardest fixtures with a negative control; a context-free
  scan loop (e.g. bare `ts.createScanner`) is never an oracle.
- `corpus/<lang>/<case>.<ext>.in` + `<case>.<ext>.expect` (+ optional
  `<case>.<ext>.edits`) — the `.in` suffix keeps fixtures out of every
  language table (M2.2's convention), so a future `ait-testmap scan` over
  aitasks never reads them.
- `results/` — committed summaries (markdown/CSV matrices, environment record);
  bulky raw logs go into one evidence artifact (`ait artifact create 1954 …
  --kind research_evidence`) in child 4, linked by handle.
- `findings_t1954_<N>.md` — each child's observations / documentation claims /
  assumptions / unknowns, kept separate, dated, with versions/commits.

### Immutable baseline

The baseline is source extracted from a **commit**, never the working tree:
`baseline/fetch.sh` reads `PIN`, runs `git archive <commit> goengines`, verifies
the tree id, applies the seam patch and verifies its sha256. Rerun =
`baseline/fetch.sh && go run ./cmd/t1954 <verb>`. Child 1 pins `f096db065` (or
the then-current annot commit). Moving the pin is a deliberate committed edit to
`PIN`, and child 4's re-run at a newer commit reports both pins side by side
(post-phase `baseline_rerun_at_landed_commit`). Uncommitted edits by concurrent
sessions therefore cannot reach any measurement.

### Evaluation seam (how providers are scored through the real M2.2 code)

The plausible production shape is "a provider replaces the lexical layer; the
landed grammar and rewriter stay". So the experiment tests exactly that seam,
using the real code and re-implementing neither.

- `baseline/seam.patch` (applied to the snapshot only, never to the repo) adds
  two exported hooks to `annot`, both nil by default:
  - `var ClassifyHook func(Lang, []byte) Context` — `Classify` delegates to it
    when it is set;
  - `var LangHook func(path string, data []byte) (Lang, bool)` — `LangOf`
    consults it first.

  Language enters `annot` only through `LangOf` (`grammar.go`) and `Classify`.
  So with both hooks set, `ParseFile`, `PlanCovers`/`Placement`, `RestampLine`
  and `Apply` — including Apply's before/after context, ownership and snapshot
  checks — run **unchanged** on a provider's `Context`, in **all 8 languages**.
  The harness registers research-only `Lang` values (`typescript`,
  `javascript`, `java`, `rust`, `swift`, each with leader `//` and no
  docstring) through `LangHook` for scratch files only.
- Guard: the baseline matrix is produced twice, from an unpatched and a
  patched-but-unhooked snapshot, and must be identical. This proves the patch
  is behaviour-neutral.
- A provider reaches the seam through the **shared adapter**
  `provider.ToContext(lang, src, caps, Result, need) (annot.Context, error)`
  (capability enforcement: see *Experimental interface*). It builds
  `Class` from line-comment / non-code spans, `Docs`/`DocEnd` from
  `Result.Doc` (see the interface), `Package`/`Import` from `Anchors`, and
  `Uncertain` from any `Diag`. A provider that cannot supply a field the
  grammar needs is reported **unsupported for that capability**, never filled
  with a guess and never reconstructed by the adapter.
- **File-level placement for the extra 4 languages** is the one piece with no
  landed rule: unmodified `Placement` falls to the bash-like "after the leading
  comment block" default (`fixedPosition`, `rewrite.go`). The research proposes
  one rule per language — TS/JS after the import block and any directive
  prologue; Java after the imports; Rust after inner attributes / `//!` and the
  `use` block; Swift after the imports — computed from provider anchors.
  For the "file-level, no annotation yet" case the edit runner builds that
  `InsertAfter` edit itself, and still applies it through the real `Apply`.
  Every other case (member blocks, existing annotations, restamps) uses
  `PlanCovers` unchanged. Both the default and the proposed position are
  recorded, and proposed rules are labelled *proposed*, not validated
  production behaviour.
- So the record, edit, refusal and behaviour suites run in **all 8 languages**
  (insertion, restamp, several members covering the same source, the
  placement guard, uncertain-file refusal, stale-plan conflict). Claims stay
  bounded by what was measured: a scratch-file result through the seam is
  evidence about the candidate, not a production integration. Where a
  provider, language or construct cannot take part, the outcome is recorded
  as `unsupported` or `refused:<reason>`, never omitted.

### Experimental interface (`provider/provider.go`)

```go
type SpanKind uint8 // LineComment | BlockComment | String | Heredoc | DocLiteral | Other
type Span struct{ Start, End int; Kind SpanKind }  // byte range, as the provider reports it
type Diag struct{ Start, End int; Reason string }   // ERROR/MISSING node, error token, unterminated construct, unsupported form
type Anchors struct{ Shebang, HeaderEnd, Package, ImportEnd, Prologue, InnerAttrEnd int } // lines; 0 = none ONLY for an anchor declared in Capabilities.Anchors
type AnchorSet uint8 // one bit per Anchors field
const ( AShebang AnchorSet = 1 << iota; AHeaderEnd; APackage; AImportEnd; APrologue; AInnerAttrEnd )
// Python module docstring, normalised by the provider (never reconstructed by the adapter):
type DocLiteral struct{ ContentStart, ContentEnd int; Raw bool } // byte offsets of the literal's CONTENT (after prefix + opening quotes, before closing quotes)
type DocInfo struct {
    Literals []DocLiteral // every literal of the first statement, in order (concatenated / parenthesised forms)
    StmtEnd  int          // byte offset just past the COMPLETE statement (closing parens included) — DocEnd derives from it, not from the last literal
}
type Capabilities struct {
    TokenRanges bool // exposes exact token/node byte ranges
    FullCover   bool // tokens/leaves partition the whole input (reconstruction is checkable)
    Errors      bool // reports malformed input as diagnostics
    DocLiterals bool // fills Result.Doc (content bounds, raw flags, statement end)
    Anchors     AnchorSet // anchors the provider DETERMINES; undeclared = unknown, never "none"
}
type Result struct {
    Spans   []Span
    Leaves  []Span      // only when Capabilities.FullCover: every token/leaf, in order
    Diags   []Diag      // non-empty ⇒ uncertain; never silently empty on failure
    Anchors Anchors
    Doc     *DocInfo    // Python only; nil = no docstring (meaningful only when Caps.DocLiterals)
}
type Provider interface {
    Name() string
    Langs() []string
    Caps(lang string) Capabilities
    Analyze(lang string, src []byte) (Result, error) // error = provider failure → "unsupported", never "no comments"
}
type Need uint8 // NeedLexical | NeedWrite | NeedFreshFileInsert (bit set)
func ToContext(lang string, src []byte, caps Capabilities, res Result, need Need) (annot.Context, error)
```

**Capability enforcement (amended by t1954_1 plan review, 2026-10-12).**
`ToContext` itself enforces what each operation needs, following the real
rewriter code path. A missing requirement is an
`*UnsupportedCapabilityError{Missing}` (wrapping `ErrUnsupportedCapability`).
The runner records it as `unsupported:<cap>` for that operation only.
- **NeedLexical:** `Spans`. Python docstring *read* records also need
  `DocLiterals`.
- **NeedWrite** — every edit (restamp, member insertion, file-level append,
  fresh file-level insertion): `Errors`, because an empty `Diags` from a
  provider that cannot report errors proves no certainty. Python also needs
  `DocLiterals` (docstring records, the `ErrDocstring` refusal, `Apply`'s
  doc-shape check). No anchors.
- **NeedFreshFileInsert** — only the file-level block with no annotation yet
  (`member == ""`, `u.Last == 0`), the one path that reaches `fixedPosition`
  or a proposed extra-language rule. It needs these anchors in
  `Capabilities.Anchors`:

  | language | required anchors |
  |---|---|
  | bash | none |
  | Go | Package |
  | Kotlin | Package, ImportEnd |
  | TS/JS | ImportEnd, Prologue |
  | Java | Package, ImportEnd |
  | Rust | InnerAttrEnd, ImportEnd |
  | Swift | ImportEnd |

  A declared anchor with value 0 is confirmed-empty and accepted.

The edit runner classifies each op from the parsed file before planning it,
and requests `NeedFreshFileInsert` only for that kind. A restamp, a member
insertion or a file-level append by a provider without anchors is therefore
still measured.

**The baseline is not forced into this interface.** Its evidence is what
`annot.Context` actually exposes: line classes, `Docs` column spans,
`DocEnd`/`Package`/`Import`, `Uncertain`. It is compared at those levels and at
the record/edit levels. Every token-range and reconstruction check is reported
**"n/a — not exposed"** for it; no spans are synthesised from its line classes.

### Oracle files (hand-written, cross-checked by native tools)

`.expect` — what is read and what may be written, kept separate:

```
lang: python
expect: certain | uncertain           # malformed/unsupported fixtures: uncertain
read:                                 # every annotation record ParseFile must return, in order
  - line=3 member= key=covers value=src/a.sh stamp=@2026-01-01/0123456789 origin=comment
  - line=1 member= key=covers value=src/d.sh stamp= origin=docstring   # decoded value
writable: 3,7,12                      # lines eligible for Replace (real comment annotation lines)
readonly: 1                           # read but never writable (docstring): any write → refusal
lookalikes: 20-25,31                  # testmap-shaped data: never read, never writable
refuse: syntax@5                      # expected ParseFile refusal (SyntaxError line), if any
placement: file=4 member:A=15         # insertion anchor (after line) per block
native: python-tokenize+ast | go-scanner | shfmt | bash-exec | node-ts | rustc | javac | none
exec: <controlled run command, optional>
```

`TestDocstringValue`'s cases (escapes, concatenated literals, split tokens,
call-vs-grouping, `\N{…}` refusals, U+FFFD, NBSP, multi-byte runes) are copied in
as fixtures with their expected decoded values or refusals, and each carries an
explicit expected **write refusal** (`ErrDocstring` / not-comment).

`.edits` — an ordered list of operations with expected outcomes and the full
expected record list after each:

```
op: annotate member=A source=src/x.sh stamp=@2026-02-02/aaaaaaaaaa
outcome: applied | refused:<docstring|not-comment|uncertain|no-member-block|conflict>
after:                                 # the complete ParseFile record list
  - line=9  member=A key=covers value=src/x.sh stamp=@2026-02-02/aaaaaaaaaa origin=comment
  - line=14 member=B key=covers value=src/x.sh stamp=@2026-01-01/bbbbbbbbbb origin=comment   # unrelated, unchanged
```

Required edit cases (each of the 8 languages; docstring cases Python only): an
insertion into a member block; a file-level insertion (at the landed placement
for the 4 M2.2 languages, at the proposed rule plus the recorded default for
the other 4); a restamp; **several members covering the same
source**, where restamping one must leave the others byte- and record-identical;
an insertion that would land after a `unit` opener (the placement guard); a
docstring covers line, where the restamp must be refused; a write into an
uncertain file, which must be refused; and a stale plan (snapshot / ownership
conflict). The edit runner drives the real
`ParseFile → PlanCovers → Apply` on scratch copies through the seam. For the
extra-language file-level case only, it builds the `InsertAfter` edit itself
and still applies it through `Apply`. It compares
the **whole record list** after each op (member ownership, source, stamp, line,
origin), not just the edited line.

### Metrics (per provider × language × case)

Safety (must be 0):
- **FP-writable** — a look-alike or read-only line made writable (classed
  Comment / accepted by `Apply`).
- **Docstring-write** — a write into a docstring line that was not refused.
- **Silent-uncertain** — an `expect: uncertain` file reported certain.
- **Record-corruption** — after an applied edit, any record other than the
  intended one differs, or the intended one has the wrong member, source or
  stamp.

Recall / cost:
- **Missed-writable** — a `writable` line not eligible.
- **Read-mismatch** — the `read` record list differs: missing, extra, wrong
  decoded value, wrong origin.
- **Over-refusal** — a valid file reported uncertain, or a legal edit refused.
- **Placement** — anchors and the actual inserted line vs `.expect`.

File fidelity (on every applied edit): untouched lines keep bytes and class;
CRLF, final-newline state, encoding (UTF-8 BOM / Latin-1 fixtures) and file
mode are preserved.

Range evidence (only where `Capabilities` declare it; otherwise "n/a — not
exposed"):
- spans in bounds, sorted, non-overlapping;
- a line-comment span starts with the leader and ends at end of line;
- span bytes equal the native oracle's token bytes (Python `tokenize` offsets,
  `go/scanner`, the parser-aware TS extractor, mvdan/sh positions);
- with `FullCover`, the concatenated leaves reproduce the input bytes exactly.

Behaviour (controlled fixtures only): run before and after each applied edit in
a scratch dir and diff the output (bash, python, go run, node, rustc,
`java File.java`). Repository and sibling-repo files are never executed.

**Unsupported** — a provider that cannot handle a language, construct or
capability is reported as such, never as an empty result.

Pass/fail/unsupported/n-a matrices go to `results/matrix_<provider>.md` plus one
combined `results/matrix.md`, with the safety columns first.

### Corpus coverage (child 1 builds; later children only add cases)

Bash, Python, Go, Kotlin + TS/JS, Java, Rust, Swift. For each: ordinary valid,
difficult valid, malformed (unterminated string/comment/heredoc), embedded
language, unsupported construct. Mandatory cases from the task: bash heredoc
bodies delayed by backslash continuation and by a quote spanning lines,
delimiter-shaped arguments, nested `$(…)`, `<<-`, quoted delimiters, heredoc in
backticks/`$((…))`; Python docstring shapes whose statement end differs from
the last literal's end, each with an expected `DocEnd` and an expected placement:
a parenthesised docstring closing on a later line, `("a" "b")` grouping,
implicit concatenation across lines, a raw literal, and the
call-vs-grouping, f-string and bytes forms that are not docstrings at all;
Python non-docstring triple strings, 3.12 nested f-strings,
module docstring with `testmap:` lines; Kotlin raw strings with `${}` templates,
nested `/* */`, char literals; Go raw strings; TS template literals with nested
`${}`, regex literals containing `//`, JSX text; Java text blocks; Rust
`r#"…"#`, nested block comments, `///` doc comments; Swift `#"…"#` raw and
`"""` multiline strings, nested comments. M2.2's adversarial cases
(`annot/lexctx_test.go`, `annot/testdata/parse/*.in`,
`annot/testdata/placement/*.in` with their goldens) are copied in as standalone
fixtures, each `.expect` derived from the landed goldens, so they survive any
later change to those files.

### Measurement rules

- Record date, host CPU model, `nproc`, Go/tool versions, module versions and
  upstream commits in `results/environment.md`.
- Bench pinned `taskset -c 0`, fastest of 3 fresh processes. Cold = one timed
  first operation per fresh process, timer started before provider
  construction/initialization (no benchmark calibration); warm = a separate
  process, untimed warm-up, then `testing.Benchmark`. Peak RSS from the
  child's rusage (`/usr/bin/time` is not installed on the research host).
  Only the operation `annot.BenchmarkScan` times — end-to-end `registry.Scan`
  with the annotation source over the M2.2 bench shape, provider via
  `ClassifyHook` — is compared against the 300 ms budget. Lexical-only
  timings ((b) every bash/Python/Go test file of aitasks, (c) read-only
  sibling-repo sets, and the M2.2 shape's files) are labelled "not
  budget-comparable". No invented numbers — a number not measured is
  written "not measured".
- Footprint: a probe binary per provider built `CGO_ENABLED=0 -trimpath` for
  the 4 release targets (failure recorded as evidence), size delta vs a no-op
  probe and vs the current `ait-testmap`.
- Maintenance: `gh api` (read-only) for last release, commit cadence,
  contributors, open issues; licenses read from module/grammar LICENSE files.

## Child scopes (child plans are written in full after approval)

Every provider prototyped in children 2 and 3 runs the full matrix, in all 8
languages: lexical, range, record, edit, refusal and behaviour levels, all
through the seam. Docstring levels apply to Python only. A provider that cannot
supply the `Context` fields a level needs is reported `unsupported` for that
level.

### Pre-phase (risk mitigations)

Carried by t1954_1, before its step 1 (copied into its plan file):

1. [feasibility_smoke] In the scratch dir, `go get` and compile a minimal probe
   for each candidate module: gotreesitter, the wazero-based tree-sitter
   wrapper, Chroma, mvdan.cc/sh/v3, and the ANTLR4 Go runtime under
   `CGO_ENABLED=0` for the 4 release targets, plus official go-tree-sitter with
   cgo on the host. Record pass/fail, versions and errors in
   `results/feasibility.md`. If a candidate fails, add a note to the affected
   child (t1954_2 / t1954_3) re-scoping it before that child is picked.
2. [scoped_commits_packaging_check] Confirm that nothing ships or tests the
   research dir: the release tarball / `install.sh` file selection,
   `goengines-check.yml` path filters, `tests/run_all_python_tests.sh` discovery
   and shellcheck globs. Record the evidence in the README. Every commit in
   every child names its paths explicitly (no `git add -A`, no bare
   `git commit`), and nothing under `goengines/` is modified.

### t1954_1 — corpus, oracle, harness, baseline
1. Create the research dir, module, README and `.gitignore`. Add
   `baseline/PIN`, `baseline/fetch.sh` and `baseline/seam.patch`; pin
   `f096db065` (or the then-current annot commit). The patch adds
   `ClassifyHook` and `LangHook`; nothing else. Verify that the
   internal-import path builds against `.baseline/goengines` and that a
   missing or mismatched `.baseline/IDENTITY` refuses to run.
2. Write the corpus with `.expect` and `.edits` files for all 8 languages and
   every mandatory case, including the `TestDocstringValue` and
   `annot/testdata` cases with their decoded values, refusals and placement
   goldens. Cross-check the expectations against native oracles where they
   exist: Python `tokenize` + `ast`, `go/scanner`, shfmt, bash execution of
   the controlled heredoc fixtures, TypeScript's parser (installed into
   the scratch dir via npm; parser-aware comment extraction, self-tested), and `rustc`/`javac` validity. For Kotlin and
   Swift, try a pinned compiler download into the scratch dir; if that fails,
   mark their native evidence `none`.
3. Harness: the interface, the shared adapter `ToContext`, the record/edit
   runner through the seam, and the `matrix`, `edit`, `realrepo`, `bench` and
   `footprint` commands. Include the guard that unpatched and
   patched-but-unhooked snapshots produce identical baseline matrices.
4. Providers:
   - `baseline`: the real `annot`, at the class, docstring, anchor, record and
     edit levels; range checks are `n/a — not exposed`; the extra 4
     languages are `unsupported`.
   - Native oracle providers that expose ranges and run through the seam:
     `go/scanner` (in-process), Python `tokenize`+`ast` (subprocess), and
     shfmt/mvdan for bash, as t1853_2's probe did. The Python oracle fills
     `DocInfo` from `ast` end positions plus `tokenize` STRING tokens, giving
     content bounds, raw flags and the complete statement end.
5. Results: the baseline and oracle matrices; real-repo disagreement (read-only
   sibling repos included); performance on the M2.2 shape and on the aitasks
   tests; `findings_t1954_1.md`.

### t1954_2 — Tree-sitter family
1. gotreesitter (pure Go, MIT): pin a release; curated build tags for the 8
   grammars; inventory which grammars use hand-ported Go external scanners
   (bash heredocs, Python strings, Kotlin, Rust raw strings, TS templates,
   Swift) and their parity tests; prototype provider; ERROR/MISSING mapping to
   `Diags`; anchors via nodes (package clause, imports, directive prologue, inner
   attributes); Python `DocInfo` from the module node (literal content bounds
   excluding prefix and quotes, raw flags, the complete statement end
   including closing parens); run the full record/edit suite through the seam
   in all 8 languages.
2. Official `github.com/tree-sitter/go-tree-sitter` (cgo): prototype as the
   reference parser (host-only, a separate build tag, so the default harness
   build stays CGO-free) (same grammars, C runtime + C scanners) — differential
   against gotreesitter; record the CGO cost (build fails under
   `CGO_ENABLED=0`; cross-toolchain requirements for darwin targets).
3. WASM: tree-sitter runtime + grammars compiled to wasm (`tree-sitter build
   --wasm` via docker/emscripten in the scratch dir) run by wazero (pure Go),
   or an existing wrapper (e.g. malivvan/tree-sitter); prototype if it builds,
   else eliminate with the recorded failure. Footprint, startup, scan latency.
4. Grammar maintenance: per grammar upstream repo, ABI version, last release,
   license, external-scanner presence; abandoned-grammar risk; pinning model
   (curated pinned set vs bundle).
5. Results + `findings_t1954_2.md`.

### t1954_3 — tokenizers, language parsers, external providers, alternatives
1. Chroma (pure Go): provider; test whether error tokens / unterminated
   constructs are reported and whether byte positions round-trip.
2. Pygments (subprocess): same, incl. its newline/tab normalisation options
   (`stripnl`, `ensurenl`), `Error` tokens, and whether `String.Doc` can
   supply `DocInfo` (statement end included), otherwise report `DocLiterals`
   unsupported; runtime-dependency cost.
3. Language-specific: mvdan.cc/sh/v3/syntax (bash, pure Go — comments,
   heredocs, positions, parse errors); Python `tokenize`/`ast` via subprocess
   and a search for maintained pure-Go Python tokenizers; Kotlin (kotlin
   compiler PSI, ktlint/detekt, kotlinx tooling — JVM runtime burden);
   `go/scanner` already baseline. Shared adapter interface cost.
4. ANTLR4 Go runtime + grammars-v4 lexers (comments on hidden channels):
   prototype at least the Kotlin and one more lexer; grammar maintenance.
5. LSP/compiler providers: does semanticTokens/foldingRange expose comments
   (gopls, pyright, typescript-language-server, kotlin-language-server) — one
   experiment per server obtainable into the scratch dir, else documented.
6. Others with evidence-backed exclusions: TextMate grammars (vscode-textmate /
   shiki), ctags, linguist, tokei/scc, semgrep, srcML, difftastic,
   tree-sitter-language-pack, highlight.js/Prism.
7. Product alternative: registry/sidecar-only annotations for unsupported
   languages — compatibility with M2.1 `AnnotationSource`, stamp/provenance,
   stale confirmation, adoption, author annotations, repair loop.
8. Results + `findings_t1954_3.md`.

### t1954_4 — report, recommendation, trail, follow-ups
1. Re-run every provider on the final corpus in one environment (baseline at
   the then-current annot commit).
2. Write `aidocs/testing_engine/t1954_annotation_parser_research.md`:
   observations vs documentation claims vs assumptions vs unknowns; candidate
   matrix; rejected alternatives; dependency/licensing/maintenance analysis;
   recommendation or explicit no-candidate-yet; supported/unsupported language
   policy; bounded provider/adapter contract (comment locations, uncertainty,
   safe placement, onboarding policy, conformance fixtures) and migration
   sketch with complexity comparison (no schedules); impact on the rewriter,
   conflicts, root confinement, stamp/provenance, annotate, verify, stale,
   adoption, author annotation, repair loop.
3. Evidence artifact (`ait artifact create 1954 … --kind research_evidence`).
4. Refresh `art:trail-testmap-feature` at deep depth (following the
   aitask-trail refresh procedure): report path, evidence handles, decision,
   residual risks, affected modules, landing order.
5. Consumer evaluation (actual child IDs then): t1853_2, t1853_3, t1855,
   t1857, t1858, t1853_7, t1860, t1861, t1863 — action vs context.
6. Create bounded follow-ups (anchor 1852, placed in the trail; advisory order,
   hard depends only for real prerequisites) and send advisory `ait note`s to
   affected existing tasks.
7. Verify every path and artifact handle the report and trail cite exists
   (`aidocs/` is not part of the website, so `check_links.py` does not apply).

### Post-phase (risk mitigations)

Carried by t1954_4 (copied into its plan file):

1. [baseline_rerun_at_landed_commit] Re-run the baseline column at the
   then-current `annot` commit (`git log -1 -- goengines/internal/testmap/annot`).
   If annot changed since child 1's recorded commit (e.g. by M2.3–M2.6), run
   both commits, report both columns and name every differing case.
2. [native_oracle_gap_followup] For any language whose fixtures still have
   `native: none` evidence (expected: Kotlin and/or Swift), the language policy
   makes no "supported" claim beyond what the hand oracle shows. Create one
   bounded follow-up (anchor 1852) to validate those fixtures on a host with
   the compiler.

## Implementation steps (this session, after approval)

1. Create the four children with the Batch Task Creation Procedure (mode child,
   parent 1954, issue_type chore, labels `testing,testmap,go_engine`, each with
   full context per the Child Task Documentation Requirements, referencing this
   plan's shared design).
2. Revert the parent to Ready (`--status Ready --assigned-to "" --plan-approved-at ""`)
   and release its lock.
3. Write `aiplans/p1954/p1954_<N>_<name>.md` for each child (detailed steps
   from the scopes above plus the shared design), commit them with
   `aitask_task_commit.sh` naming every file.
4. Child checkpoint (Start first child / Stop here).

Manual-verification sibling: not needed (no TUI or human-only behaviour).

## Verification (for the decomposition itself)

- Four child task files under `aitasks/t1954/` with `depends` chain 1→2→3→4,
  topic anchor via the parent.
- Four plan files under `aiplans/p1954/`, committed.
- `./.aitask-scripts/aitask_ls.sh -v --children 1954 99` lists them.
- Each child's own verification is in its plan (matrices reproducible from the
  README commands; `go vet` of the harness module; no change under
  `goengines/`).

## Step 9 reference

Parent archival happens when the last child is archived (Step 9 of the child
workflows).

## Risk

### Code-health risk: low
- A Go module (`go.mod`, `go.sum`, harness code) under `aidocs/` could be picked up by tooling it was not meant for: the release tarball, gofmt/CI sweeps, or a future `ait-testmap scan` of aitasks (M10). The corpus uses the `.in` suffix, and `testmap:` text in harness code sits inside Go string literals, which the lexer classes as Literal. · severity: low · → mitigation: inline pre-phase scoped_commits_packaging_check
- The shared worktree holds other sessions' uncommitted work. A broad `git add` or commit would absorb it, and the harness's `replace` builds against whatever `goengines/` is on disk, including another session's uncommitted edits. · severity: low · → mitigation: inline pre-phase scoped_commits_packaging_check

### Goal-achievement risk: medium
- The baseline landed (`f096db065`), but later M2 children (M2.3–M2.6) extend `annot`, so the measured baseline can drift between child 1 and the report. · severity: low · → mitigation: inline post-phase baseline_rerun_at_landed_commit
- Kotlin and Swift have no native compiler locally. If one cannot be fetched into the scratch dir, their expectations rest on hand-written oracles, and the correctness claims for them are partly assumption. · severity: medium · → mitigation: inline post-phase native_oracle_gap_followup
- A candidate may prove unbuildable (WASM grammar build, gotreesitter on Go 1.27, ANTLR grammars). If it surfaces late, children 2–3 cannot be re-scoped in time. The two-prototype minimum is still safe (baseline, mvdan/sh, Chroma and gotreesitter are all pure Go). · severity: low · → mitigation: inline pre-phase feasibility_smoke
- The seam patch could alter baseline behaviour, which would contaminate every comparison. · severity: low · → mitigation: in-plan (the identical-matrix guard between the unpatched and the patched-but-unhooked snapshots, t1954_1 step 3)
- A synthetic corpus can overfit to the authors' own expectations. The read-only real-repo disagreement runs counter this. · severity: low · → mitigation: in-plan (t1954_1 realrepo disagreement runs)

Reassessed after t1853_2 landed and with the four inline phases: code-health stays **low**. Goal-achievement
stays **medium**, driven by the Kotlin/Swift oracle gap and by the research
outcome, which is open by design. The baseline drift risk is now **low**.

### Planned mitigations
- timing: pre-phase | name: feasibility_smoke | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: late-surfacing unbuildable candidate | desc: compile-probe every candidate module (CGO_ENABLED=0, 4 targets; cgo reference on host) before the corpus; re-scope children 2-3 by note
- timing: pre-phase | name: scoped_commits_packaging_check | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tooling pickup of the aidocs Go module; shared dirty worktree | desc: confirm release/install/CI/test discovery exclude the research dir; path-scoped commits only; goengines untouched
- timing: post-phase | name: baseline_rerun_at_landed_commit | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: baseline drift after t1853_2 landed | desc: re-run the baseline at the then-current annot commit and report any differences since the child-1 commit
- timing: post-phase | name: native_oracle_gap_followup | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: Kotlin/Swift without native oracle | desc: no supported claim beyond hand-oracle evidence; one bounded follow-up to validate on a host with the compiler
