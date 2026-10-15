---
Task: t2023_fix_archive_extraction_tmpdir_leak_and_trap_clobber.md
Base branch: main
Output branch: main
---

# t2023 — Archive-extraction temp-dir leak, EXIT-trap clobber, bundled-owner `rm` message

## Context

Three upstream defects surfaced by t2011's review, all in the archive-bundle
tier of task resolution:

1. **Leak.** `_extract_from_archive` (`.aitask-scripts/lib/archive_utils.sh:142`)
   records its `mktemp -d` dir in `_AIT_ARCHIVE_TMPDIR`, but every one of the
   ~70 `resolve_task_file` / `resolve_plan_file` callers runs it inside `$( )`.
   The variable dies with the subshell, and bash runs no EXIT trap there. So the
   parent's `_ait_archive_cleanup` sees an empty variable, and each bundled
   resolve leaks one dir. t2011 measured six leaked dirs in one probe.
2. **Trap clobber.** Sourcing `archive_utils.sh` (via `task_utils.sh`) runs a
   bare `trap _ait_archive_cleanup EXIT` (line 117). That replaces any EXIT
   trap the caller armed first, so tests that arm `trap 'rm -rf "$TMP"' EXIT`
   before sourcing leak their fixture dir. t2011 patched this locally in two
   tests; four more still have it by static scan.
3. **Misleading `rm` refusal.** `ait attach rm` and `ait artifact rm` on a
   bundled owner refuse correctly (no mutation; pinned by the L6 tests). But the
   message comes from the transaction layer: "could not read the git status of
   /tmp/… — refusing to start a transaction whose paths cannot be verified". It
   should say the owner is packed into an archive bundle.

Probed bash facts this design rests on (bash 5.3):
- `$$` inside `$( )` is the parent's PID, and `BASHPID` is the subshell's.
- `trap -p` in a `( )` subshell shows the parent's trap, but that trap never
  fires there.
- Under `set -e`, a failing command inside an EXIT trap aborts the rest of the
  trap and turns `exit 0` into status 1.
- Without `set -e`, the original exit status survives the trap.
- Anything appended after a handler that calls `exit` never runs.
  `ait_ledger_lock_exit_trap` ends with `exit "$rc"` (`lib/ledger_block.sh:171`).
  A probe of an appended composition exited 7 and the tail never ran.
- `(exit N) && :` sets `$?` to N without tripping errexit, because a failing
  non-final command of an `&&` list is exempt.
- Re-arming EXIT from inside the running EXIT handler does not make bash run
  the trap a second time.

## Approach

### 1. `lib/archive_utils.sh` — owner-tagged extraction dirs plus a sweep

The parent cannot learn the dir's *name* across `$( )`, but it can find the dir
by a *tag* it already knows. Changes in the "Temp directory management" block:

- At source time, set per-shell state. It is **initialized only on the first
  source in a shell and kept across a re-source in the same shell**; the tests
  reset `_AIT_ARCHIVE_UTILS_LOADED` and re-source repeatedly. Re-pinning the
  base or forgetting the stored caller handler would orphan dirs already
  created, or silently drop the caller's EXIT cleanup. The review reproduced
  the second case with the earlier snippet.
  ```bash
  if [[ "${_AIT_ARCHIVE_OWNER:-}" != "${BASHPID:-$$}" ]]; then   # first source in this shell
      _AIT_ARCHIVE_OWNER="${BASHPID:-$$}"
      _AIT_ARCHIVE_TMPBASE="${TMPDIR:-/tmp}"
      [[ "$_AIT_ARCHIVE_TMPBASE" == /* ]] || _AIT_ARCHIVE_TMPBASE="$PWD/$_AIT_ARCHIVE_TMPBASE"
  fi
  : "${_AIT_ARCHIVE_CALLER_EXIT_TRAP:=}"   # written ONLY by the arm helper, never reset here
  _AIT_ARCHIVE_TMPDIR=""                   # as today; a dir it named is still swept by its tag
  ```
  - `_AIT_ARCHIVE_OWNER` is the PID of the shell that owns the EXIT trap. The
    `${BASHPID:-$$}` idiom matches `lib/stale_lock.sh:365`. On bash 3.2 (no
    `BASHPID`) it is the process PID, the same in every subshell. That is why
    the sweep below has a 3.2 guard.
  - `_AIT_ARCHIVE_TMPBASE` is `${TMPDIR:-/tmp}` **pinned and made absolute**, so
    a later `cd` cannot move it. Every extraction uses this base, so a later
    TMPDIR change cannot put a dir somewhere the sweep does not look. That
    includes a scoped `f=$(TMPDIR=/x resolve_task_file N)` and an
    export-then-restore around a resolve.
- In `_extract_from_archive`, when `_AIT_ARCHIVE_TMPDIR` is empty, create the
  dir with:
  ```bash
  mktemp -d "${_AIT_ARCHIVE_TMPBASE}/ait-archive.${_AIT_ARCHIVE_OWNER}.XXXXXX"
  ```
  - **Fallback, only when that mktemp fails** (the pinned base was deleted
    after sourcing): use the same tagged template under the extraction-time
    `${TMPDIR:-/tmp}`. Resolution keeps working rather than dying with a
    misleading "No task file found". The exit-time base in the sweep below
    covers this fallback as long as TMPDIR is unchanged at exit.
  - The random suffix and mode 0700 keep the usual mktemp safety.
  - A direct call in the parent still sets and reuses `_AIT_ARCHIVE_TMPDIR`,
    so existing behaviour and the existing tests are kept.
- `_ait_archive_cleanup`:
  - Removes `$_AIT_ARCHIVE_TMPDIR` as today.
  - Then sweeps `<base>/ait-archive.<owner>.*` for each distinct base in
    {`$_AIT_ARCHIVE_TMPBASE`, exit-time `${TMPDIR:-/tmp}`}. The pinned base is
    the primary; the exit-time base exists only to catch the fallback.
  - **The sweep runs only in the shell that owns the tag**, checked by
    `_ait_archive_may_sweep`:
    - with `BASHPID`: `BASHPID == _AIT_ARCHIVE_OWNER`;
    - without it (bash 3.2): `BASH_SUBSHELL == 0`.
    - On bash ≥4 it always holds where the trap fires.
    - On 3.2 it stops a guard-reset re-source inside `( )`, which carries the
      *process* PID as its tag, from deleting dirs the parent still holds. Such
      a subshell only removes its own `_AIT_ARCHIVE_TMPDIR`, as HEAD does.
      Probed by running `unset BASHPID`, which drops the variable's special
      meaning and so stands in for 3.2.
  - It removes an entry only if `-d`, not `-L`, and `-O` (owned by us): never
    another user's dir, never a symlink, never an untagged `tmp.*`.
  - Every `rm` is `|| true`, and the function ends with `return 0`. This
    matters because errexit is live inside EXIT traps (see Context).
- Update the comment block: why a tag rather than a variable, why `$( )` never
  propagates, and why the base is pinned. Update the stale "Must be called
  WITHOUT command substitution" note on `_extract_from_archive`: direct calls
  still share one dir, and `$( )` calls are found by the sweep.

### 2. `lib/archive_utils.sh` — chain onto the caller's EXIT trap instead of replacing it

Textual composition cannot work either way:
- **Appending** is unreachable whenever the caller's handler calls `exit`, as
  `ait_ledger_lock_exit_trap` does.
- **Prepending** destroys the caller's `$?`.
- **Prepending** also makes the ledger's first-command detector
  (`_ait_ledger_exit_trap_is_first`, which parses `trap -p EXIT`) misfire.

So the archive lib wraps the caller's handler instead of concatenating text.
The sequence below was probed against the real `ait_ledger_lock_exit_trap` in
its three spellings:
- bare `exit 42` → cleanup ran, rc 42;
- misuse `my_cleanup; ait_ledger_lock_exit_trap` → cleanup ran, the detector
  warned, rc 1, as it does today;
- explicit `rc=$?; …; ait_ledger_lock_exit_trap "$rc"` → cleanup ran, rc 42.

Replace the bare `trap _ait_archive_cleanup EXIT` with:

```bash
# (_AIT_ARCHIVE_CALLER_EXIT_TRAP is initialized with := in the state block
#  above — NOT reset here, so a same-shell re-source keeps the stored handler)
_ait_archive_exit_chain() {
    local __ait_rc=$? __ait_cur __ait_now              # `__ait_rc=$?` MUST stay first
    _ait_archive_cleanup                               # always returns 0
    # Re-arm the trap as the UNWRAPPED composition would read: the CURRENT
    # trap text (which may carry handlers a later composer such as
    # txn_chain_exit_trap prepended/appended) with our token replaced by the
    # caller's handler -- NOT the caller's text alone, which would tell a
    # first-command detector it ran first after a prepended handler ate $?.
    __ait_cur="$(trap -p EXIT)"; __ait_cur="${__ait_cur#trap -- }"; __ait_cur="${__ait_cur% EXIT}"
    eval "__ait_now=$__ait_cur"                         # unquote bash's own rendering
    case "$__ait_now" in
        *_ait_archive_exit_chain*)
            __ait_now="${__ait_now%%_ait_archive_exit_chain*}${_AIT_ARCHIVE_CALLER_EXIT_TRAP}${__ait_now#*_ait_archive_exit_chain}" ;;
        *)  __ait_now="$_AIT_ARCHIVE_CALLER_EXIT_TRAP" ;;
    esac
    trap -- "$__ait_now" EXIT                          # does not re-run the trap (probed)
    (exit "$__ait_rc") && :                            # restore $? without tripping errexit
    eval "$_AIT_ARCHIVE_CALLER_EXIT_TRAP"              # may `exit`; cleanup already ran
}
_ait_archive_arm_exit_trap() {
    local cur
    if (( ${BASH_SUBSHELL:-0} > 0 )); then             # subshell: trap -p shows the parent's
        trap _ait_archive_cleanup EXIT; return 0       # inactive handler; never trust/compose it
    fi
    cur="$(trap -p EXIT)"
    case "$cur" in *_ait_archive_cleanup*|*_ait_archive_exit_chain*) return 0 ;; esac
    if [[ -z "$cur" ]]; then trap _ait_archive_cleanup EXIT; return 0; fi
    cur="${cur#trap -- }"; cur="${cur% EXIT}"
    eval "_AIT_ARCHIVE_CALLER_EXIT_TRAP=$cur"          # unquote bash's own trap -p rendering
    trap _ait_archive_exit_chain EXIT
}
_ait_archive_arm_exit_trap
```

- **Archive cleanup runs first.** No caller `exit` can skip it.
- **Invariant: the caller's handler sees exactly what it would see in the
  *unwrapped* composition**, meaning the same trap with our token replaced by
  its text.
  - The `$?` it gets is the status our wrapper received. That is the dying
    status, or whatever a handler prepended ahead of us returned, as in the
    unwrapped trap.
  - `trap -p EXIT` shows the substituted current composition. The ledger
    detector therefore reaches the verdict it would reach without the wrapper:
    a bare ledger handler alone is "first", and the same handler after a
    prepended `_txn_exit_trap` is "not first", which warns and exits 1.
  - Its own `exit N` still decides the status.
  - The review showed that restoring only the caller's original text breaks
    this: a bare ledger trap plus a later `txn_chain_exit_trap` exited 0 with
    no warning, where the unwrapped composition exits 1 with one.
  - **Probed against the real `ledger_block.sh` and `txn_snapshot.sh`:**
    3 spellings × {no later composer, `txn_chain_exit_trap _txn_exit_trap`}.
    The substituted re-arm matches the unwrapped composition's exit status and
    warning in all six cases: bare 42 / 1+warn, misuse 1+warn / 1+warn,
    explicit 42 / 0. In every case the cleanup also ran.
  - The explicit-spelling-plus-prepend 0 is the unwrapped behaviour: a prepend
    in front of a status-reading handler loses the status by itself, and the
    wrapper neither causes nor hides that.
- **Compose only in a process's top-level shell** (`BASH_SUBSHELL == 0`, which
  exists since bash 3.0, so 3.2 composes too).
  - In a `( )` subshell, `trap -p` shows the parent's handler, which is not
    active there. Composing would run the parent's `rm -rf "$TMP"` when the
    subshell exits, mid-file.
  - Trusting that display for idempotence would leave the subshell with no
    trap at all.
  - So a subshell always gets its own bare trap. It is still today's clobber,
    but only for a trap the subshell itself armed before its first source.
- **Idempotent, and the stored handler survives.**
  - A same-shell re-source keeps the state block's values. The arm helper then
    finds its own name in `trap -p` and returns, with
    `_AIT_ARCHIVE_CALLER_EXIT_TRAP` intact. The probe confirmed it: sourced
    twice, the caller's cleanup still ran.
  - The substring match is also what prevents recursion. Once a later composer
    has prepended (`_txn_exit_trap; _ait_archive_exit_chain`), a re-source must
    not store that text as the "caller" handler, or the chain would `eval`
    itself. Probed: prepend, then re-source, ran each handler exactly once.
- **Composers that run later still behave.** `txn_chain_exit_trap` prepends onto
  `_ait_archive_exit_chain` the same way it prepends onto any handler. A later
  bare `trap … EXIT` replaces it: that is the deferred reverse clobber, see Out
  of scope.

### 3. `rm` on a bundled owner — refuse before the lock, naming the bundle

- **`lib/task_utils.sh`**, next to `task_file_is_active`: add
  `task_archive_bundle <task_id>`.
  - It echoes the path of the `.tar.zst` / `.tar.gz` bundle holding the task
    file, or nothing.
  - It reuses `_search_numbered_then_legacy` from `archive_utils.sh` with the
    same member patterns `resolve_task_file` uses: `(^|/)t<id>_.*\.md$`, and
    `(^|/)t<p>/t<p>_<c>_.*\.md$` for a child.
  - Keep `${hit%:*}`. It lists the archive but extracts nothing, so it creates
    no temp dir.
- **`aitask_attach.sh` `cmd_remove`** and **`aitask_artifact.sh` `cmd_remove`**,
  right after `resolve_task_file` and before `with_attach_lock`:
  ```bash
  if ! task_file_is_active "$task_id" "$task_file" \
          && [[ "$task_file" != "${ARCHIVED_DIR%/}"/* ]]; then
      local bundle; bundle="$(task_archive_bundle "$task_id")"
      die "ait attach rm: t${task_id} is packed into an archive bundle${bundle:+ (${bundle})} — a bundled record cannot be edited; ls and get still accept it"
  fi
  ```
  - Use the `artifact` wording in the artifact CLI.
  - A loose archived owner (the L4 path) still passes.
  - The `${ARCHIVED_DIR%/}` prefix test is the same one `add` / `create`
    already use, so trailing-slash spellings behave alike.
- Update the comments in `cmd_add` (`aitask_attach.sh` ~240) and `cmd_create`
  (`aitask_artifact.sh` ~247). They still say "(its extraction is outside the
  repo, so the transaction refuses it)"; they should say `rm` refuses a bundled
  owner itself. The help text already states the right scope ("not one packed
  into a .tar.zst bundle") and needs no change.

### 4. Tests

**`tests/test_resolve_tar_zst.sh`** — new cases after Test 13. Each is a
`bash -c` child against a per-case probe `TMPDIR`. Counters stay in the main
shell; no subshell bodies.

- **13b, `$( )` resolve leaves nothing.**
  - Run `f=$(resolve_task_file 77); cat "$f"` and exit.
  - Assert the content was read: the file outlives the `$( )`, so the sweep did
    not fire too early.
  - Assert the probe dir is empty afterwards.
  - Repeat once for `resolve_plan_file` on a bundled plan.
- **13c, an earlier EXIT trap survives sourcing and still runs.**
  - Run `trap 'touch <marker>' EXIT`, then source `task_utils.sh`, then do a
    `$( )` resolve.
  - Assert the marker exists and the probe dir is empty.
- **13d, a terminating caller handler with a nonzero exit.**
  - Run `set -e; trap 'echo "rc=$?" > <f>; exit 7' EXIT`, then source, then do
    a `$( )` resolve, then `exit 3`.
  - Assert three things:
    - `<f>` reads `rc=3`: the caller saw the dying status;
    - the child exit is 7: the caller's own `exit` still decides;
    - the probe dir is empty: archive cleanup ran even though the caller's
      handler exits. HEAD and the rejected append design both fail this.
- **13d2, a differential matrix: wrapped versus unwrapped composition, using
  the real `ledger_block.sh` and `txn_snapshot.sh`.**
  - For each spelling (bare, misuse `my_cleanup; ait_ledger_lock_exit_trap`,
    explicit `rc=$?; …; ait_ledger_lock_exit_trap "$rc"`) and each later
    composer (none, `txn_chain_exit_trap _txn_exit_trap`), run two children
    that differ only in whether `task_utils.sh` is sourced between arming the
    spelling and the composer.
    - **Unwrapped:** `ledger_block.sh` and `txn_snapshot.sh` only.
    - **Wrapped:** additionally `task_utils.sh` plus a `$( )` bundled resolve.
    - Both end in `exit 42`.
  - Assert, for each of the six cells:
    - the wrapped exit status equals the unwrapped one;
    - "ran behind another command" appears in the wrapped output iff it
      appears in the unwrapped output;
    - the wrapped probe dir is empty.
  - Also pin the absolute values the probe measured, so a baseline that drifts
    is caught: bare 42 / 1+warn, misuse 1+warn / 1+warn, explicit 42 / 0.
  - Explicitly assert that **bare + txn prepend never exits 0**. This is the
    false success the review reproduced against the earlier design.
  - Warning text is asserted, not merely a nonzero status, per
    `tests/test_ledger_lock_exit_trap.sh`'s convention.
  - Check first that `ledger_block.sh` and `txn_snapshot.sh` source nothing
    that pulls in `archive_utils.sh`. Otherwise the unwrapped arm is not
    unwrapped, and the test would assert it via
    `declare -F _ait_archive_exit_chain` being absent there.
- **13e, the sweep is scoped.**
  - Plant `ait-archive.<other-pid>.x/`, an untagged `tmp.keep/`, and a
    symlink `ait-archive.<owner>.lnk` pointing at an outside dir.
  - After the child exits, all three, and the symlink's target, still exist.
  - For a deterministic owner, the child plants the entries with its own `$$`
    before it exits.
- **13f, TMPDIR changes after sourcing.** Source with `TMPDIR=<base>`, then:
  - (i) run a scoped `f=$(TMPDIR=<other> resolve_task_file 77)`;
  - (ii) `export TMPDIR=<other2>`, resolve, then restore `TMPDIR=<base>` before
    exit;
  - (iii) fallback: `rm -rf <base>`, export `TMPDIR=<other3>`, resolve, and
    leave it set through exit.

  Assert every resolve read the right content, and that `<base>`, `<other>`,
  `<other2>` and `<other3>` hold no `ait-archive.*` afterwards. (i) and (ii)
  are the case the review probed: they leak under the extraction-time-base
  design.
- **13g, a first source inside `( )` does not run the parent's handler.**
  - The child arms `trap 'touch <parent-marker>' EXIT` without sourcing, then
    runs `( source task_utils.sh; f=$(resolve_task_file 77) )`.
  - Then it checks: the parent marker is absent after the subshell, still
    absent while the parent runs on, and present only after the parent exits.
  - The probe dir is empty after the subshell exits.

**`tests/test_archive_utils.sh`** — a new Group J2, re-source idempotence. Each
case is a `bash -c` child that arms `trap 'touch <caller-marker>' EXIT` and then
sources the lib **twice**, resetting `_AIT_ARCHIVE_UTILS_LOADED` in between as
`source_archive_utils` does.
- **J2a: one source versus two.** Assert, for both counts:
  - `<caller-marker>` exists after the child exits. This is the observable
    effect, and the earlier snippet lost it on the second source;
  - `trap -p EXIT` names `_ait_archive_exit_chain` exactly once;
  - `_AIT_ARCHIVE_CALLER_EXIT_TRAP` still equals the caller's text;
  - a `$( )` extraction made *between* the two sources is swept, so the pinned
    base and the owner survived.
- **J2b: prepend, then re-source.** Source, prepend with the real
  `txn_chain_exit_trap` a handler that touches `<txn-marker>`, then re-source.
  Assert both markers exist and each handler ran exactly once: the handlers
  append to a counter file, which must read one line per handler. That pins
  no recursion and no duplication.
  - **Nonzero-exit ledger variant:** caller `trap 'ait_ledger_lock_exit_trap' EXIT`
    → source → real `txn_chain_exit_trap _txn_exit_trap` → re-source →
    `exit 42`. Assert the exit is **not 0**: it is 1, with the "ran behind
    another command" warning, matching the unwrapped composition. Also assert
    the archive cleanup ran (the probe dir is empty). A re-source must not
    reopen the false-success path.
- **J2c: no prior trap.** Source twice. `trap -p EXIT` is exactly
  `_ait_archive_cleanup`, once.
- **J2d: bash 3.2 path, via `unset BASHPID`.**
  - Arm the caller trap, source, make a `$( )` extraction in the parent, then
    run a guard-reset re-source inside `( )` with its own extraction.
  - The parent's extraction file must still exist after the subshell exits.
    The subshell must not have swept the process-PID tag.
  - After the child exits, both dirs are gone and the caller marker exists.

**Red proof against HEAD.** Copy HEAD's `.aitask-scripts/lib` into the
scratchpad with `git archive HEAD .aitask-scripts/lib | tar -x`. Then run the
13b, 13c and 13d snippets against it and confirm each fails (leftover dir;
marker missing; leftover dir with a terminating handler). Also run 13d against
a scratch copy of the *append* design and confirm it fails. That proves the
test discriminates the rejected design. No stash and no restore in the shared
tree.

**`tests/test_attach_local_backend.sh`** and **`tests/test_artifact_cli.sh`**:
- Drop the local workaround block that t2011 added: the comment, the re-armed
  `trap 'rm -rf "$TMP"' EXIT`, and `export TMPDIR="$TMP/tmpdir"`. With
  chaining and the sweep, both are unnecessary. Keep `outside_repo`.
- L6:
  - Replace `assert_contains … "could not read the git status"` with asserts
    that the message says `is packed into an archive bundle` and names
    `aitasks/archived/_b0/old0.tar.zst`.
  - Keep the no-commit, ledger/manifest and no-task-data-change pins, and the
    `no attachment matching` / `no artifact matching` negative. It now proves
    the refusal is the guard, not a failed lookup.
  - Update the L6 comment: rm is refused before the lock.

### Post-phase (risk mitigations)

1. [trap_composition_sweep] Statically list every script under `.aitask-scripts/`
   and every test under `tests/` that arms `trap … EXIT` *before* sourcing
   `task_utils.sh` or `archive_utils.sh`. Use a small awk over each file that
   compares line numbers: first `trap .* EXIT` versus first
   `source|\. …(task|archive)_utils.sh`. For each hit, run an **execution**
   replica in `bash -c`, not a trap-text check. Arm that file's real handler
   text, with any `rm -rf "$X"` pointed at a scratch dir. Then source the lib,
   do one `$( )` bundled resolve against a probe TMPDIR, and `exit 5`. Check
   three things:
   - the handler's observable effect happened (the scratch dir is gone, or the
     marker exists);
   - the probe dir holds no `ait-archive.*`;
   - the exit status is what the handler alone would produce (5 unless it
     exits explicitly).

   Then run the trap-sensitive suites named under Verification:
   `test_ledger_lock_exit_trap.sh`, `test_gate_lock_characterization.sh`,
   `test_registry_lock.sh`, `test_fold_mark.sh` and `test_yaml_utils.sh`, plus
   the six leak re-measures.

   Record the hit list and the outcome in Final Implementation Notes. Done means
   every hit composes as above and every listed suite passes.

## Out of scope (spawned as the 'after' mitigation `chain_archive_sweep_through_rearmed_traps`)

The reverse clobber stays: a script that runs `trap … EXIT` *after* sourcing
`task_utils.sh` replaces the archive trap, and so does `registry_lock_acquire`.
`registry_lock_release`'s `trap - EXIT` clears it outright.
- Among the scripts that both resolve tasks and arm their own EXIT traps:
  `aitask_gate.sh`, `aitask_note.sh`, `aitask_create.sh` and
  `aitask_verification_followup.sh`.
- They can still leak one dir per *bundled* resolve on the paths where they
  re-arm.
- Fixing it means changing those trap sites (or adding a shared EXIT-handler
  registry), which is a separate change.

A related pre-existing property, observed while probing, belongs to the same
follow-up: `txn_chain_exit_trap` *prepends*, so in front of a status-reading
handler it hands that handler the prepended handler's 0. The explicit ledger
spelling then exits 0 for an `exit 42`, wrapped or not. Recording it in the
mitigation task's description, not fixing it here.

## Verification

- Run each of these individually:
  - `bash tests/test_resolve_tar_zst.sh`
  - `bash tests/test_archive_utils.sh`
  - `bash tests/test_attach_local_backend.sh`
  - `bash tests/test_artifact_cli.sh`
- Trap-composition sweep, for scripts that arm EXIT traps:
  - `bash tests/test_ledger_lock_exit_trap.sh`
  - `bash tests/test_gate_lock_characterization.sh`
  - `bash tests/test_registry_lock.sh`
  - `bash tests/test_fold_mark.sh`
  - `bash tests/test_yaml_utils.sh`
- `shellcheck .aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_attach.sh .aitask-scripts/aitask_artifact.sh`
- **Re-measure leaks.** For each of `test_attach_local_backend.sh`,
  `test_artifact_cli.sh`, `test_label_vocabulary_lib.sh`,
  `test_last_used_labels.sh`, `test_userconfig_writer_collision.sh` and
  `test_xdeps_parser.sh`, run it with `TMPDIR=<fresh probe>` and list what is
  left. Expected: only the intentional `ait-test-cwd-<uid>`.
- **Re-run t2011's probe shape.** Use a scratch legacy repo, with a task that
  has an attachment and an artifact packed into `_b0/old0.tar.zst`. Run
  `ait attach ls/get` and `ait artifact ls/get` with a probe `TMPDIR` and
  expect no `ait-archive.*` / `tmp.*` leftovers. `rm` should refuse with the
  bundle message and change nothing.

## Step 9 (Post-Implementation)

Current-branch profile: no merge. Archive via `aitask_archive.sh 2023` after the
Step 8 review and commit.

## Risk

### Code-health risk: low
- `archive_utils.sh` is sourced by almost every `ait` script through
  `task_utils.sh`. Changing how it installs its EXIT trap at source time changes
  trap composition for every script that armed a trap before sourcing: both
  handlers now run, the caller's first. A mistake here (`$?` clobbered, errexit
  aborting the trap, a duplicated handler) would surface far from this change.
  · severity: low (residual — addressed by inline post-phase
  trap_composition_sweep) · → mitigation: inline post-phase
  trap_composition_sweep
- The sweep deletes by glob, which is irreversible. It is restricted to the
  owner tag plus `-O` plus not-a-symlink, and that restriction is pinned in-plan
  by Test 13e. · severity: low · → mitigation: none (pinned in-plan by Test 13e)
- The wrapper runs the caller's handler through `eval` inside a function, not
  as the trap itself. `FUNCNAME` differs, and `local` becomes legal there. It
  also relies on two bash behaviours: re-arming EXIT inside the running handler
  does not re-run it, and `(exit N) && :` restores `$?` under errexit. Both
  were probed on bash 5.3 and are pinned by execution tests 13c/13d/13d2/13g.
  Subshells keep today's bare trap, and bash 3.2 composes only at top level.
  · severity: low · → mitigation: none (pinned in-plan by Tests 13c, 13d, 13d2,
  13g)
- The wrapper could hide the status-safety checks of handlers that read
  `trap -p` when *later* composers wrap around it. The review reproduced this:
  restoring only the caller's text after a `txn_chain_exit_trap` prepend
  turned a bare ledger trap's exit 42 into a silent 0. The invariant is
  equivalence with the unwrapped composition, re-arming the substituted
  current trap text, and it is pinned differentially, not by expected values
  alone. · severity: medium (residual low — design restores the full
  composition) · → mitigation: none (pinned in-plan by the Test 13d2
  differential matrix and the J2b nonzero-exit ledger variant)
- The library now keeps per-shell state (owner, pinned base, stored caller
  handler) that must survive a same-shell re-source and be re-initialized in a
  new shell. Getting either wrong silently drops the caller's cleanup or
  orphans dirs. The review reproduced the first case against the earlier
  snippet. · severity: low · → mitigation: none (pinned in-plan by Group
  J2a–J2d)

### Goal-achievement risk: medium
- The leak is fixed for every `$( )` resolve whose script keeps the archive EXIT
  trap. But scripts that run `trap … EXIT` *after* sourcing replace it:
  `aitask_gate.sh`, `aitask_note.sh`, `aitask_create.sh`,
  `aitask_verification_followup.sh`, and `registry_lock_acquire` (whose release
  runs `trap - EXIT`). Those scripts can still leak one dir per bundled resolve
  on the paths where they re-arm, so "every caller" is covered but not
  airtight. · severity: medium · → mitigation:
  chain_archive_sweep_through_rearmed_traps
- One TMPDIR case is still unswept. The pinned base must be deleted after
  sourcing (forcing the fallback), *and* TMPDIR must then change again before
  exit. Every other TMPDIR change (scoped override, export-and-restore) lands
  under the pinned base. · severity: low · → mitigation: none (pinned in-plan
  by Test 13f)

### Planned mitigations
- timing: post-phase | name: trap_composition_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — source-time EXIT-trap chaining changes trap composition in every script that armed a trap before sourcing | desc: Statically list scripts/tests arming EXIT before sourcing task_utils/archive_utils, replicate each composed trap, and run the trap-sensitive suites plus leak re-measures
- timing: after | name: chain_archive_sweep_through_rearmed_traps | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement — scripts that re-arm EXIT after sourcing (gate, note, create, verification_followup, registry_lock acquire/release) drop the archive sweep and still leak on bundled resolves | desc: Make EXIT-trap re-arm sites preserve the archive sweep (chain instead of replace/clear, or a shared EXIT-handler registry) without breaking the ledger lock's first-in-trap contract
