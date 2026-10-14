# Performance (t1954_4)

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Method (plan amendment A3): `taskset -c 0`; fastest of 3 fresh processes; **cold** = one timed first operation per fresh process, the timer started before provider construction (grammar/oracle start-up included, no benchmark calibration); **warm** = a separate process, an untimed warm-up, then `testing.Benchmark` (ns/op). "Cold" is a cold PROCESS and provider, not a cold page cache (the workload is written once beforehand). Peak RSS (KiB, Linux `ru_maxrss`): the measured process itself (`RUSAGE_SELF`), and separately its subprocesses (`RUSAGE_CHILDREN`: `git ls-files` inside the scan, the Python oracle for pytokenize). The subprocess figure is an UPPER BOUND, not the subprocess's own working set: a forked child's `ru_maxrss` includes the pages it shares with the parent at fork, which is why the scan rows show the same value twice. Rerun: `go run -tags 't1954cgo t1954wasm' ./cmd/t1954 bench --title t1954_4 --out results/t4/bench.md --aitasks <snap/aitasks> --siblings <name>=<snap>,… --subjects baseline,shfmt,pytokenize,native,gotreesitter,tscgo,tswasm,chroma,pygments,textmate,tsnative,ktpsi,antlr --lex-subjects baseline,goscanner,shfmt,pytokenize,gotreesitter,tscgo,tswasm,chroma,pygments,textmate,tsnative,ktpsi,antlr --labels 'tscgo=host-only'`.

## End-to-end scan — budget-comparable

The operation `annot.BenchmarkScan` times: `registry.Scan(ctx, dir, Inputs{Annotations: annot.Source{}, Lister: emptyLister}, false)` over the regenerated M2.2 bench shape (420 annotated tests, ¼ Python; 600 sources; 1,000 docs; a fresh git repository). A provider enters through `ClassifyHook` for its languages; the landed lexer handles the others (named per row). Budget: 300 ms (proposal *Engine binary identity and budget*); the landed `annot.BenchmarkScan` baseline is ≈21 ms (`goengines/bench/baseline.txt`).

| subject | languages via the subject | cold (fastest) | cold runs | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) | vs 300 ms budget |
|---|---|---|---|---|---|---|
| baseline | all (landed) | 24.7 ms | 24.8 ms, 24.7 ms, 25.1 ms | 26.9 ms | 46268 / 46268 | within (cold 0.1×, warm 0.1×) |
| shfmt | bash: shfmt; others: landed | 45.5 ms | 49.6 ms, 46.7 ms, 45.5 ms | 47.7 ms | 46564 / 46564 | within (cold 0.2×, warm 0.2×) |
| pytokenize | python: pytokenize; others: landed | 120.4 ms | 130.1 ms, 124.0 ms, 120.4 ms | 111.0 ms | 46136 / 46136 | within (cold 0.4×, warm 0.4×) |
| native | bash: shfmt, go: goscanner, python: pytokenize; others: landed | 138.3 ms | 139.2 ms, 138.3 ms, 142.2 ms | 132.8 ms | 46280 / 46280 | within (cold 0.5×, warm 0.4×) |
| gotreesitter | bash: gotreesitter, python: gotreesitter, go: gotreesitter, kotlin: gotreesitter, typescript: gotreesitter, tsx: gotreesitter, javascript: gotreesitter, java: gotreesitter, rust: gotreesitter, swift: gotreesitter; others: landed | 433.4 ms | 433.4 ms, 442.6 ms, 447.2 ms | 397.4 ms | 97484 / 97484 | OVER (cold 1.4×, warm 1.3×) |
| tscgo (host-only) | bash: tscgo, python: tscgo, go: tscgo, kotlin: tscgo, typescript: tscgo, tsx: tscgo, javascript: tscgo, java: tscgo, rust: tscgo, swift: tscgo; others: landed | 525.0 ms | 557.6 ms, 594.7 ms, 525.0 ms | 590.2 ms | 44280 / 44280 | OVER (cold 1.8×, warm 2.0×) |
| tswasm | bash: tswasm, python: tswasm, go: tswasm, kotlin: tswasm, typescript: tswasm, tsx: tswasm, javascript: tswasm, java: tswasm, rust: tswasm, swift: tswasm; others: landed | 1007.8 ms | 1014.9 ms, 1110.4 ms, 1007.8 ms | 438.3 ms | 372608 / 371012 | OVER (cold 3.4×, warm 1.5×) |
| chroma | bash: chroma, python: chroma, go: chroma, kotlin: chroma, typescript: chroma, tsx: chroma, javascript: chroma, java: chroma, rust: chroma, swift: chroma; others: landed | error: annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | not measured |
| pygments | bash: pygments, python: pygments, go: pygments, kotlin: pygments, typescript: pygments, tsx: pygments, javascript: pygments, java: pygments, rust: pygments, swift: pygments; others: landed | error: annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | not measured |
| textmate | bash: textmate, python: textmate, go: textmate, kotlin: textmate, typescript: textmate, tsx: textmate, javascript: textmate, java: textmate, rust: textmate, swift: textmate; others: landed | error: annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | annotations: tests/test_0.py:1: cannot determine comment context: provider: unsupported:DocLiterals | | not measured |
| tsnative | typescript: tsnative, tsx: tsnative, javascript: tsnative; others: landed | 50.9 ms | 58.1 ms, 50.9 ms, 53.1 ms | 28.7 ms | 287016 / 62780 | within (cold 0.2×, warm 0.1×) |
| ktpsi | kotlin: ktpsi; others: landed | 402.3 ms | 437.6 ms, 422.8 ms, 402.3 ms | 25.9 ms | 287016 / 64892 | OVER (cold 1.3×, warm 0.1×) |
| antlr | kotlin: antlr, java: antlr, rust: antlr; others: landed | 27.8 ms | 32.5 ms, 27.8 ms, 27.9 ms | 27.3 ms | 287016 / 50188 | within (cold 0.1×, warm 0.1×) |

## Lexical only — NOT comparable to the scan budget

Analyze + ToContext (or the landed `annot.Classify`) over preloaded bytes; files read before the timer starts. A subject is timed only on the files of its own languages.

| set | subject | files | cold (fastest) | warm (ns/op, fastest) | peak RSS KiB (process / subprocesses) |
|---|---|---|---|---|---|
| M2.2 shape tests (420) | baseline | 420 | 6.0 ms | 6.2 ms | 289100 / 0 |
| M2.2 shape tests (420) | shfmt | 315 | 24.9 ms | 25.1 ms | 289100 / 0 |
| M2.2 shape tests (420) | pytokenize | 105 | 95.1 ms | 81.3 ms | 289100 / 25408 |
| M2.2 shape tests (420) | gotreesitter | 420 | 397.2 ms | 357.1 ms | 291200 / 0 |
| M2.2 shape tests (420) | tscgo (host-only) | 420 | 510.0 ms | 500.0 ms | 291200 / 0 |
| M2.2 shape tests (420) | tswasm | 420 | 932.7 ms | 430.9 ms | 355928 / 0 |
| M2.2 shape tests (420) | chroma | 420 | 854.7 ms | 893.6 ms | 338508 / 0 |
| M2.2 shape tests (420) | pygments | 420 | 976.4 ms | 941.0 ms | 338508 / 25508 |
| M2.2 shape tests (420) | textmate | 420 | 1826.2 ms | 1569.5 ms | 338508 / 81372 |
| aitasks@7f1d0614a333 test files | baseline | 855 | 60.5 ms | 54.9 ms | 338508 / 0 |
| aitasks@7f1d0614a333 test files | goscanner | 63 | 4.5 ms | 4.5 ms | 338508 / 0 |
| aitasks@7f1d0614a333 test files | shfmt | 436 | 116.9 ms | 123.9 ms | 338508 / 0 |
| aitasks@7f1d0614a333 test files | pytokenize | 356 | 2561.1 ms | 2503.5 ms | 338508 / 25496 |
| aitasks@7f1d0614a333 test files | gotreesitter | 855 | 3262.7 ms | 3154.3 ms | 338508 / 0 |
| aitasks@7f1d0614a333 test files | tscgo (host-only) | 855 | 3667.6 ms | 3594.9 ms | 338508 / 0 |
| aitasks@7f1d0614a333 test files | tswasm | 855 | 4153.7 ms | 3451.1 ms | 458788 / 0 |
| aitasks@7f1d0614a333 test files | chroma | 855 | 8811.5 ms | 9035.4 ms | 364504 / 0 |
| aitasks@7f1d0614a333 test files | pygments | 855 | 9901.4 ms | 9912.0 ms | 364696 / 25520 |
| aitasks@7f1d0614a333 test files | textmate | 855 | 13071.4 ms | 12512.2 ms | 364696 / 81424 |
| aitasks_go@e0e3862be98a test files | baseline | 55 | 3.4 ms | 3.8 ms | 364696 / 0 |
| aitasks_go@e0e3862be98a test files | goscanner | 55 | 3.2 ms | 3.4 ms | 364696 / 0 |
| aitasks_go@e0e3862be98a test files | gotreesitter | 55 | 275.7 ms | 271.0 ms | 364696 / 0 |
| aitasks_go@e0e3862be98a test files | tscgo (host-only) | 55 | 128.9 ms | 129.7 ms | 364696 / 0 |
| aitasks_go@e0e3862be98a test files | tswasm | 55 | 641.9 ms | 107.8 ms | 364696 / 0 |
| aitasks_go@e0e3862be98a test files | chroma | 55 | 338.2 ms | 327.9 ms | 424748 / 0 |
| aitasks_go@e0e3862be98a test files | pygments | 55 | 319.7 ms | 308.8 ms | 424748 / 25488 |
| aitasks_go@e0e3862be98a test files | textmate | 55 | 867.1 ms | 556.3 ms | 424748 / 81396 |
| aitasks_mobile@75f4543fb70e test files | baseline | 37 | 0.6 ms | 0.7 ms | 424748 / 0 |
| aitasks_mobile@75f4543fb70e test files | gotreesitter | 37 | 117.8 ms | 57.9 ms | 424748 / 0 |
| aitasks_mobile@75f4543fb70e test files | tscgo (host-only) | 37 | 89.5 ms | 89.7 ms | 424748 / 0 |
| aitasks_mobile@75f4543fb70e test files | tswasm | 37 | 624.0 ms | 68.0 ms | 424748 / 0 |
| aitasks_mobile@75f4543fb70e test files | chroma | 37 | 115.5 ms | 115.6 ms | 455276 / 0 |
| aitasks_mobile@75f4543fb70e test files | pygments | 37 | 202.9 ms | 167.0 ms | 455276 / 23820 |
| aitasks_mobile@75f4543fb70e test files | textmate | 37 | 304.5 ms | 118.2 ms | 455276 / 77824 |
| aitasks_mobile@75f4543fb70e test files | ktpsi | 37 | 932.4 ms | 181.5 ms | 455468 / 108368 |
| aitasks_mobile@75f4543fb70e test files | antlr | 37 | 34.6 ms | 20.8 ms | 455660 / 0 |
| thinking_app@33b7fcd4923d test files | baseline | 397 | 10.4 ms | 9.3 ms | 456044 / 0 |
| thinking_app@33b7fcd4923d test files | pytokenize | 1 | 17.9 ms | 4.4 ms | 456812 / 23688 |
| thinking_app@33b7fcd4923d test files | gotreesitter | 397 | 2146.3 ms | 2050.4 ms | 459260 / 0 |
| thinking_app@33b7fcd4923d test files | tscgo (host-only) | 397 | 1006.3 ms | 994.0 ms | 459260 / 0 |
| thinking_app@33b7fcd4923d test files | tswasm | 397 | 1342.4 ms | 815.8 ms | 459452 / 0 |
| thinking_app@33b7fcd4923d test files | chroma | 397 | 1063.0 ms | 1063.4 ms | 540824 / 0 |
| thinking_app@33b7fcd4923d test files | pygments | 397 | 1692.9 ms | 1706.7 ms | 541016 / 22136 |
| thinking_app@33b7fcd4923d test files | textmate | 397 | 1585.3 ms | 1382.4 ms | 541208 / 81260 |
| thinking_app@33b7fcd4923d test files | ktpsi | 396 | 2723.9 ms | 1170.8 ms | 541208 / 109780 |
| thinking_app@33b7fcd4923d test files | antlr | 396 | 269.9 ms | 243.5 ms | 541208 / 0 |
| thinking_backend@e9a371524f4b test files | baseline | 51 | 2.9 ms | 3.1 ms | 541208 / 0 |
| thinking_backend@e9a371524f4b test files | shfmt | 25 | 9.5 ms | 9.6 ms | 541208 / 0 |
| thinking_backend@e9a371524f4b test files | pytokenize | 26 | 141.1 ms | 117.1 ms | 541208 / 22128 |
| thinking_backend@e9a371524f4b test files | gotreesitter | 51 | 358.8 ms | 311.5 ms | 541208 / 0 |
| thinking_backend@e9a371524f4b test files | tscgo (host-only) | 51 | 210.3 ms | 212.6 ms | 541208 / 0 |
| thinking_backend@e9a371524f4b test files | tswasm | 51 | 696.1 ms | 187.7 ms | 541400 / 0 |
| thinking_backend@e9a371524f4b test files | chroma | 51 | 549.5 ms | 558.8 ms | 564824 / 0 |
| thinking_backend@e9a371524f4b test files | pygments | 51 | 578.2 ms | 553.1 ms | 564824 / 22132 |
| thinking_backend@e9a371524f4b test files | textmate | 51 | 1155.9 ms | 820.7 ms | 564824 / 77704 |
| timexchange@c60e7e05a465 test files | baseline | 20 | 0.1 ms | 0.0 ms | 564824 / 0 |
| timexchange@c60e7e05a465 test files | gotreesitter | 20 | 64.9 ms | 4.4 ms | 564824 / 0 |
| timexchange@c60e7e05a465 test files | tscgo (host-only) | 20 | 5.2 ms | 5.2 ms | 564824 / 0 |
| timexchange@c60e7e05a465 test files | tswasm | 20 | 532.2 ms | 4.4 ms | 564824 / 0 |
| timexchange@c60e7e05a465 test files | chroma | 20 | 6.1 ms | 5.4 ms | 825228 / 0 |
| timexchange@c60e7e05a465 test files | pygments | 20 | 41.6 ms | 8.0 ms | 825420 / 22068 |
| timexchange@c60e7e05a465 test files | textmate | 20 | 136.1 ms | 6.9 ms | 825804 / 77564 |
| timexchange@c60e7e05a465 test files | ktpsi | 20 | 528.1 ms | 15.6 ms | 826380 / 108416 |
| timexchange@c60e7e05a465 test files | antlr | 20 | 7.8 ms | 1.2 ms | 826764 / 0 |

## Provider start-up detail — supplementary, not budget evidence

- tswasm: wasm 16618675 bytes; wazero compile 457.7 ms, instantiate 2.7 ms (one construction in the parent process)
