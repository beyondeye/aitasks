---
priority: low
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [testing, testmap, go_engine]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
created_at: 2026-10-14 19:23
updated_at: 2026-10-14 22:03
---

## Context

The engine now holds three independent hand lexers for Kotlin-family syntax:
- `goengines/internal/testmap/annot/lexctx.go` (the Kotlin classifier for annotation comments; M2.2);
- `goengines/internal/testmap/deps/kotlinlex.go` (the `.kt` dependency scanner; M2.3);
- `goengines/internal/testmap/deps/gradlelex.go` (the Gradle build-script blanker; t1975).

Within days, the same Kotlin 2.2 multi-dollar string blind spot was found
independently in each:
- t1975 (Gradle: made it fail closed);
- t1980 (`deps/kotlinlex.go`: made it fail closed);
- t1954_4 (annot: FP-writable, t1990).

The t1954 report (`aidocs/testing_engine/t1954_annotation_parser_research.md`)
keeps hand readers for the four supported languages, because no measured
alternative fits the safety, budget and dependency constraints together. It
also notes that a language-version change has to be absorbed in every copy.

## Objective

Evaluate, with evidence, whether these lexers should share one
Kotlin-family lexical core: one construct table of what is modelled and what
fails closed, consumed by annot's line classifier and by deps' token
scanners. Then decide.

## Required analysis

- Inventory each lexer's modelled constructs, its fail-closed constructs, and
  what its consumer needs. annot needs line classes, docstring and anchor
  data, and certainty. deps needs a token stream for imports and references
  (opaque reasons on refusal). Show where the needs differ, for example
  annot's "a comment inside a template is never an annotation line" policy.
- Measure the divergence: run the three lexers on the t1954 Kotlin corpus
  (`aidocs/testing_engine/t1954_parser_research/corpus/kotlin/`) and the real
  Kotlin files of the registered repositories (read-only, temporary checkouts
  of recorded commits, as in `results/t4/inputs.md`). Report every construct
  where they disagree.
- Compare the options:
  - shared core;
  - shared conformance fixtures only;
  - status quo plus a cross-lexer differential test.

  For each, state the implementation complexity (no schedules) and the
  blast radius in annot and deps.
- Respect the goengines dependency allowlist and the 300 ms scan budget.

## Outcome

A decision record in the task's plan. If a shared core is justified, create
a bounded implementation task (anchor 1852). Otherwise, make sure the cheaper
safeguard exists: shared fixtures or a differential test.

## Ordering

Advisory: after t1990, so that all
three lexers first agree on failing closed for that construct. No hard
dependency.
