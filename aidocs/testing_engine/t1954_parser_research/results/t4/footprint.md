# Footprint (t1954_1)

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Probe binaries built `CGO_ENABLED=0 -trimpath -buildvcs=false` for the four release targets; each probe USES its library (a blank import lets dead-code elimination hide the cost). Δ is against the no-op probe. `pytokenize` has no Go-side footprint to measure: it needs a Python 3 interpreter at run time, which no release artefact ships. Rerun: `go run ./cmd/t1954 footprint`.

| probe | what | linux/amd64 | linux/arm64 | darwin/amd64 | darwin/arm64 | Δ vs no-op (linux/amd64) |
|---|---|---|---|---|---|---|
| noop | reference | 2021164 | 1989512 | 2162432 | 2080962 | +0 |
| baseline-annot | the landed annot package (current engine cost) | 4390907 | 4214409 | 4460640 | 4210674 | +2369743 |
| goscanner | go/scanner (standard library) | 2572186 | 2544230 | 2616576 | 2534354 | +551022 |
| shfmt | mvdan.cc/sh/v3/syntax | 3030737 | 2983014 | 3199328 | 3084498 | +1009573 |
| ait-testmap (snapshot) | the current engine binary, built from the pinned snapshot | 8092059 | 7419531 | 8121600 | 7532898 | +6070895 |
| pytokenize | Python tokenize + ast via a subprocess | n/a | n/a | n/a | n/a | runtime dependency: python3 |

The tree-sitter / tokenizer candidates' footprints are measured by the children that prototype them (t1954_2, t1954_3); `results/feasibility.md` has their compile-probe sizes.
