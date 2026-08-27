---
Task: t1631_setup_data_branch_silent_failure_swallows.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1631 — `setup_data_branch`: stop swallowing a failed probe, fetch, copy and commit

## Context

t1627 fixed `setup_data_branch`'s worktree-add failure message and swept the two
neighbouring `warn` sites that discarded git's stderr. Two sites in the same
defect class were deliberately left out — a failure is discarded and the flow
continues on an assumption the failure invalidated — because neither is a
`warn`/`return` path and neither looked drivable from a fixture:

1. **`.aitask-scripts/aitask_setup.sh:1539`** — `git fetch origin aitask-data
   2>/dev/null || true` is followed by an unconditional `branch_exists=true`. A
   failed fetch is therefore recorded as "branch found", and Step 2 dies on
   `invalid reference: aitask-data`.
2. **`.aitask-scripts/aitask_setup.sh:1597,1599`** — `cp -a … 2>/dev/null || true`
   in the migration branch of Step 3 silently swallows a failed copy of the
   user's `aitasks/` / `aiplans/`. Step 5 then `git rm -r`s + `rm -rf`s the
   originals from main. **A partial copy is indistinguishable from a complete one
   at the point the source is deleted.** This is the one path in
   `setup_data_branch` that deletes user data, and there is no verification
   between the copy and the delete.

Review of the plan surfaced two more members of the same class in the same
function, both verified:

3. **`aitask_setup.sh:1538`** — the remote probe
   `git ls-remote --heads origin "aitask-data" 2>/dev/null | grep -q "aitask-data"`
   is an **unanchored tail match**: `ls-remote` matches a pattern against the
   tail of a ref name and the grep is unanchored, so a remote carrying only
   `refs/heads/backup/aitask-data` answers "found". Confirmed empirically. The
   probe's own failure (unreachable remote) is likewise discarded by
   `2>/dev/null`. The same probe shape is in `aitask_init_data.sh:195`.
4. **`aitask_setup.sh:1668-1683`** — the Step-4 subshell runs `git add .` and
   `git commit` **unchecked**, and its exit status is not inspected by the
   caller. Copy equality is not durability: if the commit fails, Step 5 can
   remove the tracked originals from main while the copied data is only staged
   in `.aitask-data`.

   *Scope note, verified:* `aitask_setup.sh:2` sets `-euo pipefail` and
   `setup_data_branch` is called as a bare statement (`:3951`), so **in
   production today a failed commit aborts all of `ait setup` before Step 5**
   rather than reaching the delete. The loss path is nonetheless live wherever
   `set -e` is off — `tests/test_data_branch_setup.sh:124` does exactly that —
   and the silent whole-setup abort is itself the outcome the Step-2 failure
   path was explicitly written to avoid ("`return`, not `die`… dying here would
   abort the ~20 remaining setup steps"). So the check is worth having on both
   counts, and it makes the no-delete guarantee independent of `set -e`.

## Implementation

### Pre-phase (risk mitigations)

1. `[worktree_identity_guard]` Before writing the teardown used by the abort
   helper in step 3, add an identity check to it: proceed with removal **only**
   when `git -C "$project_dir" worktree list --porcelain` lists
   `$project_dir/.aitask-data` as a registered worktree of this repository. The
   `git worktree remove --force` / `rm -rf` fallback is written *after* and
   *behind* this guard, never before it.

   Three properties, because this guard authorizes an `rm -rf`:

   - **Fail closed on every non-answer.** A nonzero `worktree list`, empty
     output, or a path that fails to resolve is **not** a licence to remove —
     each refuses, exactly like a `no match`. "Could not check" is its own state,
     not a negative one.
   - **Compare canonicalized paths on both sides.** `worktree list --porcelain`
     emits absolute paths from `worktree <path>` lines; `$project_dir` may carry
     symlinked components. Put both through the same resolver
     (`cd "$p" 2>/dev/null && pwd -P`) and compare the results; if either side
     fails to resolve, refuse.
   - **Say what refusing costs.** When the guard refuses, `warn` that
     `.aitask-data/` was left in place *and* that the next `ait setup` will
     early-return on it as "already configured" — so the user knows to remove it
     by hand. A silent refusal reads as a successful cleanup.

   Both branches are pinned by tests (d) — permits — and (h)/(i) — refuses.

### Main implementation

1. **Exact remote probe + honest fetch (`aitask_setup.sh` Step 1, ~lines
   1533-1543).** Replace the tail-match probe with an exact-ref one, classify
   the remote into three states, capture the fetch's stderr, and do **not**
   claim `branch_exists=true` when the fetch that materializes the ref failed:

   ```bash
       local branch_exists=false
       local remote_state="absent"   # absent | present | unknown

       if [[ "$has_remote" == true ]]; then
           # Exact ref match (t1631). The old probe was
           # `ls-remote --heads origin aitask-data | grep -q aitask-data`:
           # ls-remote matches a pattern against the TAIL of a ref and the grep
           # was unanchored, so a remote carrying only
           # `refs/heads/backup/aitask-data` answered "found". --exit-code also
           # separates "definitively absent" (2) from "the probe itself failed"
           # (anything else), which `2>/dev/null` used to collapse together.
           local ls_err="" ls_rc=0
           ls_err="$(git -C "$project_dir" ls-remote --exit-code --heads origin refs/heads/aitask-data 2>&1 >/dev/null)" || ls_rc=$?
           case "$ls_rc" in
               0) remote_state="present" ;;
               2) remote_state="absent"  ;;
               *) remote_state="unknown"
                  warn "Could not check the remote for an aitask-data branch. git said: ${ls_err:-<no output>}" ;;
           esac
       fi

       if [[ "$remote_state" == "present" ]]; then
           info "Found aitask-data branch on remote — fetching..."
           # Report git's own error rather than discarding it, and do not claim
           # the branch was found when the fetch failed (t1631). The old
           # `|| true` + unconditional `branch_exists=true` sent Step 2 into
           # `invalid reference: aitask-data`.
           local fetch_err=""
           if fetch_err="$(git -C "$project_dir" fetch origin aitask-data 2>&1 >/dev/null)"; then
               branch_exists=true
           else
               warn "Could not fetch the aitask-data branch from remote. git said: ${fetch_err:-<no output>}"
           fi
       fi

       # Check local
       if [[ "$branch_exists" == false ]] && git -C "$project_dir" show-ref --verify refs/heads/aitask-data &>/dev/null; then
           branch_exists=true
           if [[ "$remote_state" == "present" ]]; then
               info "  Using the local aitask-data branch instead. Re-run 'ait setup' once the fetch above works to reconcile it with the remote."
           fi
       fi

       # The remote definitively HAS the branch, we could not get it, and there
       # is no local copy. Creating the orphan below would mint a SECOND,
       # unrelated aitask-data — and on the migration path move the user's task
       # data into it. Refuse; this returns before Steps 3/5, so nothing is
       # copied and nothing is deleted.
       if [[ "$branch_exists" == false && "$remote_state" == "present" ]]; then
           warn "The remote has an aitask-data branch, it could not be fetched, and there is no local copy."
           warn "Skipping task data branch setup rather than creating a second, unrelated aitask-data branch."
           info "  Task and plan files stay on the current branch (legacy layout). Re-run 'ait setup' once the fetch above succeeds."
           return
       fi
   ```

   **Deliberate boundary — what this does not buy.** The refusal fires only on
   `present`, never on `unknown`. An unreachable remote (probe rc 128) keeps
   today's behavior: warn, then fall through and create the orphan locally, so
   an offline `ait setup` still works. Extending the refusal to `unknown` would
   be a usability regression well outside this task; the residual is that a
   first setup performed while offline against a remote that *does* carry
   `aitask-data` still mints a divergent branch. Pinned as a test control
   (control (g) in step 6) so the boundary is explicit rather than accidental.

2. **Same correction in `aitask_init_data.sh:193-204`.** Its probe has the
   identical unanchored shape and its fetch `warn` discards git's stderr. Apply
   the same exact-ref probe and stderr capture. Its control flow already bails
   correctly (`NO_DATA_BRANCH`) and is unchanged.

3. **The migration copy (`aitask_setup.sh` Step 3, ~lines 1592-1601).** Check
   `cp -a`'s exit status on **both** copies and abort the migration *before*
   Step 5, leaving the user's data on main untouched:

   ```bash
       if [[ "$needs_migration" == true ]]; then
           info "Migrating task data to aitask-data branch..."
           mkdir -p "$project_dir/.aitask-data/aitasks" "$project_dir/.aitask-data/aiplans"
           # cp's status is checked and a failure aborts the migration: Step 5
           # below deletes these very files from main, and a part-way copy is
           # otherwise indistinguishable from a complete one at that point
           # (t1631).
           local cp_err=""
           if ! cp_err="$(cp -a "$project_dir/aitasks/." "$project_dir/.aitask-data/aitasks/" 2>&1 >/dev/null)"; then
               abort_data_branch_setup "$project_dir" "$branch_exists" \
                   "Failed to copy aitasks/ into the data worktree. cp said: ${cp_err:-<no output>}"
               return
           fi
           if [[ -d "$project_dir/aiplans" ]]; then
               if ! cp_err="$(cp -a "$project_dir/aiplans/." "$project_dir/.aitask-data/aiplans/" 2>&1 >/dev/null)"; then
                   abort_data_branch_setup "$project_dir" "$branch_exists" \
                       "Failed to copy aiplans/ into the data worktree. cp said: ${cp_err:-<no output>}"
                   return
               fi
           fi
       else
   ```

   New helper `abort_data_branch_setup()` beside `setup_data_branch` — one
   helper, four call sites (failed copy here, failed verification in step 5,
   failed commit in step 4 on **both** the migration and fresh-setup paths). It
   mirrors the tone of the Step-2 worktree-add failure path
   (`aitask_setup.sh:1571-1589`):

   - `warn` with the caller-supplied reason;
   - state plainly that **nothing was removed from the current branch**;
   - **tear down the half-populated worktree** — behind the pre-phase identity
     guard — so a re-run retries from scratch instead of hitting the "already
     configured" early return at the top of `setup_data_branch` and leaving the
     repo half-migrated with no symlinks. Safe by construction: reaching Step 3
     means *this* invocation created that worktree (the `.aitask-data/.git`
     early return fires otherwise), and it holds only copies — Step 5 has not
     run, so nothing in it is unique. `git worktree remove --force
     .aitask-data`, falling back to `rm -rf` + `git worktree prune`; `warn` if
     the directory survives, since the next `ait setup` would then early-return.
   - leave the `aitask-data` branch in place, and say so when `branch_exists` is
     `false` (this run created it) — the same wording as the Step-2 path.

4. **Require a successful local commit before Step 5 (`aitask_setup.sh` Step 4,
   ~lines 1668-1683).** Check `git add` and `git commit` and propagate the
   result out of the subshell (`data_commit_rc=0; ( … ) || data_commit_rc=$?`):

   - On the **migration** path a nonzero result calls `abort_data_branch_setup`
     and returns — Step 5 must never delete originals whose copy is not durably
     committed. That guarantee then holds regardless of whether `set -e` is in
     effect.
   - On the **fresh-setup** path it does the **same teardown and return**, and
     crucially *before* Step 6. "Warn and continue" is not available here:
     Step 6 would lay symlinks over a data worktree whose seeded contents are
     uncommitted, and the early return at `aitask_setup.sh:1443` then reports
     any existing `.aitask-data/.git` as `success "…already configured"` — so
     `ait setup` could never retry the failed initialization, and
     `ait_ensure_data_symlinks` is called from exactly one place in setup
     (`:1700`), inside the block that never runs again. The result would be an
     apparently complete, permanently non-durable setup. Tearing the worktree
     down instead leaves the repo in the plain legacy layout that a later
     `ait setup` retries from scratch.
   - The **push** stays advisory after a successful local commit, exactly as
     t1627 left it.

   Because the helper now serves the fresh path too, name it
   `abort_data_branch_setup` (not `abort_migration`) and give it the
   path-appropriate closing line: "nothing was removed from the current branch"
   on migration, "no symlinks were created — re-run 'ait setup' to retry" on
   fresh setup.

5. **Verify the copy before the irreversible delete (`aitask_setup.sh` Step 5,
   ~lines 1689-1697).** `cp` returning 0 and the commit succeeding are the
   primary guards; this is the last one, because the delete is irreversible from
   setup's point of view. Before the `git rm -r` / `rm -rf`, compare the trees
   and refuse on any difference:

   ```bash
           if ! diff_out="$(diff -r -q "$project_dir/aitasks" "$project_dir/.aitask-data/aitasks" 2>&1)" \
              || { [[ -d "$project_dir/aiplans" ]] && ! diff_out="$(diff -r -q "$project_dir/aiplans" "$project_dir/.aitask-data/aiplans" 2>&1)"; }; then
               abort_data_branch_setup "$project_dir" "$branch_exists" \
                   "Copy verification failed — refusing to remove the originals from the current branch. diff said: $diff_out"
               return
           fi
   ```

   Fails closed: `diff` exits 1 on differences and 2 on trouble (e.g. an
   unreadable file), and both mean "do not delete".

6. **Tests** — `tests/test_data_branch_setup.sh`, reusing its existing
   `setup_repo_with_remote` + `source aitask_setup.sh --source-only` harness
   (see its Test 2 for the migration fixture shape).

   **Shared fixture mechanism: a test-local PATH shim.** One helper writes an
   executable wrapper for `git` or `cp` into a temp `bin/`, prepends it to
   `PATH` for the duration of one `setup_data_branch` call, and restores after.
   The wrapper passes everything through to the real binary (resolved via a
   saved `AIT_TEST_REAL_PATH`) except the one narrowly-matched invocation it is
   asked to fail, where it writes a recognizable message to stderr and exits
   nonzero. Verified working with passthrough; `hash -r` is called on install
   and removal (bash already invalidates its hash on a `PATH` change, but the
   call is explicit and cheap). This is **deterministic for every EUID** — no
   `chmod 000`, no root skip.

   Matchers: `git` fails when the argv contains `fetch` (test b) or `commit`
   while `$PWD` is the data worktree (test e); `cp` fails when the destination
   argument is under `.aitask-data/aitasks/` or `.aitask-data/aiplans/`, after
   first copying one file into the destination so the failure leaves a genuine
   **partial** tree (tests d, h, i). Tests (h) and (i) install **two** wrappers
   at once — `cp` to reach `abort_data_branch_setup`, `git` to subvert the identity
   guard once there — so the helper must accept a list of wrappers into one
   temp `bin/`. Every `git` matcher is scoped to its own subcommand so
   `worktree add`, `rm`, `add`, `push` and the rest still pass through.

   | # | Fixture | Assert |
   |---|---------|--------|
   | a | Remote carries **only** `refs/heads/backup/aitask-data` | **Normal creation** — orphan branch minted, `.aitask-data/.git` exists, symlinks made. Pins the exact-ref probe: the decoy is not evidence. |
   | b | Real remote `aitask-data`; `git` shim fails the fetch; no local branch | Fetch error surfaced with git's text; **no** `.aitask-data`; `aitasks/` still a real dir (not a symlink); no `refs/heads/aitask-data` minted |
   | c | As (b) plus a real **local** `aitask-data` branch | Normal completion (worktree + symlinks). Negative control: the fall-through must not become a blanket refusal |
   | d | Migration fixture; `cp` shim fails the `aitasks` copy (and a variant for `aiplans`) | cp's error surfaced; `aitasks/t1_test.md` + `aiplans/p1_test.md` still present **and still tracked on main**; `aitasks/` not a symlink; `.aitask-data/` removed so a re-run retries. Also the identity guard's **positive** control — it proves the guard is not stuck closed |
   | e | Migration fixture; `git` shim fails the data-branch `commit` | Same no-delete assertions as (d). Fails before the fix (the harness runs with `set +e`), passes after |
   | j | **Fresh** setup (no migration); `git` shim fails the data-branch `commit` | Commit error surfaced; `.aitask-data/` removed; **no `aitasks` / `aiplans` symlink in the repo root** (the teardown must precede Step 6) |
   | f | Migration fixture, unmodified | Existing Test 2 — the success path is untouched |
   | g | Remote URL points at a nonexistent repo (probe rc 128), no local branch | Probe error surfaced **and** the branch + worktree are still created. Pins the `unknown` boundary from step 1 |
   | h | As (d), plus a `git` shim that makes **`worktree list --porcelain` exit nonzero** | Identity guard refuses: `.aitask-data/` **still present and untouched** (its partial copy intact, still a registered worktree); warn names both the refusal and the "next `ait setup` will early-return" consequence; and the no-delete guarantee still holds — originals present and tracked on main, `aitasks/` not a symlink |
   | i | As (d), plus a `git` shim that runs the real `worktree list --porcelain` but **filters out the `.aitask-data` block** | Same assertions as (h). Distinct from (h) on purpose: (h) pins "command failed ⇒ refuse", (i) pins "parsed, no match ⇒ refuse", so a guard that merely checks for non-empty output cannot pass both |

   **Tests (e) and (j) each end with a shim-free re-run.** Absence of state is
   only half the claim — the point of tearing the worktree down is that
   `ait setup` can retry, and the early return at `:1443` is what would silence
   it. So both remove the shim, call `setup_data_branch` again, and assert the
   second run **completes**: `.aitask-data/.git` exists, the `aitasks` /
   `aiplans` symlinks exist, and the data branch's `HEAD` commit contains the
   expected content (the migrated `t1_test.md` for (e); the seeded
   `aitasks/metadata/` for (j)). Without that follow-up the tests would pass
   against a version that simply never created anything.

### Post-phase (risk mitigations)

1. `[step1_branch_matrix_controls]` Add explicit negative-control assertions for
   every Step-1 state the new refusal branch must **not** intercept, each
   asserting `.aitask-data/.git` exists afterwards (i.e. setup reached worktree
   creation): no remote at all (existing Test 5); remote with a fetchable
   `aitask-data` (existing Test 4); reachable remote with no matching ref
   (existing Test 1); decoy-only remote (new test a); unreachable remote (new
   test g).

   Then confirm both new guards actually discriminate — a control that cannot
   fail proves nothing. Two forced-failure injections, each reverted after:

   - temporarily widen the Step-1 refusal condition to
     `[[ "$branch_exists" == false ]]` and verify the five controls above fail;
   - temporarily invert the identity guard (authorize removal when the path is
     *not* listed) and verify tests (h) and (i) fail; then delete the guard
     entirely and verify they fail again. Check the mutation actually landed in
     the executed code path before trusting either result.

## Files

- `.aitask-scripts/aitask_setup.sh` — Step 1 probe + fetch, new
  `abort_data_branch_setup()` helper (with the pre-phase identity guard), Step 3
  migration copies, Step 4 commit check, Step 5 pre-delete verification.
- `.aitask-scripts/aitask_init_data.sh` — exact-ref probe + stderr capture.
- `tests/test_data_branch_setup.sh` — multi-wrapper shim helper, tests a–e and
  g–j, plus the post-phase controls.

## Verification

Every fixture mechanism was verified empirically before planning:

- **Probe.** `git ls-remote --heads origin aitask-data` matches
  `refs/heads/backup/aitask-data` (the bug). `git ls-remote --exit-code --heads
  origin refs/heads/aitask-data` returns rc 0 on the real ref, **2** on
  decoy-only, **128** on an unreachable remote — the three states step 1 needs.
- **PATH shim.** A pass-through wrapper on `PATH` intercepts the targeted
  invocation and passes everything else to the real binary. Privilege-independent.
- **`set -e` propagation.** A failing command in a bare subshell aborts the
  enclosing script under `set -euo pipefail` — the basis for the scope note in
  Context item 4.

Regression runs:

```bash
bash tests/test_data_branch_setup.sh
bash tests/test_data_branch_migration.sh
bash tests/test_init_data.sh
bash tests/test_setup_git.sh
bash tests/test_install_create_data_dirs.sh
bash tests/test_applink_setup_gitignore.sh
bash tests/test_task_git.sh
shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/aitask_init_data.sh
```

Existing Test 4 ("Clone on new PC") guards the fetch success path; Test 2 guards
the migration success path; Tests 1 / 1b / 5 guard the creation paths.

## Risk

### Code-health risk: low
- The new Step-1 refusal branch (`branch_exists == false && remote_state == present`) sits directly in front of the branch-creation block and intercepts a case that previously proceeded; if its condition is wider than intended it silently downgrades working repos to the legacy layout · severity: low (residual — addressed by inline post-phase step1_branch_matrix_controls, which pins all five unaffected states and forces each control to fail on a deliberately widened condition) · → mitigation: inline post-phase step1_branch_matrix_controls
- `abort_data_branch_setup` performs a destructive teardown (`git worktree remove --force` with an `rm -rf` fallback) on a path derived from `$project_dir`; its safety argument rests entirely on the `.aitask-data/.git` early return at the top of `setup_data_branch` · severity: low (residual — addressed by inline pre-phase worktree_identity_guard, which makes removal conditional on the path being a registered worktree of this repo rather than on reasoning about an early return elsewhere) · → mitigation: inline pre-phase worktree_identity_guard
- The identity guard is itself the authorization for that `rm -rf`, so a parse error, a failed `worktree list`, or an inverted condition would turn the mitigation into the destructive path · severity: low (residual — both guard branches are pinned: (d) permits, (h) command-failure refuses, (i) parsed-no-match refuses, and the post-phase injects an inverted and a deleted guard to prove those controls can fail) · → mitigation: inline post-phase step1_branch_matrix_controls
- Tightening the remote probe to an exact ref changes which repos take the "found on remote" path; a repo that today accidentally matches a decoy ref will start creating an orphan branch instead of failing at Step 2 · severity: low · → mitigation: none (that is the corrected behavior, pinned by test (a); the pre-change path could not succeed anyway — it died on `invalid reference`)
- The Step-5 `diff -r -q` verification could refuse a legitimate migration if anything ever writes into `.aitask-data/aitasks` between the copy and the check · severity: low · → mitigation: none (a false refusal is non-destructive — it declines to delete and tells the user to re-run)
- Tearing down the worktree on a fresh-setup commit failure means a repo that previously ended up with a half-initialized `.aitask-data/` now ends up with none; anything that had already written into that directory in the same run would be discarded with it · severity: low · → mitigation: none (only the seed metadata this run just wrote can be in there — Step 4 is the first commit and Step 6's symlinks have not run — and test (j) pins that the retry re-creates it)

### Goal-achievement risk: low
- The refusal fires only on `remote_state == present`, so a first setup performed while the remote is unreachable can still mint a branch that diverges from an `aitask-data` the remote actually holds · severity: low · → mitigation: none (accepted residual, stated as a deliberate boundary in step 1 and pinned by test control (g); closing it would break offline `ait setup`)
- The fix goes beyond the task's literal "fall through to the local `show-ref` check" by refusing rather than minting a divergent orphan branch; if that reading is wrong the delivered behavior differs from what was asked · severity: low · → mitigation: none (called out explicitly in step 1 for approval; reverting to plain fall-through is a two-line change)

### Planned mitigations
- timing: pre-phase | name: worktree_identity_guard | type: bug | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: destructive teardown on a `$project_dir`-derived path in abort_data_branch_setup | desc: gate the `.aitask-data` teardown on `git worktree list --porcelain` confirming it is a registered worktree of this repo; never `rm -rf` a path that fails the check
- timing: post-phase | name: step1_branch_matrix_controls | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: new Step-1 refusal branch intercepting cases beyond the intended one, and the identity guard being an untested authorization for `rm -rf` | desc: assert the five Step-1 states that must still reach worktree creation (no remote; fetchable aitask-data; reachable remote with no ref; decoy-only remote; unreachable remote), and prove both new guards discriminate by injecting a widened refusal condition and an inverted/deleted identity guard

## Final Implementation Notes

- **Actual work done:** All four defect sites landed as planned, plus one more
  found during implementation. In `aitask_setup.sh`'s `setup_data_branch`:
  the remote probe became an exact-ref `ls-remote --exit-code --heads origin
  refs/heads/aitask-data` classified into `absent` / `present` / `unknown`; the
  fetch's stderr is captured and `branch_exists` is no longer claimed on
  failure, with a refusal when the remote definitively has the branch and there
  is no local copy; both migration `cp -a` calls are status-checked; the
  data-branch commit became a hard requirement on both the migration and
  fresh-setup paths; and a `diff -r -q` verification runs before the
  irreversible Step-5 delete. Two new helpers carry it:
  `ait_data_worktree_is_registered()` (the fail-closed authorization for the
  teardown's `rm -rf`, reusing `ait_canon_path` from `lib/data_symlinks.sh` on
  both sides of the comparison) and `abort_data_branch_setup()` (four call
  sites). `aitask_init_data.sh` got the same probe correction and stderr
  capture. `tests/test_data_branch_setup.sh` gained a PATH-shim harness and
  tests 22-32 (206 -> 214 assertions).

- **Deviations from plan:** Three, all additive.
  1. The planned `chmod 000` fixture with an `EUID == 0` skip was replaced
     wholesale by PATH shims before any of it was written — review pointed out
     that root is a common CI/container identity, so the skip would disable the
     primary no-delete guarantee exactly where the suite usually runs. The shims
     are deterministic at any EUID.
  2. The planned single `cp`-failure test became 26 (aitasks) + 26b (aiplans)
     with the shim scoped per destination. Falsification exposed why: with one
     combined shim, reverting only the aitasks check still passed, because the
     aiplans check caught the failure. Each test now pins its own call site.
  3. Test 31 was added for the Step-5 verification, which no planned fixture
     reached. It needs a copy that returns 0 while writing an incomplete tree —
     a case `cp`'s own exit status cannot catch by construction.

- **Issues encountered:**
  - The plan's decoy-ref fixture (`refs/heads/backup/aitask-data`) turned out to
    be a *probe* bug, not a fetch-failure one — `ls-remote` matches on a ref's
    tail, so the decoy made the old unanchored grep answer "found". Using it as
    the fetch fixture would have converted the legitimate orphan-creation path
    into a refusal. It is now test 22, asserting normal creation, and the fetch
    failure is driven by a shim instead.
  - A `git worktree list --porcelain` D/F-conflict was evaluated as a
    shim-free way to fail a fetch and rejected: it leaves
    `refs/remotes/origin/aitask-data` created, so the downstream `worktree add`
    succeeds and the fixture would not reproduce the reported symptom.
  - **The falsification pass wrote to the real repository.** Mutations that made
    `setup_data_branch` refuse to create `.aitask-data` caused Test 4's
    pre-existing unguarded `cd "$TMPDIR_4/local/.aitask-data"` to fail, after
    which the subshell's `git add . && git commit && git push` ran against the
    project root. Three commits titled "ait: Add remote task" landed on `main`
    and were pushed before it was noticed. They contained only this task's own
    work; recovered by `git reset --soft` to `49bfc1bac`, one proper commit, and
    a force-push (user-authorised). All 8 bare `cd`s in the test file are now
    `|| exit 1`.

- **Key decisions:**
  - The Step-1 refusal is scoped to `remote_state == present` and deliberately
    not to `unknown`. An unreachable remote keeps today's behavior (warn, then
    create locally) so an offline `ait setup` still works; the accepted residual
    is that an offline first setup against a remote that does carry
    `aitask-data` still mints a divergent branch. Test 25 pins that boundary.
  - The commit check aborts on the **fresh** path too, before Step 6. Nothing is
    deleted there, but symlinks over an uncommitted worktree plus the
    `.aitask-data/.git` early return would make the failure permanently
    unretryable, and `ait_ensure_data_symlinks` is called from nowhere else in
    setup. Tests 27 and 28 both end with a shim-free re-run asserting the retry
    completes, so the tests cannot pass against a version that simply never
    creates anything.
  - Every guard was falsified by injection (8 mutations), each reverted after
    and each verified to have actually landed before its result was trusted.
    `old_verify` initially failed *nothing*, which is what prompted test 31.

- **Upstream defects identified:**
  - `tests/test_data_branch_setup.sh:565 — subshell runs 'git add . && git commit -m "ait: Add remote task" && git push' after an unguarded 'cd "$TMPDIR_4/local/.aitask-data"'; when the fixture directory is missing the block commits and pushes to the developer's real repository. Fixed in this task (all 8 bare cd sites guarded), recorded here because it is a pre-existing defect that predates t1631 and caused real damage during this session.`
