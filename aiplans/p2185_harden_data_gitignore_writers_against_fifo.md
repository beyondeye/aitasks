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
