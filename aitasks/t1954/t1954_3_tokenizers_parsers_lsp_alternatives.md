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
