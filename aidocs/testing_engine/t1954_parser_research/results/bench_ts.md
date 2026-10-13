# Performance (t1954_2)

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Method (plan amendment A3): `taskset -c 0`; fastest of 3 fresh processes; **cold** = one timed first operation per fresh process, the timer started before provider construction (grammar/oracle start-up included, no benchmark calibration); **warm** = a separate process, an untimed warm-up, then `testing.Benchmark` (ns/op). "Cold" is a cold PROCESS and provider, not a cold page cache (the workload is written once beforehand). Peak RSS (KiB, Linux `ru_maxrss`): the measured process itself (`RUSAGE_SELF`), and separately its subprocesses (`RUSAGE_CHILDREN`: `git ls-files` inside the scan, the Python oracle for pytokenize). The subprocess figure is an UPPER BOUND, not the subprocess's own working set: a forked child's `ru_maxrss` includes the pages it shares with the parent at fork, which is why the scan rows show the same value twice. Rerun: `go run -tags 't1954cgo t1954wasm' ./cmd/t1954 bench --title t1954_2 --subjects baseline,gotreesitter,tscgo,tswasm --lex-subjects baseline,gotreesitter,tscgo,tswasm --labels '<as in this file>' --out results/bench_ts.md`.

## End-to-end scan — budget-comparable

The operation `annot.BenchmarkScan` times: `registry.Scan(ctx, dir, Inputs{Annotations: annot.Source{}, Lister: emptyLister}, false)` over the regenerated M2.2 bench shape (420 annotated tests, ¼ Python; 600 sources; 1,000 docs; a fresh git repository). A provider enters through `ClassifyHook` for its languages; the landed lexer handles the others (named per row). Budget: 300 ms (proposal *Engine binary identity and budget*); the landed `annot.BenchmarkScan` baseline is ≈21 ms (`goengines/bench/baseline.txt`).

| subject | languages via the subject | cold (fastest) | cold runs | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) | vs 300 ms budget |
|---|---|---|---|---|---|---|
| baseline (same-run control) | all (landed) | 23.8 ms | 23.8 ms, 24.2 ms, 24.0 ms | 24.7 ms | 36824 / 36824 | within (cold 0.1×, warm 0.1×) |
| gotreesitter | bash: gotreesitter, python: gotreesitter, go: gotreesitter, kotlin: gotreesitter, typescript: gotreesitter, tsx: gotreesitter, javascript: gotreesitter, java: gotreesitter, rust: gotreesitter, swift: gotreesitter; others: landed | 384.5 ms | 399.1 ms, 388.0 ms, 384.5 ms | 366.8 ms | 90916 / 90772 | OVER (cold 1.3×, warm 1.2×) |
| tscgo (host-only: cgo, not buildable for the release targets) | bash: tscgo, python: tscgo, go: tscgo, kotlin: tscgo, typescript: tscgo, tsx: tscgo, javascript: tscgo, java: tscgo, rust: tscgo, swift: tscgo; others: landed | 497.7 ms | 502.5 ms, 501.2 ms, 497.7 ms | 495.6 ms | 36528 / 34620 | OVER (cold 1.7×, warm 1.7×) |
| tswasm | bash: tswasm, python: tswasm, go: tswasm, kotlin: tswasm, typescript: tswasm, tsx: tswasm, javascript: tswasm, java: tswasm, rust: tswasm, swift: tswasm; others: landed | 907.0 ms | 924.4 ms, 928.7 ms, 907.0 ms | 402.2 ms | 363364 / 344656 | OVER (cold 3.0×, warm 1.3×) |

## Lexical only — NOT comparable to the scan budget

Analyze + ToContext (or the landed `annot.Classify`) over preloaded bytes; files read before the timer starts. A subject is timed only on the files of its own languages.

| set | subject | files | cold (fastest) | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) |
|---|---|---|---|---|---|
| M2.2 shape tests (420) | baseline (same-run control) | 420 | 5.4 ms | 5.7 ms | 274780 / 0 |
| M2.2 shape tests (420) | gotreesitter | 420 | 366.9 ms | 348.9 ms | 274972 / 0 |
| M2.2 shape tests (420) | tscgo (host-only: cgo, not buildable for the release targets) | 420 | 466.7 ms | 467.4 ms | 274972 / 0 |
| M2.2 shape tests (420) | tswasm | 420 | 897.1 ms | 378.2 ms | 353768 / 0 |
| aitasks test files | baseline (same-run control) | 835 | 50.2 ms | 49.8 ms | 309060 / 0 |
| aitasks test files | gotreesitter | 835 | 2542.6 ms | 2497.7 ms | 309252 / 0 |
| aitasks test files | tscgo (host-only: cgo, not buildable for the release targets) | 835 | 2988.5 ms | 2979.7 ms | 309636 / 0 |
| aitasks test files | tswasm | 835 | 3306.9 ms | 2786.8 ms | 412140 / 0 |
| aitasks_go test files | baseline (same-run control) | 55 | 3.4 ms | 3.6 ms | 506964 / 0 |
| aitasks_go test files | gotreesitter | 55 | 267.0 ms | 249.2 ms | 507156 / 0 |
| aitasks_go test files | tscgo (host-only: cgo, not buildable for the release targets) | 55 | 123.9 ms | 123.0 ms | 507156 / 0 |
| aitasks_go test files | tswasm | 55 | 585.2 ms | 106.1 ms | 507156 / 0 |
| aitasks_mobile test files | baseline (same-run control) | 37 | 0.6 ms | 0.7 ms | 508116 / 0 |
| aitasks_mobile test files | gotreesitter | 37 | 101.2 ms | 52.9 ms | 508116 / 0 |
| aitasks_mobile test files | tscgo (host-only: cgo, not buildable for the release targets) | 37 | 86.7 ms | 86.9 ms | 508116 / 0 |
| aitasks_mobile test files | tswasm | 37 | 565.3 ms | 65.6 ms | 508116 / 0 |
| thinking_app test files | baseline (same-run control) | 397 | 9.3 ms | 9.0 ms | 508116 / 0 |
| thinking_app test files | gotreesitter | 397 | 2005.1 ms | 1910.8 ms | 508116 / 0 |
| thinking_app test files | tscgo (host-only: cgo, not buildable for the release targets) | 397 | 954.6 ms | 967.6 ms | 508116 / 0 |
| thinking_app test files | tswasm | 397 | 1310.9 ms | 795.5 ms | 508116 / 0 |
| thinking_backend test files | baseline (same-run control) | 49 | 2.7 ms | 2.9 ms | 508116 / 0 |
| thinking_backend test files | gotreesitter | 49 | 324.0 ms | 285.2 ms | 508116 / 0 |
| thinking_backend test files | tscgo (host-only: cgo, not buildable for the release targets) | 49 | 193.1 ms | 196.2 ms | 508116 / 0 |
| thinking_backend test files | tswasm | 49 | 688.1 ms | 172.4 ms | 508116 / 0 |
| timexchange test files | baseline (same-run control) | 20 | 0.0 ms | 0.0 ms | 768384 / 0 |
| timexchange test files | gotreesitter | 20 | 55.8 ms | 4.2 ms | 768384 / 0 |
| timexchange test files | tscgo (host-only: cgo, not buildable for the release targets) | 20 | 5.1 ms | 4.9 ms | 768384 / 0 |
| timexchange test files | tswasm | 20 | 516.0 ms | 4.1 ms | 768384 / 0 |

## Provider start-up detail — supplementary, not budget evidence

- tswasm: wasm 16618675 bytes; wazero compile 412.8 ms, instantiate 2.4 ms (one construction in the parent process)
