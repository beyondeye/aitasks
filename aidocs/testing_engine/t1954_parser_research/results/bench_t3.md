# Performance (t1954_3)

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Method (plan amendment A3): `taskset -c 0`; fastest of 3 fresh processes; **cold** = one timed first operation per fresh process, the timer started before provider construction (grammar/oracle start-up included, no benchmark calibration); **warm** = a separate process, an untimed warm-up, then `testing.Benchmark` (ns/op). "Cold" is a cold PROCESS and provider, not a cold page cache (the workload is written once beforehand). Peak RSS (KiB, Linux `ru_maxrss`): the measured process itself (`RUSAGE_SELF`), and separately its subprocesses (`RUSAGE_CHILDREN`: `git ls-files` inside the scan, the Python oracle for pytokenize). The subprocess figure is an UPPER BOUND, not the subprocess's own working set: a forked child's `ru_maxrss` includes the pages it shares with the parent at fork, which is why the scan rows show the same value twice. Rerun: `go run ./cmd/t1954 bench --title t1954_3 --subjects baseline,chroma,pygments,textmate --lex-subjects baseline,chroma,pygments,textmate,tsnative,ktpsi,antlr --labels '<as in this file>' --out results/bench_t3.md`.

## End-to-end scan — budget-comparable

The operation `annot.BenchmarkScan` times: `registry.Scan(ctx, dir, Inputs{Annotations: annot.Source{}, Lister: emptyLister}, false)` over the regenerated M2.2 bench shape (420 annotated tests, ¼ Python; 600 sources; 1,000 docs; a fresh git repository). A provider enters through `ClassifyHook` for its languages; the landed lexer handles the others (named per row). Budget: 300 ms (proposal *Engine binary identity and budget*); the landed `annot.BenchmarkScan` baseline is ≈21 ms (`goengines/bench/baseline.txt`).

| subject | languages via the subject | cold (fastest) | cold runs | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) | vs 300 ms budget |
|---|---|---|---|---|---|---|
| baseline | all (landed) | 28.5 ms | 28.5 ms, 30.4 ms, 28.6 ms | 28.2 ms | 44496 / 44496 | within (cold 0.1×, warm 0.1×) |
| chroma | bash: chroma, python: chroma, go: chroma, kotlin: chroma, typescript: chroma, tsx: chroma, javascript: chroma, java: chroma, rust: chroma, swift: chroma; others: landed | error: annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | not measured |
| pygments (subprocess: CPython) | bash: pygments, python: pygments, go: pygments, kotlin: pygments, typescript: pygments, tsx: pygments, javascript: pygments, java: pygments, rust: pygments, swift: pygments; others: landed | error: annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | not measured |
| textmate (subprocess: Node.js) | bash: textmate, python: textmate, go: textmate, kotlin: textmate, typescript: textmate, tsx: textmate, javascript: textmate, java: textmate, rust: textmate, swift: textmate; others: landed | error: annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | not measured |

## Lexical only — NOT comparable to the scan budget

Analyze + ToContext (or the landed `annot.Classify`) over preloaded bytes; files read before the timer starts. A subject is timed only on the files of its own languages.

| set | subject | files | cold (fastest) | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) |
|---|---|---|---|---|---|
| M2.2 shape tests (420) | baseline | 420 | 6.1 ms | 6.1 ms | 28744 / 0 |
| M2.2 shape tests (420) | chroma | 420 | 866.2 ms | 866.5 ms | 33824 / 0 |
| M2.2 shape tests (420) | pygments (subprocess: CPython) | 420 | 908.9 ms | 927.4 ms | 29324 / 23812 |
| M2.2 shape tests (420) | textmate (subprocess: Node.js) | 420 | 1882.7 ms | 1523.5 ms | 30204 / 77604 |
| aitasks test files | baseline | 839 | 54.2 ms | 51.8 ms | 63780 / 0 |
| aitasks test files | chroma | 839 | 8444.7 ms | 8931.6 ms | 101592 / 0 |
| aitasks test files | pygments (subprocess: CPython) | 839 | 9547.9 ms | 9385.2 ms | 99224 / 25300 |
| aitasks test files | textmate (subprocess: Node.js) | 839 | 13174.9 ms | 11929.7 ms | 91936 / 81356 |
| aitasks_go test files | baseline | 55 | 3.3 ms | 3.8 ms | 31756 / 0 |
| aitasks_go test files | chroma | 55 | 332.5 ms | 327.3 ms | 61060 / 0 |
| aitasks_go test files | pygments (subprocess: CPython) | 55 | 323.5 ms | 305.4 ms | 33152 / 25264 |
| aitasks_go test files | textmate (subprocess: Node.js) | 55 | 849.2 ms | 554.2 ms | 33572 / 81448 |
| aitasks_mobile test files | baseline | 37 | 0.6 ms | 0.7 ms | 33320 / 0 |
| aitasks_mobile test files | chroma | 37 | 116.9 ms | 120.3 ms | 33512 / 0 |
| aitasks_mobile test files | pygments (subprocess: CPython) | 37 | 209.8 ms | 167.1 ms | 33512 / 21752 |
| aitasks_mobile test files | textmate (subprocess: Node.js) | 37 | 295.8 ms | 126.2 ms | 33512 / 77764 |
| aitasks_mobile test files | ktpsi (subprocess: JVM) | 37 | 923.1 ms | 195.1 ms | 33512 / 108672 |
| aitasks_mobile test files | antlr | 37 | 35.6 ms | 21.5 ms | 44128 / 0 |
| thinking_app test files | baseline | 397 | 11.1 ms | 9.6 ms | 41896 / 0 |
| thinking_app test files | chroma | 397 | 1064.4 ms | 1093.8 ms | 69348 / 0 |
| thinking_app test files | pygments (subprocess: CPython) | 397 | 1807.7 ms | 1650.8 ms | 43340 / 23436 |
| thinking_app test files | textmate (subprocess: Node.js) | 397 | 1652.2 ms | 1343.1 ms | 41848 / 77644 |
| thinking_app test files | ktpsi (subprocess: JVM) | 396 | 2671.3 ms | 1330.6 ms | 36380 / 117260 |
| thinking_app test files | antlr | 396 | 258.9 ms | 239.6 ms | 55252 / 0 |
| thinking_backend test files | baseline | 51 | 3.0 ms | 3.1 ms | 38168 / 0 |
| thinking_backend test files | chroma | 51 | 546.4 ms | 544.1 ms | 42176 / 0 |
| thinking_backend test files | pygments (subprocess: CPython) | 51 | 600.2 ms | 560.7 ms | 39516 / 25372 |
| thinking_backend test files | textmate (subprocess: Node.js) | 51 | 1115.2 ms | 828.1 ms | 39452 / 81304 |
| timexchange test files | baseline | 20 | 0.1 ms | 0.1 ms | 42296 / 0 |
| timexchange test files | chroma | 20 | 5.9 ms | 5.5 ms | 42296 / 0 |
| timexchange test files | pygments (subprocess: CPython) | 20 | 43.1 ms | 8.3 ms | 42296 / 25316 |
| timexchange test files | textmate (subprocess: Node.js) | 20 | 137.5 ms | 7.4 ms | 42296 / 81336 |
| timexchange test files | ktpsi (subprocess: JVM) | 20 | 540.8 ms | 15.6 ms | 44304 / 118960 |
| timexchange test files | antlr | 20 | 7.0 ms | 1.2 ms | 46544 / 0 |
