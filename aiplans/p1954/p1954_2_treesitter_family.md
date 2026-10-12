---
Task: t1954_2_treesitter_family.md
Parent Task: aitasks/t1954_research_multilanguage_annotation_parsers.md
Sibling Tasks: aitasks/t1954/t1954_1_*.md, aitasks/t1954/t1954_3_*.md, aitasks/t1954/t1954_4_*.md
Archived Sibling Plans: aiplans/archived/p1954/p1954_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1954_2 — Tree-sitter family

## Context

Second child of t1954. It prototypes the Tree-sitter deployment options as
providers on t1954_1's harness (`R = aidocs/testing_engine/t1954_parser_research/`).
The shared design in `aiplans/p1954_research_multilanguage_annotation_parsers.md`
is authoritative: the interface, the seam, the metrics, and the rule that
claims must be bounded by what was measured. Read t1954_1's archived plan,
`R/findings_t1954_1.md`, `R/results/feasibility.md` and any inbox note first.

## Step 0 — reality check

- Run `R/baseline/fetch.sh`, `go run ./cmd/t1954 guard` and
  `go run ./cmd/t1954 matrix --provider baseline`. They must reproduce the
  committed baseline. If they do not, stop and record why.
- Re-check the latest releases and the Go requirement of each candidate.
  feasibility.md may already have eliminated or re-scoped one.

## Steps

1. **gotreesitter provider** (`R/provider/gotreesitter.go`)
   - Pin the release in `go.mod`. Use build tags or a curated registry so
     only the 8 grammars are linked.
   - **External-scanner inventory** (`R/results/ts_scanners.md`): for each
     grammar, list whether upstream has `scanner.c`, whether gotreesitter
     ships a hand-written Go port, which upstream commit its tables came from,
     and which parity tests cover it. Name the constructs the scanners
     implement: bash heredocs/strings, Python string/indent, Rust raw
     strings/block comments, TS template strings/regex, Kotlin, Swift.
   - Node mapping:
     - comment nodes → `LineComment` / `BlockComment`, split by leading
       bytes rather than by node name, because node names differ per grammar;
     - string, heredoc and raw-string nodes → literal spans;
     - `ERROR` nodes and `MISSING` nodes (`IsMissing`) → `Diags`.
   - Leaves are collected for `FullCover`; the gaps between leaves are
     whitespace, and the reconstruction check verifies that.
   - Anchors: package clause (Go/Kotlin/Java/Swift as applicable), the end of
     the import block, the directive prologue (TS/JS `"use strict"`), and Rust
     inner attributes / `//!`.
   - Python `DocInfo`: when the first statement of `module` is an
     `expression_statement` whose child is a `string` or `concatenated_string`
     (possibly parenthesised), build `Literals` from the `string_content`
     bounds plus the prefix raw flag, and `StmtEnd` from the statement node's
     end byte. An f-string, a bytes literal or a call is not a docstring,
     whatever the grammar emits.
2. **Reference cgo provider** (`R/provider/tscgo.go`, `//go:build t1954cgo`)
   - Use `github.com/tree-sitter/go-tree-sitter` with the official grammar
     modules pinned to the commits gotreesitter extracted from (or the
     nearest). Build on the host only.
   - **Differential** (`R/results/ts_differential.md`): for every corpus file
     and the real-repo sets, compare the gotreesitter and cgo trees. Report
     node-kind/byte-range mismatches and ERROR-placement differences per
     grammar, and attribute each to its runtime, table or scanner.
   - **CGO cost**: record the exact failure under `CGO_ENABLED=0`, the
     toolchains needed to cross-build darwin/arm64 (zig cc or osxcross), and
     the binary size.
3. **WASM provider** (`R/provider/tswasm.go`)
   - Either the wrapper found feasible in feasibility.md, or the tree-sitter
     runtime and grammars built to wasm (`tree-sitter build --wasm` via the
     emscripten docker image into the scratch dir) and driven by wazero.
   - Record the build recipe, wasm sizes, wazero version and startup
     (compile/instantiate) cost. Note the node-handle boxing limitation where
     it applies.
   - If it cannot be made to work within the task, eliminate it with the
     recorded failure in the findings. This is not a reason to stall.
4. **Matrix runs**: every provider in all 8 languages through the seam
   (lexical, range, record, edit, refusal, behaviour), plus `realrepo` and
   `bench`/`footprint` for each.
   - Measure ERROR/MISSING recovery behaviour explicitly: on the malformed
     fixtures, does any provider produce a tree without ERROR/MISSING (silent
     recovery)? That would be a Silent-uncertain failure.
   - Report a local-error policy (refuse only near the error) as an
     alternative column, with its false-writable count. The default policy
     stays whole-file refusal (M2.2 D9).
5. **Grammar maintenance** (`R/results/ts_grammars.md`)
   - Per grammar: upstream repo, ABI version, last release/commit date,
     contributors and open issues (`gh api`, read-only), license (read from
     the LICENSE files), external-scanner presence, and abandonment
     indicators.
   - The pinning model: a curated pinned set or a bundle; how to update a
     pin, and what a conformance run must show before a bump.
6. **Findings** `R/findings_t1954_2.md`: observations, documentation claims
   (e.g. gotreesitter's README parity claims) vs measured results,
   assumptions, unknowns, the research date and every version and commit.

## Verification

- `go build ./...` with `CGO_ENABLED=0` passes; the cgo provider builds only
  with `-tags t1954cgo`.
- README commands reproduce `R/results/matrix_{gotreesitter,tscgo,tswasm}.md`.
- Each provider's safety columns are reported in all 8 languages, with
  `unsupported` / `n/a` explicit.
- Commits name only paths under `R`.

## Step 9 reference

`chore: … (t1954_2)` commit of `R` paths; standard child archival.
