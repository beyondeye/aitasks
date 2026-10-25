---
Task: t2138_goengines_export_target_two_mode_ci.md
Base branch: main
Output branch: main
---

# t2138 — goengines as the export target: two-mode CI, integrity script, docs

## Context

The decision record `aidocs/aitasks_go/ship_path.md` (in aitasks_go, from aitasks_go#t15) makes the
private `aitasks_go` repository the single development home for every
framework Go binary. Public `goengines/` becomes a **generated export target**:
the source arrives through `promote/export.sh` (aitasks_go#t21), and the
testmap cutover runs as the bootstrap export (aitasks_go#t22). Public CI has
to validate both states of the tree: the state before the cutover, where
testmap is still developed here, and the exported state, which has no tests,
`ci/` or `bench/`. **One signal selects the mode: whether
`goengines/EXPORT.txt` exists.** This task ships both modes now. The cutover
commit creates `EXPORT.txt`, so it also activates export mode, and there is
no window in which neither validation is required.

Facts found while exploring:

- `goengines-check.yml` has a `check` job (gofmt, vet, `./ci/preflight.sh`,
  `go test`, the cross-build plus sums, and four repo-side guards) and an
  advisory `bench` job. The `release.yml` `goengines` job runs vet, the
  preflight, `go test`, `build.sh all`, `sha256sum -c` and the upload.
- `tests/test_release_workflow_goengines.py` pins this wiring. In particular,
  `assert_preflight_precedes_suite` **forbids any `if:`** on the preflight and
  suite steps. Export mode has to skip them in `release.yml`, so this guard
  must be extended to accept exactly one fail-closed legacy condition.
- After the cutover, `goengines/` may contain only exported files plus the
  public-maintained `README.md` and `.gitignore`, and the exporter refuses
  any unknown file. The integrity script therefore **cannot live under
  `goengines/`**. It goes in `.github/scripts/`, a new directory that is not
  part of the release tarball.
- `ait engine test` (`.aitask-scripts/aitask_engine.sh` `cmd_test`) runs vet,
  then `goengines/ci/preflight.sh`, then `go test`. In export mode `ci/` is
  gone, so the verb would crash. It is a consumer of the same signal and is
  in scope (E7 in `tests/test_install_engine_binary.sh` pins it).
- `main` has **no branch protection** (`gh api …/protection` returns 404). In
  practice "required" therefore means **it blocks the release**: `release`
  needs `goengines`, so a failing integrity step stops the release. In the
  check workflow, a failure shows on the commit. The docs will say this, and
  also say which job to mark required if protection is ever added.
- No `EXPORT.txt` format exists yet: aitasks_go#t21 lists only its contents.
  This task **defines format 1**, because the public side parses it. A note to
  aitasks_go#t21 hands over that contract.

## Design

### Mode condition (fail-closed)

Legacy steps and jobs are skipped **only on a positive `export` detection**:

- in `goengines-check.yml` (job level):
  `if: ${{ !cancelled() && needs.mode.outputs.mode != 'export' }}`. If the
  `mode` job fails, its output is empty, so `check` and `bench` still run in
  full. `!cancelled()` keeps them from being skipped just because their need
  failed;
- in `release.yml` (step level): `if: steps.mode.outputs.mode != 'export'`. A
  failing mode step fails the job, so the release does not happen.

### `EXPORT.txt` format 1 (defined here, written by aitasks_go#t21)

Line-oriented. A line is blank, a `#` comment, or `key: value`. Paths are
relative to `goengines/`.

```
format: 1
source: beyondeye/aitasks_go@<40|64 hex>
manifest: sha256:<64 hex>
migrated-from: beyondeye/aitasks@<sha>        # bootstrap only
gate: <name> <result>                         # one per private gate step
file: <64 hex sha256> <path>                  # one per exported file, sorted
removed: <path>                               # zero or more
```

Validation, which is part of the required `check`:

- `format: 1` must appear exactly once;
- `source:` must appear exactly once and match the grammar;
- every `file:` line must be `<64 hex> <path>`;
- a path must match `^[A-Za-z0-9._/@+-]+$`, must not be absolute, must have no
  `..` segment, and must not be listed twice;
- unknown keys are tolerated, so the exporter can add fields without breaking
  the public release. `format:` is the version gate.

### `.github/scripts/goengines_integrity.sh <mode|check|drift> [--dir <goengines>]`

Usage: bash with `#!/usr/bin/env bash` and `set -euo pipefail`, following
`aidocs/framework/shell_conventions.md`. `--dir` defaults to the repo's
`goengines/`, resolved from the script's own location. Exit 64 on usage
errors.

| verb | output | exit |
|---|---|---|
| `mode` | `MODE:legacy` / `MODE:export`; also appends `mode=<m>` to `$GITHUB_OUTPUT` when that variable is set. If `EXPORT.txt` exists but is not a regular file, or is a symlink: `MODE_ERROR:<why>` | 0 / 1 |
| `check` | legacy: `MODE:legacy` plus `INTEGRITY_SKIPPED:legacy mode — …`. Export: one `INTEGRITY_FAIL:<check>:<detail>` per failure, or `INTEGRITY_OK` | 0 / 1 |
| `drift` | legacy: `DRIFT_SKIPPED:legacy`. Export: `DRIFT:modified\|missing\|unlisted:<path>` lines, then `DRIFT_NONE` or `DRIFT_FOUND:<n>`. Under `GITHUB_ACTIONS=true` each entry also emits `::warning file=goengines/<path>,title=goengines drift::…`, naming the emergency-fix protocol. An unreadable record prints `DRIFT_UNCHECKED:<reason>`, because `check` owns that failure | **always 0** |

`check` in export mode runs every Go command in a **scratch copy**
(`cp -R`, then drop `dist/` and the built `ait-testmap`), so the checkout is
never mutated.

**Platform-dependent checks run once per release target, with the release
build settings.** `go list` and `go build` evaluate build constraints for one
`GOOS`/`GOARCH` only. A `_darwin.go` file importing the main module's `tui/`
package, or importing a private module, is invisible to a Linux-host check,
and its build can still pass. The script therefore reads the release matrix
from `build.sh`, which stays the single source: it parses the
`readonly MATRIX=(…)` line. If that line is missing or empty, the script
fails closed with `INTEGRITY_FAIL:matrix:…`. Every per-platform command runs
under `CGO_ENABLED=0 GOOS=<os> GOARCH=<arch>`, which is what `build.sh`
uses; build.sh passes no build tags. The checks run in this order:

1. **`record`**: validate `EXPORT.txt`, as described above.
2. **`gofmt`**: `"$(go env GOROOT)/bin/gofmt" -l .` must print nothing.
3. **`private-deps`**: runs under `GOWORK=off GOFLAGS=-mod=readonly`. The
   private pattern is `^github\.com/beyondeye/aitasks_go(/|$)`. The checks
   are all structural, never free-text, so the provenance header,
   `SourceCommit` and `EXPORT.txt` pass:
   - `go mod edit -json` (parsed with `python3`): no `Require` path and no
     `Replace` old or new path may match the pattern. A local replace (new
     path beginning with `./`, `../` or `/`) must not be absolute and must
     have no `..` segment. This is a lexical, conservative "inside the tree"
     check, and the docs say so;
   - `go.sum`: no line's first field may match;
   - `go list -m all`: no line may match;
   - `go list -e -deps -f '{{.ImportPath}}: {{join .Imports " "}}' ./...`,
     run **for each matrix target**: no token may match. The failure names the
     target.

   If any of these fail, the script **stops here**. Later checks may touch
   the network, and they would only mask the real reason.
4. **`independent-build`**: runs under `GOWORK=off GOFLAGS=-mod=mod
   GOPRIVATE= GONOPROXY= GONOSUMDB= GOPROXY=https://proxy.golang.org`.
   `go mod tidy -diff` must be clean (tidy already considers every
   platform). Then `go build ./...` must pass **for each matrix target**, and
   `go vet ./...` must pass on the host.
5. **`closure`**, **for each matrix target**:
   `go list -deps -f '{{if not .Standard}}{{.ImportPath}} {{with .Module}}{{.Path}}{{end}}{{end}}' ./cmd/ait-testmap`.
   A failure prints `INTEGRITY_FAIL:closure:<os>_<arch>:<binary>:<pkg>`.
   `./cmd/ait-monitord` is checked the same way when its directory exists,
   and `cmd/ait-testmap` is required. Every non-std package must belong to
   either the main module or one of the allowlisted modules (`gopkg.in/yaml.v3`,
   `github.com/bmatcuk/doublestar/v4`, `golang.org/x/sync`). A package with no
   module fails. So does any main-module package under
   `<module>/tui/`: the testmap closure contains no TUI or Charm package.

`drift` does the following:

- For each `file:` entry it compares the file's sha256 (with a
  `sha256sum`/`shasum -a 256` fallback, as `build.sh` does) and reports a
  mismatch as `modified` and an absent file as `missing`.
- It reports as `unlisted` any file that is in the tree but not in the record
  and is not `README.md`, `.gitignore` or `EXPORT.txt`. The tree is
  enumerated with `git ls-files -co --exclude-standard` inside a work tree,
  and with `find` otherwise.

## Steps

1. **Create `.github/scripts/goengines_integrity.sh`** as designed, and make
   it executable. The allowlist constant carries a comment saying it restates
   `allowedDeps` in `goengines/guards_test.go`. While that file exists, the
   new test pins that the two lists are equal.

2. **Edit `.github/workflows/goengines-check.yml`:**
   - New `mode` job: checkout, then a step `id: mode` running
     `.github/scripts/goengines_integrity.sh mode`, with
     `outputs: mode: ${{ steps.mode.outputs.mode }}`.
   - `check` and `bench`: add `needs: mode` and the fail-closed job-level
     `if:`. Their steps stay unchanged, except the multi-program sums loop in
     "Release cross-build" (step 5b).
   - `check`: add a repo-side guard step
     `bash tests/test_goengines_export_integrity.sh`.
   - New `export-integrity` job (no job-level `if`, no `continue-on-error`):
     - checkout, setup-go (`go-version-file: goengines/go.mod`), and a mode
       step;
     - `Export integrity` runs `… check`, which reports legacy and exits 0 in
       legacy mode;
     - `Drift report` runs `… drift` with `continue-on-error: true`;
     - steps gated by `if: steps.mode.outputs.mode == 'export'`: setup-python,
       then `pip install pyyaml` and the workflow guard
       `tests/test_release_workflow_goengines.py`, then
       `tests/test_goengines_build.sh` and
       `tests/test_goengines_export_integrity.sh`. These guards protect public
       files that still exist after the cutover, and in export mode the
       `check` job that ran them is skipped.
   - Trigger `paths` (push and pull_request): add `.github/scripts/**` and
     `tests/test_goengines_export_integrity.sh`.
   - Update the header comment.

3. **Edit the `goengines` job in `.github/workflows/release.yml`:**
   - after setup-go, add `Detect goengines mode` (`id: mode`, no `if`);
   - `go vet` stays unconditional;
   - the preflight and `go test` get `if: steps.mode.outputs.mode != 'export'`;
   - add `Export integrity` (`… check`, unconditional; it reports legacy in
     legacy mode) and `Drift report` (`… drift`, `continue-on-error: true`)
     **before** `Build engine release assets`;
   - the build, sums and upload steps stay unchanged.

4. **Edit `tests/test_release_workflow_goengines.py`:**
   - Extend `assert_preflight_precedes_suite(tc, steps, gate=None)`.
     - With `gate=None`, it behaves as today (no `if` at all), and the check
       workflow passes `None`.
     - With `gate=LEGACY_STEP_IF`, the preflight and the first suite step must
       both carry exactly that `if`. A step with `id: mode` must also
       precede the preflight, carry no `if`, and run
       `goengines_integrity.sh mode`.
     - `continue-on-error` stays forbidden in both cases.
   - Add negative controls: a gated preflight under some other condition, a
     suite gated differently from the preflight, a gate whose mode step is
     missing or comes later, and `== 'legacy'` (not fail-closed). Each must be
     rejected. The existing bypasses stay rejected.
   - New assertions:
     - release `goengines` runs `goengines_integrity.sh check` (no `if`, not
       continue-on-error) before `./build.sh all`, and its drift step is
       `continue-on-error: true`;
     - in check, the `mode` job outputs mode; `check` and `bench` need `mode`
       and carry exactly the `LEGACY_JOB_IF` string;
     - `export-integrity` has no job-level `if`, is not continue-on-error,
       runs the `check` and `drift` verbs (drift continue-on-error), and gates
       the guard steps on `== 'export'`;
   - `test_only_bench_is_advisory` also asserts `export-integrity` is not
     advisory;
   - `CHECK_PATHS` gains the two new paths.

5. **Create `tests/test_goengines_export_integrity.sh`** (bash; its bodies
   run in `( … )` subshells, so it calls `assert_counters_init` and
   `assert_counters_load` as CLAUDE.md requires). It SKIPs when go is
   missing, runs with `GOTOOLCHAIN=local GOFLAGS=`, and writes its fixtures
   under a `mktemp -d` scratch dir. The fixture factory `mkfix <name>`
   creates a git-initialised `goengines/` containing:
   - `go.mod` (`module github.com/beyondeye/aitasks/goengines`,
     `go <local major.minor>`);
   - a stdlib-only `cmd/ait-testmap/main.go` that opens with the provenance
     header `// Code generated by aitasks_go export from <sha>; DO NOT EDIT.`
     and declares `const SourceCommit = "aitasks_go@<sha>"`;
   - a copy of the real `goengines/build.sh`, which is where the script reads
     the matrix from;
   - an `EXPORT.txt` built from the real hashes.

   Cases:
   - **mode**: no `EXPORT.txt` gives `MODE:legacy` and writes
     `mode=legacy` to `$GITHUB_OUTPUT`. A file gives `MODE:export`. A
     directory or symlink gives `MODE_ERROR`, exit 1.
   - **legacy check / drift**: both exit 0 and report legacy. `go` must not
     be invoked, which a stub `go` on PATH proves.
   - **export accepts the provenance-labelled fixture** with `INTEGRITY_OK`
     and `DRIFT_NONE`.
   - **refusals** (each exits 1 with the named check):
     - planted private import `github.com/beyondeye/aitasks_go/widget` → `private-deps`;
     - `require` plus `replace github.com/beyondeye/aitasks_go => ./priv` → `private-deps`;
     - `replace example.com/x => ../x` (outside the tree) → `private-deps`;
     - a private module line in `go.sum` → `private-deps`;
     - **platform-only violations**: these prove the matrix loop, because each
       fixture passes a host-only check. The controls are always the
       non-host OS (`darwin` on a Linux host, `linux` on macOS):
       - `cmd/ait-testmap/dep_<other-os>.go` imports the fixture's own
         `<module>/tui/widget` → `closure`, and the failure names an
         `<other-os>_*` target;
       - `internal/x/x_<other-os>.go` imports `github.com/beyondeye/aitasks_go/widget`
         → `private-deps`, and the failure names the target;
       - each of these fixtures also passes a direct host-only `go list` probe,
         recorded as a sanity assertion, so the test shows the violation really
         is invisible to the host;
     - a `build.sh` whose `MATRIX` line has been removed → `matrix`;
     - an unformatted file → `gofmt`;
     - an untidy go.mod (an unused local require) → `independent-build`;
     - a compile error → `independent-build`;
     - `cmd/ait-testmap` importing `<module>/tui/widget` → `closure`;
     - a non-allowlisted local-replace module imported by ait-testmap → `closure`;
     - no `cmd/ait-testmap` → `closure`;
     - malformed records: `format: 2`, a missing `source:`, a bad hash, a
       `..` path, a duplicate path → `record`.
   - **checkout not mutated**: the fixture's `git status --porcelain` is
     empty after a failing `independent-build` run.
   - **drift**: a modified, a deleted and an added file give the three
     `DRIFT:` kinds and `DRIFT_FOUND:3`, with exit 0. `GITHUB_ACTIONS=true`
     adds `::warning` lines.
   - **allowlist sync**: while `goengines/guards_test.go` exists, its
     `allowedDeps` literals equal the script's allowlist.

5b. **Make `tests/test_goengines_build.sh` multi-executable.** It becomes a
    required export-mode guard, and `build.sh` builds every `cmd/*`, so a valid
    export that adds `ait-tui` or `ait-monitord` must not fail it.
    - **Real-tree sections:** discover the commands with build.sh's own rule
      (`cmd/*/` directories that contain `*.go`), giving `N`. Then:
      - host build: exactly `N` `BUILT:` lines, one per command, each named
        `<name>_<V>_<os>_<arch>` and existing on disk;
      - `all`: exactly `4·N` `BUILT:` lines and `N` `SUMS:` lines;
      - each `<name>_<V>_SHA256SUMS.txt` lists exactly that program's four
        matrix binaries, sorted, and none of another program's, and passes
        `sha256sum -c`;
      - the `go version -m` per-target checks (GOOS, GOARCH, CGO disabled,
        trimpath, no VCS stamp) loop over every program × target;
      - the `ait-testmap`-specific `version --json` identity assertions stay,
        applied to ait-testmap, which must exist (export mode requires it);
      - "bench tool never built" stays.
    - **New two-command fixture section:**
      - a fake tree holding a copy of `build.sh`, a `go.mod`, `cmd/alpha` and
        `cmd/beta` (stdlib mains printing `main.version` / `main.commit`),
        `cmd/notes/` with no `.go` file (it must not be built), and
        `.aitask-scripts/VERSION`;
      - host build: 2 `BUILT:` lines, and each binary prints its injected
        `--version` / `--commit`;
      - `all`: 8 `BUILT:` lines, 2 `SUMS:` lines, per-program sums contents,
        each sums file verifies, and nothing is built for `notes`.
    - **Workflows:** the two `sha256sum -c ait-testmap_*_SHA256SUMS.txt`
      steps (check workflow "Release cross-build" and release
      "Build engine release assets") become a loop over every
      `*_SHA256SUMS.txt` that fails when there is none. With today's single
      command the behaviour is identical. Without the change, an exported
      program's sums would go unverified. The release-workflow guard asserts
      the loop form.

6. **Edit `.aitask-scripts/aitask_engine.sh` `cmd_test`:**
   - When `goengines/EXPORT.txt` exists, it prints an info line saying the
     suite, preflight and bench run in aitasks_go at the exported commit, and
     warns that any go-test args are ignored.
   - It then runs `bash "$SCRIPT_DIR/../.github/scripts/goengines_integrity.sh" check`
     and then `… drift`, and returns.
   - Legacy behaviour stays unchanged.
   - Update the header comment for `test`.
   - Add case **E7b** to `tests/test_install_engine_binary.sh`. Its fixture
     has an `EXPORT.txt` and a stub integrity script that logs its verbs. It
     asserts that `check` and then `drift` run, that preflight and
     `go test ./...` never run, and that a failing `check` fails the verb.

7. **Rewrite `goengines/README.md` (keyed on the signal, current-state
   accurate in both modes).** A new top section, "Source of truth", covers:
   - with no `EXPORT.txt`, development happens here and the developer
     sections below apply;
   - with `EXPORT.txt`, the tree is generated from the aitasks_go `export`
     branch and must not be edited. The `DO NOT EDIT` headers, the trailers
     (`Exported-From:`, `Migrated-From:`, `Drift-Returned-In:`), the
     public-maintained files (**only** `README.md` and `.gitignore`) and the
     `EXPORT.txt` format 1 are documented;
   - CI in each mode;
   - the **emergency-fix protocol**:
     1. commit the fix here with the trailer `Return-To: aitasks_go`;
     2. in the same session, run
        `ait create --batch --project aitasks_go …` to create a return task
        naming the public commit;
     3. CI warns about the drift and never blocks;
     4. the next export refuses until the fix is ported back
        (`--drift-returned-in <private sha>`).

   The existing developer sections stay, under a heading saying they apply
   while there is no `EXPORT.txt`. They move to aitasks_go at the cutover.
   The exporter never touches `README.md`, so trimming them is the cutover
   task's job, and the note in step 10 tells it so.

8. **Amend `aidocs/framework/go_engine.md`:**
   - the release-job wiring: the mode step, the gated preflight and suite,
     and the integrity and drift steps;
   - the CI section: the `mode` job, the fail-closed condition, the new
     `export-integrity` job, the trigger paths, and the new guard in the list
     of repo-side guards;
   - a new section "Export mode": the signal, the integrity script's verbs
     and checks, the format-1 contract, the emergency-fix protocol (link to
     the README), branch protection (none today; the release path is the
     enforcer; mark `export-integrity` required if protection is added), and
     what `ait engine test` does in that mode;
   - update the sentence "`ait engine test` runs the same sequence".

9. **Amend `aidocs/testing_engine/n014_explorer_006_proposal.md`:**
   - In *Go engine and CLI (M1.2)*:
     - the dependency sentence becomes "the ait-testmap closure depends on
       `gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`, `golang.org/x/sync` only".
       The allowlist is scoped to that closure (and to ait-monitord's), and
       TUI binaries carry their own allowlist in aitasks_go;
     - add a development-location paragraph: until the scheduled testmap
       cutover (aitasks_go#t22), development happens in public `goengines/`.
       From the cutover on it happens in aitasks_go and is exported here,
       with `EXPORT.txt` as the switch.
   - In *Binary distribution (M1.3, M1.4)*, add one sentence: the CI and the
     release job are two-mode, keyed on `EXPORT.txt`; see `go_engine.md`.
   - Also check row M1.2/M1.3 of the milestone table for a dependency or
     location claim that needs the same scoping.

10. **Notes (`/aitask-note` composition) after the implementation commit:**
    - to `--project aitasks_go 21`: the `EXPORT.txt` format-1 contract, that
      the public `goengines_integrity.sh` mirrors checks 1–3, the lexical
      inside-tree replace rule, and that unknown keys are tolerated;
    - to `--project aitasks_go 22`: at cutover, trim the developer sections
      of `goengines/README.md` (the exporter leaves README alone), and the
      bootstrap commit must add `EXPORT.txt` in the same commit as the
      export.

### Post-phase (risk mitigations)
1. [actionlint_workflows] Run a pinned actionlint over both edited
   workflows, from a scratch `GOBIN` inside the session scratchpad:
   `GOBIN=<scratch>/bin go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.7`,
   then `<scratch>/bin/actionlint .github/workflows/goengines-check.yml .github/workflows/release.yml`.
   Fix every finding in the new or changed lines. Report findings in lines
   this task did not touch, but do not fix them. This catches expression and
   `needs` typos that the YAML-structure guard cannot see.

## Verification

- `bash tests/test_goengines_export_integrity.sh`: every case passes.
- `python -m unittest tests/test_release_workflow_goengines.py`: passes,
  including the new negative controls.
- `bash tests/test_install_engine_binary.sh`: E7 is unchanged and E7b passes.
- **Legacy mode on the current tree:**
  - `goengines_integrity.sh mode` prints `MODE:legacy`, and `check` / `drift`
    report legacy;
  - `ait engine test -short` behaves exactly as before.
- **Export checks accept the real tree:** copy `goengines/` to the
  scratchpad, `git init` the copy, generate an `EXPORT.txt` from its file
  hashes, and run `check --dir <copy>`. Expect `INTEGRITY_OK`. This proves
  checks 1–3 hold for today's source (test files included).
- `bash tests/test_goengines_build.sh`, `bash tests/test_goengines_benchci.sh`
  and `shellcheck .github/scripts/goengines_integrity.sh .aitask-scripts/aitask_engine.sh`.
- The post-phase actionlint run is clean.
- Step 9 (Post-Implementation): commit (`chore: … (t2138)`), archive, and
  push. CI on GitHub runs both workflows for real only after the push. See
  the risk section.

## Risk

### Code-health risk: medium
- Restructuring the required CI and release jobs could silently skip the legacy suite. A wrong `if`, or a skipped job counted as success, could let a release ship without `go test` · severity: medium (residual: expression typos are addressed by inline post-phase actionlint_workflows; the fail-closed `!= 'export'` condition and guard negative controls pin the gating; real-runner semantics remain, see below) · → mitigation: inline post-phase actionlint_workflows
- `ait engine test` gains a second branch in a script with pinned interfaces · severity: low · → mitigation: none (covered by E7 unchanged plus E7b)

- The per-target loops (four `go list` runs and four cross `go build ./...` runs) add CI time, and the test fixtures cross-compile for four targets · severity: low · → mitigation: none (the build cache is shared with build.sh's own matrix; fixtures are stdlib-only)

### Goal-achievement risk: medium
- The `EXPORT.txt` format is defined here, before the exporter (aitasks_go#t21) exists. A divergent exporter would fail the required `record` check, or produce false drift · severity: medium · → mitigation: none (the step-10 note hands the contract to t21; unknown keys are tolerated)
- GitHub Actions semantics (`!cancelled()` with a failed `needs`, a skipped job reported as success, `GITHUB_OUTPUT` plumbing) cannot be executed locally. The first real proof is the post-push run · severity: medium · → mitigation: t2141

### Planned mitigations
- timing: post-phase | name: actionlint_workflows | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — CI/release restructure silently skipping the legacy suite | desc: run pinned actionlint over goengines-check.yml and release.yml and fix findings in changed lines
- timing: after | name: observe_first_ci_runs | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — Actions semantics unverifiable locally | desc: after push, confirm goengines-check passes in legacy mode on main (check/bench run as before, export-integrity reports legacy) and the release workflow wiring parses; optionally exercise export mode once on a throwaway branch with a fixture EXPORT.txt | created: t2141

## Implementation Notes

Steps 1–9 and the `actionlint_workflows` post-phase are done. Step 10 (the
notes to aitasks_go#21 / #22) runs after the commit.

Deviations and additions:

- **Record rule added.** The record may not list `EXPORT.txt`, `README.md` or
  `.gitignore`. The first real-tree dry run turned up a generator that listed
  `EXPORT.txt` in itself, which made the record self-drifting.
- **Drift enumeration** uses `git ls-files -co --exclude-standard` (newline-
  separated, `core.quotepath=off`), falling back to `find`. No `sed -z`, which
  is GNU-only.
- **The engine-test export branch** passes `--dir "$GOENGINES"` explicitly,
  and runs `drift` only after `check` succeeds (errexit). E7b pins both.
- **The workflow guard** gained the `IntegrityStepControls` negative controls
  and a sums-loop assertion. The two-mode controls are in
  `PreflightOrderControls.test_every_gated_bypass_is_rejected`.

Verification evidence:

- `tests/test_goengines_export_integrity.sh`: 143/143.
  - Mutant: restricting `TARGETS` to the host OS fails the 7 platform-only
    assertions, so the matrix loop is load-bearing.
- `tests/test_release_workflow_goengines.py`: 22 OK.
  - Workflow mutants that fail it: `== 'legacy'` job if, `always()` step if,
    drift without `continue-on-error`.
- `tests/test_goengines_build.sh`: 107/107. A scratch tree with an extra
  `cmd/ait-tui` gives 131/131.
- `tests/test_install_engine_binary.sh`: 228/228 (E7 unchanged, E7b new).
- `tests/test_goengines_benchci.sh` 28/28; `test_annot_conformance_corpus_sync.sh`
  17/17; `test_cd_guard_lint.sh` 92/92.
- Legacy mode on the real tree:
  - `goengines_integrity.sh mode` prints `MODE:legacy`, and `check` / `drift`
    report legacy;
  - `ait engine test -short` passes.
- Export checks on a scratch copy of the real `goengines/`, with a generated
  record: `INTEGRITY_OK`, `DRIFT_NONE` (about 11 s).
- actionlint v1.7.7: clean on expressions and wiring. Its shellcheck pass
  reports only 3 SC2086 infos in the pre-existing release.yml
  "Extract changelog" step (unchanged lines, not fixed).

## Post-Review Changes

### Change Request 1 (2026-10-25 12:40)
- **Requested by user:** three verified defects in `goengines_integrity.sh`:
  1. `check_closure` read the main module with a direct `go list -m` that
     bypassed `GOWORK=off`, so an inherited workspace returned the wrong
     module;
  2. `drift` died under errexit on an unreadable `EXPORT.txt` instead of
     printing `DRIFT_UNCHECKED`;
  3. newline-separated `git ls-files` C-quoted names containing a quote or a
     backslash, so those unlisted files went unreported.
- **Changes made:**
  - Every go call (`go env GOROOT`, `go mod edit -json`, `go list -m`) now goes
    through `run_go`.
  - `parse_record` reads through `parse_record_lines` inside an `if`, so an
    unreadable record becomes the `cannot be read` error. `check` refuses it
    with `INTEGRITY_FAIL:record:EXPORT.txt cannot be read`; `drift` prints
    `DRIFT_UNCHECKED:EXPORT.txt cannot be read` and exits 0.
  - The same audit found two more errexit exits: the `sed` pipeline in
    `check_matrix` on an unreadable `build.sh` (now `INTEGRITY_FAIL:matrix`),
    and `cp -R` (now `INTEGRITY_FAIL:copy`).
  - `tree_files` is NUL-delimited for both git (`-z`) and find (`-print0`).
  - `DRIFT:` lines `%q`-quote a path holding a control character, and the
    `::warning` property and data are escaped per GitHub's workflow-command
    rules.
  - New test cases: 9b covers awkward names (space, quote, backslash,
    comma/colon) with git and without, plus the annotation escape. 9c covers
    an unreadable record and an unreadable exported file (skipped as root). 9d
    covers an inherited unrelated `GOWORK`.
  - Each new case is red against its mutant: direct `go list -m` 2 FAIL,
    newline enumeration 3 FAIL, unguarded parse 4 FAIL.
  - Results: 168/168; the real-tree dry run still gives `INTEGRITY_OK` and
    `DRIFT_NONE`.
- **Files affected:** `.github/scripts/goengines_integrity.sh`,
  `tests/test_goengines_export_integrity.sh`.

### Change Request 2 (2026-10-25 13:05)
- **Requested by user:**
  1. `go mod edit -json` (and `go env GOROOT`) inherited the caller's GOFLAGS.
     With `-modfile=<benign.mod>`, the metadata check read the benign file, so
     an absolute outside replace passed;
  2. a NUL-enumerated name containing a newline could match two adjacent
     paths in the newline-framed `REC_SEEN`, and was then silently skipped.
- **Changes made:**
  - `INDEPENDENT_ENV` now starts with `GOENV=off GOFLAGS=`.
    - Probed: go treats an empty variable as unset and falls back to the
      `go env -w` file. So `GOFLAGS=` alone does not clear a go env file's
      `-modfile`, and neither do the empty `GOPRIVATE=` etc. `GOENV=off`
      clears them.
    - Per-call `GOFLAGS=-mod=…` values come later in the env argv, so they
      still win.
  - Drift record membership is consulted only for a `safe_path` name. A
    record path never contains a newline, so any other name is unlisted.
  - New cases:
    - 9e: an absolute outside replace, a control, then `GOFLAGS=-modfile` and
      a go env file carrying `-modfile`;
    - 9b': adjacent `alpha` / `beta` record entries, plus `alpha\nbeta` and
      `other\nname`, with git and with find.
  - Mutants:
    - without `GOFLAGS=`: 1 FAIL;
    - without `GOENV=off`: 1 FAIL;
    - without the `safe_path` guard: 4 FAIL.
  - Results: 183/183; the real-tree dry run still gives `INTEGRITY_OK` and
    `DRIFT_NONE`. `go_engine.md` documents the isolated environment.
- **Files affected:** `.github/scripts/goengines_integrity.sh`,
  `tests/test_goengines_export_integrity.sh`, `aidocs/framework/go_engine.md`.

## Final Implementation Notes
- **Actual work done:**
  - Two-mode CI keyed on `goengines/EXPORT.txt`: the `mode` job, fail-closed
    job-level `if:` on `check` / `bench`, a new always-on `export-integrity`
    job, and step-level gating plus integrity and drift steps in the release
    `goengines` job.
  - The sums checks in both workflows verify every `*_SHA256SUMS.txt`.
  - `.github/scripts/goengines_integrity.sh` (`mode` / `check` / `drift`)
    implements `EXPORT.txt` format 1. Its checks are record, matrix, copy,
    gofmt, private-deps, independent-build and closure. Every platform-dependent
    check runs on each `build.sh` MATRIX target, and every go call uses one
    isolated environment.
  - New `tests/test_goengines_export_integrity.sh` (183 assertions).
  - `tests/test_goengines_build.sh` is multi-executable and adds a two-program
    fixture.
  - The workflow guard pins the two-mode wiring, with negative controls.
  - `ait engine test` export branch, pinned by E7b.
  - Docs: the `goengines/README.md` "Source of truth" section (format 1, the
    public-maintained files, CI in export mode, emergency fixes);
    `go_engine.md` (wiring and *Export mode*); n014 (closure-scoped
    allowlist, development location, two-mode note).
- **Deviations from plan:**
  - The record also refuses `EXPORT.txt` / `README.md` / `.gitignore` entries.
  - `check` gained the `copy` failure, and the matrix check reports an
    unreadable `build.sh`.
  - Drift enumeration is NUL-delimited, and drift output escapes control
    characters and annotation syntax.
  - The isolated environment includes `GOENV=off GOFLAGS=` (review rounds 1–2).
- **Issues encountered:** the review rounds found five real defects, all fixed
  with mutant-proven regression cases (Change Requests 1–2):
  - GOWORK bypass in the main-module lookup;
  - errexit exits on unreadable inputs;
  - C-quoted git names;
  - inherited `-modfile`, including through the go env file;
  - newline-name collisions in record membership.
- **Key decisions:**
  - The integrity script lives in `.github/scripts/`, because `goengines/`
    may hold only exported files plus README / .gitignore.
  - Legacy work is skipped only on a positive `export` answer.
  - `drift` never fails.
  - Unknown record keys are tolerated; `format:` is the version gate.
  - The README developer sections stay, scoped to legacy mode. The cutover
    task trims them.
  - `main` has no branch protection, so "required" is enforced through the
    release dependency.
- **Upstream defects identified:** None
