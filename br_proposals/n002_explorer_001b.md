<!-- section: overview [dimensions: requirements_*] -->
## Overview

This proposal keeps the baseline's model — a registry of source-to-test
edges in the code tree, a graded graph walk from a task's change set to a
ranked test list, a standard runner contract, declared concurrency
resources, a Welford cost ledger, a score/attribute feedback loop, and
fail-closed gates — and changes three things.

1. **The engine and CLI are one static Go binary, `aitestmap`.** The
   framework today is bash and Python with no compiled artifact; the
   selective-testing engine is the first. The reason is the mandate's
   reason: the whole point is to make a task's test cycle shorter, and an
   engine that spends several seconds parsing YAML and forking a process
   per file on every `select` or `check` eats the saving on small tasks.
   The Go engine parses a registry of thousands of rows, scans ~720 test
   files for annotations, and walks the dependency graph in well under a
   second, and it can run a real concurrent scheduler with cross-process
   locks — something bash cannot do well and Python does slowly. The
   release pipeline builds the binary for linux/darwin × amd64/arm64 as
   separate release assets (the tarball and every distro package stay
   architecture-independent), `ait setup` / `ait upgrade` install the
   correct one under a versioned per-user directory, and a framework
   developer regenerates it from source with one command.

2. **Annotations carry a verification stamp and staleness is a verb.**
   Every `testmap:covers` line records the date it was last confirmed and
   a content digest of the source it names. `aitestmap stale` reports
   every annotation whose source content no longer matches, scoped to a
   task's change set or repo-wide, in the framework's fixed line protocol.
   A procedure gate, `testmap_current`, runs in the existing
   post-implementation procedure-gate dispatch (before the change summary,
   so the rewritten stamps land in the task's commit) and has an agent
   review each stale claim against the exact source diff since the stamp.

3. **Broad tests are associated by area, not by file.** Integration,
   end-to-end and device tests declare a scope (a named area or globs)
   instead of a list of covered files. They live in a separate generated
   table (`_scoped.yaml`) so hot-file churn never rewrites them, they are
   exempt from per-edit staleness (they get a review cadence instead),
   they rank after unit tests at equal distance, and the scheduler runs
   them only after the unit wave is green.

Everything else — vocabulary, the registry directory and `owns:` routing,
the runner verbs and results format, resource kinds and scopes, the cost
model, score/attribute, the two original gates — is inherited and stated
again below where the Go boundary or the new fields change a detail.
<!-- /section: overview -->

<!-- section: architecture -->
## Architecture

### Process boundary

```
 ait testmap <verb> ...                       (user / skill / gate verifier)
   └─ .aitask-scripts/aitask_testmap.sh       bash shim: resolve binary, exec
        └─ ~/.aitask/engine/v<VERSION>/aitestmap <verb> --repo-root $AIT_DIR ...
             ├─ reads   aitestmap/**                 (registry, runners, resources, areas, costs)
             ├─ reads   .aitask-testmap/             (run outputs, ledger, prediction records)
             ├─ reads   $XDG_CACHE_HOME/ait/testmap/ (dependency-scan cache, content-addressed)
             ├─ execs   runner scripts or built-in runners
             ├─ execs   resource commands (admission / allocator) and flock(2)s host locks
             └─ writes  results.jsonl, runner.json, selection.json, prediction.json
```

Four things stay outside the binary on purpose:

- **The `ait` dispatcher and the shim.** `ait testmap` is one new case in
  the dispatcher; the shim owns binary resolution, the version match and
  the "run `ait setup`" repair hint, in the shape every sibling script
  uses for its dependency preflight.
- **The change-surface intake.** `aitask_change_surface.sh list <task>` is
  a framework script; the engine never reimplements its attribution. The
  shim pipes its output into `aitestmap select --changes -`, and the
  engine also accepts `--changes <file>` so it is testable without the
  framework.
- **Gate verifiers.** `aitask_gate_testmap_select.sh` and
  `aitask_gate_testmap_check.sh` are ordinary shell verifiers under the
  documented verifier contract; they call the engine and map its
  `runner.json` status to the verifier exit codes.
- **Custom runners.** A project may still commit its own runner scripts;
  the reference runners are built into the binary so most projects need
  only YAML under `aitestmap/`.

### Go module layout

```
engine/                              Go module github.com/beyondeye/aitasks/engine
  go.mod                             go 1.26; toolchain pinned via the `toolchain` directive
  build.sh                           the ONE place the GOOS/GOARCH matrix and ldflags live;
                                     called by release CI and by `ait engine`
  cmd/aitestmap/main.go              cobra command tree; embeds version, commit, contract
  internal/registry/                 merge aitestmap/registry/*.yaml, owns: routing, check rules
  internal/annot/                    annotation grammar v2, scanner, line-targeted rewriter
  internal/deps/                     per-language forward-dep scanners + content-addressed cache
  internal/selectr/                  graded walk, rules engine, scoped edges, kind ranking
  internal/runner/                   contract types, manifest/results codec, builtin runners
  internal/sched/                    waves, resources (flock/semaphore/admission/allocator)
  internal/cost/                     Welford ledger + fold
  internal/feedback/                 score, attribute
  internal/stale/                    digest, compare, confirm/retarget
  internal/changesurface/            parser for COMMITTED:/TASK:/OTHER:/UNKNOWN: lines
  testdata/                          golden registries, fixture repos built with git in TempDir
```

The `engine/` directory is **not** in the release tarball (the tarball is
an explicit file list) and is git-tracked only in the framework repo, so
consumer projects never see Go source. The name avoids `aitestmap/`,
which is the registry root every target repo — including this one — will
carry.

### Where state lives

| data | location | rationale |
|---|---|---|
| registry, runners, resources, areas, committed costs | `aitestmap/**` in the code tree | inherited: versioned with the code |
| run outputs, prediction records, local cost ledger | `.aitask-testmap/` (gitignored; override `AIT_TESTMAP_DIR`) | the framework's dominant pattern (`.aitask-gates/`, `.aitask-explain/`), same override shape as `AIT_CHANGE_SURFACE_DIR` |
| dependency-scan cache | `${XDG_CACHE_HOME:-~/.cache}/ait/testmap/deps/<blob-sha1>.json` | regenerable, content-addressed — the `artifact_utils.sh` precedent for what XDG cache is for |
| host-scope locks | `${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/ait-testmap-<uid>/<resource>.<slot>.lock` | `flock(2)` via `gofrs/flock`; survives no reboot, needs no cleanup |
| engine binaries | `~/.aitask/engine/v<VERSION>/aitestmap`, `~/.aitask/engine/dev/aitestmap` | mirrors `~/.aitask/python/<ver>/`; never on the interactive PATH |

### Version discipline

The binary embeds three values: `version` (the framework version it was
released with, `0.36.0`), `commit` (short SHA), and `contract` (the
registry/manifest contract number, `1`). Because `~/.aitask/` is per user
and `.aitask-scripts/VERSION` is per project, two projects on one box may
need two engines; the shim therefore resolves
`~/.aitask/engine/v$(cat .aitask-scripts/VERSION)/aitestmap` exactly, and
`ait setup` installs the version the project is on. `ait engine prune`
removes versions no project in `~/.config/aitasks/projects.yaml` is on.
<!-- /section: architecture -->

<!-- section: data_flow -->
## Data Flow

### Selection and run (per task)

```
test files ──annotations──▶ aitestmap scan --apply ──▶ aitestmap/registry/_scanned.yaml   (unit edges, stamped)
                                                    └▶ aitestmap/registry/_scoped.yaml    (broad scopes)
hand files (owns:, rules, waivers, areas.yaml) ─────▶ merged registry (in memory)

aitask_change_surface.sh list t1234 ──▶ COMMITTED:/TASK:/OTHER:/UNKNOWN: lines
        │
        ▼
aitestmap select --task t1234 --changes - [knobs]
        ├─ UNKNOWN: present ──▶ refuse (exit 1, UNKNOWN: lines echoed)
        ├─ walk: d0 changed tests, d1 unit edges + scoped globs, d2.. dependency hops, rules inject
        ├─ rank: distance, then kind (unit < integration < e2e < device), then est. cost
        ├─ mark: `stale` flag on any edge whose stamp digest ≠ current source digest
        └─ write .aitask-testmap/runs/<run-id>/selection.json + prediction.json

aitestmap schedule --run <run-id>   ──▶ waves, holds, critical path, est. wall vs serial
aitestmap run --run <run-id>        ──▶ per invocation: manifest.json → runner → results.jsonl, runner.json
        ├─ wave 1: kind=unit;  wave 2+: broad kinds only if wave 1 green (broad_after_unit)
        ├─ every results line appends to .aitask-testmap/ledger.jsonl (Welford input)
        └─ run.json: overall status, units_expected/reported, exit

aitestmap costs --update            ──▶ fold ledger into aitestmap/costs/<hostclass>.yaml
aitestmap score --run <full-run>    ──▶ caught / missed against prediction.json
aitestmap attribute ...             ──▶ aitestmap/registry/observed.yaml (unit) or areas.yaml (broad)
```

### Staleness loop (per task, post-implementation)

```
aitask_change_surface.sh list t1234 ──▶ changed sources
aitestmap stale --task t1234 ──▶ STALE:/DELETED:/UNSTAMPED:/REVIEW_DUE:/UNKNOWN: lines, DECISION:
        │
        ▼  (procedure gate testmap_current, attended agent)
for each STALE row: git diff <verified_blob> <current_blob>   ← exact source change since confirmation
        ├─ still covers      → aitestmap stale --confirm <test>:<source>       (rewrites @date/digest)
        ├─ coverage moved    → aitestmap stale --retarget <test>:<old>=<new>
        ├─ new behaviour     → aitestmap annotate <test> --covers <new>  or follow-up test task
        └─ claim was wrong   → aitestmap annotate <test> --drop <source>
aitestmap scan --apply ──▶ _scanned.yaml refreshed
aitask_gate.sh append t1234 testmap_current pass|fail ... ──▶ ledger; files ride the (t1234) commit
```

### Packaging (per release) and install (per host)

```
git tag v0.36.0 ──▶ release.yml
   ├─ job engine:  setup-go (go-version-file: engine/go.mod) → go test ./... → engine/build.sh all
   │               → aitestmap-v0.36.0-{linux,darwin}-{amd64,arm64}, aitestmap-v0.36.0-SHA256SUMS.txt
   ├─ job build:   tar -czf aitasks-v0.36.0.tar.gz  ait .aitask-scripts/ packaging/ seed/ skills/ ...   (unchanged, noarch)
   └─ gh-release:  tarball + packaging/shim/ait + 4 binaries + SHA256SUMS

ait setup   (or ait upgrade → install.sh → aitask_setup.sh --source-only)
   ├─ os  = uname -s  → linux | darwin        arch = uname -m → amd64 | arm64
   ├─ GET releases/download/v0.36.0/aitestmap-v0.36.0-<os>-<arch> + SHA256SUMS → verify → install -m 0755 (tmp → mv)
   ├─ into ~/.aitask/engine/v0.36.0/aitestmap ; `aitestmap version --json` must echo 0.36.0
   └─ fallbacks: --local-engine <path> | --engine-from-source (needs go ≥ toolchain) | warn ENGINE_MISSING

ait engine build        → go build into ~/.aitask/engine/dev/aitestmap (+ .dev marker: source path, commit)
ait engine test         → go vet + go test ./...
ait engine cross        → engine/build.sh all into engine/dist/  (same matrix as CI)
AIT_ENGINE=dev ait testmap ...   → shim picks the dev build
```
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

<!-- section: component_engine_binary -->
### Engine binary and CLI (new)

Single static binary: `CGO_ENABLED=0`, `-trimpath`, `-buildvcs=false`,
`-ldflags "-s -w -X main.version=<v> -X main.commit=<sha>"`. About 8–10 MB
per platform. Dependencies, all pure Go: `github.com/spf13/cobra` (command
tree and generated `--help`), `gopkg.in/yaml.v3` (registry codec,
preserves key order for deterministic writes), `github.com/bmatcuk/doublestar/v4`
(`**` globs for bindings, `owns:`, scopes), `github.com/gofrs/flock`
(cross-process file locks on Linux and macOS), `golang.org/x/sync`
(`errgroup`, weighted semaphore). No cgo, no SQLite; the registry is small
enough to hold in memory and YAML is the committed format the baseline
chose.

Command tree (every verb prints fixed-prefix structured lines; `--json`
prints one object; exit codes: 0 ok / findings-free, 1 refused or failed,
2 nothing to do, 3 mechanism error):

```
aitestmap scan      [--apply] [--paths <glob>...]
aitestmap check     [--task <id>] [--strict]
aitestmap select    --task <id> (--changes <file>|-) [--max-distance N] [--budget-s N]
                    [--kind unit,integration,...] [--resource-filter ...] [--run <run-id>]
aitestmap schedule  --run <run-id>
aitestmap run       (--run <run-id> | --all) [--serial] [--no-fail-fast] [--out <dir>]
aitestmap stale     (--task <id> | --all) [--confirm <test>:<source>...] [--confirm-source <path>]
                    [--retarget <test>:<old>=<new>] [--confirm-run <run-id>]
aitestmap annotate  <test> [--kind k] [--covers p...] [--drop p...] [--scope glob...] [--area a] [--runner r] [--needs res...]
aitestmap score     --run <full-run-id> --prediction <run-id>
aitestmap attribute --test T (--source S | --area A --add-path P) --decision missing-edge|test-wrong|source-wrong --evidence <run-id>
aitestmap declare   ...          aitestmap explain <test|source>       aitestmap costs [--update]
aitestmap runner    <builtin> describe|list|run --manifest <f> --out <d>
aitestmap version   [--json]
```

Performance budget on the aitasks repo (≈400 sh + 320 py test files, ≈270
sources, ≈3000 edges after bootstrap), warm cache: `scan` < 200 ms,
`check` < 300 ms, `select` < 300 ms, `stale --task` < 150 ms; cold
dependency scan < 1.5 s. The scanner and dependency pass fan out over a
worker pool sized to `runtime.NumCPU()`, capped at 8 so the engine never
competes with the tests it is about to launch. These are targets a
`go test -bench` in `internal/selectr` pins with the golden registry; a
regression past 2× fails CI.
<!-- /section: component_engine_binary -->

<!-- section: component_engine_packaging -->
### Engine packaging, install and developer regeneration (new)

**Release CI.** A new `engine` job in `.github/workflows/release.yml`,
between `plan` and the archive step: `actions/setup-go@v5` with
`go-version-file: engine/go.mod`; `go vet ./... && go test ./...` (a
failing engine test fails the release); `engine/build.sh all
"$VERSION"`, which loops over the matrix and writes
`dist/aitestmap-v${VERSION}-${GOOS}-${GOARCH}` plus
`dist/aitestmap-v${VERSION}-SHA256SUMS.txt` (`sha256sum` format, one line
per asset). The existing `softprops/action-gh-release` step uploads
`dist/*` next to the tarball and the shim. Matrix: `linux/amd64`,
`linux/arm64`, `darwin/amd64`, `darwin/arm64`. WSL reports `Linux`, so it
is covered; native Windows is not a framework target. Static binaries
have no glibc dependency, so Ubuntu 22.04 and Rocky 9 run the same file.
`release-packaging.yml` (Homebrew, AUR, `.deb`, `.rpm`) is untouched:
those packages ship only the `ait` shim and stay `noarch`; the binary
arrives through `ait setup`, per user, like the Python toolchain does.

**Install.** `install_engine_binary()` in `aitask_setup.sh`, called from
`ait setup` and from `install.sh` through the existing `--source-only`
hook (the same path `install_global_shim` uses, so `ait upgrade` installs
the new version's engine in the same run):

```bash
os="$(uname -s | tr '[:upper:]' '[:lower:]')"     # linux | darwin ; anything else → ENGINE_UNSUPPORTED
case "$(uname -m)" in x86_64|amd64) arch=amd64 ;; aarch64|arm64) arch=arm64 ;; *) arch="" ;; esac
asset="aitestmap-v${version}-${os}-${arch}"
url="https://github.com/beyondeye/aitasks/releases/download/v${version}"
# curl asset + SHA256SUMS to a tmpdir; verify with sha256sum (Linux) / shasum -a 256 (macOS);
# install -m 0755 into ~/.aitask/engine/v${version}/.aitestmap.tmp; mv -f to aitestmap (atomic);
# "$bin" version --json | jq -r .version  must equal ${version}, else remove and fail loudly.
```

Order of sources, mirroring `download_tarball()`: `--local-engine <path>`
(the `--local-tarball` twin, used by the e2e install tests) → the release
asset for the exact version → `--engine-from-source` (runs `engine/build.sh
host` with a local `go` at or above the module toolchain; for hosts off
the matrix such as `linux/riscv64`) → otherwise print `ENGINE_MISSING`
and continue; the rest of the framework does not depend on the engine. A
binary carrying a `.dev` marker is never overwritten unless
`--force-engine` is passed. `curl` sets no quarantine attribute, so
Gatekeeper does not block the unsigned macOS binary; code signing is not
in v1.

**Shim.** `.aitask-scripts/aitask_testmap.sh` (≈25 lines): resolve
`AITESTMAP_BIN` → `AIT_ENGINE=dev` → `~/.aitask/engine/v$(<VERSION>)/aitestmap`;
if not executable, print `ENGINE_MISSING:<path>` and `Run 'ait setup' to
install the aitestmap engine for framework v<VERSION>` on stderr and exit
3; else `exec "$bin" --repo-root "$AIT_DIR" "$@"`. It is allowlisted at
the five skill-permission touchpoints because the skill calls it
directly. `ait testmap` is the one new dispatcher case; `ait engine`
(below) is the second, typed by framework developers.

**Developer regeneration.** `.aitask-scripts/aitask_engine.sh`:
`build` (`go build` into `~/.aitask/engine/dev/aitestmap`, writes
`.dev` with the source path and `git rev-parse --short HEAD`, prints
`ENGINE_BUILT:<path>|<commit>`), `test` (`go vet`, `go test ./...`,
optionally `-race`), `cross` (`engine/build.sh all` into `engine/dist/`,
identical to CI), `prune`. `engine/bin/`, `engine/dist/` are gitignored.
Because `build.sh` is the single matrix definition, a CI build and a
local `cross` build of the same commit produce byte-identical binaries
(Go builds are reproducible under `-trimpath` with a pinned toolchain).
`CLAUDE.md` gains a `### Engine` block: `ait engine build && AIT_ENGINE=dev
ait testmap check`.

**Tests.** `engine/` has Go unit tests with golden registries and fixture
repos created with `git init` in `t.TempDir()`. On the bash side:
`tests/test_testmap_shim.sh` (resolution order, missing-binary message,
version mismatch) and `tests/test_install_engine_binary.sh` (the
`--local-engine` path through a real `install.sh --dir /tmp/…` run, per
the rule that setup-flow changes are exercised through a real install).
<!-- /section: component_engine_packaging -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer (`internal/registry`)

Inherited responsibilities: merge every file under `aitestmap/registry/`
into three tables (edges, rules, waivers), enforce `owns:` write routing,
report duplicate edges, fail duplicate rule names, waivers on edged paths,
orphaned annotation rows and expired waivers. Two additions:

- A fourth table, **scopes** (test → area or globs), and a fifth,
  **areas** (name → path globs), from `_scoped.yaml` and hand files'
  `areas:` blocks.
- Two generated files instead of one: `_scanned.yaml` holds unit edges,
  `_scoped.yaml` holds broad scopes. `scan --apply` rewrites each only
  when its content changed, with keys sorted, so a diff of `_scanned.yaml`
  after a hot-file confirmation touches only the stamped rows.

```yaml
# aitestmap/registry/_scanned.yaml  (generated; unit edges)
contract: 1
edges:
  - {test: tests/test_gate_pass.sh, covers: .aitask-scripts/aitask_gate_pass.sh,
     from: annotation, line: 4, verified_at: 2026-09-16, verified_blob: 8f3a1c2d9e}

# aitestmap/registry/_scoped.yaml   (generated; broad scopes)
contract: 1
scopes:
  - {test: tests/test_gate_verifiers.sh, kind: integration, area: gates, line: 5, reviewed_at: 2026-09-16}
  - {test: tests/test_no_unscoped_task_commit.sh, kind: integration,
     globs: [".aitask-scripts/aitask_*.sh"], line: 6, reviewed_at: 2026-09-16}

# aitestmap/registry/areas.yaml     (hand-written)
contract: 1
areas:
  gates:   {paths: [".aitask-scripts/aitask_gate*.sh", ".aitask-scripts/lib/gate_*.sh",
                    ".aitask-scripts/lib/gate_ledger.py", "aitasks/metadata/gates.yaml"]}
  install: {paths: ["install.sh", ".aitask-scripts/aitask_setup.sh", "packaging/**", "seed/**"]}
```

Loading 5 000 rows with `yaml.v3` into typed structs takes tens of
milliseconds; the loader validates against the `contract` number and
refuses a file from a newer contract with exit 3 and
`CONTRACT_MISMATCH:<file>|<have>|<want>`.
<!-- /section: component_registry_loader -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter (`internal/annot`)

Grammar v2. The comment leader follows the file type (`#`, `//`, `--`);
the token stays `testmap:`.

```
# testmap:kind unit                       unit | integration | e2e | device   (default unit)
# testmap:covers <path> @<YYYY-MM-DD>/<blob10>      unit kinds: one line per covered source
# testmap:area <name>                     broad kinds: a named area from areas.yaml
# testmap:scope <glob> [<glob>...]        broad kinds: literal globs
# testmap:reviewed <YYYY-MM-DD>           broad kinds: when the scope was last reviewed
# testmap:runner <name>   testmap:needs <resource>   testmap:batch no        (inherited, optional)
```

`<blob10>` is the first 10 hex digits of the git blob object id of the
covered source's content when the claim was confirmed — `sha1("blob
<len>\0" + bytes)`, the same value `git hash-object` prints — computed in
Go without invoking git. Humans never type it: `annotate` and `stale
--confirm` write it. The date is for the reader; the digest is what
`stale` compares.

Kind decides the association form and `check` enforces it: a unit test
may not declare `area`/`scope`; a broad test must declare at least one
`area` or `scope`, may add `covers` for a fixture it pins directly, and
gets `KIND_MISMATCH:` (warning; failure under `--strict`) when a unit
test carries more than `unit_covers_max` (default 6) covers — the signal
that it is really an integration test that should move to a scope.

The scanner walks every unit each runner's `list` verb reports, over a
worker pool, and matches lines with a compiled regexp per leader. The
**rewriter** edits a single annotation line by (file, line, current text)
and refuses if the text at that line no longer matches the registry row
(`REWRITE_CONFLICT:`), so a confirmation never clobbers an edit that
landed in between; it preserves line endings and never touches any other
byte of the file.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners (`internal/deps`)

Forward dependencies per source, inverted in memory into the reverse
graph the walk needs. Built-in scanners: **bash** (`source`/`.` lines and
`"$SCRIPT_DIR/aitask_x.sh"` sibling invocations, resolved against the
repo), **python** (`import`/`from … import` resolved to files under the
configured roots via a small tokenizer, not a full parser), **go**
(`go list -deps -json ./...` executed once per run and cached by the
`go.sum` digest), **kotlin** (`import` lines resolved within a Gradle
module; cross-module edges from the module graph parsed out of
`settings.gradle(.kts)` and each module's `dependencies { … }` block).
Project-specific scanners remain a plugin slot: an executable declared in
`aitestmap/scanners.yaml` that reads a path list on stdin and prints
`DEP:<from>|<to>` lines.

Cache: one JSON file per source under
`${XDG_CACHE_HOME:-~/.cache}/ait/testmap/deps/<blob-sha1>.json`; a source
whose blob is unchanged is never rescanned. A cold scan of this repo is
about 270 files and under 1.5 s; warm is a directory stat pass.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector (`internal/selectr`, `internal/changesurface`)

Intake is the change-surface line protocol — `BASELINE:`, `PLANSCOPE:`,
then `COMMITTED:`/`TASK:`/`OTHER:`/`UNKNOWN:` per path. `COMMITTED:` and
`TASK:` paths are the change set; `OTHER:` is ignored; any `UNKNOWN:`
refuses selection (exit 1, the lines echoed) exactly as the baseline
demands. Because that script says nothing through exit codes, the parser
trusts lines only. Paths under `aitasks/`, `aiplans/`, `.aitask-data/`,
`.aitask-gates/` are excluded before the walk, mirroring the script's own
excludes.

The graded walk is inherited: d0 changed tests and escalation, d1 direct
edges, d2+ dependency hops, rules injecting at a declared distance
(`select`, `implies`, `escalate`). Two additions:

- **Scoped edges** join at d1 when a changed path matches the test's area
  or globs (`doublestar.Match`). Their reason reads `scope(area gates)` or
  `scope(glob .aitask-scripts/aitask_*.sh)`.
- **Ranking** within a distance is by kind (`unit` < `integration` < `e2e`
  < `device`), then by estimated cost ascending, so the cheapest evidence
  runs first and a budget cut trims broad tests before unit tests.

Every selected line carries a `stale` mark when any edge that selected it
has `verified_blob` ≠ current digest — visible in the reason column, not
a filter. Output is the whole ranked list; cuts are knobs applied after
(`--max-distance`, `--budget-s`, `--kind`, `--resource-filter`).

```
tests/test_gate_pass.sh                d=1 unit         edge(annotation, stale) .aitask-scripts/aitask_gate_pass.sh
tests/test_gate_orchestrator.sh        d=2 unit         dep lib/gate_verifier_lib.sh <- aitask_gate_pass.sh
tests/test_gate_verifiers.sh           d=1 integration  scope(area gates)
tests/test_no_unscoped_task_commit.sh  d=1 integration  scope(glob .aitask-scripts/aitask_*.sh)
```

`select` writes `selection.json` and `prediction.json` under
`.aitask-testmap/runs/<run-id>/`; the run id is
`r-<YYYYMMDD>-<HHMMSS>-<4 hex>` and every later artifact carries it.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and runner repository (`internal/runner`)

The three verbs (`describe`, `list`, `run --manifest --out`), the manifest
and `results.jsonl` / `runner.json` shapes, bindings with first-match
resolution and per-test `testmap:runner` override, batching and
`unit: suite` wrappers are inherited verbatim. `runners.yaml` gains the
`builtin:` scheme:

```yaml
runners:
  bash-file:    {exec: "builtin:bash-file", unit: file,  batch: false, needs: [git-index]}
  pytest:       {exec: "builtin:pytest",    unit: file,  batch: true,  needs: [git-index]}
  go-test:      {exec: "builtin:go-test",   unit: file,  batch: true}
  gradle-class: {exec: tools/verification/testmap_runner.sh, unit: class, batch: true, needs: [heavy-run]}
```

Runner exit codes are unchanged (0 all passed; 1 a unit failed or the
mechanism broke, `cause` set only for the mechanism; 2 did not run for a
self-clearing reason; 75 admission refused). The engine's `run.json`
carries the aggregate; **the gate verifier, not the engine, maps to the
framework's 0/1/2/3**: engine 0 → 0 pass; any unit failed → 1 fail;
empty selection → 2 skip; mechanism error or admission refused after the
retry window → 3 error, which the orchestrator retries within
`max_retries`. Admission refusal must never become a skip, because a
skipped test gate reads as a pass. `units_expected` vs `units_reported`
is checked per invocation and a mismatch is a mechanism failure.
<!-- /section: component_runner_contract -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources (`internal/sched`)

Resource kinds and scopes are inherited (mutex / semaphore / admission /
allocator; host / worktree / run; `acquired_by: runner`). In Go they are
real: host and worktree scopes are `flock(2)` locks on slot files
(`<name>.<i>.lock`, `i < capacity`), taken in canonical name order;
admission execs the project's command and treats exit 75 as "defer and
retry with backoff until the run deadline"; an allocator execs
`acquire`, parses one JSON line as the handle, injects it into the
manifest, and runs `release` in a deferred call that also fires on
`SIGINT`/`SIGTERM` via `signal.NotifyContext`. Invocations run as
goroutines under an `errgroup`; a `--serial` flag runs one at a time
while still printing the schedule it would have used, which answers the
baseline's open question 3 with a knob rather than a decision.

Batching groups selected units by (runner, resource set, batch flag) into
invocations. Policy **`broad_after_unit`** (default true) makes wave 1
consist of unit-kind invocations only; broad kinds are scheduled only if
wave 1 has no failure, so a cheap red unit test never pays for an
8-minute screenshot suite. `--no-fail-fast` disables it. `schedule`
prints waves, holds, critical path and estimated wall time against the
serial sum, and its check half flags runner-default resources a unit does
not declare.
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger (`internal/cost`)

Welford's online update per (unit, host class): n, mean, M2 → standard
deviation, a P² estimate for p95, and last. Every `results.jsonl` line
appends one record to `.aitask-testmap/ledger.jsonl`; `costs --update`
folds the ledger into `aitestmap/costs/<hostclass>.yaml` and truncates
the ledger. Host class defaults to the hostname and is set in
`aitestmap/config.yaml` (`host_class: ci-linux-4c`). Runner invocation
overhead is tracked as its own row so the estimate for a selection is
Σ unit means + Σ per-invocation overhead.
<!-- /section: component_cost_ledger -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools (`internal/feedback`)

`score` splits a full run's failures into caught / missed against a
prediction record. `attribute` records a decision with the run id as
evidence, and its write target depends on the missed test's kind: a unit
test gets an observed edge in `observed.yaml`; a broad test gets the
missed path added to its area in `areas.yaml` (or to its literal globs in
the annotation, via the rewriter), which is how broad scopes are corrected
by evidence rather than by per-edit review. `stale --confirm-run
<run-id>` is the bridge between the two loops: it confirms every stale
unit edge whose test ran green in that run, and records
`confirmed_by: <run-id>` on the row.
<!-- /section: component_feedback_tools -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates (three, in `gates_reference.yaml` → `gates.yaml`)

```yaml
  testmap_check:
    type: machine
    description: "Test map is consistent: every changed source mapped, every test registered, no orphan or expired rows"
    blocks_dependents: false
    verifier: aitask-gate-testmap-check          # .aitask-scripts/aitask_gate_testmap_check.sh
    max_retries: 0
    timeout_seconds: 120
  testmap_select:
    type: machine
    description: "Tests selected for this task's change set pass"
    blocks_dependents: true
    verifier: aitask-gate-testmap-select
    max_retries: 1
    timeout_seconds: 1800
  testmap_current:
    type: machine
    kind: procedure                              # skill aitask-gate-testmap-current, attended agent
    description: "Coverage annotations on this task's changed sources reviewed and re-stamped"
    blocks_dependents: false
    verifier: aitask-gate-testmap-current
    max_retries: 0
```

The two command verifiers follow the copy-me template: read the task
file, call the shim, write `.aitask-gates/<task>/<gate>_<run-id>.log`,
append the terminal block through `aitask_gate.sh append`, exit the
mapped code. `testmap_current` is dispatched by the existing generic
procedure-gate block in the post-implementation step, before the change
summary — no change to that skill is needed for the dispatch itself.
Both new registry keys are added to `gates_reference.yaml` first and
synced down, so the drift guard stays green.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills

**`aitask-testmap`** teaches the obligations: when you write a test,
annotate it (`ait testmap annotate <test> --kind … --covers …` for unit,
`--area`/`--scope` for broad) and let the tool write the stamp; when you
add a source, give it an edge, a rule or a waiver; when you fix a failing
test by editing a source it had no edge to, `attribute` before the gate.

**`aitask-gate-testmap-current`** is the procedure gate. Contract: `pass`
when every `STALE:`/`DELETED:`/`UNSTAMPED:` row for the task's changed
sources was resolved; `skip` when `stale --task` reports
`DECISION:FRESH` or `SKIP` (no annotated source changed, or not a git
repo); `fail` when rows remain unresolved. Steps: (1) run `ait testmap
stale --task <id>`; (2) resolve `UNKNOWN:` paths with the user, or
exclude and log them under an autonomous profile — never guess; (3) for
each `STALE:` row show `git diff <verified_blob> <current_blob> --stat`
and the hunks, and ask confirm / retarget / add / drop / follow-up; (4)
under an autonomous profile, confirm only rows whose test ran green in
this task's `testmap_select` run (`--confirm-run`), leave the rest
unresolved and fail with the list; (5) `ait testmap scan --apply`; (6)
record the terminal block with both attribution headers, the per-class
counts and the resolved/unresolved rows, so the verdict is auditable.
<!-- /section: component_skill -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners (built into the binary)

`bash-file` (one process per file, captures stdout+stderr to
`logs/<name>.log`, maps exit 0/non-0), `pytest` (batch: one interpreter
per invocation, `--junitxml` parsed for per-unit status and duration;
honours the project's `serial` list from `aitestmap/config.yaml` by
splitting those modules into their own invocations), `go-test`
(per-file `-run` regex derived from `func Test…` names, `-json` parsed for
per-test timing, package setup cost attributed to every file in the
package), `gradle-class` (`--tests <fqn>` batch, JUnit XML), `suite`
(wraps any command as one unit), `device` (takes the allocator handle
from the manifest). Each is an `aitestmap runner <name>` subcommand, so a
project can shadow one with a script under the same name and `explain`
shows which won. Built-in runners make the `aitestmap/runners/`
directory optional in target repos.
<!-- /section: component_reference_runners -->

<!-- section: component_staleness_tool -->
### Staleness tool (`internal/stale`) (new)

`aitestmap stale (--task <id> | --all)` prints, in the fixed-line shape
the framework already uses for its manual-verification staleness check
(every content state exits 0; only CLI misuse exits non-zero; fields
`|`-separated with `%`→`%25` then `|`→`%7C` encoding):

```
SURFACE:task|all                         whether a task change set scoped the scan
EDGES:<n>                                stamped unit edges examined
STALE:<test>|<source>|<verified_at>|<verified_blob>|<current_blob>
DELETED:<test>|<source>|<verified_at>    source no longer exists
UNSTAMPED:<test>|<source>                annotation without @date/digest
REVIEW_DUE:<test>|<area-or-glob>|<reviewed_at>|<age_days>   broad scope past broad_review_days (default 90)
UNKNOWN:<path>|<reason>                  change-surface UNKNOWN: paths; drives the decision
DISPLAY:<one-line summary>
DECISION:FRESH|REVIEW|SKIP
```

Comparison is digest-only: the current value is `sha1("blob <len>\0" +
content)` of the working-tree file, so the check needs no git history and
works in a depth-1 CI checkout; the date is never compared. `--task`
restricts sources to the task's `COMMITTED:`/`TASK:` paths, which is
what makes the in-task check precise even for same-day edits. `--all` is
the repo-wide sweep for annotations that slipped past the workflow.

Mutating flags rewrite annotation lines through the rewriter and re-scan
the touched files: `--confirm <test>:<source>` (new date, new digest),
`--confirm-source <path>` (every annotation on one hot source at once — a
72-file rewrite lands as one commit instead of 72 nags), `--confirm-run
<run-id>` (every stale edge whose test passed in that run),
`--retarget <test>:<old>=<new>`. Confirmation is the only thing that
rewrites a stamp; a source edit alone never touches a test file.
<!-- /section: component_staleness_tool -->

<!-- section: component_broad_test_scopes -->
### Broad-test scopes (new)

Concrete broad tests in this repo and how they are declared:

| test | why it is broad | declaration |
|---|---|---|
| `tests/test_no_unscoped_task_commit.sh` | scans 24 `aitask_*.sh` for a repo-wide invariant | `testmap:kind integration`, `testmap:scope .aitask-scripts/aitask_*.sh` |
| `tests/test_gate_verifiers.sh` | drives every `aitask_gate_*.sh`, derives keys from disk | `testmap:area gates` |
| `tests/test_frozen_agents_acceptance.sh` | `install.sh --local-tarball` → hooks → tmux → store, end to end | `testmap:kind e2e`, `testmap:area install`, `testmap:needs tmux` |
| `tests/test_t167_integration.sh` | full `install.sh` + `ait setup` in a scratch dir | `testmap:kind e2e`, `testmap:area install` |
| `tests/test_board_header_row_live.py` | boots the real TUI against the real repo, takes `.git/index.lock` | `testmap:kind e2e`, `testmap:area board`, `testmap:needs git-index`, `testmap:batch no` |

What is different for them, in one place: separate generated table
(`_scoped.yaml`); no per-source digest, a `reviewed` date with a cadence
check instead; `check` fails a scope whose glob matches zero files or
whose area is undeclared (`DEAD_SCOPE:`); selection at d1 by glob match,
ranked after unit tests; scheduled after the unit wave; `attribute`
widens the area on a miss. The registry stays one directory with one
merge rule; only the table a row lands in differs. A project that wants
its device tests selected by distance but never run without an emulator
sets `device_policy: filter_by_resource` in `aitestmap/config.yaml`
(framework default), answering open question 5.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Inherited unchanged:

- **Static file-level facts are enough for v1** (`assumption_static_granularity_v1`); the edge schema keeps the optional `symbols` slot.
- **Existing project locks and allocators can be wrapped as resources** (`assumption_existing_locks_wrappable`) — the Go admission/allocator kinds exec the project's commands and honour their exit codes; nothing in thinking_app changes.
- **Runners can report per-unit timing inside a batch** from JUnit XML, `go test -json` or pytest junitxml (`assumption_batch_per_unit_timing_reportable`).
- **`testmap:` does not collide with prose** (`assumption_testmap_token_no_collision`); the 38 existing `# Covers:` headers in this repo are behavioural prose and are not matched.

Inherited and made precise:

- **The change-surface script is the intake** (`assumption_change_surface_is_intake`): its exit codes carry no meaning, so the engine parses only its `COMMITTED:`/`TASK:`/`OTHER:`/`UNKNOWN:` lines; an `UNKNOWN:` refuses selection and drives `stale`'s decision.
- **The gate exit contract is reused** (`assumption_gate_exit_contract_reused`) — but the framework's contract is 0 pass / 1 fail / 2 skip / 3 error, with no 75. The runner contract keeps 75 internally; the verifier maps it to 3 (retryable), and only an empty selection maps to 2.
- **Target repos accept an `aitestmap/` root** (`assumption_target_repos_accept_aitestmap_root`) — weakened to YAML only: with built-in reference runners no scripts need committing unless a project writes a custom runner.

New:

- **Go is a build-time dependency only.** Go ≥ 1.26 is needed in release CI (already provisioned there for Hugo modules) and on a framework developer's machine; users receive binaries. `CLAUDE.md` already lists Go as a prerequisite.
- **Hosts running `ait setup` can reach GitHub release downloads**, as they already must for the tarball; air-gapped hosts use `--local-engine` or `--engine-from-source`.
- **linux/darwin × amd64/arm64 covers every target host**; anything else builds from source.
- **A content digest of the covered source is the correct staleness key.** Neither file mtime (reset by checkout) nor the annotation date (day granularity, clock skew across clones) is compared; the date is display only.
- **Broad tests can be described by areas or globs whose membership changes rarely**, so a review cadence plus evidence-driven widening is adequate where per-edit staleness would only produce noise.
- **One engine version per framework version is enough**; a per-user versioned directory resolves the per-project `VERSION` mismatch without a compatibility matrix.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Advantages:

- **Computed, explained, scored selection** (`tradeoff_computed_vs_prose`) — inherited; the `stale` mark on a selected line and the digest-anchored diff add "how trustworthy is this edge" to "why was it selected".
- **Speed makes the machinery usable per task.** Sub-second `select`/`check`/`stale` on a 720-test repo means the selection overhead is negligible against even the shortest test, and `check` can run on every commit. A bash+Python engine would spend seconds in interpreter start-up and YAML parsing before the first test ran.
- **A real scheduler.** Goroutines plus `flock(2)` give correct cross-worktree contention and a critical-path report; the framework's own two suites (shell tests owning the real index, the pytest lane) finally get the enforced "do not overlap" that today is a comment in `run_all_python_tests.sh`.
- **Architecture-independent packages stay that way.** Homebrew, AUR, `.deb`, `.rpm` and the tarball ship nothing compiled; the per-arch concern is contained in one release job and one setup function.

Disadvantages:

- **Registry directory complexity** (`tradeoff_registry_directory_complexity`) — inherited, and slightly larger: five tables and two generated files. Mitigation: the merge rule is unchanged and lives in one Go package with golden tests.
- **Fail-closed bootstrap cost** (`tradeoff_fail_closed_bootstrap_cost`) — inherited. Mitigation: `check --strict` is off by default until the project enables the gate; `scan` on this repo bootstraps most direct edges from the `- Tests for <script>` header convention as `UNSTAMPED:` rows the first `stale --all --confirm-run` of a green full run stamps in bulk.
- **Static scanners overselect on hot files** (`tradeoff_static_scanner_overselection`) — inherited. Mitigation: kind ranking and `--budget-s` trim broad tests first; a project scanner plugin can narrow a hot resource file.
- **The framework gains a compiled component.** Contributors touching the engine need Go; a release now fails if `go test ./...` fails; the install grows a network fetch and a checksum step. Mitigation: `engine/build.sh` is the single matrix, `ait engine build` is one command, the engine is optional at install (`ENGINE_MISSING` is a warning until a project enables a testmap gate), and everything that is not the engine stays bash/Python.
- **Engine version skew on multi-project hosts.** One user, several projects, several `VERSION`s → several ~10 MB binaries under `~/.aitask/engine/`. Mitigation: exact-version resolution in the shim (never a silent "newest wins"), `ait engine prune` against the project registry.
- **Stamp churn on hot sources.** Confirming stamps rewrites test files; a change to a source named by 72 tests produces a 72-file diff. Mitigation: only confirmation rewrites (a source edit alone never touches a test), `--confirm-source` and `--confirm-run` make it one commit, and sources with that fan-out are better covered by an area scope than by 72 unit edges — `KIND_MISMATCH:` nudges that way.
- **Broad scopes are coarse.** A test scoped to a large area is selected for any change inside it and, with a wide glob, for nearly every task. Mitigation: it ranks last at its distance, runs after the unit wave, and a budget knob cuts it first; the cost is visible in `schedule`.

Risks:

- **Unattributed source edits** (`tradeoff_attribution_risk`) — inherited. The stamp narrows it: a source edited without review of its annotations now shows as `STALE:` in the next task that touches it and as a `stale` mark on every selection, instead of silently looking current.
- **Batch misreport and wrongly scoped resources** (`tradeoff_batch_misreport_risk`) — inherited; `units_expected` vs `units_reported` is enforced per invocation and a mismatch is a mechanism failure, never a pass.
- **Resource declarations are only as complete as declared** (`tradeoff_resource_declaration_completeness`) — inherited; `schedule`'s check half and the heuristic scan for shell tests running git in the repo root remain the only detection short of a probe.
- **Autonomous confirmation is weaker than review.** `--confirm-run` treats "the test passed" as evidence the claim still holds, which it is not in general. Mitigation: the row records `confirmed_by: <run-id>` so the provenance is visible, autonomous profiles never confirm without that evidence, and a later `score` miss on that test re-opens it.
- **An unsigned macOS binary or a blocked download leaves a host without an engine.** Mitigation: `ENGINE_MISSING` names the exact path and the repair verb; `--engine-from-source` and `--local-engine` are the documented fallbacks; the two testmap gates report exit 3 (error), never skip, when the engine is absent.
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Should `stale --confirm-run` be allowed under autonomous profiles at all, or should autonomous runs only report and leave every confirmation to an attended session?
2. Is `unit_covers_max: 6` the right nudge toward a scope, and should `check --strict` refuse rather than warn once a repo has finished bootstrapping?
3. Should `~/.aitask/engine/` be pruned automatically by `ait upgrade` (when the old version is no longer on any registered project) or only by an explicit `ait engine prune`?
4. Is a `reviewed` cadence of 90 days for broad scopes useful, or is evidence-driven widening through `attribute` enough on its own?
5. Should the Go module also absorb `aitask_change_surface.sh` in a later contract, or does keeping the intake in bash preserve a useful seam?
6. Baseline questions 1, 2, 4, 6, 7, 8 and 9 remain open; 3 (concurrent vs serial scheduler) becomes the `--serial` knob and 5 (device policy) becomes `device_policy` with the framework default `filter_by_resource`.
<!-- /section: open_questions -->