---
Task: t1626_emails_txt_writers_strand_uncommitted_addresses.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1626 — emails.txt writers strand uncommitted addresses

## Context

`aitasks/metadata/emails.txt` (the contributor list, used for autocomplete and
as the lock-email fallback) has exactly two writers, and **both** can leave an
address appended to the working tree that no code path ever commits:

1. **`aitask_pick_own.sh::store_email()`** runs at `main()` **Step 2**, *before*
   `acquire_lock()` at Step 3. A claim refused with `LOCK_FAILED` /
   `LOCK_LIVE_HOLDER` / `LOCK_UNVERIFIABLE_HOLDER` exits at line 565 — before
   `commit_and_push()` at line 601 — so the address it already appended is left
   uncommitted. The comment at 562-564 ("Nothing was claimed … there is no state
   to roll back here") is untrue for the same reason.
2. **`aitask_create.sh::add_email_to_file()`** appends, but `aitask_create.sh`
   never names `EMAILS_FILE` in any `task_git add`, and since t1599_1 scoped
   every claim commit to its own paths nothing sweeps it either.

Both are made **permanent** by the same third thing: a **membership
short-circuit** skips the write, and with it the flag that would have made
someone commit the file. There are **two such short-circuits per writer**, not
one:

- the pre-lock fast path — `grep -qxF … && return 0`
  (`aitask_pick_own.sh:253`, `aitask_create.sh:1140`);
- the **under-lock recheck** — `if ! grep -qxF …` with **no `else`**
  (`aitask_pick_own.sh:275`, `aitask_create.sh:1169`), whose false branch is a
  silent no-op that leaves the flag untouched.

So the one code path that would have committed the address never runs again.
`emails.txt` stays ` M` dirty indefinitely and the address is never shared
with the team.

**Invariant this plan establishes:** *every* membership short-circuit — all
four sites — consults `HEAD` and claims the file for commit when the address is
on disk but not committed. Fixing only the pre-lock path leaves a live
concurrent hole: writer A appends under the mutex, releases, then dies or has
its commit fail before committing; writer B (same address) was already blocked
on the mutex, so its *pre-lock* check ran while the address was still absent
and its *under-lock* recheck now finds it present — B skips the append, leaves
its flag false, and walks away from a dirty file it is holding the mutex for.
That is the original stranding shape, re-created in an interleaving.

Outcome: every append is followed by a guaranteed path-scoped commit, and a
previously-stranded address is recovered by the next writer instead of being
swallowed.

## Changes

### Pre-phase (risk mitigations)

- **`thin_alias_keeps_call_sites`** — before moving `_commit_scoped`'s body out
  of `aitask_pick_own.sh`, establish the delegator shape: `_commit_scoped()`
  stays in `aitask_pick_own.sh` as a single line forwarding to
  `task_git_commit_scoped "$@"`. No call site in `commit_and_push()` changes,
  and no negative-control injection in `tests/test_pick_own_scoped_commit.sh`
  has to be rewritten. Verified by the existing tests 1-3, 6, 7 and 9 passing
  unchanged after step 1 lands and before steps 2-3 begin.

### 1. `lib/task_utils.sh` — hoist the shared seam

- Move the body of `aitask_pick_own.sh::_commit_scoped()` (lines 431-461,
  comments included) here as **`task_git_commit_scoped <msg> <path>...`**.
  Contract unchanged: `0` = committed, `2` = verified nothing to commit,
  `1` = commit failed; empty pathspec guarded; `-o` so an empty pathspec is
  fatal rather than silently whole-index.
  One tightening: redirect the `task_git commit` stdout to `/dev/null`. It is
  already `--quiet`, but `aitask_create.sh`'s stdout is a data channel (it
  prints the created filepath), and this helper is about to be called from it.
- Add `AIT_EMAILS_FILE="aitasks/metadata/emails.txt"` — one named constant for
  a path currently duplicated in `aitask_pick_own.sh:70` and
  `aitask_create.sh:1120`. Both keep their local `EMAILS_FILE` name, assigned
  from it, so every existing call site (and the test suites' injected function
  bodies) are untouched.
- Add **`ait_email_is_committed <email>`** — `0` when the address is in the
  **committed** contributor list, `1` when it is not *or when the answer cannot
  be established*:

  ```bash
  ait_email_is_committed() {
      local email="$1" head_list="" rc=0
      head_list="$(task_git show "HEAD:$AIT_EMAILS_FILE" 2>/dev/null)" || rc=$?
      [[ $rc -eq 0 ]] || return 1        # unreadable/absent ⇒ NOT committed
      grep -qxF -- "$email" <<<"$head_list"
  }
  ```

  Fails toward "not committed" on purpose: over-claiming costs at most one
  `task_git_commit_scoped` call that returns `2` (verified nothing to commit),
  while under-claiming is permanent — the whole shape of this bug.
  (`show` is on `_ait_git_subcmd_is_readonly`'s list, so the wedged-worktree
  assertion passes it through.)

### 2. `aitask_pick_own.sh` — defect 1

- Replace `_commit_scoped()`'s body with a one-line delegation to
  `task_git_commit_scoped`; its two call sites in `commit_and_push()` stay as
  they are.
- **Move the `store_email` call out of `main()` Step 2** to immediately before
  `commit_and_push()` (i.e. after the lock gate *and* after
  `update_task_status`). Renumber the step comments: Step 2 = acquire lock,
  Step 3 = store email, Step 4 = update status, Step 5 = commit.
  Placing it after `update_task_status` — not merely after the lock — leaves no
  `set -e` early-exit between the append and its commit.
  Every refusal path (`exit 1` / `die`) now precedes the write, so a refused
  claim writes nothing at all and the 562-564 comment becomes true. Update that
  comment to say so explicitly rather than leaving it as an inherited claim.
- **Fix BOTH membership short-circuits** so neither can swallow an uncommitted
  address. Pre-lock fast path:

  ```bash
  if grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
      # Already on disk — but membership alone must NOT end the call. An
      # address appended by a write whose commit never happened is stranded
      # exactly here: every later call returns before EMAIL_STORED can be
      # set, so the one path that would commit it never runs again (t1626).
      ait_email_is_committed "$email" || EMAIL_STORED=true
      return 0
  fi
  ```

  And the **under-lock recheck**, which needs the same treatment for the
  concurrent case described in Context — its comment already says "a holder we
  waited on may have added it", and *that holder may not have committed it*:

  ```bash
  if ! grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
      printf '%s\n' "$email" >> "$EMAILS_FILE" &&
          EMAIL_STORED=true &&
          sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
  else
      # The holder we waited on added it — but it may have died, or had its
      # own commit fail, between releasing the mutex and committing. We are
      # holding the mutex and looking straight at the dirty file; walking
      # away here re-creates the stranding this task removes (t1626).
      ait_email_is_committed "$email" || EMAIL_STORED=true
  fi
  ```

  Note the `else` runs **inside** the `{ … } || rc=$?` group. It is a pure
  read plus an assignment, so it cannot set `rc`; keep it last in the branch so
  the group's status still answers for the append, exactly as t1614 pinned.

  A claim with **no** email still never reaches `store_email` (`main()` guards
  on `[[ -n "$EMAIL" ]]`), so a dirty foreign list is still left alone — the
  Test 5 invariant is preserved by construction.
- Update **both** comments that state the flag's contract, not just one:
  - the **global declaration** of `EMAIL_STORED` (`aitask_pick_own.sh:72`). It
    says the flag is set "when THIS invocation added a new address — the only
    condition", and adds "A claim refused at the task lock still leaves its
    append on disk" — the second sentence asserts the very defect this task
    removes, and the first would invite a maintainer to narrow the recovery
    branches back out. Restate it as "this claim owes emails.txt a commit",
    naming both setters and keeping the one thing that is still true (a claim
    with no email never commits a foreign line).
  - `store_email`'s header comment (lines 239-243). It currently reads
  "Sets `EMAIL_STORED=true` only when this call's APPEND actually adds a new
  address"; that is no longer the whole truth. The flag now means **"this claim
  owes `emails.txt` a commit"** — set by a successful append *or* by a detected
  uncommitted on-disk address. Leaving the old comment would make the recovery
  path read as a bug to the next reader.

### 3. `aitask_create.sh` — defect 2

- `EMAILS_FILE="$AIT_EMAILS_FILE"`.
- Restructure `add_email_to_file()` around **one** flag and **one** tail.

  The flag is `needs_email_commit`, and its meaning is *"this call owes
  `emails.txt` a commit"* — **not** *"this call appended"*. Two disjoint things
  set it, and the early `return 0` on the membership fast path is removed so
  both reach the same commit tail:

  ```bash
  add_email_to_file() {
      local email="$1"
      [[ -n "$email" ]] || return 0
      ensure_emails_file
      local needs_email_commit=false

      if grep -qFx -- "$email" "$EMAILS_FILE" 2>/dev/null; then
          # (a) RECOVERY. Already on disk — but membership alone must not end
          # the call. An address appended by a write whose commit never
          # happened is stranded exactly here (t1626). No append is made, so
          # an "appended" flag would stay false and the stranded case would
          # stay dirty forever: the flag has to answer "owes a commit".
          ait_email_is_committed "$email" || needs_email_commit=true
      else
          # (b) APPEND, under the mutex, exactly as today.
          ... stale_lock_acquire ... || { warn "contributor list busy…"; return 0; }
          {
              if ! grep -qFx -- "$email" "$EMAILS_FILE" 2>/dev/null; then
                  printf '%s\n' "$email" >> "$EMAILS_FILE" &&
                      needs_email_commit=true &&
                      sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
              else
                  # (c) RECOVERY, under the lock. The holder we waited on added
                  # it and may have died — or had its own commit fail — before
                  # committing. Same rule as (a): a membership hit consults HEAD.
                  ait_email_is_committed "$email" || needs_email_commit=true
              fi
          } || rc=$?
          <release — see policy below>
          [[ $rc -eq 0 ]] || warn "add_email_to_file: failed to record ${email} (rc=$rc)"
      fi

      if [[ "$needs_email_commit" == true ]]; then
          local crc=0
          task_git_commit_scoped "ait: Record contributor email" "$EMAILS_FILE" || crc=$?
          [[ $crc -eq 1 ]] && warn "could not commit ${EMAILS_FILE}"
      fi
      return 0
  }
  ```

  The flag sits **between the append and the `sort`** in the `&&` chain — the
  same ordering t1614 pinned for `EMAIL_STORED`: the append is the write the
  flag answers for, so a failed normalization must not leave the address
  recorded-but-uncommitted. The commit message deliberately names no task,
  matching `aitask_pick_own.sh:475`, because the file is shared and the commit
  may carry a concurrent session's append. Best-effort contract unchanged: a
  failed commit warns, never fails the creation.

  Note the **asymmetry with `store_email`** and why it is not a defect: there
  the flag (`EMAIL_STORED`) is read by a *later stage* (`commit_and_push` in
  `main()`), so its fast path can `return 0` after setting it. Here the
  committer is inside the same function, so the fast path must fall through
  instead of returning. `store_email`'s header comment ("Sets EMAIL_STORED=true
  only when this call's APPEND actually adds a new address") must be updated
  in step 2 for the same reason — the flag now also means "owes a commit".

#### Mutex-release policy (and why gating the commit on it would be backwards)

`stale_lock_release` (`lib/stale_lock.sh:680-713`) returns non-zero in exactly
the cases where **our own lock dir is still in place**: the guard-busy early
return at line 691 explicitly says `lock '<dir>' NOT released`, and the
`_stale_lock_rm_verified` failure at 700-701 is a still-held lock. So the
failure status means *more* serialization at commit time, not less — skipping
the commit on `rc != 0` would skip it precisely when it is safest. Conversely
the genuinely ambiguous case, `not owner of '<dir>' — leaving intact`
(line 706), returns **0**: our lock was reclaimed and a new owner may be
mid-write. A release-status gate therefore cannot deliver "the commit never
runs while the mutex may be held" — no ordering of these calls can, short of
committing inside the critical section, which would put a `die`-capable
`task_git` call (`assert_data_worktree_clean`) inside a section that has no
EXIT trap and would leak the lock dir on a wedged data worktree.

What the plan does instead:

- **Commit outside the mutex**, matching the shipped `store_email` /
  `commit_and_push` split.
- **Stop discarding the release status.** Today it is `|| warn "…not fully
  released"`. Capture it (`rel_rc`) and make the warning name the consequence
  and the recovery: the lock dir stays until `stale_lock`'s dead-record reclaim
  clears it. A retained mutex must never silently swallow the address, so the
  commit still runs — with the reasoning above stated in a comment at the call
  site, not left implicit.
- **The safety argument that actually holds**, for both the `not owner` case
  and any interleaving: `sort -o` renames a temp over the target, so a
  concurrent normalization is atomic to a reader; a single short `printf >>`
  append is likewise not torn. The worst outcome is a commit that lags a
  concurrent line by one write — and that line's own writer owes it a commit,
  which the fast-path recovery in (a) now guarantees. Pinned by the new
  concurrent-writer test below rather than asserted in prose.
- Both call sites (`aitask_create.sh:891` interactive-finalize parent,
  `:2207` batch parent) sit before their `task_git add "$filepath"` /
  `task_git commit`, so the contributor commit lands **first** and the task
  commit stays `HEAD` — mirroring `commit_and_push`'s ordering.

## Tests

### `tests/test_pick_own_scoped_commit.sh`

- **Test 4 fixture repair.** It currently reaches the dirty state *through the
  defect* (a refused claim appends). After the fix a refused claim writes
  nothing, so its precondition assertion is now characterizing a bug that is
  gone. Keep the invariant it actually guards ("a foreign address on the list is
  not attributed to a claim commit") and seed the dirty state directly, the way
  Test 5 does.
- **New Test 4b — the gap Test 4 cannot cover (same-address retry).**
  `aitask_lock.sh --lock 1 --email bob` → `pick_own 1 --email mallory` ⇒
  `LOCK_FAILED`; assert `emails.txt` is **clean** and mallory is absent from
  disk. Unlock, retry **with the same address** ⇒ `OWNED:1`, `emails.txt` clean,
  `mallory` present at `HEAD`, and exactly one `ait: Record contributor email`
  commit.
- **New Test 4c — fast-path recovery.** Seed `mallory` on disk uncommitted
  (simulating a write whose commit was lost), claim as `mallory` ⇒ the address
  is committed and the tree is clean, proving membership no longer swallows it.
- **New negative control** `install_prefix_store_email_ordering` (executable
  injection, same technique as `install_prefix_store_email`): rebuild the
  fixture's copy with `main()`'s pre-fix ordering — a `store_email` before the
  lock gate — and assert the defect **positively**: after `LOCK_FAILED`,
  `emails.txt` IS dirty; after the same-address retry it is STILL dirty and
  there are **zero** contributor-email commits.
- **New Test 4d — under-lock recheck recovery on the claim side.** The
  `store_email` twin of the create-side test above, and the one whose window is
  *widest*: `store_email` runs under the mutex but its commit happens much later
  in `commit_and_push`, so the "appended, released, never committed" gap spans
  the whole lock/status-update sequence. Port `holder.sh` and the bounded
  `wait_for_*` helpers from `tests/test_create_email_lock.sh` into this file's
  fixture (it already copies `registry_lock.sh` / `stale_lock.sh` via
  `setup_fake_aitask_repo`), then drive: holder takes the mutex → claim
  `pick_own 1 --email erin@test.com` blocks → release the holder, which writes
  `erin` and never commits → the claim rechecks, consults `HEAD`, and commits.
  Assert `emails.txt` clean, `erin` at `HEAD`, exactly one
  `ait: Record contributor email` commit touching only `emails.txt`, and `HEAD`
  still the claim commit.
- **New negative control** `install_prefix_store_email_norecheck` for Test 4d,
  mirroring the create-side one: pre-lock consult present, under-lock `else`
  absent ⇒ assert the address stays dirty with zero contributor-email commits.
- Re-check tests 3, 5, 6, 7, 8b, 12b against the new fast path (analysis says
  all hold: 3 and 12b re-claim an address already at `HEAD`; 5 never calls
  `store_email`; 6/7/8b take the append path, where the recheck misses and the
  new `else` never runs).

### `tests/test_create_email_lock.sh`

- **New test — `ait create --assigned-to <new address>` leaves `emails.txt`
  clean**: run `--batch --commit --silent --assigned-to carol@test.com`, then
  assert **all four**, not just cleanliness: `git status --porcelain
  emails.txt` is empty; `carol@test.com` is present in
  `git show HEAD:aitasks/metadata/emails.txt`; the
  `ait: Record contributor email` commit exists and `--name-only` on it lists
  **only** `emails.txt`; and `HEAD`'s subject is still the
  `ait: Add task t<N>: …` commit.
- **New test — fast-path recovery on this writer too**: seed `dave@test.com`
  on disk uncommitted, then create with `--assigned-to dave@test.com`. Assert
  the **same four properties**. Cleanliness alone would also pass if a task
  commit accidentally swept `emails.txt`, which is exactly the path-scoping
  violation this task must not introduce — so the "contributor-email commit
  touched only `emails.txt`" and "`HEAD` is still the task commit" assertions
  are the discriminating ones here, not decoration.
- **New test — release-failure policy**: shim `stale_lock_release` (executable
  injection, same technique as `install_prefix_add_email_to_file`) to warn and
  return 1. Assert the creation still succeeds, the retained-mutex warning is
  emitted **and names the reclaim recovery**, and the address is still
  committed — a retained mutex must never silently strand it.
- **New test — concurrent-writer safety**: reuse the existing `holder.sh`
  scenario driver (append + `sort` + rename under `registry_lock`) and run
  `ait create --assigned-to bob@test.com` against it. Assert both addresses
  survive and `emails.txt` ends clean, i.e. the commit that runs outside the
  mutex never loses the holder's line.
- **New test — under-lock recheck recovery (wait / recheck / holder never
  commits).** This is the concurrent hole; it is deterministic, synchronized on
  observed file state, and reuses `holder.sh` unchanged — the holder writes the
  address and **never commits it**, which is precisely the "died between
  release and commit" end state:
  1. Start `holder.sh` with `erin@test.com`; wait for its `ready` file.
  2. Start `ait create --batch --commit --silent --assigned-to erin@test.com`.
     Its pre-lock check runs now, while `erin` is still absent, so it takes the
     append branch and **blocks on the mutex**.
  3. Wait for `aitasks/t*_<name>.md` to appear (proves create reached the email
     step) and assert `erin` is still absent — pinning that step 2's pre-lock
     check could not have seen it.
  4. `: > go` ⇒ the holder writes `erin`, releases, exits, commits nothing.
  5. Create acquires, rechecks, finds `erin` ⇒ must consult `HEAD` and commit.
  Assert the same four properties as the other create tests: tree clean, `erin`
  at `HEAD`, the `ait: Record contributor email` commit touching **only**
  `emails.txt`, and `HEAD` still the task commit.
  Every wait is a bounded poll on a condition whose timeout is a hard FAIL
  (`wait_for_file` / `wait_for_glob` / `wait_for_content` already in this file)
  — never a sleep chosen to be "long enough".
- **New negative control for it**, `install_prefix_add_email_to_file_norecheck`:
  inject a body carrying the pre-lock HEAD consult but **not** the under-lock
  one, and assert **positively** that this exact interleaving still strands the
  address — dirty tree, zero contributor-email commits. Without this the new
  test could pass on the pre-lock fix alone and prove nothing about the `else`
  branch.
- **New negative control** `install_prefix_add_email_to_file_nocommit`: inject
  the pre-fix body (no commit, plain fast-path `return 0`) and assert
  **positively** that `emails.txt` is left ` M` dirty with **zero**
  contributor-email commits — in both the fresh-address and the
  already-on-disk shapes, so a control whose injection silently failed cannot
  pass.
- Verify tests 2/2b/3/4/5/6 still pass. Test 2 (busy mutex ⇒ write skipped)
  gains one assertion it currently lacks: **no** contributor-email commit is
  made, which is the direct pin for "the commit never runs when nothing was
  written under the mutex".

### Post-phase (risk mitigations)

- **`broad_suite_sweep`** — after steps 1-3 and the new tests land, do not stop
  at the two directly-targeted files. `lib/task_utils.sh` is sourced by nearly
  every framework script, so sweep the bash suites that exercise claiming,
  creation and locking (`tests/test_claim_id.sh`,
  `tests/test_create_silent_stdout.sh`, `tests/test_create_email_lock.sh`,
  `tests/test_pick_own_*.sh`, `tests/test_lock*.sh`) plus
  `bash tests/run_all_python_tests.sh`, and read only the last line for the
  Python verdict. Any failure here is blast-radius fallout from the new lib
  function/constant and must be resolved before commit, not deferred.

## Verification

```bash
bash tests/test_pick_own_scoped_commit.sh
bash tests/test_create_email_lock.sh
bash tests/test_pick_own_reclaim.sh 2>/dev/null || true   # if present
shellcheck .aitask-scripts/aitask_pick_own.sh \
           .aitask-scripts/aitask_create.sh \
           .aitask-scripts/lib/task_utils.sh
bash -n .aitask-scripts/aitask_pick_own.sh
```

Plus a broader guard, since `lib/task_utils.sh` is sourced by nearly every
script: run the bash tests that touch claiming/creation/locking
(`tests/test_claim_id.sh`, `tests/test_create_silent_stdout.sh`,
`tests/test_pick_own_*.sh`, `tests/test_lock*.sh`) and
`bash tests/run_all_python_tests.sh`.

Manual smoke on this repo (the real box): `./ait lock <n>` from a second shell,
then `./.aitask-scripts/aitask_pick_own.sh <n> --email <fresh address>` ⇒
`LOCK_FAILED` with `git status aitasks/metadata/emails.txt` **empty**.

## Risk

### Code-health risk: medium
- `lib/task_utils.sh` is sourced by nearly every framework script, so adding a
  function and a constant there has repo-wide blast radius even though the
  additions are inert for existing callers · severity: medium · → mitigation:
  inline post-phase `broad_suite_sweep`
- Moving `_commit_scoped`'s body out of `aitask_pick_own.sh` relocates a
  load-bearing, heavily-commented function that t1599_1's whole invariant rests
  on · severity: medium · → mitigation: inline pre-phase
  `thin_alias_keeps_call_sites`
- The recovery rule now lives at **four** call sites (two per writer) rather
  than one, so a future third membership check could silently re-open the hole
  · severity: medium · → mitigation: the rule is stated as an invariant in the
  Context section and each site carries the `ait_email_is_committed` call, and
  each of the four is covered by a test with its own positive negative-control
- The contributor commit runs **outside** the contributor-list mutex (matching
  the shipped `store_email` / `commit_and_push` split), so it can capture a
  snapshot that lags a concurrent writer's line by one write · severity: low ·
  → mitigation: inline post-phase `broad_suite_sweep` covers the regression
  surface, and the new concurrent-writer test pins the property directly; the
  lagged line is owed a commit by its own writer, which the fast-path recovery
  now guarantees
- Reordering `main()`'s steps changes *when* a contributor address is recorded:
  a refused claim no longer records it at all · severity: low · → mitigation:
  none needed — this is the intended semantic, and Test 4b pins it

### Goal-achievement risk: low
- Both defects were reproduced live against real scripts and the fix directions
  are named in the task; the only judgement call (recover-on-fast-path vs.
  reorder-only) is resolved by doing both, which the task's third bullet asks
  for · severity: low · → mitigation: none identified
- `ait_email_is_committed` adds one `git show` per claim on the common
  already-known-address path · severity: low · → mitigation: none needed — a
  claim already runs a fetch, a lock push and two commits; one local
  `show` is not measurable against that

### Planned mitigations
- timing: pre-phase | name: thin_alias_keeps_call_sites | type: refactor | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — relocating `_commit_scoped` out of `aitask_pick_own.sh` | desc: keep `_commit_scoped` as a one-line delegator to `task_git_commit_scoped` so no call site or negative-control injection moves
- timing: post-phase | name: broad_suite_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — repo-wide blast radius of adding to `lib/task_utils.sh` | desc: run the claim/create/lock bash suites and the full Python suite, not just the two directly-targeted test files

**Reassessment (post-inline):** re-running the two-dimension assessment against
the augmented plan leaves both levels unchanged — code-health stays **medium**
(the blast radius of touching `lib/task_utils.sh` is reduced-but-not-removed by
a test sweep) and goal-achievement stays **low**.

## Post-Review Changes

### Change Request 1 (2026-08-26 15:10)
- **Requested by user:** The global `EMAIL_STORED` declaration comment
  (`aitask_pick_own.sh:72`) still said the flag is set only when this invocation
  added a new address, contradicting `store_email`'s updated contract and
  inviting a future maintainer to narrow the recovery branches back out.
- **Changes made:** Rewrote the declaration comment as the contract "this claim
  owes emails.txt a commit", naming both setters and stating explicitly that
  narrowing it back removes the recovery. Verification found a second, worse
  problem in the same comment that the report did not name: its follow-on
  sentence, "A claim refused at the task lock still leaves its append on disk",
  asserted the very defect this task removes. That sentence was removed and
  replaced with the clause that IS still true — a claim carrying no email never
  commits a foreign line. Plan step 2 updated to list both comment sites rather
  than only `store_email`'s header.
- **Files affected:** `.aitask-scripts/aitask_pick_own.sh`,
  `aiplans/p1626_emails_txt_writers_strand_uncommitted_addresses.md`
- **Verification:** comment-only change; both suites re-run — 103 + 78 passing.

## Final Implementation Notes

- **Actual work done:** Implemented as planned, in the planned order (pre-phase
  mitigation first, then steps 1-3, then tests, then the post-phase sweep).
  `lib/task_utils.sh` gained `task_git_commit_scoped` (body moved verbatim from
  `aitask_pick_own.sh::_commit_scoped`, which is now a one-line delegator),
  `AIT_EMAILS_FILE`, and `ait_email_is_committed`. `aitask_pick_own.sh` moved
  `store_email` below the lock gate and the status write, and both of its
  membership short-circuits now consult HEAD. `aitask_create.sh` restructured
  `add_email_to_file` around one `needs_email_commit` flag and one commit tail,
  with both short-circuits consulting HEAD and the release status captured
  rather than discarded. Tests: `test_pick_own_scoped_commit.sh` 69 → 103
  assertions, `test_create_email_lock.sh` 35 → 78.

- **Deviations from plan:** One, in the *test* design rather than the fix. The
  plan sketched the under-lock-recheck tests as "start the holder, start the
  writer, wait for the task file to appear, then release" — which is a RACE, not
  a deterministic scenario: nothing in that ordering guarantees the writer's
  pre-lock check runs before the holder's append, and if it does not, the writer
  takes the *pre-lock* recovery branch instead and the test silently stops
  exercising the branch it exists for. Replaced with a barrier patched into the
  fixture's COPY of the mutex library (`registry_lock.sh` / `stale_lock.sh`),
  parking the writer at the seam between its pre-lock check and its mutex
  acquisition. The holder sources the PROJECT's unpatched library, so it is
  still a real second process contending on the real mutex; only the writer's
  position is pinned. This is what makes the "absent at pre-lock, present at
  under-lock" ordering a fact the test asserts rather than a timing hope.

  Also strengthened beyond the plan: `test_create_email_lock.sh` Test 12 as
  planned would have duplicated Test 3's on-disk assertions. Its scenario driver
  now samples git state before `teardown` pops the directory, so Test 12 pins
  what only it can see — the commit made outside the mutex carries the holder's
  line too and strands nothing.

- **Issues encountered:**
  - The two Test 4 assertions in `test_pick_own_scoped_commit.sh` failed after
    the fix, exactly as the plan predicted: they reached their dirty state
    *through* the defect (a refused claim appending). Repaired by seeding the
    dirty state directly, keeping the invariant the test actually guards, and
    adding Test 4b to cover the same-address retry the old test could not.
  - The `EMAIL_STORED` declaration comment (Change Request 1 above) was missed
    in the first pass — the plan named `store_email`'s header comment but not
    the global declaration eight lines from the top of the file.

- **Key decisions:**
  - **`ait_email_is_committed` fails toward "not committed".** Over-claiming
    costs at most one `task_git_commit_scoped` call that returns 2 (verified
    nothing to commit); under-claiming is permanent. Same reasoning applies to
    an unreadable HEAD, an untracked file, and a repo with no commits.
  - **The commit runs OUTSIDE the contributor-list mutex**, matching the shipped
    `store_email` / `commit_and_push` split. Committing inside would put a
    `die`-capable `task_git` call (`assert_data_worktree_clean`) inside a
    critical section with no EXIT trap, leaking the lock dir on a wedged data
    worktree.
  - **The release status is captured but does NOT gate the commit**, and the
    direction is the opposite of what it looks like: `stale_lock_release`
    returns non-zero exactly when OUR OWN lock dir is still in place
    (`stale_lock.sh:691`, `:700-701`), so the commit is *more* serialized then,
    while the genuinely ambiguous case ("not owner … leaving intact", `:706`)
    returns success. Gating on the status would skip the commit precisely when
    it is safest. The warning instead names the dead-record reclaim that clears
    a retained lock, so a retained mutex is never a silent dead end.
  - **All four membership short-circuits consult HEAD**, not just the two
    pre-lock ones. Fixing only the pre-lock path leaves a live concurrent hole,
    and each of the four is covered by a test with its own positive
    negative-control.

- **Upstream defects identified:** None

- **Verification run:** `tests/test_pick_own_scoped_commit.sh` 103/103;
  `tests/test_create_email_lock.sh` 78/78; `test_claim_id.sh` 54/54;
  `test_create_manual_verification_gates.sh` 42/42;
  `test_create_manual_verification.sh` 18/18; `test_create_project_flag.sh`
  34/34; `test_create_silent_stdout.sh` 14/14; `test_lock_diag.sh` 9/9;
  `test_lock_force.sh` 16/16; `test_lock_live_holder_gate.sh` 60/60;
  `test_lock_reclaim.sh` 20/20; `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
  `shellcheck` finding counts unchanged versus HEAD for all three source files
  (19 = 19 on `aitask_create.sh`; the rest pre-existing). Live smoke of
  `ait_email_is_committed` against this repo returns correctly in both
  directions.
