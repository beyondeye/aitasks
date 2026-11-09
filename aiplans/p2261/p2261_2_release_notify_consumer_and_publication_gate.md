---
Task: t2261_2_release_notify_consumer_and_publication_gate.md
Parent Task: aitasks/t2261_release_issue_notifications.md
Sibling Tasks: aitasks/t2261/t2261_1_*.md
Archived Sibling Plans: aiplans/archived/p2261/p2261_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2261_2 — Release-notify consumer, publication gate, release integration, docs

## Context

This is the consumer half of t2261. t2261_1 records one `.rec` file per
resolved issue under `aitasks/metadata/release_issues/pending/`, and adds the
shared `lib/issue_backends.sh` and `lib/release_issue_ledger.sh`.

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
- no automatic catch-up (that is t2266);
- duplicate prevention covers serialised and sequential runs only, and is
  never claimed as exactly-once.

Before the first edit, re-read t2261_1's archived plan
(`aiplans/archived/p2261/p2261_1_*.md`) for the shipped function names and
outputs.

## Implementation

1a. **Attested data freshness**: `ril_data_freshness` in
   `lib/release_issue_ledger.sh`.
   - Do **not** use `desync_state.py`. Its `count_ahead_behind` returns `0,0`
     when `rev-list` fails, which reads as a silent all-clear.
   - Select the ref and worktree by mode, from `ait_data_mode`:
     - branch mode: ref `aitask-data`, git via `task_git`;
     - legacy mode: ref = the current branch, git in the repo root;
     - a detached HEAD in legacy mode → `unknown:detached`.
   - Steps, checking every rc:
     - `remote get-url origin` fails → `unknown:no_remote`;
     - `fetch --quiet origin <ref>` fails → `unknown:fetch_error`;
     - `rev-parse --verify --quiet refs/heads/<ref>` or
       `refs/remotes/origin/<ref>` fails → `unknown:missing_ref`;
     - `rev-list --count <ref>..origin/<ref>` fails, or does not print
       `^[0-9]+$` → `unknown:count_failed`;
     - a count above 0 → `behind:<n>`;
     - a count of 0 → `fresh`.
   - Prints one state line. rc 0 only for `fresh`.
1b. **Publication policy and check**: new shipped
   `.aitask-scripts/lib/release_publication.sh`.
   - Policy keys: top-level, optional, in `aitasks/metadata/project_config.yaml`:
     - `release_publication_workflow`: string, a GitHub workflow file name;
     - `release_publication_assets`: a string or a list of templates. Only
       `{tag}` and `{version}` are allowed (`version` = tag minus a leading
       `v`), and each substituted name must match `^[A-Za-z0-9._+-]+$`;
     - `release_publication_checksum_manifests`: a string or a list of globs.
   - Reading the policy:
     - detect the keys by a line-start grep;
     - if none is present → generic policy, no Python needed;
     - otherwise parse with the framework Python (`lib/python_resolve.sh` →
       `require_python`, YAML through the venv) and validate the types;
     - any failure → `unknown:policy_unreadable:<key>`. That covers Python
       missing, a block mapping where a scalar or list is expected, an
       unknown placeholder and an invalid name. It never degrades to
       generic.
   - `release_publication_check <tag>` makes one non-waiting check and prints
     exactly one line:
     - `PUBLICATION:published|<run-id or ->` → rc 0;
     - `PUBLICATION:pending:<r>` → rc 10, where `<r>` is one of
       `no_release`, `draft`, `upcoming`, `run_not_found`,
       `run_in_progress`, `assets_missing:<csv>`, `manifest_missing:<glob>`;
     - `PUBLICATION:failed:<r>` → rc 11, where `<r>` is one of
       `workflow_failed:<conclusion>`, `tag_mismatch`, `remote_tag_missing`;
     - `PUBLICATION:unknown:<r>` → rc 12, where `<r>` is one of
       `api_error`, `unparseable`, `cli_missing`,
       `policy_unreadable:<key>`, `workflow_unsupported`.
   - The checks run in this order:
     1. **Remote tag**: `git ls-remote --tags origin "refs/tags/T"` and
        `"refs/tags/T^{}"`. Prefer the peeled sha. It must equal
        `git rev-parse "T^{commit}"`.
     2. **Platform**: from the origin remote (`detect_platform`), and the
        slug from the remote URL. Handle both the ssh (`git@host:o/r.git`)
        and https forms.
     3. **GitHub release**: `gh release view T -R <slug> --json
        tagName,isDraft,assets`. Distinguish a 404 (`release not found` in
        stderr → `pending:no_release`) from other failures (`unknown:api_error`).
        Then `tagName==T` and `!isDraft`.
     4. **GitLab release**: `glab api "projects/<urlenc slug>/releases/T"`.
        A 404 → `pending:no_release`. `upcoming_release==true` →
        `pending:upcoming`. A configured workflow → `unknown:workflow_unsupported`.
     5. **Workflow (GitHub)**: `gh run list -R <slug> --workflow F --event
        push --branch T --json databaseId,headSha,headBranch,status,conclusion,createdAt
        --limit 50`.
        - Filter `headBranch==T && headSha==<tag sha>`, then take the max
          `databaseId`.
        - None → `pending:run_not_found`.
        - Not `completed` → `pending:run_in_progress`.
        - `conclusion != success` → `failed:workflow_failed:<c>`.
        - Use `gh --jq` for parsing, so `jq` is not required on GitHub.
     6. **Assets**: for each required name, require present +
        `state==uploaded` + `size>0` (GitHub), or present in
        `assets.links[].name` (GitLab). For each manifest glob:
        - match it against asset names with bash pattern matching;
        - zero matches → `pending:manifest_missing:<glob>`;
        - otherwise, for each match, `gh release download T -R <slug> -p
          <name> -O -`;
        - parse `^[0-9a-f]{64}[ ][ *](.+)$` lines; any other non-blank line
          → `unknown:unparseable`;
        - every listed file must be a present, uploaded, non-empty asset.
        All missing names are collected into one `assets_missing:<csv>`.
   - Registration:
     - `.aitask-scripts/settings/settings_app.py` key-registry entries for
       the three keys plus `release_notify_host`;
     - `seed/project_config.yaml`: commented generic examples
       (`myapp-{tag}.tar.gz`, `release.yml`, `*_SHA256SUMS.txt`) and
       `release_notify_host: <hostname>`;
     - check for a registry ↔ seed parity test, and read
       `aidocs/framework/aitasks_extension_points.md` first;
     - framework repo values in `aitasks/metadata/project_config.yaml`,
       committed with `./.aitask-scripts/aitask_metadata_commit.sh
       aitasks/metadata/project_config.yaml`:
       - `release_publication_workflow: release.yml`;
       - `release_publication_assets`: `aitasks-{tag}.tar.gz`, `ait`,
         `aitasks_{version}_all.deb`, `aitasks-{version}-1.noarch.rpm`,
         `ait-testmap_{version}_SHA256SUMS.txt`;
       - `release_publication_checksum_manifests`: `*_SHA256SUMS.txt`;
       - `release_notify_host: <this machine's hostname>`.
1c. **Designation**: `release_notify_designation` in the ledger lib.
   - Read the `release_notify_host` scalar (same reader rules; it must match
     `^[A-Za-z0-9._-]+$`).
   - Compare it byte-exact with `hostname`. A failing or empty `hostname`
     command → `unknown:hostname`.
   - States:
     - `designated:<h>` → rc 0;
     - `not_designated:<d>|<this>` → rc 1;
     - `unset` → rc 1;
     - `unknown:<r>` → rc 1.
   - The mutual exclusion for a run is the local lock
     `ait_ledger_lock_acquire release_notify run`. Nothing distributed.
1. **Comment listing (tri-state)** in `lib/issue_backends.sh`.
   - GitHub, `github_list_comment_bodies <url>`: parse
     `https://<host>/<owner>/<repo>/issues/<n>`, then
     `gh api --paginate [--hostname <host> if not github.com]
     "repos/<o>/<r>/issues/<n>/comments" --jq '.[].body'`.
   - GitLab, `gitlab_list_comment_bodies <url>`:
     `glab api --paginate "projects/<urlenc slug>/issues/<iid>/notes?per_page=100"`
     piped to `jq -r '.[].body'`. This handles glab printing one array per
     page.
   - rc 0 with the bodies on stdout; any failure → non-zero, which means
     **unknown**, never absent.
2. **Consumer**: new `.aitask-scripts/aitask_release_notify.sh [--tag T]
   [--prev-tag P] [--dry-run] [--list] [--no-push]`, plus the dispatcher
   case `release-notify) shift; exec "$SCRIPTS_DIR/aitask_release_notify.sh"
   "$@" ;;` and a help line in `ait`.
   - **Inputs and records:**
     - `T` defaults to `git tag --list 'v*' --sort=-version:refname | head -1`.
     - `P` defaults to the next lower `v*` tag, or none (all history).
     - Validate that both resolve to commits.
     - Read every pending `.rec` with `ril_read`. An invalid record →
       `MALFORMED:<path>|<field>`, and it is skipped from processing (still
       reported).
   - **Classifying records** (one `git log --format='%H%x09%s' P..T` call,
     plus one `git log ... P` call):
     - map parent id `P` → the commit tags `(tP)` and `(tP_<n>)`; child id
       `P_C` → `(tP_C)` only;
     - due if any mapped commit is in `P..T`;
     - else, if mapped commits are reachable from `P` →
       `SHIPPED_EARLIER:<task>|<url>|<E>`, where
       `E = git tag --contains <newest mapped sha> --list 'v*'
       --sort=version:refname | head -1`. Print the exact safe retry command
       `ait release-notify --tag <E>`. Keep the record pending, with **no
       catch-up** (t2266);
     - else `PENDING:<task>|<url>|no_commits`;
     - a platform other than github or gitlab →
       `UNSUPPORTED:<task>|<url>|<platform>`.
   - **Posting gate**, when there are due records and this is not
     `--dry-run` or `--list`:
     1. `ril_data_freshness`;
     2. `release_notify_designation`;
     3. the run lock `ait_ledger_lock_acquire release_notify run …`;
     4. `release_publication_check T`.

     Any failure prints `INCOMPLETE:freshness:<s>`,
     `INCOMPLETE:designation:<s>` or `INCOMPLETE:not_published:<line>`, with
     a recovery hint, and exits 3. Nothing is posted.
     - Freshness hint: "run ./ait sync (resolve any conflict), then re-run
       `<same command>`".
     - Designation hint: "notifications run only on `<d>`", or, when unset,
       "add `release_notify_host: <this hostname>` to
       aitasks/metadata/project_config.yaml".
     `--dry-run` and `--list` print `FRESHNESS:`, `DESIGNATION:` and
     `PUBLICATION:` as information only.
   - **Per due record:**
     - The marker is `<!-- aitask-release:T t<task> -->`.
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
         `<short sha> <subject>` per mapped commit in `P..T`.
     - Release URL: GitHub `https://<host>/<slug>/releases/tag/T`; GitLab
       `https://<host>/<slug>/-/releases/T`.
     - A post failure → `FAILED:…|post_failed`.
     - On success:
       - under the `release_issues ledger` lock, write
         `released/T/<name>` = the original fields + `released_tag`,
         `notified_at`, `outcome`, and `commits=<full shas csv>`;
       - remove the pending file;
       - commit both paths with `ait_commit_paths_staging_untracked "ait:
         Record release notice for t<task> (T)" <released> <pending>`;
       - if the commit fails, restore the pending file, remove the released
         one, and report `FAILED:…|commit_failed`. A retry then finds the
         marker and moves the record;
       - print `POSTED:` or `ALREADY_NOTIFIED:` with the released path.
   - **End of run:**
     - unless `--no-push` or nothing was committed: `task_push` →
       `PUSH:ok|failed`;
     - `SUMMARY:posted=… already=… pending=… shipped_earlier=… failed=…
       malformed=…`.
   - **Exit:**
     - 0 = complete;
     - 1 = usage;
     - 2 = refused input;
     - 3 = incomplete (nothing posted);
     - 4 = partial (≥1 `FAILED`).
   - **`--list`:** pending records, then `released/<tag>/` grouped by tag.
3. **Wrapper**: new framework-only `wait_release_and_notify.sh <tag>
   [--timeout S] [--interval S]` at the repo root.
   - Defaults: 1800s / 20s. Env overrides: `AIT_RELEASE_WAIT_TIMEOUT`,
     `AIT_RELEASE_POLL_INTERVAL`.
   - `cd` to its own directory. Source the libs from `.aitask-scripts/lib/`.
   - Refuse to start (exit 1) unless the policy sets both
     `release_publication_workflow` and `release_publication_assets`.
   - Early designation: if this machine is not designated, print
     "notifications run only on `<d>`: run `./wait_release_and_notify.sh T`
     there" and exit 5, before any `gh` call.
   - Poll `release_publication_check T` until the deadline:
     - `published` → continue;
     - `pending` → print `WAIT:<reason>`, sleep;
     - `failed:workflow_failed:*` → `WORKFLOW_FAILED:<c>`, exit 2;
     - any other `failed` or `unknown` → `WAIT:<line>` and keep polling (it
       may be transient);
     - the deadline passes → `TIMEOUT:<last line>`, exit 3.
   - Reconciliation, branch mode only: run `./ait sync --batch` and take its
     single line.
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

   No prompt.
5. **Docs** (current state only, per
   `aidocs/framework/documentation_conventions.md`):
   - `website/content/docs/commands/issue-integration.md`, new section
     "Release notifications". It covers:
     - the ledger (location, record fields, lifecycle pending → `released/<tag>/`,
       `RELEASE_LEDGER*` outputs, the `--record-only` recovery);
     - `ait release-notify`: options, output lines, exit codes, rolling
       semantics, the marker, and `SHIPPED_EARLIER` with no catch-up;
     - the posting gate: freshness, designation, publication;
     - the policy keys, with a generic example;
     - `release_notify_host`, with the deliberate reassignment steps:
       1. make sure no run is in progress on the old machine;
       2. set the new hostname with `ait settings` or by editing the file and
          running `aitask_metadata_commit.sh`;
       3. `./ait sync` on both machines.

       State plainly that there is no automatic failover;
     - the duplicate-prevention scope, worded as in the parent Context.
   - `website/content/docs/workflows/issue-tracker.md`: a short step about
     release notifications, linking with `{{< relref >}}`.
   - Run `cd website && python3 check_links.py --build`.
6. **Tests**:
   - `tests/test_release_notify.sh` uses a legacy-mode fixture:
     - a bare origin, tags `v1.0.0` and `v1.1.0`, `(tN)` commits;
     - `.rec` files written with `ril_record`'s format;
     - `gh` stub with a file-backed comment store and per-scenario
       release/run responses;
     - `hostname` shim.
     It covers every case listed in the parent plan, "Child t2261_2" step 6,
     first bullet:
     - due vs no commits;
     - child commits under a parent;
     - a marker already present;
     - the move into `released/<tag>/`;
     - `--dry-run`;
     - a partial post failure, then a retry;
     - an unknown comment listing;
     - `SHIPPED_EARLIER` with no catch-up and the exact retry command, then
       the printed command posting once;
     - the designation cases;
     - missing and draft releases;
     - `tag_mismatch`;
     - a non-draft release with the policy configured: (a) run in progress,
       (b) run failed, (c) `.deb`/`.rpm` missing, (d) a SUMS-listed binary
       missing, (e) an unknown placeholder. Each runs both directly and via
       the `--tag E` recovery form, and each posts nothing;
     - the same release, complete → posts once;
     - no policy → the generic checks only.
   - `tests/test_release_notify_branch_mode.sh` uses `tests/lib/sync_fixture.sh`
     (a real `.aitask-data` worktree plus a bare remote). Trace `setup_repo`
     before reusing it. Cases:
     - failed fetch;
     - behind;
     - `count_failed` via a git shim (the control proving there is no 0
       fallback);
     - the wrapper's `RECONCILE_FAILED` on `CONFLICT` and on `NO_NETWORK`;
     - fresh → posts once.
   - `tests/test_wait_release_and_notify.sh` uses a scenario-scripted `gh`.
     Its JSON shapes are copied from the real captures in the t2261_2 task
     description. Cases:
     - delayed publication;
     - workflow failure;
     - timeout (stuck run; missing asset);
     - a retry after a failed run that was later re-run successfully;
     - a retry after a partial notification;
     - a run with a different sha ignored;
     - a non-designated machine → exit 5 with zero `run list` calls;
     - sequential retries → exactly one marker comment per issue. Comments
       state the scope: serialised and sequential runs, not concurrent
       multi-machine runs.
   - Use small `--timeout` / `--interval` values. Assert outcomes, never
     exact poll counts.

## Post-phase (risk mitigations)

1. [pin_release_asset_contract] Add a contract test, either inside
   `tests/test_wait_release_and_notify.sh` or as
   `tests/test_release_asset_contract.sh`.
   - It extracts the published names:
     - the `files:` entries of both `softprops/action-gh-release` steps in
       `.github/workflows/release.yml`;
     - the `gh release upload` targets in
       `.github/workflows/release-packaging.yml`;
     - one `<cmd>_{version}_SHA256SUMS.txt` per `goengines/cmd/<cmd>`.
   - It instantiates the framework policy's `release_publication_assets` for
     a sample version, using the shared template function.
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
  `bash tests/test_release_notify_branch_mode.sh` and
  `bash tests/test_wait_release_and_notify.sh` pass, along with the contract
  test.
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

Commit the code (`feature: … (t2261_2)`), the plan, and the framework
`project_config.yaml` values (via `aitask_metadata_commit.sh`). Then archive
through task-workflow Step 9. The parent t2261 auto-archives once this is
the last child.

## Risk

### Code-health risk: medium
- New shipped consumer + lib + three wrapper paths, plus four new
  `project_config.yaml` keys: a wide surface. A mis-saved key fails closed
  (`policy_unreadable`). · severity: medium · → mitigation: none (fail-closed
  design + tests)
- `create_new_release.sh` now blocks for up to the timeout and exits non-zero
  when notification is incomplete, after a successful push. · severity: low
  · → mitigation: none (clear message + retry command)

### Goal-achievement risk: medium
- Drift of the framework's declared assets from `release.yml` /
  `release-packaging.yml` would make every gate time out. · severity: low
  (residual — addressed by inline post-phase pin_release_asset_contract) ·
  → mitigation: inline post-phase pin_release_asset_contract
- The GitLab path (`glab api --paginate` notes, `glab issue note`, GitLab
  releases API) is verified only against stubs. A misread listing could miss
  the marker and duplicate a comment. · severity: medium · → mitigation:
  live_gitlab_release_notify_check
- Duplicate prevention covers serialised runs on the designated machine and
  sequential retries only (accepted scope; documented). · severity: low ·
  → mitigation: none
- `SHIPPED_EARLIER` records need a manual retry, because there is no
  catch-up (accepted scope). · severity: low · → mitigation: none (t2266)

### Planned mitigations
- timing: post-phase | name: pin_release_asset_contract | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: expected-asset drift making every gate time out | desc: Contract test deriving published asset names from release.yml/release-packaging.yml vs the framework publication policy, with a mutation control (t2261_2)
- timing: after | name: live_gitlab_release_notify_check | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: GitLab notes-listing misread causing duplicate release comments | desc: Live-check ait release-notify's GitLab path (glab api --paginate notes, glab issue note, releases API, re-run idempotency) against the local GitLab CE harness and replace hand-written glab stubs with captured output
