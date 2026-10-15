---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: test
status: Done
labels: [testing, testmap, go_engine]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-14 19:22
updated_at: 2026-10-15 14:53
completed_at: 2026-10-15 14:53
---

## Context

The t1954 research
(`aidocs/testing_engine/t1954_annotation_parser_research.md`) recommends
**retaining** the landed M2.2 readers for bash, Python, Go and Kotlin
(go/scanner for Go, hand readers for the rest). No measured alternative
matches them on safety, the 300 ms scan budget and the dependency policy
together. The corpus found two defects in them:
- the Python UTF-8 BOM, fixed by t1969;
- the Kotlin multi-dollar strings, t1990.

`annot` has already changed three times after the research pin. The
safeguard that makes "retain" acceptable is therefore a **hermetic
conformance gate inside goengines**, so that a reader regression fails
`go test` instead of waiting for the next research rerun.

## Scope

1. Copy the bash, Python, Go and Kotlin fixtures of the research corpus
   (`aidocs/testing_engine/t1954_parser_research/corpus/{bash,python,go,kotlin}/`:
   `*.in`, `*.expect`, `*.edits`) into
   `goengines/internal/testmap/annot/testdata/conformance/<lang>/`. Keep the
   `.in` suffix, so no language table claims them. Add a `PROVENANCE` file:
   the research commit and a sha256 per copied file.
2. Add `conformance_test.go` in package `annot`. For each fixture it
   drives `ParseFile → PlanCovers → Apply` on a temp copy (the real
   rewriter), then asserts:
   - **safety = 0**: no look-alike or read-only line classed Comment or
     accepted by `Apply`; no docstring write; no `expect: uncertain` file
     read as certain; after every applied edit, the complete record list
     equals the `.edits` expectation (member, source, stamp, line, origin);
   - **read records** equal the `.expect` `read:` list;
   - **fidelity**: untouched bytes, CRLF, final newline, BOM and file mode
     are preserved on every applied edit;
   - **known costs pinned**: the measured over-refusals and the `x-policy`
     cases are an explicit table in the test. A fix shows up as a test
     change, never silently.
3. The `.expect` / `.edits` parser is a small test-only reader of the
   research format. No production code changes and no new dependencies (the
   goengines allowlist stays `yaml.v3`, `doublestar/v4`, `x/sync`).
4. Negative control: a deliberately mutated classifier (for example,
   heredoc bodies classed Code) fails the test. Record the command and its
   output in the plan's Final Implementation Notes.

## Out of scope

- The research harness, the other four corpus languages, native-oracle
  differentials and benchmarks. Those stay in the research directory.
- The Kotlin multi-dollar fix itself. Its fixtures become pinned known
  failures here until that follow-up lands, or the follow-up lands first.

## Verification

- `cd goengines && go test ./internal/testmap/annot/...` passes.
- The mutated-classifier control fails.
- `go vet` is clean, and `guards_test.go` (the dependency allowlist) is
  unchanged.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1990** id=2026-10-15T06:08:35Z.b53b99969f51c505f58c60b0 from=t1990 from_verified=yes at=2026-10-15T06:08:35Z base=cf210a9e9b70395a794e1597903c34a2937711b1 base_branch=main dirty=yes host=omg16
>
> | t1990 landed as commit cf210a9e9. annot's classifyKotlin (goengines/internal/testmap/annot/lexctx.go) now MODELS the Kotlin 2.2 interpolation prefix exactly, following Kotlin.flex, instead of failing closed.
> | 
> | Effect on this task's scope: at that commit, all four corpus fixtures (kotlin/multidollar_{comment_desync,interpolation,literal_brace,quote_boundary}.kt) meet their .expect:
> | - certain;
> | - the read lists;
> | - the desync line-9 raw edit is refused with ErrNotComment (refused:not-comment).
> | 
> | So your "Out of scope" line ("Its fixtures become pinned known failures here until that follow-up lands, or the follow-up lands first") resolves to the second branch. They can be gated as plain passes rather than pinned failures or over-refusals.
> | 
> | Overlap, intended: the same four sources are inlined as unit rows (ktDollar* constants and 4 TestClassifyKotlin rows in lexctx_test.go, plus TestKotlinMultiDollar and one TestApplyRefusesNonComments case in rewrite_test.go). A corpus copy under testdata/conformance/kotlin/ would duplicate them; keeping both seems fine.
> | 
> | Evidence (archived plan p1990, "Implementation Evidence"): every TestClassifyKotlin row agrees with the 2.3.20 KotlinLexer through an adapter, and old-vs-new classifier parity is 0 differences over 2051 registered-repo Kotlin files.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T06:31:38Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T07:44:37Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-15T11:53:23Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:dcbc68fa583bcb46

> **✅ gate:risk_evaluated** run=2026-10-15T11:53:23Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1991/risk_evaluated_2026-10-15T11:53:23Z-risk_evaluated-a1.log`
