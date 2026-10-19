---
Task: t2032_chain_archive_sweep_through_rearmed_traps.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2032 — Keep the archive sweep through re-armed EXIT traps

## Context

t2023 made `lib/archive_utils.sh` sweep this shell's `ait-archive.<owner>.*`
extraction dirs from the EXIT trap. It installs `_ait_archive_cleanup` bare, or
`_ait_archive_exit_chain` when the sourcing script already had a trap. A later
bare `trap X EXIT` or `trap - EXIT` replaces that trap. After that the sweep
never runs, so every `$( resolve_task_file … )` of a bundled task made during
the process's life leaks one dir.

Measured scope is wider than the task lists. **35 top-level re-arm sites in 15
archive-loaded scripts**, plus 2 in `lib/registry_lock.sh`:

- `aitask_gate.sh` (10: ledger sections, `trap - EXIT`, registry-sync)
- `aitask_note.sh` (10, incl. the top-level `trap note_cleanup EXIT` at :89 —
  this drops the sweep for **every** `ait note` run)
- `aitask_create.sh` (5, `_child_lock_exit_trap` / `trap - EXIT`)
- `aitask_fold_mark.sh` (2)
- one site each in `aitask_ls.sh`, `aitask_task_commit.sh`,
  `aitask_metadata_commit.sh`, `aitask_verified_update.sh`,
  `aitask_usage_update.sh`, `aitask_verification_followup.sh`,
  `aitask_create_manual_verification.sh`, `aitask_remote_drift_check.sh`,
  `aitask_revert_analyze.sh`
- `lib/registry_lock.sh` acquire (:130) and release (:153). These are reached
  through `attachment_lock.sh` by attach / artifact / fold_mark / sync /
  pick_own / gate.

Three more sites are subshell-local `( … trap "rm -rf '$tmpd'" EXIT … )` with
no resolve inside: `lib/artifact_backends/gitbranch.sh:216,306` and
`aitask_artifact.sh:1084`.

## Approach — explicit re-arm after every re-arm site, enforced by a tripwire

Rejected: shadowing the `trap` builtin with a function. It would catch future
sites for free, but it changes the semantics of every `trap` call in ~all
scripts. `archive_utils`' own re-arm inside the running handler would also need
`builtin trap`. The blast radius is too wide for a cleanup helper. An explicit
call keeps the change greppable, and a static tripwire covers future sites.

### 1. `lib/archive_utils.sh` — public re-arm helper

Split `_ait_archive_arm_exit_trap` into a shared core plus two entry points:

```bash
# _ait_archive_wrap_exit_trap -- wrap whatever EXIT trap is armed NOW so the
# sweep runs first. Idempotent (our name already present -> no-op); empty ->
# bare cleanup; otherwise store the text and install the chain.
_ait_archive_wrap_exit_trap() {
    local cur
    cur="$(trap -p EXIT)"
    case "$cur" in *_ait_archive_cleanup*|*_ait_archive_exit_chain*) return 0 ;; esac
    if [[ -z "$cur" ]]; then trap _ait_archive_cleanup EXIT; return 0; fi
    cur="${cur#trap -- }"; cur="${cur% EXIT}"
    eval "_AIT_ARCHIVE_CALLER_EXIT_TRAP=$cur"
    trap _ait_archive_exit_chain EXIT
}
_ait_archive_arm_exit_trap() {          # source time: unchanged behaviour
    if (( ${BASH_SUBSHELL:-0} > 0 )); then trap _ait_archive_cleanup EXIT; return 0; fi
    _ait_archive_wrap_exit_trap
}
# ait_archive_rearm_exit_trap -- call on the line right after any
# `trap … EXIT` / `trap - EXIT` in a script that has archive_utils loaded (t2032).
ait_archive_rearm_exit_trap() { _ait_archive_wrap_exit_trap; return 0; }
```

- The re-arm composes **even inside a `( )` subshell**. The source-time
  subshell bail-out exists because `trap -p` there shows the *parent's*
  inactive trap. Right after the subshell's own `trap` command, the display is
  the subshell's active trap.
- **The directory variable carries its creating shell (fixes a pre-existing
  hole that this helper would expose).** Today `_ait_archive_cleanup` runs
  `rm -rf "$_AIT_ARCHIVE_TMPDIR"` *before* the `_ait_archive_may_sweep` check.
  A `( )` child inherits a non-empty `_AIT_ARCHIVE_TMPDIR` from a parent that
  extracted directly. With
  `( trap : EXIT; ait_archive_rearm_exit_trap )`, the child's exit would
  therefore delete the parent's live extraction. Reproduced in review
  (`parent_file=DELETED`). Today only a guard-reset re-source arms in a
  subshell, and that resets the variable to `""`, which is why the hole is
  latent. Fix:
  - `_extract_from_archive` records `_AIT_ARCHIVE_TMPDIR_SHELL="${BASHPID:-$$}:${BASH_SUBSHELL:-0}"`
    when it **creates** the dir. It does not record anything when it reuses
    an inherited dir. The `BASH_SUBSHELL` component distinguishes `( )`
    children on bash 3.2, where `$$` is the parent's PID. Reset it alongside
    `_AIT_ARCHIVE_TMPDIR=""` at source time.
  - `_ait_archive_cleanup` removes `_AIT_ARCHIVE_TMPDIR` only when
    `_AIT_ARCHIVE_TMPDIR_SHELL` equals the current shell's id. A child-created
    extraction is still removed by that child's own cleanup. An inherited dir
    is left to its creator: the parent's direct cleanup, or the owner-tag sweep
    at parent exit.
  - A child that **reuses** an inherited dir (direct `_extract_from_archive`
    with the variable already set) writes into the parent's dir, as it does
    today. That dir stays the parent's to remove.
- The ledger contract holds because the chain is unchanged. At exit it runs the
  cleanup, re-arms the caller's text in place of its own token, restores `$?`
  and evals the handler. `_ait_ledger_exit_trap_is_first` therefore reads
  exactly the text the script armed: the bare spelling stays first, and the
  misuse spelling still trips the detector.
- Update the header comments. `_AIT_ARCHIVE_CALLER_EXIT_TRAP` is now written by
  the wrap core, not "ONLY by `_ait_archive_arm_exit_trap`". Add a short
  "Re-arm contract (t2032)" paragraph to the temp-dir section.

### 2. Call sites — one pattern

- **Archive-loaded scripts:** put `ait_archive_rearm_exit_trap` on the line
  right after each `trap … EXIT` line. For the one-liners
  (`release_gate_lock_checked; trap - EXIT`), append `; ait_archive_rearm_exit_trap`
  to the same line. The trap lines themselves stay byte-identical, so
  `test_gate_lock_characterization.sh` 8a still finds
  `trap 'ait_ledger_lock_exit_trap' EXIT` as the line after each
  `acquire_gate_lock`. Representative examples: `aitask_gate.sh:294/308`,
  `aitask_note.sh:89/504/521`, `aitask_create.sh:865/924`,
  `aitask_fold_mark.sh:518/820`.
- **`lib/registry_lock.sh`:** this lib also loads without archive_utils, so use
  the guarded spelling after both the acquire trap and `trap - EXIT`:
  `if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi`
  Exiting while the lock is held runs chain → sweep → `registry_lock_release`.
  Inside that, `trap - EXIT` plus the re-arm sets a bare cleanup that does not
  re-fire, which t2023 already established.
- **Subshell-local sites with no resolve** (gitbranch.sh ×2, aitask_artifact.sh
  ×1): add a per-line marker `# archive-sweep: subshell-local`. These are
  exempt, not re-armed.
- Check each site for anything that reads `$?` right after it. Every surveyed
  site either captured rc earlier or returns a literal; recheck while editing.

### 3. `lib/txn_snapshot.sh` — record, don't change

Add a comment at `txn_chain_exit_trap` about the composition family. It
prepends, so a handler placed after the prepended one receives that handler's
status, not the dying status. In front of the explicit ledger spelling
(`rc=$?; …; ait_ledger_lock_exit_trap "$rc"`), an `exit 42` therefore ends 0.
This happens with or without the archive chain. t2023 13d2 pins the value.
Shipped prepends only sit in front of `registry_lock_release` and
`_ait_archive_exit_chain`, and neither reads `$?` for the final status.

### 4. Docs — `aidocs/framework/shell_conventions.md`

Next to the existing "compose it with any EXIT trap" bullet (~line 107), add one
bullet. In any script that loads `archive_utils.sh` (via `task_utils.sh`), every
`trap … EXIT` / `trap - EXIT` is followed by `ait_archive_rearm_exit_trap`.
Libs use the `declare -F` guard. A subshell-local trap with no resolve carries
`# archive-sweep: subshell-local`. Name the tripwire test and note the txn
prepend status caveat.

### 5. Tests

**a. `tests/test_archive_rearm_exit_trap.sh` (new, bash).** Same child-script
pattern as `test_archive_utils.sh` Group J2: a bundled `t91_` archive and a
per-case probe TMPDIR. Each case runs a child bash that sources
`archive_utils.sh` (plus `ledger_block.sh` / `registry_lock.sh` as needed),
extracts once inside `$( )`, re-arms, and exits. Asserts cover the leftover
`ait-archive.*` dirs, the handler side effects, the exit status and stderr:

1. `trap X EXIT` + re-arm: swept, X ran once, `exit 7` → 7, trap text is the chain.
2. **Control:** `trap X EXIT` with no re-arm leaves exactly one dir. This
   proves the probe is sensitive.
3. `trap - EXIT` + re-arm: bare `_ait_archive_cleanup`, swept.
4. Ledger bare spelling (real `ledger_block.sh`, real lock dir) + re-arm,
   `exit 42`: rc 42, no first-command warning, lock released, swept.
5. Ledger misuse spelling `'c; ait_ledger_lock_exit_trap'` + re-arm: rc 1, the
   detector warning fires, swept.
6. The note.sh explicit-status spelling + re-arm, `exit 42` → 42, swept.
7. Idempotence: re-arm twice → handler runs once.
8. `( trap Y EXIT; ait_archive_rearm_exit_trap )` inside a child: Y runs at
   subshell exit, and the parent's extraction survives until the parent exits
   and is then swept. Two arms, because they reach the bug differently:
   - **8a direct parent extraction.** The parent calls `_extract_from_archive`
     directly (no `$( )`), so the child inherits a non-empty
     `_AIT_ARCHIVE_TMPDIR`. Then `( trap : EXIT; ait_archive_rearm_exit_trap )`.
     Assert that the parent's file still exists after the child exits, and is
     gone after the parent exits. Record the red run before the fix (the file
     is DELETED).
   - **8b `$( )` parent extraction.** Same shape, but the dir is reached only
     through the owner-tag sweep.
   - **8c child-owned extraction.** The child itself extracts directly (the
     variable is empty on entry because the parent made no direct extraction),
     re-arms, and exits. Assert that the child's dir is removed at child exit.
     This keeps the child-cleanup behaviour.
   - **8d bash 3.2 path** (`unset BASHPID`, as in `test_archive_utils.sh` J2d):
     repeat 8a. The `BASH_SUBSHELL` component must keep the parent's dir.
9. `registry_lock_acquire` with archive loaded, die while held: lock dir
   released, swept, rc preserved. Acquire + release, then exit: swept.
10. `registry_lock.sh` sourced **without** archive_utils: acquire/release under
    `set -euo pipefail` → no error. The guard works.

**b. Real entry point (red-then-green).** Build a scaffolded project
(`tests/lib/test_scaffold.sh` `setup_fake_aitask_repo` + task_utils closure)
with a bundled archived task and one active task. Run the real
`aitask_note.sh` against the bundled id under a probe TMPDIR. Its top-level
`trap note_cleanup EXIT` drops the sweep today. Assert no `ait-archive.*` dir
remains. Before editing note.sh, record the red run (1 leaked dir) and copy it
into the plan's Final Implementation Notes. If a gate CLI verb resolves in
`$( )` and then enters a ledger section on an active task, run it the same way
as a second real entry point.

**c. `tests/test_archive_rearm_tripwire.py` (new, unittest).**
- Discovery uses the repo's own scanner. Scope is the top-level
  `.aitask-scripts/*.sh` files whose `shell_startup_closure.startup_closure`
  contains `archive_utils.sh`, or that `source` task_utils/archive_utils
  anywhere. Add every `lib/**/*.sh` except `archive_utils.sh`.
- Site regex: a `trap` command word at line start or after `;`/`&&`/`||`/
  `then`/`do`/`{`. Skip `-p`/`-l`; `EXIT` must be in the signal list. Comment
  lines are skipped, and `eval "trap …"` is deliberately not matched
  (txn_chain preserves the trap).
- A site is satisfied by `ait_archive_rearm_exit_trap` later on the same line,
  by the next non-blank non-comment line containing it, or by the marker
  `# archive-sweep: subshell-local` on the trap line.
- Self-tests: a planted unpaired fixture is flagged, a paired one passes, and a
  marker passes. Non-vacuity: assert ≥ 37 sites scanned and ≥ 15 scripts in
  scope.

### Post-phase (risk mitigations)

1. [real_entry_leak_probes] Extend `tests/test_archive_rearm_exit_trap.sh`
   group 5b with two more real-entry probes on the same scaffolded project with
   a bundled task, each under its own probe TMPDIR, and assert no
   `ait-archive.*` dir remains:
   (a) the real `aitask_gate.sh` CLI. Pick a verb that runs
   `file="$(resolve_task_file …)"` and then an `acquire_gate_lock` section;
   resolving a bundled id inside the run suffices, so a section on an active
   task with a prior bundled resolve also works.
   (b) the real `aitask_create.sh --batch --parent <active parent> …`. This
   reaches `trap '_child_lock_exit_trap' EXIT` and `trap - EXIT`. Use a parent
   whose `$( resolve_task_file )` path goes through the archive tier, or a
   source-task resolve of a bundled id.
   For each probe, record a red run before the script's sites are edited (the
   leak count), and keep both counts for the Final Implementation Notes. If a
   path turns out not to resolve in `$( )` at all, state that in the notes
   rather than faking a red.

## Verification

- `bash tests/test_archive_rearm_exit_trap.sh`
- `python3 -m unittest tests.test_archive_rearm_tripwire` and
  `bash tests/run_all_python_tests.sh --test-dir tests` (last line = verdict)
- Trap/lock-sensitive suites, run unchanged:
  `test_archive_utils.sh`, `test_resolve_tar_zst.sh`,
  `test_ledger_lock_exit_trap.sh`, `test_gate_lock_characterization.sh`,
  `test_gate*.sh`, `test_note*.sh`, `test_create*.sh` (child lock),
  `test_fold_mark*.sh`, `test_attach*.sh`, `test_artifact_cli.sh`,
  `test_registry_lock*.sh`, `test_txn*.sh`, `test_task_commit*.sh`,
  `test_no_unscoped_task_commit.sh`
- `shellcheck` on every edited script.

## Risk

### Code-health risk: medium
- ~37 edits across 16 files, including `lib/registry_lock.sh`, which every
  attach / artifact / fold / sync / pick_own lock path goes through. After
  `registry_lock_acquire`, the *visible* trap text becomes
  `_ait_archive_exit_chain` instead of `registry_lock_release '<dir>'`, so any
  code that inspects the trap mid-run sees the chain. The survey found only
  `txn_chain_exit_trap` (a prepend the chain already handles) and the ledger
  detector (reads at exit, after the chain restores the text). · severity:
  medium · → mitigation: none (pinned in-plan by tests 5a.4/5a.5/5a.9 and the
  lock/txn suites)
- The re-arm composes inside `( )` subshells, unlike the source-time arm, so
  note.sh's in-subshell ledger sections now run the chain at subshell exit.
  That exposed an inherited-directory deletion: a child's cleanup removed the
  parent's directly extracted dir. The fix scopes `_AIT_ARCHIVE_TMPDIR` removal
  to its creating shell. · severity: medium (residual low — creator-scoped
  removal) · → mitigation: none (pinned by tests 5a.8a–8d, incl. the red run
  and the bash 3.2 arm)
- The tripwire's site regex can miss unusual spellings (a trap built in a
  variable or via `eval`) or flag a heredoc line. · severity: low · →
  mitigation: none (planted-fixture self-tests + non-vacuity counts)

### Goal-achievement risk: low
- Only `ait note` gets a real-entry leak probe. The other re-arming scripts are
  covered by the tripwire (every site paired) plus spelling-level composition
  tests, not by running each script on a bundled resolve as the task's
  verification asks. · severity: low (residual — addressed by inline
  post-phase real_entry_leak_probes) · → mitigation: inline post-phase
  real_entry_leak_probes
- `txn_chain_exit_trap`'s prepend hands a status-reading handler the
  prepended handler's status. This is only recorded here, not fixed. No shipped
  prepend sits in front of a status-reading handler today. · severity: low · →
  mitigation: txn_chain_status_preserving_prepend
- Scripts that load archive_utils only through an indented (lazy) source of an
  intermediate lib are outside the scanner's scope. None exist today.
  · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: real_entry_leak_probes | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — only ait note is probed through its real entry point | desc: Red-then-green real-CLI leak probes for aitask_gate.sh (ledger section) and aitask_create.sh child-lock path under a probe TMPDIR
- timing: after | name: txn_chain_status_preserving_prepend | type: bug | priority: low | effort: low | inline_risk: medium | added_complexity: low | addresses: goal-achievement — txn_chain_exit_trap prepend hands a status-reading handler the prepended handler's status | desc: Make txn_chain_exit_trap capture $? before the prepended handler and restore it for the rest of the trap; update t2023 test 13d2's pinned value

## Step 9 (Post-Implementation)

Current-branch profile: commit code (`bug: … (t2032)`) and the plan via
`aitask_task_commit.sh`. Archival is held by the `risk_evaluated` gate per the
workflow.
