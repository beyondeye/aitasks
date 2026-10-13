# Matrix: all subjects

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Per-subject detail: `matrix_<subject>.md`. Columns as there; safety columns first.

| subject | lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | bash | 66 | 66 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 3 | 0 | 0 | 0 | n/a — not exposed | 18 / 7 / 0 / 0 |
| baseline | python | 61 | 61 | 0 | 0 | 0 | 3 | 0 | 0 | 1 | 0 | 1 | 1 | 2 | n/a — not exposed | 14 / 27 / 0 / 0 |
| baseline | go | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 7 / 2 / 0 / 0 |
| baseline | kotlin | 25 | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 9 / 1 / 0 / 0 |
| baseline | typescript | 12 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| baseline | java | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| baseline | rust | 9 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| baseline | swift | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | bash | 66 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | python | 61 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | go | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 pass / 0 fail | 7 / 2 / 0 / 0 |
| goscanner | kotlin | 25 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | typescript | 12 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | java | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | rust | 9 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | swift | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| gotreesitter | bash | 66 | 66 | 4 | 0 | 0 | 0 | 0 | 2 | 7 | 12 | 0 | 0 | 0 | 61 pass / 5 fail | 17 / 8 / 0 / 0 |
| gotreesitter | python | 61 | 61 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 59 pass / 2 fail | 13 / 28 / 0 / 0 |
| gotreesitter | go | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 19 pass / 1 fail | 7 / 2 / 0 / 0 |
| gotreesitter | kotlin | 25 | 25 | 2 | 0 | 2 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 25 pass / 0 fail | 9 / 1 / 0 / 0 |
| gotreesitter | typescript | 12 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 pass / 3 fail | 6 / 3 / 0 / 0 |
| gotreesitter | java | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 10 pass / 0 fail | 4 / 1 / 0 / 0 |
| gotreesitter | rust | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 pass / 0 fail | 4 / 1 / 0 / 0 |
| gotreesitter | swift | 10 | 10 | 2 | 0 | 1 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 10 pass / 0 fail | 4 / 0 / 0 / 0 |
| pytokenize | bash | 66 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | python | 61 | 61 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 61 pass / 0 fail | 13 / 28 / 0 / 0 |
| pytokenize | go | 20 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | kotlin | 25 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | typescript | 12 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | java | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | rust | 9 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | swift | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | bash | 66 | 66 | 2 | 0 | 1 | 0 | 0 | 0 | 6 | 8 | 0 | 0 | 0 | 66 pass / 0 fail | 17 / 8 / 0 / 0 |
| shfmt | python | 61 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | go | 20 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | kotlin | 25 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | typescript | 12 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | java | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | rust | 9 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | swift | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| tscgo | bash | 66 | 66 | 4 | 0 | 0 | 0 | 0 | 2 | 7 | 10 | 0 | 0 | 0 | 61 pass / 5 fail | 17 / 8 / 0 / 0 |
| tscgo | python | 61 | 61 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 59 pass / 2 fail | 13 / 28 / 0 / 0 |
| tscgo | go | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 19 pass / 1 fail | 7 / 2 / 0 / 0 |
| tscgo | kotlin | 25 | 25 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 25 pass / 0 fail | 9 / 1 / 0 / 0 |
| tscgo | typescript | 12 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 pass / 3 fail | 6 / 3 / 0 / 0 |
| tscgo | java | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 10 pass / 0 fail | 4 / 1 / 0 / 0 |
| tscgo | rust | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 pass / 0 fail | 4 / 1 / 0 / 0 |
| tscgo | swift | 10 | 10 | 2 | 0 | 1 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 10 pass / 0 fail | 4 / 0 / 0 / 0 |
| tswasm | bash | 66 | 66 | 4 | 0 | 0 | 0 | 0 | 2 | 7 | 10 | 0 | 0 | 0 | 61 pass / 5 fail | 17 / 8 / 0 / 0 |
| tswasm | python | 61 | 61 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 59 pass / 2 fail | 13 / 28 / 0 / 0 |
| tswasm | go | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 19 pass / 1 fail | 7 / 2 / 0 / 0 |
| tswasm | kotlin | 25 | 25 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 25 pass / 0 fail | 9 / 1 / 0 / 0 |
| tswasm | typescript | 12 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 pass / 3 fail | 6 / 3 / 0 / 0 |
| tswasm | java | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 10 pass / 0 fail | 4 / 1 / 0 / 0 |
| tswasm | rust | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 pass / 0 fail | 4 / 1 / 0 / 0 |
| tswasm | swift | 10 | 10 | 2 | 0 | 1 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 10 pass / 0 fail | 4 / 0 / 0 / 0 |
