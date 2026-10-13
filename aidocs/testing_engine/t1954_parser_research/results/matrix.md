# Matrix: all subjects

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Per-subject detail: `matrix_<subject>.md`. Columns as there; safety columns first.

| subject | lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | bash | 67 | 67 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 3 | 0 | 0 | 0 | n/a — not exposed | 21 / 8 / 0 / 0 |
| baseline | python | 64 | 64 | 0 | 0 | 0 | 3 | 0 | 0 | 1 | 0 | 1 | 1 | 2 | n/a — not exposed | 21 / 29 / 0 / 0 |
| baseline | go | 21 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 9 / 3 / 0 / 0 |
| baseline | kotlin | 26 | 26 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 11 / 2 / 0 / 0 |
| baseline | typescript | 19 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| baseline | java | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| baseline | rust | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| baseline | swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| antlr | bash | 67 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| antlr | python | 64 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| antlr | go | 21 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| antlr | kotlin | 26 | 26 | 2 | 0 | 3 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 25 pass / 1 fail | 7 / 2 / 4 / 0 |
| antlr | typescript | 19 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| antlr | java | 11 | 11 | 2 | 0 | 1 | 0 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 11 pass / 0 fail | 5 / 2 / 1 / 0 |
| antlr | rust | 10 | 10 | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 10 pass / 0 fail | 5 / 2 / 1 / 0 |
| antlr | swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| chroma | bash | 67 | 66 | 22 | 0 | 8 | 3 | 0 | 2 | 19 | 0 | 0 | 0 | 0 | 56 pass / 10 fail | 21 / 6 / 0 / 0 |
| chroma | python | 64 | 62 | 1 | 0 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 60 pass / 2 fail | 0 / 0 / 40 / 7 |
| chroma | go | 21 | 21 | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 19 pass / 2 fail | 6 / 3 / 3 / 0 |
| chroma | kotlin | 26 | 26 | 10 | 0 | 3 | 0 | 0 | 0 | 9 | 1 | 0 | 0 | 0 | 26 pass / 0 fail | 7 / 2 / 4 / 0 |
| chroma | typescript | 19 | 19 | 2 | 0 | 1 | 0 | 0 | 0 | 4 | 4 | 0 | 0 | 0 | 13 pass / 6 fail | 8 / 6 / 6 / 0 |
| chroma | java | 11 | 11 | 2 | 0 | 2 | 0 | 0 | 0 | 4 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 5 / 2 / 1 / 0 |
| chroma | rust | 10 | 10 | 0 | 0 | 2 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 0 | 8 pass / 2 fail | 5 / 2 / 1 / 0 |
| chroma | swift | 11 | 11 | 2 | 0 | 2 | 0 | 1 | 0 | 6 | 2 | 0 | 0 | 0 | 11 pass / 0 fail | 5 / 1 / 1 / 0 |
| goscanner | bash | 67 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | python | 64 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | go | 21 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 21 pass / 0 fail | 9 / 3 / 0 / 0 |
| goscanner | kotlin | 26 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | typescript | 19 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | java | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | rust | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| goscanner | swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| gotreesitter | bash | 67 | 67 | 4 | 0 | 0 | 0 | 0 | 2 | 7 | 12 | 0 | 0 | 0 | 62 pass / 5 fail | 20 / 9 / 0 / 0 |
| gotreesitter | python | 64 | 64 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 62 pass / 2 fail | 20 / 30 / 0 / 0 |
| gotreesitter | go | 21 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 20 pass / 1 fail | 9 / 3 / 0 / 0 |
| gotreesitter | kotlin | 26 | 26 | 2 | 0 | 2 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 26 pass / 0 fail | 11 / 2 / 0 / 0 |
| gotreesitter | typescript | 19 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 16 pass / 3 fail | 16 / 4 / 0 / 0 |
| gotreesitter | java | 11 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 6 / 2 / 0 / 0 |
| gotreesitter | rust | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 pass / 0 fail | 6 / 2 / 0 / 0 |
| gotreesitter | swift | 11 | 11 | 2 | 0 | 1 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 6 / 1 / 0 / 0 |
| ktpsi | bash | 67 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| ktpsi | python | 64 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| ktpsi | go | 21 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| ktpsi | kotlin | 26 | 26 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 0 | 25 pass / 1 fail | 11 / 2 / 0 / 0 |
| ktpsi | typescript | 19 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| ktpsi | java | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| ktpsi | rust | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| ktpsi | swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pygments | bash | 67 | 66 | 22 | 0 | 8 | 3 | 0 | 2 | 19 | 0 | 0 | 0 | 0 | 56 pass / 10 fail | 21 / 6 / 0 / 0 |
| pygments | python | 64 | 64 | 1 | 0 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 62 pass / 2 fail | 0 / 0 / 43 / 7 |
| pygments | go | 21 | 21 | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 19 pass / 2 fail | 6 / 3 / 3 / 0 |
| pygments | kotlin | 26 | 26 | 8 | 0 | 3 | 0 | 0 | 1 | 10 | 3 | 0 | 0 | 0 | 25 pass / 1 fail | 7 / 2 / 4 / 0 |
| pygments | typescript | 19 | 19 | 2 | 0 | 1 | 0 | 0 | 0 | 4 | 4 | 0 | 0 | 0 | 13 pass / 6 fail | 8 / 6 / 6 / 0 |
| pygments | java | 11 | 11 | 2 | 0 | 2 | 0 | 0 | 0 | 4 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 5 / 2 / 1 / 0 |
| pygments | rust | 10 | 10 | 0 | 0 | 2 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 0 | 8 pass / 2 fail | 5 / 2 / 1 / 0 |
| pygments | swift | 11 | 11 | 0 | 0 | 2 | 0 | 0 | 0 | 5 | 3 | 0 | 0 | 0 | 11 pass / 0 fail | 5 / 1 / 1 / 0 |
| pytokenize | bash | 67 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | python | 64 | 64 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 64 pass / 0 fail | 20 / 30 / 0 / 0 |
| pytokenize | go | 21 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | kotlin | 26 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | typescript | 19 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | java | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | rust | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| pytokenize | swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | bash | 67 | 67 | 2 | 0 | 1 | 0 | 0 | 0 | 6 | 8 | 0 | 0 | 0 | 67 pass / 0 fail | 20 / 9 / 0 / 0 |
| shfmt | python | 64 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | go | 21 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | kotlin | 26 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | typescript | 19 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | java | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | rust | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| shfmt | swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| textmate | bash | 67 | 66 | 12 | 0 | 0 (+8 n/a: no error reporting) | 0 | 2 | 6 | 17 | 0 | 1 | 0 | 0 | 55 pass / 11 fail | 0 / 0 / 25 / 3 |
| textmate | python | 64 | 62 | 4 | 0 | 0 (+3 n/a: no error reporting) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 57 pass / 5 fail | 0 / 0 / 40 / 7 |
| textmate | go | 21 | 21 | 0 | 0 | 0 (+3 n/a: no error reporting) | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 20 pass / 1 fail | 0 / 0 / 12 / 0 |
| textmate | kotlin | 26 | 26 | 8 | 0 | 0 (+3 n/a: no error reporting) | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 26 pass / 0 fail | 0 / 0 / 13 / 0 |
| textmate | typescript | 19 | 19 | 0 | 0 | 0 (+2 n/a: no error reporting) | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 18 pass / 1 fail | 0 / 0 / 19 / 1 |
| textmate | java | 11 | 11 | 2 | 0 | 0 (+2 n/a: no error reporting) | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 11 pass / 0 fail | 0 / 0 / 8 / 0 |
| textmate | rust | 10 | 10 | 0 | 0 | 0 (+2 n/a: no error reporting) | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 10 pass / 0 fail | 0 / 0 / 8 / 0 |
| textmate | swift | 11 | 11 | 0 | 0 | 0 (+2 n/a: no error reporting) | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 10 pass / 1 fail | 0 / 0 / 7 / 0 |
| tscgo | bash | 67 | 67 | 4 | 0 | 0 | 0 | 0 | 2 | 7 | 10 | 0 | 0 | 0 | 62 pass / 5 fail | 20 / 9 / 0 / 0 |
| tscgo | python | 64 | 64 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 62 pass / 2 fail | 20 / 30 / 0 / 0 |
| tscgo | go | 21 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 20 pass / 1 fail | 9 / 3 / 0 / 0 |
| tscgo | kotlin | 26 | 26 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 26 pass / 0 fail | 11 / 2 / 0 / 0 |
| tscgo | typescript | 19 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 16 pass / 3 fail | 16 / 4 / 0 / 0 |
| tscgo | java | 11 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 6 / 2 / 0 / 0 |
| tscgo | rust | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 pass / 0 fail | 6 / 2 / 0 / 0 |
| tscgo | swift | 11 | 11 | 2 | 0 | 1 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 6 / 1 / 0 / 0 |
| tsnative | bash | 67 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| tsnative | python | 64 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| tsnative | go | 21 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| tsnative | kotlin | 26 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| tsnative | typescript | 19 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 19 pass / 0 fail | 16 / 4 / 0 / 0 |
| tsnative | java | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| tsnative | rust | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| tsnative | swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| tswasm | bash | 67 | 67 | 4 | 0 | 0 | 0 | 0 | 2 | 7 | 10 | 0 | 0 | 0 | 62 pass / 5 fail | 20 / 9 / 0 / 0 |
| tswasm | python | 64 | 64 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 62 pass / 2 fail | 20 / 30 / 0 / 0 |
| tswasm | go | 21 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 20 pass / 1 fail | 9 / 3 / 0 / 0 |
| tswasm | kotlin | 26 | 26 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 26 pass / 0 fail | 11 / 2 / 0 / 0 |
| tswasm | typescript | 19 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 16 pass / 3 fail | 16 / 4 / 0 / 0 |
| tswasm | java | 11 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 6 / 2 / 0 / 0 |
| tswasm | rust | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 pass / 0 fail | 6 / 2 / 0 / 0 |
| tswasm | swift | 11 | 11 | 2 | 0 | 1 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 6 / 1 / 0 / 0 |
