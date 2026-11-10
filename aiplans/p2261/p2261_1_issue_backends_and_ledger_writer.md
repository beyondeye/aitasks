---
Task: t2261_1_issue_backends_and_ledger_writer.md
Parent Task: aitasks/t2261_release_issue_notifications.md
Sibling Tasks: aitasks/t2261/t2261_2_*.md
Archived Sibling Plans: aiplans/archived/p2261/p2261_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-10 10:34
---

# t2261_1 — Shared issue backends + release-ledger writer

## Context

This is the writer half of t2261. Every successful issue update records one
entry in a rolling ledger, "issues fixed since the last release". Sibling
t2261_2 reads the ledger at release time and posts "Released in vX.Y.Z".

The **parent plan `aiplans/p2261_release_issue_notifications.md` is
authoritative** for the ledger contract (layout, key, format, validation,
dedupe, locking) and for the user decisions taken during planning. This plan is
the step-by-step detail for the writer half.

Callers of `aitask_issue_update.sh` (all covered by hooking the script):
- task-workflow Step 9: `issue-update.md` (ISSUE, PARENT_ISSUE, RELATED_ISSUE,
  PARENT_RELATED_ISSUE) and the inline FOLDED_ISSUE / FOLDED_RELATED_ISSUE
  block in `task-workflow/SKILL.md`;
- `aitask-pickrem` (headless; `SKILL.md.j2`);
- `aitask-web-merge` (`SKILL.md`, plain file).

Folded and related routes call `--issue-url <u> <primary_task_id>`, so a record
always carries the primary id. Step 9 commits the archive, then updates the
issues, then pushes the task data, so the ledger commit goes out with that push.
The writer itself never pushes.

## Verification findings (re-verified 2026-11-10 against HEAD 0e17732b1)

The plan's file paths and line ranges are confirmed: the backends are at
`aitask_issue_update.sh:33-239` and Step 8 at `:405-422`. The script still runs
under `set -e` only. Its shared helpers (`ait_ledger_lock_acquire`,
`ait_commit_paths_staging_untracked`, `task_git`, `ait_data_mode`) exist as
described. t2251 is still Ready and unlocked, and the script is unchanged vs
HEAD. No in-flight task's task file names any file this plan edits.

The verification found these corrections and additions:

1. **No `jq` dependency in the argv test.** `gitlab_get_issue_status` (the only
   `jq` user) is never called by `run_update`. Drop the "skip if no jq" clause
   and the `glab issue view` stub.
2. **The SC2046 baseline.** shellcheck already reports SC2046 four times, on
   the deliberate `$(glab_repo_flag)` word-split (the flag is the two words
   `-R slug`). The verbatim move keeps the split. Add a
   `# shellcheck disable=SC2046` with a one-line reason at each of the four
   sites, so `shellcheck` is clean and argv stays identical.
3. **The tripwire.** `tests/test_archive_rearm_tripwire.py` requires every
   `trap … EXIT` in a `lib/*.sh` to be followed by the guarded spelling
   `if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi`.
   That covers `trap - EXIT` too.
4. **`ril_record` is self-isolating.** It is defined with a subshell body,
   `ril_record() ( … )`, so its EXIT trap, lock token and staging list can
   never leak into a caller. The writer calls it with stdout redirected to a
   temp file, never inside `$( )`. Because a `||` context disables errexit
   inside, the body checks every return status explicitly.
5. **The publish is a hard link, not `mv -n`.** `mv -n`'s exit status differs
   across coreutils versions. Publish with `ln -- "$tmp" "$path"`, which is
   atomic and refuses an existing target on every platform, then remove the
   temp file.
6. **The URL validator uses the existing byte-safe idiom.** It reuses the
   `LC_ALL=C tr -d <set>; printf x` sentinel from `validate_file_ref`
   (`lib/task_utils.sh:3776`). A probe confirmed it rejects a trailing newline,
   `"`, `\`, a space, non-ASCII, `[`, `]` and other schemes, and accepts the
   contract charset.
7. **The hint goes through `printf`.** `warn`/`info` use `echo -e`, which would
   mangle a `%q`-quoted URL. The recovery hint goes to stderr through `printf`.
8. **The hint is reason-aware.** For `invalid_url`, `invalid_task_id` and
   `hash_collision`, `--record-only` would fail again, so the hint says no
   retry will succeed instead of printing a command.
9. **Every caller gets the recovery line (deviation from the parent plan).**
   The parent plan adds the recovery paragraph to `issue-update.md` only. Exit
   3 and `RELEASE_LEDGER_FAILED:` are new output vocabulary for **all four**
   call sites, and the inline FOLDED block explicitly does not use
   `issue-update.md`. So each call site gets one line pointing at the
   canonical paragraph, following the "fix every consumer" rule. This costs:
   - task-workflow goldens `SKILL-{default,fast,remote}.md`;
   - the pickrem golden `SKILL-remote-claude.md`;
   - the committed `remote-` prerenders.
   No port tasks are needed. The task-workflow procedures and `pickrem` render
   into the Codex/OpenCode trees, and their `aitask-web-merge` wrappers only
   point at the Claude source.
10. **No website or doc pages change.** p2261_2 step 5 owns
    `issue-integration.md`, including `--record-only` and the
    `RELEASE_LEDGER*` outputs. This child updates only `--help`.
11. **A branch-mode case is added to the ledger test.** This repo runs in
    branch mode, and a legacy-only fixture would leave the production commit
    path (`git -C .aitask-data`) untested.

Plan-review corrections (all three verified against the code):

12. **A file being present does not mean it is persisted.** `ril_find` only
    tests `[[ -e ]]`. A SIGKILL or power loss after `ln` but before the commit
    leaves a complete, untracked matching record, which no EXIT trap removes.
    The next run would then report `duplicate` while the record never reaches
    git or `ait sync`.

    Fix: a matching hit is classified by its **git state**
    (`_ril_hit_state`) before any duplicate success.
    - Only `committed` is a duplicate.
    - Pending residue (`untracked` / `staged`) is fully validated, then
      committed by this run.
    - Every other state is an explicit failure that leaves the file in place.
13. **Preservation is a state, not an rc rule.** The earlier draft ran
    cleanup on every non-zero result. Cleanup deleted the published file
    unless `_RIL_COMMITTED=1`, which contradicted the rc-2 "leave it" branch.

    rc 2 is reachable: another operation in the shared checkout (e.g. an
    explicit metadata commit) can commit the published path before this
    writer's commit runs. Deleting the file then creates a tracked deletion.

    Fix: the single variable `_RIL_OWNED` says whether this run published a
    file that git does not hold. Cleanup deletes only when `_RIL_OWNED=1`
    **and** a nested check shows the path is absent from HEAD. Every path
    that keeps the file sets `_RIL_OWNED=0` before finishing.
14. **The dry-run baseline includes the auth check.** `run_update` calls
    `source_check_cli` (`:347`) before its dry-run return (`:387-403`), so
    the unmodified script logs `gh auth status` on `--dry-run`. The
    characterization expects exactly that one call, and no issue call or
    ledger write. The auth check's behaviour does not change in this task;
    only `--record-only`, a new mode, skips it.
15. **rc 1 needs the same preservation as rc 2** (second review, reproduced
    with the real helper). A competing commit **after**
    `task_git_commit_scoped`'s status check but before its `git commit` makes
    the commit fail with "nothing to commit", and the helper returns 1. An
    unconditional rollback `rm` would then delete a committed file.

    Fix: rc 1 and rc 2 share one resolver that re-classifies by git state.
    The rollback deletes only through the same `_ril_delete_if_owned_and_absent`
    rule cleanup uses. A test injects the competing commit at exactly that
    window, through the helper's existing `AIT_COMMIT_SCOPED_SEAM_PREGIT`
    seam (`lib/task_utils.sh`; it fires after the status check, before
    `task_git commit`).

## Pre-phase (risk mitigations)

1. [characterize_issue_update_argv] Add `tests/test_issue_update_argv.sh`
   **before editing** `aitask_issue_update.sh`, and run it on the unmodified
   script. It must PASS there; record the run and the HEAD sha in the Final
   Implementation Notes.
   - **Harness.** Use the `tests/test_note_append.sh` harness:
     - `enter_scratch_cwd`, then `tests/lib/asserts.sh`;
     - `sync_isolate_git_config` from `tests/lib/git_config_isolation.sh`;
     - a private `AITASKS_LOCK_DIR`;
     - run the **real** `$PROJECT_DIR/.aitask-scripts/aitask_issue_update.sh`
       with cwd = the fixture.
   - **Fixture.** A legacy-mode git repo, with per-repo `user.*` and
     `commit.gpgsign false`, no `.aitask-data`, no origin. It contains:
     - `aitasks/t10_x.md` with `issue: https://github.com/o/r/issues/7`;
     - `aitasks/t20_y.md` with `issue: https://gitlab.com/g/p/-/issues/9`;
     - commits `feature: x (t10)` and `feature: y (t20)`.
   - **Stubs.** `gh` and `glab` are bash stubs on a prepended PATH dir. They
     append `printf '%q ' "$(basename "$0")" "$@"; echo` to `$STUB_LOG`, so
     each call is exactly one line even for a multi-line body. `auth status`
     exits 0. `STUB_FAIL=<subcommand>` makes that subcommand exit 1.
   - **Expected values.** The expected comment body is built in the test from
     the fixture's `git log --oneline -1 --grep='(t10)'` line, in
     `build_comment_body`'s exact shape (no plan file):
     `## Resolved via aitask t10` + `\n\n### Associated Commits\n\n```\n<line>\n```` with
     trailing newlines stripped by `$( )`. The expected log lines are rendered
     with the same `printf '%q '`.
   - **Pinned full call sequences** (`auth status` call included):

     | Action | Flags | GitHub (pre-change) | GitLab |
     |---|---|---|---|
     | close-with-notes | `--close 10/20` | `gh issue close 7 --comment <b>` | `glab issue note 9 -R g/p -m <b>`; `glab issue close 9 -R g/p` |
     | comment-only | `10/20` | `gh issue comment 7 --body <b>` | `glab issue note 9 -R g/p -m <b>` |
     | close-silently | `--close --no-comment 10/20` | `gh issue close 7` | `glab issue close 9 -R g/p` |
     | folded | `--issue-url <u42> --close 10` / `--issue-url <gl11> --close 20` | `gh issue close 42 --comment <b>` | `glab issue note 11 -R g/p -m <b>`; `glab issue close 11 -R g/p` |
     | dry-run | `--dry-run --close 10` / `--dry-run --close 20` | exactly `gh auth status`; no `gh issue …` call | exactly `glab auth status`; no `glab issue …` call |

     The dry-run rows also assert that no `release_issues/` directory exists
     afterwards. That holds trivially before step 3, and the same assertion
     later covers the hook.

   - **Assertion tags.** Each assertion is tagged in a comment: `C` (constant)
     or `D` (deliberately changed by step 1).
     - Only the GitHub issue-argument rows are `D`. In step 1 they change from
       `<number>` to the issue URL, and each keeps its pre-change line as a
       commented control citing commit `0e17732b1`.
     - Every GitLab row, every `auth status` row and both dry-run rows (auth
       check only) are `C` and stay byte-identical.
   - **Subshells.** All assertions run in the main shell (subshell results are
     captured as rc/strings first), so no file-backed counters are needed. If
     any assertion ends up inside `( … )`, add
     `assert_counters_init`/`assert_counters_load` (t1207).

## Implementation

1. **Extract the backends** into the new `.aitask-scripts/lib/issue_backends.sh`.
   - Add a double-source guard `_AIT_ISSUE_BACKENDS_LOADED`. The header
     states that it requires `die` (`terminal_compat.sh`, via `task_utils.sh`)
     and reads/writes the globals `SOURCE` and `GITLAB_REPO_SLUG`.
   - Move these **verbatim**:
     - the `github_*`, `gitlab_*` (with `glab_repo_flag`) and `bitbucket_*`
       functions;
     - the five `source_*` dispatchers;
     - the "PLATFORM BACKENDS" extension comment.
     Add the SC2046 disables (finding 2). Put a comment on the Bitbucket
     block: "Retirement owned by t2251 (Bitbucket Cloud issue API removed
     2026-08-20)."
   - Add `source_issue_ref <url>`, which outputs the issue argument the
     backend CLI receives:
     - **github:** the URL itself when it starts with `http://` or `https://`.
       `gh issue view|comment|close` take `{<number> | <url>}`, confirmed via
       `gh issue comment --help`, so cross-repo and GHE issues are targeted
       correctly. A non-URL value falls back to `github_extract_issue_number`,
       today's behaviour.
     - **gitlab / bitbucket:** `source_extract_issue_number "$url"`
       (unchanged; GitLab keeps `-R slug`).
     - **other:** `die "Unknown source: $SOURCE"`.
   - Parameter names in the GitHub functions change from `issue_num` to
     `issue_ref`; the bodies are unchanged.
   - In `aitask_issue_update.sh`:
     - keep the `GITLAB_REPO_SLUG=""` and `SOURCE=""` initialisations;
     - add `source "$SCRIPT_DIR/lib/issue_backends.sh"` after `task_utils.sh`
       (column 0, with a `# shellcheck source=` line).
   - In `run_update`:
     - keep `issue_number` for every message;
     - add `issue_ref="$(source_issue_ref "$issue_url")"` after the number
       check;
     - pass `"$issue_ref"` to `source_close_issue` / `source_add_comment`.
   - Then re-run `tests/test_issue_update_argv.sh` with the `D` rows switched
     to the URL. All other rows must pass unchanged.

2. **Ledger lib** in the new `.aitask-scripts/lib/release_issue_ledger.sh`.
   - **Header.** The header covers:
     - the contract pointer: the parent plan's "Ledger contract", archived at
       `aiplans/archived/p2261_*.md` once landed;
     - that `task_utils.sh` must be sourced first;
     - that t2261_2 adds the move helper and the released-field validators.
   - **Sourcing.** Double-source guard `_AIT_RELEASE_ISSUE_LEDGER_LOADED`.
     Then, at column 0, `source "$(dirname "${BASH_SOURCE[0]}")/ledger_block.sh"`,
     a spelling the closure scanner accepts; that lib has its own guard.
   - **Constants:** `RIL_SCHEMA=1` and
     `RIL_URL_CHARSET="A-Za-z0-9._~:/?#@!\$&'()*+,;=%-"`.
   - **Path helpers:**
     - `ril_root` → `${TASK_DIR:-aitasks}/metadata/release_issues`.
     - `ril_key <url>` → `printf '%s' "$url" | git hash-object --stdin`,
       rc checked, `${h:0:16}`, validated `^[0123456789abcdef]{16}$`.
     - `ril_name <task> <url>` → `<task>--<key>.rec`.
   - **Validators**, each returning 0 or 1:
     - `ril_valid_task_id`: `^[0123456789]+(_[0123456789]+)?$`, with explicit
       digits so the check never depends on locale ranges.
     - `ril_valid_url`: a `case` scheme gate `http://?*|https://?*`, then
       `rest="$(printf '%s' "$v" | LC_ALL=C tr -d "$RIL_URL_CHARSET"; printf x)"`
       must equal `x`.
     - `ril_valid_enum <v> <alt>...`.
     - `ril_valid_iso_utc`: `YYYY-MM-DDTHH:MM:SSZ`, explicit digits.
     - `ril_valid_field <field> <value>` dispatches over the pending fields
       `schema` (`== 1`), `task_id`, `issue_url`, `platform`
       (`github|gitlab`), `action` (`closed|commented|closed_silent`) and
       `recorded_at`. An unknown field returns 2.
   - **`ril_read <path> <field>`.**
     - rc 2: unknown field;
     - rc 1: missing or unreadable file;
     - rc 3 (MALFORMED): `grep -c "^${field}="` is not exactly `1`, or the
       value from `sed -n "s/^${field}=//p"` fails `ril_valid_field`.
     - On success it prints the value and returns 0. Field names come from the
       fixed set, so the `sed`/`grep` patterns are safe.
   - **`ril_find <task> <url>`.**
     - It checks `pending/<name>`, then each `released/*/<name>`; an unmatched
       glob is skipped by an `[[ -e ]]` guard.
     - On a hit it reads `task_id` and `issue_url` through `ril_read`:
       - byte-equal → prints `pending:<path>` / `released:<path>`, rc 0;
       - different → prints `<path>`, rc 4 (`hash_collision`);
       - a malformed hit → prints `<path>`, rc 3.
     - No hit → rc 1. A key failure → rc 5.
   - **`ril_record <task> <url> <platform> <action>`**, body `( … )`. It
     prints exactly one stdout line:
     - `RELEASE_LEDGER:recorded:<path>` / `RELEASE_LEDGER:duplicate:<path>`,
       exit 0;
     - or `RELEASE_LEDGER_FAILED:<reason>[:<path>]`, exit 1;
     - or nothing when a shared helper `die`d.

     **Helpers it adds** (both reused by t2261_2):
     - `ril_validate_pending_record <path>` checks the whole file:
       - every line is `key=value` with a known pending key;
       - each of the six keys occurs exactly once;
       - every value passes `ril_valid_field`.

       It returns 0, or 3 (MALFORMED).
     - `_ril_hit_state <path>` prints exactly one git state, using two probes:
       - `task_git rev-parse --verify --quiet "HEAD:$path"` (in HEAD or not).
         `rev-parse` is on the read-only list
         (`_ait_git_subcmd_is_readonly`), so the probe never `die`s on a
         wedged data worktree. `cat-file` is not on that list and would.
       - `task_git status --porcelain --untracked-files=all -- "$path"`, with
         its rc checked. `-uall` is needed because an untracked `pending/`
         directory would otherwise be reported as the directory, not the
         file.

       | In HEAD | status output | state |
       |---|---|---|
       | yes | empty | `committed` |
       | no | starts `??` | `untracked` |
       | no | starts `A` (`A `, `AM`) | `staged` |
       | yes | non-empty | `modified` |
       | either | the status probe failed | `unknown` |
       | no | anything else | `unknown` |

       It writes nothing.

     Its steps:
     1. Validate all four values. Reasons: `invalid_task_id`, `invalid_url`,
        `invalid_platform`, `invalid_action`. Compute `name` (`key_failed`) and
        `recorded_at` with `date -u +%Y-%m-%dT%H:%M:%SZ`, validated. Initialise
        `_RIL_TMP=""`, `_RIL_PATH=""` and `_RIL_OWNED=0`.
     2. Acquire the lock with
        `ait_ledger_lock_acquire release_issues ledger "release-issue ledger lock" "release-issue ledger lock"`.
        Then set
        `trap '_ril_rc=$?; _ril_record_cleanup; ait_ledger_lock_exit_trap "$_ril_rc"' EXIT`,
        followed by the guarded re-arm (finding 3).
     3. Run `ril_find`:
        - rc 0 → go to **step 3a** with the hit;
        - rc 3 → `malformed_record:<path>`;
        - rc 4 → `hash_collision:<path>`;
        - rc 5 → `key_failed`;
        - rc 1 → continue to step 4.

        **3a. Resolve a matching hit by its git state** (finding 12). This run
        did not publish the file, so `_RIL_OWNED` stays 0 and it is never
        deleted.
        - `committed` → `RELEASE_LEDGER:duplicate:<path>`, rc 0. This is the
          **only** duplicate success.
        - `untracked` or `staged`, **pending** hit → the residue of an
          interrupted writer. It must pass `ril_validate_pending_record`;
          otherwise `malformed_record:<path>`. Commit it with the same message
          (step 5's call).
          - rc 0 → `RELEASE_LEDGER:recorded:<path>`.
          - rc 1 or rc 2 → the same git-state re-classification as step 5's
            resolver. Finding `committed` with byte-equal HEAD means
            `recorded`.
          - Anything else → `residue_commit_failed:<path>`. That is
            retryable, and the file is kept for the next attempt.

          `_RIL_OWNED` is 0 here, so the deletion rule can never fire.
        - `untracked` / `staged` **released** hit → `uncommitted_record:<path>`.
          A released copy belongs to the release consumer's move, and
          committing half of it here would split that move. The file is kept.
        - `modified` → `uncommitted_change:<path>`. A committed record was
          edited and not committed, and that change is not this writer's to
          commit or discard. The file is kept.
        - `unknown` → `persistence_unknown:<path>`. Fail closed; the file is
          kept.
     4. Write the record:
        - `mkdir -p` the `pending` dir;
        - write a temp file there with `mktemp "$dir/.${name}.XXXXXX"`;
        - print the six `key=value` lines in contract order.
        - Publish with `ln -- "$tmp" "$path"`, and only then set
          `_RIL_PATH="$path"` and `_RIL_OWNED=1`.
        - `cmp -s` the temp file against the target, then remove the temp
          file.

        If `ln` fails and the target now exists, someone published it without
        the lock (e.g. a sync). Go back to step 3: a match goes through 3a,
        anything else is `publish_raced`. In both cases `_RIL_OWNED` is still
        0, so the file is never deleted. Any other write failure gives
        `write_failed`.
     5. Commit with
        `ait_commit_paths_staging_untracked "ait: Record release-pending issue for t<task>" "$path"`.
        - rc 0 → `_RIL_OWNED=0`, then `recorded:<path>`.
        - **rc 1 or rc 2 → `_ril_resolve_failed_commit <rc>`** (findings 13
          and 15). Neither return code says whether git holds the file.
          - rc 2 means the status check saw the path clean.
          - rc 1 is also returned when another operation commits the path
            **after** the helper's status check but before its `git commit`
            (git then reports "nothing to commit"). This window was
            reproduced in plan review with the real helper: `helper_rc=1`,
            the record in HEAD, status clean.

          So the result is decided by re-classifying with `_ril_hit_state`,
          never by the rc:
          - `committed`, and HEAD's blob byte-equal to the file
            (`task_git diff --quiet HEAD -- "$path"`) → another operation
            committed exactly these bytes, so the record is persisted. Set
            `_RIL_OWNED=0` → `RELEASE_LEDGER:recorded:<path>`, rc 0.
          - The path is absent from HEAD → roll back through
            **`_ril_delete_if_owned_and_absent`**, the same function cleanup
            uses (below). Then verify the file is gone from both the worktree
            and the index (`task_git ls-files --error-unmatch` fails). Result
            `commit_failed`, or `rollback_failed:<path>` if the verification
            fails.
          - Anything else (in HEAD with different bytes, `modified`,
            `unknown`) → `_RIL_OWNED=0`, keep the file →
            `commit_unverified:<path>`.

          There is **no other deletion anywhere in `ril_record`**. Neither
          branch calls `rm` on the record path directly.
     6. `_ril_finish <line> <rc>` ends every path:
        - it runs `_ril_record_cleanup` when rc ≠ 0; by the rule below this
          only ever deletes a file this run still owns;
        - it releases the lock with `ait_ledger_lock_release`, and a release
          failure only warns, because the record is already durable;
        - it runs `trap - EXIT` plus the guarded re-arm;
        - it prints the line and exits the subshell with rc.

     `_ril_record_cleanup` runs on the die path and through `_ril_finish`:
     - it removes the temp file;
     - it runs `( ait_unstage_staged_by_us ) || true`, nested so a guard `die`
       cannot pre-empt the lock release;
     - **its keep/delete decision is one rule in one function**,
       `_ril_delete_if_owned_and_absent`, which the rc-1/rc-2 resolver also
       calls. It deletes `_RIL_PATH` only when `_RIL_OWNED=1` **and**
       `task_git rev-parse --verify --quiet "HEAD:$_RIL_PATH"` fails, i.e. the
       path is absent from HEAD. It then sets `_RIL_OWNED=0`. The probe is
       read-only, so it works on a wedged worktree. A file git already holds is never deleted, so
       a die after a successful commit, or a foreign commit, can never produce
       a tracked deletion. A comment at the rule states why.

3. **Writer hook** in `aitask_issue_update.sh`.
   - **Sourcing and refactor.** Source `lib/release_issue_ledger.sh` after
     `issue_backends.sh`. Move lines 314-345 (URL resolution, source
     detection, GitLab slug) unchanged into `resolve_issue_target`, which sets
     the global `RESOLVED_ISSUE_URL`. It is called directly, never in `$( )`,
     because it prints `info` lines and may `die`.
   - **`ledger_action`:** `CLOSE_ISSUE && NO_COMMENT` → `closed_silent`;
     `CLOSE_ISSUE` → `closed`; else `commented`.
   - **`record_release_ledger <url>`:**
     - A `SOURCE` other than github/gitlab → print
       `RELEASE_LEDGER:skipped:unsupported_platform`, return 0.
     - Otherwise run
       `ril_record "$TASK_NUM" "$url" "$SOURCE" "$(ledger_action)" >"$tmp" || rc=$?`;
       the temp file comes from `mktemp`, and a mktemp failure gives
       `tmp_unavailable`.
     - Read the first `^RELEASE_LEDGER` line, then remove the temp file.
     - rc 0 with a `RELEASE_LEDGER:` line → print it, return 0.
     - Otherwise print the `RELEASE_LEDGER_FAILED:` line, or
       `RELEASE_LEDGER_FAILED:aborted` when none was printed, call
       `print_ledger_recovery_hint`, and return 3.
   - **`print_ledger_recovery_hint <reason-text>`** prints to stderr via
     `printf` (finding 7). The lead line is "The issue WAS updated — do not
     re-run this command; that would post the comment again." In
     `--record-only` mode it is "Nothing was posted (--record-only)."
     The rest of the hint has three categories:
     - **Never retryable:** `invalid_*` and `hash_collision`. The issue
       cannot be recorded, no retry will succeed, and its release
       notification will not be posted automatically.
     - **Needs a human first:** `malformed_record`, `uncommitted_record`,
       `uncommitted_change`, `persistence_unknown`, `commit_unverified` and
       `rollback_failed`. The hint names the record path and says to inspect
       and resolve it (commit, restore or remove), then gives the
       `record_only_command`.
     - **Retryable:** every other reason, such as `commit_failed`,
       `residue_commit_failed`, `write_failed`, `publish_raced`, `aborted` or
       `tmp_unavailable`. The hint prints "Record the release-ledger entry
       with:" and the `record_only_command` output. That command is
       `./.aitask-scripts/aitask_issue_update.sh --record-only --source <SOURCE> [--issue-url <u>] [--close] [--no-comment] <TASK_NUM>`,
       with each word `printf '%q'`-quoted. The URL charset includes
       `& ; ( ) ' $ ! * ? #`.
   - **`run_update`** ends Step 8 with
     `record_release_ledger "$issue_url" || exit $?`. `main` calls
     `run_update` **outside** any conditional, so errexit still aborts on a
     failed platform call before the hook. A wrapper like `run_update || rc=$?`
     would silently disable that, so it is forbidden. `--dry-run` returns
     before Step 8.

4. **`--record-only`.**
   - **Parsing.** `parse_args` sets `RECORD_ONLY=true`. It dies when combined
     with `--dry-run`. `--commits` is accepted and ignored, and
     `--no-comment` still requires `--close`.
   - **Dispatch.** `main` runs `run_record_only` when the flag is set, else
     `run_update`. `run_record_only` runs `resolve_issue_target`, then
     `info "Record-only: no platform call is made"`, then
     `record_release_ledger "$RESOLVED_ISSUE_URL" || exit $?`. It never calls
     `source_check_cli` or a backend.
   - **`--help`** gains:
     - the `--record-only` option, described as the recovery for exit 3;
     - a "Release ledger" paragraph: what is recorded, and that it is
       committed with the task data and read at release time;
     - an "Exit status" block:
       - 0 done (`RELEASE_LEDGER:recorded|duplicate|skipped:…`);
       - 1 failed before or during the platform call, nothing recorded;
       - 3 issue updated but ledger entry not recorded; run the printed
         `--record-only` command, never the original;
     - a `--record-only` example.

5. **Procedure lines**, after re-checking each shared file's diff vs HEAD
   just before editing it (shared-file rule):
   - **`.claude/skills/task-workflow/issue-update.md`**: after the three
     commands of the main section, add one bullet:
     > **Exit 3 / `RELEASE_LEDGER_FAILED:<reason>`**: the issue update
     > succeeded; only its release-ledger entry was not recorded. Do not
     > re-run the command, which would post the comment again. Run the
     > `--record-only` command the script printed on stderr (it makes no
     > platform call). If stderr says no retry will succeed, report it and
     > continue.

     The Related Issues section gets one line, "Exit 3 is handled as above."
   - **`.claude/skills/task-workflow/SKILL.md`**, inline FOLDED_ISSUE block:
     one bullet, "Exit 3 (`RELEASE_LEDGER_FAILED:`): handle as in
     `issue-update.md`. Never re-run the command."
   - **`.claude/skills/aitask-pickrem/SKILL.md.j2`**: one bullet after the
     FOLDED_ISSUE block, outside every Jinja conditional. It says the same,
     adapted to headless use: run the printed `--record-only` command, or
     report and continue.
   - **`.claude/skills/aitask-web-merge/SKILL.md`**: one line after "If
     'Skip': do nothing."
   - **Regenerate:**
     - `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`, via
       the `tests/test_skill_render_task_workflow.sh` render loop;
     - `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md`;
     - the committed prerenders, via `./.aitask-scripts/aitask_skill_rerender.sh remote`.
       Commit only the tracked `remote-` paths it changes:
       `{.claude,.opencode}/skills/task-workflow-remote-/`,
       `.agents/skills/task-workflow-remote-codex-/` and the
       `aitask-pickrem-remote-` trees.
   - **Review.** Review every golden and prerender diff: it must contain
     exactly the added lines.
   - **Verify.** Run `./.aitask-scripts/aitask_skill_verify.sh`,
     `bash tests/test_skill_render_task_workflow.sh` and
     `bash tests/test_skill_render_aitask_pickrem.sh`.
   - **The frozen fixture.**
     `tests/fixtures/skills/task-workflow/issue-update.md.pre-rewrite` is
     frozen and is **not** edited. Run
     `tests/test_skill_parity_runtime_vs_rendered.sh` to confirm it is
     unaffected.

6. **Tests** in the new `tests/test_issue_update_ledger.sh`. It uses the same
   harness as the pre-phase and a `git` wrapper on PATH. The wrapper exits 1
   for the `commit` subcommand when `AIT_TEST_FAIL_COMMIT=1` (it skips
   `-C x` / `-c x` to find the subcommand), and otherwise `exec`s the real
   git. Cases:
   - **(a) One record per action.** One `.rec` file each for close-with-notes,
     comment-only and close-silently. The fields are right
     (`action=closed|commented|closed_silent`, `platform=github|gitlab`,
     `schema=1`, `task_id`, exact `issue_url`, a valid `recorded_at`). The
     file is committed: `git status --porcelain -- <path>` is empty and
     `git log -1 --format=%s -- <path>` shows the message. stdout carries
     `RELEASE_LEDGER:recorded:<path>`.
   - **(b) Dry run.** `--dry-run` creates no `release_issues/` dir. The stub
     log holds exactly the auth check (`gh auth status`), with no
     `gh issue …` call (finding 14).
   - **(c) Failed platform call.** `STUB_FAIL=close` → non-zero exit, no
     record, no `RELEASE_LEDGER` line.
   - **(d) Dedupe.** A second identical run prints `duplicate:<same path>`
     and exit 0; there is still one file and no new commit (HEAD unchanged).
   - **(e) Concurrency.** 6 parallel writers with distinct pairs (tasks
     30..35) → 6 committed files, each with its own commit, and a clean
     index. 4 parallel writers with one identical pair → exactly 1 file:
     1 `recorded` and 3 `duplicate`.
   - **(f) Folded route.** `--issue-url <other> --close 10` → `task_id=10`,
     `issue_url=<other>`.
   - **(g) Commit failure.** With `AIT_TEST_FAIL_COMMIT=1`:
     `RELEASE_LEDGER_FAILED:commit_failed`, exit 3, no `.rec` file and no
     temp file left, the path not in the index, and the stub log shows the
     comment was posted. stderr contains "do not re-run" and the
     `--record-only` command. Running that exact command (taken from stderr)
     gives `recorded` and zero new stub calls.
   - **(h) URL target.** The GitHub stub argv carries the full URL; the
     GitLab argv carries the number plus `-R g/p`.
   - **(i) Invalid URL.** A URL containing `"` →
     `RELEASE_LEDGER_FAILED:invalid_url`, exit 3. The stub log shows the
     update happened, stderr says no retry will succeed, and nothing is
     written.
   - **(j) Malformed reads.** `ril_read` (lib sourced in a subshell, rc
     captured outside) gives rc 3 for a duplicated key, a bad-charset value
     and a missing field, and rc 2 for an unknown field. `ril_find` over a
     planted same-name file with a different URL gives rc 4.
   - **(k) Branch mode.** The fixture has an orphan `aitask-data` branch, a
     `.aitask-data` worktree and `aitasks` → `.aitask-data/aitasks`. A record
     is committed on `aitask-data`; `main`'s HEAD and index are untouched.
   - **(l) Bitbucket.** An `--issue-url https://bitbucket.org/w/r/issues/3`
     run, with a `bkt` stub, prints `RELEASE_LEDGER:skipped:unsupported_platform`
     and exit 0, and writes nothing.
   - **(m) Record-only mode.** `--record-only` with `--dry-run` → die.
     `--record-only` makes zero stub calls even with no `gh` on PATH. This is
     a new mode, and skipping the auth check is its defined behaviour, not a
     change to the existing path.
   - **(n) Untracked residue** (finding 12). Plant a complete, valid,
     matching record at `pending/<name>` as an **untracked** file, as a killed
     writer would leave it. Then `--record-only`:
     - `RELEASE_LEDGER:recorded:<path>`, exit 0;
     - the path is in HEAD with the planted bytes, and status is clean;
     - zero stub calls.

     Then a second `--record-only` → `duplicate`, HEAD unchanged.
   - **(o) Staged residue.** The same record, but `git add`ed and
     uncommitted (a writer killed between add and commit) → committed by the
     run, `recorded`, clean index.
   - **(p) Invalid residue.** A planted untracked matching file missing
     `recorded_at` → `RELEASE_LEDGER_FAILED:malformed_record:<path>`, exit 3.
     The file is kept, nothing is committed, and the hint names the path.
   - **(q) Edited committed record.** A committed matching record edited in
     the worktree → `uncommitted_change:<path>`, exit 3. The edit is kept and
     HEAD is unchanged.
   - **(r) rc-2 branch: a competing commit at the early window, before the
     status check** (finding 13). A git-wrapper mode
     (`AIT_TEST_FOREIGN_COMMIT=1`) acts once, guarded by a marker file, on the
     helper's `ls-files --error-unmatch -- <…​.rec>` probe. It first commits
     that path with the real git (`add` + `commit -m foreign -- <path>`), then
     runs the probe. That is exactly "another operation commits the published
     path before this writer's commit". Expected:
     - `RELEASE_LEDGER:recorded:<path>`, exit 0;
     - the file still exists, and HEAD holds it with the bytes this run wrote;
     - `git status --porcelain` is empty, so there is no tracked deletion;
     - HEAD's subject is `foreign`, proving the rc-2 branch, not rc 0, ran.
   - **(t) rc-1 branch: a competing commit at the late window** (finding 15).
     The helper's existing seam is used, not a wrapper:
     - create the opt-in marker `$AITASKS_LOCK_DIR/.ait_commit_scoped_test_seams`,
       the same one `tests/test_task_data_writer_guard.sh` uses;
     - set `AIT_COMMIT_SCOPED_SEAM_PREGIT="git commit -q -m foreign -- '<path>'"`,
       where `<path>` is precomputed from `git hash-object`.

     The seam fires inside `task_git_commit_scoped` **after** its status
     check and **before** its `task_git commit`. The competing commit
     therefore makes the helper's own commit fail with "nothing to commit",
     and the helper returns 1. Expected:
     - `RELEASE_LEDGER:recorded:<path>`, exit 0;
     - the file still exists, and HEAD holds this run's bytes;
     - `git status --porcelain` is empty, so there is no tracked deletion;
     - HEAD's subject is `foreign`.

     **Pre-fix control:** with the resolver temporarily replaced by the old
     unconditional `rm`, the same case leaves a tracked deletion. This is run
     once during implementation, and the result is recorded in the Final
     Implementation Notes, not committed. It shows the case discriminates.
   - **(s) A real `die` after publish, in the branch-mode fixture.** A
     git-wrapper mode (`AIT_TEST_WEDGE_ON_PROBE=1`) acts once on the helper's
     `.rec` `ls-files --error-unmatch` probe. It creates `MERGE_HEAD` in the
     data worktree's git dir (`git -C .aitask-data rev-parse --git-dir`). The
     helper's next `task_git add` then hits `assert_data_worktree_clean` and
     `die`s. That is the production die path the subshell exists for. Expected:
     - `RELEASE_LEDGER_FAILED:aborted`, exit 3;
     - stderr carries the "stuck mid-MERGE_HEAD" message and the hint;
     - the EXIT-trap cleanup removed the owned, uncommitted file: no `.rec`,
       no temp file, the path not in the index;
     - the ledger lock was released: a second writer acquires it at once;
     - after the test removes `MERGE_HEAD`, the printed `--record-only`
       command records it.

   All assertions run in the main shell, so no file-backed counters are
   needed. If one ends up inside `( … )`, opt into them (t1207).

## Verification

- `bash tests/test_issue_update_argv.sh` passes on the unmodified script
  (recorded) and after step 1, with only the `D` rows changed.
- `bash tests/test_issue_update_ledger.sh` passes.
- `shellcheck .aitask-scripts/aitask_issue_update.sh .aitask-scripts/lib/issue_backends.sh .aitask-scripts/lib/release_issue_ledger.sh`
  is clean, apart from the pre-existing SC1091 info lines.
- The skill checks pass:
  - `./.aitask-scripts/aitask_skill_verify.sh`;
  - `bash tests/test_skill_render_task_workflow.sh`;
  - `bash tests/test_skill_render_aitask_pickrem.sh`;
  - `bash tests/test_skill_parity_runtime_vs_rendered.sh`.
- The other affected tests pass:
  - `bash tests/test_terminal_compat.sh` (its `bash -n` list includes the
    script);
  - `python3 tests/test_archive_rearm_tripwire.py` (the new lib's traps);
  - `python3 tests/test_shell_startup_closure.py` (the new column-0 sources);
  - `bash tests/test_no_unscoped_task_commit.sh` (procedure edits).

## Step 9

- Commit the code (`feature: Record resolved issues in a release ledger
  (t2261_1)`) with explicit paths, then the plan separately through
  `aitask_task_commit.sh`.
- In Step 8e, send the note to t2251 through `/aitask-note`. The note says the
  `bitbucket_*` backend and the `source_*` bitbucket arms moved from
  `aitask_issue_update.sh` to `.aitask-scripts/lib/issue_backends.sh` in
  commit `<sha>`, so t2251's inventory line is stale. It is hedged as
  tree-relative, pinned to that sha.
- Then archive via task-workflow Step 9 and push.

## Risk

### Code-health risk: medium
- Moving the backends and switching GitHub to URL targets changes the script
  that every archival route calls. A regression breaks issue closing at
  archival. · severity: low (residual — addressed by inline pre-phase
  characterize_issue_update_argv) · → mitigation: inline pre-phase
  characterize_issue_update_argv
- Exit 3 (ledger failed after a successful update) could lead a caller to
  re-run the full command and double-post the resolution comment. It is now
  covered at all four call sites (step 5) and by the reason-aware stderr hint
  (step 3). · severity: low · → mitigation: none (in plan)
- Records build up in user projects that never run `release-notify`. They are
  tiny files. · severity: low · → mitigation: none
- Same-file overlap with t2251. · severity: low · → mitigation: none (note,
  Step 9)
- The procedure lines touch `task-workflow/SKILL.md` and `pickrem`'s template,
  so their goldens and committed `remote-` prerenders must be regenerated
  together. A stale one fails the render tests or ships an outdated headless
  procedure. · severity: low · → mitigation: none (in plan: step 5
  regeneration, diff review, render tests)
- The ledger commit runs through `task_git` in branch mode, the production
  mode. A path or worktree mistake would only show there. · severity: low ·
  → mitigation: none (in plan: test cases (k) and (s))
- Interrupted writers: a duplicate success for an untracked record, or a
  cleanup that deletes a file git already holds. Either would lose a record or
  create a tracked deletion. Raised in plan review and addressed in the
  design:
  - the hit-state classification (step 3a);
  - the single `_ril_delete_if_owned_and_absent` rule, the only deletion
    path;
  - the shared rc-1/rc-2 re-classification;
  - tests (n)-(t), with both competing-commit windows.
  · severity: low (residual) · → mitigation: none (in plan)

### Goal-achievement risk: low
None identified.

The two new bullets are covered by steps already in the plan, and there are no
new mitigation candidates. The confirmed set below is unchanged from the
original planning session.

### Planned mitigations
- timing: pre-phase | name: characterize_issue_update_argv | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: backend extraction / GitHub URL-target regression at archival | desc: Pin gh/glab argv per action on the unmodified aitask_issue_update.sh before extracting the backends (t2261_1)

## Post-Review Changes

### Change Request 1 (2026-11-10 11:40)
- **Requested by user:** `_ril_on_existing` returned `duplicate` for a committed
  matching file after `ril_find` had checked only `task_id` and `issue_url`. The
  whole-record validator ran only for untracked/staged residue. A committed
  pending record with `schema=999` and no `recorded_at` therefore made
  `--record-only` exit 0 with `RELEASE_LEDGER:duplicate` (reproduced by the
  reviewer, CONFIRMED). Validate existing records before any duplicate success,
  keep malformed files with the existing diagnostic, and add the regression.
- **Changes made:** `_ril_on_existing` now validates every matching hit before
  classifying its git state. A pending hit gets the full
  `ril_validate_pending_record`. A released hit gets the new
  `_ril_pending_fields_ok`: each of the six pending fields exactly once and
  valid. Other keys are not judged, because a released copy also carries
  released-only keys whose validators t2261_2 adds. A malformed hit finishes
  with `RELEASE_LEDGER_FAILED:malformed_record:<path>`. The file is kept
  (`_RIL_OWNED` is 0 for any hit), and the hint names it. The residue branch's
  own validation call is gone, since validation now runs first for every hit.
  New tests:
  - (u) a committed corrupt pending record → `malformed_record`, exit 3, file
    byte-identical, HEAD unchanged;
  - (v) a committed released record with an extra `released_tag=` key →
    `duplicate`;
  - (v) the same record with `schema=999` → `malformed_record`.

  Before the fix, (u) and the corrupt half of (v) failed: 5 failures, with
  exit 0 and `duplicate` reported. After the fix: 128/128.
- **Files affected:** `.aitask-scripts/lib/release_issue_ledger.sh`,
  `tests/test_issue_update_ledger.sh`.

## Final Implementation Notes

- **Actual work done:**
  - **`.aitask-scripts/lib/issue_backends.sh` (new).** The GitHub, GitLab and
    Bitbucket backends and the `source_*` dispatchers, moved verbatim from
    `aitask_issue_update.sh`. The only functional change is `source_issue_ref`:
    GitHub now receives the issue URL. GitLab still receives the number plus
    `-R slug`. SC2046 is disabled, with a reason, on the deliberate
    `$(glab_repo_flag)` split.
  - **`.aitask-scripts/lib/release_issue_ledger.sh` (new).** It implements the
    contract:
    - `ril_root`, `ril_key`, `ril_name`;
    - the validators, including a NUL/stray-byte check counted with `wc`;
    - `ril_read`, `ril_validate_pending_record`, `_ril_pending_fields_ok`,
      `ril_find`, `_ril_hit_state`;
    - `ril_record`, with a subshell body, lock + EXIT trap, publish by hard
      link, and the single deletion rule `_ril_delete_if_owned_and_absent`.
  - **`aitask_issue_update.sh`.**
    - URL/source resolution moved, unchanged, into `resolve_issue_target`.
    - A Step-9 hook (`record_release_ledger`) prints `RELEASE_LEDGER:*`, or
      `RELEASE_LEDGER_FAILED:*` with exit 3 and a reason-aware stderr hint.
    - The new `--record-only` mode, and `--help` with a "Release ledger"
      paragraph and an "Exit status" block.
  - **Procedure lines** in `task-workflow/issue-update.md` (main and related
    sections), the inline FOLDED block of `task-workflow/SKILL.md`,
    `aitask-pickrem/SKILL.md.j2` and `aitask-web-merge/SKILL.md`. The goldens
    are regenerated (task-workflow `SKILL-{default,fast,remote}.md`, pickrem
    `SKILL-remote-claude.md`), and so are the 9 committed `remote-` prerender
    files (claude/codex/opencode × task-workflow `SKILL.md` + `issue-update.md`,
    pickrem `SKILL.md`).
  - **Tests.**
    - `tests/test_issue_update_argv.sh`: 41 assertions, `[C]`/`[D]` tagged.
    - `tests/test_issue_update_ledger.sh`: 128 assertions, cases (a)-(v).
    - The shared fixture `tests/lib/issue_update_fixture.sh`.
- **Deviations from plan:**
  1. **A shared fixture lib** (`tests/lib/issue_update_fixture.sh`) holds the
     stubs, the repo, the renderer and the runner for both test files. The
     plan defined them per file.
  2. **The dry-run assertion in the argv test** compares HEAD and the ledger's
     file list before and after the dry run. The plan said "no
     `release_issues/` directory afterwards". That was true only before step 3:
     once the hook exists, the earlier non-dry runs in the same fixture record
     legitimately.
  3. **The hint for `aborted` reads back the data-worktree wedge state**
     (`ait_data_inprogress_state`) and names it. The shared helper silences the
     guard's own `die` message (see the upstream defects below), so without
     this the user saw `aborted` with no cause. Test (s) asserts it.
  4. **Records are written mode 0644** (`chmod` before the hard link):
     `mktemp` creates 0600.
  5. **Change Request 1** (see Post-Review Changes): every matching hit is
     validated before any duplicate success, and the new
     `_ril_pending_fields_ok` judges released hits.
- **Issues encountered:**
  - **The first full run was 117/118.** Test (s) expected the guard's "stuck
    mid-MERGE_HEAD" message on stderr, but `ait_commit_paths_staging_untracked`
    sends its per-path `add`'s stderr to `/dev/null`. This was resolved by
    deviation 3.
  - **`main` advanced to 79416f14c (t2268)** mid-session. It touched only the
    model registry files, so there was no overlap.
  - **The working tree held other sessions' uncommitted changes** (`monitor/`,
    `sitrep_tui/`, `lib/tmux_exec.py`, `aidocs/framework/monitor_status_protocol.md`,
    two test files). They were excluded from the commit by naming paths.
- **Key decisions:**
  - **`ril_record` has a subshell body.** A `die` in a shared helper, its EXIT
    trap and its staging list can therefore never reach the issue-update
    script, which still runs under plain `set -e`. `main` calls `run_update`
    outside any conditional, so a failed platform call still exits before the
    hook.
  - **No commit return code is trusted to say where the bytes are.** rc 1 and
    rc 2 both re-classify by git state. A competing commit can produce either:
    rc 2 at the early window, before the status check, and rc 1 at the late
    window, after it.
  - **The HEAD probes use `rev-parse --verify --quiet HEAD:<path>`.** It is on
    `task_git`'s read-only list, so it never dies on a wedged worktree.
    `cat-file` is not on that list.
  - **The URL validator is byte-safe.** It uses `LC_ALL=C tr -d <charset>`
    plus the `printf x` sentinel, the `validate_file_ref` idiom. Digits are
    spelled out, never `[0-9]`.
- **Evidence (durable):**
  - **Pre-change characterization.** `tests/test_issue_update_argv.sh` was run
    on the unmodified script at HEAD 79416f14c. The script blob is 936d9a96,
    identical at 0e17732b1. With `GH_REF_7="7"` / `GH_REF_42="42"` the result
    was 39 passed / 0 failed. The same file with the URL values on the same
    unmodified script gave 35 passed / 4 failed: exactly the 4 `[D]` GitHub
    rows. After the extraction and the hook: 41/41 (two dry-run assertions
    added in deviation 2).
  - **Pre-fix controls for the review findings.** A scratch copy of
    `.aitask-scripts` was patched back to two behaviours: the old rc-only
    `_ril_commit_record` with an unconditional rm, and presence-as-duplicate
    in `_ril_on_existing`. `tests/test_issue_update_ledger.sh` run against it
    gave 101 passed / 17 failed, all in the targeted cases:
    - (t) late window: file deleted, `git status` shows ` D <path>`, the
      tracked deletion the reviewer reproduced;
    - (n)-(q): the residue left uncommitted, or an edit / malformed file
      reported as a duplicate;
    - (r): `commit_unverified` instead of recorded.
  - **Change Request 1.** Before the fix: 123 passed / 5 failed. (u) and the
    corrupt half of (v) exited 0 with `duplicate`. After: 128/128.
  - **Final runs.**
    - Ledger 128/128 and argv 41/41.
    - shellcheck: nothing but SC1091 info.
    - `aitask_skill_verify.sh` rc 0, `test_skill_render_task_workflow.sh`
      365/365, `test_skill_parity_runtime_vs_rendered.sh` 86/86,
      `test_terminal_compat.sh` 37/37.
    - The trap tripwire 15/15 and the startup-closure test 9/9.
    - `test_skill_render_aitask_pickrem.sh` Test 6 compares against the
      committed prerender, so it is re-run after the commit.
- **Upstream defects identified:**
  - `.claude/skills/task-workflow/premise-staleness.md:213` —
    `tests/test_no_unscoped_task_commit.sh` reports an unscoped task-data
    commit instruction (`AIT_UNPARSEABLE_SPAN`) here. The same failure (102
    passed / 1 failed) reproduces on a clean detached-HEAD worktree at
    79416f14c, so it predates this task.
  - `.aitask-scripts/lib/task_utils.sh:1101` — `ait_commit_paths_staging_untracked`
    runs `task_git add -- "$p" >/dev/null 2>&1`. When `task_git`'s
    `assert_data_worktree_clean` dies there, the die message goes to
    `/dev/null`: the process exits 1 with no cause printed. This affects every
    caller of the helper, not only the release ledger.
- **Notes for sibling tasks (t2261_2):**
  - **Extend the lib; do not fork it.** `RIL_PENDING_FIELDS`,
    `ril_valid_field` and `_ril_pending_fields_ok` are the extension points.
    Add the released fields (`released_tag`, `notified_at`, `outcome`,
    `commits`) and a whole-record released validator next to
    `ril_validate_pending_record`. `_ril_on_existing` then validates released
    hits with it, instead of with `_ril_pending_fields_ok`.
  - **Reuse the patterns for the move helper:**
    - a subshell body with lock + EXIT trap + guarded
      `ait_archive_rearm_exit_trap`;
    - `_ril_finish` exits the subshell;
    - `_ril_hit_state` for the git state;
    - never `cat-file` under `task_git`;
    - never decide persistence from a commit helper's rc.
  - **The ledger lock** is `ait_ledger_lock_acquire release_issues ledger`.
    The consumer's run lock (`release_notify run`) is a different key.
  - **`lib/issue_backends.sh`** is where `github_list_comment_bodies` /
    `gitlab_list_comment_bodies` go. GitHub functions take a URL ref.
  - **The test fixture** `tests/lib/issue_update_fixture.sh` (stubs that log
    `%q` argv, `ifx_make_repo`, `ifx_run`) and the ledger test's `git` wrapper
    modes are reusable. The helper's `AIT_COMMIT_SCOPED_SEAM_PREGIT` seam, with
    the marker `$AITASKS_LOCK_DIR/.ait_commit_scoped_test_seams`, injects at
    the late commit window.
  - **Docs are still owed** by t2261_2 step 5:
    `website/content/docs/commands/issue-integration.md` must gain
    `--record-only`, the `RELEASE_LEDGER*` outputs and exit 3 (`--help`
    already documents them).
