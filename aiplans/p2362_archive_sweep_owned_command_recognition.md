---
Task: t2362_archive_sweep_owned_command_recognition.md
Base branch: main
Output branch: main
---

# t2362 — archive sweep: give each installed EXIT handler a stable identity

## Context

`lib/archive_utils.sh` wraps the caller's EXIT trap so its bundled-extraction
sweep runs first. Two of its decisions read the trap text:

- `_ait_archive_wrap_exit_trap` treats any trap that contains
  `_ait_archive_cleanup` or `_ait_archive_exit_chain` as already wrapped.
- `_ait_archive_exit_chain` stores one caller in
  `_AIT_ARCHIVE_CALLER_EXIT_TRAP`.

So a caller trap that only names those functions (quoted data, a comment) is
taken as already wrapped. The re-arm then does nothing, the sweep is dropped,
and bundled extractions leak. That is the defect.

t2332 showed that recognising "our command" by whole command needs real shell
lexing, and every spelling a recogniser misses recurses. Review of the first
draft of this plan (a caller stack with one shared install text) found two
more cases that any fix must keep, both correct on HEAD today:

1. **Exit status / command position.** The trap is
   `C; : '<quoted copy of C>'` around the ledger's no-argument handler, and the
   script exits 42. HEAD returns 42. Rewriting the last occurrence of `C` hits
   the quoted copy. The ledger's first-command detector then sees the chain
   first and returns 1.
2. **Save and restore.** Wrap H, `saved=$(trap -p EXIT)`, prepend T, re-arm,
   `eval "$saved"`, re-arm. Only H may run. With one install text shared by
   every level, the restored text cannot say which level it was, so T still
   runs.

## Design: one id per installed handler

Every wrap allocates the next id `k` and installs
`_ait_archive_exit_chain --ait-id=<k> "$@"`. `CALLERS[k]` holds the text that
wrap found. Entries are never modified, reused or freed.

- **The id is the identity, carried by the executing occurrence.** When the
  chain is invoked, it learns which handler is executing from its own first
  argument, never from the trap text. So a saved and restored trap text runs
  exactly the level it was saved at (case 2). The level needs no stack
  bookkeeping, and `registry_lock`'s plain save, then restore, then re-arm is
  correct without any new archive API.
- **Ownership is byte-exact.** A re-arm is a no-op only when the trap text is
  `_ait_archive_cleanup`, or exactly the install text of an allocated id
  (parsed as a canonical decimal, rebuilt and compared). Anything else,
  quoted mentions and comments included, gets a new id. That fixes the leak.
- **No recursion, by construction.** `CALLERS[k]` was captured before `k`
  existed, so it can name only ids below `k`. The chain enforces this: a call
  nested in this shell must carry an id strictly below the one running, and an
  unallocated id runs nothing. Any hand-crafted text therefore terminates.
- **Display rewrite (the `trap -p` the caller's handler reads).** This is
  display only; no ownership or recursion decision depends on it. Its one
  safety property: **the display shows the caller's text as the first command
  only when the trap text's first command is provably a chain call carrying
  the executing id.** In every other case it keeps a non-empty head, so the
  ledger's first-command guard reports a lost status as a failure and never
  as success.

  The ledger detector (`_ait_ledger_exit_trap_is_first`) strips leading
  `[:space:]`, then needs its name followed by end, `[:space:]`, `;`, `&`,
  `|`, `)` or `'`. The rules apply in order, with D = the current display
  text:
  1. **Leading call.** After leading `[:space:]`, D's first words are
     - `_ait_archive_exit_chain`,
     - one or more `[:blank:]` (never a newline, which would end the command),
     - and `--ait-id=<k>` for the executing `k`,
     - then optionally `[:blank:]+"$@"`,
     - then a boundary (end, `[:space:]`, `;`, `&`, `|`, `)`).

     → replace that leading span with the caller text. The first command is a
     call with this id, and it ran first. Case 1
     (`C; : '<copy of C>'`) renders `ait_ledger_lock_exit_trap; : '…'` and
     returns 42. A leading call respaced by hand (`… --ait-id=0  "$@"`) still
     matches, as HEAD's bare-name splice does. A text that is exactly the
     token is the degenerate case of this rule.
  2. **Canonical token elsewhere.** D contains the exact token
     `_ait_archive_exit_chain --ait-id=<k> "$@"` → replace its **last**
     occurrence. That is the shape every prepend produces. D does not start
     with the call, so the head stays non-empty and the verdict is "not
     first".
  3. **Position unknown.** D has a non-blank character, but the call cannot
     be located textually (a respaced non-leading call, or an indirect one)
     → D, a newline, then the caller text. It keeps the head and never
     claims first. The review counterexample (`:; …--ait-id=0  "$@"`) lands
     here and stays a warned exit 1, as on HEAD.
  4. **Blank D** → the caller text. Nothing precedes the call in the trap.

  For the legacy bare spelling (no id), rule 1 matches the bare name followed
  by a boundary, and rule 2's token is the bare name.

  The verdict is fail-safe in every shape. The full text mis-renders only when
  a non-leading call is followed by a quoted copy of its own canonical token
  (rule 2 then replaces the copy). Its head is kept even then, so the verdict
  is unaffected.
- **Positional parameters.** The chain shifts `--ait-id=<k>` off. Its
  `"$@"`, which every nested `… "$@"` inside an eval'd entry sees, is the
  script's.
- **Hand-written bare `_ait_archive_exit_chain` (no id, M-bs).** It runs the
  entry just below the running id when nested in this shell, else the newest
  entry. Its display token is the bare name.
- **`_AIT_ARCHIVE_CALLER_EXIT_TRAP`** stays as a read-only mirror of
  `CALLERS[0]`, the first caller the sweep wrapped in this shell, for tests and
  diagnostics. It is written once, when id 0 is allocated, so it cannot drift.
- **Growth.** One short string per non-owned re-arm (a registry_lock
  acquire is one). Ids cannot be reused, because a saved trap text may still
  name an old one (case 2).

Rejected alternatives:

- **Bookkeeping in the composition helpers** (`txn_chain_exit_trap`,
  `_tg_prepend_exit_trap`). It covers only those two composers, not
  hand-written prepends or the save/restore case. It also couples
  `txn_snapshot.sh` and the test guard to archive_utils.
- **`declare -f` parsing.** It evals trap text at re-arm time and forks on
  every re-arm.
- **A shared-text caller stack** (the first draft). It fails both cases above.

## Implementation

### 1. `.aitask-scripts/lib/archive_utils.sh`

- **State.** Initialise the following when unset, so a same-shell re-source
  keeps them:
  - `[[ -n "${_AIT_ARCHIVE_CALLERS+x}" ]] || _AIT_ARCHIVE_CALLERS=()`;
  - `: "${_AIT_ARCHIVE_EXIT_RUNNING:=}"` and
    `: "${_AIT_ARCHIVE_EXIT_RUNNING_SHELL:=}"` (the id the chain is running,
    scoped to `"${BASHPID:-$$}:${BASH_SUBSHELL:-0}"`, so a `( )` child that
    re-armed starts fresh);
  - keep `_AIT_ARCHIVE_CALLER_EXIT_TRAP`, now the mirror.

  Replace `_AIT_ARCHIVE_CHAIN_CMD` with `_AIT_ARCHIVE_CHAIN_PFX`
  (`_ait_archive_exit_chain --ait-id=`) and `_AIT_ARCHIVE_CHAIN_SFX`
  (` "$@"`).
- **Helpers:**
  - `_ait_archive_is_id <s>`: a canonical decimal (`0`, or no leading zero
    and digits only), via globs rather than `=~` (bash 3.2 quoting);
  - `_ait_archive_owned_text <t>`: 0 iff `t` is `PFX<id>SFX` for an
    allocated id;
  - `_ait_archive_lead_span <text> <id|"">`: 0 plus `_AIT_ARCHIVE_LEAD` (the
    matched leading span) iff display rule 1 holds. It uses pure parameter
    expansion: strip `[:space:]`, then `[:blank:]` runs between words, then a
    boundary check on the remainder (no regex, no fork);
  - `_ait_archive_splice <text> <id|""> <repl>` → `_AIT_ARCHIVE_SPLICED`
    (display rules 1–4).
- **`_ait_archive_wrap_exit_trap`:**
  - empty trap → install the bare cleanup;
  - unquote once with the existing idiom;
  - `_ait_archive_cleanup` or `_ait_archive_owned_text` → return;
  - otherwise `id=${#_AIT_ARCHIVE_CALLERS[@]}`, store the text, set the mirror
    when `id == 0`, and install `PFX$id SFX`.
- **`_ait_archive_exit_chain`:**
  - `local __ait_rc=$?` first, then `_ait_archive_cleanup`;
  - parse an optional `--ait-id=` and shift it off, or apply the bare-name
    rule;
  - refuse (`return 0`) a non-id value, an unallocated id, or a nested id not
    below the running one;
  - read and unquote `trap -p`, splice with the executing token, then
    `trap -- … EXIT`;
  - set the running id and shell, `(exit "$__ait_rc") && :`, and `eval` the
    entry;
  - capture its status, restore the previous running id, and return that
    status. Under errexit a failing eval still exits first, as today.
- **Comments.** Rewrite the chain, wrap and arm headers:
  - drop "recognition is still by SUBSTRING, t2362 owns that";
  - state the id, byte-exact ownership, the strictly-decreasing guard, why ids
    are never reused (case 2), the display rules and the one mis-render.

  `ait_archive_rearm_exit_trap` and `_ait_archive_arm_exit_trap` keep their
  contracts. A subshell arm still installs the bare cleanup.

### 2. `.aitask-scripts/lib/registry_lock.sh`

- **`_registry_lock_arm_exit_trap`, chain mode.** When the archive lib is
  loaded, call `ait_archive_rearm_exit_trap` **before**
  `_registry_lock_save_caller_exit_trap`. So a raw caller trap gets its own
  archive id first, the saved text is always archive-owned, and
  `CALLERS[0]` is the caller rather than our chain. The old release re-wrapped
  the caller anyway; this only does it earlier.
- **`_registry_lock_save_caller_exit_trap`.** Delete the archive peel block
  and save the unquoted text **verbatim**. Restoring it later re-selects the
  same archive id. Keep the own-command guard (`_registry_lock_owned_tail`;
  case 21's table still covers it). Rewrite the comment.
- **`_registry_lock_restore_exit_trap`.** Unchanged.
- **`_registry_lock_exit_chain`.** Replace the `owned_tail` + `join` display
  rewrite with `_registry_lock_splice <text> <cmd> <repl>` → `_RL_SPLICED`.
  - Use the same four rules and the same safety property as the archive
    splice. Rule 1 matches `_registry_lock_exit_chain`, then optional
    `[:blank:]+"$@"`, then a boundary. Rule 2's token is
    `_registry_lock_exit_chain "$@"`. Rule 3 keeps D and then the saved text
    on a new line (D alone when nothing was saved).
  - With an empty `repl`, rule 2's head loses a trailing `"; "`, so `t; cmd`
    still renders `t`.
  - This fixes the missed `t; <cmd>;` shape. Keep both
    `# archive-sweep: exit-handler` markers.
  - The helper is duplicated on purpose: registry_lock loads without
    archive_utils, and 63 test scaffolds copy archive_utils.sh alone. Each
    comment names its twin.
- **`_registry_lock_join`.** Delete it; it becomes unused, and no test
  references it.
- **Header.** The "Caller EXIT traps" last bullet changes: the sweep stays
  outermost because the saved text is an archive id; nothing peels by text.
- **`registry_lock_release`.** Keep its tail byte-identical
  (`tests/test_fold_mark.sh`'s injector anchors on it).

### 3. Tests

**`tests/test_archive_rearm_exit_trap.sh`**

- **Pinned spellings.** Replace `CH` with
  `ch() { printf '_ait_archive_exit_chain --ait-id=%s "$@"' "$1"; }`.
  - Cases 1, 7 and 9 expect `$(ch 0)`.
  - The M `want_trap` column: none → `_ait_archive_cleanup`; plain, chain and
    ledger → `ch 0`; txn and tg → `ch 1` (their prepend gets id 1 at
    acquire); noarch → `h`.
  - P, R-term, M-bs and cases 2-8 and 10 stay unchanged and must stay green.
    No other assertion of theirs pins the chain text.
- **M-lit** (task requirement):
  - assert `LEFT == 0` in both flows;
  - flow a: `TRAP:` becomes `$(ch 0)`, and add
    `echo "STORED:$_AIT_ARCHIVE_CALLER_EXIT_TRAP"`, asserted verbatim as the
    `rmdir …` text;
  - rewrite the comment (no more "known defect owned by t2362").
- **New block O (t2362).** Fixtures build their shapes from the actually
  installed text: read back with `trap -p EXIT` and unquoted (`now`), or saved
  whole with `saved=$(trap -p EXIT)`. So each one runs unchanged against HEAD
  and the candidate. Every run asserts:
  - the RC;
  - no `maximum function nesting` in OUT;
  - the H/T/X counts via `m_count`;
  - `LEFT == 0`, except where noted;
  - no lock dir left.
- **O-status** (the review cases on command position). Every variant holds
  a real ledger lock, as `ledger_case` does, and starts with
  `trap 'ait_ledger_lock_exit_trap' EXIT; ait_archive_rearm_exit_trap`. Then
  it installs the variant's trap,
  `ait_archive_rearm_exit_trap`, and `exit 42`. `sp` is the installed text
  with the single blank before its final `"$@"` doubled:
  `sp="${now% \"\$@\"}  \"\$@\""`. Built from `now`, it means the same
  spelling change against HEAD's text and the new one.

  | variant | trap installed | expect |
  |---|---|---|
  | `quoted` (case 1) | `$now; : '$now'` | RC 42, no warning |
  | `nonlead` (the counterexample) | `:; $sp` | RC 1, the first-command warning present |
  | `lead` | `$sp` | RC 42, no warning |

  Every variant also expects the ledger lock released and `LEFT == 0`.
  `nonlead` is the non-leading counterpart of `quoted`. `lead` pins rule 1's
  blank tolerance. All three are correct on HEAD (42 / 1 / 42), so they are
  regressions by design.
- **O-saverestore** (review case 2):
  - `trap 'h' EXIT; ait_archive_rearm_exit_trap; saved=$(trap -p EXIT)`;
  - then `txn_chain_exit_trap t; ait_archive_rearm_exit_trap`;
  - then `eval "$saved"; ait_archive_rearm_exit_trap; exit 0`.
  - Expect H=1 and T=0.
  - Variant `hand`: the same, but with a hand-written prepend
    `trap -- "t; $now" EXIT` in place of the txn helper.
- **O-comment and O-lit (direct re-arm):**
  - O-comment: from no trap, `trap -- "h # docs; $now" EXIT; ait_archive_rearm_exit_trap`
    (here `now` is the installed bare cleanup).
  - O-lit: `trap 'rmdir "$D/_ait_archive_cleanup" "$D/_ait_archive_exit_chain" && echo H >> "$MARK"' EXIT; ait_archive_rearm_exit_trap`.
  - Expect H=1, `STORED:` verbatim and `TRAP:` = `$(ch 0)`. O-lit also
    expects both dirs removed.
- **O-shape × lock:**
  - shapes `semi` (`$now;`), `nl` (`t`, newline, `$now`) and `pfx`
    (`t; $now;`), each from `trap 'h' EXIT; ait_archive_rearm_exit_trap`;
  - × with or without a re-arm after the re-install;
  - × flow `a` (acquire, release, exit 0) or `b` (acquire, exit 0 while
    held).
  - Expect RC 0, H=1, and T=0 for semi and 1 otherwise. That is 12 runs.
- **O-resrc:**
  - `trap h; ait_archive_rearm_exit_trap; txn_chain_exit_trap t`;
  - then a guard-reset re-source of archive_utils.sh;
  - then acquire, with flow a or b.
  - Expect H=1 and T=1.
- **O-hold:**
  - `trap h; ait_archive_rearm_exit_trap`, then acquire;
  - during the hold, `clear` (`trap - EXIT; ait_archive_rearm_exit_trap`) or
    `replace` (`trap x EXIT; ait_archive_rearm_exit_trap`);
  - then release and exit 0.
  - Expect H=1, X=0, and post-release `TRAP:` = `$(ch 0)`.
- **O-rldisp (registry_lock's display, held, prefix plus terminator).** The
  caller trap is `echo H >> "$MARK"; trap -p EXIT >> "$MARK"`.
  - `noarch` (libs=noarchive): acquire, read back `now` (the rl command),
    `trap -- "t; $now;" EXIT`, exit 0.
  - `arch`: the caller trap and a re-arm, then acquire, read back `now`, then
    `trap -- "t; $now;" EXIT; ait_archive_rearm_exit_trap`, exit 0.
  - Both expect the recorded line
    `trap -- 't; echo H >> "$MARK"; trap -p EXIT >> "$MARK";' EXIT`,
    with H=1 and T=1.
- **O-self (the recursion guard):**
  - `trap h; ait_archive_rearm_exit_trap` (id 0);
  - then `trap -- '_ait_archive_exit_chain --ait-id=1 "$@"' EXIT; ait_archive_rearm_exit_trap`.
    This text names an id that does not exist yet, so it is pushed as id 1 and
    names itself.
  - exit 0.
  - Expect RC 0, no nesting error, H=0 (unreachable from this text), and
    LEFT 0.
- **Header case list.** Update it (M-lit wording, block O).

**`tests/test_archive_utils.sh`.** J2a's `TRAP:` expectation becomes
`--ait-id=0` (both rows, since the second source is a no-op). J2b, J2c and
the rest stay unchanged.

**`tests/test_registry_lock.sh`.** Cases 15-21 stay unchanged (no archive
lib; case 21 still covers `owned_tail`).

### Pre-phase (risk mitigations)

1. [baseline_suites] Before editing anything, run these on the unmodified tree
   and record each suite's pass/fail counts. Note any failure there as a
   pre-existing baseline.
   - `tests/test_archive_rearm_exit_trap.sh`
   - `tests/test_archive_utils.sh`
   - `tests/test_registry_lock.sh`
   - `tests/test_resolve_tar_zst.sh`
   - `tests/test_ledger_lock_exit_trap.sh`
   - `tests/test_txn*.sh`
   - `tests/test_merge_lock*.sh`
   - `tests/test_pick_own*.sh`
   - `tests/test_projects_lock*.sh`
   - `tests/test_gates_sync_registry.sh`
   - `tests/test_fold*.sh`
   - `tests/test_gate_lock_characterization.sh`
   - `python3 tests/test_archive_rearm_tripwire.py`

   Also run block O alone against the unmodified libs, to record its HEAD
   verdicts before any edit.

### Post-phase (risk mitigations)

1. [prefix_controls] In a scratch copy of `.aitask-scripts/` plus the updated
   test file (never stash or restore in the shared tree), run the test file
   against each of the following. Classify every failing assertion, and record
   the results in Final Implementation Notes.
   - (a) HEAD's `archive_utils.sh` and `registry_lock.sh`. Expected to fail:
     - the pinned `--ait-id` spellings (expected);
     - O-comment, O-lit and M-lit (LEFT, STORED, TRAP);
     - O-shape (h lost behind a missed tail);
     - O-rldisp (prefix dropped).

     Expected to pass, because they guard current behaviour: O-status,
     O-saverestore, O-resrc and O-hold.
   - (b) Mutant: the wrap's substring `case` is restored before the exact
     check. O-comment, O-lit and M-lit fail.
   - (c) Mutant: display rule 1 removed (the first draft's always-last rule).
     O-status[quoted] fails (exit 1 plus the warning).
   - (c2) Mutant: rule 3 replaced by "the caller text alone" (the second
     draft's fallback). O-status[nonlead] fails (exit 0, no warning: a lost
     status reported as success).
   - (c3) Mutant: rule 1 matches only the exact canonical token (no blank
     tolerance). O-status[lead] fails (exit 1 plus the warning).
   - (d) Mutant: the chain ignores its id and runs the newest entry (one shared
     identity). O-saverestore fails (T runs).
   - (e) Mutant: `_registry_lock_exit_chain` display without the splice
     (exact match or `saved` only). O-rldisp fails.
   - (f) Mutant: the strictly-decreasing guard removed, run under
     `timeout 60`. O-self fails (nesting limit or timeout).

## Verification

- Every baseline suite, re-run. The counts must equal the baseline plus the
  new assertions; the pinned-spelling updates keep their counts. No new
  failures.
- `bash tests/run_shell_test.sh tests/test_archive_rearm_exit_trap.sh`: no
  TMPDIR leftovers.
- `shellcheck .aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/registry_lock.sh tests/test_archive_rearm_exit_trap.sh`.
- `python3 tests/test_archive_rearm_tripwire.py`. archive_utils.sh is exempt.
  registry_lock's new re-arm call is the guarded form, and its exit-chain
  `trap` lines keep the exit-handler marker.
- Commit:
  `bug: Give each archive-sweep EXIT handler a stable id instead of matching trap text (t2362)`.

## Step 9 (Post-Implementation)

Current-branch work on `main`. Commit the code by path. Commit the plan with
`./.aitask-scripts/aitask_task_commit.sh`. Then archive per task-workflow
Step 9.

## Risk

### Code-health risk: medium
- `archive_utils.sh` arms the EXIT trap of every process that sources `task_utils.sh`. Changing the wrap/chain semantics could drop or double-run callers' handlers framework-wide · severity: medium (residual: bounded by the before/after suite comparison) · → mitigation: inline pre-phase baseline_suites
- registry_lock now saves verbatim, re-arms before saving, and rewrites its display. A missed flow (re-source, a hold-time clear or replace, die while held) would lose or double-run a caller · severity: medium (residual: every named flow has an expected-result test, and mutants (b)-(f) show the tests detect each broken rule) · → mitigation: inline post-phase prefix_controls
- The display rewrite feeds the ledger's first-command guard. A rule that claimed "first" wrongly would turn a lost status into a silent success · severity: medium (residual: one stated safety property, "first" only for a provable leading call; modelled against the real `_ait_ledger_exit_trap_is_first` on the quoted, nonlead, lead, prepend and exact shapes; pinned by O-status and mutants c/c2/c3) · → mitigation: inline post-phase prefix_controls
- The splice helper is duplicated in two libs, and the copies could drift · severity: low · → mitigation: none (deliberate, to keep each lib standalone; each comment names its twin)

### Goal-achievement risk: low
- New tests could pass on the old code and prove nothing · severity: low (residual: each test's HEAD verdict is recorded; the two review cases are regressions by design) · → mitigation: inline post-phase prefix_controls
- The installed trap text changes spelling (`--ait-id=<k>`), so any out-of-tree consumer that pins `_ait_archive_exit_chain "$@"` would break · severity: low (a repo-wide grep found pins only in the two test files updated here) · → mitigation: none
- No bash 3.2 is available to exercise the new code on the oldest supported shell · severity: low · → mitigation: none (indexed arrays, `${#a[@]}`, `${s:i:1}` and glob-based id checks are all bash 3.x)

### Planned mitigations
- timing: pre-phase | name: baseline_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: framework-wide EXIT-trap regressions | desc: run every trap-composition and lock-caller suite on the unmodified tree first, and record the baseline counts plus block O's HEAD verdicts
- timing: post-phase | name: prefix_controls | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tests that pass on the old code; unpinned rules (position, identity, recursion guard) | desc: run the updated test file against HEAD's libs and five mutants in a scratch copy, and record which assertions fail
