---
Task: t1747_3_sync_authorization_probes.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
Worktree: aiwork/t1747_3_sync_authorization_probes
plan_verified:
  - claudecode/opus5 @ 2026-09-11 11:26
---

# t1747_3 — Four fail-open authorization probes in `aitask_sync.sh`

## Context

Audit rows **A3, A4, A5 and A10** of the t1747 sweep. The rule, the fix shape and
the dispositions live in `aidocs/framework/failopen_git_probes.md`; point at that
doc, do not restate it.

Each row is a git probe whose failure reads as the permissive answer:

- A3 reads "nobody staged these paths";
- A4 reads "this quarantined path is settled";
- A5 reads "the pull did not stop on a conflict";
- A10 reads "the data worktree is not wedged".

Each probe gates an action that destroys in-flight work, or publishes a commit the
framework deliberately withheld.

> Citations are `file::function` first. Line numbers are as of **`e2f12c499`**
> (t1731), the last commit to touch `aitask_sync.sh`. The file moved twice during
> this planning pass (t1725_4 at `76a113510`, then t1731), so re-resolve by function
> name before editing.

## What this verification pass changed

1. **Line numbers re-resolved.** All four sites moved:
   - `_sync_gitdir:538`
   - `_quarantine_path:547`
   - `_worktree_wedged:591`
   - `_quarantine_load_and_prune:862` (A4 probe `:890`)
   - `_quarantine_persist:917`
   - `auto_commit:952`
   - `_commit_group` (A3 probe `:1235`)
   - `do_pull_rebase:1832` (A5 probe `:1842`)
   - `main` Step 1b (`:2076`)
2. **A10 reuses an existing seam.** `lib/task_utils.sh::_data_wedge_gitdir:274`
   (t1725_1) already resolves the git-dir *by mode, never by emptiness*. That is
   exactly the distinction `_sync_gitdir` lacks. `_sync_gitdir` has **two**
   fabricated fallbacks, not one:
   - (a) When a branch-mode `_ait_data_gitdir` answers `''`, it falls through to the
     **code** repo's `git rev-parse --git-dir` — a real directory, but of the
     *wrong* repository.
   - (b) A failed `rev-parse` becomes `.git`.

   (a) is the reachable one. In any linked worktree `.git` is a file, so
   `_ait_data_gitdir`'s fast path misses and
   `git -C .aitask-data rev-parse --absolute-git-dir` runs. Every `aiwork/` worktree
   takes that route, including this task's.
3. **Mode detection cannot flip under us.** `_ait_detect_data_worktree` decides the
   mode by the *presence* of `.aitask-data/.git`. That is a pure filesystem rung,
   not a git call, and it caches the result in `_AIT_DATA_WORKTREE`, which `$( )`
   subshells inherit. So a data worktree whose git-dir becomes unreadable
   mid-run stays `branch` mode. `_data_wedge_gitdir` then answers `''` rather than
   silently resolving the code repo's git-dir. Both the A10 fix and Test 17 rely on
   this.
4. **A5 premise corrected.** At the probe, `pull --rebase` has just stopped and
   nothing has been resolved yet; the auto-merge loop runs *after* the probe.
   - A **successful** `rebase --abort` therefore loses no work: it restores the
     pre-pull local commits.
   - The harm of the fail-open is **misclassification**: a real conflict is reported
     as `ERROR:pull_rebase_failed` ("non-conflict error").
5. **A5 recovery must be verified, not assumed** (Step-6 reviews, 2026-09-10/11).
   The condition that fails the probe — index contention, or an unreadable git-dir
   — can fail the abort too. A diagnostic that says "local commits intact" after
   `rebase --abort … || true` can describe a recovery that never happened, while
   the shared worktree stays wedged and blocks every session's task writes.

   So the branch captures the abort's rc, then re-inspects the worktree, and the
   **verified state** decides the token. The abort's exit code does not, because the
   two can disagree in both directions:
   - the abort fails with "no rebase in progress" over a clean tree;
   - the abort succeeds but leaves a sentinel behind.

   All three outcomes are driven by tests, including the one where the state cannot
   be inspected at all (Test 17).
6. **A3 reuses the existing `unverifiable` sub-reason.** It is already in
   `DEFERRED_FILE_REASONS`, and `_commit_group`'s re-hash check already emits it.
   - `staged_elsewhere` would falsely claim that another session staged something.
   - A new reason would widen a closed, two-language vocabulary for no gain.

   **No Python change.**
7. **The new tokens are all `ERROR:` suffixes.** `parse_sync_output` maps any
   `ERROR:<msg>`, and `TokenContractTest` probes `ERROR:x`. No `DEFERRED` reason is
   added: an unresolvable git-dir or a failed abort is a fault, and a deferral would
   render as a benign warning.
8. **t1731 has landed (`e2f12c499`) and is archived.** The planned pre-edit note to
   it is dropped as obsolete. Overlap, re-assessed against the landed code:
   - It adds **no** consumer of `_sync_gitdir`, `_quarantine_path` or
     `_worktree_wedged`, and touches none of the four probes.
   - Its guarded merge (`_guarded_merge_prepare`, `_converge_by_guarded_merge`)
     captures rc on its own probes and reads no git-dir. By design it leaves no
     `MERGE_HEAD` and never runs `--abort`.
   - `main` Step 1b (`:2076`) still runs before `auto_commit` (`:2088`), the guarded
     merge (`:2136`) and `do_pull_rebase` (`:2167`). So A10's refusal covers the new
     merge path too.
   - The publication-quarantine exits run before the guarded merge, so A4 and A10
     still gate its push.

   `aitask_sync.sh` has no remaining concurrent editor. The isolated worktree (a
   user decision) is kept: `main` still moves, and the worktree exercises A10's
   route.
9. **Sibling finding, not fixed here.** In `lib/task_utils.sh`, `_data_wedge_state`
   passes `''` to `_ait_inprogress_state_at`, which answers "clean" when the git-dir
   cannot be resolved. As a result `assert_task_data_writable:396` passes, and
   `ait_pull_mutex_acquire:1073` runs unlocked. Same class, but outside Group A: it
   goes to t1747_7 as a note and into the Upstream-defects bullet.

### Pre-phase (risk mitigations)

1. [baseline_sync_suites] In the fresh worktree, before any edit, run the suites
   listed under Verification on the unmodified tree. Record PASS/FAIL/TOTAL per file
   in the Final Implementation Notes. A red baseline is reported, not fixed.
2. [measure_a10_discriminator] Before writing the rest of the suite, build the A10
   linked-worktree fixture (Test A10-1 below) and confirm that the **unmodified**
   code publishes the withheld commit under the `--absolute-git-dir` shim. If it
   does not, stop and re-plan; never weaken the assertion to fit.

## Implementation

### 1. A10 — `_sync_gitdir` and its whole consumer set

```bash
# The git-dir that owns the data worktree, resolved by MODE (never by emptiness)
# through lib/task_utils.sh::_data_wedge_gitdir. 0 + path on stdout; 2 = could not
# be resolved, nothing printed. Never a default: a fabricated dir composes into the
# wedge check and the quarantine ledger. aidocs/framework/failopen_git_probes.md
_sync_gitdir() {
    local gd
    # unverified: empty from either mode ⇒ 2
    gd="$(_data_wedge_gitdir)"
    [[ -n "$gd" ]] || return 2
    printf '%s' "$gd"
}

_quarantine_path() {
    local gd
    # unverified: propagate 2
    gd="$(_sync_gitdir)" || return 2
    printf '%s/ait-sync-quarantine' "$gd"
}

# 0 = wedged (state on stdout) · 1 = not wedged · 2 = git-dir unresolvable
_worktree_wedged() {
    local gd st
    # unverified: propagate 2 — "cannot look" is never "not wedged"
    gd="$(_sync_gitdir)" || return 2
    for st in rebase-merge …; do …; done
    return 1
}
```

- **`main` Step 1b.** Use an absorbing capture, with `local` on its own line:
  `wedged="$(_worktree_wedged)" || w_rc=$?`, then a `case` on `w_rc`:
  - `0` → today's `DEFERRED:worktree_wedged`, unchanged.
  - `2` → `_note_skip`, `report_skipped`, `batch_out "ERROR:data_gitdir_unresolved"`,
    and an `iwarn` that names the recovery:
    - `git -C .aitask-data rev-parse --absolute-git-dir` shows why;
    - `ait setup` repairs the layout;
    - `git worktree repair` re-links a moved worktree.

    Then **`exit 1`**, the exit every existing `main` `ERROR:` route uses. This
    runs before `check_remote`, `auto_commit` and the guarded merge, so nothing is
    swept, merged or published.
- **`auto_commit`** becomes the **only** consumer of `_quarantine_path`:
  `qf="$(_quarantine_path)" || q_rc=$?`. On `2`, remove `$dirtyf`, emit the same
  token, and `exit 1` — **before** the data-index lock is taken, so no lock is left
  held. This branch is reached only if resolution flips between Step 1b and here,
  but its behaviour is still explicit.
- **`_quarantine_load_and_prune "$qf"` (×2) and `_quarantine_persist "$qf"`** take
  the verified path as `$1` and resolve nothing themselves. Four resolution sites
  collapse into one, so no consumer can silently start a fresh, empty ledger.

### 2. A4 — `_quarantine_load_and_prune` settlement clause

Hoist the probe out of `[[ -z "$(…)" ]]`, where a failed substitution is invisible:

```bash
if [[ "$verdict" == "free" || "$verdict" == "dead" ]]; then
    # unverified: an UNREADABLE worktree is not settled ⇒ hold
    st_rc=0
    st="$(task_git status --porcelain -- "$p" 2>/dev/null)" || st_rc=$?
    if (( st_rc == 0 )) && [[ -z "$st" ]]; then
        iinfo_err "quarantine released (owner gone, state settled): $p"; continue
    fi
    (( st_rc == 0 )) || unread=1
fi
```

- Declare `st`, `st_rc` and `unread` in the function's `local` list, and reset
  `unread` on every iteration.
- When `unread` is set, the hold message says the owner is gone but the path's
  state could not be read (with the rc), so the entry was not released. It names the
  ways out: re-run sync, check `./ait git status`, or release deliberately with
  `./ait sync --release-quarantine`.

### 3. A3 — `_commit_group` staged guard

```bash
local staged="" s_rc=0
# unverified: cannot read the shared index ⇒ defer, same outcome as a detection
staged="$(task_git diff --cached --name-only -- "${paths[@]}" 2>/dev/null)" || s_rc=$?
if (( s_rc != 0 )); then
    _protect_group_paths "unverifiable" "$tid" \
        "t${tid}: %PATH% — could not read the shared index (git diff --cached rc=${s_rc}), so whether another session staged these paths is unknown; the group was deferred. Re-run sync once the index is readable."
    return 0
fi
```

It goes exactly where the current guard is, before any `add`, `commit -o` or
`reset`.

### 4. A5 — `do_pull_rebase` conflict classifier, with a verified recovery

```bash
local conflicted="" c_rc=0
# unverified: could not tell conflict from non-conflict ⇒ abort, then VERIFY
conflicted="$(task_git diff --name-only --diff-filter=U 2>/dev/null)" || c_rc=$?
if (( c_rc != 0 )); then
    local a_rc=0 w_rc=0 wstate=""
    task_git rebase --abort >/dev/null 2>&1 || a_rc=$?
    # unverified: the recovery is judged by the worktree's STATE, never by the
    # abort's rc — "cannot inspect" is not "recovered"
    wstate="$(_worktree_wedged)" || w_rc=$?
    case $w_rc in
        1)  batch_out "ERROR:pull_conflict_unverified"
            warn "…could not tell whether pull --rebase stopped on a conflict (git diff rc=$c_rc); the rebase was aborted and the worktree verified clean — your local commits are intact. Re-run sync." ;;
        0)  batch_out "ERROR:rebase_abort_failed"
            warn "…and the recovery FAILED: rebase --abort rc=$a_rc, the data worktree is still mid-${wstate}. Every task write is blocked until it is resolved: ./ait git rebase --abort (or resolve, then ./ait git rebase --continue); ./ait git status shows where it stopped." ;;
        *)  batch_out "ERROR:rebase_abort_unverified"
            warn "…rebase --abort rc=$a_rc, and the data worktree's state could not be inspected, so the recovery is UNVERIFIED — do not assume your local commits are intact. Check ./ait git status; if it is mid-rebase: ./ait git rebase --abort." ;;
    esac
    return 1
fi
```

- `do_pull_rebase` returns 1 on all three outcomes, so `main`'s existing `exit 1`
  stands.
- The `do_pull_rebase::ait_automerge_advance` call that t1747_2's Test 13 pins does
  not move.
- The five existing `rebase --abort … || true` calls in `do_pull_rebase` (`:1866`,
  `:1874`, `:1927`, `:1932`, `:1938`) remain the canonical doc's negative-space
  rows. They are best-effort recoveries whose messages claim nothing, and a wedge
  they leave is caught on the next run by Step 1b's `DEFERRED:worktree_wedged`. The
  new branch differs because it *claims* an outcome, so it must verify one.

### 5. Call-site table

| helper | consumer (`aitask_sync.sh::…`) | on "unverified" |
|---|---|---|
| `_data_wedge_gitdir` | `_sync_gitdir` | empty ⇒ `return 2` |
| `_sync_gitdir` | `_worktree_wedged` | `return 2` |
| `_sync_gitdir` | `_quarantine_path` | `return 2` |
| `_worktree_wedged` | `main` (Step 1b) | `ERROR:data_gitdir_unresolved`, `exit 1`, before anything mutates |
| `_worktree_wedged` | `do_pull_rebase` (A5 recovery check) | rc 2 ⇒ `ERROR:rebase_abort_unverified` — never read as recovered (Test 17) |
| `_quarantine_path` | `auto_commit` | `ERROR:data_gitdir_unresolved`, `exit 1`, before the lock |
| *(verified `$qf` arg)* | `_quarantine_load_and_prune` ×2, `_quarantine_persist` | no resolution of their own |
| inline probe | `_commit_group` (A3) | defer the group, `unverifiable` |
| inline probe | `_quarantine_load_and_prune` (A4) | hold |
| inline probe | `do_pull_rebase` (A5) | abort, verify, then one of three distinct tokens |

`_data_wedge_gitdir`'s own consumers in `lib/task_utils.sh` belong to the sibling
finding and are **not** in this table.

## Tests

### New `tests/test_sync_failopen_probes.sh` — A3, A4, A10 and the call-site scan

**Harness.** Test bodies run at top level, with no subshells, so the file needs no
counter opt-in. It sources `tests/lib/asserts.sh` and `tests/lib/sync_fixture.sh`.

- It reuses `setup_repo`, `plant_lock`, `lock_yaml_live/dead`, `run_sync` and
  `data_log` from the fixture.
- It copies `advance_remote`, `remote_data_sha`, `quarantine_file`, `enable_seams`
  and `run_sync_seam` from `test_sync_deferral_and_quarantine.sh`.
- It adds `run_sync_wt`: the same as `run_sync`, but with `cd "$tmpdir/wt"`. It
  stays local to this file, so the shared fixture is not edited.

**Shim.** `install_probe_shim <bindir> <mode> <log>` writes an argv-keyed `git`
wrapper into the checkout's `bin/`, which is already first on `run_sync`'s `PATH`.
It fails exactly one argv shape and **logs every failed call**, so each test can
assert that the shim *fired* — a shim that never fires makes a green test vacuous.
Each mode matches the only caller of that shape on this route:

- `cached-name-only` fails `diff --cached --name-only` (A3). t1747_2's
  `diff --cached --quiet HEAD` is a different shape.
- `status-path:<p>` fails `status --porcelain` **without `-z`** whose last argument
  is `<p>` (A4). The sweep's own scan uses `-z -uall`.
- `absgitdir` fails `rev-parse --absolute-git-dir` (A10). Its only caller is
  `_ait_data_gitdir`'s linked-worktree path.

**Mutants.** These copy t1747_2's `_automerge_replace` / `_require` shape
(`test_sync_branch_mode_automerge.sh:794,808`):

- patch only the fixture's own copy of `aitask_sync.sh`;
- replace the target exactly once, then re-grep to prove the replacement landed;
- assert that the rest of the guard survived.

`assert_defect_present` is copied the same way.

Each case below asserts its precondition in both the test and its control.

**A3-1**
- *Fixture + shim:* the shape of the auto-commit scoping suite's Test 15. `t10` has a
  foreign stage plus a later worktree edit, and `t20` is edited too. Shim mode:
  `cached-name-only`.
- *Fixed code must:*
  - produce no `Auto-commit t10`;
  - leave `t10`'s index blob byte-identical;
  - emit a `DEFERRED_FILE` record for `t10` with reason `unverifiable`;
  - print a recognised token on the first stdout line;
  - show that the shim fired.
- *Precondition:* unshimmed, `git diff --cached --name-only -- aitasks/t10_alpha.md`
  lists the file, so the foreign stage is real.
- *Probe-only mutant:* restore `|| staged=""`. Then `t10` is committed and its index
  blob **changes**, which is the destroyed stage.

**A3-2** (permit direction)
- *Fixture:* A3-1's, with the shim removed and the foreign stage cleared
  (`git reset -q -- t10`).
- *Fixed code must:* commit the previously deferred group (`Auto-commit t10`).

**A4-1**
- *Fixture + shim:* the shape of the deferral suite's Test 11. A live lock lets a
  raced commit into quarantine, then the lock is replaced by a dead one. Shim mode:
  `status-path:aitasks/t10_alpha.md`.
- *Fixed code must:*
  - report `DEFERRED:publication_blocked`;
  - leave the remote SHA unchanged;
  - keep the entry in the ledger;
  - name the unread state on stderr;
  - show that the shim fired.
- *Precondition:* both clauses — the ledger contains `t10`'s path after run 1,
  **and** the planted lock's pid is not alive (`kill -0` fails).
- *Probe-only mutant:* restore `[[ -z "$(task_git status …)" ]]`. Then the entry is
  released and **published**.

**A4-2** (the discriminating control)
- *Fixture:* A4-1's, without the shim.
- *Fixed code must:* release the entry and advance the remote.
- *Precondition:* the same two clauses as A4-1.

**A10-1**
- *Fixture + shim:*
  1. A race-seam run in `local` puts an entry in quarantine while the lock is live.
  2. `git -C local worktree add --detach ../wt`.
  3. `aitask_init_data.sh --link-worktree ../wt`.
  4. Install shim mode `absgitdir` in `wt/bin`.
- *Fixed code must*, run from `wt`:
  - print `ERROR:data_gitdir_unresolved` and exit 1;
  - leave the remote SHA unchanged;
  - leave the entry in the ledger at `local/.git/worktrees/-aitask-data/`, so a
    later **unshimmed** run from `local` still reports
    `DEFERRED:publication_blocked`;
  - show that the shim fired.
- *Precondition:*
  - `--link-worktree` printed `LINKED`;
  - the ledger is non-empty;
  - unshimmed from `wt`, the run reports `DEFERRED:publication_blocked`. So `wt`
    resolves the real ledger; this is also the permit direction.
- *Probe-only mutant:* restore the old `_sync_gitdir` body. From `wt`, the withheld
  commit is then **published**, because the ledger is relocated and the entry lost.

**A10-2**
- *Fixture + shim:* A10-1's layout, plus
  `mkdir local/.git/worktrees/-aitask-data/rebase-merge`.
- *Fixed code must*, run shimmed from `wt`: print `ERROR:data_gitdir_unresolved`,
  never "not wedged".
- *Precondition:* unshimmed from `wt`, the run reports `DEFERRED:worktree_wedged`,
  so the wedge is visible when resolution works.

**S** (source scan)
- *Must:* match the identities and tags below.
- *Mutant:* a scanner self-test on a synthetic file with a bare consumer must fail.

**Scan: identities, not counts.** Adapt t1747_2's `automerge_callsites` awk
(`test_sync_branch_mode_automerge.sh:1029`). It emits one `file::function::helper`
row per call site in `aitask_sync.sh` for `_data_wedge_gitdir`, `_sync_gitdir`,
`_worktree_wedged` and `_quarantine_path`, excluding definitions and comment lines.
Sorted without dedup, the rows must equal:

```
aitask_sync.sh::_quarantine_path::_sync_gitdir
aitask_sync.sh::_sync_gitdir::_data_wedge_gitdir
aitask_sync.sh::_worktree_wedged::_sync_gitdir
aitask_sync.sh::auto_commit::_quarantine_path
aitask_sync.sh::do_pull_rebase::_worktree_wedged
aitask_sync.sh::main::_worktree_wedged
```

Guards:
- **Anti-empty.** Exactly 6 rows, **and** all four helper definitions are found.
- **Tags.** Every call line carries `# unverified:` within the 4 lines above it. A
  failure names this table and the canonical doc.

*What it does not buy:*
- The tag's text is not checked against behaviour. Every tagged consumer's rc-2
  branch is driven by a live test instead: Step 1b and `auto_commit` by A10-1/A10-2,
  and `do_pull_rebase` by Test 17.
- Legacy mode is not driven live, because the fixture is branch-mode only. The
  `[[ -n "$gd" ]] || return 2` it would exercise is shared by both modes.

### `tests/test_sync_branch_mode_automerge.sh` — A5, Tests 15–17

A5's conflict fixture lives here, so its tests do too. Extend `install_advance_shim`
with three modes, and amend its header comment, which currently says "`--abort`
always passes through". Each mode acts on the **first**
`diff --name-only --diff-filter=U` only (tracked with a counter file), and first
logs `ls-files -u | wc -l` and whether `rebase-merge` exists, using the real git:

- `first-probe` — fail that probe.
- `first-probe+abort` — fail that probe, then also fail `rebase --abort`.
- `first-probe+gitdir-vanish` — log the precondition, then
  `mv "$repo/.git/worktrees/-aitask-data" "$repo/.git/worktrees/-aitask-data.hidden"`,
  log that the move happened, and fail the probe.

  This models the git-dir becoming unreadable mid-run, the condition A5's probe
  failure stands for. Mode detection stays `branch`, because `.aitask-data/.git`
  still exists and the mode is cached (item 3). From then on:
  - the real `rebase --abort` fails naturally ("not a git repository");
  - `_ait_data_gitdir`'s fast path misses;
  - `git -C .aitask-data rev-parse --absolute-git-dir` fails;
  - so the post-abort `_worktree_wedged` genuinely returns 2.

  No production seam is added.

All three tests use the base fixture: Test 1's adjacent-field conflict.

**Test 15 — the abort succeeds.** Shim mode `first-probe`.
- *Fixed code must:*
  - print `ERROR:pull_conflict_unverified` and exit with rc ≠ 0;
  - pass `assert_no_rebase_wedge`;
  - keep the local commit in `git log`;
  - show that the shim fired.
- *Precondition:* when the probe failed, the shim's log shows unmerged entries > 0
  **and** `rebase-merge` present — the rebase really did stop on a conflict.
  Test 1 runs the same fixture unshimmed and gets `AUTOMERGED`; that is the permit
  direction.
- *Mutant:* restore `2>/dev/null || true`. Output becomes `ERROR:pull_rebase_failed`.

**Test 16 — the abort itself fails.** Shim mode `first-probe+abort`.
- *Fixed code must:*
  - print `ERROR:rebase_abort_failed` and exit with rc ≠ 0;
  - leave `rebase-merge` **still present** — the inverse of
    `assert_no_rebase_wedge`, so the test proves the worktree really is wedged;
  - put `./ait git rebase --abort` on stderr, and **not** the word "intact";
  - show, in the shim log, the abort that failed.
- *Cleanup:* run the real `git rebase --abort`, then assert there is no wedge, so
  later tests start clean.
- *Mutant:* the unverified-recovery shape — `task_git rebase --abort … || true`,
  then `ERROR:pull_conflict_unverified` unconditionally. It claims the verified
  token while `rebase-merge` exists.

**Test 17 — the recovery cannot be inspected.** Shim mode
`first-probe+gitdir-vanish`.
- *Fixed code must:*
  - print `ERROR:rebase_abort_unverified` and exit with rc ≠ 0;
  - put both `./ait git status` and `./ait git rebase --abort` on stderr;
  - print neither "intact" nor "verified clean".
- *Preconditions*, all asserted:
  1. The shim's log shows unmerged entries > 0 and `rebase-merge` present at
     the moment of the probe — a real in-flight conflict.
  2. The shim logged the move, and the log shows the `rebase --abort` call reached
     after it — the post-abort check, not Step 1b, is what saw the missing git-dir.
  3. After the test moves the admin dir back, `rebase-merge` **still exists**. So
     the worktree really was left wedged, and a "verified clean" label would have
     been false. This assertion is the one that makes the test discriminating.
- *Cleanup:* restore the admin dir, run the real `git rebase --abort`, then run
  `assert_no_rebase_wedge`.
- *Mutant:* replace `1)  batch_out "ERROR:pull_conflict_unverified"` with
  `1|2)  batch_out "ERROR:pull_conflict_unverified"`, exactly once. This is rc 2 read
  as verified — the same outcome a bare `if _worktree_wedged` would produce. With the
  mutant, the run prints `ERROR:pull_conflict_unverified` and the stderr claims
  "intact" while the worktree is wedged and uninspectable (`assert_defect_present`).

### Red proof without a red commit

1. Write every test first, and run it against the unmodified `aitask_sync.sh`.
   - Expected failures, each with the predicted pre-fix outcome: A3-1, A4-1, A10-1,
     A10-2, Tests 15–17 (pre-fix, all three print `ERROR:pull_rebase_failed`) and
     the scan.
   - Expected passes: the A3-2 and A4-2 controls.
2. Apply the fix and confirm that everything is green.
3. Land the fix and the tests in **one** commit. The mutants are the permanent form
   of the proof.

## Verification

```bash
bash tests/test_sync_failopen_probes.sh
bash tests/test_sync_branch_mode_automerge.sh
bash tests/test_sync_guarded_merge.sh           # t1731's suite — same file, new path
bash tests/test_sync.sh
bash tests/test_sync_auto_commit_scoping.sh
bash tests/test_sync_deferral_and_quarantine.sh
bash tests/test_sync_protect_paths.sh
bash tests/test_no_unscoped_task_commit.sh
~/.aitask/venv/bin/python -m pytest -q tests/test_sync_action_runner.py
shellcheck .aitask-scripts/aitask_sync.sh     # re-baseline at e2f12c499 first; add nothing
```

Run pytest directly on that one module. `run_all_python_tests.sh <path>` disables the
parallel lane, and it ran past 600 s in t1747_2.

## Not in this task

- **The canonical doc's line citations.** Its rows still cite the audit's line
  numbers, and its SHA is point-in-time. Reconciling it is t1747_7's job, so after
  the commit, send t1747_7 a note with the real line numbers. The note covers:
  - the moved rows;
  - the A5 premise correction and the verified-recovery shape;
  - that `do_pull_rebase`'s five best-effort aborts stay in the negative-space
    table;
  - the sibling finding (item 9).
- **The sibling fail-open in `lib/task_utils.sh::_data_wedge_state` and its
  consumers.** It goes to t1747_7 in the same note, and into the Upstream-defects
  bullet after checking whether an existing task already tracks it.

## Step 9

- **Worktree:** `aiwork/t1747_3_sync_authorization_probes`, on branch
  `aitask/t1747_3_sync_authorization_probes`. It is cut from `main` at Step 7, after
  the drift check.
- **Merge:** the merge broker 3-way merges onto `main` as it stands at that point.
  If `aitask_sync.sh` conflicts, re-run this plan's tests against the merged tree
  before archiving.
- **Archival:** standard. The parent t1747 archives after its last child.

## Risk

### Code-health risk: medium
- **Empty stdout on the most-run path.** The change adds four guards and two new hard
  stops (`main` Step 1b, `auto_commit`). A capture that `set -e` does not absorb
  yields the empty-stdout class, which every consumer reads as
  `ERROR: empty output`.
  · severity: medium (residual — the baseline makes any regression attributable to
  this change, and every new test asserts a recognised first stdout line)
  · → mitigation: inline pre-phase baseline_sync_suites
- **A bare consumer of the tri-state `_worktree_wedged`.** A future consumer that
  reads it bare would silently re-open A10's wedge half. t1731 landed without adding
  one. A5's recovery check is the only new consumer, it captures explicitly, and
  Test 17 drives its rc-2 branch end-to-end.
  · severity: low
  · → mitigation: none needed as a task — the scan's identity set and tag guard turn
  a bare in-file consumer red
- **Signature change.** `_quarantine_load_and_prune` and `_quarantine_persist` now
  take the ledger path. Both are file-local, with three call sites, all in
  `auto_commit`.
  · severity: low · → mitigation: none
- **Test 17 moves the fixture's admin dir.** A failure between the move and the
  restore leaves that one fixture broken.
  · severity: low · → mitigation: none needed as a task — the move is confined to the
  test's own temporary repo, and the test restores the dir and cleans up
  unconditionally before asserting

### Goal-achievement risk: low
- **Predicted discriminators.** The A10 discriminator (a linked worktree built with
  `--link-worktree` in a synthetic repo) is **predicted, not yet measured**, and so
  is Test 17's vanish-mid-run shape. If the unmodified code does not behave as
  predicted, the matching test is vacuous.
  · severity: low (residual — A10 is measured before the rest of the suite is
  written, with a stop-and-re-plan exit; Test 17's discriminating assertion is
  measured, not assumed: `rebase-merge` must still exist after the restore)
  · → mitigation: inline pre-phase measure_a10_discriminator
- **More refusals can strand a user.** A10 now errors instead of syncing, A3 and A4
  hold for as long as the probe stays unreadable, and A5 can now report a
  still-wedged or uninspectable worktree instead of hiding it. In each case,
  proceeding (or hiding the wedge) is the harm, and every refusal names its
  recovery: `ait setup` / `git worktree repair`, re-running,
  `--release-quarantine`, `./ait git status` / `./ait git rebase --abort`.
  · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: baseline_sync_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — unabsorbed set -e capture on the most-run path | desc: run the sync suites and the runner module on the unmodified worktree and record counts before any edit
- timing: pre-phase | name: measure_a10_discriminator | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — A10 discriminator predicted, not measured | desc: build the linked-worktree A10 fixture first and confirm the unmodified code publishes under the --absolute-git-dir shim; stop and re-plan if not
