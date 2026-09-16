<!-- section: overview [dimensions: requirements_*] -->
## Overview

The goal is unchanged: a framework feature, generic across `aitasks`,
`thinking_app`, `thinking_backend`, `aitasks_go` and `aitasks_mobile`, that
maintains a relation between source files and test units, translates a task's
change set into a ranked set of tests with a reason on every line, runs them
through project-defined runners under a standard contract, tracks cost per
unit by host class, learns from failures the map did not predict, is enforced
by gates, and is taught to agents by a skill. The static Go engine
(`ait-testmap`), per-edge blob-digest stamps healed by a committed run-evidence
join, scoped rows for broad tests under an explicit suite budget, the graded
walk, the real scheduler, the cost ledger and the three gates are n003's and
are kept.

The two explorers answered the same two mandate notes — *the framework is
`aitasks`, so the engine belongs under `~/.aitasks/`* and *does the design
support thinking_app's screen × localization subdivision?* — with different
mechanisms. This node takes the stronger mechanism for each note, bridges what
the other side got right, and records the facts checked against the two
repositories that decided between them.

**1. Per-user root: n005's variable and default, n004's migration made
explicit and deferred.** The engine installs at
`$AITASKS_HOME/engine/v<VERSION>/ait-testmap` with `AITASKS_HOME` defaulting to
`~/.aitasks`, owned by one library file (`lib/aitasks_home.sh`), never falling
back to `~/.aitask` (n005) — a component with no legacy gains nothing from a
legacy fallback except the ability to hide a wrong install. The legacy Python
tenants (`venv`, `pypy_venv`, `python`, `bin`, `uv`, `dev_tier`,
`update_check`) are not moved by this feature (n005), but n004's migration is
not thrown away: it ships as an explicit verb, `ait engine home --migrate`
(n004's algorithm — `flock`, per-entry same-device rename, `rmdir`,
compatibility symlink, refusals on a foreign symlink, a cross-device pair or an
unrecognised entry), with its known-entry set corrected: `pypy_venv`, created
by `setup_pypy_venv()` and named by `python_resolve.sh`, was absent from n004's
set and is present on the host this was written on, so n004's migration as
specified would have refused here. `ait setup` prints a one-line `HOME_LEGACY:`
hint and does not migrate by default; flipping that default is a named
follow-up, admitted once the verb has been exercised through a real
`install.sh --dir` run, which is the framework's rule for every setup-flow
change. Motivation, measured rather than argued: framework code naming
`~/.aitask` is **8 files / 35 references** (21 of them in `aitask_setup.sh`),
plus 20 test files and 18 documentation files — 48 files repo-wide, which is
n005's "49"; n004's "121 across 28 files" counted occurrences and included
tests. Nothing compares the path for equality or canonicalises it, the venv's
console-script shebangs dereference `/home/<u>/.aitask/venv/bin/python3`, and
`pyvenv.cfg`'s `command =` line is informational — so n004's symlink premise
holds. What does not hold is the blast radius: a default migration touches
every install in the field on the next `ait setup`, and that is not a cost the
selective-testing feature should carry in the same change.

**2. A project's own subdivision as a first-class unit: n005's model, with
four pieces of n004 bridged in.** Member units (`<path>#<member>`, opened by
`testmap:unit` blocks), variant axes (`aitestmap/axes.yaml` with facets,
values and facet-valued sources; `<unit>@<variant>` ids enumerated by the
runner's `list`), per-variant cost, `last_pass` and evidence, suite child
rows, the test-side closure with `testmap:reads`, the fail-closed Kotlin
scanner that escalates instead of narrowing, automatic scoring of the newest
prediction on every full run, and `readiness` against declared admission
criteria are all n005's. From n004: **invocation-group costing** (the budget
charges a Robolectric class boot once and each further method its marginal
mean), the **fail-safe statement and the per-variant reason** on every
selected row, the **reconciliation checks** (`UNCOVERED_VALUE`,
`UNMAPPED_ARTIFACT` — the generic form of the silent-green class
`MatrixClassificationTest` closes by hand), the **hand-declared coordinate**
(`testmap:axis`) for a test that occupies a coordinate but produces no golden,
the `--axis` knob, and the grid heuristic in `classify --suggest`.

Why n005's model and not n004's axes-and-cells:

- **Soundness under a whole-run filter.** Gradle `--tests` filters the entire
  `testDebugUnitTest` task; `verifyRoborazziDebug` drives that one task. A
  selection that names twelve cells silently drops the other ~370 classes —
  fences, oracles, ViewModel tests, geometry gates. thinking_app's own design
  record (`aidocs/testing/change-aware-verification.md`, t381) makes this the
  design driver and t388 forbids a narrow run that cannot justify every
  omission. n004's cell selection never addresses it; n005 makes `list` the
  universe (`UNREGISTERED` for an unlisted class), models the test-side
  closure, inherits `reads` globs, and escalates on opaque files.
- **Freshness applies to the suite the mandate names.** n004's cells carry no
  `covers`, no stamp and no evidence ("not digest-stamped … no `EVIDENCED`
  class for cells"). The staleness and evidence machinery that n003 was built
  around would therefore not touch thinking_app's main suite at all. n005
  stamps the member block's edges and anchors evidence per variant, so a
  Hebrew pass cannot re-stamp an Arabic claim.
- **One enumeration surface, not two.** n005's universe is the `list` verb the
  runner contract already has; n004 adds an `aitestmap/cells/` plugin
  directory and a ~2,500-row generated `_cells.yaml` whose `unit` strings must
  coincidentally equal what the runner's `list` prints. Here `scan --apply`
  records each member's `variants:` list (49 rows × ≤10 values) so `select`
  never execs a runner.
- **The intersection is already there.** Checked against n004's own worked
  table, every single-file row has at most one non-`ANY` axis, so "union
  within an axis, intersection across axes" reduces to n005's facet join; and
  n004's per-file union — the rule that makes its two-edit case 104 cells
  rather than 470 — *is* n005's union across hits. n004's `ANY` for an
  unmatched file is the same statement as n005's "a file matching no axis
  source reaches units only through edges and dependencies, which select every
  variant".
- **The one gap in n005 is small and filled.** A non-capturing test that
  belongs to a coordinate (`ArMatrixArabicOnlyTest` is Arabic without writing
  a golden) had no way to say so; `testmap:axis matrix.locale=ar` on a plain
  unit now joins the axis hit.
- **n004's `reach:` root does not match the tree.** Screens live under
  `ui/mvvm/<feature>/<Name>Screen.kt`, not `ui/screens/`; and a computed reach
  is a dependency fact re-derived under a new name, where an annotated edge is
  stamped, evidenced and reviewed.

**Does the design support the mapping?** Yes, and it prints its work: a change
to `ui/mvvm/auth/welcome/WelcomeScreen.kt` selects `ScreenFixtures.kt#Welcome`
on every matrix it is enrolled in; a change to `res/values-ru/strings.xml`
selects every enrolled screen on `pixel5Ru_ltr` and `shortPhoneRu_ltr` only —
or, with the opt-in `android-res` scanner, only the screens whose closure names
a changed key; both together union; a `const val` edit escalates to the whole
JVM suite with the construct named; and every row carries the facet value or
`*` that placed it. Nothing in the engine knows Gradle, Roborazzi or the
membership manifests — the project's runner script lowers ids through
`matrix_classes` / `preview_resolve_token`, the routing it already owns.
<!-- /section: overview -->

<!-- section: decision_matrix [dimensions: component_*, assumption_*] -->
## Decision Matrix: What Was Taken From Which Parent, and Why

| aspect | n004_explorer_002a | n005_explorer_002b | chosen | why |
|---|---|---|---|---|
| engine install root | `~/.aitasks/engine/v<V>/` via `aitasks_home()` (`AITASKS_HOME` > `~/.aitasks` if it exists > `~/.aitask`) | `$AITASKS_HOME/engine/v<V>/`, default `~/.aitasks`, no fallback | **n005** | the engine never lived under `~/.aitask`; a fallback there can only mask a missing install; one variable, one owner file |
| legacy tenants | migrated by `ait setup` under a lock, `~/.aitask` left as a symlink | left in place; a later change | **n004 mechanism, n005 default** | migration shipped as `ait engine home --migrate` with the known-entry set corrected (`pypy_venv`); `ait setup` hints, does not migrate; default flip is a named follow-up after a real-install test |
| home resolver in Go | `internal/home` | none | **n005** | the engine's state is repo-local and XDG; it never needs its install root; `version --json` prints `ENGINE:` from the executable path |
| `ait engine home` verb | yes (report) | no | **n004** | prints root, legacy tenants found, symlink state, and what `--migrate` would do |
| unit model for a product-shaped suite | axes + cells: `_cells.yaml` generated from an `aitestmap/cells/` plugin; cells have no covers/stamp/evidence | member units + variant axes; runner `list` is the universe; per-variant evidence | **n005** | soundness under a whole-run filter; freshness applies; one enumeration surface; compact committed footprint |
| axis semantics | union within an axis, intersection across axes, per file, unioned across files; unmatched file = `ANY` | axis-source hit → variants carrying the facet value; edge/dep/rule/test-dep hit → all variants; union across hits | **n005 rule, n004 fail-safe wording** | equivalent on every single-file case in n004's own table; per-file union = union across hits; `ANY` = "no axis hit" |
| coordinate for a non-capturing test | `testmap:axis <name>=<value>` | — | **n004** | `testmap:axis matrix.locale=ar` on a plain unit joins the axis hit |
| screen coordinate | `reach:` from `ui/screens/{value}Screen.kt`, `fanout_max` | `covers` edges on the member block, seeded by `annotate --from-body`; Kotlin scanner for d2 | **n005** | the root pattern does not exist in the tree; an annotated edge is stamped, evidenced and reviewed; fan-out is already handled by `KIND_MISMATCH` and the budget |
| whole-run filter soundness | not addressed | `list` = universe, test-side closure, `reads`, opaque contract → `ESCALATE`, red-proof fixtures | **n005** | the design driver of thinking_app's t381 record; the only way a `--tests` run can justify each omission |
| cost of a multi-method selection | invocation group: `overhead.p95 + Σ unit.p95`, `group_by: class` | variants batch into one invocation; overhead rows recorded | **n004** | n005 records the overhead but sums per-variant p95; group costing is what makes "12 methods across 3 classes" read as cheap. Bridged into `describe` (`group_by:`) and the ledger |
| runner unit granularity | `file \| class \| method \| suite` | `file \| class \| method \| variant \| suite` + `axis:`, `token_format:` | **n005**, n004's `gradle-class` method mode | the builtin consumes `<lowering>` verbatim, so `Class.method` per selected variant in one invocation per class is n004's mode |
| structural checks | `DEAD_AXIS_GLOB`, `UNMAPPED_CELL`, `UNCOVERED_VALUE` (also in `stale`) | `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`, `UNANNOTATED_MEMBER`, `DEAD_MEMBER`, `UNREGISTERED` | **union, all in `check`** | `UNCOVERED_VALUE` and `UNMAPPED_ARTIFACT` added; structural rot is `check`'s (like `DEAD_SCOPE`), content and evidence are `stale`'s; `--strict` on both |
| symbol narrowing | none | opt-in `android-res` scanner | **n005** | first consumer of the reserved `symbols` slot; degrades to file level without a before blob |
| feedback | `axis-membership-missing`, widen only | automatic score after every full run, `costs/predictions.yaml`, `missing-axis-source`, `readiness` | **n005 + n004's widen-only rule** | t386's `PREDICTION_FALSE_NEGATIVES:` shape, and it feeds admission |
| run-gate admission | none | `run_gate_admission` + `readiness` | **n005** | t388's three criteria, as data the engine reports and never enforces |
| variant batches in waves | cells ride wave 1 unless contended | variants are unit kind, one invocation | **n005 + ordering** | within a wave, invocations holding an admission resource are ordered last; thinking_app's whole JVM suite is one Gradle run either way |
| `--axis` knob | yes | `--format tokens` | **both** | `--axis matrix.locale=ar` forces a facet; `--format tokens` feeds `preview` |
| `classify --suggest` | grid heuristic | `reads`-helper heuristic | **both** | |
| latency fixture | 2,500-cell table < 400 ms | thinking_app shape (49 × 10, ~370 classes, ~900 Kotlin) < 250 ms | **n005** | no cell table exists in the merged design |
| stale/check classes for axes | `STALE_AXIS` in `stale` | check rules only | **check** | membership rot is structural, not content |
| evidence for variants | none | per variant; `EVIDENCED` only when every reached variant is anchored | **n005** | a Hebrew render says nothing about an Arabic line box |
<!-- /section: decision_matrix -->

<!-- section: architecture [dimensions: component_go_engine, component_engine_binary, component_binary_distribution, component_engine_packaging, component_registry_loader, component_user_root, component_framework_home] -->
## Architecture

### Process boundary

```
ait testmap <verb> ...                          (user / skill / gate verifier)
 └─ .aitask-scripts/aitask_testmap.sh           bash shim, ~35 lines; sources lib/aitasks_home.sh
      │   resolve  $AIT_TESTMAP_BIN  >  AIT_ENGINE=dev → $AITASKS_HOME/engine/dev/ait-testmap
      │            >  $AITASKS_HOME/engine/v$(cat .aitask-scripts/VERSION)/ait-testmap
      │   verify   `<bin> version` == VERSION (dev: <VERSION>-dev+<sha>), else ENGINE_MISSING:<path> / ENGINE_MISMATCH, exit 3
      │   for --task verbs: aitask_change_surface.sh list <id>  |  <bin> <verb> --changes - ...
      └─ $AITASKS_HOME/engine/v<VERSION>/ait-testmap --repo-root "$AIT_DIR" <verb> ...
           internal/registry        merge aitestmap/registry/*.yaml + axes.yaml → six tables; id grammar; owns: routing; check rules
           internal/axes            axis table, facet lookup, source-glob join, variant validation, --axis knob, axes --explain
           internal/annot           grammar v3 scanner (unit blocks, reads, axis), stamp reader, line-targeted rewriter
           internal/deps            bash/python/go/kotlin/gradle scanners (kotlin: opaque contract, main + test roots) + android-res + plugins
           internal/changesurface   BASELINE:/PLANSCOPE:/COMMITTED:/TASK:/OTHER:/UNKNOWN: parser; before-blob resolution
           internal/selectr         graded walk, rules, variant expansion, axis join, test-dep, ESCALATE, scoped join, group budget, formats
           internal/sched           errgroup waves, flock slot files, admission/allocator exec, broad_after_unit, schedule report
           internal/runner          describe/list TSV/manifest/results codecs (child rows, artifact column), bindings, builtins, inversion
           internal/cost            Welford + P² per id, invocation-group overhead, ledger, fold, last_pass, flake, predictions.yaml
           internal/feedback        score (auto on full runs), attribute, readiness
           internal/stale           digest compare, per-variant evidence join, classes, confirm/retarget
           internal/gitx            git via os/exec: rev-parse, ls-tree, merge-base --is-ancestor, log --name-status -M, show <sha>:<path>
           internal/platform        os/arch naming shared with engine/build.sh
             ├─ exec:  git, runner scripts or builtin runners, admission/allocator commands, scanner plugins
             └─ files: aitestmap/** (committed) · .aitask-testmap/ (runs, ledger; gitignored) ·
                       ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/ · ${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/aitasks-testmap-<uid>/
.aitask-scripts/lib/aitasks_home.sh             AITASKS_HOME, aitasks_engine_dir  (the only owner of the per-user root)
.aitask-scripts/aitask_gate_testmap_check.sh    machine verifier  <task> <attempt> <run-id> → check --task
.aitask-scripts/aitask_gate_testmap_run.sh      machine verifier  → select --include-stale → schedule → run
.aitask-scripts/aitask_engine.sh                ait engine build | test | cross | prune | home [--migrate]
.claude/skills/aitask-gate-testmap-fresh/       procedure gate: consumes `stale` lines, fixes annotations, `verify`
.claude/skills/aitask-testmap/                  agent skill: annotate (file/member/axis), axes, reads, attribute, verify, classify, tokens
engine/                                          Go source — framework repo only; excluded from the release tarball
```

The boundary rule is n003's and unchanged: parse, walk, match, digest and
schedule in Go; gate ledger, task file and shell environment in bash; the
binary never writes `aitasks/`, `aiplans/`, `.aitask-data/` or a gate ledger
and never invokes `aitask_*.sh`; builtin runners exec what `runners.yaml` gives
them. thinking_app's lowering (`matrix_classes`, `preview_resolve_token`) stays
in that repository's bash behind its own runner script; the engine sees ids
and lowerings as opaque strings. There is no `internal/home`: the engine's
state is repository-local and XDG-cached, the shim resolves the binary, and
`version --json` prints `ENGINE:<path>` from `os.Executable()`.

### Go module (`engine/`)

Unchanged from n003 — `go 1.26`, pinned toolchain, `CGO_ENABLED=0`, `-trimpath
-buildvcs=false -ldflags "-s -w -X main.version -X main.commit -X main.contract=1"`,
`gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`, `golang.org/x/sync`, stdlib `flag`,
`syscall.Flock`, `os/exec` git — plus one package, `internal/axes`, and one
fixture family under `testdata/opaque/` with one Kotlin file per opaque branch
and a test that disables that branch and asserts the verdict flips from
`ESCALATE` to a narrow selection.

### Where state lives

| data | location |
|---|---|
| registry, runners, resources, areas, axes, committed costs, predictions | `aitestmap/**` in the code tree |
| run outputs, prediction records, local ledger | `.aitask-testmap/runs/<run-id>/`, `.aitask-testmap/ledger.jsonl` (gitignored; `AIT_TESTMAP_DIR` override) |
| gate logs | `.aitask-gates/<task>/<gate>_<run-id>.log` |
| dependency-scan cache | `${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json` |
| host-scope locks | `${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/aitasks-testmap-<uid>/<resource>.<slot>.lock` |
| engine binaries | `$AITASKS_HOME/engine/v<VERSION>/ait-testmap` (+ `.sha256`), `$AITASKS_HOME/engine/dev/ait-testmap` (+ `.dev`) — never on PATH |
| legacy Python tenants | `~/.aitask/{venv,pypy_venv,python,bin,uv,dev_tier,update_check}` until `ait engine home --migrate` moves them and leaves `~/.aitask` as a symlink |

### Registry directory (one directory, six tables)

```
aitestmap/
  config.yaml            unit_covers_max: 8 · suite_budget_s: 600 · bootstrap_until · require_stamp · broad_review_days: 0
                         concurrency: serial|parallel · broad_after_unit: true · device_policy: filter_by_resource
                         host_class · flake_threshold: 0.2 · symbol_scanners: [] (thinking_app: [android-res])
                         run_gate_admission: {min_scored_full_runs: 0, max_false_negatives: 0, require_opaque_proofs: true, approved_by: null}
  axes.yaml              optional; declared axes with facets, values and facet-valued sources
  runners.yaml           runner repository (builtin: or script), bindings, command:/cwd: overrides, unit, axis, group_by, token_format
  resources.yaml         named resources (mutex / semaphore / admission / allocator; host / worktree / run)
  registry/
    _scanned.yaml        generated: unit and member edges with @date/blob10 stamps; variants: {axis, values[]} per member;
                         axis: coordinates from testmap:axis lines                           written only by scan --apply
    _scoped.yaml         generated: broad rows (areas, globs, triggers, reads_from, reviewed)   written only by scan --apply
    observed.yaml        written only by attribute: observed edges, axis sources (widen only), area members, triggers
    areas.yaml           hand-written named glob sets (seedable via areas --import-codemap)
    <area>.yaml          hand-written: owns:, edges, scopes, rules, waivers, areas:
  costs/<hostclass>.yaml Welford n/mean/sd/p95/last + last_pass {sha, at, run_id} + flake per id; invocation-group overhead rows
  costs/predictions.yaml last 200 scored full runs: {run_id, prediction_run_id, task, predicted, false_negatives, missed[]}
  runners/*.sh           optional project runners (a script named like a builtin shadows it)
  scanners/*             optional executable scanner plugins
```

Merge rule as in n003 (every `registry/` file contributes rows to the same
tables; `owns:` routing; `contract:` per file with `CONTRACT_MISMATCH`
refusal). The axis table is loaded from `axes.yaml` only. `check` rules gained
since n003: `DEAD_AXIS_SOURCE:<axis>.<facet>=<v>|<glob>` (a source glob
matching no file), `UNKNOWN_VARIANT:<id>` (a listed variant outside the
axis's values), `UNCOVERED_VALUE:<axis>|<value>` (a declared value no runner
lists — n004), `UNANNOTATED_MEMBER:<id>` (listed, no `testmap:unit` block),
`DEAD_MEMBER:<file>#<member>` (a block no runner lists),
`UNREGISTERED:<path>` (a test file no runner lists), and
`UNMAPPED_ARTIFACT:<path>|<runner>` (a file matching a runner's declared
`artifact_glob:` that no listed id claims — n004's `UNMAPPED_CELL`, the
silent-green class `MatrixClassificationTest` closes by hand). The last three
structural rules fail `check --strict` only until a repo has finished
bootstrapping, the treatment `UNSTAMPED` gets.
<!-- /section: architecture -->

<!-- section: framework_home [dimensions: component_user_root, component_framework_home, requirements_user_root, requirements_framework_home_name, assumption_legacy_user_root_coexists, assumption_home_symlink_compatibility] -->
## The Per-User Root, and the Migration Kept Behind a Verb

### What this feature installs (n005)

```
$AITASKS_HOME                      default $HOME/.aitasks   (env override; never falls back to ~/.aitask)
  engine/
    v<VERSION>/ait-testmap         exact-version slot the shim requires == .aitask-scripts/VERSION
    v<VERSION>/ait-testmap.sha256  sidecar; ait setup short-circuits when it matches the release SHA256SUMS
    dev/ait-testmap                ait engine build output; version must read <V>-dev+<sha>
    dev/.dev                       {source, commit} marker; never overwritten without --force-engine
    .home.lock                     flock target for --migrate and for ait engine prune
```

Owner: `.aitask-scripts/lib/aitasks_home.sh` —
`AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"`,
`aitasks_engine_dir() { printf '%s/engine/%s' "$AITASKS_HOME" "$1"; }` —
sourced by the shim, `install_engine_binary()` in `aitask_setup.sh`,
`aitask_engine.sh` and both gate verifiers. Every message that names the slot
(`ENGINE_MISSING:<path>`, `ENGINE_BUILT:<path>|<commit>`,
`TESTMAP_BINARY:installed:<path>`) prints the resolved path; `ait setup`'s
summary prints `AITASKS_HOME:<path>` beside the venv line so a host with both
roots sees both. `ait engine prune` walks `$AITASKS_HOME/engine/v*/` only.
Precedents already in the tree: `~/.config/aitasks/projects.yaml`
(`aitask_projects.sh`), `~/.config/aitasks/agent_marks.json`,
`${XDG_CACHE_HOME:-~/.cache}/aitasks/`. Tests: `tests/test_aitasks_home.sh`
(default, env override, and a grep that fails if any file this feature adds
names `~/.aitask/`); `test_testmap_shim.sh` and `test_install_engine_binary.sh`
assert the new path. Docs (`aidocs/framework/go_engine.md`, the `CLAUDE.md`
Engine block, `packaging_strategy.md`) name `~/.aitasks/engine/` and say in
one sentence that `~/.aitask/` holds the Python tenants until migrated.

Not changed: `.aitask-testmap/` and every other per-repository `.aitask-*`
directory (`.aitask-data`, `.aitask-gates`, `.aitask-explain`, …) — a rename
there has cross-repository blast radius and no user-visible benefit; the
mandate is about the user's home, which the framework owns entirely.

### The migration, as a verb (n004's mechanism, corrected)

`ait engine home` prints the resolved root, whether `~/.aitask` exists and
which known tenants it holds, whether `~/.aitask` is already a symlink and to
where, and what `--migrate` would do. `ait engine home --migrate`:

```
flock $AITASKS_HOME/.home.lock (mkdir -p $AITASKS_HOME first; fail fast if another ait holds it)
  ├─ ~/.aitask absent                              → HOME_SKIPPED:no-legacy-root
  ├─ ~/.aitask is already a symlink → $AITASKS_HOME → HOME_SKIPPED:already-migrated   (idempotent re-run)
  ├─ ~/.aitask is a symlink elsewhere              → HOME_SKIPPED:foreign-symlink:<target>
  ├─ ~/.aitask and $AITASKS_HOME on different devices → HOME_SKIPPED:cross-device
  ├─ an entry under ~/.aitask outside the known set  → HOME_SKIPPED:unknown-entry:<name>   (report; never guess)
  │     known set: {venv, pypy_venv, python, bin, uv, dev_tier, update_check, engine}
  │     pypy_venv is the correction to n004: setup_pypy_venv() creates it and python_resolve.sh
  │     reads $HOME/.aitask/pypy_venv; the host this was designed on carries it
  ├─ for each known entry present: mv ~/.aitask/<e> $AITASKS_HOME/<e>   (same-device rename, atomic per entry)
  ├─ rmdir ~/.aitask                                                    (fails loudly if not empty)
  └─ ln -s $AITASKS_HOME ~/.aitask                                      → HOME_MIGRATED:<n entries>
```

Why the symlink is safe (n004's premise, verified here): the venv's
`pyvenv.cfg` records `command = … -m venv /home/<u>/.aitask/venv` as
information only; console-script shebangs are
`#!/home/<u>/.aitask/venv/bin/python3` and dereference; the
`~/.aitask/bin/{python,python3}` wrappers `exec "$HOME/.aitask/venv/bin/python"`;
`~/.aitask/python/<ver>/bin/python3` symlinks point at absolute interpreter
paths outside the home; `lib/aitask_path.sh` prepends a path that resolves
through the link. A grep over `.aitask-scripts/`, `ait` and `install.sh` finds
no `==`/`!=`/`-ef` comparison and no `realpath`/`os.path.realpath`/`samefile`
on the home path. Reverting is `rm ~/.aitask && mv ~/.aitasks ~/.aitask`.

Why it is not the default in this release: it touches every install in the
field; its refusal cases are exactly the ones a designer does not see on their
own host (the `pypy_venv` omission is the proof); and the framework's rule for
setup-flow helpers is that they are exercised through a real `install.sh
--dir` run before they ship — which is a task of its own, not a paragraph in
this one. `ait setup` prints `HOME_LEGACY:<path>|run 'ait engine home
--migrate'` when legacy tenants exist and continues. The follow-up that flips
the default is admitted when `tests/test_aitasks_home.sh` covers: fresh
install; migration from a populated legacy root with a working venv and PyPy
venv afterwards; idempotent re-run; a hostile pre-existing `~/.aitask`
symlink; cross-device refusal; and the `AITASKS_HOME` override isolating a run.
Until then `~/.aitasks/` (engine) and `~/.aitask/` (Python) coexist and share
nothing.
<!-- /section: framework_home -->

<!-- section: product_spaces [dimensions: component_variant_axes, component_axes, component_cell_enumeration, requirements_axis_product_selection, requirements_screen_locale_subdivision, assumption_axis_sources_declarable, assumption_axis_membership_declarable, assumption_cells_enumerable_by_plugin, assumption_variant_universe_from_runner_list] -->
## Product Spaces: Member Units, Variant Axes, One Enumeration Surface

### The shape being modelled (verified against thinking_app)

Ten recording matrices (`known_matrices()` in
`tools/verification/lib/screenshot-review.sh`): `pixel5_rtl`, `pixel5_ltr`,
`shortPhone_rtl`, `shortPhone_ltr`, `imeProxy_rtl`, `bidiSampler_rtl`,
`pixel5Ru_ltr`, `shortPhoneRu_ltr`, `pixel5Ar_rtl`, `shortPhoneAr_rtl`. Each
is one to three Robolectric classes (`matrix_classes()`), each class one
`@Config(qualifiers = …)` whose constant is literally locale × direction ×
geometry (`he-rIL-ldrtl-…`, `en-rUS-ldltr-…`, `ru-rRU-ldltr-…`,
`ar-rEG-ldrtl-…`). 49 `ScreenFixture("Name") { … }` bodies in
`ScreenFixtures.kt` (76 KB) compose production screens; the abstract
`ScreenCatalogScreenshotsTest` dispatches `@Test fun welcome() =
capture(ScreenFixtures.welcome())` once per subclass. The catalogue is a
membership contract: `secondary-matrices-expected.txt` lists 247 goldens (48
`pixel5Ru_ltr`, 47 each `pixel5_ltr` / `shortPhone_ltr` / `pixel5Ar_rtl`, 17
each `shortPhone_rtl` / `shortPhoneRu_ltr` / `shortPhoneAr_rtl`, 6
`imeProxy_rtl`, 1 `bidiSampler_rtl`), `primary-catalog-expected.txt` ~50. The
routing *token → (matrix, class, method, png)* is `preview_resolve_token`;
`preview [<matrix>:]<Screen>…` and `unit-tests --tests <fqn>` already narrow
along it; `verify_active_tiered` already wires `suite-outcome-check.py
--require-ran/--forbid-ran/--expect-run-id`. What no file states is
*production composable → screen token*. And what constrains any selector is
that `--tests` filters the whole `testDebugUnitTest` run.

### The id grammar (n005)

`<path>[#<member>][@<variant>]`:

- `<path>` — a test file, the n003 unit.
- `#<member>` — a named block inside the file, opened by `testmap:unit
  <Member>`. A member has its own `covers` edges, stamps, costs and evidence;
  the file itself is not a unit when it has members.
- `@<variant>` — a value of the axis the unit's runner declares. Variants are
  enumerated by the runner's `list`, never written by hand; they share the
  member's annotations and have their own cost, `last_pass` and evidence rows.

### Axis declaration (n005 schema)

```yaml
# aitestmap/axes.yaml  (thinking_app; the engine ships no axis of its own)
contract: 1
axes:
  matrix:
    facets: [locale, direction, geometry]
    values:
      pixel5_rtl:       {locale: he, direction: rtl, geometry: pixel5}
      pixel5_ltr:       {locale: en, direction: ltr, geometry: pixel5}
      shortPhone_rtl:   {locale: he, direction: rtl, geometry: shortPhone}
      shortPhone_ltr:   {locale: en, direction: ltr, geometry: shortPhone}
      imeProxy_rtl:     {locale: he, direction: rtl, geometry: imeProxy}
      bidiSampler_rtl:  {locale: he, direction: rtl, geometry: pixel5}
      pixel5Ru_ltr:     {locale: ru, direction: ltr, geometry: pixel5}
      shortPhoneRu_ltr: {locale: ru, direction: ltr, geometry: shortPhone}
      pixel5Ar_rtl:     {locale: ar, direction: rtl, geometry: pixel5}
      shortPhoneAr_rtl: {locale: ar, direction: rtl, geometry: shortPhone}
    sources:                                   # facet value <- source globs: the axis edges
      locale:
        he: ["app/src/main/res/values-iw/**", "app/src/main/res/raw-iw/**", "app/src/main/res/font/heebo_*.ttf"]
        en: ["app/src/main/res/values-en/**", "app/src/main/res/raw-en/**", "app/src/main/res/font/roboto_*.ttf"]
        ru: ["app/src/main/res/values-ru/**", "app/src/main/res/raw-ru/**", "app/src/main/res/font/roboto_*.ttf"]
        ar: ["app/src/main/res/values-ar/**", "app/src/main/res/raw-ar/**", "app/src/main/res/font/cairo_*.ttf"]
      # direction and geometry have no sources: they are test-side constants in ScreenshotTestHarness.kt,
      # reached through the test-dep closure (every screen class imports them), which selects every variant.
```

Sources every locale reads — `app/src/main/res/values/**` (the Hebrew mirror
plus `system_strings.xml` and `donottranslate.xml`), `utils/TypeScale.kt`,
`utils/Fonts.kt`, `ui/components/AppRoot.kt` — are not axis sources. Kotlin
files reach screens through edges or the import scanner and select every
variant. The resource directory `values/**` has no Kotlin importer and no
member names it, so thinking_app's hand file declares one rule —
`when: ["app/src/main/res/values/**"] select: ["app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt#*"] distance: 1`
— every member, every variant, narrowed to the members naming a changed key
when `android-res` is enabled. Without that rule the change would refuse
selection, which is the fail-closed default and the right first-day
behaviour.

### The selection rule (formal, so the runner and `explain` agree)

1. An **edge, rule, dependency hop or test-dep** that reaches a unit selects
   **all** of its variants (`#Welcome@*`), reason as in n003, and the row
   prints `@*` as its facet reason.
2. A changed path matching an **axis source** selects, for every unit whose
   runner lives on that axis, the variants whose facet carries the value
   (`*@pixel5Ru_ltr`, `*@shortPhoneRu_ltr`), reason
   `axis(matrix.locale=ru) <- app/src/main/res/values-ru/strings.xml`, at
   distance 1 — and every plain unit carrying `testmap:axis
   matrix.locale=ru` (n004's hand-declared coordinate, for a test that
   occupies a coordinate but writes no golden).
3. With `symbol_scanners: [android-res]` and a reachable before blob, rule 2
   is narrowed to the members whose forward closure names a changed key:
   `axis(matrix.locale=ru)[timer_ring_label,daily_summary] <- values-ru/strings.xml`.
4. Several hits **union**. There is no intersection across hits, because each
   hit is a real blast radius. This is n004's per-file union stated once: a
   file with a locale source and a file with a screen edge give
   *locale-variants ∪ screen-variants*, never their product.
5. A file matching no axis source is not an axis hit; it reaches units only
   through rules 1 and 3, which select every variant — n004's `ANY`, without a
   second vocabulary.
6. `--axis <axis>.<facet>=<v>` (n004) forces a facet for a reviewer probing one
   matrix; `--format tokens` prints one line per selected variant in the
   runner's `token_format`.
7. Cost, ranking, budget, `last_pass`, evidence and `score` operate on
   variant ids; stamps and annotations operate on the member.

Worked on the real grid (n004's cases, n005's semantics):

| change set | selected |
|---|---|
| `res/values-ar/strings.xml` | every enrolled screen × `{pixel5Ar_rtl, shortPhoneAr_rtl}` = 64 variants (47 + 17) + `ArMatrixArabicOnlyTest` (`testmap:axis`) |
| `ui/mvvm/questions/QuestionsScreen.kt` | `#Questions@*` — every matrix Questions is enrolled in |
| both of the above | the union: 64 + the Questions variants outside the two Arabic matrices |
| `res/font/cairo_bold.ttf` | the same 64 |
| `ui/components/HeroBand.kt` | every member whose closure imports it, every variant (d2) — a superset of thinking_app's t86 case |
| `utils/TypeScale.kt` (`const val`) | `ESCALATE:…TypeScale.kt|const-val|screen-matrix,gradle-class` — the whole JVM suite at d0 |
| `ScreenshotTestHarness.kt` | every screen class through the test-dep closure |

### One enumeration surface: the runner's `list`

The variant universe is what the project's runner prints from `list` — for
thinking_app, one row per golden in the two membership manifests plus one row
per other class under `app/src/test/java`. n004's `aitestmap/cells/` plugin is
that same script; n004's `_cells.yaml` is the `variants: {axis, values[]}`
field `scan --apply` writes on each member row of `_scanned.yaml` (49 rows,
each with at most ten values) so that `select` never execs a runner. `check`
and `scan` exec `list`; `select`, `stale` and `explain` read the committed
table. A listed variant outside the axis is `UNKNOWN_VARIANT`; a declared
value no runner lists is `UNCOVERED_VALUE` (n004); a listed member with no
block is `UNANNOTATED_MEMBER`; a block no runner lists is `DEAD_MEMBER`; an
unlisted test file is `UNREGISTERED`. A runner whose `describe` names an
`artifact_glob:` (thinking_app: `app/src/test/screenshots/**/*.png`) gets the
two-way reconciliation n004 asked for: every listed id may carry an
`artifact` column, and a file matching the glob that no id claims is
`UNMAPPED_ARTIFACT` — an entire matrix's goldens entering the tracked tree
audited by nobody, with every gate green, is the failure `MatrixAuditRegistry`
and `MatrixClassificationTest` exist to close by hand.

`ait testmap axes --list | --check | --explain <path>` (n004's verbs) prints,
for one file, every facet value it sources and why, or that it sources none:

```
AXIS:matrix.locale|ar|glob app/src/main/res/font/cairo_*.ttf|axes.yaml:22
AXIS:matrix.direction|-|no source declared (test-side constant)
AXIS:matrix.geometry|-|no source declared (test-side constant)
```

In `aitasks` the same machinery applies to `tests/golden/`: a `renders` runner
lists `tests/test_skill_render_<skill>.sh#<skill>@<profile>-<agent>` from the
`SKILL-<profile>-<agent>.md` files, with an `agent` facet sourced from
`.claude/**`, `.opencode/**`, `.agents/**` and a `profile` facet sourced from
the per-profile Jinja partials — a change to one agent's tree selects that
agent's goldens across every skill.

### What variant axes are not

Not a replacement for `covers` (a member still names the sources it renders);
not a replacement for `area`/`scope` (a broad test with no grid is a scoped
row); not inferred (the engine never guesses a coordinate; an undeclared axis
means every variant is selected, which is more, not less).
<!-- /section: product_spaces -->

<!-- section: thinking_app_mapping [dimensions: component_selector, component_runner_contract, component_reference_runners, component_dependency_scanners, component_annotation_scanner, assumption_kotlin_scanner_fail_closed, assumption_existing_locks_wrappable] -->
## Worked Mapping: thinking_app

### Annotations

```kotlin
    // testmap:unit Welcome
    // testmap:covers app/src/main/java/com/softman/thinking/ui/mvvm/auth/welcome/WelcomeScreen.kt   @2026-09-16/7c1e0b9a3d
    // testmap:covers app/src/main/java/com/softman/thinking/ui/mvvm/auth/welcome/WelcomeViewModel.kt @2026-09-16/2a9f47d0c1
    fun welcome(coordinator: MainCoordinator = coordinator()) = ScreenFixture("Welcome") {
        val viewModel = WelcomeViewModel(coordinator).apply { registerResult.value = "" }
        WelcomeScreen(viewModel).body()
    }
```

`ait testmap annotate ScreenFixtures.kt#Welcome --from-body` seeds these from
the block's own symbols through the Kotlin scanner's import resolution; the
agent confirms; the stamp is the tool's. A file-level block before the first
`testmap:unit` carries `testmap:kind unit` and `testmap:runner screen-matrix`.
Tree-scanning helpers declare what they read once, in the helper
(`// testmap:reads app/src/main/java/**/*.kt` in `SourceFence.kt`); every unit
whose test-file closure imports `SourceFence` (71 files today) inherits that
glob as a trigger, never deferred, with reason `reads(SourceFence.kt) <-
<path>`. A non-capturing test that belongs to a coordinate says so:
`// testmap:axis matrix.locale=ar` on `ArMatrixArabicOnlyTest.kt`.

### Runners

```yaml
# aitestmap/runners.yaml  (thinking_app)
runners:
  screen-matrix: {exec: tools/verification/testmap_runner.sh, unit: variant, axis: matrix, batch: true,
                  needs: [heavy-run], group_by: class, token_format: "{variant}:{member}",
                  artifact_glob: "app/src/test/screenshots/**/*.png"}
  gradle-class:  {exec: tools/verification/testmap_runner.sh, unit: class, batch: true, needs: [heavy-run]}
  verify-active: {exec: tools/verification/screenshot-tests.sh, unit: suite, full: true,
                  children: tools/verification/testmap_runner.sh}     # post-processor: results-summary.json → child rows
bindings:
  - {glob: "app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt", runner: screen-matrix}
  - {glob: "app/src/test/java/**/*.kt",                                        runner: gradle-class}
```

`tools/verification/testmap_runner.sh` (project-owned, sources
`lib/screenshot-review.sh`):

- `describe` → `contract:1 unit:variant axis:matrix batch:true needs:heavy-run group_by:class token_format:{variant}:{member} artifact_glob:…`.
- `list` → for every non-comment line of the two manifests
  (`<Screen>_<matrix>.png`): one row
  `…/ScreenFixtures.kt#<Screen>@<matrix>\tunit\t<lowering>\t<artifact>` where
  `<lowering>` is the comma-joined `<class>.<method>` for every class in
  `matrix_classes <matrix>` (the base class owns the method; the others are
  inert because Gradle fails only when the whole include set matches
  nothing); plus one row per other class under `app/src/test/java` for
  `gradle-class`. The two runners share the script and split the universe by
  binding, so every JVM class is listed exactly once.
- `run --manifest <f> --out <d>` → collects lowerings →
  `screenshot-tests.sh unit-tests --tests <l1> --tests <l2> …` (which reserves
  the heavy-run slot through `jvm_gradle`, sets `-Pthinking.runId` and
  classifies the no-verdict states) → `suite-outcome-check.py
  --expect-run-id <id> --require-ran <every class in the manifest>` → parses
  `app/build/test-results/testDebugUnitTest/*.xml`, inverting each
  `<testcase classname name>` through its own `list` table to an id; a
  `pixel5Ru_ltr` `welcome` failure carries
  `{"status":"fail","evidence":{"golden":"Welcome_pixel5Ru_ltr.png","compare":"<abs path>"}}`.
  A row inverting to no registered id, or `units_reported == 0` with
  `units_expected > 0` (the zero-match trap n004 names — a `--tests` filter
  matching nothing exits 0), is a mechanism failure with a `cause`, never a
  pass, and anchors nothing. Exit contract `0/1/2/75/64` as `unit-tests`
  defines it.
- `children` (for the `verify-active` suite runner) → after a full run,
  `lib/screenshot-diff-set.sh` rows keyed on `result_id` (= golden basename)
  become child rows `{id: …#<Screen>@<matrix>, status, parent: verify-active}`
  for every catalogue golden, so the full gate anchors per-variant evidence
  and feeds the prediction ledger without ever being *selected* per variant.

### Three changes, three selections, with group costing

```
$ ait testmap select --task t9001 --changes -          # t9001 edits ui/mvvm/auth/welcome/WelcomeScreen.kt
…ScreenFixtures.kt#Welcome@pixel5_rtl        d=1 unit  edge(annotation) WelcomeScreen.kt  @*     grp CurrentHeadScreenshotsTest  est 0.34s
…ScreenFixtures.kt#Welcome@pixel5_ltr        d=1 unit  edge(annotation) WelcomeScreen.kt  @*     grp Pixel5LtrScreenshotsTest    est 0.31s
…  (every matrix Welcome is enrolled in — 8: it is absent from imeProxy_rtl and bidiSampler_rtl)
…testing/SourceFenceTest.kt (+70)            d=1 unit  reads(SourceFence.kt) <- WelcomeScreen.kt
…testing/PrimaryCtaReachabilityTest.kt       d=2 unit  test-dep WelcomeScreen.kt <- Welcome fixture
ESTIMATE:unit|8 groups|overhead 8×p95 4.6s + Σ 2.7s ≈ 39s in one Gradle invocation
tokens: pixel5_rtl:Welcome pixel5_ltr:Welcome shortPhone_rtl:Welcome shortPhone_ltr:Welcome pixel5Ru_ltr:Welcome …

$ ait testmap select --task t9002 --changes -          # t9002 edits res/values-ru/strings.xml (2 keys), symbol_scanners: [android-res]
…ScreenFixtures.kt#Questions@pixel5Ru_ltr      d=1 unit  axis(matrix.locale=ru)[timer_ring_label,accumulated_time] <- values-ru/strings.xml
…ScreenFixtures.kt#Questions@shortPhoneRu_ltr  d=1 unit  axis(matrix.locale=ru)[timer_ring_label,accumulated_time] <- values-ru/strings.xml
…ScreenFixtures.kt#QuestionNumber@pixel5Ru_ltr d=1 unit  axis(matrix.locale=ru)[accumulated_time] <- values-ru/strings.xml
…RuMatrixRussianOnlyTest.kt                    d=1 unit  axis(matrix.locale=ru) <- values-ru/strings.xml   (testmap:axis)
…localization/CatalogParityGateTest.kt         d=1 unit  reads(CatalogManifest.kt) <- values-ru/strings.xml
tokens: pixel5Ru_ltr:Questions shortPhoneRu_ltr:Questions pixel5Ru_ltr:QuestionNumber
        (without android-res: every enrolled screen on both ru matrices — 65 variants — same reason minus the key list)

$ ait testmap select --task t9004 --changes -          # t9004 edits utils/TypeScale.kt, which declares `const val`
ESCALATE:app/src/main/java/com/softman/thinking/utils/TypeScale.kt|const-val|screen-matrix,gradle-class
…  every id of both runners at d=0 — the whole JVM suite, which is what verify-active runs
```

`select --format tokens | xargs tools/verification/screenshot-tests.sh preview`
is the advisory surface the repository's design record calls Stage 1: it runs
no verdict and gates nothing. The full `verify-active` stays the completion
gate (`test_command`); its child rows score every prediction made during the
task.

### What the fail-closed scanner costs there, measured

The opaque contract marks any file declaring `inline fun` or `const val`
(42 files under `app/src/main/java`) or a DI binding (`@Module` / `@Provides`
/ `@Inject`, 63 files) as opaque, so a change to any of them escalates to the
whole JVM suite. That is the project's own S1 contract (t384), chosen by the
project because the alternative is a `NARROW` verdict nobody can trust; the
prediction ledger is how the list is tuned, and every opaque branch has a
red-proof fixture so the fallback is shown reachable, not assumed.

### What stays in bash in that repository

`known_matrices`, `matrix_classes`, `matrix_manifest`, `preview_resolve_token`,
the membership manifests, `suite-outcome-check.py`, `screenshot-diff-set.sh`,
`heavy-run-lock.sh` (exit 75 admission) and `emulator-allot.sh` are untouched.
The runner script is the only addition; `axes.yaml`, one hand rule and the
annotations are the only committed data.
<!-- /section: thinking_app_mapping -->

<!-- section: data_flow [dimensions: component_selector, component_staleness_tool, component_freshness, component_evidence_join, component_cost_ledger, component_engine_packaging, component_binary_distribution, component_runner_contract, component_feedback_tools, component_framework_home] -->
## Data Flow

### Authoring → registry

```
test files ──annotations──▶ ait testmap scan --apply ──▶ registry/_scanned.yaml   unit/member edges {test, covers, from, line, stamped_at, stamped_blob, variants, axis}
                                                     └▶ registry/_scoped.yaml    broad rows {test, kind, areas, globs, triggers, reads_from, needs, reviewed_at, line}
runner list (TSV) ─────────────────────────────────▶ the universe: file ids, member ids, member@variant ids, lowering, artifact — consumed by scan and check only
hand files + areas.yaml + axes.yaml + observed.yaml ▶ merged registry (in memory, six tables)
```

`scan` asks every runner's `list` for the ids it owns, reads each annotated
file once, splits it into blocks at `testmap:unit` lines, matches `testmap:`
lines per comment leader (and Python module docstrings), refuses unknown keys
with a line number, joins member blocks to listed member ids by name, records
each member's listed variants, and rewrites each generated file only when
content changed. A `testmap:reads <glob>` line is legal only in a file no
runner lists (a helper) and lands in an in-memory helper table.

### Task → selection → run

```
aitask_change_surface.sh list t1234 ──▶ BASELINE:/PLANSCOPE:/COMMITTED:/TASK:/OTHER:/UNKNOWN: lines  (the shim pipes)
        ▼
ait-testmap select --task t1234 --changes - --include-stale [--format lines|json|tokens] [--axis a.f=v] --run <run-id>
        ├─ UNKNOWN: present ──▶ refuse (exit 1, lines echoed);  exclude aitasks/ aiplans/ .aitask-data/ .aitask-gates/
        ├─ opaque: a changed file the kotlin scanner marked opaque ──▶ ESCALATE:<file>|<reason>|<runners>  → every id of those runners at d0
        ├─ walk:  d0 changed tests + escalation
        │         d1 unit/member edges · axis sources (facet value → carrying variants and testmap:axis units; symbol-narrowed when enabled)
        │            · test-dep (changed file in a unit's own test-file forward closure, incl. helpers' reads globs) · scoped join
        │         d2.. reverse-dependency hops from the blob-keyed cache · rules inject select/implies/escalate
        ├─ expand: a hit on a member → all its variants; an axis hit → the carrying variants only; union across hits
        ├─ stale: `stale` mark when a selecting edge's stamped_blob ≠ current blob and any reached variant lacks evidence
        ├─ rank:  distance → kind (unit < integration < e2e < device) → est. cost ascending (per variant)
        ├─ group: variants of one runner sharing a group_by key form one invocation group; group cost = overhead.p95 + Σ unit.p95
        ├─ budget: broad rows and groups in ascending cost until suite_budget_s; remainder DEFERRED:<id>|budget; trigger and reads hits never deferred
        └─ write .aitask-testmap/runs/<run-id>/{selection.json, prediction.json}   (per-variant rows with facet reasons and groups)
           --format tokens: one line per selected variant in the runner's token_format (thinking_app: <matrix>:<Screen>)

ait-testmap schedule --run <run-id>  ──▶ waves, holds, critical path; variants of one runner batch into one invocation;
                                         within a wave, invocations holding an admission resource are ordered last
ait-testmap run --run <run-id>       ──▶ manifest.json {units: [{id, lowering, timeout_s}]} → runner → results.jsonl (per id) + runner.json
        ├─ wave 1: unit kind · wave 2+: broad kinds only if wave 1 is green (broad_after_unit)
        ├─ a suite runner may add child rows {id, status, parent: <suite id>} for registered ids it can attribute
        ├─ every result row → ledger.jsonl {run_id, id, status, duration_ms, head_sha}; every invocation → {group, overhead_ms, units_reported}
        ├─ units_expected ≠ units_reported, units_reported == 0 with units_expected > 0, or a report row inverting to no id → mechanism failure
        └─ run.json: aggregate status; exit 0 / 1 / 2 / 75 / 64
```

### Results → evidence → cost → prediction ledger

Every passing row whose invocation has no `cause`, for an id under the flake
threshold, advances that id's `last_pass {sha, at, run_id}`. `costs --update`
folds the ledger — per-id rows and per-invocation overhead rows — into
`costs/<hostclass>.yaml`. **After any full run** — `run --all`, or a `unit:
suite` runner marked `full: true` (thinking_app's `verify-active`) — the engine
looks up the newest `prediction.json` for the same task (or, with no task, the
newest on this host for HEAD's first-parent chain), scores it, and prints
`PREDICTION_SCORED:<prediction_run_id>|<full_run_id>`,
`PREDICTION_FALSE_NEGATIVES:<n>` and one `PREDICTION_MISSED:<id>` per failed
id the prediction did not select (a changed golden is a failure here),
appending to `costs/predictions.yaml` (200 rows, oldest dropped). No
prediction → `PREDICTION_SCORED:none`. The count is a plain non-negative
integer and never a verdict.

### Post-implementation → staleness → fix in the same commit

As in n003 (`stale --task --changes -` → `STALE_PATH` / `STALE` / `EVIDENCED`
/ `UNSTAMPED` / `STALE_AREA` / `REVIEW_DUE` / `UNKNOWN` / `DISPLAY` /
`DECISION`), with one change: for a member with variants the evidence join
runs per reached variant and the row reads

```
STALE:<test>|<source>|<stamped_at>|<stamped_blob>|<current_blob>|<unevidenced variants>
EVIDENCED:<test>|<source>|<stamped_blob>|<current_blob>|<run_sha>|<run_id>       every reached variant evidenced
```

where `<unevidenced variants>` is a comma list (`pixel5Ar_rtl,shortPhoneAr_rtl`)
or `-` for a unit without variants. The procedure gate shows the same
`git diff <stamped_blob> <current_blob>` and, for a variant-bearing row, names
the matrices not yet rendered against the current bytes — exactly the
`preview <matrix>:<Screen>` invocation to run before confirming. Structural
rot on axes, members and artifacts is `check`'s, not `stale`'s: `stale --all`
prints one `CHECK_STRUCTURAL:<n>` summary line so a repo-wide sweep sees it,
and `check --strict` is the gate.

### Release → host

```
git tag v0.36.0 ──▶ release.yml
   ├─ plan
   ├─ engine  (needs: plan)   setup-go (go-version-file: engine/go.mod) → go vet ./... → go test ./...
   │                          → engine/build.sh all 0.36.0 → dist/ait-testmap_0.36.0_{linux,darwin}_{amd64,arm64}
   │                                                        + dist/ait-testmap_0.36.0_SHA256SUMS.txt → upload-artifact
   ├─ release (needs: [plan, engine])  Verify VERSION == tag (unchanged) → tarball (noarch, engine/ excluded)
   │                                   → action-gh-release files: tarball + shim + 4 binaries + SHA256SUMS (both steps)
   └─ packaging (unchanged)            Homebrew / AUR / .deb / .rpm ship only the shim; nfpm arch: all
.github/workflows/engine-check.yml  (new)  on: push, pull_request  paths: [engine/**]  → gofmt -l, go vet, go test, 2x bench rule

ait setup   (or ait upgrade → install.sh --force → aitask_setup.sh --source-only → install_engine_binary)
   ├─ source lib/aitasks_home.sh; mkdir -p "$AITASKS_HOME/engine"
   ├─ legacy tenants under ~/.aitask and no symlink → HOME_LEGACY:<path>|run 'ait engine home --migrate'   (hint only; continue)
   ├─ os/arch via lib/platform_detect.sh; else ENGINE_UNSUPPORTED (skip, exit 0)
   ├─ $AITASKS_HOME/engine/v<V>/ait-testmap exists and .sha256 sidecar matches → return
   ├─ --local-engine <path>  |  curl -fsSL --max-time 60 <asset> + SHA256SUMS  |  --engine-from-source
   ├─ sha256sum -c / shasum -a 256 → install -m 0755 to .tmp → mv -f → write .sha256
   ├─ `<bin> version --json` must echo <V> (and prints ENGINE:<path>), else remove and fail loudly
   ├─ --no-testmap / AIT_TESTMAP_FETCH=0 → TESTMAP_BINARY:skipped:<reason>
   └─ summary: VENV:~/.aitask/venv … AITASKS_HOME:~/.aitasks  ENGINE:~/.aitasks/engine/v<V>/ait-testmap

ait engine build          → $AITASKS_HOME/engine/dev/ait-testmap + .dev marker; ENGINE_BUILT:<path>|<commit>
ait engine test | cross   → go vet + go test [-race] | build.sh all into engine/dist/ (identical to CI)
ait engine prune          → remove $AITASKS_HOME/engine/v*/ no project in ~/.config/aitasks/projects.yaml is on
ait engine home           → HOME_ROOT:<path>  HOME_LEGACY:<path>|<tenants>  HOME_SYMLINK:none|<target>  HOME_NEXT:<what --migrate would do>
ait engine home --migrate → HOME_MIGRATED:<n> | HOME_SKIPPED:<reason>      (explicit; never run by setup in this release)
AIT_ENGINE=dev ait testmap ...   → the dev slot
```
<!-- /section: data_flow -->

<!-- section: freshness [dimensions: component_freshness, component_staleness_tool, component_evidence_join, assumption_blob_digest_is_staleness_key, assumption_git_history_is_freshness_clock, assumption_passing_run_anchors_edges] -->
## Annotation Freshness with Variants

The stamp, the anchor and the join are n003's: `testmap:covers <path>
@<date>/<blob10>` per edge, `<blob10>` the git blob id of the covered source's
content computed in Go without invoking git, written only by `annotate`,
`verify` and `stale --confirm*` through the line-targeted rewriter
(`REWRITE_CONFLICT:` on an intervening edit); `last_pass {sha, at, run_id}`
per id from every passing row of an invocation without a `cause` under the
flake threshold; the evidence join asking, for an edge whose `stamped_blob ≠
current_blob`, whether a reachable `last_pass.sha` holds the source at exactly
`current_blob` (one `git ls-tree` per distinct sha); `EVIDENCED` on a hit,
`STALE` otherwise; a shallow clone sees only `STALE`, the safe direction.

The one refinement (n005) is where evidence lives: `last_pass` is recorded
**per id**, so a member with variants has one anchor per matrix, and the join
runs per reached variant. All reached variants evidenced → `EVIDENCED`;
otherwise `STALE` with the unevidenced variants named. A Hebrew render that
passed against the current `WelcomeScreen.kt` says nothing about the Arabic
render, whose line boxes run 27–30 % taller; the procedure gate must not
re-stamp on the strength of the wrong matrix. The full-run child rows make
this cheap: every `verify-active` at task completion anchors all 297 goldens
at once, so the next task's `stale` finds evidence for most hot sources
without anyone running anything extra.

`stale --confirm-evidenced` remains the only autonomous re-stamp and requires
every reached variant evidenced. `--confirm-source <path>` and `--retarget`
are unchanged. `verify <file>#<member>` re-stamps one member. The
`testmap_fresh` procedure gate (`kind: procedure`, the `docs_updated` shape,
dispatched by the existing procedure-gate block before the change summary so
stamp rewrites ride the `(t<id>)` commit; not a git hook, not a Claude Code
hook) follows n003's eight steps, with the variant-bearing `STALE` row naming
the matrices to preview, and with `check`'s structural rows (`UNCOVERED_VALUE`,
`UNMAPPED_ARTIFACT`, `DEAD_AXIS_SOURCE`, `UNANNOTATED_MEMBER`, `DEAD_MEMBER`)
resolved by editing `axes.yaml`, the runner's `list`, or the member block —
never waved through, because a row that survives a re-scan is a defect in the
project's own routing, which is worth surfacing at review time rather than at
the next full run.
<!-- /section: freshness -->

<!-- section: broad_tests [dimensions: component_suite_registry, component_broad_test_scopes, assumption_areas_express_suite_blast_radius, assumption_broad_tests_area_scoped] -->
## High-Level Tests: Scoped Rows, and Where Variants Take Over

Unchanged from n003 in substance. Integration, e2e and device tests declare
`testmap:area` (named glob sets from `areas.yaml`, seedable via `areas
--import-codemap`), `testmap:scope` (inline globs, budgeted) or
`testmap:trigger` (inline globs, budget-exempt), live in `registry/_scoped.yaml`
beside the unit table, join the ranked list at distance 1 as sinks, are ranked
`unit < integration < e2e < device` then by cost, are taken under
`suite_budget_s` with every cut printed as `DEFERRED:`, run only after a green
unit wave (`broad_after_unit`), are drift-flagged by evidence (`STALE_AREA`)
with `REVIEW_DUE` opt-in, and are widened by `attribute`
(`missing-trigger` / `area-too-narrow`). `covers` on a scoped row is allowed
for digest-stamped fixture pins.

Two additions since n003:

- **`testmap:reads <glob>` on a helper** (n005): every unit whose test-file
  closure contains the helper inherits the glob as a trigger, so
  thinking_app's 71 `SourceFence` importers stay selected on any Kotlin change
  — the floor the design record says a selector cannot trade away — as data,
  never deferred. `_scoped.yaml` rows gain `reads_from`.
- **A suite row may report child rows** (n005): a `unit: suite` runner marked
  `full: true` with a `children:` post-processor anchors registered ids on
  every run, so a wrapped full gate feeds evidence and the prediction ledger
  without ever being selected per variant.

Variant-bearing units are **unit kind**, not scoped rows: they carry
`covers`, stamps and evidence, they are never area-scoped, and their wave is
the unit wave — with the ordering refinement that invocations holding an
admission resource go last within a wave so a cheap red test reports before a
Robolectric boot. `classify --suggest` gains two heuristics: a test file
importing a `reads`-bearing helper (n005), and an area-scoped suite whose test
classes share a stem and differ by a token that also names a directory or a
resource qualifier — proposed as a variant axis with the candidate values
printed (n004).
<!-- /section: broad_tests -->

<!-- section: selection [dimensions: component_selector, component_dependency_scanners, assumption_change_surface_is_intake, assumption_static_granularity_v1] -->
## Selection: Fail-Closed Scanners and the Test-Side Closure

Intake, refusal on `UNKNOWN:`, the graded walk, rules, kind-then-cost ranking
and the cut knobs are n003's. Three additions (n005), one bridge (n004):

**Opaque contract (Kotlin scanner).** Handled constructs: an explicit `import
<repo package>…` → edge; a same-package reference → the package is fully
connected; a repo-package star import → an edge to every file in the package;
a fully-qualified in-body reference found in the comment-stripped body → edge.
Everything else marks the *file* `opaque:<reason>`: `inline fun`, `const val`,
`@Module` / `@Provides` / `@Inject`, `Class.forName` / `::class.java`, a file
under a generated or KSP root, a file that fails to tokenize or read. An
opaque file participates in the graph normally as a *dependency*; a *change to
it* emits `ESCALATE:<file>|<reason>|<runner set>` and selects every id of the
runners bound to its module at d0. The scanner runs over main and test roots.
Each opaque reason has a fixture in `engine/testdata/opaque/` and a test that
disables the branch and observes a narrow selection.

**Test-side closure.** A unit is selected at d1 with reason `test-dep <file>`
when a changed file is in the forward closure of the unit's own test file:
imports, abstract-base inheritance, test resources read by literal path, and
the `reads` globs of any helper in the closure. A change to
`ComposeScreenTest.kt` selects its 106 dependants and a change to
`robolectric.properties` every Robolectric class, without a second model.

**Symbol narrowing (opt-in).** `symbol_scanners: [android-res]` indexes
`R.string.<key>`, `stringResource(R.string.<key>)` and `"<key>".localized()`
sites per Kotlin file (639 + 406 sites under `ui/` today) and, for a changed
`res/values*/{strings,plurals}.xml`, diffs the before blob (`HEAD:<path>` for
a `TASK:` row, the parent of the first `(t<id>)` commit for a `COMMITTED:`
row) against the working tree to list changed keys; an axis hit or the
`values/**` rule is then narrowed to members whose closure names a changed
key; with no before blob the whole file's key set is used. `explain` prints
the key list.

**Facet reason on every row (n004).** Each selected variant row prints the
facet value that placed it (`axis(matrix.locale=ru)`) or `@*` for an edge,
dependency, rule or test-dep hit, so a reader's first question about a sharp
selection — what it left out and why — is answered on the line. Reasons, in
full: `edge(annotation|declared|observed)`, `dep <a> <- <b>`, `rule <name>`,
`axis(<axis>.<facet>=<v>)[keys] <- <path>`, `test-dep <file>`,
`reads(<helper>) <- <path>`, `area(<name>) <- <path>`, `scope(<glob>) <-
<path>`, `trigger(<glob>) <- <path>`, `stale-evidence <source>`, and the
`ESCALATE:` line. Cut knobs: `--max-distance`, `--budget-s`, `--kind`,
`--resource-filter`, `--suite-budget`, `--suites`, `--axis <axis>.<facet>=<v>`,
`--format lines|json|tokens`.

Granularity stays file-level for the change surface: a change anywhere in
`ScreenFixtures.kt` is a change to every member (d0 for all 297 variants) and,
through the test-side closure, to its 90 importers — the fail-safe answer the
design record gives for any test-source change until hunk-level attribution
exists (open question below).
<!-- /section: selection -->

<!-- section: runner_contract [dimensions: component_runner_contract, component_reference_runners, assumption_gate_exit_contract_reused, assumption_batch_per_unit_timing_reportable] -->
## Runner Contract

```
describe   → contract:1 unit:file|class|method|variant|suite axis:<name>? batch:true|false needs:[…]
             group_by:<key>? overhead_ms:<n>? token_format:<fmt>? filter_scope:run? full:true? artifact_glob:<glob>?
list       → TSV rows: <id>\t<kind>\t<lowering>[\t<artifact>]      ids may carry #<member> and @<variant>; lowering is opaque to the engine
run        → --manifest <f> --out <d>; manifest units: [{id, lowering, timeout_s, group}]; results.jsonl rows keyed by id;
             optional child rows {id, status, duration_ms, parent, evidence?} for a unit: suite runner;
             runner.json {status, exit, cause, units_expected, units_reported, overhead_ms, groups: [{group, overhead_ms, units_reported}]}
```

`list` is the universe: `check` fails `UNREGISTERED:<path>` for a test file no
runner lists and, for a runner whose filter restricts a whole run
(`filter_scope: run`), the selector treats "listed and not selected" as a
deliberate omission it must be able to justify — which is why the test-side
closure and `reads` exist. `group_by` (n004) names the key that makes several
selected ids one invocation for both batching and costing; `artifact_glob`
(n004) opts a runner into artifact reconciliation. Builtin runners:
`bash-file`, `pytest` (`testmap:batch no` honoured, the serial carve-out pinned
by extending `tests/test_serial_carveout_doc_drift.sh`), `go-test`,
`gradle-class` (consuming `<lowering>` verbatim as `--tests`, one invocation
per `group_by` group, inverting JUnit `classname`+`name` through the list
table — n004's method mode is this builtin with `unit: method` and `group_by:
class`), `suite` (any command; child rows from a `children:` post-processor),
`device` (allocator handle), `engine-test` (`go-test` over `engine/`). A
project script of the same name shadows a builtin. Exit mapping to the
verifier contract is n003's table (0→0, 1→1, 2→2 skip, 75→3 after in-engine
deferral, 64/absent→3); admission refusal and a missing engine never become a
skip.
<!-- /section: runner_contract -->

<!-- section: gates [dimensions: component_gates, requirements_gate_enforcement] -->
## Gates and Admission

The three gate entries are n003's (`testmap_fresh` procedure, no `unlocks`;
`testmap_check` machine, `max_retries: 0`, `timeout_seconds: 120`, `unlocks:
[testmap_run]`; `testmap_run` machine, `blocks_dependents: true`,
`max_retries: 1`, `timeout_seconds: 1800`), registered in
`gates_reference.yaml` and synced to `gates.yaml`, with the two bash
verifiers on the `tests_pass` template. `testmap_check` fails `STALE_PATH`
rows on its own and, past bootstrap, `UNSTAMPED` under `require_stamp` and
the structural rows under `--strict` (`UNCOVERED_VALUE`, `UNMAPPED_ARTIFACT`,
`UNANNOTATED_MEMBER`, `DEAD_MEMBER`, `UNKNOWN_VARIANT`, `DEAD_AXIS_SOURCE`,
`UNREGISTERED`).

One addition (n005) governs *when a project turns `testmap_run` on*:

```yaml
# aitestmap/config.yaml
run_gate_admission:
  min_scored_full_runs: 30          # rows in costs/predictions.yaml
  max_false_negatives: 0            # over those rows
  require_opaque_proofs: true       # engine self-check: every opaque branch has a red-proof fixture
  approved_by: {who: <email>, at: 2026-10-01, statement: aidocs/testing/change-aware-verification.md#what-this-cannot-do}
```

`ait testmap readiness` prints `READINESS:<criterion>|<met|unmet>|<value>` per
line and `READINESS_DECISION:ADMISSIBLE|NOT_YET`, never a pass/fail exit. The
engine never enables a gate. For thinking_app the intended state is:
`testmap_check` and `testmap_fresh` from bootstrap; `tests_pass` (full
`verify-active`) unchanged as the completion gate; `testmap_run` added only
when readiness is admissible, and even then beside `tests_pass`, not instead
of it — t388's three criteria as data.
<!-- /section: gates -->

<!-- section: go_engine [dimensions: component_go_engine, component_engine_binary, assumption_engine_latency_targets, assumption_go_toolchain_available, assumption_go_toolchain_ci_and_dev_only] -->
## The Go Engine: Why, and What It Must Cost

Unchanged from n003 in rationale: the engine's latency is paid at every gate
and commit step; a pure-Python parse of ~720 units and ~2,500–3,000 edges is
hundreds of milliseconds before any walk; a real concurrent scheduler with
cross-process locks is something bash cannot do well. Targets, pinned by
`go test -bench` on two golden registries — the aitasks shape and a
thinking_app shape (49 members × 10 matrices ≈ 300 variants, ~370 JVM
classes, ~900 Kotlin files) — with a 2× regression failing `engine-check.yml`,
validated before the gates are enabled:

| verb | target | what dominates |
|---|---|---|
| `select` (aitasks, with stale marks) | < 200 ms | YAML load + walk + digest of covered sources of selected units |
| `select` (thinking_app shape, axis expansion) | < 250 ms | + facet join over ≤10 values per member; no runner exec |
| `select` cold | < 1.5 s | ~270 files regex-scanned, blob-hashed, cached |
| `scan` | < 300 ms | ~720 file reads + comment parse over a pool; plus `list` per runner |
| `check` | < 300 ms | merged-table rules + `list` per runner + variant/artifact reconciliation |
| `stale --task` | < 300 ms | digests of the task's sources + one `ls-tree` per distinct evidence sha |
| `stale --all` | < 2 s | same, whole registry |

The n004 cell-table target (2,500 rows < 400 ms) has no referent in the merged
design; the variant universe is 49 member rows with value lists. Pools capped
at 8. CLI verbs: `scan | check | select | schedule | run | stale | verify |
annotate | score | attribute | declare | explain | costs | areas | axes |
classify | readiness | runner | version`; fixed-prefix `KEY:value` lines,
`--json`, per-verb exits `0/1/2/3/64`, `WROTE:<path>` per mutated file. Go ≥
1.26 in release CI through the new `engine` job's `setup-go` (`release.yml`
has no Go step today; `hugo.yml`'s is at `website/go.mod`'s 1.25.7) and on
framework developers' machines; target-project users never compile.
<!-- /section: go_engine -->

<!-- section: components [dimensions: component_*] -->
## Components

*(inherited from n003)* means unchanged in substance; *(inherited from n005)*
or *(inherited from n004)* names the explorer whose design was taken;
*(merged from n004 and n005)* means both contributed mechanisms as described;
*(new: introduced to bridge n004 and n005)* is a component neither had.

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(inherited from n005; n004's `internal/home` dropped)*

`engine/cmd/ait-testmap` with
`internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}`;
Go 1.26, pinned toolchain, `CGO_ENABLED=0`, `-trimpath -buildvcs=false
-ldflags "-s -w -X …"`; `gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`,
`golang.org/x/sync`; stdlib `flag`, `syscall.Flock`, `os/exec` git. Verbs as
listed above. Never writes `aitasks/`, `aiplans/`, `.aitask-data/` or a gate
ledger; never invokes `aitask_*.sh`; never needs its own install root. Tests
against fixture repos in `t.TempDir()`, including `testdata/opaque/`.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary: identity, output contract, budget *(inherited from n005)*

Embeds `version`, `commit`, `contract`; `version --json` prints them plus
`ENGINE:<resolved path>`; `CONTRACT_MISMATCH:` on registry files from a newer
contract (contract 1 includes `axes.yaml`, the id grammar and the `artifact`
column). Budget pinned by `go test -bench` on the two golden registries with
the 2× rule; pools capped at 8.
<!-- /section: component_engine_binary -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited from n005)*

`.aitask-scripts/lib/aitasks_home.sh`: `AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"`,
`aitasks_engine_dir <version|dev>`, `$AITASKS_HOME/.home.lock`. Sourced by the
shim, `install_engine_binary`, `aitask_engine.sh` and the verifiers; no
fallback to `~/.aitask/`. `ait setup` creates `$AITASKS_HOME/engine/` (0755)
and prints `AITASKS_HOME:<path>`. `tests/test_aitasks_home.sh`: default,
override, and a grep over the files this feature adds that fails on
`~/.aitask/`.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home: report and migration verb *(inherited from n004, made explicit and deferred; known set corrected)*

`ait engine home` in `aitask_engine.sh`: prints `HOME_ROOT:`, `HOME_LEGACY:`
with the tenants found, `HOME_SYMLINK:`, `HOME_NEXT:`. `ait engine home
--migrate`: n004's algorithm under `flock $AITASKS_HOME/.home.lock` —
refusals `no-legacy-root` / `already-migrated` / `foreign-symlink:<target>` /
`cross-device` / `unknown-entry:<name>`; known set `{venv, pypy_venv, python,
bin, uv, dev_tier, update_check, engine}`; per-entry `mv`; `rmdir ~/.aitask`;
`ln -s $AITASKS_HOME ~/.aitask`; `HOME_MIGRATED:<n>` / `HOME_SKIPPED:<reason>`.
`--no-home-migration` / `AIT_HOME_MIGRATE=0` are the names reserved for the
day `ait setup` migrates by default; in this release `ait setup` only prints
`HOME_LEGACY:<path>|run 'ait engine home --migrate'`. Tests
(`tests/test_aitasks_home.sh`, extended): fresh install; migration from a
populated legacy root with a working venv and PyPy venv afterwards; idempotent
re-run; hostile pre-existing symlink; cross-device refusal; `AITASKS_HOME`
override. Doc: a home paragraph in `packaging_strategy.md`; the 18 doc files
naming `~/.aitask` are updated by the follow-up that flips the default, when
the statement becomes current. Tradeoffs: `tradeoff_home_migration_window`
(the `rmdir`→`ln -s` window and the field blast radius) and
`tradeoff_split_home_rejected` (as the end state), below.
<!-- /section: component_framework_home -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited from n005)*

`engine/build.sh`; the `engine` job in `release.yml`; `engine-check.yml`;
`lib/platform_detect.sh`; the shim's handshake (`AIT_TESTMAP_BIN` >
`AIT_ENGINE=dev` at `$AITASKS_HOME/engine/dev/` requiring `<V>-dev+<sha>` >
`$AITASKS_HOME/engine/v<V>/` requiring `== VERSION` > `ENGINE_MISSING:<path>`
exit 3). Tests `test_testmap_shim.sh` (extended with an `AITASKS_HOME` host),
`test_platform_detect.sh`, `test_aitasks_home.sh`. Docs name
`~/.aitasks/engine/`. `release-packaging.yml` and `nfpm.yaml` untouched.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade, developer regeneration *(merged from n004 and n005)*

`install_engine_binary()` in `aitask_setup.sh` (reached by `ait setup` and by
`ait upgrade` through `install.sh --source-only`), beside `install_global_shim`:
uname mapping; `.sha256` short-circuit; `--local-engine` > exact-version asset
> `--engine-from-source` > `ENGINE_MISSING` warning; checksum; atomic install
to `$AITASKS_HOME/engine/v<V>/`; `version --json` must echo `<V>`; `.dev`
never overwritten without `--force-engine`; `--no-testmap` /
`AIT_TESTMAP_FETCH=0`; `.aitask-testmap/` gitignored. `aitask_engine.sh`:
`build` (dev slot), `test`, `cross`, `prune` (`$AITASKS_HOME/engine/v*/`
against `projects.yaml`, never automatic in upgrade), `home [--migrate]`
(n004). `tests/test_install_engine_binary.sh` through a real `install.sh --dir
--local-engine` asserting the `$AITASKS_HOME` path.
<!-- /section: component_engine_packaging -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(merged from n004 and n005)*

`internal/registry`: merges `registry/*.yaml` and `axes.yaml` into six tables
(edges, scopes, areas, rules, waivers, axes); parses
`<path>[#<member>][@<variant>]`; reads each member's `variants:` list from
`_scanned.yaml` (written by `scan --apply` from runner `list`); `owns:`
routing; write routing; deterministic writes; check rules incl. `STALE_PATH`,
`UNSTAMPED`, `DEAD_SCOPE`, `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`,
`UNCOVERED_VALUE` (n004), `UNANNOTATED_MEMBER`, `DEAD_MEMBER`, `UNREGISTERED`,
`UNMAPPED_ARTIFACT` (n004's `UNMAPPED_CELL`, re-sited), `KIND_MISMATCH`,
`CONTRACT_MISMATCH`; observed axis sources merged at load may only widen a
facet value's globs (n004). Golden tests pin the merge rule and the id
grammar.
<!-- /section: component_registry_loader -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited from n005; n004's `testmap:axis` and `--axis` bridged)*

`internal/axes`: loads `axes.yaml` `{axes: {<name>: {facets[], values{v: {facet: fv}}, sources{facet: {fv: [globs]}}}}}`;
`FacetOf`, `VariantsWith`, `SourcesHit(changedPaths) → [(axis, facet, fv, path)]`
via `doublestar.Match`; validates runner `describe` `axis:` against declared
axes and `list` variants against value sets; joins `testmap:axis` coordinates
on plain units. Used by the selector (rules 1–7), the runner codec
(`token_format` expansion: `{variant}`, `{member}`, `{path}`, `{facet.<name>}`),
cost and evidence (per-variant ids), `check`, and the `--axis` knob. A project
with no `axes.yaml` has an empty table and every code path is a no-op.
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited from n004, re-sited onto the variant-axes table)*

`ait testmap axes --list | --check | --explain <path>`: prints every declared
axis with its facets, values and value-count from `list`; runs the axis check
rules; and, for one file, prints `AXIS:<axis>.<facet>|<value or ->|<why>` per
facet — which glob matched, or that no source is declared — so a maintainer
can see where a file lands before anything is trusted. n004's
`resolve(changeSet) → set | ANY` is the `SourcesHit` join read the other way;
`ANY` is printed as `-` and means "no axis hit; reaches units only through
edges and dependencies".
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited from n004, re-sited onto the runner `list` verb)*

There is no `aitestmap/cells/` directory and no `_cells.yaml`: the project's
runner `list` is the enumeration surface, and its output is persisted as the
`variants:` field on each member row of `_scanned.yaml` by `scan --apply`, so
`select` never execs a plugin. What n004's enumeration bought — two-way
reconciliation — is kept: `UNCOVERED_VALUE:<axis>|<value>` (a declared value
no runner lists) and `UNMAPPED_ARTIFACT:<path>|<runner>` (a file matching a
runner's `artifact_glob:` that no listed id's `artifact` column claims). Both
fail `check --strict` after bootstrap. For thinking_app the runner's `list`
reads the two membership manifests and `matrix_classes` — every fact from a
file the project already guards; a golden landing in the tree with no manifest
line is `UNMAPPED_ARTIFACT` the same day.
<!-- /section: component_cell_enumeration -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(merged from n004 and n005)*

`internal/annot`: grammar v3 — `testmap:unit <Member>` opens a block that owns
every following `testmap:` line until the next `testmap:unit` or end of file
(a file-level block precedes the first unit); keys `kind`, `covers <path>
@<date>/<blob10>`, `area`, `scope`, `trigger`, `reads <glob>` (helper files
only), `axis <axis>.<facet>=<value>` (n004; a plain unit's coordinate),
`reviewed`, `runner`, `needs`, `batch`; per comment leader (`#`, `//`, `--`)
and Python docstrings; unknown keys refused with a line number; block
ownership by position only; the line-targeted rewriter keyed by (file, line,
current text) with `REWRITE_CONFLICT:`; `annotate --from-body` seeds `covers`
for a member from the Kotlin scanner's symbol resolution of the block's own
lines.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(inherited from n005)*

`internal/deps`: bash, python, go (`go list -deps -json`), kotlin (closed
construct list; `opaque:<reason>` otherwise; main and test roots; Gradle
module graph), plus plugins under `aitestmap/scanners/` speaking `{"file",
"deps", "opaque"?, "reads"?}` per line; the opt-in `android-res` symbol
scanner; forward deps cached per source blob under the XDG cache and inverted
in memory. n004's `reach:` (a second consumer of the inverted graph) is not
carried: the same walk from an annotated member edge gives the same answer
with a stamp on it.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(merged from n004 and n005)*

`internal/selectr` + `internal/changesurface`: intake; refusal on `UNKNOWN:`;
the graded walk with rules; variant expansion and axis join (symbol-narrowed
when enabled; `testmap:axis` units included); test-dep at d1 through the
test-side closure and helper `reads`; `ESCALATE:` on a changed opaque file;
scoped join; kind-then-cost ranking per variant; invocation-group formation by
the runner's `group_by` with group cost `overhead.p95 + Σ unit.p95` (n004);
stale marks from the per-variant evidence join; `--include-stale`; suite
budget over broad rows and groups with `DEFERRED:`; cut knobs incl. `--axis`
(n004); `--format lines|json|tokens`; the prediction record with per-variant
rows, facet reasons and groups; `explain` with key lists, closure paths and
facet coordinates.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(merged from n004 and n005)*

`internal/runner`: `describe` fields (`unit`, `axis`, `batch`, `needs`,
`group_by` (n004), `token_format`, `filter_scope`, `full`, `children`,
`artifact_glob` (n004)); `list` TSV codec with the optional `artifact` column;
manifest with lowerings and groups; `results.jsonl` with child rows;
`runner.json` with per-group overhead rows; inversion of batch reports to ids
with "no registered id" and "zero reported with some expected" as mechanism
failures; bindings and per-test override; `builtin:` with `command:`/`cwd:`;
shadow-by-name; batching by (runner, group, resource set, batch flag);
per-unit timeouts; exit contract `0/1/2/75/64`.
<!-- /section: component_runner_contract -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited from n003; ordering refinement)*

`internal/sched` as in n003: mutex / semaphore / admission / allocator; host /
worktree / run scopes; `flock(2)` slots in canonical order; admission 75
deferral to the run deadline; allocator handle injection with signal-safe
release; errgroup waves; `broad_after_unit`; `concurrency: serial|parallel`
(serial at bootstrap); the schedule report. Variants of one runner and one
resource set batch into one invocation per `group_by` group, so a thinking_app
selection is one Gradle run holding one heavy-run slot; within a wave,
invocations holding an admission resource are ordered last (the ordering half
of n004's wave placement).
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(merged from n004 and n005)*

`internal/cost`: Welford per (id, host class) with P² p95 and last, where an
id may be a variant; `.aitask-testmap/ledger.jsonl` `{run_id, id, status,
duration_ms, head_sha}` plus per-invocation rows `{run_id, group, overhead_ms,
units_reported}` (n004: promoted to a first-class input); `costs --update`
folds both into `costs/<hostclass>.yaml` and truncates; `last_pass` and flake
rate per id; the estimate for a selection is Σ over groups of `overhead.p95 +
Σ unit.p95`, reported per kind; `costs/predictions.yaml` (200-row cap) written
by the automatic score.
<!-- /section: component_cost_ledger -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited from n005: per variant)*

`internal/stale` + `internal/gitx`: for each mismatched edge, candidate shas
per reached variant from ledger and committed costs (any host class); drop
`cause` invocations and ids over `flake_threshold`; keep ancestors of HEAD
(memoised); one `git ls-tree <sha> -- <paths…>` per distinct sha under a pool
of four; `EVIDENCED` only when every reached variant is covered; never
rewrites; `stale --confirm-evidenced` is the explicit re-stamp.
<!-- /section: component_evidence_join -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(merged from n004 and n005)*

`internal/feedback`: `score --run --prediction`; automatic invocation after
`run --all` and after a `full: true` suite run, printing `PREDICTION_SCORED`,
`PREDICTION_FALSE_NEGATIVES`, `PREDICTION_MISSED` and appending to
`costs/predictions.yaml`; `attribute` with `missing-edge` / `test-wrong` /
`source-wrong` (units and members), `missing-axis-source` (a facet value gains
a source glob in `observed.yaml`, merged at load, widen only — n004's rule),
`missing-trigger` / `area-too-narrow`; `readiness` against
`run_gate_admission`.
<!-- /section: component_feedback_tools -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(merged from n004 and n005)*

`testmap_fresh`, `testmap_check`, `testmap_run` in `gates_reference.yaml`
synced to `gates.yaml`; the two verifiers on the `tests_pass` template with
the exit mapping table; engine absent → 3. `testmap_check` additionally fails
the structural rows under `--strict` (n004's `UNMAPPED_CELL` rule as
`UNMAPPED_ARTIFACT`). `run_gate_admission` in `config.yaml` and `ait testmap
readiness` (n005); the engine never edits a gate set.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(merged from n004 and n005)*

`aitask-testmap`: annotate a file, a `testmap:unit` member (`--from-body` to
seed) or a coordinate (`testmap:axis`); declare an axis source in `axes.yaml`
when a new locale or matrix arrives (the repo's "adding a language" procedure
gains one line); `reads` on a new tree-scanning helper; `axes --explain` before
trusting a membership; attribute before the gate; verify after editing an
annotation; `classify --suggest` (incl. the grid heuristic); `select --format
tokens` piped into the project's render loop. `aitask-gate-testmap-fresh`: the
procedure gate, naming unevidenced matrices per `STALE` row and resolving
`check`'s structural rows by editing `axes.yaml`, the runner's `list` or the
member block — never waved through. Claude Code first, then ported.
<!-- /section: component_skill -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(merged from n004 and n005)*

`bash-file`, `pytest` (`testmap:batch no` honoured), `go-test`, `gradle-class`
(`--tests <lowering>` batch, one invocation per `group_by` group, JUnit
inversion, zero-match trap — n004's method mode), `suite` (any command; child
rows from a `children:` post-processor), `device`; `command:`/`cwd:`
overrides; shadow-by-name; `engine-test` over `engine/`. thinking_app's
`tools/verification/testmap_runner.sh` is a project runner, not a builtin.
<!-- /section: component_reference_runners -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(inherited from n005: member scope)*

The per-edge stamp written only by `verify`, `annotate`, `stale --confirm*`,
scoped to the member block; `last_pass` per id; `verify` and `verify
--all-evidenced`; `bootstrap_until`, `require_stamp`, `flake_threshold`; the
`testmap_fresh` procedure gate before the change summary; not a git hook, not
a Claude Code hook. Variants carry no stamp of their own — the member's edges
are the claim, the variant's `last_pass` is the evidence.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(inherited from n005; structural summary line)*

`stale --task --changes - | --all` with n003's line classes and encoding;
`STALE` rows carry `|<unevidenced variants>`; `--strict` on `STALE_PATH`;
rename hints and culprits from `git log -M`; `--confirm`, `--confirm-source`,
`--confirm-evidenced`, `--retarget`; `stale --all` adds one
`CHECK_STRUCTURAL:<n>` summary line so a repo-wide sweep sees axis, member and
artifact rot that `check` owns.
<!-- /section: component_staleness_tool -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(merged from n004 and n005)*

`areas.yaml`; `_scoped.yaml` rows gain `reads_from` (n005); `owns:` by area
name; the d1 join; suite budget with `DEFERRED:`; `DEAD_SCOPE`,
`KIND_MISMATCH`; `ait testmap areas` (`--import-codemap`, `--list`,
`--check`); `classify --suggest` with the `reads`-helper heuristic (n005) and
the grid heuristic proposing a variant axis (n004); `missing-trigger` /
`area-too-narrow`.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited from n005; variant boundary stated)*

`broad_after_unit`, `device_policy: filter_by_resource`, evidence-based
`STALE_AREA`, opt-in `REVIEW_DUE`, `attribute` widening, fixture pins. A suite
row marked `full: true` with a `children:` post-processor anchors registered
ids on every run. Variant-bearing units are unit kind, never area-scoped, and
ride the unit wave.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Inherited unchanged from n003 (both explorers agree):

- **Existing project locks and allocators can be wrapped as resources**
  (`assumption_existing_locks_wrappable`) — thinking_app's heavy-run lock
  (exit 75 admission in `heavy-run-lock.sh`) and emulator allocator are
  exec'd, never reimplemented; the runner script goes through
  `screenshot-tests.sh unit-tests`, which reserves the slot itself.
- **The change-surface script is the intake** (`assumption_change_surface_is_intake`)
  — lines only, `UNKNOWN:` refuses; the before blob a symbol scanner needs is
  resolved from the same rows and is simply absent without history.
- **`testmap:` does not collide with prose** (`assumption_testmap_token_no_collision`).
- **The gate exit contract is reused** through two verifier shells
  (`assumption_gate_exit_contract_reused`); `75` stays inside the engine.
- **Go ≥ 1.26 in release CI via a new `setup-go` step and on developer
  machines** (`assumption_go_toolchain_available`), **build-time only**
  (`assumption_go_toolchain_ci_and_dev_only`).
- **Release assets are reachable from `ait setup` / `ait upgrade`**
  (`assumption_release_asset_reachable`); **air-gapped hosts have documented
  fallbacks** (`assumption_release_assets_reachable`) — the pre-seeded
  directory is `$AITASKS_HOME/engine/`.
- **Git history is the evidence clock, not the staleness key**
  (`assumption_git_history_is_freshness_clock`); **the blob digest is the key**
  (`assumption_blob_digest_is_staleness_key`).
- **Broad tests are area-scoped with evidence-based drift**
  (`assumption_broad_tests_area_scoped`).
- **linux/darwin × amd64/arm64 suffices** (`assumption_platform_matrix_sufficient`).
- **One engine per framework version** (`assumption_one_engine_per_framework_version`)
  — the versioned directory is `$AITASKS_HOME/engine/v<VERSION>/`.

Inherited and revised:

- **Static file-level facts are enough for v1** (`assumption_static_granularity_v1`)
  — n005's revision: file-level remains the default; two narrower
  granularities are in use rather than reserved — member units (position-scoped
  blocks, no language parsing) and the edge `symbols` slot through
  `android-res`; no scanner produces symbol-level coverage of *code*. n004's
  exception ("product spaces are handled without symbol analysis because the
  coordinate comes from a plugin") is subsumed: the coordinate comes from the
  runner's `list`.
- **Runners can report per-unit timing inside a batch**
  (`assumption_batch_per_unit_timing_reportable`) — and can invert a report
  row to a registered id (n005); and the same JUnit XML reports each `@Test`
  method with its own duration, which is what makes a variant's marginal cost
  measurable separately from its class's boot (n004).
- **A passing run anchors edges** (`assumption_passing_run_anchors_edges`) —
  per variant; a unit with variants is `EVIDENCED` only when every reached
  variant has a qualifying pass (n005).
- **Areas, scopes and triggers express a broad test's blast radius**
  (`assumption_areas_express_suite_blast_radius`) — extended by helper `reads`
  globs inherited through the test-file closure (n005).
- **Target repos accept an `aitestmap/` root** (`assumption_target_repos_accept_aitestmap_root`)
  — plus an optional `axes.yaml`; runner scripts and axes are both optional
  (a repo with no product space declares none and gets exactly n003's
  behaviour); thinking_app commits one runner script because its lowering is
  its harness's own routing.
- **The engine latency targets** (`assumption_engine_latency_targets`) — the
  aitasks table plus a thinking_app-shaped fixture (49 members × 10 matrices,
  ~370 classes, ~900 Kotlin files) at `select` < 250 ms warm; n004's
  2,500-row cell target has no referent here.

New in n005, kept:

- **A runner's `list` is the complete universe its filter can address**
  (`assumption_variant_universe_from_runner_list`) — for thinking_app, the two
  membership manifests (297 goldens over 10 matrices) plus every other class
  under `app/src/test/java`; an unlisted class is `UNREGISTERED`, never
  silently unfiltered. This is what makes a whole-run `--tests` filter sound:
  nothing is omitted by accident, only by a selection the engine printed.
- **Axis sources are declarable as globs** (`assumption_axis_sources_declarable`)
  — the locale facet's sources are `values-<q>/**`, `raw-<q>/**` and the
  per-family fonts; sources every locale reads are ordinary edges or the one
  `values/**` rule; direction and geometry are test-side constants reached
  through the test-dep closure.
- **The Kotlin scanner's opaque list is sufficient** (`assumption_kotlin_scanner_fail_closed`)
  — every construct known to defeat a static import graph is
  pattern-detectable and escalates; measured on thinking_app, 42 main files
  declare `const val`/`inline fun` and 63 carry DI annotations, so escalation
  is frequent by design; the residual risk is a construct not on the list,
  which is why each branch has a red-proof fixture and the prediction ledger
  counts what the list missed.
- **The two per-user roots coexist** (`assumption_legacy_user_root_coexists`)
  — for this release: `~/.aitasks/` (engine) and `~/.aitask/` (Python tenants)
  share nothing; the migration verb exists but is not run by default.

New in n004, kept and re-sited:

- **Axis membership is declarable by the suite's owners**
  (`assumption_axis_membership_declarable`) — the general claim of which
  `assumption_axis_sources_declarable` is the thinking_app instance:
  `res/values-ar/**` and `font/cairo_*.ttf` *are* the Arabic matrices' inputs;
  `.claude/` vs `.opencode/` vs `.agents/` *are* aitasks' agent facet. A
  source matching no axis source is not an axis hit and reaches units only
  through edges and dependencies, which select every variant — the fail-safe
  direction n004 called `ANY`. Falsifier: a project whose membership is
  genuinely dynamic (a runtime flag choosing a locale), for which the answer
  is to declare no sources on that facet.
- **The variant universe is enumerable from the project's own routing
  statement** (`assumption_cells_enumerable_by_plugin`) — re-sited: the
  enumerator is the runner's `list` verb (thinking_app: `matrix_classes()`
  crossed with the membership manifests; aitasks: the rendered `tests/golden/`
  tree), not a second plugin directory; the framework never infers a variant.
  Falsifier: a repo whose test methods are only knowable by running the build,
  for which `list` may exec the build's own list task — off the hot path, since
  only `scan` and `check` call it.
- **Every consumer of the legacy `~/.aitask` tree keeps resolving once it is a
  symlink** (`assumption_home_symlink_compatibility`) — the migration verb's
  precondition, checked: 8 framework files / 35 references (21 in
  `aitask_setup.sh`, 6 in `python_resolve.sh`, 3 in `aitask_path.sh`), 20 test
  files, 18 doc files; no `==`/`!=`/`-ef` comparison and no `realpath` /
  `samefile` on the home path; venv shebangs, wrappers and `pyvenv.cfg`
  dereference or are informational. Falsifier: a comparison introduced later
  — which `tests/test_aitasks_home.sh`'s post-migration venv exercise would
  surface.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Advantages:

- **Computed, explained, scored selection** (`tradeoff_computed_vs_prose`) —
  thinking_app's prose rule ("a localized screen change may use `preview` or
  the RTL tier; a shared component or tooling change must run the full gate")
  becomes an axis join, an import fan-out and an `ESCALATE:` line, each printed
  with the path that caused it and the facet value that placed each variant.
- **Speed makes the machinery usable per task** (`tradeoff_engine_speed_enables_per_task_use`)
  — sub-second on aitasks, sub-250 ms with axis expansion on thinking_app; the
  facet join is a glob match per changed file per facet and a set test per
  member, and `select` never execs a runner.
- **A real scheduler** (`tradeoff_real_scheduler`) — a variant batch is one
  Gradle invocation holding one heavy-run slot; cheap invocations report first.
- **Architecture-independent packages stay that way** (`tradeoff_noarch_packages_preserved`).

Disadvantages:

- **Two per-user roots during the transition** (`tradeoff_two_user_roots`) —
  `~/.aitask/` (venv, pypy_venv, python, bin, uv) and `~/.aitasks/` (engine)
  side by side until `ait engine home --migrate` is run; a user who deletes one
  to reset the framework removes half of it. Mitigations: one variable with one
  owner, `ait setup` printing both roots and the `HOME_LEGACY:` hint,
  `ENGINE_MISSING` naming the exact path, `ait engine home` reporting the
  state, and the test that fails if any file of this feature names
  `~/.aitask/`.
- **The migration's window and field blast radius** (`tradeoff_home_migration_window`)
  — when run, `--migrate` has a sub-millisecond window between `rmdir
  ~/.aitask` and `ln -s` during which a concurrent process hardcoding the
  legacy path sees `ENOENT`; narrowed by the flock and by symlinking
  immediately, not eliminated. And its refusal cases are the ones a designer
  does not see on their own host: n004's known-entry set lacked `pypy_venv`,
  which this host carries. Both are why the verb is explicit in this release
  and why flipping the default is admitted only through the real-install test.
- **A split home was rejected as the end state, accepted as the transition**
  (`tradeoff_split_home_rejected`) — n004 is right that two dot-directories
  one character apart holding halves of one install is a permanent
  explanation tax on `ait setup --repair`, `ait engine prune`, backup advice
  and every doc page; n005 is right that this feature should not pay the
  migration's field cost. The resolution pays neither forever: the migration
  is designed, shipped and testable now, and becomes the default in a named
  follow-up.
- **Axis projection is coarse by default** (`tradeoff_axis_projection_coarseness`)
  — a one-key edit to `values-ru/strings.xml` selects every enrolled screen on
  both ru matrices (about 65 variants) rather than the two screens naming the
  key; sound, and 2 of 10 matrices rather than all; narrowed by `android-res`
  and cheap in practice because `--format tokens` drives `preview`.
- **Axes are a third authoring surface** (`tradeoff_axis_declaration_burden`)
  — thinking_app must declare ten matrix values with three facets, four
  locale source-glob sets, one `values/**` rule, one runner script and one
  `testmap:axis` line per non-capturing coordinate test; a wrong declaration
  gives confidently wrong selection. Mitigated by `DEAD_AXIS_SOURCE`,
  `UNKNOWN_VARIANT`, `UNCOVERED_VALUE`, `axes --explain <path>`, and by an
  undeclared source reaching every variant.
- **The committed universe is small, and `list` runs on `scan`/`check`**
  (`tradeoff_cell_table_size`) — instead of n004's ~2,500 generated cell rows,
  `_scanned.yaml` carries 49 member rows with a `variants:` list; the price is
  that `scan` and `check` exec each runner's `list` (thinking_app: a bash
  script reading two manifests, milliseconds), and that a matrix added to the
  manifests is invisible to `select` until the next `scan --apply` — which
  `check` reports as `UNKNOWN_VARIANT`/`UNCOVERED_VALUE` drift.
- **Registry directory complexity** (`tradeoff_registry_directory_complexity`)
  — six tables, two generated files, an id grammar with `#` and `@`
  fragments, and an `artifact` column; the axis table is empty for four of the
  five target repos and every axis code path is a no-op then.
- **Fail-closed bootstrap cost** (`tradeoff_fail_closed_bootstrap_cost`) — a
  repo with axes additionally needs its runner's `list` green (no
  `UNKNOWN_VARIANT`) before the structural rules can fail `check`, and a repo
  whose completion gate is a full suite waits for `min_scored_full_runs`
  before `testmap_run` is admissible; the ledger fills itself from the full
  runs the repo already performs.
- **Static scanners overselect on hot files** (`tradeoff_static_scanner_overselection`)
  — a `ui/components/*` edit selects most screens on every matrix, which is
  the right answer and close to a full run; `ScreenFixtures.kt` reaches
  every member because a change surface is file-level; the symbol scanner, a
  project plugin and (later) hunk-level attribution are the narrowing tools.
- **Two toolchains** (`tradeoff_two_toolchains`), **a compiled component**
  (`tradeoff_compiled_component_cost`), **a self-downloaded asset in setup**
  (`tradeoff_setup_network_fetch`), **version skew on multi-project hosts**
  (`tradeoff_engine_version_skew`) — as in n003, with the slot under
  `$AITASKS_HOME/engine/`.
- **Stamp churn** (`tradeoff_stamp_churn`) — better than n003 for thinking_app:
  all 49 members' stamps live in `ScreenFixtures.kt`, so a hot-source
  confirmation is a one-file diff; variants carry no stamp.
- **Area and scope coarseness** (`tradeoff_area_glob_coarseness`,
  `tradeoff_broad_scope_coarseness`) — unchanged; `reads` globs are a third
  budget-exempt sharp edge beside triggers.

Risks:

- **Whole-run filter soundness** (`tradeoff_whole_run_filter_soundness`) —
  when a runner's filter restricts a whole run, every unselected class is
  silently not run, so a narrow selection is exactly as sound as the test-side
  closure, the `reads` globs and the opaque contract. Mitigations, each
  checkable: `list` enumerates the universe (`UNREGISTERED`), the scanner runs
  over the test root, `reads` keeps the 71 fence importers selected on any
  Kotlin change, opaque files escalate, every opaque branch has a red-proof
  fixture, `readiness` gates the run gate on scored history, and the project
  keeps its full suite as the completion gate regardless. This is the risk
  n004's cell selection would have carried unmitigated.
- **A facet join is sharper than a file edge** (`tradeoff_intersection_can_underselect`)
  — an axis-source hit selects only the variants carrying the facet value, so
  a wrong source glob (a font family assigned to the wrong locale) under-selects
  where a plain `covers` edge would have selected every variant. Structurally
  narrowed: under-selection needs an explicit, reviewable wrong glob, never an
  omission (an unmatched file reaches every variant); observed axis sources
  from `attribute` may only widen; `--axis` and `--format tokens` with
  `preview` are the reviewer's escape; and every row prints the facet value
  that placed it, so what a sharp selection excluded is visible.
- **Member annotation drift** (`tradeoff_member_annotation_drift`) — a
  `testmap:unit` block is keyed by name and the runner's `list` keys the same
  member by the manifest's `<Screen>_<matrix>.png`; a rename on one side
  orphans the other. `check` fails both directions (`UNANNOTATED_MEMBER`,
  `DEAD_MEMBER`) and `scan --apply` refuses rather than guesses; thinking_app's
  own manifest/`@Test` drift loop already fails the rename on its side.
- **Unattributed source edits** (`tradeoff_attribution_risk`) — narrowed
  further in a repo with a full completion gate: every miss is counted by the
  automatic score within one task.
- **Batch misreport** (`tradeoff_batch_misreport_risk`) — two more places to
  misreport: the JUnit → id inversion, and the zero-match trap at method
  granularity (a `--tests` filter matching nothing exits 0); a row inverting to
  no registered id and `units_reported == 0` with `units_expected > 0` are
  mechanism failures, `units_expected`/`units_reported` is per id, and no line
  from an invocation with a `cause` anchors.
- **Resource declarations are only as complete as declared**
  (`tradeoff_resource_declaration_completeness`), **flaky passes anchor**
  (`tradeoff_flaky_pass_anchors`, per id), **autonomous confirmation is weak**
  (`tradeoff_autonomous_confirmation_weak`, requiring every reached variant),
  **the handshake is strict** (`tradeoff_strict_version_handshake`), **an
  engine can be absent** (`tradeoff_engine_absent_on_host`), **evidence needs
  reachable history** (`tradeoff_evidence_requires_reachable_history`) — as in
  n003.
<!-- /section: tradeoffs -->

<!-- section: conflict_resolutions [dimensions: component_*, assumption_*, tradeoff_*] -->
## Conflict Resolutions

Each entry names the conflict, the strategy applied in the mandated priority
order (Adapter/Bridge > Assumption update > Component replacement), the
resolution, and the dimensions it changed.

### 1. Same role: `component_framework_home` (n004) vs `component_user_root` (n005)

- **Conflict.** Both own the per-user root. n004 migrates the legacy tree in
  `ait setup` with a resolver that falls back to `~/.aitask`; n005 adds a
  second root and never reads the legacy one. Taking n004 whole puts a
  field-wide migration inside a testing feature; taking n005 whole leaves a
  split home with no owner.
- **Strategy.** Adapter (split the role) plus assumption update.
- **Resolution.** `component_user_root` = the resolver library, the engine
  slot, no fallback (n005). `component_framework_home` = `ait engine home`
  (report) and `ait engine home --migrate` (n004's algorithm) with the known
  set corrected to include `pypy_venv`; `ait setup` prints `HOME_LEGACY:` and
  does not migrate; a named follow-up flips the default after the
  real-install test. `assumption_legacy_user_root_coexists` holds for this
  release; `assumption_home_symlink_compatibility` becomes the verb's
  precondition, verified (no equality compares; 8 code files / 35 refs).
- **Dimensions changed.** `component_user_root`, `component_framework_home`,
  `component_engine_packaging`, `requirements_user_root`,
  `requirements_framework_home_name`, `assumption_legacy_user_root_coexists`,
  `assumption_home_symlink_compatibility`, `tradeoff_two_user_roots`,
  `tradeoff_home_migration_window`, `tradeoff_split_home_rejected`.

### 2. Same role: `component_axes` + `component_cell_enumeration` (n004) vs `component_variant_axes` (n005)

- **Conflict.** Both model a product-shaped suite. n004: axes with member
  globs, cells enumerated by a plugin into a generated table, no stamps or
  evidence on cells. n005: member units with covers edges, variant axes with
  facets, the runner's `list` as the universe, per-variant evidence. They
  disagree on where the universe comes from, whether the suite is inside the
  freshness model, and whether filtering the run is sound.
- **Strategy.** Component replacement (n004's cell table by n005's runner-list
  universe) with three adapters bridging n004's contributions.
- **Resolution.** n005's model is the unit model. Adapters: (a) `scan --apply`
  persists each member's `variants:` list so `select` never execs a runner —
  the property n004's committed table bought; (b) `describe` gains
  `group_by:` and `artifact_glob:`, `list` an optional `artifact` column, and
  `check` gains `UNCOVERED_VALUE` and `UNMAPPED_ARTIFACT`; (c) `testmap:axis`
  on a plain unit and the `--axis` knob. `component_axes` keeps n004's
  resolver verbs (`axes --list/--check/--explain`) re-sited on the n005 table;
  `component_cell_enumeration` records the re-siting and the reconciliation
  rules. `assumption_cells_enumerable_by_plugin` is re-sited onto `list`.
- **Dimensions changed.** `component_variant_axes`, `component_axes`,
  `component_cell_enumeration`, `component_registry_loader`,
  `component_runner_contract`, `component_annotation_scanner`,
  `component_selector`, `component_reference_runners`,
  `assumption_cells_enumerable_by_plugin`,
  `assumption_variant_universe_from_runner_list`, `tradeoff_cell_table_size`.

### 3. Semantics: intersection across axes (n004) vs union across hits (n005)

- **Conflict.** n004: a cell is selected iff for every axis the axis is `ANY`
  or the cell's value is in the resolved set, applied per file and unioned
  across files. n005: an axis hit selects the variants carrying the facet
  value; other hits select every variant; hits union; "no intersection
  semantics".
- **Strategy.** Assumption update, by checking equivalence.
- **Resolution.** On every single-file row of n004's own worked table at most
  one axis is non-`ANY`, so n004's intersection reduces to n005's facet join;
  n004's per-file union *is* n005's union across hits; n004's `ANY` for an
  unmatched file is n005's "no axis hit → reached only through edges and
  dependencies → every variant". The merged rule is n005's, stated with
  n004's fail-safe wording, and the one real difference (a non-variant test
  belonging to a coordinate) is `testmap:axis`. `axes --explain` prints `-`
  where n004 printed `ANY`.
- **Dimensions changed.** `requirements_axis_product_selection`,
  `requirements_screen_locale_subdivision`,
  `assumption_axis_membership_declarable`,
  `assumption_axis_sources_declarable`, `component_selector`,
  `tradeoff_intersection_can_underselect`.

### 4. Screen coordinate: computed `reach:` (n004) vs annotated member edges (n005)

- **Conflict.** n004 derives a `screen` membership by walking the dependency
  graph from `ui/screens/{value}Screen.kt`; n005 annotates each member block
  with the composables it renders (seeded by `annotate --from-body`) and lets
  the Kotlin scanner supply d2.
- **Strategy.** Component replacement.
- **Resolution.** n005. The `ui/screens/` root does not exist (screens live
  under `ui/mvvm/<feature>/`); a computed reach is the same dependency fact
  without a stamp, evidence or review, and its `fanout_max` collapse is what
  `KIND_MISMATCH` and the budget already provide. `reach:` is not carried.
- **Dimensions changed.** `component_dependency_scanners`,
  `component_annotation_scanner`, `assumption_static_granularity_v1`.

### 5. Where structural rot is reported: `stale` (n004) vs `check` (n003/n005)

- **Conflict.** n004 prints `STALE_AXIS`, `UNMAPPED_CELL`, `UNCOVERED_VALUE`
  from `stale` and fails `stale --strict` on them; n003 keeps structural rules
  (`DEAD_SCOPE`, `KIND_MISMATCH`) in `check`.
- **Strategy.** Assumption update.
- **Resolution.** Structural rot (axis sources, members, variants, artifacts)
  is `check`'s; `stale` stays content and evidence; `stale --all` prints one
  `CHECK_STRUCTURAL:<n>` summary line; `--strict` applies to both verbs.
- **Dimensions changed.** `component_staleness_tool`,
  `component_registry_loader`, `component_gates`,
  `requirements_annotation_staleness`.

### 6. Evidence for the product suite: none (n004) vs per variant (n005)

- **Conflict.** n004 states cells carry no stamp and no `EVIDENCED` class;
  n005 stamps the member and anchors per variant.
- **Strategy.** Component replacement.
- **Resolution.** n005. An unstamped screen suite would leave the framework's
  main freshness mechanism inapplicable to the repo the mandate names, and a
  per-file `covers` on the abstract base would let a Hebrew pass re-stamp an
  Arabic claim. Variants themselves carry no stamp (the member's edges are
  the claim), which keeps n004's stamp-churn argument.
- **Dimensions changed.** `component_freshness`, `component_evidence_join`,
  `assumption_passing_run_anchors_edges`, `tradeoff_stamp_churn`,
  `tradeoff_autonomous_confirmation_weak`.

### 7. Cost of a multi-method selection: per-variant sum (n005) vs invocation group (n004)

- **Conflict.** n005 records per-invocation overhead rows but estimates a
  member as the sum of its selected variants' p95; n004 charges a group once
  and each further method its marginal mean.
- **Strategy.** Adapter.
- **Resolution.** `describe` gains `group_by:`; the selector forms groups; the
  ledger's invocation rows carry `group`; the estimate and the budget read
  `overhead.p95 + Σ unit.p95` per group.
- **Dimensions changed.** `component_cost_ledger`, `component_selector`,
  `component_runner_contract`, `requirements_cost_tracking`,
  `assumption_batch_per_unit_timing_reportable`.

### 8. Whole-run filter soundness: unaddressed (n004) vs modelled (n005)

- **Conflict.** n004's cell selection under Gradle `--tests` would silently
  drop every non-capturing class; n005 makes `list` the universe, models the
  test-side closure and `reads`, escalates on opaque files, and gates the run
  gate on `readiness`.
- **Strategy.** Component replacement (n005), with n004's zero-match trap
  kept.
- **Resolution.** n005's four mitigations plus `units_reported == 0 with
  units_expected > 0` as a mechanism failure. Measured cost recorded: 42 main
  files with `const val`/`inline fun` and 63 with DI annotations escalate —
  the project's own S1 contract.
- **Dimensions changed.** `component_dependency_scanners`,
  `component_selector`, `component_runner_contract`, `component_gates`,
  `assumption_kotlin_scanner_fail_closed`,
  `assumption_variant_universe_from_runner_list`,
  `tradeoff_whole_run_filter_soundness`, `tradeoff_batch_misreport_risk`.

### 9. Engine home resolver: `internal/home` (n004) vs none (n005)

- **Conflict.** n004 adds a Go package resolving the install root; n005 keeps
  the root in bash only.
- **Strategy.** Component replacement.
- **Resolution.** None in Go. The engine's state is repository-local and
  XDG-cached; the shim resolves the binary; `version --json` prints `ENGINE:`
  from the executable path; `prune` is bash.
- **Dimensions changed.** `component_go_engine`, `component_engine_binary`.

### 10. Wave placement of variant batches: conditional wave 1/2 (n004) vs unit wave (n005)

- **Conflict.** n004 moves cells to wave 2 when their groups contend for a
  declared resource; n005 keeps variants in the unit wave.
- **Strategy.** Assumption update.
- **Resolution.** Variants are unit kind and ride the unit wave; within a
  wave, invocations holding an admission resource are ordered last, which
  gives n004's "a cheap red test never pays for a Robolectric boot" without
  a second wave rule. For thinking_app every JVM class is one Gradle run
  regardless.
- **Dimensions changed.** `component_scheduler_resources`,
  `component_broad_test_scopes`.

### 11. Latency fixture: 2,500-row cell table (n004) vs thinking_app shape (n005)

- **Conflict.** Different second benchmark fixtures and targets.
- **Strategy.** Assumption update.
- **Resolution.** The thinking_app-shaped fixture at < 250 ms; the cell-table
  number has no referent in the merged design.
- **Dimensions changed.** `assumption_engine_latency_targets`,
  `requirements_go_engine`, `component_engine_binary`,
  `tradeoff_engine_speed_enables_per_task_use`.

### 12. Reference-count discrepancy on `~/.aitask`

- **Conflict.** n004: "121 hardcoded references across 28 shell/Python files
  plus 16 documentation files"; n005: "49 framework files".
- **Strategy.** Measured.
- **Resolution.** Framework code: 8 files / 35 occurrences (21 in
  `aitask_setup.sh`, 6 in `python_resolve.sh`, 3 in `aitask_path.sh`, one each
  in four others); tests: 20 files; docs: 18 files; 48 files repo-wide. The
  numbers are recorded in `assumption_home_symlink_compatibility` and
  `tradeoff_home_migration_window`.
- **Dimensions changed.** `assumption_home_symlink_compatibility`,
  `tradeoff_home_migration_window`.

### 13. Migration known-entry set

- **Conflict.** n004's set `{venv, bin, python, uv, dev_tier, update_check,
  engine}` omits `pypy_venv`, which `setup_pypy_venv()` creates,
  `python_resolve.sh` reads, and this host carries; n004's own rule would
  refuse the migration here.
- **Strategy.** Correction.
- **Resolution.** `pypy_venv` added to the known set; the omission is the
  stated reason the verb is explicit rather than default.
- **Dimensions changed.** `component_framework_home`,
  `tradeoff_home_migration_window`.

### 14. Near-duplicate dimensions across the explorers

- **Conflict.** `requirements_framework_home_name` (n004) /
  `requirements_user_root` (n005); `requirements_axis_product_selection`
  (n004) / `requirements_screen_locale_subdivision` (n005);
  `assumption_axis_membership_declarable` / `assumption_axis_sources_declarable`;
  `assumption_cells_enumerable_by_plugin` /
  `assumption_variant_universe_from_runner_list`; `tradeoff_cell_table_size` /
  `tradeoff_registry_directory_complexity`; `tradeoff_intersection_can_underselect`
  / `tradeoff_axis_projection_coarseness` (opposite directions of the same
  knob).
- **Strategy.** Keep every key; make each pair complementary.
- **Resolution.** Each paired key carries the facet its parent emphasised —
  the mandate's naming principle vs the feature's installed surface; the
  general product-space requirement vs the thinking_app instance; the general
  declarability claim vs the concrete globs; the enumeration principle vs the
  enumerator; committed footprint vs table count; under- vs over-selection —
  stated against the merged design so no key is a copy of another and none
  is dropped.
- **Dimensions changed.** All paired keys listed.
<!-- /section: conflict_resolutions -->

<!-- section: bootstrap_order -->
## Per-Repository Bootstrap Order

```
scan → classify --suggest → areas --import-codemap
     → [ axes.yaml → runner script with list/describe → annotate --from-body per member → testmap:reads on helpers → scan --apply ]
     → waivers → testmap_check (non-strict) → first full run (child rows anchor) → automatic score
     → stale --all --confirm-evidenced → require_stamp: true → check --strict
     → review `schedule` → concurrency: parallel → readiness → testmap_run
```

The axis steps sit after `classify --suggest` deliberately: the grid heuristic
is what tells a maintainer a product space exists before they hand-write one.
`UNCOVERED_VALUE`, `UNMAPPED_ARTIFACT`, `UNANNOTATED_MEMBER` and `DEAD_MEMBER`
stay non-fatal until `check --strict`, the treatment `UNSTAMPED` gets, so a
half-declared axis cannot block a repo that is still bootstrapping. For the
framework itself, in a separate release: `ait engine home --migrate` on
maintainers' hosts → `tests/test_aitasks_home.sh` through a real `install.sh
--dir` → flip the `ait setup` default → update the 18 doc files.
<!-- /section: bootstrap_order -->

<!-- section: open_questions -->
## Open Questions

1. Should `ait setup` migrate the home by default in the *next* release
   (proposed), or only ever on `ait engine home --migrate`? The criterion
   proposed here is the real-install test passing on the migration, idempotent
   re-run and hostile-symlink cases.
2. Should `~/.aitask` remain a symlink indefinitely once migrated, or be
   removed after all 8 framework files are ported to `aitasks_home()`?
   Proposed: keep for at least two minor versions, with `ait engine home`
   reporting the remaining hardcoded call sites so the removal is data-driven.
3. Hunk-level attribution inside a member file: a change to `ScreenFixtures.kt`
   is a change to every member today. The change surface would need line
   ranges and the engine the block spans (which it already has from
   `testmap:unit` positions). Proposed as the first consumer of a hunk-level
   change surface, after v1.
4. Should an axis hit on a member with **no** `covers` edges (a screen nobody
   annotated yet) still select its carrying variants (proposed: yes — an axis
   edge is an edge), or be an `UNSTAMPED`-style bootstrap warning?
5. Is `EVIDENCED` requiring *every* reached variant too strict for the
   `imeProxy_rtl` / `bidiSampler_rtl` matrices, which enrol a handful of
   screens and render rarely? Alternative: an axis value may be marked
   `evidence: optional` in `axes.yaml`.
6. Should `UNMAPPED_ARTIFACT` fail `check` (not only `--strict`) once a repo
   has finished bootstrapping? It is the exact silent-green class this feature
   exists to eliminate, but it makes adding a golden a two-step act.
7. Should `run_gate_admission.min_scored_full_runs` count only runs whose
   prediction was non-trivial (at least one selected variant)?
8. Should the `android-res` scanner also index Compose `@StringRes` parameters
   passed through helpers, or is a helper file's own edge the acceptable
   over-approximation for v1?
9. For `aitasks_mobile`, is the natural axis the source-set target
   (`commonTest` / `androidHostTest` / `androidDeviceTest`), or is that a
   runner/kind distinction with no axis needed? No axis is declared there.
10. Should observed axis sources from `attribute` ever be allowed to *narrow*
    a facet's globs after enough evidence? Proposed: never — a narrowing
    mistake is silent, a widening mistake merely costs time.
11. Baseline questions still open: `--confirm-evidenced` under autonomous
    profiles; cross-host-class evidence; `unit_covers_max: 8`; automatic prune
    on upgrade; `broad_review_days` default; a distance-like grade for scoped
    rows; absorbing `aitask_change_surface.sh` into the engine; the deb/rpm
    postinstall message; routing of a new declared edge with no `owns:` match
    (proposed: refuse); the CI evidence export format (JUnit alongside the
    results directory); whether thinking_app keeps `verify-active` as a suite
    runner for the record/promote flow while `screen-matrix` handles selected
    variants (proposed: yes — they answer different questions).
<!-- /section: open_questions -->