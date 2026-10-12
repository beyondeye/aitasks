---
priority: medium
effort: high
depends: []
issue_type: chore
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
created_at: 2026-10-12 17:50
updated_at: 2026-10-12 17:55
---

## Context

Child 1 of t1954 (research: sustainable multi-language annotation reading and safe editing for `ait test` / testmap). The parent plan `aiplans/p1954_research_multilanguage_annotation_parsers.md` is authoritative: it holds the **shared design** every child follows. That design covers layout, immutable baseline, evaluation seam, experimental interface, oracle file formats, metrics, corpus coverage and measurement rules. Read it in full first.

M2.2 (t1853_2) landed in `f096db065`, with its contract in the proposal at `7229dee86`. It reads and writes `testmap:` lines only on lines its lexer proves are comments (`goengines/internal/testmap/annot/lexctx.go`): `go/scanner` for Go, handwritten readers for bash, Python and Kotlin. This child builds the reproducible research infrastructure and measures that baseline. Children 2 and 3 prototype candidate providers on it; child 4 writes the report and recommendation.

User decisions:
- The harness is a **separate Go module under `aidocs/`**, never built or shipped by goengines.
- Sibling repos may be scanned **read-only**: counts and paths only, nothing executed.
- Languages: bash, Python, Go and Kotlin, plus TS/JS, Java, Rust and Swift.

## Key files to create (all new)

- `aidocs/testing_engine/t1954_parser_research/`
  - `README.md`, `.gitignore` (ignores `.baseline/`)
  - `go.mod`: module `github.com/beyondeye/aitasks/goengines/t1954research`, with `replace github.com/beyondeye/aitasks/goengines => ./.baseline/goengines`; never the live checkout
  - `baseline/PIN`, `baseline/fetch.sh`, `baseline/seam.patch`. The patch adds exactly two nil-by-default hooks to the snapshot's `annot`: `ClassifyHook`, which `Classify` delegates to, and `LangHook`, which `LangOf` consults first. Nothing else.
  - `provider/` (interface, shared adapter `ToContext`, providers)
  - `cmd/t1954/` (`matrix`, `edit`, `realrepo`, `bench`, `footprint`)
  - `oracle/`
  - `corpus/<lang>/*.in` + `.expect` + `.edits`
  - `results/`
  - `findings_t1954_1.md`
- **Nothing under `goengines/` is modified.**

## Reference files

- `goengines/internal/testmap/annot/`:
  - `lexctx.go`: `Classify`, `Context{Class, Docs, DocEnd, Package, Import, Uncertain}`
  - `lang.go`: `LangOf`
  - `grammar.go`: `ParseFile`, `TestDocstringValue` in `grammar_test.go`
  - `rewrite.go`: `Apply`, `PlanCovers`, `Placement`, `fixedPosition`, `RestampLine`
  - `testdata/parse` and `testdata/placement`: fixtures to copy, with their goldens
  - `lexctx_test.go`
- `aiplans/archived/p1853/p1853_2_m2_2_annotation_grammar_rewriter.md`: design D1–D18 and the Final Implementation Notes, including the probe that used Python tokenize/ast and shfmt as oracles.
- `goengines/README.md`: dependency allowlist, CGO-free build for 4 targets, benchgate conventions.
- `goengines/bench/baseline.txt`: `annot.BenchmarkScan` ≈21 ms, budget 300 ms.

## Implementation plan (summary — full plan in `aiplans/p1954/p1954_1_*.md`)

0. Pre-phase (risk mitigations):
   - `feasibility_smoke`: compile-probe every candidate module (gotreesitter, the wazero tree-sitter wrapper, Chroma, mvdan/sh, ANTLR4 Go) under `CGO_ENABLED=0` for linux/darwin × amd64/arm64, plus cgo go-tree-sitter on the host. Write the results to `results/feasibility.md`, and note t1954_2 / t1954_3 if anything fails.
   - `scoped_commits_packaging_check`: show that release/install, `goengines-check.yml`, python test discovery and the shellcheck globs never touch the research dir. Commit only named paths.
1. Research dir and module; immutable baseline (`git archive` of the pinned commit, tree-id verification, patch sha256, refuse on an IDENTITY mismatch).
2. Corpus with `.expect` (separate `read` records, `writable`, `readonly`, `lookalikes`, `refuse`, `placement`) and `.edits` (ops with expected outcome and the full after-record list) for all 8 languages and every mandatory case. Native cross-checks where available; Kotlin/Swift compilers into the scratch dir if obtainable, else `native: none`.
3. Harness: interface, adapter, record/edit runner through the seam (real `ParseFile → PlanCovers → Apply` on scratch copies), and the unpatched vs patched-unhooked identical-matrix guard.
4. Providers: `baseline` (range checks `n/a — not exposed`); native oracles `go/scanner`, Python `tokenize`+`ast` (fills `DocInfo`), shfmt/mvdan.
5. Results: matrices, real-repo disagreement, performance against the 300 ms budget, `findings_t1954_1.md`.

## Verification

- `baseline/fetch.sh && go vet ./... && go run ./cmd/t1954 matrix` reproduces `results/` from the README commands.
- The identical-matrix guard passes.
- A tampered `.baseline/IDENTITY` refuses to run.
- `git status` shows changes only under the research dir.
