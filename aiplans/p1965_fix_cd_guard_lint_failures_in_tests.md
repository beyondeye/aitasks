---
Task: t1965_fix_cd_guard_lint_failures_in_tests.md
Base branch: main
Output branch: main
---

# t1965 — Fix cd-guard lint failures in tests

## Context

`bash tests/test_cd_guard_lint.sh` fails on main with 90 passed and 2 failed. The rule is
defined in `tests/lib/cd_guard_scan.py` and explained in
`aidocs/framework/testing_conventions.md`. Every `cd` must be guarded
(`|| exit 1`) or confined to a subshell `&&` chain, and every test that changes
its cwd must call `enter_scratch_cwd` first. Re-running the lint gives the same 9
sites the task lists. I re-ran it on the current tree, so nothing new has
appeared. All 8 affected test files pass today (baseline recorded), so this is
lint-only cleanup with no behaviour change.

Working on the current branch, because the `fast` profile does not create a
worktree.

## Implementation

### A. Unconfined `&&` chains (4 sites)

1. `tests/test_aitasks_home.sh:319` (`tree_sig`): the subshell runs a
   `while … do …; done` body, so the chain continues past `;`. Rewrite it as a
   guarded cd inside the existing subshell:
   `(cd "$d" || exit 1; find . -print0 | … done)`. On failure the output is the
   same (empty), and `exit 1` exits only the subshell.
2. `tests/test_install_engine_binary.sh:224`: `$(cd "$AH/engine" && ls -A | grep … || true)`
   breaks the chain with `|| true`. Drop the cd:
   `"$(ls -A "$AH/engine" | grep '^\.staging' || true)"`.
3. `tests/test_setup_hooks_only.sh:74` (`make_proj`): the `(` sits on its own
   line, so the cd is not "first inside `(`" on the scanned line. Collapse it to
   one line:
   `(cd "$dir" && git init -q && git add -A && git commit -qm init) >/dev/null 2>&1`.
4. `tests/test_upgrade_prunes_retired_scripts.sh:73` (`build_tarball`): the
   `while` body has a `;`. Use a guarded cd inside the existing subshell:
   `(cd "$PROJECT_DIR" || exit 1; git ls-files … | while …; done) > "$list"`.

A dry run of the scanner over these exact shapes (via `scan_text`) classifies
them as `guarded`, `subshell-andchain` and `guarded`. No violations remain.

### B. Missing `enter_scratch_cwd` (5 files)

Add the following right after `PROJECT_DIR` is derived and `asserts.sh` is
sourced. Each file must have no `$(pwd)` capture before the call and no
`dirname "$BASH_SOURCE"` derivation after it:

```bash
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
```

The 5 files are:
- `tests/test_add_model.sh` (after line 9)
- `tests/test_list_panes_session_scope_live.sh` (after line 24, before the tmux skip check)
- `tests/test_opencode_models_merge.sh` (after line 24)
- `tests/test_opencode_models_reserved.sh` (after line 20)
- `tests/test_setup_hooks_only.sh` (after the `asserts.sh` source, line 26)

I audited the cwd-relative paths in these files. Each one is either inside a
`(cd "$FIX"/"$PROJECT_DIR" && …)` subshell, inside a heredoc or string, or
prefixed with a fixture directory. If a hidden relative write exists, it now
fails loudly with EACCES instead of landing in the repository, which is the
helper's purpose. If that happens, fix it to use an absolute path.

**User-supplied path overrides (review finding: verified and valid).**
`tests/test_opencode_models_merge.sh` takes two overrides from the environment:

- `OPENCODE_MODELS_SCRIPT`, read into `SCRIPT_UNDER_TEST` at line 21.
- `REGISTRY_CAS_LIB`, read inline at line 40.

Both are `cp`'d from the process cwd in `setup_fixture`, outside any fixture
subshell. A relative value such as
`OPENCODE_MODELS_SCRIPT=.aitask-scripts/aitask_opencode_models.sh` resolves from
the invoking directory today. After `enter_scratch_cwd` it would resolve from
the empty scratch directory, and `cp` would fail.

Fix it in that file, before the helper call. Resolve both values once and anchor
relative ones at the invoking directory:

```bash
# abs_path <path> — anchor a relative override at the invoking directory, so it
# still names the same file after enter_scratch_cwd moves the cwd.
abs_path() { case "$1" in /*) printf '%s\n' "$1" ;; *) printf '%s\n' "$PWD/$1" ;; esac; }
SCRIPT_UNDER_TEST="$(abs_path "${OPENCODE_MODELS_SCRIPT:-$PROJECT_DIR/.aitask-scripts/aitask_opencode_models.sh}")"
CAS_LIB_UNDER_TEST="$(abs_path "${REGISTRY_CAS_LIB:-$PROJECT_DIR/.aitask-scripts/lib/registry_cas.sh}")"
```

Line 40 then copies `"$CAS_LIB_UNDER_TEST"`. The file never reassigns
`REGISTRY_CAS_LIB`, so reading it once at startup is equivalent. The
empty-means-default behaviour of `:-` is unchanged. The scanner's `_CAPTURE`
rule targets `VAR="$PWD"`/`"$(pwd)"` captures that a later `cd` returns to.
This helper never stores the cwd and never cds, so it does not trip that rule,
and it does not need to.

I audited the other 4 files for the same pattern:
- `test_list_panes_session_scope_live.sh` has `PYTHON="${PYTHON:-python3}"`, but
  it is only invoked inside `(cd "$PROJECT_DIR" && "$PYTHON" …)`. A relative
  value therefore already resolves against `PROJECT_DIR`, before and after, so
  the scratch cwd does not affect it.
- `test_add_model.sh`, `test_opencode_models_reserved.sh` and
  `test_setup_hooks_only.sh` read no path overrides from the environment.

## Verification

- `bash tests/test_cd_guard_lint.sh` passes with 92/92.
- Re-run each touched file and compare with the baseline (all green):
  `test_aitasks_home`, `test_install_engine_binary`, `test_setup_hooks_only`,
  `test_upgrade_prunes_retired_scripts`, `test_add_model`,
  `test_list_panes_session_scope_live`, `test_opencode_models_merge`,
  `test_opencode_models_reserved`.
- **Relative-override checks** for `test_opencode_models_merge.sh`. The default
  runs above never exercise the overrides.
  - From the repo root:
    `OPENCODE_MODELS_SCRIPT=.aitask-scripts/aitask_opencode_models.sh REGISTRY_CAS_LIB=.aitask-scripts/lib/registry_cas.sh bash tests/test_opencode_models_merge.sh`
    gives 32/32.
  - From `tests/` with `../`-relative values for both overrides: 32/32.
  - Control showing the override is actually consumed:
    `OPENCODE_MODELS_SCRIPT=no_such_script.sh bash tests/test_opencode_models_merge.sh`
    must fail, with `cp` naming `<invoking dir>/no_such_script.sh` and not a
    scratch-dir path.
- `shellcheck` the touched files. No new warnings compared with before.
- Confirm that `git status` in the repo shows no new stray files after the runs.

## Post-implementation

Step 9: commit `test: Fix cd-guard lint failures in tests (t1965)` with only the
8 named paths (the worktree has unrelated dirty files from other sessions), then
archive.

## Risk

### Code-health risk: low
- None identified. The change is test-only and mechanical, made at 9 sites that
  the scanner proves are now accepted. Runtime semantics stay the same, because
  each `cd` keeps its scope and failure output.

### Goal-achievement risk: low
- Moving into the scratch cwd changes how relative user-supplied overrides
  resolve, which the default suite runs cannot see. This is addressed in the plan
  body by `abs_path` and checked in verification.
  · severity: low · → mitigation: inline (plan body, section B)
- Otherwise none identified. The lint result is the acceptance criterion and is checked
  directly. A file that the scratch cwd breaks would fail visibly in verification.

## Final Implementation Notes
- **Actual work done:** Fixed all 9 sites the lint reported, as planned:
  - Rewrote the 4 unconfined `&&` chains. `test_aitasks_home.sh` and
    `test_upgrade_prunes_retired_scripts.sh` use a guarded
    `cd … || exit 1;` inside their existing subshells.
    `test_install_engine_binary.sh` drops its cd for `ls -A "$AH/engine"`.
    `test_setup_hooks_only.sh` collapses its subshell onto one line.
  - Added `enter_scratch_cwd` to the 5 files that were missing it.
  - In `test_opencode_models_merge.sh`, the `OPENCODE_MODELS_SCRIPT` and
    `REGISTRY_CAS_LIB` overrides are now anchored by a local `abs_path`
    before the cwd moves. This was a review finding during planning.
- **Deviations from plan:** Added the repo's conventional comment above each new
  source line: `# Start from an empty read-only dir, never the invoking one (t1826).`
  251 existing adopters use it.
- **Issues encountered:** None. Every file passed on the first run.
- **Key decisions:** I anchored the overrides with a `case`/`$PWD` helper rather
  than `realpath`. `realpath` would need an existing path, and its `-m` flag is
  missing on BSD/macOS. The helper never stores the cwd or cds to it, so it is
  not the "capture the invoking cwd" pattern that the scanner's `_CAPTURE` rule
  targets.
- **Verification:**
  - `test_cd_guard_lint.sh` passes 92/92.
  - All 8 touched files pass, the same as the baseline.
  - The merge test with relative overrides passes 32/32, run from the repo root
    and from `tests/`.
  - With a bogus override the merge test fails, and `cp` names `<invoking dir>/no_such_script.sh`.
  - shellcheck shows nothing new apart from the informational SC1091 "not
    following" note on the new source lines, which the existing adopters share.
- **Upstream defects identified:** None
