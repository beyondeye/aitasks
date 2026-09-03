---
Task: t1698_attach_artifact_transaction_boundary_not_isolated_from_workt.md
Branch: main
Base branch: main
Output branch: main
---

# t1698 — Isolate the attach/artifact transaction boundary from the worktree

## Context

`ait attach` and `ait artifact` run their mutations as git transactions, but the
boundary of those transactions is not isolated from the surrounding worktree.
Three measured, pre-existing defects share that one root cause:

1. **A successful commit absorbs an unrelated in-flight edit.** `_attach_commit`
   / `_artifact_commit` run `task_git add -- "$path"`, which stages the *whole*
   file. Path-scoping the commit does not help when the path itself is already
   dirty, so a user's unrelated edit to `aitasks/t5_demo.md` is published under
   an `ait: Attach …` message. Once in HEAD, no rollback can undo it.
2. **Rollback destroys an unrelated in-flight edit.** The existing rollbacks are
   `task_git reset` + `task_git checkout -- <path>` — restore-from-**HEAD**,
   which discards any pre-existing dirty state on a transaction-owned path.
3. **A post-mutation abort leaves uncommitted ledger drift.** The rollback lives
   inline inside the commit-failure branch *only*. Since t1675 added `|| die`
   guards, an abort can now happen after a mutation and before the commit (a
   successful `attach_meta decref` followed by a failing `frontmatter_patch.py
   remove`), leaving the ledger decremented on disk with the frontmatter intact.

t1675 stopped a failed mutation being reported as **success**; it deliberately
left the residual on-disk state to this task (`lib/attachment_lock.sh` and
`tests/test_attach_lock_callback_contract.sh` both carry an explicit "see t1698"
pointer).

**Outcome:** one promoted snapshot facility, a fail-closed dirty-path preflight
on all eight verb paths, and a rollback that fires from *every* abort path and
restores pre-transaction bytes and index entries rather than HEAD. Invariant:
**a transaction either commits completely, or restores its own paths to their
pre-transaction bytes and index entries.**

---

### Pre-phase (risk mitigations)

Runs **before** Step 1, so it characterizes today's behaviour rather than the
change's.

**`fail_loud_restore_contract`.** Build `txn_snap_restore`'s status
accumulation, `_TXN_RESTORE_FAILED`, the snapshot-preserving `txn_snap_cleanup`
and `_txn_exit_trap`'s two-branch message **as part of Step 1 itself**, with the
Step 6a restore-fault case written alongside them — not bolted on afterwards.
The specification is under "The restore-failure contract" in Step 1. Sequencing
it first matters because the promoted fold code is fail-quiet by construction
(`|| warn` then an unconditional full-rollback claim): porting it as-is and
hardening later means every intermediate commit ships a rollback that can lie
about what it restored, and the eight verbs are wired onto it in between.

**`pin_attach_lock_not_leaked_on_abort`.** Add a case to
`tests/test_attach_txn_worktree_isolation.sh` (or a small standalone file, if it
lands before that one exists) asserting that `attachments/.attach.lock` does not
exist after a **faulted** `attach add` and a faulted `artifact create` — i.e.
the global attach mutex is released when a transaction dies mid-body, not only
when it returns. Use t1675's `AIT_PYTHON` shim for the fault.

It must **pass on today's tree**: `registry_lock_acquire`'s own EXIT trap
releases the lock on a `die`, and that is exactly the trap Step 2 chains onto.
Writing it first turns the highest-rated code-health risk — a bare `trap … EXIT`
inside the callback silently replacing the lock-release handler — from a review
question into a test that fails the moment the chain is wrong. Pairs with
`tests/test_attach_local_backend.sh` section I, which covers the *success* path
only.

---

## Step 1 — Promote the snapshot facility to `lib/txn_snapshot.sh` (new file)

`aitask_fold_mark.sh:428-489` already carries a correct facility (t1668).
Promote it under neutral names rather than writing a second one.

**New file `.aitask-scripts/lib/txn_snapshot.sh`**, with the standard
source-guard / `_SELF` preamble used by `lib/attachment_meta.sh`. It requires
`task_utils.sh` (for `task_git` and `_ait_detect_data_worktree`) and
`terminal_compat.sh` (`die` / `warn`) to have been sourced by the caller —
document that in the header, as `attachment_meta.sh` does.

**Two touchpoints deliberately not needed**, both checked against
`aidocs/framework/aitasks_extension_points.md` and
`aidocs/framework/shell_conventions.md`: the 5-file agent allowlist applies only
to helpers *invoked* from a skill (this is a sourced lib with no skill-facing
path), and `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` mirrors only
`./ait`'s source-on-startup chain, which this lib does not join — it is sourced
by its three consumers directly, exactly like `lib/attachment_meta.sh`.

State (file globals):

```bash
_TXN_SNAP_DIR=""
_TXN_SNAP_PATHS=()          # index i -> data-root-relative path; i.blob / i.idx hold its state
_TXN_ACTIVE=false
_TXN_ROLLBACK_HOOK=""       # optional verb-specific extra restore (blobs)
declare -A _TXN_CLEAN_CHECKED=()
declare -A _TXN_SNAPSHOTTED=()
```

**Two independent dedup sets, exactly as the task specifies.** A single `seen`
set is unsound: clean-check-first would mark the path and make the snapshot
skip, leaving nothing to restore; snapshot-first would mark it and make the
clean check skip, letting a dirty path be committed. Both are reset by
`txn_snap_init`, so the two helpers are order-independent.

### API

| function | behaviour |
|---|---|
| `txn_snap_init` | `mktemp -d` the snapshot dir (`die` on failure); clear `_TXN_SNAP_PATHS` and both dedup maps. |
| `txn_snap_add <relpath>` | Record one path's pre-mutation state. No-op if already in `_TXN_SNAPSHOTTED`. Copies the bytes to `<dir>/<i>.blob` when the file exists (absence is represented by the *missing* `.blob`, so restore deletes a transaction-created path); captures `task_git ls-files --stage -- <relpath>` verbatim into `<dir>/<i>.idx` — **fail closed** on a non-zero exit (an unreadable index must not be recorded as "absent", which would make `--force-remove` delete the caller's real entry). |
| `txn_snap_restore` | For each snapshotted path, in index order: restore bytes (or `rm -f` when absent pre-transaction); `task_git update-index --force-remove -- <p>` to drop every stage; replay `<i>.idx` via `update-index --index-info` when non-empty; finally `task_git update-index -q --refresh`. **Attempts every path**, returns non-zero if any failed, and records each via `txn_rollback_failed` — see below. |
| `txn_snap_cleanup` | `rm -rf` the snapshot dir; clear `_TXN_SNAP_DIR`. **Refuses to delete it when `_TXN_SNAP_RESTORE_INCOMPLETE` is true** — it is then the only surviving copy of the pre-transaction bytes. |
| `txn_require_clean <label> <relpath>` | No-op if already in `_TXN_CLEAN_CHECKED`. Otherwise `die` when the path has uncommitted changes. |
| `txn_chain_exit_trap <handler>` | Prepend `<handler>` to the current `EXIT` trap (see Step 2). |
| `txn_begin <label>` | `txn_snap_init`; `txn_chain_exit_trap '_txn_exit_trap'`; `_TXN_ACTIVE=true`; clear `_TXN_ROLLBACK_HOOK`; record `<label>` for messages. |
| `txn_on_rollback <fn>` | Register the verb's blob-specific extra restore. The hook reports failures with `txn_rollback_failed`, never `\|\| true`. |
| `txn_rollback_failed <desc>` | Record one un-restored item (from either half) and return 0. The single reporting seam. |
| `txn_rollback` | `_TXN_ACTIVE=false`; `txn_snap_restore`; run `_TXN_ROLLBACK_HOOK` when set; `txn_snap_cleanup`. Idempotent. **Returns non-zero if *either* half recorded a failure**, so no caller can claim a full rollback after a partial one. |
| `txn_end` | Terminal success: `_TXN_ACTIVE=false`; `txn_snap_cleanup`. |

### `txn_require_clean` — the dirt predicate

```bash
txn_require_clean() {
    local label="$1" p="$2"
    [[ -n "${_TXN_CLEAN_CHECKED[$p]:-}" ]] && return 0
    _TXN_CLEAN_CHECKED["$p"]=1
    local st
    st="$(task_git status --porcelain -- "$p")" \
        || die "${label}: could not read the status of ${p} — refusing to start"
    [[ -z "$st" ]] && return 0
    die "${label}: ${p} has uncommitted changes — this operation stages that whole path, so committing it would fold your edit into an \`ait\` commit. Commit it (./ait git commit -- ${p}) or revert it, then re-run."
}
```

`git status --porcelain -- <path>` covers all three ways the path can be dirty —
unstaged modification, staged modification, and untracked-but-present — and
returns empty for a path that does not exist, which is the transaction-created
case. The capture is `|| die`: a failed status read must not be misread as
clean (the fail-closed rule the whole file is built on). The status is read
before the check because `set -e` is suppressed inside every caller.

**Never stash-and-reapply.** Reapplying hunks around a commit can conflict, and
stashing in a shared worktree is the very hazard this task removes.

### The restore-failure contract — the claim must not outrun the restore

`_fold_restore_snapshots` warns per failed path and returns nothing, and
`_fold_abort_cleanup` then prints *"rolled back every mutation; nothing was
committed"* **unconditionally**. Those two facts compose into a false claim: a
`cp` onto a read-only path, or an `update-index` against an unwritable index,
leaves real drift behind while the user is told the tree is clean. Errexit is
suppressed inside every consumer, so nothing else catches it either.

Promoting this verbatim would ship the bug to eight more call sites. The lib
therefore makes restore **fail loud**:

The contract covers **every** restore action, not just the snapshot half. A
transaction's rollback has two parts — the snapshotted non-blob paths, and the
verb's blob hook — and a failure in either leaves real drift. `attach gc` is the
sharp case: its hook restores blobs it *deleted*, so a failed
`task_git checkout` means a permanently missing blob reported as a clean
rollback. One recorder serves both:

```bash
_TXN_RESTORE_FAILED=()            # every un-restored item, both kinds
_TXN_SNAP_RESTORE_INCOMPLETE=false   # snapshot half specifically (drives cleanup)

# txn_rollback_failed <description> -- the ONLY way any restore action reports
# failure. Hooks call it instead of `|| true`; txn_snap_restore uses it too.
# Always returns 0: recording a failure must never abort the rest of the restore.
txn_rollback_failed() { _TXN_RESTORE_FAILED+=( "$1" ); return 0; }

# txn_rollback_ok -- the ONE verdict, DERIVED from what was recorded.
txn_rollback_ok() { (( ${#_TXN_RESTORE_FAILED[@]} == 0 )); }
```

**The verdict is derived, never plumbed.** `txn_rollback_failed` returns 0 on
purpose — a failure to restore path 3 must not skip paths 4 and 5 — so any
caller shaped like

```bash
some_restore_step || rc=1      # WRONG: the `||` never fires
```

silently produces a clean verdict, because the recorder it calls succeeded.
Measured:

```
prune-only verdict rc=0 (0 == the bug)  recorded=1
```

Every verdict therefore comes from `txn_rollback_ok` (or, inside
`txn_snap_restore`, from the *delta* in the array across the call). One
derivation point, not N remembered `rc=1` assignments: a restore action added
later cannot manufacture a false clean verdict by forgetting to propagate,
because **recording is the propagation**.

Both are reset in `txn_snap_init`, never mid-rollback.

Verb hooks change from `|| true` to `|| txn_rollback_failed "<what, with enough
context to repair it>"`:

| hook action | recorded as |
|---|---|
| `artifact_backend_delete "$hash"` | `blob <hash> on backend <b> — created by this transaction and could not be deleted; reclaim with 'ait attach gc' (local) or remove it from the backend store by hand` |
| `task_git reset -- <blob_rel>` | `index entry <blob_rel> — still staged` |
| `task_git checkout -- <blob_rel>` (gc / artifact rm) | `blob <blob_rel> — deleted by this transaction and NOT restored; recover with 'git checkout HEAD -- <blob_rel>'` |

That last row is why this matters: without it, `gc` can delete a blob, fail to
put it back, and print "rolled back every mutation".

**These sites stay on t1675's ALLOWLIST, but their justification changes.**
`|| txn_rollback_failed …` matches neither accepted form (`|| die`,
`|| return <n>`), so the static guard still flags them. Rewrite each entry's
comment: it is no longer "best-effort on an already-failing path, nothing left
to abort" — it is now "failure is *recorded* and surfaced in the partial-rollback
report", which is a strictly better reason to exempt the line.

```bash
txn_snap_restore() {
    local i p fs before=${#_TXN_RESTORE_FAILED[@]}
    (( ${#_TXN_SNAP_PATHS[@]} )) || return 0
    for i in "${!_TXN_SNAP_PATHS[@]}"; do
        p="${_TXN_SNAP_PATHS[$i]}"; fs="$(_txn_fs_path "$p")"
        if [[ -f "$_TXN_SNAP_DIR/$i.blob" ]]; then
            cp -- "$_TXN_SNAP_DIR/$i.blob" "$fs" 2>/dev/null \
                || txn_rollback_failed "snapshot: $p (bytes)"
        else
            rm -f -- "$fs" 2>/dev/null \
                || txn_rollback_failed "snapshot: $p (delete)"
        fi
        task_git update-index --force-remove -- "$p" >/dev/null 2>&1 \
            || txn_rollback_failed "snapshot: $p (index clear)"
        if [[ -s "$_TXN_SNAP_DIR/$i.idx" ]]; then
            task_git update-index --index-info < "$_TXN_SNAP_DIR/$i.idx" >/dev/null 2>&1 \
                || txn_rollback_failed "snapshot: $p (index)"
        fi
    done
    task_git update-index -q --refresh >/dev/null 2>&1 || true
    (( ${#_TXN_RESTORE_FAILED[@]} == before )) && return 0    # derived, not plumbed
    _TXN_SNAP_RESTORE_INCOMPLETE=true
    return 1
}

txn_rollback() {
    _TXN_ACTIVE=false
    txn_snap_restore || true                                  # already recorded
    [[ -z "$_TXN_ROLLBACK_HOOK" ]] || "$_TXN_ROLLBACK_HOOK" || true
    txn_snap_cleanup                                          # keeps the dir if incomplete
    txn_rollback_ok                                           # <- the rollback verdict
}
```

Note there is no `rc` variable left in `txn_snap_restore`: its own status is the
**delta** in `_TXN_RESTORE_FAILED` across the call, so it cannot disagree with
what was recorded, and `_TXN_SNAP_RESTORE_INCOMPLETE` is set from that same
derivation.

`txn_rollback`'s status is the **union** of both halves, so a hook failure alone
is enough to suppress the full-rollback claim. `txn_snap_cleanup` keys off
`_TXN_SNAP_RESTORE_INCOMPLETE` rather than the array, because the snapshot
directory is only worth preserving when it holds bytes that did not make it
back — a hook-only failure has nothing in it to recover from, and pointing the
user at an irrelevant directory is its own kind of dishonesty.

Every path is attempted — a failure on one must not skip the rest — and the
status is accumulated rather than taken from the last command. Note
`--force-remove` is now **counted** rather than `|| true`'d: it succeeds for a
path that is not in the index, so a genuine failure means an unwritable index,
and silently continuing would leave a stale entry that the `.idx` replay does
not overwrite when the snapshot recorded no entry at all.

`_txn_exit_trap` then reports what actually happened:

```bash
_txn_exit_trap() {
    local rc=$?
    if [[ "$_TXN_ACTIVE" == true ]]; then
        if txn_rollback; then
            warn "${_TXN_LABEL}: aborted before the commit (exit ${rc}) — rolled back every mutation; nothing was committed"
        else
            echo "Error: ${_TXN_LABEL}: aborted (exit ${rc}) and the rollback did NOT fully restore:" >&2
            printf '  - %s\n' "${_TXN_RESTORE_FAILED[@]}" >&2
            echo "Nothing was committed, but the items above are left mid-transaction and need manual repair." >&2
            [[ "$_TXN_SNAP_RESTORE_INCOMPLETE" == true ]] && \
                echo "Their pre-transaction contents are preserved in ${_TXN_SNAP_DIR} (<i>.blob = bytes, <i>.idx = index entry); remove that directory once repaired." >&2
        fi
    fi
    txn_snap_cleanup
    return 0
}
```

Each item carries its own recovery instruction (the `txn_rollback_failed` table
above), so the report is actionable per line rather than a bare path list.

Three properties this buys, none of which the pre-fix build has:

1. **The full-rollback claim is never printed after a partial restore.** The
   commit-failure arms take the same branch — `txn_rollback || <partial
   message>` — so `die "… — rolled back"` is only reached when the rollback
   succeeded.
2. **The snapshot directory survives a failed restore.** It is the only
   remaining copy of the pre-transaction bytes, so deleting it would destroy the
   user's data at exactly the moment they need it. `txn_snap_cleanup` keeps it
   and the message names it. On a clean rollback it is removed as before.
3. **A failed blob hook is as loud as a failed snapshot restore.** `attach gc`
   deletes blobs and its hook puts them back; before this, a failed
   `task_git checkout` there meant a permanently lost blob announced as a clean
   rollback.

`_txn_exit_trap` still captures `$?` as its first command and never calls
`exit`, so the process's own status is untouched; the partial-restore case is
already on a failing path and needs a truthful message, not a different code.

Pinned by the Step 6a restore-fault case.

### Data-root path resolution (a fix the promotion carries)

`_fold_snap_add`'s `cp -- "$p"` / `rm -f -- "$p"` use the data-root-relative
path directly against the process CWD. That is correct in legacy mode
(`_AIT_DATA_WORKTREE == "."`) and for `aitasks/` / `aiplans/` in branch mode
(they are symlinks into `.aitask-data/`), but **not** for `attachments/` or
`artifacts/`, which are not symlinked (`lib/data_symlinks.sh`:
`AIT_DATA_LINKS=(aitasks aiplans)`). In branch mode `[[ -f "attachments/meta/…" ]]`
is false, so today's fold meta-tree snapshot silently records "absent" and a
rollback would *delete* the real meta file.

The lib therefore resolves filesystem operations through the data worktree while
keeping the data-root-relative path for every `task_git` call — mirroring what
`_attach_rollback_add` already does (`rm -f "$meta_file"` uses
`attach_meta_dir`, not the relpath):

```bash
_txn_fs_path() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then printf '%s' "$1"
    else printf '%s/%s' "$_AIT_DATA_WORKTREE" "$1"; fi
}
```

Used by `txn_snap_add` (the `-f` test and `cp`) and `txn_snap_restore` (the `cp`
and `rm -f`). `task_git ls-files` / `update-index` / `status` keep the relpath.

---

## Step 2 — `txn_chain_exit_trap`: why the rollback must chain, not replace

`registry_lock_acquire` (`lib/registry_lock.sh:130`) installs
`trap "registry_lock_release '<dir>'" EXIT`, **overwriting** whatever the caller
had, and `registry_lock_release` clears it outright with `trap - EXIT`. So a
rollback trap installed before `with_attach_lock` is destroyed by the acquire,
and one installed with a bare `trap … EXIT` inside the callback would leak the
lock.

The idiom already exists in `_fold_attach_txn` (`aitask_fold_mark.sh:791-793`);
promote it so the two halves cannot drift:

```bash
txn_chain_exit_trap() {
    local cur; cur="$(trap -p EXIT)"; cur="${cur#trap -- }"; cur="${cur% EXIT}"
    eval "trap '$1; '$cur EXIT"
}
```

Ordering is load-bearing: our handler runs **first** (rolls back while the lock
is still held), then `registry_lock_release`.

`_txn_exit_trap` mirrors `_fold_abort_cleanup`:

```bash
_txn_exit_trap() {
    local rc=$?
    if [[ "$_TXN_ACTIVE" == true ]]; then
        txn_rollback
        warn "${_TXN_LABEL}: aborted before the commit (exit ${rc}) — rolled back every mutation; nothing was committed"
    fi
    txn_snap_cleanup
    return 0
}
```

It captures `$?` as its first command and never calls `exit`, so the script's
own exit status survives it (the rule recorded for
`ait_ledger_lock_exit_trap`). It is the **first** handler in the chain, so it
does not destroy a status a later handler needs, and `registry_lock_release`
does not read `$?`. Its two branches — full rollback vs. partial — are specified
under "The restore-failure contract" in Step 1.

This is what closes **defect 3**: `die` calls `exit`, so there is no
"every abort path" to instrument by hand — the trap *is* every abort path.

---

## Step 3 — Rewire `aitask_fold_mark.sh` onto the lib

Source `lib/txn_snapshot.sh` **at the top of the file**, after
`lib/task_utils.sh` (`aitask_fold_mark.sh:68`) — not beside the lazy
`attachment_lock.sh` / `attachment_meta.sh` sources at line 824, which run
inside `_fold_attach_txn`: `txn_snap_init` is called at top level (line 531),
long before that function exists. The lib's two dependencies (`task_git` from
`task_utils.sh`, `die`/`warn` from `terminal_compat.sh`) are both already
sourced there. `aitask_attach.sh` and `aitask_artifact.sh` add it to their
existing top-of-file source blocks.

Then delete the private copies and rename the call sites:

| removed | replaced by |
|---|---|
| `_fold_snap_dir`, `_fold_snap_paths` | `_TXN_SNAP_DIR`, `_TXN_SNAP_PATHS` (internal to the lib) |
| `_fold_snap_init` | `txn_snap_init` |
| `_fold_snap_add` (2 call sites: line 532 loop, line 769 meta tree) | `txn_snap_add` |
| `_fold_restore_snapshots` | `txn_snap_restore` |
| `rm -rf "$_fold_snap_dir"` in `_fold_abort_cleanup` | `txn_snap_cleanup` |
| the inline `trap -p EXIT` chain in `_fold_attach_txn` | `txn_chain_exit_trap '_fold_abort_cleanup'` |

`_fold_txn_active`, `_fold_rollback`, `_fold_abort_cleanup`,
`_fold_prune_unsnapshotted_meta`, `_fold_snapshot_meta_tree` and
`_fold_meta_root` / `_fold_meta_pre` stay fold-local: fold arms **before** the
lock (the verbs arm inside it) and its rollback has extra prune semantics. Fold
does **not** call `txn_require_clean` — see the placement constraint in Step 4.

### The fold wrappers must carry the restore verdict too

Staying fold-local is not the same as staying fail-quiet. Today:

```bash
_fold_rollback() {
    _fold_txn_active=false
    _fold_restore_snapshots        # status discarded...
    _fold_prune_unsnapshotted_meta # ...this is what the function returns
}
```

and **all four** call sites ignore even that and print an unconditional claim —
`_fold_abort_cleanup` (`aitask_fold_mark.sh:522`) and Step 6's three failure
arms (`:998`, `:1008`, `:1018`, each `_fold_rollback` then `die "… — rolled back
the whole fold transaction"`). So promoting the primitive alone gives fold the
preserved recovery directory but leaves it claiming a full rollback it may not
have performed — and `_fold_abort_cleanup`'s own bare `rm -rf "$_fold_snap_dir"`
would delete that directory anyway.

Three edits, all in the same commit as the promotion:

1. `_fold_rollback` returns the **derived** verdict — not `|| rc=1` plumbing:
   ```bash
   _fold_rollback() {
       _fold_txn_active=false
       txn_snap_restore || true             # recorded, not swallowed
       _fold_prune_unsnapshotted_meta       # records via txn_rollback_failed
       txn_rollback_ok                      # <- the verdict
   }
   ```
   The prune deletes meta files the transaction created, so a failure there is
   residual drift exactly like a failed byte restore; its `rm -f` records through
   `txn_rollback_failed` and stops being `|| true`.

   **`_fold_prune_unsnapshotted_meta || rc=1` would be a no-op**, and this is the
   trap worth stating twice: `txn_rollback_failed` returns 0 by design, it sits
   in the prune loop's tail position, so the function returns 0 even having
   recorded a failure — a prune-only failure would sail through as a complete
   rollback. Measured with the loop shape in a scratch shell: `verdict rc=0,
   recorded=1`. The prune must therefore **not** try to propagate a status at
   all; `txn_rollback_ok` reads what was recorded.
2. All four call sites branch on it, using the **same** wording as
   `_txn_exit_trap`'s two branches — the truthful partial message, the per-item
   list, and the retained-snapshot recovery line. One phrasing, two files.
3. `_fold_abort_cleanup`'s `rm -rf "$_fold_snap_dir"` becomes `txn_snap_cleanup`,
   which honours `_TXN_SNAP_RESTORE_INCOMPLETE`. Without this the recovery
   directory the contract promises is deleted three lines later.

Pinned end-to-end by two new `test_fold_mark.sh` cases — a failed **snapshot
restore** and a failed **prune** — plus the positive control (Step 6a-fold).

Fold gains the dedup for free, and that is a strict improvement: `fold_paths`
can name the same file twice, and the meta tree is snapshotted at Step 5b *after*
Steps 3-5 already mutated the task files. Dedup makes the second `txn_snap_add`
a no-op, so restore yields the true pre-fold bytes instead of the post-Step-5
ones.

### Update `tests/test_fold_mark.sh`'s pre-fix injectors in the same commit

Two injectors patch the delimited `# --- fold transaction (t1668)` block by
name and would stop being pre-fix builds once the names move:

- `install_prefix_no_abort_rollback` — stubs `_fold_snap_add`,
  `_fold_restore_snapshots`, … . Change the stubs to shadow the **lib** names
  (`txn_snap_add() { :; }`, `txn_snap_restore() { :; }`, `txn_snap_init() { :; }`,
  `txn_snap_cleanup() { :; }`) — the block sits below the `source` line, so a
  redefinition there shadows the lib. Update its grep guard
  `_fold_snap_add "\$_p"` → `txn_snap_add "\$_p"`.
- `install_attach_txn_returns_nonzero` — its `'    _fold_snapshot_meta_tree$'`
  guard still holds (that function stays fold-local); re-verify after the edit.

Both injectors already self-assert that the injection landed; keep those
assertions meaningful rather than merely passing.

---

## Step 4 — The preflight (defect 1), per verb

**Placement: at the verbs, never in the seam.** A preflight inside
`with_attach_lock`, `_attach_commit`, `_artifact_commit` or the shared helpers
would break `ait fold` outright: fold writes task files in its Steps 4-5 and
commits only at Step 6, so at its Step 5b attach transaction those files are
*legitimately dirty with the fold's own work*. Fold reaches only
`_fold_attach_txn`, never the eight verb paths.

Each check goes at the top of the verb's transaction callback, **before its
first mutation**. That is inside the lock rather than before it (`meta_rel` /
`manifest_rel` need the hash / handle that the callback resolves), which is
functionally identical for correctness and avoids re-hashing a 25 MB file
outside the lock. `gc` and `decref-deleted` discover paths as they iterate and
check immediately before each path's first mutation, as the task requires.

Every verb also calls `txn_begin "<label>"` as the first statement of its
callback, and `txn_snap_add` on the same non-blob paths (Step 5).

| verb (callback) | paths checked | placed immediately before |
|---|---|---|
| `_attach_add_txn` | `$task_file`, `meta_rel` | `artifact_backend_put` (after the size cap, dup guard and pre-existence probe, all of which only `die`) |
| `_attach_rm_txn` | `$task_file`, `meta_rel` | `attach_meta decref` |
| `_attach_gc_txn` | `meta_rel` of each **actually-swept** blob | that blob's `artifact_backend_delete` / `rm -f "$meta_file"` |
| `_attach_decref_deleted_txn` | `attach_meta_relpath "$hash"` | the `incref`/`decref` in **each** of the two mutating branches (the `REBIND_NOOP` branch mutates nothing and must not be refused) |
| `_artifact_create_txn` | `$task_file`, `manifest_rel` | `artifact_store` |
| `_artifact_update_txn` | `manifest_rel` **only** | `artifact_store`, after the `hash == current` no-op return |
| `_artifact_move_txn` | `manifest_rel` **only** | phase 1 `artifact_resolve`, after the same-backend no-op return |
| `_artifact_rm_txn` | `$task_file`; `manifest_rel` separately | `frontmatter_patch.py remove`; the manifest check goes on the last-reference branch only, before `rm -f "$manifest_path"` |

Three deliberate narrowings, all asserted in Step 6 rather than assumed:

- **`attach gc` checks the *swept* set, not the *candidate* set.** The check sits
  after the `refs` / blocking-set / grace gates, each of which `continue`s, so a
  blob that is retained is never checked. This is discriminating, not cosmetic:
  checking all zero-refcount candidates would refuse
  `test_attach_lock_callback_contract.sh:332` and `test_attach_archive_gc.sh:75`,
  both of which legitimately sweep while an unrelated retained candidate's meta
  JSON is dirty.

- **`update` / `move` never check a task file.** They never stage one — the
  stable-handle / mutable-manifest split. A dirty task file must not block them.
- **`artifact rm` checks the manifest only on the branch that stages it.** The
  stale-reference and referenced-elsewhere branches stage the task file alone.

`attach add`'s `meta_rel` requires the hash, which `_attach_add_txn` already
computes for the dup guard; `attach rm`'s comes from `_attach_resolve_ref`.
Blob relpaths are never passed to `txn_require_clean`: a blob's path is its
content hash, so there is nothing to absorb.

---

## Step 5 — The rollback (defects 2 + 3), per verb

Each transaction becomes:

```bash
_attach_rm_txn() {
    txn_begin "ait attach rm"
    ...resolve...
    txn_require_clean "ait attach rm" "$task_file"
    txn_require_clean "ait attach rm" "$meta_rel"
    txn_snap_add "$task_file"
    txn_snap_add "$meta_rel"
    ...mutations...
    if ! _attach_commit ...; then
        txn_rollback
        die "ait attach rm: commit failed — rolled back"
    fi
    txn_end
    success ...
}
```

The existing inline `task_git reset` + `task_git checkout -- <path>` pairs are
**deleted** — that is the HEAD restore which is defect 2. What replaces them is
`txn_snap_restore`, which puts back pre-transaction bytes *and* index entries.

**Blob paths keep HEAD restore**, per the task: content-addressed, and
snapshotting would copy up to 25 MB per blob with `gc` sweeping many. Each verb
registers its existing blob logic as the rollback hook via `txn_on_rollback`:

| verb | hook (unchanged logic, moved) |
|---|---|
| `attach add` | `task_git reset -- <blob_rel>` + `artifact_backend_delete` when `blob_pre == false` |
| `attach rm` | none |
| `attach gc` | `task_git reset`/`checkout --` over the swept blob relpaths (restores the deleted blobs from HEAD) |
| `decref-deleted` | none |
| `artifact create` | reset + `artifact_backend_delete` when `blob_pre == false`; the manifest delete moves into the snapshot's "absent pre-transaction" handling |
| `artifact update` | `artifact_backend_delete` when `blob_pre == false` — **the `&& backend == local` gate is dropped**, see below |

Every hook reports its own failures with `txn_rollback_failed` instead of
`|| true`, so they reach the same partial-rollback report as the snapshot half
(Step 1, "The restore-failure contract"). The `gc` and `artifact rm` hooks are
the ones that matter most: they restore blobs the transaction *deleted*.
| `artifact move` | `artifact_backend_delete` over `new_hashes` |
| `artifact rm` | reset + checkout over the swept blob relpaths |

### Fix `artifact update`'s backend-gated blob delete (a bug the hooks inherit)

`_artifact_update_txn` is the odd one out among the three artifact rollbacks, and
copying it verbatim into a hook would carry the bug forward:

```
aitask_artifact.sh:385   if [[ "$blob_pre" == false && "$backend" == "local" ]]; then   # update
aitask_artifact.sh:317   if [[ "$blob_pre" == false ]]; then                            # create
aitask_artifact.sh:479   for nh in "${new_hashes[@]}"; do                               # move
```

`create` and `move` delete a blob **this transaction created** on *any* backend;
`update` deletes only on `local`. So on a `dir` (or any future) backend,
`artifact_store` puts a new version blob, `artifact_manifest set-current` then
fails, the manifest snapshot restores — and the blob stays. Nothing references
it, `attach gc` only sweeps local blobs, and `ait artifact update` prints
"rolled back". That is a false claim and it breaks the task's invariant.

**Drop the `&& "$backend" == "local"` from the delete condition** (keep the
`task_git reset` local-gated — only local blobs are ever staged). This makes all
three rollbacks state the same rule: *unstage what was staged, delete what this
transaction created, on whatever backend it created it.*

Verified by the Step 6c pin "artifact update on a **dir** backend, faulted at
`set-current`" — the backend store must be byte-identical to its pre-command
state, which no existing test asserts.

**Hooks read file-scope globals, never enclosing locals.** A trap-invoked
function must not depend on the dying frame's `local`s, so each transaction
assigns the state its hook needs (`_ATTACH_TXN_BLOB_REL`, `_ATTACH_TXN_BLOB_PRE`,
`_ATTACH_TXN_HASH`, `_ATTACH_TXN_BLOB_PATHS=()`, and the artifact equivalents) at
the point it becomes known. This mirrors how `_fold_rollback` reads the global
`_fold_snap_paths` rather than a caller local.

`_artifact_rm_txn`'s existing mid-transaction rollback (the
`referenced-hashes` scan failure, `aitask_artifact.sh:571-583`) collapses into
`txn_rollback` + `die` like every other arm.

`_attach_rollback_add` and `_artifact_rollback_create` shrink to their blob
halves and are renamed to say so (`_attach_rollback_add_blobs` /
`_artifact_rollback_create_blobs`).

### Re-derive t1675's ALLOWLIST line numbers — a mandatory deliverable

`tests/test_attach_lock_callback_contract.sh:391-425` pins **seven
`<file>:<line>` sites** exempted from the static mutator-check, four of them the
deliberate `artifact_backend_delete … || true` inside the rollbacks this step
edits. The block's own comment states the design: *"it pins a LINE NUMBER, so it
silently stops matching if the file shifts. That is intentional — a stale entry
re-exposes its site to the guard."*

Every edit in Steps 4-5 shifts lines in both files, so **all seven entries must
be re-derived and their comments re-checked in the same commit**:

| entry | after this change |
|---|---|
| `aitask_attach.sh:315` (`_attach_rollback_add`) | new line in `_attach_rollback_add_blobs` |
| `aitask_artifact.sh:324` (`_artifact_rollback_create`) | new line in `_artifact_rollback_create_blobs` |
| `aitask_artifact.sh:386` (`_artifact_update_txn` commit-failure) | moves into the registered rollback hook |
| `aitask_artifact.sh:480` (`_artifact_move_txn` commit-failure) | moves into the registered rollback hook |
| `aitask_artifact.sh:163` (pipeline head) | line shift only |
| `aitask_attach.sh:576` (tail position) | line shift only |
| `aitask_artifact.sh:~571` (`if ! remaining=…`) | line shift; its comment cites `aitask_artifact.sh:580-584` restoring "from HEAD" — that becomes `txn_rollback`, so the comment must be corrected, not just renumbered |

`bash tests/test_attach_lock_callback_contract.sh` failing on Part B is the
signal that a number is stale; it is a required gate in Step 6e, not an
optional one.

One closure question to settle empirically rather than assume: the guard grows a
callback's closure to a fixpoint over **same-file functions named in an
in-closure body**. The hooks are now reached via `txn_on_rollback
_attach_rollback_add_blobs` — a bare-word argument, which should still name
them. Run the guard after the rename and confirm the hook bodies are still
scanned (a hook that falls *out* of the closure would make its allowlist entry
suppress nothing, silently un-testing the site). If it falls out, call the hook
directly from the commit-failure arm as well so the name stays in the body.
`lib/txn_snapshot.sh` itself is out of scope for the guard by design ("NOT
covered: a mutator reached through a function defined in ANOTHER file") and
calls no `MUTATORS` entry, so it needs no allowlist.

---

## Step 6 — Verification

### 6a. `tests/test_txn_snapshot.sh` (new, lib-level)

Drives the lib directly in a scratch git repo. Round-trip cases:

- a **staged** path comes back staged with the same blob (`ls-files --stage`
  compared before/after);
- an **unstaged-but-modified** path comes back with its bytes;
- a path with **no index entry** stays out (the `--force-remove` half);
- a **transaction-created** path is deleted on restore;
- an **unreadable index** fails closed rather than recording "absent" — force it
  by pointing `GIT_INDEX_FILE` at a garbage file (verified: `git ls-files
  --stage` then exits 128 with `fatal: … index file smaller than expected`) and
  assert `txn_snap_add` dies **and** that nothing was recorded;
- **restore-time failure is reported as failure** — snapshot cleanly, then break
  restore *after* capture (corrupt the index via `GIT_INDEX_FILE`, and separately
  `chmod a-w` the containing directory so the `cp` fails) and assert three
  things: `txn_snap_restore` returns non-zero; `_TXN_RESTORE_FAILED` names the
  offending path; and the snapshot directory still exists afterwards. Then drive
  it through `_txn_exit_trap` and assert the emitted text is the **partial**
  message naming the paths and the snapshot dir — *not* "rolled back every
  mutation". The message is part of the guard, so assert its wording, and assert
  the full-rollback phrase is **absent**;
- a **second `txn_snap_add` after mutation** is a no-op, so restore yields the
  pre-transaction bytes;
- both **ordering** cases: `txn_require_clean` → `txn_snap_add` still snapshots,
  and `txn_snap_add` → `txn_require_clean` still refuses an entry-dirty path
  (this is what proves the two dedup sets are independent);
- `txn_require_clean` accepts a non-existent path and a clean tracked path, and
  refuses each of the three dirt shapes (unstaged, staged, untracked).

- **a failed rollback *hook* is as loud as a failed snapshot restore** — register
  a hook that calls `txn_rollback_failed "blob … could not be deleted"`, let the
  snapshot half succeed, and assert `txn_rollback` still returns non-zero, the
  item appears in the report, and the full-rollback phrase is absent. This is the
  case that separates "restore verdict" from "rollback verdict"; without it a
  hook could fail silently while every other test passes.

Plus a **branch-mode** case, which is what pins the `_txn_fs_path` fix: build a
fixture with `.aitask-data/` as the data worktree and a path under
`attachments/` (deliberately *not* one of the two symlinked names), snapshot it,
mutate it, restore it, and assert the bytes come back. Today's fold code records
that path as "absent" and a restore would **delete** it, and no existing test
catches this — `tests/test_attach_fold_rebind.sh:3` states its fixture is
legacy-mode, and `test_fold_mark.sh` is legacy-mode too. Without this case the
promotion ships the same latent gap it inherited.

Uses `tests/lib/asserts.sh` (`assert_eq` / `assert_contains` /
`assert_exit_nonzero_rc` / `assert_file_exists`). Subshell-free bodies, so the
in-process counters are fine; no `assert_counters_init` needed.

### 6a-fold. End-to-end fold restore-failure pin

A lib-level test cannot prove the **fold wrappers** carry the verdict — they are
fold-local by design (Step 3). Add a case to `tests/test_fold_mark.sh`:

- run a fold that aborts before Step 6 (reuse the file's existing fault
  injection), with restore forced to fail on the primary task file — `chmod a-w`
  its containing directory after the snapshot is captured, so the `cp` back
  fails;
- assert stderr carries the **partial** message and names the primary, that the
  phrase `rolled back every mutation` is **absent**, and that the retained
  snapshot directory is named and still exists;
- **a prune-only failure**, in the same file: the prune half is the one a
  `|| rc=1` verdict silently drops, so it needs its own case rather than riding
  on the restore one. `_fold_prune_unsnapshotted_meta` only deletes meta files
  the transaction *created*, and the shipped ledger never creates one during a
  fold (the function is defensive — its own comment says so), so this is not
  reachable without help. Use the file's existing python injector idiom to add,
  right after `_fold_snapshot_meta_tree`, a line creating one meta file under a
  fresh shard and `chmod a-w` on that shard directory. The **real** prune code
  then runs, its **real** `rm -f` fails, and the case asserts the partial
  message names that meta file with its recovery instruction, the snapshot half
  reports nothing, and `rolled back every mutation` is absent. Say in the test's
  comment that the path is defensive and the injection is what makes it
  reachable — do not let it read as a production scenario;
- then a control in the same shape with neither half broken, asserting the full
  claim **is** printed and the directory is gone — a one-sided assertion here
  would pass against a build that never prints the full message at all.

Guard both on `[[ $(id -u) -ne 0 ]]`: root ignores the write bit, so under a
root test runner the `chmod` forcing silently does nothing and the pin would
pass vacuously. Skip with a visible message rather than reporting a pass.

### 6b. Dirty-worktree pins, success path (no fault injected)

New file `tests/test_attach_txn_worktree_isolation.sh`, fixture identical to
t1675's (legacy-mode git repo, `_ait_detect_data_worktree` → `.`).

**Must refuse** (non-zero, no success message, zero commits added, and the dirty
file byte-identical afterwards):

- `attach add` with a dirty task file — **unstaged**, and again **staged**;
- `attach rm` with dirty meta JSON;
- `artifact update` with a dirty manifest;
- `artifact move` with a dirty manifest;
- `artifact create` with a dirty task file;
- `artifact rm` with a dirty task file;
- `attach gc` with a dirty meta JSON on a sweep candidate.

**Must still succeed** (exit 0, success message, expected commit count, and the
dirty bystander still dirty and unchanged):

- `artifact update` with a dirty **task file** (manifest clean) — asserts the
  stable-handle split rather than assuming it;
- `artifact move` with a dirty **task file**;
- `attach decref-deleted` with two doomed tasks sharing one attachment — the
  dedup case: without the two-set design the second `txn_require_clean` would
  see the transaction's own first decref as dirt and refuse a valid operation;
- `ait fold` with attachments and its own dirty task files (drives
  `aitask_fold_mark.sh` end-to-end, proving the preflight is at the verbs and
  not in the seam).

### 6c. Dirty-worktree pins, abort path (fault injected)

Same file. Each asserts non-zero exit, no success message, zero commits added,
**and** every transaction path byte-identical to its pre-command state (bytes
*and* `git status --porcelain` output, so a leftover index entry is caught).

- The recorded **defect-2** case: dirty task file + commit forced to fail via a
  `pre-commit` hook, **no python fault**. This fails on today's tree and is the
  regression proof.

**One post-mutation state pin per distinct rollback-hook shape — all eight verbs,
not just the four with snapshot-only rollbacks.** t1675's pins assert exit
status, absence of a success message, and commit count; none of them looks at
what is left on disk (its header says so explicitly). So a hook that deletes the
wrong thing — or nothing — passes today's suite. Each pin below additionally
asserts the **backend store and the worktree** are byte-identical to their
pre-command state.

| verb | fault (`AIT_FAULT_*`) | hook shape under test | extra state assertion |
|---|---|---|---|
| `attach add` | `frontmatter_patch.py append` | local blob delete + unstage | the new blob is gone from `attachments/blobs/<shard>`; the meta JSON is gone; the task file byte-identical |
| `attach rm` | `frontmatter_patch.py remove` | snapshot only (no blobs) | meta JSON and task file byte-identical (the decref is undone) |
| `attach gc` | `attachment_meta.py refs`, **NTH=2**, two orphaned blobs | **destructive**: restore deleted blobs + metas from HEAD | candidate 1 — already swept when the fault lands — has **both** its blob and its meta JSON back, byte-identical, and `git status --porcelain` is clean |
| `decref-deleted` | `attachment_meta.py decref`, **NTH=2** | snapshot only | every touched meta JSON byte-identical |
| `artifact create` | `frontmatter_patch.py append` | blob delete (any backend) + manifest absent-restore | blob gone, manifest file gone, task file byte-identical |
| `artifact update` (**dir backend**) | `artifact_manifest.py set-current` | blob delete on a **non-local** backend | the new version blob is gone **from the dir store**, manifest byte-identical — this is the pin that catches the dropped `&& backend == local` gate |
| `artifact move` (dir → local) | `artifact_manifest.py set-backend` | `new_hashes` loop delete on the target | every blob this move created on the target is gone; blobs that pre-existed there remain; manifest still names the source backend |
| `artifact rm` | `artifact_manifest.py referenced-hashes` | swept-blob HEAD restore | manifest and task file byte-identical; no blob deleted |

**Plus one forced hook-failure pin**, since every row above exercises a hook that
*succeeds*. Take the `attach gc` case — the destructive one — and additionally
make its blob restore fail (`chmod a-w` the blob's shard directory after the
sweep, before the fault lands). Assert: non-zero exit; the **partial**-rollback
report; the blob named in it with its `git checkout HEAD -- <path>` recovery
hint; and that `rolled back every mutation` does **not** appear. Same
`[[ $(id -u) -ne 0 ]]` guard as 6a-fold — root defeats the `chmod`.

The `gc` and `move` rows are the two that need an occurrence index or a
multi-item fixture to reach the hook at all: a fault on the *first* item aborts
before any deletion, so the hook's non-trivial restore path is never entered and
the pin passes vacuously. `move` is pinned **dir → local** for the reason t1675
records at A11 — the other direction stages no blob paths, so the commit would
fail on its own and the pin would stop discriminating.

`artifact create`'s pin also removes the need for t1675's `rm -f
artifacts/manifests/t5-report.json` fixture-hygiene line (see 6e (ii)).

Fault injection reuses **t1675's shim verbatim** — the documented `AIT_PYTHON`
override (`python_resolve.sh` rung 1) with a passthrough shim that fails a named
script + subcommand on its Nth call. Copy the `SHIM` / `run_faulted` /
`run_clean` block from `tests/test_attach_lock_callback_contract.sh:45-90`; the
occurrence index is what lets a fault land *after* earlier mutations in a loop,
which is the only way to reach a rollback hook's non-trivial restore path.

### 6d. Pre-fix control, per pin (mandatory)

Every pin in 6b and 6c is run a second time against a **scratchpad copy of the
unfixed scripts** and must fail there. A pin that passes both ways proves
nothing.

Shape: copy the repo's `.aitask-scripts/` into
`$TMP/prefix/.aitask-scripts/`, restore `aitask_attach.sh` /
`aitask_artifact.sh` / `aitask_fold_mark.sh` from `git show HEAD~:<path>` (the
pre-fix revision), and re-run each pin against that tree in its own fixture
repo.

**Both headline defects were re-reproduced on today's tree while writing this
plan**, so the two controls below are known-executable rather than assumed:

```
# defect 1 — dirty task file, successful add
add exit=0 ;  commit "ait: Attach a.bin to t5" touches aitasks/t5_demo.md
git show HEAD:aitasks/t5_demo.md | grep -c 'USER EDIT IN FLIGHT'  ->  1   # absorbed

# defect 2 — dirty task file, commit forced to fail by a pre-commit hook
before: 1 ;  "Error: ait attach rm: commit failed — rolled back" ; rm exit=1
after : 0                                                             # destroyed
```

**The trap this guards against is systematic here:** several transactions stage
a path the failed mutator was supposed to create, so pre-fix `git add` fails on
its own and the run *appears* correct for the wrong reason. The control must
therefore assert the **specific** pre-fix symptom (the absorbed line present in
HEAD / the destroyed line absent from the worktree), not merely a non-zero exit
— exactly the discrimination t1675's A3 comment records.

### 6e. Two fixtures that break, and one that is a free integration check

A blast-radius sweep of every in-tree caller found exactly three places affected.

**(i) `tests/test_trail_gather.py:2386` — a real break, fix it.**
`test_positive_handle_resolution_mandatory` calls `aitask_artifact.sh create 100
<trail> --kind implementation_trail` after `self.repo.write_task("100", "root")`
(line 2382) — and the fixture's `_git_init` (lines 72-92) commits only
`README.md`, so `aitasks/t100_root.md` is **untracked**. `create` stages the task
file, so it refuses and the `returncode == 0` assertion at 2391 fails. Add a
`git add` + `git commit` of the task file to the fixture before the create.

**(ii) `tests/test_attach_lock_callback_contract.sh:169` and `:309` — expected to
stay green *because of* this change, and that is the integration check.**
Read against the preflight alone they would refuse: pin A1 leaves
`attachments/meta/<shard(a.bin)>.json` untracked (the `incref` landed, the
`frontmatter_patch.py append` faulted, nothing rolls it back), and pin A7 leaves
`meta(b.bin)` modified — precisely defect 3. But the preflight and the rollback
land **together**, so each aborted pin now restores its own paths and the drift
never reaches the next verb.

That makes these two lines a free end-to-end assertion: **if they refuse, the
rollback is not firing on the `die` path.** Do not "fix" them with hygiene lines
— diagnose the trap chain instead. The same reasoning is why line 245's
`rm -f artifacts/manifests/t5-report.json` hygiene line should become
unnecessary; removing it is the cleanest positive proof the rollback works, and
its own comment already says it exists only because "t1675 stops the false
success, not the drift".

**(iii) `.aitask-scripts/board/aitask_board.py` — safe, ordering verified.**
`_do_delete` calls `_decref_doomed_attachments` as its **first** action
(`:13800-13806`), before `_unfold_deleted_primary_children`'s
`aitask_update.sh` writes and before the `git rm`. And `decref-deleted` stages
nothing but meta JSONs (`aitask_attach.sh:508-513`), so no task-file dirt can
reach it.

Everything else under `tests/` is safe: the attach/artifact fixtures all
`git add -A; git commit` at init and commit each hand-patched task file before
the next verb. One constraint to respect while editing:
`tests/lib/docs_vocabulary_scan.py:184-188` asserts the set of
`frontmatter_patch.py` callers is exactly `{aitask_artifact.sh, aitask_attach.sh,
aitask_fold_mark.sh}` — `lib/txn_snapshot.sh` must not call it (it does not).

### 6f. Regression net

```bash
bash tests/test_fold_mark.sh                        # required — real-entry-point proof
bash tests/test_attach_lock_callback_contract.sh    # t1675's contract
bash tests/test_attach_local_backend.sh             # incl. section G (unrelated staged file)
bash tests/test_attach_meta.sh
bash tests/test_attach_archive_gc.sh
bash tests/test_attach_gc_manifest_blocking.sh
bash tests/test_attach_task_delete_decref.sh
bash tests/test_attach_fold_rebind.sh
bash tests/test_attachment_meta_lib.sh
bash tests/test_artifact_cli.sh
bash tests/test_artifact_dir_backend.sh
bash tests/test_artifact_fold_transfer.sh
bash tests/test_artifact_share_resolution.sh
bash tests/test_artifact_manifest_lib.sh
bash tests/test_txn_snapshot.sh                     # new
bash tests/test_attach_txn_worktree_isolation.sh    # new
bash tests/run_all_python_tests.sh --test-dir tests # for test_trail_gather.py

shellcheck .aitask-scripts/aitask_attach.sh .aitask-scripts/aitask_artifact.sh \
           .aitask-scripts/aitask_fold_mark.sh .aitask-scripts/lib/txn_snapshot.sh
```

`test_attach_local_backend.sh` section G stages an *unrelated* file
(`unrelated.txt`), outside the transaction's paths — it must still pass, and it
is the proof the preflight is scoped to the transaction rather than to the
worktree.

---

## Step 7 — Documentation and the accepted behaviour change

### The refusal is reachable in normal use — measured, not hypothetical

`./.aitask-scripts/aitask_update.sh --batch <id> --status …` **writes the task
file and does not commit it** (verified in a scratch repo: ` M
aitasks/t5_demo.md` after the call; the t1677 commit-owner is the *caller*, e.g.
`aitask_pick_own.sh`, not `--batch` itself). So a task file is routinely dirty
mid-session, and after this change `ait attach add` / `ait artifact create` /
`ait artifact rm` on that task will **refuse**.

That is the intended fix — absorbing the edit is the defect — but it must be
handled honestly:

- The refusal message names the path and the remedy, which is the whole reason
  `txn_require_clean` takes a `<label>` and interpolates the path.
- The concrete in-tree caller is the **`aitask-trail` skill**, whose create flow
  runs `aitask_artifact.sh create <owner_id> <tmpfile>` and stages the owner's
  task file. Its step 4 already ends with "Any other failure → surface and stop",
  so the refusal is surfaced with an actionable message and nothing is corrupted.
  **No skill edit in this task**: changing it would mean touching the Claude
  Code source plus every rendered per-profile and per-agent variant, which is a
  separate change under this repo's skill-authoring rules. Note it in the task's
  Final Implementation Notes so a follow-up can add the specific bullet if the
  generic arm proves too vague in practice.
- The four in-tree test flows that run `aitask_update.sh --batch` before a verb
  (`test_attach_archive_gc.sh:74`, `test_attach_task_delete_decref.sh:186`,
  `test_attach_fold_rebind.sh:105-107`) all reach `gc` / `decref-deleted` /
  `fold`, none of which checks a task file — so they are **safe**, but re-confirm
  that when Step 6e runs rather than trusting this note.

### Doc surfaces

- Update `lib/attachment_lock.sh`'s closing "NOT COVERED HERE — see t1698" note
  to point at the new lib and state the invariant that now holds.
- Update `tests/test_attach_lock_callback_contract.sh`'s header note (it says
  the residual state is "not asserted here, deliberately … belongs to t1698")
  to name where it *is* asserted now, and drop the `rm -f
  artifacts/manifests/t5-report.json` fixture-hygiene line if the rollback makes
  it unnecessary.
- `aidocs/task_attachments_design.md` and `aidocs/unified_artifact_design.md`:
  record the transaction-boundary invariant beside their existing
  transaction/lock sections, and name the refusal as user-visible behaviour.
- Add the `show_help` text in `aitask_attach.sh` / `aitask_artifact.sh` a one-line
  note that these verbs refuse on a dirty path they would stage — that help text
  is the only user-facing surface these verbs actually have.

**Website: two one-line additions, no new page.** There is no `ait attach` /
`ait artifact` command page —
`website/content/docs/commands/task-management.md` contains no attach/artifact
content at all. The two rows that *do* name the verbs as writers become
incomplete without a clause, so add one to each:

- `website/content/docs/development/task-format.md:56-57` — the `artifacts` /
  `attachments` rows ("Written by `ait artifact create` / `rm`", "Written by
  `ait attach add` / `rm`"): note that those verbs refuse when the task file has
  uncommitted changes.
- `website/content/docs/skills/aitask-trail.md:85` — trail create writes the
  owner task file, so the same precondition applies.

Run `python3 check_links.py --build` in `website/` after both edits. Leave the
two release-note blog posts alone (historical).

---

## Step 9 — Post-Implementation

Standard: commit on the current branch (profile `fast`, `create_worktree:
false`), then archive t1698 and its plan per `task-workflow` Step 9. The
`risk_evaluated` gate is active for this task.

---

## Risk

### Code-health risk: medium
- The preflight changes user-visible behaviour on eight verb paths at once; a
  path checked that the verb does not actually stage would refuse a valid
  operation (`artifact update`/`move` vs. task files, `artifact rm`'s
  non-last-reference branches are the sharp cases) · severity: medium · →
  mitigation: the Step 6b "must still succeed" pins assert each narrowing
  directly instead of assuming it
- `aitask_update.sh --batch` leaves the task file dirty (measured), so the
  preflight will refuse real, previously-working invocations mid-session — most
  visibly the `aitask-trail` create flow · severity: medium · → mitigation:
  trail_skill_dirty_owner_refusal_note
- Promoting the fold facility touches `aitask_fold_mark.sh`, a load-bearing
  transactional path, and `tests/test_fold_mark.sh`'s pre-fix injectors patch it
  by name — a stale injector silently stops being a negative control ·
  severity: medium · → mitigation: injector update is in the same commit and
  `test_fold_mark.sh` is a required regression gate
- The EXIT-trap chain must interleave correctly with `registry_lock`'s own trap
  (which overwrites on acquire and clears on release); a bare `trap … EXIT`
  would leak the global attach lock · severity: high · → mitigation: inline
  pre-phase pin_attach_lock_not_leaked_on_abort

- Every restore action in the tree is fail-quiet — `txn_snap_restore`'s writes,
  the verb blob hooks' `artifact_backend_delete` / `task_git reset` /
  `task_git checkout`, and fold's prune — so a partial rollback can be announced
  as a complete one and the snapshot (the only copy of the pre-transaction bytes)
  deleted underneath it. `attach gc` is the worst case: a blob it deleted stays
  gone · severity: high · → mitigation: inline pre-phase
  fail_loud_restore_contract
- The recorder returns 0 by design (so one failure does not skip the remaining
  restores), which makes every `|| rc=1` verdict a silent no-op — measured: a
  prune-only failure returns rc=0 with one item recorded · severity: high · →
  mitigation: inline pre-phase fail_loud_restore_contract (one derived
  `txn_rollback_ok`, no plumbed statuses anywhere)
- `artifact update` gated its new-blob delete on `backend == local` while
  `create` and `move` do not, so a non-local abort leaks the blob it created ·
  severity: medium · → mitigation: the gate is dropped in Step 5 and pinned by
  the Step 6c dir-backend `set-current` fault
- Four of the eight rollback hooks (`attach add`, `attach gc`, `artifact
  update`, `artifact move`) had no on-disk state assertion, so a hook that
  restores the wrong thing would pass the suite · severity: high · → mitigation:
  Step 6c now carries one post-mutation state pin per hook shape, with the
  occurrence-index fixtures needed to reach the non-trivial restore paths

### Goal-achievement risk: low
- The pre-fix control could pass for the wrong reason — several transactions
  stage a path the failed mutator was to create, so pre-fix `git add` fails on
  its own · severity: medium · → mitigation: Step 6d requires each control to
  assert the specific pre-fix symptom, not merely a non-zero exit
- Defect 3's "every abort path" is reached via the EXIT trap rather than by
  instrumenting each `die`; a `die` that fires before `txn_begin` would not roll
  back · severity: low · → mitigation: `txn_begin` is the first statement of
  every callback, and everything before it is a pure refusal (`die` with no
  mutation)

### Planned mitigations
- timing: pre-phase | name: fail_loud_restore_contract | type: bug | priority: high | effort: medium | inline_risk: low | added_complexity: medium | addresses: code-health — every restore action in the tree is fail-quiet (txn_snap_restore's writes under suppressed errexit, the verb blob hooks' `|| true`, fold's prune), and the fold wrappers it is promoted from then claim a full rollback unconditionally at four call sites | desc: add txn_rollback_failed as the single reporting seam and route the snapshot half, every verb blob hook and fold's prune through it; derive EVERY verdict from the recorded set through a single txn_rollback_ok (never `|| rc=1`, a silent no-op against a recorder that returns 0 — measured) and give txn_snap_restore a delta-derived status; split _txn_exit_trap and all four fold call sites into a full-rollback and a partial-rollback message that lists each un-restored item with its own recovery instruction; preserve the snapshot directory when the snapshot half is incomplete (including replacing fold's bare rm -rf with txn_snap_cleanup); pin with a restore-time fault case and a forced hook-failure case in tests/test_txn_snapshot.sh, a forced gc blob-restore failure in the verb suite, and end-to-end fold cases for a failed restore AND a failed prune with a positive control in tests/test_fold_mark.sh
- timing: pre-phase | name: pin_attach_lock_not_leaked_on_abort | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the rollback's EXIT trap must chain onto registry_lock's, which overwrites on acquire and clears on release | desc: characterization test pinning that attachments/.attach.lock is absent after a faulted attach add / artifact create, written before the change so it captures today's correct behaviour and fails loudly if the trap chain leaks the lock
- timing: after | name: trail_skill_dirty_owner_refusal_note | type: documentation | priority: medium | effort: medium | inline_risk: low | added_complexity: high | addresses: code-health — aitask_update.sh --batch leaves task files dirty, so ait artifact create <owner> now refuses mid-session and the aitask-trail create flow only reports it through a generic "surface and stop" arm | desc: document the clean-owner-file precondition and its remedy in .claude/skills/aitask-trail/SKILL.md.j2 next to the existing "handle already exists" guidance, regenerate every rendered variant and the goldens under tests/golden/skills/aitask-trail/, and spawn the companion Codex / OpenCode port tasks
