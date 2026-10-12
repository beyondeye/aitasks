---
Task: t1954_3_tokenizers_parsers_lsp_alternatives.md
Parent Task: aitasks/t1954_research_multilanguage_annotation_parsers.md
Sibling Tasks: aitasks/t1954/t1954_1_*.md, aitasks/t1954/t1954_2_*.md, aitasks/t1954/t1954_4_*.md
Archived Sibling Plans: aiplans/archived/p1954/p1954_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1954_3 — Tokenizers, language parsers, external providers, alternatives

## Context

Third child of t1954. It evaluates every non-Tree-sitter family on the harness
(`R = aidocs/testing_engine/t1954_parser_research/`). The shared design in
`aiplans/p1954_research_multilanguage_annotation_parsers.md` is authoritative.
Read the archived plans and findings of t1954_1 and t1954_2, `R/results/feasibility.md`
and any inbox note first.

## Step 0 — reality check

- Run `R/baseline/fetch.sh`, then `go run ./cmd/t1954 guard`. The committed
  matrices must reproduce.
- Re-check candidate releases.

## Steps

1. **Chroma** (`R/provider/chroma.go`, pure Go)
   - Map `Comment.Single` / `Comment.Multiline` / `Comment.Preproc`, the
     String.* tokens (including `String.Heredoc`, `String.Doc`) and `Error`
     tokens.
   - Check `FullCover`: does concatenating the token values reproduce the
     input? Chroma may normalise line endings or tabs.
   - On the malformed fixtures, is anything reported, or is the input
     silently recovered? Count every Silent-uncertain case.
   - Record which lexers are regex-state machines that cannot express
     heredoc delimiters or nesting, citing the lexer source.
2. **Pygments** (`R/oracle/pygments_oracle.py` + `R/provider/pygments.go`,
   subprocess, JSON)
   - The same questions as Chroma, with `stripnl=False, ensurenl=False`
     forced and the default normalisation recorded.
   - Map `Token.Error`.
   - Check whether `String.Doc` can supply `DocInfo` with the statement end.
     If not, set `DocLiterals` to unsupported.
   - Cost the runtime: a Python dependency on the engine path, startup per
     invocation, and batching.
3. **Language-specific providers**
   - `R/provider/mvdansh.go`: mvdan.cc/sh/v3 as a full bash provider —
     comments, heredoc bodies, words/strings and parse errors with byte
     offsets, plus its bash-dialect limits (the 3 files t1853_2's probe saw
     shfmt reject).
   - `pytokenize` (t1954_1's oracle) promoted to a provider row, with its
     subprocess cost. Search for maintained pure-Go Python tokenizers (e.g.
     gpython's lexer, go-python packages) and check 3.12 f-string support;
     prototype one if it exists, else record the exclusion.
   - Kotlin: kotlin-compiler-embeddable PSI, ktlint and detekt (all JVM).
     Feasibility, runtime size, startup, and offline packaging; prototype via a
     small JVM helper in the scratch dir if a JDK is available (java 21 is),
     else document.
   - Write down the shared adapter cost: lines of glue per provider, and the
     capability gaps.
4. **ANTLR4** (`R/provider/antlr_<lang>.go`)
   - Use the Go runtime `github.com/antlr4-go/antlr/v4`, generate grammars-v4
     lexers (KotlinLexer plus at least one more, e.g. TypeScript or Java) with
     the ANTLR tool jar in the scratch dir, and commit only the generated Go
     needed to rerun, or a regeneration script plus a pinned jar checksum.
   - Hidden-channel comments become spans and token-recognition errors
     become `Diags`.
   - Assess grammar maintenance: grammars-v4 commit activity per grammar and
     known-issue counts.
5. **LSP / compiler providers**
   - For gopls, pyright, typescript-language-server and kotlin-language-server
     (installed into the scratch dir, never system-wide), test whether
     `textDocument/semanticTokens/full` emits `comment` tokens with exact
     ranges and whether `foldingRange` reports `comment` kinds. Write a tiny
     LSP client in `R/cmd/t1954 lsp` or use a script.
   - Record what each server actually exposes, plus the deployment burden:
     the runtime, a project workspace requirement, and startup.
   - A server that cannot be obtained is documented from its own
     documentation and marked "not measured".
6. **Other approaches**: TextMate grammars (vscode-textmate / shiki via node in
   the scratch dir: same regex-state class as Chroma, so one experiment),
   universal-ctags, linguist, tokei/scc, semgrep, srcML, difftastic,
   tree-sitter-language-pack, highlight.js/Prism, and anything discovered.
   Each gets either a prototype row or an evidence-backed exclusion in the
   findings, citing source, docs or a measurement.
7. **Product alternative: registry/sidecar-only annotations**
   - Design-level evaluation against the landed M2.1 `registry.AnnotationSource`
     (`goengines/internal/testmap/registry`) and M2.2's stamp/provenance:
     - where sidecar records live in `aitestmap/`;
     - how member identity survives edits;
     - stale confirmation (M4), adoption (M6), author annotation (M7.4) and
       the repair loop (t1853_7);
     - what is lost compared with inline annotations (co-location, review
       visibility);
     - compatibility, if mixed with inline.
   - Run a small experiment if cheap, e.g. a fake `AnnotationSource` fed from
     a YAML sidecar, exercised by the registry `scan` engine at the pinned
     snapshot.
8. **Runs**: matrix, realrepo, bench and footprint for every prototyped
   provider, in all 8 languages, through the seam.
9. **Findings** `R/findings_t1954_3.md`: observations, documentation claims,
   assumptions and unknowns kept separate, with versions, licenses and
   maintenance data.

## Verification

- README commands reproduce every new `R/results/matrix_<p>.md`.
- `CGO_ENABLED=0 go build ./...` passes; subprocess providers report
  `unsupported` cleanly when their runtime is absent.
- Every candidate family listed in the parent task has either a prototype or a
  recorded elimination.
- Commits name only paths under `R`.

## Step 9 reference

`chore: … (t1954_3)` commit of `R` paths; standard child archival.
