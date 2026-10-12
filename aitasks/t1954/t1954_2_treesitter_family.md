---
priority: medium
effort: high
depends: [t1954_1]
issue_type: chore
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-12 17:51
updated_at: 2026-10-12 17:51
---

## Context

Child 2 of t1954 (annotation-parser research). It evaluates the **Tree-sitter family** on the infrastructure t1954_1 built: the research module at `aidocs/testing_engine/t1954_parser_research/`, the corpus and oracles, the immutable baseline, and the evaluation seam. The shared design is authoritative: read the parent plan `aiplans/p1954_research_multilanguage_annotation_parsers.md` and t1954_1's archived plan and `findings_t1954_1.md` first. Also read t1954_1's `results/feasibility.md` and any note sent to this task — they may re-scope candidates.

Engine constraints that decide eliminations:
- `CGO_ENABLED=0 -trimpath`; linux/darwin × amd64/arm64; offline prebuilt binaries.
- Dependency allowlist (yaml.v3, doublestar/v4, x/sync): a new dependency is a policy change to justify.
- `scan` budget 300 ms.

## Candidates

1. **gotreesitter** (`github.com/odvcencio/gotreesitter`, MIT): a pure-Go runtime that loads tree-sitter parse tables. About 119 of its 206 grammars ship **hand-written Go external scanners**. Pin a release and use curated build tags for the 8 grammars (bash, python, go, kotlin, typescript/javascript, java, rust, swift). Inventory which of those grammars rely on hand-ported external scanners and how parity is tested; those are custom readers by another name, so verify them hardest (bash heredocs, Python strings, Rust raw strings, TS templates, Kotlin, Swift).
2. **Official `github.com/tree-sitter/go-tree-sitter`** (cgo): the reference parser, with the same grammars on the C runtime and C scanners. Build it host-only under a separate build tag, so the default harness build stays CGO-free. Run a differential against gotreesitter, and record the CGO cost: the failure under `CGO_ENABLED=0` and the cross-toolchain needed for darwin.
3. **WASM**: the tree-sitter runtime and grammars compiled to wasm (`tree-sitter build --wasm`, via docker/emscripten in the scratch dir) run by wazero (pure Go), or an existing wrapper such as malivvan/tree-sitter. Prototype it if it builds; otherwise eliminate it with the recorded failure.

Each prototype implements the shared `Provider` interface:
- ERROR/MISSING nodes become `Diags`; a file with any of them is uncertain.
- Comments and string/heredoc/raw-string nodes become spans.
- Anchors come from nodes: package clause, imports, directive prologue, inner attributes.
- Python `DocInfo` comes from the module node: literal content bounds excluding prefix and quotes, raw flags, and the statement end including closing parens.
- Each runs the **full matrix in all 8 languages through the seam**: the lexical, range, record, edit, refusal and behaviour levels.

## Also deliver

- Grammar maintenance table: upstream repo, ABI version, last release, license, external-scanner presence, abandonment risk; curated pinned set vs bundle.
- Footprint (4 targets), cold/warm latency against the 300 ms budget, peak RSS.
- `findings_t1954_2.md`: observations / documentation claims / assumptions / unknowns, with the research date and versions.
- Path-scoped commits only; nothing under `goengines/` changes.

## Verification

- `baseline/fetch.sh && go run ./cmd/t1954 matrix --provider <p>` reproduces `results/matrix_<p>.md`.
- The cgo provider builds only under its tag.
- The default module build passes with `CGO_ENABLED=0`.
