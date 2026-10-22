---
Task: t1854_2_m3_2_reference_runners.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-22 09:21
---

# Plan: t1854_2 — M3.2a Evidence contract

## Context

M3.2 was re-decomposed on 2026-10-21 around trustworthy test evidence (parent
t1854, *M3.2 re-decomposition*). This child writes guarantees G1–G7 (and the
G10 wording) into M3.1's runner contract **before any production runner
exists**. It registers no builtin. Every other M3.2 sibling consumes it. The
task body `aitasks/t1854/t1854_2_m3_2_reference_runners.md` is authoritative
for the guarantees and acceptance criteria. This plan records Step 0 and the
detailed design.

Automation-first (user directive, 2026-10-11): no path makes a human action a
precondition.

## Step 0 — Reality check (executed 2026-10-21 at main `5582dd4f4`)

Providers inspected on the merge target. M3.1 is t1854_1 `3d1a2b628`, plus
t2080 `6d6b9c8ac` and t1853_4 `1518db768` (axis keys). M3.4 is t1854_4
`487271c89` and t2081 `d9569b6ad`. The hang guard is t1985 `a81352ffb` /
t1998 `b82f4becc`. Nothing in flight touches `goengines/`: none of the 11
tasks in `Implementing` is a testmap task. The aitasks repo has no
`aitestmap/`, so no production `children:` user exists.

| # | task body says | repository has | decision |
|---|---|---|---|
| 1 | Case identities: "case rows in `list`, or a separate `cases` verb" (decide) | `list` = `<id>\t<kind>\t<lowering>[\t<artifact>]`; `case` is not a unit kind | **Case rows in `list`**: `<unit id>\tcase\t<identity>`. One discovery pass yields both, so native collection (pytest `--collect-only`) never runs twice, and it is fresh on every `Load` |
| 2 | Duplicate at discovery → `INPUT_ERROR:lister` | a list error is `RUNNER_PROTOCOL:<r>\|list\|…`, which `scan`/`check` wrap as `INPUT_ERROR:lister\|RUNNER_PROTOCOL:…` (README `list` row) | keep the existing route: `INPUT_ERROR:lister` from scan/check, `RUNNER_PROTOCOL` from `run`, both exit 3 |
| 3 | `FreshReport(path, invStart)` | `readReport` already refuses links, FIFOs and oversize files | `FreshReport(dir, path, start) ([]byte, absent bool, error)`. It needs `dir` to judge "outside". It reads through the same safe open, so there is no check-then-read gap. `start` = the report dir's own mtime taken right after `Mkdir`, the same kernel clock as the files (`time.Now()` vs coarse fs timestamps would false-stale a fresh file) |
| 4 | per_unit runner reports `timeout` as a top-level row; under `cases` top-level rows are refused | contradiction for `cases` + `timeouts: per_unit` | `Validate` refuses `accounting: cases` with `timeouts: per_unit`. No sibling plans that pair (pytest/go/gradle batch, device none) |
| 5 | `children:` refused at load while unregistered | `children:` is an opaque name checked only for `full: true`; child rows accepted whenever `full: true` | `Validate` refuses an unregistered name. Child rows are valid only when `full: true` **and** `children:` is set, so a `full` suite without a contract has its child rows refused (`invalid_child`). Affected tests register a test-only contract: `runner/run_test.go` `TestRunAllSubsumedAndChildren`, `describe_test.go` / `repo_test.go` goldens, `cost/eligibility_test.go` `TestEligibilitySuiteAndChildRows` |
| 6 | Engine derives a `cases` unit's status | `decide` checks exit 0/1/2 against **top-level rows** (`zero_reported`, `exit_mismatch`, `missing`). A clean refusal is exit 75 with nothing emitted and no protocol error | under `cases`, the exit-consistency check reads the **adapter's own case rows**: exit 0 is inconsistent iff a reported case is `fail`/`error`, exit 1 iff none is, exit 2 iff any case row exists. There is no `zero_reported` / `missing` from `decide`: G1a (`incomplete`) and G3 own "nothing reported", and an adapter cannot know the `zero_tests` policy. Derivation runs only after classifying how the runner ended (E), so a clean exit-75 refusal stays `refused`. Reconciliation **errors** become protocol errors and the invocation `cause` (as M3.1 does for `missing`). The G3 **policy** reason (`zero_tests`) never does |
| 6a | G1a "malformed identity", G2 "ambiguous" | M3.1 attributes a malformed `results.jsonl` line to the expected id it still names (`ownID`) and invalidates that unit's earlier result | the same rule for `cases.jsonl`. A malformed line whose `unit` is an expected id → that unit's evidence is `malformed_case` (unit `error`, whatever valid rows it also has). A malformed line naming no identifiable unit → every unit of the invocation is `malformed_case` (G2: ambiguous evidence is never a pass). A line naming a unit outside the manifest stays an invocation-level protocol error. As in M3.1, only an engine kill excuses an unterminated final line as truncated |
| 7 | `zero_tests: error\|skip` on entries | entry keys are strict | new entry key. Set on a non-`cases` runner → `RUNNER_INVALID` (same rule shape as `batch_timeout_s`) |
| 8 | "reason `zero_tests` printed and in the ledger" | `UNIT:` line has 5 fixed fields | new `CASES:<id>\|<expected>\|<passed>\|<failed>\|<errored>\|<skipped>\|<reasons>` line after each `cases` unit's `UNIT:` line. Result/record/ledger gain `reason`. Skipped identities are listed in `--json` / `record.json` only (identities may hold `\|`) |
| 9 | Runner overrides of `accounting` (D6) | a builtin cannot see `runners.yaml` overrides | the engine passes the effective class: manifest `accounting`, env `AIT_TESTMAP_ACCOUNTING` on `list` and `run`, plus `AIT_TESTMAP_REPORT_DIR` on `run` (t1854_14 already names that variable) |
| 10 | `DISCOVERY:` from scan/check | `registry.Listing` (M2.1-owned) has no discovery field | no registry change. `runner.Lister` becomes a pointer type that records the loaded runners' `candidates`, and `scancheck.go` prints `DISCOVERY:` lines (text only; scan/check `--json` unchanged, so M2.x JSON characterizations stay put) |
| 11 | `unaccounted` (G7) before t1854_14 | child rows come from M3.1's row path | `unaccounted` = owned units of every `subsumed_by` runner whose terminal suite has a selected unit, that were not themselves selected and have no valid child row. t1854_14 swaps the row source for the reconciler |
| 12 | Hang guard: process tests under `isolated` | `isolated` is unexported in package `runner`; cost tests cannot call it | new process-starting tests live in package `runner`. The cost changes are tested through the existing `eligRepo`/`judged` helpers, as every current cost eligibility test is |

Ownership re-confirmed: every file below is M3.1's or M3.4's (named
extensions this task's body lists), plus `scancheck.go` / `run.go` (M3.1 /
M2.1 verb files, named in the body), the README and the proposal (M3.2 row,
component, OQ 8, follow-ups).

**Notes to send after the commit** (the decisions above change their
assumptions; hedged, carrying the SHA):
- t1854_6: rows 1, 3, 9, helper names.
- t1854_9, t1854_10, t1854_11, t1854_13: rows 1, 4, 6, 9, and the `cases.jsonl` wire form.
- t1854_12: rows 5, 6.
- t1854_14: the reconciler API, rows 3, 5, 9, 11.

## Design

### A. describe / config (`runner/describe.go`, `config.go`)
- Constants `AccountingCases|Unit|Aggregate`, `DiscoveryNative|Inventory|Candidates`.
- `Describe.Accounting`, `Describe.Discovery`, with defaults `unit` / `candidates` in `defaultDescribe`. Add them to `describeKeys`, the parse switch and `Merge`, so runners.yaml overrides them through the existing D6 path.
- `Validate`:
  - an unknown accounting or discovery value is refused;
  - `cases` + `per_unit` is refused;
  - `children:` must name a registered reporting contract.
- Reporting-contract seam: `RegisterReportingContract(name)` (panics on a duplicate name or an invalid name) and the unexported `reportingContractRegistered`, guarded by a mutex like `RegisterBuiltin`. Test helper `withReportingContract(t, name)`.
- `Entry.ZeroTests` (`zero_tests`, values `error|skip`, default `error`). It is validated in `parseEntry`. `loadRunner` refuses it unless the effective accounting is `cases`.

### B. list case rows (`runner/list.go`, `repo.go`)
- `ParseList` accepts a 3-field row `<unit id>\tcase\t<identity>`.
- `ValidCaseID(s)` is non-empty, valid UTF-8 and has no control character (no tab, no newline). The identity is otherwise free text.
- Case rows attach to `ListRow.Cases` (in file order). A case row naming a unit not listed in the same output is an error. So is a duplicate identity within a unit, which names both lines.
- `loadRunner`: case rows from a runner whose effective accounting is not `cases` are a `RUNNER_PROTOCOL …|list|` error. `list` gets env `AIT_TESTMAP_ACCOUNTING`.
- `Unit.Cases []string` (json `cases,omitempty`), copied in `assign`. A `cases` unit with no case rows has zero expected cases, and G3 applies at run.

### C. Reconciler (new `runner/reconcile.go`) — the API t1854_14 calls
```go
type CaseCounts struct{ Expected, Passed, Failed, Errored, Skipped int }        // json snake_case
type EvidenceKey struct{ Parent, Unit registry.ID }                              // Parent zero = top-level
type Expectation struct {
    Key EvidenceKey; Cases []string; ZeroTests string // ZeroTests "" = error
    Taints []string // evidence-level faults the caller found before reconciling: malformed_case | rejected_report
}
type CaseResult struct{ Key EvidenceKey; Case, Status string; DurationMS int64; Message string }
type Reconciled struct {
    Key EvidenceKey; Status string
    Reasons []string // reconciliation ERRORS only
    Policy  string   // "zero_tests" when G3 decided the status; never an error
    Counts CaseCounts; Skipped []string; DurationMS int64
    Complete bool    // len(Reasons) == 0 (the normal-exit path)
    Terminal bool    // Complete && Counts.Expected > 0 (the kill path)
}
func Reconcile(expect []Expectation, reported []CaseResult) (out []Reconciled, stray []CaseResult)
```
- **Per expected identity (G1a).**
  - An identity needs exactly one result; two or more → `duplicate_case`.
  - A result whose identity is not expected, is invalid, or has a status outside `pass|fail|error|skip` → `unexpected_case`.
  - Each caller-supplied taint is added as a reason: `malformed_case` (a line naming the unit that could not be validated) or `rejected_report` (the report itself was refused, G6). An unknown taint is a programming error and panics.
  - An expected identity with no result → `incomplete`.
  - Reasons come in the fixed order duplicate_case, unexpected_case, malformed_case, rejected_report, incomplete.
  - Because a taint is a reason, rejected or ambiguous evidence always outranks G3: a zero-expected unit with a rejected report is `error`, never a policy `skip`.
  - `Reconciled.Terminal` = no reason and `Counts.Expected > 0` (every expected identity has exactly one terminal result). The kill path reads it (E).
- **Counters (engine-owned).** Only identities with exactly one valid result are counted, by their status. `Expected = len(Cases)`. `Skipped` lists those identities, sorted. `DurationMS` = Σ of the counted durations.
- **Status (G1b).**
  1. any reason → `error`;
  2. else any `fail` → `fail`;
  3. else any `error` → `error`;
  4. else zero expected → G3: `Policy = "zero_tests"`, status `error` (default) or `skip` (`zero_tests: skip`). `Reasons` stays empty, so a G3 outcome is `Complete` and never a protocol error;
  5. else all `skip` → `skip`;
  6. else `pass`.
- **Display.** `Result.Reason` = `Reasons` joined with `,`, else `Policy`.
- **Inputs.** Output follows the expectation order. `stray` holds results whose key matches no expectation; the caller reports them. Keying `(Parent, Unit, Case)` makes child evidence a first-class input.

### D. Freshness (`runner/report_unix.go`)
`FreshReport(dir, path string, start time.Time) (data []byte, absent bool, err error)`:
- refuses a `path` outside `dir` (it uses `filepath.Rel` and also refuses `..`);
- refuses any intermediate component that is not a real directory (`Lstat`);
- refuses a symbolic link (via `readReport`'s `O_NOFOLLOW`);
- refuses an mtime before `start` (stale), using an fstat on the opened handle;
- otherwise reads like `readReport`, with the same cap.

Each refusal returns an error naming why. `absent` = no such file.

### E. Invocation (`runner/invoke.go`, `results.go`, `outcome.go`)
- **Manifest.** It gains `report_dir`, `accounting`, and `units[].cases` (`omitzero`: present as `[]` or the list for `cases` runners, absent otherwise). `idir/report/` is created with `os.Mkdir` (fresh, empty), and its mtime becomes `start`. `run` gets env `AIT_TESTMAP_REPORT_DIR` and `AIT_TESTMAP_ACCOUNTING`.
- **`rowContext`.**
  - Gains `Accounting`. `Full` becomes `Children`: child rows are allowed only for `full` + a registered `children:`.
  - Under `cases`, a top-level result row for an expected id → per-id `result_under_cases` (unit `error`). Start rows stay valid.
- **Case evidence** (`readCases`). After the results.jsonl validation, `<report_dir>/cases.jsonl` is read through `FreshReport`:
  - strict decode of `{"unit","case","status","duration_ms","message"?}` (unknown fields refused; `duration_ms` ∈ [0, 2^40]);
  - only after an engine kill is an unterminated final line ignored as truncated;
  - a FreshReport refusal (stale, link, outside, not regular, oversize, unreadable) → `report:cases.jsonl:<why>` **and** the taint `rejected_report` on every expected unit. An *absent* file is no rejection, so a zero-expected unit keeps its legitimate G3 outcome;
  - non-empty content counts toward `Emitted`.
- **A malformed line (6a).** It is probed for a string `unit` (`json.Unmarshal` into `{Unit *string}`, the `ownID` pattern):
  - an expected unit → the taint `malformed_case` on that unit + `cases:malformed:line N`;
  - no identifiable unit → the taint `malformed_case` on **every** expected unit + `cases:malformed:line N`;
  - a unit outside the manifest → only `cases:unexpected_id|unregistered_id:<id>`.

  A well-formed row naming a foreign unit is that same protocol error.
- **Under `unit` / `aggregate`.** A non-empty `cases.jsonl` → protocol error `cases:refused` (the invocation gets a reconciliation cause). Unit rows are untouched.
- **Under `cases`: classify the end first, then derive.** This is the same order as `decide`. Derivation runs only on a runner that ran and ended on its own terms:
  - **Exit 0/1/2, not killed, started.** `Reconcile` every expected unit not already per-id-invalid. Each gets a derived `Row` (Status, Reason, Cases counts, Skipped, Duration) and is marked reported. Each entry of `Reasons` adds the protocol error `<reason>:<unit>`; `Policy` adds nothing.
  - **Engine kill.** `Reconcile` every unit, then apply a fixed precedence per unit:
    1. **Attributable invalid evidence wins.** Take the reasons minus `incomplete` (duplicate / unexpected / malformed / rejected). If any remain → `error` with those reasons and their protocol errors. What the runner did write is invalid whether or not it was killed.
    2. **Genuinely finished work is kept.** `Terminal` (≥ 1 expected case, each with exactly one result) → the derived status.
    3. **Otherwise the work was unfinished** → `AttributeKill` (timeout / not_started / batch_timeout). That covers an incomplete unit **and a zero-expected unit**: an empty expectation is not proof the unit completed, so G3 never applies on the kill path.

    The record's `killed`, `timed_out` and the timeout bound are kept in every case. A reconciliation error outranks `timeout` as the primary cause, as it already does.
  - **Exit 75, start error, or any out-of-contract exit.** No derivation. A clean exit 75 (nothing emitted, `cases.jsonl` included, and no protocol error) stays `refused`. Exit 75 with emitted evidence or a protocol error stays `exit_mismatch` with the units `missing`. Mechanism exits are unchanged.
- **`decide` under `cases`.** The exit-consistency arm reads `Validation.Cases{Rows int; Failing bool}` (case rows reported; any `fail`/`error` among them) instead of the top-level rows:
  - exit 0 + Failing → `exit_mismatch`;
  - exit 1 + !Failing → `exit_mismatch`;
  - exit 2 + Rows > 0 → `exit_mismatch`;
  - there is no `zero_reported` / `missing` arm, because the reconciler owns them.

  `decide` copies Reason / Cases / Skipped into `Result`. The `unit` / `aggregate` arms are untouched; the pre-phase characterization pins this.
- **Result.** Gains `Reason`, `Cases *CaseCounts`, `SkippedCases`. `MarshalJSON` is updated.
- **Record.** Gains `accounting`, `discovery`, `report_dir`, and `cases` (Σ over the invocation's `cases` units; omitted otherwise).

### F. Run report and output (`runner/run.go`, `cmd/ait-testmap/run.go`, `scancheck.go`)
- `RunReport.Accounting` (`json:"accounting"`) is `RunAccounting{Selected, Cases, Unit, Aggregate, Unaccounted}`. It is computed in `Run` on both the zero-selection path and the normal path. `RunReport.DiscoveryCandidates []string` (`json:"discovery_candidates"`) holds the loaded runners declaring `candidates`, in runners.yaml order.
- **Text output of `run`.**
  - `DISCOVERY:<runner>|candidates` lines come after `RUN:`.
  - A `CASES:` line follows each `cases` unit's `UNIT:` line.
  - `RUN_ACCOUNTING:<selected>|<cases>|<unit>|<aggregate>|<unaccounted>` comes just before `RUN_RESULT`.
- **scan / check.** `runner.Lister` gains a pointer receiver and records `Candidates()` after `List`. `testmapInputs` uses `&runner.Lister{}`. `scanWith`/`checkWith` print `DISCOVERY:` lines before `SCAN:` / the summary lines when the lister is a `*runner.Lister`, so fakes print nothing and the M2.x characterization tests are unchanged.

### G. Ledger and eligibility (`cost/hook.go`, `ledger.go`, `eligibility.go`)
- `ResultRow` gains `accounting`, `discovery` and `reason` (all `omitempty`). They come from the result's unit's runner: the subsumed runner for a child row, and `""` when it is unknown.
- `judge.decide`: just before the clean-tree shortcut, a non-child result whose runner's accounting is `aggregate` → `false, "opaque:aggregate"`. Every earlier reason keeps precedence, and every other decision is unchanged.

### H. Docs
- **`goengines/README.md`, Interfaces table.**
  - Update the rows: `describe` (accounting, discovery, contract-gated `children:`), `list` (case rows), manifest / results (report_dir, `cases.jsonl`, `result_under_cases`, child rows need a contract), `runners.yaml` (`zero_tests`), `run` (DISCOVERY, CASES, RUN_ACCOUNTING), scan (DISCOVERY), cost ledger (accounting / discovery / reason), anchor eligibility (`opaque:aggregate`).
  - New rows: the reconciler, `FreshReport`, `RegisterReportingContract`.
  - Then a `### Evidence contract (M3.2)` subsection below the table, with the G1–G10 guarantee table and the status proves / does-not-prove table (copied from the task body, current-state wording).
- **Proposal `aidocs/testing_engine/n014_explorer_006_proposal.md`.**
  - Replace the M3.2 Module Map row with rows M3.2a–k (the parent's sibling table, mapped to the existing columns).
  - Rewrite *Reference runners (M3.2)* around G1–G10, the classes, and the shapes decided here.
  - Change OQ 8's default to "no per-file evidence without an explicit report (t1854_14)".
  - Add t2117 / t2118 / t2119 to *Named follow-ups (not v1)*.

## Implementation steps

### Pre-phase (risk mitigations)

1. [characterize_default_accounting_unchanged] Before editing any runner file, add `runner/characterize_unit_accounting_test.go` (under `isolated`). It runs one `unit`-accounting fixture repository through `Run` with runners that produce pass, fail, missing (exit 0 without a row), a per-id protocol error (duplicate row), a malformed line naming an expected id, a clean exit-75 refusal, exit 75 with a row, exit 2 with no rows, and a `timeouts: none` engine kill. It pins, as literal expectations taken from today's code:
   - every result's `(id, status, message)`;
   - every record's `cause`, `cause_detail`, `units_reported`, `units_started`, `refused`, `timed_out` and `protocol_errors`;
   - `rep.Exit()`.

   Run it green on the unmodified tree. It must stay green, unedited, after every later step.

### Main steps

1. Describe and config keys, and the reporting-contract seam (A), with tests: `TestDescribeEvidenceKeys`, `TestDescribeRefusesUnknownClasses`, `TestDescribeCasesPerUnitRefused`, `TestChildrenNeedRegisteredContract`, `TestZeroTestsEntryKey`. Fix the existing children tests with `withReportingContract`.
2. List case rows (B): `TestListCaseRows`, `TestListCaseRowsMalformed` (an orphan, a duplicate, a control character) and, through scan, `TestListDuplicateCaseThroughScan` (cmd package; INPUT_ERROR:lister).
3. The reconciler (C) and `TestReconcileMatrix`. Expected `{a,b}`, with reported:
   - `{a,a}` → error [duplicate_case, incomplete];
   - `{a,c}` → [unexpected_case, incomplete];
   - `{a}` → [incomplete];
   - `{a,b,b}` → [duplicate_case].

   Also: pass+skip → pass with skipped [b] and counts {2,1,0,0,1}; fail+error → fail; error+pass → error; all skip → skip; zero expected under error/skip → error/skip with `Policy` zero_tests and **empty `Reasons`, `Complete`**; zero expected with a stray result → unexpected_case; `{a,b}` passing plus the taint `malformed_case` → error [malformed_case] with counts unchanged; zero expected + the taint `rejected_report` under `skip` → error [rejected_report] (never skip); `Terminal` is true only for a reason-free unit with ≥ 1 expected case. The same table runs again with child keys (`Parent` set, two parents sharing a unit id kept apart). Counters are asserted on every row.
4. FreshReport (D) and `TestFreshReportRefusals`: older mtime (Chtimes), a final symlink, a symlinked intermediate dir, `../` outside, an absolute outside path, absent, plus a fresh file that is accepted.
5. Invocation integration (E), with process tests under `isolated`:
   - `TestCasesRunReconciled`: a cases fixture runner writing `cases.jsonl` via `$AIT_TESTMAP_REPORT_DIR`. It covers pass+skip, `{a,a}`, `{a,c}`, a missing file → error incomplete, the CASES line data, the record counters, and the manifest `cases`/`accounting`/`report_dir`.
   - `TestCasesTopLevelRowRefused`.
   - `TestCaseRowsRefusedUnderUnit`.
   - `TestCasesZeroTestsPolicy`:
     - `zero_tests: skip`, alone, adapter exit 0 → unit `skip`, reason `zero_tests` (CASES line, record, result), no cause, `rep.Exit()` 2. The same with adapter exit 2 → no cause, Exit 2;
     - `skip` beside a passing cases unit → Exit 0;
     - default `error` → unit `error` reason `zero_tests`, no cause, Exit 1.
   - `TestCasesMalformedEvidence`:
     - complete passing rows for `{a,b}`, then a malformed line naming the unit (`{"unit":"u","case":"a","status":"bogus","duration_ms":1}`) → unit `error` reason `malformed_case`, cause reconciliation `cases:malformed:line 3`, Exit 1;
     - a malformed line naming no unit (`{"case":` truncated, normal exit) → every unit of the invocation `error` `malformed_case`;
     - a well-formed row for a foreign unit → invocation protocol error, the unit's own derived status kept.
   - `TestCasesRefusal`:
     - a cases runner that exits 75 and emits nothing → `Refused`, no cause, units `refused`, Exit 75;
     - exit 75 with a `cases.jsonl` row → not refused, cause `exit_mismatch`, units `missing`, Exit 1.
   - `TestCasesExitConsistency`:
     - exit 0 with a failing case → `exit_mismatch`;
     - exit 1 with all passing → `exit_mismatch`;
     - exit 1 with a failing case → no cause.
   - `TestCasesStaleReport`:
     - the runner `touch -d` backdates `cases.jsonl` (with otherwise complete passing rows) → units `error`, reason `rejected_report`, cause reconciliation `report:cases.jsonl:…`, Exit 1;
     - a symlinked `cases.jsonl` → the same;
     - a zero-expected unit under `zero_tests: skip` with a stale report → `error` `rejected_report` (not `skip`), cause reconciliation, Exit 1;
     - the same unit with no `cases.jsonl` at all → `skip` `zero_tests`, no cause, Exit 2.
   - `TestCasesKilledAttribution` (`timeouts: none` singletons, the runner sleeps past `timeout_s`):
     - complete passing rows, then hang → `pass` kept, `killed`/`timed_out: unit` recorded;
     - one of two cases reported, then hang → `timeout`;
     - a zero-expected unit (`zero_tests: skip`) that hangs → `timeout`, not `skip`;
     - complete passing rows plus a newline-terminated malformed line naming the unit, then hang → `error` `malformed_case` with cause reconciliation **and** `timed_out: unit` / `killed` retained;
     - a batch runner killed with start rows → the started unit `timeout`, the unstarted `not_started`.
   - `TestReportDirFreshPerInvocation`.
   - Update `TestValidateRows`'s child cases to the `Children` flag.
6. Run report and output (F): `TestRunAccounting` (selected by class and unaccounted with a subsumed runner missing one child row), and in the cmd package `TestRunThroughBinary` (DISCOVERY, RUN_ACCOUNTING; a JSON `accounting` check) and `TestScanCheckRealLister` (DISCOVERY lines).
7. Ledger and eligibility (G): `TestEligibilityAggregateNeverAnchors` (clean and dirty tree), `TestLedgerRecordsAccountingDiscovery`. `TestEligibilitySuiteAndChildRows` registers a test-only contract in a cost `_test.go` `init`. Every other eligibility test stays green.
8. **Isolated mutants.** Each runs in a scratch copy of one file (backup → sed → `go test -run` → restore from the backup → `cmp` byte-identical; never `git restore`). Each must turn the named test red:
   - count-only reconciliation, and counters taken from the raw rows (G1a) → `TestReconcileMatrix`;
   - zero expected → pass (G3) → zero-tests tests;
   - incomplete applied as pass (G2) → matrix + `TestCasesRunReconciled`;
   - malformed-line attribution dropped (G2) → `TestCasesMalformedEvidence`;
   - derivation moved before end-state classification → `TestCasesRefusal`;
   - `Policy` appended as a protocol error → `TestCasesZeroTestsPolicy`;
   - the `rejected_report` taint dropped → `TestCasesStaleReport` (zero-expected row);
   - the kill path applying `Complete` instead of `Terminal`, and the kill path dropping step 1 → `TestCasesKilledAttribution`;
   - the `result_under_cases` check dropped (G2) → `TestCasesTopLevelRowRefused`;
   - each FreshReport check dropped: mtime, symlink, outside (G6) → `TestFreshReportRefusals` / `TestCasesStaleReport`;
   - the contract check in `Validate` dropped, and the child-rows-without-contract check dropped (G7) → the contract tests;
   - the `opaque:aggregate` check dropped → the eligibility test.

   Record each result in Final Implementation Notes.
9. Docs (H).
10. `cd goengines && go vet ./... && ait engine test` (which runs the preflight tripwire) green; `shellcheck` is n/a.
11. Step 9 (Post-Implementation): archival on the current branch, no merge. After the commit, send the sibling notes listed in Step 0.

## Risk

### Code-health risk: medium
- `ValidateRows` / `decide` / `invoke` are M3.1's load-bearing outcome path. The derived-row injection, the cases exit-consistency arm and the `Children` gate could shift outcomes for default (`unit`) runners that should be untouched · severity: low (residual — addressed by inline pre-phase characterize_default_accounting_unchanged) · → mitigation: inline pre-phase characterize_default_accounting_unchanged
- The Result / Record / ledger schemas grow. Every new ledger field is `omitempty` and is read with a non-strict decode, so old ledgers fold unchanged · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The reconciler API is designed before its second caller (t1854_14) exists. The child-report translation could need a different shape · severity: medium · → mitigation: none (keyed `(Parent, Unit, Case)`; t1854_14's Step 0 re-checks it; a note is sent)
- The case-rows-in-`list` protocol binds four adapters (t1854_9/10/11/13) before any of them is written · severity: low · → mitigation: none (notes; each adapter's Step 0)
- mtime staleness on unusual filesystems (NFS, a clock step) can refuse a fresh report. That fails closed (`error`, never `pass`) · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_default_accounting_unchanged | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: M3.1 outcome-path regression for default runners | desc: pin unit-accounting run outcomes before the evidence changes and keep them green

## Verification
- `bash -c 'cd goengines && go test ./internal/testmap/runner/... ./internal/testmap/cost/... ./cmd/ait-testmap/...'`, then `./ait engine test`. The last line must be green.
- Mutant table recorded with red/green per mutant and a `cmp` restore check.
- `goengines/README.md` rows name every new test. The proposal renders: the M3.2a–k rows sit in the M3 Module Map table, and the section markers are intact.
- Acceptance-criteria walk in Final Notes: one line per criterion → the test or file that meets it.
