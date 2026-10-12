---
Task: t1954_1_corpus_harness_baseline.md
Parent Task: aitasks/t1954_research_multilanguage_annotation_parsers.md
Sibling Tasks: aitasks/t1954/t1954_2_*.md, aitasks/t1954/t1954_3_*.md, aitasks/t1954/t1954_4_*.md
Archived Sibling Plans: aiplans/archived/p1954/p1954_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1954_1 — Corpus, oracle, harness and baseline

## Context

First child of t1954. It builds the reproducible research infrastructure every
later child uses, and measures the landed M2.2 baseline (`annot`, `f096db065`).
The **shared design** in `aiplans/p1954_research_multilanguage_annotation_parsers.md`
is authoritative: layout, immutable baseline, evaluation seam, experimental
interface, oracle formats, metrics, corpus coverage and measurement rules.
This plan does not restate it; it orders the work and adds the concrete details.

Research dir (`R` below): `aidocs/testing_engine/t1954_parser_research/`.
Scratch dir for downloads and builds: the session scratchpad, never a system
path and never committed.

## Step 0 — reality check at pick time

- `git log -1 --format=%H -- goengines/internal/testmap/annot`. Pin that commit
  (expected `f096db065` or later).
- Re-read `annot/lexctx.go` (`Context` fields), `lang.go` (`LangOf`),
  `grammar.go` (`ParseFile`), and `rewrite.go` (`Apply`, `PlanCovers`,
  `Placement`, `fixedPosition`, `RestampLine`, `ErrDocstring`). If the API
  moved, adapt the seam patch and the adapter, and record what changed in the
  findings.
- Check for notes sent to t1954_1 (`aitask_query_files.sh inbox 1954_1`).

## Pre-phase (risk mitigations)

1. [feasibility_smoke] In a scratch module, `go get` the latest releases of:
   - `github.com/odvcencio/gotreesitter`
   - a wazero-based tree-sitter wrapper (e.g. `github.com/malivvan/tree-sitter`)
   - `github.com/alecthomas/chroma/v2`
   - `mvdan.cc/sh/v3`
   - `github.com/antlr4-go/antlr/v4`

   Build a one-line probe for each with `CGO_ENABLED=0 -trimpath` for
   linux/darwin × amd64/arm64. Separately, build `github.com/tree-sitter/go-tree-sitter`
   with cgo on the host, and record what fails under `CGO_ENABLED=0`.

   Write `R/results/feasibility.md`: module, version, Go requirement,
   pass/fail per target, error text, and probe binary size. On a failure,
   `./ait note 1954_2` (or `1954_3`) `--from 1954_1` with the evidence, so the
   child is re-scoped before it is picked.
2. [scoped_commits_packaging_check] Show from the sources that nothing ships
   or tests `R`:
   - the release tarball / `install.sh` / `aitask_setup.sh` file selection
   - `.github/workflows/*` path filters (`goengines-check.yml`)
   - `tests/run_all_python_tests.sh` discovery: harness Python files must not
     match its pattern (name them `*_oracle.py`, not `test_*.py`)
   - the shellcheck globs

   Record the evidence (file:line) in `R/README.md` § *Isolation*. If
   something does include `R`, stop and ask the user. Every commit names its
   paths. `git status` must show nothing new outside `R`, and nothing under
   `goengines/` changes.

## Steps

1. **Module, baseline and identity**
   - `R/go.mod`: module `github.com/beyondeye/aitasks/goengines/t1954research`.
     Use the same `go` / `toolchain` lines as `goengines/go.mod`, and
     `replace github.com/beyondeye/aitasks/goengines => ./.baseline/goengines`.
   - `R/.gitignore`: `.baseline/`.
   - `R/baseline/PIN` (key: value lines): `commit`, `tree` (from
     `git rev-parse <commit>:goengines`), `seam_sha256`.
   - `R/baseline/fetch.sh` (bash, `set -euo pipefail`):
     1. read PIN;
     2. `git -C "$(git rev-parse --show-toplevel)" archive <commit> goengines | tar -x -C .baseline.tmp`;
     3. verify the tree id with `git rev-parse <commit>:goengines`;
     4. check `seam.patch` against its sha256, then `patch -p1 --forward`;
     5. write `IDENTITY` (commit, tree, seam sha);
     6. atomically rename the result to `.baseline/`.

     `--unpatched` produces `.baseline-unpatched/` for the guard.
   - `R/baseline/seam.patch`: exactly two nil-by-default exported hooks
     (`ClassifyHook` in `lexctx.go` `Classify`, `LangHook` in `lang.go`
     `LangOf`), and nothing else.
   - The harness checks `.baseline/IDENTITY` against `PIN` on startup and exits
     2 on a mismatch, a missing file or a missing snapshot. It prints the
     identity at the top of every result.
2. **Corpus** `R/corpus/<lang>/` for bash, python, go, kotlin, typescript
   (+ `.js`), java, rust and swift. Every file is named `<case>.<ext>.in`, with
   `<case>.<ext>.expect` and, where it applies, `<case>.<ext>.edits` (formats
   in the shared design).
   - Copy from the pinned commit (`git show <commit>:<path>`):
     - `annot/testdata/parse/*.in`, with `.expect` derived from the `.golden` files;
     - `annot/testdata/placement/*.in`, with the placement anchor and expected
       record list after insertion, from the goldens;
     - the cases embedded in `lexctx_test.go` and `TestDocstringValue`, with
       decoded values, refusals and the explicit write refusal for every
       docstring case.
   - Add the mandatory cases listed in the shared design for every language,
     including the Python `DocEnd` shapes.
   - Every language gets the ordinary, difficult-valid, malformed,
     embedded-language and unsupported-construct classes, plus the edit set:
     member insert, file-level insert, restamp, several members covering the
     same source, the placement guard, an uncertain-file refusal, and a
     stale-plan conflict.
   - Encoding/EOL fixtures: CRLF, no final newline, UTF-8 BOM, Latin-1
     comment bytes, and an executable mode where the language uses one.
3. **Native cross-checks** (`R/oracle/`, results in `R/results/oracle_check.md`):
   - Python: `tokenize` + `ast` (`python3`).
   - Go: `go/scanner`.
   - bash: shfmt / mvdan `syntax` positions, plus controlled execution of the
     heredoc fixtures in a scratch copy.
   - TS/JS: the `typescript` npm package installed into the scratch dir,
     using `ts.createScanner` / `forEachLeadingCommentRange`.
   - Rust and Java: `rustc --emit=metadata` / `javac` validity, and the run
     scripts for the behaviour fixtures.
   - Kotlin and Swift: try a pinned compiler download into the scratch dir
     (the kotlinc release zip; swiftly or a swift.org tarball). If one
     cannot be obtained, set `native: none` and say so.

   Every disagreement between a hand `.expect` and a native tool is resolved
   in favour of the tool, or explained.
4. **Harness** `R/provider/`, `R/cmd/t1954/`:
   - `provider.go`: the interface from the shared design (`Span`, `Diag`,
     `Anchors`, `DocLiteral`, `DocInfo`, `Capabilities`, `Result`,
     `Provider`).
   - `adapter.go`: `ToContext(lang, src, Result) (annot.Context, error)`.
     It does no reconstruction; a missing capability returns
     `ErrUnsupportedCapability`.
   - `langs.go`: research `Lang` values for the extra 4 languages, served via
     `LangHook` only for corpus scratch paths.
   - `placement.go`: the proposed file-level rules for TS/JS, Java, Rust and
     Swift from `Anchors`. Each is labelled `proposed`, and the default
     `fixedPosition` result is recorded next to it.
   - `runner.go`, with three levels:
     - **lexical**: classes vs `.expect`;
     - **range**: only when `Capabilities` declare it;
     - **record/edit**: copy the fixture to a scratch root, run the `.edits`
       ops through `annot.ParseFile → PlanCovers → Apply` with both hooks set,
       building the `InsertAfter` edit for the extra-language file-level case
       only, then compare the **full** `ParseFile` record list, the outcome,
       the bytes and classes of untouched lines, and EOL/BOM/mode.
   - **behaviour**: run the `exec` command before and after, in the scratch
     copy only.
   - `cmd/t1954` verbs:
     - `matrix [--provider p] [--lang l]`, written to `R/results/matrix_<p>.md`
       with the safety columns first;
     - `edit`, the edit suite alone;
     - `realrepo --repo <path>`, a read-only walk of git-visible files in the
       known languages, which writes per-provider disagreement counts and
       paths (no contents) to `R/results/realrepo_<repo>.md`;
     - `bench`, which uses `testing.Benchmark` over the M2.2 shape
       (regenerated like `annot/bench_test.go`), the aitasks test files and
       the sibling sets. It runs cold and warm, takes the fastest of 3, and
       reports peak RSS via a `/usr/bin/time -v` re-exec;
     - `footprint`, the probe-binary sizes for the 4 targets.
   - **Guard** `cmd/t1954 guard`: runs the baseline matrix against
     `.baseline-unpatched` (built with a second module path via `go work`, or
     a copy of the harness module with a different replace) and against
     `.baseline`, unhooked. Byte-identical output is required.
5. **Providers in this child**
   - `baseline` uses the real `annot` with both hooks nil. Its levels are
     class, docstring, anchors, record and edit; range is `n/a — not
     exposed`; the extra 4 languages are `unsupported`.
   - `goscanner` (in-process `go/scanner`): `TokenRanges`, `Errors`.
   - `pytokenize` (subprocess `R/oracle/py_oracle.py`, JSON out): tokenize
     tokens plus an `ast` walk for `DocInfo` (content bounds from STRING
     token prefix/quote parsing, `Raw`, and `StmtEnd` from
     `ast.Expr.end_lineno/end_col_offset` → byte offset).
   - `shfmt` (mvdan `syntax`): comments, heredoc bodies and words with
     positions, and parse errors as `Diags`.
6. **Runs and results**
   - The baseline and native-provider matrices.
   - The guard result.
   - `realrepo` over aitasks, aitasks_go, aitasks_mobile, thinking_app,
     thinking_backend and timexchange (read-only; resolve paths with
     `./ait projects resolve <name>`).
   - The bench against the 300 ms budget.
   - `R/results/environment.md`: date, CPU, nproc, tool versions, module
     versions, and the PIN identity.
   - `R/findings_t1954_1.md`, with observations, documentation claims,
     assumptions and unknowns in separate sections.
7. **README** `R/README.md`: purpose, isolation evidence, prerequisites, and
   the exact rerun commands (`baseline/fetch.sh`, `go run ./cmd/t1954 …`).

## Verification

- `cd R && baseline/fetch.sh && go vet ./... && go run ./cmd/t1954 guard && go run ./cmd/t1954 matrix`
  reproduces the committed `results/`.
- Corrupting `.baseline/IDENTITY` makes every verb exit 2.
- The baseline matrix shows 0 in every safety column on the 4 M2.2 languages.
  Any non-zero value is a finding about M2.2: record it and send a note to the
  owning task, but do not fix it here.
- `git status --short` shows paths under `R` only (plus the task and plan
  files).

## Step 9 reference

Commit with a `chore: … (t1954_1)` message naming only paths under `R`. Archive
through the standard child Step 9.
