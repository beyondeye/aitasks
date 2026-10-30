---
priority: medium
effort: high
depends: [t1854_12, t1854_8, t1854_9]
xdeps: [60]
xdeprepo: aitasks_go
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:06
updated_at: 2026-10-30 12:09
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t60_5
in beyondeye/aitasks_go. This body is the framework half.

## Context

Child **M3.2k — Suite reporting contract** of t1854, framework half. Since
the t22 cutover the engine work of M3.2k (the three reporting-contract
formats, attribution through the shared reconciler, the suite-path tests and
the engine README rows) is aitasks_go#t60_5 in beyondeye/aitasks_go, under the
engine-side M3 parent aitasks_go#t60.

This task keeps the one framework deliverable: the **n014 proposal
conformance edit** in `aidocs/testing_engine/n014_explorer_006_proposal.md`.
Both places to edit already state the M3.2k design (added by t1854_2, commit
`c6b1b491c`), so the edit brings them into line with what aitasks_go#t60_5
actually lands; it is not new design:

- the *Reference runners (M3.2)* component (`### Reference runners *(M3.2)*`,
  line ~3437), in the paragraph "A `full: true` suite gets child evidence
  (M3.2k) only from reports its command writes explicitly … JUnit XML, a
  `go test -json` stream, or the engine-native per-test JSONL …" (line
  ~3508);
- **Open Question 8** in `## Open Questions and their v1 defaults` (line
  ~5620: "Default: no per-file evidence without an explicit report — a bash
  suite reports per-file exits through the engine-native per-test JSONL …").
  Open Question 8 stays answered "no per-file evidence without an explicit
  report"; the edit makes its wording match the landed contract.

Line numbers are as of aitasks main at the cutover; re-locate them by
heading before editing.

## Dependencies and ordering

- `depends:` t1854_12, t1854_8, t1854_9 (all archived, satisfied). The
  former edge to t1854_10 (aitasks_go#t60_2) is dropped: that task was re-homed, and its
  replacement is a prerequisite of aitasks_go#t60_5.
- `xdeps: [aitasks_go#t60]` (`xdeprepo: aitasks_go`). It unblocks only when
  aitasks_go#t60 is Done, which happens only when all of its children are Done,
  including aitasks_go#t60_5 and the Postponed device adapter aitasks_go#t60_4. This
  is deliberate: it keeps t1854 (whose last local child this is) from
  archiving before the engine side of M3 closes. The cost is accepted: this
  small spec edit waits for all of M3.
- Before editing, read aitasks_go#t60_5's final plan and Final Implementation
  Notes (and any note it sent here) for the landed contract names, their
  identity mapping, the JUnit collision rule and where the bash JSONL helper
  lives.

## Acceptance

- The *Reference runners (M3.2)* paragraph and Open Question 8 name the
  registered reporting contracts and their identity mapping exactly as
  aitasks_go#t60_5 landed them, including the refusal (or proven uniqueness) of
  colliding JUnit `(classname, name)` keys.
- The spec text describing the engine-native per-test JSONL matches the
  landed format and names its documented helper, wherever aitasks_go#t60_5's
  Step 0 placed it. If the helper ships as a framework script
  (`.aitask-scripts/`) or into target repositories, that part was filed in
  aitasks as its own task; this task only references it.
- No other spec section contradicts them (check at least the *Module Map*
  M3.2k row, line ~786, and the M3.2a row).
- A doc-only commit in aitasks (`documentation: … (t1854_14)`), with no
  change under `goengines/`.
- This body points to aitasks_go#t60_5 (done above).

## Carried obligations (framework half)

- Context / "Proposal Open question 8 is answered 'no per-file evidence without an explicit report'" — *Context*: Open Question 8 keeps that default; the conformance edit aligns its wording.
- Acceptance / Documented formats / "an engine-native per-test JSONL … (a small documented helper may write it)" — *Acceptance*, second item: the spec text describing the format and its helper; the format, parser, README and an engine-embedded helper are aitasks_go#t60_5's.
- Key files / "the proposal (the *Reference runners* component and OQ 8)" — *Context*: the two places to edit.
- Inbox t1854_9 / "JUnit XML (classname, name) keys are NOT collision-safe … must refuse (or prove unique)" — *Acceptance*, first item: the spec wording; enforcement and its test are aitasks_go#t60_5's.
- Inbox aitasks_go#t15 / cutover protocol — the header of this body is the pointer; the engine work moved to aitasks_go#t60_5, and this half's commit is doc-only.

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t60_5 and is quoted for reference only.

> - The engine half owns:
>   - the three reporting-contract formats (JUnit XML, a `go test -json` stream file, an engine-native per-test JSONL), each registered with `runner.RegisterReportingContract`;
>   - translating report entries into candidate `(suite parent, subsumed unit, case identity)` results;
>   - attribution through the shared reconciler (G1a/G1b) against each subsumed runner's own discovery;
>   - refusing unmapped, ambiguous or stale entries, and counting `unaccounted` in `RUN_ACCOUNTING`;
>   - the no-injection rule;
>   - the `goengines/README.md` Interfaces rows and the documented JSONL format (plus its helper if it is engine-embedded).
> - Acceptance:
>   - the suite-path matrix: `{a,a}` → `duplicate_case`; `{a,c}` → `unexpected_case` + `incomplete`; `{a}` → `incomplete`; mixed pass+skip → `pass` with the skip listed; fail+skip → `fail`; absent subsumed unit → `unaccounted`; bash file reported twice → `duplicate_case`; stale report → refused;
>   - isolated mutants (per-unit count matching, report-supplied counters) turn the equal-count cases red;
>   - real-tool tests per format through the real pytest, go and bash adapters (G10);
>   - the command env gains only `AIT_TESTMAP_REPORT_DIR` and the t1854_7 marker (no `BASH_ENV`/`PYTHONPATH`/`PYTEST_ADDOPTS`);
>   - JUnit `(classname,name)` keys are refused or proven unique (t1854_9 note);
>   - suite evidence never uses the file name `cases.jsonl` (t1854_12 note);
>   - the engine tests are green.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_2** id=2026-10-22T08:04:20Z.dfef9825e36e26d08cbfce78 from=t1854_2 from_verified=yes at=2026-10-22T08:04:20Z base=6dc5b76a4681026614ebb8366c455ff7d4915ff1 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_2 (M3.2a), as landed in 6dc5b76a4. Verify the API in internal/testmap/runner/reconcile.go before relying on it.
> | - Reconciler: runner.Reconcile([]Expectation{Key: EvidenceKey{Parent: suite id, Unit: subsumed id}, Cases, ZeroTests, Taints}, []CaseResult{Key, Case, Status, DurationMS, Message}) -> ([]Reconciled, stray). A unit-class subsumed runner: pass Cases = [its own id] per your plan. Report-level faults go in Taints (runner.ReasonMalformedCase / ReasonRejectedReport); report the `stray` results yourself. Reconciled has Status, Reasons (errors), Policy (zero_tests), Counts, Skipped, Complete, Terminal; TestReconcileMatrix already drives child keys.
> | - Register each report format with runner.RegisterReportingContract(name); until then `children:` is RUNNER_INVALID and child rows are invalid_child.
> | - Reports: read through runner.FreshReport(ReportDir, path); the dir is $AIT_TESTMAP_REPORT_DIR / manifest report_dir.
> | - RunAccounting.Unaccounted today counts subsumed units (terminal suite selected, not themselves selected) with no valid child row (accountFor in run.go); swap its source to reconciled child evidence.
> | - The child-row path in ValidateRows (rowContext.Children) is M3.1's; replacing it with the reconciler is yours.

> **✉ note:t1854_5** id=2026-10-22T12:42:23Z.a5cc19f3f781db65d9e6ac6a from=t1854_5 from_verified=yes at=2026-10-22T12:42:23Z base=ed04c92a57296b34828cb90e9af371b88383aae6 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1854_5 (M3.2b shared hang watchdog), landed in commit ed04c92a5. This supersedes your body's carried fact that "`isolated(t, hangLimit)` and its tripwire are unexported test code in package runner; the tripwire parses only runner". Not checked against your plan; re-verify in your Step 0.
> | 
> | - The guard is now `hangguard.Isolated(t, limit) bool`, imported from github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard (test support: only _test.go files may import it). A process-starting top-level test begins with `if !hangguard.Isolated(t, <limit>) { return }`. runner keeps its own `isolated(t, hangLimit)` wrapper, which is also accepted. Each package picks its own limit.
> | - Opt-in is ONE entry in `tripwirePackages` in internal/testsupport/hangguard/tripwire_test.go: {dir, name, localStarters, allow}. goengines/ci/preflight.sh (both workflows, `ait engine test`) then enforces it. A _test.go file importing hangguard from a package with no entry fails preflight (TestIsolationTripwireImports).
> | - The tripwire is lexical. Put in localStarters any entry point that starts processes through methods, interfaces or func fields. Another listed entry's localStarters count as starters for you too: with runner listed, runner.Run and runner.Load are seen in your package.
> | - Hazard for adapters that run test binaries (e.g. go-test): a child process inherits AIT_HANGGUARD_ISOLATE. A child test binary of this module that uses the guard would refuse to run ("runs inside the subprocess of ..."), or run a same-named test unguarded. Clear the variable in such a child's environment.
> | - Details and the full rationale are in the archived plan p1854_5 (Final Implementation Notes, "Notes for sibling tasks").

> **✉ note:t15** id=2026-10-25T08:54:31Z.ba6cfd0020f6061e6763328a from=aitasks_go#t15 at=2026-10-25T08:54:31Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t1854_9** id=2026-10-26T08:06:29Z.7ff6eacc6c4ba113aeb97177 from=t1854_9 from_verified=yes at=2026-10-26T08:06:29Z base=7f49dbd62e8c9ab5ae05de2935184d3bf72256d7 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_9 (M3.2f pytest adapter), as landed in 0c2f693c9. Not checked against your plan.
> | - JUnit XML (classname, name) keys are NOT collision-safe identities. Measured with pytest 8.4.2: `tests/test_a.py::TestC::test_m` and `tests/test_a/TestC.py::test_m` (with --import-mode=importlib) both report classname="tests.test_a.TestC" name="test_m". A module defining the first only under --collect-only and the second only otherwise turns a collect-vs-run substitution into an equal-count "pass" when report entries are mapped onto the *expected* identities. If your JUnit format attributes entries by reconstructing node ids, it must refuse (or prove unique) such keys; mapping only against the expected set is not enough.
> | - The pytest builtin therefore does NOT use JUnit: its evidence is an engine-owned plugin's exact runtime node ids (README row "`pytest` builtin (M3.2f)"). It writes no junit.xml, so real-tool JUnit tests on your path need the project's own `--junitxml`.
> | - Module-level skips appear in JUnit as `classname="" name="tests.test_s"` with `<skipped message="collection skipped">` (a collector, not a test); a test failing then erroring in teardown appears as TWO <testcase> elements for one node id.

> **✉ note:t1854_12** id=2026-10-27T07:02:13Z.1e2caf23298e8c1eb7475b80 from=t1854_12 from_verified=yes at=2026-10-27T07:02:13Z base=aff353fe0e81e10eb613a30540418eb91c820e45 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_12 (M3.2i suite adapter), as landed in commit ecefd276d. Verify against goengines/README.md and runner/builtin/suite.go.
> | - The suite writes no child rows, and its describe fixes `unit: suite`, `accounting: aggregate`, `discovery: inventory`, `timeouts: none`. A runners.yaml override of those four to another value refuses the list. `full` and `children` stay overridable, so a `full: true` suite with your registered `children:` contract needs no change to that rule.
> | - Logs: `unit-0000.stdout` / `unit-0000.stderr` in the invocation's report directory. The command runs as `bash -c <command:>` and inherits `AIT_TESTMAP_REPORT_DIR`, which is where explicit reports would be written.
> | - Under aggregate accounting a `cases.jsonl` the command writes there is refused by t1854_2's invoke path. The unit row keeps the command's status, the invocation gets cause `reconciliation` with detail `cases:refused:cases.jsonl from accounting: aggregate`, and the run exits 1 (TestSuiteCasesFileRefused). Your reporting contract must not use that file name for suite evidence.
> | - Measured with real tools: a `full: true` suite with a `subsumed_by` bash-file runner and no children gives RUN_ACCOUNTING unaccounted = the subsumed units (TestSuiteFullWithoutChildren).

> **✉ note:t22_3** id=2026-10-29T22:22:37Z.5a9af9d4d26f4692be271b37 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:37Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
