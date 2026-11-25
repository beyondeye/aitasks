---
Task: t2332_archive_exit_chain_args_and_substring_match.md
Base branch: main
Output branch: main
---

# t2332 — archive sweep EXIT chain: forward `"$@"` (defect 1); defer substring matching (defect 2)

## Context

`lib/archive_utils.sh` wraps a caller's EXIT trap so the bundled-extraction
sweep runs first. t2322 found two defects:

1. **Positional parameters lost.** The chain is installed as a bare
   `trap _ait_archive_exit_chain EXIT` (archive_utils.sh:263) and evals the stored
   caller text inside the function, whose `$@` is empty. A caller handler reading
   `$1` dies with "unbound variable" under `set -u`. Because the sweep wraps
   registry_lock's chain from outside, this also defeats registry_lock's own
   `"$@"` fix whenever the sweep is armed.
2. **Substring recognition.** The idempotence check (:256) and the chain's trap
   rewrite (:222) match the sweep's function names as substrings, so a caller trap
   whose quoted data names them is treated as "already ours" and the sweep is
   dropped (an extraction dir leaks).

**Scope decision (user, after two plan-review rounds):** fix defect 1 only and
**defer defect 2** to a follow-up task. The reviews showed that recognising
"our command" in trap text by whole command needs real shell lexing. Separators
(`;`, newline), trailing terminators and comments each produced a miss, and a
miss makes the chain store itself as its own caller: it recurses and the
caller's handler is lost. The substring check's failure mode is benign by
comparison (a skipped sweep leaks a temp dir in rare quoted/comment shapes). So
the recursion-safe substring check stays, made aware of the new chain text, and
the follow-up carries the design analysis: a caller stack, or bash's own parser
via `declare -f`.

## Implementation

### Pre-phase (risk mitigations)
1. [baseline_suites] Before editing, run on the unmodified tree and record
   pass counts: `tests/test_archive_rearm_exit_trap.sh`, `tests/test_archive_utils.sh`,
   `tests/test_registry_lock.sh`, `tests/test_resolve_tar_zst.sh`,
   `tests/test_ledger_lock_exit_trap.sh`, `tests/test_txn*.sh`,
   `tests/test_merge_lock.sh`, `tests/test_pick_own.sh`,
   `tests/test_projects_lock_on_die.sh`, `tests/test_gates_sync_registry.sh`,
   `tests/test_fold*.sh`, and `python3 tests/test_archive_rearm_tripwire.py`
   (skip any that does not exist; note pre-existing failures as baseline).

### 1. `.aitask-scripts/lib/archive_utils.sh`

- New constant beside the globals:
  ```bash
  # The sweep chain's trap text, the ONE value it is installed from. "$@"
  # expands in the exit context, so the caller's text, eval'd inside the
  # function, keeps $1/$#/"$@" (t2332; twin of _REGISTRY_LOCK_CHAIN_CMD).
  _AIT_ARCHIVE_CHAIN_CMD='_ait_archive_exit_chain "$@"'
  ```
- `_ait_archive_wrap_exit_trap`: install with
  `trap -- "$_AIT_ARCHIVE_CHAIN_CMD" EXIT` (was `trap _ait_archive_exit_chain EXIT`).
  The substring idempotence `case` is **unchanged** — `*_ait_archive_exit_chain*`
  also matches the new text, so a re-source / re-arm stays a no-op.
- `_ait_archive_exit_chain`: the trap-text rewrite must replace the **whole
  installed command**, or the caller's text would be shown as `h "$@"`. Use:
  ```bash
  case "$__ait_now" in
      *"$_AIT_ARCHIVE_CHAIN_CMD"*)
          __ait_now="${__ait_now%%"$_AIT_ARCHIVE_CHAIN_CMD"*}${_AIT_ARCHIVE_CALLER_EXIT_TRAP}${__ait_now#*"$_AIT_ARCHIVE_CHAIN_CMD"}" ;;
      *_ait_archive_exit_chain*)      # a hand-written bare spelling
          __ait_now="${__ait_now%%_ait_archive_exit_chain*}${_AIT_ARCHIVE_CALLER_EXIT_TRAP}${__ait_now#*_ait_archive_exit_chain}" ;;
      *)  __ait_now="$_AIT_ARCHIVE_CALLER_EXIT_TRAP" ;;
  esac
  ```
  Keep `local __ait_rc=$?` first, `trap -- "$__ait_now" EXIT`,
  `(exit "$__ait_rc") && :`, and the final `eval` (it now sees the forwarded
  positional parameters). Update the header comment: add a "positional
  parameters" bullet; note recognition is still by substring and why (pointer
  to the follow-up task).

### 2. `.aitask-scripts/lib/registry_lock.sh`

- `_registry_lock_save_caller_exit_trap`: the archive peel must recognise the new
  installed text. Order: `_ait_archive_cleanup` → `"$_AIT_ARCHIVE_CHAIN_CMD"` →
  bare `_ait_archive_exit_chain` (a hand-written spelling, kept so the existing
  M-bs rows still peel). Inside the existing `declare -F ait_archive_rearm_exit_trap`
  guard, so the constant is defined. Update the comment block (~line 322).

### 3. Tests: update pinned trap text

`trap -p` now renders `trap -- '_ait_archive_exit_chain "$@"' EXIT`:
- `tests/test_archive_rearm_exit_trap.sh`: cases 1, 7, 9; the M matrix's
  `want_trap` column (define `CH='_ait_archive_exit_chain "$@"'` and use it in
  the spec rows). M-bs stays as is (bare hand-written spelling, still supported).
- `tests/test_archive_utils.sh` J2a: the `TRAP:` expectation.
- `tests/test_registry_lock.sh` case 21 is a pure-string recogniser table and
  stays unchanged.

### 4. Tests: new regressions (`tests/test_archive_rearm_exit_trap.sh`)

- **P: positional parameters.** The body runs `set -- alpha "b c"`, then
  `trap 'echo "ARGS:$#:$1:$2" >> "$MARK"; trap -p EXIT >> "$MARK"' EXIT`, then
  one variant:
  - `direct`: `ait_archive_rearm_exit_trap; exit 4`
  - `lock-a`: acquire, release, `exit 4`
  - `lock-b`: acquire, then `exit 4` while held
  - `wlock-a` / `wlock-b`: the same two flows, but with
    `ait_archive_rearm_exit_trap` run **before** the acquire. The caller is
    then archive-wrapped when the lock is taken, so registry_lock's peel of the
    `"$@"` chain command is actually exercised. In the raw `lock-*` variants
    there is nothing to peel.
  - `txn`: re-arm plus `txn_chain_exit_trap t`, then `exit 4`
  
  Each variant asserts:
  - RC is 4;
  - MARK line 1 is exactly `ARGS:2:alpha:b c`, written once;
  - MARK's `trap -p` line shows the caller's own text, with no stray `"$@"` (in
    `txn` it also has the prepend head);
  - OUT has no "unbound variable";
  - `LEFT == 0` and the lock dir is gone.
  
  `run_case` already runs under `set -uo pipefail`.
- **R-term: re-arm idempotence over the shapes the review raised.** These are
  built from the **actually installed** trap text, so the same fixture runs
  against HEAD and the candidate: `cur=$(trap -p EXIT); cur=${cur#trap -- };
  cur=${cur% EXIT}; eval "now=$cur"`. The variants:
  - `trap -- "$now;" EXIT`
  - `trap -- "t"$'\n'"$now" EXIT`
  - `trap -- "t; $now;" EXIT`
  
  Each one starts from `trap 'h' EXIT; ait_archive_rearm_exit_trap`, then
  re-arms again and `exit 0`. Assert:
  - RC 0;
  - H ran exactly once, and T exactly once where present;
  - `STORED:` is still `h`;
  - `LEFT == 0`;
  - RC < 128, and OUT has no "maximum function nesting".
  
  These pin the substring rule's recursion safety and must pass on HEAD too.
- **M-lit**: keep it as is. Reword its comment to name the follow-up task as
  the owner of the missing LEFT assertion.
- Update the file's header case list (P, R-term).

### 5. Follow-up task (created after approval, before the code commit)

`./.aitask-scripts/aitask_create.sh --batch` with: type bug, priority medium,
effort medium, labels `bash_scripts,shell`, anchor 2290,
`followup_kind: upstream_defect`. The name is something like
`archive_sweep_owned_command_recognition`. The body covers:
- defect 2 as stated in t2332;
- the reproduced shapes, each of which breaks text-based whole-command
  recognition: newline separator (recursion), trailing `;` (recursion),
  `# comment; _ait_archive_cleanup` (false positive, leak), and the
  registry_lock tail rewrite missing `t; <cmd>;`;
- the two candidate designs:
  - **caller stack:** push on an unrecognised re-arm; a nested call runs the
    next-older caller; needs an archive-owned unwrap/restore API for
    registry_lock's save/restore;
  - **bash's own parser:** `declare -f` normalisation of a throwaway function;
    carries an eval-at-re-arm injection risk;
- the requirement that the eventual fix adds expected-result tests (not twin
  differential tests) and the M-lit LEFT assertion.

Reference the new id in the M-lit comment and the archive_utils comment.

### Post-phase (risk mitigations)
1. [prefix_controls] Run a pre-fix control and mutants, each in a scratch copy of
   `.aitask-scripts/` + `tests/` (never stash or restore in the shared tree):
   - (a) HEAD's `archive_utils.sh` + `registry_lock.sh` with the new tests: P
     fails (unbound `$1` / no ARGS line) and R-term passes. Classify each
     assertion.
   - (b) Mutant: install `trap _ait_archive_exit_chain EXIT` (no `"$@"`). P
     fails.
   - (c) Mutant: the chain rewrite without the `"$_AIT_ARCHIVE_CHAIN_CMD"`
     branch. P's `trap -p` assertion fails (`… "$@"` left in the text).
   - (d) Mutant: the registry_lock peel without the CMD branch. P
     `wlock-a`/`wlock-b` and the M matrix's already-wrapped rows (chain, txn,
     tg, ledger) fail. The raw `lock-*` variants are expected to pass, since
     they have no archive layer to peel.
   
   Record the results in Final Implementation Notes.

## Verification

- Re-run every baseline suite from the pre-phase. Counts must equal the
  baseline plus the new assertions, with no new failures.
- `bash tests/run_shell_test.sh tests/test_archive_rearm_exit_trap.sh`: no
  TMPDIR leftovers.
- `shellcheck .aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/registry_lock.sh`.
- Commit: `bug: Forward "$@" through the archive sweep's EXIT chain (t2332)`.

## Step 9 (Post-Implementation)

This is current-branch work on `main`. Commit the code; commit the plan with
`./.aitask-scripts/aitask_task_commit.sh`; then archive per task-workflow
Step 9.

## Risk

### Code-health risk: medium
- `archive_utils.sh` arms the EXIT trap of every process that sources `task_utils.sh`; a mistake in the chain silently drops callers' handlers framework-wide · severity: medium (residual: the change is now confined to the install text and one rewrite branch; the baseline comparison bounds it) · → mitigation: inline pre-phase baseline_suites

### Goal-achievement risk: medium
- Defect 2 (substring false positive → leaked extraction dir) is deliberately left unfixed; t2332 delivers half its stated scope · severity: medium · → mitigation: none (user decision; follow-up task created with the design analysis)
- New regressions might also pass on the old code, proving nothing · severity: low · → mitigation: inline post-phase prefix_controls

### Planned mitigations
- timing: pre-phase | name: baseline_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: framework-wide EXIT-trap regressions | desc: run all trap-composition and lock-caller suites on the unmodified tree first and record the baseline
- timing: post-phase | name: prefix_controls | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tests that pass on the old code | desc: run new tests against HEAD's libs and three mutants in a scratch copy; record which assertions fail

## Final Implementation Notes
- **Actual work done:** `lib/archive_utils.sh` installs the sweep chain from
  `_AIT_ARCHIVE_CHAIN_CMD='_ait_archive_exit_chain "$@"'`, so the caller's text,
  eval'd inside the function, keeps the script's positional parameters. The
  chain's `trap -p` rewrite replaces the whole installed command (a bare
  hand-written `_ait_archive_exit_chain` is still replaced by name).
  `lib/registry_lock.sh`'s archive peel recognises the new command and still
  accepts the bare one. Substring idempotence is kept and documented.
  Tests: pinned trap text updated (rearm cases 1/7/9, the M `want_trap` column,
  archive_utils J2a). New blocks: P (positional parameters: direct, lock-a/b,
  wlock-a/b, txn) and R-term (re-arm idempotence over the `cmd;`, newline and
  `t; cmd;` re-installs, built from the actually installed trap text).
  Follow-up **t2362** was created for defect 2.
- **Deviations from plan:** none beyond the plan-review rounds recorded above.
  Two whole-command designs were rejected in review: their misses (newline
  separator, trailing `;`) recurse, and they false-positive on a comment. The
  user then chose to scope this task to defect 1.
- **Issues encountered:** none during implementation.
- **Key decisions:**
  - Keep the substring rule; it fails benignly. The trade-off is documented in
    `_ait_archive_exit_chain`'s header comment.
  - Add no shared helper lib: 63 test scaffolds copy `archive_utils.sh` alone.
  - The peel falls back with `${_AIT_ARCHIVE_CHAIN_CMD:-_ait_archive_exit_chain}`,
    so an empty cmd can never reach `_registry_lock_owned_tail`. An empty cmd
    would match any text ending in "; ".
- **Baseline (pre-phase baseline_suites):** all green on the unmodified tree.
  archive_rearm 194, archive_utils 78, registry_lock 98, resolve_tar_zst 81,
  ledger_lock_exit_trap 78, txn_snapshot 60, merge_lock_broker 138,
  merge_lock_concurrency 42, pick_own_scoped_commit 103,
  pick_own_expect_status ok, projects_lock_released_on_die 38,
  gates_sync_registry 94, fold_content 103, fold_file_refs_union 19,
  fold_mark 277, fold_risk_mitigation_drop 5, fold_validate 7, tripwire OK.
  After the change every suite is identical, except archive_rearm at 262
  (+68 new). No TMPDIR leftovers (`tests/run_shell_test.sh`).
- **Post-phase prefix_controls:** each run used a scratch copy of
  `.aitask-scripts/` + the test file.
  - (a) HEAD libs: 33 fail. 8 are pinned trap-text spellings (expected); 25 are
    P behavioural failures (`$1: unbound variable` at archive_utils.sh:228 /
    registry_lock.sh:423, handler never runs) across all six variants.
    R-term passes on HEAD, as intended: it guards a regression, not a
    pre-existing bug.
  - (b) install without `"$@"`: the same 33.
  - (c) rewrite without the CMD branch: 8 fail. A stray `"$@"` appears in
    `trap -p` for P direct, lock-a, wlock-a and txn. lock-b and wlock-b pass,
    because registry_lock's chain sets the final trap from its own saved text.
  - (d) peel without the CMD branch: 16 fail. The caller is lost in the M
    chain/txn/tg/ledger rows (both flows), the ledger lock is not released, and
    P wlock-a/b fail. The raw lock-* variants pass, as predicted (nothing to
    peel).
  - No bash 3.2 is available here, so the `SHELL_UNDER_TEST=/bin/bash` run was
    not done. `"$@"` is the same construct registry_lock already ships.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/archive_utils.sh:285 — _ait_archive_wrap_exit_trap's substring idempotence check treats a caller trap that merely names _ait_archive_cleanup / _ait_archive_exit_chain (quoted data, comment) as already wrapped, so the sweep is dropped and extractions leak (already filed as t2362)`
