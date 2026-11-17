---
Task: t2322_registry_lock_preserve_caller_exit_trap.md
Base branch: main
Output branch: main
---

# t2322 — registry_lock: preserve the caller's EXIT trap

## Context

`registry_lock_acquire` (`.aitask-scripts/lib/registry_lock.sh:130`) does
`trap "registry_lock_release '$dir'" EXIT`, **replacing** the caller's EXIT
trap, and `registry_lock_release` (`:155`) does `trap - EXIT`, **clearing** it.
A caller's own EXIT handler is therefore dead during the hold and gone after
release. t2302 hit it as a test leak (`tests/test_registry_lock.sh` lost its
`rm -rf "$TMPROOT"` trap). Production callers carry workarounds: the fold
re-arms `_fold_abort_cleanup` after `with_attach_lock`
(`aitask_fold_mark.sh:839`), and `aitask_gate.sh` sync-registry hand-swaps
traps (`:1493`, `:1501`). `txn_snapshot.sh` and `attachment_lock.sh` carry
comments describing the overwrite.

Goal: acquire **chains** its release in front of the caller's trap; release
**restores** the caller's trap. Then the caller-side workarounds can go.

## Findings that shape the design (measured / read)

1. **Subshell hazard (measured, bash 5.3):** inside `( … )`, `trap -p EXIT`
   prints the *parent's* trap although it is not armed there. Naive
   capture-and-chain in a subshell would run the parent's cleanup (e.g.
   `rm -rf "$TMPROOT"`) when the subshell exits. The repo already handles this
   in `lib/archive_utils.sh` `_ait_archive_arm_exit_trap`: it composes only when
   `BASH_SUBSHELL == 0`. We take the same boundary. In a subshell, behaviour
   stays exactly as it is today (replace, then clear).
2. **Archive sweep interplay:** most callers source `task_utils.sh`, so their
   pre-acquire trap is `_ait_archive_cleanup` or `_ait_archive_exit_chain` (the
   chain stores the inner caller in `_AIT_ARCHIVE_CALLER_EXIT_TRAP`). If we save
   `_ait_archive_exit_chain` as our caller and then call
   `ait_archive_rearm_exit_trap`, the archive overwrites its stored caller with
   *our* token, and exit recurses archive→us→archive→us. **Fix: unwrap the
   archive layer when saving.** Substitute the token `_ait_archive_exit_chain` →
   `$_AIT_ARCHIVE_CALLER_EXIT_TRAP` (exactly what its runtime rewrite does), and
   `_ait_archive_cleanup` → nothing (bare) or `:` (inside a composite). The
   archive wraps us as the outermost layer (the rearm already present). After
   release we restore the unwrapped text and rearm, so the archive wraps it
   again. The state is identical to the pre-acquire state, and no other lib's
   private variable is written (it is read only).
3. **Ledger first-command detector** (`lib/ledger_block.sh`): a no-arg
   `ait_ledger_lock_exit_trap` checks that it is first in `trap -p EXIT`. Our
   exit chain must therefore rewrite the trap with our token replaced by the
   caller's text, restore `$?` and then `eval` the caller's text. This is the
   same contract as `_ait_archive_exit_chain`, mirrored.
4. **Chain order: release first, then the caller's handler.** An appended
   command never runs after a handler that calls `exit`, so release-first never
   leaks the lock. Handlers that need the lock (txn rollback, fold rollback)
   are already **prepended inside the hold** via `txn_chain_exit_trap`, so they
   still run under the lock, before our chain.
5. **Fold double-run is safe:** with chaining, `_fold_abort_cleanup` runs once
   via the in-hold prepend (under the lock) and again as the restored caller
   trap. `_fold_rollback` sets `_fold_txn_active=false` first, and
   `txn_snap_cleanup` is idempotent, so the second run is a no-op.
6. Nested acquire while already holding (one-lock-per-process is already the
   contract) must not re-save our own token: guard on an "armed" flag.

## Implementation

### Pre-phase (risk mitigations)

- **lock_caller_baseline**: before any edit, run every suite in the
  Verification list on the unmodified tree, and record each file's PASS/FAIL
  summary in the plan's Final Implementation Notes. Failures that already
  exist are then attributed to the baseline, not to this change. Never stash or
  git-restore to get the baseline (the worktree is shared and dirty). Run on
  the tree as it stands.

### 1. `.aitask-scripts/lib/registry_lock.sh`

New state: `_registry_lock_trap_mode` (`""|chain|replace`),
`_registry_lock_saved_trap` (archive-free caller text), and
`_registry_lock_trap_shell` (the shell that armed it:
`${BASHPID:-$$}:${BASH_SUBSHELL:-0}`, the same identity
`_AIT_ARCHIVE_TMPDIR_SHELL` uses in `archive_utils.sh`).

**Trap state is per-shell; the variables are not.** A `( … )` / `$( )` child
inherits all three variables but **not** the armed EXIT trap. The
"is it armed?" test is therefore `mode non-empty AND _registry_lock_trap_shell
== current shell`. A mismatch means inherited, inactive state. The child
discards it and arms its own (replace mode, because it is a subshell), and
**never** composes the inherited parent cleanup. The identity is sound on bash
3.2 too (no `BASHPID`): inherited state always comes from a strictly shallower
`BASH_SUBSHELL` level, so the level part alone separates parent from child.
(Verified finding: with an unscoped flag, a parent holding A plus a child
acquiring B leaks B at child exit. Today's code releases B, so an unscoped flag
would be a regression.)

- `_registry_lock_caller_exit_trap`: read `trap -p EXIT`, strip
  `trap -- ` / ` EXIT`, `eval` it to unquote bash's own rendering (the archive
  idiom), then unwrap the archive tokens (finding 2). Print the result.
- `_registry_lock_arm_exit_trap` (called on successful acquire):
  - armed **in this shell** (mode set and the shell identity matches) → return
    (same-shell nested acquire; keep the saved state, no self-recursion).
  - otherwise reset the mode and saved text first (drop inherited state), record
    the current shell identity, then:
  - `BASH_SUBSHELL > 0` → mode `replace`, `trap "registry_lock_release '$dir'" EXIT`
    plus the guarded rearm (today's text, verbatim).
  - else → mode `chain`, save the caller text, then `trap _registry_lock_exit_chain EXIT`
    plus the guarded rearm.
- `_registry_lock_drop <dir>`: the token release, the warn and the state clear
  (the body of today's release, no trap operations).
- `registry_lock_release`: owner check as today → `_registry_lock_drop`, then
  `_registry_lock_restore_exit_trap`. Still always returns 0.
- `_registry_lock_restore_exit_trap`: mode `chain` **and** the shell identity
  matches the current shell → `trap -- "$saved" EXIT` (or `trap - EXIT` when empty) plus the guarded
  rearm. Otherwise → `trap - EXIT` plus the guarded rearm (today's behaviour,
  which also covers a subshell releasing a lock the parent armed: restoring
  there would arm the parent's text in the subshell). Clear the mode and saved
  state.
- `_registry_lock_exit_chain` (the EXIT handler in chain mode):
  `local __rl_rc=$? …` first. Snapshot the saved text, `_registry_lock_drop`,
  rewrite the current trap with our token → the saved text (else the saved
  text alone; clear when empty), `(exit "$__rl_rc") && :`, then
  `eval "$saved"`. The trap statements here carry a new tripwire marker
  `# archive-sweep: exit-handler`: re-arming inside a running EXIT handler would
  wrap a sweep that has already run outermost.
- Header: document chain/restore, the subshell boundary, the order, and the
  archive unwrap. Update the "One active lock per process" note.

### 2. `tests/test_archive_rearm_tripwire.py`

Add a second accepted per-line marker, `# archive-sweep: exit-handler`, with a
docstring line explaining it, plus a self-test (a marked line passes, an
unmarked one is still flagged). Re-check that the `sites >= 42` floor still
holds after the call-site removals below (adjust it only if the true count
legitimately drops, and say so).

### 3. Remove the caller-side workarounds

- `aitask_fold_mark.sh`: delete the post-`with_attach_lock` re-arm at `:839`
  (`trap '_fold_abort_cleanup' EXIT   # registry_lock_release did …`) and its
  rearm line. Keep the explicit `|| _fold_attach_rc=$?` branch, because it still
  produces the `die` message, and rewrite its comment. Keep
  `txn_chain_exit_trap '_fold_abort_cleanup'` in `_fold_attach_txn`, because it
  is what makes the rollback run **under** the lock. Rewrite the `:780` comment
  to say that, and why the second run of the handler is a no-op.
- `aitask_gate.sh` sync-registry: drop `trap 'registry_lock_release …' EXIT` /
  rearm after the acquire and `trap - EXIT` / rearm after the release. The
  `trap - EXIT` would now clobber the restored caller trap.
- Comment updates (no behaviour change): `lib/txn_snapshot.sh:243`
  (`txn_chain_exit_trap` rationale: the prepend now orders rollback before
  release, and release restores the *pre-acquire* trap, so during-hold traps
  still end at release), `lib/attachment_lock.sh:81`, `lib/merge_lock.sh:30`,
  `lib/archive_utils.sh:144` (the variable is also *read* by registry_lock's
  unwrap).

### 4. Tests

- `tests/test_registry_lock.sh` (new cases, each in a throwaway `bash` child
  script so the suite's own traps are not involved):
  - **15** a top-level caller trap survives acquire+release: `trap -p EXIT`
    after release equals the caller's text, and the handler runs once at exit.
  - **16** exit while held (`exit 7`): the status stays 7, the lock dir is gone
    *before* the caller's handler runs (the handler records `[ -d lock ]`), the
    handler runs once and sees its own text in `trap -p EXIT`.
  - **17** subshell boundary: the parent has a trap, `( acquire; )` exits. The
    parent's handler runs exactly once (not inside the subshell), and the
    subshell still released its lock (case 5 stays green).
  - **17b** inherited armed state (the blocking review finding): the parent
    sets its own caller trap and acquires A at top level, then
    `( registry_lock_acquire B; )` exits **without** an explicit release.
    Assert that B is removed after the subshell, A still exists after the
    subshell, and the parent's handler has not run yet (marker count 0). Then
    the parent releases A: A is removed, `trap -p EXIT` is the caller's text
    again, and at parent exit the handler runs exactly once. Pre-fix control:
    the same script against a copy of the lib whose armed-state guard is
    unscoped (identity check deleted) shows B left behind. This proves the case
    can fail.
  - **18** nested acquire does not recurse: two acquires, then exit; the
    handler runs once and the process exits normally.
  - Update the stale t2302 header comment. Keep the parent-owned root, which
    also covers signals, but stop claiming the library drops the trap.
- `tests/test_archive_rearm_exit_trap.sh` (with archive loaded): **9c** a
  caller trap plus the archive sweep, then acquire+release. The trap is again
  `_ait_archive_exit_chain`, and dying afterwards runs the caller handler once
  and sweeps. **9d** dying while held runs the caller handler once, releases
  the lock and sweeps, with no recursion. Cases 9/9b/10 stay as they are.
- `tests/test_fold_mark.sh`: replace `install_attach_rearm_removed` and
  `test_negative_control_attach_rearm_removed` with a **pre-fix control on the
  library**. Inject the old release (`trap - EXIT` in place of
  `_registry_lock_restore_exit_trap`) into the fixture's
  `.aitask-scripts/lib/registry_lock.sh`, run the same non-zero-return scenario,
  and `assert_defect_present` for no rollback. The positive
  `test_attach_txn_nonzero_return_rolls_back` now proves the restore, because
  the re-arm line is gone. Update the comments that cite the removed re-arm.

### Post-phase (risk mitigations)

- **trap_shape_matrix**: add a table-driven case to
  `tests/test_archive_rearm_exit_trap.sh`. Each row is a pre-acquire EXIT-trap
  shape: none, a plain caller handler, `_ait_archive_cleanup`,
  `_ait_archive_exit_chain` + caller, a `txn_chain_exit_trap`-prepended
  composite, and the no-arg `ait_ledger_lock_exit_trap` (with a ledger lock
  held). Each shape is run two ways, (a) acquire → release → `exit 3` and
  (b) acquire → `exit 3` while held. Assert: every handler runs exactly once
  (marker-line counts), the exit status is 3 (the ledger row is not turned into
  a generic 1), the lock dir is gone, and the archive is swept.

### Step 9 (Post-Implementation)
Commit the code with `bug: … (t2322)`, then archive via the workflow's Step 9.

## Verification

```bash
bash tests/test_registry_lock.sh
bash tests/test_archive_rearm_exit_trap.sh
SHELL_UNDER_TEST=/bin/bash bash tests/test_archive_rearm_exit_trap.sh   # if a 3.2 bash exists
python3 tests/test_archive_rearm_tripwire.py
bash tests/test_fold_mark.sh
bash tests/test_projects_lock_released_on_die.sh
bash tests/test_attach_txn_worktree_isolation.sh
bash tests/test_txn_snapshot.sh
bash tests/test_create_email_lock.sh
bash tests/test_pick_own_scoped_commit.sh
bash tests/test_shadow_rejected.sh
bash tests/test_scratchpad_store.sh
bash tests/test_sitrep_todo.sh
bash tests/test_agent_marks_concurrency.sh
bash tests/test_artifact_fetch_exclusion.sh
bash tests/test_merge_lock_broker.sh
bash tests/run_shell_test.sh tests/test_registry_lock.sh   # leftovers check
shellcheck .aitask-scripts/lib/registry_lock.sh .aitask-scripts/aitask_fold_mark.sh .aitask-scripts/aitask_gate.sh
```
Plus a grep of `tests/` for gate sync-registry coverage (`sync-registry`), and
run whatever test exercises it.

## Risk

### Code-health risk: medium
- The archive-chain unwrap or exit-chain interplay could recurse at exit or drop a handler for an unanticipated trap shape · severity: medium · → mitigation: inline post-phase trap_shape_matrix
- A caller whose pre-acquire trap used to be cleared after release now gets it back, so the handler can run at a new point or twice (audited: fold handler idempotent, gate swap removed) · severity: low · → mitigation: inline pre-phase lock_caller_baseline

- Module trap state is inherited by subshells while the armed trap is not; an unscoped "armed" flag would leak a child's lock (review finding, verified) · severity: medium · → mitigation: addressed in the design (shell-identity-scoped armed state) + case 17b with a pre-fix control

### Goal-achievement risk: low
- Acquires inside `( … )` subshells still lose a subshell-set caller trap (deliberate boundary; an inherited trap is not detectable there) · severity: low · → mitigation: none (documented + case 17)

### Planned mitigations
- timing: pre-phase | name: lock_caller_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: callers depending on the old clear semantics | desc: run all lock-caller suites on the unmodified tree first and record the baseline
- timing: post-phase | name: trap_shape_matrix | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: archive/exit-chain recursion or lost handler | desc: table-driven test over every pre-acquire trap shape × release-then-exit / die-while-held
