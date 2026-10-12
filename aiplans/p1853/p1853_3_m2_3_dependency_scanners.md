---
Task: t1853_3_m2_3_dependency_scanners.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_5_*.md, aitasks/t1853/t1853_6_*.md, aitasks/t1853/t1853_7_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-12 22:09
---

# Plan: t1853_3 — M2.3 Dependency scanners

## Context

Parent goal: M2, the registry and map model (everything that reads and writes
`aitestmap/` without running a test). This child is **M2.3, the dependency
scanners**, wave **B**. It provides the per-file dependency graph and the
static facts that later modules read:
- the closure for the selector (M4.1)
- the `static:invocation` / `static:import` / `static:package` facts, anchor
  lines and declared symbols for the seeder (M6.2), the packet writer (M7.1)
  and author corroboration (M7.4)
- the two `annotate` arms `--suggest` and `--from-body`

The selector uses this graph to choose which tests to run. **Under-selection
(a real dependency the graph misses) is the dangerous direction; every design
choice below prefers over-approximation, and any construct the scanners cannot
see through becomes an opaque file (a change to it escalates) or a
closure-only fallback edge, never a silent drop.**

Providers:
- M1.2 (`t1852_2`, `33012bff7`): `platform`, `gitx`, `testmap.CacheDir()`,
  `fixture`, `benchgate`
- M2.1 (`t1853_1`, `0d04347ab`): `registry` config, id grammar, `ErrAbsent`
- M2.2 (`t1853_2`, `f096db065`, contract at `7229dee86`): `annot` (`LangOf`,
  `Classify`, `ParseFile`, `Annotate`, the hook) and `annotateArms`

**Automation-first (user directive, 2026-10-11).** No path shipped here makes
a human action a precondition. **`--from-body` (user decision, 2026-10-12)
writes by default, through the existing annotation writer, recording the
automated actor and the scanner provenance; `--dry-run` previews; there is no
mandatory confirmation step.**

## Step 0 — Reality check (EXECUTED 2026-10-12, main @ 13a8751d5)

### 1. Sources re-read

- the proposal's Module Map row M2.3
- *Dependency scanners (M2.3)*
- the *Annotation scanner* arms paragraph
- *The origin table* and "Where the static facts come from"
- *Selector (M4.1)*: test-dep at distance 1, `ESCALATE` on opaque files, the
  android-res before blob
- *Seeder (M6.2)*: direct facts only
- *Where state lives*: the dependency cache
- `assumption_static_granularity_v1`, `assumption_kotlin_scanner_fail_closed`,
  `tradeoff_static_scanner_overselection`
- *Named follow-ups*: a versioned plugin contract and symbol-level
  attribution, both not v1
- the *Cross-module interfaces* "scanner facts" row
- the brainstorm lineage: n005 and n006 *Selection: fail-closed scanners*

An independent plan review (Plan agent) then challenged the draft for
fail-open paths. Its findings are folded in below.

### 2. Providers as they exist now

| provider | landed by | state in tree |
|---|---|---|
| `platform.CacheRoot`, `NewGroup`, `PoolCap` 8 | t1852_2 `33012bff7` | as the note said |
| `testmap.CacheDir()` | t1852_2 | `${XDG_CACHE_HOME:-$HOME/.cache}/aitasks/testmap`; an error when neither variable is absolute |
| `gitx.Repo.ListFiles` | t1853_2 `f096db065` | git-visible files, **including tracked files deleted from the working tree**; any stderr output is an error |
| `gitx.BlobDigest`, `Repo.ObjectFormat` | t1852_2 | in-process sha1 / sha256 |
| `annot.LangOf`, `annot.Classify` | t1853_2 | line classes `Code` / `Comment` / `Literal`, plus `Uncertain`; no tokens; **no version constant** |
| `annot` no-follow reader (`readNoFollow`, `openDir`) | t1853_2 | unexported |
| `annot.ParseFile`, `File.Unit`, `Unit.Opener`, `File.Lines` | t1853_2 | block ownership by position |
| `annot.Annotate`, `Restamp`, `Actor` | t1853_2 | all-or-nothing stamping. `Restamp` has no provenance field. The default actor is `agent:$AIT_AGENT_STRING`, else unspecified |
| `annotateArms` | t1853_2 | in `cmd/ait-testmap/annotate.go`; an unregistered arm → `NOT_IMPLEMENTED:annotate --<arm>`, exit 64; `TestStampVerbUsage` pins all three as stubs |
| `registry.Config` | t1853_1 | `SymbolScanners`, `HelperRoots`, `Excluded`; **no "source roots" key** |
| `go` toolchain | — | go1.27.1 here; `go list -e -deps -json ./...` over `goengines/` takes ≈70 ms |
| M3.1 / M3.2, M4.1, M6.2, M7.x | — | not landed; their parents (t1854, t1855, t1857, t1858) are not decomposed yet. M3.2's `bash-file list --invocations` overlaps the bash facts |

**Repository shape** (the probe targets):
- 432 bash tests: 378 bind `SCRIPT_DIR` via `$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)`, 349 bind `PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"`, 39 embed Python (`python3 -c` and `python3 - <<EOF`)
- 352 Python tests: bootstraps such as `sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))`
- ≈1,342 scannable files, ≈24 MB

Parent anchors re-verified:
- module path, `go 1.26.0` / toolchain `go1.27.1`
- the allowlist (`yaml.v3`, `doublestar/v4`, `x/sync`)
- the Invariant 4–5 tripwire: non-test files only. `os/exec` makes the git
  write verbs (`add`, `rm`, `tag`, `reset`, …) and the agent names forbidden
  literals, so `os/exec` is confined to `golist.go` and `plugin.go`

### 3–4. Differences and decisions

| # | proposal says | coarse plan says | repository has | decision |
|---|---|---|---|---|
| D1 | `go list -deps -json`, cached under a key that changes with any Go source's import set plus `go.mod` / `go.sum` | "decide the key" | — | **Adapt — the key, and why.** One SHA-256 per module, over:<br>• for every Go module in the repository plus `go.work` (in-repo `replace` and workspace targets count): the `go.mod` / `go.sum` / `go.work` bytes<br>• **every `.go` file `go list` reads, not only universe files** (review finding: a gitignored, generated or `exclude:`d Go file is still a package input, and a same-name edit of its imports changes the graph). The walk is **not** the `./...` discovery walk (second review: `go list -deps` also loads a `_bridge` or `testdata` package that a local package imports directly, and those directories are exactly what `./...` skips). The module tree is walked **on disk over every directory**. The only skips are directories whose name begins with `.` (an import path element cannot begin with a dot, so nothing can import them) and nested-module directories (they are keyed as their own module and are part of this key through the every-module rule above). `_*`, `testdata` and `vendor` are walked. Symlinked directories are not followed. Every `.go` file found contributes its header: path, package clause, every `//go:` directive line (`build`, `embed`, …), the legacy `// +build` lines, the cgo preamble when it imports `"C"`, and the sorted import paths. The header is computed **from the file's current bytes** (blob id → cached `Raw`, rescanned on a miss), so an ignored file is never trusted by name<br>• **membership names:** for every directory holding a `.go` file, the names of its non-Go files (C/H/S, `.syso`, …); and for every package with a `//go:embed` directive, the **recursive** listing (relative path of every file and directory) of its whole directory subtree, so a file added under an embedded directory changes the key<br>• **a post-check that keeps the claim honest:** after `go list` runs, every local package directory it reports (`Module.Main`, or `Dir` inside the repository) must lie in the walked set, and every `EmbedFiles` entry must lie in a recursively listed subtree. Otherwise (a symlinked package directory, an untracked input form) the result is used for this scan but **never cached**, and a `Problem` names the input (conservative invalidation)<br>• the environment that selects packages: `GOOS`, `GOARCH`, `CGO_ENABLED`, `GOFLAGS`, `GOWORK`, `GOEXPERIMENT`, `GOTOOLCHAIN`, the resolved `go` binary path and mtime<br>Why: a `go.sum`-only key misses a new local import (proposal Deviation 7). The headers come from the blob cache, so the warm path execs nothing; only an import-set or membership change re-runs `go list`. **Results with a local error are never cached.** Stored as `deps/golist/<key>.json` |
| D2 | the go scanner gives package membership | — | — | **Adapt.** All Go graph data comes from `go list`; the granularity is the package (`assumption_static_granularity_v1`).<br>• **membership:** `GoFiles` + `CgoFiles` + `IgnoredGoFiles` (a tag-excluded file still belongs, as an over-approximation); `TestGoFiles` / `XTestGoFiles`; `EmbedFiles` and C / H / S files (closure-only); the package's `testdata/**` (closure-only from its test files)<br>• **edges:** same-package files; `XTestGoFiles` → `TestGoFiles` (`export_test.go`); local packages from `Imports` / `TestImports` / `XTestImports`<br>• **run:** `go list -e -deps -json -mod=readonly ./...` (command-line `-mod` overrides the user's `GOFLAGS`, whose other flags such as `-tags` are kept; `-mod` is left alone when `vendor/modules.txt` exists), with `GOPROXY=off`<br>• **failures:** a third-party `DepsErrors` (module not downloaded) is ignored — it is never a repository file. A **local** package with `Error`, or an unresolved import under the module path, makes that package's files opaque (`go-list-failed`); a `go list` that fails outright marks the whole module (`go-list-failed`, or `go-unavailable` when there is no `go` binary). Fail closed, never cached |
| D3 | `$SCRIPT_DIR` / `$PROJECT_DIR` forms "resolved against every source root"; Python "through the file's own `sys.path` bootstrap" | — | no source-root concept anywhere | **Adapt + record in the proposal.** **Source roots** = the repository root ∪ every directory that some scanned file's bootstrap resolves to (bash directory-valued variables, Python `sys.path` entries), as a union over the universe. Resolution is per file first. A ref with an unresolvable base, or a known base whose candidate is not in the universe, is retried against every source root, plus the file's directory and its parent. Every such hit is a **closure-only** edge with `via` = `fallback`: it widens selection but is never seeded |
| D4 | forward deps cached per source blob at `deps/<blob-sha1>.json`, inverted in memory | — | sha256 repositories exist; `annot` has no version | **Adapt.** The cache stores only **path-independent syntactic facts** (`Raw`). Resolution and every **path-dependent** opaque rule (`generated`, `java-unscanned`) run in memory on every scan.<br>• **key:** the blob id under the repository's object format (as stamps do, M2.2 D13)<br>• **entry:** `{v, lang, raw}`; `v` = the deps schema version; a mismatch or a corrupt entry is rescanned and overwritten<br>• **`annot` changes:** a fingerprint test pins `annot.Classify` over a fixed corpus. If M2.2's lexers change, it fails and names the schema constant to bump, so stale classifications cannot survive silently<br>• **writes:** atomic (temp file + rename); an unavailable cache only means the scan runs uncached (a `Problem`, never an error)<br>• eviction is a follow-up (noted) |
| D5 | the `--suggest` / `--from-body` arms are "named extensions of M2.2's `internal/annot`" | same | `annotateArms` lives in `cmd/`; `deps` imports `annot` | **Adapt + record in the proposal.** The engines live in `internal/testmap/deps` (an `annot` → `deps` import would be a cycle) and register into M2.2's extension point `annotateArms` from a new M2.3-owned file, `cmd/ait-testmap/annotate_deps.go`. `TestStampVerbUsage`'s stub loop shrinks to `--author` |
| D6 | `--suggest` "proposes covers lines from the closure"; `--from-body` "seeds covers" | — | `Restamp` carries no provenance | **Adapt (user decision for `--from-body`).** `--suggest` is **read-only** output. `--from-body` **writes** through the rewriter. The default actor is `agent:$AIT_AGENT_STRING`, else `auto` (automated, never unspecified, never human); an explicit `--by` wins. Scanner provenance goes through **one additive named extension of M2.2's `annot`**: `Restamp.Origin string` (json `origin,omitempty`), and `AnnotateWith(ctx, root, test, sources, actor, AnnotateOptions{Origin, Snapshot})`, which `Annotate` now calls with zero options (no behaviour change). `--from-body` passes `scanner:from-body`; M2.6's hook can record it. `--dry-run` writes nothing.<br>**Write snapshot (review finding):** `FromBody` infers from one reading of the test file and passes that reading's `File.Snapshot()` as `AnnotateOptions.Snapshot`. `AnnotateWith` then:<br>(a) refuses with `*ConflictError{Reason: "snapshot"}` when its own reload differs<br>(b) uses the **inference** snapshot as the `EditSet.Snapshot` that `Apply` re-checks inside its guarded write (read → compare → temp write → concurrent re-read → rename)<br>So the whole window from inference to rename is covered by Apply's transaction, not by a separate preflight comparison. On a snapshot conflict the `--from-body` glue **recomputes once** (fresh inference, fresh snapshot) and retries; a second conflict is `REWRITE_CONFLICT` (75) with nothing written |
| D7 | Kotlin opaque: inline functions, `const val`, DI bindings, `Class.forName` / `::class.java`, generated / KSP sources, an unreadable file | — | — | **Adapt (closed list made concrete).** Content rules (in `Raw`): `inline-fun`, `const-val`, `di` (`@Module @Provides @Binds @Inject @Component @Subcomponent @InstallIn @EntryPoint @HiltViewModel @AndroidEntryPoint @HiltAndroidApp`), `di-koin` (an `org.koin.` import), `reflection` (`Class.forName`, `::class.java`), `untokenizable`. Path and config rules (resolve phase): `generated` (a `build/generated/` prefix, or a path segment `generated`, `ksp` or `kapt`), `java-unscanned` (`.java` files are indexed by package and file stem so Kotlin imports of them resolve, but their own deps are unscanned), `dynamic-resource` (`getIdentifier(`; only when android-res is enabled), `gradle-dynamic` (D8). For every language: `unreadable`; plus `uncertain` for a Python / bash file `Classify` cannot trust *and* the scanner cannot parse. Each reason is one row of `opaqueRules`; the test seam `disableOpaque` drives the red proofs |
| D8 | the Gradle module graph | — | — | **Adapt (the full minimum graph, as the task requires; review finding).**<br>• **Logical names → directories:** the textual parse of the root `settings.gradle(.kts)` takes `include(":a", ":b:c")` / `include ':a', ':b'` string literals (`:b:c` → `b/c` by default) and `project(":x").projectDir = file("rel")` / `new File(settingsDir, "rel")` overrides. A directory holding a `build.gradle(.kts)` that no include names is also a module (name derived from its path), and so is the root project `:`. `GradleModule{Name, Dir, BuildFile, Deps}`; `ModuleOf(path)` is the deepest module directory.<br>• **Dependencies:** each module build file's `project(":x")` references (any configuration: `implementation`, `api`, `testImplementation`, `androidTestImplementation`, …; also `projects.x.y` typesafe accessors, mapped through the include names) → `Deps`, resolved through the logical names.<br>• **Edges:** every Kotlin / Java source gets closure-only edges to its own module's build file, to the **build files of every module in its module's transitive `Deps`** (a dependency's build change can change its outputs), and to the build inputs (root settings, `gradle.properties`, `gradle/libs.versions.toml`, `buildSrc/**`).<br>• **Conservative fallback:** an `include` / `projectDir` / `project()` argument that is not a string literal, or a `project()` name that matches no module, records a `Problem` and marks the **build file containing it** opaque (`gradle-dynamic`; escalate rather than claim a narrow module graph). A module whose dependencies cannot be read (a dynamic dependency block) gets `Deps = every module` (over-approximation), so M4.1's runner sets widen rather than narrow |
| D9 | plugins under `aitestmap/scanners/`, one JSON line per file `{file, deps, opaque?, reads?}` | — | — | **Adapt (v1 contract made concrete).**<br>• **which files run:** every regular, executable, non-symlink file directly under `aitestmap/scanners/`<br>• **invocation:** once per scan, cwd = root, stdin = the universe one path per line, **30 s timeout**<br>• **output:** each stdout line is `{"file", "deps", "opaque"?, "reads"?}`; paths must pass `registry.CheckPath` and be in the universe; `reads` must be valid globs<br>• **refusals:** unknown keys, a malformed line, a non-zero exit or a timeout → `*PluginError` → `SCANNER_ERROR:<plugin>\|<detail>`, exit 3<br>Output is not blob-cached. Edges are closure-only, `via` = `plugin:<name>` |
| D10 | the opt-in `android-res` symbol scanner | — | `symbol_scanners: []` | **Adapt.** Enabled by `symbol_scanners: [android-res]`; any other name is an error. `Raw` always records `R.string.<k>` / `R.plurals.<k>` / `"<k>".localized()`; `FileFacts.Keys` exposes them only when enabled. A `.java` file then gets `Keys: ["*"]` (unscanned → it names every key).<br>• `ResKeys(xml)`: over any `res/values*/*.xml`, the digest of each `<string>` / `<plurals>` element **including its attributes**<br>• `ChangedKeys(before, after)`: a nil side means every key of the other |
| D11 | bash literal invocation facts | — | 39 tests embed Python | **Adapt (review finding).**<br>• **lines:** every line except `Comment` lines is scanned — `Literal` (heredoc / string) lines too, because embedded commands are real; an `Uncertain` file has every line scanned<br>• **embedded Python:** `python3 -c '…'` / `python3 - <<EOF` bodies, and any `import x` / `from x import y` statement on a non-comment line, go through the Python import extractor and resolve against the source roots (closure-only, `via` = `embedded-python`); `-m pkg.mod` is a module ref<br>• **non-literal words** (`"$dir/lib/x.sh"` with an unknown `$dir`, `${X:-…}/x.sh`, `$1/…`): the literal tail after the last variable is suffix-matched against the universe (closure-only, `via` = `suffix`) |
| D12 | — | — | `annot.Source`'s universe | **Adapt (same universe).** `ListFiles`, minus `exclude:`, minus files missing from the working tree, minus symbolic-link paths and non-regular files. Read through `os.Root` with a per-component `Lstat` check; this read-only path does not need M2.2's race-hardened writer handles (recorded), so no `annot` reader is exported |
| D13 | facts are "exposed to `internal/seed`" | — | no verb | **Adapt.** The Go API `deps.Scan`, documented under Design. The arms are the only CLI surface. Note to M4.1: the closure must be walked transitively (`Closure` with `max <= 0`); sourcing and import chains are deeper than distance 2 |

### 5. Notes

Sent after the code commit (post-phase `interface_notes_downstream`).

### 6. Ownership

- **Owned:**
  - `goengines/internal/testmap/deps/**` (new)
  - `cmd/ait-testmap/annotate_deps.go` and `annotate_deps_test.go` (new)
  - two `bench/baseline.txt` lines
- **Named extensions** (minimal):
  - `annot/hook.go`: the additive `Restamp.Origin` field
  - `annot/stampverbs.go`: `AnnotateWith` and `AnnotateOptions{Origin, Snapshot}`, with `Annotate` delegating to it
  - the arm stub loop in `TestStampVerbUsage`
  - README *Layout* / *Interfaces* rows
  - an additive proposal paragraph and Line-protocol index entries

## Design — package `goengines/internal/testmap/deps`

### Public API (`deps.go`, `graph.go`)

```go
type Origin string // "static:invocation" | "static:import" | "static:package"; "" = closure-only (never seeded)
type Dep struct {
    Target string; Line int // anchor line in the scanned file (0 = package-level)
    Origin Origin
    Via    string // source|exec|path|fallback|suffix|embedded-python|import|from-import|init|conftest|package|same-package|
                  // xtest|embed|testdata|star-import|fq-ref|package-fallback|module-build|build-input|plugin:<n>
}
type Symbol struct{ Name, Kind string; Line int }
type FileFacts struct {
    Path, Lang string; Deps []Dep; Opaque string; Reads []string
    Symbols []Symbol; Keys []string; Unresolved []string // literal refs/imports that matched no repo file (diagnostic)
}
type GradleModule struct{ Name, Dir, BuildFile string; Deps []string /* logical names, transitive closure via Graph */ }
type Options struct{ Config registry.Config; CacheDir string /* "" = testmap.CacheDir()/deps */; Uncached bool }
type Problem struct{ Path, Reason string }
type Reach struct{ Path string; Distance int; Via string /* first hop */ }

func Scan(ctx context.Context, root string, o Options) (*Graph, error)
func (g *Graph) Files() []string
func (g *Graph) Facts(path string) (FileFacts, bool)
func (g *Graph) Static(path string) []Dep            // direct deps carrying an Origin — what the seeder reads
func (g *Graph) Reverse(path string) []string        // files with a direct dep on path
func (g *Graph) Closure(path string, max int) []Reach // forward BFS; max <= 0 = unbounded
func (g *Graph) Opaque(path string) string
func (g *Graph) Modules() []GradleModule
func (g *Graph) ModuleOf(path string) (GradleModule, bool)
func (g *Graph) Problems() []Problem
func ResKeys(xml []byte) (map[string]string, error)
func ChangedKeys(before, after []byte) ([]string, error)
type PluginError struct{ Plugin string; Line int; Reason string } // Line() → SCANNER_ERROR:<plugin>|<detail>
```

Cut as having no v1 consumer yet (the notes say so):
- `ReverseClosure` (M4.1 builds it from `Reverse`)
- `Relation` (M7.4 uses `Closure`)
- `OpaqueReasons` (M4.4)

### Pipeline (`scan.go`)

1. Validate `cfg.SymbolScanners`, read the object format, build the universe
   (D12).
2. Pick the scanner by path:
   - `annot.LangOf` (bash / python / go / kotlin; `.kts` Gradle scripts are
     Kotlin too)
   - `.java` → java index
   - the D8 Gradle files → build inputs
   - `res/values*/*.xml` → resource keys (only when android-res is on)
3. **Raw phase:** `platform.NewGroup(ctx, 0)` workers. For each file: read,
   compute the blob id, look up the cache, else `scanRaw(lang, data)` and a
   cache write.
4. **Go phase:** per module (D1 / D2).
5. **Plugin phase:** D9.
6. **Resolve phase**, in memory:
   1. source roots (D3)
   2. the Kotlin / Java index: package → files; (package, top-level name) →
      files, covering classes, objects, interfaces, functions, extension
      functions, properties and typealiases
   3. modules
   4. per-file resolve → `FileFacts`, including the path / config opaque rules
   5. the reverse index
   6. a deterministic sort
7. **Every file's bytes are hashed on every scan; there is no stat-based
   freshness shortcut** (review finding). Size + mtime + inode survive a
   same-size, timestamp-restoring edit, which would reuse stale `Raw` facts
   and silently drop dependencies. A budget shortfall is measured and
   reported (step 12), never traded for correctness. Allowed speed-ups keep
   content hashing: the parallel pool, one read per file, a packed cache
   file.

### bash (`bash.go`)

**Raw:**
- `Assigns[]{Var, Expr, Line}`
- `Refs[]{Line, Expr, Via}`
- `PyImports[]{Module, Line}`
- `Symbols`

A path expression is `{Base: dir-of-file|cwd|var:<NAME>|lit, Parts, Tail}`.

**Assignment forms:**
- `$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` and `$(dirname "$0")` →
  `dir-of-file`, with an optional `/..` tail
- `$(cd "$Y/.." && pwd)`
- `"$Y/rel"`, `"${Y}/rel"`
- `$PWD/…`, `$(pwd)/…` → `cwd` (the repository root)
- anything else is *unknown*

**Refs:**
- every word with a `/` or a script extension
- the right-hand side of an assignment that resolves to a file (`LIB=".../agent_string.sh"`; then `source "$LIB"`)
- a bare `$VAR` bound to a file

**Symbols:**
- `name()` / `function name` → `func`
- top-level `case` arm words → `verb`
- `[A-Z][A-Z0-9_]{2,}:` tokens inside `echo` / `printf` arguments → `token`

**Resolve:**
1. A variable is evaluated against **every** binding it has in the file, not
   only the last one before the ref (review finding), so all candidates
   count.
2. Universe hits other than the file itself → `static:invocation`.
3. Misses go to the D3 fallback (closure-only).
4. Non-literal words go to the D11 suffix match.

Source roots contributed: every resolved directory-valued binding.

### python (`python.go`)

A tokenizer (every string prefix, triple quotes, comments, brackets,
continuation) builds logical lines.

**Imports:** `import` / `from` statements at **any indentation** — inside
functions, `try` blocks and `if TYPE_CHECKING` too.

**Raw:**
- `Imports[]{Module, Names, Level, Line}`
- `Boot[]{Expr, Line, Op}`
- `Strings[]{Text, Line}`: path-shaped literals and `Path / "…"` chains
- `Dynamic`: `importlib` / `spec_from_file_location` / `__import__` /
  `import_isolated` calls, with their string arguments
- `Symbols` (top-level `def` / `class`)

**Bootstrap evaluator:**
- `__file__`
- `Path(x)` / `pathlib.Path(x)`
- `.resolve()` / `.absolute()`
- `.parent`, `.parents[N]`
- `/ "lit"`
- `os.path.dirname|abspath|realpath|join(…)`
- `str()` / `os.fspath()`
- string literals
- `NAME = expr` bindings
- `for v in (a, b): sys.path.insert(0, str(v))`
- anything else is unresolved

**Resolve:**
1. **`sys.path` is modelled faithfully** (review finding), as an ordered
   list:
   - it starts as `[the file's directory, the repository root]` (the script
     directory is `sys.path[0]`; the root stands for the cwd / pytest
     rootdir)
   - each top-level bootstrap statement is applied in file order:
     `insert(0, x)` prepends, so repeated `insert(0, …)` calls end up in
     reverse order and an inserted `src` **precedes** the file's own
     directory; `insert(i, x)` with a literal `i` inserts at `min(i, len)`;
     `append(x)` appends; the `for v in (a, b)` form applies each element in
     order
   - a bootstrap whose effect is **uncertain** sets the file's precedence to
     uncertain. Uncertain means: an unresolved path, a non-literal index, or
     a statement under control flow (indented under `if` / `try` / `def` /
     any loop other than the supported literal `for`)
   - **imports are resolved in statement order, not against the final path**
     (second review). The top-level straight-line statements are walked
     once, in file order:
     - a bootstrap mutates the modelled list
     - an `import` / `from` resolves against the list **as it stands at that
       line**, and records the module in a modelled `sys.modules`
     - the modelled `sys.modules` is keyed by the **exact fully qualified
       module name** (third review). A later import of the *same name*
       resolves to the same file, whatever paths were inserted since. A
       submodule is its own entry: `import pkg` records only `pkg` →
       `pkg/__init__.py`.
     - `import pkg.child` / `from pkg import child` with `pkg` already
       recorded and `child` not: the child is resolved **inside the recorded
       package's own directory** (its `__path__`: the directory of the
       recorded `pkg/__init__.py`) as `child.py` or `child/__init__.py`, and
       recorded as `pkg.child` — a distinct dependency. When `pkg`'s
       location is uncertain (several candidates, a namespace package, an
       uncertain import), every candidate child under every candidate
       package directory is kept closure-only, with no claimed winner.
     - `from pkg import name`, where `name` may be an attribute of `pkg`
       rather than a submodule: `pkg/__init__.py` is always a dep, and
       `pkg/name.py` (or `name/__init__.py`), when it exists, is a dep too
     - an import that is not top-level straight-line (inside `def` / `if` /
       `try` / a loop, or after the first uncertain bootstrap) has uncertain
       precedence; it is resolved against every list state the file reaches
       (the union), and its winner is not claimed (rule 2)
   - no interpreter is modelled beyond this; anything else is uncertain
2. For each import, **every** candidate (`D/a/b.py`, `D/a/b/__init__.py`,
   `D/a/b/c.py`) in every search directory is a hit:
   - when precedence is certain, the first hit in the modelled order →
     `static:import`; the others → closure-only
   - when precedence is uncertain and there is more than one candidate, every
     candidate is closure-only, with no claimed static winner; a single
     candidate is still `static:import`, since nothing competes with it
3. The parent package `__init__.py` files → closure-only (`init`).
4. Ancestor `conftest.py` files up to the root → closure-only (`conftest`).
5. **A miss always tries the source roots** (not only when the bootstrap was
   unresolved), closure-only, so paths added by `conftest` / `PYTHONPATH` /
   pytest `pythonpath=` still connect.
6. String literals and `Dynamic` arguments that resolve to universe files →
   closure-only (`path`).

### go (`golang.go`, `golist.go`)

**Raw:**
- `Package`
- `Directives`
- `CgoPreamble`
- `Imports`
- `Symbols` (exported funcs, types, vars and consts; methods as
  `Type.Method`)

A parse error falls back to a token scan for the header.

**Facts:**
- `_test.go` → `static:package` deps on its package's `GoFiles` (plus
  `CgoFiles` / `IgnoredGoFiles` non-test files), anchored at its package
  clause
- every other D2 edge is closure-only

### kotlin, java, gradle (`kotlin.go`, `kotlinlex.go`, `gradle.go`)

**`kotlinlex`:**
- tokens: identifiers, `.`, `::`, `@`, keywords
- comments are skipped, including nested `/* */`
- string contents are skipped; `${…}` / `$ident` template code is kept as code
- an unterminated construct → `untokenizable`

**Raw:**
- `Package`, `Imports[]{Path, Alias, Star, Line}`
- `Decls[]{Name, Kind, Line}` (top-level)
- `Refs[]{Chain, Line}` (dotted chains)
- `Opaque` (content rules, the first in table order)
- `Keys`

**Imports** resolve by **longest-declared-prefix walk**. Find the longest
prefix of the import path that is a repository package P whose next segment N
is a top-level declaration in P → the declaring file(s). This covers nested
members (`Outer.Inner.CONST`), enum entries, companion members and
`import P.Obj.*`.
- An import, or an fq-ref chain, inside a repository package that matches no
  declaration → **every file of that package**, closure-only
  (`package-fallback`; review finding), and it is recorded in `Unresolved`.
- A star import of a repository package → every file of the package
  (closure-only).
- Same package → every other file of the package, closure-only
  (`same-package`; same-package facts are excluded from seeds).
- Explicit-import and fq-ref hits → `static:import`.

**Java index:** `package x.y;` plus the file stem; opaque `java-unscanned`.

**Gradle:** D8.

### android-res (`androidres.go`)

D10. `encoding/xml`. The element digest is a SHA-256 of the canonical
re-serialisation (name, sorted attributes, inner XML).

### plugins (`plugin.go`)

D9. Stdout has a 1 MiB line cap; the first stderr line becomes the error
detail.

### `--suggest` / `--from-body` (`suggest.go`, `frombody.go`)

```go
type Suggestion struct{ Source string; Origins []string; Anchor string; Via string; Covered bool }
func Suggest(ctx context.Context, root string, test registry.ID, o Options) (refused string, s []Suggestion, err error)
type BodyRef struct{ Source, Symbol string; Line int }
func FromBody(ctx context.Context, root string, test registry.ID, o Options) (refused string, refs []BodyRef, snapshot string, err error)
// snapshot = annot.File.Snapshot() of the very bytes the refs were inferred from; the glue hands it to AnnotateWith (D6)
```

**`Suggest`** ("from the closure"):
- Requires `aitestmap/` (`registry.ErrAbsent`).
- Refusals: `excluded`, `missing`, `not-a-file`, `no-scanner`.
- Lists the test file's direct deps. A dep under `helper_roots` is walked
  through, and its own direct deps are listed with `via` = `helper:<path>`;
  the helper itself is not listed.
- Grouped by source, with origins merged (`closure` when there are none), the
  first anchor kept, and the test file excluded.
- `Covered` comes from `annot.ParseFile` on the target block.

**`FromBody`:**
- Kotlin only (`not-kotlin`).
- Requires a member (`no-member`) and its block (`no-member-block`).
- Body = from the member's opener to the next opener or EOF.
- The body is re-tokenised from the file bytes (not cached). Identifiers and
  chains resolve through explicit imports / aliases, same-package
  declarations, star-imported packages and fq-refs.
- Excluded: the test file, `helper_roots` matches, and non-universe files.
- Nothing resolves → `no-symbols`.

### Verb glue `cmd/ait-testmap/annotate_deps.go`

`init` registers `annotateArms["--suggest"]` and `annotateArms["--from-body"]`.

**`annotate --suggest [--json] <test>[#<member>]`:**
- Output:
  - `SUGGEST:<test>|<source>|<origins csv or closure>|<anchor>|<via>|<new|covered>`, sorted
  - `SUGGESTS:<new>|<covered>`
- `SUGGEST_REFUSED:<test>|<reason>`, exit 1; exit 0 otherwise.

**`annotate --from-body [--by <actor>] [--dry-run] [--json] <test>#<member>`:**
- Output:
  - `FROM_BODY:<test>|<source>|<symbol>|<line>`
  - then (not with `--dry-run`)
    `annot.AnnotateWith(…, actor, AnnotateOptions{Origin: "scanner:from-body", Snapshot: <the inference reading's snapshot>})`,
    printed through the existing `printStamps`
  - a snapshot conflict recomputes once (D6); a second conflict →
    `REWRITE_CONFLICT` (75)
- The default actor is D6's.
- `FROM_BODY_REFUSED:<test>|<reason>`, exit 1.

Exits stay within `stampExits`. A `*PluginError` prints its own line (3).

## Implementation steps

1. **`annot` extension:**
   - `Restamp.Origin`, plus `AnnotateWith(…, AnnotateOptions{Origin, Snapshot})`
     with `Annotate` delegating with zero options
   - `stampverbs_test.go` cases:
     - the hook receives `Origin` from `AnnotateWith`, and `""` from
       `Annotate`
     - an `AnnotateOptions.Snapshot` that differs from the current file →
       `*ConflictError{snapshot}`, nothing written
     - a file changed **after** `AnnotateWith`'s reload and before
       `Apply`'s read (through the existing `beforeRename`-style seam, or a
       new `beforeApply` seam) → conflict, because the `EditSet` carries the
       inference snapshot, not the reload's
   - every existing `annot` test unchanged and green
2. `deps/cache.go` + `cache_test.go`:
   - round trip
   - a stale `v`, corrupt JSON and a lang mismatch each rescan
   - an unwritable directory still scans and reports a `Problem`
   - `Uncached` writes nothing
   - **the `annot.Classify` fingerprint test** (D4)
3. `deps/kotlinlex.go` + tests: token tables, nested comments, raw strings
   with templates, char literals, `untokenizable`.
4. `deps/bash.go` + `bash_test.go`:
   - every assignment form
   - `.` / `source` / exec / argument refs
   - the `SCRIPT_DIR` → `PROJECT_DIR` chain, and the
     `SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"` rebinding: every binding
     tried
   - `LIB=…; source "$LIB"`
   - the unknown-variable source-roots fallback (closure-only)
   - the suffix match for `"$d/lib/x.sh"`
   - heredoc / `-c` embedded Python imports and paths **are** found
   - comment lines are ignored
   - the symbols
5. `deps/python.go` + `python_test.go`:
   - each bootstrap form (`parents[1]`, the `for` loop,
     `os.path.join(os.path.dirname(__file__), "..", "x")`)
   - every hit kept, the first one seeded
   - **precedence:**
     - a shadowed module: `tests/subject.py` and `src/subject.py`, with
       `sys.path.insert(0, src)` → `src/subject.py` is the `static:import`
       (what Python loads; checked against a real `python3` in the test when
       available), and `tests/subject.py` is closure-only
     - two `insert(0, …)` calls → reverse order
     - `insert(1, …)`, `append`
     - a bootstrap under `try:` / `if` → uncertain → no static winner among
       several candidates, every candidate still an edge
     - **import before insert, and a repeated import** (second review):
       `import subject`; `sys.path.insert(0, src)`; `import subject`. Both
       statements resolve to `tests/subject.py` (what Python loads;
       cross-checked with a real `python3` when available). `src/subject.py`
       stays a closure-only candidate and is never `static:import`
     - an import inside a function after an insert → uncertain, union of
       states, no claimed winner
     - **submodules are distinct cache entries** (third review): `import
       pkg`, then `from pkg import child`, then `import pkg.child` — `pkg/__init__.py`
       and `pkg/child.py` are both deps of the test (`pkg/child.py` resolved
       inside the loaded `pkg`'s directory, even after a later `insert(0, …)`
       that would shadow a different `pkg`), cross-checked with a real
       `python3` when available
   - `__init__` and `conftest` edges
   - a miss → fallback (closure-only)
   - imports inside a function and inside `try` are found
   - an import inside a string or docstring is not an import
   - the `.sh` literal and `spec_from_file_location` edges
6. `deps/golang.go`, `golist.go` + `golang_test.go` (fixture modules with
   `go 1.21`, `GOTOOLCHAIN=local`):
   - membership, including an external `_test` package, `export_test.go`,
     `IgnoredGoFiles` behind a tag, embed, testdata
   - local import edges
   - a local syntax error → `go-list-failed` for that package only; never
     cached
   - a missing third-party module → no opaque
   - `go` absent from `PATH` → `go-unavailable`
   - a warm re-scan execs no `go` (hook counter)
   - **red-proved invalidation:** add `import "<mod>/b"` to `a/a.go` with
     `go.mod` / `go.sum` byte-identical, then re-scan. `b/b.go` must be in
     `Closure("a/a_test.go")`. The same sequence with `goKeyFunc` swapped for
     a `go.sum`-only key must **miss** it. Both are asserted.
   - the same red/green pair for a new file in an existing package, a
     `//go:build` flip, and a `//go:embed` pattern change
   - **an ignored generated Go file (review finding):** `a/zz_gen.go` is
     listed in `.gitignore` (outside the universe) and imports `<mod>/b`.
     Prime the warm cache, then rewrite `zz_gen.go` to import `<mod>/c`
     instead, with every module file, every universe file and every file
     name unchanged. The re-scan must re-run `go list` and show `c/c.go` (not
     `b/b.go`) reachable from `a/a_test.go`. A key built from universe headers
     plus on-disk names (the pre-review design, through `goKeyFunc`) must
     miss it — the red
   - **an underscore package imported directly (second review):** `a/a.go`
     imports `<mod>/_bridge`, and `_bridge/bridge.go` imports `<mod>/b`.
     Prime the warm cache, then change `_bridge` to import `<mod>/c`, with
     `go.mod`, `go.sum`, `a`'s headers and every file name unchanged. The
     re-scan must show `c/c.go` in `Closure("a/a_test.go")`. A key built from
     a `./...`-rules walk (through `goKeyFunc`) misses it — the red
   - **recursive embed membership (second review):** `a/a.go` has
     `//go:embed assets` with `a/assets/first.txt`. Prime the cache, then add
     `a/assets/second.txt` with no Go file and no package-level entry
     changed. The re-scan re-runs `go list`, and `a/assets/second.txt` is a
     closure-only `embed` dep of `a`'s files. A key with per-directory
     (non-recursive) names misses it — the red
   - **post-check:** a package directory reached through a symlinked
     directory → the result is used but not cached (the next warm scan
     re-runs `go list`), and a `Problem` is recorded
7. `deps/kotlin.go`, `gradle.go` + `kotlin_test.go`, `opaque_test.go`:
   - explicit, alias, star, same-package and fq-ref edges
   - the nested-member and companion / enum import walk
   - `package-fallback` for an unresolvable repository import
   - the Java index
   - Gradle:
     - `include` logical names
     - a **`projectDir` override** fixture: `:feature` lives in
       `modules/feat`; `ModuleOf` and the name map follow the override
     - a **cross-module dependency** fixture: `:app` →
       `implementation(project(":core"))` and `projects.core`; `:app`
       sources get edges to `core/build.gradle.kts`, and `Deps` is
       transitive
     - an unlisted build-file directory becomes a module
     - build-input edges
     - the `gradle-dynamic` fallback (non-literal include, unknown project
       name) → `Problem`, opaque build file, and `Deps` = every module for a
       dynamic dependency block — red-proved like the Kotlin branches
   - **opaque red proofs:** for every `opaqueRules` row, a fixture
     `testdata/opaque/<reason>/…` with a test file that reaches a subject only
     through the construct (for example a DI module binding an
     implementation the test never imports):
     - the scan marks the construct's file opaque with exactly that reason
     - `Reverse` / `Closure` show the narrow graph (the dependent is not
       reached)
     - with `disableOpaque(reason)` the file is no longer opaque
     - so the opaque flag is the only thing standing between the change and
       a narrow selection
   - a table test fails when a rule has no fixture, or a fixture names no
     rule
   - `unreadable` uses chmod 000, with `t.Skip` when euid is 0
8. `deps/androidres.go` + test:
   - `ResKeys` with an attribute-only change
   - `ChangedKeys` for added / removed / changed keys and a nil side on each
     side
   - the opt-in gate, Java `["*"]`, `dynamic-resource`
   - an unknown scanner name → error
9. `deps/plugin.go` + `plugin_test.go` (script plugins in the fixture):
   - the happy path
   - non-executable and symlinked files are ignored
   - `*PluginError` for a non-zero exit, a malformed line, an unknown key, a
     path outside the universe, a bad glob, and a timeout (a short test
     timeout through a seam)
10. `deps/scan.go`, `graph.go` + `scan_test.go`:
    - universe filtering (excluded, ignored, symlinked, deleted-but-tracked)
    - unbounded `Closure` / `Reverse`, `Static`
    - deterministic, sorted output
    - **cache hit by blob:** the second scan triggers 0 `scanRaw` calls; one
      blob at two paths resolves correctly for each path; an edit misses
11. `suggest.go`, `frombody.go` + tests; `cmd/ait-testmap/annotate_deps.go` +
    `annotate_deps_test.go` through `run()`:
    - `--suggest` text and `--json`, `new` / `covered`, the helper walk,
      refusals, `TESTMAP_ABSENT` (2)
    - `--from-body`: `FROM_BODY:` lines, then `STAMP:…|added`; only covers
      lines change (`git diff -U0`)
    - the hook receives actor `auto` (no `AIT_AGENT_STRING`), or
      `agent:<s>`, or the explicit `--by`, with `Origin` =
      `scanner:from-body`
    - `--dry-run` writes nothing
    - **the inference → write race (review finding)**, deterministic through
      the test seam `deps.afterFromBodyInference`:
      - the seam rewrites the member body (`WelcomeScreen` →
        `OtherScreen`) once: the glue recomputes and the file ends up
        covering `OtherScreen.kt` only; `WelcomeScreen.kt` is never written
        (no stale mapping)
      - the seam rewrites it on every call: exit 75 `REWRITE_CONFLICT`, and
        the file equals the seam's last write byte for byte
    - the four refusals; `SCANNER_ERROR` (3)
    - `TestStampVerbUsage` keeps only `--author` as a stub
12. **Measure first, then bench** (review finding: the budgets were
    ungrounded):
    1. Run a temporary uncommitted `deps/probe_test.go` over this repository:
       cold and warm `Scan` times, file count and MB, under
       `taskset -c 0 GOMAXPROCS=1`.
    2. If warm is > 150 ms, profile and apply only **content-hashing-
       preserving** speed-ups (Pipeline 7): the pool, a single read per file,
       a packed cache file. Never a stat-based shortcut.
    3. Then add `BenchmarkScanWarm` / `BenchmarkScanCold` over an
       aitasks-shape fixture sized **by bytes** to the measured tree
       (≈1,350 files, ≈24 MB, a Go module).
    4. Budgets: warm `budget=150ms` (inside `select`'s 200 ms), cold
       `budget=1.5s` (the proposal's cold `select`). **If the measured warm
       still exceeds 150 ms, accept and report the shortfall rather than
       weaken correctness:** record the measurement and the profile in Final
       Implementation Notes, set the budget at the measurement plus headroom,
       and send a note to t1855 (M4.1's `select` budget is at risk).
    5. Record with `taskset -c 0 go run ./internal/tools/benchgate -baseline bench/baseline.txt -update`.
13. Checks:
    - `gofmt -l .`
    - `go vet ./...`
    - `go test ./...` (the tripwire and the allowlist)
    - the full benchgate
    - `ait engine test`
14. Documentation (path-scoped commits):
    - proposal *Dependency scanners*: an additive paragraph recording D1–D13
    - the *Annotation scanner* arms sentence: where the arms register, and
      `Restamp.Origin`
    - Line-protocol index: `SUGGEST:` `SUGGESTS:` `SUGGEST_REFUSED:`
      `FROM_BODY:` `FROM_BODY_REFUSED:` `SCANNER_ERROR:`
    - README *Layout* row `internal/testmap/deps`; *Interfaces* rows for
      `deps.Scan` / `Graph`, the plugin protocol, the cache, and the two arms

15. **Downstream notes**, after the code commit: one hedged
    `./ait note <id> --from 1853_3` per recipient, citing the commit SHA ("as
    landed in `<sha>`"). Each note says that no human-only step was met.
    - **t1855** (M4.1):
      - the `Graph` API; walk the closure unbounded (D13)
      - `Opaque` → `ESCALATE`; `ModuleOf` for runner sets
      - `ResKeys` / `ChangedKeys` and Java `["*"]`
      - the measured warm-scan time against `select`'s budget
    - **t1857** (M6.2 seeder / M6.4):
      - `Static()` origins and anchors; closure-only edges (`Origin ""`) are never seeds
      - the source-roots definition (D3)
      - the fallback / suffix / embedded-python / package-fallback edges are closure-only
    - **t1858** (M7.1 / M7.4):
      - `Symbols` / anchors for packets
      - corroboration via `Closure`
      - `Restamp.Origin` and the arm registration pattern for `--author`
    - **t1854** (M3.2): `bash-file list --invocations` should print `deps` bash facts rather than re-scan
    - **t1853_6** (M2.6): `Restamp.Origin` = `scanner:from-body` with actor `auto` / `agent:<s>`
    - **t1853_7**: `Suggest` as the scanner-suggestion source

### Post-phase (risk mitigations)

1. [probe_own_repository] Run `deps.Scan` over this repository's root
   through a temporary `deps/probe_test.go`. It resolves the root with
   `git rev-parse --show-toplevel` and is deleted afterwards, never committed.
   - **Oracle:** for every bash test (`tests/**/*.sh`) and every Python test,
     extract with an independent regexp every literal repository path
     (`\.aitask-scripts/[A-Za-z0-9_./-]+`, `tests/lib/[A-Za-z0-9_./-]+`,
     `seed/…`, `ait`, `install.sh`) and every `import` / `from` module name
     that names a repository file.
   - **Assertion:** each oracle hit that exists in the universe must be in that
     file's `Facts().Deps` (static or closure-only), or be explained (a
     dynamic construct, a path built at runtime).
   - **Record** in Final Implementation Notes:
     - files scanned
     - per-language dep counts and `Unresolved` counts
     - oracle hits matched / explained / missed
     - opaque files by reason
     - `Problems`
     - cold and warm timings
   - **Every miss is a resolver defect:** fix it and add its form as a fixture
     in step 4 / 5's tests before committing. A remaining dynamic-only miss is
     listed with its reason.

## Verification

- `ait engine test` is green, including the Invariant 4–5 tripwire and the
  allowlist (no new module).
- One red-proved fixture per opaque branch, showing the narrow graph without
  the rule. The Go invalidation is red-proved against a `go.sum`-only key for
  an import, a new file, a build tag and an embed change.
- bash literal invocation, including the `$SCRIPT_DIR` / `$PROJECT_DIR` forms,
  rebinding and embedded Python; the Python `sys.path` bootstrap import; Go
  package membership.
- The plugin protocol and its refusals; a cache hit by blob; the
  `android-res` opt-in.
- `annotate --suggest` / `--from-body` through `run()`. `--from-body` records
  the automated actor and `scanner:from-body`, and never writes a mapping
  inferred from a reading the file no longer matches.
- **Go key completeness**, each change re-running `go list`:
  - an ignored generated file's import change (red against the universe-only
    key)
  - a directly imported `_bridge` package's import change (red against the
    `./...` walk)
  - a file added under an embedded directory (red against non-recursive
    names)
  - an untracked input form is never cached
- **Python precedence:**
  - a shadowed module resolves the way Python loads it
  - repeated `insert(0, …)` calls reverse order
  - imports resolve at their own line, with a module cache, so an import
    before an insert and a repeated import both stay on the first-loaded
    file
- **Gradle:** a `projectDir` override and a cross-module `project()`
  dependency.
- **No stat-based freshness anywhere:** every scan hashes content.
- The probe-measured warm and cold scans; the benchmarks under budget.
- No path requires a human action.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).

## Risk

### Code-health risk: medium
- **New package with hand-written resolvers.** A large new package (≈4k lines) with hand-written tokenizers and evaluators (bash words and assignments, Python logical lines and the bootstrap evaluator, the Kotlin lexer) is a real maintenance surface. Each unmodelled construct needs a fixture. · severity: medium · → mitigation: inline post-phase probe_own_repository (real-tree forms become fixtures)
- **Contained blast radius.** Outside `deps` the change is limited to one additive `annot` extension (`Restamp.Origin`, `AnnotateWith` with an optional inference snapshot), one new glue file and one test-loop edit. Existing verbs are unchanged. · severity: low · → mitigation: none needed (named extensions, `annot` tests unchanged)
- **Stale cache after M2.2 lexer changes.** The blob cache depends on `annot.Classify`, which M2.2 owns; a lexer change could leave stale classifications. · severity: medium before the fingerprint test, low residual · → mitigation: in-plan design (D4 fingerprint test)

### Goal-achievement risk: medium
- **Under-approximation on real repositories.** The bash / Python resolvers may still miss real dependencies on this repository's ≈780 tests, and under-selection is silent. The fixtures prove the forms we thought of, not the forms the tree actually uses. · severity: medium (residual — addressed by inline post-phase probe_own_repository, which checks every literal path and import against an independent oracle on the real tree; other repositories' bash / Python idioms remain unmeasured) · → mitigation: inline post-phase probe_own_repository
- **Kotlin untested against a real tree.** The Kotlin opaque contract, the import walk and android-res are designed against thinking_app (a sibling repository) but tested only on fixtures. Opaque frequency, `package-fallback` volume and missed constructs are unmeasured. · severity: medium · → mitigation: kotlin_target_probe
- **Warm-scan budget.** The warm scan may not fit inside `select`'s 200 ms on the aitasks shape. · severity: medium · → mitigation: in-plan step 12 (measure first; stat index; recorded budget and a t1855 note on overrun)
- **Stale facts reaching the writer or the cache key** (review findings, fixed in plan). A Go cache key that hashed only universe headers, a stat-based blob shortcut, and a `--from-body` write planned from a later reading than the inference could each silently drop or misstate a dependency. · severity: high before the fix, low residual · → mitigation: in-plan design (D1 on-disk Go inputs; content hashing only; D6 inference snapshot carried into Apply) + their red fixtures
- **`go list` behaviour across hosts.** Toolchain auto-download, workspaces and vendor mode may differ on other hosts; the fail-closed opaque branches make that escalation, not a miss. · severity: low · → mitigation: in-plan design (D2 failure handling, tests)

### Planned mitigations
- timing: post-phase | name: probe_own_repository | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — bash/python resolvers under-approximating on the real tree | desc: run deps.Scan over this repository via a temporary uncommitted probe; check every literal repo path and import found by an independent regexp oracle against the facts; fix each miss with a fixture; record counts, opaque reasons and timings
- timing: after | name: kotlin_target_probe | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — Kotlin opaque contract / import walk / android-res unmeasured on a real tree | desc: run the deps scanner over the thinking_app repository (cross-repo via ait projects); measure opaque frequency per reason, package-fallback and unresolved volume, android-res key counts and scan time against the proposal's numbers; file fixes as tasks
