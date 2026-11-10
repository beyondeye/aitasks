---
Task: t2261_2_release_notify_consumer_and_publication_gate.md
Parent Task: aitasks/t2261_release_issue_notifications.md
Sibling Tasks: aitasks/t2261/t2261_1_*.md
Archived Sibling Plans: aiplans/archived/p2261/p2261_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-10 13:41
---

# t2261_2 — Release-notify consumer, publication gate, release integration, docs

## Context

This is the consumer half of t2261. t2261_1 (landed, cd1699c9f) records one
`.rec` file per resolved issue under `aitasks/metadata/release_issues/pending/`,
and added the shared `lib/issue_backends.sh` and `lib/release_issue_ledger.sh`.

This child does four things:
- posts "Released in vX.Y.Z" on each due issue, but only after the release
  is verifiably published;
- moves each record to `released/<tag>/`;
- runs automatically from the framework's local release command;
- documents it all.

**The parent plan `aiplans/p2261_release_issue_notifications.md` is
authoritative** for the ledger contract and for these user decisions, which
are not to be reopened:
- automatic posting after publication, with no prompt;
- every posting entry point is gated: freshness → designation → publication;
- the publication policy is per project, in `project_config.yaml`;
- one designated machine, with no distributed lock and no failover;
- no automatic catch-up (that is t2266, which exists);
- duplicate prevention covers serialised and sequential runs only, and is
  never claimed as exactly-once.

## Verification findings (2026-11-10, HEAD e16e440e4)

Checked against the code. The approach holds. Corrections, now folded into
the steps below:

- **V1 — lock state is per-shell globals.** `ait_ledger_lock_acquire` stores
  the held lock in `_AIT_LEDGER_LOCK_DIR` / `_AIT_LEDGER_LOCK_TOKEN`
  (`lib/ledger_block.sh:51-80`). If one shell holds the `release_notify run`
  lock and then takes the `release_issues ledger` lock, the second acquire
  overwrites the first's token. So the per-record move helper is a **subshell
  function**, like `ril_record`, and the run lock lives in the consumer's
  main shell. `ait_ledger_lock_acquire` also `die`s when its retries run out.
  The consumer maps that to `INCOMPLETE:run_lock:busy`, exit 3, through a
  phase flag that its EXIT trap reads (step 2).
- **V2 — released-record validators were deferred to this child.** t2261_1's
  notes say: extend `ril_valid_field` / `_ril_known_field`, add a whole-record
  `ril_validate_released_record`, and switch `_ril_on_existing`'s released
  branch from `_ril_pending_fields_ok` to it (new step 1d).
- **V3 — `aitask_sync.sh --batch` prints its status on the FIRST line.**
  `DEFERRED_FILE:` continuation lines can follow it. The wrapper reads line 1
  only.
- **V4 — `require_python` dies** (`lib/python_resolve.sh:81`). The policy
  reader uses `resolve_python` and maps an empty result to
  `unknown:policy_unreadable:<key>`. The shell reader `project_config_values`
  (`lib/gate_verifier_lib.sh:77`) is not used: it cannot see a block mapping,
  which reads as "absent" (the t1672 hole), and that would fail open.
- **V5 — docs inventory was incomplete.** Also needed:
  `website/content/docs/workflows/releases.md` (the framework release steps:
  "Create release → Publish" gains the notification step and its retry),
  `website/content/docs/commands/_index.md` (a command-table row), one
  clause in `website/content/docs/development/_index.md` step 2, and the
  `ait --help` line under "Integration:".
- **V6 — asset-name derivation for the contract test.** `packaging/shim/ait`
  publishes as its basename `ait`. `${{ github.ref_name }}` maps to `{tag}`,
  `${VERSION}` to `{version}`. `goengines/dist/*` holds the cross-built
  binaries plus `<cmd>_<version>_SHA256SUMS.txt`, one per `goengines/cmd/<cmd>`
  (today only `ait-testmap`). Captured release assets match the policy below.
- **V7 — `task_push` reports through `TASK_PUSH_STATUS`**
  (`pushed|up-to-date|no-remote|failed`). The consumer maps
  `pushed`/`up-to-date` → `PUSH:ok`, `no-remote` → `PUSH:skipped`,
  `failed` → `PUSH:failed`.
- **V8 — the move commit.** `ait_commit_paths_staging_untracked` commits a
  tracked path's deletion through `commit -o` (documented at
  `lib/task_utils.sh:1060-1078`), so `<released> <pending>` lands as one
  commit. Persistence is judged from git state (`_ril_hit_state`), never from
  the helper's rc alone (the t2261_1 rule).
- **V9 — the tag is untrusted input** that becomes a directory name, a marker
  and a URL part. `T`, `P` and every `E` are validated with
  `^[A-Za-z0-9._+-]+$`: no leading `-`, not `.` or `..`. A failure is exit 2,
  refused input.
- **V10 — the framework `release_notify_host`** is this machine's
  `hostname`, `omg16`. It is committed to the task-data branch, which is
  pushed to origin.
- **V11 — an interrupted move must be resumable** (review finding 1). There
  are two crash windows:
  - after the released copy is published, before the pending file is
    removed: both files exist;
  - after the removal, before the commit: an uncommitted released copy plus
    a tracked deletion of the pending file.

  A consumer that scans only `pending/` cannot see the second state, and the
  hard-link publish would refuse the first. Step 1d defines
  `ril_resume_move`. Step 2 runs a **residue sweep** under the run lock
  before classifying records. Tests interrupt the move in both windows and
  prove the retry commits it with no second comment.
- **V12 — policy key detection must not depend on formatting** (review
  finding 2). YAML allows quoted keys (`"release_publication_workflow": …`)
  and flow mappings, and a line-start grep misses both, which would degrade
  a configured policy to the generic one. There is now no grep shortcut:
  - an existing config file is always parsed with `yaml.safe_load` through a
    loader that refuses duplicate keys;
  - absence counts as proven only when the file does not exist, or when the
    parse succeeded and the key is not in the top-level mapping;
  - a read error, a non-mapping document, a duplicate key or a missing Python
    is `unknown:policy_unreadable:<reason>`.
- **V13 — GitLab checksum manifests need a GitLab download path** (review
  finding 3). Manifests are fetched with `glab release download T -R <slug>
  -n <name> -D <tmpdir>`. The listed files are validated against
  `assets.links[].name` on GitLab, and against the uploaded, non-empty asset
  state on GitHub.
- **V14 — the pending whitelist stays pending-only** (review finding 4).
  `ril_validate_pending_record` uses `_ril_known_field` as its key
  whitelist. Widening that helper would let a pending record carry
  released-only keys, even duplicated invalid ones, and still validate. So
  the field sets get separate predicates (step 1d).
- **Unchanged and confirmed:**
  - t2251, the Bitbucket retirement in `lib/issue_backends.sh`, is still
    Ready. This child only *adds* functions there, and t2261_1 already sent
    the note.
  - `create_new_release.sh` runs under `set -euo pipefail` and ends at the
    push and the "Done!" lines.
  - `release.yml`'s `packaging` job is `uses:
    ./.github/workflows/release-packaging.yml`.
  - No settings registry ↔ seed parity test exists. Only
    `test_every_key_declares_a_type` runs over `PROJECT_CONFIG_SCHEMA`.
  - `ait release-notify` is a human-typed command, so it gets a dispatcher
    case. It needs no whitelist entries, because no skill invokes it.

## Implementation

1a. **Attested data freshness**: `ril_data_freshness` in
   `lib/release_issue_ledger.sh`.
   - Do **not** use `desync_state.py`. Its `count_ahead_behind` returns `0,0`
     when `rev-list` fails, which reads as a silent all-clear.
   - Select the ref and the git runner by mode, from `ait_data_mode`:
     - branch mode: ref `aitask-data`, git through `task_git`;
     - legacy mode: ref = the current branch (`git symbolic-ref --quiet
       --short HEAD`), git in the repo root. A detached HEAD →
       `unknown:detached`.
   - The steps, checking every rc:
     - `remote get-url origin` fails → `unknown:no_remote`;
     - `fetch --quiet origin <ref>` fails → `unknown:fetch_error`;
     - `rev-parse --verify --quiet refs/heads/<ref>` or
       `refs/remotes/origin/<ref>` fails → `unknown:missing_ref`;
     - `rev-list --count <ref>..origin/<ref>` fails, or prints something other
       than `^[0123456789]+$` → `unknown:count_failed`;
     - a count above 0 → `behind:<n>`;
     - a count of 0 → `fresh`.
   - It prints one state line, with rc 0 only for `fresh`.
1b. **Publication policy and check**: new shipped
   `.aitask-scripts/lib/release_publication.sh`, plus the small shipped
   reader `.aitask-scripts/lib/release_publication_policy.py`.
   - **Policy keys**: top-level and optional, in
     `aitasks/metadata/project_config.yaml`:
     - `release_publication_workflow`: string, a GitHub workflow file name;
     - `release_publication_assets`: a string or a list of templates. Only
       `{tag}` and `{version}` are allowed (`version` = the tag minus a
       leading `v`), and each substituted name must match
       `^[A-Za-z0-9._+-]+$`;
     - `release_publication_checksum_manifests`: a string or a list of globs.
   - **Reading the policy** (`release_publication_policy_load`, V12). The
     same reader serves `release_notify_host` in 1c:
     - config file absent (`[[ ! -e ]]`) → proven absence, generic policy;
     - present but not a readable regular file →
       `unknown:policy_unreadable:read_error`;
     - otherwise always parsed: `resolve_python` (empty →
       `unknown:policy_unreadable:python_unavailable`) runs the `.py` reader
       under `-I`. There is no grep shortcut, because quoted keys and flow
       mappings must count;
     - the reader uses `yaml.safe_load` with a `SafeLoader` subclass whose
       mapping constructor **refuses duplicate keys**;
     - the document must be a mapping, or empty/null (= every key absent).
       Anything else → `policy_unreadable:document`;
     - it type-checks each of the four keys: a scalar, or a list of scalars
       for the `string_or_list` ones. A mapping or other wrong type → that
       key;
     - it prints `VAL\t<key>\t<value>` lines and ends with one `OK` line. A
       missing `OK`, a non-zero rc or an `ERR\t<reason>` line →
       `unknown:policy_unreadable:<reason or key>`. Truncated output is
       never trusted;
     - placeholder and name validation (`{tag}` / `{version}` only,
       `^[A-Za-z0-9._+-]+$`) happens in bash after the parse, with the same
       `unknown:policy_unreadable:<key>` result. It never degrades to
       generic.
   - **`release_publication_expand_assets <tag>`**: prints the instantiated
     required names. This is the one template function, shared with the
     contract test.
   - **`release_publication_check <tag>`**: one non-waiting check that prints
     exactly one line:
     - `PUBLICATION:published|<run-id or ->` → rc 0;
     - `PUBLICATION:pending:<r>` → rc 10, where `<r>` is one of
       `no_release`, `draft`, `upcoming`, `run_not_found`,
       `run_in_progress`, `assets_missing:<csv>`, `manifest_missing:<glob>`;
     - `PUBLICATION:failed:<r>` → rc 11, where `<r>` is one of
       `workflow_failed:<conclusion>`, `tag_mismatch`, `remote_tag_missing`;
     - `PUBLICATION:unknown:<r>` → rc 12, where `<r>` is one of
       `api_error`, `unparseable`, `cli_missing`,
       `policy_unreadable:<key>`, `workflow_unsupported`, `platform`.
   - **The checks run in this order:**
     1. **Remote tag.** `git ls-remote --tags origin "refs/tags/T"` and
        `"refs/tags/T^{}"`; prefer the peeled sha. None → `remote_tag_missing`.
        It must equal `git rev-parse "T^{commit}"`, else `tag_mismatch`.
     2. **Platform** comes from origin (`detect_platform`), and the host and
        slug from the remote URL, ssh (`git@host:o/r.git`) and https forms.
        Anything else → `unknown:platform`.
     3. **GitHub release.** `gh release view T -R <slug> --json
        tagName,isDraft,assets`. A 404 (`release not found` on stderr) →
        `pending:no_release`; any other failure → `unknown:api_error`. Then
        `tagName==T` and `!isDraft`. Parse with `gh --jq`, so `jq` is not
        required on GitHub.
     4. **GitLab release.** `glab api "projects/<urlenc slug>/releases/T"`.
        A 404 → `pending:no_release`. `upcoming_release==true` →
        `pending:upcoming`. A configured workflow →
        `unknown:workflow_unsupported`.
     5. **Workflow (GitHub).** `gh run list -R <slug> --workflow F --event
        push --branch T --json databaseId,headSha,headBranch,status,conclusion,createdAt
        --limit 50`.
        - Filter `headBranch==T && headSha==<tag sha>`, then take the max
          `databaseId`.
        - None → `pending:run_not_found`.
        - Not `completed` → `pending:run_in_progress`.
        - `conclusion != success` → `failed:workflow_failed:<c>`.
     6. **Assets.**
        - Each required name must be present with `state==uploaded` and
          `size>0` (GitHub), or present in `assets.links[].name` (GitLab).
        - Each manifest glob is matched against asset names with bash
          pattern matching. Zero matches → `pending:manifest_missing:<glob>`.
        - Each match is downloaded by platform (V13):
          - GitHub: `gh release download T -R <slug> -p <name> -O -`;
          - GitLab: `glab release download T -R <slug> -n <name> -D <tmpdir>`,
            reading `<tmpdir>/<name>`.

          A download failure → `unknown:api_error`.
        - Each manifest is parsed for `^[0-9a-f]{64}[ ][ *](.+)$` lines. Any
          other non-blank line → `unknown:unparseable`.
        - Every listed file must be an asset by the same platform rule as the
          required names: present, uploaded and non-empty on GitHub; present
          in `assets.links[].name` on GitLab.
        - All missing names are collected into one `assets_missing:<csv>`.
   - **Registration:**
     - `.aitask-scripts/settings/settings_app.py` `PROJECT_CONFIG_SCHEMA`
       entries: `release_publication_workflow` (`string`),
       `release_publication_assets` and
       `release_publication_checksum_manifests` (`string_or_list`), and
       `release_notify_host` (`string`);
     - `seed/project_config.yaml`: commented generic examples
       (`myapp-{tag}.tar.gz`, `release.yml`, `*_SHA256SUMS.txt`) and
       `# release_notify_host: <hostname>`;
     - the framework repo values in `aitasks/metadata/project_config.yaml`,
       committed with `./.aitask-scripts/aitask_metadata_commit.sh
       aitasks/metadata/project_config.yaml`:
       - `release_publication_workflow: release.yml`;
       - `release_publication_assets`: `aitasks-{tag}.tar.gz`, `ait`,
         `aitasks_{version}_all.deb`, `aitasks-{version}-1.noarch.rpm`,
         `ait-testmap_{version}_SHA256SUMS.txt`;
       - `release_publication_checksum_manifests`: `*_SHA256SUMS.txt`;
       - `release_notify_host: omg16`.
1c. **Designation**: `release_notify_designation` in the ledger lib.
   - It reads the `release_notify_host` scalar with the same Python reader
     and fail-closed rules. The value must match `^[A-Za-z0-9._-]+$`.
   - It is compared byte-exact with `hostname`, the same source
     `aitask_lock.sh::get_hostname` uses. A failing or empty `hostname` →
     `unknown:hostname`.
   - States:
     - `designated:<h>` → rc 0;
     - `not_designated:<d>|<this>` → rc 1;
     - `unset` → rc 1;
     - `unknown:<r>` → rc 1.
1d. **Released-record validation and the move helper** (ledger lib, V1/V2).
   - Add `RIL_RELEASED_FIELDS=(released_tag notified_at outcome commits)`.
   - Extend `ril_valid_field` with these arms:
     - `released_tag`: the V9 tag rule;
     - `notified_at`: ISO UTC;
     - `outcome`: `posted|already_present`;
     - `commits`: a non-empty csv of 40 lowercase hex characters each.
   - **Field predicates stay separate (V14).**
     - `_ril_known_field` keeps its exact current meaning, pending fields
       only. It stays the whitelist of `ril_validate_pending_record`, which is
       not changed.
     - Add `_ril_known_released_field` (the four released fields) and
       `_ril_readable_field` (either set).
     - `ril_read` switches its unknown-field check to `_ril_readable_field`,
       so it can read released fields. On a pending record a released key is
       still absent, so it reads MALFORMED.
     - Regression, in a new section of `tests/test_issue_update_ledger.sh`: a
       pending record with an extra `outcome=posted` line, and one with that
       line twice, are both MALFORMED. The consumer reports them `MALFORMED:`
       and posts nothing for them.
   - Add `ril_validate_released_record <path>`: every line is `key=value`
     with a key from either set, the six pending fields plus the four
     released fields each occur exactly once, and every value is valid.
   - `_ril_on_existing`'s released branch calls it instead of
     `_ril_pending_fields_ok`. Then update the two t2261_1 tests that pinned
     the old behaviour: case (v), a released record with only an extra
     `released_tag=`, now needs the full released field set to count as a
     `duplicate`.
   - Add `ril_move_released <pending_path> <tag> <outcome> <commits_csv>`, a
     **subshell** body that reuses `ril_record`'s pattern:
     - take the `release_issues ledger` lock, install the EXIT trap, and
       guard the `ait_archive_rearm_exit_trap` re-arm;
     - re-validate the pending record;
     - write `released/<tag>/<name>` from a temp file with a hard-link
       publish. The content is the original fields plus `released_tag`,
       `notified_at`, `outcome` and `commits`;
     - check it with `ril_validate_released_record`, then `rm` the pending
       file;
     - commit with `ait_commit_paths_staging_untracked "ait: Record release
       notice for t<task> (<tag>)" <released> <pending>`;
     - decide the result from `_ril_hit_state` of both paths, never from the
       rc (V8);
     - on failure, restore the pending file from the saved bytes, delete the
       released file only if this run published it and HEAD does not hold it,
       and report `commit_failed`;
     - an **existing released target** goes through `ril_resume_move`, under
       the lock already held, instead of failing the hard link;
     - print one line: `RIL_MOVED:<released path>`,
       `RIL_MOVE_RESUMED:<released path>` or
       `RIL_MOVE_FAILED:<reason>[:<path>]`.
   - **Resuming an interrupted move (V11)**: `ril_resume_move <released_path>`
     takes the same ledger lock, unless it is entered from inside
     `ril_move_released`. The rc-only rollback in `ril_move_released` covers
     a commit that *returned* a failure. This covers the process dying in
     either crash window.
     - **Inputs that qualify as residue:**
       - a `released/<tag>/<name>` whose `_ril_hit_state` is `untracked` or
         `staged`;
       - or a `pending/<name>` that is in HEAD but missing from the worktree
         (`task_git ls-files --deleted -- <root>/pending/`). It is paired with
         the released file of the same name under any tag.
     - **Before adopting**, every check must pass:
       1. the released file passes `ril_validate_released_record`;
       2. the directory name equals its `released_tag`;
       3. the filename equals `ril_name <task_id> <issue_url>` of its own
          fields;
       4. its six pending fields equal, byte for byte, those of the pending
          record it came from. That record is
          `task_git show HEAD:<pending path>` when HEAD holds the pending
          path, else the worktree pending file. With neither →
          `RIL_MOVE_FAILED:unverifiable:<path>`;
       5. a worktree pending file that is still present matches the HEAD
          copy, or is untracked with the same fields;
       6. the pending path has no other git state (for example, it is not
          modified in the index).

       Any mismatch → `RIL_MOVE_FAILED:residue_mismatch:<path>`. **Nothing
       is deleted or rewritten**, and the record is left for a human.
     - **Completing the move:** remove the worktree pending file if it is
       still present, then commit `<released> <pending>` with the same
       helper and the same git-state verdict. On failure: restore the
       pending file from the saved bytes when this call removed it, and leave
       the released residue in place. It is still valid residue for the next
       retry.
     - An **unpaired pending deletion**, with no released file of that name
       anywhere, is reported `RIL_MOVE_FAILED:unpaired_pending_deletion:<path>`.
       Nothing is restored automatically, because whoever deleted it may have
       meant to.
     - A test-only seam, `_RIL_MOVE_TEST_SEAM=after_publish|after_remove`,
       is honoured only when the marker file
       `$AITASKS_LOCK_DIR/.ril_move_test_seams` exists, the same gating as the
       existing `AIT_COMMIT_SCOPED_SEAM_PREGIT`. At that point it sends
       `kill -KILL` to the move subshell's `$BASHPID`, so the tests reproduce
       real process death and not a returned failure.
1. **Comment listing (tri-state)** in `lib/issue_backends.sh`.
   - **GitHub**, `github_list_comment_bodies <url>`: parse
     `https://<host>/<owner>/<repo>/issues/<n>`, then
     `gh api --paginate [--hostname <host> when not github.com]
     "repos/<o>/<r>/issues/<n>/comments" --jq '.[].body'`.
   - **GitLab**, `gitlab_list_comment_bodies <url>`: parse
     `https://<host>/<slug>/-/issues/<iid>` generically, then
     `glab api [--hostname <host> when not gitlab.com] --paginate
     "projects/<urlenc slug>/issues/<iid>/notes?per_page=100"`, piped to
     `jq -r '.[].body'`. That handles glab printing one array per page.
   - The `source_list_comment_bodies` dispatcher covers github and gitlab
     only. Anything else returns non-zero.
   - Returns rc 0 with the bodies on stdout. Any failure (including a bad
     URL) is non-zero, which means **unknown**, never absent.
   - Posting reuses `source_add_comment`. GitLab sets `GITLAB_REPO_SLUG` with
     the existing `gitlab_extract_repo_from_issue_url`, the same as
     issue-update, so its gitlab.com-only stripping is inherited unchanged.
2. **Consumer**: new `.aitask-scripts/aitask_release_notify.sh [--tag T]
   [--prev-tag P] [--dry-run] [--list] [--no-push]`. Add the dispatcher case
   `release-notify) shift; exec "$SCRIPTS_DIR/aitask_release_notify.sh"
   "$@" ;;` and the help line `release-notify  Comment "Released in vX.Y.Z"
   on resolved issues` under "Integration:" in `ait`.
   - **Inputs and records:**
     - `T` defaults to `git tag --list 'v*' --sort=-version:refname | head -1`.
     - `P` defaults to the next lower `v*` tag, or none (all history).
     - Validate both with V9 and require that both resolve to commits;
       otherwise exit 2.
     - Read every pending `.rec` with `ril_validate_pending_record`. An
       invalid record → `MALFORMED:<path>`; it is skipped from processing
       and still reported.
   - **Classifying records** uses one `git log --format='%H%x09%s' P..T`
     call and one `git log … P` call:
     - map a parent id `P` to the commit tags `(tP)` and `(tP_<n>)`. A child
       id `P_C` maps to `(tP_C)` only. Match with a bash regex, digits spelled
       out;
     - due if any mapped commit is in `P..T`;
     - else, if mapped commits are reachable from `P` →
       `SHIPPED_EARLIER:<task>|<url>|<E>`, where
       `E = git tag --contains <newest mapped sha> --list 'v*'
       --sort=version:refname | head -1`. Print the exact safe retry command
       `ait release-notify --tag <E>`. The record stays pending, with **no
       catch-up** (t2266);
     - else `PENDING:<task>|<url>|no_commits`;
     - a platform other than github or gitlab →
       `UNSUPPORTED:<task>|<url>|<platform>`.
   - **Residue detection (V11)** runs before the gate. It enumerates the
     residue inputs of 1d, read-only, and prints `RESIDUE:<path>|<state>` for
     each. `--dry-run` and `--list` stop at reporting.
   - **Posting gate**, when there are due records or residue and this is not
     `--dry-run` or `--list`:
     1. `ril_data_freshness`;
     2. `release_notify_designation`;
     3. the run lock `ait_ledger_lock_acquire release_notify run …`,
        acquired in the main shell under `_RN_PHASE=run_lock`. The EXIT
        trap is `trap 'rc=$?; _rn_on_exit "$rc"' EXIT`, which turns a death
        during that phase into `INCOMPLETE:run_lock:busy` and status 3, then
        calls `ait_ledger_lock_exit_trap "<status>"`;
     4. **the residue sweep**, now under the run lock: `ril_resume_move` for
        each residue path. `RIL_MOVE_RESUMED:` → `RESUMED:<task>|<url>|<path>`.
        `RIL_MOVE_FAILED:` → `FAILED:<task or ->|<path>|<reason>`, which
        counts toward exit 4. The sweep runs **before** records are
        classified, so a record whose comment is already posted can never be
        classified due and listed again. The pre-gate pass only decides
        whether the gate is needed and feeds `--dry-run` output. After the
        sweep, the pending records are **re-scanned and classified again**,
        and only that result is posted from;
     5. `release_publication_check T`, only when due records remain. The
        sweep posts nothing, so it does not need publication.

     Any failure in 1–3 or 5 prints `INCOMPLETE:freshness:<s>`,
     `INCOMPLETE:designation:<s>`, `INCOMPLETE:run_lock:busy` or
     `INCOMPLETE:not_published:<line>`, with a recovery hint, and exits 3.
     Nothing is posted.
     - Freshness hint: "run ./ait sync (resolve any conflict), then re-run
       `<same command>`".
     - Designation hint: "notifications run only on `<d>`", or, when unset,
       "add `release_notify_host: <this hostname>` to
       aitasks/metadata/project_config.yaml".

     `--dry-run` and `--list` print `FRESHNESS:`, `DESIGNATION:` and
     `PUBLICATION:` as information only.
   - **Per due record:**
     - The marker is `<!-- aitask-release:T t<task> -->`, matched with
       `grep -F` in the listed bodies.
     - List the comments:
       - found → `ALREADY_NOTIFIED:`, outcome `already_present`;
       - unknown → `FAILED:<task>|<url>|comment_list_unknown`, stays
         pending;
       - absent → `source_add_comment`.
     - The comment body is:
       - the marker line;
       - `## Released in T`;
       - "The fix for this issue (aitask t<task>) ships in [T](<release url>).";
       - `### Commits in this release`, then a fenced code block with
         `<short sha> <subject>` per mapped commit in `P..T`. Inside the
         fence there are no @-mention pings.
     - Release URL: GitHub `https://<host>/<slug>/releases/tag/T`; GitLab
       `https://<host>/<slug>/-/releases/T`.
     - A post failure → `FAILED:…|post_failed`.
     - On success, `ril_move_released`:
       - `RIL_MOVED:` → print `POSTED:` or `ALREADY_NOTIFIED:` with the
         released path;
       - `RIL_MOVE_FAILED:` → `FAILED:…|commit_failed`. A retry then finds
         the marker and moves the record.
   - **End of run:**
     - unless `--no-push` or nothing was committed: `task_push` →
       `PUSH:ok|failed|skipped` (V7);
     - `SUMMARY:posted=… already=… resumed=… pending=… shipped_earlier=…
       failed=… malformed=… unsupported=…`.
   - **Exit:**
     - 0 = complete;
     - 1 = usage;
     - 2 = refused input;
     - 3 = incomplete (nothing posted);
     - 4 = partial (≥1 `FAILED`).
   - **`--list`:** pending records, then `released/<tag>/` grouped by tag.
3. **Wrapper**: new framework-only `wait_release_and_notify.sh <tag>
   [--timeout S] [--interval S]` at the repo root.
   - Defaults are 1800s / 20s. Env overrides: `AIT_RELEASE_WAIT_TIMEOUT`,
     `AIT_RELEASE_POLL_INTERVAL`.
   - It `cd`s to its own directory and sources the libs from
     `.aitask-scripts/lib/`.
   - It refuses to start (exit 1) unless the policy sets both
     `release_publication_workflow` and `release_publication_assets`.
   - Early designation: if this machine is not designated, print
     "notifications run only on `<d>`: run `./wait_release_and_notify.sh T`
     there" and exit 5, before any `gh` call.
   - Poll `release_publication_check T` until the deadline:
     - `published` → continue;
     - `pending` → print `WAIT:<reason>`, sleep;
     - `failed:workflow_failed:*` → `WORKFLOW_FAILED:<c>`, exit 2;
     - any other `failed` or `unknown` → `WAIT:<line>`, keep polling (it may
       be transient);
     - the deadline passes → `TIMEOUT:<last line>`, exit 3.
   - Reconciliation, branch mode only: run `./ait sync --batch` and take the
     **first** line of its output (V3).
     - Proceed on `SYNCED`, `PUSHED`, `PULLED`, `NOTHING`, `AUTOMERGED` or
       `MERGED`.
     - Anything else, empty output, or a non-zero rc →
       `RECONCILE_FAILED:<token>`, plus the hint "resolve with ./ait sync,
       then retry", and exit 5.
   - Run the consumer: `./.aitask-scripts/aitask_release_notify.sh --tag T`.
     - Relay its output.
     - For each `SHIPPED_EARLIER:…|<E>` line, add the wrapper's own command
       `./wait_release_and_notify.sh <E>`.
     - Consumer rc 0 → 0, rc 3 → 5, rc 4 → 4, others → 1.
   - Every non-zero exit prints `RETRY: ./wait_release_and_notify.sh T`.
4. **`create_new_release.sh`**: after `git push origin main --tags` and the
   "Done!" lines:

   ```bash
   echo ""
   echo "Waiting for the release workflow to publish v$new_version before notifying resolved issues..."
   notify_rc=0
   ./wait_release_and_notify.sh "v$new_version" || notify_rc=$?
   if [[ $notify_rc -ne 0 ]]; then
     echo -e "\033[1;33mWARNING:\033[0m Release v$new_version was pushed, but issue notifications are incomplete (exit $notify_rc)."
     echo "Retry: ./wait_release_and_notify.sh v$new_version"
     exit "$notify_rc"
   fi
   ```

   There is no prompt.
5. **Docs** (current state only, per
   `aidocs/framework/documentation_conventions.md`):
   - `website/content/docs/commands/issue-integration.md`:
     - the `ait issue-update` section gains `--record-only`, the
       `RELEASE_LEDGER*` outputs and the exit-status table, including exit 3
       (owed by t2261_1);
     - a new section "ait release-notify" covers:
       - the ledger: location, record fields, and the lifecycle pending →
         `released/<tag>/`;
       - options, output lines, exit codes, rolling semantics, the marker,
         and `SHIPPED_EARLIER` with no catch-up;
       - the posting gate: freshness, designation, publication;
       - the policy keys, with a generic example;
       - `release_notify_host` and how to reassign it deliberately:
         1. make sure no run is in progress on the old machine;
         2. set the new hostname with `ait settings`, or by editing the file
            and running `aitask_metadata_commit.sh`;
         3. `./ait sync` on both machines.

         State plainly that there is no automatic failover;
       - the duplicate-prevention scope, worded as in the parent Context;
       - that a project which cuts tags without platform releases never
         posts;
       - `RESIDUE:` / `RESUMED:`: an interrupted move is completed by the
         next posting run without a new comment, and residue that does not
         verify is left for a human;
       - that the policy is read with a real YAML parser and fails closed
         when Python is unavailable.
   - `website/content/docs/commands/_index.md`: a table row for
     `ait release-notify`.
   - `website/content/docs/workflows/issue-tracker.md`: a short step about
     release notifications, linked with `{{< relref >}}`.
   - `website/content/docs/workflows/releases.md`: the release steps gain
     "Notify resolved issues": `create_new_release.sh` waits for publication,
     then comments, and on failure prints a `wait_release_and_notify.sh`
     retry. Update the pipeline diagram line.
   - `website/content/docs/development/_index.md` step 2: one clause.
   - Run `cd website && python3 check_links.py --build`.
6. **Tests**. Every file uses `tests/lib/asserts.sh`, and the file-backed
   counters if any body runs in `( … )`.
   - `tests/test_release_notify.sh` uses a new legacy-mode fixture:
     - a bare origin, and tags `v1.0.0` / `v1.1.0` / `v1.2.0` with `(tN)`
       commits pushed;
     - `.rec` files written through `ril_record` itself, with the
       `ril_record` format;
     - a `gh` stub with a file-backed comment store and per-scenario
       release, run and download responses;
     - a `hostname` shim.

     It reuses `tests/lib/issue_update_fixture.sh`'s `%q` argv-log style but
     not `ifx_make_repo`, which has no origin. Cases:
     - due vs no commits;
     - child commits under a parent;
     - a marker already present;
     - the move into `released/<tag>/`, with the released record validated;
     - `--dry-run`;
     - a partial post failure, then a retry;
     - an unknown comment listing;
     - `SHIPPED_EARLIER` with no catch-up and the exact retry command, then
       the printed command posting once and a second run posting nothing;
     - the designation cases: unset, another host, an invalid value, a
       match, and `--dry-run` informational;
     - missing and draft releases;
     - `tag_mismatch`;
     - an invalid `--tag` → exit 2;
     - the run lock held → `INCOMPLETE:run_lock:busy`, exit 3;
     - a non-draft release with the policy configured: (a) run in progress,
       (b) run failed, (c) `.deb`/`.rpm` missing, (d) a SUMS-listed binary
       missing, (e) an unknown placeholder, (f) a block mapping. Each runs
       both directly and via the `--tag E` recovery form, and each posts
       nothing;
     - the same release, complete → posts once;
     - no policy → the generic checks only;
     - **policy formatting controls (V12)**, each with a configured workflow
       and asset list, asserting the workflow and asset requirements are
       enforced (a stub with no run → `pending:run_not_found`, never
       published-by-generic):
       - quoted keys (`"release_publication_workflow": release.yml`);
       - single-quoted keys;
       - a whole-document flow mapping.

       Also: a duplicate key → `policy_unreadable:duplicate_key`; a
       non-mapping document → `policy_unreadable:document`; `AIT_PYTHON`
       pointing at a script that exits 1, and one that prints no `OK` →
       `policy_unreadable`; an unreadable config file → `read_error`; a
       missing config file → generic. Each posts nothing except the generic
       case;
     - **GitLab manifests (V13)**, with a `glab` stub for `api` releases and
       `release download`: a complete release where every SUMS-listed file
       is a link → posts once; a SUMS file listing a missing link →
       `pending:assets_missing:<name>`, nothing posted; a failing
       `release download` → `unknown:api_error`;
     - **interrupted moves (V11)**, each starting after a real post:
       - the seam `after_publish` (SIGKILL), then a retry;
       - the seam `after_remove` (SIGKILL), then a retry;
       - the same two states built by hand, an uncommitted released copy
         with the pending file present or deleted, then a retry.

       Each retry must print `RESUMED:`, commit exactly
       `<released> <pending>` (`git show --stat HEAD`), leave a clean
       `git status` for both paths, and post **zero** new comments: the
       stub's comment store count stays 1. A later run is `SUMMARY` all
       zero;
     - **residue refusal controls**: released residue whose pending fields
       differ from HEAD's, a tag-directory / `released_tag` mismatch, and an
       unpaired pending deletion. Each gives `FAILED:…|<reason>`, exit 4,
       no file deleted or rewritten (byte-identical), and no comment.
   - `tests/test_release_notify_branch_mode.sh` uses
     `tests/lib/sync_fixture.sh`. Its traced `setup_repo` gives a bare
     remote, a clone with a real `.aitask-data` worktree, a copied
     `.aitask-scripts`, a `bin/hostname` shim (`TEST_HOSTNAME`) and an
     initialized lock branch. It has no tags and no `project_config.yaml`,
     so the test adds both. Cases:
     - failed fetch;
     - behind;
     - `count_failed` via a git shim (the control proving there is no 0
       fallback);
     - the wrapper's `RECONCILE_FAILED` on `CONFLICT` and on `NO_NETWORK`;
     - fresh → posts once;
     - an `after_remove` interruption in the real `.aitask-data` worktree,
       then a retry → `RESUMED:`, with the commit on the data branch and
       zero new comments.
   - `tests/test_wait_release_and_notify.sh` uses a scenario-scripted `gh`.
     Its JSON shapes are copied from the real captures in the t2261_2 task
     description. Cases:
     - delayed publication;
     - workflow failure;
     - timeout (a stuck run; a missing asset);
     - a retry after a failed run that was later re-run successfully;
     - a retry after a partial notification;
     - a run with a different sha ignored;
     - a non-designated machine → exit 5 with zero `run list` calls;
     - sequential retries → exactly one marker comment per issue. The
       comments state the scope: serialised and sequential runs, not
       concurrent multi-machine runs.
   - Use small `--timeout` / `--interval` values. Assert outcomes, never
     exact poll counts.
   - Re-run `tests/test_issue_update_ledger.sh` and
     `tests/test_issue_update_argv.sh` after 1d.

## Post-phase (risk mitigations)

1. [pin_release_asset_contract] Add `tests/test_release_asset_contract.sh`.
   - It extracts the published names:
     - the `files:` entries of both `softprops/action-gh-release` steps in
       `.github/workflows/release.yml`, taking basenames, with
       `${{ github.ref_name }}` → `{tag}` (V6);
     - the `gh release upload` targets in
       `.github/workflows/release-packaging.yml`, with `${VERSION}` →
       `{version}`;
     - one `<cmd>_{version}_SHA256SUMS.txt` per `goengines/cmd/<cmd>`.
   - It instantiates the framework policy's `release_publication_assets` for
     a sample version with `release_publication_expand_assets`.
   - It asserts the two sets are equal, with `goengines/dist/*` covered by
     the `release_publication_checksum_manifests` glob.
   - It asserts `release_publication_workflow == release.yml`, and that
     `release.yml` still has a job that `uses:
     ./.github/workflows/release-packaging.yml`, so the run conclusion covers
     packaging.
   - Mutation control: a fake `files:` line in a temporary copy of the
     workflow must make the comparison fail.

## Verification

- `bash tests/test_release_notify.sh`,
  `bash tests/test_release_notify_branch_mode.sh`,
  `bash tests/test_wait_release_and_notify.sh` and
  `bash tests/test_release_asset_contract.sh` pass, as do
  `tests/test_issue_update_ledger.sh` and `tests/test_issue_update_argv.sh`.
- `python3 -m pytest tests/test_settings_project_config_value_types.py`, or
  the runner with `--test-dir`.
- `shellcheck .aitask-scripts/aitask_release_notify.sh
  .aitask-scripts/lib/release_publication.sh
  .aitask-scripts/lib/release_issue_ledger.sh
  .aitask-scripts/lib/issue_backends.sh wait_release_and_notify.sh
  create_new_release.sh`.
- `cd website && python3 check_links.py --build`.
- Read-only on the real repo:
  `./.aitask-scripts/aitask_release_notify.sh --dry-run --tag v0.40.1`
  prints the range and the `FRESHNESS:`, `DESIGNATION:` and `PUBLICATION:`
  states, and posts nothing.

## Step 9

- Commit the code (`feature: … (t2261_2)`) by naming its paths. The working
  tree holds other sessions' uncommitted files
  (`lib/artifact_manifest.py`, `lib/artifact_registry.py`,
  `lib/attachment_meta.py`, `CLAUDE.md`, `aidocs/…`,
  `tests/test_trails_focus_writer.py`, `website/README.md`,
  `tests/test_validator_regex_trailing_newline.py`); never include them.
- Commit the plan, and the framework `project_config.yaml` values via
  `aitask_metadata_commit.sh`.
- Then archive through task-workflow Step 9. The parent t2261 auto-archives
  once this is the last child.

## Risk

### Code-health risk: medium
- New shipped consumer + lib + three wrapper paths, plus four new
  `project_config.yaml` keys: a wide surface. A mis-saved key fails closed
  (`policy_unreadable`). · severity: medium · → mitigation: none (fail-closed
  design + tests)
- `create_new_release.sh` now blocks for up to the timeout and exits non-zero
  when notification is incomplete, after a successful push. · severity: low
  · → mitigation: none (clear message + retry command)
- Tightening `_ril_on_existing`'s released branch to a whole-record
  validator (1d) changes t2261_1's shipped duplicate classification for
  released hits. · severity: low · → mitigation: none (covered by updating
  the t2261_1 ledger test (v) cases and re-running both t2261_1 test files)
- The resumable move (`ril_resume_move` + residue sweep) adds a second write
  path on the ledger. It is bounded by the same lock, the same commit helper
  and the same git-state verdict, adopts only residue whose identity and
  content verify against HEAD, and never deletes or rewrites anything that
  does not. · severity: medium · → mitigation: none (in plan — SIGKILL-seam
  and hand-built interruption tests, refusal controls)
- Policy parsing now always needs Python when a config file exists. A host
  without the framework interpreter cannot post, even under the generic
  policy (fail-closed by design). · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Drift of the framework's declared assets from `release.yml` /
  `release-packaging.yml` would make every gate time out. · severity: low
  (residual — addressed by inline post-phase pin_release_asset_contract) ·
  → mitigation: inline post-phase pin_release_asset_contract
- The GitLab path (`glab api --paginate` notes, `glab issue note`, GitLab
  releases API, and `glab release download -n/-D` for manifests) is verified
  only against stubs. A misread listing could miss the marker and duplicate a
  comment. A wrong download flag would keep a manifest-configured GitLab
  project blocked (fail-closed, `unknown:api_error`). · severity: medium ·
  → mitigation: live_gitlab_release_notify_check
- Duplicate prevention covers serialised runs on the designated machine and
  sequential retries only (accepted scope; documented). · severity: low ·
  → mitigation: none
- `SHIPPED_EARLIER` records need a manual retry, because there is no
  catch-up (accepted scope). · severity: low · → mitigation: none (t2266)

### Planned mitigations
- timing: post-phase | name: pin_release_asset_contract | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: expected-asset drift making every gate time out | desc: Contract test deriving published asset names from release.yml/release-packaging.yml vs the framework publication policy, with a mutation control (t2261_2)
- timing: after | name: live_gitlab_release_notify_check | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: GitLab notes-listing misread causing duplicate release comments | desc: Live-check ait release-notify's GitLab path (glab api --paginate notes, glab issue note, releases API, re-run idempotency) against the local GitLab CE harness and replace hand-written glab stubs with captured output

## Implementation progress (2026-11-10)

All steps 1a–6 and the post-phase are implemented. Test results: release_notify
225/225, branch_mode 39/39, wait_release 43/43, asset_contract 10/10,
issue_update_ledger 133/133, issue_update_argv 41/41. Mutant controls in an
isolated copy: widening `_ril_known_field` fails (w) ×3 and (r) ×3; removing
the residue sweep fails 17 (p)/(q) assertions.

Deviations, each recorded with its reason:
- **An explicit policy step** runs between freshness and designation:
  `INCOMPLETE:policy_unreadable:<key>`. The designation lives in the same
  file, so an unreadable policy now names the key instead of reading as a
  designation failure.
- **Freshness and designation gate every non-dry run**, including one with
  nothing due locally: "nothing to do" from stale data is not an all-clear.
- **The residue source must be HEAD's pending record.** An untracked pending
  twin is refused (`unverifiable` / `residue_mismatch`), so restore-on-failure
  never has to reconstruct an untracked file.
- **A record whose residue was refused is skipped**
  (`PENDING:…|residue_unresolved`). Without that, the (q) tag-directory case
  moved the genuine record past the stray residue.
- **A pending record not yet committed** (an interrupted writer) gives
  `PENDING:…|uncommitted_record` and is not posted for.
- **`UNSUPPORTED:` was dropped.** It is unreachable: the record validator
  admits only github and gitlab, so anything else is `MALFORMED:`.
  `MALFORMED` counts toward exit 4.
- **The origin is read from the configured `remote.origin.url`**, with
  `detect_platform_from_url`, not from `git remote get-url`, which applies
  `insteadOf` rewrites. The release page lives at the configured address.
- **`_ril_finish` runs `${_RIL_CLEANUP_FN:-_ril_record_cleanup}`**, so the
  move and resume subshells share the finish without the writer's cleanup.
- **The wrapper's dead-network case:** with every fetch failing, `ait sync
  --batch` reports `DEFERRED:fetch_exclusion:data_branch_fetch_failed` (not
  `NO_NETWORK`). It is still refused, and the test pins the real token.
- **The contract test is its own file**, `tests/test_release_asset_contract.sh`.

## Post-Review Changes

### Change Request 1 (2026-11-10, implementation review)
- **Requested by user:** six reviewer findings, all CONFIRMED by the reviewer
  and re-verified here:
  1. the marker lookup `printf | grep -qF` under pipefail: an early match gives
     printf SIGPIPE and the run posts a duplicate;
  2. freshness compared against a tracking ref that a bare `fetch origin <ref>`
     does not update under a restricted `remote.origin.fetch`;
  3. the move / resume subshells inherited the caller's ledger-lock globals, so
     an early `_ril_finish` released the caller's `release_notify run` lock;
  4. tag selection through `| head` / `| awk … exit` under pipefail aborted
     with exit 141 on a large tag list (and the SHIPPED_EARLIER lookup and the
     wrapper's sync-token read had the same shape);
  5. `--list` resolved tags first, so a repo with no tags could not list its
     ledger;
  6. the residue scan costs at least 3 git calls per historical record on every
     run (follow-up).
- **Changes made:**
  1. a bash substring test (`[[ "$bodies" == *"$marker"* ]]`);
  2. an explicit refspec, `fetch origin +refs/heads/<ref>:refs/remotes/origin/<ref>`;
  3. `_AIT_LEDGER_LOCK_DIR` / `_AIT_LEDGER_LOCK_TOKEN` are cleared at the entry
     of `ril_move_released`, `ril_resume_move` and `ril_record`;
  4. `mapfile` over the full `git tag` output, for selection and the
     SHIPPED_EARLIER lookup; the wrapper takes `${sync_out%%$'\n'*}`;
  5. `--list` is handled before `resolve_tags`;
  6. created follow-up **t2276** (batched residue scan).

  An audit of the new production files found no other early-closing pipeline
  reader.

  New regression cases in `tests/test_release_notify.sh`: (s) a long thread with
  an early marker, (t) a restricted refspec, (u) the caller's lock surviving
  early move failures, (v) 8003 tags, (w) `--list` with no tags.
- **Pre-fix controls** (each fix reverted alone, in an isolated copy, full
  suite run): marker → (s) ×3 failed (a 301st comment was posted); fetch →
  (t) ×3; lock → (u) ×1; tags → (v) ×3 (exit 141); list → (w) ×2. Every other
  assertion passed in each run (239–241/242).
- **Results after the fix:** release_notify 242/242, branch_mode 39/39,
  wait_release 43/43, asset_contract 10/10, issue_update_ledger 133/133,
  issue_update_argv 41/41, shellcheck clean.
- **Files affected:** `.aitask-scripts/aitask_release_notify.sh`,
  `.aitask-scripts/lib/release_issue_ledger.sh`, `wait_release_and_notify.sh`,
  `tests/test_release_notify.sh`.

### Change Request 2 (2026-11-10, implementation review)
- **Requested by user:** two reviewer findings, both CONFIRMED and re-verified:
  1. tag enumeration read `git tag` through `mapfile < <(…)`, whose success
     says nothing about git's. A failed listing read as an empty or truncated
     list. The reviewer reproduced `RANGE:(root)..v1.2.0` and a v1.2.0 notice
     posted for t10, which shipped in v1.0.0, breaking the no-catch-up rule.
     The containing-tag lookup had the same hole;
  2. `tests/test_metadata_writer_inventory.py` reported four unclassified
     metadata writers: two inherited from t2261_1 (`aitask_issue_update.sh`,
     `lib/release_issue_ledger.sh`, already unclassified at HEAD) and two added
     here (`aitask_release_notify.sh`, `lib/release_publication.sh`).
- **Changes made:**
  1. new `git_lines <array> <git args…>` captures git with `$( )`, so its rc is
     git's own:
     - tag enumeration failure → `INCOMPLETE:tags:git_failed`, exit 3, before
       any range is formed;
     - a failed containing-tag lookup → `FAILED:<task>|<url>|tag_lookup_failed`
       (no guessed `SHIPPED_EARLIER`), counted in `failed=` and exit 4;
     - the `git log` range reads → `INCOMPLETE:log:git_failed`.
  2. inventory classification, with the t2261_1 and t2261_2 paths labelled
     separately:
     - WIRED: `lib/release_issue_ledger.sh::_ril_commit_record` and
       `::_ril_commit_move`, both via `ait_commit_paths_staging_untracked`;
     - KNOWN_UNCOMMITTED: `::_ril_move_cleanup`, which restores a tracked
       record's committed bytes, so there is nothing to commit;
     - PINNED_FILES: `aitask_issue_update.sh`, `aitask_release_notify.sh`
       (temp capture files only; delegate to the ledger lib) and
       `lib/release_publication.sh` (reads project_config.yaml; writes only
       its mktemp directory).

     The discovery guard is unchanged.
  - New regression case (x) in `tests/test_release_notify.sh`: `tag --list`
    failing with empty and with partial output, under an explicit and a
    default tag, and `tag --contains` failing.
- **Pre-fix control** (the old `mapfile < <(…)` reads restored, isolated
  copy): 16 (x) assertions failed, including a post and a moved t10 record
  under `list_empty`, the reviewer's scenario. All other assertions
  (243/259) passed.
- **Results after the fix:** release_notify 259/259,
  test_metadata_writer_inventory 6/6.
- **Files affected:** `.aitask-scripts/aitask_release_notify.sh`,
  `tests/test_release_notify.sh`, `tests/test_metadata_writer_inventory.py`.
- **Found by the full Python suite while verifying CR2:**
  `tests/test_archive_rearm_tripwire.py` flagged the temp-dir EXIT trap in
  `release_publication_check`. That function is a `( … )` body that resolves
  no task file, so the trap got the documented
  `# archive-sweep: subshell-local` marker. After that:
  `PYTHON SUITE: PASSED (runner=pytest, exit=0)`, all six bash files pass
  (259 + 39 + 43 + 10 + 133 + 41), and shellcheck is clean.

## Final Implementation Notes

- **Actual work done:**
  - **`.aitask-scripts/aitask_release_notify.sh` (new) + `ait release-notify`**
    (dispatcher case and help line).
    - Classifies the pending records against `<prev>..<tag>`: due, already
      notified (marker), `SHIPPED_EARLIER` with the exact retry command,
      pending, malformed, uncommitted, `residue_unresolved`.
    - Gate: freshness → policy → designation → run lock → residue sweep →
      re-classify → publication.
    - Posts with a hidden marker, moves each record in one commit, pushes
      once, prints `SUMMARY:`. Exit 0/1/2/3/4.
  - **`.aitask-scripts/lib/release_publication.sh` (new) +
    `lib/release_publication_policy.py` (new).**
    - The per-project policy is read with a real YAML parser (a
      duplicate-refusing SafeLoader), fail-closed.
    - `release_publication_expand_assets` is the one template function.
    - `release_publication_origin` reads the configured `remote.origin.url`.
    - `release_publication_check` is one non-waiting check:
      - remote tag;
      - GitHub release / GitLab release;
      - workflow run for tag + commit, newest id wins;
      - required assets;
      - checksum manifests, downloaded via `gh` or `glab release download`.
  - **`lib/release_issue_ledger.sh` (extended).**
    - Released fields and `ril_validate_released_record`. The pending
      whitelist stays pending-only.
    - `ril_data_freshness`, using an explicit refspec fetch.
    - `release_notify_designation`.
    - `ril_move_released`: subshell, lock, one path-scoped commit,
      git-state verdict.
    - `ril_resume_move` / `_ril_resume_locked`, which complete an
      interrupted move only when the residue verifies against HEAD.
    - `ril_list_residue`, plus a SIGKILL test seam behind a marker file.
    - `_ril_finish` takes `_RIL_CLEANUP_FN`.
  - **`lib/issue_backends.sh`:** tri-state `github_list_comment_bodies`,
    `gitlab_list_comment_bodies` and `source_list_comment_bodies`.
  - **`wait_release_and_notify.sh` (new, framework-only)** and the
    `create_new_release.sh` hook (no prompt; exits non-zero with the retry
    command when notification is incomplete).
  - **Registration:**
    - settings schema entries for the four keys;
    - the seed's commented example;
    - the framework policy in `aitasks/metadata/project_config.yaml`
      (`release_notify_host: omg16`).
  - **Docs:**
    - `commands/issue-integration.md`: the `issue-update` ledger outputs and
      exit 3, and a new "ait release-notify" section (ledger, gate, policy,
      designation and reassignment, duplicate scope, output and exit);
    - `commands/_index.md`, `workflows/issue-tracker.md`,
      `workflows/releases.md`, `development/_index.md`.
  - **Tests:**
    - `test_release_notify.sh`: 259 assertions, cases (a)–(x);
    - `test_release_notify_branch_mode.sh`: 39;
    - `test_wait_release_and_notify.sh`: 43;
    - `test_release_asset_contract.sh`: 10, the post-phase
      pin_release_asset_contract;
    - the shared `tests/lib/release_notify_fixture.sh`;
    - `test_issue_update_ledger.sh` (v) updated and (w) added: 133;
    - `test_metadata_writer_inventory.py` classifications.
- **Deviations from plan:** listed under "Implementation progress" above
  (policy step, always-gated runs, HEAD-sourced residue, residue_unresolved,
  uncommitted_record, no `UNSUPPORTED:`, configured origin URL, the real
  dead-network token, a separate contract file). The two change requests
  added: substring marker search, explicit-refspec freshness, no inherited
  lock in move subshells, full tag reads with git's own status, `--list`
  before tag resolution.
- **Issues encountered:**
  - Test-only bugs, all fixed in the tests:
    - `task_utils.sh` sources its libs via the caller's `SCRIPT_DIR`, so
      fixtures set it;
    - `git show --name-only` folds the move into an `R` rename, so tests use
      `--no-renames`;
    - unquoted `{tag}` inside a YAML flow list is a YAML error;
    - a bare repo whose HEAD names a missing `master` gives clones no `main`;
    - two `insteadOf` entries for one URL keep the older one.
  - **`main` advanced mid-session:** t2211_5, t2269, t2258_1, with no
    overlap with these files.
  - **Other sessions' uncommitted edits** were excluded from the commit:
    - t2271: `lib/task_utils.sh` (`ait_commit_paths_staging_untracked`,
      which the move uses) and `tests/test_frozenagent_app.py`;
    - another session: `.claude/skills/aitask-docs-gap`,
      `.claude/skills/aitask-gate-docs-updated`, `website/content/docs/skills/*`.

    The tests passed with them present.
- **Key decisions:**
  - Fail closed everywhere: anything unknown posts nothing.
  - A move is judged landed only from git state.
  - Residue is adopted only when HEAD's pending record matches it byte for
    byte; anything else is left for a human and its record is skipped.
  - Shell scans never pipe into early-closing readers under pipefail
    (`grep -q`, `head`, `awk … exit`), and never read git through
    `mapfile < <(…)`.
- **Evidence (durable):**
  - **Pre-fix controls:** isolated copies, each with one change reverted and
    the full suite run:
    - widened whitelist → ledger (w) ×3 and notify (r) ×3 failed, and the
      consumer posted for the corrupt record;
    - no residue sweep → 17 (p)/(q) failed;
    - pipe marker search → (s) ×3, a 301st comment;
    - bare fetch → (t) ×3;
    - inherited lock → (u) ×1;
    - `| head` tags → (v) ×3, exit 141;
    - `--list` after tags → (w) ×2;
    - `mapfile < <(git tag)` → (x) ×16, t10 posted and moved.
  - **Final:**
    - bash 259 + 39 + 43 + 10 + 133 + 41, all passing;
    - `PYTHON SUITE: PASSED (runner=pytest, exit=0)`;
    - `check_links.py --build` SWEEP: PASSED;
    - shellcheck clean;
    - `--dry-run --tag v0.40.1` on the real repo: `FRESHNESS:fresh`,
      `DESIGNATION:designated:omg16`, `PUBLICATION:published|40858419630`,
      t2235 pending (its commits are in no tag yet).
- **Upstream defects identified:**
  - `.claude/skills/task-workflow/premise-staleness.md:213` —
    `tests/test_no_unscoped_task_commit.sh` reports an unscoped task-data
    commit instruction (`AIT_UNPARSEABLE_SPAN`). Pre-existing, already
    recorded by t2261_1.
- **Notes for sibling tasks:** the last child of t2261. For the follow-ups:
  - t2266 (catch-up) must route every post through the same gate;
  - t2276 (batched residue scan) must keep `ril_list_residue`'s
    unknown-on-failure contract;
  - the spawned `live_gitlab_release_notify_check` should replace the
    hand-written glab stubs in `tests/lib/release_notify_fixture.sh` with
    captured output, including `glab release download -n/-D`.
