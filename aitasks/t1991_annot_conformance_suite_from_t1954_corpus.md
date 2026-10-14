---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [testing, testmap, go_engine]
anchor: 1852
created_at: 2026-10-14 19:22
updated_at: 2026-10-14 19:22
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
