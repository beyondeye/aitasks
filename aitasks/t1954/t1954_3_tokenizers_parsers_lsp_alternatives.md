---
priority: medium
effort: high
depends: [t1954_2]
issue_type: chore
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-12 17:51
updated_at: 2026-10-12 17:51
---

## Context

Child 3 of t1954 (annotation-parser research). It evaluates every **non-Tree-sitter** family on t1954_1's infrastructure: the research module at `aidocs/testing_engine/t1954_parser_research/`, the corpus and oracles, the immutable baseline, and the evaluation seam. The shared design in the parent plan `aiplans/p1954_research_multilanguage_annotation_parsers.md` is authoritative. Read the archived plans and findings of t1954_1 and t1954_2 first, plus `results/feasibility.md` and any note sent to this task.

Engine constraints: CGO-free across 4 targets, offline, dependency allowlist, `scan` < 300 ms. A provider that needs a runtime the engine does not ship (Python, a JVM, Node, a language server) must be evaluated **and costed**, not assumed out.

## Candidates (prototype where feasible; otherwise eliminate with recorded evidence)

1. **Chroma** (pure Go highlighter): are unterminated constructs and errors reported, or silently recovered? Do byte positions round-trip (`FullCover`)?
2. **Pygments** (subprocess): the same questions, plus newline/tab normalisation (`stripnl`, `ensurenl`), `Error` tokens, whether `String.Doc` can supply `DocInfo` including the statement end (else `DocLiterals` unsupported), and the runtime-dependency cost.
3. **Language-specific parsers:**
   - mvdan.cc/sh/v3/syntax (bash: comments, heredocs, positions, parse errors) as a full provider;
   - Python `tokenize`/`ast` as a provider via subprocess, plus a search for maintained pure-Go Python tokenizers;
   - Kotlin tooling (compiler PSI, ktlint/detekt, kotlinx tooling) and its JVM runtime burden;
   - the cost of a shared adapter interface across these.
4. **ANTLR4 Go runtime + grammars-v4 lexers** (comments on hidden channels): prototype at least Kotlin and one more language; assess grammar maintenance.
5. **LSP/compiler providers**: do semanticTokens or foldingRange expose comments in gopls, pyright, typescript-language-server and kotlin-language-server? Run one experiment per server that can be installed into the scratch dir (never system-wide); otherwise document it. Do not assume every server exposes comments.
6. **Other approaches**, each with an evidence-backed exclusion or a prototype: TextMate grammars (vscode-textmate / shiki), ctags, linguist, tokei/scc, semgrep, srcML, difftastic, tree-sitter-language-pack, highlight.js/Prism, and anything else discovered.
7. **Product alternative**: registry/sidecar-only annotations for unsupported languages. Cover compatibility with M2.1 `AnnotationSource`, stamp/provenance, stale confirmation (M4), adoption (M6), author annotation (M7.4), the repair loop (t1853_7), and the cost of the inline-annotation requirement.

Every prototyped provider runs the **full matrix in all 8 languages through the seam**: the lexical, range, record, edit, refusal and behaviour levels. Report `unsupported` / `n/a` explicitly, never as empty output.

## Also deliver

- Versions/commits, maintenance (`gh api`, read-only) and licenses.
- Footprint and performance.
- `findings_t1954_3.md`.
- Path-scoped commits only; nothing under `goengines/` changes.

## Verification

- README commands reproduce `results/matrix_<p>.md` for every prototyped provider.
- Every candidate family has a prototype or an evidence-backed elimination recorded in the findings.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1954_1** id=2026-10-12T18:32:42Z.b24ff1548761b7c2513c664b from=t1954_1 from_verified=yes at=2026-10-12T18:32:42Z base=13a8751d59fde438d0a871bd130bc70fb4df23eb base_branch=main dirty=yes host=omg16
>
> | The t1954 shared design (aiplans/p1954_research_multilanguage_annotation_parsers.md, "Experimental interface") was amended during t1954_1's plan review:
> | - Capabilities gained `Anchors AnchorSet`: an anchor the provider does not declare is UNKNOWN, never "none"; a declared anchor with value 0 is confirmed-empty.
> | - `ToContext(lang, src, caps, res, need)` enforces per-operation requirements itself: every write needs `Errors` (and `DocLiterals` for Python); only fresh file-level insertion needs the per-language anchor table. Missing → unsupported:<cap> for that op only.
> | - TS/JS native evidence must come from parser-aware extraction (bare ts.createScanner misreads template continuations); any native oracle overriding a hand .expect must pass a self-test with a negative control.
> | - Bench: cold = one timed first op per fresh process incl. provider init; only end-to-end registry.Scan is compared to the 300 ms budget; lexical-only rows are labelled.
> | Hedge: the harness code implementing this lands with t1954_1's commit, not yet at the time of this note.

> **✉ note:t1954_1** id=2026-10-12T18:38:46Z.e7c6cab92696f2b714cc7283 from=t1954_1 from_verified=yes at=2026-10-12T18:38:46Z base=e3ddd44c5b6ff4d33ab7b8250f632fa2d20d05ba base_branch=main dirty=yes host=omg16
>
> | Feasibility smoke (t1954_1 pre-phase; evidence will be in aidocs/testing_engine/t1954_parser_research/results/feasibility.md, landing with t1954_1's commit): Chroma v2.27.0, mvdan.cc/sh/v3 v3.14.1, antlr4-go v4.13.1 (runtime) all build CGO_ENABLED=0 for the 4 release targets. Advisory observation (not a measured matrix result): Chroma's swift lexer reported 21 comment tokens for a snippet with one real comment after a `#"""…"""#` raw string. ANTLR has no usable lexer without generating one from grammars-v4 with the Java ANTLR tool.

> **✉ note:t1954_1** id=2026-10-13T09:01:52Z.5d14df8eaefc710f438ba746 from=t1954_1 from_verified=yes at=2026-10-13T09:01:52Z base=5e730b0fb5168432674a24eb41c63089473153bf base_branch=main dirty=yes host=omg16
>
> | t1954_1 measured mvdan.cc/sh/v3 v3.14.1 (provider `shfmt`) through the seam — aidocs/testing_engine/t1954_parser_research/results/matrix_shfmt.md (commit 5e730b0fb, baseline pin f096db065):
> | - FP-writable (safety): in an unquoted `<<-` heredoc whose body line ends in `\`, mvdan matches the delimiter before joining the backslash-newline, so it reads heredoc DATA as a comment annotation (corpus/bash/lex_heredoc_strip_continuation.sh; bash 5.3 execution confirms the hand oracle).
> | - Silent-uncertain (safety): it does not flag the unterminated heredoc inside a backtick substitution (lex_heredoc_in_backticks.sh).
> | - Over-refusal 8 / read-mismatch 6: `$((`-ambiguous subshells, Latin-1 bytes ("invalid UTF-8"), an ANSI-C heredoc delimiter, and a grammar error that does not affect comment context. Real repos: it refuses 10/1,620 bash files the baseline reads (results/realrepo_*.md).
> | - Bench (results/bench.md): end-to-end 49.4 ms cold with bash via shfmt, within the 300 ms budget.
> | Add Chroma/Pygments/ANTLR providers in provider/ and they plug into the same matrices (README "Adding a provider").

> **✉ note:t1954_2** id=2026-10-13T14:25:01Z.c221d645d5842a268c2a5d3a from=t1954_2 from_verified=yes at=2026-10-13T14:25:01Z base=a2395c30931f2303a84ab5e7df4527b49e275f5b base_branch=main dirty=yes host=omg16
>
> | t1954_2 landed harness changes in aidocs/testing_engine/t1954_parser_research/ (commit a2395c309) that t1954_3's providers depend on:
> | - `.tsx` is now its own research Lang `tsx` (provider/langs.go): providers see only the Lang, never the path, and TS vs TSX are different grammars. A Chroma/Pygments/other provider must list "tsx" in Langs() and handle it, or corpus/typescript/jsx_text.tsx scores `unsupported`. requiredAnchors["tsx"] = ImportEnd|Prologue.
> | - `bench --subjects a,b --lex-subjects a,b --out results/bench_<x>.md` (plus --labels/--excluded/--title/--rerun) measures only new rows; t1954_1's bench.md stays as committed. `footprint --ts-only` shows the pattern for a separate footprint file.
> | - Scoring fix (internal/runner/edits.go): an op refused for a different reason than expected (e.g. uncertain vs not-comment) is no longer counted as record corruption; it is a note only.
> | - Tagged-provider verbs can register through `extraVerbs` (cmd/t1954/main.go).
> | Evidence/context: findings_t1954_2.md items 1-5; archived plan p1954_2 "Notes for sibling tasks".

> **👁 note:read** id=2026-10-13T14:28:38Z.8110647cee18e8c37a022bd3 by=t1954_3 at=2026-10-13T14:28:38Z mode=explicit ids=2026-10-12T18:32:42Z.b24ff1548761b7c2513c664b,2026-10-12T18:38:46Z.e7c6cab92696f2b714cc7283,2026-10-13T09:01:52Z.5d14df8eaefc710f438ba746,2026-10-13T14:25:01Z.c221d645d5842a268c2a5d3a
