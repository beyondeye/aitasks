---
Task: t1599_1_scope_pick_own_claim_commit.md
Parent Task: aitasks/t1599_scope_task_data_commits_to_their_own_paths.md
Sibling Tasks: aitasks/t1599/t1599_2_*.md, aitasks/t1599/t1599_3_*.md, aitasks/t1599/t1599_4_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# p1599_1 — Scope the claim commit in `aitask_pick_own.sh`

## Context

Highest-frequency site of the t1599 defect: `aitask_pick_own.sh` runs on **every
task claim**, and **83 of the last 300** `ait: Start work on t…` commits on the
live `aitask-data` branch (28%) carry a foreign task file. Worst case
`c1427200b` (claiming t1405) swallowed **178** foreign files — an `ait board`
boardidx reshuffle landing under an unrelated claim.

Owns `.aitask-scripts/aitask_pick_own.sh` exclusively. See the task file for the
full rationale and reference patterns.

## Step 1 — Pre-phase (risk mitigations)

**`partial_commit_worktree_semantics`** — run before any scoping edit.

`git commit -m <msg> -- <paths>` is a **partial** commit: it takes those paths'
**worktree** content and ignores their index entry. The other three children
inherit this pattern, so pin the semantic before propagating it.

Add to `tests/test_pick_own_scoped_commit.sh`: stage the task file, modify it
again on disk, claim, and assert which version landed in the commit. State the
answer in the test's header comment.

## Step 2 — Scope `commit_and_push()` (`:360-373`)

Replace the body per the task file. Three things are load-bearing:

1. `task_git add -- "${paths[@]}"` — needed **only** so an untracked path can be
   named; a pathspec cannot match a file git does not know about.
2. `task_git commit -m <msg> --quiet -- "${paths[@]}"` — `-m` **before** `--`, or
   git reads the message as a path.
3. An **empty-`paths` guard**. `git commit --` with no pathspec commits the whole
   index, silently re-creating the exact bug being fixed.

Also scope the no-op guard at `:366`: today's `task_git diff --cached --quiet`
has no pathspec, so unrelated staged content from another session decides whether
the claim commits at all. Use `task_git status --porcelain -- "${paths[@]}"`
(the `aitask_gate.sh:1025-1032` shape).

## Step 3 — Thread the paths from the call site (`:475`)

Exactly two data-branch paths are written by a claim: the task file
(`resolve_task_file`, resolved at `:396`) and `aitasks/metadata/emails.txt`
(`EMAILS_FILE` at `:68`, written by `store_email` at `:232-237`).

Nothing else — lock artifacts are blobs on the orphan `aitask-locks` branch,
`.aitask-gates/` is gitignored and written after the commit, and `active_gates`
is committed separately by an already-scoped helper.

Build the array conditionally: `:396` ends with `|| true` so `task_file` can be
empty, and `emails.txt` exists only when an email resolved.

## Verification

New `tests/test_pick_own_scoped_commit.sh` — **nothing asserts this commit
today** (`grep -rn 'Start work on t' tests/` → zero hits).

- Fixture: `setup_paired_repos` from `tests/test_lock_force.sh:37-91`.
- Seed and commit a bystander `aitasks/t2_bystander.md`, then leave it dirty.
- Claim t1; assert (`tests/test_gate_record.sh:83-96` idioms) the subject, that
  `git show --name-status --pretty=format: -M0 HEAD` contains **only** t1's
  paths, and that the bystander is still ` M` unstaged
  (`tests/test_archive_no_overbroad_add.sh:154-167` shape).
- Claim with no email → no `emails.txt` in the commit.
- Idempotent re-claim → no new commit (`rev-list --count`,
  `tests/test_gate_record.sh:100-107`).
- Step 1's characterization assertions.

**Negative control (required):** the bystander assertion must FAIL against the
pre-fix `task_git add aitasks/`. A test that passes today proves nothing.

`shellcheck .aitask-scripts/aitask_pick_own.sh`.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.
