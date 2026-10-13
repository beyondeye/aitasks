# Performance (t1954_1)

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Method (plan amendment A3): `taskset -c 0`; fastest of 3 fresh processes; **cold** = one timed first operation per fresh process, the timer started before provider construction (grammar/oracle start-up included, no benchmark calibration); **warm** = a separate process, an untimed warm-up, then `testing.Benchmark` (ns/op). "Cold" is a cold PROCESS and provider, not a cold page cache (the workload is written once beforehand). Peak RSS (KiB, Linux `ru_maxrss`): the measured process itself (`RUSAGE_SELF`), and separately its subprocesses (`RUSAGE_CHILDREN`: `git ls-files` inside the scan, the Python oracle for pytokenize). The subprocess figure is an UPPER BOUND, not the subprocess's own working set: a forked child's `ru_maxrss` includes the pages it shares with the parent at fork, which is why the scan rows show the same value twice. Rerun: `go run ./cmd/t1954 bench`.

## End-to-end scan — budget-comparable

The operation `annot.BenchmarkScan` times: `registry.Scan(ctx, dir, Inputs{Annotations: annot.Source{}, Lister: emptyLister}, false)` over the regenerated M2.2 bench shape (420 annotated tests, ¼ Python; 600 sources; 1,000 docs; a fresh git repository). A provider enters through `ClassifyHook` for its languages; the landed lexer handles the others (named per row). Budget: 300 ms (proposal *Engine binary identity and budget*); the landed `annot.BenchmarkScan` baseline is ≈21 ms (`goengines/bench/baseline.txt`).

| subject | languages via the subject | cold (fastest) | cold runs | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) | vs 300 ms budget |
|---|---|---|---|---|---|---|
| baseline | all (landed) | 23.8 ms | 24.4 ms, 24.5 ms, 23.8 ms | 26.6 ms | 37672 / 37672 | within (cold 0.1×, warm 0.1×) |
| pytokenize | python: pytokenize; others: landed | 131.5 ms | 131.5 ms, 132.9 ms, 131.6 ms | 124.4 ms | 28164 / 27292 | within (cold 0.4×, warm 0.4×) |
| shfmt | bash: shfmt; others: landed | 49.4 ms | 49.6 ms, 49.4 ms, 49.7 ms | 47.4 ms | 33624 / 33624 | within (cold 0.2×, warm 0.2×) |
| native | bash: shfmt, go: goscanner, python: pytokenize; others: landed | 150.6 ms | 153.5 ms, 150.6 ms, 153.7 ms | 137.9 ms | 35740 / 35740 | within (cold 0.5×, warm 0.5×) |

## Lexical only — NOT comparable to the scan budget

Analyze + ToContext (or the landed `annot.Classify`) over preloaded bytes; files read before the timer starts. A subject is timed only on the files of its own languages.

| set | subject | files | cold (fastest) | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) |
|---|---|---|---|---|---|
| M2.2 shape tests (420) | baseline | 420 | 6.3 ms | 6.1 ms | 18472 / 0 |
| M2.2 shape tests (420) | pytokenize | 105 | 98.3 ms | 82.5 ms | 15580 / 12612 |
| M2.2 shape tests (420) | shfmt | 315 | 22.3 ms | 22.6 ms | 17608 / 0 |
| aitasks test files | baseline | 828 | 59.1 ms | 58.2 ms | 46748 / 0 |
| aitasks test files | goscanner | 45 | 2.8 ms | 2.8 ms | 17608 / 0 |
| aitasks test files | pytokenize | 350 | 2379.3 ms | 2422.1 ms | 29428 / 12612 |
| aitasks test files | shfmt | 433 | 118.2 ms | 114.3 ms | 34736 / 0 |
| aitasks_go test files | baseline | 55 | 4.0 ms | 4.0 ms | 17608 / 0 |
| aitasks_go test files | goscanner | 55 | 3.4 ms | 3.3 ms | 17608 / 0 |
| aitasks_mobile test files | baseline | 37 | 0.7 ms | 0.6 ms | 17608 / 0 |
| thinking_app test files | baseline | 397 | 12.1 ms | 10.2 ms | 19348 / 0 |
| thinking_app test files | pytokenize | 1 | 24.2 ms | 4.7 ms | 17608 / 12612 |
| thinking_backend test files | baseline | 49 | 3.4 ms | 3.3 ms | 19908 / 0 |
| thinking_backend test files | pytokenize | 24 | 134.6 ms | 115.9 ms | 20100 / 12612 |
| thinking_backend test files | shfmt | 25 | 9.1 ms | 9.3 ms | 27704 / 0 |
| timexchange test files | baseline | 20 | 0.1 ms | 0.0 ms | 20100 / 0 |
