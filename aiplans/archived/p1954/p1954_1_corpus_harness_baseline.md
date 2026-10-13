---
Task: t1954_1_corpus_harness_baseline.md
Parent Task: aitasks/t1954_research_multilanguage_annotation_parsers.md
Sibling Tasks: aitasks/t1954/t1954_2_*.md, aitasks/t1954/t1954_3_*.md, aitasks/t1954/t1954_4_*.md
Archived Sibling Plans: aiplans/archived/p1954/p1954_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-12 21:31
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

## Verification of this plan (2026-10-12, at pick time)

Checked against the tree; the plan stands, with these corrections folded into
the steps below:

- **Pin unchanged.** `git log -1 -- goengines/internal/testmap/annot` is still
  `f096db065a7249836c9a82f9d05bbd20fc43b961`; no M2.3–M2.6 change to `annot` yet.
- **API matches.** `Context{Class, Docs, DocEnd, Package, Import, Uncertain}`,
  `DocSpan{StartLine, StartCol, EndLine, EndCol, Raw}` (line/column, not byte
  offsets — the adapter converts `DocLiteral` byte offsets), `LangOf(p, data)`,
  `Classify(Lang, data)` (default branch = `classifyBash`, so an unhooked
  research `Lang` would silently lex as bash — the baseline provider must report
  the extra 4 languages `unsupported` and never run them), `ParseFile` (the only
  caller of `LangOf` + `Classify` besides `Source`), `PlanCovers`, `Placement`,
  `fixedPosition` (default branch = `leading(0)` for any unknown `Lang.Name`),
  `RestampLine`, `ErrDocstring`/`ErrNotComment`/`ErrUncertainContext`/
  `ErrNoMemberBlock`, `ConflictError{Reason: text|snapshot|ownership|concurrent}`,
  `Apply(root, EditSet{Path, Snapshot, Edits})`. `annot/hook.go` is the M2.6
  post-re-stamp hook (unrelated to the seam; untouched).
- **Toolchain.** go 1.27.0 local, `goengines/go.mod` says `go 1.26.0` /
  `toolchain go1.27.1` with `GOTOOLCHAIN=auto` → the research module copies
  both lines; the toolchain actually used is recorded in `environment.md`.
- **Missing tools → adjusted:**
  - `shfmt` CLI is not installed → the bash oracle and the `shfmt` provider use
    the `mvdan.cc/sh/v3/syntax` library in-process (research module dep only).
    Because provider and oracle would then be the same code, the bash
    cross-check's independent evidence is `bash -n` plus controlled execution
    of the heredoc fixtures in scratch; this is stated in `oracle_check.md`.
  - `/usr/bin/time` is not installed → peak RSS comes from re-executing the
    bench as a child process and reading
    `ProcessState.SysUsage().(*syscall.Rusage).Maxrss` (Linux: KiB). The method
    is recorded in `environment.md`.
  - `kotlinc` / `swiftc` absent → kotlinc release zip into scratch, run on the
    local JDK 21; Swift via the official `swift` docker image (docker 29 is
    present), with `-v <scratch>:/w` and `swiftc -parse`. If either fails, that
    language is `native: none`.
- **Isolation evidence (pre-phase 2) already found:** release tarball lists
  explicit dirs (`.github/workflows/release.yml:133-142`, no `aidocs/`);
  `goengines-check.yml:9-23` path filters are `goengines/**` + named files;
  `tests/run_all_python_tests.sh:174,224` discover `tests/test_*.py` only;
  shellcheck targets `.aitask-scripts/aitask_*.sh`. `tests/test_guard_contract_doc_drift.sh:52`
  greps `aidocs/` for fixed banned phrases — the corpus must not contain them
  (the guard is run once after the corpus is written).
- **Guard mechanism made concrete.** The harness references `annot.ClassifyHook`
  / `LangHook`, so it cannot compile against an unpatched snapshot as-is. Files
  that touch the hooks carry `//go:build !unpatched`; the baseline provider and
  the matrix writer do not. A committed `go.unpatched.mod` (+ `go.unpatched.sum`)
  replaces `goengines => ./.baseline-unpatched/goengines`. The guard runs
  `go run -tags unpatched -modfile=go.unpatched.mod ./cmd/t1954 matrix --provider baseline --out <tmp1>`
  and the normal build's baseline matrix into `<tmp2>`, and requires
  byte-identical output (identity header line excluded and compared
  separately: same commit + tree, seam sha differs by design).
- **LangHook scope simplified.** `LangOf` receives the repo-relative path, so the
  hook cannot tell scratch paths from others by location; it maps only the 5
  research extensions (`.ts`, `.js`, `.java`, `.rs`, `.swift`) and returns
  `false` otherwise, so the 4 M2.2 languages always take the landed path. The
  hook is set only inside the harness process.

## Review amendments (user plan review, 2026-10-12 — all three verified valid)

**A1. TypeScript/JS oracle must be parser-aware.** `ts.createScanner` is
context-free: only the parser rescans template continuations
(`reScanTemplateToken`), regex literals (`reScanSlashToken`) and JSX text. A
bare scan loop misreads `}` after `${1}` as a brace, so it reports a fake
`// testmap:covers` inside a template and misses the real comment after the
closing backtick. So `R/oracle/ts_oracle.js` (run with node from the scratch
`node_modules`):
- parses with `ts.createSourceFile(name, text, Latest, /*setParentNodes*/ true, ScriptKind from ext: TS/TSX/JS/JSX)`;
- collects every token leaf by recursive `node.getChildren(sf)`. The parser
  produces template heads/middles/tails, regex literals and `JsxText` as
  single leaves, so no template, regex or JSX byte is ever lexed as trivia;
- builds comment ranges from each leaf's trivia `[leaf.pos, leaf.getStart(sf))`
  as the union of `ts.forEachTrailingCommentRange(text, leaf.pos)` and
  `ts.forEachLeadingCommentRange(text, leaf.pos)`. Leading collection skips
  comments before the first newline when `pos > 0`, so both calls are needed.
  It skips leaves of kind `JsxText` / `JsxTextAllWhiteSpaces`, and includes
  the `EndOfFileToken`'s trivia;
- self-checks full cover: leaf ranges + comment ranges + whitespace must
  partition the file. Any unaccounted non-whitespace trivia byte is an oracle
  error for that file, never a silent result;
- reports diagnostics from `ts.createProgram([file], {noResolve, noLib, allowJs, jsx: preserve})`
  → `getSyntacticDiagnostics(sf)`.

**Validation before it may override hand expectations:**
`R/oracle/ts_selftest/` holds pinned cases with hand-checked answers:
- the reviewer's repro (a template continuation after `${1}` with a fake
  covers line inside, then a real comment after the backtick);
- nested `${`…`}` templates;
- a regex literal containing `//`;
- `/`-division vs regex ambiguity;
- JSX text containing `//` and `/*`;
- a shebang;
- a malformed unterminated template.

The same cases also run through a naive scan loop as a **negative control**,
which must fail at least the template case, proving the self-test can detect
the defect. TS/JS native evidence is used only if every self-test case passes.
Otherwise `native: none` for TS/JS, with the failure recorded.

A malformed fixture where the oracle reports 0 syntactic diagnostics cannot
vouch for uncertainty. That fixture's `expect: uncertain` stays hand-only,
marked as such. **General rule:** every native oracle that overrides a hand
`.expect` first passes a self-test on that language's hardest fixtures,
recorded in `oracle_check.md`.

**A2. Capability contract: anchor availability and certainty are explicit.**
In the shared interface, a zero `Anchors` field means "none", and
`ToContext(lang, src, Result)` cannot see capabilities. So "verified there is
no import block" is indistinguishable from "cannot tell", and a tokenizer's
default zeros would act as placement evidence. Amend the interface:

```go
type AnchorSet uint8 // one bit per Anchors field
const ( AShebang AnchorSet = 1 << iota; AHeaderEnd; APackage; AImportEnd; APrologue; AInnerAttrEnd )
type Capabilities struct {
    TokenRanges, FullCover, Errors, DocLiterals bool
    Anchors AnchorSet // anchors the provider DETERMINES; a declared anchor with value 0 = confirmed none
}
type Need uint8 // NeedLexical | NeedWrite | NeedFreshFileInsert (bit set)
func ToContext(lang string, src []byte, caps Capabilities, res Result, need Need) (annot.Context, error)
```

Requirements follow the real code path, not a blanket level. In the landed
rewriter, `PlanCovers` restamps an existing covers line as a `Replace` without
calling `Placement`. `Placement` returns `u.Last` (block already annotated) or
the member opener before it consults `fixedPosition`. Only the **fresh
file-level insertion** (`member == ""`, `u.Last == 0`) reaches
`fixedPosition`, and with it `Package` / `Import` / `DocEnd`. The proposed
extra-language rules apply only to that case as well. `Apply`/`verifyResult`
never read anchors. So `ToContext` enforces the following itself, and no
caller can bypass it:
- **NeedLexical:** `Spans` only. Python docstring *read* records additionally
  need `DocLiterals`; without it, Python read records are
  `unsupported:DocLiterals` and line classes still score.
- **NeedWrite** (every edit: restamp, member insertion, file-level append,
  fresh file-level insertion): `caps.Errors`, because certainty must be
  established and an empty `Diags` from a provider that does not report
  errors proves nothing. Python also needs `DocLiterals`, because the
  docstring records, the `ErrDocstring` refusal and `Apply`'s doc-shape check
  depend on it. No anchors are needed.
- **NeedFreshFileInsert** (on top of NeedWrite): `requiredAnchors[lang] ⊆ caps.Anchors`.
  The table follows the landed `fixedPosition` and the proposed rules:

  | language | required anchors |
  |---|---|
  | bash | none |
  | Go | `APackage` |
  | Kotlin | `APackage`, `AImportEnd` |
  | TS/JS | `AImportEnd`, `APrologue` |
  | Java | `APackage`, `AImportEnd` |
  | Rust | `AInnerAttrEnd`, `AImportEnd` |
  | Swift | `AImportEnd` |

An anchor not declared in `caps.Anchors` is written into the `Context` as 0,
but it can never reach `fixedPosition`. The edit runner classifies each op
from the parsed file *before* planning it:
- **restamp**: the unit already has a covers line for the source;
- **member insertion**: `member != ""`;
- **file-level append**: `member == ""`, `u.Last > 0`;
- **fresh file-level insertion**: `member == ""`, `u.Last == 0`.

It requests `NeedFreshFileInsert` only for the last kind.

A missing requirement returns `*UnsupportedCapabilityError{Missing: []string}`
(wrapping `ErrUnsupportedCapability`). The runner records `unsupported:<cap>`
for **that op only**, and the remaining ops of the same `.edits` file are
still measured. Declared anchors with value 0 pass through as
confirmed-empty. `placement.go`'s proposed rules read anchors only after the
same check.

Unit and edit-suite tests (`provider/adapter_test.go` +
`cmd/t1954/edit_caps_test.go`, Kotlin fixture through the real seam) pin:
- undeclared anchor → fresh file-level insertion `unsupported:APackage,AImportEnd`;
- with the same capabilities, a restamp, a member insertion and a file-level
  append are measured: applied, with the full record list compared;
- declared-zero anchors → fresh insertion accepted, placed as for "no
  package/imports";
- `Errors=false` → every write `unsupported:Errors`, while Lexical still scores;
- Python without `DocLiterals` → writes and docstring read records unsupported,
  while classes still score.

This amends the parent's shared design. Step 0 below edits the interface block
in `aiplans/p1954_research_multilanguage_annotation_parsers.md` and sends
advisory notes to t1954_2 and t1954_3 (their plans defer to the shared design
and do not restate it).

**A3. Cold vs warm benchmark, and which number meets the budget.**
- **Budget-comparable operation:** exactly what `annot.BenchmarkScan` times.
  That is `registry.Scan(ctx, dir, registry.Inputs{Annotations: annot.Source{}, Lister: emptyLister{}}, false)`
  over the regenerated M2.2 shape: 600 sources, 420 annotated tests (¼ Python),
  1,000 docs, a fresh git repo, and `registry.ConfigPath` = `contract: 1`. A
  provider enters through `ClassifyHook`. Only this end-to-end number is
  compared with the 300 ms budget.
- **Lexical-only timings** (provider `Analyze` + `ToContext`, or
  `annot.Classify`, over preloaded bytes: the M2.2 shape's test files, every
  aitasks bash/Python/Go test file, the sibling sets) are a separate table
  labelled "lexical-only — not comparable to the scan budget".
- **Cold:** each sample is a fresh child process (`t1954 bench-child --mode cold`)
  pinned with `taskset -c 0`. The timer (`time.Now`) starts before provider
  construction and initialization (grammar load, oracle subprocess start) and
  stops after exactly one timed operation; there is no `testing.Benchmark`
  calibration. The parent takes 3 fresh processes and reports the fastest and
  all three, plus peak RSS from each child's rusage. The workload is generated
  once beforehand, so "cold" means a cold process and provider, not a cold
  page cache; this is stated in the results.
- **Warm:** a separate child process runs one untimed warm-up operation, then
  `testing.Benchmark` over the same operation (ns/op), fastest of 3 processes.

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
   or tests `R` (evidence gathered above; re-confirm at commit time):
   - the release tarball / `install.sh` / `aitask_setup.sh` file selection
   - `.github/workflows/*` path filters (`goengines-check.yml`)
   - `tests/run_all_python_tests.sh` discovery: harness Python files must not
     match its pattern (name them `*_oracle.py`, not `test_*.py`)
   - the shellcheck globs, and `test_guard_contract_doc_drift.sh` (scans aidocs)

   Record the evidence (file:line) in `R/README.md` § *Isolation*. If
   something does include `R`, stop and ask the user. Every commit names its
   paths. `git status` must show nothing new outside `R`, and nothing under
   `goengines/` changes.

## Steps

0. **Shared-design amendment (A2).** Edit the *Experimental interface* block
   of `aiplans/p1954_research_multilanguage_annotation_parsers.md`: add
   `AnchorSet`, `Capabilities.Anchors`, `Need`, the new `ToContext`
   signature and its per-operation enforcement rules (anchors only for fresh
   file-level insertion; `Errors` and, for Python, `DocLiterals` for every
   write); replace "`Anchors` zero = none" with
   "zero = none only for an anchor declared in `Capabilities.Anchors`". Commit
   it with `aitask_task_commit.sh` naming that file. Then send `./ait note 1954_2 --from 1954_1`
   and `./ait note 1954_3 --from 1954_1`, saying that the shared interface
   gained explicit anchor availability and a Write-level `Errors` requirement,
   and pointing to the amended section. In the notes, hedge that the harness
   code itself lands with this child's commit.
1. **Module, baseline and identity**
   - `R/go.mod`: module `github.com/beyondeye/aitasks/goengines/t1954research`.
     Use the same `go` / `toolchain` lines as `goengines/go.mod`, and
     `replace github.com/beyondeye/aitasks/goengines => ./.baseline/goengines`.
     `R/go.unpatched.mod` is the same with `./.baseline-unpatched/goengines`.
   - `R/.gitignore`: `.baseline/`, `.baseline-unpatched/`, `.baseline.tmp*/`.
   - `R/baseline/PIN` (key: value lines): `commit`, `tree` (from
     `git rev-parse <commit>:goengines`), `seam_sha256`.
   - `R/baseline/fetch.sh` (bash, `set -euo pipefail`):
     1. read PIN;
     2. `git -C "$(git rev-parse --show-toplevel)" archive <commit> goengines | tar -x -C .baseline.tmp`;
     3. verify the tree id with `git rev-parse <commit>:goengines`;
     4. check `seam.patch` against its sha256, then `patch -p1 --forward`;
     5. write `IDENTITY` (commit, tree, seam sha);
     6. atomically rename the result to `.baseline/`.

     `--unpatched` produces `.baseline-unpatched/` (steps 1–3, 5–6; IDENTITY
     carries `seam_sha256: none`).
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
   - bash: mvdan `syntax` positions (library; no shfmt CLI), `bash -n`, plus
     controlled execution of the heredoc fixtures in a scratch copy.
   - TS/JS: the `typescript` npm package (pinned version) installed into the
     scratch dir; the parser-aware `ts_oracle.js` of amendment A1, gated on its
     self-test + negative control. A bare `createScanner` loop is never used as
     an oracle.
   - Rust and Java: `rustc --emit=metadata` / `javac` validity, and the run
     scripts for the behaviour fixtures.
   - Kotlin: kotlinc release zip into scratch on local JDK 21. Swift: official
     `swift` docker image, `swiftc -parse`. If one cannot be obtained, set
     `native: none` and say so.

   Every disagreement between a hand `.expect` and a native tool is resolved
   in favour of the tool, or explained.
4. **Harness** `R/provider/`, `R/cmd/t1954/`:
   - `provider.go`: the interface from the shared design (`Span`, `Diag`,
     `Anchors`, `DocLiteral`, `DocInfo`, `Capabilities`, `Result`,
     `Provider`).
   - `adapter.go`: `ToContext(lang, src, caps, Result, need Need) (annot.Context, error)`
     per amendment A2. It enforces the per-need capability rules itself (anchors
     only for fresh file-level insertion) and
     does no reconstruction; a missing capability returns
     `*UnsupportedCapabilityError`. Converts `DocLiteral` byte offsets to
     `DocSpan` line/columns and `StmtEnd` to `DocEnd`. `adapter_test.go` pins
     the A2 cases.
   - `langs.go`: research `Lang` values for the extra 4 languages (+ JS),
     served via `LangHook` by extension only (see verification notes).
   - `seam.go` (`//go:build !unpatched`): installs/clears both hooks around
     one provider run.
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
     - `matrix [--provider p] [--lang l] [--out dir]`, written to
       `R/results/matrix_<p>.md` + combined `matrix.md`, safety columns first;
     - `edit`, the edit suite alone;
     - `realrepo --repo <path>`, a read-only walk of git-visible files in the
       known languages, which writes per-provider disagreement counts and
       paths (no contents) to `R/results/realrepo_<repo>.md`;
     - `bench` (+ internal `bench-child`), per amendment A3: the
       budget-comparable end-to-end `registry.Scan` over the regenerated M2.2
       shape; separately labelled lexical-only tables (M2.2 test files, aitasks
       tests, sibling sets); cold = a single timed first operation per fresh
       process including provider init; warm = `testing.Benchmark` after a
       warm-up; `taskset -c 0`; fastest of 3 processes; peak RSS from the
       child's rusage;
     - `footprint`, the probe-binary sizes for the 4 targets;
     - `guard`, as described in the verification notes (byte-identical
       baseline matrices from the unpatched and patched-unhooked builds).
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
   - The bench: only the end-to-end scan (cold and warm) is judged against the
     300 ms budget; lexical-only rows are labelled not budget-comparable.
   - `R/results/environment.md`: date, CPU, nproc, tool versions, module
     versions, the toolchain actually selected, the RSS method, and the PIN
     identity.
   - `R/findings_t1954_1.md`, with observations, documentation claims,
     assumptions and unknowns in separate sections.
7. **README** `R/README.md`: purpose, isolation evidence, prerequisites, and
   the exact rerun commands (`baseline/fetch.sh`, `go run ./cmd/t1954 …`).

## Verification

- `cd R && baseline/fetch.sh && baseline/fetch.sh --unpatched && go vet ./... && go run ./cmd/t1954 guard && go run ./cmd/t1954 matrix`
  reproduces the committed `results/`.
- Corrupting `.baseline/IDENTITY` makes every verb exit 2.
- The baseline matrix shows 0 in every safety column on the 4 M2.2 languages.
  Any non-zero value is a finding about M2.2: record it and send a note to the
  owning task, but do not fix it here.
- `bash tests/test_guard_contract_doc_drift.sh` still passes.
- `go test ./provider/... ./cmd/t1954/...` passes (A2 capability cases,
  including "anchors missing → only fresh file-level insertion unsupported").
- `node oracle/ts_oracle.js --selftest` passes every case, and the naive-scan
  negative control fails the template case (A1).
- `results/bench.md` shows the end-to-end cold/warm rows separately from the
  lexical-only rows, with the M2.2 baseline end-to-end within a sane factor of
  the recorded ≈21 ms (A3 sanity check of the regenerated workload).
- `git status --short` shows paths under `R` only (plus the task and plan
  files).

## Step 9 reference

Commit with a `chore: … (t1954_1)` message naming only paths under `R`. Archive
through the standard child Step 9.

## Risk

### Code-health risk: low
- A Go module (`go.mod`, `go.sum`, harness code) under `aidocs/` could be picked up by tooling it was not meant for (release tarball, CI, python discovery, shellcheck, aidocs grep guards). Verified at pick time that none include it. · severity: low · → mitigation: inline pre-phase scoped_commits_packaging_check
- The shared worktree holds other sessions' uncommitted work (task-data sync already reports unstaged changes); a broad `git add`/commit would absorb it. · severity: low · → mitigation: inline pre-phase scoped_commits_packaging_check

### Goal-achievement risk: medium
- Kotlin and Swift have no local compiler; if the kotlinc zip or the swift docker image cannot be used, their expectations rest on hand oracles. · severity: medium · → mitigation: in-plan (step 3 fetch attempts) + t1954_4 post-phase native_oracle_gap_followup
- A candidate module may prove unbuildable and surface too late to re-scope t1954_2/3. · severity: low · → mitigation: inline pre-phase feasibility_smoke
- The seam patch could alter baseline behaviour. · severity: low · → mitigation: in-plan (`guard` verb: unpatched vs patched-unhooked byte-identical matrices via `-modfile`)
- A synthetic corpus can overfit to the authors' own expectations. · severity: low · → mitigation: in-plan (read-only `realrepo` disagreement runs)
- A context-free native tokenizer used as an oracle can be wrong exactly on the hard cases (TS templates/regex/JSX) and would then override correct hand expectations. · severity: high (pre-review) → low (residual — addressed by amendment A1: parser-aware oracle, self-test with negative control, override only when it passes) · → mitigation: in-plan (A1)
- Zero-valued anchors or empty diagnostics from a provider that cannot determine them would be read as placement/certainty evidence. · severity: high (pre-review) → low (residual — addressed by amendment A2: declared AnchorSet, per-operation enforcement inside ToContext so only fresh file-level insertion needs anchors, adapter + edit-suite tests) · → mitigation: in-plan (A2)
- Cold latency diluted by benchmark calibration, or lexical-only timings judged against an end-to-end budget. · severity: medium (pre-review) → low (residual — addressed by amendment A3) · → mitigation: in-plan (A3)
- The child is large (8 languages × corpus + 4 providers + 6 verbs); an unreached level must be reported "not measured", never omitted. · severity: low · → mitigation: in-plan (results record every cell as pass/fail/unsupported/n-a/not measured)

### Planned mitigations
(Confirmed by the user at parent t1954 planning; carried verbatim.)
- timing: pre-phase | name: feasibility_smoke | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: late-surfacing unbuildable candidate | desc: compile-probe every candidate module (CGO_ENABLED=0, 4 targets; cgo reference on host) before the corpus; re-scope children 2-3 by note
- timing: pre-phase | name: scoped_commits_packaging_check | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tooling pickup of the aidocs Go module; shared dirty worktree | desc: confirm release/install/CI/test discovery exclude the research dir; path-scoped commits only; goengines untouched

## Post-Review Changes

### Change Request 1 (2026-10-13 10:35)
- **Requested by user:** seven verified harness defects (all confirmed by
  reading the code before fixing):
  1. file-mode fidelity sampled the mode only after the op;
  2. a behaviour check that could not run (missing tool / launch failure)
     was scored as "unchanged";
  3. the TypeScript oracle request omitted the file name, so `.ts` parsed as
     `.tsx` (a `<number>1` type assertion lost the following comment);
  4. the native composite silently dropped an unavailable part, while bench
     labels still named it;
  5. raw edit ops bypassed the capability check and discarded hook failures
     (mis-scored as refused:uncertain + corruption);
  6. full-cover evidence accepted duplicate or overlapping leaves that
     happened to rebuild the bytes;
  7. bench `best()` overwrote the accumulated RSS maxima with the fastest
     sample's.
- **Changes made:**
  1. the mode is sampled before the op, with a test seam `afterApply`;
  2. `execResult.diff` reports not-measured, counted in
     `Row.BehaviourNotMeasured` and shown in the matrices;
  3. `oracle.Comments(name, lang, src)` and `Options.Oracle` carry the file
     name, and `ts_oracle.js --serve` refuses a request without one;
  4. `NewComposite` returns an error naming the missing part, and bench
     labels come from the composition actually constructed;
  5. raw ops `Check(NeedWrite)`, and hook failures go through `failErr`
     into unsupported or not-measured (`ProviderError`);
  6. `partitionViolations` requires in-bounds, ordered, contiguous leaves
     from 0 to `len(src)`;
  7. `best()` tracks RSS maxima separately.

  Each fix has a regression test (`internal/runner/review_test.go`, 2 new
  in `caps_test.go`, `provider/composite_test.go`,
  `internal/oracle/oracle_test.go`, `cmd/t1954/bench_test.go`, and a
  `type_assertion.ts` TS self-test case). The guard, matrices, oracle check
  and bench were regenerated. The matrices are numerically unchanged (no
  behaviour check was actually skipped), the oracle check still has 0
  disagreements, and the guard still passes.
- **Files affected:** `internal/runner/{edits.go,range.go,runner.go,caps_test.go,review_test.go}`,
  `internal/report/report.go`, `internal/oracle/{oracle.go,oracle_test.go}`,
  `provider/{composite.go,composite_test.go}`, `oracle/ts_oracle.js`,
  `cmd/t1954/{bench.go,bench_test.go,oraclecheck.go}`, `findings_t1954_1.md`,
  and `results/{guard,matrix*,oracle_check,bench}.md`.

### Change Request 2 (2026-10-13 11:49)
- **Requested by user:** two more verified accounting gaps:
  1. with behaviour checks disabled (`--behaviour=false`), applied edits of
     `exec:` fixtures recorded neither a check nor a skip;
  2. the post-op record re-read ignored the subject's failures and compared
     an empty list, scoring a correct write as corruption.
- **Changes made:**
  1. disabled verification is counted in `BehaviourNotMeasured`, with a
     note, for every applied edit of an `exec:` fixture;
  2. the re-read goes through `failErr`. A failure there makes the records
     "not verified" (`Row.RecordsNotVerified`, shown in the edit-ops cell),
     while the write stays applied and the fidelity and behaviour checks
     still run.

  Regressions: `TestDisabledBehaviourIsNotMeasured` and
  `TestProviderFailingAfterApplyLeavesRecordsUnverified` (a provider
  failing only after `Apply` succeeded, toggled via the `afterApply`
  seam). The committed matrices and guard are byte-identical after
  regeneration (behaviour enabled, no re-read failures).
- **Files affected:** `internal/runner/{edits.go,runner.go,caps_test.go,review_test.go}`,
  `internal/report/report.go`, `findings_t1954_1.md`.

## Final Implementation Notes
- **Actual work done:** all of `aidocs/testing_engine/t1954_parser_research/`:
  - the separate Go module `…/goengines/t1954research`;
  - the immutable baseline: `baseline/PIN`, `fetch.sh`, `seam.patch` with
    exactly two nil hooks, and IDENTITY with commit, tree, seam sha and a
    new **content_sha256** re-checked on every run, plus a build-info check
    of the replace target; exit 2 on any mismatch;
  - the experimental interface + `ToContext` with per-operation capability
    enforcement (amendment A2);
  - providers `goscanner`, `pytokenize` (long-lived `oracle/py_oracle.py`)
    and `shfmt` (mvdan library), and a `native` composite for the bench;
  - the runner: lexical, record, placement, edit (real
    `ParseFile → PlanCovers → Apply` on scratch copies), range and
    behaviour levels;
  - verbs `matrix`, `edit`, `guard` (unpatched vs patched-unhooked via
    `-tags unpatched -modfile=go.unpatched.mod`), `classes`,
    `oraclecheck`, `realrepo`, `bench`/`bench-child` (amendment A3),
    `footprint`, `env`;
  - a 213-fixture corpus in 8 languages, generated by
    `corpus/gen/gen_corpus.py`: 114 fixtures imported from the pinned
    M2.2 fixtures and test tables, plus hand oracles;
  - the parser-aware TS oracle `oracle/ts_oracle.js` with self-test and
    negative control (amendment A1);
  - committed `results/`: feasibility, guard, matrices (baseline +
    3 providers), oracle check, 6 read-only real-repo reports, bench,
    footprint, environment; plus `findings_t1954_1.md` and the README.
- **Deviations from plan:**
  1. Tooling:
     - `shfmt` CLI and `/usr/bin/time` are absent, so the mvdan library is
       used in-process, and RSS is taken in-process (`RUSAGE_SELF`, plus
       `RUSAGE_CHILDREN` as an upper bound, since fork-shared pages inflate
       it);
     - kotlinc 2.4.21 (zip into scratch) and Swift 6.2.4 (docker) WERE
       obtained, so no `native: none`.
  2. Additions to the oracle/metric format:
     - `.expect` key `comments:` (lexical comment lines, metric
       Missed-comment);
     - `x-policy` (real comments the M2.2 policy never treats as annotation
       lines, reported as a policy divergence, not FP-writable);
     - `x-native-differs` (explained native disagreements);
     - `NeedRecords` refines `NeedLexical` (Python docstring records need
       DocLiterals);
     - the stale op's `mutate=` is modelled in the generator.
  3. Corrections to M2.2-derived expectations, decided by bash 5.3
     execution: the `$'E\x4fF'` heredoc delimiter is decoded (line 3 is a
     real annotation), and `$(( cd a\n) )` is valid. M2.2's refusals are
     measured as over-refusal.
  4. The runner counts lexical metrics only when the subject is certain,
     and record corruption only when the file changed.
  5. Two review rounds (Post-Review Changes 1–2) hardened the accounting:
     - the mode is sampled before the op;
     - behaviour that is not run or disabled counts as not measured;
     - the TS oracle gets the file name;
     - the composite refuses a missing part;
     - raw ops are capability-checked;
     - full-cover is an exact partition;
     - bench RSS maxima are kept across samples;
     - records unverifiable after a write are flagged "not verified".
- **Issues encountered:**
  - The generator's first expectations had errors (a prose comment marked as
    look-alike, `syntax@1` on M2.2 cases that pin no line, stale mutations
    not modelled). The native cross-check and the baseline run surfaced
    them; they were fixed in the generator, and a lint now refuses any
    token-bearing line without a hand marker.
  - A benchmark run contended with kotlinc/docker and was discarded; the
    reported bench ran on an idle host.
  - `go run` masks exit codes (shows 1); exit 2 was verified with built
    binaries.
- **Key decisions:**
  - The baseline is never forced into the provider interface: range checks
    are "n/a — not exposed".
  - Research languages reach `annot` only via `LangHook`, by extension.
  - Proposed placement rules for TS/JS, Java, Rust and Swift are labelled
    *proposed*, and the landed default is recorded beside them.
  - Malformed = native tool rejects, or bash's "here-document delimited by
    end-of-file" warning. Grammar-only errors stay `certain`.
- **Upstream defects identified:**
  - `goengines/internal/testmap/annot/lexctx.go:555 — classifyPython does not skip a leading UTF-8 BOM, so a BOM-prefixed module's docstring (and its testmap: records) is not detected (CPython's ast.get_docstring sees it)`
  - `goengines/internal/testmap/annot/rewrite.go:420-432 — fixedPosition then places a fresh file-level line at 0, above the BOM; Apply writes it and the module stops running (SyntaxError U+FEFF). Reproduced in corpus/python/bom_doc.py; exposure today nil (0 BOM files in 5,723 sources across the six surveyed repos)`
- **Notes for sibling tasks:**
  - Add a provider: implement `provider.Provider`, `register` it, and
    declare `Capabilities` honestly (undeclared anchors are unknown). Then
    run `matrix` / `realrepo` / `bench` / `footprint`. Cgo providers go
    behind a build tag.
  - Add cases in `corpus/gen/hand_<lang>.py`, regenerate, then run
    `oraclecheck`.
  - The bench end-to-end subject delegates unsupported languages to the
    landed lexer via `seam.Landed`. That is safe only because
    `annot.Source` is sequential.
  - `annot.Source` fails the whole scan on one refused file, which matters
    for any fail-closed provider in production.
  - shfmt/mvdan findings for t1954_3: a heredoc continuation defect
    (FP-writable), an unterminated heredoc in backticks not flagged, and
    refusals of `$((` subshells and Latin-1.
  - gotreesitter is buildable for all 4 targets; the malivvan wrapper is
    C/C++ only (notes sent).
  - t1954_4 reruns at the then-current `annot` commit: t1853_3 (M2.3) is
    editing `annot` right now, which is exactly why the pin is immutable.
