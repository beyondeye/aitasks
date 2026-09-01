---
Task: t1668_make_fold_mark_pre_step6_abort_transactional.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1668 — Make the fold-mark pre-Step-6 abort transactional

## Context

`.aitask-scripts/aitask_fold_mark.sh` mutates task files in Steps 3–5b and only
assembles `rollback_paths` **after** Step 5b. Any abort before Step 6 therefore
leaves the fold's mutations on disk, dirty and uncommitted, with no rollback:

```bash
# fixture with t10 present, t9999 absent
aitask_fold_mark.sh --commit-mode fresh 10 9999
# -> exit 1, "No task file found for task number 9999"
# -> aitasks/t10_primary.md now carries folded_tasks: [9999], dirty
```

Two consequences: the dirty task file is exactly what the next unscoped commit
sweeps up (the failure class t1599_2 exists to prevent), and under t1661's
output contract the run emits **no records**, so stdout gives a consumer no
signal that anything landed. t1661 scoped its guarantee to Step 6 and documented
this gap ("WHAT THIS DOES NOT BUY"); documenting a gap is not closing it.

Outcome: the whole run becomes one transaction. Every abort from the first
mutation through Step 6 restores the repository — **index and working tree** —
to exactly the state it was in before the fold started.

## Design decisions

**Restore from a pre-mutation snapshot, not from HEAD.** The existing
`_fold_rollback` does `task_git checkout -- <paths>`, which restores HEAD
content. Firing that on pre-Step-6 aborts would *introduce* a data-loss path:
the documented ad-hoc fold flow (`task-workflow/planning.md` §6.1) runs

```bash
aitask_fold_content.sh … | aitask_update.sh --batch <primary> --desc-file -
aitask_fold_mark.sh --commit-mode fresh <primary> <folded…>
```

so the primary is **already dirty** with the merged description when
`fold_mark` runs; a HEAD-restore on abort would throw that merge away.

**Snapshot the index too — all stages — and drop the blanket `reset`.**
`_fold_rollback` currently opens with `task_git reset -q -- "${rollback_paths[@]}"`.
Verified: `aitask_update.sh` stages only under `--commit`
(`aitask_update.sh:2262`), which `fold_mark` never passes — so Steps 3–5b stage
**nothing**, and that reset can only ever discard the *user's* pre-existing
staged state. It is replaced by an exact per-path index snapshot/restore that
round-trips `git ls-files --stage` output through `git update-index
--index-info`, which is the format designed to be fed back. That matters beyond
the ordinary case: a path in an **unresolved merge** has three index entries
(stages 1/2/3), and this repo's task data is rebased by `ait syncer`, so a
conflicted `aitasks/` path is a live possibility. Parsing a single `mode,sha`
out of that and writing one stage-0 entry would silently resolve the user's
conflict; feeding the captured lines back preserves every stage verbatim.

**Snapshot the whole attachment-meta tree, not a predicted subset.**
`cmd_rebind` (`lib/attachment_meta.py:186`) walks *every* meta file and rewrites
each one whose `refs` contain the folded id. That set is a property of the
**ledger**, not of the task's `attachments:` frontmatter, so predicting it from
`attach_task_hashes` can miss a drifted ref — and HEAD-restoring a meta file
would discard any pre-fold uncommitted metadata edit. So the fold snapshots the
whole `attachments/meta` tree (files + index entries + the file list, so a file
created during the transaction can be removed again) as the first action
*inside* the attach lock. This runs only on the attachment path; the common bare
fold never touches it.

**Make the attachment transaction actually fail.** `with_attach_lock` invokes
its callback as `"$@" || rc=$?`, which disables errexit for the whole callback —
verified empirically. `_fold_merge_one` then runs `seen_hashes[$h]=1` *after*
the `frontmatter_patch.py append`, so a failed append is overwritten by a
successful assignment and `with_attach_lock` returns **0**: today the fold can
commit partial attachment state. `attach_meta rebind` is worse — it runs in a
process substitution, whose status is not observable at all. Every mutating
attachment operation must propagate its own failure explicitly.

**Chain the EXIT trap through the attach lock.** `registry_lock_acquire`
installs its **own** `trap … EXIT` and `registry_lock_release` does
`trap - EXIT`, silently stripping the fold's handler. `lib/stale_lock.sh`
already states the rule ("chain handlers rather than clearing them").
`_fold_attach_txn` prepends the fold rollback to whatever handler is installed
at that moment; the plain handler is re-armed after `with_attach_lock` returns.
Verified on this bash: `trap -p EXIT` inside `$( )` reports the parent handler.

## Files

- `.aitask-scripts/aitask_fold_mark.sh` — the fix.
- `tests/test_fold_mark.sh` — rework one pinned test, add six, add a negative
  control, retarget one fragile anchor.
- `.claude/skills/task-workflow/task-fold-marking.md` — the reference doc the
  script header says it mirrors; its "What this does not buy" paragraph
  describes the gap being closed.

---

### Pre-phase (risk mitigations)

1. `[pin_dirty_entry_rollback]` In `tests/test_fold_mark.sh`, **before** touching
   `aitask_fold_mark.sh`, add `test_step6_rollback_preserves_dirty_entry`: set up
   `t10_primary.md` + `t20_a.md`, commit, then append a `PRE-FOLD EDIT` marker
   line to `aitasks/t10_primary.md` **after** the commit (standing in for
   `aitask_fold_content.sh`'s description merge). Install the failing pre-commit
   hook and run `--commit-mode fresh 10 20`. Assert: exit non-zero,
   `folded_tasks` empty (the fold was undone) **and** the `PRE-FOLD EDIT` marker
   is still present. Run it against the unmodified script and record that it
   FAILS on the marker assertion — that failure is the proof the snapshot switch
   is a real semantics change, not a no-op. Only then proceed to Step 1.

## Step 1 — Validate `--commit-mode` at argument-parse time

In `aitask_fold_mark.sh`, right after the existing
`[[ ${#folded_ids[@]} -eq 0 ]] && die "need at least one folded id"` and
**before** `primary_id="${primary_id#t}"` / `resolve_file_by_id`:

```bash
# Validated here, before anything is resolved or mutated: reaching Step 6 with
# a bad mode would mean rolling back a transaction that never needed to start.
case "$commit_mode" in
    fresh|amend|none) ;;
    *) die "invalid --commit-mode: '$commit_mode' (expected fresh, amend, or none)" ;;
esac
```

Keep Step 6's `*)` arm as an unreachable internal guard, reword its message to
`die "internal: unvalidated --commit-mode: $commit_mode"`, and replace its stale
comment ("Validated only here, after Steps 3-5b already wrote every mutation…").

## Step 2 — Hoist the fold's file set above the first mutation

Move the path-set assembly (currently just after Step 5b) to sit **immediately
before** the Step 3 `aitask_update.sh --batch "$primary_id"` call, i.e. after the
`plan_approved_at` no-union comment. Everything it needs is already resolved
there: `primary_file`, `folded_files`, `transitive_files`, and the parent file of
each `<parent>_<child>` folded id. Drop only its trailing `fold_meta_relpaths`
loop — those paths do not exist yet.

**Rename `rollback_paths` → `fold_paths`** at all sites (assembly, both Step 6
arms, `_fold_amend_guard`'s `own_paths`, the "empty fold path set" guard). After
this change it no longer defines what rollback restores — it is the fold's own
file set: what Step 6 stages/commits and what the amend guard treats as owned.
The restore set is the snapshot registry below. Keep the existing comments'
meaning, updating the names.

## Step 3 — Snapshot registry: exact index + worktree restore

New block immediately before the first mutation (delimited so the negative
control can excise it):

```bash
# --- fold transaction (t1668) ------------------------------------------------
# The rollback restores the exact PRE-FOLD state of every path it snapshots:
# both the working-tree bytes and the index entry. It is not a HEAD restore --
# the fold's own primary is routinely dirty on entry (aitask_fold_content.sh
# merges the description immediately before this script runs) and the caller
# may have staged it, and neither may be discarded by an aborted fold.
_fold_snap_dir=""
_fold_snap_paths=()          # index i -> repo path
_fold_txn_active=false

# _fold_snap_add <path> -- record one path's pre-mutation state. Absence is
# represented explicitly (no .blob file) so restore can delete a path the
# transaction created.
_fold_snap_add() {
    local p="$1" i="${#_fold_snap_paths[@]}"
    [[ -n "${_fold_snap_dir:-}" ]] || die "internal: snapshot dir not created"
    if [[ -f "$p" ]]; then
        cp -- "$p" "$_fold_snap_dir/$i.blob" || die "fold: could not snapshot $p"
    fi
    # Empty when the path is not in the index; ONE line per index entry
    # ("<mode> <sha> <stage>\t<path>") -- three of them for an unmerged path.
    # Captured verbatim so `update-index --index-info` can replay every stage.
    task_git ls-files --stage -- "$p" > "$_fold_snap_dir/$i.idx" 2>/dev/null || : > "$_fold_snap_dir/$i.idx"
    _fold_snap_paths[$i]="$p"
}

_fold_snap_init() {
    _fold_snap_dir="$(mktemp -d "${TMPDIR:-/tmp}/ait_fold_snap_XXXXXX")"
}

# _fold_restore_snapshots -- put every snapshotted path back, index and worktree.
#
# The index half always REMOVES the current entry first (--force-remove drops
# every stage of a path, conflicted or not) and then replays the captured
# lines through --index-info. That is what makes an unmerged path round-trip:
# all three stages come back exactly as they were, and a path that had no entry
# at all stays out of the index.
_fold_restore_snapshots() {
    local i p
    for i in ${!_fold_snap_paths[@]+"${!_fold_snap_paths[@]}"}; do
        p="${_fold_snap_paths[$i]}"
        if [[ -f "$_fold_snap_dir/$i.blob" ]]; then
            cp -- "$_fold_snap_dir/$i.blob" "$p" 2>/dev/null \
                || warn "fold rollback: could not restore $p"
        else
            rm -f -- "$p" 2>/dev/null || true      # did not exist pre-fold
        fi
        task_git update-index --force-remove -- "$p" >/dev/null 2>&1 || true
        if [[ -s "$_fold_snap_dir/$i.idx" ]]; then
            task_git update-index --index-info < "$_fold_snap_dir/$i.idx" >/dev/null 2>&1 \
                || warn "fold rollback: could not restore the index entry for $p"
        fi
    done
    task_git update-index -q --refresh >/dev/null 2>&1 || true
}
```

`_fold_rollback` (moved up from below Step 5b — it must be defined before the
trap can fire) becomes:

```bash
_fold_rollback() {
    _fold_txn_active=false
    _fold_restore_snapshots
    _fold_prune_unsnapshotted_meta      # no-op unless Step 5b ran
}
```

`_fold_prune_unsnapshotted_meta` removes any file under `attachments/meta`
that was not in the pre-transaction listing (see Step 5). It is a no-op when the
meta tree was never snapshotted.

Then, still before the first mutation:

```bash
_fold_abort_cleanup() {
    local rc=$?
    if [[ "$_fold_txn_active" == true ]]; then
        _fold_rollback
        warn "fold aborted before the commit step (exit ${rc}) — rolled back every mutation; nothing was committed"
    fi
    if [[ -n "$_fold_snap_dir" && -d "$_fold_snap_dir" ]]; then
        rm -rf "$_fold_snap_dir"
    fi
    return 0
}

_fold_snap_init
for _p in "${fold_paths[@]}"; do _fold_snap_add "$_p"; done
trap '_fold_abort_cleanup' EXIT
_fold_txn_active=true
# --- end fold transaction ----------------------------------------------------
```

A `die` inside `_fold_snap_add` runs *before* the arm, so it rolls nothing
back — correct, nothing is mutated yet. `_fold_abort_cleanup` uses only `if`
blocks and `|| true`-guarded commands and never calls `exit`, so the script's own
status survives.

Disarm on success by adding `_fold_txn_active=false` on the line **after** Step
6's closing `esac` — all three failure arms `die` inside the case, so only a
terminal success reaches it. `_fold_rollback` disarms itself, so the three
explicit Step-6 rollback sites stay as they are and the trap does not
double-fire. Delete the now-dead `task_git reset` / `task_git checkout` bodies.

## Step 4 — Keep the trap alive across the attach lock

At the top of `_fold_attach_txn` (which runs *inside* `with_attach_lock`, after
`registry_lock_acquire` installed its own EXIT handler):

```bash
_fold_attach_txn() {
    # registry_lock_acquire has just installed its lock-release EXIT handler
    # OVER ours (and registry_lock_release clears EXIT outright). Chain rather
    # than clear -- the rule lib/stale_lock.sh states -- so an abort inside this
    # transaction rolls the fold back AND releases the lock, in that order.
    #
    # NOTE: with_attach_lock runs us as `"$@" || rc=$?`, so errexit is DISABLED
    # for everything below. Every mutating call must check its own status.
    local _cur
    _cur="$(trap -p EXIT)"; _cur="${_cur#trap -- }"; _cur="${_cur% EXIT}"
    eval "trap '_fold_abort_cleanup; '$_cur EXIT"
    _fold_snapshot_meta_tree
    …
}
```

The call site needs an explicit failure branch, not a bare invocation.
`with_attach_lock` ends with `return "$rc"`, and `registry_lock_release` has
already run `trap - EXIT` by then — so a callback that *returns* non-zero
(rather than calling `die`) would trip top-level errexit **one line before** the
re-arm, and the Step-5b mutations would survive. Suppress errexit for the
wrapper, re-arm first, then fail:

```bash
    _fold_attach_rc=0
    with_attach_lock _fold_attach_txn || _fold_attach_rc=$?
    trap '_fold_abort_cleanup' EXIT   # registry_lock_release did `trap - EXIT`
    (( _fold_attach_rc == 0 )) \
        || die "fold: attachment transfer failed (exit ${_fold_attach_rc})"
```

(A `die` from inside `with_attach_lock` itself — the lock-busy path — happens
*before* `registry_lock_acquire` installs anything, so the fold's original trap
is still armed there and rolls back correctly.)

## Step 5 — Snapshot the meta tree, and make Step 5b failures real

`_fold_snapshot_meta_tree` — first action inside the lock, before any rebind:

```bash
_fold_snapshot_meta_tree() {
    local d p
    d="$(attach_meta_dir)"
    [[ -d "$d" ]] || return 0
    _fold_meta_root="$d"
    _fold_meta_pre=()                       # pre-transaction file listing
    while IFS= read -r p; do
        [[ -n "$p" ]] || continue
        _fold_meta_pre+=( "$p" )
        _fold_snap_add "attachments/meta/${p#"$d"/}"     # data-root-relative
    done < <(find "$d" -type f -name '*.json' | sort)
}
```

`_fold_snap_add` takes the data-root-relative form (the `task_git` contract) —
the same shape `attach_meta_relpath` produces, derived by stripping
`attach_meta_dir`'s prefix rather than introducing a second convention.
`_fold_prune_unsnapshotted_meta` then removes any `*.json` under
`_fold_meta_root` that is not in `_fold_meta_pre`.

Then make every mutating attachment operation propagate failure (errexit is off
in this callback):

- `_fold_merge_one` and `_fold_merge_one_artifact` — append
  `|| die "fold: attachment/artifact merge failed for <id>"` to the
  `frontmatter_patch.py append` call, **before** the `seen_*` assignments that
  currently overwrite its status.
- `_fold_rebind_refs` — replace the process substitution with a captured run so
  the status is observable:

  ```bash
  local out rc=0
  out="$(attach_meta rebind "$fid" "$primary_id")" || rc=$?
  (( rc == 0 )) || die "fold: attachment rebind failed for t${fid} (exit ${rc})"
  while IFS= read -r changed; do
      [[ -n "$changed" ]] || continue
      _m="$(attach_meta_relpath "$changed")"
      fold_meta_relpaths+=( "$_m" )
      fold_paths+=( "$_m" )
  done <<< "$out"
  ```

Final ordering of `fold_paths` at Step 6 is unchanged (primary, folded,
transitive, parents, metas), so `task_git_commit_scoped` and
`_fold_amend_guard`'s `own_paths` see exactly what they see today.

## Step 6 — Documentation

Both places currently document the gap and must now describe the guarantee:

- **Script header** — replace the `WHAT THIS DOES NOT BUY` paragraph: the whole
  run is one transaction; an abort at any point from the first mutation through
  Step 6 restores every mutated path's index entry and working-tree bytes to
  their pre-fold state and emits no records, so an empty record set now
  genuinely means "nothing landed". Keep the "exit status is authoritative"
  line and name the honest residual: a signal that bypasses the EXIT trap
  (`SIGKILL`, power loss) still leaves the mutations on disk. Note that the
  restore is *pre-fold state*, not HEAD, and why.
- **`.claude/skills/task-workflow/task-fold-marking.md`** — rewrite its final
  "**What this does not buy:**" paragraph the same way. (Static reference file,
  no `.j2` template, no per-profile renders or goldens — nothing to regenerate.)

## Step 7 — Tests (`tests/test_fold_mark.sh`)

**Rework** `test_abort_mid_mutation_emits_no_records` →
`test_abort_mid_mutation_rolls_back`. Same trigger (`fold_mark … 10 9999`), but
the residual assertions invert: `folded_tasks` empty, primary clean in the
worktree, HEAD unchanged, stderr still names `9999` and now also names the
rollback. Update the file's header comment block, which spells out the old
residual.

**Add eight tests:**

1. `test_abort_preserves_pre_existing_dirty_primary` — append a marker line to
   `t10_primary.md` after the setup commit (standing in for the description
   merge), abort on the missing id. The marker must still be present **and**
   `folded_tasks` empty. Discriminates snapshot-restore from HEAD-restore.
2. `test_abort_preserves_pre_existing_staged_primary` — same, but `git add` the
   marker first. Assert the index entry is restored, not dropped: `git status
   --porcelain -- aitasks/t10_primary.md` still reports a staged modification
   (`M `), `git diff --cached` still contains the marker, and `folded_tasks` is
   empty. Fails against a rollback that opens with a blanket `reset`.
3. `test_abort_rolls_back_child_and_parent` — `fold_mark … 10 30_1 9999`, so
   Step 4 mutates the child and its parent before dying. Assert `t30_1` is back
   to `status: Ready` with no `folded_into`, `t30_orig_parent.md` still lists
   `children_to_implement: [t30_1]`, and all three paths are clean.
4. `test_invalid_commit_mode_rejected` — `--commit-mode bogus 10 20`: exit
   non-zero, stderr names the mode, primary has no `folded_tasks` and is clean.
5. `test_invalid_commit_mode_precedes_resolution` — `--commit-mode bogus 9999
   8888`: stderr must name the commit mode and must **not** say "primary task
   file not found". The discriminating case for Step 1.
6. `test_attach_merge_failure_aborts_the_fold` — the precondition for the
   post-phase mitigation below: with the injected `frontmatter_patch.py` failure
   in place, assert the run **exits non-zero and stderr names the merge
   failure**. Without this the mitigation's rollback assertions could pass
   against a build that never reached the failure at all.
7. `test_abort_preserves_unmerged_index_stages` — synthesise a conflicted index
   entry for `aitasks/t10_primary.md` without a real merge:
   ```bash
   sha=$(git hash-object -w aitasks/t10_primary.md)
   printf '100644 %s 1\t%s\n100644 %s 2\t%s\n100644 %s 3\t%s\n' \
       "$sha" aitasks/t10_primary.md "$sha" aitasks/t10_primary.md \
       "$sha" aitasks/t10_primary.md | git update-index --index-info
   ```
   Capture `git ls-files --stage -- aitasks/t10_primary.md`, abort on the
   missing id, and assert the capture is byte-identical afterwards. A restore
   that parses one `mode,sha` and writes a stage-0 entry collapses the conflict
   and fails this. (`ait syncer` rebases task data, so this is a reachable
   state, not a synthetic-only one.)
8. `test_attach_txn_nonzero_return_rolls_back` — the wrapper-exit contract,
   distinct from the `die`-based injection in test 6. Add a source-level
   injector `install_attach_txn_returns_nonzero` (same shape as the other
   patchers) that replaces `_fold_attach_txn`'s body with `return 3`, so the
   callback **returns** non-zero instead of dying. Assert the run exits
   non-zero, stderr names `attachment transfer failed (exit 3)`, the fold rolled
   back, and `attachments/.attach.lock` is gone. Against a bare
   `with_attach_lock _fold_attach_txn` call site this fails: errexit fires
   before the re-arm and nothing rolls back.

**Add a negative control** `install_prefix_no_abort_rollback`, mirroring
`install_unbuffered_record_emission`: replace the delimited
`# --- fold transaction (t1668) ---` … `# --- end fold transaction ---` block
with a pre-fix stub that defines the same names as no-ops and installs no trap,
assert the injection landed (no `trap '_fold_abort_cleanup' EXIT` remains), then
re-run test 1's shape under `assert_defect_present` — the pre-fix build must
still show `folded_tasks: [9999]` on disk.

**Retarget one fragile anchor.** `install_prefix_commit_block` finds the end of
Step 6 via `s.index('die "invalid --commit-mode: $commit_mode"')`, a string Step
1 changes. Anchor on the block instead — the nested `case "$crc"` ends with an
indented `esac`, so only the top-level one matches at column 0:

```python
end = s.index('\nesac\n', s.index('# Step 6: commit')) + len('\nesac\n')
```

Register all new tests in the runner list at the bottom of the file.

### Post-phase (risk mitigations)

1. `[verify_attach_window_abort]` Add `test_abort_inside_attach_txn_rolls_back`,
   building on test 6's proven fault injection. Fixture: a folded task carrying
   an `attachments:` entry (so `_fold_any_attach_or_artifacts` is true and Step
   5b runs) with a real meta file under `attachments/meta`, plus a stub
   `lib/frontmatter_patch.py` in the fixture that exits non-zero on `append`.
   **Order matters:** first assert the injected failure reached the abort (exit
   non-zero, stderr names the merge failure — test 6), then assert all three
   halves: the fold rolled back (`t10_primary.md` has no `folded_tasks`, the
   folded task is still `Ready`, worktree clean), the **meta file's pre-fold
   uncommitted edit survives** (dirty it before the run and assert the dirty
   bytes, not HEAD content, are back), and the lock was released
   (`attachments/.attach.lock` does not exist). Each half fails against a
   different wrong build — a chain that replaced the lock handler, a chain that
   never ran, a meta restore that went to HEAD. If the fixture cannot reach Step
   5b at all, stop and report — an unreachable test is not coverage.
2. `[pin_control_excision_span]` Extend `install_prefix_commit_block`'s
   post-injection assertions (which already prove the pre-fix block landed) to
   pin the *span* that was removed: the rebuilt file must no longer define
   `_fold_amend_guard` (already checked) **and** must still define
   `_fold_abort_cleanup` and `_fold_snap_add` — i.e. the retargeted `\nesac\n`
   anchor cut the Step-6 block and nothing above it. A mis-anchored excision
   that swallowed the transaction block would otherwise leave all three t1599_2
   negative controls passing while proving nothing.

---

## Verification

```bash
# 0. Prove the index round-trip idiom on a throwaway repo BEFORE relying on it:
#    force-remove a conflicted path, replay the captured lines, and confirm all
#    three stages come back byte-identical.

# 1. The reworked + new cases, and the whole t1599_2 / t1661 suite.
bash tests/test_fold_mark.sh

# 2. Every other suite that drives aitask_fold_mark.sh.
for t in test_attach_fold_rebind test_artifact_fold_transfer \
         test_fold_file_refs_union test_verifies_field \
         test_fold_risk_mitigation_drop test_gate_frontmatter_roundtrip \
         test_auto_merge_file_ref; do
  echo "== $t"; bash "tests/$t.sh" || echo "FAILED: $t"
done

# 3. Lint.
shellcheck .aitask-scripts/aitask_fold_mark.sh
```

Manual end-to-end check of the primary-flow guarantee, in a scratch fixture
(never in this repo's worktree): dirty **and stage** the primary, run
`aitask_fold_mark.sh --commit-mode fresh <primary> <missing-id>`, and confirm
`git status --porcelain` reports exactly the pre-existing staged modification
and nothing else, and `git diff HEAD` shows no `folded_tasks:` line.

Step 9 (Post-Implementation) handles cleanup, archival, and merge.

---

## Risk

### Code-health risk: medium
- Snapshot-restore changes the semantics of the **existing** Step 6 rollback
  that t1599_2 and t1661 pinned; those suites assert only "no residue" against
  clean-on-entry fixtures, so a mistake in the restore loop can pass them while
  silently corrupting a dirty-on-entry fold · severity: low (residual — the
  dirty-on-entry case is pinned by inline pre-phase pin_dirty_entry_rollback,
  which is required to fail against the pre-change build) · → mitigation: inline pre-phase pin_dirty_entry_rollback
- The EXIT-trap chain composes the fold's handler with `registry_lock`'s
  lock-release handler. A wrong capture silently disables one of the two —
  either the fold never rolls back inside Step 5b, or the attach lock leaks —
  and neither failure is visible on the success path · severity: low (residual —
  both halves are asserted by inline post-phase verify_attach_window_abort) · → mitigation: inline post-phase verify_attach_window_abort
- Retargeting `install_prefix_commit_block`'s excision anchor is load-bearing
  for three t1599_2 negative controls; an anchor that matches the wrong span
  leaves those controls passing while proving nothing · severity: low (residual
  — the span's boundaries are pinned by inline post-phase
  pin_control_excision_span) · → mitigation: inline post-phase pin_control_excision_span
- Index restore via `update-index --force-remove` + `--index-info` reaches for a
  lower-level git plumbing surface than anything else in this script; a mistake
  there corrupts the index rather than failing loudly, and the destructive half
  (`--force-remove`) runs before the replay · severity: medium · → mitigation:
  none (bounded by test 2, which asserts the restored staged entry directly,
  test 7, which asserts an unmerged path's three stages round-trip byte-exactly,
  and the `warn`-on-failure branch)
- Two restore mechanisms now coexist (per-path snapshots for task files, a
  tree-wide snapshot for attachment meta). The asymmetry is real and documented,
  but it is one more invariant a future editor must hold · severity: low ·
  → mitigation: none

### Goal-achievement risk: low
- Step 4 rests on `trap -p EXIT` reporting the parent handler from inside a
  command substitution — verified on this bash before planning. If it fails on
  another, the chain is a no-op and the Step-5b window stays uncovered ·
  severity: low (residual — inline post-phase verify_attach_window_abort fails
  outright if the chain is a no-op) · → mitigation: inline post-phase verify_attach_window_abort
- Making the attachment merge/rebind failures real changes behaviour beyond the
  stated scope: a fold that today silently commits partial attachment state will
  now abort. That is the correct outcome and is what makes the mitigation test
  meaningful, but it is a behaviour change no existing test pins · severity: low
  · → mitigation: inline post-phase verify_attach_window_abort

### Planned mitigations
- timing: pre-phase | name: pin_dirty_entry_rollback | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (snapshot-restore changes pinned Step 6 semantics) | desc: Pin the dirty-on-entry Step 6 rollback case before switching the restore mechanism, and record that it fails against the pre-change build.
- timing: post-phase | name: verify_attach_window_abort | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 + both goal-achievement risks (EXIT-trap chaining across the attach lock, and real Step-5b failure propagation) | desc: Abort inside the Step 5b attach transaction and assert the injected failure reached the abort, that the fold rolled back, that a pre-fold dirty meta file survives, and that the attach lock was released.
- timing: post-phase | name: pin_control_excision_span | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 3 (retargeted negative-control anchor) | desc: Pin the boundaries of the span install_prefix_commit_block excises so a mis-anchored cut fails loudly instead of leaving the t1599_2 controls vacuous.

*(Post-inline reassessment, single pass: the three inline phases turn each
linked code-health bullet into a low residual, but the dimension stays
**medium** — the blast radius through `aitask_fold_mark.sh`'s commit path, the
new index-plumbing surface, and the coexistence of two snapshot mechanisms are
unchanged by adding tests. Goal-achievement stays **low**; the new
failure-propagation bullet is a genuinely new risk introduced by addressing the
review, added as its own bullet rather than by rewriting a linked one. No
mitigation selection was reopened.)*

---

## Post-Review Changes

### Change Request 1 (2026-09-01 15:20)
- **Requested by user:** `_fold_snap_add` turned a failed `task_git ls-files
  --stage` into an empty `.idx` file via `|| :`. An index-read failure before
  any mutation was therefore recorded as "path absent", so a later rollback's
  `update-index --force-remove` would DELETE the caller's pre-existing index
  entry instead of restoring it. The snapshot must fail loudly before Step 3,
  while no fold mutation exists.
- **Changes made:** Replaced the `|| :` truncation with
  `|| die "fold: could not read the index entry for <path> — refusing to start
  a transaction that could not be rolled back"`. Dying there is safe precisely
  because it precedes the arm: nothing is mutated yet, so fail-closed costs
  nothing. The comment now states why a non-zero exit is unambiguous —
  `ls-files` exits 0 with empty output for a path merely absent from the index,
  so non-zero can only mean the read failed.
  Added `test_index_read_failure_aborts_before_mutating`, driven by a PATH
  `git` shim that refuses `ls-files` and forwards everything else to the real
  binary (the CLI boundary, not a source patch, so it exercises the real
  unreadable/locked-index failure). It seeds a STAGED pre-fold edit and asserts
  the abort message, that the staged index entry is byte-identical afterwards,
  and that nothing was mutated. Mutation-tested: restoring the `|| :` makes the
  staged entry disappear (`D `, empty `ls-files` output) and fails three of the
  assertions.
- **Files affected:** `.aitask-scripts/aitask_fold_mark.sh`,
  `tests/test_fold_mark.sh`

---

## Final Implementation Notes

- **Actual work done:** All seven plan steps plus the three inline mitigation
  phases landed as designed, in three files:
  - `.aitask-scripts/aitask_fold_mark.sh` — `--commit-mode` validated at
    argument-parse time; the fold's file set hoisted above the first mutation
    and renamed `rollback_paths` → `fold_paths` (it is the commit scope, not the
    restore set); a snapshot registry that captures each path's working-tree
    bytes *and* full index entry list before it can be mutated, restored via
    `update-index --force-remove` + `--index-info`; an `EXIT` trap
    (`_fold_abort_cleanup`) armed immediately after the snapshot and disarmed
    only on a Step 6 terminal success; the whole `attachments/meta` tree
    snapshotted as the first action inside the attach lock; the trap chained in
    front of `registry_lock`'s handler in `_fold_attach_txn` and re-armed at an
    explicit `with_attach_lock` failure branch; explicit failure propagation on
    both `frontmatter_patch.py append` sites and on `attach_meta rebind`.
  - `tests/test_fold_mark.sh` — the pinned residual test reworked
    (`test_abort_mid_mutation_emits_no_records` →
    `test_abort_mid_mutation_rolls_back`), 11 tests added, one negative control
    added (`install_prefix_no_abort_rollback`), one injector added
    (`install_attach_txn_returns_nonzero`), and `install_prefix_commit_block`'s
    excision anchor retargeted from the `--commit-mode` die string (which Step 1
    moved) to a column-0 `\nesac\n` search from `# Step 6: commit`.
  - `.claude/skills/task-workflow/task-fold-marking.md` — the "what this does
    not buy" paragraph replaced by the transaction guarantee, the pre-fold (not
    HEAD) restore semantics, and the honest residual (a signal that bypasses the
    trap).
- **Deviations from plan:** Two, both from Step-8 review rounds and both
  scope-preserving. (1) `_fold_snap_add`'s index read originally used `|| :`,
  which turned a read failure into a recorded "absent" and would have made
  rollback delete the caller's index entry; it now fails closed with `die`,
  covered by `test_index_read_failure_aborts_before_mutating`. (2) The negative
  control's "did the injection land" greps had to be tightened from bare name
  matches to definition/arming-site matches, because the new transaction block
  legitimately mentions `_fold_amend_guard` and the post-attach-lock re-arm
  legitimately contains `trap '_fold_abort_cleanup' EXIT` — a bare grep read
  both as "the excision failed".
- **Issues encountered:**
  - `${!arr[@]+"${!arr[@]}"}` is parsed as *indirection*, not the keys form, and
    dies with "invalid variable name". Replaced with a `(( ${#arr[@]} ))` guard
    plus a plain `"${!arr[@]}"`.
  - The attach-window tests needed lib copies the shared scaffold does not
    carry; added a local `_copy_attachment_libs` rather than widening
    `tests/lib/test_scaffold.sh`, which every other suite pays for.
- **Key decisions:**
  - **Snapshot-restore, not HEAD-restore.** Extending the existing
    `_fold_rollback` to pre-Step-6 aborts would have *introduced* a data-loss
    path: the documented ad-hoc fold flow runs `aitask_fold_content.sh |
    aitask_update.sh --desc-file -` immediately before this script and does not
    commit, so the primary is routinely dirty (and may be staged) on entry.
  - **Index snapshot covers every stage.** `ls-files --stage` emits three lines
    for an unmerged path; parsing one `mode,sha` and writing a stage-0 entry
    would silently resolve a user's conflict, and `ait syncer` rebases task
    data, so that state is reachable.
  - **Whole meta tree, not a predicted subset.** `cmd_rebind` walks every meta
    file and rewrites those whose `refs` contain the folded id — a property of
    the ledger, not of task frontmatter, so a frontmatter-derived prediction
    could miss a drifted ref.
  - **Chain the EXIT trap rather than replace it**, per the rule already stated
    in `lib/stale_lock.sh`. Verified empirically first that `trap -p EXIT`
    inside `$( )` reports the parent handler.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/attachment_lock.sh:39-45 — with_attach_lock runs its
    callback as `"$@" || rc=$?`, which disables errexit for the whole callback;
    every other consumer (`aitask_attach.sh`'s add/rm transactions) inherits
    that, so any unchecked command inside one of those callbacks fails silently.
    Fixed only at this script's own call sites; the shared seam still has no
    guard rail and no test pinning the property.`
- **Verification:** `bash tests/test_fold_mark.sh` → 216/216. All 13 adjacent
  suites that copy or drive the script pass. `shellcheck` reports the same 6
  pre-existing info findings as the baseline (no new ones). Six mutants were
  injected and each was caught by a distinct assertion: no meta snapshot; no
  trap chain; a chain that clobbers the lock-release handler; a bare
  `with_attach_lock` call site; dropped index replay; and the restored `|| :`
  fail-open index read. The manual end-to-end check confirms an aborted fold
  leaves exactly the caller's pre-existing staged modification with no
  `folded_tasks` residue.
