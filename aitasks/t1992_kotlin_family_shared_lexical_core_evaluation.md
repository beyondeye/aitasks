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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1990** id=2026-10-15T06:08:50Z.37d2f78d839e2bd5759caeed from=t1990 from_verified=yes at=2026-10-15T06:08:50Z base=cf210a9e9b70395a794e1597903c34a2937711b1 base_branch=main dirty=yes host=omg16
>
> | t1990 landed as commit cf210a9e9 and changes one row of your three-lexer inventory. If your inventory or divergence run was taken against an earlier tree, annot's row is stale.
> | 
> | - annot (goengines/internal/testmap/annot/lexctx.go, classifyKotlin) now MODELS the Kotlin 2.2 interpolation prefix. It does not fail closed, unlike t1975 (gradlelex) and t1980 (kotlinlex). The rules follow JetBrains/kotlin compiler/psi/parser/src/org/jetbrains/kotlin/lexer/Kotlin.flex:
> |   - `{INTERPOLATION}?"` gives prefix n = max(run, 1);
> |   - in STRING/RAW_STRING, LONG_TEMPLATE_ENTRY_START and SHORT_TEMPLATE_ENTRY open a template only when the $-run is >= n (the last n dollars start it; any excess is text);
> |   - pushState/popState keep a prefix per string frame.
> | 
> |   New helper: kotlinDollars. Why model rather than fail closed: an Uncertain context makes annot.ParseFile return a SyntaxError for any file carrying `testmap:`, and ScanAnnotations (annot/source.go:54-60) propagates it. Failing closed would fail the whole scan, not just one file's opaque reason as in deps.
> | - annot also models SHORT_TEMPLATE_ENTRY with an ESCAPED_IDENTIFIER (`` $`name` ``). A backticked name can hold quotes. deps/kotlinlex.go str() does not handle it. With the probe in t1999 (filed from t1990), ktLex returns err=nil and silently drops tokens that the 2.3.20 KotlinLexer keeps. Whether gradlelex.go's kts mode has the same gap was NOT checked.
> | - A reusable differential: the archived plan p1990 ("Implementation Evidence") has a KotlinLexer adapter (Java, kotlin-compiler-embeddable-2.3.20.jar from ~/.gradle) that maps tokens to line classes plus certainty. It handles the BOM, unclosed constructs at EOF, and the template-line policy. It also has an old-vs-new parity harness over the 2051 .kt/.kts files of the registered repositories, archived at recorded HEADs. Both may serve your "cross-lexer differential" option.

> **✉ note:t1997** id=2026-10-15T07:42:18Z.3d060fe5f431b6e01a368c48 from=t1997 from_verified=yes at=2026-10-15T07:42:18Z base=af9f27ae77caa6f23658bbe820b41029e5b3bf07 base_branch=main dirty=yes host=omg16
>
> | t1997 (commit 6ed14e3a3) changed one fact your Kotlin-family lexical-core comparison may record about goengines/internal/testmap/deps/kotlinlex.go:
> | 
> | - The deps lexer used to drop ESCAPED_IDENTIFIER-ness: a backticked name was emitted as kind `n` with its backticks stripped, indistinguishable from a keyword. `ktok` now carries `esc bool`, set by the code-level backtick case (kotlinlex.go:81 as of 6ed14e3a3). The `$`-template identifier path (`emit` at :233) still sets `esc: false`; t1999 is changing that path.
> | - The deps scanner (kotlin.go:175) now refuses escaped tokens at the declaration gate. The `package` / `import` branches and the keyword-text opaque checks are still escape-blind. t2002 (filed from t1997) covers the `import` case, where an escaped `` `import` `` swallows the next declaration.
> | 
> | So a shared core would need to expose "escaped identifier" as a token property for the deps consumer. Advisory context only; how the evaluation weighs it is yours to decide.

> **✉ note:t1991** id=2026-10-15T11:53:17Z.fcfcb5eb50cc95026e658e83 from=t1991 from_verified=yes at=2026-10-15T11:53:17Z base=e7777595830c856bd03b0df8bfdf68113686d279 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1991 (annot conformance gate), for the "shared conformance fixtures only" option and any shared-core change.
> | 
> | - t1991 landed a hermetic conformance gate in commit 8f69074cb.
> |   goengines/internal/testmap/annot/testdata/conformance/kotlin/ holds
> |   byte-identical copies of the 31 Kotlin fixtures of the t1954 research corpus
> |   (PROVENANCE: corpus commit 07713a9c4). conformance_test.go replays them
> |   through the real ParseFile -> PlanCovers -> Apply. It also sends a direct
> |   Replace write probe at every labelled look-alike or read-only line; 16 of
> |   the Kotlin probes are "sensitive", meaning a misclassification would let
> |   Apply write the line.
> | - On the annot side, the shared-fixtures option is therefore partly in place
> |   already. The format reader, however, is test-only (conformance_reader_test.go
> |   in package annot), so deps cannot import it as is. Sharing would mean moving
> |   it to a non-test helper package or duplicating it.
> | - Any shared-core change to annot's Kotlin reader must keep TestConformance
> |   green. Every deviation from a fixture's oracle must be pinned in confKnown,
> |   and a pin that stops occurring also fails, so a behaviour change shows up as
> |   a test change.
> | - At cf210a9e9 (after t1990) all four multidollar_*.kt fixtures are clean,
> |   including the write probe on multidollar_comment_desync.kt line 9. Replayed
> |   against annot 3d1a2b628 (before t1990), the gate reproduces the research's
> |   Kotlin row exactly.
> | - tests/test_annot_conformance_corpus_sync.sh, a CI step in
> |   goengines-check.yml, fails when the research corpus and the copy differ in
> |   file list, bytes or executable bits. A fixture added to the research corpus
> |   for a differential study therefore also has to be copied.
> | 
> | These are tree-relative claims dated by this note's base commit; the decision
> | remains yours.
