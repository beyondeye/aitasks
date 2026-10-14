# Footprint (t1954_3)

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Rerun: `go run ./cmd/t1954 footprint-t3` (subprocess rows read the scratch installs named by `T1954_PYGMENTS_PYTHON`, `T1954_TS_NODE_MODULES`, `T1954_KOTLINC`, `T1954_TM_NODE_MODULES`, `T1954_LSP_NODE_MODULES`, `T1954_GOPLS`, `T1954_KOTLIN_LSP`). Go probes are built `CGO_ENABLED=0 -trimpath -buildvcs=false` for the four release targets and USE their library; Δ is against the no-op probe. The no-op, baseline-annot and engine rows of t1954_1 are in `footprint.md`.

## Go libraries

| probe | what | linux/amd64 | linux/arm64 | darwin/amd64 | darwin/arm64 | Δ vs no-op (linux/amd64) |
|---|---|---|---|---|---|---|
| noop | reference | 2021164 | 1989512 | 2162432 | 2080962 | +0 |
| chroma | github.com/alecthomas/chroma/v2 v2.27.0 `lexers` (the registry embeds every lexer; no per-language subset), 9 lexers used | 8411977 | 8036822 | 8523040 | 8176722 | +6390813 |
| antlr | antlr4-go/antlr/v4 v4.13.1 + the three generated lexers (provider/antlrgen: Kotlin, Java, Rust), driven directly | 3340239 | 3236327 | 3401952 | 3296754 | +1319075 |

## Subprocess providers and servers: runtime + library on disk

Not shippable in the engine's release artefact (one static Go binary): each needs a runtime the host must provide. Sizes are `du` of the scratch install (bytes, apparent size); the runtime row is the host's.

| provider / server | runtime | library on disk | runtime on disk |
|---|---|---|---|
| pygments | CPython (Python 3.14.7) | 20.6 MB (`lib`) | host CPython (system install; not measured) |
| pytokenize (t1954_1) | CPython | standard library only | host CPython (system install; not measured) |
| tsnative | Node.js (v25.2.1) | 23.6 MB (`typescript`) | 123.8 MB (`node`) |
| textmate | Node.js | 0.1 MB (`vscode-textmate`) + 0.5 MB (`vscode-oniguruma`) + 12.8 MB (`tm-grammars`) | 123.8 MB (`node`) |
| ktpsi | JVM (openjdk version "21.0.2" 2024-01-16) | kotlin-compiler.jar + stdlib + coroutines: 63.6 MB | 352.5 MB (`21.0.2`) |
| LSP: gopls | native binary | 43.2 MB (`gopls`) | — |
| LSP: pyright | Node.js | 19.5 MB (`pyright`) | 123.8 MB (`node`) |
| LSP: typescript-language-server | Node.js | 2.4 MB (`typescript-language-server`) + typescript 23.6 MB (`typescript`) | 123.8 MB (`node`) |
| LSP: kotlin-lsp | bundled JBR | 1199.7 MB (`kotlin-server-263.6379.0`) (includes its JBR) | — |
