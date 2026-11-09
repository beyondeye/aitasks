---
Task: t2261_1_issue_backends_and_ledger_writer.md
Parent Task: aitasks/t2261_release_issue_notifications.md
Sibling Tasks: aitasks/t2261/t2261_2_*.md
Archived Sibling Plans: aiplans/archived/p2261/p2261_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2261_1 — Shared issue backends + release-ledger writer

## Context

This is the writer half of t2261. Every successful issue update records one
entry in a rolling ledger, "issues fixed since the last release". The sibling
t2261_2 consumes the ledger at release time.

The **parent plan `aiplans/p2261_release_issue_notifications.md` is
authoritative** for:
- the ledger contract: layout, key, format, validation, dedupe, locking;
- the user decisions taken during planning.

This plan is the step-by-step detail for the writer half.

Callers of `aitask_issue_update.sh`, all covered by hooking the script:
- task-workflow Step 9: `issue-update.md` (ISSUE, PARENT_ISSUE,
  RELATED_ISSUE, PARENT_RELATED_ISSUE) and the inline FOLDED_ISSUE /
  FOLDED_RELATED_ISSUE handling in `task-workflow/SKILL.md`;
- `aitask-pickrem`;
- `aitask-web-merge`.

The folded and related routes call `--issue-url <u> <primary_task_id>`, so a
record always carries the primary id.

Coordination with t2251 (Ready, not started), which retires the Bitbucket
backend in the same file:
- re-check its state before the first edit (shared-file rule: diff vs HEAD);
- move its code into the new lib unchanged;
- send it a note after the commit (step 7).

## Pre-phase (risk mitigations)

1. [characterize_issue_update_argv] Add `tests/test_issue_update_argv.sh`
   **before editing** `aitask_issue_update.sh`.
   - Scratch legacy-mode git project (no data branch) containing:
     - `aitasks/t10_x.md` with `issue: https://github.com/o/r/issues/7`;
     - `aitasks/t20_y.md` with `issue: https://gitlab.com/g/p/-/issues/9`;
     - a commit `feature: x (t10)`.
   - PATH stubs:
     - `gh`, `glab` append `"$0 $*"` to `$LOG`;
     - `auth status` exits 0;
     - `glab issue view … -F json` prints `{"state":"opened"}`;
     - `jq` is the real one, if present; skip the GitLab cases with a clear
       SKIP line if `jq` is absent.
   - Pin the exact argv for each action, for both platforms:

     | Action | Flags |
     |---|---|
     | close-with-notes | `--close` |
     | comment-only | none |
     | close-silently | `--close --no-comment` |
     | folded | `--issue-url <u> --close 10` |

   - Must PASS on the unmodified script. Record the HEAD sha it was measured
     on in a comment.
   - After step 1:
     - GitLab expectations stay byte-identical;
     - GitHub expectations change only `<number>` → the issue URL;
     - the old GitHub line stays as a commented pre-change control.
   - Per memory "Pre-fix controls: classify every assertion": tag each
     assertion `D` (deliberately changed) or `C` (constant) in a comment.

## Implementation

1. **Extract backends** → new `.aitask-scripts/lib/issue_backends.sh`.
   - Add a double-source guard (`_AIT_ISSUE_BACKENDS_SH`).
   - Requires `die` from `terminal_compat.sh` (already sourced via
     `task_utils.sh`).
   - Move `github_*`, `gitlab_*`, `bitbucket_*` and the `source_*`
     dispatchers verbatim. Globals: `SOURCE`, `GITLAB_REPO_SLUG`.
   - Add `source_issue_ref <url>`: for github it echoes the URL; for gitlab
     and bitbucket it echoes the extracted number.
   - The GitHub functions take that ref unchanged as their issue argument
     (`gh issue view|comment|close` accept a URL).
   - In `run_update`:
     - keep `issue_number` for the messages;
     - compute `issue_ref="$(source_issue_ref "$issue_url")"`;
     - pass `issue_ref` to `source_close_issue` / `source_add_comment`.
   - Put a comment on the Bitbucket block: "retirement owned by t2251".
   - `aitask_issue_update.sh` sources the lib after `task_utils.sh`.
   - No other behaviour change.
2. **Ledger lib** → new `.aitask-scripts/lib/release_issue_ledger.sh`.
   - Double-source guard. Requires `task_utils.sh`, `ledger_block.sh` and
     `stale_lock.sh` sourced first; document that in the header.
   - Functions:
     - `ril_root` → `${TASK_DIR:-aitasks}/metadata/release_issues`.
     - `ril_valid_task_id` → `^[0-9]+(_[0-9]+)?$`.
     - `ril_valid_url` → the contract charset.
     - `ril_valid_enum <value> <a|b|c>`.
     - `ril_key <url>` → `printf '%s' "$url" | git hash-object --stdin |
       cut -c1-16`. The rc of git is checked; an empty result is a failure.
     - `ril_name <task> <url>` → `<task>--<key>.rec`.
     - `ril_read <path> <field>` → exact-key `sed -n "s/^${field}=//p"`
       (field names are a fixed internal set). It enforces exactly one
       occurrence, and validates the value per field before printing. A
       violation returns 3 (MALFORMED).
     - `ril_find <task> <url>`: checks `pending/<name>`, then every
       `released/*/<name>`. For a hit it compares the stored `task_id` and
       `issue_url` byte-exact. Equal → prints `pending:<path>` or
       `released:<path>`, rc 0. Different → `hash_collision`, rc 4. No
       hit → rc 1.
     - `ril_record <task> <url> <platform> <action>`:
       - validate every value;
       - take `ait_ledger_lock_acquire release_issues ledger "release-issue
         ledger lock" "release-issue ledger lock"`;
       - `ril_find` → on a hit print `RELEASE_LEDGER:duplicate:<path>`, release
         the lock, rc 0;
       - otherwise `mkdir -p pending` and write the file atomically: temp file
         in the same dir, then `mv -n`, then re-check that the target holds
         our bytes;
       - commit with `ait_commit_paths_staging_untracked "ait: Record
         release-pending issue for t<task>" <path>`;
       - on commit rc ≠ 0: `rm -f` the file, unstage (the helper already
         unstages), print `RELEASE_LEDGER_FAILED:commit_failed`, rc 1;
       - on success print `RELEASE_LEDGER:recorded:<path>`;
       - release the lock with `ait_ledger_lock_release`. A release failure
         is reported with a stderr warning and does not change the verdict.
   - The move helper is added in t2261_2.
3. **Writer hook** in `run_update`, after a successful Step 8.
   - `action`: `CLOSE_ISSUE && NO_COMMENT` → `closed_silent`; `CLOSE_ISSUE`
     → `closed`; else `commented`.
   - Run `( ril_record "$TASK_NUM" "$issue_url" "$SOURCE" "$action" )` in a
     subshell: `rc=0; ( … ) || rc=$?`. A `die` inside a helper (for example
     `assert_data_worktree_clean`) then cannot turn the successful update
     into a plain exit 1.
   - If the subshell printed no `RELEASE_LEDGER*` line, print
     `RELEASE_LEDGER_FAILED:aborted`.
   - On failure:
     - write a stderr hint: "The issue WAS updated — do not re-run this
       command. Record the release-ledger entry with: `<exact --record-only
       command with the same flags>`";
     - `exit 3`.
   - Only github and gitlab are recorded. `SOURCE=bitbucket` →
     `RELEASE_LEDGER:skipped:unsupported_platform`, exit 0 (t2251 retires
     that path).
   - `--dry-run` returns before the hook. The platform calls run under
     `set -e`, so a failed call exits first.
4. **`--record-only`** flag. It resolves the URL exactly like `run_update`
   (task file or `--issue-url`) and auto-detects the platform from the URL.
   It skips `source_check_cli` and every platform call, then runs the same
   record step (same outputs and exits). `--help` describes it as the
   recovery for exit 3. It conflicts with `--dry-run` (die).
5. **Procedure note** in `.claude/skills/task-workflow/issue-update.md`, one
   short paragraph after the first command block: output containing
   `RELEASE_LEDGER_FAILED:` (exit 3) means the issue update succeeded. Run
   only the printed `--record-only` command, and never re-run the original
   command, which would post the comment twice. Then:
   - run `./.aitask-scripts/aitask_skill_verify.sh`;
   - regenerate the goldens that cover this procedure in the same commit
     (see "Regenerate goldens after any `.md.j2` or closure edit" in
     `aidocs/framework/skill_authoring_conventions.md`);
   - check whether `tests/fixtures/skills/task-workflow/issue-update.md.pre-rewrite`
     is involved.
   Suggest follow-up port tasks for the Codex (`.agents/skills/`) and
   OpenCode trees, per CLAUDE.md.
6. **Tests** in `tests/test_issue_update_ledger.sh`: a scratch legacy-mode
   project with git init and committed task files, `gh`/`glab` stubs whose
   failure mode is controlled by an env var, and an argv log.
   - (a) One `.rec` per action, with the correct fields:
     - `action=closed` / `commented` / `closed_silent`;
     - `platform=github` / `gitlab`;
     - committed, so `git status --porcelain` is empty for the path.
   - (b) `--dry-run` → no ledger directory.
   - (c) A stub failure (exit 1) → script non-zero, no record.
   - (d) Dedupe: a second identical run → `duplicate`, still one file, no new
     commit.
   - (e) Concurrency:
     - 6 parallel writers with distinct pairs → 6 files, all committed;
     - 4 parallel writers with an identical pair → exactly 1 file.
   - (f) `--issue-url <other> 10` → `task_id=10`, `issue_url=<other>`.
   - (g) Injected commit failure, using a git wrapper on PATH that fails
     `commit` when `AIT_TEST_FAIL_COMMIT=1`:
     - `RELEASE_LEDGER_FAILED:commit_failed`, exit 3, no file left, index
       clean, stub log shows the comment was posted;
     - then `--record-only` → recorded, and the stub log shows zero new
       calls.
   - (h) The GitHub stub argv contains the full URL.
   - (i) A URL containing `"` → `RELEASE_LEDGER_FAILED:invalid_url`, exit 3,
     and the issue was still updated.
   - (j) `ril_read` on a hand-corrupted file (duplicate key, bad charset) →
     rc 3.
   If any body runs in a `( … )` subshell, use
   `assert_counters_init` / `assert_counters_load` (t1207).
7. **After the commit:** `./ait note 2251 --from 2261_1 --text "…"`. The text
   says the Bitbucket issue backend (`bitbucket_*` and the `source_*`
   dispatch arms) moved from `aitask_issue_update.sh` to
   `.aitask-scripts/lib/issue_backends.sh` in commit <sha>, so t2251's
   inventory line is stale and the removal now happens in the lib. Hedge it:
   the claim is tree-relative and pinned to that sha.

## Verification

- `bash tests/test_issue_update_argv.sh` passes on the unmodified script and
  after the extraction.
- `bash tests/test_issue_update_ledger.sh` passes.
- `shellcheck .aitask-scripts/aitask_issue_update.sh
  .aitask-scripts/lib/issue_backends.sh
  .aitask-scripts/lib/release_issue_ledger.sh`.
- `./.aitask-scripts/aitask_skill_verify.sh` and the regenerated goldens.
- `bash tests/test_terminal_compat.sh`: it lists `aitask_issue_update.sh`.

## Step 9

Commit the code (`feature: … (t2261_1)`) and the plan separately, then archive
via task-workflow Step 9 and push.

## Risk

### Code-health risk: medium
- Moving the backends and switching GitHub to URL targets changes the script
  that every archival route calls. A regression breaks issue closing at
  archival. · severity: low (residual — addressed by inline pre-phase
  characterize_issue_update_argv) · → mitigation: inline pre-phase
  characterize_issue_update_argv
- Exit 3 (ledger failed after a successful update) could lead a caller to
  re-run the full command and double-post the resolution comment. Covered by
  the printed `--record-only` hint and the `issue-update.md` note (steps 3
  and 5). · severity: medium · → mitigation: none (in plan)
- Records build up in user projects that never run `release-notify`. They
  are tiny files. · severity: low · → mitigation: none
- Same-file overlap with t2251. · severity: low · → mitigation: none (note,
  step 7)

### Goal-achievement risk: low
None identified.

### Planned mitigations
- timing: pre-phase | name: characterize_issue_update_argv | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: backend extraction / GitHub URL-target regression at archival | desc: Pin gh/glab argv per action on the unmodified aitask_issue_update.sh before extracting the backends (t2261_1)
