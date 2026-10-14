# Footprint — tree-sitter family (t1954_2)

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Probe binaries built `-trimpath -buildvcs=false` like `results/footprint.md` (t1954_1), whose no-op reference is rebuilt here: 2021164 bytes on linux/amd64.

Rerun: `tsref/fetch.sh && tswasm/build.sh <zig> && go run ./cmd/t1954 footprint --ts --ts-only --zig <zig>`. Each probe parses real input with all 10 research grammars (a blank import would let dead-code elimination hide the cost). Δ is against the no-op probe above. A failure is the most informative line of the build error (`<R>` = the research directory).

| probe | what | linux/amd64 | linux/arm64 | darwin/amd64 | darwin/arm64 | Δ vs no-op (linux/amd64) |
|---|---|---|---|---|---|---|
| gotreesitter (subset) | gotreesitter v0.55.1, `grammar_subset` + the 10 `grammar_subset_<lang>` tags, CGO_ENABLED=0 | 17009379 | 15730022 | 17295792 | 16229586 | +14988215 |
| gotreesitter (all) | gotreesitter v0.55.1, default embedding (all ~206 grammars), CGO_ENABLED=0 | 35051168 | 33695763 | 35392992 | 34344306 | +33030004 |
| tswasm | wazero v1.12.0 + the embedded `.tswasm/ts.wasm` (C runtime + 10 grammars), CGO_ENABLED=0 | 24345615 | 23983325 | 24389808 | 24187938 | +22324451 |
| tscgo (CGO_ENABLED=0) | go-tree-sitter v0.25.0 + the 10 C grammars (`-tags t1954cgo`), CGO_ENABLED=0 — the release constraint | fail: imports github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsbash: build constraints exclude all Go files in <R>/provider/tscgo/tsbash | fail: imports github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsbash: build constraints exclude all Go files in <R>/provider/tscgo/tsbash | fail: imports github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsbash: build constraints exclude all Go files in <R>/provider/tscgo/tsbash | fail: imports github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsbash: build constraints exclude all Go files in <R>/provider/tscgo/tsbash | — |
| tscgo (host cgo) | the same with CGO_ENABLED=1, host toolchain (gcc) | 19614464 | not attempted | not attempted | not attempted | +17593300 |
| tscgo (cgo, zig cc cross) | the same with CGO_ENABLED=1 and `zig cc -target <triple>` as CC (zig 0.17.0) | not attempted | 21691720 | fail: error: unable to find dynamic system library "resolv" using strategy paths_first. searched paths: none | fail: error: unable to find dynamic system library "resolv" using strategy paths_first. searched paths: none | — |
