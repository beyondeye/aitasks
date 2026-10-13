---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: []
issue_type: chore
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1954_2, t1954_3, t1954_4]
anchor: 1852
created_at: 2026-10-12 15:57
updated_at: 2026-10-13 12:02
---

## Context and user decision

Research sustainable language-aware annotation reading and safe source editing for `ait test` / testmap. This is user-requested new work arising from review of t1853_2 (M2.2 annotation grammar and rewriter), in topic t1852 and implementation trail `art:trail-testmap-feature`.

The current design supports Go with its existing scanner and Bash, Python and Kotlin with handwritten comment-context readers. The user accepts this limited implementation for now, but considers it critical infrastructure and does not accept maintaining an expanding collection of custom readers as the unexamined long-term strategy. This research does not block t1853_2 or require replacing its implementation now. It can begin independently; inspect the actual task/plan/code state when executing and distinguish proposed behavior from landed behavior.

## Objective

Compare all materially relevant candidate approaches and establish their actual suitability through reproducible experiments. Deliver a justified recommendation, a supported/unsupported language policy, and a migration sequence incorporated into the existing ait test trail. Advertised language counts and highlighting demonstrations are insufficient evidence for safe automated edits.

## Candidate approaches

Evaluate every family below; explain with evidence when a candidate is eliminated before prototyping:

1. Tree-sitter and maintained grammars through Go bindings. Compare practical native/static, shared-library and WASM deployment options where available; curated pinned grammars versus bundles; external scanners, ABI/version compatibility and licensing.
2. General-purpose tokenizers/highlighters: Chroma (pure Go) and Pygments (Python). Establish whether error reporting and byte-position fidelity support authorizing writes, rather than assuming highlighting accuracy suffices.
3. Established language-specific parsers/tokenizers: Go scanner/parser, a maintained shell parser such as mvdan/sh, Python tokenizer/parser, viable Kotlin tooling, and parsers for additional target languages. Assess a shared adapter interface and the runtime/toolchain burden.
4. External parser helpers/services, including compiler/LSP-backed syntax or token providers where the required information is actually exposed. Establish feasibility; do not assume every server exposes comments.
5. Current custom readers as a measured baseline; hybrid providers and explicit refusal/fallback policies. Assess registry/sidecar-only annotations for unsupported languages as a product alternative, including compatibility and inline-annotation requirement costs.
6. Other credible maintained approaches discovered during research; record evidence-backed exclusions rather than silently omitting them.

Use primary documentation, upstream source/issues/releases and experiments. Record versions/commits, research date, maintenance status and licenses. The initial links below are leads, not suitability claims.

## Use-case requirements

- Read real `testmap:` comments and Python module docstrings; distinguish strings, heredocs, raw strings, templates, embedded languages and ordinary prose. Python docstrings remain read-only.
- Preserve member ownership, source paths and stamps. Establish safe per-language insertion positions: identifying comments alone is insufficient. Preserve unrelated bytes, encoding, line endings, final-newline state and executable mode.
- Define behavior for malformed, incomplete, unsupported and error-recovered syntax. Measure false-positive writable comments separately from missed annotations; empty results must not disguise uncertainty. Account for Tree-sitter ERROR and MISSING/recovery behavior. Never silently fall back to unsafe text matching.
- Fit the Go engine architecture, actual dependency policy, supported release platforms and packaging. Measure build/cross-compilation requirements, CGO/runtime dependencies, offline operation, binary/grammar footprint, startup, scan latency and memory against the actual M2.2 benchmark/budget. Do not invent performance numbers.
- Assess the ongoing cost of adding a language, updating/pinning grammars, abandoned grammars and placement rules. Separate shared-engine maintenance from per-language adapters and conformance fixtures.
- Preserve the centralized rewriter, conflicts, root confinement/no-follow policy and stamp/provenance contracts. Assess migration impact on annotate, verify, stale confirmation, adoption, author annotations and the repair loop.

## Experiments

Build a corpus covering Bash/Python/Go/Kotlin plus at least three additional language families relevant to real target repositories (select and justify; examples include TypeScript/JavaScript, Rust, Java/C# and C/C++). Include ordinary valid files, difficult valid syntax, malformed files, embedded languages and unsupported constructs.

Reuse M2.2 adversarial fixtures when available. Include Bash heredoc bodies delayed by backslash continuations or spanning quotes, delimiter-shaped arguments and nested substitutions; non-docstring Python triple strings and modern f-strings; Kotlin raw strings/templates/nested comments; Go raw strings. Keep standalone fixtures if the baseline has not yet landed.

Prototype surviving candidates behind one experimental interface returning comment byte ranges, uncertainty/errors and placement information. Verify token/range round trips and exact proposed edits. Compare against native language tools and before/after execution of controlled fixtures where useful; never execute arbitrary repository files as a syntax check. Preserve pass/fail/unsupported matrices, reproducible commands, timings and environment details. Keep fixtures and harnesses with the report or as task-owned artifacts so results can be rerun.

## Deliverables and trail integration

1. A durable report under `aidocs/testing_engine/`, with this task ID in its filename, and reproducible evidence. Separate observations, documentation claims, assumptions and unknowns. Include the candidate matrix, rejected alternatives, dependency/licensing/maintenance analysis, and a recommendation or explicit no-candidate-yet conclusion.
2. A bounded provider/adapter contract and migration sketch: trustworthy comment locations, uncertainty, safe placement, language onboarding policy and conformance tests. Compare implementation complexity without inventing schedules. A production replacement is outside this research task.
3. On completion, re-read and refresh `art:trail-testmap-feature`. Link the exact report path and evidence artifact handles in its narrative (and evidence/relations at deep depth); record the decision, residual risks, affected modules and recommended landing order. Marking this task Done alone is insufficient.
4. Evaluate the then-existing consumers: M2.2/t1853_2; M2.3/t1853_3 if the provider affects dependency scanning; M4/t1855; M6/t1857; M7/t1858; repair loop/t1853_7; M9/t1860 docs/ports; M10/t1861 rollout; t1863 cross-linking. Use actual child IDs as they exist then. Distinguish consumers needing action from those needing context. Research informs long-term language expansion; current four-language work remains unblocked.
5. Create bounded implementation follow-ups justified by the recommendation, grouped under topic t1852 and placed in the trail. Use advisory ordering for recommendations and hard dependencies only for actual prerequisites. Send durable advisory notes with report links/decisions to existing affected tasks where useful; notes never replace implementation tasks.

## Acceptance criteria

- Every candidate family is evaluated or explicitly eliminated with evidence. Prototype at least two viable approaches unless documented feasibility findings eliminate all but one.
- Shared-corpus results cover safe editing/placement, uncertain syntax and additional languages; advertised language counts alone do not qualify.
- The recommendation accounts for correctness, portability, performance, dependency policy and maintenance, and explains rejected alternatives.
- The report, corpus, harness commands and results are durable and cross-linked.
- The ait test trail contains this research task and, on completion, its actual result and resulting follow-up sequence. Do not make current M2.2 implementation depend on the research.

## References

- `art:trail-testmap-feature` (owner t1852; inspect the latest version).
- `aitasks/t1853/t1853_2_m2_2_annotation_grammar_rewriter.md`, its current/archived plan, and `aidocs/testing_engine/n014_explorer_006_proposal.md` (M2.2, placement, Invariant 6).
- `goengines/README.md`, `goengines/go.mod`, `goengines/internal/testmap/annot/` when available.
- https://github.com/tree-sitter/go-tree-sitter
- https://github.com/tree-sitter/tree-sitter/wiki/List-of-parsers
- https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html
- https://github.com/alecthomas/chroma
- https://pygments.org/docs/api/
- https://pygments.org/docs/tokens/
- https://pkg.go.dev/mvdan.cc/sh/v3/syntax
