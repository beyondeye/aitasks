---
Task: t2116_install_dirty_baseline_failopen_probes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2116 — `install.sh`'s dirty baseline must not read "unverified" as "clean"

## Context

t1747_4 (commit 08c0ca972) fixed audit rows A9/A9b of
`aidocs/framework/failopen_git_probes.md` in `aitask_setup.sh`. `install.sh` (the
stand-alone `curl | bash` / `ait upgrade` installer) carries a duplicated twin of
the same machinery. It cannot source the setup helpers, so it was left out of that
sweep. The twin has the same fail-open shape:

- `_install_list_changes` (install.sh ~:1267): all three probes are
  `2>/dev/null)" || true`, so a failed probe produces an **empty list**.
  - It is the **subtrahend** in `snapshot_pre_install_dirty` (~:1310 data,
    ~:1318 main). An empty baseline means `commit_installed_files` /
    `commit_installed_data_files` sweep another session's uncommitted work into
    `ait: Update aitasks framework to v…`.
  - It is the **minuend** in both committers (~:1388, ~:1525), which then report
    a false "already committed".
- `_install_version_tracked` (~:1228, `&>/dev/null`) conflates rc 1 (untracked)
  with rc 128 (git error). `_install_commit_eligible` (snapshot gate, ~:1314)
  combines it with `_install_is_worktree`. A transient failure during the
  snapshot skips the main baseline. If git has recovered by commit time, the
  committer then commits against an empty baseline (commit-all).
- The data block gates on `_install_data_worktree_present`. A present `.git`
  whose `rev-parse` fails is treated as "no data worktree" (empty baseline)
  instead of "unverified".

Install-side difference from setup: an untracked VERSION means **no commit at
all** (`commit_installed_files` skips), not a bootstrap commit-all. So rc 1 stays
"skip the main baseline", and that is consistent because the committer skips
too.

### Readers of the baselines (every one gets a disposition)

`grep` over the repo: `AIT_INSTALL_DIRTY_BASELINE` / `AIT_INSTALL_DATA_DIRTY_BASELINE`
are read only inside install.sh: by `commit_installed_files` (subtract, intersect,
post-commit `still_untracked`) and `commit_installed_data_files` (subtract,
intersect). **There is no `.gitignore`-style side consumer.**
`setup_data_gitignore_symlink_safe`, which main() calls before
`commit_installed_files`, only rewrites the file. Whether `.gitignore` is
committed is decided entirely by `commit_installed_files`, so the main-commit
refusal covers it. No test references the helpers being changed.

## Implementation — `install.sh`

### 1. `_install_list_changes` gets a real exit status
The same shape as `_ait_list_framework_changes` in `aitask_setup.sh:4322`:
- `local untracked modified staged probe_rc=0`
- each capture ends in `|| probe_rc=1`
- `(( probe_rc == 0 )) || return 2`, with the comment
  "A partial list is not a smaller dirty set: print nothing on failure"
- keep the existing `{ grep -Ev "$exclude_re" || true; }` (load-bearing for an
  empty list) and `--no-renames`.

Extend the header comment: returns 0 when the list is verified, and 2 (stdout
empty) when any probe failed (t2116).

### 2. `_install_version_tracked` becomes tri-state
```bash
# Is .aitask-scripts/VERSION in <dir>'s index? 0 = tracked, 1 = genuinely
# untracked (the project does not track the framework), 2 = unverified.
# `--error-unmatch` exits 1 for an untracked path and 128 for a git error.
_install_version_tracked() {
    local rc=0
    git -C "$1" ls-files --error-unmatch -- .aitask-scripts/VERSION >/dev/null 2>&1 || rc=$?
    case $rc in 0) return 0 ;; 1) return 1 ;; *) return 2 ;; esac
}
```
Delete `_install_commit_eligible`: it has no other caller, and its boolean `&&`
is exactly what hid rc 2. Move its "SAME predicate" rationale into the
snapshot's comment. `_install_is_worktree` and `_install_data_worktree_present`
stay; the latter is still the data committer's gate.

### 3. Flags + `snapshot_pre_install_dirty`
- Add `AIT_INSTALL_BASELINE_UNVERIFIED=0` and
  `AIT_INSTALL_DATA_BASELINE_UNVERIFIED=0` next to `AIT_INSTALL_BASELINE_ARMED`.
  The comment says ARMED means "a snapshot ran" and UNVERIFIED means "it ran but
  could not read the dirty state", with one flag per baseline and each flag read
  only by its own committer. Keep them separate from ARMED.
- The snapshot resets both flags to 0.
- **Data block:** `if [[ -d "$data_dir/.git" || -f "$data_dir/.git" ]]`. A
  failed `_install_is_worktree` sets the data flag. Otherwise, capture with
  `|| data_rc=$?`, and a nonzero rc sets the data flag.
- **Main block:**
  - A failed `_install_is_worktree` sets the main flag **unconditionally** and
    returns. The comment covers a nested `--dir` inside an ancestor repo (no
    local `.git`), and notes the flag is inert with no repo because the committer
    bails on its own repo check first.
  - Then `vrc` from `_install_version_tracked`:
    - `0`: continue to the list.
    - `1`: return (the committer skips too).
    - other: set the main flag and return.
  - The list capture uses `|| main_rc=$?`, and a nonzero rc sets the main flag.
- Every helper call site gets an `# unverified: …` comment directly above it
  (needed by the call-site scan).

### 4. `_install_refuse_unverified_commit <what> <recovery>`
Adapted from `_ait_refuse_unverified_commit` (`aitask_setup.sh:4352`):
```bash
warn "Could not read the uncommitted state of $what — the framework update was NOT committed."
warn "Committing without it could sweep someone else's uncommitted work into the upgrade commit."
info "Once git works again, review 'git status' and commit the framework files yourself with $recovery."
```
Unlike setup's text, it does **not** say "re-run ait setup/upgrade". The files a
refused run left dirty are in the *next* run's pre-run baseline, so a re-run
reports them and leaves them alone. Manual commit is the recovery that actually
works. This reasoning is to be confirmed during implementation (see Final Notes
below).

### 5. `commit_installed_files`
- The `_install_is_worktree` bail is unchanged.
- VERSION check: `vrc=0; _install_version_tracked … || vrc=$?`.
  - `1`: the existing "not git-tracked — skipping" message.
  - `2`: `_install_refuse_unverified_commit`. The commit was already skipped
    (safe), but the message falsely said "not tracked".
- After the not-armed warning: if the main flag is set, refuse and return.
- List: `list_rc=0; all_changes="$(…)" || list_rc=$?`. A nonzero rc refuses
  instead of the false "already committed".
- `cached_pycache` (`|| true`) is left alone: a failure skips a cleanup, which is
  the under-destructive direction. `still_untracked` is left alone: it only feeds
  a warning.

### 6. `commit_installed_data_files`
After the armed warning, apply the same two refusals: the data flag, and its own
`list_rc`. Recovery text: `'git -C .aitask-data add' / 'git -C .aitask-data commit'`
(install.sh cannot assume a working `./ait`). Use the same recovery text as the
existing data-branch warnings, following the nearest code.

### 7. Call-site table

| helper / flag | call site | polarity | on unverified |
|---|---|---|---|
| `_install_list_changes` | snapshot (data) | subtrahend | data flag = 1 |
| `_install_list_changes` | snapshot (main) | subtrahend | main flag = 1 |
| `_install_list_changes` | `commit_installed_files` | minuend | refuse (was a false success) |
| `_install_list_changes` | `commit_installed_data_files` | minuend | refuse (was a false success) |
| `_install_version_tracked` | snapshot | baseline gate | rc 1 skips (unchanged); rc 2 sets main flag |
| `_install_version_tracked` | `commit_installed_files` | commit gate | rc 2 refuses with the true reason (was a mislabelled skip) |
| `_install_is_worktree` (rev-parse) | snapshot main / data | gate | main or data flag = 1 |
| main flag | `commit_installed_files` (also covers the `.gitignore` rewrite) | — | refuse |
| data flag | `commit_installed_data_files` | — | refuse |
| `still_untracked`, `cached_pycache` | `commit_installed_files` | display / cleanup | left as-is |

### 8. Doc: `aidocs/framework/failopen_git_probes.md`
Add one current-state sentence under the A9/A9b rows, or in "The detection
boundary". It says `install.sh` is outside the `.aitask-scripts/` audit boundary
but carries the A9/A9b twin (`_install_list_changes`, `_install_version_tracked`),
fixed with the same shape and pinned by `tests/test_install_failopen_probes.sh`.
Table counts are unchanged.

## Tests — new `tests/test_install_failopen_probes.sh`

This mirrors `tests/test_setup_failopen_probes.sh`. It sources
`install.sh --source-only` (the existing test hook), runs `set +euo pipefail`,
and works in-process with `INSTALL_DIR` pointed at each fixture. It reuses the
argv-keyed `with_shim` / `shim_fired`, the fixture helpers (VERSION tracked, plus
an unstaged edit, a staged edit, and an untracked victim), `add_data_repo`, and
`reset_baseline_globals` (for the `AIT_INSTALL_*` globals). Mutants run in `( … )`
subshells that only print; all assertions stay in the parent, so the plain
counters suffice and the file-backed counters are not needed.

Mutants (an eval'd `declare -f` edit, with a check that the edit landed and that
the rest of the function survived):
- **A9:** `probe_rc=1` becomes `true` in `_install_list_changes`.
- **A9b:** `return 2` becomes `return 1` in `_install_version_tracked`.

| # | case | asserts |
|---|---|---|
| P | precondition, no shim | The baseline names all 3 victims, both flags are 0, and the upgrade commit carries `newly_installed.sh` only |
| 1.0–1.2 | snapshot shim on `ls-files --others` / `--modified` / `diff --cached` | Shim fired; main flag is 1; "NOT committed"; HEAD unchanged; porcelain shows ` M`, `M `, `??` intact. Mutant control: the victim lands in HEAD |
| 2 | clean snapshot; shim `ls-files --modified` during `commit_installed_files` only | Refused; no "already committed"; HEAD unchanged |
| 2d | data twin of 2 (`\.aitask-data ls-files --others` during the data committer) | Refused; no false success; data HEAD and index unchanged; new metadata still `??`. Mutant: false "already committed" |
| 3 | VERSION tracked in main plus a data repo with a foreign edit; data-only snapshot shim | Data flag 1, main flag 0; data commit refused and the edit intact; main commit still happens (independence). Mutant sweeps the data edit |
| 4 | A9b: shim `ls-files --error-unmatch` during the snapshot **only**, then git recovers | Main flag 1; data baseline still captured, data flag 0; main commit refused with foreign edits intact. Mutant: snapshot skips, committer (git recovered) sweeps the foreign edit |
| 4c | shim `--error-unmatch` during `commit_installed_files` | Refusal text (not "not git-tracked"); no commit |
| 5 | rc split | untracked 1 / tracked 0 / no repo 2 / shimmed 2 / corrupt index 2 (and the snapshot flags it); untracked VERSION: flag 0 and the committer prints "not git-tracked — skipping" |
| 7a | data `rev-parse` gate shimmed during the snapshot | Data flag 1; data commit refused; edit intact |
| 7b / 7n | nested `--dir` (`R/sub`, no local `.git`); main `rev-parse` shimmed during the snapshot only | Flag 1, refused, `R`'s HEAD unchanged, edit ` M`. Control 7n: forcing the flag back to 0 sweeps the edit |
| E | errexit: inside `( set -euo pipefail; … )`, the failed snapshot plus both committers | Reaches the end (`REACHED`): the refusal paths are errexit-safe for `curl \| bash` |
| S | call-site scan (awk + self-test copied from the setup test) | install.sh rows match the 6-row table, each tagged `unverified:`; each helper is defined once; `_install_commit_eligible` is gone; only install.sh calls the helpers tree-wide; `--error-unmatch -- .aitask-scripts/VERSION` appears once in install.sh |

**Red before the fix:** run the new test file with `INSTALL_SH`-style override
pointing at a `git archive HEAD` export of the pre-fix install.sh. Add an
`INSTALL_SH` env override like `test_install_upgrade_dirty_baseline.sh` has. The
fail-closed cases must fail.

## Verification
```bash
bash tests/test_install_failopen_probes.sh
bash tests/test_install_upgrade_dirty_baseline.sh   # end-to-end upgrade, path-list pin
bash tests/test_setup_failopen_probes.sh            # setup twin untouched
bash tests/test_install_merge.sh                    # one script per `bash` call:
bash tests/test_install_create_data_dirs.sh         # `bash a.sh b.sh` runs only a.sh,
bash tests/test_packaging_cleanup.sh                # passing b.sh to it as an argument
shellcheck install.sh tests/test_install_failopen_probes.sh   # compare counts before/after
```
Also run the red-before-fix proof described above.

Step 9 (Post-Implementation) handles the commit, archival and plan-completeness.

## Risk

### Code-health risk: low
- One production file (install.sh) and one doc sentence change. The edits copy a
  shape that has already landed and been reviewed (`aitask_setup.sh` t1747_4).
  One helper with no other caller is deleted, pinned by the scan · severity: low
  · → mitigation: none needed
- install.sh runs under `set -euo pipefail` via `curl | bash`. A new refusal
  branch that trips errexit would abort an upgrade after extraction · severity:
  low · → mitigation: covered in-plan (case E, plus the existing end-to-end
  `test_install_upgrade_dirty_baseline.sh`)

### Goal-achievement risk: low
- A spurious refusal would leave an upgrade uncommitted. Refusal needs a real git
  failure (rc ≥ 2 or a failed capture), never an empty result. Case P and the
  existing upgrade test pin the normal path · severity: low · → mitigation:
  covered in-plan
