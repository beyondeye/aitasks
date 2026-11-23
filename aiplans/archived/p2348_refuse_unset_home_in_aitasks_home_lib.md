---
Task: t2348_refuse_unset_home_in_aitasks_home_lib.md
Base branch: main
Output branch: main
---

# t2348: Refuse an unset or empty HOME in `lib/aitasks_home.sh`, keeping the paths that need no root

## Context

`lib/aitasks_home.sh:19` runs `export AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"`
at source time. I reproduced the results before planning:

| caller | HOME unset | HOME="" |
|---|---|---|
| `aitask_testmap.sh` | `HOME: unbound variable`, rc 1 | runs against root-level `/.aitasks/engine/...`, rc 3 |
| `aitask_engine.sh` | `HOME: unbound variable`, rc 1 | runs on `/.aitasks`; `home` treats **`/.aitask`** as the legacy root |
| `aitask_engine.sh` with an explicit `AITASKS_HOME` | crashes at **line 68** (`REGISTRY_FILE=…$HOME…`) | works (`--help`, build/test/cross) |

The goal is a clear refusal. A raw unbound-variable abort is not acceptable, and
neither is a root-level default. The refusal must apply only where a path is
actually derived from HOME. The paths that need no default root keep working with
a blank HOME:
- the shim's `AIT_TESTMAP_BIN` override tier;
- `ait engine --help`;
- engine verbs given an explicit `AITASKS_HOME`.

An empty `AITASKS_HOME` stays forbidden, because `$AITASKS_HOME/engine/...` would
become `/engine/...`.

### Sourcer inventory (checked)

I listed the sourcers with `grep -rln aitasks_home`. Gate verifiers and
`aitask_test.sh` are named in the lib header, but they do not source it today.

- **`aitask_setup.sh:40`**: it already refuses an empty HOME at line 13, before the
  source. `install.sh` reaches setup through `--source-only` and hits the same
  guard. Nothing changes here.
- **`aitask_testmap.sh:59`**: runs under `set -euo pipefail`. Setup's
  `report_testmap_state` also sources it with `--source-only`, inside a
  `( … ) || exit 3` subshell where the lib is already loaded.
- **`aitask_engine.sh:62`**: runs under `set -euo pipefail`.
  - It also expands `$HOME` at line 68 (`REGISTRY_FILE`, read only by `cmd_prune`).
  - It expands `$HOME` again at line 281 (`LEGACY_ROOT`, read only by the `home_*`
    functions, which are reached only through `cmd_home`).
- **`lib/engine_install.sh:60`**: sourced by setup's `install_engine_binary`. The
  `install.sh` call path runs it as `… || true`, which turns errexit off, so a
  failed `source` is silently ignored unless the failure is propagated explicitly.

## Implementation

1. **`.aitask-scripts/lib/aitasks_home.sh`**: replace the guard and export at
   lines 17–19:
   ```bash
   if [[ -z "${AITASKS_HOME:-}" ]]; then
       if [[ -z "${HOME:-}" ]]; then
           echo "Error: AITASKS_HOME is unset and HOME is unset or empty, so the per-user framework root (\$HOME/.aitasks) cannot be derived; set AITASKS_HOME (or HOME)." >&2
           return 1
       fi
       AITASKS_HOME="$HOME/.aitasks"
   fi
   export AITASKS_HOME
   ```
   - Set `_AITASKS_HOME_LOADED=1` only **after** this succeeds, so a later source
     checks again.
   - An empty `AITASKS_HOME` still falls back to the HOME default, which keeps
     test T3 passing.
   - A refusal exports nothing and defines no `aitasks_engine_dir`.
   - Add a header paragraph covering the refusal, and the rule that every sourcer
     must propagate it explicitly (a sourced `return` disappears under `|| true`).

2. **`.aitask-scripts/aitask_testmap.sh`**: resolve the override tier **before**
   the root is initialised.
   - Remove the top-level `source …/aitasks_home.sh` (line 59).
   - Inside `testmap_resolve_engine`, load it lazily, after the VERSION check and
     Tier 1 (`AIT_TESTMAP_BIN`) and right before the existing
     `_tm_safe "$AITASKS_HOME"` check:
     ```bash
     # The default root is needed only from here on (dev + release slots);
     # the override above works without HOME.
     if ! source "$SCRIPT_DIR/lib/aitasks_home.sh" 2>/dev/null; then
         # Preserve the old check order: a blank root passed _tm_safe, so the
         # next answer was the AIT_ENGINE mode check. An invalid mode still
         # gets USAGE/64. Only a dev/release lookup gets ENGINE_HOME_UNSET.
         case "${AIT_ENGINE:-}" in
             ""|dev) TESTMAP_ENGINE_ERROR="ENGINE_HOME_UNSET:AITASKS_HOME|set AITASKS_HOME, or a non-empty HOME"; return 3 ;;
             *)      TESTMAP_ENGINE_ERROR="$_TM_MODE_USAGE"; return 64 ;;
         esac
     fi
     ```
     - Define `_TM_MODE_USAGE="USAGE:AIT_ENGINE must be 'dev' or unset"` once at
       top level and use it for both this arm and the existing `*)` arm of the
       Tier 2 `case`, so the string has a single definition.
     - Resulting order: override (Tier 1) first, then mode validation, then the
       default root. With a root present, the old order is unchanged:
       `_tm_safe(AITASKS_HOME)` runs before the mode check.
   - The lib's stderr is suppressed, so the shim keeps its one-diagnostic-line
     contract. The token is the diagnostic, it is printed by the existing main
     path, and the exit status is 3.
   - Under `--source-only`, the caller sees rc 3 and `TESTMAP_ENGINE_ERROR`, and
     its shell is never exited.
   - Sourcing inside the function is safe:
     - the lib declares nothing `local`, so `AITASKS_HOME`, the loaded flag and
       `aitasks_engine_dir` all become global;
     - nothing else in the shim reads `AITASKS_HOME` or calls `aitasks_engine_dir`
       (I grepped for both).
   - Add a header table row: `ENGINE_HOME_UNSET:AITASKS_HOME|… | stderr, exit 3;
     dev/release lookup with neither AITASKS_HOME nor HOME; the override tier
     needs neither, and an invalid AIT_ENGINE still answers USAGE/64 | S1, S2, S4`.
   - Add a note to the `tier order` row saying Tier 1 runs before the root
     exists.

3. **`.aitask-scripts/aitask_engine.sh`**:
   - **Help first.** Right after `SCRIPT_DIR=`/`GOENGINES=` and before any
     `source`, add:
     ```bash
     case "${1:-}" in -h|--help) sed -n '4,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
     ```
     Remove the duplicate `-h|--help` arm from the final dispatch. With this,
     help works with no HOME and no `AITASKS_HOME` at all.
   - **Propagate the lib refusal.** Change the line-62 source to
     `source …/aitasks_home.sh || exit 1`. The lib's `Error:` line is the message.
   - **Line 68.** Change it to
     `REGISTRY_FILE="${AITASKS_PROJECTS_INDEX:-${HOME:+$HOME/.config/aitasks/projects.yaml}}"`,
     so startup survives an unset HOME.
     - Its only consumer is `cmd_prune` (lines 197–206).
     - In `cmd_prune`, after argument parsing and before the `-f` check, add:
       `[[ -n "$REGISTRY_FILE" ]] || { echo "PRUNE_REFUSED:no-home|set AITASKS_PROJECTS_INDEX or HOME"; exit 1; }`
     - Add a contract row next to `no-registry`.
   - **Line 281.** Change it to `LEGACY_ROOT="${HOME:+$HOME/.aitask}"` and keep the
     `legacy-root-ok` marker. Every consumer is a `home_*` function reached only
     from `cmd_home` (I audited the callers of `home_report`, `home_migrate` and
     `home_preflight`). At the top of `cmd_home`, before the trailing-slash trim
     and before any read, add:
     ```bash
     [[ -n "$LEGACY_ROOT" ]] || { echo "HOME_SKIPPED:home-unset"; exit 1; }
     ```
     - This covers both `home` and `home --migrate`, so `/.aitask` can never act
       as the legacy root.
     - Add a contract row: `HOME_SKIPPED:home-unset | home / home --migrate with
       HOME unset or empty; nothing read or moved, exit 1`.
   - Verbs that never use HOME (build/test/cross, usage, `UNKNOWN_VERB`) keep
     working with a blank HOME and an explicit `AITASKS_HOME`. With HOME unset,
     they now get past line 68.

4. **`.aitask-scripts/lib/engine_install.sh:60`**: change the line to
   ```bash
   source "$_ENGINE_INSTALL_DIR/aitasks_home.sh" || { unset _ENGINE_INSTALL_LOADED; return 1; }
   ```
   - The refusal then survives install.sh's errexit-off `|| true` chain, and the
     installer stays unloaded instead of continuing with an unbound
     `$AITASKS_HOME`.
   - Setup's existing `if ! source …engine_install.sh` branch is unreachable for
     this cause, because setup's own HOME guard runs first. Leave it alone.

5. **New test: `tests/test_aitasks_home_unset_home.sh`**, modelled on
   `tests/test_python_resolve_unset_home.sh`.
   - Harness: a scratch cwd, `run_tmpdir`, and in-process counters.
   - Every child runs under `env -i PATH=/usr/bin:/bin`, with HOME **absent** and
     with `HOME=` (each case runs in both forms).
   - A `AITASKS_HOME_TEST_ROOT=<tree>` seam lets the cases run against a control
     tree.
   - **N1, lib with neither variable set:**
     - `source` returns 1;
     - stderr names both `AITASKS_HOME` and `HOME`, and contains no `unbound variable`;
     - `AITASKS_HOME` stays unset, `aitasks_engine_dir` is not defined, and
       `_AITASKS_HOME_LOADED` stays unset;
     - **positive control:** with an explicit `AITASKS_HOME=<scratch>`, the root
       resolves to `<scratch>`.
   - **Probe-safety rule (shim):**
     - Under the pre-fix shim, `HOME=` makes Tier 2/3 resolve
       `/.aitasks/engine/{dev,v<V>}/ait-testmap`.
     - `_tm_check_slot` then **executes** any executable it finds there
       (`"$bin" version`), even when it would later reject the version. No
       scratch cwd contains that absolute path.
     - Every shim run that could reach Tier 2/3 without an explicit scratch
       `AITASKS_HOME` therefore takes one of two forms:
       - **(a) In-process resolver case, blank HOME (absent and `HOME=`):**
         source the shim with `--source-only`, then **redefine `_tm_check_slot`**
         as a recorder: `_tm_check_slot() { printf 'PROBE:%s\n' "$1" >>"$PROBES"; return 1; }`.
         The stub records the path and executes nothing. Only then call
         `testmap_resolve_engine`.
       - **(b) CLI case (`bash aitask_testmap.sh …` as a process):** run with
         HOME **absent** only. The old shim aborts while it is being sourced,
         before any probe; the new shim refuses before any probe.
     - Unrestricted: runs that never reach Tier 2/3, namely the override (S2)
       and an invalid mode (S4 bogus), plus runs whose root is an explicit
       scratch `AITASKS_HOME` (S3). These run as CLI processes in both HOME forms.
     - A header comment in the file states this rule.
   - **S1, shim with neither variable set:**
     - **(b) CLI, HOME absent:**
       - `aitask_testmap.sh version` exits 3, and its stderr is exactly the
         `ENGINE_HOME_UNSET:` line;
       - stderr contains no `unbound variable`.
     - **(a) Resolver, both HOME forms, probe stubbed:**
       - rc is 3, `TESTMAP_ENGINE_ERROR` holds the token, and the sourcing shell
         survives;
       - `$PROBES` is **empty**: no slot was probed.
       - Pre-fix, the `HOME=` run records `PROBE:/.aitasks/engine/v<V>/ait-testmap`.
         That record is the signal, and nothing is executed.
   - **S2, override with a blank HOME** (the review's regression case):
     - `AIT_TESTMAP_BIN=<scratch stub that echoes "STUB:$*">` runs and prints
       `STUB:version`, with rc 0 and stderr `ENGINE_OVERRIDE:`;
     - this holds with and without `AITASKS_HOME`.
   - **S3, shim with an explicit `AITASKS_HOME` and no HOME:**
     `ENGINE_MISSING:<scratch>/engine/v<V>/ait-testmap|…`, rc 3.
   - **S4, invalid mode with a blank HOME** (the review's regression case):
     - with no `AITASKS_HOME` and `AIT_ENGINE=bogus`, stderr is exactly
       `USAGE:AIT_ENGINE must be 'dev' or unset` and rc is 64. It is never
       `ENGINE_HOME_UNSET`.
     - with `AIT_ENGINE=dev`, the result is `ENGINE_HOME_UNSET`, rc 3. This runs
       under the probe-safety rule: (a) the resolver with the probe stubbed in
       both HOME forms, asserting `$PROBES` is empty, plus (b) the CLI with HOME
       absent.
     - with `AIT_ENGINE=bogus` plus a valid `AIT_TESTMAP_BIN`, the override still
       runs first (`STUB:version`, rc 0).
   - **E1, engine help** (the review's regression case):
     - `aitask_engine.sh --help` and `-h` exit 0 and print the help header;
     - this holds with a blank HOME, with and without `AITASKS_HOME`.
   - **E2, engine `home`, read-only report only:**
     - With a blank HOME and `AITASKS_HOME=<scratch>`, `home` (no argument)
       prints `HOME_SKIPPED:home-unset`, exits 1, and leaves the scratch root
       unchanged.
     - The guard sits at the top of `cmd_home`, before the argument `case`, so
       this one case covers the code path `--migrate` shares.
     - **No case in this file ever runs `home --migrate`.** Under the pre-fix
       control tree, the old engine derives the absolute `/.aitask` from a blank
       HOME. No scratch cwd contains that path, and a migrate run could move host
       files. The old `home` report is lock-free and read-only (`home_report` /
       `home_preflight`, both documented read-only), so it is safe to run on
       either tree.
     - File-move coverage stays in the existing scratch-HOME migration suite,
       `tests/test_aitasks_home.sh` H*.
   - **Safety rule for the whole file:** under a blank HOME, every engine call is
     one of `--help`, `-h`, `home` (no argument), `prune --dry-run`, or an unknown
     verb. A header comment states this rule and the reason for it.
   - **E3, engine `prune --dry-run` with a blank HOME and `AITASKS_HOME=<scratch>`:**
     - no `AITASKS_PROJECTS_INDEX`: `PRUNE_REFUSED:no-home|…`, exit 1;
     - `AITASKS_PROJECTS_INDEX=<scratch>/missing.yaml`:
       `PRUNE_REFUSED:no-registry|<scratch>/missing.yaml`, which shows the override
       still bypasses HOME.
   - **E4, engine startup without HOME:**
     - with neither variable, `home` prints the lib's `Error:` line, exits 1, and
       shows no `unbound variable`;
     - with an explicit `AITASKS_HOME` and HOME unset, an unknown verb gives
       `UNKNOWN_VERB:`, exit 64. Startup survives line 68.
   - **N3, engine_install with errexit off:**
     - script: `bash -c 'warn(){ :; }; source …/engine_install.sh || echo "REFUSED:$?"; echo SURVIVED; declare -F engine_publish_locked && echo HAS_FN; echo "LOADED=${_ENGINE_INSTALL_LOADED-unset} AH=${AITASKS_HOME-unset}"'`
     - expected output: `REFUSED:1`, `SURVIVED`, no `HAS_FN`, and
       `LOADED=unset AH=unset`. The caller survives and the installer stays
       unloaded.
   - **HOME-set control:** with `HOME=<scratch>`, the lib resolves
     `<scratch>/.aitasks`. Shim and engine behaviour with HOME set is pinned by
     the existing suites.
   - **Pre-fix control:**
     - Build a scratch tree in which **all four** changed scripts are their
       pre-change versions (`git show HEAD:<path>` for the lib, the shim, the
       engine and engine_install). Reverting only the lib would leave the new
       engine guards in place.
     - Run the suite against that tree with `AITASKS_HOME_TEST_ROOT`. The control
       is the **unmodified** file. The probe-safety rule and the engine safety
       rule already confine every blank-HOME run to stubbed or pre-probe paths,
       so the control needs no special-casing. The pre-fix CLI shim cases run
       only with HOME absent.
     - Classify every assertion as failing pre-fix (the fix's signal) or passing
       pre-fix (a behaviour the fix preserves, e.g. S2 with `HOME=`, E1 with
       `HOME=` plus `AITASKS_HOME`).
     - Record the table in the Final Implementation Notes.

6. **Docs**: `aidocs/framework/shell_conventions.md:174` only lists the lib by name,
   so no change is needed. The contract tables in the shim and engine headers are
   the reference docs, and steps 2–3 update them.

## Verification

- `bash tests/test_aitasks_home_unset_home.sh` must pass everything. Then run the
  pre-fix control and record its failing and passing assertions.
- Regression runs:
  - `bash tests/test_aitasks_home.sh`
  - `bash tests/test_testmap_shim.sh`
  - `bash tests/test_install_engine_binary.sh`
  - `bash tests/test_python_resolve_unset_home.sh`
  - `bash tests/test_install_upgrade_dirty_baseline.sh`
  - `bash tests/test_upgrade_prunes_retired_scripts.sh`
- Lint:
  `shellcheck .aitask-scripts/aitask_testmap.sh .aitask-scripts/aitask_engine.sh .aitask-scripts/lib/aitasks_home.sh .aitask-scripts/lib/engine_install.sh tests/test_aitasks_home_unset_home.sh`
- Manual check: re-run the pre-plan repro table on the fixed tree, adding an
  `AIT_TESTMAP_BIN` row and an `engine --help` row.
  - Follow the same safety rules: run the shim with `HOME=` only through the
    override, or with an explicit scratch `AITASKS_HOME`.
  - Never run `engine home --migrate` with a blank HOME.

## Step 9 (Post-Implementation)

This is current-branch mode. Commit the code as `bug: … (t2348)` and commit the
plan separately. Then follow the standard Step 9 flow to archive the task.

## Risk

### Code-health risk: low
- `${HOME:+…}` empties two engine path variables, which follows the
  "emptying a path default" pattern. Every consumer has been audited:
  - `REGISTRY_FILE` is read only by `cmd_prune`;
  - `LEGACY_ROOT` is read only by the `home_*` functions under `cmd_home`.

  Both consumers refuse on an empty value, and E2/E3 test this. Severity: low.
  → mitigation: none needed (covered in plan)
- Moving the shim's lib source inside a function relies on global semantics.
  Nothing in the lib is `local`, setup's already-loaded subshell is a no-op, and
  S1–S3 plus the existing `test_testmap_shim.sh` cover it. Severity: low.
  → mitigation: none needed (covered in plan)

### Goal-achievement risk: low
None identified. Every sourcer is inventoried. Every path that needs no default
root (override, help, explicit root) has a regression case that runs with a blank
HOME. Each propagation route (errexit, `--source-only`, errexit-off `|| true`)
has its own case.

## Post-Review Changes

### Change Request 1 (2026-11-23 01:30)
- **Requested by user (review):**
  - A readonly-empty `AITASKS_HOME` under the shim's conditional source set the loaded flag and probed `/engine/v<V>/ait-testmap`.
  - `home --bogus` with a blank HOME answered `HOME_SKIPPED` instead of USAGE/64.
  - An override engine lost the inherited `AITASKS_HOME` / `AITASKS_HOME_LOCK`.
  - A missing lib was misreported as `ENGINE_HOME_UNSET`.
- **Changes made:**
  - The lib refuses an unassignable root up front (readonly empty `AITASKS_HOME`, or a readonly foreign `AITASKS_HOME_LOCK`), keeps a post-assignment backstop, records `AITASKS_HOME_REFUSAL` (`home-unset` | `root-unsettable`), and sets the loaded flag as the very last line.
  - The shim loads the root BEFORE Tier 1 (so exports reach an override engine) but reports a failure only after it, mapping the reason:
    - `home-unset` → `ENGINE_HOME_UNSET` (or USAGE/64 for an invalid mode);
    - empty reason (the lib never ran) → `ENGINE_LIB_FAILED:<lib>|run 'ait setup' to repair the install`;
    - any other reason → `ENGINE_ROOT_INVALID:AITASKS_HOME|<reason>`.
  - `cmd_home` validates its arguments before the HOME guard.
  - New cases N2, S5, S6, S7 and E2 `home --bogus`.
- **Files affected:** `lib/aitasks_home.sh`, `aitask_testmap.sh`, `aitask_engine.sh`, `tests/test_aitasks_home_unset_home.sh`

### Change Request 2 (2026-11-23 02:00)
- **Requested by user (review):**
  - The lib assigned the derived root before the lock check. A refusal by a function-local readonly lock therefore left a stale root that a retry reused.
  - A readonly lock already holding the right value was reassigned, which aborted an unguarded source under errexit.
  - A stale startup comment in the shim described the old load order.
- **Changes made:**
  - The lib validates the candidate root and lock before publishing either, and every refusal unsets its temporaries.
  - Values that are already correct are exported without reassignment.
  - The shim comment now describes the load order as implemented.
  - New N2 cases: retry after a refusal derives the new root; a matching readonly lock (explicit and derived root) loads with no readonly error.
- **Files affected:** `lib/aitasks_home.sh`, `aitask_testmap.sh`, `tests/test_aitasks_home_unset_home.sh`

## Final Implementation Notes
- **Actual work done:**
  - **`lib/aitasks_home.sh`** refuses (`Error:` line, return 1, `AITASKS_HOME_REFUSAL`) when no usable root can be established. Two cases: (a) `AITASKS_HOME` and HOME both unset or empty; (b) the root or lock cannot be assigned. A refusal publishes nothing, and the loaded flag is set only after full initialisation.
  - **`aitask_testmap.sh`** loads the root before the override tier but requires it only for the dev and release slots. New tokens: `ENGINE_HOME_UNSET`, `ENGINE_ROOT_INVALID`, `ENGINE_LIB_FAILED`. An invalid `AIT_ENGINE` keeps USAGE/64, and the override works with no HOME.
  - **`aitask_engine.sh`**:
    - help is answered before any library is sourced;
    - the lib refusal ends the run (`|| exit 1`);
    - `REGISTRY_FILE` and `LEGACY_ROOT` use `${HOME:+…}`, so an empty value is refused by the consumer (`PRUNE_REFUSED:no-home` in `cmd_prune`, `HOME_SKIPPED:home-unset` in `cmd_home` after its argument check), and `/.aitask` can never be treated as the legacy root.
  - **`lib/engine_install.sh`** propagates the refusal with `|| { unset _ENGINE_INSTALL_LOADED; return 1; }`, so it survives install.sh's errexit-off `|| true`.
  - Contract tables in the shim and engine headers are updated.
- **Deviations from plan:**
  - The three plan-review rounds and two implementation-review rounds widened the scope from the first plan:
    - lazy root plus override-first ordering;
    - help answered before any library is sourced;
    - per-consumer engine guards instead of a startup-wide HOME refusal;
    - preserved USAGE/64 order;
    - readonly-root handling, lib-failure diagnostics, and validate-then-publish.
  - The test grew from the planned N1–N3/S1–S4/E1–E4 cases to 118 assertions.
- **Issues encountered:**
  - **Readonly assignment (`AITASKS_HOME=…` on a readonly var).** Inside a conditional `source` under errexit, bash continues past it silently; outside one, the shell aborts. Hence the up-front checks plus the backstop.
  - **Pre-fix control safety.** The old code derives absolute `/.aitasks` and `/.aitask` paths from `HOME=""`, so the test confines every blank-HOME run to safe forms (documented in the test header):
    - stubbed `_tm_check_slot`;
    - CLI cases with HOME absent;
    - read-only engine verbs only, and never `home --migrate`.
- **Key decisions:**
  - The shim drops the lib's stderr and keeps its one-diagnostic-line contract. The lib reports why it refused through `AITASKS_HOME_REFUSAL`, so the shim never re-implements the rule.
  - The engine verbs that need no HOME keep working with an explicit `AITASKS_HOME`.
- **Verification:**
  - `tests/test_aitasks_home_unset_home.sh` passes 118/118. Against the pre-fix tree (the four changed scripts at HEAD, the rest copied), it scores 43 passed and 75 failed.
  - Assertions that also pass pre-fix fall into two groups:
    - behaviour the fix preserves (S2/S4-bogus/E1/E3-registry-override with `HOME=`, S3 explicit root, C1 HOME set);
    - checks that are vacuous after an old-code crash (`no HAS_FN`, `no slot probed` with HOME absent). Their companion RC, SURVIVED and token assertions fail pre-fix.
  - Targeted mutants, each caught by exactly its intended cases:

    | mutant | fails | caught by |
    |---|---|---|
    | override root load removed | 21 | S1, S3–S7 |
    | readonly precheck removed | 1 | N2 message (the backstop still refuses) |
    | precheck and backstop both removed | 6 | N2, S5 — reproduces the reviewer's `/engine/v0.42.0` probe |
    | lib failure mapped to HOME | 1 | S7 |
    | HOME guard before argument parsing | 4 | E2 `--bogus` |
    | root published before the lock check | 2 | N2 retry |
    | unconditional lock reassignment | 4 | N2 matching lock |

  - Regression:
    - passing: `test_aitasks_home`, `test_python_resolve_unset_home`, `test_install_upgrade_dirty_baseline`, `test_upgrade_prunes_retired_scripts`;
    - failing: `test_testmap_shim` E1 and `test_install_engine_binary` S2/E4. Only the Go source builds fail, and the cause is host configuration, not this change. `go env` persists `GOEXPERIMENT=nodwarf5`, while the mise go1.27.4 compiler was not built with it ("compile: version go1.27.4 does not match go tool version go1.27.4-X:nodwarf5"). `build.sh` and `cmd_build` are untouched.
  - shellcheck `-S warning` is clean (SC1091 info notes only, as on the base files).
- **Upstream defects identified:** None
