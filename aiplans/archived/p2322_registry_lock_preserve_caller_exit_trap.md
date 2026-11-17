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

## Post-Review Changes

### Change Request 1 (2026-11-17 17:10)
- **Requested by user:** two blocking review findings, both CONFIRMED by the reviewer:
  (1) the saved caller trap was eval'd inside `_registry_lock_exit_chain`, whose
  `$@` is empty, so a caller handler reading `$1` died with "unbound variable"
  (under `set -u`) when the process exited while holding the lock;
  (2) the self-token defence (and, the same class, the archive-layer peel)
  rewrote any SUBSTRING `_registry_lock_exit_chain` / `_ait_archive_*`, including
  quoted caller data (`rmdir "$d/_registry_lock_exit_chain"` → `rmdir "$d/:"`).
- **Changes made:**
  - The chain is installed as `trap '_registry_lock_exit_chain "$@"' EXIT`
    (`_REGISTRY_LOCK_CHAIN_CMD`); `"$@"` expands in the exit context, so the
    caller's text, eval'd inside the function, keeps `$1`/`$#`/`"$@"`.
  - Wrapper recognition is by WHOLE COMMAND via `_registry_lock_owned_tail`:
    the text equals the wrapper command, or is a `txn_chain_exit_trap`
    composite (`__txn_chain_rc=$?;` prefix) whose last command is the wrapper —
    the only shapes the producers emit. Used for the archive peel, the
    self-token defence and the exit chain's trap rewrite
    (`_registry_lock_join` composes head + tail).
  - Regressions: `test_registry_lock.sh` case 19 (script args, die-while-held
    and release-then-exit) and case 20 (literal `_registry_lock_exit_chain` in
    quoted data); `test_archive_rearm_exit_trap.sh` M-lit (literal
    `_ait_archive_cleanup` / `_ait_archive_exit_chain` paths, archive loaded).
  - Mutant controls (ad hoc, scratch lib copies): no-`"$@"` → case19[held]
    fails (2 asserts; released passes — the reviewer's exact shape);
    substring self-defence → case20 fails (5 asserts); substring archive peel
    → M-lit fails (and 9b / M[none/a]).
- **Files affected:** `.aitask-scripts/lib/registry_lock.sh`,
  `tests/test_registry_lock.sh`, `tests/test_archive_rearm_exit_trap.sh`

### Change Request 2 (2026-11-17 17:45)
- **Requested by user:** (blocking, CONFIRMED) `_registry_lock_owned_tail`
  recognised composites only with the `__txn_chain_rc=$?;` prefix, but
  `tests/lib/tmpdir_guard.sh::_tg_prepend_exit_trap` emits the same
  status-preserving shape with `__tg_rc` — so a caller handler behind an archive
  chain behind a tg prepend vanished (a regression introduced by Change
  Request 1). (follow-up/low) the installed trap literal duplicated
  `_REGISTRY_LOCK_CHAIN_CMD`.
- **Changes made:**
  - Recognition no longer keys on the producer: a wrapper is a command when it
    is the whole text, or the last command after an unescaped `"; "` ending the
    text (every prepend keeps the earlier trap as its tail). Quoted data still
    cannot match (it ends in a quote), and a `\;` before the word is refused.
  - The chain is installed with `trap "$_REGISTRY_LOCK_CHAIN_CMD" EXIT`.
  - Regressions: matrix row `tg` (real `_tg_prepend_exit_trap`, both flows);
    `test_registry_lock.sh` case 21, a table over every producer shape and the
    near-misses (quoted data, `"a; name"` inside quotes, escaped `\;`,
    mid-text mention, longer name).
  - Mutant control: restoring the `__txn_chain_rc` prefix fails M[tg/a],
    M[tg/b] (handler lost — the reviewer's reproduction) and 3 case-21 rows.
- **Files affected:** `.aitask-scripts/lib/registry_lock.sh`,
  `tests/test_registry_lock.sh`, `tests/test_archive_rearm_exit_trap.sh`

### Change Request 3 (2026-11-17 18:15)
- **Requested by user:** (blocking, low, CONFIRMED) `_registry_lock_owned_tail`
  refused ANY head ending in a backslash, but an even run (`\;`) is a literal
  backslash followed by an active `;`. A trap such as
  `printf "%s\n" \; _ait_archive_exit_chain` therefore lost its archive-stored
  caller under the lock (both flows), while it ran without the lock.
- **Changes made:** escaping is decided by the PARITY of the run of
  backslashes before the `;` (odd → escaped, refused; even → active,
  recognised). Regressions: case 21 rows for an even run (hit) and an odd run of
  three (miss); `M-bs` in `test_archive_rearm_exit_trap.sh`, a differential
  over {even, odd} × {no lock, release-then-exit, die-while-held} asserting the
  lock never changes what runs. Mutant control: the round-2 "any backslash"
  rule fails M-bs[even/a], M-bs[even/b] and the case-21 even row.
- **Files affected:** `.aitask-scripts/lib/registry_lock.sh`,
  `tests/test_registry_lock.sh`, `tests/test_archive_rearm_exit_trap.sh`

## Final Implementation Notes
- **Actual work done:** `lib/registry_lock.sh` chains instead of replacing:
  in the top-level shell `registry_lock_acquire` saves the caller's EXIT trap
  (archive-sweep layer peeled off) and installs
  `trap "$_REGISTRY_LOCK_CHAIN_CMD" EXIT` (`_registry_lock_exit_chain "$@"`),
  which at exit releases first and then runs the caller's text with the dying
  `$?`, the script's positional parameters and its own text visible in
  `trap -p EXIT`; `registry_lock_release` restores the saved trap. Subshells
  keep the pre-t2322 replace/clear behaviour; the armed state is scoped to the
  arming shell (`${BASHPID:-$$}:${BASH_SUBSHELL}`). Wrapper commands are
  recognised by whole command (whole text, or last command after an unescaped
  `"; "`, escaping by backslash-run parity), never by substring. Workarounds
  removed: the fold's post-`with_attach_lock` re-arm and the manual trap swap in
  `aitask_gate.sh` sync-registry. Tripwire gained the
  `# archive-sweep: exit-handler` marker. Comments updated in
  `txn_snapshot.sh`, `merge_lock.sh`, `archive_utils.sh`.
- **Deviations from plan:** three review rounds tightened the design (see Post-Review
  Changes): positional parameters through `"$@"`; whole-command recognition with
  producer-agnostic tail matching (covers `_tg_prepend_exit_trap`); parity-based
  escape detection. Case numbering grew to 15-21 in `test_registry_lock.sh`,
  plus the archive suite's M matrix (7 shapes incl. `tg`), M-lit and M-bs.
- **Issues encountered:** (1) the plan's first draft had an unscoped "armed"
  flag — a ( ) child inheriting it would leak its own lock (caught in plan
  review, case 17b + pre-fix control). (2) The `aitask_gate.sh` sync-registry
  hunk was committed by a concurrent session inside its own commit
  `7df50e1c5` (t2324), which committed the whole working-tree file. The interim
  (gate hunk on main before the library change) is behaviour-equivalent: under
  the old library the removed lines duplicated what acquire/release already
  did. So this task's code commit carries the other nine files only.
  (3) No bash 3.2 is available on this machine, so the
  `SHELL_UNDER_TEST=/bin/bash` portability run was NOT done (code avoids
  bash-4-only constructs; `${BASHPID:-$$}` falls back as in archive_utils).
- **Key decisions:** release-first ordering (a caller handler that calls `exit`
  can never strand the lock; under-lock rollback stays a `txn_chain_exit_trap`
  prepend inside the hold, which the fold keeps); the archive sweep stays the
  outermost wrapper (peel on save, re-arm on install/restore) so no other lib's
  private state is written; the test-side parent-owned root in
  `test_registry_lock.sh` is kept (still the stronger owner, covers signals).
- **Baseline (pre-phase lock_caller_baseline):** all 19 suites green on the
  unmodified tree (registry_lock 51, archive_rearm 66, fold 277, txn 60,
  create_email_lock 78, pick_own 103, shadow_rejected 130, scratchpad 116,
  sitrep_todo 367, agent_marks 25, artifact_fetch_exclusion 245, merge_lock
  135, gates_sync_registry 94, agent_sessions 42, single_winner 15,
  share_resolution 98, attach_txn 149, projects_lock_on_die 38, tripwire OK).
  After: 28 suites green (registry_lock 98, archive_rearm 194, fold 277, …),
  no TMPDIR leftovers.
- **Post-phase trap_shape_matrix:** done (`M` block: none / plain / chain /
  txn / tg / ledger / noarchive × release-then-exit / die-while-held); against
  the pre-t2322 library it fails 17 assertions.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/archive_utils.sh:228 — _ait_archive_exit_chain evals the stored caller trap inside a function installed as a bare `trap _ait_archive_exit_chain EXIT` (:263), so a caller handler reading $1 / "$@" sees an empty argument list (fatal under set -u) whenever the archive sweep wraps it`
  - `.aitask-scripts/lib/archive_utils.sh:256 — _ait_archive_wrap_exit_trap's idempotence check (and the chain rewrite at :222) match _ait_archive_cleanup / _ait_archive_exit_chain as SUBSTRINGS, so a caller trap whose quoted data merely names them (e.g. rmdir "$d/_ait_archive_cleanup") is treated as already wrapped and the sweep is silently dropped`
