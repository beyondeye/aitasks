---
Task: t2056_fix_printf_grep_q_sigpipe_in_pipefail_tests.md
Base branch: main
Output branch: main
---

# t2056 — Remove `writer | grep -q` SIGPIPE races from pipefail tests

## Context

t2053 fixed `md_has`: `printf … | grep -qxF` under `set -o pipefail` can exit
141 on a PRESENT match. `grep -q` exits on its first match while the writer is
still writing; the writer takes SIGPIPE and pipefail reports 141, so the test
reads "found" as "absent". This task fixes the sibling sites t2053's review
listed, plus a sweep of the other pipefail tests.

Facts established while surveying (bash 5.3; the printf/echo builtins buffer
through stdio, which writes to a pipe in chunks of about 4 KiB):
- A value of 4 KiB or less goes out in one `write(2)` into an empty 64 KiB pipe.
  That write lands before grep can read, so it cannot race. A larger value takes
  several writes and can race.
- **`test_runner_python_isolation.sh:60,65` is a live race.** `$body` is the
  whole runner file (about 12 KB). A false `VIOLATION:missing-unset` is
  reachable.
- **`test_setup_git.sh:857,894` and `test_change_surface.sh:90,100` are latent,
  not live.** `test_setup_git.sh` runs `set +euo pipefail` after its last
  source at line 481. `test_change_surface.sh` only sets `set -u`, and none of
  its sourced libs enable pipefail. The task said every listed site was in a
  pipefail file; for these two files that is wrong. They are converted anyway,
  as cheap hardening against a future `set -o pipefail`.

## Fix patterns (one per writer shape)

- **Writer is a variable** (`printf '%s\n' "$x" | grep -q…`, `echo "$x" |
  grep -q…`, `printf '%s' "$x" | grep -q…`): change to a here-string,
  `grep -q… <<<"$x"`. There is no writer process, so there is no SIGPIPE. The
  here-string adds the same trailing newline as `printf '%s\n'`. It is also
  stricter than `echo`, which would swallow a value such as `-n`.
- **Writer is a command** (`cmd | grep -q PAT`): drop `-q` and write
  `cmd | grep PAT >/dev/null`. grep then reads all of its input, so the writer
  is never cut off, and the pipeline status stays grep's match status.
- Put a one-line comment citing t2056 only where a reader might "simplify" the
  code back. That means the shared assertion helpers (`assert_line` /
  `assert_no_line`, `has_line`, `check_runner`, `assert_match` /
  `assert_no_match`), following t2053's `md_has` comment. Plain call sites get
  no comment.

## Steps

1. Run each file below once before editing and keep the PASS/FAIL totals (a
   read-only baseline; no stash).
2. Named sites:
   - `tests/test_change_surface.sh:90,100` (`assert_line`, `assert_no_line`):
     here-string.
   - `tests/test_setup_git.sh:857` (`$(… | grep -qxF ".gitignore" && echo yes)`)
     and `:894` (`has_line`): here-string.
   - `tests/test_restore_flows_live.sh:237`: here-string.
   - `tests/test_attach_task_delete_decref.sh:175` (a negative assertion, so a
     141 here would be a spurious FAIL): here-string.
   - `tests/test_runner_python_isolation.sh:60,65` (`check_runner`):
     here-string.
3. Sweep. These sites run under live pipefail and use the pipeline's exit
   status (`if`, `&&`, `||`, `!`):
   - Variable writers, changed to here-strings:
     - `test_apply_initializer_output.sh:112`
     - `test_brainstorm_group_progress_aggregate.sh:73,75,115,175,177,241,243`
     - `test_explain_context.sh:388`, both halves. The `! echo | grep -q SC1091`
       half turns a 141 into a false "absent".
     - `test_no_sed_hex_escape.sh:91`
     - `test_session_hook_live.sh:127`
     - `test_session_hook_install.sh:293,295,302,323,353,355,369,371,393,395`
     - `test_task_git.sh:613`
     - `test_update_check.sh:27,41`
     - `test_task_filename_invariant.sh:56`
     - `test_chatlink_relay.sh:674,679`: the generated `fake_agent.sh`, which
       runs `set -euo pipefail` inside an unquoted heredoc. Keep the `\$`
       escaping: `grep -q "STATUS:answered" <<<"\$OUT1" || exit 10`.
   - Command writers, changed to drop `-q` and redirect to `>/dev/null`:
     - `test_stats_data.sh:106`
     - `test_sync_holder_pane_live.sh:174`
     - `test_frozen_standin_spike.sh:284` (`window_exists`)
4. Left unchanged, with the reason recorded in Final Implementation Notes:
   - `test_yaml_utils.sh:787,807,861`: these deliberately test the emitter
     against an early-exiting reader.
   - `test_freeze_engine_live.sh:592`: a shim that has no pipefail.
   - The hook scripts in `test_artifact_gitbranch_backend.sh:470,654`: they are
     `sh` without pipefail.
   - Every `| head`, `| grep -m1` and `| awk '…exit'` inside a `$( )` whose
     status is discarded (no errexit, not tested). The captured text is still
     correct there.
   - errexit `| head` sites over single-match small inputs
     (`test_brainstorm_apply_created_by_group.sh:89`,
     `test_codex_model_detect.sh:171,313,314`) and
     `test_attribution_verdict_log.sh:61` (a substitution in argument
     position, which is not subject to errexit).
   - `test_skill_errexit_capture.sh`: it is dirty in the shared worktree (another
     session owns it), and its sites discard the status anyway.
   - Before editing, check `git status --short` on every target file. Any file
     that has become dirty since the survey is not edited, because another
     session owns its working-tree changes. Its sites go through the
     completion check in step 5 rather than being silently dropped.
5. **Completion check (blocks archival).** Before Step 8's commit review, build
   a per-site ledger for every site listed in steps 2 and 3. Each site ends in
   exactly one of three states:
   - **fixed**: confirmed by re-running the survey regex
     (`\| *grep\b[^|]*-[a-zA-Z]*q`) over the edited files. The only hits left in
     any edited file must be sites listed in step 4 as excluded.
   - **confirmed safe**: only when the input is provably 4 KiB or less (one
     write into an empty pipe), with the evidence written into the ledger.
     This state is for sites that were skipped, never for convenience.
   - **tracked**: a skipped site that is neither fixed nor provably safe. It
     becomes a follow-up task created with `aitask_create.sh --batch`
     (`followup_kind: upstream_defect`, `anchor: 1065`). The task lists the
     file:line, the exact pipeline and the fix pattern, and its id is recorded
     in the ledger.

   The ledger goes verbatim into the plan's Final Implementation Notes. **Do
   not proceed to Step 9 archival while any site is left without one of these
   three states.** This is the durable record that the skipped work survived
   archival, and it never requires editing another session's changes.

## Verification

- Red proof, in the scratchpad and not committed, under `set -o pipefail`:
  - Use a value with the needle first followed by more than 64 KiB of padding.
  - `printf '%s\n' "$v" | grep -qxF needle; echo $?` should give 141, repeated
    20 times.
  - `grep -qxF needle <<<"$v"; echo $?` should give 0, repeated 20 times.
  - `cmd | grep needle >/dev/null` should give 0.
- `bash tests/<file>.sh` for every edited file. Totals must match the baseline
  from step 1, and there must be no new FAILs. Live tmux and agent tests that
  skip or cannot run here are reported as such.
- `shellcheck` on the edited test files shows no new warnings compared with
  before.
- The step 5 ledger is complete: every site from steps 2 and 3 is fixed,
  confirmed safe, or tracked.
- Step 9 (Post-Implementation): commit only the edited test paths, then archive.
  Archive only after the step 5 ledger is complete.

## Risk

### Code-health risk: low
None identified. The edits are mechanical, equivalent rewrites in test files
only, and each file's PASS/FAIL totals are checked against its baseline.

### Goal-achievement risk: low
- A target file could become dirty because a concurrent session edits it, which
  would leave a required site unfixed · severity: low (residual: step 5's
  ledger blocks archival until each site is fixed, confirmed safe, or tracked
  as a follow-up task) · → mitigation: none (built into the plan as step 5)

Every named site is covered, and the sweep classification (status consumed vs
discarded, live vs latent pipefail) is recorded with the reason for each
exclusion.
