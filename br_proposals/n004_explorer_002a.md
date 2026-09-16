<!-- section: overview [dimensions: requirements_*] -->
## Overview

The goal is unchanged: a framework feature, generic across `aitasks`,
`thinking_app`, `thinking_backend`, `aitasks_go` and `aitasks_mobile`, that
maintains a relation between source files and test units, translates a task's
change set into a ranked set of tests with a reason on every line, runs them
through project-defined runners under a standard contract, tracks cost per
unit by host class, learns from failures the map did not predict, is enforced
by gates, and is taught to agents by a skill. The static Go engine
(`ait-testmap`), the per-edge blob-digest stamp with a run-evidence join, the
scoped table for high-level tests, the graded walk, the scheduler with real
locks, the cost ledger and the three gates are all kept as designed.

Two things change.

**1. The framework is called `aitasks`, so its home directory is `~/.aitasks`.**
The engine installs at `~/.aitasks/engine/v<VERSION>/ait-testmap`, not
`~/.aitask/engine/…`. Rather than leave a user with two dot-directories one
character apart holding halves of one install, `ait setup` performs a single
locked migration: the legacy `~/.aitask/` subtrees (`venv`, `bin`, `python`,
`uv`, `dev_tier`, `update_check`) move into `~/.aitasks/`, the emptied legacy
root is removed, and `~/.aitask` is left behind as a symlink to `~/.aitasks`.
That symlink is what makes the change affordable: the 121 hardcoded
`$HOME/.aitask/…` references across 28 shell and Python files, the venv's
absolute shebangs, the `~/.aitask/bin/python3` wrappers and the
`~/.aitask/python/<ver>/bin/python3` symlinks all dereference a path rather
than compare one, so every one of them keeps working unedited. New code calls
one resolver — `aitasks_home()` in bash, `internal/home` in Go — and existing
call sites are ported later, at leisure, by tasks that are already touching
them. The move is reversible in two commands.

**2. A third association form — axes and cells — because the existing two
cannot express a product space, and two of the five target repos have one.**

The design so far offers `covers` (a flat source→test edge, digest-stamped)
and `area`/`scope`/`trigger` (a flat glob→broad-test scope). `thinking_app`'s
visual suite is neither. Its natural subdivision is a **grid**: 47 screens ×
10 locale/geometry matrices ≈ 250 tracked goldens, one `@Test` method per
cell, one Robolectric class per (matrix, catalog slice). The questions a
change asks of that grid are two-dimensional and independent:

- `app/src/main/res/values-ar/strings.xml` changes → **every screen**, but
  only in the **Arabic** matrices (`pixel5Ar_rtl`, `shortPhoneAr_rtl`).
- `ui/screens/QuestionsScreen.kt` changes → the **Questions** screen, in
  **every** matrix.
- `res/font/cairo_*.ttf` changes → every screen, Arabic matrices only.
- Both of the first two in one task → the **union of those two sets**, which
  is 2 matrices × 47 screens + 10 matrices × 1 screen, not 10 × 47.

Flat edges cannot say this. Encoding the grid as `covers` edges needs one edge
per (source, cell) pair — thousands of rows meaning less than the grid does —
and, because flat edges union, a task touching both an Arabic resource and a
screen composable would still select the whole grid. Encoding it as one
`area: ui` scope selects the entire ten-matrix suite for any UI edit, behind
`thinking_app`'s heavy-run lock, which is precisely the all-or-nothing the
feature exists to remove. So: **no, the design as it stood did not support
this mapping**; it degraded to one of those two extremes.

The addition is deliberately small and generic:

- `aitestmap/registry/axes.yaml` declares **axes** (`screen`, `locale`,
  `device`) with their value sets and, per value, the **source globs that are
  members of it**.
- An executable under `aitestmap/cells/` enumerates the repo's **cells** — one
  JSON line per test unit with its coordinate on each axis — derived from the
  routing statement the project already owns. `ait testmap cells --refresh`
  writes them, sorted, to the generated `registry/_cells.yaml`.
- Selection resolves each axis against the change set to either a value set or
  `ANY`, then selects a cell iff **for every axis** the axis is `ANY` or the
  cell's value is in the set. **Union within an axis, intersection across
  axes.** A file matching no member glob of an axis is `ANY` on that axis, so
  an incomplete declaration over-selects and never under-selects.
- The `gradle-class` runner gains `unit: method`, so a cell is addressable
  (`--tests com.…Pixel5ArRtlScreenshotsTest.questions`), and the budget is
  costed per **invocation group** (the class), because the second cell in an
  already-booted Robolectric class costs its per-unit mean, not another boot.

The same machinery covers this repository's own product space: `tests/golden/`
holds `SKILL-<profile>-<agent>.md` and `<procedure>-<profile>.md` renderings,
so `.opencode/**` is a member of `agent=opencode` and a `{% if profile ==
"fast" %}` edit is `profile=fast` — a change to one agent's tree selects that
agent's goldens across every skill, not all of them.
<!-- /section: overview -->

<!-- section: what_changed [dimensions: component_framework_home, component_axes, component_cell_enumeration] -->
## What Changed From the Previous Design, and What Did Not

| aspect | previously | now | why |
|---|---|---|---|
| engine install root | `~/.aitask/engine/v<V>/` | `~/.aitasks/engine/v<V>/` | the framework is `aitasks`; the engine is a new component with no legacy to preserve, so it starts at the correct path |
| rest of the user home | `~/.aitask/{venv,bin,python,uv,dev_tier}` | migrated once to `~/.aitasks/`, `~/.aitask` left as a symlink | a split home would have to be explained at every future call site; the symlink makes the move cost nothing at the 121 existing references |
| path resolution | hardcoded `$HOME/.aitask/…` | `aitasks_home()` / `internal/home`, `AITASKS_HOME` override | one place to change, and a test can point a whole run at a temp home |
| association forms | `covers` edges, `area`/`scope`/`trigger` scopes | plus **axes + cells** | a product-shaped suite is neither a flat edge set nor one scope |
| registry tables | five (edges, scopes, areas, rules, waivers) | seven (+ axes, cells) | `axes` is declarative, `cells` is generated — neither is a new hand-authoring surface |
| runner unit granularity | `file \| class \| suite` | `file \| class \| method \| suite` | a cell is a `@Test` method; without method granularity a cell is not addressable |
| budget costing | per unit p95 | per **invocation group** for batched runners | a second method in a booted Robolectric class is ~0.3 s, not the ~5 s the class cost |
| `check` rules | `STALE_PATH`, `UNSTAMPED`, `DEAD_SCOPE`, `KIND_MISMATCH`, `CONTRACT_MISMATCH` | plus `DEAD_AXIS_GLOB`, `UNMAPPED_CELL`, `UNCOVERED_VALUE` | the generic form of the silent-green failure `thinking_app` closes by hand today |
| `stale` classes | `STALE_PATH`/`STALE`/`EVIDENCED`/`UNSTAMPED`/`STALE_AREA`/`REVIEW_DUE` | plus `STALE_AXIS` | an axis membership glob that has rotted is drift, reported like area drift |
| `attribute` kinds | missing-edge, test-wrong, source-wrong, missing-trigger, area-too-narrow | plus `axis-membership-missing` | the feedback loop must be able to correct an axis, or a wrong membership is permanent |
| everything else | — | unchanged | digest stamps, evidence join, gates, scheduler, cost ledger, change-surface intake, boundary rule, release CI shape |

Unchanged and worth restating, because the two additions do not touch them:
the binary never invokes `aitask_*.sh`; the shim pipes the change surface in;
the engine never writes `aitasks/`, `aiplans/`, `.aitask-data/` or a gate
ledger; the repository-local directories keep their existing `.aitask-*`
prefix (`.aitask-scripts/`, `.aitask-data/`, `.aitask-gates/`,
`.aitask-explain/`, `.aitask-testmap/`) — renaming those is a different,
cross-repository change with `.gitignore` and sibling-project blast radius, and
the mandate is about the user's home, which the framework owns entirely.
<!-- /section: what_changed -->

<!-- section: architecture [dimensions: component_go_engine, component_engine_binary, component_binary_distribution, component_engine_packaging, component_registry_loader, component_framework_home] -->
## Architecture

### Process boundary

```
ait testmap <verb> ...                          (user / skill / gate verifier)
 └─ .aitask-scripts/aitask_testmap.sh           bash shim, ~35 lines:
      │   source lib/aitasks_home.sh            → AITASKS_HOME resolved once
      │   resolve  $AIT_TESTMAP_BIN  >  AIT_ENGINE=dev → $AITASKS_HOME/engine/dev/ait-testmap
      │            >  $AITASKS_HOME/engine/v$(cat .aitask-scripts/VERSION)/ait-testmap
      │   verify   `<bin> version` == VERSION (dev slot: <VERSION>-dev+<sha>), else ENGINE_MISSING / ENGINE_MISMATCH, exit 3
      │   for --task verbs: aitask_change_surface.sh list <id>  |  <bin> <verb> --changes - ...
      └─ $AITASKS_HOME/engine/v<VERSION>/ait-testmap --repo-root "$AIT_DIR" <verb> ...
           internal/home            AITASKS_HOME > ~/.aitasks > ~/.aitask; one function, used by nothing on the hot path
           internal/registry        merge aitestmap/registry/*.yaml → edges, scopes, areas, axes, cells, rules, waivers
           internal/annot           grammar v2 scanner, stamp reader, line-targeted rewriter
           internal/deps            bash/python/go/kotlin/gradle forward-dep scanners + plugin exec; blob-keyed cache; inverted in memory
           internal/axes            axis value sets, member globs, reach: computation, resolve(changeSet) → set | ANY
           internal/cells           cell-plugin exec, _cells.yaml codec, reconciliation against axis value sets
           internal/changesurface   parser for BASELINE:/PLANSCOPE:/COMMITTED:/TASK:/OTHER:/UNKNOWN: lines
           internal/selectr         graded walk, rules, scoped join at d1, cell join at d1, ranking, budgets, stale marks, prediction
           internal/sched           errgroup waves, flock slot files, admission/allocator exec, broad_after_unit, schedule report
           internal/runner          manifest/results codec, bindings, builtin: runners, unit granularity, invocation grouping
           internal/cost            Welford + P² p95 ledger, per-invocation overhead rows, last_pass anchors, flake rate
           internal/feedback        score, attribute (edges; area/trigger widening; axis membership)
           internal/stale           digest compare, evidence join, classes, confirm/retarget
           internal/gitx            git via os/exec: rev-parse, ls-tree, merge-base --is-ancestor, log --name-status -M
           internal/platform        os/arch naming shared with engine/build.sh
             ├─ exec:  git, runner scripts or builtin runners, admission/allocator commands, scanner plugins, cell plugins
             └─ files: aitestmap/** (committed) · .aitask-testmap/ (runs, ledger; gitignored) ·
                       ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/ · ${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/aitasks-testmap-<uid>/
.aitask-scripts/lib/aitasks_home.sh             aitasks_home(); AITASKS_HOME export; the ONE bash path resolver
.aitask-scripts/aitask_gate_testmap_check.sh    machine verifier  <task> <attempt> <run-id> → check --task
.aitask-scripts/aitask_gate_testmap_run.sh      machine verifier  → select --include-stale → schedule → run
.aitask-scripts/aitask_engine.sh                ait engine build | test | cross | prune | home
.claude/skills/aitask-gate-testmap-fresh/       procedure gate: consumes `stale` lines, fixes annotations, `verify`
.claude/skills/aitask-testmap/                  agent skill: annotate, declare axes, cells --refresh, attribute, verify, classify
engine/                                          Go source — framework repo only; excluded from the release tarball
```

**Boundary rule (unchanged).** Anything that parses, walks, matches, digests
or schedules is Go. Anything that touches the gate ledger, the task file, or
the shell environment is bash and calls the binary. Cell plugins and scanner
plugins are project-owned executables the engine `exec`s with a fixed
contract; the engine never interprets a project's build system itself.

### The framework home

```
~/.aitasks/                     canonical root (AITASKS_HOME overrides)
  engine/v0.36.0/ait-testmap    + ait-testmap.sha256
  engine/dev/ait-testmap        + .dev marker {source, commit}
  venv/                         migrated from ~/.aitask/venv
  bin/{python,python3}          migrated
  python/<ver>/bin/python3      migrated (symlinks; targets are absolute and unaffected)
  uv/                           migrated
  dev_tier                      migrated marker file
  update_check                  migrated
  .home.lock                    flock target for the migration and for `ait engine prune`
~/.aitask -> ~/.aitasks         compatibility symlink, created by the migration
```

`aitasks_home()` (bash) and `internal/home.Root()` (Go) implement one rule:

1. `$AITASKS_HOME` if set and non-empty (tests and multi-install hosts).
2. `$HOME/.aitasks` if it exists.
3. `$HOME/.aitask` otherwise (a host that has not run `ait setup` since the
   rename; never created by new code).

`ait engine home` prints the resolved root, whether it is legacy, whether the
compatibility symlink is in place, and what `ait setup` would do next.

### Migration, and why it is safe

`migrate_framework_home()` runs in `aitask_setup.sh` **before**
`install_engine_binary()` and `install_global_shim()`:

```
flock ~/.aitasks/.home.lock (create ~/.aitasks first; fail-fast if another ait holds it)
  ├─ ~/.aitask absent                     → nothing to do            HOME_SKIPPED:no-legacy-root
  ├─ ~/.aitask is already a symlink → ~/.aitasks  → idempotent re-run  HOME_SKIPPED:already-migrated
  ├─ ~/.aitask is a symlink elsewhere     → refuse, name the target   HOME_SKIPPED:foreign-symlink
  ├─ ~/.aitask and ~/.aitasks on different filesystems → refuse       HOME_SKIPPED:cross-device
  ├─ an entry under ~/.aitask that is not in the known set            HOME_SKIPPED:unknown-entry:<name>
  │     {venv, bin, python, uv, dev_tier, update_check, engine}       (report it; do not guess)
  ├─ for each known entry: mv ~/.aitask/<e> ~/.aitasks/<e>            (same-device rename, atomic per entry)
  ├─ rmdir ~/.aitask                                                  (fails loudly if not empty)
  └─ ln -s ~/.aitasks ~/.aitask                                       HOME_MIGRATED:<n entries>
```

The venv keeps working because nothing in it compares a path: `pyvenv.cfg`,
console-script shebangs and the `~/.aitask/bin/python3` wrapper all
*dereference* `$HOME/.aitask/venv/bin/python`, which the symlink resolves.
Same for `~/.aitask/python/pypy-<ver>/bin/python3`, whose symlink target is the
absolute path of the real interpreter outside the framework home. The
`PATH` entry `lib/aitask_path.sh` prepends resolves through the symlink too.

`--no-home-migration` / `AIT_HOME_MIGRATE=0` skips the step entirely; the
engine then installs under the resolved legacy root and everything else is
unchanged, which is the escape hatch for a host where the symlink is
unacceptable. Reverting is `rm ~/.aitask && mv ~/.aitasks ~/.aitask`.

### Go module (`engine/`)

```
engine/
  go.mod                 module github.com/beyondeye/aitasks/engine; go 1.26; toolchain directive pinned
  build.sh               the ONE place GOOS/GOARCH matrix, CGO_ENABLED=0, -trimpath, -buildvcs=false,
                         -ldflags "-s -w -X main.version=<V> -X main.commit=<sha> -X main.contract=1" live
  cmd/ait-testmap/main.go   stdlib `flag` verb table; per-verb --help; line protocol / --json
  internal/<pkg>/        as above
  testdata/              golden registries incl. a 2,500-row cell fixture; fixture repos via `git init` in t.TempDir()
```

Dependencies unchanged: `gopkg.in/yaml.v3`, `github.com/bmatcuk/doublestar/v4`,
`golang.org/x/sync`. The cell plugin contract is JSON lines over stdout, so
`encoding/json` from the standard library covers it; no new module.

### Registry directory (one directory, seven tables)

```
aitestmap/
  config.yaml            unit_covers_max: 8 · suite_budget_s: 600 · bootstrap_until · require_stamp · broad_review_days: 0
                         concurrency: serial|parallel · broad_after_unit: true · device_policy: filter_by_resource
                         host_class · flake_threshold: 0.2 · axis_fanout_max: 6 · cells: auto|all|none
  runners.yaml           runner repository (builtin: or script), bindings, command:/cwd: overrides, unit granularity
  resources.yaml         named resources (mutex / semaphore / admission / allocator; host / worktree / run)
  registry/
    _scanned.yaml        generated: unit edges with @date/blob10 stamps        written only by scan --apply
    _scoped.yaml         generated: broad rows (areas, globs, triggers)         written only by scan --apply
    _cells.yaml          generated: cell rows (unit, runner, axes, artifact)    written only by cells --refresh
    observed.yaml        written only by attribute: observed edges, area members, triggers, axis memberships
    areas.yaml           hand-written named glob sets (seedable via `areas --import-codemap`)
    axes.yaml            hand-written axis declarations: values, member globs, reach: roots
    <area>.yaml          hand-written: owns: [globs | area names | axis names], edges, scopes, rules, waivers, areas:
  cells/*                optional executable cell plugins (one JSON line per unit)
  costs/<hostclass>.yaml Welford n/mean/sd/p95/last + last_pass + flake per unit + per-invocation overhead rows
  runners/*.sh           optional project runners (a script named like a builtin shadows it)
  scanners/*             optional executable scanner plugins
```

Merge rule unchanged in shape: every file under `registry/` contributes rows to
the same tables; `owns:` now also accepts an **axis name**, so a hand file may
own an axis's membership block. A row outside its file's `owns:` fails `check`;
`declare` routes by `owns:` and refuses when nothing matches.
<!-- /section: architecture -->

<!-- section: axes_and_cells [dimensions: component_axes, component_cell_enumeration, requirements_axis_product_selection, assumption_axis_membership_declarable, assumption_cells_enumerable_by_plugin] -->
## Axes and Cells: Mapping Source Changes Into a Product Space

### The shape being modelled

`thinking_app`'s visual verification is a grid, and the repository already
states the grid in exactly one place per dimension:

- **Matrices** — `known_matrices()` in `tools/verification/lib/screenshot-review.sh`
  lists ten: `pixel5_rtl`, `pixel5_ltr`, `shortPhone_rtl`, `shortPhone_ltr`,
  `imeProxy_rtl`, `bidiSampler_rtl`, `pixel5Ru_ltr`, `shortPhoneRu_ltr`,
  `pixel5Ar_rtl`, `shortPhoneAr_rtl`. Each decomposes into a **locale** (`he`,
  `en`, `ru`, `ar`), a **device geometry** (`pixel5`, `shortPhone`,
  `imeProxy`, `bidiSampler`) and a **direction** (`rtl`, `ltr`) — the
  qualifier constants in `ScreenshotTestHarness.kt` are literally
  `"$LOCALE-$DIRECTION-$GEOMETRY"`.
- **Classes per matrix** — `matrix_classes()` in the same file maps each
  matrix to the one or two Robolectric classes that render it. A Robolectric
  class carries exactly one `@Config(qualifiers = …)`, which is *why* there is
  a class per matrix and not one generalised renderer.
- **Screens** — one `@Test` method per screen on
  `ScreenCatalogScreenshotsTest` and its extended sibling, and the exact set of
  produced goldens is a membership manifest:
  `tools/verification/primary-catalog-expected.txt` and
  `tools/verification/secondary-matrices-expected.txt` (247 secondary lines).
- **Golden naming** — `secondaryGoldenPath()` writes
  `<Screen>_<matrix>_<direction>.png` under a `GOLDEN_TOKEN = [A-Za-z0-9]+`
  grammar that exists precisely so the name decomposes back into its
  coordinates.

So the coordinate of every test unit is already derivable from artefacts the
project maintains and guards. What is missing is a framework that can consume
it.

### Axis declaration

```yaml
# aitestmap/registry/axes.yaml   (hand-written, in thinking_app)
contract: 1
axes:
  locale:
    values: [he, en, ru, ar]
    members:
      he: ["app/src/main/res/values/**", "app/src/main/res/values-iw/**",
           "app/src/main/res/font/heebo_*.ttf"]
      en: ["app/src/main/res/values-en/**", "app/src/main/res/font/roboto_*.ttf"]
      ru: ["app/src/main/res/values-ru/**"]
      ar: ["app/src/main/res/values-ar/**", "app/src/main/res/font/cairo_*.ttf"]
  device:
    values: [pixel5, shortPhone, imeProxy, bidiSampler]
    members: {}          # no source is device-specific today; every change is ANY here
  screen:
    values_from: cells   # the value set is whatever the cell plugin enumerates
    reach:
      from: "app/src/main/java/com/softman/thinking/ui/screens/{value}Screen.kt"
      scanner: kotlin
      fanout_max: 6      # a source reaching more than 6 screens resolves to ANY
```

Three membership styles, in increasing cost:

1. **Explicit globs** (`locale`). The strongest and the cheapest to check: a
   glob that matches nothing is `DEAD_AXIS_GLOB` at `check` time.
2. **Empty membership** (`device`). Every change is `ANY` on that axis, so the
   axis constrains nothing until someone declares members. Declaring an axis
   with no members is legal and useful: it makes the coordinate visible in
   reasons and in `explain` before anyone commits to narrowing on it.
3. **Computed reach** (`screen`). For each value `v`, the root file
   `…/{v}Screen.kt` is walked through the existing Kotlin dependency scanner;
   every source reachable from it is a member of `v`. A source reachable from
   more than `fanout_max` values resolves to `ANY` — which is what a shared
   design-system file such as `ui/components/Buttons.kt` correctly becomes.

`ait testmap axes --explain app/src/main/res/font/cairo_bold.ttf` prints:

```
AXIS:locale|ar|glob app/src/main/res/font/cairo_*.ttf|axes.yaml:11
AXIS:device|ANY|no member glob matched
AXIS:screen|ANY|no member glob matched; reach: not computed for non-Kotlin sources
```

### Resolution and the selection rule

For a change set `S`, each axis `A` resolves to either an explicit value set or
`ANY`:

```
resolve(A, S):
    if ∃ f ∈ S with no member of A matching f:  return ANY        # fail-safe
    return ⋃ { members(A, f) : f ∈ S }
```

A cell `c` is selected iff, **for every axis** `A`:
`resolve(A, S) == ANY  ∨  c.axes[A] ∈ resolve(A, S)`.

That is **union within an axis, intersection across axes** — and it is the
whole of the mandate's question. Worked examples on the real grid:

| change set | locale | device | screen | cells selected |
|---|---|---|---|---|
| `res/values-ar/strings.xml` | `{ar}` | ANY | ANY | 47 screens × 2 Arabic matrices = 94 |
| `ui/screens/QuestionsScreen.kt` | ANY | ANY | `{Questions}` | 1 screen × 10 matrices = 10 |
| both of the above | `{ar}` | ANY | ANY ∪ `{Questions}` → ANY¹ | 94 ∪ 10 |
| `res/font/cairo_bold.ttf` | `{ar}` | ANY | ANY | 94 |
| `ui/components/Buttons.kt` | ANY | ANY | ANY (fan-out > 6) | all ≈ 250 |
| `ScreenshotTestHarness.kt` | ANY | ANY | ANY | all ≈ 250 |

¹ The third row is the important one and the reason the rule is stated as it
is. `values-ar/strings.xml` has no `screen` membership, so `screen` resolves to
`ANY`; `QuestionsScreen.kt` has no `locale` membership, so `locale` would
resolve to `ANY` too — giving the whole grid. That is correct but coarse, so
the selector applies the rule **per changed file and unions the resulting cell
sets**, rather than resolving each axis once over the whole change set:

```
select(S) = ⋃ { cells matching coordinate-filter(f) : f ∈ S }
```

Each file contributes the cells its own coordinate implies; the union across
files is the answer. This keeps intersection sharp within a file (an Arabic
resource is Arabic-only) and union safe across files (two unrelated edits do
not cancel each other), and it is what makes the two-edit case 104 cells
instead of 470. `resolve` over the whole change set is kept only for
`--explain` and for the `DISPLAY:` summary line.

### Cell enumeration

Cells are never hand-written. A project-owned executable under
`aitestmap/cells/` prints one JSON object per line:

```json
{"unit":"com.softman.thinking.testing.Pixel5ArRtlScreenshotsTest.questions",
 "runner":"gradle-class",
 "axes":{"screen":"Questions","locale":"ar","device":"pixel5","direction":"rtl"},
 "artifact":"app/src/test/screenshots/secondary-matrices/Questions_pixel5Ar_rtl.png"}
```

In `thinking_app` that plugin is roughly sixty lines of bash: source
`lib/screenshot-review.sh`, iterate `known_matrices()`, ask `matrix_classes()`
for the classes, read the membership manifest for the screens each class
produces, decompose the matrix token into `locale`/`device`/`direction` with
the same grammar `secondaryGoldenPath()` writes. It reads the project's single
routing statement rather than restating it — the rule this repository already
holds for any list appearing in three or more places.

In `aitasks` the plugin walks `tests/golden/skills/<skill>/SKILL-<profile>-<agent>.md`
and `tests/golden/procs/<proc>/<procedure>-<profile>.md` and emits
`{"axes":{"skill":"aitask-pick","profile":"fast","agent":"claude"}}` per
rendered variant, with the verifying test as the unit.

`ait testmap cells --refresh` execs every plugin under a bounded pool
(cap 8), validates that each axis value is declared (or, under
`values_from: cells`, collects it), and writes `registry/_cells.yaml` sorted by
`(unit)`, only when the content changed. `--diff` shows what a refresh would
change without writing. `--list` and `--explain <unit>` are read-only.

### Reconciliation: the silent-green class, generically

Enumeration lets `check` ask two questions no flat table can:

- `UNMAPPED_CELL:<artifact>|<reason>` — an artefact the project tracks that no
  enumerated cell claims. This is exactly the failure
  `MatrixClassificationTest` and `MatrixAuditRegistry` exist to close by hand
  in `thinking_app`: an entire matrix's goldens entering the tracked tree
  audited by nobody, with every gate green. Here it is a framework rule any
  repo with an `artifact:` field gets.
- `UNCOVERED_VALUE:<axis>|<value>` — a declared axis value that no cell
  occupies. A new locale added to `values:` with no matrix registered is
  reported the day it is declared rather than the day someone notices.

Both fail `check --strict`; `UNMAPPED_CELL` also fails `stale --strict`, so a
repo-wide CI sweep catches it outside a task.

### What axes are not

- Not a replacement for `covers`. A test that names specific sources still
  names them; a cell coordinate answers *which configuration*, never *which
  source*.
- Not a replacement for `area`/`scope`. A broad test with no grid is a scoped
  row, and a cell is never area-scoped.
- Not digest-stamped. A cell's freshness is structural — membership globs that
  still match, enumeration that still reconciles — not content-based. There is
  no per-cell `@blob` and no `EVIDENCED` class for cells.
- Not inferred. The framework never guesses a coordinate; an axis with no
  declaration is `ANY`, which selects more, not less.
<!-- /section: axes_and_cells -->

<!-- section: data_flow [dimensions: component_selector, component_staleness_tool, component_freshness, component_evidence_join, component_cost_ledger, component_engine_packaging, component_binary_distribution, component_cell_enumeration] -->
## Data Flow

### Authoring → registry

```
test files ──annotations──▶ ait testmap scan --apply ──▶ registry/_scanned.yaml   unit edges {test, covers, line, stamped_at, stamped_blob}
                                                     └▶ registry/_scoped.yaml    broad rows {test, kind, areas, globs, triggers, needs, reviewed_at}
aitestmap/cells/* ──────────▶ ait testmap cells --refresh ──▶ registry/_cells.yaml  cell rows {unit, runner, axes, artifact, plugin}
hand files + areas.yaml + axes.yaml + observed.yaml ─────▶ merged registry (in memory, seven tables)
```

`scan` asks every runner's `list` verb for the units it owns, reads each file
once, matches `testmap:` lines with a compiled regexp per comment leader (and
Python module docstrings), refuses unknown keys with a line number, and
rewrites each generated file only when its content changed, keys sorted.
`cells --refresh` is a separate verb on a separate cadence because it execs the
project's build-adjacent tooling; it is never on the hot path of `select`.

### Task → selection → run

```
aitask_change_surface.sh list t1234 ──▶ BASELINE:/PLANSCOPE:/COMMITTED:/TASK:/OTHER:/UNKNOWN: lines
        │  (the shim pipes; exit codes carry no meaning, lines do)
        ▼
ait-testmap select --task t1234 --changes - --include-stale [knobs] --run <run-id>
        ├─ UNKNOWN: present ──▶ refuse (exit 1, the lines echoed)
        ├─ exclude aitasks/ aiplans/ .aitask-data/ .aitask-gates/ before the walk
        ├─ walk:  d0 changed tests + escalation · d1 unit edges + scoped join + CELL JOIN
        │         d2.. reverse-dependency hops from the blob-keyed cache · rules inject select/implies/escalate
        ├─ cell join: per changed file, coordinate-filter over _cells.yaml (union across files,
        │             intersection across axes within a file); reasons carry every axis
        ├─ stale: `stale` mark on a unit row when a selecting edge's stamped_blob ≠ current blob and no evidence covers it
        ├─ union: --include-stale adds STALE / STALE_AREA / STALE_AXIS rows at distance s
        ├─ rank:  distance → kind (unit < cell < integration < e2e < device) → est. cost ascending
        ├─ budget: cell rows grouped into invocation groups (one Robolectric class = one group);
        │          a group costs overhead(p95 of the invocation) + Σ per-unit p95 of its selected cells;
        │          groups taken in ascending group cost until suite_budget_s; remainder DEFERRED:<unit>|budget
        └─ write .aitask-testmap/runs/<run-id>/{selection.json, prediction.json}
```

The invocation-group costing is the difference between this being usable and
not. Measured on `thinking_app` at an earlier catalogue size, a capturing
Robolectric class costs ~3.8–5.9 s of test time for 14–18 captures, inside a
Gradle invocation whose total build time was ~93 s. Charging each cell the
class's cost would make any multi-cell selection look like the full suite and
the budget would cut almost everything; charging the group once and each extra
cell its ~0.3 s marginal mean is both true and what makes "run 12 cells across
3 classes" a cheap, obvious selection.

### Results → evidence → cost

Unchanged, with one addition: every invocation writes a **per-invocation
overhead row** (`{group, overhead_ms, units_reported}`) alongside the per-unit
rows, and `costs --update` folds both. Cells do not anchor edges — they have no
edges — but their per-unit timings and their invocation overheads are what the
budget reads.

### Post-implementation → staleness → fix in the same commit

```
aitask_change_surface.sh list t1234  |  ait-testmap stale --task t1234 --changes -
        ├─ edges: STALE_PATH / STALE / EVIDENCED / UNSTAMPED            (unchanged)
        ├─ broad rows: STALE_AREA, REVIEW_DUE (opt-in)                  (unchanged)
        ├─ axes:  member glob matching nothing                          → STALE_AXIS:<axis>|<value>|<glob>|dead
        │         cell axis value absent from the declared value set    → STALE_AXIS:<axis>|<value>|<unit>|undeclared
        ├─ cells: tracked artifact with no enumerated cell              → UNMAPPED_CELL:<artifact>|unclaimed
        │         declared value with no cell                           → UNCOVERED_VALUE:<axis>|<value>
        ├─ UNKNOWN:<path>|<reason>  from the change surface
        └─ DISPLAY:<summary>  DECISION:FRESH|REVIEW|SKIP   (content states exit 0; --strict exits 1 on STALE_PATH, UNMAPPED_CELL)
```

The procedure gate gains two duties: a `STALE_AXIS` row is fixed by editing
`axes.yaml` (or dropping a retired value), and an `UNMAPPED_CELL` row is fixed
by re-running `cells --refresh` and, if it persists, by the plugin being
wrong — which is a defect in the project's routing, exactly the thing worth
surfacing at review time rather than at the next full run.

### Full run → score → attribute

`score` now classifies cell misses too. A cell that failed in a full run but
was not selected proposes `axis-membership-missing:<axis>|<file>|<value>` —
either the changed file was `ANY` on an axis where it should have had a
membership, or it was given a membership that excluded the failing value.
`attribute` writes it to `registry/observed.yaml`, which the loader merges into
the axis at load, so a wrong narrowing is corrected by evidence rather than by
argument.

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
.github/workflows/engine-check.yml  (new)  on: push, pull_request  paths: [engine/**]  → gofmt -l, go vet, go test

ait setup   (or ait upgrade → install.sh --force → aitask_setup.sh --source-only)
   ├─ migrate_framework_home()   → HOME_MIGRATED:<n> | HOME_SKIPPED:<reason>   (first, under the home lock)
   ├─ install_engine_binary()    (beside install_global_shim)
   │    ├─ os = uname -s → linux|darwin ; arch = uname -m → amd64|arm64 ; else ENGINE_UNSUPPORTED (skip, exit 0)
   │    ├─ $(aitasks_home)/engine/v<V>/ait-testmap exists and .sha256 sidecar matches → return
   │    ├─ --local-engine <path> | curl -fsSL --max-time 60 <asset> + SHA256SUMS | --engine-from-source
   │    ├─ sha256sum -c (shasum -a 256 on macOS) → install -m 0755 to .tmp → mv -f (atomic) → write .sha256
   │    ├─ `<bin> version --json` must echo <V>, else remove and fail loudly
   │    └─ --no-testmap / AIT_TESTMAP_FETCH=0 → TESTMAP_BINARY:skipped:<reason>
   └─ nothing else in setup depends on the engine

ait engine build → engine/build.sh host → $(aitasks_home)/engine/dev/ait-testmap + .dev marker
ait engine test  → go vet + go test ./... [-race]     ait engine cross → build.sh all into engine/dist/
ait engine prune → remove $(aitasks_home)/engine/v*/ no project in ~/.config/aitasks/projects.yaml is on
ait engine home  → print resolved root, legacy/migrated state, symlink status
AIT_ENGINE=dev ait testmap ...  → shim picks the dev slot (version must read <V>-dev+<sha>)
```
<!-- /section: data_flow -->

<!-- section: freshness [dimensions: component_freshness, component_staleness_tool, component_evidence_join, assumption_blob_digest_is_staleness_key, assumption_git_history_is_freshness_clock, assumption_passing_run_anchors_edges] -->
## Annotation Freshness: Digest Key, Evidence Anchor

Unchanged from the design this refines, and restated because the cell work
deliberately does not touch it.

### The stamp

```
# testmap:kind unit
# testmap:covers .aitask-scripts/aitask_gate_pass.sh        @2026-09-16/8f3a1c2d9e
# testmap:covers .aitask-scripts/lib/gate_verifier_lib.sh   @2026-09-16/41b0c7e2aa
```

`<blob10>` is the first ten hex digits of the git blob object id of the covered
source's content when the claim was last confirmed — `sha1("blob <len>\0" +
bytes)`, what `git hash-object` prints — computed in Go without invoking git.
Humans never type it: `annotate`, `verify` and `stale --confirm*` write it
through the line-targeted rewriter, which refuses (`REWRITE_CONFLICT:`) if the
text at that line no longer matches the registry row. The date is for the
reader; the digest is what is compared. A repository using git's sha256 object
format is detected once (`git rev-parse --show-object-format`) and stamped with
the matching function.

### The anchor and the evidence join

Re-flagging every edge whenever its source changes would be noise:
`aitask_update.sh` is named by 72 tests. Most of that staleness is
self-healing, because a test that ran and passed against the current content of
a source has demonstrated that its edge still holds at least as far as a test
can.

- Every passing result line records `last_pass: {sha: <HEAD at run>, at,
  run_id}` for its unit in the local ledger and, after `costs --update`, in the
  committed `costs/<hostclass>.yaml` (any host class counts). Lines from an
  invocation whose `runner.json` has a `cause`, and units whose flake rate
  exceeds `flake_threshold`, never anchor.
- For an edge whose `stamped_blob ≠ current_blob`, the **evidence join** asks:
  is there a `last_pass.sha` for this test, reachable from HEAD (`git merge-base
  --is-ancestor`), whose tree holds the source at exactly `current_blob`?
  Implementation: group mismatched edges by candidate sha, run one `git ls-tree
  <sha> -- <paths...>` per distinct sha under a bounded pool, compare object
  ids. A hit is `EVIDENCED`; no hit is `STALE`.
- Where the sha is not in fetched history the join yields nothing and the edge
  is `STALE` — the fail-safe direction. Digest comparison itself never needs
  history; history only ever *removes* nags.

`stale --confirm-evidenced` re-stamps exactly the `EVIDENCED` rows (recording
`confirmed_by: <run_id>`) and is the only bulk confirmation an autonomous
profile may perform.

### Why cells carry no stamp

A cell claims a *configuration*, not a source's content, so there is nothing to
digest. Its analogue of rot is structural and is caught by `check` and `stale`
without any test-file rewrite: a member glob that stopped matching
(`STALE_AXIS … dead`), a coordinate whose value was retired (`STALE_AXIS …
undeclared`), an artefact nobody claims (`UNMAPPED_CELL`), a value nobody
occupies (`UNCOVERED_VALUE`). This is a feature, not an omission: stamping
2,500 cell rows would put the stamp-churn problem back at ten times the scale
the `EVIDENCED` class was introduced to remove.

### Classes and report

```
SURFACE:task|all
EDGES:<n>                                                   stamped unit edges examined
CELLS:<n>                                                   enumerated cells examined
STALE_PATH:<test>|<source>|deleted|<culprit_tasks>
STALE_PATH:<test>|<source>|renamed|<new_path>|<culprit_tasks>
STALE:<test>|<source>|<stamped_at>|<stamped_blob>|<current_blob>
EVIDENCED:<test>|<source>|<stamped_blob>|<current_blob>|<run_sha>|<run_id>
UNSTAMPED:<test>|<source>
STALE_AREA:<test>|<area-or-glob>|<n_files>|<n_commits>
STALE_AXIS:<axis>|<value>|<glob-or-unit>|dead|undeclared
UNMAPPED_CELL:<artifact>|unclaimed
UNCOVERED_VALUE:<axis>|<value>
REVIEW_DUE:<test>|<area-or-glob>|<reviewed_at>|<age_days>
UNKNOWN:<path>|<reason>
DISPLAY:<one-line human summary>
DECISION:FRESH|REVIEW|SKIP
```

Fields are `|`-separated with `%`→`%25` then `|`→`%7C` encoding, matching
`aitask_verification_stale.sh` exactly; every content state exits 0, only CLI
misuse exits non-zero, and `--strict` exits 1 on `STALE_PATH` and
`UNMAPPED_CELL` for CI.

### The procedure gate

`testmap_fresh` is a `kind: procedure` gate (the `docs_updated` shape),
dispatched by the existing generic procedure-gate block of the
post-implementation step — before the change summary, so rewritten stamps and
annotation edits are part of the reviewed diff and land in the task's `(t<id>)`
commit. It is not a git hook (the framework installs none, and `commit --only`
makes a pre-commit hook unusable) and not a Claude Code hook (those must stay
silent and cannot take an editing decision). The `aitask-gate-testmap-fresh`
skill:

1. `aitask_gate.sh begin-procedure <task> testmap_fresh` → `RUN_ID:`, `ATTEMPT:`.
2. `ait testmap stale --task <task>` (the shim pipes the change surface).
3. `UNKNOWN:` paths: resolve with the user; under an autonomous profile exclude
   and log them — never guess.
4. `STALE_PATH:` rows: retarget to the renamed path, or to the successor the
   culprit task's plan names; else drop the line and note it.
5. `STALE:` rows: show `git diff <stamped_blob> <current_blob> --stat` and the
   hunks; ask confirm / retarget / `annotate --covers <new>` / `--drop` /
   follow-up task. Autonomous profiles never confirm a `STALE:` row.
6. `EVIDENCED:` rows: `stale --confirm-evidenced` (allowed autonomously).
7. `UNSTAMPED:` rows outside the bootstrap window: verify now or waive with an
   `until` date.
8. `STALE_AXIS:` / `UNCOVERED_VALUE:` rows: edit `axes.yaml`, or record the
   value as retired. `UNMAPPED_CELL:` rows: `cells --refresh --diff`, then
   refresh; a row that survives a refresh is reported as a plugin defect and
   never waved through.
9. `ait testmap scan --apply`; `aitask_gate.sh append --only-if-running
   <run-id> <task> testmap_fresh pass|skip|fail` with per-class counts and the
   resolved/unresolved rows in the sidecar log.
<!-- /section: freshness -->

<!-- section: broad_tests [dimensions: component_suite_registry, component_broad_test_scopes, assumption_areas_express_suite_blast_radius, assumption_broad_tests_area_scoped] -->
## High-Level Tests: Scoped Rows, and Where Cells Take Over

### Why they are not edges

Measured on this repository: 4 tests are in the serial carve-out, 29 boot a
real tmux pane, 46 bash tests drive `./ait` end to end, and
`tests/test_brainstorm_cli.sh` statically names 24 scripts. As `covers` edges
they would sit at distance 1 from most of the tree, every edit would
stale-flag them, and `_scanned.yaml` would carry thousands of rows meaning
"everything". So they are scoped rows in their own generated table.

### Vocabulary

```
# testmap:kind e2e                        integration | e2e | device | cell
# testmap:area brainstorm                 named glob set from areas.yaml; budgeted
# testmap:scope .aitask-scripts/aitask_*.sh          inline globs; budgeted like an area
# testmap:trigger .aitask-scripts/lib/launch_modes*.py   a hit always selects, never deferred
# testmap:axis locale=ar                  a hand-declared coordinate for the minority a plugin cannot reach
# testmap:reviewed 2026-09-16             display; REVIEW_DUE only when broad_review_days > 0
# testmap:covers tests/fixtures/board_seed.yaml @2026-09-16/0c1d2e3f4a   optional fixture pin, digest-stamped
# testmap:runner bash-file   testmap:needs tmux-server   testmap:batch no
```

`testmap:axis` exists for the handful of tests that occupy a coordinate but are
not produced by any plugin — `thinking_app`'s `ArabicFontMetricsTest` and
`ArabicMatrixAuditVerdictProbeTest` are `locale=ar` without being captures, so
an Arabic resource change should select them even though they write no golden.
Hand-declared coordinates merge into the same cell table with `from:
annotation` instead of `from: plugin`.

### Check rules

- `kind ∈ {integration, e2e, device}` for scoped rows; `kind: cell` rows come
  from the cell table and may not be hand-authored except through
  `testmap:axis`. A unit test carrying `area`/`scope`/`trigger` fails; a scoped
  row without at least one `area`/`scope`/`trigger` fails.
- Every named area exists; every area glob and scope glob matches at least one
  file (`DEAD_SCOPE:`); every axis member glob matches at least one file
  (`DEAD_AXIS_GLOB:`).
- A unit test with more than `unit_covers_max` (default 8) covers lines gets
  `KIND_MISMATCH:<test>|<n>|CONVERT_TO_SUITE` — a warning normally, a failure
  under `check --strict`.
- `ait testmap classify --suggest` lists scope candidates from heuristics
  (`tmux new-session`, an exec of `./ait`, membership in a runner's serial
  carve-out, covers above the limit) and now also flags an area-scoped suite
  whose members decompose into a grid — the signal being a set of test classes
  whose names share a stem and differ by a token that also appears in a
  directory or resource-qualifier name.

### Selection and scheduling

A scoped row joins the ranked list at distance 1 when the change set intersects
any glob of any of its areas, any scope glob, or any trigger
(`doublestar.Match`). Within a distance the list is ranked
`unit < cell < integration < e2e < device`, then by estimated cost ascending.
Scoped rows never contribute distance, never appear in `implies`, and are sinks
in the walk. Then the budget: trigger hits always run; area, scope and cell
groups are taken in ascending cost until `suite_budget_s` (default 600) is
spent, and the remainder is printed as `DEFERRED:<test>|budget` so every cut is
explicit and lands in the prediction record. `--suites auto|all|none` and
`--cells auto|all|none` select the policies independently.

`broad_after_unit: true` makes wave 1 unit-kind invocations only. **Cells ride
wave 1** when their invocation groups do not contend for a declared resource,
and wave 2 otherwise — for `thinking_app` they contend for the heavy-run lock
and therefore land in wave 2, so a cheap red unit test never pays for a
Robolectric boot. `device_policy: filter_by_resource` selects device units by
distance but runs them only when the emulator allocator hands out a handle.
<!-- /section: broad_tests -->

<!-- section: selection [dimensions: component_selector, assumption_change_surface_is_intake] -->
## Selection: the Graded Walk, One List

Intake is the change-surface line protocol — `BASELINE:`, `PLANSCOPE:`, then
`COMMITTED:`/`TASK:`/`OTHER:`/`UNKNOWN:` per path — piped in by the shim
(`--changes -`) or read from a file (`--changes <file>`, for engine tests
outside the framework). `COMMITTED:` and `TASK:` are the change set; `OTHER:` is
ignored; any `UNKNOWN:` refuses selection with exit 1 and the lines echoed.
Paths under `aitasks/`, `aiplans/`, `.aitask-data/`, `.aitask-gates/` are
excluded before the walk. A changed source with no edge, no rule, no area, no
scope, no axis membership and no waiver refuses the same way.

The graded walk: d0 for a changed test and for escalation, d1 for a direct
edge, a scoped join and a cell join, d2+ for reverse-dependency hops, rules
injecting at a declared distance with `select`, `implies`, `escalate`. Reverse
dependencies come from the in-process scanners (bash `source`/`.` lines and
`$SCRIPT_DIR/aitask_*.sh` sibling invocations; Python `import`/`from` resolved
under configured roots; `go list -deps -json ./...` cached by the `go.sum`
digest; Kotlin imports within a Gradle module plus the module graph from
`settings.gradle(.kts)`) and from executable plugins under
`aitestmap/scanners/`; forward deps are cached per source blob under the XDG
cache and inverted in memory, and the same inverted graph backs `reach:` axis
membership, so nothing is walked twice.

A selection in `thinking_app` for a task that edited `values-ar/strings.xml`
and `ui/screens/QuestionsScreen.kt`:

```
ArabicFontPolicyTest                                d=1 unit  edge(annotation) res/values-ar/strings.xml
QuestionsScreenBehaviorTest                         d=1 unit  edge(annotation) ui/screens/QuestionsScreen.kt
QuestionsHeaderFitTest                              d=2 unit  dep ui/screens/QuestionsScreen.kt
…Pixel5ArRtlScreenshotsTest.welcome                 d=1 cell  screen=ANY<-values-ar/strings.xml; locale=ar; device=pixel5     grp A est 0.31s
…Pixel5ArRtlScreenshotsTest.questions               d=1 cell  screen=ANY; locale=ar                                          grp A est 0.34s
…  (45 more cells in group A)                                                                                grp A overhead est 4.8s
…ShortPhoneArRtlScreenshotsTest.*                   d=1 cell  locale=ar; device=shortPhone                    grp B overhead est 3.9s
…CurrentHeadScreenshotsTest.questions               d=1 cell  screen=Questions<-QuestionsScreen.kt; locale=ANY grp C est 0.42s
…Pixel5LtrScreenshotsTest.questions                 d=1 cell  screen=Questions; locale=ANY                    grp D est 0.38s
…  (6 more single-cell groups, one per remaining matrix)
ArabicMatrixAudit                                   d=1 cell  locale=ar (testmap:axis)                        grp A
tools/verification/depin-checks-test.sh             d=1 integration  DEFERRED budget  area(verification)      est 61s
```

Every selected unit row carries a `stale` mark when any edge that selected it
is `STALE` — visible in the reason column, never a filter. Every cell row
carries its per-axis reason, including which axes resolved to `ANY` and why,
because a reader's first question about a sharp selection is what it left out.
`select` writes `selection.json` and `prediction.json` under
`.aitask-testmap/runs/<run-id>/` (`r-<YYYYMMDD>-<HHMMSS>-<4 hex>`). The
prediction record holds task, knobs, change set, unit rows with distances,
scoped rows with reasons and deferrals, cell rows with coordinates and
invocation groups, escalations fired, and the estimate per kind. Cuts are knobs
applied after ranking: `--max-distance`, `--budget-s`, `--kind`,
`--resource-filter`, `--suite-budget`, `--suites`, `--cells`, `--axis
<name>=<value>` (force a coordinate, for a reviewer probing one matrix).
`explain <test|source|unit>` prints the binding chain, every reason path, the
axis coordinates, and which runner (builtin or shadowing script) won.
<!-- /section: selection -->

<!-- section: runner_contract [dimensions: component_runner_contract, component_reference_runners, assumption_gate_exit_contract_reused, assumption_existing_locks_wrappable, assumption_batch_per_unit_timing_reportable] -->
## Runner Contract, Builtin Runners, Exit Mapping

The three verbs (`describe`, `list`, `run --manifest <f> --out <d>`), the
manifest and `results.jsonl` / `runner.json` shapes, first-match bindings with
the per-test `testmap:runner` override, batching and `unit: suite` wrappers are
unchanged. `runners.yaml` carries the `builtin:` scheme with `command:` and
`cwd:` overrides, and **unit granularity is now declared per runner**:

```yaml
runners:
  bash-file:    {exec: "builtin:bash-file",  unit: file,   batch: false, needs: [git-index]}
  pytest:       {exec: "builtin:pytest",     unit: file,   batch: true,  needs: [git-index],
                 command: ["$AITASKS_HOME/venv/bin/python", "-m", "pytest"]}
  go-test:      {exec: "builtin:go-test",    unit: file,   batch: true}
  gradle-class: {exec: "builtin:gradle-class", unit: method, batch: true, needs: [heavy-run],
                 command: ["tools/verification/lib/jvm-gradle.sh"],
                 group_by: class}                       # the invocation group for costing and batching
  verify-active:{exec: tools/verification/screenshot-tests.sh, unit: suite}
  engine-test:  {exec: "builtin:go-test",    unit: file,   batch: true,  cwd: engine/}
bindings:
  - {glob: "tests/test_*.sh",  runner: bash-file}
  - {glob: "tests/test_*.py",  runner: pytest}
  - {glob: "engine/**/*_test.go", runner: engine-test}
  - {glob: "**/*_test.go",     runner: go-test}
```

`unit: method` is what makes a cell addressable. The `gradle-class` builtin
emits one `--tests <FQCN>.<method>` argument per selected cell in a single
invocation per group, and parses per-method status and duration out of the JUnit
XML the Gradle test task already writes. `group_by: class` tells the scheduler
and the budget that all methods of one class share one boot.

**The zero-match trap is handled explicitly.** A Gradle `--tests` filter that
matches no test can complete successfully with zero tests executed, which would
otherwise read as "all passed". The runner therefore treats
`units_reported == 0 with units_expected > 0` as a mechanism failure with a
`cause`, never a pass — and such an invocation anchors no evidence. This is the
same `units_expected`/`units_reported` reconciliation every batch runner
performs, made load-bearing at method granularity.

Builtin runners (`ait-testmap runner <name> describe|list|run`): `bash-file`
(one process per file, stdout+stderr to `logs/<name>.log`), `pytest` (one
interpreter per invocation, `--junitxml` parsed; a unit annotated
`testmap:batch no` gets its own invocation — this repository's four
serial-carve-out modules carry that annotation, and
`tests/test_serial_carveout_doc_drift.sh` is extended to pin the annotations
against the runner's list so the two cannot diverge), `go-test` (per-file
`-run` regex from `func Test…` names, `-json` for per-test timing),
`gradle-class` (above), `suite` (any command as one unit), `device` (takes the
allocator handle from the manifest). A project script of the same name under
`aitestmap/runners/` shadows the builtin and `explain` shows which won.
`thinking_app` keeps `verify-active` as a suite runner for the full
record/promote flow and uses the builtin `gradle-class` for selected cells.

Runner exit codes are unchanged (0 all passed; 1 a unit failed or the mechanism
broke, `cause` set only for the mechanism; 2 did not run for a self-clearing
reason; 75 admission refused); the engine's `run` adds 64 for a usage or
configuration error.

The verifier shells, not the engine, map to the framework's verifier contract
`0 pass / 1 fail / 2 skip / 3 error`:

| engine exit | `aitask_gate_testmap_run.sh` | `aitask_gate_testmap_check.sh` |
|---|---|---|
| 0 | 0 pass | 0 pass |
| 1 | 1 fail | 1 fail |
| 2 (nothing selected) | 2 skip | — |
| 75 (admission refused past the run deadline) | 3 error → retried within `max_retries` | — |
| 64 / other / engine absent (shim exit 3) | 3 error | 3 error |

Admission refusal and a missing engine must never become a skip, because a
skipped test gate reads as a pass. Verifier 3 appends nothing to the ledger.
<!-- /section: runner_contract -->

<!-- section: gates [dimensions: component_gates, requirements_gate_enforcement] -->
## Gates

Registered in `.aitask-scripts/gates_reference.yaml` (canonical) and synced to
`aitasks/metadata/gates.yaml`; every field key already exists:

```yaml
  testmap_fresh:
    type: machine
    kind: procedure                              # skill aitask-gate-testmap-fresh
    description: "Source-to-test annotations and axis memberships on this task's changed sources reviewed and re-stamped"
    blocks_dependents: false
    verifier: aitask-gate-testmap-fresh
    max_retries: 0
    # unlocks ABSENT (linear-default), like docs_updated: a headless run defers procedure gates.
  testmap_check:
    type: machine
    description: "Test map consistent: changed sources mapped, tests registered, cells reconciled, no rotted paths"
    blocks_dependents: false
    verifier: aitask-gate-testmap-check
    max_retries: 0
    timeout_seconds: 120
    unlocks: [testmap_run]
  testmap_run:
    type: machine
    description: "Selected tests (unit, cell and scoped, stale-evidence included) pass"
    blocks_dependents: true
    verifier: aitask-gate-testmap-run
    max_retries: 1
    timeout_seconds: 1800
```

`testmap_check` does not depend on `testmap_fresh` having run: it fails
`STALE_PATH` rows, `UNMAPPED_CELL` rows, and — past bootstrap under
`require_stamp` — `UNSTAMPED` rows, on its own. The procedure gate exists so the
fix happens *before* the check fails, in the reviewed diff. A project enables
the three by adding them to its profile's declared gate set; `tests_pass` may
stay for a monolithic `test_command`; the manual-verification reachable-gate
filter leaves all three unreachable for `manual_verification` tasks, which is
correct. The full run is `ait testmap run --all`, the same machinery with every
unit and every cell selected.
<!-- /section: gates -->

<!-- section: go_engine [dimensions: component_go_engine, component_engine_binary, assumption_engine_latency_targets, assumption_go_toolchain_available, assumption_go_toolchain_ci_and_dev_only] -->
## The Go Engine: Why, and What It Must Cost

The wall time of a selected run is dominated by the tests, but the engine's own
latency is paid at every gate and every commit step (`select`, `check`,
`stale`), interactively (`explain`), and on every `scan`. The framework already
routes `ait board` through a PyPy fast path for exactly this class of cost; a
pure-Python parse of ~720 units and ~2,500–3,000 edges is in the hundreds of
milliseconds before any walk starts, and a real concurrent scheduler with
cross-process locks is something bash cannot do well and Python does slowly.
Targets on this repository, warm cache, pinned by `go test -bench` fixtures with
a golden registry in `internal/selectr`; a regression past 2× fails
`engine-check.yml`; the gates are not enabled here until the benchmarks pass:

| verb | target | what dominates |
|---|---|---|
| `select` (with stale marks) | < 200 ms | YAML load + walk + digest of covered sources of selected units |
| `select` with a 2,500-row cell table | < 400 ms | + one glob match per changed file per axis, one set test per cell |
| `select` cold | < 1.5 s | ~270 files regex-scanned, blob-hashed, cached |
| `scan` | < 300 ms | ~720 file reads + comment parse over a pool |
| `check` | < 300 ms | merged-table rules + `list` per runner + cell reconciliation |
| `stale --task` | < 300 ms | digests of the task's sources + one `ls-tree` per distinct evidence sha |
| `stale --all` | < 2 s | same, whole registry |
| `cells --refresh` | < 2 s | project plugin exec, pooled; **never on the hot path** |

The cell join is deliberately the cheapest thing in the table: axis resolution
is `O(|changed files| × |axes| × |member globs|)` and the cell filter is a hash
lookup per cell, so the 2,500-row table costs tens of milliseconds. The
expensive part — asking the project what its cells *are* — happens in
`cells --refresh`, on the cadence of "a screen or a matrix was added", and its
output is committed.

The scanner, dependency and cell-plugin passes fan out over a pool sized to
`runtime.NumCPU()`, capped at 8, so the engine never competes with the tests it
is about to launch.

CLI: `ait testmap <verb>` with verbs `scan | check | select | schedule | run |
stale | verify | annotate | score | attribute | declare | explain | costs |
areas | axes | cells | classify | runner | version`. Every verb prints
fixed-prefix `KEY:value` lines on stdout, `--json` prints one object,
diagnostics go to stderr, exit codes are per verb (`0` ok / findings-free, `1`
refused or failed, `2` nothing to do, `3` mechanism error, `64` usage).
Mutating verbs write only the files the registry's write-routing rules name and
print `WROTE:<path>` per file.

Go ≥ 1.26 is needed in release CI (added: `actions/setup-go@v5` with
`go-version-file: engine/go.mod` in the new `engine` job — `release.yml` has no
Go step today; the only `setup-go` is `hugo.yml`'s, at `website/go.mod`'s
1.25.7, which is not this) and on framework developers' machines;
target-project users never compile.
<!-- /section: go_engine -->

<!-- section: components [dimensions: component_*] -->
## Components

*(new)* marks a component this proposal introduces; *(revised)* marks one whose
design changed here; the rest are carried forward unchanged in substance.

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home *(new)*

**Technology.** `.aitask-scripts/lib/aitasks_home.sh` (bash, sourced by the
dispatcher and by `aitask_setup.sh`) and `engine/internal/home` (Go).
**Resolution.** `AITASKS_HOME` → `$HOME/.aitasks` if it exists → `$HOME/.aitask`.
The resolved value is exported once as `AITASKS_HOME` so subprocesses and the
engine agree without re-resolving.
**Migration.** `migrate_framework_home()` in `aitask_setup.sh`: `flock` on
`~/.aitasks/.home.lock`; refuse on a foreign symlink, a cross-device pair, or an
unrecognised entry under the legacy root; `mv` each of
`{venv, bin, python, uv, dev_tier, update_check, engine}` that exists;
`rmdir ~/.aitask`; `ln -s ~/.aitasks ~/.aitask`. Prints
`HOME_MIGRATED:<n>` or `HOME_SKIPPED:<reason>`.
**Opt-out.** `--no-home-migration` / `AIT_HOME_MIGRATE=0`.
**Verb.** `ait engine home` prints root, legacy flag, symlink state and the next
action.
**Tests.** `tests/test_aitasks_home.sh`: fresh install (no legacy root);
migration from a populated legacy root with a working venv afterwards;
idempotent re-run; hostile pre-existing `~/.aitask` symlink pointing elsewhere;
cross-device refusal (simulated by an `AITASKS_HOME` on a `tmpfs`);
`AITASKS_HOME` override isolating a whole run into `t.TempDir()`-style scratch.
**Documentation.** `aidocs/packaging/packaging_strategy.md` gains a home
paragraph; the 16 documentation files naming `~/.aitask` are updated in the
same change because doc prose is current-state-only.
<!-- /section: component_framework_home -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis registry and membership resolver *(new)*

**Technology.** `engine/internal/axes`, `doublestar/v4` for globs, the existing
`internal/deps` inverted graph for `reach:`.
**Schema.** `aitestmap/registry/axes.yaml`: per axis a `values:` list or
`values_from: cells`, an optional `default:`, `members: {value: [globs]}`, and
an optional `reach: {from: <pattern with {value}>, scanner: <name>, fanout_max: N}`.
`axis_fanout_max` in `config.yaml` is the global default (6).
**API.** `resolve(axis, file) → set|ANY`; `coordinateFilter(file) → predicate over cells`.
**Verbs.** `ait testmap axes --list | --check | --explain <path>`.
**Check rules.** `DEAD_AXIS_GLOB` (a member glob matching nothing),
`UNCOVERED_VALUE` (a declared value with no cell), value-set reconciliation
against `_cells.yaml` in both directions.
**Configuration in `thinking_app`.** Four `locale` values with
`res/values-*/**` and `res/font/{heebo,roboto,cairo}_*.ttf` globs; a `device`
axis with four values and no members (visible, not yet narrowing); a `screen`
axis with `values_from: cells` and a `reach:` root of
`app/src/main/java/com/softman/thinking/ui/screens/{value}Screen.kt`.
**Configuration in `aitasks`.** `agent` (`claude`→`.claude/**`,
`opencode`→`.opencode/**`, `codex`/`agy`→`.agents/**`), `profile`
(`default`/`fast`/`remote`, members being the per-profile Jinja partials),
`skill` (`values_from: cells`, `reach:` from each skill's `SKILL.md.j2`).
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Cell enumeration *(new)*

**Technology.** `engine/internal/cells`; project plugins are any executable
under `aitestmap/cells/`, run with `cwd` at the repository root, printing one
JSON object per line to stdout and diagnostics to stderr; a non-zero exit fails
`cells --refresh` and names the plugin.
**Line schema.** `{"unit": string, "runner": string, "axes": {name: value},
"artifact": string?, "needs": [string]?}`. `unit` is whatever the named runner's
`list` verb also produces, so the two tables join.
**Generated table.** `registry/_cells.yaml`, rows
`{unit, runner, axes, artifact, needs, plugin, from: plugin|annotation}`,
sorted by `unit`, written only when the content changed.
**Verbs.** `cells --refresh [--diff] [--plugin <name>]`, `cells --list`,
`cells --explain <unit>`.
**Scale.** `thinking_app` ≈ 2,500 rows (ten matrices over the 47-screen base and
extended catalogues plus hand-enrolled screens and the `testmap:axis` minority);
`aitasks` ≈ 60 rows (13 skills × 3 profiles for the Claude tree, plus the
procedure renderings).
**The `thinking_app` plugin**, concretely: source
`tools/verification/lib/screenshot-review.sh`; for each `known_matrices()` entry
take `matrix_classes()`; decompose `<geometry><Locale>_<direction>` with the
`GOLDEN_TOKEN` grammar; read
`tools/verification/{primary-catalog-expected.txt,secondary-matrices-expected.txt}`
for which screens each matrix actually produces; emit one line per
`(class, method)` with `artifact` set to the manifest's path. It restates
nothing — every fact comes from a file the project already guards.
<!-- /section: component_cell_enumeration -->

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(revised)*

`engine/cmd/ait-testmap` with
`internal/{registry,annot,deps,changesurface,axes,cells,selectr,sched,runner,cost,feedback,stale,gitx,home,platform}`.
Go 1.26 with a pinned toolchain directive, `CGO_ENABLED=0`, `-trimpath
-buildvcs=false -ldflags "-s -w -X main.version -X main.commit -X
main.contract"`. Dependencies: `gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`,
`golang.org/x/sync`; everything else standard library (`flag`, `os/exec`,
`encoding/json`, `crypto/sha1`, `crypto/sha256`, `syscall.Flock`). No cobra, no
go-git, no gofrs/flock. Line-protocol stdout with `--json`, per-verb exit
contracts. The binary never writes `aitasks/`, `aiplans/`, `.aitask-data/` or a
gate ledger and never invokes `aitask_*.sh`. Tests run against fixture repos
created with `git init` in `t.TempDir()`, never the framework repo.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary: identity, output contract, performance budget *(revised)*

Embeds `version`, `commit` and `contract`; `version --json` is the install-time
self-check; fixed-prefix structured output plus `--json`; `CONTRACT_MISMATCH`
refusal on registry files from a newer contract. The performance budget is
pinned by `go test -bench` over a golden registry that now includes a
2,500-row cell fixture and a four-axis declaration, with a 2× regression failing
`engine-check.yml`. Scanner, dependency and cell-plugin pools are capped at 8.
<!-- /section: component_engine_binary -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution: release assets and the host-side handshake *(revised)*

`engine/build.sh` is the single build and matrix command. The `engine` job in
`release.yml` (`setup-go` from `engine/go.mod`, `go vet`, `go test`, `build.sh
all`) produces `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` and
`ait-testmap_<V>_SHA256SUMS.txt`, attached by both `action-gh-release` steps
with `release needs: [plan, engine]`; the VERSION-matches-tag guard is
unchanged. A new `engine-check.yml` runs on `push`/`pull_request` for
`engine/**` (`gofmt -l`, `vet`, `test`, the 2× bench rule).
`lib/platform_detect.sh` maps `uname`. The shim's strict handshake resolves
`AIT_TESTMAP_BIN` (with an override notice) → `AIT_ENGINE=dev` slot requiring
`<V>-dev+<sha>` → `$(aitasks_home)/engine/v<V>/` requiring `== VERSION` →
`ENGINE_MISSING` exit 3 with a repair hint. Tests: `test_testmap_shim.sh`
(extended with a legacy-home host and an `AITASKS_HOME` host) and
`test_platform_detect.sh`. Docs: `aidocs/framework/go_engine.md`, a `CLAUDE.md`
Engine block, a `packaging_strategy.md` paragraph. `release-packaging.yml` and
nfpm `arch: all` are untouched.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade and developer regeneration *(revised)*

`install_engine_binary()` in `aitask_setup.sh`, reached by `ait setup` and by
`ait upgrade` through `install.sh`'s `--source-only` path, beside
`install_global_shim` and **after** `migrate_framework_home()`. `uname` mapping;
`.sha256` sidecar short-circuit; source order `--local-engine` → exact-version
release asset → `--engine-from-source` → `ENGINE_MISSING` warning; `sha256sum -c`
(`shasum -a 256` on macOS); atomic install into `$(aitasks_home)/engine/v<V>/`;
`version --json` must echo `<V>`; `.dev`-marked binaries are never overwritten
without `--force-engine`; `--no-testmap` / `AIT_TESTMAP_FETCH=0` print
`TESTMAP_BINARY:skipped`. `.aitask-testmap/` is gitignored by setup.
`aitask_engine.sh` provides `ait engine build|test|cross|prune|home` (prune
against `~/.config/aitasks/projects.yaml`, never automatic in upgrade).
`tests/test_install_engine_binary.sh` drives a real `install.sh --dir
--local-engine` and asserts the binary lands under `~/.aitasks/engine/`.
<!-- /section: component_engine_packaging -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(revised)*

`internal/registry` merges `aitestmap/registry/*.yaml` into **seven** tables:
edges, scopes, areas, **axes**, **cells**, rules, waivers. `owns:` routes by
glob (edges, rules), by area name (hand-declared scopes) and now by axis name
(membership blocks in a hand file). Write routing: `scan --apply` →
`_scanned.yaml` and `_scoped.yaml`; `cells --refresh` → `_cells.yaml`;
`attribute` → `observed.yaml`; `declare` → the owning hand file, refusing when
nothing owns. Deterministic sorted writes, only on change. Check rules:
`STALE_PATH`, `UNSTAMPED` past bootstrap under `require_stamp`, `DEAD_SCOPE`,
`DEAD_AXIS_GLOB`, `UNMAPPED_CELL`, `UNCOVERED_VALUE`,
`KIND_MISMATCH|CONVERT_TO_SUITE` above `unit_covers_max` (warn; fail under
`--strict`), `CONTRACT_MISMATCH`. Golden tests pin the merge rule, including
the precedence of `observed.yaml` axis memberships over declared ones (they
widen, never narrow).
<!-- /section: component_registry_loader -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(revised)*

Grammar v2: `testmap:kind`, `testmap:covers <path> @<date>/<blob10>`,
`testmap:area`, `testmap:scope`, `testmap:trigger`, **`testmap:axis
<name>=<value>`**, `testmap:reviewed`, `testmap:runner`, `testmap:needs`,
`testmap:batch` — per comment leader and Python module docstrings. Unknown keys
are refused with a line number. `kind` decides the association form. A
line-targeted rewriter edits stamps by `(file, line, current text)` and refuses
on `REWRITE_CONFLICT`. `testmap:axis` lines contribute cell rows with
`from: annotation`, which is how a coordinate-bearing test that produces no
artefact joins the grid.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(revised)*

Built-in bash, Python, Go (`go list -deps -json` cached by the `go.sum` digest),
Kotlin and Gradle module-graph scanners, plus executable plugins under
`aitestmap/scanners/` speaking one JSON line per file. Forward deps are cached
per source blob under
`${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json` and inverted
in memory. The inverted graph now has a second consumer: `reach:` axis
membership walks it from each value's declared roots, so a `screen` coordinate
costs no extra scan.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(revised)*

`internal/selectr` with `internal/changesurface`: line-protocol intake via
`--changes -` or a file, refusing on `UNKNOWN:`; the graded walk with
`select`/`implies`/`escalate` rules; scoped join at d1; **cell join at d1** by
per-file coordinate filter, unioned across the change set; ranking by distance,
then kind (`unit < cell < integration < e2e < device`), then cost; stale marks
from digest compare plus the evidence join; `--include-stale` union of `STALE`,
`STALE_AREA` and `STALE_AXIS` rows at distance `s`; the suite budget costed per
**invocation group** with `DEFERRED` lines and budget-exempt triggers;
`--suites` and `--cells` policies; cut knobs including `--axis <name>=<value>`;
the prediction record with per-kind estimates; `explain`.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(revised)*

`internal/runner`: `describe`/`list`/`run` verbs, manifest and
`results.jsonl`/`runner.json` formats, first-match bindings and the per-test
override, the `builtin:` scheme with `command:`/`cwd:` overrides and
shadow-by-name, **unit granularity declared per runner as `file | class |
method | suite`**, **batching by `(runner, invocation group, resource set, batch
flag)`** where `group_by: class` makes the group the class for method-granularity
runners, per-unit timeouts, `units_expected`/`units_reported` reconciliation
(with `units_reported == 0 && units_expected > 0` as a mechanism failure), exit
contract `0/1/2/75` plus `64` for usage errors.
<!-- /section: component_runner_contract -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(revised)*

`internal/sched`: resource kinds `mutex`/`semaphore`/`admission`/`allocator`,
scopes `host`/`worktree`/`run`, `acquired_by` planning; `flock(2)` slot files
taken in canonical order; admission `exec` with 75 deferral and backoff to the
run deadline; allocator `exec` with signal-safe release; goroutines under
`errgroup`; batching; `broad_after_unit` waves with **cells riding wave 1 when
their invocation groups hold no contended resource and wave 2 otherwise**;
`concurrency: serial|parallel` defaulting to `serial` at bootstrap (one
invocation at a time, schedule printed) with `--serial`/`--parallel` overrides;
the schedule report and its check half. `thinking_app`'s heavy-run lock
(`tools/verification/heavy-run-lock.sh`) and emulator allocator
(`tools/verification/emulator-allot.sh`) are wrapped as an `admission` and an
`allocator` resource without modification.
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(revised)*

`internal/cost`: Welford per `(unit, host class)` with P² p95 and last; per-repo
ledger `.aitask-testmap/ledger.jsonl` carrying `run_id`, `unit`, `status`,
`duration_ms`, `head_sha` per result; `costs --update` folds into
`aitestmap/costs/<hostclass>.yaml` and truncates. **Per-invocation overhead rows
are promoted from bookkeeping to a first-class input**: the row is
`{group, overhead_ms, units_reported}`, and a cell group's estimated cost is
`overhead.p95 + Σ unit.p95` over its selected cells — the number the budget
reads. `last_pass {sha, at, run_id}` per unit and a flake rate with
`flake_threshold` excluding a unit from anchoring; per-kind estimates.
<!-- /section: component_cost_ledger -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(carried forward)*

`internal/stale` with `internal/gitx`, reading `internal/cost`: for every edge
whose `stamped_blob` differs from the current blob, collect the test's
`last_pass` shas from the local ledger and committed costs (any host class),
drop candidates from invocations with a `cause` or units over the flake
threshold, keep shas that are ancestors of HEAD, and run one `git ls-tree` per
distinct sha. An edge whose source object id at that sha equals the current blob
is `EVIDENCED`, otherwise `STALE`. It never rewrites; `stale
--confirm-evidenced` is the explicit re-stamp and the only bulk confirmation an
autonomous profile may run. Cells have no edges and never enter this join.
<!-- /section: component_evidence_join -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(revised)*

`internal/feedback`: `score` splits a full run's failures into caught/missed for
unit, scoped **and cell** rows against a prediction record. `attribute` records
`missing-edge`/`test-wrong`/`source-wrong` for units,
`missing-trigger`/`area-too-narrow` for scoped rows, and
**`axis-membership-missing`** for a cell miss — naming the axis, the changed
file and the value that should have been reachable — each with task and run id,
written to `registry/observed.yaml`. Observed axis memberships are merged at
load and may only **widen** a value's member set, never narrow it, so evidence
can correct an over-narrow declaration but cannot silently sharpen selection.
<!-- /section: component_feedback_tools -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(revised)*

Three entries in `gates_reference.yaml` synced to `gates.yaml`: `testmap_fresh`
(`kind: procedure`, verifier `aitask-gate-testmap-fresh`, no `unlocks`, the
`docs_updated` shape), `testmap_check` (machine, `max_retries: 0`,
`timeout_seconds: 120`, `unlocks: [testmap_run]`), `testmap_run` (machine,
`blocks_dependents: true`, `max_retries: 1`, `timeout_seconds: 1800`). Two bash
verifiers on the `tests_pass` template map engine exits `0/1/2/75/64` and a
missing engine to verifier `0/1/2/3/3/3`, appending via `aitask_gate.sh`.
`testmap_check` additionally fails `UNMAPPED_CELL` rows.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(revised)*

`aitask-testmap` teaches: annotate (`covers`, or `area`/`scope`/`trigger`, or
`testmap:axis`); declare an axis, a value or a member glob; run `cells --refresh
--diff` after adding a screen, a locale or an agent tree; give a new source an
edge, rule, area, axis membership or waiver; `attribute` before the gate;
`verify` after editing an annotation; `classify --suggest` to choose the table,
including the grid suggestion. `aitask-gate-testmap-fresh` is the procedure gate
that runs `stale --task`, shows `git diff <stamped_blob> <current_blob>` per
`STALE` row, retargets `STALE_PATH` rows from the culprit task's plan, re-stamps
`EVIDENCED` rows, resolves `STALE_AXIS`/`UNCOVERED_VALUE`/`UNMAPPED_CELL` rows,
prompts on `UNSTAMPED` rows past bootstrap, never guesses `UNKNOWN` and never
confirms a `STALE` row autonomously. Authored for Claude Code first, then ported
to the other supported agents.
<!-- /section: component_skill -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(revised)*

Built into the binary as `ait-testmap runner <name>`: `bash-file`, `pytest`
(junitxml; `testmap:batch no` forces its own invocation — the serial carve-out,
pinned by extending `tests/test_serial_carveout_doc_drift.sh`), `go-test`
(per-file `-run` regex, `-json`), **`gradle-class` with `unit: class` or
`unit: method`** (method granularity emits one `--tests <FQCN>.<method>` per
selected cell in one invocation per `group_by` group and parses per-method JUnit
XML), `suite`, `device` (allocator handle). `command:`/`cwd:` overrides live in
`runners.yaml`; a project script of the same name shadows a builtin and
`explain` shows which won. `engine-test` runs `go-test` over `engine/` so the
engine's own tests ride the map.
<!-- /section: component_reference_runners -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness: stamps, anchors, `verify`, the procedure gate *(revised)*

The per-edge `@<date>/<blob10>` stamp is written only by `verify`, `annotate`
and `stale --confirm*`. `last_pass` anchors live in the ledger and in committed
costs. `verify` and `verify --all-evidenced` re-stamp. Config: `bootstrap_until`,
`require_stamp`, `flake_threshold`. The `testmap_fresh` procedure gate is
dispatched by the existing procedure-gate block before the change summary, so
stamp rewrites ride the `(t<id>)` commit; it is not a git hook and not a Claude
Code hook. **Cells carry no stamp** — their freshness is structural, and the
reasons are in the freshness section.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(revised)*

`internal/stale`: `stale --task --changes - | --all` prints
`SURFACE`/`EDGES`/`CELLS`/`STALE_PATH`/`STALE`/`EVIDENCED`/`UNSTAMPED`/`STALE_AREA`/`STALE_AXIS`/`UNMAPPED_CELL`/`UNCOVERED_VALUE`/`REVIEW_DUE`/`UNKNOWN`/`DISPLAY`/`DECISION`
lines with `%25`/`%7C` encoding; content states exit 0; `--strict` exits 1 on
`STALE_PATH` and `UNMAPPED_CELL`. It compares blob digests of the working tree
only, consults the evidence join, and adds rename hints and culprit task ids
from `git log --name-status -M` when history is reachable. Mutations:
`--confirm`, `--confirm-source`, `--confirm-evidenced`, `--retarget`, through
the rewriter with a re-scan of touched files.
<!-- /section: component_staleness_tool -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(revised)*

`registry/areas.yaml` plus `areas:` blocks in hand files, seedable via
`ait testmap areas --import-codemap` from `aitasks/metadata/code_areas.yaml` as
`<path>/**`. `registry/_scoped.yaml` rows are
`{test, kind, runner, areas, globs, triggers, needs, reviewed_at, line}`, with
`owns:` by area name for hand-declared rows. The d1 join, kind ranking and the
suite budget (`suite_budget_s` default 600, `--suite-budget`, `--suites
auto|all|none`) with `DEFERRED` lines and budget-exempt triggers are unchanged.
Check rules include `DEAD_SCOPE` and `KIND_MISMATCH|CONVERT_TO_SUITE`. `ait
testmap areas` gains nothing; `classify --suggest` gains one heuristic — an
area-scoped suite whose test classes share a stem and differ by a token that
also names a directory or a resource qualifier is proposed as an axis product,
with the candidate axis and values printed.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(revised)*

`kind: integration|e2e|device` selects the scoped association form;
`broad_after_unit: true` runs scoped rows only after a green unit wave;
`device_policy: filter_by_resource` is the default. Scoped rows are exempt from
per-edit digest staleness, with `STALE_AREA` (files in scope changed since
`last_pass`, no pass since) as the evidence-based drift signal feeding
`--include-stale`, and `REVIEW_DUE` as an opt-in cadence (`broad_review_days`,
default 0). `attribute` widens areas by evidence. `covers` on a scoped row is
allowed for digest-stamped fixture pins. **`kind: cell` is a separate third
category**: cells are never area-scoped, never carry `area`/`scope`/`trigger`,
and their wave placement follows their invocation group's resources rather than
`broad_after_unit` alone.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Each is flagged **[inherited]**, **[inherited, amended]** or **[new]**.

1. **`assumption_home_symlink_compatibility` [new].** Every existing consumer of
   the legacy `~/.aitask` tree keeps resolving once `~/.aitask` is a symlink to
   `~/.aitasks`, because all of them dereference a path rather than compare one.
   The surface was counted, not estimated: 121 hardcoded `$HOME/.aitask`
   references across 28 shell and Python files, 16 documentation files, plus the
   venv's absolute shebangs and `pyvenv.cfg`, the `~/.aitask/bin/{python,python3}`
   wrappers, and the `~/.aitask/python/<ver>/bin/python3` symlinks whose targets
   are absolute paths outside the framework home. No framework code compares a
   home path for equality or calls `realpath` on one. **Falsifier:** a
   `[[ "$dir" == "$HOME/.aitask" ]]` comparison anywhere, or a tool that
   canonicalises the venv root and then rejects it — either would surface as a
   failure in `tests/test_aitasks_home.sh`'s post-migration venv exercise.

2. **`assumption_axis_membership_declarable` [new].** For a product-shaped
   suite, which axis value a source belongs to is declarable as globs by the
   people who own the suite, because the project already routes by exactly that
   shape: `res/values-ar/**` and `font/cairo_*.ttf` *are* the Arabic matrices'
   inputs, and `.claude/` vs `.opencode/` vs `.agents/` *are* the agent axis. A
   source matching no member glob of an axis is `ANY` on that axis, the
   fail-safe direction. **Falsifier:** a project whose axis membership is
   genuinely dynamic (a runtime feature flag choosing a locale) — for which the
   answer is to declare no members on that axis, keeping it visible and
   non-narrowing.

3. **`assumption_cells_enumerable_by_plugin` [new].** A repo's cell set is
   enumerable by a project-owned executable derived from the project's existing
   single routing statement, not a second hand-maintained list. Evidence:
   `thinking_app` already derives its `--tests` argument order, its catalogue
   counts and its audit ownership from `matrix_classes()` and two membership
   manifests, and guards the derivation with its own tests. **Falsifier:** a
   repo where the set of test methods is only knowable by running the build —
   for which `cells --refresh` may exec the build's own list task, at the cost
   of a slower refresh, since refresh is off the hot path.

4. **`assumption_static_granularity_v1` [inherited, amended].** Static
   file-level facts are enough for v1 of the *edge graph*; no scanner in use
   today produces symbol-level coverage, and the schema keeps an optional
   `symbols` slot on an edge for a later hunk-level matcher. **Amendment:**
   product spaces are the one place where file-level facts provably collapse —
   `ScreenFixtures.kt` is a single 76 KB file that every screenshot class
   depends on and that reaches every screen — and they are handled without
   symbol analysis, because a cell's coordinate comes from the project's plugin
   rather than from a scanner.

5. **`assumption_change_surface_is_intake` [inherited].** The change-surface
   script's attribution is the right intake; its exit codes carry no meaning, so
   the shim pipes its `COMMITTED:`/`TASK:`/`OTHER:`/`UNKNOWN:` lines into
   `--changes -` and the engine parses lines only. Selection never reads a raw
   git diff; an `UNKNOWN:` path refuses selection and drives the stale decision.

6. **`assumption_existing_locks_wrappable` [inherited].** `thinking_app`'s
   heavy-run lock and emulator allocator can be wrapped as resources without
   changing them; the Go admission and allocator kinds exec the project's
   commands, honour their exit codes, and defer on 75 until the run deadline.

7. **`assumption_batch_per_unit_timing_reportable` [inherited, widened].**
   Runners can report per-unit timing inside a batch from their tool's own
   report format. **Widened:** the same JUnit XML that reports a Gradle test
   class reports each `@Test` method inside it, which is what makes a cell's
   marginal cost measurable separately from its class's boot — the number the
   invocation-group budget depends on.

8. **`assumption_target_repos_accept_aitestmap_root` [inherited, widened].**
   Every target repo will accept a root `aitestmap/` directory of YAML committed
   into its code tree. Runner scripts are optional (the reference runners are
   built in) and **cell plugins are optional** (a repo with no product space
   declares no axes and gets exactly today's behaviour).

9. **`assumption_testmap_token_no_collision` [inherited].** The annotation token
   `testmap:` does not collide with existing prose comments in any target repo;
   the 38 existing `# Covers:` headers in this repository are behavioural prose
   and are not matched.

10. **`assumption_gate_exit_contract_reused` [inherited].** The verifier
    contract `0 pass / 1 fail / 2 skip / 3 error` is reused through two
    dedicated verifier shells, not through `gate_command_exit_contract` (which
    maps only command exits 0/1/2). Runner exit 75 is deferred inside the engine
    and a final 75 maps to verifier 3; only an empty selection maps to 2; a
    missing engine maps to 3, never skip.

11. **`assumption_go_toolchain_available` [inherited].** Go ≥ 1.26 is available
    in release CI through an `actions/setup-go` step this design adds to
    `release.yml` (`go-version-file: engine/go.mod`) and on framework
    developers' machines; target-project users never need Go.

12. **`assumption_go_toolchain_ci_and_dev_only` [inherited].** Go is a
    build-time dependency only: `release.yml` has no Go step today and the
    repository's only `setup-go` is `hugo.yml`'s at `website/go.mod`'s 1.25.7,
    so the engine job provisions its own toolchain.

13. **`assumption_release_asset_reachable` [inherited].** A host running `ait
    setup` or `ait upgrade` can reach the releases host over HTTPS, as it already
    must for the framework tarball; the shim itself never downloads, so a gate
    run never performs a network fetch.

14. **`assumption_release_assets_reachable` [inherited, path corrected].**
    Air-gapped or off-matrix hosts supply the binary via `--local-engine`,
    `--engine-from-source`, `AIT_TESTMAP_BIN` or a pre-seeded
    `~/.aitasks/engine/`; `--no-testmap` / `AIT_TESTMAP_FETCH=0` skip the fetch
    and nothing else in setup depends on it.

15. **`assumption_git_history_is_freshness_clock` [inherited].** Git history is
    the evidence clock, not the staleness key: commit reachability decides which
    `last_pass` anchors may suppress a `STALE` row, never whether an edge is
    stale. `mtime` is never compared. A shallow clone whose anchors are outside
    fetched history reports `STALE`, not `EVIDENCED`, and remains fully
    functional.

16. **`assumption_passing_run_anchors_edges` [inherited].** A passing run of a
    test at commit C, on any host class, from an invocation without a `cause`
    and for a unit under the flake threshold, is evidence that its annotated
    edges held for the source content present in C's tree.

17. **`assumption_areas_express_suite_blast_radius` [inherited].** The blast
    radius of a high-level test is expressible as a union of area glob sets plus
    scope globs plus budget-exempt trigger globs; what that misses surfaces
    through `score` on a full run.

18. **`assumption_engine_latency_targets` [inherited, cell targets added].** On
    this repository the engine meets `select` < 200 ms warm, `scan` < 300 ms,
    `check` < 300 ms, `stale --task` < 300 ms, `stale --all` < 2 s, cold
    `select` < 1.5 s; with a 2,500-row cell table `select` stays < 400 ms warm
    and `cells --refresh` < 2 s. Pinned by committed `go test -bench` fixtures
    with a 2× regression failing `engine-check.yml`, validated before the gates
    are enabled here.

19. **`assumption_platform_matrix_sufficient` [inherited].** linux/darwin ×
    amd64/arm64 covers every target host (WSL reports Linux); any other platform
    builds from source via `--engine-from-source`.

20. **`assumption_blob_digest_is_staleness_key` [inherited].** The git blob
    digest of the covered source's content is the staleness key; file mtime and
    the annotation date are never compared — the date is display only. The blob
    id doubles as the join key into any commit's tree for the evidence join.

21. **`assumption_broad_tests_area_scoped` [inherited].** Integration, e2e and
    device tests can be described by named areas or globs whose membership
    changes rarely, so evidence-based drift (`STALE_AREA`) plus `attribute`
    widening is adequate; a calendar cadence is opt-in and off by default.

22. **`assumption_one_engine_per_framework_version` [inherited, path
    corrected].** One engine build per framework version suffices; a per-user
    versioned directory `~/.aitasks/engine/v<VERSION>/` resolves per-project
    VERSION differences without a compatibility matrix, and exact-version
    resolution in the shim never falls back to newest-wins.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

### Advantages

- **`tradeoff_computed_vs_prose`.** Selection is computed, explained and scored
  rather than remembered. The stale mark, the `EVIDENCED` class, the
  digest-anchored diff and now the per-axis reason turn "why was this selected"
  and "how much should I trust it" into printed data.
- **`tradeoff_engine_speed_enables_per_task_use`.** Sub-second
  `select`/`check`/`stale` makes selection overhead negligible against the
  shortest test and lets `check` run at every commit step. The cell join adds
  one glob match per changed file per axis and one hash lookup per cell, so a
  2,500-row table costs tens of milliseconds; the expensive question — what the
  cells *are* — is answered in `cells --refresh`, off the hot path, and
  committed.
- **`tradeoff_real_scheduler`.** Goroutines plus `flock(2)` give correct
  cross-worktree contention and a critical-path report; the shell suite and the
  pytest lane get the enforced do-not-overlap that is only a comment today, and
  `thinking_app`'s heavy-run lock and emulator allocator become declared
  resources the schedule report can reason about.
- **`tradeoff_noarch_packages_preserved`.** Homebrew, AUR, `.deb`, `.rpm` and the
  tarball ship nothing compiled; the per-arch concern is contained in one release
  job and one setup function.

### Disadvantages

- **`tradeoff_home_migration_window`.** Renaming the framework home touches every
  install in the field: 121 hardcoded `$HOME/.aitask` references across 28
  shell/Python files, 16 documentation files, the venv's absolute shebangs and two
  symlink trees. **Mitigation:** none of those 121 references is rewritten here —
  the migration moves the tree and leaves `~/.aitask` as a symlink, so they all
  keep resolving, and call sites are ported to `aitasks_home()` by later tasks
  that are already editing them. **Residual:** a sub-millisecond window between
  `rmdir ~/.aitask` and `ln -s`, during which a concurrent process that hardcodes
  the legacy path would see `ENOENT`. Narrowed by a `flock`, by doing the symlink
  immediately after the `rmdir`, and by `ait setup` refusing to migrate while
  another `ait` holds the home lock — but not eliminated, so the step prints a
  one-line warning and `--no-home-migration` skips it.
- **`tradeoff_split_home_rejected`.** The alternative — engine at
  `~/.aitasks/engine/`, everything else left at `~/.aitask/` — satisfies the
  mandate literally at zero migration risk, and was rejected: it leaves a user
  with two dot-directories one character apart holding halves of one install,
  which `ait setup --repair`, `ait engine prune`, backup advice and every
  documentation page would then have to explain forever. The migration cost is
  paid once and is reversible in two commands
  (`rm ~/.aitask && mv ~/.aitasks ~/.aitask`); the split would be paid at every
  future call site.
- **`tradeoff_axis_declaration_burden`.** Axes are a third authoring surface, and
  a project that declares them wrongly gets confidently wrong selection.
  Concretely: `thinking_app` must declare four `locale` values with their
  `res/values-*/` and font globs, a `device` axis with four values, a `screen`
  axis with a `reach:` root, and one ~60-line cell plugin. **Mitigation:**
  membership is declarative and checkable — `DEAD_AXIS_GLOB` fails a member glob
  that matches nothing, `UNCOVERED_VALUE` fails a declared value no cell occupies,
  and `axes --explain <path>` answers why one file landed where it did before
  anything is trusted; and `ANY` is the default for an unmatched file, so an
  incomplete axis over-selects rather than under-selects.
- **`tradeoff_cell_table_size`.** `_cells.yaml` for `thinking_app` is roughly
  2,500 generated rows and churns whenever a screen or a matrix is added.
  **Mitigation:** sorted deterministic writes make a single screen addition a
  ~10-line diff; `cells --refresh --diff` shows the change before it is made;
  the file is generated and reviewed like a lockfile, not authored. Enumerating
  cells at every `select` instead was rejected because it would put a
  build-adjacent plugin exec on the hot path of every gate.
- **`tradeoff_two_toolchains`.** Bash and Go in one framework. Mitigated by the
  boundary rule (parse/walk/match/digest/schedule in Go; gate ledger, task file
  and shell environment in bash; builtins exec configured commands and never
  source shell state), the `engine-check.yml` job, and Go source confined to
  `engine/` and excluded from the tarball.
- **`tradeoff_compiled_component_cost`.** The framework gains a compiled
  component: contributors touching the engine need Go, a release fails if `go
  test` fails, install gains a fetch and checksum step. Mitigated by a single
  `build.sh` matrix, `ait engine build`, and the engine being optional until a
  testmap gate is enabled.
- **`tradeoff_setup_network_fetch`.** `ait setup` gains the framework's first
  self-downloaded release asset. Mitigated by reusing the CDN URL family
  `install.sh` already uses, SHA256SUMS verification, the `.sha256` sidecar,
  `--no-testmap` / `AIT_TESTMAP_FETCH=0`, the shim never fetching on its own, and
  setup never depending on the binary for anything else.
- **`tradeoff_engine_version_skew`.** A user with several projects on different
  framework versions keeps several ~10 MB binaries under `~/.aitasks/engine/`.
  Mitigated by exact-version resolution in the shim (never newest-wins) and `ait
  engine prune` against the project registry, never a count-based prune.
- **`tradeoff_registry_directory_complexity`.** Seven tables and three generated
  files need more CLI logic than a single file would. Kept to one directory with
  one merge rule in one Go package with golden tests; the two new tables are
  declarative and generated respectively, so neither is a new hand-authoring
  surface.
- **`tradeoff_fail_closed_bootstrap_cost`.** Fail-closed enforcement means each
  repo needs an explicit waiver pass before `testmap_check` is enabled and a first
  green full run before `require_stamp` and `--strict` are turned on; a repo with
  axes additionally needs its cell plugin green before `UNMAPPED_CELL` can fail.
  Mitigated by `check --strict` off until enabled and bulk stamping via `stale
  --all --confirm-evidenced`.
- **`tradeoff_area_glob_coarseness`.** Area and scope globs are coarser than
  edges: a broad area over-selects on every edit inside it, and a scoped test
  depending on a file outside its scope is under-selected until a full run scores
  it. Mitigated by the suite budget with explicit `DEFERRED` lines, budget-exempt
  triggers, and the missing-trigger / area-too-narrow attribution path.
- **`tradeoff_broad_scope_coarseness`.** A test scoped to a large area is
  selected for any change inside it. Mitigated by ranking last at its distance,
  running only after a green unit wave, being cut first by the budget with the cut
  printed as `DEFERRED`, and the cost visible in `schedule`.
- **`tradeoff_static_scanner_overselection`.** Static scanners overselect on hot
  files and cannot see runtime coupling. Axes are the targeted answer for one
  shape of this — `ScreenFixtures.kt` makes every screen reachable from every
  fixture edit, and an axis coordinate assigned per unit sidesteps the scanner
  for that suite entirely — but the general case remains, trimmed by kind
  ranking, the budget and project scanner plugins.
- **`tradeoff_stamp_churn`.** Confirming stamps rewrites test files, so a source
  named by 72 tests could yield a 72-file diff. Mitigated: `EVIDENCED` rows need
  no rewrite until someone chooses `--confirm-evidenced`, `--confirm-source`
  makes a deliberate re-stamp one commit, only confirmation rewrites, and
  `KIND_MISMATCH` nudges such fan-out toward a scope or an axis. Cells carry no
  stamp at all, which is what keeps a 2,500-row table from multiplying this.

### Risks

- **`tradeoff_intersection_can_underselect`.** Intersection across axes is
  sharper than union and therefore *capable* of missing a real coupling. The
  structural mitigation is that a file matching no member glob of an axis
  resolves that axis to `ANY`, so the only way to under-select is an explicit,
  reviewable wrong membership — never an omission. Beyond that: `score` on a full
  run raises `axis-membership-missing`; observed memberships may only widen;
  `--cells all` is an always-available escape; and every cell row prints its
  per-axis reason, so a reader can see what a sharp selection excluded.
- **`tradeoff_batch_misreport_risk`.** A batch runner that misreports per-unit
  results corrupts attribution, cost and evidence. Mitigated by
  `units_expected`/`units_reported` reconciliation per invocation, a mismatch
  being a mechanism failure, and no line from an invocation with a `cause` ever
  anchoring. **Sharper at method granularity:** a Gradle `--tests` filter that
  matches nothing can exit 0 with zero tests, so `units_reported == 0` with
  `units_expected > 0` is treated as a mechanism failure, never a pass.
- **`tradeoff_attribution_risk`.** An agent that edits sources without
  attributing produces a map that looks current and is not. Narrowed — such a
  source shows as `STALE` in the next task touching it and as a stale mark on
  every selection — but a new coupling with no edge at all is still only caught by
  `score` on a full run.
- **`tradeoff_resource_declaration_completeness`.** Declared resources are only as
  complete as the declarations; an undeclared interference is invisible until a
  full run or a probe finds it. Serial-by-default at bootstrap means declarations
  are reviewed in the schedule report before concurrency is trusted.
- **`tradeoff_flaky_pass_anchors`.** A flaky pass anchors evidence as surely as a
  real one. Mitigated by per-run status in the ledger so `costs` exposes a flake
  rate, and a unit above `flake_threshold` is excluded from the evidence join.
- **`tradeoff_strict_version_handshake`.** The binary must match
  `.aitask-scripts/VERSION` exactly, so an `ait upgrade` on a host that cannot
  fetch leaves `ait testmap` refusing to run until a matching binary is supplied.
  Intended fail-closed behaviour; the error names the fix.
- **`tradeoff_autonomous_confirmation_weak`.** Treating a green test as evidence
  that a coverage claim still holds is weaker than review. Narrowed: the only
  autonomous confirmation is `--confirm-evidenced`, which requires a pass whose
  tree held the current bytes of the specific source, records `confirmed_by:
  <run_id>`, and is re-opened by a later `score` miss. A `STALE` row is never
  confirmed without a human.
- **`tradeoff_engine_absent_on_host`.** An unsigned macOS binary or a blocked
  download leaves a host without an engine. Mitigated by `ENGINE_MISSING` naming
  the path and repair verb, the `--engine-from-source` and `--local-engine`
  fallbacks, and the testmap gates exiting 3 (error), never skip.
- **`tradeoff_evidence_requires_reachable_history`.** The evidence join can only
  suppress a `STALE` row when the anchoring commit is reachable, so a depth-1 CI
  clone sees the precise digest verdict with no self-healing. The safe direction,
  and the reason `--strict` fails only on `STALE_PATH` and `UNMAPPED_CELL`; a
  repo-wide `stale --all --strict` job should run on a full clone or accept
  `STALE` noise.
<!-- /section: tradeoffs -->

<!-- section: bootstrap_order -->
## Per-Repository Bootstrap Order

Unchanged for a repo with no product space; two steps are inserted for one with:

```
scan → classify --suggest → areas --import-codemap → [ axes.yaml → cells/ plugin → cells --refresh ]
     → waivers → testmap_check (non-strict) → first full run → score
     → stale --all --confirm-evidenced → require_stamp: true → check --strict
     → review `schedule` → concurrency: parallel → testmap_run
```

The axis steps sit after `classify --suggest` deliberately: the grid heuristic
is what tells a maintainer a product space exists before they hand-write one.
`UNMAPPED_CELL` and `UNCOVERED_VALUE` stay non-fatal until `check --strict`,
which is the same treatment `UNSTAMPED` gets, so a half-declared axis cannot
block a repo that is still bootstrapping.
<!-- /section: bootstrap_order -->

<!-- section: open_questions -->
## Open Questions

1. Should the home migration be part of `ait setup` at all, or a separate
   explicit `ait engine home --migrate` that `setup` only *offers*? Proposed:
   part of `setup`, because a split home that nobody migrates is the outcome an
   opt-in produces — but the sub-millisecond `ENOENT` window is a real, if
   small, argument for making it a deliberate act.
2. Should `~/.aitask` remain a symlink indefinitely, or should a later release
   remove it once all 121 call sites are ported? Proposed: keep it for at least
   two minor versions, with `ait engine home` reporting how many framework files
   still hardcode the legacy path so the removal is data-driven.
3. Should the repository-local `.aitask-*` directory prefix follow the home
   rename (`.aitasks-scripts/`, `.aitasks-data/`, …)? Proposed: no — different
   blast radius (every sibling project's `.gitignore`, every doc, every path in
   every task file), and no user-visible benefit. But it does leave the framework
   spelling its own name two ways.
4. Is per-file coordinate filtering (union across the change set) right, or
   should the selector also offer whole-change-set resolution as a knob for
   reviewers who want the sharper answer? Proposed: per-file by default,
   whole-set available through `--axis` overrides only.
5. Should `axis_fanout_max` default to 6? It is an unmeasured guess; the honest
   version is to run `axes --explain` over a repo's whole source tree during
   bootstrap and pick the knee in the reach distribution, then record the number
   that was chosen and why.
6. Should an observed axis membership from `attribute` be allowed to *narrow* a
   value's member set after enough evidence? Proposed: never — widening only,
   because a narrowing mistake is silent and a widening mistake merely costs
   time.
7. Should `UNMAPPED_CELL` fail `check` or only `check --strict`? Proposed:
   `check` once a repo has finished bootstrapping, because it is the exact class
   of silent green this feature is meant to eliminate; but that makes adding a
   golden a two-step act (record, then refresh) which some workflows will find
   abrasive.
8. Does a cell row need a distance-like grade — a coordinate reached through a
   scanned dependency counting weaker than one from a declared glob — or are
   `ANY` and the budget enough?
9. Should `--confirm-evidenced` be allowed under autonomous profiles at all, or
   should autonomous runs only report and leave every re-stamp to an attended
   session?
10. Should the evidence join accept a `last_pass` from another host class when
    its tree holds the current blob (proposed: yes, any host class), or only from
    the class that will run the gate?
11. Is `unit_covers_max: 8` right, and should `check --strict` refuse rather than
    warn once a repo has finished bootstrapping (proposed: yes)?
12. Should `ait upgrade` prune `~/.aitasks/engine/` automatically when the old
    version is on no registered project, or only `ait engine prune` (proposed:
    only explicit)?
13. Should `broad_review_days` stay off by default, or is a long cadence worth
    the noise for e2e tests that never fail?
14. Should the Go module later absorb `aitask_change_surface.sh` in a new
    contract, or does keeping the intake in bash preserve a useful seam?
15. Should the deb/rpm postinstall message mention the binary fetch that `ait
    setup` performs, given the packages themselves stay `noarch`?
16. Still open from the baseline: routing of a new declared edge when no `owns:`
    matches (proposed: refuse); the CI evidence export format (JUnit alongside
    the results directory); and whether `thinking_app` keeps `verify-active` as a
    suite runner for the record/promote flow while `gradle-class` handles selected
    cells (proposed: yes — they answer different questions).
<!-- /section: open_questions -->