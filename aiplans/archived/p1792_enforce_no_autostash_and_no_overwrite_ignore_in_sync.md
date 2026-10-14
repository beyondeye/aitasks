---
Task: t1792_enforce_no_autostash_and_no_overwrite_ignore_in_sync.md
Base branch: main
Output branch: main
---

# t1792 — enforce `--no-autostash` / `--no-overwrite-ignore` in `ait sync`

## Context

`ait sync` makes two promises:

- it never touches files it left protected (live sessions' dirty task files);
- it never clobbers local ignored files (`userconfig.yaml`, `*.local.json`).

The task names three defects:

1. **Autostash.** `do_pull_rebase`'s `pull --rebase` honours a user's
   `rebase.autoStash`, which stashes and re-applies the protected files. The
   behind-only `merge --ff-only` does the same under `merge.autoStash`.
2. **Ignored files.** The behind-only `merge --ff-only` overwrites an ignored
   file that an incoming commit adds. The rebase it falls back to does the same.
3. **Test leakage.** The fixture's `run_sync` inherits the developer's global
   git config.

### Scope

Decided with the user after four plan-review rounds.

**t1792 ships** the parts that are safe under concurrent framework writers today:

- `--no-autostash` on both routes;
- a **pinned, git-protected behind-only fast-forward** with **no rebase
  fallback**. `merge --ff-only` holds `index.lock` for its whole checkout,
  compare-and-swaps HEAD, and with `--no-overwrite-ignore` refuses an ignored
  file at write time;
- fixture config isolation;
- docs stating exactly that guarantee.

**The diverged route** (local commits to replay) keeps `pull --rebase`, now with
`--no-autostash`.

- Its ignored-file protection cannot be made race-free: rebase writes the
  worktree in several steps, and framework writers are only *preflight*-checked
  (`assert_data_worktree_clean`), never excluded. In legacy mode they are not
  checked at all.
- So it moves to a **new follow-up task that depends on t1678**, the data-index
  writer-lock adoption.
- That task carries all four review rounds' findings as its spec; see
  "Follow-up task".

## Findings (line numbers as of 6a3a81efc; the task body's are stale)

- **`do_pull_rebase` (`.aitask-scripts/aitask_sync.sh:1890`).** It runs
  `task_git "${AIT_RECONCILE_GIT_OPTS[@]}" pull --rebase --quiet` (`:1898`).
  Its callers:
  - main's general pull (`:2259`);
  - main's behind-only `merge --ff-only --quiet "@{u}"` (`:2252`), used only
    when protected files exist, with a fallback to `do_pull_rebase` (`:2254`);
  - the push-rejection retry (`:2123`). Its `local_ahead` is always > 0, so it
    is always the diverged route.

  `pull --rebase` itself fast-forwards when there is nothing to replay, with git's
  default overwrite-ignore. So today *every* behind-only pull, protected files or
  not, can overwrite an ignored file.
- **t1731's ignored-file check** is a nested loop over ignored × written paths.
  `ls-files -o -i --exclude-standard` lists 7 entries in `.aitask-data` but
  12,116 in this repo (the legacy-mode shape), too slow per pull. So the shared
  check is indexed.
- **Tests that pin what changes.**
  - `test_sync_branch_mode_automerge.sh` Test 16 asserts that the shim log
    contains `"pull --rebase"`. That still holds: the diverged route keeps the
    pull and only gains a flag.
  - `test_sync_guarded_merge.sh`'s slug scan greps `_gm_refuse <slug>` call
    sites, so those call sites must stay.
- **Direct fixture wrappers that run `aitask_sync.sh`:**
  - `run_sync` (`tests/lib/sync_fixture.sh:186`);
  - `tests/test_sync_deferral_and_quarantine.sh`: `run_sync_seam` (~:105),
    Test 13B (~:463), Test 30 (~:798);
  - `tests/test_sync_failopen_probes.sh`: `run_sync_seam` (~:39),
    `run_sync_wt` (~:55).
- **Out of scope.**
  - `lib/task_utils.sh` `_task_pull_rebase` (`:1316`) and
    `task_data_converge`'s fast-forward (`:1646`) belong to t1956; note them
    there.
  - `test_sync.sh`, `test_sync_branch_mode_automerge.sh` and `test_task_push.sh`
    use their own fixtures, which are not isolated. Offer a follow-up at
    Step 8b.

## Implementation

1. **Probe git's behaviour** in scratchpad repos only (git 2.55.0). Record the
   results in Final Implementation Notes. Any contradiction stops the work and
   goes back to the user.
   - (a) `merge --ff-only` with `merge.autoStash=true` rewrites an unrelated
     dirty tracked file (inode/ctime), and `--no-autostash` does not.
   - (b) `pull --rebase` with `rebase.autoStash=true` succeeds on a dirty
     tracked file, and `--no-autostash` refuses.
   - (c) `merge --ff-only --no-overwrite-ignore` refuses when an ignored file
     sits at, over, or under an incoming path. That includes one created after
     a scan. The refusal leaves HEAD, index and worktree unchanged.
   - (d) Behind-only `pull --rebase` overwrites such a file. This is the
     pre-fix evidence.
   - (e) The recovery commands the docs will give:
     `./ait git rm <path>` + `./ait git commit -m … -- <path>` commits only that
     deletion.
   - (f) The docs' list of ways an incoming commit can track a path this
     checkout ignores. A path that was tracked before its ignore rule was added
     is updated by an ordinary `git add`, with no `-f`.

2. **The behind-only route moves into `do_pull_rebase`.**
   - Remove main's behind-only special case (`:2250-2257`). Main calls
     `do_pull_rebase` whenever `remote_ahead > 0` and no guarded merge
     converged.
   - Move t1725_3's rationale comment into `do_pull_rebase`.
   - Fix the comments that say "main fast-forwards": `_rebase_blocked` rule 5,
     the guarded-merge header, and main's Step 7.
   ```bash
   do_pull_rebase() {
       local remote_count="$1"
       _sync_test_seam pre_pull
       _pull_pin || return 1                 # PULL_H, PULL_U, PULL_BEHIND; else ERROR:pull_preflight_unverified
       if [[ "$PULL_BEHIND" == true ]]; then
           _pull_ff_ignored_check || return 1   # ERROR:pull_overwrites_ignored / pull_preflight_unverified
           _sync_test_seam pre_pull_apply
           iinfo "Fast-forwarding $remote_count new commits..."
           local ff_err="" ff_rc=0
           ff_err="$(task_git "${AIT_RECONCILE_GIT_OPTS[@]}" merge --ff-only --no-autostash \
               --no-overwrite-ignore --quiet "$PULL_U" 2>&1)" || ff_rc=$?
           if (( ff_rc != 0 )); then
               batch_out "ERROR:pull_ff_refused"
               warn "Fast-forward to ${PULL_U:0:12} refused; nothing was changed: ${ff_err//$'\n'/ }"
               return 1
           fi
           return 0
       fi
       iinfo "Pulling $remote_count new commits (rebase)..."
       … task_git "${AIT_RECONCILE_GIT_OPTS[@]}" pull --rebase --no-autostash --quiet …
       … existing conflict / automerge / abort handling, unchanged …
   }
   ```
   - **`_pull_pin`.**
     - Pin `PULL_H` (`HEAD^{commit}`) and `PULL_U` (`@{u}^{commit}`); each must
       match `^[0-9a-f]{40,64}$`.
     - Classify with `merge-base --is-ancestor PULL_H PULL_U`: 0 → behind-only,
       1 → diverged, otherwise `ERROR:pull_preflight_unverified`.
     - The fast-forward targets the pinned `PULL_U`, not `@{u}`, so a commit
       fetched after the check is not applied.
   - **No fallback.** A refused fast-forward is reported, never retried as a
     rebase. That retry was the unprotected fallback the task names.
     - If HEAD moved (a writer committed after the pin), the fast-forward
       refuses, because it compare-and-swaps HEAD. The next sync takes the
       diverged route.
     - Comment: git writes the whole checkout under `index.lock`, so a
       framework writer cannot interleave with it.
   - **The diverged route** keeps `pull --rebase`, plus `--no-autostash`.
     - A comment there states that its ignored-file exposure is known and
       tracked by the follow-up task (name its id once created).
     - It also states why a preflight here would not be a guarantee.

3. **Autostash comments.** At both call sites, explain why the flag is there:
   a user's `rebase.autoStash` / `merge.autoStash` would stash and re-apply the
   files the sweep left protected, which t1599_3 and t1658_1 rejected.

4. **One indexed ignored-file check, shared with the guarded merge.**
   - Add globals `GM_HIT_W` / `GM_HIT_P` and `PULL_H` / `PULL_U` /
     `PULL_BEHIND` next to the other `GM_*` variables.
   - Add `_gm_ignored_hit` after `_gm_collides`. It uses `_gm_collides`'s
     relation (same path, one under the other, case-folded), indexed. It
     returns 0 on a hit (setting `GM_HIT_W`/`GM_HIT_P`), 1 on none, and 2 when
     it cannot list.
     ```bash
     _gm_ignored_hit() {
         GM_IGNORED=(); GM_HIT_W=""; GM_HIT_P=""
         (( ${#GM_WRITTEN[@]} )) || return 1
         _gm_names_into ignored ls-files -z -o -i --exclude-standard || return 2
         (( ${#GM_IGNORED[@]} )) || return 1
         local -A wpath=() wunder=()
         local w p k a
         for w in "${GM_WRITTEN[@]}"; do        # index written paths + their ancestors, case-folded
             k="${w,,}"; wpath["$k"]="$w"; a="$k"
             while [[ "$a" == */* ]]; do
                 a="${a%/*}"; [[ -n "${wunder[$a]:-}" ]] && break; wunder["$a"]="$w"
             done
         done
         for p in "${GM_IGNORED[@]}"; do
             k="${p,,}"
             w="${wpath[$k]:-${wunder[$k]:-}}"     # p written, or a written path under p
             a="$k"
             while [[ -z "$w" && "$a" == */* ]]; do  # p under a written path
                 a="${a%/*}"; w="${wpath[$a]:-}"
             done
             if [[ -n "$w" ]]; then GM_HIT_W="$w"; GM_HIT_P="$p"; return 0; fi
         done
         return 1
     }
     ```
   - **`_pull_ff_ignored_check`.**
     - It sets `GM_WRITTEN=()` and fills it with `_gm_names_into written diff
       --name-only -z --no-renames --diff-filter=d "$PULL_H" "$PULL_U"`.
       Deletions only remove tracked files, so they are excluded.
     - It then calls `_gm_ignored_hit`.
       - Hit → `ERROR:pull_overwrites_ignored`. The warn names both paths with
         `_gm_show`, says nothing was changed, and gives the recovery.
       - A listing failure → `ERROR:pull_preflight_unverified`.

     This check only *names* the file early. Git's `--no-overwrite-ignore` is the
     write-time guard, and it also covers a file created after the scan
     (`pull_ff_refused`).
   - **`_guarded_merge_prepare`.** Its ignored-file block becomes
     `_gm_ignored_hit || ig_rc=$?`. Return 0 →
     `_gm_refuse ignored_written …`; return 2 →
     `_gm_refuse unknown_state "could not list ignored files"`. Slugs and
     wording are unchanged, and it keeps its own written set, deletions
     included.

5. **Seams.** Add these two to the seam list (~:405-428):
   - **`pre_pull`**, before the pin. A commit landing here turns behind-only
     into diverged, which proves the pull never autostashes.
   - **`pre_pull_apply`**, after the ignored-file check and before the
     fast-forward. It proves three things:
     - a file created here is still refused, by git at write time;
     - a commit fetched here is not applied;
     - a commit made here makes the fast-forward refuse, with no fallback.

6. **Isolate git config in the fixture.** In `tests/lib/sync_fixture.sh`:
   ```bash
   # Developer git config never reaches a sweep (t1792): merge.autoStash /
   # rebase.autoStash (or core.hooksPath, an excludesFile, …) there can both hide
   # and invent sync defects. setup_repo's per-repo user.* settings still apply.
   sync_isolate_git_config() { export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1; }
   ```
   Call it inside `run_sync` and inside the 5 direct wrappers listed in
   Findings.

7. **Regression consumers.** Run every regression suite. Change a test that
   pins the old behind-only fallback only after confirming the new outcome is
   the intended one, and record each such change.

8. **New test file `tests/test_sync_autostash_ignored.sh`.**
   - **Setup.** Source `scratch_cwd.sh`, `asserts.sh` and `sync_fixture.sh`.
     Cells run at top level, never in assertion subshells.
   - **Helpers:**
     - `file_ident`: `python3` `os.lstat` → `st_ino st_ctime_ns`;
     - `sha_of`;
     - `pc2`: advances the remote;
     - `racer`: a seam-hook snippet that pushes from a sibling clone and
       optionally fetches locally;
     - `enable_seams` / `run_sync_with_seam`.
   - **Every cell asserts:**
     - its fixture preconditions: the seam fired, pc2 advanced the remote, the
       ignored file is `!!` before the run;
     - the verdict, the protected or private file, and where HEAD ends.
       "Unchanged" means its bytes **and** its `file_ident`.

   | cell | covers | setup | expect |
   |---|---|---|---|
   | C1 / C1c | ff ignores `merge.autoStash` (C1c: control without the config) | behind-only; live lock on t10 + tracked edit; pc2 touches t30; repo `merge.autoStash=true` | `PULLED`; t10 unchanged |
   | C2 / C2c | pull ignores `rebase.autoStash` (C2c: control) | C1's setup plus `rebase.autoStash=true`; `pre_pull` commits a t20 edit (the holder-commits race) | `ERROR:pull_rebase_failed`; t10 unchanged |
   | C3 | ignored-file check, behind-only, protected path | lock on t10 + edit; local userconfig; pc2 `git add -f` userconfig | `ERROR:pull_overwrites_ignored`; bytes unchanged, still `!!`; HEAD unchanged; stderr names the path |
   | C4 | same, no protected files | local userconfig; pc2 force-adds it | as C3 |
   | C5 | no false positive | local userconfig; pc2 touches t30 | `PULLED`; userconfig unchanged |
   | C7 | fixture isolation | test shell `GIT_CONFIG_GLOBAL=<fake: merge.autoStash=true>`; a `pre_group_commit` hook records `git config --get merge.autoStash` | no value (rc=1) |
   | C10 | write-time guard | pc2 force-adds userconfig; no local copy at the check; `pre_pull_apply` creates a private copy | `ERROR:pull_ff_refused`; private copy unchanged; HEAD unchanged |
   | C13 | pinned target | local userconfig; pc2 U (t30); the `pre_pull_apply` racer pushes U', which force-adds userconfig, then fetches it locally | `PULLED`; HEAD == U; userconfig unchanged. A second run gives `ERROR:pull_overwrites_ignored` |
   | C22 | no rebase fallback | pc2 touches t30; `pre_pull_apply` commits a t10 edit through `./ait git` | `ERROR:pull_ff_refused`; branch == the late commit; t30's ident unchanged (nothing written) |

### Post-phase (risk mitigations)

`pin_pull_rebase_to_fetched_upstream` is implemented **for the route t1792
ships**: the fast-forward targets the pinned `PULL_U` (step 2, cell C13). Its
diverged-route half moves to the follow-up task, by the user's scope decision.

1. **[document_sync_ignored_refusal]** Edit
   `website/content/docs/commands/sync.md`, current-state prose only:
   - **How It Works, step 5.**
     - No local commits: sync fast-forwards to the fetched commit. It does not
       fetch again and does not fall back to a rebase.
     - Local commits: it rebases them with `git pull --rebase`.
   - **Auto-commit policy.** The "fast-forwards" bullet gets the same wording.
   - **New subsection, "Stashing and ignored files":**
     - Sync never stashes: it passes `--no-autostash`, so `rebase.autoStash` /
       `merge.autoStash` do not apply.
     - When it fast-forwards, it never overwrites an ignored file (such as
       `aitasks/metadata/userconfig.yaml`). Instead it stops, changes nothing,
       and reports a token.
     - **The limit.** When sync must replay your unpushed commits, git's rebase
       has no such protection. It overwrites an ignored file that an incoming
       commit writes.
     - **How an incoming commit can track a path this checkout ignores.** Being
       ignored here does not stop a commit elsewhere from tracking the same
       path:
       - the path was tracked before an ignore rule was added, and later
         commits update it with an ordinary `git add`;
       - another checkout has different ignore rules (its own
         `.git/info/exclude` or global excludes file);
       - someone force-added it with `git add -f`.
     - **Token table:**

       | token | what to do |
       |---|---|
       | `pull_overwrites_ignored` | Move the named file aside and run `ait sync`, then keep one version. To untrack a shared private file, use the commands verified in step 1(e), publish, and restore your copy. |
       | `pull_ff_refused` | Read git's reason on stderr. If an ignored file is in the way, treat it like the row above; otherwise re-run `ait sync`. |
       | `pull_preflight_unverified` | Re-run `ait sync`. |
     - TUIs show only the token; `ait sync` in a terminal prints the details.
   - **Link check.** Run `python3 check_links.py --build` (in `website/`).

## Follow-up task (create after the Step 8 commit; `depends: [1678]`)

**Title:** *Guarantee sync's diverged rebase never overwrites ignored files
(needs writer exclusion)*.
**Fields:** type `bug`; labels `git`, `syncer`, `robustness`; anchor 1599.

The body records the user's choices:

- **Strategy A.** Refuse unless provably safe.
- **The four review rounds' findings**, each confirmed, as acceptance criteria
  with their repro shapes:
  1. **Replay boundary.** It must be pinned. `--fork-point` / `@{u}` are
     mutable: a merge that incorporates the local work drops the local commit.
  2. **Written set.** It must include each replayed commit's writes, not just
     the endpoint difference (the add-then-remove pair).
  3. **Scan-to-write race.** The rebase has no write-time protection. The
     ignore-rule check must therefore make git's untracked-file protection the
     backstop.
  4. **Late local commits.** Commits made after the pin must never enter the
     replay.
  5. **Exceptions.** `check-ignore -v` exits 0 on a `!negation` match.
     Classify without `-v`. The diagnostic needs `--stdin` with `-z`, and must
     keep the refusal if it fails.
  6. **Re-attach.** A detached-HEAD re-attach done outside git's rebase state
     orphans a writer's commit. Keep git's own finish, or make the re-attach
     atomic. `symref-update` needs git 2.46, which excludes Ubuntu 24.04 and
     Apple git.
  7. **Writer exclusion.** Rebase-state markers are a preflight, not an
     exclusion: `task_git` is a TOCTOU, and legacy mode does no check at all.
     Writer exclusion must be valid across the whole guarded operation in both
     modes. That is t1678's lock.
- **Candidate design.** A guarded `rebase -i` whose pass-through sequence
  editor checks `orig-head` and the branch tip against the pinned HEAD, plus the
  preflight checks, all inside t1678's lock. Include its parity flags
  (`--no-autosquash --empty=drop --no-fork-point -c rebase.updateRefs=false`).
- **Required cells.** C8, C9, C11, C11b, C12, C13b, C15, C16a/b, C18, C19, C20
  and C21 from this task's plan revisions, each with a red-proof mutant.

## After implementation

- **Notes**, via `/aitask-note`:
  - **To t1956:**
    - the behind-only fast-forward now lives in `do_pull_rebase`;
    - `_gm_ignored_hit` is the one ignored-file check;
    - the `task_utils.sh` findings (`:1316`, `:1646`), hedged "as of <commit>".
  - **To t1678:** the new follow-up depends on its lock covering sync's pull,
    from pin to rebase finish, in **both** modes.
    - Legacy mode: `ait_data_inprogress_state` answers empty.
    - Branch mode: `task_git`'s state check is a preflight, not an exclusion.

  On both, `depends:` and `status:` stay unchanged.
- **Step 9 (Post-Implementation):** follow the task-workflow procedure:
  review, commit `bug: … (t1792)`, archive.

## Verification

- `bash tests/test_sync_autostash_ignored.sh` passes in full.
- **Red proofs from isolated mutants.** Copy `ait`, `.aitask-scripts` and
  `tests` into a scratchpad directory, one copy per mutant; never restore or
  stash in the shared worktree. Each mutant must turn only its own cells red:

  | mutant | change | red cells |
  |---|---|---|
  | M1 | ff without `--no-autostash` | C1 |
  | M2 | pull without `--no-autostash` | C2 |
  | M3 | ff without `--no-overwrite-ignore` | C10 |
  | M4 | ignored-file check skipped | C3, C4, C13 second run (token only; git still saves the bytes) |
  | M9 | ff to `@{u}` instead of `PULL_U` | C13 |
  | M11 | no isolation in `run_sync` | C7 |
  | M16 | the old fallback restored (ff refusal → `pull --rebase`) | C10, C22 |
- **Regression.** Run each of these and confirm it still passes:
  - Shell suites: `test_sync_guarded_merge.sh`, `test_sync_rebase_gate.sh`,
    `test_sync_deferral_and_quarantine.sh`, `test_sync_failopen_probes.sh`,
    `test_sync_protect_paths.sh`, `test_sync_auto_commit_scoping.sh`,
    `test_sync_branch_mode_automerge.sh`, `test_sync.sh`,
    `test_sync_holder_pane_live.sh`, `test_metadata_partial_sync_recovery.sh`
    (Cell A: the fast-forward), `test_task_push.sh`.
  - Python suites (`run_all_python_tests.sh --test-dir`):
    `test_sync_action_runner.py`, `test_syncer_rows.py`.
- **Lint and links.** `shellcheck .aitask-scripts/aitask_sync.sh`, then
  `cd website && python3 check_links.py --build`.

## Risk

### Code-health risk: medium
- Isolating git config changes the environment of the 7 fixture-based sync
  test files · severity: low · → mitigation: none (the regression run covers it)
- Moving the guarded merge's ignored-file check into `_gm_ignored_hit` changes
  tested t1731 code · severity: low · → mitigation: none (slugs and messages
  are pinned by `test_sync_guarded_merge.sh`)
- The behind-only route changes: main's special case folds in, every
  behind-only pull becomes a pinned protected fast-forward, and nothing falls
  back to a rebase.
  - A behind-only pull with a dirty unrelated file now fast-forwards where
    `pull --rebase` refused.
  - A fast-forward refused by a racing commit is now reported (re-run) instead
    of rebased.

  severity: medium · → mitigation: none (cells C22 and C5, mutant M16, and
  the regression run, incl. `test_metadata_partial_sync_recovery.sh` Cell A)
- New fail-closed refusals on the behind-only route: an ignored-file collision
  stops sync until the file is moved. Today git overwrites it silently ·
  severity: low (residual: documented, with recovery, by inline post-phase
  document_sync_ignored_refusal) · → mitigation: inline post-phase
  document_sync_ignored_refusal

### Goal-achievement risk: low
- Residual window between the check and `pull --rebase`'s own re-fetch ·
  severity: low (residual — closed for the behind-only route by inline
  post-phase pin_pull_rebase_to_fetched_upstream (pinned `PULL_U`, C13); the
  diverged route moves to the follow-up task) · → mitigation: inline post-phase
  pin_pull_rebase_to_fetched_upstream
- The diverged route can still overwrite an ignored file that an incoming
  commit adds. This was outside the task's three named defects, discovered in
  review, and cannot be made race-free without t1678 · severity: low ·
  → mitigation: none (the follow-up task, depending on t1678; documented in
  code and in sync.md)

### Planned mitigations
- timing: post-phase | name: pin_pull_rebase_to_fetched_upstream | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: residual window between the ignored-file check and pull --rebase's own re-fetch | desc: rebase onto exactly the upstream SHA the guard examined (no second fetch) and test a remote commit arriving between check and apply
- timing: post-phase | name: document_sync_ignored_refusal | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: new user-visible ERROR:pull_overwrites_ignored refusal with no user doc | desc: document in sync.md that sync never stashes or overwrites ignored files, the refusal token, and verified recovery steps

## Post-Review Changes

### Change Request 1 (2026-10-14 17:20)
- **Requested by user:** (1) the new refusal warnings passed `_gm_show`-quoted
  paths and git's error text through `warn()`, whose `echo -e` decodes escapes;
  a newline in a filename split the line and an escape sequence could reach the
  terminal. Print them verbatim and add a newline/control-character filename
  assertion. (2) The new test defined `dhead()`, a duplicate of the fixture's
  `data_head()`.
- **Changes made:**
  - `aitask_sync.sh`: new `_warn_verbatim` (colour via `%b`, message via
    `%s`) and `_one_line` (newline → space, other control characters → `?`).
    The `pull_overwrites_ignored` and `pull_ff_refused` warnings use them.
  - Test: `dhead` removed and every call site now uses `data_head`. `sha_of`
    hashes from stdin, because GNU `sha256sum` escapes a filename that contains
    a newline. Two cells were added:
    - **C3b:** a name with a newline and ESC; the `%q` form is printed verbatim
      on one line.
    - **C10b:** a name with a newline and a literal `\e`. Git already turns
      control characters into `?` in its own message, but `echo -e` would
      decode the `\e`.
  - New mutants M17 (hit message back to `warn`) and M18 (ff message back to
    `warn`) turn only C3b and only C10b red, respectively.
- **Files affected:** `.aitask-scripts/aitask_sync.sh`,
  `tests/test_sync_autostash_ignored.sh`

## Final Implementation Notes
- **Actual work done:** Implemented the approved split scope.
  - `aitask_sync.sh`:
    - `do_pull_rebase` now pins `PULL_H`/`PULL_U` (`_pull_pin`).
    - A behind-only branch gets `_pull_ff_ignored_check`, then
      `merge --ff-only --no-autostash --no-overwrite-ignore "$PULL_U"`, with no
      rebase fallback. A refusal emits `ERROR:pull_ff_refused`.
    - The diverged route runs `pull --rebase --no-autostash`.
    - Main's behind-only special case is folded into `do_pull_rebase`.
    - `_gm_ignored_hit` is the one indexed ignored-file check, shared with
      `_guarded_merge_prepare` (slugs and wording unchanged).
    - New seams: `pre_pull`, `pre_pull_apply`.
    - New tokens: `ERROR:pull_overwrites_ignored`, `ERROR:pull_ff_refused`,
      `ERROR:pull_preflight_unverified`.
  - Fixture: `sync_isolate_git_config` is called in `run_sync` and in the 5
    direct wrappers.
  - New `tests/test_sync_autostash_ignored.sh`: 83 assertions; cells C1, C1c,
    C2, C2c, C3, C3b, C4, C5, C7, C10, C10b, C13, C22.
  - `sync.md`: How It Works step 5, the Auto-commit policy bullet, and the new
    "Stashing and ignored files" section (tokens, recovery, the diverged
    limitation, and the three ways an ignored path can be tracked).
  - Follow-up **t1984** was created for the diverged route (depends on t1678);
    it carries all four review rounds' findings and the required cells.
- **Deviations from plan:**
  - t1984 was created before the code commit rather than after, so the code
    comment in `do_pull_rebase` could name its real id.
  - The ff refusal uses `_warn_verbatim`/`_one_line` (Change Request 1).
  - `sha_of` hashes from stdin (see Issues encountered).
- **Issues encountered:**
  - Probe (c) showed git itself already renders control characters in its
    "would be overwritten" message as `?`. C10b therefore uses a *literal* `\e`
    in the filename, which git leaves alone but `echo -e` would decode; that is
    what makes M18 red.
  - GNU `sha256sum` escapes a filename containing a newline and prefixes the
    digest with `\`.
  - `run_all_python_tests.sh` with positional paths ran the whole suite, so the
    two sync Python files were run directly with the venv pytest (240 passed).
- **Key decisions:**
  - The writer-coordination concern (review round 4) was handed to t1678/t1984
    instead of being engineered here, by the user's scope decision.
  - `merge --ff-only` holds `index.lock` across its checkout and moves HEAD only
    from the HEAD it read, so the behind-only route is safe against concurrent
    framework writers.
  - A refused fast-forward is reported, not retried as a rebase.
- **Verification:**
  - Probes (a)-(f) were all confirmed on git 2.55.0 in scratch repos. Recovery
    commands: `git rm` + `commit -- <path>` commits only the deletion and leaves
    other staged entries staged.
  - Mutants M1, M2, M3, M4, M9, M11, M16, M17 and M18 each turn only their
    intended cells red. M3, M4 and M16 also turn red the odd-name variants of
    their own scenarios (C3b, C10b).
  - Regression: all 11 shell suites pass (guarded merge 147, automerge 166,
    deferral 138, task_push 365, …), the 240 Python sync tests pass,
    shellcheck shows info notes only, and `check_links.py --build` passes.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/task_utils.sh:1316` — `_task_pull_rebase` runs
    `pull --rebase` without `--no-autostash` (the pick-time pull; owned by
    t1956, handed over by note).
  - `.aitask-scripts/lib/task_utils.sh:1646` — `task_data_converge`'s
    `merge --ff-only` has neither `--no-autostash` nor `--no-overwrite-ignore`
    (owned by t1956, handed over by note).
  - `tests/test_sync.sh`, `tests/test_sync_branch_mode_automerge.sh` and
    `tests/test_task_push.sh` run `aitask_sync.sh` through their own fixtures,
    which still inherit the developer's global and system git config (the same
    leak t1792 fixed in `sync_fixture.sh`).
  - `tests/test_linked_trail_jump_live.sh:164` — it cd's without calling
    `enter_scratch_cwd`, so `tests/test_cd_guard_lint.sh` fails on the live
    tree. This predates t1792 (commit aa6b5fb2a).
