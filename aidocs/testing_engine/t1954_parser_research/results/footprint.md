# Footprint (t1954_1)

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Probe binaries built `CGO_ENABLED=0 -trimpath -buildvcs=false` for the four release targets; each probe USES its library (a blank import lets dead-code elimination hide the cost). Δ is against the no-op probe. `pytokenize` has no Go-side footprint to measure: it needs a Python 3 interpreter at run time, which no release artefact ships. Rerun: `go run ./cmd/t1954 footprint`.

| probe | what | linux/amd64 | linux/arm64 | darwin/amd64 | darwin/arm64 | Δ vs no-op (linux/amd64) |
|---|---|---|---|---|---|---|
| noop | reference | 2021164 | 1989512 | 2162432 | 2080962 | +0 |
| baseline-annot | the landed annot package (current engine cost) | 4389891 | 4213657 | 4460592 | 4210626 | +2368727 |
| goscanner | go/scanner (standard library) | 2572226 | 2544230 | 2616576 | 2534354 | +551062 |
| shfmt | mvdan.cc/sh/v3/syntax | 3030737 | 2983014 | 3199328 | 3084498 | +1009573 |
| ait-testmap (snapshot) | the current engine binary, built from the pinned snapshot | 6329964 | 5963644 | 6322240 | 5917634 | +4308800 |
| pytokenize | Python tokenize + ast via a subprocess | n/a | n/a | n/a | n/a | runtime dependency: python3 |

The tree-sitter / tokenizer candidates' footprints are measured by the children that prototype them (t1954_2, t1954_3); `results/feasibility.md` has their compile-probe sizes.
