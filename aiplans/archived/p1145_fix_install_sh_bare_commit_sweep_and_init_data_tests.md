---
Task: t1145_fix_install_sh_bare_commit_sweep_and_init_data_tests.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
---

# Plan: Fix install.sh bare-commit sweep and init-data tests (t1145)

## Context

Two independent defects, both spawned from t1128 during Step 8b review:

1. **`install.sh` bare-commit sweep.** `commit_installed_files` and
   `commit_installed_data_files` finalize with a **bare `git commit`** (no
   pathspec) guarded by a global `git diff --cached --quiet`. On a dirty
   `curl|bash` upgrade a foreign pre-staged index is swept into the framework
   commit. t1128 already fixed the same class in `aitask_setup.sh`
   (`commit_framework_files` / `commit_framework_data_files`, which now
   path-scope both the guard and the commit — see `aitask_setup.sh:2863-2874`
   and `:3012-3019`). The user deferred porting this to `install.sh` out of
   t1128; it is sentinel-gated (`.aitask-scripts/VERSION` tracked) so it never
   fires on a true bootstrap, only on a dirty upgrade.

2. **`tests/test_init_data.sh` — 23/30 checks fail on baseline.** Confirmed a
   pre-existing regression, **not** caused by t1128. Root cause: commit t1069
   added `source "$SCRIPT_DIR/lib/github_release.sh"` at `aitask_setup.sh:19`
   (unconditional, runs even under `--source-only`). The test helper
   `create_data_branch_setup` copies `aitask_setup.sh` and sources it, but the
   scaffold (`setup_fake_aitask_repo`) only stages `python_resolve.sh` (the
   line-15 dep), not `github_release.sh`. Under `set -e` the missing source
   aborts `setup_data_branch`, so no data branch / worktree / symlinks are ever
   created — cascading into the 23 failures across Tests 2,4,5,6,7,8.
   Verified: staging `github_release.sh` (which sources nothing else) makes
   `source aitask_setup.sh --source-only` succeed.

Intended outcome: `install.sh` never sweeps a foreign index; `test_init_data.sh`
returns to 30/30 passing.

## Defect 1 — `install.sh` path-scoped finalize commits

Mirror the t1128 reference in `aitask_setup.sh`. **Subtlety** absent from the
reference: `commit_installed_files` also does a one-time `git rm --cached` of
stale `__pycache__` paths (`install.sh:905-908`), and those paths are filtered
**out** of `changed_files`. If we path-scoped the commit to `changed_files`
alone, an empty array would expand `git commit -- ` to a no-pathspec commit =
the very sweep we are removing. So the finalize pathspec must be
`changed_files` **plus** the `cached_pycache` removal paths, and we must guard
against an empty pathspec.

### `commit_installed_files` (around `install.sh:897-930`)

- After building `changed_files`, introduce a `commit_paths` array seeded from
  `changed_files`. When `cached_pycache` is non-empty, append each pycache path
  to `commit_paths` (so its staged deletion is committed) **before** the
  existing `git rm --cached` call.
- Replace the finalize guard+commit:
  ```bash
  if [[ ${#commit_paths[@]} -gt 0 ]] && \
     ! (cd "$INSTALL_DIR" && git diff --cached --quiet -- "${commit_paths[@]}" 2>/dev/null); then
      ...
      git commit -m "ait: Update aitasks framework to v${version}" -- "${commit_paths[@]}" 2>&1
      ...
  fi
  ```
- Add a short comment matching the reference wording at
  `aitask_setup.sh:2863-2866` (path-scoping stops the foreign-index sweep).

### `commit_installed_data_files` (around `install.sh:1013-1022`)

No pycache path here; `changed_files` is always non-empty at this point (early
return at `:993`). Path-scope directly to `changed_files`:
```bash
if ! git -C "$data_dir" diff --cached --quiet -- "${changed_files[@]}" 2>/dev/null; then
    ...
    git -C "$data_dir" commit -m "ait: Update aitasks framework data to v${version}" -- "${changed_files[@]}" 2>&1
    ...
fi
```
Add the same one-line path-scoping comment (mirrors `aitask_setup.sh:3012-3013`).

## Defect 2 — `tests/test_init_data.sh` scaffold dependency

In `create_data_branch_setup` (around `test_init_data.sh:91`), stage the missing
lib right after the `aitask_setup.sh` copy:
```bash
cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$repo_dir/.aitask-scripts/"
# aitask_setup.sh sources lib/github_release.sh at startup (t1069);
# python_resolve.sh (its other startup dep) is provided by setup_fake_aitask_repo.
cp "$PROJECT_DIR/.aitask-scripts/lib/github_release.sh" "$repo_dir/.aitask-scripts/lib/"
```
Scoped to this helper (only test that sources `aitask_setup.sh`) rather than the
shared `setup_fake_aitask_repo`, per the scaffold's "caller adds script-specific
files on top" design.

## Files to modify

- `install.sh` — `commit_installed_files`, `commit_installed_data_files`.
- `tests/test_init_data.sh` — `create_data_branch_setup`.

## Risk

### Code-health risk: low
- `install.sh` change is a narrowing of an already-guarded, sentinel-gated path,
  mirroring a landed reference (t1128); the pycache-pathspec handling removes the
  one edge case naive path-scoping would break · severity: low · → mitigation: TBD
- `test_init_data.sh` change is test-only (one `cp` line) with no production
  surface · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Both root causes are confirmed (reference diff for #1; `SOURCE_ONLY_OK`
  reproduction for #2); verification is deterministic (30/30 test pass;
  shellcheck clean; diff parity with the reference) · severity: low · → mitigation: TBD

## Verification

1. `bash tests/test_init_data.sh` → expect **30 passed, 0 failed**.
2. `shellcheck install.sh tests/test_init_data.sh` → clean (no new warnings).
3. Inspect `install.sh` diff: both finalize commits now carry `-- "${...[@]}"`
   on the `diff --cached --quiet` guard and the `git commit`, matching
   `aitask_setup.sh` `commit_framework_files` / `commit_framework_data_files`.
4. (Optional sanity) Re-run any setup-adjacent suite touched incidentally to
   confirm no regression.

## Step 9 (Post-Implementation)

Standard cleanup, gate run (`risk_evaluated` recorded post-approval in Step 7),
and archival per the shared task-workflow Step 9.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. (1) `install.sh` —
  `commit_installed_files` now builds a `commit_paths` array (framework
  `changed_files` + the `__pycache__` paths it `git rm --cached`es) and
  path-scopes both the `git diff --cached --quiet` guard and the `git commit`
  to it, plus an `${#commit_paths[@]} -gt 0` empty-pathspec guard;
  `commit_installed_data_files` path-scopes its guard and commit to
  `changed_files`. (2) `tests/test_init_data.sh` — `create_data_branch_setup`
  now `cp`s `lib/github_release.sh` alongside `aitask_setup.sh`.
- **Deviations from plan:** None.
- **Issues encountered:** None. The pycache edge case (empty `changed_files`
  making a naive path-scoped `git commit -- ` sweep the whole index) was
  anticipated in planning and handled via the `commit_paths` union + the
  `-gt 0` guard.
- **Key decisions:** Scoped the test-scaffold `cp` to `create_data_branch_setup`
  (the only helper that sources `aitask_setup.sh`) rather than the shared
  `setup_fake_aitask_repo`, per the scaffold's "caller adds script-specific
  files on top" design. Included the pycache-removal paths in the finalize
  pathspec so the one-time `git rm --cached` cleanup still commits.
- **Upstream defects identified:** None.

**Verification results:** `bash tests/test_init_data.sh` → 30 passed, 0 failed
(was 7/30). `shellcheck install.sh tests/test_init_data.sh` → only the 3
pre-existing install.sh findings (SC2295/SC2043/SC1091) and pre-existing
test-file findings; zero new findings on the changed lines. `bash -n` clean on
both files.
