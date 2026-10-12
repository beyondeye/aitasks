---
Task: t1711_gitignore_trailing_slash_leaves_worktree_dirty.md
Base branch: main
Output branch: main
---

# t1711 — `.aitask-data/` trailing slash leaves linked worktrees dirty

## Context

In a linked worktree, `.aitask-data` is a **symlink**
(`ait_link_worktree_data()` in `.aitask-scripts/lib/data_symlinks.sh`). The
directory-only pattern `.aitask-data/` doesn't match it, so the worktree shows
`?? .aitask-data`. Git then refuses `git worktree remove`, which gives
`WORKTREE_KEPT dirty` → `CLEANED_PARTIAL` and the task can't archive.

State of the tree today (verified):

- **This repo's `.gitignore` is already fixed.** Commit `dfbcc0f2a` ("Drop the
  trailing slash from .aitask-data in .gitignore (t1711)") landed the one-line fix
  but left the task `Ready`. No sweep, gate or install-path work was done.
- **New installs still get the bug.** `setup_data_branch` Step 7 in
  `.aitask-scripts/aitask_setup.sh` (~L1910) appends `echo ".aitask-data/"`. Its
  presence check `grep -qxF ".aitask-data/"` would not recognise the corrected
  bare line, so it would append a duplicate block.
- **Existing installs are never repaired.** The legacy-line migration (~L1893,
  t699) rewrites only `aitasks/` and `aiplans/`, and it sits behind
  `setup_data_branch`'s "already configured" early return. Every `ait setup`
  re-run skips it.
- **Sweep result:** the authoritative names are `AIT_DATA_DIR_NAME` (`.aitask-data`)
  plus `AIT_DATA_LINKS` (`aitasks aiplans`). This repo's `.gitignore` has all
  three as bare entries. No other `<name>/` entry names something a worktree
  materialises as a symlink. `aiwork/` and `.aitask-crews/` are real directories
  in the primary, and nothing links them into a worktree.
- **No existing test caught this.** Test 22 in `tests/test_task_worktree_helper.sh`
  links a worktree but tears it down with `--force`. Its fixture repo also has no
  `.gitignore`.

## Implementation

### 1. `aitask_setup.sh` — one shared, idempotent rewriter for the data names

Add a function next to `setup_worktree_dirs_gitignore`. It derives its names from
`data_symlinks.sh`, which is already sourced at L27:

```bash
# --- Symlink-safe data-name gitignore rules (t699, t1711) ---
# In branch mode .aitask-data, aitasks and aiplans are symlinks in every linked
# worktree (ait_link_worktree_data). A trailing-slash pattern matches
# directories only, so `.aitask-data/` leaves the worktree dirty and
# `git worktree remove` refuses. Rewrite the exact legacy `<name>/` line to the
# bare `<name>`, which matches both shapes. Names come from data_symlinks.sh.
# Prints nothing on stdout. Exit status is a three-way contract that callers
# MUST branch on (never collapse 1 and 2):
#   0  rewrote the file
#   1  nothing to do (no .gitignore, or no legacy line) — file untouched
#   2  could not inspect or rewrite (unreadable / not a regular file, not
#      writable, render or rename failure) — the original file is left in place,
#      unmodified, with its mode intact
_ait_render_data_gitignore() {   # renderer for ait_atomic_render: guard awk
    awk -v names="$2" '
        BEGIN { n = split(names, a, " "); for (i = 1; i <= n; i++) want[a[i] "/"] = a[i] }
        ($0 in want) { print want[$0]; next }
        { print }
    ' "$1" || return 1
}
_ait_rewrite_data_gitignore_lines() {
    local gitignore="$1" name legacy=()
    [[ -e "$gitignore" || -L "$gitignore" ]] || return 1
    for name in "$AIT_DATA_DIR_NAME" "${AIT_DATA_LINKS[@]}"; do
        if grep -qxF -- "$name/" "$gitignore" 2>/dev/null; then
            legacy+=("$name")
        else
            [[ $? -eq 1 ]] || return 2        # grep 2 = unreadable/dir, not "absent"
        fi
    done
    [[ ${#legacy[@]} -gt 0 ]] || return 1
    # A read-only .gitignore is the user saying "do not touch". The rename below
    # would replace it anyway, so refuse explicitly (the setup_claude_session_hook
    # precedent for settings.json).
    [[ -w "$gitignore" ]] || return 2
    # shellcheck source=lib/atomic_write.sh
    source "$SETUP_LIB_DIR/atomic_write.sh"
    # Stages beside the (resolved) file, chmods the temp to the file's current
    # mode, renames in, and discards the temp on failure. A hand-rolled
    # mktemp+mv would land the file 0600 and strip other users' read access in
    # a shared checkout. It also follows a symlinked .gitignore instead of
    # replacing the link.
    ait_atomic_render "$gitignore" _ait_render_data_gitignore "$gitignore" "${legacy[*]}" \
        || return 2
    return 0
}
```

Notes:
- **Reuse, don't hand-roll.** `ait_atomic_render` / `ait_atomic_tmp` in
  `.aitask-scripts/lib/atomic_write.sh` already preserve the destination's mode
  (`ait_file_mode` + `chmod`). Setup sources that lib lazily from
  `$SETUP_LIB_DIR`, as `setup_claude_session_hook` does (~L2882). The lib's
  `_AIT_ATOMIC_WRITE_LOADED` guard makes a repeat source a no-op.
- The renderer guards its one fallible command (`|| return 1`), per the lib's
  "RENDERERS MUST NOT RELY ON `set -e`" contract. The lib also refuses a
  zero-byte result, which only matters for a pathological `.gitignore` and maps
  to status 2.
- This also fixes the same mode-stripping flaw in the inline t699 `aitasks/` /
  `aiplans/` migration, which this function replaces.

Every call site captures the status errexit-safely (`rc=0; _ait_rewrite… || rc=$?`;
setup runs under `set -euo pipefail`) and branches on all three values.

(If a bare line already exists next to its legacy twin, both end up as identical
bare lines. That is harmless; the existing Test 12 duplicate-count assertions
only cover fixtures without a pre-existing bare twin.)

### 2. `setup_data_branch` Step 7 — use the rewriter and write the bare form

- Replace the inline `aitasks/` / `aiplans/` awk migration (~L1893–1908) with:
  ```bash
  local rw_rc=0
  _ait_rewrite_data_gitignore_lines "$gitignore" || rw_rc=$?
  case "$rw_rc" in
      0) gitignore_changed=true ;;
      1) ;;
      *) warn "Could not rewrite trailing-slash data entries in .gitignore (left unchanged) — 'ait setup' retries it" ;;
  esac
  ```
  Keep the explanatory comment and point it at the new function. A failure here
  doesn't stop setup. The presence check below then sees no bare line and appends
  the bare block, so the result is still symlink-safe.
- Presence check: `grep -qxF ".aitask-data/"` → `grep -qxF "$AIT_DATA_DIR_NAME"`.
  It runs after the rewrite, so a legacy line has already become bare.
- Appended block: `echo ".aitask-data/"` → `echo "$AIT_DATA_DIR_NAME"`. Keep
  `aitasks` / `aiplans` as they are.

### 3. New re-run repair: `setup_data_gitignore_symlink_safe`

This function is what fixes existing installs on `ait setup`. "Repair" is
`ait setup`'s verb per CLAUDE.md, and the function runs on every setup, unlike
Step 7.

```bash
setup_data_gitignore_symlink_safe() {
    local project_dir="$SCRIPT_DIR/.."
    local rc=0
    _ait_rewrite_data_gitignore_lines "$project_dir/.gitignore" || rc=$?
    case "$rc" in
        0) success "Rewrote trailing-slash data entries in .gitignore to the symlink-safe form" ;;
        1) success "Data entries in .gitignore already symlink-safe" ;;
        *) warn "Could not rewrite trailing-slash data entries in .gitignore — left unchanged."
           warn "  Linked task worktrees will show '?? .aitask-data' and worktree cleanup will keep them."
           warn "  Fix by hand: change '.aitask-data/' to '.aitask-data' (same for aitasks/ aiplans/), or re-run 'ait setup'." ;;
    esac
    return 0   # non-fatal, like every other gitignore step in setup
}
```

- **Placement: immediately before the final `commit_framework_files` in
  `main()`** (~L5010, after `prune_retired_scripts`). It does **not** go next to
  `setup_data_branch`. The `.gitignore` helpers that run between those two points
  commit `.gitignore` themselves without consulting `AIT_SETUP_DIRTY_BASELINE`:
  `setup_draft_directory`, `setup_testmap_gitignore` and others commit
  `-- .gitignore`, and `setup_worktree_dirs_gitignore` does an unscoped commit.
  Any of them, adding its own missing rule, would carry this rewrite **and** a
  user's pre-existing uncommitted `.gitignore` edit into a setup commit. Placed
  last, the only commit that can pick the rewrite up is `commit_framework_files`,
  which subtracts the baseline. Add a comment at the call site saying why it must
  stay last.
- **No commit of its own.** `.gitignore` is in `_ait_framework_paths`, so that
  final `commit_framework_files` commits it, unless `.gitignore` was in the
  pre-setup dirty baseline. In that case the rewrite stays on disk, uncommitted,
  and the existing "Pre-existing uncommitted changes … left alone" warning lists
  `.gitignore`. That is the protected outcome: the fix works locally and the
  user's own edit is never swept.
- Honest scope of the claim: an *earlier* helper can still sweep a dirty
  `.gitignore` when *its* rule is missing. That hazard already exists and is
  independent of this task (see follow-ups). This step guarantees only that
  **the repair itself** never rides an unprotected commit.
- Ungated by mode: the rewrite only touches exact `<name>/` lines, and
  `name` → bare is a superset that matches identically for directories.

### 4. Structural gate — new `tests/test_gitignore_data_symlinks.sh`

This test asks git instead of re-implementing pattern matching. Use the shared
`tests/lib/asserts.sh` and `scratch_cwd.sh`. No subshell bodies, so no
file-backed counters are needed.

- Source `.aitask-scripts/lib/data_symlinks.sh` and build
  `NAMES=("$AIT_DATA_DIR_NAME" "${AIT_DATA_LINKS[@]}")`. Assert the list is
  non-empty, so the test can't pass vacuously.
- `check_gitignore <label> <gitignore-file>`: make a throwaway `git init` repo
  and copy the file in as `.gitignore`. Create a real **symlink** per name
  (`ln -s target <name>`) and a control symlink `ait_t1711_control`. Read
  `git status --porcelain --untracked-files=all`, then:
  - assert no `?? <name>` line for each name;
  - assert `?? ait_t1711_control` **is** reported. That proves the harness is
    still observing.
- Case A — the repo's tracked `.gitignore` (`$PROJECT_DIR/.gitignore`). This
  catches the slash coming back, the line being deleted, or a later `!` negation.
- Case B — the block setup writes for new installs. Source
  `aitask_setup.sh --source-only` and run `setup_data_branch` against a fixture,
  reusing the `setup_local_repo` pattern from `test_data_branch_setup.sh`
  (L295–310). If lifting that fixture would be heavy, cover B in
  `test_data_branch_setup.sh` instead (step 5) and keep this file to Cases A and C.
- Case C — the repair: a `.gitignore` with `.aitask-data/`, `aitasks/`,
  `aiplans/` and an unrelated `foo/` line. Run
  `_ait_rewrite_data_gitignore_lines`: it returns 0, `check_gitignore` passes,
  and `foo/` is untouched. A second call returns 1 (idempotent).
- Case D — the failure path is distinct from "unchanged". Every fault is
  deterministic, independent of the user, and on a fixture holding a legacy
  `.aitask-data/` line:
  - **D1 write failure:** source `atomic_write.sh`, then override
    `ait_atomic_render` with a stub that returns 1. The lib's load guard keeps
    the lazy re-source from restoring it.
  - **D2 uninspectable:** `.gitignore` is a *directory* (grep exits 2). This
    fault holds even when the test runs as root.
  - **D3 read-only:** `chmod 444 .gitignore`. Skip it, with a printed note, when
    `[[ -w ]]` still holds (root).

  For each fault:
  - the rewriter returns **2**, not 1;
  - the file is byte-identical (`cmp` against a saved copy) where it is a file;
  - `setup_data_gitignore_symlink_safe` prints the "Could not rewrite" warning,
    **not** "already symlink-safe", and still returns 0.

  Control: the same fixture with the fault removed returns 0. That proves each
  failure came from the injected fault.
- Case E — mode preserved: `chmod 664` a legacy fixture under `umask 022`. 664
  differs from both mktemp's 0600 and the umask default 0644, so preservation
  can't pass by accident. After a rewrite returning 0, `ait_file_mode` is still
  `664`.
  - Also: a `.gitignore` that is a symlink to a sibling file is rewritten
    *through* the link. The link survives (`-L`) and the target holds the bare
    line.
  - Red proof during implementation: in a scratch copy, swap the render for the
    earlier mktemp+mv and confirm Case E fails with 600. That shows the case
    discriminates.
- Negative control: a `.gitignore` containing the literal pre-fix block
  (`.aitask-data/`). `check_gitignore`'s "not reported" assertion must fail for
  `.aitask-data`. Implement this as a direct porcelain check that expects
  `?? .aitask-data`, so the gate demonstrably detects the defect.

Test-input note (the downstream trap): bash tests here are invoked directly and
there is no UP-TO-DATE caching, so the trap doesn't apply. The test reads
`$PROJECT_DIR/.gitignore` at runtime, though, so add a header comment naming it
as an input for the test-map engine. (The annotation format in
`goengines/.../annot/` is uncommitted work belonging to another session; don't
depend on it.)

### 5. Update `tests/test_data_branch_setup.sh`

- Test 1 (~L356): `assert_file_contains ".gitignore has .aitask-data/" … ".aitask-data/"`
  → exact-line check for bare `.aitask-data` (`grep -qxF`), plus an assertion
  that there is no `.aitask-data/` line. Extend the symlink-porcelain filter
  (~L392) to `(aitasks|aiplans|\.aitask-data)`. In the primary, `.aitask-data` is
  a real dir, so also run the step-4 symlink check against a copy of this
  generated `.gitignore` (this is Case B, if it lands here).
- Test 12 (legacy migration, ~L840): the fixture already starts with
  `.aitask-data/`. Add assertions that it was rewritten to bare `.aitask-data`
  and that exactly one such line exists.
- Test 18 (~L1136): `".aitask-data/"` substring → exact bare-line check.
- New Test: an already-configured repo (`.aitask-data/.git` exists) with a
  legacy `.aitask-data/` line. Run `setup_data_gitignore_symlink_safe`; the line
  is rewritten. This pins the re-run path that `setup_data_branch` early-returns
  past.
- New Test: commit protection. This is the sequence the review used, replayed
  in `main()`'s order with the repair in its final position:
  1. Fixture: a committed `.gitignore` carrying a legacy `.aitask-data/` line,
     **no** `.aitask-testmap/` rule, plus an uncommitted user edit
     (`echo user-edit-t1711 >> .gitignore`).
  2. `snapshot_pre_setup_dirty`, so the baseline records `.gitignore`.
  3. `setup_testmap_gitignore`: the missing rule exists, so it self-commits.
     This is the pre-existing sweep, asserted only as the precondition that it
     ran.
  4. `setup_data_gitignore_symlink_safe`, then `commit_framework_files`.
  5. Assert `git show HEAD:.gitignore` still has the legacy `.aitask-data/`
     line, so the repair was **not** committed. Assert the working tree has bare
     `.aitask-data`, and `git status --porcelain -- .gitignore` shows it
     modified.
  6. Control (clean baseline, same steps): HEAD *does* contain bare
     `.aitask-data`, so `commit_framework_files` really is the committer, and the
     fixture can show the repair being committed.
- Structural pin for the placement: from `aitask_setup.sh`, extract the body of
  `main()` (awk between `^main() {` and the closing `^}`). Assert:
  - `setup_data_gitignore_symlink_safe` appears **after** every
    `setup_*_gitignore` / `setup_draft_directory` / `setup_data_branch` call;
  - the next non-blank, non-`echo` statement after it is `commit_framework_files`.

  A future reorder that reintroduces the sweep then fails loudly.

### 6. Seam test — `tests/test_task_worktree_helper.sh`, new Case 23

This verifies the fix at the layer that broke. Do it once with the fixed file and
once with a pre-fix control:

- `fresh_repo`; `lw_fixture "$REPO"`; write a `.gitignore` and commit it on the
  primary branch.
  - **23a:** use a copy of `$PROJECT_DIR/.gitignore`.
  - **23b:** use the pre-fix block (`.aitask-data/`, `aitasks`, `aiplans`).
- `git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"`;
  `aitask_init_data.sh --link-worktree aiwork/tA`; positive control:
  `.aitask-data` is a symlink.
- 23a: `git -C aiwork/tA status --porcelain` is empty, and
  `run_helper remove tA` (**no `--force`**) reports `WORKTREE_REMOVED`.
- 23b: status shows `?? .aitask-data`, and `run_helper remove tA` reports
  `WORKTREE_KEPT dirty`. This proves the case discriminates.
- Note: `aiwork/` must be ignored in the primary, or the worktree dir shows as
  untracked there. That is the primary's status, not the worktree's, so only the
  worktree's own porcelain is asserted.

`aitask_merge_task.sh cleanup` rolls this verdict up (`WORKTREE_REMOVED` →
`CLEANED`). Asserting the helper's verdict covers the failing link without
standing up the merge-reservation machinery. Step 7 below runs `cleanup`
once end to end by hand.

## Verification

1. `bash tests/test_gitignore_data_symlinks.sh`, `bash tests/test_data_branch_setup.sh`,
   `bash tests/test_task_worktree_helper.sh`, `bash tests/test_init_data.sh`,
   `bash tests/test_applink_setup_gitignore.sh`: all PASS.
2. Red proof: temporarily point Case A at a scratch copy of `.gitignore` with
   `.aitask-data/` restored (never edit the real file) and confirm the gate
   FAILS. Case 23b is the committed red proof at the seam.
3. `shellcheck .aitask-scripts/aitask_setup.sh tests/test_gitignore_data_symlinks.sh`.
4. In a scratch clone fixture, check that `setup_data_gitignore_symlink_safe` run
   twice gives a single rewrite and leaves `git diff` stable.
4b. By hand in a scratch fixture, replay the review's sequence (dirty
   `.gitignore` in the baseline, missing `.aitask-testmap/` rule, repair at its
   final position, `commit_framework_files`). Confirm the repair is absent from
   HEAD and left dirty on disk. Then move the call to right after
   `setup_data_branch` in a scratch copy of the script and confirm the sweep
   reproduces, to prove the test discriminates. The scratch copy is never the
   real file.
5. In a scratch repo, cut a worktree, link it, then run
   `aitask_merge_task.sh cleanup <id> <name>` and confirm `CLEANED` rather
   than `CLEANED_PARTIAL`, as the task asks. If it needs reservation state that
   is hard to fake, record that and rely on Case 23.

## Out of scope / follow-ups to mention at Step 8

- `ait upgrade` (install.sh) doesn't run setup, so an existing install is
  repaired only by `ait setup`. install.sh does source `aitask_setup.sh`
  (L1623), so a one-line call before `commit_installed_files` is possible.
  `commit_installed_files` has no dirty-baseline protection, though. Offer this
  as a follow-up task rather than widening this change.
- The self-committing `.gitignore` helpers in setup (`setup_draft_directory`,
  `setup_testmap_gitignore`, `setup_worktree_dirs_gitignore`, …) ignore
  `AIT_SETUP_DIRTY_BASELINE`. When their own rule is missing, they sweep a user's
  pre-existing `.gitignore` edit into a setup commit.
  `setup_worktree_dirs_gitignore` is worse: its commit is unscoped, a
  whole-index sweep. This predates t1711 and is not introduced by it. This task
  only keeps the repair off those commits. Offer one separate bug task to route
  every `.gitignore` helper through the baseline-protected commit.

## Step 9

Commit code (`bug: … (t1711)`) and the plan separately, then archive via the
standard post-implementation flow (Step 9).

## Risk

### Code-health risk: low
- The new re-run repair edits a user-owned `.gitignore` on every `ait setup` · severity: low · → mitigation: none. It rewrites exact whole lines only, is idempotent, and is placed last so only the baseline-protected `commit_framework_files` can commit it. The placement is pinned structurally and by the dirty-baseline sequence test.
- Replacing `.gitignore` could change its mode, symlink-ness or partial contents · severity: low · → mitigation: none. It goes through `ait_atomic_render`, which preserves mode, follows symlinks, stages on the same filesystem and refuses empty output; Case E pins mode and symlink handling.
- A failed rewrite could be reported as success · severity: low · → mitigation: none. The three-way exit status (0 rewrote / 1 unchanged / 2 failed) is branched on at every call site, and Case D pins it with three injected faults (stubbed render, directory, read-only).
- Moving the t699 migration into a shared function could change its behaviour · severity: low · → mitigation: none. The existing Test 12 assertions pin it, and the new tests extend them.

### Goal-achievement risk: low
- Existing downstream installs are repaired only when the user runs `ait setup`, not on `ait upgrade` · severity: low · → mitigation: none. It is recorded as an out-of-scope follow-up above.

## Post-Review Changes

### Change Request 1 (2026-10-12 18:20)
- **Requested by user:** (1) CRLF `.gitignore` (core.autocrlf=true) was missed:
  the rewriter returned 1, the repair said "already symlink-safe", and the
  linked worktree still showed `?? .aitask-data`. (2) The gate's derived-name
  check asserted a fixed count of 3, so a new canonical data link with a correct
  rule would fail it.
- **Changes made:**
  - Verified first: git strips a trailing CR before matching, so CRLF
    `.aitask-data/` stays directory-only (symlink untracked) while CRLF bare
    `.aitask-data` works.
  - Rewriter detection matches `name/` and `name/\r`. The renderer strips the CR
    only for comparison and re-emits it, so CRLF files stay CRLF byte for byte.
    The Step 7 presence check also accepts the CRLF bare line, so no duplicate
    block is appended.
  - The gate's non-vacuity check is now "data dir + at least one link, all
    bare" with no fixed count or literals. Case C's fixture and expected output
    are built from `NAMES` too (it hardcoded the three names).
  - New Case F: a CRLF legacy fixture. The precondition (git reports the
    symlink) passes, the rewrite returns 0, the bytes are exact with CRLF kept
    and unrelated lines untouched, git status passes for every name, and a
    second run returns 1.
  - Red proofs: the LF-only detector fails Case F. A fourth link plus its rule
    passes (51/51), and without the rule it fails Case A. End to end: a
    core.autocrlf=true clone, repaired then linked, gives a clean worktree
    status and a plain `git worktree remove` exits 0.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`,
  `tests/test_gitignore_data_symlinks.sh`

## Final Implementation Notes
- **Actual work done:** This repo's `.gitignore` was already fixed by `dfbcc0f2a`. This task fixed the install path and added the gates.
  - `setup_data_branch` now writes bare `.aitask-data` for new installs.
  - A shared rewriter, `_ait_rewrite_data_gitignore_lines`, replaces the inline t699 `aitasks/`/`aiplans/` migration. It derives names from `data_symlinks.sh`, is CRLF-aware, uses a three-way exit status, and preserves mode and symlinks via `ait_atomic_render`.
  - A new re-run repair, `setup_data_gitignore_symlink_safe`, runs last in `main()` before `commit_framework_files` and fixes existing installs on `ait setup`.
  - Tests:
    - new `tests/test_gitignore_data_symlinks.sh`: Cases A, C–F plus a negative control, 47 checks;
    - `tests/test_data_branch_setup.sh`: exact-line checks, a symlink check on the generated file, and Tests 33–35;
    - `tests/test_task_worktree_helper.sh`: Case 23, a seam test with a plain `remove`, real vs pre-fix `.gitignore`.
- **Deviations from plan:**
  - Case B (the new-install `.gitignore`) lives in `test_data_branch_setup.sh` through a local `assert_data_symlinks_ignored` helper, as the plan allowed.
  - Case D's planned `TMPDIR` fault no longer applies, because the atomic render stages beside the file. It became D1 (stubbed render), D2 (directory) and D3 (read-only).
  - CRLF handling and the derived-name gate were added in review (see Post-Review Changes).
- **Issues encountered:**
  - `porcelain_for` ran inside `$( )`, so its repo counter never advanced and every check reused one repo. Fixed with `mktemp -d` per call.
  - The first rewriter draft used mktemp+mv, which dropped the mode to 600 and replaced a symlinked `.gitignore`. Replaced with `ait_atomic_render`.
  - Placing the repair after `setup_data_branch` let later self-committing `.gitignore` helpers sweep the repair and a user's dirty `.gitignore` into a setup commit. Moved it to last.
- **Key decisions:**
  - The repair makes no commit of its own and relies on the baseline-protected `commit_framework_files`. A pre-dirty `.gitignore` gets the fix on disk, left uncommitted and reported.
  - The structural gate asks git, never a hand-rolled matcher, and always has a control symlink. Test 35 pins the repair's placement in `main()`.
  - Red proofs (scratch copies only) back each test: slash restored, LF-only detection, mktemp+mv, reordered `main()`, and a fourth link without a rule.
  - Verified end to end that `aitask_merge_task.sh cleanup` gives `CLEANED` with the fix and `CLEANED_PARTIAL:WORKTREE_KEPT=dirty,BRANCH_KEPT=skipped` with the pre-fix block.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:2724` — `setup_worktree_dirs_gitignore` commits with an unscoped `git commit -m` (no `-- .gitignore`). That is a whole-index sweep that can carry a concurrent session's staged files into a setup commit.
  - `.aitask-scripts/aitask_setup.sh` — the self-committing `.gitignore` helpers (`setup_draft_directory`, `setup_python_cache_gitignore`, `setup_gate_logs_gitignore`, `setup_testmap_gitignore`, `setup_shadow_store_gitignore`, `setup_worktree_dirs_gitignore`) ignore `AIT_SETUP_DIRTY_BASELINE`. When their own rule is missing, they sweep a user's pre-existing uncommitted `.gitignore` edit into a setup commit (reproduced in Test 34's control analysis).
  - `install.sh:1623` — `ait upgrade` does not run setup, so `setup_data_gitignore_symlink_safe` reaches existing installs only through `ait setup`. A call before `commit_installed_files` is possible, but that commit has no dirty-baseline protection.
  - `tests/test_cd_guard_lint.sh` — already failing on main: `tests/test_add_model.sh` has no `enter_scratch_cwd` (t1940), and four `unconfined-andchain` cd sites are in `test_aitasks_home.sh:319`, `test_install_engine_binary.sh:224`, `test_setup_hooks_only.sh:74` and `test_upgrade_prunes_retired_scripts.sh:73`.
