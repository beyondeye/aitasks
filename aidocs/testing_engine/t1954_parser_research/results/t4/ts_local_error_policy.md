# Local-error refusal policy — an alternative (t1954_2)

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

The harness and M2.2 refuse a file **as a whole** when the provider reports any diagnostic (D9); the matrices score that policy. This report scores the alternative: refuse only the lines a diagnostic spans, plus one line on each side, and keep the provider's class elsewhere. **FP-writable (local)**: look-alike or read-only lines (`x-policy` lines excluded) that would be classed Comment outside the refused zone. Each one is a write the whole-file policy prevents. **Writable kept / lost**: the fixture's writable lines that stay writable, or are lost to the zone or to the class. Whole-file refusal keeps none of these lines and has 0 FP-writable by construction. Only files on which the provider reports a diagnostic are counted. Rerun: `go run ./cmd/t1954 localpolicy --provider <p,…>`.

| provider | lang | files with diagnostics | FP-writable (local) | writable kept / lost |
|---|---|---|---|---|
| gotreesitter | bash | 20 | 1 | 1 / 5 |
| gotreesitter | python | 5 | 0 | 1 / 0 |
| gotreesitter | go | 4 | 0 | 0 / 1 |
| gotreesitter | kotlin | 2 | 0 | 0 / 0 |
| gotreesitter | typescript | 2 | 0 | 0 / 0 |
| gotreesitter | java | 3 | 0 | 0 / 1 |
| gotreesitter | rust | 2 | 0 | 0 / 0 |
| gotreesitter | swift | 2 | 0 | 0 / 1 |
| tscgo | bash | 18 | 1 | 1 / 5 |
| tscgo | python | 5 | 0 | 1 / 0 |
| tscgo | go | 4 | 0 | 0 / 1 |
| tscgo | kotlin | 3 | 0 | 0 / 0 |
| tscgo | typescript | 2 | 0 | 0 / 0 |
| tscgo | java | 3 | 0 | 0 / 1 |
| tscgo | rust | 2 | 0 | 0 / 0 |
| tscgo | swift | 2 | 0 | 1 / 0 |
| tswasm | bash | 18 | 1 | 1 / 5 |
| tswasm | python | 5 | 0 | 1 / 0 |
| tswasm | go | 4 | 0 | 0 / 1 |
| tswasm | kotlin | 3 | 0 | 0 / 0 |
| tswasm | typescript | 2 | 0 | 0 / 0 |
| tswasm | java | 3 | 0 | 0 / 1 |
| tswasm | rust | 2 | 0 | 0 / 0 |
| tswasm | swift | 2 | 0 | 1 / 0 |
| shfmt | bash | 14 | 0 | 0 / 3 |
| pytokenize | python | 5 | 0 | 0 / 1 |
| goscanner | go | 3 | 0 | 0 / 0 |

## FP-writable lines under the local policy

- gotreesitter bash/lex_two_heredocs.sh: line 4 (look-alike/read-only) writable under the local policy
- tscgo bash/lex_two_heredocs.sh: line 4 (look-alike/read-only) writable under the local policy
- tswasm bash/lex_two_heredocs.sh: line 4 (look-alike/read-only) writable under the local policy
