---
Task: t2185_harden_data_gitignore_writers_against_fifo.md
Base branch: main
Output branch: main
---

# t2185 — Harden the data-name .gitignore writers against a FIFO / non-regular .gitignore

## Context

t2178 moved every `setup_*` `.gitignore` helper onto `_ait_add_gitignore_rules`
and gated it on `[[ -f ]]`, because a FIFO in place of `.gitignore` blocks
`grep`'s open-for-read and `>>`'s open-for-write until a peer appears (its 27f red
proof: exit 124 for all 11 helpers). Two writers of the **main** `.gitignore`
were outside its scope and still have the old shape:

1. `_ait_rewrite_data_gitignore_lines` (`.aitask-scripts/aitask_setup.sh:2900`)
   checks only `-e || -L` before `grep`. A FIFO hangs
   `setup_data_gitignore_symlink_safe`, which runs on **every** `ait setup`
   (main(), line 5626) and on upgrade (`install.sh` ~1900).
2. `setup_data_branch` Step 7 (`aitask_setup.sh:2003-2068`) appends the data
   block and the rendered-skill block with unchecked `{ … } >> "$gitignore"`
   after `[[ ! -f ]]` tests. A FIFO hangs it; a read-only regular file or a
   directory aborts setup, because `setup_data_branch` is called bare in
   main() under `set -euo pipefail`. (First branch-mode setup only.)

Outcome: both paths are non-fatal and never block. A file they cannot handle gets
an honest warning, and nothing changes on the success path (the bytes written to
consumers' `.gitignore` stay the same).

Measured facts this relies on (from the task): git itself does not block on a
FIFO `.gitignore` (`ls-files --others --exclude-standard`, `status`, `diff`).
**Step 7 never runs again** once `.aitask-data/.git` exists (the early return at
`setup_data_branch` line ~1627), and nothing else writes its two blocks
(grep-verified). So a Step 7 warning cannot suggest re-running `ait setup` as a
fix. The rewriter's "'ait setup' retries it" *is* true, because
`setup_data_gitignore_symlink_safe` reruns the rewrite every time.

## Sequencing — t2184 overlaps this plan (found after approval, 2026-11-03)

When this plan was approved, **t2184** ("anchor setup .gitignore task data
entries") was `Implementing` in a live session. It had **uncommitted** edits to
every file this plan touches:
- `aitask_setup.sh`: the rewriter now also matches bare names and rewrites to
  `/<name>`; the Step 7 data block writes `/$AIT_DATA_DIR_NAME` plus
  `printf '/%s\n' "${AIT_DATA_LINKS[@]}"` and is guarded on
  `/$AIT_DATA_DIR_NAME`; there is a new `_ait_report_unhidden_nested_data_paths`.
- `tests/test_gitignore_data_symlinks.sh` and `tests/test_data_branch_setup.sh`.

Do **not** edit any of these while t2184 is uncommitted: a path-scoped commit
by either session would carry the other's half-finished work. Once t2184 lands,
re-verify this plan against that HEAD before implementing:
- **Data block and guard:** take Step 7's data block lines and guard pattern
  from the landed code (anchored `/<name>` forms, `AIT_DATA_LINKS` loop),
  not from the snippets below, which show the pre-t2184 bare form.
- **Parity baseline:** capture the pre-phase baseline on the post-t2184 HEAD.
- **Rewriter warning:** the warning wording in `setup_data_gitignore_symlink_safe`
  changed ("legacy data entries", "root-anchored"). Update the D4 assertions to
  match.
- **Nested-path report:** `_ait_report_unhidden_nested_data_paths` runs
  `git ls-files -o --exclude-standard` after a successful rewrite. It is
  git-only, so it does not block on a FIFO; Test 40's FIFO case confirms this.

## Design decisions

- **Rewriter:** one line, `[[ -f "$gitignore" ]] || return 2`, placed right after
  the existence check. Its documented contract already reads "2 = … not a regular
  file", and callers already report rc 2 without failing. A directory or a
  dangling symlink already returned 2 (grep exited 2), so the only change is
  that a FIFO or device now returns 2 instead of hanging.
- **Step 7 does NOT go through `_ait_add_gitignore_rules`.** That writer checks
  each rule separately with whole-line `grep -qxF`. Step 7's blocks use
  **per-block** guards: the data block is keyed on `.aitask-data` alone and
  accepts a CRLF line (t1711), and the rendered-skill block is keyed on a
  substring `grep -F` of `.claude/skills/*-/`. Its `!` negations must also come
  **after** the broad `*-/` patterns. A per-rule writer would append only the
  missing rules, which can put a broad pattern after an existing negation and
  silently cancel that negation.
- So Step 7 gets a small **block writer** that sits beside the t2178 writer and
  reuses its partial-write state (`_ait_gitignore_partial`,
  `_ait_gitignore_note_partial`) instead of copying it.
- **Deliberate edge changes, pinned by tests:**
  - A regular `.gitignore` that cannot be read (for example mode 200, where grep
    exits 2) used to get the block appended blindly. It now warns and writes
    nothing.
  - A dangling-symlink `.gitignore` used to get its target created. It now warns
    and writes nothing.
  - Both match the t2178 writer's "cannot inspect ⇒ don't write" behaviour.
- When a Step 7 block fails, `gitignore_changed` is not set, so nothing claims
  the block was written. If the other block succeeded, Step 9 still commits the
  file as it is on disk. That is the same thing `commit_framework_files` would
  do later anyway, and it matches t2178.

### Pre-phase (risk mitigations)

1. [step7_parity_baseline] **Before editing any source**, capture what the
   unmodified `setup_data_branch` writes. Use the scratchpad
   (`/tmp/claude-1000/-home-ddt-Work-aitasks/1f4f7f1c-cc8b-4817-8bc8-a2173482b77a/scratchpad/parity/`)
   and a small driver script there that sources `aitask_setup.sh --source-only`
   with a scratch `HOME` and runs `setup_data_branch </dev/null` in a fresh
   `git init` repo (pattern: `setup_local_repo` in
   `tests/test_data_branch_setup.sh:159`). Run four fixtures:
   - (a) no `.gitignore`;
   - (b) LF `.gitignore` holding `foo/` plus `bar`;
   - (c) CRLF `.gitignore` already holding `.aitask-data\r` (data guard hit;
     rendered-skill block appended);
   - (d) legacy `.aitask-data/` plus `aitasks/` plus `aiplans/` (the rewrite
     path, then the guard).

   Save each resulting `.gitignore` as `baseline_<fixture>.gitignore`.

   Also run **probe (e)**, a dangling-symlink `.gitignore` (`ln -s gi-missing-target .gitignore`).
   It measures the "used to get its target created" claim in Design decisions
   instead of assuming it. Record:
   - whether `gi-missing-target` now exists, and what it contains;
   - whether Step 9 committed `.gitignore` (`git log --stat -1`).

   (e) is an **expected difference**, not a parity fixture. If the old code did
   not create the target, correct the Design-decisions wording to what was
   observed.
2. [red_proof_new_tests] Add the new test cases (main steps 3 and 4) **before**
   the source fix. Run them against unmodified source and record the red output:
   - the rewriter FIFO case (D4) exits 124;
   - the Step 7 FIFO case exits 124;
   - the Step 7 `readonly` and `directory` cases end without `SURVIVED` (errexit
     abort);
   - the `clean` control is green.

   Keep the output for the archived plan's Final Implementation Notes.

## Implementation steps

1. **`.aitask-scripts/aitask_setup.sh`: rewriter gate** (`_ait_rewrite_data_gitignore_lines`, ~line 2903):
   ```bash
   [[ -e "$gitignore" || -L "$gitignore" ]] || return 1
   # Open only a regular file (or a symlink to one): a FIFO blocks grep's open
   # until a writer appears (t2185, as _ait_add_gitignore_rules, t2178).
   [[ -f "$gitignore" ]] || return 2
   ```

2. **`.aitask-scripts/aitask_setup.sh`: block writer + Step 7.**
   - Add the new helpers right after `_ait_warn_gitignore_rules_failed`
     (~line 3110). Extend the section comment near line 3004 ("Every setup
     .gitignore helper writes through `_ait_add_gitignore_rules`") with one
     sentence saying why Step 7 uses whole-block writes instead (per-block guards
     and negation order).
     ```bash
     # Step 7's two block guards — grep's status: 0 present, 1 absent, 2 unreadable.
     _ait_gitignore_has_data_block() {
         grep -qxF -e "$AIT_DATA_DIR_NAME" -e "$AIT_DATA_DIR_NAME"$'\r' -- "$1" 2>/dev/null
     }
     _ait_gitignore_has_skill_block() {
         grep -qF -e ".claude/skills/*-/" -- "$1" 2>/dev/null
     }

     # _ait_ensure_gitignore_block <gitignore> <guard> <line>...
     #   -> 0 appended, 1 already present, 2 could not inspect or write (an
     #      existing path that is not a regular file, an unreadable file, a failed
     #      or unverified append); on 2 _ait_gitignore_partial says whether bytes
     #      landed. <guard> <gitignore> is the block's own presence test; it runs
     #      again after the append as the read-back. Appends "" + the lines,
     #      byte-identical to the old Step 7 echo blocks.
     _ait_ensure_gitignore_block() {
         local gitignore="$1" guard="$2" rc=0 before
         shift 2
         _ait_gitignore_partial=""
         if [[ -e "$gitignore" || -L "$gitignore" ]]; then
             [[ -f "$gitignore" ]] || return 2
             "$guard" "$gitignore" || rc=$?
             case "$rc" in 0) return 1 ;; 1) ;; *) return 2 ;; esac
             before="$(wc -c < "$gitignore" 2>/dev/null)" || before=""
         else
             before="absent"
         fi
         if ! { echo ""; printf '%s\n' "$@"; } 2>/dev/null >> "$gitignore"; then
             _ait_gitignore_note_partial "$gitignore" "$before"
             return 2
         fi
         rc=0
         "$guard" "$gitignore" || rc=$?
         if [[ "$rc" -ne 0 ]]; then
             _ait_gitignore_note_partial "$gitignore" "$before"
             return 2
         fi
         return 0
     }

     # _ait_warn_gitignore_block_failed <label> <what> <line>... — rc-2 report.
     # Reads _ait_gitignore_partial, so it runs straight after the failed write.
     # Prints the block's rule lines (no comments or blanks) in order, as the
     # hand fix. It never suggests re-running setup: Step 7 does not run again
     # once the data worktree exists.
     ```
   - Warning text:
     - **Not partial:** `Could not add the <label> entries to .gitignore — left unchanged.`
     - **Partial:** `… — the write stopped part-way, so it may now end in an incomplete entry.`
     - Then `  <what> will show as untracked in 'git status'.`
     - Then `  'ait setup' does not retry this step. Fix by hand: [delete any incomplete line at the end of .gitignore, then ]add these lines to .gitignore, in this order:`
     - Then one `    <rule>` line per rule.
   - **Step 7 rewrite** (lines 2020-2068):
     - Turn the two `echo` blocks into local arrays `data_block` / `skill_block`.
       Keep the same lines, including the inner `""` blanks, the comments and
       the literal `aitasks` / `aiplans`.
     - Call `_ait_ensure_gitignore_block "$gitignore" <guard> "${block[@]}" || blk_rc=$?`
       for each block.
     - Branch on the result: `0` → `gitignore_changed=true`; `1` → nothing;
       otherwise call `_ait_warn_gitignore_block_failed`. Use label/what:
       - data block: `task data` / `The task data symlinks ($AIT_DATA_DIR_NAME, aitasks, aiplans)`
       - skill block: `rendered-skill` / `Rendered per-profile skill directories`
     - Keep the existing comments: the CRLF note and the "keep in sync with the
       repo .gitignore until t777_29" note.

3. **`tests/test_gitignore_data_symlinks.sh`: Case D4 (FIFO).**
   - Source `tests/lib/proc_fixtures.sh`.
   - Put a FIFO at `$D_PROJ/.gitignore` and run a bounded child:
     `run_bounded 15 <log> env HOME=<scratch> bash -c 'source setup --source-only; [[ $- == *e* ]] && echo ERREXIT_ON; rc=0; _ait_rewrite_data_gitignore_lines "$2/.gitignore" || rc=$?; echo RW_RC=$rc; SCRIPT_DIR="$2/.aitask-scripts"; setup_data_gitignore_symlink_safe; echo SURVIVED'`.
   - Assert:
     - bounded status `0` (124 = hung);
     - `ERREXIT_ON` (control);
     - `RW_RC=2`;
     - `SURVIVED`;
     - "Could not rewrite" is printed and "already symlink-safe" is not;
     - the path is still a FIFO.
   - Remove the FIFO afterwards so the later "clean file" check still runs on a
     regular file.

4. **`tests/test_data_branch_setup.sh`: Test 40 / 40b (Step 7).**
   - Source `tests/lib/proc_fixtures.sh`.
   - **Test 40**, integration. For each fault in `clean readonly directory fifo`:
     - Build a fresh `setup_local_repo`. Readonly is a committed `base-rule`
       file with `chmod 444`, skipped when it is still writable (root).
     - Run `setup_data_branch` in a bounded (30s) errexit child, with a scratch
       `HOME`, `cd "$2"`, then `echo SURVIVED`.
     - Assert for every fault:
       - status `0`, `ERREXIT_ON` and `SURVIVED`;
       - "Task data branch configured successfully";
       - the `aitasks` / `aiplans` symlinks exist.
     - **clean** (positive control: errexit setup can finish at all):
       - both blocks are on disk;
       - one new commit naming only `.gitignore`.
     - **faults:**
       - both block warnings say `— left unchanged`;
       - the output contains `does not retry this step` and the
         `.claude/skills/*-/` hand-fix line;
       - no new commit;
       - the fixture is unchanged (still a FIFO / a directory /
         `base-rule`).
   - **Test 40b**, helper unit cases, in-process except the partial case:
     - append returns 0 and a second call returns 1, with a byte-exact check of
       the appended block;
     - a CRLF `.aitask-data\r` file returns 1 (the CRLF guard still works);
     - a write-only (mode 200) file returns 2 and is unchanged (the deliberate
       edge change; skipped as root);
     - **dangling symlink** (the other deliberate edge change):
       `ln -s gi-missing-target "$dir/.gitignore"`. Assert:
       - rc 2 and `_ait_gitignore_partial` empty;
       - the link is still a symlink (`[[ -L ]]`) and `readlink` still returns
         `gi-missing-target`;
       - `gi-missing-target` was not created (`[[ ! -e "$dir/gi-missing-target" ]]`).

       Nothing in this case depends on the uid, so it never skips;
     - partial write: a 1016-byte file plus `ulimit -f 1` with
       `trap "" XFSZ`, inside `run_bounded`, then the block writer and the
       warner. Pattern: `tests/test_setup_git.sh` 27l at ~1140. Assert "the
       write stopped part-way", no "left unchanged", and the control that the
       size grew by less than one block.
   - Keep assertions outside subshells: PASS/FAIL/TOTAL are in-process counters
     here, and this file does not use the file-backed counters.

### Post-phase (risk mitigations)

1. [step7_parity_compare] Re-run the pre-phase driver on fixtures (a)-(d)
   against the patched source and `cmp` each `.gitignore` with its
   `baseline_<fixture>.gitignore`. They must all be byte-identical.
   Then rerun probe (e) on the patched source. Expect a non-fatal block warning,
   no `gi-missing-target` and no `.gitignore` commit, and record it beside the
   pre-phase observation as the measured before/after of the deliberate change.
   Record both results in Final Implementation Notes.

## Verification

- `bash tests/test_gitignore_data_symlinks.sh`
- `bash tests/test_data_branch_setup.sh`
- `bash tests/test_setup_git.sh`. The t2178 writer is untouched, but this guards
  the shared partial state.
- `bash tests/test_data_branch_migration.sh`,
  `bash tests/test_install_upgrade_dirty_baseline.sh`,
  `bash tests/test_init_data.sh`,
  `bash tests/test_applink_setup_gitignore.sh`,
  `bash tests/test_install_create_data_dirs.sh` (other `setup_data_branch` /
  repair consumers).
- `shellcheck .aitask-scripts/aitask_setup.sh`
- Red proof (pre-phase 2) and byte parity (post-phase 1) are recorded in Final
  Implementation Notes.
- **Out of scope, report only:** in Test 40's FIFO run, note whether any *other*
  step misbehaves on a FIFO `.gitignore`. `commit_framework_files` / `git add`
  are not exercised by `setup_data_branch`. Anything found becomes a follow-up
  for its owner, not part of this task.

## Step 9 (Post-Implementation)

Commit the code (`bug: … (t2185)`), then do the plan's Final Implementation
Notes, the gate runs, archival and merge per task-workflow Step 9. The task is
on the current branch (`main`), so there is no worktree to clean up.

## Risk

### Code-health risk: low
- Rewriting Step 7's two append blocks could change the bytes `ait setup` writes into consumers' `.gitignore` on the success path (fresh install, existing file, CRLF file, legacy rewrite) · severity: low (residual — addressed by inline pre-phase step7_parity_baseline + inline post-phase step7_parity_compare) · → mitigation: inline pre-phase step7_parity_baseline, inline post-phase step7_parity_compare
- Deliberate edge-state changes: an unreadable regular `.gitignore` and a dangling-symlink `.gitignore` now warn instead of being written blindly or having their target created · severity: low · → mitigation: none (both pinned by direct Test 40b cases — write-only file and dangling symlink; old dangling behaviour measured by pre-phase probe (e); matches the t2178 writer)

### Goal-achievement risk: low
- New tests could pass vacuously (child never reaches Step 7, or a FIFO case that never hung even before the fix) · severity: low (residual — addressed by inline pre-phase red_proof_new_tests) · → mitigation: inline pre-phase red_proof_new_tests
- Another step of `setup_data_branch` (worktree add, Step 9 commit) might also misbehave on a non-regular `.gitignore`, so a Step 7-only fix would not make the whole function survive · severity: low · → mitigation: none (Test 40 runs the whole function bounded; the `clean` control separates harness failure from fault behaviour; out-of-scope findings go to a follow-up)

### Planned mitigations
- timing: pre-phase | name: step7_parity_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: Step 7 rewrite could change success-path .gitignore bytes | desc: capture the .gitignore the unmodified setup_data_branch writes for fixtures (a)-(d) before editing source
- timing: pre-phase | name: red_proof_new_tests | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: new tests could pass vacuously | desc: run the new D4 / Test 40 cases against unmodified source and record 124 / errexit-abort red output
- timing: post-phase | name: step7_parity_compare | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: Step 7 rewrite could change success-path .gitignore bytes | desc: rerun fixtures (a)-(d) on the patched source and cmp against the baselines

## Post-Review Changes

### Change Request 1 (2026-11-03 23:22)
- **Requested by user:** In `_ait_ensure_gitignore_block` the append group `{ echo ""; printf ...; }` checked only the final `printf`'s status, so a transient failure of the separator `echo` followed by a successful `printf` was lost. On a `.gitignore` whose last line had no newline (`keep-me`), that glued the block's comment onto the rule (`keep-me# ...`), returned rc 0 with an empty partial flag, and changed what `keep-me` ignores. Fix it so either failure reaches the rc-2 path, and add a focused regression case.
- **Changes made:**
  - The separator and the block are now chained with `echo "" && printf '%s\n' "$@"`, with a comment explaining why a newline-separated group loses the status.
  - New Test 40b cases:
    - a no-fault control: a no-newline `keep-me` stays a whole line;
    - an injected separator fault (`echo` shadowed in the substitution's subshell) asserts `rc=2 partial=` and a byte-identical file.
  - Red proof on the pre-fix code: both new assertions FAIL (`got 'rc=0 partial='`; the file changed). Green after the fix: 468/468.
  - Parity fixtures (a)-(d) are still byte-identical; probe (e) still creates no target.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`, `tests/test_data_branch_setup.sh`

## Final Implementation Notes
- **Actual work done:**
  - **`.aitask-scripts/aitask_setup.sh`**
    - `_ait_rewrite_data_gitignore_lines` got a `[[ -f ]] || return 2` gate right after its existence check.
    - New Step 7 block writer `_ait_ensure_gitignore_block`, with its guards `_ait_gitignore_has_data_block` / `_ait_gitignore_has_skill_block` and the reporter `_ait_warn_gitignore_block_failed`. They sit right after `_ait_warn_gitignore_rules_failed`, and the t2178 section comment now says why Step 7 writes whole blocks.
    - `setup_data_branch` Step 7 builds `data_block` / `skill_block` arrays and sends both through the writer. A failed block is reported (rc 2) and never sets `gitignore_changed`.
    - The warning gives the rule lines to add by hand (printed with `printf`, so they can be copied) and says `'ait setup' does not retry this step`.
  - **Tests**
    - `tests/test_gitignore_data_symlinks.sh`: Case D4 (FIFO; bounded errexit child).
    - `tests/test_data_branch_setup.sh`: Test 40 covers clean / readonly / directory / fifo, with bounded errexit runs of the whole `setup_data_branch`. Test 40b covers append bytes, idempotency, absent file, the CRLF guard, the skill guard, the separator-fault regression and its control, a write-only file, a dangling symlink, and a partial write under `ulimit -f`.
- **Deviations from plan:**
  - The plan was written before t2184 landed. Implemented on post-t2184 HEAD (`a992cbd30`), so the data block and guard use t2184's anchored `/<name>` forms, and the D4 assertions keep to wording that is stable across t2184.
  - Change Request 1 (review) chains the separator with `&&`; see Post-Review Changes.
  - The comment on the rewriter gate originally claimed the FIFO "hung every `ait setup` and upgrade". It was reworded because git itself blocks earlier (see Issues encountered).
- **Issues encountered:**
  - **Red proof (pre-phase red_proof_new_tests, on unmodified a992cbd30):**
    - D4 exited 124 after printing only `ERREXIT_ON`.
    - Test 40 `fifo` exited 124.
    - `readonly` and `directory` exited 1 without `SURVIVED`, aborting setup with `aitask_setup.sh: line 1618: …/.gitignore: Permission denied` and `…: Is a directory`.
    - `clean` was green. The 40b cases failed because the helpers did not exist yet.
    - There were 0 failures outside the new cases (`426 passed, 38 failed`, all `40*`).
  - **Green:** 113/113 and 468/468. The other consumers all passed: `test_setup_git` 666, `test_data_branch_migration` 21, `test_install_upgrade_dirty_baseline` 137, `test_init_data` 148, `test_applink_setup_gitignore` 4, `test_install_create_data_dirs` 40, `test_agent_instructions` 156, `test_ait_git_gateway_pull` 281. Shellcheck findings are identical to HEAD.
  - **Parity (step7_parity_baseline / step7_parity_compare):** fixtures (a) no file, (b) LF, (c) CRLF with `/.aitask-data\r`, and (d) legacy trailing-slash give byte-identical `.gitignore` files and the same Step 9 commit before and after. This was re-checked after Change Request 1.
  - **Probe (e), dangling-symlink `.gitignore`, measured:**
    - Before the fix, Step 7 created `gi-missing-target` with both blocks, and Step 9 committed `.gitignore` itself, the symlink (`.gitignore | 1 +`).
    - After the fix, both blocks warn, the link is left as it is, no target is created, and nothing is committed.
  - **The task's premise was too narrow.** It said "git itself does not block on a FIFO `.gitignore`". On git 2.56.0 on this host, that holds only for some shapes:
    - **Untracked FIFO `.gitignore`:** `git ls-files --others --exclude-standard`, `git status --porcelain` and `git add -- .gitignore` all time out (124).
    - **Tracked `.gitignore` replaced by a FIFO:** `ls-files --others --exclude-standard` with no pathspec returns 0, but with `-- sub/` (a directory git walks) it times out. `git add` returns 128.
    - **Consequence:** `snapshot_pre_setup_dirty` hangs in its `ls-files --others --exclude-standard -- <framework paths>` call, measured with xtrace for both shapes. `main()` runs it before `setup_data_branch`, so a full `ait setup` with a FIFO `.gitignore` still hangs before this task's code runs.
    - This task fixes the framework's own reads and appends. That fix stands on its own (the readonly and directory aborts are reached; the helpers can be called directly). It does not make `ait setup` survive a FIFO end to end.
- **Key decisions:**
  - Whole-block writer rather than `_ait_add_gitignore_rules`. That writer guards each rule separately, which would break the CRLF-tolerant single guard and could append a broad `*-/` pattern after an existing `!` re-include, cancelling it.
  - The guard re-runs after the append as the read-back.
  - It reuses `_ait_gitignore_partial` and `_ait_gitignore_note_partial`.
  - The warning never suggests re-running setup, because Step 7 sits behind the "already configured" early return.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:4780 — _ait_list_framework_changes' git ls-files --others --exclude-standard probe, reached from snapshot_pre_setup_dirty (:4862, the first git step in main()), blocks on a FIFO .gitignore on git 2.56.0 (untracked FIFO, or a tracked .gitignore replaced by one while git walks a directory), so 'ait setup' still hangs before setup_data_branch; install.sh's snapshot_pre_install_dirty likely shares the shape (not measured). A single early precondition (refuse/warn when .gitignore exists but is not a regular file) before any git probe would cover git's own reads`
  - `.aitask-scripts/aitask_setup.sh:3187 — _ait_add_gitignore_rules (t2178) writes its separator, comment and rules as { echo ""; echo "# comment"; printf ...; }, checking only the last status: a transient failure of the separator echo on a .gitignore whose last line lacks a newline glues the comment onto that rule (probe: 'keep-me' -> 'keep-me# Some comment', rc 0, "Added rule-a/"), the same defect Change Request 1 fixed in _ait_ensure_gitignore_block`
