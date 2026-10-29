---
Task: t2150_observe_goengines_release_job_next_tag.md
Base branch: main
Output branch: main
---

# t2150 — Observe the goengines Release job at the first tag after t2148

## Context

t2138 made the release workflow's `goengines` job two-mode (legacy / export,
keyed on `goengines/EXPORT.txt`), but v0.40.0 predates it, so the wiring had
never run on a tag. t2148 fixed the procsup hosted-runner leak. This task
observes the first `v*` tag after t2148 and checks the job against the four
Goal points and the static guard `tests/test_release_workflow_goengines.py`.

The task is observation-only. **No code changes are planned.** The deliverable
is the evidence below, recorded in this plan's Final Implementation Notes, plus
a bug task only if a divergence is found (none was).

## Evidence gathered during planning (read-only)

Tag: `v0.40.1` → `b5e76cf6b` (Release run headSha `b5e76cf6b592…`, event push).
t2148's fix `a06e4f5d8` is an ancestor (`git merge-base --is-ancestor` → yes).
`goengines/EXPORT.txt` does not exist at `v0.40.1`, so legacy mode is expected.
`release.yml`, `goengines_integrity.sh`, `goengines/build.sh` and the static
guard test are unchanged between `v0.40.1` and current `main` (empty diff
--stat), so the guard at HEAD models the exact wiring that ran.

Release run **40858419630**: all 13 jobs `success`. Job `goengines`
(**123395220031**), every step `success`:

1. **Mode detection.** The `Detect goengines mode` step printed `MODE:legacy`.
   The script appends `mode=<m>` to `$GITHUB_OUTPUT` (`goengines_integrity.sh:540-541`).
   The gate `steps.mode.outputs.mode != 'export'` let all four gated steps run,
   which is consistent with a non-`export` value. ✔
2. **Preflight + suite.** The `Hang-guard preflight` (`./ci/preflight.sh`) ran, and
   `ok …/internal/testsupport/hangguard 0.756s` printed. The pinned pytest 8.4.2 / xdist 3.8.0
   was installed. `go test ./...` with `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` ran,
   and all 21 packages printed `ok`, including `internal/procsup 7.515s` (the
   t2148 area). ✔
3. **Export integrity.** It printed `MODE:legacy` and then
   `INTEGRITY_SKIPPED:legacy mode — goengines/ is developed here; gofmt, vet, the preflight, go test and the bench are its validation`.
   Drift report: `DRIFT_SKIPPED:legacy`. ✔
4. **Sums + assets.** `./build.sh all` built 4 targets for the single
   executable under `goengines/cmd/` (`ait-testmap`, the only entry at
   v0.40.1). It produced `ait-testmap_0.40.1_SHA256SUMS.txt`, and the in-job
   `sha256sum -c` loop printed `OK` for all 4. Artifact `goengines-dist`
   (ID 12889983906) uploaded 5 files. The `release` job (**123396018588**)
   downloaded that artifact (same digest `ad76da16…`) and uploaded all 5 to the
   GitHub release. Independent check: `gh release download v0.40.1 --pattern
   'ait-testmap_*'` into scratch, then `sha256sum -c` reported 4/4 `OK`. Release assets =
   {4 binaries, 1 sums file}, which is exactly one sums file per `cmd/` executable. ✔

Static guard: `python3 tests/test_release_workflow_goengines.py` gave 26 tests, `OK`.
Observed step order and gating (mode → vet → gated preflight → gated
python/pytest → gated go test → ungated check → advisory drift → build with
the `for s in "${sums[@]}"` loop → upload; release `needs: [plan, goengines]`,
downloads `goengines-dist`, attaches `goengines/dist/*`) match the guard's
model. **No divergence found, so no bug task is created.**

Scope boundary: these claims cover this one run (legacy mode). The
export-mode run (`MODE:export`, `INTEGRITY_OK`, drift/asset checks after the
aitasks_go#t22 cutover) is **not** observed here. The advisory note from
aitasks_go#t22_2 says it belongs in a separate follow-up filed after the cutover;
that is out of this task's scope.

## Implementation steps (post-approval)

1. Re-run the static guard once to confirm the result is unchanged:
   `python3 tests/test_release_workflow_goengines.py`.
2. Add a `## Final Implementation Notes` section to this plan with the
   step-level conclusions and IDs above (run 40858419630, jobs 123395220031 /
   123396018588, artifact 12889983906). Upstream defects: `None`.
3. No code commit (there are no code changes). Commit the plan file only, via
   `./.aitask-scripts/aitask_task_commit.sh`.
4. Step 9: no branch or merge (current-branch mode). Run `ait gates run 2150`
   (the `risk_evaluated` gate), then archive.

## Verification

- The guard test passes (26/26).
- Each Goal point maps to a quoted log line or a re-run checksum above.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Observed the first `v*` tag after t2148: `v0.40.1` → `b5e76cf6b`; t2148 fix `a06e4f5d8` is an ancestor. Release run **40858419630** (event push, headSha `b5e76cf6b592fcef21415535dc8f43848addb87e`) had all 13 jobs `success`. Step-level conclusions for job `goengines` (**123395220031**), all steps `success`:
  - `Detect goengines mode` → `MODE:legacy` (no `goengines/EXPORT.txt` at the tag; `mode=` is appended to `$GITHUB_OUTPUT` at `.github/scripts/goengines_integrity.sh:540-541`).
  - `go vet` → success, no findings.
  - `Hang-guard preflight` → ran (`ok …/internal/testsupport/hangguard 0.756s`). This and the next three steps are gated on `steps.mode.outputs.mode != 'export'`, and all four executed.
  - `Setup Python` / `Install pinned pytest` → pytest 8.4.2 + pytest-xdist 3.8.0.
  - `go test` (`AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`) → 21/21 packages `ok`, incl. `internal/procsup 7.515s`.
  - `Export integrity` → `MODE:legacy` + `INTEGRITY_SKIPPED:legacy mode — goengines/ is developed here; gofmt, vet, the preflight, go test and the bench are its validation`.
  - `Drift report` → `DRIFT_SKIPPED:legacy`.
  - `Build engine release assets` → 4 targets of `ait-testmap` (the only executable under `goengines/cmd/` at v0.40.1); `ait-testmap_0.40.1_SHA256SUMS.txt`; in-job `sha256sum -c` 4/4 `OK`.
  - `Upload engine release assets` → artifact `goengines-dist` ID 12889983906, 5 files, digest `ad76da16c783…`.
  - The `release` job (**123396018588**) downloaded the same artifact (same digest) and uploaded all 5 `ait-testmap_*` files to the GitHub release.
  - Independent re-check: `gh release download v0.40.1 --pattern 'ait-testmap_*'` followed by `sha256sum -c ait-testmap_0.40.1_SHA256SUMS.txt` gave 4/4 `OK`. The release has 4 binaries + 1 sums file, i.e. one sums file per `cmd/` executable.
- **Divergence from the static guard:** none. `release.yml`, `goengines_integrity.sh`, `goengines/build.sh` and `tests/test_release_workflow_goengines.py` show an empty diff between `v0.40.1` and `main` at `c0483ba6e`, so the guard at HEAD models the wiring that ran. `python3 tests/test_release_workflow_goengines.py` gave 26 tests `OK`. The observed order and gating match the guard's model. No bug task was created.
- **Deviations from plan:** None.
- **Issues encountered:** The job log's per-step labels read `UNKNOWN STEP`, so steps were segmented by their `##[group]Run …` headers instead.
- **Key decisions:** Claims are bounded to this one legacy-mode run. The first export-mode Release run (`MODE:export`, `INTEGRITY_OK`, drift and asset checks after the aitasks_go#t22 cutover) was not observed and is out of scope. The advisory note from aitasks_go#t22_2 places it in a follow-up filed after the cutover.
- **Upstream defects identified:** None
