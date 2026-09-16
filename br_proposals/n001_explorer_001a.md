<!-- section: overview [dimensions: requirements_*] -->
## Overview

The goal is unchanged: a framework feature, generic across aitasks,
thinking_app, thinking_backend, aitasks_go and aitasks_mobile, that maintains
a relation between source files and test units, translates a task's change
set into the ranked set of tests that must run with a reason on every line,
runs them through project-defined runners under a standard contract, tracks
cost per unit by host class, learns from failures the map did not predict, is
enforced by gates so the map cannot rot silently, and is taught to agents by a
skill.

This proposal departs from the baseline in three places and corrects it in one.

1. **The engine and CLI are one static Go binary, `ait-testmap`.** Registry
   loading and merging, annotation scanning, dependency scanning, the graded
   walk, scheduling, the cost ledger, scoring and staleness detection all run
   in-process. Bash keeps only what must stay bash: the `ait` dispatcher arm,
   a thin resolver that finds the right binary for this host, the two gate
   verifier shells that append to the gate ledger, and the project-local
   runner scripts. The release workflow gains a `GOOS`/`GOARCH` matrix job
   that publishes four checksummed binaries per tag; `ait setup` fetches the
   one for the host into `~/.aitask/bin/`, and a single `go/build.sh` script
   is shared by CI and by the `install-dev` target so a framework developer
   rebuilds from source in one command. The tarball and every package-manager
   artifact stay architecture-independent.

2. **Annotation freshness is evidence-anchored, not clock-based.** Every
   annotation block carries `testmap:verified <sha> <date>`, written only by
   the CLI. Git preserves no mtimes, so "last modified" is a commit, not a
   timestamp: an annotation is stale when a covered source changed in
   `<anchor>..HEAD`, where the anchor is the newer of the verification stamp
   and the last recorded passing run of that test. `ait testmap stale`
   computes this for a task's change surface or for the whole repo in one
   pass, prints a line-protocol report in three classes (path rotted, run
   evidence missing, area drifted), and a procedure gate at the
   post-implementation review step hands those lines to an agent procedure
   that fixes annotations before the task's commit — so the fix lands in the
   same reviewed diff.

3. **High-level tests live in a separate table with a separate vocabulary.**
   Measured on this repo: 4 tests are in the serial carve-out, 29 boot a real
   tmux pane, 46 bash tests drive `./ait` end to end, and the widest one
   names 24 scripts. Such tests never carry `testmap:covers`. They declare
   `testmap:kind e2e` and bind to named **areas** (glob sets in
   `aitestmap/areas.yaml`) plus optional `testmap:trigger` globs, are stored
   under `aitestmap/suites/`, and are selected in a second, cost-budgeted
   lane. They never enter the edge graph, never contribute distance, and
   cannot pollute the per-file registry. A unit-table test with more than a
   configured number of `covers` lines fails `check` with a convert-to-suite
   hint.

The correction: the baseline assumed the gate verifier's exit mapping is
reused unchanged for runner exit codes `0/1/2/75`. The framework's verifier
contract is `0 pass / 1 fail / 2 skip / 3 error`, and
`gate_command_exit_contract` maps only command exits `0/1/2`; `75` appears
nowhere in the framework — it is thinking_app's admission code. The runner
contract keeps `75`, and the two verifier shells map it to verifier `3`
(could not evaluate, retried within the gate's budget, nothing appended to
the ledger).
<!-- /section: overview -->

<!-- section: architecture -->
## Architecture

```
ait  (bash dispatcher; `testmap)` arm)
 └─ .aitask-scripts/aitask_testmap.sh          thin: sources lib/aitask_path.sh, lib/testmap_bin.sh, execs the binary
     └─ ~/.aitask/bin/ait-testmap-<VERSION>    Go 1.26, CGO_ENABLED=0, ~8 MB, one per host
          internal/registry   merge aitestmap/registry/*.yaml + suites/*.yaml, owns: routing, check rules
          internal/annot      per-file-type comment scanner, `verified` stamp reader/writer
          internal/deps       bash/python/go/kotlin/gradle reverse-dependency scanners + plugin exec, digest cache
          internal/selectr    graded walk, rules engine, two lanes, prediction record
          internal/sched      resources (mutex/semaphore/admission/allocator), waves, critical path
          internal/runner     manifest/results contract, runner repository, batching, exit mapping
          internal/cost       Welford ledger, host classes, fold, last-pass anchors
          internal/feedback   score, attribute
          internal/stale      anchor resolution, git log walk, three staleness classes
          internal/gitx       git exec wrapper (no go-git): log --name-status, merge-base, rev-parse
          internal/platform   os/arch naming shared with build.sh
          ├─ exec: git, runner scripts, admission/allocator commands, scanner plugins
          └─ files: aitestmap/ (committed) · .aitask-gates/<task>/testmap/ (evidence)
                    $XDG_CACHE_HOME/aitasks/testmap/ (ledger, deps cache) · $XDG_RUNTIME_DIR/aitasks/testmap/locks/
.aitask-scripts/aitask_gate_testmap_check.sh   machine verifier: `<task> <attempt> <run-id>` → check
.aitask-scripts/aitask_gate_testmap_run.sh     machine verifier: select --lanes both --include-stale → schedule → run
.claude/skills/aitask-gate-testmap-fresh/      procedure gate: consumes `stale` lines, fixes annotations, `verify`
.claude/skills/aitask-testmap/                 agent skill: annotate, attribute, waive, verify, classify
go/                                            source (framework repo only; excluded from the release tarball)
```

**Boundary rule.** Anything that parses, walks, matches or schedules is Go.
Anything that touches the gate ledger, the task file, or the shell
environment is bash and calls the binary. The binary never writes to
`aitasks/`, `aiplans/`, or `.aitask-data/`, never appends to a gate ledger,
and never invokes `aitask_*.sh`; the bash verifiers own those side effects
through `aitask_gate.sh append`, exactly as `aitask_gate_tests_pass.sh` does.
Runner scripts stay project-local bash because they wrap project tools
(`bash tests/x.sh`, `pytest`, `go test -json`, `gradlew`); the binary speaks
to them only through the manifest/results files.

**Where the source lives.** `go/` at the root of the aitasks framework
repository: `go/go.mod` (`module github.com/beyondeye/aitasks/go`),
`go/cmd/ait-testmap/main.go`, `go/internal/<pkg>/`, `go/build.sh`,
`go/Makefile`. Not in the sibling `aitasks_go` project, which is a widget
library with its own release cadence; the engine must be version-locked to
`.aitask-scripts/VERSION`, which only this repository's release flow stamps.
`go/` is excluded from the release tarball: target projects never compile,
they download.

**Dependencies.** `gopkg.in/yaml.v3` (already used by `aitasks_go`) and
`github.com/bmatcuk/doublestar/v4` for `**` globs; everything else is the
standard library (`flag` verb table, `os/exec`, `encoding/json`,
`crypto/sha256`, `syscall.Flock`). No cobra, no go-git: git is already a hard
framework dependency and the same `git` the shell scripts use must see the
same repository state (worktrees, `commit --only`, task-data branches).

### Registry directory (extended)

```
aitestmap/
  config.yaml           knobs: max_covers_per_test, suite_budget_s, require_anchor, bootstrap_until, host_class
  runners.yaml          runner repository and path→runner bindings          (baseline)
  resources.yaml        named resources for concurrency                     (baseline)
  areas.yaml            named glob sets that high-level tests bind to       (new)
  registry/             unit-mapped tests: edges, rules, waivers            (baseline)
    _scanned.yaml       written only by `scan --apply`
    observed.yaml       written only by `attribute`
    <area>.yaml         hand-written; declares owns: globs
  suites/               area-bound tests: suites, triggers, waivers         (new)
    _scanned.yaml       written only by `scan --apply`
    observed.yaml       written only by `attribute`
    <name>.yaml         hand-written; declares owns: area names
  costs/<hostclass>.yaml   Welford summaries + last_pass anchors            (baseline + anchors)
  runners/*.sh          project-local runner scripts                        (baseline)
  scanners/*            optional project scanner plugins (executables)      (baseline slot, now a directory)
```

The two tables never cross: a `covers` path that names a suite fails `check`;
a rule's `select:` may name a suite explicitly, which is how "a tooling change
runs the screenshot gate" is written as data.
<!-- /section: architecture -->

<!-- section: data_flow -->
## Data Flow

**Authoring → registry.** An agent writes a test and its `testmap:` comment
block. `ait testmap scan --apply` asks every runner's `list` verb for the
units it owns, parses the comment blocks in-process (one `os.ReadFile` per
unit, a per-file-type leader regex), and rewrites `registry/_scanned.yaml`
and `suites/_scanned.yaml`. Rows keep the `verified: {sha, at}` stamp read
from the file. `check` validates the merged tables.

**Task → selection → run.** At claim, `aitask_change_surface.sh capture`
snapshots the dirty set (existing behaviour). At gate time the run verifier
calls `ait testmap select --task <id>`; the binary runs
`aitask_change_surface.sh list <id>`, parses `COMMITTED:`/`TASK:` lines as the
change set, refuses on any `UNKNOWN:`, loads the registry, resolves reverse
dependencies from the digest cache (rescanning only files whose sha256
changed), runs the graded walk for lane 1 and the area/trigger match for lane
2, unions `stale --class run` rows when `--include-stale` is set, applies the
cut knobs, writes the prediction record to
`.aitask-gates/<task>/testmap/prediction_<run-id>.json`, and prints the ranked
list. `schedule` groups units by runner and batch flag, resolves resources,
prints waves. `run` acquires resources in canonical order, invokes runners
with a manifest, reads `results.jsonl` and `runner.json`, checks
`units_expected == units_reported`, appends every result line to the local
ledger with the HEAD sha, and exits under the runner contract.

**Results → anchors → cost.** Each passing result line advances the unit's
`last_pass: {sha, host_class, at}` in the local ledger. `costs --update` folds
the ledger into `aitestmap/costs/<hostclass>.yaml` (Welford n/mean/sd/p95/last
plus `last_pass`). The anchor is therefore committed with the code and is
available on a fresh clone.

**Commit time → freshness.** At the post-implementation review step, the
`testmap_fresh` procedure gate runs `ait testmap stale --task <id>`. The
binary resolves an anchor per annotation row, groups rows by anchor, runs one
`git log --name-status --find-renames <anchor>..HEAD -- <paths>` per distinct
anchor (a bounded worker pool), and classifies. The agent procedure edits the
annotations the `STALE_PATH:` rows name, runs `ait testmap verify <test>...`
which rewrites the `testmap:verified` stamp to HEAD and re-scans, and records
the gate. The annotation fix and the code change land in the same task commit.

**Full run → score → attribute.** CI or a developer runs `ait testmap run
--all`. `score --prediction <file> --results <dir>` splits failures into
caught/missed; each miss becomes a proposed row in `registry/observed.yaml`
(missing edge) or `suites/observed.yaml` (missing trigger / area too narrow)
that `attribute` accepts with a decision and evidence.

**Release → host.** On a `v*` tag, the `build-go` matrix job builds four
binaries with `-X main.version=<VERSION>`, the `release` job attaches them
plus `ait-testmap_<VERSION>_checksums.txt` to the GitHub release next to the
tarball and shim. `ait setup` (and the resolver, lazily, after `ait upgrade`)
downloads the binary for `uname -s`/`uname -m`, verifies the sha256, installs
it as `~/.aitask/bin/ait-testmap-<VERSION>` and repoints the
`~/.aitask/bin/ait-testmap` symlink. `~/.aitask/bin` is already on PATH via
`lib/aitask_path.sh`.
<!-- /section: data_flow -->

<!-- section: go_engine -->
## The Go Engine

### Why Go here, and what it actually speeds up

The wall time of a selected run is dominated by the tests themselves; the
engine's own latency matters because `select`, `check` and `stale` run at
every gate and every commit step, `explain` runs interactively, and `scan`
walks every test file. Today's framework pays, per Python invocation, the
interpreter start plus `python_resolve.sh` venv resolution, and the framework
already routes `ait board` through a PyPy fast path for exactly this class of
cost (`aidocs/framework/python_tui_performance.md`). For the aitasks repo the
registry will hold roughly 722 test units, an estimated 2,500 edges, and 266
scanned source files; a pure-Python YAML parse of that many rows is in the
hundreds of milliseconds before any walk starts.

Targets on the aitasks repo, warm digest cache, measured by
`go test -bench` fixtures committed with the engine:

| verb | target | what dominates |
|---|---|---|
| `select` | < 100 ms | YAML load + walk |
| `select` cold (deps rescan) | < 1 s | 266 files regex-scanned, sha256 per file |
| `scan` | < 400 ms | 722 file reads + comment parse |
| `check` | < 300 ms | merged-table rules + `list` per runner |
| `stale --task` | < 300 ms | ~50 distinct anchors → 50 concurrent `git log` calls |
| `stale --all` | < 2 s | same, whole registry |

These are targets, not measurements; they are an explicit assumption below.

### CLI shape

`ait testmap <verb>`, verbs: `scan | check | select | schedule | run | score |
attribute | declare | explain | costs | stale | verify | areas | classify |
version`. Every verb is batch-safe: line protocol `KEY:value` on stdout for
scripts, `--json` for TUIs, diagnostics on stderr, exit codes per verb
documented in `ait testmap <verb> --help`. Verbs that mutate the tree
(`scan --apply`, `verify`, `declare`, `attribute`, `costs --update`) write
only the files listed in the registry write-routing rules and print
`WROTE:<path>` per file.

### Version handshake and resolver

`ait-testmap version` prints the value injected at build time. The resolver
`lib/testmap_bin.sh: resolve_testmap_bin()` chooses, in order:

1. `$AIT_TESTMAP_BIN` if executable (explicit override; any version accepted,
   a `TESTMAP_BIN_OVERRIDE:` notice goes to stderr).
2. `~/.aitask/bin/ait-testmap-dev` when `AIT_TESTMAP_DEV=1` (version must
   read `<VERSION>-dev+<sha>` for the current `VERSION`).
3. `~/.aitask/bin/ait-testmap-<VERSION>` (version must equal
   `.aitask-scripts/VERSION`; mismatch is a hard error, never a silent
   fallback).
4. If absent and `AIT_TESTMAP_FETCH != 0`: one fetch attempt through the same
   function `ait setup` uses, then retry step 3.
5. `die "ait-testmap <VERSION> not installed for <os>/<arch>; run 'ait setup'
   or build from source (see aidocs/framework/go_engine.md)"`.

`aitask_testmap.sh` is the only script that resolves the binary; the two gate
verifiers source the same lib, following the extension-points rule that a
framework binary is reached through a sourced lib from every script that may
call it, never through a shell-rc PATH edit.
<!-- /section: go_engine -->

<!-- section: binary_distribution -->
## Binary Distribution and Developer Rebuilds

### Release CI

`release.yml` gains a `build-go` job between `plan` and `release`:

```yaml
  build-go:
    needs: plan
    runs-on: ubuntu-latest
    strategy:
      matrix: { goos: [linux, darwin], goarch: [amd64, arm64] }
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with: { go-version-file: go/go.mod, cache-dependency-path: go/go.sum }
      - run: go/build.sh release ${{ matrix.goos }} ${{ matrix.goarch }} ${{ needs.plan.outputs.version }}
      - uses: actions/upload-artifact@v4
        with: { name: ait-testmap-${{ matrix.goos }}-${{ matrix.goarch }}, path: go/dist/ }
```

`go/build.sh` is the single place the build command lives:
`CGO_ENABLED=0 GOOS=$2 GOARCH=$3 go build -trimpath -ldflags "-s -w -X
main.version=$4" -o dist/ait-testmap_$4_$2_$3 ./cmd/ait-testmap`. The
`release` job adds `needs: build-go`, downloads the four artifacts, runs
`sha256sum` into `ait-testmap_<VERSION>_checksums.txt`, and appends all five
files to the `files:` list of both `action-gh-release` steps. The
`Verify VERSION file matches tag` step is unchanged and still gates the
release; the injected `main.version` is the same string, so a binary can
never claim a version its tarball does not have.

`release-packaging.yml` is untouched: Homebrew, AUR, `.deb` and `.rpm` keep
shipping only the shim, and `nfpm.yaml` stays `arch: all`. The shim-only
model in `aidocs/packaging/packaging_strategy.md` gains one section stating
that framework binaries are release assets fetched by `ait setup` per host,
never bundled by a package manager.

A second, PR-time job (`go-check` in `contribution-check.yml`) runs
`gofmt -l`, `go vet ./...` and `go test ./...` under `go/`, so an engine
regression is caught before a tag.

### Install and upgrade

`aitask_setup.sh` gains `_ensure_testmap_binary()` and a new
`lib/platform_detect.sh` (`ait_platform_os` → `linux|darwin`, WSL reported
as `linux`; `ait_platform_arch` → `amd64|arm64`, mapped from `x86_64`,
`aarch64`, `arm64`; anything else returns `unsupported`). The function:

1. Reads `.aitask-scripts/VERSION`; if `~/.aitask/bin/ait-testmap-<VERSION>`
   exists and its recorded sha256 (`~/.aitask/bin/ait-testmap-<VERSION>.sha256`)
   matches, returns.
2. Downloads `ait-testmap_<VERSION>_<os>_<arch>` and
   `ait-testmap_<VERSION>_checksums.txt` from
   `https://github.com/beyondeye/aitasks/releases/download/v<VERSION>/` into a
   temp dir with `curl -fsSL --max-time 60`, the same CDN URL family
   `install.sh` uses for the tarball (no API call, no rate limit).
3. Verifies the sha256 against the checksums file; a mismatch deletes the
   download and fails with `TESTMAP_BINARY:checksum_mismatch`.
4. `install -m 0755` to the versioned path, writes the `.sha256` sidecar,
   atomically repoints `~/.aitask/bin/ait-testmap` (symlink, `ln -sfn` via a
   temp name and `mv -T`), prunes versioned binaries older than the two most
   recent.
5. On `unsupported` arch or `AIT_TESTMAP_FETCH=0` / `ait setup --no-testmap`:
   prints `TESTMAP_BINARY:skipped:<reason>` and returns 0; `ait testmap`
   later fails with the build-from-source hint. The rest of `ait setup` never
   depends on the binary.

`ait upgrade` changes nothing: it rewrites `.aitask-scripts/VERSION`, so the
next `ait testmap` (step 4 of the resolver) or `ait setup` fetches the
matching binary. Windows is not built: the packaging strategy already defers
a Windows shim, and WSL resolves to `linux`.

### Rebuilding from source for framework development

```
cd go && make install-dev        # build.sh dev → ~/.aitask/bin/ait-testmap-dev, version <VERSION>-dev+<short-sha>
export AIT_TESTMAP_DEV=1         # resolver step 2 now wins
./ait testmap select --task t1234
make dist                        # build.sh release for all four targets into go/dist/ (release dry-run)
make test                        # go vet + go test ./...
```

`make install-dev` is the one command the mandate asks for; `ait testmap
--dev-build` is a convenience arm in `aitask_testmap.sh` that runs it and
re-execs. Because CI and `make` both call `go/build.sh`, the local artifact
and the released artifact cannot drift in flags. A framework developer
testing the engine inside another project (thinking_app) sets
`AIT_TESTMAP_BIN=/path/to/aitasks/go/dist/ait-testmap_..._linux_amd64`.
`aidocs/framework/go_engine.md` documents the layout, the resolver order, the
version handshake and the build script.
<!-- /section: binary_distribution -->

<!-- section: freshness -->
## Annotation Freshness

### The stamp

```
# testmap:covers .aitask-scripts/aitask_gate_pass.sh
# testmap:covers .aitask-scripts/lib/gate_verifier_lib.sh
# testmap:kind unit
# testmap:verified 3f2a9c1 2026-09-16
```

`testmap:verified <short-sha> <YYYY-MM-DD>` is the date and commit at which
the block was last confirmed against the sources it names. It is written only
by `ait testmap verify <test>...` (or `scan --stamp` at bootstrap) and copied
into `_scanned.yaml` as `verified: {sha: 3f2a9c1, at: 2026-09-16}`; the
`check` gate fails a hand-edited stamp whose sha is not an ancestor of HEAD.
The date is for humans; the sha is what the check uses, because a clone,
a checkout or a rebase resets mtimes and git records none.

### The anchor

Re-reading an annotation every time its source changes would be noise:
`aitask_update.sh` is named by 72 tests, so one edit would flag 72 blocks.
What actually goes stale is narrower, and most of it is self-healing:

- If the test **ran and passed** at a commit after the source change, the
  edge demonstrably still holds. So every passing result line records
  `last_pass: {sha: <HEAD at run>, host_class, at}` in the local ledger and,
  after `costs --update`, in the committed `costs/<hostclass>.yaml`.
- The **anchor** of a unit is the newest of `verified.sha` and any
  `last_pass.sha` (local ledger first, then committed summaries, any host
  class) that is an ancestor of HEAD. A sha on another branch is ignored.
  A unit with no anchor is `UNVERIFIED`.

The stamp lives in the test file so the mandate's "field on the annotation"
is met and a reviewer sees it; the run evidence lives in the ledger so gate
runs never dirty test files.

### Classes

`ait testmap stale [--task <id> | --all] [--class path,run,area] [--strict] [--json]`

```
ANCHOR:<test>|<sha>|verified|last_pass|none
STALE_PATH:<test>|<source>|deleted|<culprit_task>
STALE_PATH:<test>|<source>|renamed|<new_path>|<task>
STALE_RUN:<test>|<source>|<n_commits>|<task_ids>
STALE_AREA:<suite>|<area>|<n_files>|<n_commits>
UNVERIFIED:<test>
DECISION:FRESH|STALE
```

- **`STALE_PATH`** — a covered path was deleted or renamed after the anchor
  (`--name-status --find-renames=50%` on the walk). This is the case that
  needs an annotation edit, and it is fail-closed: `check` fails on any
  `STALE_PATH` row, and `--strict` makes `stale` exit 1 on it for CI.
- **`STALE_RUN`** — a covered source changed after the anchor and the test
  has not passed since. No edit is needed; the row is a selection input.
  `select --include-stale` adds the unit at distance `s` with reason
  `stale-evidence <source> <n_commits>`, which catches a test that a
  previous task's waiver or postponed run skipped. The run verifier passes
  this knob by default.
- **`STALE_AREA`** — a suite's area had files change after the suite's
  anchor. Same treatment as `STALE_RUN` in lane 2.
- **`UNVERIFIED`** — no anchor at all. Tolerated while
  `config.yaml: bootstrap_until` is in the future; after the first full run
  every unit has a `last_pass` anchor, and `require_anchor: true` turns
  `UNVERIFIED` into a `check` failure.

Implementation: rows are grouped by anchor sha; for each distinct anchor one
`git log --format=%H%x00%ct%x00%s --name-status --find-renames=50%
<anchor>..HEAD -- <paths>` runs under a worker pool capped at four; task ids
are parsed from `(t<N>)` subjects, matching `aitask_verification_stale.sh`'s
`CHANGED:<path>|<n_commits>|<task_ids>` contract so the two staleness reports
read alike. Paths are passed with `:(literal)` pathspecs.

### The procedure gate

`testmap_fresh` is a `kind: procedure` gate (the `docs_updated` shape), so
it is dispatched at the post-implementation review step before the review
prompt and before the task's `(t<id>)` commit. It is not a git hook: the
framework installs none, `commit --only` makes a pre-commit hook unusable
(`aitask_sync.sh` documents why), and a Claude Code `Stop`/`PostToolUse`
hook must stay silent and cannot take an editing decision. The
`aitask-gate-testmap-fresh` skill:

1. `aitask_gate.sh begin-procedure <task> testmap_fresh` → `RUN_ID:`, `ATTEMPT:`.
2. `ait testmap stale --task <task>` → parse lines.
3. For each `STALE_PATH` row: open the test, replace or remove the `covers`
   line (renamed → new path; deleted → the successor file if the procedure
   can identify it from the culprit task's plan, else remove and note), then
   `ait testmap verify <test>` — rewrites the stamp to HEAD/today, re-scans,
   prints `WROTE:`.
4. `STALE_RUN` / `STALE_AREA` rows: report the count; they are consumed by
   the run gate.
5. `UNVERIFIED` rows outside the bootstrap window: prompt once — verify now
   or waive with an `until` date.
6. `aitask_gate.sh append --only-if-running <run-id> ... pass|fail`.

Standalone use: `ait testmap stale --all --strict` is a weekly CI job and a
board action; `ait testmap verify --all-fresh` stamps every row whose anchor
is a `last_pass` newer than its `verified` stamp, for a maintainer who wants
the file stamps to reflect run evidence.
<!-- /section: freshness -->

<!-- section: suite_lane -->
## High-Level Tests: the Suite Lane

### Why a second table

A test that boots `./ait board` in tmux exercises every module the board
loads; `tests/test_brainstorm_cli.sh` statically names 24 scripts. Encoded as
`covers` edges these tests would sit at distance 1 from most of the tree,
every edit would make their blocks stale, and `_scanned.yaml` would carry
thousands of rows that mean "everything". So they are not edges.

### Vocabulary

```
# testmap:kind e2e                     integration | e2e | device   (unit is not allowed here)
# testmap:area brainstorm              one or more named areas from aitestmap/areas.yaml
# testmap:area agentcrew
# testmap:trigger .aitask-scripts/lib/launch_modes*.py     extra globs; always select when hit
# testmap:runner bash-file
# testmap:needs tmux-server
# testmap:batch no
# testmap:verified 3f2a9c1 2026-09-16
```

```yaml
# aitestmap/areas.yaml
contract: 1
areas:
  brainstorm: {paths: [".aitask-scripts/aitask_brainstorm_*.sh", ".aitask-scripts/brainstorm/**"]}
  agentcrew:  {paths: [".aitask-scripts/aitask_crew_*.sh", ".aitask-scripts/agentcrew/**", ".aitask-scripts/lib/agentcrew_utils.*"]}
  board:      {paths: [".aitask-scripts/board/**", ".aitask-scripts/aitask_board.sh"]}
  tui_common: {paths: [".aitask-scripts/lib/tui_*.py", ".aitask-scripts/lib/tmux_exec.*"]}
```

`aitestmap/suites/_scanned.yaml` rows:
`{test, kind, runner, areas: [...], triggers: [...], needs: [...], from: annotation, verified: {sha, at}}`.
Hand-written `suites/<name>.yaml` files declare `owns:` as area names and
may add `waivers` (a suite deliberately excluded from selection until a
date). `suites/observed.yaml` is written only by `attribute`. When a project
already has `aitasks/metadata/code_areas.yaml`, `ait testmap areas
--import-codemap` seeds `areas.yaml` from it; the two files stay separate
because code areas are single directories and suite areas need glob sets.

### Check rules for suites

- `kind` ∈ {integration, e2e, device}; a suite carrying `covers` fails;
  a unit-table test carrying `area` or `trigger` fails.
- At least one `area` or `trigger`; every named area exists; every area glob
  matches at least one file in the tree (an empty area is the rot signal for
  globs).
- A unit-table test with more than `config.yaml: max_covers_per_test`
  (default 8) `covers` lines fails with `CONVERT_TO_SUITE:<test>|<n>`.
- `ait testmap classify --suggest` lists suite candidates from heuristics —
  `tmux new-session`, an exec of `./ait`, membership in a runner's serial
  carve-out, more than the covers limit — with the matched heuristic per
  line, for the bootstrap pass. On this repo that is roughly 60–70 files;
  the 107 files that use Textual's headless `App.run_test` are not flagged,
  they are narrow and stay unit-mapped.

### Selection in lane 2

A suite is selected when the change set intersects any glob of any of its
areas, or any trigger. Reason lines read `area(brainstorm) <-
.aitask-scripts/aitask_brainstorm_init.sh` or `trigger(lib/launch_modes*.py)
<- .aitask-scripts/lib/launch_modes.py`. Lane knobs: `--suites auto|all|none`
and `--suite-budget <s>`. Under `auto` (the gate default) trigger hits are
always run; area hits are ordered by cost p95 ascending and run until
`suite_budget_s` (config, default 600) is spent, the remainder printed as
`DEFERRED:<suite>|budget` so the cut is explicit. Suites never contribute
distance, never appear in `implies`, and are sinks in the walk. A rule may
`select:` a suite by name, which is how thinking_app's "tooling change runs
`verify-active`" becomes data. The prediction record and the estimate line
report the two lanes separately.

### Feedback for suites

A full-run failure in a suite the prediction did not select yields a
proposed `suites/observed.yaml` row naming the changed paths outside its
areas; `attribute` accepts it with `missing-trigger` (adds a trigger glob) or
`area-too-narrow` (adds a path to the area) and records task and run id.
<!-- /section: suite_lane -->

<!-- section: selection [dimensions: component_selector] -->
## Selection: the Graded Walk Plus a Lane

Lane 1 is the baseline walk unchanged in semantics: distance 0 for a changed
test and for escalation, 1 for a direct edge, 2 for one hop through the
reverse-dependency graph, rules injecting at a declared distance with
`select`, `implies` and `escalate` effects; the output is the whole ranked
list with a reason per line and every cut is a knob applied afterwards
(maximum distance, time budget from cost stats, kind filter, resource filter).
Two additions: distance `s` for `stale-evidence` rows when `--include-stale`
is set, and lane 2 for suites as described above. Reverse dependencies come
from the in-process scanners (bash `source` and sibling invocations, python
imports, `go list -deps -json`, Kotlin imports within a module, the Gradle
module graph) plus executable plugins under `aitestmap/scanners/` that speak
one JSON line per file (`{"file":..., "deps":[...]}`); results are cached
under `$XDG_CACHE_HOME/aitasks/testmap/deps/<sha256>.json`. The change set
comes from `aitask_change_surface.sh list <task>`: `COMMITTED:` and `TASK:`
lines are the change set, an `UNKNOWN:` line refuses selection with exit 1,
and a changed source with no edge, no rule, no area, and no waiver refuses
the same way.

```
tests/test_gate_pass.sh              d=1  edge(annotation)  .aitask-scripts/aitask_gate_pass.sh
tests/test_gate_orchestrator.sh      d=2  dep  lib/gate_verifier_lib.sh <- aitask_gate_pass.sh
tests/test_gate_ledger.sh            d=2  rule gates-area
tests/test_update_risk.sh            d=s  stale-evidence .aitask-scripts/aitask_update.sh 3
tests/test_brainstorm_cli.sh         L2   area(brainstorm) <- .aitask-scripts/aitask_brainstorm_init.sh   est 41s
tests/test_board_header_row_live.py  L2   DEFERRED budget  area(board)                                    est 48s
```
<!-- /section: selection -->

<!-- section: runner_contract [dimensions: component_runner_contract] -->
## Runner Contract and Exit Mapping

The runner repository, bindings, `describe`/`list`/`run` verbs, manifest and
`results.jsonl`/`runner.json` formats, batching semantics and whole-suite
runners are the baseline's. The runner exit contract stays `0` every unit
passed, `1` a unit failed or the mechanism broke (`cause=` present only in
the mechanism case), `2` did not run for a self-clearing reason, `75`
admission refused — so thinking_app's tools wrap without change. The
engine's own `run` verb exits under the same contract and additionally
`64` for a usage or configuration error.

The verifier shells map engine exits to the framework's verifier contract:

| engine exit | `aitask_gate_testmap_run.sh` | `aitask_gate_testmap_check.sh` |
|---|---|---|
| 0 | 0 pass | 0 pass |
| 1 | 1 fail | 1 fail |
| 2 (nothing selected, or runner self-cleared) | 2 skip | — |
| 75 (admission refused) | 3 error → retried within `max_retries` | — |
| 64 / other | 3 error | 3 error |

Verifier 3 appends nothing to the ledger, which is the existing contract for
"could not evaluate". `gate_command_exit_contract` is not involved: these are
dedicated verifiers, not `run_command_gate` wrappers, because their command
is fixed and their skip semantics are richer than a config-key opt-in.
<!-- /section: runner_contract -->

<!-- section: gates_and_cli [dimensions: component_gates] -->
## Gates

Registered in `.aitask-scripts/gates_reference.yaml` (canonical) and copied
to `aitasks/metadata/gates.yaml`; no new field keys are needed (`kind:` and
`unlocks:` already exist):

```yaml
  testmap_fresh:
    type: machine
    kind: procedure
    description: "Source-to-test annotations re-verified for the task's change surface"
    blocks_dependents: false
    verifier: aitask-gate-testmap-fresh
    unlocks: [testmap_check]
  testmap_check:
    type: machine
    description: "Test map consistent: changed sources mapped, tests registered, no drift, no rotted paths"
    blocks_dependents: false
    verifier: aitask-gate-testmap-check
    max_retries: 0
    timeout_seconds: 120
    unlocks: [testmap_run]
  testmap_run:
    type: machine
    description: "Selected tests (both lanes, stale-evidence included) pass"
    blocks_dependents: true
    verifier: aitask-gate-testmap-run
    max_retries: 3
    timeout_seconds: 1800
```

`testmap_fresh` runs at the review step so its edits are reviewed;
`testmap_check` and `testmap_run` run with the machine gates at
post-implementation. A project enables them by adding the three names to its
profile's declared gate set; `tests_pass` may stay declared for projects that
keep a monolithic `test_command`, and the manual-verification reachable-gate
filter leaves all three unreachable for `manual_verification` tasks, which
is correct. The full run is `ait testmap run --all`, the same machinery with
every unit selected, invoked by CI or by hand and writing the same evidence
under `.aitask-gates/<task>/testmap/` or, for CI, a directory of its choice.
<!-- /section: gates_and_cli -->

<!-- section: components [dimensions: component_*] -->
## Components

<!-- section: component_go_engine -->
### Go engine and CLI (new)

`go/cmd/ait-testmap` plus the `internal/` packages listed in the
architecture. Go 1.26 (`go.mod` pins it; `actions/setup-go` reads the file),
`CGO_ENABLED=0`, `-trimpath -ldflags "-s -w -X main.version=<VERSION>"`.
Two third-party modules: `gopkg.in/yaml.v3`, `github.com/bmatcuk/doublestar/v4`.
Line-protocol stdout, `--json` alternative, stderr diagnostics, per-verb exit
contracts. Host-scope locks are `flock` on files under
`$XDG_RUNTIME_DIR/aitasks/testmap/locks/<name>` (fallback
`$XDG_CACHE_HOME/aitasks/testmap/locks/` when the runtime dir is unset);
worktree scope keys on the checkout path's sha256. Unit tests are table-driven
against fixture repositories under `go/internal/testdata/`, created with
`git init` in a temp dir, never against the framework repo.
<!-- /section: component_go_engine -->

<!-- section: component_binary_distribution -->
### Binary distribution and dev rebuild (new)

`go/build.sh` (the one build command), `go/Makefile` (`build`, `test`,
`install-dev`, `dist`), the `build-go` matrix job and the five extra release
assets in `release.yml`, the `go-check` PR job in `contribution-check.yml`,
`lib/platform_detect.sh`, `lib/testmap_bin.sh` (resolver and version
handshake), `_ensure_testmap_binary()` in `aitask_setup.sh` with
`--no-testmap` / `AIT_TESTMAP_FETCH=0`, the `.sha256` sidecar and
two-version prune under `~/.aitask/bin/`, `aidocs/framework/go_engine.md`,
and a paragraph in `aidocs/packaging/packaging_strategy.md`. Tests:
`tests/test_testmap_bin_resolve.sh` (resolver order, version mismatch is a
hard error, override notice) and `tests/test_platform_detect.sh`.
<!-- /section: component_binary_distribution -->

<!-- section: component_freshness -->
### Freshness: stamps, anchors, `stale`, `verify`, procedure gate (new)

`internal/stale` and `internal/gitx`; the `testmap:verified` stamp reader and
writer in `internal/annot`; `last_pass` anchors in `internal/cost`; the
`stale`, `verify` verbs; the `testmap_fresh` gate entry; the
`aitask-gate-testmap-fresh` procedure skill (Claude Code first, then ported to
`.agents/skills/` and `.opencode/skills/` as separate tasks per the framework's
skill-porting rule); `config.yaml: bootstrap_until, require_anchor`.
<!-- /section: component_freshness -->

<!-- section: component_suite_registry -->
### Suite registry and areas (new)

`aitestmap/areas.yaml`, `aitestmap/suites/`, the `area`/`trigger`
annotations, the suite rows in `internal/registry`, the lane-2 matcher in
`internal/selectr`, the suite check rules and `max_covers_per_test` guard,
`ait testmap areas` (`--import-codemap`, `--list`, `--check`), `ait testmap
classify --suggest`, and the `missing-trigger` / `area-too-narrow` decisions
in `attribute`.
<!-- /section: component_suite_registry -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer

`internal/registry`: merges `registry/*.yaml` into edges, rules, waivers and
`suites/*.yaml` into suites, triggers, waivers; enforces `owns:` routing for
both (globs for the unit table, area names for the suite table); write
routing (`scan --apply` → `_scanned.yaml` in each table, `attribute` →
`observed.yaml` in each, `declare` → the owning hand file, refusing when no
`owns:` matches); the check rules: duplicate rule names, waiver-with-edge,
annotation rows whose annotation is gone, expired waivers, stamps not
reachable from HEAD, `STALE_PATH` rows, suite rules above, and the
cross-table exclusions.
<!-- /section: component_registry_loader -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner

`internal/annot`: per-file-type comment leader (`#`, `//`, `--`; Python
module docstrings are also searched for `testmap:` lines so the repo's
docstring-`Covers:` habit has a home), the `covers/kind/runner/needs/batch/
area/trigger/verified` vocabulary, refusal of unknown `testmap:` keys with a
line number, and the stamp writer used by `verify`. Produces both
`_scanned.yaml` files from the union of every runner's `list` output.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners

`internal/deps`: built-in scanners for bash (`source`/`.` lines and
`$SCRIPT_DIR/aitask_*.sh` sibling invocations), python (`import`/`from`
resolved within `.aitask-scripts/`), Go (`go list -deps -json ./...` executed
once per package set), Kotlin (imports within a Gradle module) and the Gradle
module graph (`settings.gradle.kts` includes plus `project(":x")`
dependencies); executable plugins in `aitestmap/scanners/` with the one-JSON-
line-per-file contract; results keyed by file sha256 in the XDG cache and
invalidated per file, so a warm `select` rescans only what changed.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector

`internal/selectr`: change-set intake from `aitask_change_surface.sh list`
(refusing on `UNKNOWN:`), lane-1 graded walk with the rules engine, lane-2
area/trigger match with the budget knob, `--include-stale` union, cut knobs,
the prediction record (`task, knobs, change set, lane-1 units with distances,
lane-2 units with reasons and deferrals, escalations, estimate per lane`),
and `explain <test|source>` printing the binding chain and every reason path.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository

`internal/runner`: `runners.yaml` loading, deterministic binding resolution
(annotation, first matching binding, refuse), manifest writing, `results.jsonl`
and `runner.json` reading, `units_expected`/`units_reported` reconciliation,
batching by runner and `batch` flag, per-unit timeouts, and the exit contract
`0/1/2/75/64`. Reference runner scripts remain bash under
`aitestmap/runners/`.
<!-- /section: component_runner_contract -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources

`internal/sched`: `resources.yaml` kinds (mutex, semaphore, admission,
allocator), scopes (host, worktree, run), `acquired_by: runner` planning,
canonical-order acquisition with release on every exit path (deferred
`Unlock` plus a signal handler), batch-level holds, the `schedule` report
(waves, holds, critical path, estimated wall against serial sum), and the
check half flagging a runner default resource a unit does not declare.
Whether v1 executes waves concurrently or serially-with-report stays a
config switch (`config.yaml: concurrency: report|execute`, default `report`).
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger

`internal/cost`: local ledger `$XDG_CACHE_HOME/aitasks/testmap/ledger/<hostclass>.jsonl`
appended per result line with `run_id, unit, status, duration_ms, head_sha`;
`costs --update` folds into `aitestmap/costs/<hostclass>.yaml` with Welford
`n, mean, sd, p95, last` and the new `last_pass: {sha, at}` per unit; host
class from `config.yaml: host_class`, defaulting to the hostname. The estimate
for a selection is the sum of unit means plus one recorded overhead per runner
invocation, reported per lane.
<!-- /section: component_cost_ledger -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools

`internal/feedback`: `score --prediction <file> --results <dir>` splitting
failures into caught/missed for both lanes; `attribute` recording
`missing-edge`, `test-wrong`, `source-wrong` for the unit table and
`missing-trigger`, `area-too-narrow` for the suite table, each with task and
run id as evidence, written to the respective `observed.yaml`.
<!-- /section: component_feedback_tools -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates

Three entries (`testmap_fresh`, `testmap_check`, `testmap_run`) in
`gates_reference.yaml`; the two bash verifiers under `.aitask-scripts/`
following the verifier template (log to
`.aitask-gates/<task>/<gate>_<run-id>.log`, append via `aitask_gate.sh
append`, exit the appended status); registered in the helper-script
whitelist; the exit mapping table above.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skill

`aitask-testmap`: the obligations — annotate what a new test covers or which
areas a new high-level test binds to; give a new source an edge, rule, area
or waiver; attribute before the gate when a failing test is fixed by editing
a source it had no edge to; run `verify` after editing an annotation; use
`classify --suggest` when unsure which table a test belongs to. Plus the
`aitask-gate-testmap-fresh` procedure skill described under freshness.
<!-- /section: component_skill -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners

`bash-file` (one process per file, `needs: [git-index]`), `pytest` (batched,
junitxml for per-unit timing, respects the project's serial carve-out by
honouring `batch: no`), `go-test` (per file, `-run` regex derived from
`func Test` names, `-json` for timing), `gradle-class` (batched `--tests`
FQNs, `needs: [heavy-run]`, `acquired_by: runner`), a whole-suite wrapper
(`unit: suite`, wraps `screenshot-tests.sh verify-active` and
`run_script_tests.sh`), and a device runner using the emulator allocator. All
bash, all speaking the three verbs; a Go-side `runner` package validates
their output, it does not replace them. A seventh, `go-test` over `go/`
itself, lets the framework's own engine tests ride the same map.
<!-- /section: component_reference_runners -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Inherited, unchanged:

- Static file-level facts are enough for v1; the edge schema keeps an
  optional `symbols` slot for a later hunk-level matcher.
- The change-surface script's attribution is the right intake; selection
  never reads a raw `git diff`, and an `UNKNOWN:` path refuses selection.
- Existing project locks and allocators can be wrapped as resources without
  changing them.
- Runners can report per-unit timing inside a batch from their tool's own
  report format.
- Every target repo will accept a root `aitestmap/` directory and runner
  scripts committed into its code tree.
- The annotation token `testmap:` does not collide with existing prose in any
  target repo (this repo's `Covers:` lines are prose and are left alone).

Inherited, revised:

- The gate verifier exit contract is reused — but as the verifier contract
  `0/1/2/3`, through two dedicated verifier shells, not through
  `gate_command_exit_contract`; runner `75` maps to verifier `3`.

New:

- A Go toolchain (≥ 1.26) is available in release CI via `actions/setup-go`
  and on framework developers' machines; target-project users never need it.
- A host running `ait setup` or the first `ait testmap` after an upgrade can
  reach `github.com/beyondeye/aitasks/releases`; air-gapped hosts use
  `AIT_TESTMAP_BIN` or a pre-seeded `~/.aitask/bin/`.
- Git history is the freshness clock: commit-SHA reachability, never mtime.
  A shallow clone whose anchors are outside the fetched history reports those
  units `UNVERIFIED` rather than guessing.
- A passing run of a test at commit C is evidence that its annotated edges
  held at C, on any host class.
- The blast radius of a high-level test is expressible as a union of area
  globs plus trigger globs; what that misses surfaces through `score` as an
  observed trigger.
- The engine latency targets in the table above are achievable on the
  aitasks repo with a warm cache; they are validated by committed benchmarks
  before the gates are enabled here.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Advantages (inherited): selection is computed, explained and scored rather
than remembered; blast radius becomes data instead of prose; fail-closed
checks make rot visible; one runner contract lets five different repos share
one selector, one scheduler and one cost model; wrapping existing locks and
gates avoids rewriting proven tooling. New: `select`/`check`/`stale` are
cheap enough to run at every gate and commit step without a venv; the
freshness anchor turns the "map looks current and is not" risk from
undetectable into a computed report, and most staleness heals itself through
run evidence; the suite lane keeps the unit registry small and its stamps
meaningful.

Disadvantages (inherited): a merged registry directory needs more CLI logic
than one file — now two merged directories, mitigated by both sharing one
loader and one `owns:` model; fail-closed enforcement means bootstrapping
each repo needs an explicit waiver pass before `testmap_check` can be
enabled, and now also a first full run before `require_anchor` can be turned
on; static scanners overselect on hot files and cannot see runtime coupling.

New disadvantages:

- Two toolchains in one framework. Mitigation: the Go/bash boundary rule
  above, a PR-time `go-check` job, and Go source confined to `go/`, excluded
  from the tarball, so nothing a target project receives needs Go.
- `ait setup` acquires a network fetch with checksum verification — the
  first release asset the framework downloads for itself. Mitigation: the
  CDN URL family `install.sh` already uses, the `.sha256` sidecar, the
  `--no-testmap` opt-out, and the fact that the rest of setup never depends
  on the binary.
- Area globs are coarser than edges: a broad area over-selects its suites on
  every edit inside it, and a suite that depends on a file outside its areas
  is under-selected until a full run scores it. Mitigation: the budget knob
  with explicit `DEFERRED:` lines, triggers for the known sharp edges, and
  the `missing-trigger` attribution path.

Risks:

- (inherited) An agent that edits sources without attributing produces a map
  that looks current and is not; now reduced, not removed — `stale` sees a
  changed source with no run evidence, but cannot see a new coupling with no
  edge at all; only `score` on a full run can.
- (inherited) A batch runner that misreports per-unit results corrupts
  attribution and cost, and now also anchors: a false `pass` line advances
  `last_pass`. Mitigation: `units_expected`/`units_reported` reconciliation,
  and `verify --all-fresh` never stamps from a run whose `runner.json` has a
  `cause`. A wrongly scoped resource either serialises everything or protects
  nothing.
- A flaky pass advances the anchor as surely as a real one. Mitigation: the
  ledger records `status` per run so `costs` can expose a flake rate, and a
  unit above a configured flake threshold is excluded from anchoring.
- The version handshake is strict by design: an `ait upgrade` on a host that
  cannot fetch leaves `ait testmap` refusing to run until a matching binary
  is supplied. That is the intended fail-closed behaviour, and the error
  names the fix.
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Should the `verified` stamp be optional for unit-table tests whose only
   anchor is run evidence, so that bootstrap does not rewrite 720 files, with
   `scan --stamp` reserved for suites and hand-declared edges?
2. Is `max_covers_per_test: 8` the right default guard, or should the guard
   be relative (a test covering more than N% of an area is a suite)?
3. Does lane 2 need a distance-like grade — for example, area hit through a
   scanned dependency counts as a weaker hit than a direct file in the area —
   or is trigger/area/budget enough?
4. Should the anchor consider `last_pass` from any host class, or only from
   the host class that will run the gate?
5. Do the deb/rpm packages, which today pull the shim only, gain a
   `Recommends:` on nothing new, or should the postinstall message mention
   the binary fetch that `ait setup` performs?
6. Is `report` the right v1 default for `concurrency:`, with `execute` turned
   on per project after the schedule report has been reviewed?
7. Baseline questions that still stand: routing of a new declared edge when
   no `owns:` matches (proposed: refuse); device-unit default policy; CI
   evidence export format (JUnit alongside the results directory); how the
   thinking_app screenshot gate is wrapped; the per-repo bootstrap order
   (scan → classify → areas → waivers → `testmap_check` → first full run →
   `require_anchor` → `testmap_run`).
<!-- /section: open_questions -->