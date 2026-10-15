---
Task: t1991_annot_conformance_suite_from_t1954_corpus.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1991 — annot conformance suite from the t1954 corpus

## Context

The t1954 research (`aidocs/testing_engine/t1954_annotation_parser_research.md`)
keeps the landed M2.2 readers for bash, Python, Go and Kotlin. Its corpus found
two reader defects that `annot`'s own tests missed: the Python BOM (fixed, t1969)
and Kotlin multi-dollar strings (t1990, **in flight right now in another session
on this host**, pid 2940659, editing `lexctx.go` in this same checkout). Keeping
the hand readers is acceptable only if a reader regression fails `go test`. This
task copies the bash/Python/Go/Kotlin part of the corpus into `annot` and replays
it through the real `ParseFile → PlanCovers → Apply`, the way the research
harness scored the `baseline` subject. No production code changes and no new
dependencies.

Facts this plan rests on (verified during planning):
- The research PIN `3d1a2b628` is still the newest commit touching
  `goengines/internal/testmap/annot/`. The live package is the research baseline
  without the two seam hooks. `results/t4/matrix_baseline.md` is therefore the
  expected result for the live code.
- Corpus: 189 cases, 444 files (bash 69, python 67, go 22, kotlin 31), all
  small. Last changed in `07713a9c445128840b674d7b4d015db60530d591` (t1954_4);
  clean in the working tree. One file is `100755`
  (`bash/exec_mode_edit.sh.in`).
- Baseline deviations at the pin, four languages only (matrix notes):
  - `bash/heredoc_in_backtick_subst.sh`: over-refusal, uncertain@2;
  - `bash/lex_arith_or_subshell_across_lines.sh`: over-refusal, uncertain@1;
  - `bash/lex_heredoc_escape_in_quoted_delimiter.sh`: over-refusal, uncertain@1;
  - `kotlin/multidollar_interpolation.kt`: over-refusal, uncertain@5 (t1990);
  - `kotlin/multidollar_comment_desync.kt`: FP-writable ×3 and record corruption
    ×1. A raw write into line 9 is applied (t1990).
  - `x-policy` lines: `bash/lex_backtick_spanning.sh:2`,
    `bash/lex_continuation_line_is_code.sh:2`, `python/lex_continuation.py:2`,
    `python/tstrings_314.py:5`. None is classed Comment today (the matrix has no
    "policy divergence" note).
- `.in` / `.expect` / `.edits` are not extensions `LangOf` claims, so `knownExt`
  and testmap scans ignore the copies. `TestInvariant5Tripwire` reads only
  non-test `.go` files.
- Name collisions to avoid in package `annot`: `bom`, `oneLine`, `Line`,
  `readFile`, `writeFile`, `golden`, `planOne`, `testStamp`. Every new identifier
  gets a `conf` prefix.

## Implementation

Work on the current branch (profile fast). Paths below are relative to
`goengines/internal/testmap/annot/` unless they start with `goengines/` or
`aidocs/`.

### 1. Copy the fixtures and write PROVENANCE

```bash
R=aidocs/testing_engine/t1954_parser_research/corpus
D=goengines/internal/testmap/annot/testdata/conformance
git diff --quiet 07713a9c445128840b674d7b4d015db60530d591 -- $R/{bash,python,go,kotlin}   # must be clean
mkdir -p $D && cp -p -r $R/{bash,python,go,kotlin} $D/
```

`testdata/conformance/PROVENANCE`, generated with `sha256sum`, sorted by path:

```
# annot conformance fixtures (t1991): byte-for-byte copies of the bash, Python,
# Go and Kotlin fixtures of the t1954 parser-research corpus.
# Lines: <sha256>  <lang>/<file>. conformance_test.go verifies every line and
# refuses files that are not listed.
source: aidocs/testing_engine/t1954_parser_research/corpus
commit: 07713a9c445128840b674d7b4d015db60530d591
measured: annot 3d1a2b628fc07f75b279c0c125ed4705316c9368
<sha256>  bash/bash_members.sh.edits
…
```

Cross-check: `git show <commit>:<R>/<path> | sha256sum` equals the listed hash
for a sample, and the `.in` count is 189. Check that `git ls-files -s` keeps the
copy of `exec_mode_edit.sh.in` at `100755` after `git add`.

### 2. `conformance_reader_test.go`: the test-only reader of the research format

A trimmed port of `aidocs/.../internal/corpus/corpus.go`, keeping its strictness
(unknown keys, duplicate keys and malformed records are errors, so format drift
fails loudly):
- `confRecord` (`line member key value stamp origin`), `String()` with the same
  `fmtValue` quoting rule, and `parseConfRecord`;
- `confExpect` (lang, uncertain, read, writable, readonly, lookalikes, comments,
  refuse, placement, plus `extra` for `x-*` keys; `native` / `exec` / `note` are
  accepted and ignored);
- `confOp` (`annotate|stale|raw`, args, including `new=` and `mutate=`, which
  take the rest of the line, then outcome and after records);
- `parseConfLines` (`3,7,12`, `20-25`, empty);
- `loadConfCases(dir)`, which globs `*/*.in` sorted and reads the data and
  perm mode of each `.in`, its `.expect` (required) and its `.edits` (optional).

### 3. `conformance_test.go`: the driver

The header comment says what the gate is, where the fixtures come from, and how
to refresh them (step 1's commands plus regenerating PROVENANCE). It also says
the rule: a deviation is pinned in `confKnown`, never skipped.

**Per case**, `confCheck(t, c) []string` returns findings. The finding texts are
the research runner's note texts, so a pinned finding can be traced to
`results/t4/matrix_baseline.md`. The case's language comes from
`LangOf(name, data)` and must equal `.expect lang:` (a hard error otherwise).

- **Lexical** (`Classify`): `certain := ctx.Uncertain == nil`.
  - **Safety:** for each look-alike or read-only line that is not `x-policy`, a
    certain context must not class it Comment (`FP-writable: …`). `expect:
    uncertain` with a certain context is `silent-uncertain`.
  - **Cost:**
    - `expect: certain` with an Uncertain context is `over-refusal: valid file
      uncertain at line N (construct)`;
    - a writable line not classed Comment is `missed-writable`;
    - a `comments:` line not classed Comment is `missed-comment`.
  - **Policy:** every `x-policy` line always emits `policy: line N classed
    <Code|Comment|Literal>`. The table must pin it, so a policy change shows up
    as a test change.
- **Records** (`ParseFile(name, data)`):
  - the refusal is compared with research's `sameRefusal` rule (an
    `uncertain@N` matches `uncertain` regardless of N; `syntax` matches the kind
    only) → `refusal: got …, want …`;
  - the read records are compared with `read:` as a multiset → `read: extra …` /
    `read: missing …`;
  - an extra comment-origin record on a look-alike or read-only line that is not
    `x-policy` is `FP-writable: …`.
- **Placement:** for each `placement:` entry, `f.Placement(member)` gives the
  line, and a difference is `placement …`.
- **Edits**, on a scratch copy at `t.TempDir()/tests/<name>` with the `.in`'s
  mode. `from=original` resets the copy; other ops build on the current file.
  - `annotate`: `ParseFile` → `PlanCovers` → `Apply` with the snapshot.
  - `stale`: plan, apply the `mutate=` change (`append:` / `replace:N:`, keeping
    the file's EOL), then `Apply`.
  - `raw`: a direct `Edit` (`replace` / `insert-after`) with `Want` taken from
    the current line.
  - Outcomes are mapped as research's `outcomeOf`, plus `ErrByteOrderMark` →
    `refused:byte-order-mark`. Anything unmapped → `error:`.
  - A wrong outcome is classified as research does:
    - safety: `docstring-write` (want `refused:docstring`, got applied),
      `FP-writable` (want `refused:not-comment`), `silent-uncertain` (want
      `refused:uncertain`), `record-corruption` (any other refused→applied, or
      the default case);
    - cost: `over-refusal` (want applied, got refused);
    - a refusal for a different reason, with the file untouched, is a cost note.
  - After every op the complete record list (`ParseFile` again) must equal
    `after:` in order. A difference is `record-corruption` when the bytes
    changed, otherwise a cost note. A non-applied op that changed the file is
    `record-corruption`.
  - **Fidelity** on every applied op (research's `fidelity`): BOM, final
    newline, mode, the CRLF convention, and exactly one line replaced or
    inserted with every other line byte-identical. A violation is a
    `fidelity: …` finding.
  - Behaviour (`exec:`) is **not run**: the gate is hermetic and launches no
    subprocess. Fidelity covers the byte level.
- **Protected-line write probes**, independent of `.edits`. Some protected
  fixtures have no `.edits` at all (`go/cgo_preamble.go`, `go/embedded_sql.go`,
  …), so without these probes their write path is never exercised.
  - **Scope:** every labelled look-alike or read-only line (146 lines, 107 of
    them covers-shaped) gets one direct `Replace` probe on its **own fresh
    scratch copy**, built from the original `.in` with its mode.
  - **Probe construction**, so that a classifier regression would actually be
    accepted. `render` accepts a `Replace` only on a Comment-class line that
    parses as a covers line owned by `(Member, Source)`.
    - `Want` is the line's text without `\r`.
    - **Covers-shaped** line (after the indent and a line-1 BOM, the language
      leader, optional blanks, `testmap:covers <path>`): `Source` = that path,
      `Member` = the block that owns the line's position (the member of the
      last unit opener above it, `""` when there is none), and `New` =
      `RestampLine(Want, @2026-02-02/bbbbbbbbbb)`. These probes are
      *sensitive*: if the line were misclassified as Comment, `Apply` would
      write it, as it does today on `kotlin/multidollar_comment_desync.kt:9`.
    - **Docstring covers record** on the line (`origin=docstring` in `read:`):
      `Member` / `Source` from the record, and `New` = indent + leader +
      ` testmap:covers <source> <stamp>` (the research raw-op form).
    - **Any other line** (mid-line token, another key, a foreign leader):
      `Source` `src/conformance_probe`, the same `Member` rule and `New`.
      These are refused by `render`'s precondition and only confirm "refused,
      bytes unchanged".
  - **Expected outcome**, from the file's expected state: `refused:uncertain`
    when `.expect` says uncertain (or `refuse: uncertain…`),
    `refused:syntax` for `refuse: syntax…`, and `refused:not-comment`
    otherwise. Every refused probe must leave bytes **and** mode unchanged.
  - **Findings:**
    - applied on a look-alike line is `FP-writable: probe line N applied`, or
      `policy: probe line N applied` for an `x-policy` line;
    - applied on a read-only line is `docstring-write: probe line N applied`;
    - a refusal that changed bytes or mode is `record-corruption`;
    - `refused:conflict` or `error:` is `probe-error` (unpinnable without
      `tracking`). A setup mistake therefore can never pass as a protective
      refusal;
    - any other refusal reason is a cost finding: `probe line N: got X, want
      Y; file untouched`.
  - **Coverage pin:** the count of sensitive probes per language is a constant
    in the test (expected bash 39, python ≈39 minus docstring records, go 13,
    kotlin 16; the exact numbers are measured and pinned). Probe coverage
    therefore cannot shrink silently.

**Known deviations**, a table in the test:

```go
type confPin struct {
	why      string   // the research classification, in one line
	tracking string   // the task that removes it; required for a safety finding
	findings []string // exact finding texts
}
var confKnown = map[string]confPin{ "bash/heredoc_in_backtick_subst.sh": {…}, … }
```

Its entries are the three bash over-refusals, the two t1990 Kotlin cases
(`tracking: "t1990"`) and the four `x-policy` lines. Two probe findings are
also expected in those entries:
- `bash/heredoc_in_backtick_subst.sh:3`: refused:uncertain instead of
  not-comment, a cost;
- `kotlin/multidollar_comment_desync.kt:9`: the probe is applied
  (`FP-writable`, t1990).

**Tests:**
- `TestConformance`: loads the cases and requires the count to equal the
  `.in` lines of PROVENANCE, never 0. It then runs one subtest per
  `<lang>/<name>`, whose sorted findings must equal the sorted pins. The
  failure lists an `unpinned finding: …` and a `pinned but not observed (fixed?
  update confKnown): …`.
  - A table key that names no case fails.
  - A safety-category pin (`FP-writable`, `docstring-write`,
    `silent-uncertain`, `record-corruption`, `fidelity`, `error`) in an entry
    without `tracking` fails. So "safety = 0" holds except for named, tracked
    defects.
- `TestConformanceProvenance`: every listed sha256 matches its file, the files on
  disk under the four language directories equal the listed set, and `commit:`
  is 40 hex characters.
- `TestConformanceCheckerCatches` (harness self-check, no production change):
  - on `go/ordinary.go`, moving writable line 4 into `lookalikes` yields both
    `FP-writable` findings;
  - setting `uncertain` yields `silent-uncertain`;
  - changing op 1's expected outcome to `refused:conflict` yields
    `record-corruption`;
  - dropping a record from op 2's `after:` yields a records-after finding;
  - `confFidelity` on synthetic bytes reports each of BOM, final newline, mode,
    CRLF and an extra changed line;
  - **probe validity (positive controls):** the probe builder aimed at a real
    writable covers line yields `applied` in each language
    (`bash/ordinary.sh`, `python/ordinary.py`, `go/ordinary.go`,
    `kotlin/ordinary.kt`, with at least one member-block line). This proves
    that `Want` / `Member` / `Source` / `New` are well formed, so a protected
    line's refusal comes from protection and not from setup;
  - a probe with a deliberately wrong `Want` is reported as `probe-error`,
    never as a passing refusal.

No `t.Parallel`. `rewrite.go`'s `beforeRename` seam is package-global.

### 4. Measure and pin against committed `annot` only

t1990 may leave uncommitted edits to `lexctx.go` in this checkout. Before
measuring, check `git status --short goengines/internal/testmap/annot/`.
- If any non-test file of the package is modified, measure in an isolated copy:
  `git archive HEAD goengines | tar -x -C <scratch>/iso`, then copy the new
  test files and testdata into it.
- Fill `confKnown` from the measured findings, and cross-check them against the
  per-case notes of `results/t4/matrix_baseline.md`. The expected match is
  exact, apart from the always-on `policy:` lines.
- If t1990 has landed by then, the Kotlin pins follow the new HEAD and the
  `tracking` comment says so.

Never stash, restore or edit `lexctx.go` in the shared tree.

### 5. Negative control (mutated classifier), in an isolated copy only

In a `git archive HEAD goengines` copy plus the new files, apply a one-line
mutation in `lexctx.go` so that bash heredoc bodies are lexed as code: the
pending heredoc is never registered. Then run:

```bash
cd <scratch>/nc/goengines && go test ./internal/testmap/annot/ -run 'TestConformance$' -count=1
```

Expect a FAIL with unpinned `FP-writable` findings on the heredoc fixtures.
Record the exact mutation (diff), the command and the output in the plan's Final
Implementation Notes, then delete the scratch copy. The shared tree's
`lexctx.go` is never touched.

### Post-phase (risk mitigations)

1. [conformance_corpus_drift_guard] Add `tests/test_annot_conformance_corpus_sync.sh`.
   It is a repo-level bash test, so the Go tests stay hermetic: nothing under
   `goengines/` reads `aidocs/`.
   - **Conventions:** `set -euo pipefail`, `enter_scratch_cwd`,
     `tests/lib/asserts.sh`, a `Results:` footer and the `[[ "$FAIL" -eq 0 ]]`
     guard. Assertions run in the parent shell, so the subshell counter opt-in
     is not needed.
   - **`conformance_drift <corpus_dir> <copy_dir>`** prints one line per
     difference and nothing when the two are in sync:
     - `only-in-research:<lang>/<file>` and `only-in-copy:<lang>/<file>`
       compare the file lists (`find -type f`, sorted) of `bash python go
       kotlin`;
     - `content:<lang>/<file>` is a `cmp -s` difference on a common file;
     - `mode:<lang>/<file>` is an executable-bit difference (`[ -x ]` on each
       side) on a common file;
     - `extra-in-copy:<entry>` is any top-level entry of the copy directory
       other than the four language directories and `PROVENANCE`.
   - **Real check:** the function prints nothing for
     `aidocs/testing_engine/t1954_parser_research/corpus` against
     `goengines/internal/testmap/annot/testdata/conformance`. On failure, the
     message names the refresh procedure in the `conformance_test.go` header.
   - **PROVENANCE:** it has a `commit:` line of 40 hex characters. The test
     does **not** require that commit to be the newest corpus commit: matching
     contents are the contract, and the commit is recorded provenance.
   - **Negative controls**, run on `cp -p -r` scratch copies of both trees in
     `$TMP`:
     - a clean scratch pair prints nothing, which proves the copy is sound;
     - an extra research file → `only-in-research:`;
     - an extra copy file → `only-in-copy:`;
     - a changed byte → `content:`;
     - `chmod +x` on a copied fixture → `mode:`;
     - a stray top-level file in the copy → `extra-in-copy:`.

     Each control asserts its specific line.
   - **Verify:** `bash tests/test_annot_conformance_corpus_sync.sh` passes and
     `shellcheck` is clean. The file joins the step-3 code commit.
2. [conformance_corpus_drift_guard] Wire the guard into CI, so that a research
   fixture change can never leave CI green with a stale copy. The Go tests stay
   hermetic: the guard is a repository-level step, never a `go test`.
   - In `.github/workflows/goengines-check.yml`, add to the **identical** `push`
     and `pull_request` `paths` lists:
     - `aidocs/testing_engine/t1954_parser_research/corpus/**` (the research
       corpus);
     - `tests/test_annot_conformance_corpus_sync.sh` (the guard).

     The copied fixtures are already under `goengines/**`. In the `check` job,
     next to the other repository-side guards, add the step:

     ```yaml
     - name: annot conformance corpus sync guard
       working-directory: .
       run: bash tests/test_annot_conformance_corpus_sync.sh
     ```

     Also mention it in the header comment.
   - `tests/test_release_workflow_goengines.py` pins the trigger list exactly
     (`CHECK_PATHS`) and the guards the check job must run. Add both new paths
     to `CHECK_PATHS` and add `tests/test_annot_conformance_corpus_sync.sh` to
     the `test_check_job_runs_the_guards` tuple, so the wiring itself is
     guarded.
   - Update `aidocs/framework/go_engine.md` ("CI:
     `.github/workflows/goengines-check.yml`"): the trigger sentence, and a
     bullet for the new guard in the repository-side guard list.
   - **Verify:** `python3 -m unittest tests/test_release_workflow_goengines.py`
     passes. A scratch-copy negative control (the file's own
     `AIT_WORKFLOWS_DIR` mechanism) shows that removing the new step or the
     corpus path makes it fail.

## Verification

From `goengines/`:
- `go test ./internal/testmap/annot/... -count=1` passes, both in the shared tree
  and in the isolated HEAD copy. If they differ, foreign uncommitted changes are
  the cause; report both.
- `go vet ./internal/testmap/annot/...` is clean. Also run `go vet ./...`. If it
  fails only on other sessions' uncommitted `internal/testmap/runner` files,
  report that and leave them alone.
- `go test -run 'TestDependencyAllowlist|TestInvariant5' . -count=1` passes, and
  `git diff --quiet -- goengines/guards_test.go goengines/go.mod goengines/go.sum`
  shows no change.
- `gofmt -l internal/testmap/annot` prints nothing.
- The mutated-classifier control fails (step 5).
- `bash tests/test_annot_conformance_corpus_sync.sh` passes, and its negative
  controls fire (post-phase).
- `python3 -m unittest tests/test_release_workflow_goengines.py` passes, and its
  scratch-copy control fails without the new step or the new path.
- The commit names its paths:
  `goengines/internal/testmap/annot/conformance_test.go`,
  `conformance_reader_test.go`, `testdata/conformance`,
  `tests/test_annot_conformance_corpus_sync.sh`,
  `.github/workflows/goengines-check.yml`,
  `tests/test_release_workflow_goengines.py` and
  `aidocs/framework/go_engine.md`.
  Message: `test: Add the annot conformance suite from the t1954 corpus (t1991)`.

## Risk

### Code-health risk: low
- New test identifiers in package `annot` could collide with existing test
  helpers (`bom`, `oneLine`, `readFile`, …) and break the package's test build.
  · severity: low · → mitigation: none needed (every identifier is
  `conf`-prefixed, step 2/3)
- The CI wiring edits `goengines-check.yml`, whose trigger list
  `test_release_workflow_goengines.py` pins exactly. The two must change
  together, or the structure guard fails. The change is small and guarded by
  that test. · severity: low · → mitigation: none needed (post-phase step 2
  updates both and runs the guard plus a negative control)
- The pinned table makes t1990's `go test` fail when its Kotlin fix lands
  without a matching pin update. This is the intended "a fix shows up as a test
  change" contract, but it couples two live tasks. · severity: low · →
  mitigation: none needed (advisory note to t1990 at Step 8e)

### Goal-achievement risk: low
- Pins measured while t1990 has uncommitted `lexctx.go` edits in this checkout
  would encode work-in-progress behaviour. · severity: medium · → mitigation:
  none needed (step 4 measures against committed HEAD in an isolated copy)
- A porting slip in the harness could make a check vacuous, so the gate passes
  where the research would flag. · severity: medium · → mitigation: none needed
  (the checker self-test, the mutated-classifier control, and pins cross-checked
  against `matrix_baseline.md`, steps 3–5)
- The research corpus and the goengines copy can drift: a fixture added later to
  the research corpus (report §8.3 trigger) never reaches the gate, and nothing
  flags it. · severity: low (residual: the inline post-phase
  conformance_corpus_drift_guard detects it) · → mitigation: inline post-phase
  conformance_corpus_drift_guard

### Planned mitigations
- timing: post-phase | name: conformance_corpus_drift_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: research corpus and goengines copy drift | desc: repo-level bash test comparing file lists, bytes and executable bits of the four corpus languages against testdata/conformance, with negative controls, wired into goengines-check.yml (corpus + guard in the trigger paths, a check-job step) with the workflow structure guard and go_engine.md updated; PROVENANCE commit recorded but not required to be the newest

## Step 9 reference

The post-implementation steps follow task-workflow Step 9: no separate branch on
the current branch, then the gate/build verification, archival and push.
Step 8e: offer an advisory `/aitask-note` to t1990 (still in flight). It says
that `confKnown` pins its two fixtures with `tracking: "t1990"`, and that
whichever lands second updates those pins. It also says that the four
multi-dollar fixtures are already in `testdata/conformance/kotlin/`.

## Post-Review Changes

### Change Request 1 (2026-10-15 10:05)
- **Requested by user:** (1) the oracle reader silently replaced a second
  `outcome:` / `after:` within one `.edits` op and accepted a reversed range
  (`4-1`) as an empty line list, contradicting the strict-reader guarantee;
  reject both, with focused malformed-input checks. (2) `TestConformance`
  summed sensitive-probe counts inside the selected subtests but compared them
  with full-corpus totals, so `-run` on one case failed; make the coverage
  check selection-independent.
- **Changes made:**
  - `parseConfEdits` rejects a duplicate `outcome:` or `after:` within an op
    (and an empty `outcome:`); `parseConfLines` rejects a reversed range (it
    applies to every `.expect` line list too).
  - New `TestConformanceReaderRejectsMalformed`: 9 malformed `.edits`, 2
    reversed ranges, 5 malformed `.expect`, each with its expected error, plus
    positive controls (two well-formed ops; `3,5-5,7-8`). Against the unfixed
    reader (isolated copy) it fails on exactly the three reported behaviours.
  - The sensitive-probe aggregate moved out of `TestConformance` into
    `TestConformanceProbeCoverage`, which builds (never runs) the probes of
    every case; `confProtected` is shared by both. `-run
    '^TestConformance$/^go$/^ordinary.go$'` now passes.
- **Files affected:** `goengines/internal/testmap/annot/conformance_reader_test.go`,
  `goengines/internal/testmap/annot/conformance_test.go`

## Final Implementation Notes
- **Actual work done:**
  - `goengines/internal/testmap/annot/testdata/conformance/{bash,python,go,kotlin}/`:
    445 files (189 cases: 69 / 67 / 22 / 31), `cp -p` copies of the corpus at
    `07713a9c445128840b674d7b4d015db60530d591` (the `100755` of
    `bash/exec_mode_edit.sh.in` kept). Every one of the 445 PROVENANCE hashes
    was cross-checked against `git show <commit>:<corpus>/<path> | sha256sum`
    (0 mismatches). PROVENANCE header: `source:`, `commit:` (the corpus commit)
    and `research-pin:` (annot `3d1a2b628`, where the research measured).
  - `conformance_reader_test.go`: the strict test-only reader of the
    `.expect` / `.edits` format, plus `TestConformanceReaderRejectsMalformed`.
  - `conformance_test.go`, the gate:
    - `TestConformance` (one subtest per case): lexical, records, placement,
      `.edits` replay through the real `ParseFile → PlanCovers → Apply`,
      fidelity, and protected-line write probes;
    - `TestConformanceProbeCoverage`: sensitive probes per language, pinned at
      bash 39, python 16, go 13, kotlin 16;
    - `TestConformanceKnownTable`: every pin has a why, and a safety pin needs
      `tracking`;
    - `TestConformanceProvenance`: every hash, no unlisted file, no stray
      top-level entry, a 40-hex `commit:`;
    - `TestConformanceCheckerCatches`: the harness self-checks, plus probe
      validity in all four languages (member blocks included) and a malformed
      probe that is a `probe-error`, never a pass.
  - `tests/test_annot_conformance_corpus_sync.sh` (the inline post-phase
    `conformance_corpus_drift_guard`) checks file lists, bytes and exec bits,
    with 7 negative controls (17 assertions). It is wired into
    `.github/workflows/goengines-check.yml`: the corpus and the guard are in
    both trigger lists, and the check job has an `annot conformance corpus sync
    guard` step. `tests/test_release_workflow_goengines.py` pins both
    (`CHECK_PATHS` and the guard list), and `aidocs/framework/go_engine.md`
    documents them.
- **Deviations from plan:**
  - **t1990 landed before the measurement** (`cf210a9e9`, which models Kotlin
    2.2 multi-dollar strings exactly). The four multi-dollar fixtures are
    therefore clean at HEAD, `confKnown` has no t1990 entries, and no pin needs
    `tracking`.
  - Final `confKnown`, which matches `results/t4/matrix_baseline.md` case for
    case:
    - `bash/heredoc_in_backtick_subst.sh`: over-refusal @2, a refusal
      mismatch, and the probe cost on line 3;
    - `bash/lex_arith_or_subshell_across_lines.sh`: over-refusal @1;
    - `bash/lex_heredoc_escape_in_quoted_delimiter.sh`: over-refusal @1 and a
      refusal mismatch;
    - x-policy class readings: `bash/lex_backtick_spanning.sh:2` Literal,
      `bash/lex_continuation_line_is_code.sh:2` Code,
      `python/lex_continuation.py:2` Code, `python/tstrings_314.py:5` Literal.
  - Python has 16 sensitive probes, not "≈39". Most protected Python lines are
    mid-line tokens or docstring content, which get the non-sensitive probe
    forms.
- **Issues encountered:**
  - The first draft of the "look-alike classed Comment" self-check also had to
    drop line 4 from `read:`. The records check flags only *extra* records,
    exactly as research does.
  - The review found that the reader silently replaced a duplicated
    `outcome:` / `after:` and accepted a reversed range, and that the probe
    aggregate depended on `-run` selection. Both were fixed (Post-Review Changes
    above).
- **Key decisions:**
  - Finding texts follow the research runner's notes, so pins can be traced to
    the research matrix.
  - Every finding must be pinned, and a pin that stops occurring fails too.
  - Probes run on a fresh copy each, and expect the file's protective refusal.
    A conflict or an `error:` outcome is a `probe-error`, never a pass.
  - Behaviour (`exec:`) is not run: the gate is hermetic. The drift guard is a
    repo-level CI step, because the Go tests must not read `aidocs/`.
  - All measurements and probes were taken with the `annot` package clean in
    the shared tree (checked before each run); the controls below ran in
    isolated `git archive` copies.
- **Negative control (mutated classifier), recorded verbatim.** In an isolated
  `git archive HEAD goengines` copy plus the new test files and testdata, the
  unmutated copy passed (`ok … annot 0.256s`). Then this mutation (bash heredocs
  never registered, so their bodies are lexed as code):

  ```diff
  --- lexctx.go.orig
  +++ lexctx.go
  @@ -451,7 +451,7 @@
   				return false, &Unclosed{Line: no, Construct: "heredoc delimiter"}
   			}
   			h.line = no
  -			*pending = append(*pending, h)
  +			_ = h // NEGATIVE CONTROL: heredoc never registered
   			i = next
   			wordStart = true
   		case top.kind == 'P' && c == '(':
  ```

  Command: `cd <scratch>/nc/goengines && go test ./internal/testmap/annot/ -run 'TestConformance$' -count=1`
  → `exit=1`, `FAIL github.com/beyondeye/aitasks/goengines/internal/testmap/annot 0.063s`.
  - 17 cases failed: `bash/{edits_members, edits_uncertain, embedded,
    heredoc_matrix, lex_delayed_by_continuation, lex_delayed_by_spanning_quote,
    lex_heredoc, lex_heredoc_ansi_c_delimiter, lex_heredoc_body_continuation,
    lex_heredoc_in_cmdsubst, lex_heredoc_locale_delimiter,
    lex_heredoc_partly_quoted, lex_heredoc_strip_continuation,
    lex_heredoc_strip_quoted, lex_two_heredocs, lex_unterminated_heredoc,
    lookalikes}.sh`.
  - 107 unpinned findings: 58 FP-writable, 18 read, 17 cost, 5 refusal, 4
    record-corruption, 3 silent-uncertain, 2 over-refusal.
  - Excerpt:

    ```
    --- FAIL: TestConformance/bash/embedded.sh (0.00s)
    conformance_test.go:136: unpinned finding: FP-writable: line 4 classed Comment (look-alike/read-only)
    conformance_test.go:136: unpinned finding: read: extra line=4 member= key=covers value=src/py_in_heredoc.py stamp= origin=comment
    conformance_test.go:136: unpinned finding: FP-writable: look-alike/read-only line 4 read as a comment annotation
    conformance_test.go:136: unpinned finding: FP-writable: probe line 4 applied
    ```

  - The write probes alone caught 17 accepted writes in 13 cases. 12 of those
    fixtures have no `.edits` (`bash/embedded.sh`,
    `bash/lex_heredoc*.sh`, …), so without the probes their write path would
    not have been exercised.
- **Second control (a real historical defect).** The same gate, run against
  `git archive 3d1a2b628 goengines` (the pre-t1990 reader), exits 1 on exactly
  the research's Kotlin row, and nothing else changes:
  `kotlin/multidollar_comment_desync.kt` gives FP-writable line 9 classed
  Comment, `read: extra line=9 …`, FP-writable record, FP-writable `op 1 (raw
  …): outcome applied, want refused:not-comment`, `record-corruption: op 1 …:
  records after differ`, and `FP-writable: probe line 9 applied`.
  `kotlin/multidollar_interpolation.kt` gives over-refusal @5, `refusal: got
  uncertain@5, want none`, and `cost: probe line 4: refused:uncertain, want
  refused:not-comment`.
- **Other controls:**
  - the drift guard's 7 scratch-pair controls (in the test itself);
  - the workflow structure guard fails on a scratch workflow without the new
    step (`test_check_job_runs_the_guards`) and without the corpus path
    (`test_triggers_on_everything_the_guards_protect`);
  - `TestConformanceReaderRejectsMalformed`, against the unfixed reader, fails
    on duplicate outcome, duplicate after and the reversed ranges.
- **Verification:**
  - `go test ./internal/testmap/annot/... -count=1` ok (0.3 s);
  - `go vet ./...` clean and `gofmt -l` empty;
  - `go test -run 'TestDependencyAllowlist|TestInvariant5' .` ok, with
    `guards_test.go`, `go.mod` and `go.sum` unchanged;
  - `bash tests/test_annot_conformance_corpus_sync.sh`: 17/17;
  - `python3 -m unittest tests/test_release_workflow_goengines.py`: 9 tests
    OK;
  - `shellcheck -x` clean.
- **Upstream defects identified:**
  - `tests/test_linked_trail_jump_live.sh:164 — no enter_scratch_cwd before the first cd, so tests/test_cd_guard_lint.sh fails (91/92) on HEAD (committed by t1957_4)`
