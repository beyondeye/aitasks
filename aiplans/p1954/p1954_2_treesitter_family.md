---
Task: t1954_2_treesitter_family.md
Parent Task: aitasks/t1954_research_multilanguage_annotation_parsers.md
Sibling Tasks: aitasks/t1954/t1954_1_*.md, aitasks/t1954/t1954_3_*.md, aitasks/t1954/t1954_4_*.md
Archived Sibling Plans: aiplans/archived/p1954/p1954_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-13 15:43
---

# Plan: t1954_2 — Tree-sitter family

## Context

Second child of t1954. It prototypes the three Tree-sitter deployment options as
providers on the harness t1954_1 landed in `5e730b0fb`
(`R = aidocs/testing_engine/t1954_parser_research/`) and scores them through
the real M2.2 grammar and rewriter (the seam). The shared design in
`aiplans/p1954_research_multilanguage_annotation_parsers.md` is authoritative
(interface, `ToContext` per-operation capability enforcement, metrics,
measurement rules, "claims bounded by what was measured"). Nothing under
`goengines/` changes; every commit names paths under `R` only.

## Verification of this plan (2026-10-13, at pick time)

Checked against the landed harness, `R/results/feasibility.md`,
`R/findings_t1954_1.md` and the two inbox notes from t1954_1 (acknowledged).
The plan stands with these corrections, folded into the steps below:

- **Harness is landed and healthy.** `CGO_ENABLED=0 go build ./...` passes;
  the research dir is clean in git. Providers register via
  `provider/registry.go` `register()`; `matrix --provider all` writes
  `matrix_<p>.md` per subject plus combined `matrix.md`. `bench` and
  `footprint` **hardcode** their subject/probe lists (`benchSubjects`,
  `lexSubjects`, `footprintProbes` in `cmd/t1954/{bench,footprint}.go`), and
  `bench` has no subject filter → both need small extensions.
- **Versions unchanged.** gotreesitter latest is still **v0.55.1** (Go ≥1.22);
  official `go-tree-sitter` v0.25.0 (vendors the C runtime `src/lib.c`);
  wazero v1.12.0. Local: go1.27.1 (auto toolchain), tree-sitter CLI 0.26.9,
  docker 29, node 25. **No zig / emcc / wasi-sdk locally.**
- **Grammar set is 10, not 8.** The corpus has `.tsx` and `.jsx` fixtures, so
  the curated set is bash, python, go, kotlin, typescript, **tsx**,
  javascript (handles JSX), java, rust, swift.
- **The dialect is invisible to providers.** `Provider.Analyze(lang, src)` and
  the seam's `ClassifyHook(Lang, data)` carry no path, and `langs.go` maps
  `.tsx` to the `typescript` Lang. A tree-sitter provider therefore cannot pick
  the TSX grammar (parsing `.ts` with TSX misreads `<T>x` assertions; `.tsx`
  with TS errors out). Fix: a research Lang `tsx` (see step 1).
- **Grammar provenance is pinned upstream.** gotreesitter's
  `grammars/languages.lock` pins each grammar's upstream commit
  (bash a06c2e44, python 26855eab, go 2346a3ab, kotlin = fwcd 1852ea17,
  typescript/tsx 75b3874e, javascript 58404d8c, java e10607b4, rust 77a37472,
  swift = alex-pinkus 00bbb0a2). The C references build **exactly these
  commits**, so a differential isolates runtime/table/scanner differences
  instead of grammar-version drift.
- **Swift ships no generated parser at that commit** (`src/` has
  `grammar.json`, `scanner.c`, no `parser.c`; `gh api` read-only), and
  `tree-sitter-swift` has no tagged Go module. Its C reference must generate
  `parser.c` with the pinned CLI.
- **gotreesitter is not uniformly "extracted tables".** Per its
  `docs/architecture.md` / `docs/grammar-ownership.md`, tables are normally
  ts2go-extracted from upstream `parser.c`, but some grammars are
  **grammargen-owned** (Go is "Own": a Go-DSL re-implementation of the
  grammar), and some use **hand-written Go lexers** (`grammars/go_lexer.go`,
  `grammars/java_lexer.go`) in addition to Go-ported external scanners
  (`grammars/<lang>_scanner.go` for bash, python, go, kotlin, typescript, tsx,
  javascript, rust, swift). All three are "custom readers by another name" and
  go into the inventory.
- **gotreesitter can stop early.** `Tree.ParseStoppedEarly()` /
  `ParseStopReason()` / `ParseStrict` exist (work limits): a stopped parse
  must become a Diag, never a silently short tree.
- **WASM route re-scoped (note 2):** the only wrapper (malivvan v0.0.1) bundles
  C/C++ only, but its recipe is reusable: one **WASI reactor** module built with
  `zig cc --target=wasm32-wasi-musl -mexec-model=reactor` from the runtime
  `lib.c` + grammar sources, driven by wazero. `tree-sitter build --wasm`
  produces emscripten SIDE_MODULEs for web-tree-sitter's loader, which wazero
  cannot link — recorded as an eliminated sub-route, not attempted further.

## Step 0 — reality check

- `cd R && baseline/fetch.sh && baseline/fetch.sh --unpatched` (no-op if
  present and valid), `go vet ./... && go test ./...`,
  `go run ./cmd/t1954 guard`, and
  `go run ./cmd/t1954 matrix --provider baseline --out <scratch>/m0`, diffed
  against `results/matrix_baseline.md`. A difference stops the task and is
  recorded.
- Record `uptime` load before every timed run (bench needs an idle host).

## Steps

1. **Harness extensions (shared, behaviour-neutral for existing subjects)**
   - `provider/langs.go`: add `TSX = annot.Lang{Name: "tsx", Leader: "//"}`;
     map `.tsx` → `TSX` (`.ts/.mts` stay `typescript`, `.jsx` stays
     `javascript`); add to `byName`, `ResearchLangs`, `IsResearch`.
   - `provider/adapter.go` `requiredAnchors["tsx"] = AImportEnd|APrologue`;
     `provider/placement.go` case `"typescript","tsx","javascript"`;
     `internal/oracle/oracle.go:60` and `cmd/t1954/oraclecheck.go:189` accept
     `"tsx"` alongside `typescript`/`javascript`. Rows stay grouped by corpus
     dir (`Row.Lang = c.Lang`), so tables keep 8 language rows.
   - `cmd/t1954/bench.go`: `--subjects` and `--lex-subjects` flags (defaults =
     today's lists) so the tree-sitter rows can be measured into a separate
     file without re-measuring t1954_1's rows.
   - `cmd/t1954/footprint.go`: new probes (step 6); keep the existing rows.
   - **Neutrality check:** after this step, rerun `matrix` (all default
     subjects), `oraclecheck` and `guard`; the committed `results/` files must
     be byte-identical (`git diff --stat -- R/results` empty). Any change is a
     defect in this step, not a finding.

2. **Shared tree-sitter mapping** (`provider/tsmap.go`, no build tag, no
   runtime import) — one mapping for all three runtimes, so the differential
   compares runtimes, not three mapping implementations.
   - Input: a flat preorder node list `[]TSNode{Kind string; Start, End int;
     Parent int; Named, Error, Missing, Extra bool}` plus `stopped string`
     (empty = complete parse).
   - Per-language kind tables (`tsKinds[lang]`), read from each grammar's
     `node-types.json` at the pinned commit: comment kinds; data kinds
     (strings, raw strings, chars, regex, templates, JSX text); code-island
     kinds inside data (bash `command_substitution`/`process_substitution`/
     `arithmetic_expansion`/`expansion`; python `interpolation`; TS/JS/TSX
     `template_substitution`; kotlin/swift interpolated expressions); heredoc
     kinds; anchor kinds.
   - Spans:
     - comment node → `LineComment` if its bytes start with the leader (`#`
       or `//`), else `BlockComment`; a trailing `\r` is trimmed (CRLF);
     - data node → `String` span(s) = node range minus its code-island
       children (so a line starting inside `${…}`/`$( … )` stays code, and a
       real comment inside a multi-line f-string field is still a comment);
     - bash heredoc body → one `Heredoc` span from body start through the
       terminator line (as `shfmt` does; heredoc lines are never writable).
   - Diags: every `ERROR` node and every `MISSING` node; `stopped != ""` →
     a Diag `"parse stopped early: <reason>"`; a root that ends before the last
     non-whitespace byte → Diag. A runtime panic/error → `Analyze` returns an
     error (reported unsupported/not measured, never "no comments").
   - Anchors (top-level children of the root only, comments skipped), 1-based
     lines: go `package_clause` → Package, last `import_declaration` end →
     ImportEnd; kotlin package header / last import header; java
     `package_declaration` / last `import_declaration`; TS/JS/TSX last
     top-level `import_statement` → ImportEnd and the last leading directive
     (`expression_statement` whose only child is a `string`) → Prologue; rust
     leading `inner_attribute_item` / `//!` `/*!` → InnerAttrEnd, last
     `use_declaration` → ImportEnd; swift last `import_declaration`; bash
     shebang. Declared `Capabilities.Anchors` = exactly what is computed per
     language (declared zero = confirmed none).
   - Python `DocInfo`: first non-comment child of `module` is an
     `expression_statement` whose single child is a `string` or
     `concatenated_string`, possibly inside `parenthesized_expression`; each
     literal's content = `string_start.End` → `string_end.Start`, `Raw` from
     the prefix in `string_start`; a prefix containing `f`/`F` or `b`/`B`
     (and any `call`) is not a docstring. `StmtEnd` = the
     `expression_statement` end byte (excludes `;`, includes closing parens).
   - Caps for every language: `TokenRanges`, `FullCover` (leaves + gaps are
     whitespace → leaves emitted as a partition including gap spans), `Errors`,
     `DocLiterals` (python), `Anchors` as above.
   - `provider/tsmap_test.go`: the hardest snippets per language (fake
     `testmap:` line inside each string form + real comment after it; f-string
     field spanning lines; JSX text with `//`; TS template continuation after
     `${1}`; Rust `r#"…"#`; Swift `#"""…"""#`; bash heredoc in `$( )`;
     docstring shapes: parenthesised, concatenated, raw, f-string/bytes/call =
     none), malformed input → Diags, and a **kind-table guard**: every kind
     listed in `tsKinds` exists in the grammar's symbol table, so a grammar
     bump that renames a kind fails loudly instead of silently unmapping it.

3. **gotreesitter provider** (`provider/gotreesitter.go`, default build)
   - `go get github.com/odvcencio/gotreesitter@v0.55.1`; default embedding
     (no tags needed to reproduce); one `*Parser` per language, created lazily.
   - Parse with `Parser.Parse`, then `tree.ParseStoppedEarly()` →
     `stopped`; walk to `[]TSNode`; `tsmap`. `Name() = "gotreesitter"`,
     `Langs()` = the 9 research/M2.2 lang names incl. `tsx`.
   - Regenerate `go.unpatched.mod/.sum` (README procedure); guard must pass.

4. **C reference sources** (`tsref/`)
   - `tsref/LOCK` (committed): per grammar, repo, commit (copied from
     gotreesitter v0.55.1 `grammars/languages.lock`), subdir, and sha256 of
     `parser.c`/`scanner.c` (Swift: of the generated `parser.c`, with the CLI
     version).
   - `tsref/fetch.sh` (bash, `set -euo pipefail`): shallow-fetch each repo at
     its commit into `R/.tsref/<lang>/` (gitignored), verify the commit, run
     `tree-sitter generate src/grammar.json` for Swift, verify every sha256
     against `LOCK` and exit 2 on any mismatch (same fail-closed shape as
     `baseline/fetch.sh`). `.gitignore` gains `/.tsref/` and `/.tswasm/`.

5. **Reference cgo provider** (`provider/tscgo.go`, `//go:build t1954cgo && cgo`)
   - `github.com/tree-sitter/go-tree-sitter v0.25.0`; one cgo package per
     grammar under `provider/tscgo/<lang>/` (separate translation units:
     parser.c statics clash otherwise) whose preamble `#include`s
     `.tsref/<lang>/…/parser.c` and `scanner.c` — the official
     `bindings/go` pattern — exporting the `TSLanguage*`.
   - Walk with a `TreeCursor` into `[]TSNode`; same `tsmap`. Registered only
     under the tag.
   - **Differential** (`results/ts_differential.md`, verb `tsdiff` behind the
     tag): for every corpus file and the real-repo file sets (read-only), compare
     gotreesitter vs tscgo at two levels — (a) the provider `Result` (spans,
     diags, anchors, doc: the safety-relevant level) and (b) the trees (kind,
     byte range, error/missing flags, first divergent node). Per grammar:
     counts, ERROR-placement differences, and a **cause column** whose values
     are drawn from {mapping, table, scanner, runtime, unknown} under the
     evidence rules of post-phase `failure_attribution_pass`. A divergence
     alone never establishes a cause: anything not proven in isolation is
     labelled `heuristic:<cause>` or `unknown`. A runtime failure is its own
     row, never "no difference".
   - **CGO cost:** record the `CGO_ENABLED=0` result for a tagged build, the
     host cgo build, and a darwin cross attempt with zig as `CC`
     (`zig cc -target aarch64-macos` / `x86_64-macos`) — pass or exact failure.

6. **WASM provider** (`provider/tswasm.go`, `//go:build t1954wasm`)
   - `tswasm/build.sh`: download a pinned zig release (version + sha256) into
     the scratch dir; compile go-tree-sitter v0.25.0's vendored `src/lib.c`
     (same runtime source as tscgo, from the module cache) + the 10 grammars
     from `.tsref/` + a small C shim into one reactor `R/.tswasm/ts.wasm`;
     record its sha256 and size. If zig fails, try the wasi-sdk docker image;
     if both fail, eliminate the route with the recorded failure and move on.
   - `tswasm/shim.c`: `t1954_parse(lang_id, src, len)` walks the tree inside
     wasm and returns a flat preorder buffer (symbol, start, end, parent,
     flags) + symbol-name lookup — one host↔guest call per file, and no
     `TSNode` struct-by-value crossing.
   - Go side: wazero runtime (compile once per provider, instantiate once),
     WASI preview1; decode into `[]TSNode`; same `tsmap`. Record compile and
     instantiate time, and whether wazero uses its compiler or interpreter per
     target.
   - Add tswasm to the differential (expected identical to tscgo; any
     difference is a wasm-toolchain/engine finding).

7. **Matrix, real repos, bench, footprint**
   - `go run -tags 't1954cgo t1954wasm' ./cmd/t1954 matrix` → new
     `matrix_{gotreesitter,tscgo,tswasm}.md`, combined `matrix.md` (README
     states the committed combined file comes from the full-tag build). The
     existing per-subject files must stay byte-identical.
   - Explicitly reported: on malformed fixtures, any provider producing no
     ERROR/MISSING (Silent-uncertain); and a **local-error policy** column
     (refuse only lines near a Diag) with its FP-writable count, as an
     alternative — the default stays whole-file refusal (M2.2 D9).
   - `realrepo --provider gotreesitter,tscgo,tswasm --out results/ts` for the
     six repos (read-only) → `results/ts/realrepo_<repo>.md`; Kotlin across
     thinking_app / timexchange / aitasks_mobile is the main real-world
     evidence for the Kotlin custom reader.
   - Bench on an idle host, from one binary built with
     `-tags 't1954cgo t1954wasm'` (so the re-executed `bench-child` processes
     carry the same providers): `bench --subjects <every successfully built
     provider of gotreesitter,tscgo,tswasm> --lex-subjects <same>
     --out results/bench_ts.md`.
     - **End-to-end** (the budget-comparable `registry.Scan` over the M2.2
       shape, bash + python through the subject via `ClassifyHook`, other
       languages delegated as today): cold and warm, and peak RSS (process and
       subprocesses), for **every** built provider, each judged against the
       300 ms budget. The tswasm row's cold number includes wazero compile +
       instantiate (provider construction is inside the cold timer). The
       tscgo row is labelled **host-only (cgo; not buildable for the release
       targets)** — reference evidence, not a deployable configuration.
     - A provider eliminated in steps 5–6 gets an explicit
       `eliminated — not measured (see findings)` row, never an omission.
     - **Lexical-only** rows (M2.2 test files, aitasks tests, the sibling
       sets incl. Kotlin) for the same providers, labelled not
       budget-comparable; wazero compile/instantiate times are reported
       separately as supplementary detail, not as budget evidence.
   - `footprint`: probes for gotreesitter `grammar_subset` + the 10
     `grammar_subset_<lang>` tags (4 targets), gotreesitter default (all
     grammars) for reference, tswasm (wazero + embedded wasm, 4 targets),
     tscgo (`CGO_ENABLED=0` → recorded failure; host cgo size). Existing rows
     unchanged.

8. **Inventories**
   - `results/ts_scanners.md`, per grammar: upstream `scanner.c` present?;
     gotreesitter Go scanner file; hand-written Go lexer file; table source
     (ts2go-extracted vs grammargen-owned, from `grammars/grammar_ownership.go`);
     upstream commit; in-module tests touching it (`grammars/<lang>_*_test.go`)
     and upstream parity boards (`docs/c-parity-boards.md`, cited as
     documentation claims); the constructs the scanner implements (from the
     grammar's `externals`: bash heredocs/strings, python string/indent, rust
     raw strings/block comments, TS templates/ASI, kotlin, swift); and the
     measured differential result for that grammar.
   - `results/ts_grammars.md`, per grammar: upstream repo, pinned commit, ABI
     (`LANGUAGE_VERSION` in parser.c), last release + date, last commit date,
     contributors, open issues, archived flag (`gh api`, read-only), license
     (LICENSE at the commit), scanner presence, Go-binding availability,
     abandonment indicators; plus gotreesitter itself (cadence, license,
     `licenses/grammars.json`). Pinning model: gotreesitter bumps all
     grammars together (bundle coupling) unless blobs are supplied externally
     (`grammar_blobs_external`); the conformance gate before any bump = zero
     safety regressions on the corpus matrix and the real-repo walks.

9. **Findings** `R/findings_t1954_2.md`: observations / documentation claims
   (e.g. gotreesitter README parity and "error-free trees" claims vs measured)
   / assumptions / unknowns, research date, every version, commit and sha256.
   README: rerun commands for the three providers, the tags, `tsref/fetch.sh`,
   `tswasm/build.sh`, and the env vars they need.

### Post-phase (risk mitigations)

1. [failure_attribution_pass] For every non-zero safety or recall cell of
   `gotreesitter` (FP-writable, Silent-uncertain, Record-corruption,
   Docstring-write, Missed-writable, Missed-comment, Read-mismatch), run the
   same fixture through `tscgo` and dump both trees (`classes` verb +
   a tree dump with leaves). Possible causes stay open — **mapping, table,
   scanner, runtime, unknown** — for shared and gotreesitter-only failures
   alike: gotreesitter's tables are not always the C ones (Go is a
   grammargen-owned rewrite; Swift's C `parser.c` is our own generation), so a
   gotreesitter-only failure can be a table difference, not a runtime one.
   Evidence rules:
   - **mapping (definitive)** only when the tree is correct and `tsmap`'s
     output is wrong, reproduced by a new `tsmap_test.go` case → fix
     `tsmap`, then rerun steps 7–8;
   - **definitive for table / scanner / runtime** only when a minimal
     snippet reproduces it **and** additional evidence isolates that single
     component (e.g. changing only that component — swapping in the other
     runtime's tables or scanner, where that is actually possible — changes
     the result). No such isolation work is required; when it is not
     available, the cause is not definitive;
   - otherwise the cause is recorded as `heuristic:<cause>` with the
     indicator that suggested it, or `unknown`. Heuristic indicators include:
     identical leaf/token streams with a different tree (consistent with
     **either** a table difference or a runtime defect — it does not choose
     between them); table provenance from `ts_scanners.md` (it says where
     the tables came from, not what caused the failure); an external-token
     kind at the first divergent leaf; recovery-placement differences.
   Record each failure (fixture, cell, cause, evidence or heuristic label) in
   `findings_t1954_2.md` and the differential's cause column before any
   claim about a candidate.
2. [deliverable_completeness_check] Before the commit, walk the task's
   "Also deliver" and "Verification" lists and this plan's steps 1–9: each
   item must be a committed file with measured content, or carry an explicit
   `eliminated: <recorded failure>` / `not measured: <reason>` record. List
   every not-measured cell in the findings' Unknowns section; any silent gap
   blocks the commit.

## Verification

- `CGO_ENABLED=0 go vet ./... && go test ./...` (default build) passes;
  `go test -tags t1954cgo ./provider/...` passes on the host; the cgo provider
  is absent from the default build (`go run ./cmd/t1954 matrix --provider
  tscgo` fails with "unknown provider").
- `go run ./cmd/t1954 guard` passes; existing `results/matrix_{baseline,
  goscanner,pytokenize,shfmt}.md`, `oracle_check.md`, `guard.md` are
  byte-identical after regeneration.
- `tsref/fetch.sh && go run ./cmd/t1954 matrix --provider gotreesitter`
  reproduces `results/matrix_gotreesitter.md`; the tagged commands reproduce
  `matrix_tscgo.md` / `matrix_tswasm.md` (or the WASM elimination record).
- `results/bench_ts.md` has end-to-end cold/warm and peak-RSS rows for every
  successfully built tree-sitter provider (tscgo labelled host-only) and an
  explicit row for any eliminated one.
- Every provider's safety columns are reported in all 8 corpus languages with
  `unsupported` / `n/a` / `not measured` explicit.
- `git status --short` shows paths under `R` only (plus task/plan files);
  nothing under `goengines/` changes; commits name their paths.

## Step 9 reference

`chore: Add t1954 tree-sitter family providers and evidence (t1954_2)` commit
of `R` paths only; standard child archival (Step 9).

## Risk

### Code-health risk: low
- The `tsx` research Lang and the bench/footprint flags touch shared harness files (`langs.go`, `adapter.go`, `placement.go`, `oracle.go`, `oraclecheck.go`, `bench.go`, `footprint.go`) that t1954_3/4 also use; a mistake could silently shift t1954_1's committed evidence. · severity: low · → mitigation: in-plan (step 1 neutrality check: committed results byte-identical after regeneration)
- The shared worktree holds other sessions' uncommitted work; new go.mod deps and gitignored fetch dirs must not leak into commits or into `goengines/`. · severity: low · → mitigation: in-plan (path-scoped commits, `.tsref/`/`.tswasm/` gitignored, downloads in scratch)

### Goal-achievement risk: low
- Scope is large (three runtimes × 10 grammars, a differential, two inventories, bench, footprint, real-repo walks); some deliverable could end up silently missing rather than recorded as not measured / eliminated. · severity: low (residual — addressed by inline post-phase deliverable_completeness_check) · → mitigation: inline post-phase deliverable_completeness_check
- A wrong or incomplete per-language kind table in the shared mapping would show up as a tree-sitter failure (FP-writable, missed comments) and be blamed on the candidate. · severity: low (residual — addressed by inline post-phase failure_attribution_pass, plus the kind-table guard test and the shared mapping) · → mitigation: inline post-phase failure_attribution_pass
- The WASM route needs a toolchain not on the host (zig / wasi-sdk) and a custom shim; it may not build. · severity: low · → mitigation: in-plan (explicit elimination path with the recorded failure)
- Swift's C reference uses a `parser.c` generated by CLI 0.26.9, which may not match the tables gotreesitter used, so the differential could mix table and runtime differences for Swift. · severity: low · → mitigation: in-plan (attribution labelled heuristic; generator version recorded)
- Bench numbers on a host shared with concurrent agents can be inflated. · severity: low · → mitigation: in-plan (load recorded before each timed run; idle-host requirement)

Reassessed with the two inline post-phases: code-health stays **low**;
goal-achievement drops to **low** — every remaining risk is bounded by an
in-plan mechanism or an explicit elimination/not-measured record, and the
research outcome itself is open by design.

### Planned mitigations
- timing: post-phase | name: failure_attribution_pass | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: mapping/kind-table mistakes blamed on the candidate | desc: cross-check every non-zero gotreesitter cell against tscgo; causes stay open (mapping/table/scanner/runtime/unknown); definitive only when isolated, else heuristic; fix mapping bugs; record in findings
- timing: post-phase | name: deliverable_completeness_check | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: large scope, silently missing deliverables | desc: before the commit, every deliverable is a measured file or an explicit eliminated/not-measured record
