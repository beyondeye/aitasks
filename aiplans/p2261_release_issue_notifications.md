---
Task: t2261_release_issue_notifications.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2261 — Release-time issue notifications (parent plan: split into 2 children)

## Context

When an archived task's linked issue is updated, `aitask_issue_update.sh` posts
"Resolved via aitask tN" (example: issue #16 / t2235). Nothing happens at
release time. A user who reported the issue never learns which release ships
the fix. This task adds two things:

1. A rolling ledger of issues fixed since the last release. The issue-update
   script writes it.
2. A release step that comments "Released in vX.Y.Z" on each ledger issue
   whose fix is in the new tag.

Decisions taken with the user during planning:

- **Storage: one file per record.** A shared single file gets an `ait sync`
  rebase conflict whenever two machines append between syncs, and
  `lib/stale_lock.sh` only serialises sessions on one machine. With one file
  per record, there is no cross-machine conflict by construction.
- **Integration: automatic, gated on publication, no confirmation prompt.**
  After `git push origin main --tags`, the local release command waits for the
  `release.yml` run for this exact tag and commit. It then checks that the
  GitHub release and its expected assets exist, and only then posts. If the
  workflow fails or the wait times out, nothing is posted, the records stay
  pending, and the exact retry command is printed. A retry checks publication
  again and never double-posts. Each record moves on its own, so partial
  progress survives. This stays in the local release command, which has the
  task data; CI does not.
- **Every posting entry point enforces the same gate.** The public
  `ait release-notify` included, it requires attested data freshness and a
  verified published release through one shared check. Unknown freshness or
  publication posts nothing and returns an incomplete result. Added after
  plan review.
- **The publication policy is per project** (`project_config.yaml` keys:
  workflow, required assets, checksum manifests). The check reads it on every
  path, direct and recovery included. The framework repo configures its own
  workflow and assets; other projects get only the generic release checks.
  Added after the second plan review.
- **Accepted scope boundaries** (user decisions, third review):
  - **No automatic catch-up.** Records whose commits shipped in an older
    release stay pending, and the exact safe retry command for that release
    is printed. Automatic catch-up is a separate follow-up task, created at
    decomposition.
  - **One designated notification machine**, named by the
    `release_notify_host` key in `project_config.yaml`. It is checked before
    posting, together with the existing local run lock. Reassignment is a
    deliberate documented edit. There is no distributed locking and no
    automatic failover.
- **Duplicate-prevention scope.** The local run lock, the marker check before
  each post, and the per-record move prevent duplicate comments for runs
  serialised on the designated machine and for sequential retries, including
  a retry after a crash between a post and its record move. This is **not**
  an unconditional exactly-once guarantee. The plan and docs claim no more,
  and say what is not covered:
  - concurrent runs on two machines when the designation is bypassed or
    reassigned mid-run;
  - an immediate retry while the platform's comment listing has not yet
    caught up with a just-posted comment;
  - a marker comment edited or deleted by hand.
- **Split into two children.** The parent plan fixes the record format (the
  contract between them).

Premise corrections found during exploration:

- `aitask_changelog.sh --gather` does **not** map child ids to the parent. It
  lists each `(tN)` / `(tN_M)` id separately. The parent/child mapping is
  defined here, in the consumer.
- The GitHub backend calls `gh issue comment <number>` without a repo. An
  `issue:` URL in another repository (or on GitHub Enterprise) is therefore
  commented on the *current* repo's issue with that number. `gh issue
  comment|close|view` all accept the issue URL, so the shared backend targets
  the URL. Same-repo behaviour is unchanged.
- t2251 (Ready, not started) retires the Bitbucket backend in this same file.
  t2261_1 moves that backend into the new lib unchanged and then sends t2251 a
  note (see below). No Bitbucket support in the consumer: the API was removed
  on 2026-08-20 (t2247).

## Ledger contract (shared by both children)

Location (task-data branch; legacy mode: main branch):

```
aitasks/metadata/release_issues/pending/<task_id>--<key>.rec
aitasks/metadata/release_issues/released/<tag>/<task_id>--<key>.rec
```

- `<key>` = first 16 hex characters of `printf '%s' "$issue_url" | git
  hash-object --stdin`. That is a byte-exact hash with no extra dependency.
  The hash is only a filename. **Identity** is the exact `task_id` +
  `issue_url` bytes stored inside the file. A filename hit whose stored URL
  differs is refused as `hash_collision` (fail closed).
- Format: `key=value` lines, one field per line, parsed by an exact key match.
  Every value is validated on write **and** on read against a strict charset.
  The URL must match `^https?://[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+$`, which
  excludes quotes, backslashes, whitespace and control characters. A read that
  fails validation is reported as `MALFORMED`, never skipped silently.

```
schema=1
task_id=2235
issue_url=https://github.com/beyondeye/aitasks/issues/16
platform=github            # github|gitlab
action=closed              # closed|commented|closed_silent
recorded_at=2026-11-09T13:43:43Z
```

The released copy adds `released_tag=`, `notified_at=`, `outcome=`
(`posted|already_present`) and `commits=<full-sha>,<full-sha>`.

- Dedupe: a pending **or** released record with the same (task_id, issue_url)
  means no new record (`RELEASE_LEDGER:duplicate:<path>`).
- Commit-to-task mapping (consumer): a parent id `P` matches the commit tags
  `(tP)` and `(tP_<n>)`. A child id `P_C` matches only `(tP_C)`. Folded and
  related routes are recorded under the primary task id. The writer already
  receives that id through `--issue-url ... <task_id>`.
- Shared helpers live in a new `.aitask-scripts/lib/release_issue_ledger.sh`:
  path and key derivation, write, read and validate, find, and move. The
  writer and the consumer both source it.
- Posting preconditions, enforced by **every posting entry point** (details
  in t2261_2 steps 1a, 1b, 2):
  1. **Freshness is attested.** Fetch the data ref and count how far the
     local ref is behind its remote. Every git rc is checked, and anything
     short of a proven count of 0 is non-fresh.
  2. **This is the designated machine.** `hostname` must equal
     `release_notify_host`, byte for byte. The value is read after the
     freshness check, so the designation itself is fresh.
  3. **The release is published.** The check is
     `release_publication_check`, one shared implementation used by both the
     consumer and the framework wrapper.
  A failure posts nothing, keeps every record pending, and returns
  `INCOMPLETE:` with a recovery command. `--dry-run` and `--list` only report
  these states and never require them.
- Locking: `ait_ledger_lock_acquire release_issues ledger …` from
  `lib/ledger_block.sh` (built on `lib/stale_lock.sh`) is held around each
  find + write/move + commit. Commits go through
  `ait_commit_paths_staging_untracked` (`lib/task_utils.sh`) with explicit
  paths only. A commit failure **rolls back** the file change, so no ownerless
  dirty file is left behind for `ait sync`'s sweep.

## Child t2261_1 — Shared issue backends + ledger writer

Files: new `.aitask-scripts/lib/issue_backends.sh`, new
`.aitask-scripts/lib/release_issue_ledger.sh`,
`.aitask-scripts/aitask_issue_update.sh`,
`.claude/skills/task-workflow/issue-update.md`, new
`tests/test_issue_update_ledger.sh`.

### Pre-phase (risk mitigations)

1. [characterize_issue_update_argv] Before touching `aitask_issue_update.sh`,
   add `tests/test_issue_update_argv.sh`. It uses a scratch legacy-mode project
   with a task file carrying `issue:` (one GitHub URL and one gitlab.com URL),
   PATH stubs `gh`, `glab` and `jq` that append their full argv to a log, and
   `gh auth status` / `glab auth status` stubs that exit 0. For each action —
   close with notes, comment only, close silently, and
   `--issue-url <u> --close <primary>` — it pins the exact logged argv on the
   **unmodified** script, and the file must PASS on the unmodified script.
   After the extraction (step 1), the GitLab assertions must still pass
   unchanged. The GitHub assertions change in exactly one way: the issue
   argument goes from `<number>` to the issue URL. Keep the pre-change
   expectation in the test as a commented control, citing the commit it was
   measured on.

### Implementation

1. **Extract backends.** Move the `github_*`, `gitlab_*` and `bitbucket_*`
   functions and the `source_*` dispatchers from `aitask_issue_update.sh` into
   `lib/issue_backends.sh`, with a double-source guard and globals `SOURCE`
   and `GITLAB_REPO_SLUG`. Keep bodies verbatim, except for one change:
   dispatchers take an *issue ref*. For GitHub the ref is the issue URL; for
   GitLab it is still the number plus `-R slug`. Add a
   `source_issue_ref <url>` helper. In `run_update`, keep `issue_number` for
   messages and pass `issue_ref` to the backend calls. Mark the Bitbucket
   block with a pointer to t2251.
2. **Ledger lib.** Add `lib/release_issue_ledger.sh` implementing the contract
   above: `ril_root`, `ril_key`, `ril_validate_*`, `ril_find <task> <url>`
   (→ `pending:<path>` / `released:<path>` / none),
   `ril_record <task> <url> <platform> <action>`, `ril_read <path> <field>`.
   The move helper is added in t2261_2.
3. **Writer hook.** After the platform call in `run_update` Step 8 succeeds,
   map the flags to an action: `--close` → `closed`,
   `--close --no-comment` → `closed_silent`, otherwise `commented`. Then run
   the record step **in a subshell**, so a `die` inside a shared helper (for
   example `assert_data_worktree_clean`) cannot turn a successful issue update
   into a plain exit 1. Output:
   - `RELEASE_LEDGER:recorded:<path>` or `RELEASE_LEDGER:duplicate:<path>` →
     exit 0;
   - `RELEASE_LEDGER_FAILED:<reason>` plus a stderr hint ("the issue WAS
     updated; do not re-run; record it with: `<exact --record-only
     command>`") → **exit 3**.
   `--dry-run` never records. A failed platform call exits under `set -e`
   before the hook, so it never records.
4. **`--record-only` retry mode.** Records the ledger entry from the same
   flags (`--close`, `--no-comment`, `--issue-url`) without any platform or
   CLI call. Document it in `--help` as the recovery for exit 3.
5. **Procedure note.** Add one short paragraph to `issue-update.md`: an
   output containing `RELEASE_LEDGER_FAILED:` means the issue update itself
   succeeded, so run the printed `--record-only` command, never the original
   one. Run `./.aitask-scripts/aitask_skill_verify.sh` and regenerate any
   goldens that cover this procedure in the same commit. Suggest port tasks
   for the Codex and OpenCode trees, per CLAUDE.md.
6. **Tests** (`tests/test_issue_update_ledger.sh`): a scratch legacy-mode git
   project plus PATH stubs for `gh` and `glab` that log their argv.
   - Records exactly one file per action (close-with-notes, comment-only,
     close-silently).
   - Records nothing on `--dry-run` or on a failed stub call.
   - Dedupe: a second run of the same pair gives `duplicate` and still one
     file.
   - Concurrency: N parallel writers with distinct pairs give N committed
     records. N parallel writers with the same pair give exactly one.
   - The `--issue-url` route records the primary task id.
   - An injected commit failure gives `RELEASE_LEDGER_FAILED`, exit 3, the
     file rolled back, and the issue still updated. `--record-only` then
     records it with zero stub calls.
   - The GitHub stub receives the URL as the issue argument.
   - An invalid-charset URL is refused.
   Uses file-backed counters if any test runs inside a `( … )` subshell
   (CLAUDE.md, t1207).
7. **Note to t2251** after the commit, via `./ait note 2251 --from 2261_1`:
   the Bitbucket issue backend moved to `lib/issue_backends.sh`. Its inventory
   line for `aitask_issue_update.sh` is stale.

## Child t2261_2 — Consumer, publication gate, release integration, docs

Files: new `.aitask-scripts/aitask_release_notify.sh`, `ait` (dispatcher case
plus help line `release-notify`), `lib/release_issue_ledger.sh` (move and
freshness helpers), new shipped `lib/release_publication.sh`,
`lib/issue_backends.sh` (comment listing), new framework-only
`wait_release_and_notify.sh` (repo root, not shipped), `create_new_release.sh`,
website pages, new tests `tests/test_release_notify.sh`,
`tests/test_release_notify_branch_mode.sh` and
`tests/test_wait_release_and_notify.sh`.

1a. **Attested data freshness** (`ril_data_freshness` in the ledger lib).
   - `desync_state.py` is deliberately not used. Its `count_ahead_behind`
     returns `0,0` when `rev-list` fails, which would read as a silent
     all-clear.
   - The mode comes from `ait_data_mode`. In branch mode the ref is
     `aitask-data` through `task_git`. In legacy mode it is the current branch
     in the repo root.
   - The steps, with every rc checked:
     - no `origin` → `unknown:no_remote`;
     - `fetch --quiet origin <ref>` fails → `unknown:fetch_error`;
     - a local or remote ref is missing → `unknown:missing_ref`;
     - `rev-list --count <ref>..origin/<ref>` fails or prints a non-integer →
       `unknown:count_failed`;
     - a count above 0 → `behind:<n>`;
     - a count of 0 → `fresh`.
   - Anything but `fresh` blocks posting.
1b. **Shared publication check and per-project policy** (new shipped
   `lib/release_publication.sh`).
   - The project's publication policy lives in **`project_config.yaml`**, so
     every posting entry point applies it with no caller flags. That covers
     direct `ait release-notify`, the `SHIPPED_EARLIER` recovery command, and
     the wrapper. No shipped code names framework assets.
   - Three new optional top-level keys, all absent by default:
     - `release_publication_workflow`: a GitHub workflow file. Its run for
       tag + commit must have concluded `success`.
     - `release_publication_assets`: a string or a list of asset-name
       templates. Only the `{tag}` and `{version}` placeholders are allowed
       (`{version}` = tag without the leading `v`). After substitution, each
       name must match `^[A-Za-z0-9._+-]+$`.
     - `release_publication_checksum_manifests`: a string or a list of globs.
       Every release asset that matches is downloaded, and every filename it
       lists (sha256sum format, `*` binary marker allowed) must also be an
       uploaded, non-empty asset. A glob that matches nothing →
       `pending:manifest_missing:<glob>`.
   - When none of the three keys is present, only the generic checks apply:
     the tag matches, and the release exists, is not a draft, and is not
     upcoming.
   - Reading the policy fails closed. A key is detected by a line-start grep.
     If one is present, it is parsed with the framework Python. Any of the
     following → `unknown:policy_unreadable:<key>`, and nothing is posted: a
     wrong type, a block mapping, an unknown placeholder, an invalid name, or
     Python unavailable while a key is present.
   - `release_publication_workflow` set on a GitLab project →
     `unknown:workflow_unsupported`, fail closed. It is never ignored.
   - Registration:
     - Settings TUI key entries in `.aitask-scripts/settings/settings_app.py`
       (types `string` / `string_or_list`);
     - a commented, generic example in `seed/project_config.yaml`, using
       placeholder names (`myapp-{tag}.tar.gz`), not framework ones;
     - the framework repo's own values in
       `aitasks/metadata/project_config.yaml`, committed with
       `aitask_metadata_commit.sh`:
       - `release_publication_workflow: release.yml`;
       - assets `aitasks-{tag}.tar.gz`, `ait`, `aitasks_{version}_all.deb`,
         `aitasks-{version}-1.noarch.rpm`,
         `ait-testmap_{version}_SHA256SUMS.txt`;
       - manifests `*_SHA256SUMS.txt`.
     Before adding the keys, check `aidocs/framework/aitasks_extension_points.md`
     and any settings registry ↔ seed parity test.
   - `release_publication_check <tag>` takes no policy flags. It makes one
     non-waiting check and prints one line:
   - `PUBLICATION:published|<run-id or ->` (rc 0);
   - `PUBLICATION:pending:<reason>` (rc 10). Reasons: `no_release`, `draft`,
     `upcoming`, `run_not_found`, `run_in_progress`, `assets_missing:<csv>`,
     `asset_not_uploaded:<name>`;
   - `PUBLICATION:failed:<reason>` (rc 11). Reasons:
     `workflow_failed:<conclusion>`, `tag_mismatch`, `remote_tag_missing`;
   - `PUBLICATION:unknown:<reason>` (rc 12). Reasons: `api_error`,
     `unparseable`, `cli_missing`, `policy_unreadable:<key>`,
     `workflow_unsupported`. Unknown is never treated as published.

   The checks:
   - **Always:** `git ls-remote --tags origin T`, peeled when annotated, must
     equal `git rev-parse T^{commit}`.
   - **GitHub:** `gh release view T -R <slug> --json tagName,isDraft,assets`.
     A 404 means `pending:no_release`. The release must have `tagName==T` and
     `!isDraft`.
   - **GitLab:** `glab api projects/<enc>/releases/T`. A 404 means
     `pending:no_release`, and `upcoming_release==true` means
     `pending:upcoming`.
   - **Policy `release_publication_workflow` (GitHub only):** `gh run list
     -R <slug> --workflow F --event push --branch T --json
     databaseId,headSha,headBranch,status,conclusion,createdAt`, keeping runs
     with `headBranch==T && headSha==<tag commit>`, newest first. This shape
     was confirmed on real output: tag pushes report `headBranch` as the tag.
     - No run → `pending:run_not_found`.
     - Not completed → `pending:run_in_progress`.
     - Completed but not `success` → `failed:workflow_failed:<conclusion>`.
     - This is what catches the window in this repo where `release.yml`'s
       `release` job has already created the non-draft release, but the
       `packaging` job is still running, or failed.
   - **Policy assets and manifests:** every required name must be present.
     On GitHub it must also have `state==uploaded` and `size>0`; on GitLab it
     must appear in `assets.links[].name`. Missing names →
     `pending:assets_missing:<csv>`.

1c. **Designated notification machine** (`release_notify_designation` in the
   ledger lib).
   - Reads the optional top-level `release_notify_host` key from
     `project_config.yaml`: a scalar, validated against
     `^[A-Za-z0-9._-]+$`. It is compared byte-exact with `hostname`, the same
     source `aitask_lock.sh::get_hostname` uses.
   - The outcomes:
     - `designated:<host>`;
     - `not_designated:<designated>|<this>`;
     - `unset`;
     - `unknown:<reason>`, for an invalid value or a failing `hostname`.
   - Posting requires `designated`. `unset` refuses as well: the hint gives
     the exact key line that designates this machine. Everything else fails
     closed.
   - Registered like the publication keys (Settings TUI entry, seed comment).
   - The framework repo's own value is set to this machine's hostname when
     t2261_2 lands, through `aitask_metadata_commit.sh`.
   - Mutual exclusion on the designated machine is the existing
     `ait_ledger_lock_acquire release_notify run` local lock. Nothing
     distributed is added, and there is no failover.

1. **Comment listing (tri-state).** Add `github_list_comment_bodies <url>`:
   `gh api --paginate [--hostname H] repos/O/R/issues/N/comments --jq
   '.[].body'`. Add `gitlab_list_comment_bodies`: `glab api --paginate
   "projects/<urlenc slug>/issues/<iid>/notes?per_page=100"` piped to
   `jq -r '.[].body'`, which handles glab's one-array-per-page output. Return
   0 with the bodies, or non-zero meaning **unknown**. Unknown never means
   absent, so the consumer does not post.
2. **Consumer** `aitask_release_notify.sh [--tag T] [--prev-tag P] [--dry-run]
   [--list] [--no-push]`, plus a dispatcher case `ait release-notify`.
   - `T` defaults to the latest `v*` tag. `P` defaults to the `v*` tag before
     `T` in version order, or all history when there is none.
   - There are no publication flags. The policy always comes from
     `project_config.yaml`, so a direct run, a recovery run and the wrapper
     cannot differ.
   - Takes a run lock (`release_notify run`) for the whole run, so two
     consumers cannot race the marker check.
   - **Posting gate, run before the first post on every posting invocation.**
     This covers direct use, the `SHIPPED_EARLIER` recovery, and calls from
     the wrapper.
     - First `ril_data_freshness`. Anything else than `fresh` →
       `INCOMPLETE:freshness:<state>` plus the hint "run ./ait sync (resolve
       any conflict), then re-run: `<same command>`", exit 3.
     - Then `release_notify_designation`. Anything else than `designated` →
       `INCOMPLETE:designation:<state>`, exit 3. The hint names the
       designated machine, or the key line to set when unset.
     - Then the local run lock.
     - Then `release_publication_check`. Anything else than `published` →
       `INCOMPLETE:not_published:<line>`, exit 3.
     - Both failures post nothing and keep every record pending.
     - `--dry-run` and `--list` print `FRESHNESS:`, `DESIGNATION:` and
       `PUBLICATION:` as information only.
   - Per pending record:
     - The record is **due** if one of its mapped commits is in `P..T`.
     - If its commits are all reachable from `P`, it gets
       `SHIPPED_EARLIER:…|<E>` (E = the earliest `v*` tag containing its
       newest mapped commit) and **stays pending**. **There is no automatic
       catch-up.** The consumer prints the exact safe retry command,
       `ait release-notify --tag <E>`. That command goes through the full
       posting gate (freshness, designation, publication of E).
     - With no commits, it gets `PENDING:…` (the ledger is rolling).
     - Platforms other than github and gitlab get `UNSUPPORTED`.
   - For a due record: the marker is `<!-- aitask-release:T tN -->`. The
     consumer lists comments:
     - **found** → outcome `already_present` (no post);
     - **absent** → post one comment: marker, "Released in T", the release
       link, and that task's commits in `P..T` in a code fence (no @-mention
       pings);
     - **unknown** → `FAILED` and stays pending.
   - After each success, under the ledger lock, move the record to
     `released/T/` with the added fields and commit just that record. One
     failure leaves the others done, and a retry handles only what is still
     pending.
   - The release link comes from origin. GitHub:
     `https://github.com/<slug>/releases/tag/T`. GitLab:
     `https://<host>/<slug>/-/releases/T`.
   - Stdout lines: `RANGE:`, `FRESHNESS:`, `DESIGNATION:`, `PUBLICATION:`,
     `DUE:`, `POSTED:`,
     `ALREADY_NOTIFIED:`, `PENDING:`, `SHIPPED_EARLIER:`, `UNSUPPORTED:`,
     `FAILED:`, `MALFORMED:`, `INCOMPLETE:`, `PUSH:ok|failed|skipped`,
     `SUMMARY:`.
   - The `SHIPPED_EARLIER` hint names `ait release-notify --tag <E>`. That
     path passes through the same gate, so E's publication is checked too.
   - The data branch is pushed once at the end (`task_push`, best-effort,
     reported). Records moved locally but not yet pushed are still safe: on
     another clone the marker check turns them into `already_present`.
   - `--dry-run` posts nothing, moves nothing and commits nothing. `--list`
     prints pending records and the per-tag history.
   - Exit codes:
     - 0 = complete;
     - 1 = usage;
     - 2 = refused input (bad or missing tag);
     - 3 = incomplete: a precondition was not established and nothing was
       posted;
     - 4 = partial: at least one `FAILED` after posting started.
3. **Publication gate** `wait_release_and_notify.sh <tag> [--timeout S]
   [--interval S]`. Defaults: 1800s and 20s, overridable through
   `AIT_RELEASE_WAIT_TIMEOUT` / `AIT_RELEASE_POLL_INTERVAL`. Real runs take
   about 3.5 minutes.
   - The wrapper owns only the **waiting**. Each poll calls the shared
     `release_publication_check T`, which reads the repo's policy.
   - The wrapper refuses to start (exit 1) unless the framework repo's
     `project_config.yaml` sets both `release_publication_workflow` and
     `release_publication_assets`. A framework release is never
     generic-gated by accident.
   - **Early designation check**, before any polling. If
     `release_notify_designation` is not `designated`, the wrapper prints
     "notifications run only on `<designated>`: run
     `./wait_release_and_notify.sh T` there" and exits 5. It makes zero
     `gh run list` calls and posts nothing. The consumer re-checks the
     designation after sync and stays the authority.
   - How each check result is handled:
     - `pending` → keep polling;
     - `failed:workflow_failed:*` → `WORKFLOW_FAILED:`, exit 2;
     - other `failed` or `unknown` results → keep polling until the deadline,
       because unknown can be transient;
     - the deadline expiring → `TIMEOUT:<last check line>`, exit 3.
     In every one of these cases nothing is posted.
   - **Reconciliation is required, not best-effort.** In branch mode, run
     `./ait sync --batch`.
     - Proceed only on `SYNCED`, `PUSHED`, `PULLED`, `NOTHING`, `AUTOMERGED`
       or `MERGED`.
     - Anything else (`CONFLICT:*`, `NO_NETWORK`, `NO_REMOTE`, `DEFERRED:*`,
       `ERROR:*`, empty output, non-zero rc) → `RECONCILE_FAILED:<token>`,
       exit 5, nothing posted. The recovery hint is "resolve with ./ait sync,
       then retry".
     - In legacy mode the data lives on `main`, which was just pushed, so the
       sync step is skipped.
     - The consumer's attested freshness check runs in both modes and is the
       authority.
   - Then run the consumer for T. It re-verifies publication against the
     same policy with the same code.
     - Consumer exit 3 → exit 5.
     - Consumer exit 4 → exit 4.
     - The consumer's `SHIPPED_EARLIER` lines are relayed with the wrapper's
       own safe retry command `./wait_release_and_notify.sh <E>`. Nothing is
       posted for them in this run.
   - Every non-zero exit prints `RETRY: ./wait_release_and_notify.sh T`.
     Re-running checks publication and freshness again; markers and
     per-record moves make it safe.
4. **`create_new_release.sh`.** After the push and the "Done!" line, run
   `./wait_release_and_notify.sh "v$new_version"` with no prompt and capture
   its rc under `set -e` (`rc=0; … || rc=$?`). On a non-zero rc, say the
   release push succeeded but notifications are incomplete, and repeat the
   retry command.
5. **Docs.**
   - `website/content/docs/commands/issue-integration.md`: the ledger
     (location, record lifecycle, `RELEASE_LEDGER*` outputs, `--record-only`)
     and `ait release-notify` (options, outputs, rolling semantics, the
     marker).
   - The same page also documents the publication-policy keys, and
     `release_notify_host` with **how to reassign it deliberately**:
     1. make sure no `release-notify` or wrapper run is in progress on the
        old machine;
     2. set the new hostname with `ait settings`, or by editing the file and
        running `aitask_metadata_commit.sh`;
     3. `./ait sync` on both machines.
     It also states plainly that there is no automatic failover, and gives
     the duplicate-prevention scope from the Context section.
   - `website/content/docs/workflows/issue-tracker.md`: a short release step.
   - Describe the current state only. Run `python3 check_links.py --build`
     in `website/`.
6. **Tests.**
   - `test_release_notify.sh` uses a fixture repo with tags and `(tN)`
     commits, legacy-mode ledger records and a stub `gh`. Cases:
     - due vs no commits (stays pending);
     - child commits under a parent entry;
     - a marker that is already there gives `already_present` and no post;
     - the move into `released/<tag>/`;
     - `--dry-run` writes nothing;
     - one post failure: the others move and a retry posts only the failed
       one;
     - an unknown comment listing gives no post;
     - **`SHIPPED_EARLIER`, with no catch-up**: the record stays pending, zero
       post calls, and the printed retry command is exactly
       `ait release-notify --tag <E>`. Running that printed command (fully
       gated) posts "Released in <E>" once, and a second run posts nothing;
     - **designation** (`hostname` shim):
       - unset → `INCOMPLETE:designation:unset`, no post, the hint carries
         the key line;
       - another host → `INCOMPLETE:designation:not_designated:…`, no post;
       - an invalid value → `unknown`, no post;
       - a match → posts;
       - `--dry-run` reports `DESIGNATION:` without requiring it;
     - **direct invocation against a missing release** (the stub's `gh
       release view` returns 404) and **against a draft release**:
       `INCOMPLETE:not_published:pending:no_release|draft`, exit 3, zero
       post calls, records still pending. `--dry-run` still lists `DUE:` with
       `PUBLICATION:pending:…`;
     - a remote tag at another sha → `failed:tag_mismatch`, no post;
     - **an existing non-draft release with the policy configured**, invoked
       directly and through the `SHIPPED_EARLIER` recovery form `--tag E`.
       Each of the following posts nothing, exits 3 and keeps the records
       pending:
       - (a) the workflow run is still in progress →
         `pending:run_in_progress`;
       - (b) the run concluded `failure` →
         `failed:workflow_failed:failure`;
       - (c) the run succeeded but the `.deb` / `.rpm` are missing →
         `pending:assets_missing:…`;
       - (d) a SHA256SUMS asset lists a binary that is not uploaded →
         `pending:assets_missing:<binary>`;
       - (e) a policy key with an unknown placeholder →
         `unknown:policy_unreadable`.
       The same release with every condition met posts once;
     - **no policy configured** (another project): only the generic checks
       apply, and it posts once the non-draft release exists. The assertion
       confirms that no framework asset names are required.
   - `test_release_notify_branch_mode.sh` uses a **real separate task-data
     worktree** from `tests/lib/sync_fixture.sh` (bare remote plus a
     branch-mode clone with `.aitask-data`). Trace its `setup_repo` before
     reusing it. Cases:
     - **failed fetch**: origin repointed to a removed path →
       `INCOMPLETE:freshness:unknown:fetch_error`, exit 3, zero post calls,
       records pending, recovery line printed;
     - **behind**: a second clone pushes a new pending record → `behind:1`,
       no post;
     - **`count_failed`**: `rev-list` forced to fail through a git shim →
       non-fresh. This is the control proving the check never falls back to
       0;
     - **failed reconciliation**: the wrapper's `./ait sync --batch` hits
       `CONFLICT` (both clones edit the same task file) and, separately,
       `NO_NETWORK` (origin removed) → `RECONCILE_FAILED`, exit 5, nothing
       posted, `RETRY:` printed;
     - **fresh**: posts once.
   - `test_wait_release_and_notify.sh` uses a scenario-scripted `gh` stub. Its
     JSON shapes are taken from real captured `gh run list` / `gh release
     view` output, and a bare repo acts as origin. Cases:
     - **delayed publication**: no run, then in progress, then success;
       release 404, then draft, then complete; posts once;
     - **workflow failure**: exit 2, nothing posted, records pending, `RETRY:`
       printed;
     - **timeout**: a run stuck in progress, and separately a missing asset;
       exit 3, nothing posted;
     - **retries**: a retry after a failed run that was later re-run
       successfully posts. A retry after a partial notification posts only
       the remainder, with no duplicate comment;
     - a run for the same tag with a different sha is ignored;
     - **non-designated machine**: exit 5 before polling (the stub logs zero
       `run list` calls), nothing posted, the message names the designated
       host;
     - **sequential retries do not duplicate**: run, fail part-way, retry,
       retry again. Each issue gets exactly one marker comment, which the
       stub's comment store counts. The test name and comments state the
       guarantee is for serialised and sequential runs, not concurrent
       multi-machine runs.

### Post-phase (risk mitigations)

1. [pin_release_asset_contract] Add a contract test, either inside
   `tests/test_wait_release_and_notify.sh` or as
   `tests/test_release_asset_contract.sh`.
   - It extracts the asset names the workflows publish:
     - the `files:` entries of both `softprops/action-gh-release` steps in
       `.github/workflows/release.yml`;
     - the `gh release upload` targets in
       `.github/workflows/release-packaging.yml`.
   - It also takes one `<cmd>_{version}_SHA256SUMS.txt` per
     `goengines/cmd/<cmd>`.
   - It asserts that the framework repo's `release_publication_assets`
     (instantiated for a sample version by the shared template function) plus
     `release_publication_checksum_manifests` cover exactly that set.
     `goengines/dist/*` maps to the SUMS-listed binaries through the
     manifest glob.
   - It asserts `release_publication_workflow` names `release.yml`, and that
     `release.yml` still calls `release-packaging.yml` inside the same run,
     so the run conclusion covers packaging.
   - A mutation control adds a fake `files:` line to a copy of the workflow
     and expects the test to fail.

## Step 9 reference

Each child follows task-workflow Step 9: commit, archive, push. The parent
archives when both children are done.

## Decomposition mechanics (post-approval)

- Create t2261_1 and t2261_2 with the Batch Task Creation Procedure, writing
  each child's section above into its task description: context, files, steps,
  verification.
- Write the child plans `aiplans/p2261/p2261_{1,2}_*.md`, and commit them
  path-scoped.
- Revert the parent to Ready and release its lock.
- Each child plan carries its own copy of the inline phase blocks above:
  `characterize_issue_update_argv` → t2261_1, `pin_release_asset_contract` →
  t2261_2.
- Each child plan also carries the matching `## Risk` bullets, so each child's
  risk gate has its own section.
- The spawned 'after' mitigation `live_gitlab_release_notify_check` goes into
  **t2261_2's** `### Planned mitigations`, so t2261_2's Step 8d creates it.
  The parent never runs Step 8 itself.
- Create the **deferred follow-up** "Automatic catch-up for SHIPPED_EARLIER
  release-notify records" now, as a standalone task, so it is not lost. It
  depends on t2261 and is labelled `release_scripts` / `issue_integration`.
  Its description covers:
  - the current behaviour (records stay pending; the retry command is
    printed);
  - the open design questions: which release a late record belongs to,
    chained catch-up across several skipped releases, and gating each older
    tag's publication;
  - the constraint that every posting path keeps the gate from t2261_2.

## Verification

- `bash tests/test_issue_update_argv.sh`,
  `bash tests/test_issue_update_ledger.sh`, `bash tests/test_release_notify.sh`,
  `bash tests/test_release_notify_branch_mode.sh` and
  `bash tests/test_wait_release_and_notify.sh` all PASS.
- `shellcheck` on the new and changed scripts.
- `./.aitask-scripts/aitask_skill_verify.sh` (t2261_1).
- `check_links.py --build` (t2261_2).
- Manual, read-only: `./.aitask-scripts/aitask_release_notify.sh --dry-run
  --tag v0.40.1` on the real repo lists the expected range and records.

## Risk

### Code-health risk: medium
- Moving the backends into a shared lib and switching GitHub to URL targets
  changes the script that every archival route calls (Step 9, pickrem,
  web-merge). A regression breaks issue closing at archival. · severity: low
  (residual — addressed by inline pre-phase characterize_issue_update_argv) ·
  → mitigation: inline pre-phase characterize_issue_update_argv
- The new exit 3 (ledger failed after a successful update) could lead a
  caller that retries any non-zero exit to re-run the full command and post
  the resolution comment twice. Covered in the plan by the printed
  `--record-only` hint and the `issue-update.md` note (t2261_1 steps 3 and 5).
  · severity: medium · → mitigation: none (in plan)
- Records build up in every user project's data branch, including projects
  that never run `release-notify`. They are tiny files, and `--list` shows
  them. · severity: low · → mitigation: none
- Same-file overlap with t2251 (Bitbucket retirement). · severity: low ·
  → mitigation: none (note to t2251, t2261_1 step 7)

### Goal-achievement risk: medium
- The framework's expected release assets are declared in its
  `project_config.yaml` policy. Drift from `release.yml` /
  `release-packaging.yml` (a renamed or added asset) would make every gate
  run time out, and no notification would ever be posted.
  · severity: low (residual — addressed by inline post-phase
  pin_release_asset_contract) · → mitigation: inline post-phase
  pin_release_asset_contract
- The GitLab path (`glab api --paginate` notes listing, `glab issue note`) is
  verified only against stubs. A misread listing would miss the marker and
  post duplicate comments. · severity: medium · → mitigation:
  live_gitlab_release_notify_check
- If `release-notify` was skipped for a release, records whose commits all
  shipped before the previous tag stay pending. They are reported as
  `SHIPPED_EARLIER` with the exact safe retry command. Automatic catch-up is
  deferred to a follow-up task (accepted scope). · severity: low ·
  → mitigation: none (deferred follow-up task)
- Duplicate prevention covers serialised runs on the designated machine and
  sequential retries only. A bypassed or mid-run-reassigned designation, a
  lagging comment listing, or a hand-edited marker can still produce a
  duplicate. This is accepted scope, documented, with no distributed
  locking. · severity: low · → mitigation: none
- Requiring a published release object means a project that cuts tags
  without creating platform releases can never post release notices. This is
  by design: the comment links to the release page, so it must exist. It
  will be documented. · severity: low · → mitigation: none
- Three new user-facing `project_config.yaml` keys widen the config surface.
  This is justified because the policy is project-specific by request, and a
  mis-saved key fails closed (`policy_unreadable`), never open. · severity:
  low · → mitigation: none

Reassessment after inline insertion: code-health stays **medium**, because
the exit-3 double-post risk remains. Goal-achievement stays **medium**,
because the GitLab live check is a spawned 'after' task and has not run when
this plan is implemented.

### Planned mitigations
- timing: pre-phase | name: characterize_issue_update_argv | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: backend extraction / GitHub URL-target regression at archival | desc: Pin gh/glab argv per action on the unmodified aitask_issue_update.sh before extracting the backends (t2261_1)
- timing: post-phase | name: pin_release_asset_contract | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: expected-asset drift making every gate time out | desc: Contract test deriving published asset names from release.yml/release-packaging.yml vs the gate's expected set, with a mutation control (t2261_2)
- timing: after | name: live_gitlab_release_notify_check | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: GitLab notes-listing misread causing duplicate release comments | desc: Live-check ait release-notify's GitLab path (glab api --paginate notes, glab issue note, re-run idempotency) against the local GitLab CE harness and replace hand-written glab stubs with captured output
