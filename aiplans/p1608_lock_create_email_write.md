---
Task: t1608_lock_create_email_write.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1608 — Lock `add_email_to_file`'s write to the contributor list

## Context

`aitasks/metadata/emails.txt` has exactly two writers. t1599_1 put one of them
(`store_email()` in `.aitask-scripts/aitask_pick_own.sh:243-280`) behind the
`ait_lock_dir emails` mutex; the other
(`add_email_to_file()` in `.aitask-scripts/aitask_create.sh:1128-1135`) still does
an unlocked `echo >> ; sort -u -o`. A mutex only excludes writers that honour it,
so today's serialization buys nothing against a concurrent `ait create`: `sort -o`
snapshots the file and renames its output over the target, so whichever writer
finishes second erases the address the other just appended. Closing this one call
site completes the protocol — the remaining `emails.txt` references
(`aitask_lock.sh:625`, `board/aitask_board.py:197`, `lib/profile_editor.py`) are
readers, re-verified by an independent sweep of `.aitask-scripts/` and `seed/`.

## Findings that shape the fix

**Interop is real, by construction, not coincidence.** `lib/registry_lock.sh` is a
thin adapter: `registry_lock_acquire` calls `stale_lock_acquire "$dir" …` on the
*same* caller-supplied dir, and `registry_lock_release` calls
`stale_lock_release`. Two callers using the different adapters on one lock dir
therefore contend on one `mkdir` mutex. Step 3's Test 1 pins this executably in
both directions rather than leaving it asserted in prose.

**Use `stale_lock` directly in `aitask_create.sh`, not `registry_lock`.** Two
reasons, both concrete:

- `aitask_create.sh` already sources `lib/stale_lock.sh` (line 17) and already
  speaks this protocol for its child-creation lock
  (`acquire_child_lock`/`release_child_lock`, lines 337-360). No new dependency.
- `registry_lock_acquire` installs `trap "registry_lock_release '$dir'" EXIT` and
  `registry_lock_release` runs `trap - EXIT`. `aitask_create.sh` installs its own
  `trap '_child_lock_exit_trap' EXIT` (lines 832, 2094) around child creation.
  Both current `add_email_to_file` call sites (lines 889 and 2158) sit in the
  **parent**-task branch where no child trap is live, so registry_lock would be
  safe *today* — but it would silently disarm the child-lock trap if the call ever
  moved. `stale_lock` installs no trap and takes an explicit owner token.

Since the adapters do interoperate, converging both call sites on one adapter (the
task's fallback) is not required.

**Busy behaviour: warn and continue** — the same call `store_email` makes, for a
stronger reason here. At both call sites the task file has already been written to
disk and is not yet committed, and the address is already recorded in the task's own
`assigned_to:` frontmatter; only the autocomplete vocabulary misses it. Aborting
`ait create` because a convenience list was busy would leave an uncommitted task on
disk to fix a strictly smaller problem. This is stated in a comment at the call
site, not left implicit.

## Implementation

### 1. `.aitask-scripts/aitask_create.sh` — lock the write

Add the budget seam next to `EMAILS_FILE` (line 1117), mirroring
`EMAILS_LOCK_TIMEOUT` in `aitask_pick_own.sh:81` but in the attempts×sleep form
`stale_lock_acquire` takes, and matching the child lock's `20 0.5` (~10s):

```bash
EMAILS_LOCK_ATTEMPTS="${EMAILS_LOCK_ATTEMPTS:-20}"
EMAILS_LOCK_SLEEP="${EMAILS_LOCK_SLEEP:-0.5}"
```

Rewrite `add_email_to_file()` to the `store_email` shape — same lock path,
re-check under the lock, release on every exit path:

```bash
add_email_to_file() {
    local email="$1"
    [[ -n "$email" ]] || return 0
    ensure_emails_file
    grep -qFx -- "$email" "$EMAILS_FILE" 2>/dev/null && return 0   # fast path only

    # `echo >> ; sort -u -o` is a read-modify-write and `sort -o` renames a
    # SNAPSHOT over the target, so a concurrent append is erased. Same mutex as
    # store_email() in aitask_pick_own.sh (t1608) — the two use different
    # adapters over lib/stale_lock.sh, which contend on one mkdir mutex.
    local lockdir token rc=0
    lockdir="$(ait_lock_dir emails)" || return 0
    if ! stale_lock_acquire "$lockdir" "$EMAILS_LOCK_ATTEMPTS" "$EMAILS_LOCK_SLEEP" \
            "contributor list"; then
        # Best-effort: the task file already carries assigned_to, and it is on
        # disk uncommitted — a busy vocabulary list must not fail creation.
        warn "contributor list busy — email not recorded$(stale_lock_describe "$lockdir")"
        return 0
    fi
    token="$STALE_LOCK_TOKEN"
    {
        # Re-check under the lock: a holder we waited on may have added it.
        if ! grep -qFx -- "$email" "$EMAILS_FILE" 2>/dev/null; then
            printf '%s\n' "$email" >> "$EMAILS_FILE"
            sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
        fi
    } || rc=$?
    stale_lock_release "$lockdir" "$token" \
        || warn "add_email_to_file: contributor-list lock not fully released"
    [[ $rc -eq 0 ]] || warn "add_email_to_file: failed to record ${email} (rc=$rc)"
    return 0
}
```

`aitask_create.sh` runs under `set -e` only (no `-u`/`pipefail`). The `{ … } || rc=$?`
group and the `grep … && return 0` guard are both errexit-safe in that mode
(verified: a failing command left of `&&` does not trigger `set -e`).

### 2. `.aitask-scripts/aitask_pick_own.sh` — retire the stale comment

`store_email` carries an `INCOMPLETE until t1608:` block (lines 259-262) saying the
other writer is unlocked. Replace it with the now-true statement: both writers hold
`ait_lock_dir emails`, via different adapters over the same `stale_lock` core, and
both must keep using that path.

### 3. `tests/test_create_email_lock.sh` — new

Follows the fixture pattern of `tests/test_create_silent_stdout.sh` (bare remote +
clone + `setup_fake_aitask_repo`, which already copies both `stale_lock.sh` and
`registry_lock.sh`) and the mutex-boundary shape of Test 8 in
`tests/test_pick_own_scoped_commit.sh`. All lock paths are isolated via
`AITASKS_LOCK_DIR`.

- **Test 1 — the two adapters exclude each other on one lock dir, both directions.**
  Source `registry_lock.sh` and `stale_lock.sh` directly. (a) hold via
  `registry_lock_acquire` → assert `stale_lock_acquire` on the same dir returns 1;
  release → assert it now succeeds. (b) hold via `stale_lock_acquire` → assert
  `registry_lock_acquire` returns 1; release → assert it now succeeds. Acquire in
  the test's own process, never in a command substitution (`stale_lock.sh` header).

- **Test 2 — `ait create` honours the mutex (Test 8 shape).** Plant a live holder
  on `$AITASKS_LOCK_DIR/emails` (a backgrounded `sleep`, its pid in `pid`). Run
  `aitask_create.sh --batch --commit --assigned-to bob@test.com` with
  `EMAILS_LOCK_ATTEMPTS=2 EMAILS_LOCK_SLEEP=0.05`. Assert: exit 0 and the task file
  exists (creation not failed), `emails.txt` byte-identical to before (never
  written unlocked), and `contributor list busy` on stderr. Then kill the holder,
  remove the lock dir, re-run with a second address → it lands (other side of the
  boundary).

- **Tests 3 and 4 — no address is lost across the two writers, plus its negative
  control.** One shared scenario driver, run twice: once against the fixed script
  (Test 3) and once against an injected pre-fix copy (Test 4). Both branches
  synchronize on an **observed file state**, never on a clock — `stale_lock_acquire`
  emits nothing while it waits (`lib/stale_lock.sh:249-299`), so `emails.txt`
  content is the only real observable, and each branch's wait is a bounded poll on
  a *condition* whose timeout is a hard FAIL, not a fall-through.

  The holder side is a helper that sources `registry_lock.sh` — the adapter
  `store_email` uses — acquires `$AITASKS_LOCK_DIR/emails`, captures the file
  snapshot, and only then hands control back. `ait create --batch --commit
  --assigned-to bob@test.com` runs in the background with a budget that comfortably
  outlasts the holder section (`EMAILS_LOCK_ATTEMPTS=600 EMAILS_LOCK_SLEEP=0.05`,
  ~30s).

  - **Test 4 (negative control, injected pre-fix code):** while still holding the
    lock, poll `emails.txt` until it contains `bob@test.com`, bounded (say 20s).
    **Assert that it appeared** — this is the defect asserted positively: the
    unlocked writer wrote *while the mutex was held*. Timing out is a FAIL with an
    explicit message, so an injection that silently failed cannot pass. Only after
    that observation does the helper write back `snapshot + alice@test.com` with
    `sort -u -o` and release. Then `wait` for create and assert `bob@test.com` is
    **absent** and `alice@test.com` present — the lost update, reproduced.

  - **Test 3 (fixed code):** first wait (bounded, FAIL on timeout) for the created
    task file, which `aitask_create.sh` writes immediately before calling
    `add_email_to_file` — that is the proof create actually reached the email step
    rather than not having started. Then **boundedly assert `bob@test.com` stays
    absent** from `emails.txt` for a settle window while the lock is still held —
    the mirror of Test 4's observation, and the assertion that the write is now
    excluded. Only then write back `snapshot + alice@test.com`, release, `wait`,
    and require **both** addresses present.

  The pre-fix injection uses the `install_prefix_commit_and_push` technique from
  `tests/test_pick_own_scoped_commit.sh:141-160`: rebuild the fixture's *copy* of
  `aitask_create.sh` with the legacy unlocked `add_email_to_file` appended ahead of
  the final `main "$@"` line, so the control stays executable after the fix lands.

- **Test 5 — the failure path releases the mutex.** The `{ … } || rc=$?` catch
  exists so a failed append/sort still reaches `stale_lock_release`; nothing else in
  this suite exercises it, so a future change could strand the lock while every
  success and busy test stayed green. Force the mutation to fail through a narrow
  PATH shim: a `sort` wrapper, first on `PATH`, that exits 1 **only** when its
  arguments name `-o` and the emails path, and otherwise `exec`s the real binary
  resolved by absolute path at shim-generation time (`command -v sort` before the
  `PATH` prepend, so it cannot recurse). `aitask_create.sh` invokes `sort` in
  exactly one place (line 1133), so the shim cannot perturb anything else in it, and
  the pass-through keeps the helper scripts it shells out to intact.

  Assert, in order: (a) the `add_email_to_file: failed to record` warning is on
  stderr — proof the injection actually took effect rather than being assumed;
  (b) `ait create` still exits 0 and the task file exists — the best-effort
  contract holds on the failure path too; (c) `$AITASKS_LOCK_DIR/emails` no longer
  exists; and (d) a fresh `stale_lock_acquire` on that same dir from the test
  process succeeds within 2 attempts — post-failure reacquisition proven, not
  inferred from (c). Finally remove the shim and run create with a further address
  to show the path still works end-to-end.

- **Test 6 — `bash -n` syntax check on `aitask_create.sh`.**

Counter handling: the file's test bodies run in the shell's own scope (no `( … )`
subshells), matching `test_create_silent_stdout.sh`, so the in-process
`PASS`/`FAIL`/`TOTAL` helpers from `tests/lib/asserts.sh` are used directly. Any
body that must run in a subshell instead opts into `assert_counters_init` /
`assert_counters_load` per CLAUDE.md.

## Verification

```bash
bash tests/test_create_email_lock.sh          # new suite, all tests pass
bash tests/test_pick_own_scoped_commit.sh     # t1599_1 mutex tests still pass
bash tests/test_create_silent_stdout.sh       # create --batch --commit contract
bash tests/test_parallel_child_create.sh      # child-lock path untouched
bash tests/test_create_manual_verification.sh
shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_pick_own.sh
```

Negative-control discipline: Tests 3 and 4 run the same scenario driver against the
fixed and the injected script, so they discriminate on the changed dimension by
construction. Before committing, additionally confirm the suite fails when run
against an un-fixed `aitask_create.sh` (stash the Step 1 edit and re-run) — the
control's injection must be what produces the loss, not a broken fixture. Every
bounded poll in the suite fails loudly on timeout rather than falling through, so a
scenario that did not actually reproduce cannot report success.

No user-facing docs change: no website or `aidocs/` page documents the
contributor-list mutex, and the fix is invisible at the CLI surface.

Step 9 (Post-Implementation) applies as usual: commit as
`bug: <description> (t1608)`, then archive the task and plan.
