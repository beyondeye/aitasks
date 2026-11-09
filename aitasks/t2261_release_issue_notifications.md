---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [release_scripts, bash_scripts, issue_integration]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t2261_1, t2261_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-11-09 15:41
updated_at: 2026-11-09 23:13
---

## Problem

The framework can import an issue into a task, and when that task is archived
it posts a "Resolved via aitask tN" comment with plan notes and commit refs
(`aitask_issue_update.sh`; example: https://github.com/beyondeye/aitasks/issues/16
for t2235). There is **no mechanism at release time**: when a new release tag is
cut (`create_new_release.sh` → tag push → `.github/workflows/release.yml`),
nothing tells the resolved issues which release actually ships the fix.

Collecting the issue list at release time is the hard part. The task → `issue:`
mapping is spread across archived task files (most of them inside tar bundles),
child tasks carry their commits under `tP_C` while the issue lives on parent
`tP`, and a **folded** task's `issue:` lives only in the folded file, which
archival deletes (the `FOLDED_ISSUE:` line is printed once and then lost).

## Design (agreed during exploration)

Record each resolved issue in a **rolling ledger**, "issues fixed since the last
release". The script that updates the issue when its task is completed writes the
ledger. The release step consumes it.

### 1. Writer: `aitask_issue_update.sh`

- Every route that comments on or closes an issue goes through this one script:
  primary `issue:`, `PARENT_ISSUE:`, `RELATED_ISSUE:`, `FOLDED_ISSUE:`,
  `FOLDED_RELATED_ISSUE:` (via `--issue-url` + the primary task id). Callers:
  task-workflow Step 9 (`issue-update.md` + the inline FOLDED_* handling in
  `task-workflow/SKILL.md`), `aitask-pickrem`, `aitask-web-merge`. Adding the
  ledger write here covers all of them, folded issues included.
- Append a record **only after the platform call succeeded** (comment posted
  and/or issue closed), for every action: close-with-notes, comment-only,
  close-silently. `--dry-run` never records. "Skip" never reaches the script, so
  it records nothing.
- Record fields: `task_id`, `issue_url`, `platform` (github/gitlab), `action`
  (closed / commented / closed_silent), `recorded_at`. Do **not** freeze commit
  SHAs here: commits can land after archival. Issue #16 / t2235 is the example:
  doc commit 85b688f06 came after the comment.
- Storage: a committed file on the task-data branch under `aitasks/metadata/`
  (name and format decided in planning, e.g. `release_pending_issues.*`). It must
  be shared across clones/machines. Serialize concurrent appends with a lock
  (`lib/stale_lock.sh` or a sibling locking helper) and commit by explicit path
  (`aitask_task_commit.sh` / `aitask_metadata_commit.sh`, never a bare
  `./ait git commit`). Dedupe on an exact (task_id, issue_url) identity.
- A ledger-write failure must not hide a successful issue update. Report it
  loudly with a distinct output line/exit, so the caller can retry the record
  without re-posting the comment.

### 2. Consumer: new shipped release-notify script / `ait` verb

- Input: the new tag (default: latest `v*` tag) and the previous tag.
- For each pending ledger entry: find the task's `(tN)` commits in
  `<prev_tag>..<tag>` (child ids map to the entry recorded under the parent id
  and vice versa, as `aitask_changelog.sh --gather` already does). If any
  commit is reachable from the tag, post one comment on the issue: "Released in
  vX.Y.Z", a link to the release (`…/releases/tag/vX.Y.Z` on GitHub, the
  equivalent on GitLab), and the task's commits included in that release.
- Idempotency: put a hidden marker such as `<!-- aitask-release:vX.Y.Z tN -->`
  in the comment and check the existing comments before posting, so a re-run is
  a no-op.
- Notified entries move from the pending section to a per-release history
  section (keep them, don't delete). Entries whose commits are not reachable from
  the tag stay pending, which is what makes the ledger rolling.
- Reuse the platform backends in `aitask_issue_update.sh`. Extract them into a
  shared lib, or add a mode, rather than writing a parallel backend.
- `--dry-run` lists what would be posted.

### 3. Integration

- `create_new_release.sh` (framework-only) runs the consumer after
  `git push origin main --tags`. The release URL is deterministic, and a
  failure there is non-fatal with a clear rerun hint. Alternatively, defer to an
  explicit manual run once the release workflow has finished; decide in
  planning. CI was considered and rejected: the `release.yml` job has no task
  data, because `aitasks/` is a symlink into the `aitask-data` branch worktree.
- Register the new script per `aidocs/framework/aitasks_extension_points.md`
  (ait dispatcher, whitelists, etc.).
- Optional: `/aitask-changelog` reads the ledger to add "Fixes #N" links to
  changelog entries.
- Website docs: document the ledger and the release notification in the issue
  integration / contribution workflow pages, then run `check_links.py`.

## Out of scope

- Backfilling issues resolved before the ledger existed (explicitly not wanted).

## Coordination

- t2251 (Ready) retires the Bitbucket backend in `aitask_issue_update.sh`, the
  same file. Check its state before editing and gate on it per the shared-file
  rule. Don't add Bitbucket support to the new consumer: the Bitbucket Cloud
  issue API was removed on 2026-08-20 (t2247).

## Tests

- Writer: a record is appended only on platform success, for each action; never
  on `--dry-run` or on a failed platform call (use a stubbed `gh`/`glab`);
  dedupe; concurrent appends under the lock; folded/related routes via
  `--issue-url` record the primary task id.
- Consumer: reachable vs unreachable entries (the latter stay pending); child
  commits under a parent entry; the idempotency marker suppresses a second
  post; history rotation; dry-run posts nothing.
