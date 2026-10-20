---
Task: t2081_testmap_closure_implicit_inputs_audit.md
Base branch: main
Output branch: main
---

# t2081 — Audit implicit runner inputs for anchor eligibility

## Context

`goengines/internal/testmap/cost/eligibility.go` (M3.4, t1854_4) lets a passing
result anchor on a dirty tree only when the modified paths are disjoint from
everything the unit can read. Today that covers the test file, its
`deps.Graph.Closure`, covers, reads globs and runner files. Two classes of input
are missing, so a dirty one can still anchor (a false `EVIDENCED`):

- inputs the test framework reads **implicitly**, which no scanner models;
- targets the scanners **silently drop** because they lie outside the scan universe.

This task audits the four reference runners, closes both classes with a red-proved fixture per gap asserting the exact `anchor_reason`, and pins the D12 counterexample as a fail-closed test. D12 is **not** relaxed here.

### Finding 1: `exclude:` silently drops read targets (every scanner)

Every scanner tests a target with `u.has(...)`, and the universe is git-visible files minus `exclude:`. An excluded target therefore gets no edge, and outside bash it is not `Unresolved` either:

- **python:** ancestor conftests (`deps/python.go:1802`) and absolute imports. An unchanged excluded `tests/conftest.py` that imports `src/helper.py` hides `src/helper.py` from the closure.
- **go:** `appendUniverse` (`deps/golist.go:716`) drops every go-list-named file outside the universe: members, tests, xtests, cgo aux, **embeds** (`:621-625`) and `testdata`. A dirty excluded `pkg/assets/message.txt` embedded by `pkg/a.go` is invisible.
- **kotlin:** same-package and import resolution run over scanned files only.
- **bash:** a miss is `Unresolved`, so it fails closed, but imprecisely.

`exclude:` means "never listed, never UNREGISTERED" (`registry/config.go:49`). It is a **registry** rule, not a statement about what code reads. **Fix:** the eligibility scan lifts `exclude:`, so excluded files become ordinary graph nodes, the closure follows them, and a dirty one is reported as `closure:<f>`.

Whatever is still outside the lifted universe (gitignored, symlinked, non-regular) cannot be scanned. That gets the fail-closed handling in Finding 3.

Lifting must cover **every input the disjointness check reads**, not only `deps.Scan`:
- **Scanner-plugin reads:** plugins receive the scan universe on stdin (`deps/plugin.go:114`), so they follow the lift automatically.
- **`testmap:reads` annotations:** these come from `annot.Source`, which still skips `exclude:` (`annot/source.go:41`). A lifted, reachable excluded helper would otherwise lose its read declarations, which is weaker than today, when the helper is unresolved and blocks. They get their own lifted reader; see step 3.
- **Go importer side:** a package whose files are **all** outside the universe has no facts on which a mark can survive. Its importers must carry the mark themselves; see step 2.
- **The runner-script route:** `runnerConfig` walks the script's own closure, which the lift also changes. It must apply the same reads, plugin-reads and annotation guards as the test side. They are shared helpers, so the two routes cannot drift; see step 5.

### Finding 2: implicit inputs per runner

The reference runners (M3.2, `t1854_2`) are **not implemented yet**: there is no builtin, describe output or command line to read. So the rules key on the **test file's scanner language** (`Facts(test).Lang`), not on a runner name.

| runner | already in the closure | executable implicit inputs (added **with their closure**) | non-executable implicit inputs (path rules) |
|---|---|---|---|
| pytest (`python`) | ancestor `conftest.py` and its imports; imported `__init__.py` | the test's own `__init__.py` package chain (prepend import mode runs them) | `pytest.ini`, `.pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg` in any ancestor-or-self dir |
| go-test (`go`) | package members, in-package tests, imports, embeds, `testdata/` | **all `.go` files of the test's directory**, which brings in the xtests of an in-package test. They share the test binary; the asymmetry is pinned at `golang_test.go:68` | `go.mod`, `go.sum`, `go.work`, `go.work.sum` in ancestor-or-self dirs; `<ancestor>/vendor/**` |
| gradle-class (`kotlin`) | module build file, project-dep build files, settings, root `gradle.properties`, `gradle/libs.versions.toml`, `buildSrc/**` | every Gradle script in the graph (`gradle`/`gradle-kts` kinds): root `build.gradle(.kts)` with `subprojects{}`, `apply from:` scripts, included builds | `gradle.properties` anywhere; `gradle/**`; `gradlew(.bat)`; `buildSrc/**`; `build-logic/**`; dirs of non-root `settings.gradle(.kts)`; module `src/*/{resources,res,assets}/**`, `src/*/AndroidManifest.xml` |
| bash-file (`bash`) | literal/var-resolved `source`/`exec`; literal misses → `Unresolved` | none (no framework files) | none. The gap is in the scanner: a **dynamic** `source "$x"` / `"$cmd"` (empty literal tail) or an unknown-base ref whose suffix matched nothing is dropped silently (`deps/bash.go:821-831`) |

Executable implicit inputs are treated like the test's own closure:
- their own closure is added;
- opacity / `Unresolved`, `testmap:reads` and plugin `reads` are checked over all of it;
- a dirty one is `implicit:<f>`, and a dirty file in their closure is `closure:<f>`.

### Finding 3: unscannable implicit executables fail closed

A file that exists but is outside even the lifted universe cannot be scanned. Gitignored and symlinked files fall here.

- **python:** an ancestor-or-self `conftest.py` / `__init__.py` that exists (`os.Root.Lstat` under the root) but has no graph facts → `opaque:implicit-unscanned:<p>`.
- **go:** a go-list-named file (member, test, xtest, aux, embed) outside the universe → `Unresolved` on every file that would have linked it → `opaque:unresolved:<f>`.

**Residuals (documented, not closable by these rules):**
- **Gitignored non-executable inputs** (`local.properties`, `.env`): invisible to `git status` itself.
- **Environment:** `BASH_ENV`, `PYTHONPATH`, `pytest -p` / `pytest_plugins` string plugins, `sitecustomize`.
- **Gradle scripts' non-script reads**, e.g. `file("config/x.yml")`.
- **Heuristic hits:** a bash suffix-match hit is treated as modelled, which is the scanner's existing heuristic.
- **Edit-and-revert within one invocation.**

## Pre-implementation gate (in-flight overlap)

**t2080** (`fix_run_provenance_paths_under_subdir_registry`, Implementing) has uncommitted edits in `cost/eligibility_test.go` and `runner/provenance_test.go`, and will touch `cost/eligibility.go` (the `root-not-toplevel` guard). Before the **first edit** of either `cost/` file:
- check `git status --short goengines/internal/testmap/cost/` and t2080's status;
- if t2080's changes are still uncommitted, **stop and ask** the user whether to wait.

Never stash, restore or commit them. Implement on top of t2080's committed state. The `deps/` edits do not overlap and may proceed first.

## Implementation

1. **`deps/bash.go` `bashFacts`:** an unmatched `source`/`exec` ref becomes `Unresolved` in two cases:
   - an empty `Rel` with no hit. Any base can produce this; `source "$DYN"` is `var:DYN` + `""`, and it hits `continue` today;
   - an unknown base whose suffix match found nothing.

   For each:
   - The marker is `"<dynamic>"` for an empty `Rel`, else `"<dynamic>/"+Rel`. A suffix *hit* stays resolved.
   - Update the `Unresolved` doc in `deps/deps.go:62`.
   - The cache stores raw facts and resolution runs after it, so there is no `schemaVersion` bump.

2. **`deps/golist.go` `goFacts`:** collect go-list-named files outside the universe instead of dropping them silently.
   - Keep `appendUniverse` for edges. Add a sibling `outside(u, files...) []string` that returns the dropped ones.
   - Append them to `Unresolved` of every file that `link`s that list:
     - dropped members, aux and `EmbedFiles` → on the in-universe members **and** tests/xtests. They compile together, so an importer reaching an in-universe member also inherits the mark;
     - `TestEmbedFiles` → on tests;
     - `XTestEmbedFiles` → on xtests;
     - dropped tests/xtests → on each test/xtest.
   - **Importer side (entirely unscannable packages).** `importFiles` becomes `importFiles(run, ip) (files, unres []string)`:
     - **byPath branch:** `unres` = `q`'s non-test inputs outside the universe (its `GoFiles`/`CgoFiles`/non-test `IgnoredGoFiles`, aux, `EmbedFiles`), each as a path.
     - **Fallback branch** (module-path arithmetic over `res.DirGo`): if no in-universe non-test file is found for a local-module import, `unres = [ip]`. The import cannot be followed.

     `link` appends `unres` to the importing file's `Unresolved`. This covers a package whose files are **all** gitignored. `pkgMembers` returns nothing there, so no facts exist inside it to carry a mark, and its own imports (e.g. a dirty in-universe `m/c`) are unreachable.
   - Update the head comment at `golist.go:21-24`.

3. **`cost/eligibility.go` `load`:** scan with `exclude:` lifted (`scanCfg := cfg; scanCfg.Exclude = nil`). Comment why: exclude is a registry rule, and the closure must see what code reads.

   **Read declarations over the same lifted universe.** `annot.Source.Annotations` skips `cfg.Excluded` (`annot/source.go:41`), so a lifted, now-reachable excluded helper's `testmap:reads` would be lost. That is weaker than before, when the helper was unresolved and blocked.
   - Add `annot.ExcludedReads(ctx, root) (reads map[string][]string, bad map[string]string, err error)` in `annot/source.go`. It walks the same git-visible, no-follow, known-language files, but **only the `cfg.Excluded` ones**, returning each file's `Reads` globs. An excluded file whose annotations the grammar refuses is reported in `bad[path] = reason` instead of failing the run.
   - Factor the per-file read/parse body out of `Annotations` into one helper both loops share. `Annotations` itself is unchanged, so registration exclusions are preserved and excluded files still contribute no covers or units.
   - `load` merges the result into `in.reads` and keeps `in.badAnnot = bad`.
   - `decide` rejects a unit whose checked file set contains a `bad` path as `opaque:annotations:<f>`. Its read declarations are unknown, so it fails closed.

4. **New `cost/implicit.go`**, the audit as code. Its doc comment carries the Finding 2 table in short form and the residuals.
   - `implicitFiles(g, test, lang) []string`: the executable implicit inputs present in the graph, sorted:
     - **python:** `__init__.py` of each ancestor-or-self dir of the test;
     - **go:** every graph `.go` file whose `path.Dir` equals the test's dir, minus the test;
     - **kotlin:** every graph file of kind `gradle`/`gradle-kts`.
   - `unscannedImplicit(root, g, test, lang) string` (python only): Lstat the ancestor-or-self `conftest.py` / `__init__.py` through `os.OpenRoot(root)`; return the first one that exists but has no facts.
   - `implicitHit(g, test, lang, modified) string`: the path rules of Finding 2's last column, as predicates over the **modified set** (sorted clone), using `doublestar.Match` for the module-resource globs and `g.ModuleOf(test)`.

5. **`cost/eligibility.go` `decide`:** after `opaque:no-facts` (keep the `facts` value), the order is:
   1. `files := j.closure(test)`; `imp := implicitFiles(...)`; `ext :=` dedup of `imp` ∪ each `imp` member's `Closure`, minus `files`.
   2. `opaqueIn(g, files ++ ext)`.
   3. `opaque:annotations:<f>` for a file in `files ++ ext` with unreadable excluded annotations.
   4. `unscannedImplicit` → `opaque:implicit-unscanned:<p>`.
   5. `test-file`.
   6. `closure:` over `files[1:]`.
   7. `implicit:<f>` over `imp`.
   8. `closure:<f>` over the rest of `ext`.
   9. `covers`.
   10. `reads` / `plugin-reads` over `files ++ ext`.
   11. `implicitHit` → `implicit:<p>`.
   12. `runnerConfig`.

   **One file-set guard for both routes.** Factor the per-file-set checks into helpers that the test side and the runner side both call, so the two routes cannot drift:
   - `annotIn(in, files) string` → the first file with unreadable excluded annotations;
   - `readsIn(in, files, modified) string` → `reads:<glob>` from `in.reads`, then `plugin-reads:<glob>` from `Facts(f).Reads`.

   **`runnerConfig` (project/shadow script closure)** gets the same guards, which it lacks today. A script runner's helper `testmap:reads` was already unchecked even in-universe, and the lift extends the gap to excluded helpers. After the existing opacity check on `files := j.closure(script)`:
   - `annotIn` → `runner-config:annotations:<f>`;
   - `readsIn` → `runner-config:reads:<glob>` / `runner-config:plugin-reads:<glob>`;
   - then the existing membership check.

   Extend the head comment accordingly.

6. **Tests, `deps/`:**
   - **`bash_test.go` `TestBashDynamicRefIsUnresolved`:**
     - `source "$X"` → `<dynamic>`;
     - `bash "$TMP/gen.sh"` (no suffix match) → `<dynamic>/gen.sh`;
     - a suffix hit is not unresolved;
     - a plain `cat "$X/f"` argument is not unresolved.
   - **`golang_test.go` `TestGoOutsideUniverseIsUnresolved`:**
     - an excluded embed and an excluded member each appear in the right files' `Unresolved`, and an in-universe embed does not;
     - **an entirely gitignored intermediate package:** `a/a_test.go` imports `m/hidden`; gitignored `hidden/hidden.go` imports tracked `m/c`. The test asserts that `a/a_test.go`'s `Unresolved` holds `hidden/hidden.go`;
     - **the fallback branch:** an import of a local-module path with no in-universe non-test file, which go list did not report, puts that import path in `Unresolved`.

     Uses the existing `goEnvFixture` skip.
   - **`annot` test `TestExcludedReads`:** an excluded `vendor/lib.sh` declaring `testmap:reads fixtures/*.json` is returned, a non-excluded file is not, and an excluded file with a refused annotation lands in `bad` without an error.

7. **Tests, `cost/eligibility_test.go`.** A new helper `implicitRepo(t, unit, files, exclude)` builds a minimal committed fixture: config with `exclude:`, `.gitignore`, `runners.yaml` binding `[unit]`, and a shadow runner listing and passing `unit`. It chmods before commit. Go rows skip without a toolchain and set `GOTOOLCHAIN=local GOFLAGS= GOWORK=off GOPROXY=off` (as in `deps/golang_test.go:20-29`). Each language gets a **positive control**: dirty `docs/readme.md` → anchors with reason `""`.
   - **`TestEligibilityImplicitInputs`**, a table asserting exact reasons:
     - **python:**
       - `pyproject.toml` → `implicit:pyproject.toml`;
       - `tests/pytest.ini`;
       - `tests/__init__.py` → `implicit:tests/__init__.py`;
       - a module imported only by `tests/__init__.py` → `closure:<m>`.
     - **go:**
       - `go.mod`;
       - `go.sum`;
       - the xtest `pkg/a_ext_test.go` of in-package `pkg/a_test.go` → `implicit:pkg/a_ext_test.go`;
       - a package imported only by that xtest → `closure:<f>`;
       - `vendor/x/y.go`.
     - **kotlin:**
       - root `build.gradle.kts` for an `app/` test;
       - `gradle/wrapper/gradle-wrapper.properties`;
       - `app/gradle.properties`;
       - `app/src/test/resources/f.json`;
       - `build-logic/src/main/kotlin/Conv.kt`.
   - **`TestEligibilityExcludedConftestHelper`** (concern 1): an excluded, **unchanged** `tests/conftest.py` does `import helper`; `src/helper.py` is reached via a `sys.path` bootstrap in the conftest, or by placing the helper as `tests/helper.py`, whichever the Python model resolves (confirm with a `deps` probe first). Dirty only the helper → `closure:<helper>`.
     - **Control:** the same fixture without the conftest's import anchors.
     - **Variant:** the conftest is **gitignored** instead (exists, unscannable) → `opaque:implicit-unscanned:tests/conftest.py`.
   - **`TestEligibilityExcludedEmbed`** (concern 2): `pkg/a.go` has `//go:embed assets/message.txt`, and `pkg/assets/**` is excluded. Dirty only `pkg/assets/message.txt` → `closure:pkg/assets/message.txt`.
     - **Variant:** the asset is gitignored → `opaque:unresolved:pkg/a.go` (unchanged tree except `docs/readme.md`).
   - **`TestEligibilityExcludedHelperReadsDeclaration`** (concern 3): `tests/test_a.sh` sources an unchanged excluded `vendor/lib.sh` that declares `# testmap:reads fixtures/*.json` and reads that data dynamically (no static edge). Dirty **only** `fixtures/x.json` → `reads:fixtures/*.json`.
     - **Control:** the same fixture without the declaration anchors. That proves the declaration is the only guard.
     - **Variant:** the helper carries a refused annotation → `opaque:annotations:vendor/lib.sh`.

     In this test, drop the `eligRepo` scanner plugin's `fixtures/*.json` read on the test (use `implicitRepo` or override `aitestmap/scanners/fx`), so the plugin glob does not shadow the helper's.
   - **`TestEligibilityScriptRunnerHelperReads`** (concern 5). Built like `TestEligibilityScriptRunnerClosure`: project-script runner `tools/run.sh` sources an unchanged **excluded** `vendor/runner-lib.sh` declaring `# testmap:reads runnerdata/*.json`, read dynamically with no static edge. Dirty **only** `runnerdata/x.json` → `runner-config:reads:runnerdata/*.json`.
     - **No test-side shadowing:** `runnerdata/` matches neither the test helper's `tests/data/*.txt` nor the plugin's `fixtures/*.json`, and no test-side file declares it. Assert this with a control: the same fixture without the declaration anchors.
     - **Variants:**
       - the helper carries a refused annotation → `runner-config:annotations:vendor/runner-lib.sh`;
       - a scanner plugin declares `runnerdata/*.json` on `tools/run.sh` (no annotation) → `runner-config:plugin-reads:runnerdata/*.json`;
       - an in-universe (non-excluded) helper with the same declaration → `runner-config:reads:runnerdata/*.json`. This is the pre-existing gap.
   - **`TestEligibilityGitignoredGoPackage`** (concern 4): the same three-package shape as the deps test, with only `c/c.go` dirty → `opaque:unresolved:a/a_test.go`. Skips without a Go toolchain.
   - **`TestEligibilityDynamicSourceIsOpaque`:** `source "$DYN"` → `opaque:unresolved:tests/test_a.sh`.
   - **`TestEligibilityUnscannedHelperReadsDirtyFile`** (the D12 counterexample): `tests/test_a.sh` sources a **gitignored**, unchanged `tests/gen/lib.sh` (present on disk, outside the universe), which itself `source`s `src/c.sh` (in-universe and otherwise unreferenced). Dirty **only** `src/c.sh` → `opaque:unresolved:tests/test_a.sh`.
     - **Control:** without the sourcing line it anchors.
     - **Variant:** the helper is *excluded* instead → `closure:src/c.sh`. The lifted scan follows it.
   - **Update `TestEligibilityUnresolvedSourceIsOpaque`:** its excluded `vendor/lib.sh` is now scanned. Rename it to `TestEligibilityExcludedSourceIsFollowed` and expect `closure:vendor/lib.sh`.

8. **`goengines/README.md:183`:**
   - The eligibility row adds:
     - the lifted `exclude:`;
     - the implicit inputs, with their closure;
     - `opaque:implicit-unscanned:<p>`;
     - `implicit:<path>`;
     - `opaque:annotations:<f>`;
     - the runner script's closure now also checked for declared/plugin reads and unreadable annotations (`runner-config:reads|plugin-reads|annotations:…`);
     - excluded files' `testmap:reads` via `annot.ExcludedReads`;
     - bash dynamic refs and Go outside-universe files / unfollowable local imports as `Unresolved`.
   - Add an `annot.ExcludedReads` mention to the annotation-source row (line 170).
   - Update the tests column.
   - The deps scanner rows (bash / go) note the new `Unresolved` sources.

9. **Red proofs** (recorded in Final Notes). One isolated mutant per rule and per new test, each restored byte-identical (`cmp`), and each must fail its own test:
   - each `implicitHit` predicate;
   - `implicitFiles` per language;
   - the `ext` closure;
   - `unscannedImplicit`;
   - the lifted exclude;
   - the `ExcludedReads` merge;
   - the `opaque:annotations` check;
   - each `runnerConfig` guard (annotations, reads, plugin-reads);
   - the bash `<dynamic>` append;
   - the golist outside recording (package side);
   - the importer-side `unres`, in both the byPath and the fallback branch;
   - the **D12 narrowing mutant**: `opaqueIn` treats `unresolved:` as opaque only when some modified path is absent from `g.Files()`. `TestEligibilityUnscannedHelperReadsDirtyFile` must fail under it.

### Post-phase (risk mitigations)

1. **[measure_unresolved_rate_after_dynamic_refs]** Measure on this repo, with a real `deps.Scan` of the root:
   - **(a)** the share of bash tests (`tests/*.sh`) with any `Unresolved` in {test} ∪ `Closure(test,0)`, with and without the `<dynamic>` append. The baseline should reproduce ≈ 400/448.
   - **(b)** the hook input cost (cold/warm) with `exclude:` lifted vs not. On this repo there is no `aitestmap/config.yaml`, so expect ≈ equal. State that.

   Use a throwaway `cost/zz_measure_test.go`: create it, run it, delete it. It is never committed and never `git restore`d. Paste the measurement code verbatim and the numbers into Final Notes.

## Verification

- `cd goengines && go vet ./... && go test ./internal/testmap/...` (or `ait engine test`).
- Step 9: archival via `aitask_archive.sh 2081` (current-branch mode, so no merge).

## Risk

### Code-health risk: medium
- **The scanner's `Unresolved` meaning widens.** Bash dynamic refs and Go go-list-named files outside the universe join it. Its only consumer is `cost/eligibility.go`, but `deps` JSON output changes for affected files. · severity: medium (bounded: one consumer, resolution runs after the cache, no schema bump; the full `./internal/testmap/...` run catches pinned facts) · → mitigation: none
- **The eligibility scan lifts `exclude:`.** It reads more files (vendor trees, excluded modules) on every dirty-tree hook. This is extra latency, and an unparsable excluded file may surface as `opaque:` or `eligibility-error:deps:`, both fail-closed. · severity: medium (cost measured by the inline post-phase) · → mitigation: inline post-phase measure_unresolved_rate_after_dynamic_refs
- **`implicit.go` is a second, framework-shaped model next to the scanners**, and could drift. · severity: low (one test row per rule; the doc names the scanner lines it complements) · → mitigation: none
- **In-flight overlap with t2080** on `cost/eligibility*.go`. · severity: medium (gated before the first edit; never stash or restore) · → mitigation: none

### Goal-achievement risk: medium
- **The reference runners (M3.2) are not implemented.** Rules key on the test language, not on the runner's real command line, cwd or unit kind. An implemented runner may read inputs these rules miss. · severity: medium · → mitigation: align_implicit_inputs_with_reference_runners
- **Dirty-tree anchors become rarer still.** The bash `<dynamic>` marker adds to the 400/448 (89 %) unresolved bash tests from t1854_4. This is the fail-safe direction, but it erodes self-healing. · severity: medium (residual) · → mitigation: inline post-phase measure_unresolved_rate_after_dynamic_refs
- **Path-rule residuals are documented, not closed:** gitignored non-executable inputs, environment, Gradle scripts' file reads, and suffix-match guesses. · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: measure_unresolved_rate_after_dynamic_refs | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — dirty-tree anchors rarer after the bash <dynamic> marker; code-health — lifted-exclude scan cost | desc: Measure the share of this repo's bash tests with Unresolved refs in {test} ∪ closure before/after the bash dynamic-ref change, and the hook input cost with exclude lifted; report both in Final Notes
- timing: after | name: align_implicit_inputs_with_reference_runners | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — implicit-input rules keyed on language because M3.2 reference runners are not implemented | desc: Once M3.2 (t1854_2) lands the pytest/go-test/gradle-class/bash-file runners, cross-check cost/implicit.go against their real command lines, cwd, unit kind and config flags (pytest -c/rootdir, go-test per-package units, gradle filter_scope) and add red-proved rows for any input they read that the rules miss

## Post-Review Changes

### Change Request 1 (2026-10-20 15:10)
- **Requested by user:** three review findings:
  - (1, high) The Go module-file rule considered only ancestors of the test dir. A reached local dependency module (`replace => ../lib`) has its `go.mod` language version ignored, so editing only `lib/go.mod` anchored.
  - (2, high) A deleted Go `testdata` case disappears from the graph and no rule caught it, so a deletion that turned a failing test green anchored.
  - (3, medium, follow-up) `implicitFiles` / `implicitHit` / `extend` redo repo-wide `g.Files()` scans and Gradle-script closure walks per result.
- **Changes made:**
  - (1)+(2) The Go rules now derive their directories from every Go file in the checked set (test, closure, implicit inputs and theirs) via `goDirs`:
    - `go.mod` / `go.sum` / `go.work` / `go.work.sum` and `<d>/vendor/**` count for any ancestor `d` of a reached package;
    - any **deleted** path (`os.Root.Lstat` fails) under a reached package's directory tree is `implicit:<path>`. This covers a removed member, testdata case or embedded asset.

    The old test-dir-only `.go` sibling rule was dropped; the deletion rule subsumes it. `implicitHit` now takes `root` and the checked set and returns an error, which becomes `eligibility-error:implicit:`.
  - New fixtures, each with an exact reason:
    - `TestEligibilityGoDependencyModule`: control, `closure:lib/l.go`, `implicit:lib/go.mod`, `implicit:app/go.mod`;
    - `go-deleted-testdata`;
    - `go-deleted-dep-member`.
  - New and updated mutants are all red: M3 (module files), M3b (module scope = test-only), M4 (deletion), M4b (package scope = test-only), M5 (vendor), M19 (call).
  - (3) is deferred to a follow-up task (performance), per its disposition.
- **Files affected:** `goengines/internal/testmap/cost/implicit.go`, `cost/eligibility.go`, `cost/implicit_test.go`, `goengines/README.md`

### Change Request 2 (2026-10-20 15:40)
- **Requested by user:** (high) The Go fallback rejected a path under a reached package only when `Lstat` failed. A tracked testdata file replaced by a symlink (or reached through a symlinked directory) still exists, yet the scan's no-follow universe drops it, so it anchored.
- **Changes made:**
  - The fallback now applies the universe's own criterion, `regularNoFollow` in `cost/implicit.go`: every ancestor must be a real directory and the final component a regular file, each checked by its own `Lstat` through `os.Root`. Anything failing it under a reached package is `implicit:<path>`.
  - New `TestEligibilityGoSymlinkedInput` has three variants:
    - **final-component link** → `implicit:pkg/testdata/bad.txt`;
    - **linked ancestor dir** → `implicit:pkg/testdata` (the link itself is listed);
    - **linked ancestor dir with the link gitignored** → `implicit:pkg/testdata/bad.txt`. Only the tracked paths under it are modified, and each resolves through the link.
  - Mutants M4 (fallback off), M4c (existence-only check) and M4d (no ancestor walk) are all red. M4d was green until the hidden-link variant was added.
- **Files affected:** `goengines/internal/testmap/cost/implicit.go`, `cost/implicit_test.go`, `goengines/README.md`

## Final Implementation Notes
- **Actual work done:**
  - **`deps/bash.go`:** an unmatched `source`/`exec` with no static target (empty literal tail on any base, or an unknown-base suffix miss) is `Unresolved` as `<dynamic>[/<tail>]`.
  - **`deps/golist.go`:**
    - go-list-named files outside the universe (members, tests, xtests, cgo/asm/syso, embeds) are `Unresolved` on every file that would have linked them; `pkgOutside`/`appendOutside` hold the logic;
    - importers carry an imported local package's outside inputs (byPath branch) or the import path itself (fallback branch finds no universe file).
  - **`deps/deps.go`:** `FileFacts` doc updated (`Unresolved` = what the closure cannot follow).
  - **`annot/source.go`:** `ExcludedReads` (the `exclude:`d complement: reads globs plus a path→reason map of unreadable ones); the per-file body is factored into `readAnnotations`, and `Annotations` is unchanged.
  - **`cost/eligibility.go`:**
    - the scan lifts `exclude:`; excluded reads are merged, and `badAnnot` → `opaque:annotations:`;
    - implicit inputs and their closures (`extend`) join the checked set;
    - `annotIn`/`readsIn` are shared between the test side and `runnerConfig`, giving `runner-config:annotations|reads|plugin-reads:`;
    - `implicitHit` errors become `eligibility-error:implicit:`.
  - **`cost/implicit.go` (new):** the audit as code. `implicitFiles` (python `__init__` chain, Go same-dir `.go`, every Gradle script), `unscannedImplicit` (python conftest/`__init__` existing but factless → `opaque:implicit-unscanned:`), `implicitHit` path rules, `goDirs` (reached packages and their ancestors), `regularNoFollow`.
  - **Tests:**
    - deps: `TestBashDynamicRefIsUnresolved`, `TestGoOutsideUniverseIsUnresolved`;
    - annot: `TestExcludedReads`;
    - cost (`implicit_test.go`): `TestEligibilityImplicitInputs` (33 rows), `TestEligibilityGoDependencyModule`, `TestEligibilityGoSymlinkedInput`, `TestEligibilityExcludedConftestHelper`, `TestEligibilityExcludedEmbed`, `TestEligibilityGitignoredGoPackage`, `TestEligibilityExcludedHelperReadsDeclaration`, `TestEligibilityScriptRunnerHelperReads`, `TestEligibilityDynamicSourceIsOpaque`, `TestEligibilityUnscannedHelperReadsDirtyFile`;
    - `judgedIDs` helper; `TestEligibilityUnresolvedSourceIsOpaque` renamed to `TestEligibilityExcludedSourceIsFollowed` (now `closure:vendor/lib.sh`).
  - **README:** the deps, annotation-source and eligibility rows.
- **Deviations from plan:**
  - The Go rules were widened in review (CR1/CR2). Module/workspace files and vendor now count for ancestors of **every reached Go package**, not only the test's. The planned same-dir `.go` path rule was replaced by "any path under a reached package's tree failing the universe's no-follow criterion" (deleted, symlink, or via a linked directory).
  - Kotlin-row fixture isolation: a `buildSrc` source pulls the root build script into every Kotlin closure (it lives in module `:`), so that row has its own file map (`ktBuildSrc`).
  - The fallback-branch fixture uses a `_gen/` package imported only by a tag-ignored file. `./...` skips `_` directories, so go list never reports it; a gitignored but listed package goes through the byPath branch instead.
  - The gitignored-embed variant reports `opaque:unresolved:pkg/a_test.go`, not `pkg/a.go`. The test file carries the package's outside inputs too, and it is checked first.
- **Issues encountered:**
  - Three mutants first failed to compile (`if false` leaving a loop or `fi` variable unused; a deleted `case` leaving `p` unused). They were rewritten as `&& false` and rerun; none was counted before that.
  - M4d (no ancestor walk) was green until the hidden-link fixture was added: a listed symlink is caught by its own final-component check.
- **Key decisions:**
  - Rules key on the test file's scanner language, because the M3.2 reference runners do not exist yet. The spawned after-mitigation aligns the rules with them once they land.
  - **D12 not relaxed.** The counterexample (`TestEligibilityUnscannedHelperReadsDirtyFile/gitignored`: an unchanged gitignored helper sourcing dirty `src/c.sh`) stays `opaque:unresolved:`, and the D12 narrowing mutant (M21) turns it green → red-proved.
  - `exclude:` is a registry rule only; registration (`Annotations`, covers, units) still never sees excluded files.
- **Red proofs:** 33 isolated mutants, each restored byte-identical (`filecmp`), and each failed its own expected tests:
  - **implicit rules:**
    - M1–M2 (python predicate, ancestry);
    - M3, M3b (Go module files; module scope = test only);
    - M4, M4b, M4c, M4d (unseen-under-package; package scope; existence-only check; no ancestor walk);
    - M5 (vendor);
    - M6a–c (gradle.properties / script rule / gradlew);
    - M7a–d (`gradle/`, `buildSrc`, `build-logic`, included builds);
    - M8 (module resources);
  - **implicit files and closures:**
    - M9–M11 (`implicitFiles` per language);
    - M12 (`unscannedImplicit`);
    - M13 (`extend` closure);
  - **eligibility guards:**
    - M14 (lifted exclude);
    - M15 (ExcludedReads merge);
    - M16–M18 (`annotIn` test side; runner `annotIn` / `readsIn`);
    - M19 (`implicitHit` call);
    - M20 (implicit vs closure naming);
    - M21 (D12 narrowing);
  - **scanners:**
    - M22–M23 (bash `<dynamic>`);
    - M24–M26 (golist package side; importer byPath; fallback);
    - M27–M28 (ExcludedReads reads / bad).
- **Measurement (post-phase `measure_unresolved_rate_after_dynamic_refs`),** on this repo with a real `deps.Scan`:
  - **Bash tests (`tests/*.sh`):** 451. Unresolved in {test} ∪ closure: **444 now** vs **402 without `<dynamic>` entries**; the baseline reproduces t1854_4's 400/448. That means 42 tests (9 %) are newly opaque, all from dynamic `source`/`exec`. On a dirty tree, 98 % of this repo's bash tests cannot anchor (the fail-safe direction).
  - **Scan cost:** `deps.Scan` 718 ms cold / 142 ms warm with `exclude:` as configured, and 605 ms / 122 ms lifted. They are equal within noise: this repo has no `aitestmap/config.yaml`, so `exclude:` is `[]`. `annot.ExcludedReads` took 7 ms.
  - The measurement code is a throwaway `cost/zz_measure_test.go` (created, run, deleted; never committed), verbatim:
```go
package cost

import (
	"strings"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/deps"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// Throwaway (t2081 post-phase): bash tests with any Unresolved in
// {test} ∪ closure, with and without the <dynamic> entries; scan cost.
func TestZZMeasure(t *testing.T) {
	root := "/home/ddt/Work/aitasks"
	cfg, err := registry.LoadConfig(root)
	if err != nil {
		t.Fatal(err)
	}
	lifted := cfg
	lifted.Exclude = nil
	for _, c := range []struct {
		name string
		cfg  registry.Config
	}{{"exclude-as-configured", cfg}, {"exclude-lifted", lifted}} {
		cache := t.TempDir()
		for _, pass := range []string{"cold", "warm"} {
			start := time.Now()
			if _, err := deps.Scan(bg, root, deps.Options{Config: c.cfg, CacheDir: cache}); err != nil {
				t.Fatal(err)
			}
			t.Logf("deps.Scan %s %s: %v", c.name, pass, time.Since(start))
		}
	}
	start := time.Now()
	if _, _, err := annot.ExcludedReads(bg, root); err != nil {
		t.Fatal(err)
	}
	t.Logf("annot.ExcludedReads: %v (exclude list: %q)", time.Since(start), cfg.Exclude)
	g, err := deps.Scan(bg, root, deps.Options{Config: lifted, Uncached: true})
	if err != nil {
		t.Fatal(err)
	}
	total, any, literal, dynOnly := 0, 0, 0, 0
	for _, f := range g.Files() {
		if !strings.HasPrefix(f, "tests/") || strings.Count(f, "/") != 1 || !strings.HasSuffix(f, ".sh") {
			continue
		}
		total++
		files := []string{f}
		for _, r := range g.Closure(f, 0) {
			files = append(files, r.Path)
		}
		hasLit, hasDyn := false, false
		for _, p := range files {
			ff, _ := g.Facts(p)
			for _, u := range ff.Unresolved {
				if strings.HasPrefix(u, "<dynamic>") {
					hasDyn = true
				} else {
					hasLit = true
				}
			}
		}
		if hasLit || hasDyn {
			any++
		}
		if hasLit {
			literal++
		}
		if hasDyn && !hasLit {
			dynOnly++
		}
	}
	t.Logf("bash tests: %d; unresolved now: %d; without <dynamic> (baseline): %d; newly unresolved by <dynamic> only: %d", total, any, literal, dynOnly)
}
```
- **Upstream defects identified:** None
