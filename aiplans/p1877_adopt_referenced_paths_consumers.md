---
Task: t1877_adopt_referenced_paths_consumers.md
Base branch: main
Output branch: main
---

# t1877 — Adopt `find_references()` in the remote drift check; record the admission/trail decision

## Context

`plan_paths.extract()` only recognises `sh|py|md|yaml|yml|json|toml`, so plans
for Go/Rust/TS projects, and any extensionless file, contribute no path evidence.
t1873 added the inverted, language-agnostic `find_references()`, but only the
shadow's `shadow_scope.py` uses it. The task asks which of the other consumers
should switch, measuring the impact before any switch.

**Measured on the live corpus during planning** (320 archived plans, `git ls-files`
as the candidate set; drift simulated as 960 plan × 10-consecutive-`main`-commit
windows):

| | old (`extract ∩ changed`) | `find_references` | `find_references`, bare root names demoted |
|---|---|---|---|
| references found | 3460 | 3792 | — |
| drift windows with ≥1 overlap | 269 (28.0%) | 377 (39.3%) | exact strong / weak-only / lost counts recorded from the implemented path (see Verification) |

- **Zero windows lost an overlap.** Every reference `extract()` found that
  `find_references` did not (32 references in 21 plans) was an `extract()` FALSE POSITIVE: `` `…/SKILL.md.j2` ``
  truncates to `…/SKILL.md`, a different tracked file.
- Of the 108 windows that only the new search flags, 106 are the bare word `ait`
  ("`ait setup`") matching the root dispatcher file `ait`. The genuine gains
  are `.md.j2`, `.gitignore`, `VERSION`, `Dockerfile`, `.go`, `go.mod`.

**Decisions (confirmed with the user):**
1. **Drift check switches** to `find_references()` over its remote-changed set.
   There are two tiers:
   - `OVERLAP:` (strong) is a full reference to a path that has a `/` or a `.` in
     its last component.
   - `WEAK_OVERLAP:` (new) is either a full reference to an extensionless
     root-level file (`ait`, `Makefile`, `LICENSE`), or a suffix-only
     (module-relative) reference.

   The weak tier is shown in warn mode and never escalated.
2. **Parallel admission and the trail gatherer keep `extract()`**, and the
   measured reasons are recorded. They need candidates FROM the plan. No
   changed-path set exists for any in-flight task (no diff, worktree or commit
   lookup in `parallel_admission*.py` / `trail_gather.py`). Building one means
   extra git calls per in-flight task on the pick path, and an in-flight task
   rarely has tagged commits before Step 8. Admission already ships `off` at a
   34% prompt rate (`fast.yaml:27-37`). The `.md.j2` false positive they keep is
   handed to a follow-up task.

## Implementation steps

1. **`.aitask-scripts/lib/plan_paths.py`**
   - Add `reference_kinds(text, candidates) -> dict[str, str]`, which maps each
     referenced candidate to `"full"`, `"bare"` or `"suffix"`:
     - `"full"` is a `find_references` hit whose candidate has a `/`, or a `.`
       in its name.
     - `"bare"` is a `find_references` hit on a single-component candidate with
       no `.` (for example `ait` or `Makefile`).
     - `"suffix"` is a `find_suffix_references` hit (it already excludes full
       hits).

     The function composes the existing functions and adds no matcher, so no
     second grammar appears.
   - Extend `main()` with `--references [--] <plan-file>`:
     - Read candidate paths from stdin, NUL-delimited, as bytes decoded with
       `surrogateescape`.
     - Print `<kind>\t<path>` per hit, codepoint-sorted, encoded with
       `surrogateescape`.
     - Skip candidates that contain `\n`: they can never match a per-line scan,
       and they would break the line protocol.
     - Keep the exit codes: 3 for an unreadable plan, 2 for usage.
   - Docstring: the drift check is now a `find_references` consumer. The
     "consumers keep the extension grammar" sentence names only admission and
     the gatherer, with a pointer to the findings-doc decision.

2. **`.aitask-scripts/lib/plan_paths_sh.sh`**: replace `plan_paths_extract`
   (whose only caller is the drift check) with
   `plan_paths_references <plan-file>`. It reads NUL-delimited candidates on
   stdin, fails closed exactly as before (non-zero exit, no output), and passes
   `--`. Update the header.

3. **`.aitask-scripts/aitask_remote_drift_check.sh`**
   - Get the remote set with `git diff --name-only -z <base>...origin/<base>`
     into a mktemp file. The empty check stays: an empty file gives
     `NO_OVERLAP`.
   - **Diff-failure branch, explicit and errexit-safe.** Today the script runs
     `remote_files=$(git diff …) || remote_files=""`, so a failed diff yields
     `NO_OVERLAP` with exit 0 (best-effort). Preserve exactly that:
     ```bash
     remote_tmp=$(mktemp "${TMPDIR:-/tmp}/aitask_drift_remote_XXXXXX") || { debug "mktemp failed"; echo "NO_OVERLAP"; exit 0; }
     trap 'rm -f "$remote_tmp"' EXIT
     diff_rc=0
     git diff --name-only -z "${BASE_BRANCH}...origin/${BASE_BRANCH}" > "$remote_tmp" 2>/dev/null || diff_rc=$?
     if [[ $diff_rc -ne 0 ]]; then
         debug "git diff failed ($diff_rc): treating as no remote file changes"
         echo "NO_OVERLAP"; exit 0
     fi
     [[ -s "$remote_tmp" ]] || { debug "no remote-only file changes found"; echo "NO_OVERLAP"; exit 0; }
     ```
     This branch is deliberately separate from `EXTRACT_FAILED`. A diff failure
     keeps its pre-existing best-effort meaning, and only a failure of the plan
     reference scan fails closed. The header comment states the distinction.
   - If the plan exists (`-e || -L`), run
     `plan_paths_references "$PLAN_FILE" < "$remote_tmp"`. Failure gives
     `EXTRACT_FAILED` with exit 3, unchanged.
   - Map `full` to `OVERLAP:<p>` and `bare`/`suffix` to `WEAK_OVERLAP:<p>`. Print
     all OVERLAP lines, then the WEAK lines, then `NO_OVERLAP` exactly once when
     there is no strong line. This keeps the protocol backward-compatible: a
     parser that ignores `WEAK_OVERLAP` sees the same verdict shape.
   - Remove the `grep -Fxf` intersect and the "extension list is a known
     narrowing" comment. Update the header protocol, `--help` and the
     EXTRACT_FAILED wording ("the reference scan could not run").

4. **Procedures** (source of truth `.claude/skills/task-workflow/`):
   - `remote-drift-check.md` step 3: for `AHEAD` + `NO_OVERLAP` with
     `WEAK_OVERLAP` lines under `warn`, display "…none directly touch files in
     your plan; these may be referenced: <list>". Under `strong-only`, return
     silently. With strong `OVERLAP` present, list the weak ones after the
     strong ones, labelled "possibly referenced".
   - `merge-target-sync.md` step 2: likewise, show weak paths as "possibly
     referenced".
   - Re-render the tracked `-remote-` variants for all three agents
     (`.claude/skills/task-workflow-remote-/`,
     `.opencode/skills/task-workflow-remote-/`,
     `.agents/skills/task-workflow-remote-codex-/`) through
     `aitask_skill_render.sh` / the rerender driver.
   - Regenerate `tests/golden/procs/task-workflow/remote-drift-check-default.md`,
     plus any merge-target-sync golden, per the canonical loop in
     `tests/test_skill_render_task_workflow.sh`. Review the diff.

5. **Docs**
   - `aidocs/framework/plan_path_reference_extraction_findings.md`: update the
     consumers paragraph and "Related". Add **§7 Consumer adoption (t1877)** with
     the measurement method (a reproducible command block, per the doc's own
     style), the tables above, the two tiers, the admission/trail
     keep-`extract()` decision with reasons, and the `.md.j2` false positive.
   - Grep `aidocs/`, `website/content/` and `.claude/skills/aitask-trail/`
     (`SKILL.md.j2:116-120`, whose trail statement stays true) for claims that
     the drift check is extension-limited, and correct them. If a website page
     changes, run `python3 check_links.py --build`.

6. **Tests**
   - `tests/test_remote_drift_check.sh`:
     - Flip the Go/Rust/TS non-extraction block (~`:606-659`) to expect
       `OVERLAP:internal/pkg/server.go`.
     - Add cases:
       - `src/Makefile` gives OVERLAP.
       - A root `ait` cited as "`ait setup`" gives `WEAK_OVERLAP:ait` plus
         `NO_OVERLAP`.
       - A module-relative suffix gives WEAK_OVERLAP.
       - A plan citing `x/SKILL.md.j2` with the remote changing `x/SKILL.md`
         gives NO_OVERLAP (the old false positive).
       - `src/app.py@v2` gives no overlap.
       - An NFD-committed path cited in NFC gives OVERLAP with git's
         spelling.
       - A non-UTF-8 remote path gives exit 0 and a verdict.
       - A remote path with a newline gives no crash.
       - **Diff-failure branch.** Put a `git` wrapper on `PATH` that delegates
         to the real git except for `diff --name-only`, which exits 128. Assert
         stdout is exactly `AHEAD:1` then `NO_OVERLAP`, exit 0, and no
         `EXTRACT_FAILED`. Positive control first: the same fixture without the
         wrapper yields `OVERLAP:`, so the wrapper provably reaches the diff
         call.
   - `tests/test_plan_paths.py`: unit tests for `reference_kinds` and for the
     `--references` CLI (NUL input, surrogateescape round-trip, the usage and
     unreadable exit codes).
   - `tests/test_plan_paths_seam.sh`:
     - Guard (b), the single grammar, stays **untouched**.
     - Guard (c) asserts that the drift check calls `plan_paths_references`, not
       `plan_paths_extract`.
     - The fail-closed section keeps its positive control
       (`OVERLAP:.aitask-scripts/aitask_archive.sh`) and the
       `EXTRACT_FAILED`/exit-3 assertions.

### Post-phase (risk mitigations)

1. [drift_protocol_consumer_sweep] Run
   `git grep -n 'OVERLAP' -- .claude .opencode .agents tests/golden aidocs website/content`
   and list every file that parses or documents `aitask_remote_drift_check.sh`
   output. For each one, confirm that it handles `WEAK_OVERLAP:`, or that it is
   a regenerated render/golden matching the source procedure. Fix any
   straggler. Add a test to `tests/test_remote_drift_check.sh`: a plan whose
   only hit is a bare root name must produce exactly
   `AHEAD:1`, `WEAK_OVERLAP:<name>`, `NO_OVERLAP`, in that order, with exit 0.
   This is the backward-compat contract for parsers that ignore the weak line.

## Verification

- `bash tests/test_remote_drift_check.sh`, `bash tests/test_plan_paths_seam.sh`,
  `bash tests/test_plan_approved_marker_drift.sh`,
  `bash tests/test_shadow_scope.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests` (or at least
  `python3 -m pytest tests/test_plan_paths.py`). Read the last verdict line.
- `bash tests/test_skill_render_task_workflow.sh`,
  `./.aitask-scripts/aitask_skill_verify.sh`
- `shellcheck .aitask-scripts/aitask_remote_drift_check.sh .aitask-scripts/lib/plan_paths_sh.sh`
- **Final measurement from the implemented two-tier path (blocking for
  completion).** Re-run the corpus simulation, with the same 320 archived plans
  and the same deterministic 960 windows as planning. Classify each window
  through `plan_paths.py --references` (fed NUL-delimited candidates exactly as
  `plan_paths_references` feeds it) plus the shell's `full`→strong /
  `bare|suffix`→weak mapping. Record **exact** counts and percentages in
  findings §7:
  - old-overlap windows (`extract ∩ changed`, the baseline)
  - **strong** windows (≥1 `OVERLAP`), which is the new always-prompt rate
  - **weak-only** windows (0 strong, ≥1 weak), split into bare-only,
    suffix-only and both. This is the new warn-tier-display rate, and the
    number that shows the suffix policy's impact.
  - **downgraded** windows (old overlap, now weak-only)
  - **lost** windows (old overlap, now neither strong nor weak). This must be 0,
    and any non-zero case is listed with its path and investigated before
    completion.
  - the top weak-hit paths per sub-tier

  Ship the measurement as a reproducible command block in §7, and replace the
  "≈" column in this plan's Context table with the recorded figures. If
  suffix-only weak windows exceed ~5% of windows, list their top paths and
  raise it at Step 8 review rather than tuning silently.
- Step 9 (Post-Implementation): archival and commit via the task workflow.

## Risk

### Code-health risk: medium
- The drift check gains a new protocol line (`WEAK_OVERLAP:`). It is parsed by
  prose procedures (`remote-drift-check.md`, `merge-target-sync.md`), their
  tracked `-remote-` renders for three agents, and a procedure golden. Missing
  one leaves an agent that ignores or mis-renders weak hits, or a stale golden.
  The drift check also sits on the pick hot path, and moving to NUL-delimited
  stdin (bash cannot hold NUL in a variable) is new plumbing. · severity: medium · → mitigation: inline post-phase drift_protocol_consumer_sweep

### Goal-achievement risk: medium
- The "extensionless root-level name is weak" rule is tuned to this repo's
  `ait` noise. In a consumer project, a real root `Makefile`/`Dockerfile`
  reference becomes weak, and a `strong-only` profile then stays silent about
  it. The measurement also uses a proxy (synthetic 10-commit windows, not real
  drift history). · severity: medium · → mitigation: accepted, recorded in findings §7
- Parallel admission and the trail gatherer keep `extract()`, including its
  measured false positive (`…/SKILL.md.j2` → `…/SKILL.md`, 32 references in 21
  plans), which can manufacture an admission `CONFLICT`/trail overlap on the
  wrong file. · severity: medium · → mitigation: fix_extract_multi_extension_truncation

### Planned mitigations
- timing: post-phase | name: drift_protocol_consumer_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — WEAK_OVERLAP protocol line missed by a consumer | desc: Sweep every drift-output parser/render/golden for WEAK_OVERLAP handling and pin the weak-only backward-compat line order in a test
- timing: after | name: fix_extract_multi_extension_truncation | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — extract() false positive (SKILL.md.j2 → SKILL.md) kept by admission/trail | desc: Make plan_paths.extract() reject a match followed by a path character, then re-measure parallel-admission replay and trail corpus rates before/after
