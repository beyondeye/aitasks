# Tree-sitter grammar maintenance (t1954_2)

Research date: 2026-10-13. Every value comes from `gh api` (read-only) or
from the pinned sources fetched by `tsref/fetch.sh`. "Last release" is the
GitHub release (`releases/latest`); "last commit" is the newest commit on
the default branch; "contributors" counts anonymous contributors too. These
are moment-relative and record activity only. They are not quality claims.

## Grammars (the 10 research grammars)

| grammar | upstream repo | pinned commit (gotreesitter v0.55.1 `languages.lock`) | ABI at pin (`LANGUAGE_VERSION`) | last release (date) | last commit | contributors | open issues + PRs | archived | license at pin | upstream C external scanner (lines) | gotreesitter source custody | official Go binding at pin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | tree-sitter/tree-sitter-bash | `a06c2e44` | 15 | v0.25.1 (2025-12-02) | 2025-12-02 | 31 | 88 | no | MIT | yes (1,217) | mirror | yes (`bindings/go`) |
| python | tree-sitter/tree-sitter-python | `26855eab` | 15 | v0.25.0 (2025-09-11) | 2025-09-15 | 37 | 36 | no | MIT | yes (437) | mirror | yes |
| go | tree-sitter/tree-sitter-go | `2346a3ab` | 15 | v0.25.0 (2025-08-29) | 2025-09-15 | 27 | 18 | no | MIT | none | **own** (grammargen Go DSL + Go ASI scanner + hand-written lexer) | yes |
| kotlin | fwcd/tree-sitter-kotlin | `1852ea17` | 14 | 0.3.8 (2024-08-03) | 2026-08-01 | 47 | 12 | no | MIT | yes (979) | mirror | yes |
| typescript | tree-sitter/tree-sitter-typescript (`typescript/`) | `75b3874e` | 14 | v0.23.2 (2024-11-11) | 2025-01-30 | 42 | 55 | no | MIT | yes (13 + shared `common/scanner.h` 347) | mirror | yes |
| tsx | tree-sitter/tree-sitter-typescript (`tsx/`) | `75b3874e` | 14 | (same repository) | | | | no | MIT | yes (13 + shared 347) | mirror | yes |
| javascript | tree-sitter/tree-sitter-javascript | `58404d8c` | 15 | v0.25.0 (2025-09-01) | 2025-09-15 | 54 | 29 | no | MIT | yes (364) | mirror | yes |
| java | tree-sitter/tree-sitter-java | `e10607b4` | 14 | v0.23.5 (2024-12-21) | 2025-09-15 | 43 | 23 | no | MIT | none | mirror (+ hand-written Go lexer) | yes |
| rust | tree-sitter/tree-sitter-rust | `77a37472` | 15 | v0.24.2 (2026-03-27) | 2026-03-27 | 42 | 55 | no | MIT | yes (403) | mirror | yes |
| swift | alex-pinkus/tree-sitter-swift | `00bbb0a2` | 15 (generated here) | 0.7.3 (2026-06-01) | 2026-10-10 | 39 | 40 | no | MIT | yes (1,112) | **own** (grammargen) | **no generated parser committed** at the pin; `tree-sitter generate` from `src/grammar.json` is needed (`tsref/LOCK`, CLI 0.26.9) |

Notes:
- "ABI at pin" is read from each `parser.c`. Swift's was generated here by
  tree-sitter CLI 0.26.9, so its ABI is a property of our generation, not
  of the upstream repository. Regenerating gives byte-identical output: the
  `tsref/fetch.sh` srcsum check passed on a second, independent fetch.
- **Abandonment indicators** at the research date: no grammar repository is
  archived. Releases lag commits for several grammars: Kotlin's last release
  is 2024-08 but it had commits in 2026-08; TypeScript's last release is
  2024-11 with commits to 2025-01. A stale release tag is not abandonment,
  but a pinning model cannot rely on tagged releases for these grammars. It
  must pin commits, which is what gotreesitter's `languages.lock` does.
- **Kotlin and Swift come from community repositories**, not the
  `tree-sitter` org: fwcd/tree-sitter-kotlin (a separate
  tree-sitter-grammars/tree-sitter-kotlin fork exists at v1.1.0) and
  alex-pinkus/tree-sitter-swift. Their maintenance depends on their
  individual maintainers.

## Runtimes

| component | repo | version used | last release / tag | last commit | contributors | open issues + PRs | license |
|---|---|---|---|---|---|---|---|
| gotreesitter (pure Go) | odvcencio/gotreesitter | v0.55.1 | v0.55.1 (2026-09-26); v0.52 → v0.55.1 tagged within weeks | 2026-10-13 | 23 | 48 | MIT; bundled grammar licenses in `licenses/grammars.json` (206 entries, audited per `languages.lock` ref) |
| go-tree-sitter (official, cgo) | tree-sitter/go-tree-sitter | v0.25.0 | no GitHub releases; module tags only | 2025-11-12 | 6 | 19 | MIT |
| wazero (pure-Go wasm runtime) | tetratelabs/wazero | v1.12.0 | v1.12.0 (2026-05-29) | 2026-09-28 | 86 | 52 | Apache-2.0 |
| zig (wasm C toolchain, build-time only) | ziglang/zig | 0.17.0 (release tarball, sha256-verified) | 0.17.0 (2026-10-01) | — | — | — | MIT |

## Pinning model

- **gotreesitter is a bundle.** One module version pins every grammar's
  tables, Go scanner ports and owned grammars together (`languages.lock`).
  You cannot bump one grammar alone without forking the module, or without
  supplying blobs yourself (`grammar_blobs_external` +
  `GOTREESITTER_GRAMMAR_BLOB_DIR`, `docs/build-tags.md`). Even then the Go
  scanner port and any hand-written lexer stay tied to the module version.
  The curated set is a link-time choice (`grammar_subset` +
  `grammar_subset_<lang>`, `results/footprint.md`), not a version choice.
- **The C references (tscgo, tswasm) pin per grammar.** `tsref/LOCK` names
  each repository commit and a srcsum over each grammar's source directory.
  Bumping one grammar is a one-line LOCK edit plus `--print-sums`.
- **Conformance gate before any bump**, in either model:
  - zero safety regressions on the corpus matrix (FP-writable,
    Docstring-write, Silent-uncertain, Record-corruption);
  - no new provider errors and no new uncertain-only files on the real
    repository walks (`results/ts/realrepo_*.md`);
  - the gotreesitter-vs-C differential (`results/ts_differential.md`)
    re-run, with every new Result difference triaged.

  These are the measurements this task produced, so the gate is
  reproducible. Who runs it, and how often, is outside this task.
