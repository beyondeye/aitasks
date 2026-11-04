---
Task: t2188_setup_gitignore_guard_restores_missing_data_link_rules.md
Base branch: main
Output branch: main
---

# t2188 — Restore missing task-data `.gitignore` rules on every setup route

## Context

`setup_data_branch` Step 7 decides whether to append the task-data block
(`/.aitask-data`, `/aitasks`, `/aiplans`) by checking **only** the
`/.aitask-data` line. A `.gitignore` that has that line but lost `/aitasks` or
`/aiplans` (a hand edit) never gets them back. The root `aitasks` / `aiplans`
symlinks then show as `??`, where a broad `git add -A` can commit them. The
reverse case is wrong too: when only `/.aitask-data` is missing, the whole block
is re-appended and the link rules are duplicated.

The re-run repair `setup_data_gitignore_symlink_safe` only rewrites legacy lines
and never adds a missing rule. It is the only route that reaches existing
installs: Step 7 sits behind setup's "already configured" early return, and
`install.sh` / `ait upgrade` calls only the repair.

What I verified that differs from the task text: the task says the shared rule
table "already handles CRLF". It does not: `_ait_add_gitignore_rules` matches
with a plain `grep -qxF -- "$rule"`. Routing the data rules through it as-is
would lose the CRLF handling the Step 7 guard has today.

## Builds on t2185 (landed during planning as 253608e67)

**Reviewer concern, verified.** At a992cbd30, Step 7's rendered-skill block
was an unchecked `{ … } >> "$gitignore"`. A `.gitignore` that was a directory,
a read-only file or a FIFO therefore aborted first-time `ait setup` under
errexit (or hung, for a FIFO) after the data branch already existed, so
protecting only the data block would not have made Step 7 non-fatal.
**t2185 fixed exactly this, and landed while this plan was being written.** It:
- moves **both** Step 7 blocks onto a checked whole-block writer,
  `_ait_ensure_gitignore_block`. The writer never opens a non-regular file,
  chains its writes with `echo "" && printf …`, reads them back, reports a
  partial write, and never aborts setup;
- adds `[[ -f ]] || return 2` to `_ait_rewrite_data_gitignore_lines`;
- adds **Test 40**: the whole `setup_data_branch` runs in a bounded errexit
  child for `clean` / `readonly` / `directory` / `fifo`, and each case asserts
  `SURVIVED`, "Task data branch configured successfully" and the symlinks.
  This is the first-setup failure assertion the review asked for. It also adds
  **Test 40b** (the writer contract, including the `keep-me` separator fault)
  and **D4** (the repair on a FIFO).

So t2188 does **not** re-implement any of this. It keeps t2185's protection of
the rendered-skill block, and keeps Test 40 green for every fault while
changing the data block (step 3).

**Premise corrected.** t2185 keeps the data block on a guard keyed on
`/.aitask-data` alone (`_ait_gitignore_has_data_block`), which is the t2188
defect. t2185's reason for avoiding the per-rule writer is the
**rendered-skill** block's `!` negations, which must follow its broad patterns.
The data block has no negations, so the per-rule writer is safe for it once it
has the same chained writes (step 1a). The skill block stays on t2185's writer.

**Before the first edit,** re-read the landed Step 7, `_ait_ensure_gitignore_block`,
`_ait_warn_gitignore_block_failed`, `_ait_gitignore_has_data_block`, Test
40/40b and D4 at HEAD. Take every line and message from there, not from the
snippets below. `main` can advance while this runs: re-check with
`git log 253608e67..HEAD -- <the files below>` before each commit.

**Order:** the pre-phase (K, H2), then 27n and 27m (27n run red against the
current writer), then step 1 (writer hardening, after which 27n is green),
**before** step 3 routes the Step 7 data block through the writer. Then the
remaining steps.

## Implementation steps

### Pre-phase (risk mitigations)

1. [characterize_legacy_mode_gitignore] Add the legacy-mode invariant first.
   Case K in `tests/test_install_upgrade_dirty_baseline.sh` asserts that an
   upgraded legacy-mode project's `.gitignore` gains none of `/.aitask-data`,
   `/aitasks`, `/aiplans`. Case H2 (step 6) asserts the same at function level. Run both and
   confirm they are **green on the code as it stands**: today's repair never adds
   rules. Once the repair gains its add half, they are the guard that it stays
   branch-mode only.

### Main steps

1. **Harden `_ait_add_gitignore_rules` before anything is routed through it.**
   The 27n regression test (step 9) must already be written and seen red in
   place before this edit.
   - **(a) Checked sequencing.** Today the append runs `echo ""`,
     `echo "# $comment"` and `printf '%s\n' "${missing[@]}"` as separate commands
     in one `{ … }` group, whose status is the last command's only.
     - So a failed **separator** is lost. On a `.gitignore` whose last line
       has no newline (`keep-me`), the comment is glued onto that rule
       (`keep-me# Task data …`), which changes what it ignores.
     - The read-back checks only the rule lines, so it still passes, and the
       writer returns 0 with `_ait_gitignore_partial` empty.
     - t2185 closed this in its block writer with `echo "" && printf …`. Do
       the same here: `echo "" && echo "# $comment" && printf '%s\n' "${missing[@]}"`
       in the append branch, and `echo "# $comment" && printf …` in the create
       branch.
     - Add a comment explaining why (the same reason t2185's writer states).
       Success bytes are unchanged, so 27k's exact-block pins and 27l's
       partial-write case still hold.
     - This closes the hole for every table group, not only the data rules.
   - **(b) CRLF.** In both the presence loop and the read-back loop, replace
     `grep -qxF -- "$rule" "$gitignore"` with
     `grep -qxF -e "$rule" -e "$rule"$'\r' -- "$gitignore"`, keeping the 0/1/other
     rc handling. Update the header comment: a CRLF line counts as present,
     because git strips the trailing CR before matching (measured by
     `test_gitignore_data_symlinks.sh` Case F). Appended lines stay LF, as Step 7
     writes them today.

2. **New `data` group in `_ait_gitignore_group`:** comment
   `Task data (lives on aitask-data branch, accessed via symlinks)`, which is
   the existing text, so the `# Task data (lives on aitask-data branch` count
   assertions still hold. Rules are `/$AIT_DATA_DIR_NAME` followed by `/<link>`
   for each of `AIT_DATA_LINKS`, built in a loop with no stray global.
   `_ait_gi_what="The root task-data entries"`, `_ait_gi_label="task data"`.
   `upgrade_store_gitignore_rules` does not gain `data`: the data rules have
   their own route, gated on branch mode (step 4).

3. **Step 7 data block → per-rule writer (on top of landed t2185).** Replace the data
   block's `_ait_ensure_gitignore_block "$gitignore" _ait_gitignore_has_data_block …`
   call and its `_ait_warn_gitignore_block_failed "task data" …` arm with:
   ```bash
   blk_rc=0
   _ait_gitignore_group data
   _ait_add_gitignore_rules "$gitignore" "$_ait_gi_comment" "${_ait_gi_rules[@]}" || blk_rc=$?
   case "$blk_rc" in
       0) gitignore_changed=true ;;
       1) ;;
       *) _ait_warn_gitignore_rules_failed "$_ait_gi_what" "${_ait_gi_rules[@]}" ;;
   esac
   ```
   - Each rule is now checked separately, LF or CRLF. After a failed rewrite,
     the missing anchored rules are still added, as before.
   - The rendered-skill block stays on `_ait_ensure_gitignore_block` exactly as
     t2185 lands it.
   - Remove `_ait_gitignore_has_data_block` (now unused) and drop the
     data-block sentence from t2185's block-writer header comment.
   - The data-block failure warning now offers "re-run 'ait setup'". That
     becomes **true**: in branch mode the repair adds missing data rules,
     later in the same `main()` run and on every re-run. t2185's "does not
     retry this step" stays correct for the rendered-skill block only.
   - One byte change: a `.gitignore` created from nothing now starts with the
     data comment, not a blank line. Only t2185's 40b pins the leading blank,
     and it pins the block writer, which still produces it.

4. **The repair adds missing rules in branch mode**
   (`setup_data_gitignore_symlink_safe`). Order: rewrite first, so a legacy
   `aitasks/` becomes `/aitasks` rather than gaining a duplicate, then add, then
   report.
   ```bash
   local add_rc=1   # 1 = nothing added (also: legacy mode, add not attempted)
   # Same predicate as setup_data_branch's "already configured" check and
   # task_utils' data-worktree resolver. Never in legacy mode: there aitasks/
   # is tracked task data, and ignoring it would hide every new task file.
   if [[ -d "$project_dir/$AIT_DATA_DIR_NAME/.git" || -f "$project_dir/$AIT_DATA_DIR_NAME/.git" ]]; then
       add_rc=0
       _ait_gitignore_group data
       _ait_add_gitignore_rules "$project_dir/.gitignore" "$_ait_gi_comment" "${_ait_gi_rules[@]}" || add_rc=$?
   fi
   ```
   - The rewrite `case` stays as it is, except that its rc-1 line ("already
     symlink-safe and root-anchored") is printed only when `add_rc != 0`.
   - Then a second `case "$add_rc"`:
     `0) success "Added $_ait_gitignore_added to .gitignore (missing task-data rules)"`,
     `1) ;;`, `*) _ait_warn_gitignore_rules_failed "$_ait_gi_what" "${_ait_gi_rules[@]}"`.
   - The function still commits nothing and returns 0, so the dirty-baseline
     contract of `commit_framework_files` and `commit_installed_files` is
     unchanged.
   - A FIFO `.gitignore` cannot hang the add: `_ait_add_gitignore_rules`
     refuses non-regular files before opening them, and the rewriter refuses
     them since t2185.
   - Extend the header comment to cover the add half and the legacy-mode
     exclusion.

5. **Docs:** in `website/content/docs/commands/setup-install.md`, `ait upgrade`
   step 5, add a sentence after the rewrite description: in a project whose
   task data lives on the separate `aitask-data` branch, any of the three
   root-anchored entries missing from `.gitignore` is added back, and committed
   under the same "no uncommitted changes" condition. Current-state voice.
   Then run `python3 check_links.py --build` in `website/`.

6. **Repair-route tests: Case H in `tests/test_gitignore_data_symlinks.sh`**,
   using the `SCRIPT_DIR=<proj>/.aitask-scripts` pattern of Cases D/G:
   - **H1:** branch mode (`mkdir -p proj/.aitask-data/.git`), one link rule
     missing. Expect rc 0 and `Added /<link>`; each anchored name exactly once;
     `check_gitignore` passes; no "already symlink-safe". A second run is
     byte-identical, prints the "already" line and prints no "Added".
   - **H1b:** only `/.aitask-data` is missing, so only it is added and the link
     rules are not duplicated.
   - **H2 (pre-phase, legacy mode):** the same `.gitignore` with no
     `.aitask-data/`. The file stays byte-identical (`cmp`), with no "Added" and
     the "already" line present.
   - **H3:** branch mode with the legacy lines `.aitask-data/` and `aiplans/`.
     The result is all three anchored lines, each once; both the rewrite and
     the add are reported.
   - **H4:** branch mode with `.gitignore` as a directory. Non-fatal, warns
     "Could not add", makes no "Added" claim.
   - **H5:** branch mode with all three as CRLF lines. Untouched (byte-identical)
     and "already". With `/aitasks\r` removed, exactly one `/aitasks` is
     appended and no CRLF line is duplicated (CR-tolerant count is 1 per name).
   - **D4 extension (t2185's FIFO case):** a second bounded run in branch mode
     (`.aitask-data/.git` present) proves the add half does not block on a
     FIFO. Expect status 0, `SURVIVED`, "Could not add", no "Added", and the
     FIFO left in place.

7. **Step 7 tests in `tests/test_data_branch_setup.sh`:**
   - **Test 40 update (t2185's errexit test):** keep every fault's `SURVIVED` /
     configured / symlink / no-commit assertions.
     - The data-block assertions move to the per-rule warning: "Could not add
       /.aitask-data /aitasks /aiplans to .gitignore — left unchanged", naming
       `'/.aitask-data'`.
     - The rendered-skill assertions ("rendered-skill entries", "does not retry
       this step", `    .claude/skills/*-/`) stay.
     - New, per fault: clear the fault (chmod 644; rmdir or rm, then an empty
       file), then run `setup_data_gitignore_symlink_safe` with `SCRIPT_DIR`
       set. All three data rules now exist exactly once, which proves the
       "re-run 'ait setup'" remedy is real.
   - **Test 40b update:** the writer-contract cases that pass
     `_ait_gitignore_has_data_block` as the guard switch to a test-local guard
     with the same body, defined in the parent shell and inside the
     partial-write child. Drop "the data guard still accepts a CRLF line";
     data-rule CRLF is covered by 12d and H5.
   - **New 12c:** the Test 12/12b fixture with `.gitignore` = `node_modules/`,
     blank line, the `# Task data …` comment, `/.aitask-data`, `/aiplans`.
     Precondition: `HEAD:.gitignore` lacks `/aitasks`. After `setup_data_branch`:
     each anchored line exactly once; `assert_data_symlinks_ignored`; no
     `?? aitasks`; `.gitignore` committed and clean; `HEAD:.gitignore` carries
     `/aitasks`.
   - **New 12d:** the same fixture as CRLF with all three rules present. No line
     is added, each name is counted once (CR-tolerant), and no second
     `# Task data` block appears.

8. **Upgrade route end to end: `tests/test_install_upgrade_dirty_baseline.sh`:**
   - **Case K addition** (the pre-phase, above).
   - **New Case L** (branch mode, missing `/aitasks`, clean `.gitignore`):
     - Run `make_project "$TMP/L"`, then convert it to branch mode with the
       orphan-branch recipe from `tests/test_install_create_data_dirs.sh`
       `make_branch_mode`: `git mktree </dev/null` → `commit-tree` →
       `update-ref refs/heads/aitask-data` → `git worktree add .aitask-data aitask-data`.
     - Move the install's `aitasks/` / `aiplans/` into the worktree and commit
       there. Untrack them on main (`git rm -r -q --cached --ignore-unmatch`).
       Create the `.aitask-data/<name>` symlinks. Write `.gitignore` =
       `node_modules/`, `/.aitask-data`, `/aiplans` and commit.
     - **Fixture preconditions** fail fast, so a fixture mistake cannot pass as
       a red test: `aitasks` is a symlink, `.aitask-data/.git` exists, and
       porcelain shows `?? aitasks`.
     - Run `upgrade`. Expect RC 0; exactly one `/aitasks` on disk and in
       `HEAD:.gitignore`; `.gitignore` clean; the upgrade commit carries
       `.gitignore`; `git status --porcelain -- aitasks` is empty.
   - **New Case L2:** the same fixture with a dirty `.gitignore` (append
     `user-rule.log`). `/aitasks` lands on disk; `HEAD:.gitignore` still lacks
     it; the file stays ` M`; the upgrade commit lacks `.gitignore`.

9. **Shared-writer tests in `tests/test_setup_git.sh`** (written before step 1,
   see **Order**):
   - **27m, CRLF:** a CRLF `.gitignore` already holding `aiwork/\r` and
     `.aitask-crews/\r`. `setup_worktree_dirs_gitignore` prints its "already"
     line, leaves the file byte-identical and makes no commit.
   - **27n, separator failure on a file with no final newline**
     (`_ait_add_gitignore_rules` directly, with the data comment and the three
     anchored data rules as literals, since step 2's group does not exist yet).
     Faults are injected by shadowing `echo` inside a `$( )` subshell, as
     t2185's 40b does; each fault case asserts `rc=… partial=…` from that
     subshell:
     - **control**, no fault, `printf 'keep-me'`: rc 0; `keep-me` is still a
       whole line; exact bytes `keep-me\n# <comment>\n<rules>\n`. The
       single separator newline only ends the `keep-me` line, so no blank line
       follows it. These are the bytes both the current and the chained writer
       produce.
     - **separator fault**: `echo` fails only for the single empty argument
       and delegates otherwise. Expect `rc=2 partial=`, the file byte-identical
       (`cmp`), and no `keep-me#` line. Today's writer returns `rc=0 partial=`
       with the rule glued, which is the reviewer's reproduction.
     - **comment fault**: `echo` fails only for an argument starting `# `.
       Expect `rc=2 partial=yes`: the separator landed, and it is reported,
       never success.
     - **create-branch comment fault**, no `.gitignore`: rc 2, never 0.
     - **Binding, added after step 2:** `_ait_gitignore_group data` yields
       exactly the comment and rules 27n uses, so the test stays tied to what
       Step 7 and the repair write.
   - Run 27n **before** step 1 and confirm the separator and comment faults
     fail on the current writer (an in-place red proof). Run it again after
     step 1 and confirm it is green.

## Verification

- `bash tests/test_gitignore_data_symlinks.sh`, `bash tests/test_data_branch_setup.sh`
  (including t2185's Test 40/40b as updated), `bash tests/test_install_upgrade_dirty_baseline.sh`,
  `bash tests/test_setup_git.sh`: all PASS.
- Regression set: `bash tests/test_data_branch_migration.sh`,
  `bash tests/test_init_data.sh`, `bash tests/test_install_create_data_dirs.sh`,
  `bash tests/test_applink_setup_gitignore.sh`, `bash tests/test_agent_instructions.sh`.
- `shellcheck .aitask-scripts/aitask_setup.sh` (no new findings).
- **Red proof against the pre-t2188 code.** No stash, no restore in the shared
  tree: `git worktree add --detach <scratchpad>/red <pre-t2188 HEAD>`, copy
  only the edited test files into it, and run them there.
  - Must fail: the branch-mode add cases (H1/H1b/H3/H5-missing in the repair,
    12c in Step 7, L in the upgrade, 27m and 27n's separator and comment faults
    in the shared writer, and Test 40's new "re-run repairs the data rules"
    assertion). 27n's red result is also observed in place before step 1.
  - Must pass: the legacy-mode assertions (H2, K).
  - Then `git worktree remove` it, and record the commands and results in the
    Final Implementation Notes.
- `cd website && python3 check_links.py --build`.

## Step 9 (Post-Implementation)

Current-branch mode. Commit the code (`bug: … (t2188)`) with paths named, and
the plan separately. Then do the gate run and archival in Step 9.

## Risk

### Code-health risk: medium
- The repair now writes in a new way on the load-bearing setup and
  `ait upgrade` path. If the branch-mode predicate were wrong, a legacy-mode
  project would gain `/aitasks`, and every new task file would be silently
  ignored. · severity: high · → mitigation: inline pre-phase characterize_legacy_mode_gitignore
- Step 3 edits Step 7 code and Test 40/40b that t2185 has only just landed.
  Taking a line from a stale snapshot would undo part of its hardening.
  · severity: medium · → mitigation: in plan (re-read the landed code at HEAD before the first edit; Test 40/40b/D4 kept green)
- Moving the data rules from t2185's block writer to the per-rule writer would
  lose t2185's separator-failure protection: the per-rule writer's group status
  hides a failed separator, so the comment is glued onto a final line with no
  newline while rc is 0. · severity: medium · → mitigation: in plan (step 1a chained writes, 27n regression test red-then-green, ordered before step 3)
- The CRLF-aware matcher and the chained writes change `_ait_add_gitignore_rules`
  for every table group on both routes. Success bytes are unchanged, and CRLF
  matching only affects CRLF files, which the byte-identical pins (27h/27k) do
  not use. · severity: low · → mitigation: in plan (27m/27n plus the full `test_setup_git.sh` run)

### Goal-achievement risk: low
- The upgrade-route fixture is hand-converted to branch mode and might not
  match a real branch-mode project. · severity: low · → mitigation: in plan (fixture precondition assertions in step 8)

### Planned mitigations
- timing: pre-phase | name: characterize_legacy_mode_gitignore | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: repair adding data rules in a legacy-mode project | desc: Add the legacy-mode no-data-rules assertions (H2, case K) and run them green on the unmodified code before changing the repair

## Final Implementation Notes
- **Actual work done:**
  - `_ait_add_gitignore_rules` writes with `echo "" && echo "# $comment" && printf …`, in both the append and the create branch, and matches a rule in its LF or CRLF form in both the presence check and the read-back.
  - New `data` group in `_ait_gitignore_group`.
  - `setup_data_branch` Step 7 writes the task-data rules through the per-rule writer from that group. The rendered-skill block stays on t2185's `_ait_ensure_gitignore_block`. `_ait_gitignore_has_data_block` was removed.
  - `setup_data_gitignore_symlink_safe` runs the rewrite and then, only when `.aitask-data/.git` exists, adds missing anchored rules. It reports "Added …", or warns through `_ait_warn_gitignore_rules_failed`.
  - Docs: one sentence in `setup-install.md` (`ait upgrade` step 5).
  - Tests:
    - repair route: Case H (H1, H1b, H2, H3, H4, H4b, H5, H5b) and D4b in `test_gitignore_data_symlinks.sh`;
    - Step 7: 12c/12d, plus the Test 40/40b updates, in `test_data_branch_setup.sh`;
    - upgrade route: case K's legacy-mode assertions and cases L/L2 in `test_install_upgrade_dirty_baseline.sh`;
    - shared writer: 27m/27n in `test_setup_git.sh`.
- **Deviations from plan:**
  - t2185 landed (253608e67) during planning, so the pre-edit gate was dropped and the work rebased onto the landed code, as the plan's re-check required.
  - Added **H4b**: branch mode, a read-only `.gitignore` with no legacy line that lacks a rule. While reviewing the diff I found that the repair's "already symlink-safe and root-anchored" line printed whenever `add_rc != 0`, so a failed add (rc 2) printed it next to "Could not add …". The condition is now `add_rc == 1`: legacy mode, or nothing missing. A mutant run with the old condition prints the contradictory line, so H4b guards it.
  - The H4b and Test 40 assertions name **every** rule of the group in the failure line ("Could not add /.aitask-data /aitasks /aiplans …"), because `_ait_warn_gitignore_rules_failed` reports the whole group, as 27f pins for the other groups.
- **Issues encountered:**
  - My first H1 expected bytes were missing the blank separator line. The fixture file ends in a newline, so `echo ""` adds an empty line. Fixed in the test.
  - My first H4b assertion named only the missing rule. Fixed, as above.
  - New SC2154 infos in `test_setup_git.sh`, for variables set by the sourced script, are silenced with scoped disables.
- **Key decisions:**
  - Data rules use the per-rule writer. The block has no `!` negations, so t2185's ordering argument only applies to the rendered-skill block.
  - The branch-mode predicate is `.aitask-data/.git` (`-d` or `-f`), the same one `setup_data_branch`, `task_utils` and `install.sh` use.
  - Step 7's data-rule failure warning now offers "re-run 'ait setup'". That is true because the repair retries in branch mode, and Test 40 proves it by clearing each fault and running the repair.
  - A `.gitignore` created from nothing now starts with the data comment, not a blank line. No test pins that byte.
- **Red proof (durable record):**
  - `git worktree add --detach <scratchpad>/red aa67dd50e` (pre-t2188 HEAD, t2185 included), copy the 4 edited test files into it, run each suite there, then `git worktree remove --force <scratchpad>/red`.
  - Results on the pre-fix code:
    - `test_gitignore_data_symlinks`: 15 FAIL (D4b, H1×5, H1b×2, H3×3, H4, H5b×3). H2 passes.
    - `test_setup_git`: 27m×4 and 27n×6 FAIL, then it aborts at the binding with `unknown .gitignore rule group: data`.
    - `test_data_branch_setup`: 25 FAIL (12c×4; Test 40 readonly/directory/fifo × data-rule warning and re-run checks).
    - `test_install_upgrade_dirty_baseline`: 5 FAIL (L×4, L2×1). K's legacy-mode assertions pass.
  - Before the writer fix, the in-place 27n run showed the reviewer's reproduction: `rc=0 partial=` with `keep-me#` glued.
  - After the change: 182/182, 680/680, 501/501, 162/162; also `test_data_branch_migration`, `test_init_data`, `test_install_create_data_dirs`, `test_applink_setup_gitignore` and `test_agent_instructions` pass. The setup script's shellcheck findings by code are identical to HEAD.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:_ait_warn_gitignore_rules_failed` — every caller passes the group's full rule list (`${_ait_gi_rules[@]}`), not the missing subset, so for a multi-rule group (`worktrees`, now `data`) the rc-2 warning and its "Fix by hand: add the lines …" tell the user to add rules the file already has.
