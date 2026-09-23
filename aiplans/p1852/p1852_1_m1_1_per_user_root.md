---
Task: t1852_1_m1_1_per_user_root.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_5_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/fable5_1 @ 2026-09-23 16:19
---

# Plan: t1852_1 — M1.1 Per-user root

## Context

Parent goal: M1 — Engine foundation and distribution (`ait-testmap` as a
buildable, installable, resolvable binary). This submodule is **M1.1 Per-user
root**, wave **A**, no providers — one of the two roots of the feature's
dependency graph. It delivers the one `AITASKS_HOME` path resolver every bash
piece of the feature sources, and the setup lines that make the per-user root
visible.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
Module Map `#### M1` row M1.1 (line 679), component *Per-user root (M1.1)*
(2042–2052), *Process map* (321), *Where state lives*, assumptions
`assumption_legacy_user_root_coexists` / `assumption_home_symlink_compatibility`
(3199–3212), tradeoffs *The per-user root (M1)* (3670+). Parent plan:
`aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md` (reality
anchors, deviations 4 and 6).

## Owned files / provides / consumes

- **Owns:** `.aitask-scripts/lib/aitasks_home.sh` (new); `tests/test_aitasks_home.sh`
  (new — the default, the env override, the no-`~/.aitask/` grep guard); the
  `setup_aitasks_home()` step (the `mkdir` 0755) and the `AITASKS_HOME:<path>`
  summary line in `aitask_setup.sh` (a named extension of setup — Deviation 4
  of the parent plan); the `test_scaffold.sh` copy-list entry.
- **Provides:** `AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}`,
  `aitasks_engine_dir <version|dev>`, `AITASKS_HOME_LOCK=$AITASKS_HOME/.home.lock`
  — sourced by the shim (M1.4), `install_engine_binary()` / `aitask_engine.sh`
  (M1.5), the migration verb (M1.6), later the verifiers (M8) and
  `aitask_test.sh` (M5.1).
- **Consumes:** nothing.
- **Named extensions into this child's files:** M1.6 adds the migration cases
  to `tests/test_aitasks_home.sh`; M1.5 registers its two setup functions in
  the guard's `FEATURE_FUNCTIONS`. Exemptions from the guard are per-line
  markers in the consumer's own code, never entries in this file.

## Step 0 — Reality check (executed 2026-09-22, main @ 63012375f)

Every anchor re-verified against the merge target. Tabulated differences:

| # | item | proposal says | coarse plan says | repository has | decision |
|---|---|---|---|---|---|
| 1 | `lib/aitasks_home.sh` / any `~/.aitasks` reference | new, none exist | same | **absent**; no script names `~/.aitasks` (only `aitasks.io` URLs match a loose grep) | adapt nothing — build as specified |
| 2 | legacy `~/.aitask/` reference set | 8 framework files, 35 refs | same (parent anchors) | **9 files, 36 refs** — the ninth is `ait:127` (`$HOME/.aitask/update_check`, a dereferenced path, so `assumption_home_symlink_compatibility` still holds) | not a cut error; the migration's known-entry set already contains `update_check`. **Note to t1852_6** (its symlink-compat re-check must count `ait` too) |
| 3 | setup summary block | "beside the venv line" | `main()` at :4364, `Python venv:` at :4511 | confirmed: `info "  Python venv: $VENV_DIR"` at `aitask_setup.sh:4511`, then `Python:` / `PyPy venv:` / `Global shim:` / `Version:` | the new line goes immediately after `Python venv:` |
| 4 | how setup sources the lib | "sourced by … `install_engine_binary`" | "decide startup vs lazy at the reality check" | setup sources its three libs **unconditionally at column 0** (`:15,19,23` — `python_resolve`, `github_release`, `data_symlinks`); `tests/test_shell_startup_closure.py` derives Python-fixture closures from exactly that shape | **source at column 0** like its siblings; the scaffold rule therefore applies (row 5) |
| 5 | scaffold copy list | — | "add if on a startup chain" | `setup_fake_aitask_repo()` lists 15 libs; two fixtures (`tests/test_setup_help_flag.sh:42-46`, `tests/test_init_data.sh:93-97`) copy `aitask_setup.sh` on top of the scaffold and hand-copy only `github_release.sh`; `test_t167_integration.sh` / `test_seed_manifest_drift.sh` go through a real tarball / `cp -r` — so **one scaffold entry covers every fixture** | add `aitasks_home.sh` to the scaffold; append it to the baseline list at `aidocs/framework/shell_conventions.md:135` (that list is already missing `ledger_block`/`data_symlinks`/`txn_snapshot` — not repaired here, noted) |
| 6 | the printed token | `AITASKS_HOME:<path>` (protocol form, no space — like every `KEY:<value>` line in the proposal, and like M1.6's `HOME_LEGACY:<path>\|<tenants>` hint that will sit beside it) | same | summary lines are human-form `Key: value` | **emit the protocol form literally**: `info "  AITASKS_HOME:$AITASKS_HOME"` — downstream tests grep the token |
| 7 | mode 0755 | "creates `$AITASKS_HOME/engine/` (0755)" | same | no idiom for it in the tree except `sudo mkdir -p -m 755` (`:326`) | `mkdir -p -m 0755` — explicit mode on the final component regardless of umask; an **existing** directory is never `chmod`ed (setup must not rewrite a user's permissions) |
| 8 | `aitasks_engine_dir` API shape | `<version\|dev>` → `…/engine/v<version>/` or `…/engine/dev/` | same | consumers not written yet; M1.4's plan composes `$AITASKS_HOME/engine/v<V>/ait-testmap` | print **without trailing slash** (`…/engine/v<version>`, `…/engine/dev`); empty arg → usage on stderr, `return 2`; the bare version is passed (no `v` prefix). **Note to t1852_4 and t1852_5** |
| 9 | grep-guard scope | "no framework script of this feature names `~/.aitask/`" | explicit allowlist excludes the legacy tenants (`aitask_setup.sh`, `python_resolve.sh`, `aitask_path.sh`) | the feature's scripts today = the lib alone; M1.6's `home` arm will legitimately name `~/.aitask` (it migrates and symlinks it); setup and `aitask_engine.sh` are **mixed-purpose** files | scan a **pre-registered feature-file list** plus **feature-owned functions inside shared files** (setup's `setup_aitasks_home` now; M1.5's two installer functions later), with exemptions **per line** via a `# legacy-root-ok: <reason>` marker — never per file, so an unrelated legacy-path line in a mixed file still fails while a marked migration line (including the legacy `engine` entry the migration moves) passes. **Note to t1852_5** (register its functions) and **t1852_6** (mark its migration lines; no file allowlist exists) |
| 10 | verification `AITASKS_HOME=/tmp/x ./ait setup` | — | listed as acceptance | a full `ait setup` installs a venv, needs network, and prompts; `main()` is a flat sequence of function calls with no command-substituted step output | the test sources `aitask_setup.sh --source-only` (pattern `tests/test_setup_find_modern_python.sh:15`), tests the function directly (T7) **and** runs `main()` with every other function stubbed (T8) under a scratch `HOME`, with a negative control proving the directory comes from `main()`'s call; the full-flow run stays a manual smoke |
| 11 | install flow | — | — | `install.sh:1070` extracts the whole `.aitask-scripts/` and `chmod +x`es `lib/*.sh`; `install.sh:1487` sources setup `--source-only` from the extracted tree | nothing to add to `install.sh` |
| 12 | `aitasks_extension_points.md` "No global PATH override" | — | — | the lib exports only `AITASKS_HOME` (+ the lock var), never `PATH` | n/a |

**Ownership re-confirmed:** every file below is owned here or lands as the
owner's named extension (setup: one `source` line, one function, one call, one
summary line — the installer functions remain M1.5's).

**Notes owed (post-approval, before implementation):** t1852_4 (row 8 — API
shape), t1852_5 (rows 8 and 9 — API shape; register `install_engine_binary` /
`report_testmap_state` in the guard's `FEATURE_FUNCTIONS`), t1852_6 (rows 2
and 9 — count `ait` in the symlink-compat re-check; the guard has **no file
allowlist** — mark each legitimate legacy-root line, the `engine` entry of the
known set and the `destination-exists:engine` preflight included, with
`# legacy-root-ok: <reason>`; an unmarked line anywhere in `aitask_engine.sh`
fails the guard). Hedge: the lib and the guard are uncommitted at note time.

## Implementation steps

1. **`.aitask-scripts/lib/aitasks_home.sh`** (new, executable like its
   siblings; mirror `lib/aitask_path.sh`):

   ```bash
   #!/usr/bin/env bash
   # aitasks_home.sh — the per-user framework root ($AITASKS_HOME).
   #
   # Sourced (not executed) by every bash piece of the test-map feature: the
   # `ait testmap` shim, install_engine_binary() / aitask_engine.sh, the gate
   # verifiers and aitask_test.sh. It is the ONE owner of the path: nothing
   # else composes "$HOME/.aitasks", and it never falls back to the legacy
   # per-user root (venv, bin, python, uv, …), which coexists with this one
   # until `ait engine home --migrate` runs.
   #
   # Exports: AITASKS_HOME, AITASKS_HOME_LOCK. Function: aitasks_engine_dir.
   # Idempotent: sourcing this multiple times is a no-op after the first.

   if [[ -n "${_AITASKS_HOME_LOADED:-}" ]]; then
       return 0
   fi
   _AITASKS_HOME_LOADED=1

   export AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"
   # Taken (flock) by `ait engine home --migrate` and refused-against by any
   # `ait` that would otherwise touch the root mid-move.
   export AITASKS_HOME_LOCK="$AITASKS_HOME/.home.lock"

   # aitasks_engine_dir <version|dev> — print the engine slot for one version:
   #   dev        → $AITASKS_HOME/engine/dev
   #   <version>  → $AITASKS_HOME/engine/v<version>   (bare version, no `v`)
   # No trailing slash; callers append "/ait-testmap". Empty arg → usage, 2.
   aitasks_engine_dir() {
       local version="${1:-}"
       if [[ -z "$version" ]]; then
           echo "usage: aitasks_engine_dir <version|dev>" >&2
           return 2
       fi
       if [[ "$version" == "dev" ]]; then
           printf '%s\n' "$AITASKS_HOME/engine/dev"
       else
           printf '%s\n' "$AITASKS_HOME/engine/v$version"
       fi
   }
   ```

   The comment names "the legacy per-user root" without spelling the path, so
   the grep guard's comment-stripping is belt-and-braces, not load-bearing.

2. **`.aitask-scripts/aitask_setup.sh`** — three named-extension edits:
   - after the `data_symlinks.sh` source (`:21-23`), the same shape:
     ```bash
     # Per-user framework root ($AITASKS_HOME) — the engine install dir (t1852_1).
     # shellcheck source=lib/aitasks_home.sh
     source "$SCRIPT_DIR/lib/aitasks_home.sh"
     ```
   - a new step function next to the other `setup_*` helpers (place it just
     before `setup_gate_logs_gitignore()` at `:2345`):
     ```bash
     # --- Per-user framework root (t1852_1) ---
     # $AITASKS_HOME/engine/ is where install_engine_binary() (M1.5) lands the
     # ait-testmap binary. Only the engine root is created here; an existing
     # directory is left with whatever mode it has.
     setup_aitasks_home() {
         if [[ -d "$AITASKS_HOME/engine" ]]; then
             success "AITASKS_HOME:$AITASKS_HOME (engine root present)"
             return
         fi
         info "Creating per-user framework root $AITASKS_HOME/engine ..."
         mkdir -p -m 0755 "$AITASKS_HOME/engine"
         success "AITASKS_HOME:$AITASKS_HOME"
     }
     ```
   - call it from `main()` immediately before `install_global_shim` (after the
     venv tiers, before anything project-side), followed by `echo ""` like its
     neighbours; and in the summary block insert
     `info "  AITASKS_HOME:$AITASKS_HOME"` directly after
     `info "  Python venv: $VENV_DIR"` (`:4511`).

3. **`tests/lib/test_scaffold.sh::setup_fake_aitask_repo()`** — append, with
   the usual why-comment:
   ```bash
   # aitasks_home.sh is sourced at startup by aitask_setup.sh (t1852_1 — the
   # per-user $AITASKS_HOME root) and, from M1.4 on, by the ait-testmap shim.
   # A stdlib-only leaf with no deps.
   cp "$PROJECT_DIR/.aitask-scripts/lib/aitasks_home.sh"      "$repo_dir/.aitask-scripts/lib/"
   ```
   And append `aitasks_home.sh` to the baseline list in
   `aidocs/framework/shell_conventions.md:135-143`.

4. **`tests/test_aitasks_home.sh`** (new). Skeleton from `tests/test_claim_id.sh`
   (`scratch_cwd.sh` → `enter_scratch_cwd`, `asserts.sh`, `PASS/FAIL/TOTAL`
   footer). Every scenario runs in a **subprocess** (`bash -c` with an explicit
   env) and the assertions run in the main shell, so no `( … )` bodies and no
   counter opt-in. `LIB="$PROJECT_DIR/.aitask-scripts/lib/aitasks_home.sh"`,
   `SCRATCH="$(mktemp -d)"` + `trap rm EXIT`, `dir_mode()` copied from
   `tests/test_add_model.sh:110-114` (`stat -c '%a' || stat -f '%Lp'`).

   - **T1 default:** `env -u AITASKS_HOME HOME="$SCRATCH/home" bash -c '. "$1"; printf "%s\n" "$AITASKS_HOME"' _ "$LIB"` → `$SCRATCH/home/.aitasks`.
   - **T2 override:** `AITASKS_HOME="$SCRATCH/x"` → `$SCRATCH/x`; **T3 empty
     override** (`AITASKS_HOME=`) → the default (pins `:-` semantics).
   - **T4 lock var:** `$AITASKS_HOME_LOCK` = `<root>/.home.lock`.
   - **T5 `aitasks_engine_dir`:** `1.2.3` → `<root>/engine/v1.2.3`; `dev` →
     `<root>/engine/dev`; no arg → non-zero exit, stderr contains `usage:`,
     stdout empty.
   - **T6 idempotent:** sourcing twice in one shell succeeds and yields the
     same values (the double-source guard).
   - **T7 setup creates the root:** `HOME="$SCRATCH/home" AITASKS_HOME="$SCRATCH/x" bash -c 'source "$1" --source-only; set +euo pipefail; setup_aitasks_home' _ "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh"`
     → dir exists, `dir_mode` = `755` **under `umask 077`**, output contains
     `AITASKS_HOME:$SCRATCH/x`. Re-run → still `AITASKS_HOME:` and no error.
     Pre-create `engine/` as `700` → re-run leaves it `700` (never chmods).
   - **T8 main-path wiring (bounded, no network):** in a subprocess, source
     `aitask_setup.sh --source-only`, `set +euo pipefail`, then stub **every**
     function `declare -F` lists except `main`, `setup_aitasks_home`, `info`,
     `success`, `warn`, `die` as `<name>() { return 1; }` (the `return 1`
     makes the three opt-in tier probes — `prompt_install_pypy_if_tty`,
     `chat_deps_present`, `dev_deps_present` — answer "no"; nothing in
     `main()` is command-substituted except `command -v bash` / `cat
     VERSION`, so no stub's output is consumed). Run `main` with
     `HOME="$SCRATCH/home" AITASKS_HOME="$SCRATCH/y"`, capture stdout. Assert:
     `$SCRATCH/y/engine` exists with mode `755`; the output contains
     `AITASKS_HOME:$SCRATCH/y` **twice** (the step's `success` line and the
     summary); and in the summary the line immediately after the one
     containing `Python venv:` contains `AITASKS_HOME:` (adjacency pinned
     behaviourally — `grep -n` both, assert `n2 == n1 + 1`). **Negative
     control:** the same run with `setup_aitasks_home` *also* stubbed leaves
     `$SCRATCH/z/engine` absent — proving the directory comes from `main()`'s
     call, not from sourcing. (This replaces a static source grep, which would
     stay green if the call were dropped from `main()`.)
   - **T9 grep guard** (pattern: `tests/test_no_raw_tmux.sh`, header documents
     the scope). Two scopes, both scanned **line by line**:
     - `FEATURE_FILES=( .aitask-scripts/lib/aitasks_home.sh
       .aitask-scripts/aitask_testmap.sh .aitask-scripts/lib/platform_detect.sh
       .aitask-scripts/aitask_engine.sh .aitask-scripts/aitask_test.sh
       .aitask-scripts/aitask_gate_testmap_check.sh )` — whole files owned by
       the feature (the M1/M5/M8 bash pieces the proposal names); an absent
       path is reported `SKIP (not landed)` and not counted.
     - `FEATURE_FUNCTIONS=( "aitask_setup.sh:setup_aitasks_home" )` —
       feature-owned functions inside **shared** files, extracted with
       `awk '/^<name>\(\) \{/,/^}/'` and scanned alone, so the 21 legitimate
       legacy-tenant lines elsewhere in setup neither trip nor shield anything
       (M1.5 registers `install_engine_binary` and `report_testmap_state`).
     - **Exemptions are per line, never per file:** a line carrying the
       trailing marker `# legacy-root-ok: <reason>` is exempt — the one
       sanctioned way for M1.6's migration code to name the legacy root,
       including its `engine` entry (the proposal's known-entry set is
       `{venv, pypy_venv, python, bin, uv, dev_tier, update_check, engine}`
       and the `destination-exists:engine` preflight must read
       `$HOME/.aitask/engine`). The marker is the whole exemption; there is
       no path the marker cannot cover and no file it covers wholesale. Pure-
       comment lines are dropped first.
     - Pattern: `(\$HOME|\$\{HOME\}|~)/\.aitask(/|["'"'"'[:space:]]|$)` —
       matches `~/.aitask/` and `$HOME/.aitask` but not `.aitask-scripts` /
       `.aitask-data` / `.aitask-testmap`.
     - Assertions: the real tree is clean. Negative controls in a temp tree
       (the scanner takes a root argument): (a) a rogue feature file naming
       `$HOME/.aitask/bin` → flagged; (b) the same line with the marker → not
       flagged; (c) **mixed-purpose file**: one marked legacy line
       (`ln -s … ~/.aitask # legacy-root-ok: migration`) plus one **unmarked**
       `$HOME/.aitask/engine/v1` line → exactly one hit, naming the unmarked
       engine line (the marked line shields only itself); (d) function scope:
       a temp `aitask_setup.sh` with a legacy ref outside `setup_aitasks_home`
       and one inside → exactly one hit, the inside one; (e) a comment-only
       mention and a `.aitask-scripts`-only line → not flagged.
   - **T10 no legacy path in the lib** (the task's own acceptance line):
     `grep -c '\.aitask/' "$LIB"` → 0.

5. Run `shellcheck .aitask-scripts/lib/aitasks_home.sh .aitask-scripts/aitask_setup.sh`
   (the second must stay at its current warning baseline) and
   `bash -n` both.

### Post-phase (risk mitigations)

1. [run_setup_fixture_tests] After step 2's `source` line is in
   `aitask_setup.sh` and step 3's scaffold entry exists, run the fixtures that
   copy setup on top of the scaffold — `bash tests/test_setup_help_flag.sh`,
   `bash tests/test_init_data.sh`, `bash tests/test_setup_find_modern_python.sh`
   — and the closure contract
   `bash tests/run_all_python_tests.sh tests/test_shell_startup_closure.py`
   (last-line verdict only). Any red — in particular a
   `No such file or directory` at source time — means a fixture still lacks
   `aitasks_home.sh`; fix the copy path before Step 8, never by softening the
   `source` to a lazy one.

## Verification / acceptance

- `bash tests/test_aitasks_home.sh` → `ALL TESTS PASSED`; `shellcheck` clean
  on the new lib.
- The fixtures that copy `aitask_setup.sh` still boot:
  `bash tests/test_setup_help_flag.sh`, `bash tests/test_init_data.sh`,
  `bash tests/test_setup_find_modern_python.sh`; the closure contract:
  `bash tests/run_all_python_tests.sh tests/test_shell_startup_closure.py`
  (check the last-line verdict only).
- `grep -rn '\.aitask/' .aitask-scripts/lib/aitasks_home.sh` → nothing.
- Manual smoke (optional, network): in a scratch install,
  `AITASKS_HOME=/tmp/x ./ait setup` prints `AITASKS_HOME:/tmp/x` twice (step
  + summary) and `/tmp/x/engine` is `drwxr-xr-x`.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9
(post-implementation). Current-branch profile: no worktree, no merge.

## Risk

### Code-health risk: low
- A new column-0 `source` in `aitask_setup.sh` breaks any fixture that copies setup without the new lib; all seven such fixtures were traced (row 5) and every one goes through `setup_fake_aitask_repo`, a real tarball, or the live tree — a single scaffold entry covers them · severity: low (residual — addressed by inline post-phase run_setup_fixture_tests) · → mitigation: inline post-phase run_setup_fixture_tests

### Goal-achievement risk: low
- None identified. (The one ambiguous acceptance detail — the exact `AITASKS_HOME:` token form — is decided in row 6 and pinned by T7/T8.)

### Planned mitigations
- timing: post-phase | name: run_setup_fixture_tests | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a fixture that copies aitask_setup.sh without the new startup lib | desc: run the three setup-copying fixtures and the startup-closure contract test after the source line lands; red means a copy path is missing
