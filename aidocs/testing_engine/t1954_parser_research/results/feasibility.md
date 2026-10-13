# Feasibility smoke (t1954_1 pre-phase `feasibility_smoke`)

- Date: 2026-10-12. Host: Intel Core Ultra 9 275HX, 24 threads, Linux x86_64.
  Toolchain: go 1.27.0 (local). `GOTOOLCHAIN=auto`, but the probes are
  separate modules without a `toolchain` line, so the local go1.27.0 built them.
- Rerun: `feasibility/functional_probes.sh <scratch-dir>`. It needs network
  access for `go get`; everything is written to `<scratch-dir>` and the Go
  module cache.
- Method: every probe **parses real input** with the candidate. A blank import
  was tried first and rejected as evidence. Dead-code elimination let the cgo
  binding `github.com/tree-sitter/go-tree-sitter` "build" under
  `CGO_ENABLED=0`, because its non-cgo files compile and nothing calls into C.
- Each probe is built `CGO_ENABLED=0 -trimpath -buildvcs=false` for the four
  release targets, linux/darwin × amd64/arm64 (`goengines/build.sh`). The
  official cgo binding is additionally built with `CGO_ENABLED=1`. "Host run"
  is the linux/amd64 binary's output.
- Reference size: a no-op probe (`golang.org/x/sync/errgroup` blank import)
  is 2,038,871 bytes on linux/amd64.

## Snippet

One snippet per language. Each puts a fake `testmap:covers` line inside the
language's hardest string form, then a real comment after it:
- bash: `$(cat <<EOF … EOF)`;
- Python: `"""…"""`;
- Go: a raw string;
- Kotlin: `"""…${1}…"""`;
- TS/JS: a template continuation after `${1}`;
- Java: a text block;
- Rust: `r#"…"#`;
- Swift: `#"""…"""#`.

The correct answer is **exactly 1 comment** and no error.

## Results

| candidate | version | Go req | linux/amd64 | linux/arm64 | darwin/amd64 | darwin/arm64 | size linux/amd64 (bytes) | host run |
|---|---|---|---|---|---|---|---|---|
| gotreesitter, all grammars embedded (default) | v0.55.1 | 1.22.0 | pass | pass | pass | pass | 35,056,288 | all 9 grammars: `err=false, comments=1` |
| gotreesitter, `grammar_subset` + the 9 grammars | v0.55.1 | 1.22.0 | pass | pass | pass | pass | 16,850,854 | identical to the line above |
| chroma/v2 (`lexers`) | v2.27.0 | 1.25 | pass | pass | pass | pass | 8,409,891 | `comments=1, errtok=0` for 8 languages; **swift: `comments=21`** |
| mvdan.cc/sh/v3 `syntax` | v3.14.1 | 1.26.0 | pass | pass | pass | pass | 3,070,659 | 1 comment at byte 42 (the real one); unterminated heredoc → parse error |
| antlr4-go/antlr/v4 (runtime only) | v4.13.1 | 1.22 | pass | pass | pass | pass | 2,458,075 | runtime works; no lexer without generating one from a `.g4` with the Java ANTLR tool |
| tetratelabs/wazero | v1.12.0 | 1.25.0 | pass | pass | pass | pass | 7,242,327 | instantiates a module |
| malivvan/tree-sitter (wazero + tree-sitter `.wasm`) | v0.0.1 | 1.23.4 | pass | pass | pass | pass | 11,617,648 | parses C; **bundles only the C and C++ grammars** |
| tree-sitter/go-tree-sitter + tree-sitter-go, `CGO_ENABLED=0` | v0.25.0 / v0.25.0 | 1.23 | **fail** | **fail** | **fail** | **fail** | — | `bindings/go: build constraints exclude all Go files` |
| tree-sitter/go-tree-sitter + tree-sitter-go, `CGO_ENABLED=1` | v0.25.0 / v0.25.0 | 1.23 | pass (host) | **fail** | **fail** | **fail** | 3,200,032 | `root=source_file err=false`; cross builds fail without a C cross toolchain (`gcc_arm64.S: no such instruction`, `clang: unsupported option '-arch'`) |

## Observations

- Every pure-Go candidate builds and runs under the engine's release
  constraints. No candidate child has to be re-scoped because of a build
  failure.
- The official Go binding cannot meet `CGO_ENABLED=0` at all: its grammar
  bindings are cgo-only. It also cannot cross-build from this host without
  per-target C toolchains. t1954_2 keeps it as a host-only reference parser,
  as planned.
- gotreesitter's default build embeds all ~206 grammars (35 MB). The curated
  `grammar_subset` build for the 9 grammars is still 16.9 MB, 14.8 MB over a
  no-op Go binary. That is a footprint fact for the recommendation, not a
  feasibility failure.
- The only published wazero tree-sitter wrapper (`malivvan/tree-sitter`)
  calls itself pre-release, has one version (v0.0.1) and bundles only C/C++.
  So the WASM route for the 8 research languages means compiling the runtime
  and grammars to wasm ourselves. t1954_2 was told by note.
- Chroma's Swift lexer reports 21 comment tokens for a snippet with 1 real
  comment, on the `#"""…"""#` raw multi-line string. This is a first hint that
  highlighter tokens do not establish comment context. It is recorded for
  t1954_3, and it is the matrix's job to measure it.

## Not measured here

Latency and memory. Those are the `bench` verb's job, per candidate, in the
child that prototypes it.
