---
Task: t1770_harden_check_link_relevance_self_verification.md
Base branch: main
Output branch: main
---

# t1770 — Make `--report` fail closed; un-strand the test module's `unittest.main()`

## Context

Two defects share one shape: **a run reports success while a large part of it
never executed.** (t1790 is folded in; it names the same two defects.)

1. `website/check_link_relevance.py:642-643` — `main()` returns `0` for `--report`
   before `evaluate_controls(result)` at `:671`. Measured today: `--report` exits 0
   and prints 0 control lines, so a collapsed extractor or resolver emits an empty
   machine-readable report that reads as success. This contradicts
   `website/README.md:211-213` ("exits non-zero only when one of its own
   self-controls fails … prints every control on every run"). The flag's `--help`
   ("print records only, no summary or controls") disagrees with the README.
2. `tests/test_check_link_relevance.py:865-866` — the `__main__` guard sits
   mid-file. Measured today: direct execution `Ran 55 tests`, discovery `Ran 70`.

**Contract resolution (README vs `--help`):** the **exit status** is the
authoritative contract and it holds in every mode — a failed self-control exits 1,
`--report` included. What `--report` suppresses is **display**: its stdout stays
records only (machine-readable), and a failed control is named on **stderr**. Code,
`--help`, docstring and README all get rewritten to say exactly that.

**Constraints carried in (t1759 / t1768 notes):**
- The report never gates: misses still exit 0; only a failed control exits 1.
- `scan()` stays control-free — `check_link_relevance_history.py` replays through
  `scan()` + `ENGINE_CONTROLS` and never calls `main()`/`--report`. Controls are
  evaluated in `main()` only.
- `CONTROLS` / `ENGINE_CONTROL_NAMES` / `ENGINE_CONTROLS` / `CORPUS_CONTROLS` are
  not touched.

Mode: current branch (profile `fast`), no worktree.

## Implementation

### 1. `website/check_link_relevance.py`

- In `main()`, right after `result = scan(content_dir)`, evaluate the controls
  once:
  ```python
  controls = evaluate_controls(result)
  failed = [name for name, ok in controls.items() if not ok]
  ```
  (still outside `scan()`).
- Extract the existing stderr failure block into a helper so both modes share it:
  ```python
  def _report_failed_controls(failed: List[str]) -> int:
      """Name each failed control on stderr; 1 if any failed, else 0."""
      if not failed:
          return 0
      # ANY failed control, not all of them: … (existing comment, moved verbatim)
      print("\nFAILED CONTROL(S) -- this run proves nothing about the content:",
            file=sys.stderr)
      for name in failed:
          print(f"  - {name}", file=sys.stderr)
      return 1
  ```
- Report branch becomes:
  ```python
  if args.report:
      # stdout stays records only, for a machine reader -- but the controls ran
      # above, so a collapsed extractor fails closed here as it does in a full run.
      return _report_failed_controls(failed)
  ```
- Full mode keeps its output order unchanged: records, warnings, verbose list,
  summary, `control :` lines, then `rc = _report_failed_controls(failed)`; if
  `rc` return it, else print the "Relevance is a heuristic" footer and return 0.
- `--help` for `--report`: `"print records only on stdout; controls still run,
  and a failed one exits 1 and is named on stderr"`.
- Module docstring: usage line → `--report  # records only on stdout; a failed
  control still exits 1`; the exit-status paragraph ("exits non-zero only when …")
  gains "in every mode, `--report` included".

### 2. `website/README.md` (≈ lines 208-213)

Rewrite the last sentence of "It is a report, not a gate." to the resolved
contract (current-state only, no history): exits non-zero only when a self-control
fails, **in every mode**; a full run prints every control; `--report` keeps stdout
to the records alone, but still evaluates every control and names a failed one on
stderr.

### 3. `tests/test_check_link_relevance.py`

a. **Move the guard to the physical end of the module** and put a t1518-style
   comment above it (why mid-file is wrong: `unittest.main()` calls `sys.exit()`,
   so classes below are never defined under direct execution, while discovery is
   unaffected). Delete the now-obsolete t1768 comment at `:651-653` ("These
   classes sit ABOVE the stranded guard …"), keeping the section header line.

b. **`ControlFailureTests._run_cli(self, controls, *extra_args)`** — append
   `extra_args` to `argv` so report-mode tests reuse it.

c0. **Pin the normal-mode half of the display contract** (verified gap: no test in
   this module asserts a `control :` stdout line; `ControlFailureTests` checks only
   stderr names and exit codes, and the one `": False"` assertion in the repo,
   `tests/test_check_link_relevance_history.py:229`, pins the *history* script's
   output, not `main()`). Without this, a refactor that makes `--report` fail
   closed but drops or bypasses the full-mode control display passes every other
   test while violating the rewritten README. New
   `ControlFailureTests.test_normal_mode_prints_every_control_verdict_exactly_once`:
   patched controls with **mixed** verdicts (first `False`, rest `True`, so a
   hard-coded `True` cannot pass), run `main()` without `--report`, then for each
   name assert the exact line `f"control       : {name}: {verdict}"` occurs
   **exactly once** in stdout, and that the number of stdout lines starting with
   `control` equals `len(CONTROL_NAMES)` (no duplicates, no extras). The
   report-mode counterpart ("emits none") is in (c) below; the two together pin
   both sides of the display split.

c. **New `ReportModeControlTests(SiteTestCase)`** (above the guard), with a
   fixture that yields one reported miss so stdout is never vacuously empty:
   - `test_each_control_failing_alone_fails_report_mode` — per control (subTest),
     `--report` returns 1, the failing name is on stderr, no passing control is
     blamed, and stdout has **no** `control` line and **no** `links checked` line.
   - `test_all_controls_passing_exits_zero_with_records_only` — rc 0, stdout is
     non-empty and every non-blank line is a record line (`"  ->  "` in it).
   - `test_report_mode_evaluates_every_control` — spy predicates record calls;
     each is called exactly once (the defect was "controls never called").
   - `test_misses_alone_do_not_fail_report_mode` — the report-never-gates
     constraint, pinned for `--report` specifically.
   Reuses `ControlFailureTests.CONTROL_NAMES` and the `patch.object(clr,
   "CONTROLS", …)` pattern already in the file.

d. **New `EntryPointAgreementTests(unittest.TestCase)`** (above the guard) —
   asserts direct execution and discovery collect the same tests, structurally:
   - module helper `_defs_after_main_guard(source) -> Optional[List[str]]` parses
     with `ast`, finds the top-level `if __name__ == "__main__":`, returns the
     names of top-level `ClassDef`/`FunctionDef` after it (`None` if no guard).
   - `test_guard_is_the_last_statement_of_this_module` — reads `__file__`: guard
     exists, it is `tree.body[-1]`, and nothing is defined after it. Direct
     execution defines exactly what precedes the guard, so this is the count
     agreement by construction.
   - `test_helper_detects_a_stranded_class` — negative control on a synthetic
     source string with a class after the guard → reported by name.
   - `test_helper_reports_a_missing_guard` → `None`.
   Why AST and not a subprocess count comparison: a direct-run subprocess would
   execute this very test and recurse, and needs env-var plumbing to stop it.

## Out of scope → Step 8b upstream defects

A scan of `tests/**/*.py` found three more modules with the same stranded guard.
They are other tasks' files and will be listed under "Upstream defects identified",
**not** fixed here:
- `tests/test_minimonitor_own_mark.py:786` — 2 classes after the guard
- `tests/test_monitor_finalize_offload.py:418` — 1 class after the guard
- `tests/test_shadow_seam.py:1263` — 4 classes after the guard
A repo-wide AST guard test is the natural follow-up, but it can only land after
those three are fixed (it would fail immediately today), so it is not added here.

## Verification

1. `python3 tests/test_check_link_relevance.py` and
   `python3 -m unittest discover -s tests -p test_check_link_relevance.py` →
   identical `Ran N` (70 + the new tests), both `OK`.
2. **Red proof, isolated** (no probe in the shared tree): copy the *pre-fix*
   `check_link_relevance.py` (`git show HEAD:website/check_link_relevance.py`) and
   the new test module into a scratchpad `website/` + `tests/` layout, run the
   report-mode tests there → they fail (rc 0 / controls never called). The same
   tests pass against the fixed script.
   The normal-mode display test (3.c0) is a **regression pin**, green both before
   and after the fix, so its red proof is a mutant instead: in the same scratchpad
   layout, a copy of the *fixed* script with the `control :` print loop deleted
   → that test fails and every report-mode test still passes. This is exactly the
   refactor it exists to catch.
3. `cd website && python3 check_link_relevance.py --report; echo $?` → records,
   exit 0, no `control` lines. `python3 check_link_relevance.py` → 6 `control …:
   True` lines, exit 0 (live corpus confirmed passing all controls today).
4. `python3 tests/test_check_link_relevance_history.py` → still passes (replay
   path untouched).
5. No `website/content/` change, so `check_links.py` is not required.

## Step 9

Post-implementation: current-branch mode (no merge), build verification via the
gate orchestrator (`ait gates run 1770`), archival via
`aitask_archive.sh 1770`, which also deletes folded t1790.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned. `main()` evaluates the controls right after
  `scan()` (never inside it) and both modes route failure through
  `_report_failed_controls()`; `--report` keeps stdout to records only and exits 1
  on a failed control, naming it on stderr. Full-mode output order is unchanged.
  `--help`, the module docstring and `website/README.md` state the one resolved
  contract. The `__main__` guard now ends the test module; the obsolete t1768
  "sit ABOVE the stranded guard" comment is gone. New tests: the normal-mode
  display pin (`ControlFailureTests.test_normal_mode_prints_every_control_verdict_exactly_once`),
  `ReportModeControlTests` (4) and `EntryPointAgreementTests` (3, incl. two
  negative controls on synthetic source). 70 → 78 tests.
- **Deviations from plan:** (1) Step 3.c0 — the normal-mode display pin — was
  added at plan review on the user's request, after verifying no existing test
  asserted a `control :` stdout line. (2) `ControlFailureTests._run_cli` gained
  `*extra_args` as planned, but `ReportModeControlTests` ended up with its own
  `_run_report` because its fixture must yield a reported miss (so "stdout is
  records only" is never vacuous); `extra_args` is currently unused. Left as-is
  rather than changing reviewed code after approval.
- **Issues encountered:** None in the code. At claim time `aitask_pick_own.sh`
  warned that the task-data sync failed (data worktree had unstaged changes
  blocking rebase) — non-blocking, ownership was acquired.
- **Key decisions:** The exit status is the authoritative contract in every mode;
  `--report` suppresses display only. Entry-point agreement is asserted on the
  source via `ast` (guard is the last statement, nothing defined after it) rather
  than by comparing subprocess runs, which would recurse into the test itself.
  `scan()`, `CONTROLS`, `ENGINE_CONTROL_NAMES` and the ENGINE/CORPUS split are
  untouched (t1768's replay contract).
- **Verification results:** direct run and discovery both `Ran 78` / `OK`;
  `tests/test_check_link_relevance_history.py` 13 OK; live corpus `--report` rc 0
  with 0 control lines, full run rc 0 with 6 `True` controls. Red proofs, all in
  isolated scratchpad copies: pre-fix script → report-mode tests fail (7
  failures: every failing control returned 0, and no control was called);
  display-loop mutant → only the normal-mode pin fails; guard re-stranded
  mid-file → `EntryPointAgreementTests` fails naming the stranded classes (and a
  direct run of that mutant shows the partial green `Ran 56`). Full Python suite
  not run — only the two affected modules.
- **Upstream defects identified:**
  - `tests/test_minimonitor_own_mark.py:786` — `unittest.main()` guard mid-file; `OwnAgentStaysCapturedTests` and `OwnWindowInfoConfirmationTests` never run under direct execution
  - `tests/test_monitor_finalize_offload.py:418` — `unittest.main()` guard mid-file; `AgentScopingCallSiteTests` never runs under direct execution
  - `tests/test_shadow_seam.py:1263` — `unittest.main()` guard mid-file; `FormatShadowStaleBannerTests`, `NarrowShadowStaleBannerTests`, `FormatStalenessDetailTests` and `_Meta` never run under direct execution
