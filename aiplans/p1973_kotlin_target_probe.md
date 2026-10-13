---
Task: t1973_kotlin_target_probe.md
Base branch: main
Output branch: main
---

# t1973 — Kotlin target probe: `deps.Scan` over thinking_app

## Context

t1853_3 (M2.3) shipped the dependency scanners. Its Kotlin side (the opaque
contract, the import walk, android-res, the Gradle module graph and
`annotate --from-body`) was designed against thinking_app but tested only on
fixtures. This task is that plan's spawned "after" mitigation. It runs the real
scanner over the real tree, checks it against independent oracles, records the
measurements in this plan, and files each defect as its own bug task with a
reproducing fixture.

**Deliverables:** a measurements section in this plan, plus zero or more bug
tasks. No scanner code is changed here. Fixes belong to the spawned tasks.

Facts established during planning:
- `./ait projects resolve thinking_app` → `RESOLVED:/home/ddt/Work/thinking_app`
  (HEAD `1dc7b95`, 2026-10-13). The tree has untracked files (`DESIGN/`,
  `.aitask-explain/`, `.aitask-history/`, `app/google-services.json.oauth-backup`).
  `gitx.ListFiles` uses `--cached --others --exclude-standard`, so the scanner
  would see those files too. **Every measurement therefore runs on a clean clone
  pinned to a recorded SHA.** The live tree gets only one read-only timing
  cross-check.
- Shape: 3363 tracked files. There are 784 `.kt` files (main 335, test 445,
  androidTest 3, debug 1) and no `.java`. There is one Gradle module
  (`settings.gradle`: `include ':app'`), plus `build.gradle`, `app/build.gradle`,
  `gradle/libs.versions.toml` and a stray
  `tools/verification/measurements/worker-peak-t451/fork-membership.init.gradle`.
  There are 5 `values*/strings.xml` files under `app/src/main/res` and 1 under
  test resources. One locale has a `string-array`. 35 commits touch
  `values/strings.xml`. 64 `.kt` files carry Hilt-style annotations, none use
  Koin, and no Kotlin file uses `R.array.`. The tree also carries the aitasks
  framework (bash/python), which the scan includes.
- Scanner internals relied on (`goengines/internal/testmap/deps/`):
  - `Scan(ctx, root, Options{Config, CacheDir, Uncached})` (`scan.go:171`).
  - `Graph` accessors: `Files`, `Facts`, `Static`, `Reverse`, `Closure`,
    `Opaque`, `Modules`, `ModuleOf` and `Problems` (`graph.go`).
  - Edge `Via` values for Kotlin are `import`, `star-import`, `fq-ref`,
    `same-package` and `package-fallback` (`kotlin.go:386-430`).
  - The graph keeps only the first opaque reason (`firstOpaque`), but
    `scanKotlin(data).Opaque` returns the full set (`kotlin.go:70`).
  - `ResKeys` / `ChangedKeys` (`androidres.go`).
  - `FromBody` (`frombody.go:31`) needs an `aitestmap/` directory
    (`requireRegistry`, `suggest.go:33`) and a `// testmap:unit <Member>`
    opener in the test file.
- Prior probe shape to reuse: an uncommitted, env-gated `deps/probe_test.go`,
  deleted afterwards (p1853_3 "Probe record").

## Implementation steps

### Pre-phase (risk mitigations)

1. [oracle_self_control] *Run this between step 3 (oracles built) and step 7
   (triage).* Do not trust any oracle count until both oracles pass a fault
   injection.
   - Write `graph.mut.json`, a copy of `graph.json` with four faults injected:
     one resolved Kotlin `import` edge deleted (pick a test→main edge the oracle
     resolves exactly), one file's `opaque_all.json` reason set altered (drop
     `const-val` from a file that has it), one `ChangedKeys` entry removed
     from a diff result, and one name removed from a `reskeys.json` map.
   - Run `kt_oracle.py` and `res_oracle.py` on the mutated inputs. They must
     report **exactly** those four faults beyond the unmutated baseline. Any
     extra or missing report is an oracle bug: fix the oracle and repeat.
   - Record the pass and the injected identifiers in Measurements.

### Main steps

Scratch root: `$S=/tmp/claude-1000/-home-ddt-Work-aitasks/33854a44-ea4d-4aa5-9488-71e24f0a697e/scratchpad/t1973`.

1. **Pin the snapshot.**
   - `root=$(./ait projects resolve thinking_app | sed -n 's/^RESOLVED://p')`.
   - Save `git -C "$root" status --porcelain=v2 --untracked-files=all` to
     `$S/live_status.before`.
   - `git clone --quiet --no-hardlinks "$root" "$S/ta"`. Record
     `git -C "$S/ta" rev-parse HEAD` and the tree id. All numbers below are for
     that SHA.

2. **Write the temporary probe** at
   `goengines/internal/testmap/deps/probe_t1973_test.go`, in package `deps` so
   it can reach `scanKotlin`. It is never committed. Every test calls `t.Skip`
   unless `AIT_T1973_ROOT` / `AIT_T1973_OUT` are set.
   - `TestProbeT1973Scan`:
     - A cold scan with an empty `t.TempDir()` cache, then 3 warm scans on the
       same cache, then one `Uncached` scan. Log each wall time.
     - Run twice: with `registry.Defaults()`, and with `SymbolScanners:
       [android-res]`.
     - Dump `graph.json` / `graph_res.json` holding every file's `Facts`, plus
       `Modules`, `ModuleOf(file)` for each file, and `Problems`.
     - For every `.kt` file, also dump `opaque_all.json`: the full
       `scanKotlin(data).Opaque` set and `Symbols`.
     - For every file matching `ResValuesRe`, dump `reskeys.json`: the
       `ResKeys(data)` name → digest map, or the error.
   - `TestProbeT1973ChangedKeys`: for each `$OUT/res_diffs/<n>/{before,after}.xml`
     pair, write `ChangedKeys` and both `ResKeys` maps to JSON.
   - `TestProbeT1973FromBody`: for each `path#Member` line in
     `$OUT/fb_members.txt`, run `FromBody(ctx, $AIT_T1973_FB_ROOT, id,
     Options{Config: Defaults(), CacheDir: tmp})` and write the refusal and refs
     to JSON. This is the inference only. It never calls `AnnotateWith`, so it
     never writes anything. Log each member's `annot.ParseFile` opener line
     and the line of the next opener, as the step-5 range check.
   - Run with `cd goengines && AIT_T1973_ROOT=… AIT_T1973_OUT=… go test
     ./internal/testmap/deps -run ProbeT1973 -count=1 -v`.

3. **Build the independent oracles.** These are Python scripts in `$S`. They
   share no code with the scanner and read only the clone's bytes and the JSON
   dumps.
   - `kt_oracle.py`, for declarations:
     - First strip comments and strings with a small state machine.
     - Then extract each `.kt` file's package and its top-level declarations
       with a **modifier-aware** column-0 matcher:
       - optional same-line annotations `@X` / `@X(...)`;
       - then any of `public private internal protected data enum sealed
         abstract open inner value annotation inline suspend operator infix
         tailrec external const lateinit expect actual`;
       - then `fun interface|class|interface|object|fun|val|var|typealias`,
         where `fun` also takes a receiver (`fun <T> Recv.name`).
     - The forms that actually occur, surveyed during planning, are `class`,
       `data class`, `enum class`, `abstract class`, `sealed class` /
       `sealed interface`, `open class`, `object`, `fun`, `suspend fun`,
       `inline fun`, `fun interface`, `val`/`var`, `const val`, and each of
       those with a visibility prefix.
     - **Coverage denominator:** report every column-0 line starting with a
       lowercase word or `@` that the matcher neither classified nor knows as
       `package` / `import` / an annotation-only line. Triage each such pattern
       by hand. None may be dropped silently.
   - `kt_oracle.py`, for imports. Classify every explicit import into exactly
     one of three classes. The totals must reconcile: all = external +
     resolved + unclassified.
     - **external**: no prefix of the path is a repository package.
     - **resolved**: the oracle finds `pkg` + declaration name for it.
     - **unclassified repository candidate**: a prefix is a repository package,
       but the oracle finds no declaration. Examples are generated `R` /
       `BuildConfig`, nested members, and declarations the oracle missed. Each
       distinct import path here is triaged by category in step 7, not excluded.
   - `kt_oracle.py`, for edges and opaque reasons:
     - Report **under-selection**: a resolved import where the graph has no
       edge from the importer to the target file, through any `Via`.
     - Report **precision loss**: a resolved import where the scanner used
       `package-fallback`.
     - Detect `const val`, `inline … fun`, `::class.java`, `Class.forName`,
       `getIdentifier(` and DI annotations (`@Inject @Module @Provides @Binds
       @HiltViewModel @AndroidEntryPoint @HiltAndroidApp @InstallIn @EntryPoint
       @AssistedInject @Assisted @Singleton @Component`).
     - Report **opaque disagreements** between that detection and
       `opaque_all.json`, listed per reason.
     - Report **declaration disagreements** between oracle declarations and the
       scanner's `Symbols`.
   - **Hand-checked declaration sample.** This is independent of both parsers
     and catches a declaration form that both of them omit.
     - Pick 12 files that between them contain every surveyed declaration form,
       including a multi-line `@Config(...)` before a `class`, a
       `@HiltViewModel` class, `sealed interface`, `fun interface`, extension
       funs, `private const val`, and `typealias` if one exists.
     - Read each file and write its top-level declaration list by hand into
       `$S/decl_sample.json` (name, kind, line).
     - Compare both the oracle and the scanner's `Symbols` against it. A form
       either side misses is an oracle fix or a scanner defect.
   - `res_oracle.py`. Note what the graph actually holds: `FileFacts.Keys` holds
     **Kotlin reference keys** (and `*` for Java). XML files never carry it
     (`resolve.go:92,106`). The two sides are therefore compared separately:
     - **Declarations vs `ResKeys`.** The probe dumps `ResKeys(data)` for every
       `res/values*/*.xml` (`ResValuesRe`). The oracle uses expat byte offsets
       to extract each depth-1 `<string>` / `<plurals>` element's name, its
       sorted attribute set and its raw inner bytes. This mirrors the
       documented contract: the digest covers the element kind, the sorted
       attributes and the raw `innerxml`, and a `string` and a `plurals` with
       the same name fold into one key. Compare the name sets.
     - **Unsupported kinds** (`string-array`, `integer-array`, `array`, `color`,
       `dimen`, `bool`, `integer`, …) are counted per file and reported as an
       inventory. They are not defects unless Kotlin references them; planning
       measured 0 `R.array.` refs.
     - **References vs graph `Keys`.** Compare the regex `R.(string|plurals).X`
       and `"x".localized` refs per Kotlin file with that file's graph `Keys`.
       Report keys that are referenced but declared in no supported element.
     - **`ChangedKeys`.** Under the raw contract, the expected keys are those
       added, removed, or with a different (kind, attrs, raw inner bytes)
       tuple. Compare that set with `ChangedKeys` for exact agreement.
     - **Separately**, compute a canonical (ElementTree C14N) diff for
       information only. A key that changed raw but not canonically, for
       example from whitespace or entity spelling, is classified as
       **conservative over-report**, which is by design per the contract.
       Only a disagreement with the raw-contract expectation can become a
       defect.
   - Gradle check, inline in the same script:
     - The expected modules are `:` and `:app`.
     - Every `app/**` file must map to `:app` through `ModuleOf` and every
       other file to `:`.
     - Compare the `:app` `Deps` with the `project(...)` references in
       `app/build.gradle`.
     - List every `gradle-dynamic` problem and how the stray `*.init.gradle`
       file is classified.

4. **Prepare the android-res diffs.** Take the 10 most recent commits touching
   `app/src/main/res/values/strings.xml`, plus 2 that touch a locale file. For
   each one, write `git -C "$S/ta" show <rev>^:<path>` and `<rev>:<path>` into
   `res_diffs/<n>/`. Skip the parent side for a file's creating commit and
   record that.

5. **Prepare the from-body fixture** on the clone. thinking_app has no registry
   and no openers, and the live repository is never edited, so the fixture lives
   only in the clone.
   - `mkdir "$S/ta/aitestmap"`.
   - Pick about 6 real test members by grep, one per construct:
     - a JVM unit test using explicit imports;
     - an extension function called in receiver position and imported from
       another package;
     - a same-package extension call with no import;
     - a star-import user;
     - a fully-qualified reference;
     - a Compose `androidTest`.
   - **Member boundaries.** `FromBody` reads from the opener to the next opener
     or end of file (`frombody.go:57-62`), not to the method's closing brace,
     so each sampled method must be isolated:
     - Insert `// testmap:unit <Name>` at the method's indentation, directly
       above its annotations.
     - Insert a **boundary opener** `// testmap:unit <Name>End` on the line
       right after the method's closing brace, at the same indentation.
     - A boundary is still needed when another sampled member follows. If a
       sampled method is the last in its file, the boundary goes before the
       class's closing brace.
     - Commit in the clone.
   - **Record the exact line range** per member, from the opener line to the
     boundary line minus 1, in the clone's committed file. Both `FromBody`'s
     inference and the hand oracle read exactly this range. The file-level
     imports and package come from the whole file, as `FromBody` resolves
     through them.
     - Check the range mechanically: `ParseFile` must show the member's
       `Opener.No` and its boundary at the recorded lines. The probe logs
       both.
   - Record the hand oracle for each member: read the recorded line range and
     list the repository declarations it names, which gives the expected source
     files.
   - Write `fb_members.txt` and run `TestProbeT1973FromBody` with
     `AIT_T1973_FB_ROOT="$S/ta"`. Do this after steps 2–4, because the opener
     edits change the clone's blobs.

6. **Run, then cross-check the timing on the live tree.** Run steps 2–4 on the
   clean clone, then step 5.
   - Run one cold and warm `TestProbeT1973Scan` timing pass against the live
     `$root`, for timing only.
   - Re-capture `git -C "$root" status --porcelain=v2 --untracked-files=all`
     and `diff` it against `live_status.before`. It must be identical, proving
     the probe wrote nothing into thinking_app.

7. **Triage by hand.**
   - Open every under-selection miss, opaque disagreement, `ChangedKeys`
     mismatch, Gradle mis-mapping and from-body miss. Classify each one as a
     **scanner defect**, an **oracle error** (fix the oracle and re-run) or
     **by design**.
   - "By design" covers, for example, over-approximation through
     `package-fallback` for a generated `R` or `BuildConfig`, and `same-package`
     breadth.
   - Sample `Unresolved` by category: generated (`R`, `BuildConfig`, …),
     nested member, extension, typealias, other.

8. **Record the measurements** in this plan, in a `## Measurements` section
   (template below).

9. **File the defects.** For each scanner defect, use the Batch Task Creation
   Procedure to create a `bug` task with:
   - labels `testing,testmap,go_engine`, anchor 1852;
   - a minimal Kotlin, Gradle or XML fixture that reproduces it;
   - the expected and actual edge, reason or key, and the thinking_app path
     where it occurs.

   Scale the priority to the direction of the error: under-selection is high,
   over-approximation is medium/low. If a timing budget is exceeded, send a note
   to t1855 (M4.1) with `/aitask-note` instead of a task, following p1853_3's
   rule. High `package-fallback` volume is a precision cost, not a defect.
   Record it, and offer an enhancement task only if it dominates closure size.

10. **Clean up.**
    - Delete `probe_t1973_test.go`. `git status --short goengines/` must show
      nothing from this task.
    - The clone and oracles stay in the session scratchpad. They are not
      repository artifacts.

## Measurements (template, filled in at step 8)

- Snapshot: thinking_app `<sha>` / tree `<tree>`, plus the files and MB scanned per language.
- Opaque: per-reason file counts for main / test, and against the proposal's 42 (`const val`/`inline fun`) and 63 (DI) main files.
- Kotlin edges: counts per `Via`, `Static` count, `package-fallback` edge count and number of distinct files reached, `Unresolved` by category.
- Oracle: imports classified as external / resolved / unclassified repository
  candidate, with reconciled totals and the triage categories for the
  unclassified class. For resolved imports: matched, under-selection misses
  and precision losses. Declaration coverage: unclassified column-0 patterns,
  and the hand sample of 12 files vs both the oracle and `Symbols`.
- Gradle: modules, `ModuleOf` mismatches, `gradle-dynamic` problems.
- android-res:
  - `ResKeys` names vs the raw-contract oracle, per XML file;
  - the unsupported element-kind inventory;
  - Kotlin files carrying keys, reference keys vs regex refs, `*` files and
    dangling refs;
  - `ChangedKeys` agreement over N diffs, with conservative over-reports
    counted separately.
- Timing: cold, warm (min / median), uncached, and the live-tree cross-check, against warm 200 ms (`select`) / 150 ms (scan budget) and cold 1.5 s.
- from-body: per member, the exact line range, refs vs the hand oracle, and
  misses with their constructs.
- Defect tasks filed: `t<id>` list.

## Verification

- The probe runs green and its JSON dumps exist. Each oracle prints a summary
  whose totals reconcile: checked = matched + misses.
- Every reported miss is opened by hand and classified, so no count goes
  unexamined.
- Each filed bug task carries a fixture that reproduces the defect. Where it is
  cheap, confirm this by adding the fixture to the temporary probe package and
  watching the scanner give the wrong answer, then remove it.
- Live thinking_app status is byte-identical before and after. The aitasks
  `goengines/` has no residual change.

## Risk

### Code-health risk: low
- None identified. No repository code changes. The temporary probe is deleted, the clone lives in the scratchpad, and a before/after status diff proves thinking_app is untouched.

### Goal-achievement risk: medium
- The regex oracle may share blind spots with the token-level scanner, so under-selection misses could be undercounted · severity: low (residual — addressed by inline pre-phase oracle_self_control, which proves the oracles detect injected faults; a declaration form both parsers omit is covered by the step-3 hand-checked declaration sample and the unclassified-line denominator) · → mitigation: inline pre-phase oracle_self_control
- The from-body check covers only about 6 hand-picked members against a hand oracle, so missed constructs outside that sample stay unmeasured. Each member is isolated by a boundary opener, so the inference and the hand oracle read the same recorded range · severity: low · → mitigation: none
- The resource comparisons could produce false defects by comparing against the wrong contract. They compare against `ResKeys` and its raw-digest contract, keep Kotlin reference keys separate, and inventory unsupported kinds · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: oracle_self_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — regex oracle sharing blind spots with the scanner | desc: inject one deleted import edge, one dropped opaque reason, one dropped ChangedKeys entry and one dropped ResKeys name into the scanner dumps; both oracles must report exactly those faults before any count is trusted

## Post-implementation

Step 8: there are no code changes to commit, only this plan via
`aitask_task_commit.sh`. Step 9 archival then follows. The work happens on the
current branch, so nothing is merged.
