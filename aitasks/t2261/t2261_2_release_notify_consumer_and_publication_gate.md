---
priority: medium
effort: high
depends: [t2261_1]
issue_type: feature
status: Implementing
labels: [release_scripts, bash_scripts, issue_integration]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2261
created_at: 2026-11-09 23:13
updated_at: 2026-11-10 12:42
---

## Context

Child 2 of t2261 (release-time issue notifications). t2261_1 builds the
writer: every successful issue update records a ledger entry under
`aitasks/metadata/release_issues/pending/`. This child builds the
**consumer**. After a release is verifiably published, it comments
"Released in vX.Y.Z" on each pending issue whose task commits are in the new
tag, then moves each record to `released/<tag>/`. It also wires this into the
framework's local release command.

**The authoritative design is `aiplans/p2261_release_issue_notifications.md`**
(Context decisions, "Ledger contract", "Child t2261_2"). The child plan
`aiplans/p2261/p2261_2_*.md` carries the step-by-step detail. Decisions taken
with the user during t2261 planning, not to be reopened:

- Notification is automatic after a successful publication, with no
  confirmation prompt. If the workflow fails or the wait times out, nothing is
  posted, records stay pending, and the exact retry command is printed.
  Retries check again, never double-post, and partial progress is kept per
  record.
- **Every posting entry point** runs the same gate, `ait release-notify`
  included: attested data freshness → designated machine → publication.
  Unknown means nothing is posted, `INCOMPLETE:` is reported, and the exit is
  3.
- The publication policy is per project, in `project_config.yaml`
  (`release_publication_workflow`, `release_publication_assets`,
  `release_publication_checksum_manifests`). It is read on every path, with
  no caller flags. Other projects get only the generic checks: tag match, and
  a release that exists, is not a draft and is not upcoming.
- One designated notification machine (`release_notify_host`), compared
  byte-exact with `hostname`, plus the local run lock. No distributed locking
  and no failover; reassignment is a deliberate, documented edit.
- No automatic catch-up. A `SHIPPED_EARLIER` record stays pending, and the
  exact safe retry command is printed. Catch-up is a separate follow-up task.
- Duplicate prevention covers serialised runs on the designated machine and
  sequential retries. It is **not** an unconditional exactly-once guarantee;
  never claim more.

## Key files

- New `.aitask-scripts/aitask_release_notify.sh` plus the `ait
  release-notify` dispatcher case and help line. It is not skill-invoked, so
  it needs no whitelist entries (`aidocs/framework/aitasks_extension_points.md`).
- `.aitask-scripts/lib/release_issue_ledger.sh` (from t2261_1): add the move
  helper, `ril_data_freshness` and `release_notify_designation`.
- New shipped `.aitask-scripts/lib/release_publication.sh`:
  `release_publication_check <tag>`, which emits `PUBLICATION:`
  published / pending / failed / unknown and reads the policy, failing closed.
- `.aitask-scripts/lib/issue_backends.sh` (from t2261_1): tri-state
  `github_list_comment_bodies` / `gitlab_list_comment_bodies`.
- New framework-only `wait_release_and_notify.sh` (repo root, not shipped)
  and `create_new_release.sh`: run it after the push, no prompt.
- `.aitask-scripts/settings/settings_app.py` key entries,
  `seed/project_config.yaml` commented generic examples, and the framework
  repo's own `aitasks/metadata/project_config.yaml` values (committed with
  `aitask_metadata_commit.sh`).
- Website: `website/content/docs/commands/issue-integration.md` and
  `website/content/docs/workflows/issue-tracker.md`. Then `check_links.py
  --build`.
- New tests: `tests/test_release_notify.sh`,
  `tests/test_release_notify_branch_mode.sh` (real `.aitask-data` worktree
  via `tests/lib/sync_fixture.sh`), `tests/test_wait_release_and_notify.sh`,
  and the post-phase asset contract test.

## Reference files

- Real `gh` output captured during planning (keep the stub shapes faithful):
  - `gh run list --workflow release.yml --json
    databaseId,headSha,headBranch,event,status,conclusion,createdAt,updatedAt`
    gives `headBranch` = the tag (for example `v0.40.1`) and `headSha` = the
    tagged commit. Real runs take about 3.5 minutes.
  - `gh release view v0.40.1 --json tagName,isDraft,assets` gives assets
    `ait`, `ait-testmap_0.40.1_{darwin,linux}_{amd64,arm64}`,
    `ait-testmap_0.40.1_SHA256SUMS.txt`, `aitasks-0.40.1-1.noarch.rpm`,
    `aitasks-v0.40.1.tar.gz` and `aitasks_0.40.1_all.deb`, each with `size`
    and `state: "uploaded"`.
- `.github/workflows/release.yml`: the `release` job creates the non-draft
  release, then the `packaging` job (`release-packaging.yml`) uploads the
  `.deb` and `.rpm`. The release object therefore exists before packaging
  finishes, which is why the workflow-run check is part of the policy.
- `.aitask-scripts/aitask_sync.sh` batch tokens; `lib/task_utils.sh`
  (`task_push`, `ait_data_mode`, `task_git`); `lib/ledger_block.sh`.
- `.aitask-scripts/aitask_changelog.sh` (`get_latest_tag`, the
  `(t<id>)` grep).
- Memory notes: "Widened reads keep partial positive evidence" (paginated
  comment listing is tri-state) and "All-clear = positive, attested
  evidence". `desync_state.py`'s `count_ahead_behind` returns 0,0 on failure,
  so it is not used.

## Implementation plan

The steps are in the parent plan, "Child t2261_2", 1a–6, plus the post-phase:

- 1a attested freshness;
- 1b publication policy + check;
- 1c designation;
- 1 comment listing;
- 2 consumer;
- 3 wrapper (polls the shared check, then requires `ait sync --batch`
  success, then runs the consumer);
- 4 `create_new_release.sh`;
- 5 docs (including how to reassign the designated host, and the honest
  duplicate-prevention scope);
- 6 tests: delayed publication, workflow failure, timeout, retries, missing
  and draft releases, a non-draft release with an incomplete or failed
  workflow and missing assets, failed fetch, failed reconciliation, the
  designation cases, and `SHIPPED_EARLIER` without catch-up;
- post-phase [pin_release_asset_contract]: the workflow-derived asset set
  must equal the framework policy, with a mutation control.

The planned 'after' mitigation, created at this child's Step 8d:
`live_gitlab_release_notify_check` (the GitLab path against the local GitLab
CE harness; replace the hand-written glab stubs with captured output).

## Verification

- `bash tests/test_release_notify.sh`, `bash tests/test_release_notify_branch_mode.sh`
  and `bash tests/test_wait_release_and_notify.sh` pass, along with the asset
  contract test.
- `shellcheck` on the new and changed scripts.
- `cd website && python3 check_links.py --build`.
- Read-only on the real repo:
  `./.aitask-scripts/aitask_release_notify.sh --dry-run --tag v0.40.1`.
