---
Task: t1747_4_setup_dirty_baseline_probe.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Sibling Tasks: aitasks/t1747/t1747_5_*.md, aitasks/t1747/t1747_6_*.md, aitasks/t1747/t1747_7_*.md
Archived Sibling Plans: aiplans/archived/p1747/p1747_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-21 17:27
---

# t1747_4 — `ait setup`'s dirty baseline must not read "unverified" as "clean"

## Context

Audit rows A9 + A9b (`aidocs/framework/failopen_git_probes.md`). `ait setup`
snapshots which framework paths were already dirty before it writes anything,
then commits only (changed − baseline). Every git probe feeding that baseline
is `2>/dev/null || true`, so a git failure gives an **empty baseline**, which
reads as "nothing was dirty". Setup then commits another session's
uncommitted work under `ait: Add aitask framework`.

**Verify-pass findings** (the code has moved since the plan was written; the
note from t1972 was checked against the code):

1. Line numbers are stale. The functions are now at `aitask_setup.sh` ~4311
   (`_ait_list_framework_changes`), ~4371 (`snapshot_pre_setup_dirty`),
   ~4415 (`commit_framework_files`) and ~4572 (`commit_framework_data_files`).
2. The staged term now has `--no-renames` (t1972). The rewrite keeps it, so
   Test 28c still passes.
3. `snapshot_pre_setup_dirty` captures the **data** baseline first, using only
   the data worktree's own predicate. The main VERSION probe runs after it.
   **So a single `AIT_SETUP_BASELINE_UNVERIFIED` flag, as the task proposed,
   is wrong.** If the main probe failed, it would also refuse the data commit,
   and the other way round, which undoes t1972's "each baseline gated on its
   own committer" rule. This plan uses **two flags**, one per baseline:
   `AIT_SETUP_BASELINE_UNVERIFIED` (main) and
   `AIT_SETUP_DATA_BASELINE_UNVERIFIED` (data).
4. **A consumer the task body missed:** `_ait_gitignore_predates_setup`
   (~:2348) also subtracts the main baseline. Every `.gitignore` helper
   commits through `_ait_commit_gitignore_rule`, and so does
   `setup_data_branch` Step 9. With an empty baseline, those commit a
   `.gitignore` the user had dirty. It has to read the main flag too.
5. **The same polarity in the snapshot's own repo gates:** if
   `rev-parse --is-inside-work-tree` fails while a `.git` is present, it
   currently means "skip the baseline", which leaves it empty. On the data
   side, a `.git` that git cannot read is an unverified baseline, not a
   missing one. On the **main** side, a failed `rev-parse` sets the main flag
   **unconditionally**, not keyed on `$project_dir/.git`. `ensure_git_repo`
   (`:1066`) allows a **subdirectory installation**, where Git finds an
   ancestor repository and there is no local `.git`, and it continues
   automatically when non-interactive. Keying on `.git` would leave the flag
   at 0 there, and a transient failure would sweep once git recovers (review
   reproduced this). When there truly is no repository the flag does no harm:
   every consumer (`commit_framework_files`, `_ait_commit_gitignore_rule`)
   runs its own repo check and stops **before** reading the flag, and not
   committing is the safe direction for `setup_data_branch` Step 9.

`--hooks-only` (~:3291) also calls the snapshot and then
`commit_framework_files`, so the fix covers it without extra work.

## Implementation — `.aitask-scripts/aitask_setup.sh`

### 1. `_ait_list_framework_changes` gets a real exit status

```bash
    local untracked modified staged probe_rc=0
    untracked="$(git -C "$workdir" ls-files --others --exclude-standard \
        -- "$@" 2>/dev/null)" || probe_rc=1
    modified="$(git -C "$workdir" ls-files --modified -- "$@" 2>/dev/null)" || probe_rc=1
    staged="$(git -C "$workdir" diff --cached --name-only --no-renames \
        -- "$@" 2>/dev/null)" || probe_rc=1
    # A partial list is not a smaller dirty set: print nothing on failure.
    (( probe_rc == 0 )) || return 2
    printf '%s\n%s\n%s\n' "$untracked" "$modified" "$staged" \
        | sed '/^$/d' | sort -u | grep -Ev "$exclude_re" || true
```

The trailing `|| true` stays, because `grep -Ev` exits 1 on an empty result.
The function returns 2 *before* printing, so a caller can never treat a
partial list as complete. The header comment gets a sentence on the contract:
0 means verified, 2 means unverified with stdout empty.

### 2. New `_ait_framework_version_tracked` (next to the helper above)

```bash
# Is .aitask-scripts/VERSION in <dir>'s index? 0 = tracked, 1 = genuinely
# untracked (bootstrap), 2 = unverified. `--error-unmatch` exits 1 for an
# untracked path and 128 for a git error, so the two are separable (t1747_4).
_ait_framework_version_tracked() {
    local rc=0
    git -C "$1" ls-files --error-unmatch -- .aitask-scripts/VERSION >/dev/null 2>&1 || rc=$?
    case $rc in 0) return 0 ;; 1) return 1 ;; *) return 2 ;; esac
}
```

Before relying on the rc split, re-measure it in a scratch repo: untracked →
1, not a repo → 128, unreadable index → 128.

### 3. Globals and `snapshot_pre_setup_dirty`

- Declare `AIT_SETUP_BASELINE_UNVERIFIED=0` and
  `AIT_SETUP_DATA_BASELINE_UNVERIFIED=0` beside `AIT_SETUP_BASELINE_ARMED`.
  Add a comment saying that `ARMED` means "a snapshot ran", that `UNVERIFIED`
  means "it ran but could not read the dirty state", and that the two must not
  be merged.
- The snapshot resets both flags to 0 at the top.
- **Data block.** When `.git` is present: if `rev-parse` fails, set
  `AIT_SETUP_DATA_BASELINE_UNVERIFIED=1`. Otherwise capture with
  `local data_rc=0` on its own line, then `… || data_rc=$?`, and set the data
  flag when it is nonzero. Each call carries an `# unverified: …` comment
  directly above it.
- **Main block.**
  - If `rev-parse` fails, set the main flag unconditionally and return (see
    Context 5). The comment names the subdirectory-install case, so nobody
    later "optimises" it into a `.git` check.
  - Then `local vrc=0`, `_ait_framework_version_tracked "$project_dir" || vrc=$?`,
    and `case`:
    - `0` → continue.
    - `1` → `return 0` (the current bootstrap commit-all).
    - otherwise → set the main flag and `return 0`.
  - Then the list capture with `|| list_rc=$?`, which sets the main flag on
    failure.
- Update the function's header comment: what "unverified" means, and that the
  data and main flags are independent.

### 4. Shared refusal message

```bash
# Refuse a framework commit whose pre-setup dirty state could not be read:
# setup's own files left uncommitted are recoverable by re-running setup,
# someone else's work committed under a setup message is not (t1747_4).
_ait_refuse_unverified_commit() {
    local what="$1" recovery="$2"
    warn "Could not read the uncommitted state of $what — framework files were NOT committed."
    warn "Committing without it could sweep someone else's uncommitted work into the setup commit."
    info "Re-run 'ait setup' once git works again, or commit the intended files yourself with $recovery."
}
```

### 5. `commit_framework_files`

- Keep the existing repo bail and the not-armed warning. Then, before listing:
  `# unverified: refuse` → if `AIT_SETUP_BASELINE_UNVERIFIED == 1`, call
  `_ait_refuse_unverified_commit "the framework paths" "'git add' / 'git commit'"`
  and `return`.
- For the list, declare `local list_rc=0` on its own line, then
  `all_changes="$(…)" || list_rc=$?`. A nonzero `list_rc` gets the same
  refusal and return. This replaces the current false
  `success "All framework files already committed"`.
- At the non-interactive blast-radius warning (~:4497), replace the inline
  probe with
  `vrc=0; _ait_framework_version_tracked "$project_dir" || vrc=$?`.
  - `1` → the existing warning, unchanged.
  - `2` → the same warning, prefixed with "Could not verify whether the
    framework is already tracked".
  - The `# unverified:` comment states this is display only: the commit
    itself was gated by the verified snapshot, and over-warning is the safe
    direction for a display.

### 6. `commit_framework_data_files`

The same two refusals: the `AIT_SETUP_DATA_BASELINE_UNVERIFIED` flag, and its
own `list_rc`. Recovery text: `'./ait git add' / './ait git commit'`.

### 7. `_ait_gitignore_predates_setup`

Add `[[ "${AIT_SETUP_BASELINE_UNVERIFIED:-0}" == "1" ]] && return 0` as the
first line, with a comment saying an unreadable baseline counts as "may
predate". Change the two caller messages (~:2021, ~:2365) from "had
uncommitted changes before setup" to "may hold uncommitted changes from
before setup", because they now also cover the unverified case. No test pins
the old wording (grep-checked).

### 8. Call-site table

| helper / flag | call site | polarity | disposition on unverified |
|---|---|---|---|
| `_ait_list_framework_changes` | `snapshot_pre_setup_dirty` (data) | subtrahend | `AIT_SETUP_DATA_BASELINE_UNVERIFIED=1` |
| `_ait_list_framework_changes` | `snapshot_pre_setup_dirty` (main) | subtrahend | `AIT_SETUP_BASELINE_UNVERIFIED=1` |
| `_ait_list_framework_changes` | `commit_framework_files` | minuend | refuse (was a false success) |
| `_ait_list_framework_changes` | `commit_framework_data_files` | minuend | refuse (was a false success) |
| `_ait_framework_version_tracked` | `snapshot_pre_setup_dirty` | bootstrap gate | rc 1 is bootstrap (unchanged); rc 2 sets the main flag |
| `_ait_framework_version_tracked` | `commit_framework_files` | display | warn as for bootstrap |
| main flag | `commit_framework_files`, `_ait_gitignore_predates_setup` | — | refuse / treat `.gitignore` as pre-existing |
| data flag | `commit_framework_data_files` | — | refuse |
| `still_untracked` in `commit_framework_files` | — | display | left as-is (informational) |

## Tests — new `tests/test_setup_failopen_probes.sh`

This is a new file rather than more tests in the 1005-line
`test_setup_git.sh`, which this change leaves untouched. It follows
`tests/test_sync_failopen_probes.sh`:

- It sources `aitask_setup.sh --source-only` the same way `test_setup_git.sh`
  does, and runs in-process.
- The mutant cases run in `( … )` subshells that only **print** observations;
  every assertion is made in the parent shell, so the counters survive.
- The footer resets the baseline globals.

**Shim.** `$T/bin/git` is an argv-keyed shim. When the joined argv matches
`$SHIM_FAIL` (an ERE), it logs to `$SHIM_LOG` and exits 128; otherwise it
`exec`s the real git. It is scoped by saving and restoring `PATH` around only
the call under test. Every fail-closed case asserts the shim fired.

**Mutants.** Each mutant is built with `eval` from a `sed` edit of
`declare -f <fn>`, inside the subshell, so it touches only the probe:
- **A9:** `probe_rc=1` becomes `true`, which restores the `|| true` shape.
- **A9b:** `return 2` becomes `return 1` in `_ait_framework_version_tracked`,
  which restores the conflated shape.
- **Gitignore:** drop the flag line from `_ait_gitignore_predates_setup`.

Each mutant checks that the substitution landed: no `probe_rc=1` (or no
`return 2`) remains. It also checks that the rest of the function survived:
`--no-renames`, `diff --cached` and `grep -Ev` are still there. If either
check fails, the case fails and is never vacuous.

**Fixture (Test 21 shape plus an untracked victim).** A committed fake
project with `VERSION` tracked, plus three pieces of foreign work present
**before** the snapshot:
- an unstaged edit to `placeholder.sh`;
- a staged edit to `staged.sh`;
- a new untracked `foreign_untracked.sh`.

After the snapshot, setup "writes" `newly_installed.sh`.

| # | case | asserts |
|---|---|---|
| P | precondition, no shim | Baseline is non-empty and names all three victims. Both flags are 0. The commit carries `newly_installed.sh` only. |
| 1a–c | snapshot shim fails `ls-files --others` / `ls-files --modified` / `diff --cached` (one probe each) | Shim fired. Main flag is 1. The output carries "NOT committed". HEAD is unchanged. Porcelain still shows ` M placeholder.sh`, `M  staged.sh` (still staged) and `?? foreign_untracked.sh`. |
| 1n | mutant, same three shims | The respective victim **lands in HEAD** (defect observed). |
| 2 | clean snapshot, shim active only during `commit_framework_files` (`ls-files --modified`) | Refuses. No "already committed" success line. HEAD is unchanged. |
| 3 | data twin: VERSION untracked in main plus a Test-28 data repo with a foreign edit; shim `-C .*\.aitask-data .*ls-files --modified` during the snapshot | Data flag is 1 and main flag is 0. The data commit is refused and the edit is still ` M`. The main bootstrap commit still happens (independence). The mutant sweeps the data edit. |
| 4 | A9b: VERSION tracked, foreign edits, data repo present; shim `ls-files --error-unmatch` → 128 | Main flag is 1. The data baseline is still captured and the data flag is 0 (the t1972 note). The main commit is refused and the edits are intact. The mutant takes the bootstrap path and sweeps the foreign edits. |
| 5 | A9b permit | The helper returns 1 (untracked), 0 (tracked) and 2 (not a repo, or under the shim). A genuinely untracked VERSION still commits all with the "first-time framework tracking" warning, and the main flag is 0. |
| 6 | `.gitignore`: user-dirty `.gitignore` plus an unverified snapshot, then `setup_draft_directory` | `.gitignore` is not in any new commit and the user's edit is still dirty. The mutant does commit it. |
| 7a | data `rev-parse` gate: shim fails `-C .*\.aitask-data .*rev-parse --is-inside-work-tree`, during the snapshot only | Data flag is 1. `commit_framework_data_files` refuses, and the data edit is intact. |
| 7b | main `rev-parse` gate, **nested installation**: repo root `R` with aitasks installed in `R/sub` (no `R/sub/.git`), `sub/.aitask-scripts/VERSION` tracked, and a foreign unstaged edit to a tracked `sub/` framework file. The shim fails the main `rev-parse --is-inside-work-tree` during the snapshot only, then is removed (git recovers). | Precondition: `R/sub/.git` is absent and an unshimmed `rev-parse` from `sub` succeeds. Shim fired. Main flag is 1. `commit_framework_files` refuses. `R`'s HEAD is unchanged. The foreign edit is still ` M`. |
| 7n | control for 7b: the same fixture and failed snapshot, then the main flag forced back to 0 (the pre-fix state) before committing | The foreign edit **lands** in the commit, which proves the flag is what protects it. |
| S | call-site scan (awk copied from `test_sync_failopen_probes.sh`, plus its self-test) | `aitask_setup.sh` call sites of the two helpers match the table exactly: 6 rows, each tagged `unverified:`. Each helper is defined once. Tree-wide, only `aitask_setup.sh` calls them. `--error-unmatch -- .aitask-scripts/VERSION` appears once in `aitask_setup.sh`, inside the helper. |

## Verification

```bash
bash tests/test_setup_failopen_probes.sh
bash tests/test_setup_git.sh                 # Tests 20/21/22/26/27/28 unchanged and green
bash tests/test_setup_metadata_commit_scope.sh
bash tests/test_data_branch_setup.sh
bash tests/test_no_unscoped_task_commit.sh
bash tests/test_setup_hooks_only.sh
shellcheck .aitask-scripts/aitask_setup.sh tests/test_setup_failopen_probes.sh
```

The shellcheck baseline for `aitask_setup.sh` has pre-existing SC2015,
SC2034, SC2129 and SC2295 notes. Compare counts before and after; the new
code must add none.

**Final Implementation Notes** must record two things:
- `install.sh:1229` (`_install_version_tracked`-style `&>/dev/null`) has the
  same A9b shape. It is out of scope for this sweep, which covers
  `.aitask-scripts/`.
- The two extra consumers covered beyond the task body: the `.gitignore`
  predicate, and the `rev-parse` gates.

Step 9 (Post-Implementation) handles commit, archival and the
plan-completeness check.

## Risk

### Code-health risk: low
- One file is touched. There is one new helper per concern, the four list
  callers and two VERSION sites are given explicit dispositions, and one
  inline probe that appeared twice becomes a helper. The new tests are in
  their own file. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- A spurious refusal would leave a fresh `ait setup` with framework files
  uncommitted. Refusal needs a real git failure (rc ≥ 2 or a failed capture),
  never just an empty result. Case 5 pins that the bootstrap path is
  untouched, and Tests 20/21/28 stay green. · severity: low · → mitigation:
  covered in-plan (case 5)
- Scope goes slightly beyond the task body: the `.gitignore` consumer and the
  `rev-parse` gates. Both are the same baseline in the same polarity, and
  leaving them would keep the sweep open through a side door. Each has its own
  live case (6, 7a/7b). 7b pins the subdirectory-install layout that
  `ensure_git_repo` permits. · severity: low · → mitigation: covered in-plan
