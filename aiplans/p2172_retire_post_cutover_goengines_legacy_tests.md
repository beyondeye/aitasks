---
Task: t2172_retire_post_cutover_goengines_legacy_tests.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2172 — Retire post-cutover legacy goengines tests

## Context

Since the aitasks_go#t22 cutover, `goengines/` is an export (EXPORT.txt present,
source aitasks_go@544ed20). An export carries no `ci/`, no tests and no
`testdata/`. Three repository tests still point at subjects that only existed in
legacy mode, and **all three fail today** when run locally:

- `tests/test_goengines_benchci.sh` → `goengines/ci/benchci.sh: No such file`
- `tests/test_goengines_dashcheck.sh` → `goengines/ci/dashcheck.sh: No such file`
- `tests/test_annot_conformance_corpus_sync.sh` → `…/testdata/conformance/PROVENANCE: No such file`

Their private ports (aitasks_go@a0515af, t22_5) are canonical. CI never noticed
because they only run in the legacy `check` job, which is skipped in export mode.

Item 3 evidence: the public `goengines/README.md` "Interfaces" + "Evidence
contract (M3.2)" sections are **identical** to the private canonical copy
(local checkout at aitasks_go@a0515af), except the private copy's 5-line
"Ported verbatim … canonical" note. Public consumers read these shapes:
`.aitask-scripts/aitask_testmap.sh:51` (exit codes, cites README "## Interfaces"),
`aidocs/framework/go_engine.md:8,312-315`, `CLAUDE.md:128`. The private repo is
not publicly readable.

Work on the current branch (`main`, profile fast). No worktree.

## Implementation

1. **Delete the three retired tests** (`git rm`):
   `tests/test_goengines_benchci.sh`, `tests/test_goengines_dashcheck.sh`,
   `tests/test_annot_conformance_corpus_sync.sh`. Keep
   `tests/test_goengines_build.sh`. The research corpus under
   `aidocs/testing_engine/t1954_parser_research/corpus/` stays untouched.

2. **`.github/workflows/goengines-check.yml`**
   - Remove from both `push.paths` and `pull_request.paths`:
     `tests/test_goengines_benchci.sh`, `tests/test_goengines_dashcheck.sh`,
     `tests/test_annot_conformance_corpus_sync.sh`, and
     `aidocs/testing_engine/t1954_parser_research/corpus/**` (it was a trigger
     only for the corpus-sync guard).
   - Header comment: drop "the t1954 research corpus" from the paths sentence.
   - `check` job: remove the steps "benchci.sh tests", "dashcheck.sh tests"
     (+ its "Stubbed:" comment) and "annot conformance corpus sync guard".
     Every other check step stays (gofmt, vet, preflight, pytest pin, go test,
     cross-build, release guard, build.sh tests, export-integrity tests).
   - Untouched: `mode` job, `LEGACY_JOB_IF` gating (fail-closed fallback),
     `export-integrity` job, `bench` job.
   - `bench` comment "promotion criteria in goengines/README.md 'Host
     normalization'" → that section now lives only in the private README; reword
     to "aitasks_go's goengines/README.md".

3. **`tests/test_release_workflow_goengines.py`** (the guard pins the path list
   and the check job's guard set — must move in lockstep with step 2)
   - `CHECK_PATHS`: drop the same four entries.
   - `test_check_job_runs_the_guards`: drop the three retired tests from the
     loop.
   - Add a negative assertion there: none of the three retired paths appears in
     any job's `run:` or in the trigger paths (so a re-added stale step fails
     the guard).
   - Module docstring: remove the corpus-sync / dashcheck clauses.

4. **`aidocs/framework/go_engine.md`**
   - Check-job guard list (~l.187-195): remove the benchci and corpus-sync
     bullets.
   - l.7-8 and "Engine internals" (l.312-315): layout and submodule rules moved
     to aitasks_go's README; say so, and say the public README carries a mirror
     of the consumed interface shapes.
   - l.207 "Host normalization": point at aitasks_go's README.

5. **`goengines/README.md` — record the item-3 decision (public-maintained file,
   so editing it here is allowed and is not drift).** Decision: **keep the
   sections as a documented mirror**, not a pointer. Insert a short paragraph
   between the `## Interfaces` heading and the existing line
   `Shapes other tasks consume, each pinned by the named test.` — that line
   stays verbatim and is the **anchor**: everything above it in either copy is
   the repository-specific note (the private copy's "Ported verbatim…
   canonical" note sits in the same place), everything from it onward is the
   shared contract content. The paragraph says:
   - the canonical copy is aitasks_go's `goengines/README.md`; rows are added
     and changed there first;
   - this copy is a mirror for public consumers (shell callers such as
     `aitask_testmap.sh`, `aidocs/framework/go_engine.md`), who cannot read the
     private repository; it was verified identical at aitasks_go@a0515af;
   - "pinned by" names tests in aitasks_go (an export ships none);
   - refresh: when an export changes a consumed shape, copy the two sections
     from the private README in the same public commit that lands the export;
     if they disagree, the private copy wins.
   - Also add "Interfaces / Evidence contract (canonical)" to the `## Development`
     bullet list of what the private README documents.

Step 9 (Post-Implementation) handles commit, archival.

## Verification

- `python3 -m unittest tests/test_release_workflow_goengines.py` passes.
- Negative control: temporarily re-adding one retired path to a scratch copy of
  the workflow (`AIT_WORKFLOWS_DIR`) fails the new assertion.
- `bash tests/test_goengines_build.sh` and
  `bash tests/test_goengines_export_integrity.sh` pass.
- The three deleted scripts are gone (`ls` fails for each), and
  `.github/workflows/goengines-check.yml` references none of them, neither in
  `on.*.paths` nor in any step's `run:` (`grep -c` = 0 on that file). The only
  remaining references outside archived tasks/plans are the intentional
  negative assertions in `tests/test_release_workflow_goengines.py` and
  task t2172's own text; `aidocs/framework/go_engine.md` has none.
- YAML parses (`python3 -c 'import yaml; yaml.safe_load(open(...))'`).
- The CI half of the task's verification ("a push touching `goengines/**` runs
  green in export mode") can only be observed after push; this repo does not
  push in-task, so it is reported as pending, not claimed.

## Risk

### Code-health risk: low
- Workflow path list and its structure guard must change together; a mismatch
  fails the guard (which is exactly the detection) · severity: low · → mitigation: none (step 3 lockstep + guard run)

### Goal-achievement risk: low
- The public Interfaces mirror can drift from the private canonical copy, since
  nothing public can compare them · severity: low · → mitigation: aitasks_go#83 (interfaces_mirror_drift_check)

### Planned mitigations
- timing: after | name: interfaces_mirror_drift_check | type: enhancement | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: public Interfaces mirror drifting from the private canonical copy | desc: (aitasks_go, via --project aitasks_go) make the export step compare the shared contract content of goengines/README.md's Interfaces + Evidence contract (M3.2) sections against the public aitasks copy — from the anchor line `Shapes other tasks consume, each pinned by the named test.` to the end of the Evidence contract section, excluding each repo's intentional note above the anchor — and report drift; tests: identical contracts with differing notes → no warning, a changed row → warning, a missing anchor in either copy → error (never a silent pass) | created: aitasks_go#83

## Final Implementation Notes

- **Actual work done:** all five plan steps. Deleted the three retired tests;
  pruned their four trigger paths (incl. the t1954 corpus glob) and three
  `check` steps from `goengines-check.yml`; the guard test gained
  `RETIRED_GUARDS` + `test_no_retired_guard_is_named`; `go_engine.md` and the
  public README record that layout/rules/host-normalization live in aitasks_go
  and that the public Interfaces/Evidence sections are a mirror.
- **Deviations from plan:** README note names `ait testmap` and `ait setup`'s
  engine self-check (`lib/engine_install.sh`, `version --json`) as the public
  consumers — verified by grep — instead of "shell callers" generically.
- **Issues encountered:** a first substring-based edit of the guard test
  matched the more-indented copies too and aborted before writing; redone with
  edits scoped to the `CHECK_PATHS` block.
- **Key decisions:** item 3 — keep the public Interfaces/Evidence sections as a
  documented mirror (public consumers cannot read aitasks_go), with the line
  `Shapes other tasks consume, each pinned by the named test.` as the shared
  anchor; each repo's own note sits above it. The legacy `bench` job and
  go_engine.md's bench/scaled-ratio prose stay: the job still exists for the
  fail-closed mode fallback.
- **Upstream defects identified:** None
- **Verification:** `test_release_workflow_goengines.py` 27/27 OK; negative
  control (scratch workflow with a re-added `dashcheck.sh tests` step via
  `AIT_WORKFLOWS_DIR`) fails exactly `test_no_retired_guard_is_named`;
  `test_goengines_build.sh` 107/107; `test_goengines_export_integrity.sh`
  181/181; workflow YAML parses; `goengines_integrity.sh drift` → `DRIFT_NONE`;
  public vs private README identical from the anchor line onward. Before the
  change all three retired tests failed locally (missing subjects). The CI
  half (a push touching `goengines/**` running green in export mode) is
  pending — only observable after push.
- **Risk mitigation (Step 8d):** created cross-repo as aitasks_go#83
  (`t83_interfaces_mirror_drift_check`, committed there as ce58c33). Not
  written to this task's `risk_mitigation_tasks`: that field holds local ids
  only, and `83` would name this repository's t83.
